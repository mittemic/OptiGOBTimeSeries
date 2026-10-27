import ast
import csv
import glob
import json
import os
import re
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from moo.optigob_problem2 import OBJECTIVE_SIGN

RESULTS_DIR = "moo/results"
# Full set of objective keys the optimiser can produce; a given run only
# includes whichever of these were selected on the Scenario Discovery page.
ALL_OBJECTIVES = ["co2e", "hnv", "protein", "hwp"]
LABELS = {
    "co2e": "Net Zero CO2e",
    "hnv": "Biodiversity (HNV)",
    "protein": "Protein Output",
    "hwp": "Harvested Wood Products",
}


def to_display(df: pd.DataFrame) -> pd.DataFrame:
    """Flip maximised objectives (hnv/protein/hwp) back to positive for display.
    The algorithm and CSVs keep them negative (NSGA-II only minimises) — this is
    a display-only transform, applied nowhere near the actual optimisation."""
    d = df.copy()
    for col in d.columns:
        if col in OBJECTIVE_SIGN:
            d[col] = d[col] * OBJECTIVE_SIGN[col]
    return d

# -------------------------
# Page header
# -------------------------

st.title("Scenario Discovery Evaluation")

# -------------------------
# Guard: results must exist
# -------------------------

csv_files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*_pareto.csv")))
if not csv_files:
    st.warning("No optimisation results found. Please run the Scenario Discovery first.")
    if st.button("← Back to Scenario Discovery"):
        st.switch_page("pages/03_Scenario_Discovery.py")
    st.stop()

# -------------------------
# Detect which objectives this run actually optimised, from the CSV header
# -------------------------

with open(csv_files[0], newline="") as _f:
    _header = next(csv.reader(_f))
OBJECTIVES = [c for c in _header if c in ALL_OBJECTIVES]

# -------------------------
# Data loading (cached per run — keyed on a signature of the results directory's
# actual contents, not just the file count. Two different runs can easily produce
# the same number of generation files; keying on count alone let Streamlit's cache
# silently hand back a previous run's dataframe — including its columns — for a
# new run that selected a different set of objectives. mtime changes on every
# write, including generation-by-generation during a single run, and again on
# every fresh run since run_nsga2() rmtree's the results dir first.
# -------------------------

run_sig = max((os.path.getmtime(f) for f in csv_files), default=0.0)


@st.cache_data
def load_all_generations(run_sig: float, objectives: tuple[str, ...]) -> dict[int, pd.DataFrame]:
    pattern = re.compile(r"gen(\d+)_pareto\.csv$")
    gens: dict[int, pd.DataFrame] = {}
    for fpath in glob.glob(os.path.join(RESULTS_DIR, "*_pareto.csv")):
        m = pattern.search(fpath)
        if m:
            gens[int(m.group(1))] = pd.read_csv(fpath, usecols=list(objectives))
    return dict(sorted(gens.items()))


@st.cache_data
def load_generation_with_json(gen: int, run_sig: float) -> pd.DataFrame:
    return pd.read_csv(os.path.join(RESULTS_DIR, f"gen{gen}_pareto.csv"))


@st.cache_data
def compute_all_hypervolumes(run_sig: float, objectives: tuple[str, ...], n_samples: int = 10_000) -> tuple[list, list]:
    """
    Monte Carlo hypervolume approximation (vectorised, fast for large fronts).
    Objectives are normalised to [0, 1] using the global min/max across all generations;
    reference point is 1.1 in every normalised dimension.
    """
    OBJECTIVES = list(objectives)
    gens = load_all_generations(run_sig, objectives)
    if not gens:
        return [], []

    all_data = pd.concat(gens.values())
    g_min = all_data[OBJECTIVES].min().values
    g_range = (all_data[OBJECTIVES].max() - all_data[OBJECTIVES].min()).values
    g_range[g_range == 0] = 1.0  # avoid divide-by-zero

    ref = np.array([1.1] * len(OBJECTIVES))
    box_volume = float(np.prod(ref))

    rng = np.random.default_rng(42)
    samples = rng.uniform(0.0, ref, size=(n_samples, len(OBJECTIVES)))

    gen_numbers, hvs = [], []
    for gen, df in gens.items():
        pts = ((df[OBJECTIVES].values - g_min) / g_range).clip(0, None)
        valid = pts[np.all(pts <= ref, axis=1)]
        if len(valid) == 0:
            hvs.append(0.0)
        else:
            # dominated[i] = True if sample i is dominated by any Pareto point
            # shape broadcast: (n_samples,1,d) >= (1,m,d) → (n_samples,m,d)
            batch = 500
            dominated = np.zeros(n_samples, dtype=bool)
            for start in range(0, n_samples, batch):
                sl = samples[start : start + batch]
                dominated[start : start + batch] = np.any(
                    np.all(sl[:, None, :] >= valid[None, :, :], axis=2), axis=1
                )
            hvs.append(box_volume * dominated.mean())
        gen_numbers.append(gen)

    return gen_numbers, hvs


# -------------------------
# Load data
# -------------------------

generations = load_all_generations(run_sig, tuple(OBJECTIVES))
gen_numbers = sorted(generations.keys())
final_gen = max(gen_numbers)

st.caption(f"{len(gen_numbers)} generations loaded · {len(generations[final_gen])} solutions in final generation")

# -------------------------
# Tabs
# -------------------------

tab1, tab2, tab3 = st.tabs([
    "📊 Pareto Fronts",
    "🔍 Configuration Finder",
    "📈 Hypervolume Indicator",
])

# =========================================================
# TAB 1 – PARETO FRONTS
# =========================================================

with tab1:

    if len(OBJECTIVES) < 2:
        st.info(
            f"This run optimised a single objective ({LABELS[OBJECTIVES[0]]}) — there's no "
            "2-D Pareto front to plot. Use the Configuration Finder tab to inspect solutions."
        )
    else:
        # --- Objective selectors ---
        sel_col1, sel_col2 = st.columns(2)
        with sel_col1:
            x_label = st.selectbox(
                "X-axis objective",
                options=[LABELS[o] for o in OBJECTIVES],
                index=0,
                key="pf_x_obj",
            )
        with sel_col2:
            y_label = st.selectbox(
                "Y-axis objective",
                options=[LABELS[o] for o in OBJECTIVES],
                index=1,
                key="pf_y_obj",
            )

        label_to_key = {v: k for k, v in LABELS.items()}
        obj_x = label_to_key[x_label]
        obj_y = label_to_key[y_label]

        if obj_x == obj_y:
            st.warning("Please select two different objectives.")
        else:
            def _get_sel(event, name: str) -> dict:
                """Safely extract a named Altair selection from a chart event."""
                try:
                    sel = event.selection
                    if sel is None:
                        return {}
                    result = getattr(sel, name, None)
                    if result is not None:
                        return result or {}
                    if isinstance(sel, dict):
                        return sel.get(name, {}) or {}
                except Exception:
                    pass
                return {}

            # --- Chart 1: final generation only ---
            st.divider()
            st.subheader(f"Pareto Front — Generation {final_gen} ({len(generations[final_gen])} solutions)")

            df_final = to_display(generations[final_gen][[obj_x, obj_y]])
            df_final["_idx"] = range(len(df_final))

            sel1 = alt.selection_point(name="sel1", on="click", clear="dblclick", fields=["_idx"])
            chart1 = (
                alt.Chart(df_final)
                .mark_circle(size=60, opacity=0.7)
                .encode(
                    x=alt.X(f"{obj_x}:Q", title=x_label),
                    y=alt.Y(f"{obj_y}:Q", title=y_label),
                    color=alt.condition(sel1, alt.value("#1f77b4"), alt.value("#aec7e8")),
                    tooltip=[
                        alt.Tooltip(f"{obj_x}:Q", title=x_label),
                        alt.Tooltip(f"{obj_y}:Q", title=y_label),
                        alt.Tooltip("_idx:Q", title="Solution #"),
                    ],
                )
                .add_params(sel1)
            )
            event1 = st.altair_chart(chart1, on_select="rerun", use_container_width=True)

            # --- Chart 2: all generations coloured by generation ---
            st.divider()
            st.subheader("Pareto Front Evolution — All Generations")

            gen_dfs = []
            for gen in gen_numbers:
                df_g = to_display(generations[gen][[obj_x, obj_y]])
                df_g["Generation"] = gen
                df_g["_gen_idx"] = range(len(df_g))
                gen_dfs.append(df_g)
            all_gens_df = pd.concat(gen_dfs, ignore_index=True)

            sel2 = alt.selection_point(
                name="sel2", on="click", clear="dblclick", fields=["Generation", "_gen_idx"]
            )
            chart2 = (
                alt.Chart(all_gens_df)
                .mark_circle(size=20, opacity=0.4)
                .encode(
                    x=alt.X(f"{obj_x}:Q", title=x_label),
                    y=alt.Y(f"{obj_y}:Q", title=y_label),
                    color=alt.Color("Generation:Q", scale=alt.Scale(scheme="viridis")),
                    tooltip=[
                        alt.Tooltip(f"{obj_x}:Q", title=x_label),
                        alt.Tooltip(f"{obj_y}:Q", title=y_label),
                        alt.Tooltip("Generation:Q"),
                    ],
                )
                .add_params(sel2)
            )
            event2 = st.altair_chart(chart2, on_select="rerun", use_container_width=True)

            # --- Resolve which point was selected ---
            # Altair selection state is a list of point dicts: [{"_idx": 42}, ...]
            # or a dict of arrays: {"_idx": [42], ...} — handle both defensively.
            def _first_point(sel) -> dict:
                if not sel:
                    return {}
                if isinstance(sel, list):
                    return sel[0] if sel else {}
                if isinstance(sel, dict):
                    # {"field": [val], ...} → {"field": val, ...}
                    return {k: v[0] if isinstance(v, list) and v else v for k, v in sel.items()}
                return {}

            selected_row = None
            selected_gen_num = None

            s1 = _get_sel(event1, "sel1")
            pt1 = _first_point(s1)
            if pt1.get("_idx") is not None:
                idx = int(pt1["_idx"])
                full_df = load_generation_with_json(final_gen, run_sig)
                selected_row = full_df.iloc[idx]
                selected_gen_num = final_gen

            if selected_row is None:
                s2 = _get_sel(event2, "sel2")
                pt2 = _first_point(s2)
                if pt2.get("Generation") is not None and pt2.get("_gen_idx") is not None:
                    sel_gen = int(pt2["Generation"])
                    sel_idx = int(pt2["_gen_idx"])
                    full_df = load_generation_with_json(sel_gen, run_sig)
                    selected_row = full_df.iloc[sel_idx]
                    selected_gen_num = sel_gen

            # --- Display selected configuration ---
            st.divider()
            if selected_row is not None:
                st.subheader(f"Selected Configuration — Generation {selected_gen_num}")

                metric_cols = st.columns(len(OBJECTIVES))
                for m_col, obj in zip(metric_cols, OBJECTIVES):
                    m_col.metric(LABELS[obj], f"{selected_row[obj] * OBJECTIVE_SIGN[obj]:.3e}")

                try:
                    config_dict = ast.literal_eval(selected_row["json"])
                except Exception:
                    config_dict = selected_row["json"]

                with st.expander("Full JSON Configuration", expanded=True):
                    st.json(config_dict)
                    st.download_button(
                        label="Download configuration",
                        data=json.dumps(config_dict, indent=2),
                        file_name=f"solution_gen{selected_gen_num}.json",
                        mime="application/json",
                        key="pf_download_btn",
                    )
            else:
                st.info("Click a point in either chart to view its full configuration.")


# =========================================================
# TAB 2 – CONFIGURATION FINDER
# =========================================================

with tab2:
    st.subheader("Configuration Finder")

    cf_gen = st.select_slider(
        "Generation",
        options=gen_numbers,
        value=final_gen,
        key="cf_gen_slider",
    )

    df_full = load_generation_with_json(cf_gen, run_sig)
    df_full_display = to_display(df_full[OBJECTIVES])

    # --- Objective filter sliders (in display space — positive for maximised goals) ---
    st.divider()
    st.markdown("**Filter by objective range:**")

    filter_cols = st.columns(2)
    filters = {}
    for i, obj in enumerate(OBJECTIVES):
        col_min = float(df_full_display[obj].min())
        col_max = float(df_full_display[obj].max())
        with filter_cols[i % 2]:
            if abs(col_max - col_min) < 1e-12:
                st.caption(f"{LABELS[obj]}: {col_min:.3e} (single value)")
                filters[obj] = (col_min, col_max)
            else:
                lo, hi = st.slider(
                    LABELS[obj],
                    min_value=col_min,
                    max_value=col_max,
                    value=(col_min, col_max),
                    format="%.3e",
                    key=f"cf_{obj}_{cf_gen}",
                )
                filters[obj] = (lo, hi)

    # --- Apply filters (comparing in the same display space as the sliders) ---
    mask = pd.Series([True] * len(df_full), index=df_full.index)
    for obj, (lo, hi) in filters.items():
        mask = mask & (df_full_display[obj] >= lo) & (df_full_display[obj] <= hi)
    df_filtered = df_full[mask].reset_index(drop=True)

    n_filtered = len(df_filtered)
    n_total = len(df_full)

    # --- Filtered solution table ---
    st.divider()
    st.markdown(f"**{n_filtered} of {n_total} solutions** match the current filters.")

    if n_filtered == 0:
        st.warning("No solutions match the current filters — adjust the sliders above.")
    else:
        display_df = to_display(df_filtered[OBJECTIVES])
        for col in OBJECTIVES:
            display_df[col] = display_df[col].map(lambda x: f"{x:.3e}")
        display_df.index = range(1, len(display_df) + 1)
        display_df.columns = [LABELS[c] for c in OBJECTIVES]

        cf_event = st.dataframe(
            display_df,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
        )

        # --- Selected solution detail ---
        selected_rows = cf_event.selection.rows
        if selected_rows:
            idx = selected_rows[0]
            row = df_filtered.iloc[idx]

            st.divider()
            st.subheader(f"Solution {idx + 1}")

            metric_cols = st.columns(len(OBJECTIVES))
            for m_col, obj in zip(metric_cols, OBJECTIVES):
                m_col.metric(LABELS[obj], f"{row[obj] * OBJECTIVE_SIGN[obj]:.3e}")

            try:
                config_dict = ast.literal_eval(row["json"])
            except Exception:
                config_dict = row["json"]

            with st.expander("Full JSON Configuration", expanded=True):
                st.json(config_dict)
                st.download_button(
                    label="Download configuration",
                    data=json.dumps(config_dict, indent=2),
                    file_name=f"solution_gen{cf_gen}_{idx + 1}.json",
                    mime="application/json",
                    key="cf_download_btn",
                )
        else:
            st.info("Select a row in the table to view its full configuration.")


# =========================================================
# TAB 3 – HYPERVOLUME INDICATOR
# =========================================================

with tab3:
    st.subheader("Hypervolume Indicator")
    st.caption(
        "Objectives are normalised to [0, 1] across all generations before computing. "
        "Hypervolume is approximated via Monte Carlo sampling (10,000 samples, reference point 1.1 per dimension). "
        "A rising curve indicates the front is still expanding into better trade-off regions."
    )

    with st.spinner("Computing hypervolume across all generations…"):
        hv_gens, hv_vals = compute_all_hypervolumes(run_sig, tuple(OBJECTIVES))

    if hv_gens:
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Initial hypervolume", f"{hv_vals[0]:.4f}")
        col_b.metric("Final hypervolume", f"{hv_vals[-1]:.4f}")
        improvement = hv_vals[-1] - hv_vals[0]
        col_c.metric("Improvement", f"{improvement:+.4f}")

        hv_chart_df = pd.DataFrame({"Hypervolume": hv_vals}, index=hv_gens)
        hv_chart_df.index.name = "Generation"
        st.line_chart(hv_chart_df, x_label="Generation", y_label="Hypervolume Indicator (normalised)")

        st.divider()
        hv_df = pd.DataFrame({"Generation": hv_gens, "Hypervolume": hv_vals})
        st.dataframe(hv_df, use_container_width=True)
        st.download_button(
            label="Download hypervolume data",
            data=hv_df.to_csv(index=False),
            file_name="hypervolume.csv",
            mime="text/csv",
        )

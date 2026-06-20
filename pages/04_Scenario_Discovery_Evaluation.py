import ast
import glob
import json
import os
import re
import altair as alt
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

RESULTS_DIR = "moo/results"
OBJECTIVES = ["co2e", "hnv", "protein", "hwp"]
LABELS = {
    "co2e": "Net Zero CO2e",
    "hnv": "Biodiversity (HNV)",
    "protein": "Protein Output",
    "hwp": "Harvested Wood Products",
}

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
# Data loading (cached per run via file count as key)
# -------------------------

n_files = len(csv_files)


@st.cache_data
def load_all_generations(n_files: int) -> dict[int, pd.DataFrame]:
    pattern = re.compile(r"gen(\d+)_pareto\.csv$")
    gens: dict[int, pd.DataFrame] = {}
    for fpath in glob.glob(os.path.join(RESULTS_DIR, "*_pareto.csv")):
        m = pattern.search(fpath)
        if m:
            gens[int(m.group(1))] = pd.read_csv(fpath, usecols=OBJECTIVES)
    return dict(sorted(gens.items()))


@st.cache_data
def load_generation_with_json(gen: int, n_files: int) -> pd.DataFrame:
    return pd.read_csv(os.path.join(RESULTS_DIR, f"gen{gen}_pareto.csv"))


@st.cache_data
def compute_all_hypervolumes(n_files: int, n_samples: int = 10_000) -> tuple[list, list]:
    """
    Monte Carlo hypervolume approximation (vectorised, fast for large fronts).
    Objectives are normalised to [0, 1] using the global min/max across all generations;
    reference point is 1.1 in every normalised dimension.
    """
    gens = load_all_generations(n_files)
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

generations = load_all_generations(n_files)
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

        df_final = generations[final_gen][[obj_x, obj_y]].copy()
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
            df_g = generations[gen][[obj_x, obj_y]].copy()
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
            full_df = load_generation_with_json(final_gen, n_files)
            selected_row = full_df.iloc[idx]
            selected_gen_num = final_gen

        if selected_row is None:
            s2 = _get_sel(event2, "sel2")
            pt2 = _first_point(s2)
            if pt2.get("Generation") is not None and pt2.get("_gen_idx") is not None:
                sel_gen = int(pt2["Generation"])
                sel_idx = int(pt2["_gen_idx"])
                full_df = load_generation_with_json(sel_gen, n_files)
                selected_row = full_df.iloc[sel_idx]
                selected_gen_num = sel_gen

        # --- Display selected configuration ---
        st.divider()
        if selected_row is not None:
            st.subheader(f"Selected Configuration — Generation {selected_gen_num}")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric(LABELS["co2e"], f"{selected_row['co2e']:.3e}")
            m2.metric(LABELS["hnv"], f"{selected_row['hnv']:.3e}")
            m3.metric(LABELS["protein"], f"{selected_row['protein']:.3e}")
            m4.metric(LABELS["hwp"], f"{selected_row['hwp']:.3e}")

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

    df_full = load_generation_with_json(cf_gen, n_files)

    display_df = df_full[OBJECTIVES].copy()
    for col in OBJECTIVES:
        display_df[col] = display_df[col].map(lambda x: f"{x:.3e}")
    display_df.index = range(1, len(display_df) + 1)
    display_df.columns = [LABELS[c] for c in OBJECTIVES]

    st.markdown(
        f"**{len(display_df)} Pareto-optimal solutions** — select a row to inspect its configuration."
    )

    event = st.dataframe(
        display_df,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = event.selection.rows
    if selected_rows:
        idx = selected_rows[0]
        row = df_full.iloc[idx]

        st.divider()
        st.subheader(f"Solution {idx + 1}")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(LABELS["co2e"], f"{row['co2e']:.3e}")
        m2.metric(LABELS["hnv"], f"{row['hnv']:.3e}")
        m3.metric(LABELS["protein"], f"{row['protein']:.3e}")
        m4.metric(LABELS["hwp"], f"{row['hwp']:.3e}")

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
            )
    else:
        st.info("Click a row in the table above to view its full configuration.")


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
        hv_gens, hv_vals = compute_all_hypervolumes(n_files)

    if hv_gens:
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Initial hypervolume", f"{hv_vals[0]:.4f}")
        col_b.metric("Final hypervolume", f"{hv_vals[-1]:.4f}")
        improvement = hv_vals[-1] - hv_vals[0]
        col_c.metric("Improvement", f"{improvement:+.4f}")

        fig3, ax3 = plt.subplots(figsize=(10, 5))
        ax3.plot(hv_gens, hv_vals, marker="o", markersize=3, linewidth=1.5, color="steelblue")
        ax3.fill_between(hv_gens, hv_vals, alpha=0.15, color="steelblue")
        ax3.set_xlabel("Generation")
        ax3.set_ylabel("Hypervolume Indicator (normalised)")
        ax3.set_title("Hypervolume Indicator Over Generations")
        ax3.grid(True, alpha=0.3)
        plt.tight_layout()

        st.pyplot(fig3)
        plt.close(fig3)

        st.divider()
        hv_df = pd.DataFrame({"Generation": hv_gens, "Hypervolume": hv_vals})
        st.dataframe(hv_df, use_container_width=True)
        st.download_button(
            label="Download hypervolume data",
            data=hv_df.to_csv(index=False),
            file_name="hypervolume.csv",
            mime="text/csv",
        )

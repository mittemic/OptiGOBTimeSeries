import glob
import os
import threading

import streamlit as st

from moo.optigob_problem2 import DEFAULT_LOWER_BOUND, DEFAULT_UPPER_BOUND, DEFAULT_INDICES

RESULTS_DIR = "moo/results"

DEFAULTS = {
    "sd_population_size": 300,
    "sd_n_generations": 100,
    "sd_mutation_probability": 0.01,
    "sd_mutation_distribution_index": 20,
    "sd_crossover_probability": 0.9,
    "sd_crossover_distribution_index": 20,
}

# ---------------------------------------------------------------------------
# Variable metadata
# Each entry: (raw_index, display_label, vtype)
# vtype controls display scale / slider step:
#   "year"       raw as-is = actual year  (2030-2050, step 1)
#   "scaler"     raw / 100 = 0.00-2.00    (step 0.01)
#   "rate"       raw as-is, integer (step 1, upper bound set by DEFAULT_UPPER_BOUND)
#   "rewetting"  raw / 100 = 0.00-1.00    (step 0.01)
#   "biomethane" raw * 1000 = 0-20 000    (step 1000)
#   "cat2"       integer 0-1              (step 1)
#   "cat3"       integer 0-2              (step 1)
#
# optigob_problem2 collapses each system to a single waypoint (fixed at year
# 2050) except AD emissions, which keeps three independent years. Indices are
# looked up by name via DEFAULT_INDICES rather than hardcoded, since the raw
# position of each variable is an implementation detail of optigob_problem2.
# ---------------------------------------------------------------------------

def _idx(name):
    return DEFAULT_INDICES.index(name)

VARIABLE_GROUPS = [
    {
        "name": "Forestry",
        "vars": [
            (_idx("ef_harvest"), "Existing forest harvest (0=low, 1=high)", "cat2"),
            (_idx("ef_ccs"), "Existing forest CCS (0=off, 1=on)", "cat2"),
            (_idx("af_harvest"), "Afforestation harvest (0=low, 1=high)", "cat2"),
            (_idx("af_ccs"), "Afforestation CCS (0=off, 1=on)", "cat2"),
            (_idx("af_rate"), "Afforestation rate", "rate"),
            (_idx("af_broadleaf"), "Broadleaf fraction (0=50%, 1=30%)", "cat2"),
            (_idx("af_organic_soil"), "Organic soil fraction (0=15%, 1=0%)", "cat2"),
        ],
    },
    {
        "name": "Pigs",
        "vars": [
            (_idx("pigs_abatement"), "Abatement (0=2020 BL, 1=MACC, 2=Frontier)", "cat3"),
            (_idx("pigs_scaler"), "Scaler", "scaler"),
        ],
    },
    {
        "name": "Poultry",
        "vars": [
            (_idx("poultry_abatement"), "Abatement (0=2020 BL, 1=MACC, 2=Frontier)", "cat3"),
            (_idx("poultry_scaler"), "Scaler", "scaler"),
        ],
    },
    {
        "name": "Sheep",
        "vars": [
            (_idx("sheep_abatement"), "Abatement (0=2020 BL, 1=MACC, 2=Frontier)", "cat3"),
            (_idx("sheep_scaler"), "Scaler", "scaler"),
        ],
    },
    {
        "name": "Crops",
        "vars": [
            (_idx("crops_abatement"), "Abatement (0=2020 BL, 1=MACC, 2=Frontier)", "cat3"),
            (_idx("crops_scaler"), "Scaler", "scaler"),
        ],
    },
    {
        "name": "Cattle",
        "vars": [
            (_idx("cattle_abatement"), "Abatement (0=2020 BL, 1=MACC, 2=Frontier)", "cat3"),
            (_idx("cattle_scaler"), "Scaler", "scaler"),
            (_idx("cattle_dairy_prod"), "Dairy productivity (0=2020 Prod, 1=Medium, 2=Strong)", "cat3"),
            (_idx("cattle_beef_prod"), "Beef productivity (0=2020 Prod, 1=Medium, 2=Strong)", "cat3"),
        ],
    },
    {
        "name": "Organic soil under grass",
        "vars": [
            (_idx("org_soil_under_grass"), "Rewetting ratio", "rewetting"),
        ],
    },
    {
        "name": "Industrial peat",
        "vars": [
            (_idx("industrial_peat"), "Rewetting ratio", "rewetting"),
        ],
    },
    {
        "name": "Domestic peat",
        "vars": [
            (_idx("domestic_peat"), "Rewetting ratio", "rewetting"),
        ],
    },
    {
        "name": "AD Emissions",
        "vars": [
            (_idx("ad_impl"), "Implementation (0=off, 1=on)", "cat2"),
            (_idx("ad_impl_year"), "Implementation year", "year"),
            (_idx("ad_ccs"), "CCS (0=off, 1=on)", "cat2"),
            (_idx("ad_add_biomethane"), "Grass biomethane", "biomethane"),
            (_idx("ad_add_biomethane_year"), "Additional biomethane year", "year"),
            (_idx("ad_co2_removal"), "CO2 removal", "biomethane"),
            (_idx("ad_co2_removal_year"), "CO2 removal year", "year"),
        ],
    },
]

# ---------------------------------------------------------------------------
# Display ↔ raw conversion helpers
# ---------------------------------------------------------------------------

def _to_display(raw, vtype):
    if vtype == "year":
        return int(raw)
    if vtype == "scaler":
        return round(int(raw) / 100, 2)
    if vtype == "rate":
        return int(raw)
    if vtype == "rewetting":
        return round(int(raw) / 100, 2)
    if vtype == "biomethane":
        return int(raw) * 1000
    return int(raw)  # cat2, cat3


def _to_raw(display, vtype):
    if vtype == "year":
        return int(display)
    if vtype == "scaler":
        return round(display * 100)
    if vtype == "rate":
        return int(display)
    if vtype == "rewetting":
        return round(display * 100)
    if vtype == "biomethane":
        return round(display / 1000)
    return int(display)


def _slider_kwargs(vtype, abs_lo_raw, abs_hi_raw):
    abs_lo = _to_display(abs_lo_raw, vtype)
    abs_hi = _to_display(abs_hi_raw, vtype)
    if vtype == "year":
        return dict(min_value=abs_lo, max_value=abs_hi, step=1)
    if vtype == "scaler":
        return dict(min_value=abs_lo, max_value=abs_hi, step=0.01)
    if vtype == "rate":
        return dict(min_value=abs_lo, max_value=abs_hi, step=1)
    if vtype == "rewetting":
        return dict(min_value=abs_lo, max_value=abs_hi, step=0.01)
    if vtype == "biomethane":
        return dict(min_value=abs_lo, max_value=abs_hi, step=1000)
    return dict(min_value=abs_lo, max_value=abs_hi, step=1)  # cat2 / cat3

# ---------------------------------------------------------------------------
# Initialise running state
# ---------------------------------------------------------------------------

for _key, _val in [("moo_running", False), ("moo_progress", {}), ("moo_thread", None)]:
    if _key not in st.session_state:
        st.session_state[_key] = _val

# ---------------------------------------------------------------------------
# Progress view (shown while algorithm runs)
# ---------------------------------------------------------------------------

@st.fragment(run_every="1s")
def _progress_fragment():
    # Auto-refreshing in isolation (rather than blocking the whole script with
    # time.sleep() + a manual st.rerun() every second) is what keeps this from
    # racing with the rest of the page — the old blocking-loop version could
    # leave stray Optimisation Parameters / Variable Bounds widgets rendered
    # alongside the progress view if a widget interaction landed mid-sleep.
    progress = st.session_state["moo_progress"]
    current = progress.get("current", 0)
    total = progress.get("total", 1)
    error = progress.get("error")

    if error:
        st.error(f"Optimisation failed: {error}")
        st.session_state["moo_running"] = False
        st.rerun()  # scope="app" (default) — exits the running branch entirely

    st.subheader("Running Optimisation…")
    st.progress(current / total if total > 0 else 0)
    st.caption(f"Generation {current} of {total} complete")

    params = st.session_state.get("moo_params", {})
    if params:
        st.divider()
        st.subheader("Run Summary")
        s_col1, s_col2, s_col3 = st.columns(3)
        s_col1.metric("Population size", params.get("population_size", "—"))
        s_col2.metric("Generations", params.get("n_generations", "—"))
        s_col3.metric("Total evaluations", f"{params.get('max_evaluations', 0):,}")

    thread = st.session_state["moo_thread"]
    if progress.get("done") or (thread is not None and not thread.is_alive()):
        st.session_state["moo_running"] = False
        st.session_state["moo_thread"] = None
        st.switch_page("pages/04_Scenario_Discovery_Evaluation.py")


if st.session_state["moo_running"]:
    st.title("Scenario Discovery")
    _progress_fragment()
    st.stop()

# ---------------------------------------------------------------------------
# Configuration form
# ---------------------------------------------------------------------------

st.title("Scenario Discovery")
st.markdown(
    "Configure the parameters for the multi-objective optimisation (NSGA-II) and "
    "launch a discovery run to explore the Pareto-optimal scenario space."
)

# ---------------------------------------------------------------------------
# Optimisation goals
# ---------------------------------------------------------------------------

st.header("Optimisation Goals")
st.caption(
    "Choose which objectives to optimise for. NSGA-II will only optimise the objectives "
    "selected here — results and the evaluation page adapt to however many are picked."
)

# session_key -> (objective key from optigob_problem2.ALL_OBJECTIVES, display label)
GOALS = {
    "goal_co2e": ("co2e", "CO2e"),
    "goal_biodiversity": ("hnv", "Bio-Diversity"),
    "goal_protein": ("protein", "Protein"),
    "goal_hwp": ("hwp", "Harvested Wood Production"),
}

for _goal_key in GOALS:
    if _goal_key not in st.session_state:
        st.session_state[_goal_key] = True

goal_cols = st.columns(4)
for goal_col, (goal_key, (_, goal_label)) in zip(goal_cols, GOALS.items()):
    goal_col.checkbox(goal_label, key=goal_key)

selected_goals = [obj_key for goal_key, (obj_key, _) in GOALS.items() if st.session_state[goal_key]]

if not selected_goals:
    st.warning("Select at least one optimisation goal.")

# ---------------------------------------------------------------------------
# Algorithm parameters
# ---------------------------------------------------------------------------

st.header("Optimisation Parameters")

col1, col2 = st.columns(2)

with col1:
    population_size = st.number_input(
        "Population size",
        min_value=50,
        max_value=500,
        value=DEFAULTS["sd_population_size"],
        step=10,
        key="sd_population_size",
        help="Number of candidate solutions maintained in each generation.",
    )

    mutation_probability = st.number_input(
        "Mutation probability",
        min_value=0.0,
        max_value=1.0,
        value=DEFAULTS["sd_mutation_probability"],
        step=0.01,
        format="%.2f",
        key="sd_mutation_probability",
        help="Probability of mutating each gene of a solution.",
    )

    mutation_distribution_index = st.number_input(
        "Mutation distribution index",
        min_value=10,
        max_value=30,
        value=DEFAULTS["sd_mutation_distribution_index"],
        step=1,
        key="sd_mutation_distribution_index",
        help="Controls the spread of the polynomial mutation. Higher values produce offspring closer to the parent.",
    )

with col2:
    n_generations = st.number_input(
        "Number of generations",
        min_value=30,
        max_value=300,
        value=DEFAULTS["sd_n_generations"],
        step=10,
        key="sd_n_generations",
        help="How many generations the algorithm will run.",
    )

    crossover_probability = st.number_input(
        "Crossover probability",
        min_value=0.0,
        max_value=1.0,
        value=DEFAULTS["sd_crossover_probability"],
        step=0.1,
        format="%.1f",
        key="sd_crossover_probability",
        help="Probability of applying crossover to a pair of solutions.",
    )

    crossover_distribution_index = st.number_input(
        "Crossover distribution index",
        min_value=10,
        max_value=30,
        value=DEFAULTS["sd_crossover_distribution_index"],
        step=1,
        key="sd_crossover_distribution_index",
        help="Controls the spread of the SBX crossover. Higher values produce offspring closer to the parents.",
    )

# ---------------------------------------------------------------------------
# Variable bounds
# ---------------------------------------------------------------------------

st.divider()
st.header("Variable Bounds")
st.caption(
    "Restrict the search space by narrowing the lower and upper bounds for each variable. "
    "The absolute limits shown are the problem defaults — you can only tighten them, not expand beyond."
)

# Initialise bounds in session state from the problem defaults
if "sd_lower_bound" not in st.session_state:
    st.session_state["sd_lower_bound"] = list(DEFAULT_LOWER_BOUND)
if "sd_upper_bound" not in st.session_state:
    st.session_state["sd_upper_bound"] = list(DEFAULT_UPPER_BOUND)

lo_bounds = st.session_state["sd_lower_bound"]
hi_bounds = st.session_state["sd_upper_bound"]

for group in VARIABLE_GROUPS:
    with st.expander(group["name"], expanded=False):
        for idx, label, vtype in group["vars"]:
            abs_lo_raw = DEFAULT_LOWER_BOUND[idx]
            abs_hi_raw = DEFAULT_UPPER_BOUND[idx]

            cur_lo_disp = _to_display(lo_bounds[idx], vtype)
            cur_hi_disp = _to_display(hi_bounds[idx], vtype)

            kwargs = _slider_kwargs(vtype, abs_lo_raw, abs_hi_raw)

            new_lo_disp, new_hi_disp = st.slider(
                label,
                value=(cur_lo_disp, cur_hi_disp),
                key=f"vb_{idx}",
                **kwargs,
            )

            lo_bounds[idx] = _to_raw(new_lo_disp, vtype)
            hi_bounds[idx] = _to_raw(new_hi_disp, vtype)

# Count how many variables have been narrowed from defaults
n_narrowed = sum(
    1 for i in range(len(DEFAULT_LOWER_BOUND))
    if lo_bounds[i] != DEFAULT_LOWER_BOUND[i] or hi_bounds[i] != DEFAULT_UPPER_BOUND[i]
)
if n_narrowed:
    st.info(f"{n_narrowed} variable{'s' if n_narrowed != 1 else ''} have narrowed bounds.")

# ---------------------------------------------------------------------------
# Run summary
# ---------------------------------------------------------------------------

max_evaluations = int(population_size) * int(n_generations)

st.divider()
st.subheader("Run Summary")

s_col1, s_col2, s_col3 = st.columns(3)
s_col1.metric("Population size", population_size)
s_col2.metric("Generations", n_generations)
s_col3.metric("Total evaluations", f"{max_evaluations:,}")

st.session_state["moo_params"] = {
    "population_size": int(population_size),
    "n_generations": int(n_generations),
    "max_evaluations": max_evaluations,
    "mutation_probability": float(mutation_probability),
    "mutation_distribution_index": int(mutation_distribution_index),
    "crossover_probability": float(crossover_probability),
    "crossover_distribution_index": int(crossover_distribution_index),
    "lower_bound": list(lo_bounds),
    "upper_bound": list(hi_bounds),
    "objectives": list(selected_goals),
}

# ---------------------------------------------------------------------------
# Action buttons
# ---------------------------------------------------------------------------

st.divider()

btn_col1, btn_col2 = st.columns([1, 5])

with btn_col1:
    if st.button("Reset"):
        for key in DEFAULTS:
            st.session_state.pop(key, None)
        st.session_state.pop("sd_lower_bound", None)
        st.session_state.pop("sd_upper_bound", None)
        for idx, _, _ in [v for g in VARIABLE_GROUPS for v in g["vars"]]:
            st.session_state.pop(f"vb_{idx}", None)
        for goal_key in GOALS:
            st.session_state.pop(goal_key, None)
        st.rerun()

with btn_col2:
    if st.button("Run Optimisation ➜", disabled=not selected_goals):
        # Clear existing CSV results
        for f in glob.glob(os.path.join(RESULTS_DIR, "*.csv")):
            os.remove(f)

        params = st.session_state["moo_params"]
        progress = {
            "current": 0,
            "total": params["n_generations"],
            "done": False,
            "error": None,
        }
        st.session_state["moo_progress"] = progress

        def _run(params, progress):
            try:
                from moo.nsga2 import run_nsga2
                run_nsga2(params=params, on_generation=lambda gen: progress.update({"current": gen}))
            except Exception as exc:
                progress["error"] = str(exc)
            finally:
                progress["done"] = True

        thread = threading.Thread(target=_run, args=(params, progress), daemon=True)
        thread.start()
        st.session_state["moo_thread"] = thread
        st.session_state["moo_running"] = True
        st.rerun()

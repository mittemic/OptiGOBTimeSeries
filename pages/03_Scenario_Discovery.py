import glob
import os
import threading
import time

import streamlit as st

from moo.optigob_problem import DEFAULT_LOWER_BOUND, DEFAULT_UPPER_BOUND

RESULTS_DIR = "moo/results"

DEFAULTS = {
    "sd_population_size": 100,
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
#   "year"      raw * 10 = actual year  (2030–2120, step 10)
#   "scaler"    raw / 100 = 0.00–2.00  (step 0.01)
#   "rate"      raw / 2  = 0–10 %/yr   (step 0.5)
#   "rewetting" raw / 100 = 0.00–1.00  (step 0.01)
#   "biomethane" raw as-is 0–20 000    (step 100)
#   "cat2"      integer 0–1            (step 1)
#   "cat3"      integer 0–2            (step 1)
# ---------------------------------------------------------------------------

VARIABLE_GROUPS = [
    {
        "name": "Forestry",
        "vars": [
            (0, "Existing forest harvest (0=low, 1=high)", "cat2"),
            (1, "Existing forest CCS (0=off, 1=on)", "cat2"),
            (2, "Afforestation harvest (0=low, 1=high)", "cat2"),
            (3, "Afforestation CCS (0=off, 1=on)", "cat2"),
            (4, "Afforestation rate", "rate"),
            (5, "Broadleaf fraction (0=50%, 1=30%)", "cat2"),
            (6, "Organic soil fraction (0=15%, 1=0%)", "cat2"),
        ],
    },
    {
        "name": "Pigs",
        "vars": [
            (7,  "Waypoint 1 year", "year"),
            (8,  "Waypoint 1 abatement (0=2020 BL, 1=MACC, 2=Frontier)", "cat3"),
            (9,  "Waypoint 1 scaler", "scaler"),
            (10, "Waypoint 2 year", "year"),
            (11, "Waypoint 2 abatement", "cat3"),
            (12, "Waypoint 2 scaler", "scaler"),
            (13, "Waypoint 3 year", "year"),
            (14, "Waypoint 3 abatement", "cat3"),
            (15, "Waypoint 3 scaler", "scaler"),
        ],
    },
    {
        "name": "Poultry",
        "vars": [
            (16, "Waypoint 1 year", "year"),
            (17, "Waypoint 1 abatement (0=2020 BL, 1=MACC, 2=Frontier)", "cat3"),
            (18, "Waypoint 1 scaler", "scaler"),
            (19, "Waypoint 2 year", "year"),
            (20, "Waypoint 2 abatement", "cat3"),
            (21, "Waypoint 2 scaler", "scaler"),
            (22, "Waypoint 3 year", "year"),
            (23, "Waypoint 3 abatement", "cat3"),
            (24, "Waypoint 3 scaler", "scaler"),
        ],
    },
    {
        "name": "Sheep",
        "vars": [
            (25, "Waypoint 1 year", "year"),
            (26, "Waypoint 1 abatement (0=2020 BL, 1=MACC, 2=Frontier)", "cat3"),
            (27, "Waypoint 1 scaler", "scaler"),
            (28, "Waypoint 2 year", "year"),
            (29, "Waypoint 2 abatement", "cat3"),
            (30, "Waypoint 2 scaler", "scaler"),
            (31, "Waypoint 3 year", "year"),
            (32, "Waypoint 3 abatement", "cat3"),
            (33, "Waypoint 3 scaler", "scaler"),
        ],
    },
    {
        "name": "Crops",
        "vars": [
            (34, "Waypoint 1 year", "year"),
            (35, "Waypoint 1 abatement (0=2020 BL, 1=MACC, 2=Frontier)", "cat3"),
            (36, "Waypoint 1 scaler", "scaler"),
            (37, "Waypoint 2 year", "year"),
            (38, "Waypoint 2 abatement", "cat3"),
            (39, "Waypoint 2 scaler", "scaler"),
            (40, "Waypoint 3 year", "year"),
            (41, "Waypoint 3 abatement", "cat3"),
            (42, "Waypoint 3 scaler", "scaler"),
        ],
    },
    {
        "name": "Cattle",
        "vars": [
            (43, "Waypoint 1 year", "year"),
            (44, "Waypoint 1 abatement (0=2020 BL, 1=MACC, 2=Frontier)", "cat3"),
            (45, "Waypoint 1 scaler", "scaler"),
            (46, "Waypoint 1 dairy productivity (0=2020 Prod, 1=Medium, 2=Strong)", "cat3"),
            (47, "Waypoint 1 beef productivity (0=2020 Prod, 1=Medium, 2=Strong)", "cat3"),
            (48, "Waypoint 2 year", "year"),
            (49, "Waypoint 2 abatement", "cat3"),
            (50, "Waypoint 2 scaler", "scaler"),
            (51, "Waypoint 2 dairy productivity", "cat3"),
            (52, "Waypoint 2 beef productivity", "cat3"),
            (53, "Waypoint 3 year", "year"),
            (54, "Waypoint 3 abatement", "cat3"),
            (55, "Waypoint 3 scaler", "scaler"),
            (56, "Waypoint 3 dairy productivity", "cat3"),
            (57, "Waypoint 3 beef productivity", "cat3"),
        ],
    },
    {
        "name": "Organic soil under grass",
        "vars": [
            (58, "Waypoint 1 year", "year"),
            (59, "Waypoint 1 rewetting ratio", "rewetting"),
            (60, "Waypoint 2 year", "year"),
            (61, "Waypoint 2 rewetting ratio", "rewetting"),
            (62, "Waypoint 3 year", "year"),
            (63, "Waypoint 3 rewetting ratio", "rewetting"),
        ],
    },
    {
        "name": "Industrial peat",
        "vars": [
            (64, "Waypoint 1 year", "year"),
            (65, "Waypoint 1 rewetting ratio", "rewetting"),
            (66, "Waypoint 2 year", "year"),
            (67, "Waypoint 2 rewetting ratio", "rewetting"),
            (68, "Waypoint 3 year", "year"),
            (69, "Waypoint 3 rewetting ratio", "rewetting"),
        ],
    },
    {
        "name": "Domestic peat",
        "vars": [
            (70, "Waypoint 1 year", "year"),
            (71, "Waypoint 1 rewetting ratio", "rewetting"),
            (72, "Waypoint 2 year", "year"),
            (73, "Waypoint 2 rewetting ratio", "rewetting"),
            (74, "Waypoint 3 year", "year"),
            (75, "Waypoint 3 rewetting ratio", "rewetting"),
        ],
    },
    {
        "name": "AD Emissions",
        "vars": [
            (76, "Implementation (0=off, 1=on)", "cat2"),
            (77, "Implementation year", "year"),
            (78, "CCS (0=off, 1=on)", "cat2"),
            (79, "Grass biomethane", "biomethane"),
            (80, "Additional biomethane year", "year"),
            (81, "CO2 removal", "biomethane"),
            (82, "CO2 removal year", "year"),
        ],
    },
]

# ---------------------------------------------------------------------------
# Display ↔ raw conversion helpers
# ---------------------------------------------------------------------------

def _to_display(raw, vtype):
    if vtype == "year":
        return int(raw) * 10
    if vtype == "scaler":
        return round(int(raw) / 100, 2)
    if vtype == "rate":
        return round(int(raw) / 2, 1)
    if vtype == "rewetting":
        return round(int(raw) / 100, 2)
    return int(raw)  # biomethane, cat2, cat3


def _to_raw(display, vtype):
    if vtype == "year":
        return int(display) // 10
    if vtype == "scaler":
        return round(display * 100)
    if vtype == "rate":
        return round(display * 2)
    if vtype == "rewetting":
        return round(display * 100)
    return int(display)


def _slider_kwargs(vtype, abs_lo_raw, abs_hi_raw):
    abs_lo = _to_display(abs_lo_raw, vtype)
    abs_hi = _to_display(abs_hi_raw, vtype)
    if vtype == "year":
        return dict(min_value=abs_lo, max_value=abs_hi, step=10)
    if vtype == "scaler":
        return dict(min_value=abs_lo, max_value=abs_hi, step=0.01)
    if vtype == "rate":
        return dict(min_value=abs_lo, max_value=abs_hi, step=0.5)
    if vtype == "rewetting":
        return dict(min_value=abs_lo, max_value=abs_hi, step=0.01)
    if vtype == "biomethane":
        return dict(min_value=abs_lo, max_value=abs_hi, step=100)
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

if st.session_state["moo_running"]:
    st.title("Scenario Discovery")
    progress = st.session_state["moo_progress"]
    current = progress.get("current", 0)
    total = progress.get("total", 1)
    error = progress.get("error")

    if error:
        st.error(f"Optimisation failed: {error}")
        st.session_state["moo_running"] = False
        st.stop()

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
    else:
        time.sleep(1)
        st.rerun()

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
        st.rerun()

with btn_col2:
    if st.button("Run Optimisation ➜"):
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

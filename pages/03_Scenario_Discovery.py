import glob
import os
import threading
import time

import streamlit as st

RESULTS_DIR = "moo/results"

DEFAULTS = {
    "sd_population_size": 100,
    "sd_n_generations": 100,
    "sd_mutation_probability": 0.01,
    "sd_mutation_distribution_index": 20,
    "sd_crossover_probability": 0.9,
    "sd_crossover_distribution_index": 20,
}

# -------------------------
# Initialise running state
# -------------------------

for _key, _val in [("moo_running", False), ("moo_progress", {}), ("moo_thread", None)]:
    if _key not in st.session_state:
        st.session_state[_key] = _val

# -------------------------
# Progress view (shown while algorithm runs)
# -------------------------

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

    thread = st.session_state["moo_thread"]
    if progress.get("done") or (thread is not None and not thread.is_alive()):
        st.session_state["moo_running"] = False
        st.session_state["moo_thread"] = None
        st.switch_page("pages/04_Scenario_Discovery_Evaluation.py")
    else:
        time.sleep(1)
        st.rerun()

    st.stop()

# -------------------------
# Configuration form
# -------------------------

st.title("Scenario Discovery")
st.markdown(
    "Configure the parameters for the multi-objective optimisation (NSGA-II) and "
    "launch a discovery run to explore the Pareto-optimal scenario space."
)

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

# -------------------------
# Derived summary
# -------------------------

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
}

# -------------------------
# Action buttons
# -------------------------

st.divider()

btn_col1, btn_col2 = st.columns([1, 5])

with btn_col1:
    if st.button("Reset"):
        for key in DEFAULTS:
            st.session_state.pop(key, None)
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

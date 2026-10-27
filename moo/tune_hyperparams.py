"""
Hyperparameter search for moo.nsga2.run_nsga2()'s NSGA-II/III settings, using
Optuna to search population size, mutation probability, and crossover probability
against a hypervolume performance goal.

Standalone script, not wired into the Streamlit app. Run as:
    poetry run python -m moo.tune_hyperparams

Requires optuna, which is not currently a project dependency:
    poetry add optuna
"""

import random

import numpy as np
import optuna
from jmetal.core.quality_indicator import HyperVolume

from moo.nsga2 import run_nsga2
from moo.optigob_problem2 import ALL_OBJECTIVES, Optigob_Problem

# ---------------------------------------------------------------------------
# Tuning-run configuration — knobs of this script, not of NSGA itself.
# ---------------------------------------------------------------------------
OBJECTIVES = list(ALL_OBJECTIVES)   # tune against all four objectives
N_TRIALS = 40                       # Optuna trials (each trial = len(SEEDS) NSGA runs)
SEEDS = (1, 2, 3)                   # repeats per trial — a single GA run is not a reliable score
TOTAL_EVALUATIONS = 30000           # fixed evaluation budget per NSGA run; population size trades off against generations
PILOT_POPULATION = 100              # a single, separate run used only to fix HV normalisation
PILOT_GENERATIONS = 15


def _fixed_hyperparams() -> dict:
    """Distribution indices held fixed, not searched — the least sensitive of
    the six NSGA parameters, per the earlier scope-reduction discussion."""
    return dict(mutation_distribution_index=20, crossover_distribution_index=20)


def compute_pilot_bounds(seed: int = 0):
    """
    Run one modest, generously-configured NSGA search and derive fixed
    normalisation bounds (component-wise min/max across its final population).

    These bounds make hypervolume comparable ACROSS every subsequent tuning
    trial. pages/04's hypervolume tab renormalises per-run, which is fine for
    watching one run's own progress but means two different hyperparameter
    configs would each get rescaled to their own achieved range — making their
    hypervolumes meaningless to compare against each other. Fixing the bounds
    once, here, is what avoids that.
    """
    random.seed(seed)
    np.random.seed(seed)

    result = run_nsga2(
        params=dict(
            population_size=PILOT_POPULATION,
            mutation_probability=1.0 / Optigob_Problem().number_of_variables(),
            crossover_probability=0.9,
            max_evaluations=PILOT_POPULATION * PILOT_GENERATIONS,
            objectives=OBJECTIVES,
            lower_bound=None,
            upper_bound=None,
            **_fixed_hyperparams(),
        ),
        write_results=False,
    )

    raw = np.array([s.objectives for s in result])
    obj_min = raw.min(axis=0)
    obj_range = raw.max(axis=0) - obj_min
    obj_range[obj_range == 0] = 1.0  # guard against a degenerate (constant) objective

    return obj_min, obj_range


def make_normaliser(obj_min: np.ndarray, obj_range: np.ndarray):
    def normalise(result) -> np.ndarray:
        raw = np.array([s.objectives for s in result])
        return np.clip((raw - obj_min) / obj_range, 0.0, None)
    return normalise


def run_and_score(config: dict, seed: int, normalise, hv_indicator: HyperVolume) -> float:
    random.seed(seed)
    np.random.seed(seed)
    result = run_nsga2(params=config, write_results=False)
    return hv_indicator.compute(normalise(result))


def build_objective(normalise, hv_indicator: HyperVolume):
    def objective(trial: optuna.Trial) -> float:
        population_size = trial.suggest_int("population_size", 50, 300, step=10)
        mutation_probability = trial.suggest_float("mutation_probability", 0.005, 0.15, log=True)
        crossover_probability = trial.suggest_float("crossover_probability", 0.6, 1.0)

        config = dict(
            population_size=population_size,
            mutation_probability=mutation_probability,
            crossover_probability=crossover_probability,
            max_evaluations=TOTAL_EVALUATIONS,
            objectives=OBJECTIVES,
            lower_bound=None,
            upper_bound=None,
            **_fixed_hyperparams(),
        )

        scores = [run_and_score(config, seed, normalise, hv_indicator) for seed in SEEDS]
        return float(np.mean(scores))
    return objective


def main():
    print(f"[tune] Deriving fixed hypervolume normalisation bounds from a pilot run "
          f"(population={PILOT_POPULATION}, generations={PILOT_GENERATIONS})...")
    obj_min, obj_range = compute_pilot_bounds()
    print(f"[tune] Pilot bounds: min={obj_min}, range={obj_range}")

    normalise = make_normaliser(obj_min, obj_range)
    hv_indicator = HyperVolume(reference_point=[1.1] * len(OBJECTIVES))

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=0))
    study.optimize(build_objective(normalise, hv_indicator), n_trials=N_TRIALS)

    print()
    print("[tune] Best config:", study.best_params)
    print(f"[tune] Best mean hypervolume (at {TOTAL_EVALUATIONS} evaluations per run):", study.best_value)
    best_generations = TOTAL_EVALUATIONS // study.best_params["population_size"]
    print(f"[tune] Best population_size implies ~{best_generations} generations "
          f"at {TOTAL_EVALUATIONS} total evaluations.")


#if __name__ == "__main__":
#    main()

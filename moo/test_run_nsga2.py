"""
Repeated-run quality assessment for moo.nsga2.run_nsga2().

Runs run_nsga2() N_ITERATIONS times (independent runs — no seeding, so each
iteration samples the algorithm's natural run-to-run variability), and for each
iteration's resulting Pareto front computes:

  - hypervolume            (dominated volume; higher is better)
  - inverted generational distance (IGD; distance from a reference front to the
                             front — lower is better)
  - epsilon indicator       (worst-case per-objective gap to a reference front;
                             lower is better)
  - spacing                 (evenness of the front's distribution; lower/closer
                             to 0 is more uniform)
  - number of solutions     (size of the raw non-dominated front, duplicates included)
  - number of unique        (size of the front after dropping solutions whose
                             objective vector exactly duplicates another one)

Solutions with identical objectives never dominate each other, so a front can
contain exact copies. Hypervolume/IGD/epsilon ignore them but spacing does not
(copies sit at distance 0), so every front is de-duplicated by objective vector
before scoring. n_solutions keeps the raw count so the duplication stays visible.

Hypervolume/IGD/epsilon/spacing all need a common scale to be meaningful, and
IGD/epsilon additionally need a reference front to compare against. Neither is
known in advance for this problem (no true Pareto front exists), so both are
derived empirically from the 30 runs themselves:
  - normalisation bounds = component-wise min/max across every point produced
    by any of the N_ITERATIONS runs (or, optionally, fixed bounds loaded from a
    JSON file via FIXED_BOUNDS_PATH so hypervolumes are comparable across batches)
  - reference front = the non-dominated subset of that same pooled set

This is the standard approach for empirically assessing an algorithm's
consistency when no ground truth is available — see e.g. Zitzler et al. (2003)
on empirical multiobjective indicator studies. It also means these numbers are
only meaningful relative to *this* batch of runs, not as absolute figures
comparable to some other batch computed on a different day/config.

This script only reads run_nsga2() (via write_results=False, so it never
touches moo/results/) — no other project file is modified by running it.

Usage:
    poetry run python -m moo.test_run_nsga2
"""

import csv
import json
import os
import statistics as stats

import numpy as np
from jmetal.core.quality_indicator import EpsilonIndicator, HyperVolume, InvertedGenerationalDistance
from jmetal.util.ranking import FastNonDominatedRanking

from moo.nsga2 import run_nsga2
from moo.optigob_problem2 import ALL_OBJECTIVES

# ---------------------------------------------------------------------------
# Run configuration
# ---------------------------------------------------------------------------
N_ITERATIONS = 30

# None = use run_nsga2()'s own built-in defaults (population_size=300,
# max_evaluations=30000 as of writing) — i.e. test exactly what a user gets
# out of the box. That is ~30,000 Optigob simulations PER iteration, so 30
# iterations is a multi-hour run. For a quick smoke test, set this to a
# smaller explicit params dict instead, e.g.:
#   NSGA_PARAMS = dict(population_size=50, mutation_probability=0.03,
#                       mutation_distribution_index=20, crossover_probability=0.9,
#                       crossover_distribution_index=20, max_evaluations=50 * 15,
#                       objectives=None, lower_bound=None, upper_bound=None)
NSGA_PARAMS = None

LOG_CSV_PATH = os.path.join(os.path.dirname(__file__), "nsga2_quality_log.csv")

# Normalisation bounds. By default (both None) they are derived from the points
# produced by this batch of runs, so hypervolumes are only comparable within the
# batch. To compare hypervolumes across batches, fix the bounds:
#   1. run once with SAVE_BOUNDS_PATH set to write this batch's bounds to JSON
#   2. in later runs set FIXED_BOUNDS_PATH to that file; it is loaded (and checked
#      against the run's objectives) before any NSGA run starts
# Note: IGD and epsilon still compare against this batch's own pooled reference
# front, so they stay batch-relative even with fixed bounds.
FIXED_BOUNDS_PATH = None   # e.g. os.path.join(os.path.dirname(__file__), "nsga2_bounds.json")
SAVE_BOUNDS_PATH = None    # e.g. os.path.join(os.path.dirname(__file__), "nsga2_bounds.json")

METRIC_NAMES = ["hypervolume", "igd", "epsilon", "spacing", "n_solutions", "n_unique"]


def pareto_front(solutions):
    """Non-dominated subset of a list of jMetalPy Solutions, matching the same
    filtering moo/observer.py already uses when writing generation CSVs."""
    ranking = FastNonDominatedRanking()
    ranking.compute_ranking(solutions)
    return ranking.get_subfront(0)


def unique_by_objectives(solutions):
    """Keep the first solution for each distinct objective vector. Identical
    chromosomes give bit-identical objectives, so exact comparison is enough."""
    seen = set()
    unique = []
    for s in solutions:
        key = tuple(s.objectives)
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def run_objective_names():
    """Objective keys this run optimises, in the canonical order used by the
    solutions' objective vectors (mirrors Optigob_Problem's ordering)."""
    requested = NSGA_PARAMS.get("objectives") if NSGA_PARAMS else None
    return [k for k in ALL_OBJECTIVES if requested is None or k in requested]


def load_bounds(path, objectives):
    with open(path) as f:
        data = json.load(f)
    if data["objectives"] != objectives:
        raise ValueError(f"Bounds file {path} was saved for objectives {data['objectives']}, "
                         f"but this run optimises {objectives}")
    obj_min = np.array(data["obj_min"], dtype=float)
    obj_range = np.array(data["obj_range"], dtype=float)
    if len(obj_min) != len(objectives) or len(obj_range) != len(objectives):
        raise ValueError(f"Bounds file {path} does not have one value per objective")
    return obj_min, obj_range


def save_bounds(path, objectives, obj_min, obj_range):
    with open(path, "w") as f:
        json.dump({"objectives": objectives,
                   "obj_min": [float(v) for v in obj_min],
                   "obj_range": [float(v) for v in obj_range]}, f, indent=2)


def spacing(points: np.ndarray) -> float:
    """Schott (1995) spacing metric on an already-normalised set of points:
    the standard deviation of each point's nearest-neighbour (L1) distance.
    0 = perfectly evenly spaced; jMetalPy does not ship this indicator."""
    n = len(points)
    if n < 2:
        return 0.0
    nearest = np.empty(n)
    for i in range(n):
        dist = np.sum(np.abs(points - points[i]), axis=1)
        dist[i] = np.inf
        nearest[i] = dist.min()
    mean_dist = nearest.mean()
    return float(np.sqrt(np.sum((nearest - mean_dist) ** 2) / (n - 1)))


def summarise(values):
    return {
        "min": min(values),
        "max": max(values),
        "average": stats.mean(values),
        "median": stats.median(values),
    }


def main():
    print(f"[test_run_nsga2] Running run_nsga2() {N_ITERATIONS} times "
          f"(params={'<run_nsga2 defaults>' if NSGA_PARAMS is None else NSGA_PARAMS})...")

    # Load fixed bounds up front so a missing/mismatched file fails now, not
    # after hours of NSGA runs.
    objectives = run_objective_names()
    fixed_bounds = None
    if FIXED_BOUNDS_PATH is not None:
        fixed_bounds = load_bounds(FIXED_BOUNDS_PATH, objectives)
        print(f"[test_run_nsga2] Using fixed normalisation bounds from {FIXED_BOUNDS_PATH}")
    else:
        print("[test_run_nsga2] Normalisation bounds will be derived from the pooled runs")

    # -------------------------------------------------------------------
    # Pass 1 — run N_ITERATIONS independent NSGA searches, keep each run's
    # own Pareto front (as raw objective arrays, plus solution count).
    # -------------------------------------------------------------------
    iteration_fronts = []   # de-duplicated fronts, used for all scoring
    raw_front_sizes = []    # non-dominated count before de-duplication
    for i in range(1, N_ITERATIONS + 1):
        print(f"[test_run_nsga2] Iteration {i}/{N_ITERATIONS}...")
        result = run_nsga2(params=NSGA_PARAMS, write_results=False)
        front = pareto_front(result)
        unique_front = unique_by_objectives(front)
        iteration_fronts.append(unique_front)
        raw_front_sizes.append(len(front))
        print(f"[test_run_nsga2]   -> {len(front)} non-dominated solutions, "
              f"{len(unique_front)} unique")

    # -------------------------------------------------------------------
    # Derive shared normalisation bounds and reference front from every
    # point produced across all N_ITERATIONS runs (see module docstring).
    # -------------------------------------------------------------------
    pooled_solutions = [s for front in iteration_fronts for s in front]
    pooled_raw = np.array([s.objectives for s in pooled_solutions])

    if fixed_bounds is not None:
        obj_min, obj_range = fixed_bounds
    else:
        obj_min = pooled_raw.min(axis=0)
        obj_range = pooled_raw.max(axis=0) - obj_min
        obj_range[obj_range == 0] = 1.0  # guard against a degenerate (constant) objective

    if SAVE_BOUNDS_PATH is not None:
        save_bounds(SAVE_BOUNDS_PATH, objectives, obj_min, obj_range)
        print(f"[test_run_nsga2] Normalisation bounds saved to {SAVE_BOUNDS_PATH}")

    def normalise(raw: np.ndarray) -> np.ndarray:
        return np.clip((raw - obj_min) / obj_range, 0.0, None)

    if fixed_bounds is not None:
        # Fixed bounds can sit inside this batch's range; points past the
        # hypervolume reference point (1.1) contribute no volume.
        beyond = int(np.any(normalise(pooled_raw) > 1.1, axis=1).sum())
        print(f"[test_run_nsga2] {beyond}/{len(pooled_raw)} pooled points lie beyond the "
              f"hypervolume reference point under the fixed bounds")

    reference_front_solutions = unique_by_objectives(pareto_front(pooled_solutions))
    reference_front = normalise(np.array([s.objectives for s in reference_front_solutions]))

    n_objectives = pooled_raw.shape[1]
    hv_indicator = HyperVolume(reference_point=[1.1] * n_objectives)
    igd_indicator = InvertedGenerationalDistance(reference_front=reference_front)
    epsilon_indicator = EpsilonIndicator(reference_front=reference_front)

    print(f"[test_run_nsga2] Pooled reference front: {len(reference_front_solutions)} solutions "
          f"across {n_objectives} objectives")

    # -------------------------------------------------------------------
    # Pass 2 — score every iteration's own front against the shared
    # normalisation/reference derived above.
    # -------------------------------------------------------------------
    rows = []
    for i, front in enumerate(iteration_fronts, start=1):
        raw = np.array([s.objectives for s in front])
        norm = normalise(raw)

        row = {
            "iteration": i,
            "hypervolume": hv_indicator.compute(norm),
            "igd": igd_indicator.compute(norm),
            "epsilon": epsilon_indicator.compute(norm),
            "spacing": spacing(norm),
            "n_solutions": raw_front_sizes[i - 1],
            "n_unique": len(front),
        }
        rows.append(row)
        print(f"[test_run_nsga2] Iteration {i:2d}: "
              f"hypervolume={row['hypervolume']:.4f}  igd={row['igd']:.4f}  "
              f"epsilon={row['epsilon']:.4f}  spacing={row['spacing']:.4f}  "
              f"n_solutions={row['n_solutions']}  n_unique={row['n_unique']}")

    # -------------------------------------------------------------------
    # Log every iteration's metrics to CSV.
    # -------------------------------------------------------------------
    with open(LOG_CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["iteration"] + METRIC_NAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[test_run_nsga2] Per-iteration log written to {LOG_CSV_PATH}")

    # -------------------------------------------------------------------
    # Summary statistics across all N_ITERATIONS iterations.
    # -------------------------------------------------------------------
    print()
    print(f"[test_run_nsga2] Summary across {N_ITERATIONS} iterations:")
    print(f"{'metric':<14}{'min':>14}{'max':>14}{'average':>14}{'median':>14}")
    for metric in METRIC_NAMES:
        values = [row[metric] for row in rows]
        s = summarise(values)
        print(f"{metric:<14}{s['min']:>14.4f}{s['max']:>14.4f}{s['average']:>14.4f}{s['median']:>14.4f}")


#if __name__ == "__main__":
#    main()

"""
Side-by-side quality assessment of NSGA (moo.nsga2.run_nsga2), MOEA/D
(moo.moaed.run_moead) and a random-search baseline (moo.random_search).

Runs each algorithm N_ITERATIONS times (independent, unseeded runs, alternating
between the algorithms so slow drift on the machine hits all of them equally) and
scores every run's Pareto front with the same indicators as moo/test_run_nsga2.py
(hypervolume, IGD, epsilon, spacing, number of solutions, number of unique
solutions).

No algorithm parameters are set here. Every algorithm is called with params=None,
i.e. with the defaults written in moo/nsga2.py, moo/moaed.py and
moo/random_search.py. Edit those files to change what gets tested.

What makes the numbers comparable between the algorithms:
  - ONE set of normalisation bounds for all runs of all algorithms, derived from
    the union of every point any of them produced (or fixed bounds loaded from
    FIXED_BOUNDS_PATH)
  - ONE reference front for IGD / epsilon: the non-dominated, de-duplicated union
    of all algorithms' points, so no algorithm is judged against a front built
    only from its own output
  - the same hypervolume reference point (1.1 in normalised space)
  - fronts de-duplicated by objective vector before scoring
  - the Optigob evaluations of every run are counted, and the script warns if the
    algorithms did not get the same budget (their defaults live in separate files)

Random search returns the complete non-dominated archive of everything it
evaluated, uncapped (the strongest form of the baseline). Its size is therefore
not a population size: n_solutions / n_unique, and size-sensitive indicators such
as IGD and spacing, are not like-for-like with the fixed-size populations of the
evolutionary algorithms, and it is left out of the population-size check.

Saved data, so nothing has to be re-run to add an algorithm or re-score:
  - FRONTS_PATH: every finished run is appended there (JSON lines: raw objective
    vectors of its de-duplicated front plus its budget/timing). On start, runs
    already stored are reused instead of re-run, so an interrupted batch resumes
    and an existing batch can be re-scored (e.g. after adding an algorithm to
    ALGORITHMS, only the new runs execute). Each record carries a fingerprint of
    the algorithm/model code and data; if it no longer matches, the script stops
    instead of silently mixing runs made with different settings. Delete the
    file (or change FRONTS_PATH) to start a fresh batch.
  - SAVE_BOUNDS_PATH: the normalisation bounds used, reusable via FIXED_BOUNDS_PATH.

Indicators are vectorised equivalents of jMetalPy's (checked equal), because the
random-search archives are large enough to make jMetalPy's Python loops slow.

Usage:
    poetry run python -m moo.test_run_nsga2_vs_moaed
"""

import csv
import glob
import hashlib
import json
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
from jmetal.core.quality_indicator import HyperVolume
from scipy.spatial.distance import cdist

from moo.moaed import run_moead
from moo.nsga2 import run_nsga2
from moo.optigob_problem2 import ALL_OBJECTIVES, Optigob_Problem
from moo.random_search import run_random_search
from moo.test_run_nsga2 import METRIC_NAMES, load_bounds, save_bounds, spacing, summarise

# ---------------------------------------------------------------------------
# Run configuration (test harness only — algorithm settings live in the
# algorithm files)
# ---------------------------------------------------------------------------
N_ITERATIONS = 30

ALGORITHMS = [("NSGA", run_nsga2), ("MOEA/D", run_moead), ("Random", run_random_search)]

# Algorithms whose output is an archive rather than a fixed-size population.
NO_POPULATION = {"Random"}

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_CSV_PATH = os.path.join(HERE, "algorithm_comparison_3way_log.csv")
FRONTS_PATH = os.path.join(HERE, "algorithm_comparison_fronts.jsonl")

# Same meaning as in test_run_nsga2.py. The bounds used are always saved so the
# batch can be reproduced; set FIXED_BOUNDS_PATH to score against earlier bounds.
FIXED_BOUNDS_PATH = None
SAVE_BOUNDS_PATH = os.path.join(HERE, "algorithm_comparison_bounds.json")

CSV_COLUMNS = ["algorithm", "iteration"] + METRIC_NAMES + ["population_size", "evaluations", "seconds"]

# Code and data that determine what a run produces; hashed into every stored run.
FINGERPRINT_PATTERNS = [
    "moo/nsga2.py", "moo/moaed.py", "moo/random_search.py", "moo/optigob_problem2.py",
    "optigob/**/*.py", "resource_manager/*.py", "data/database.db",
]


class EvaluationCounter:
    """Counts Optigob_Problem.evaluate calls by wrapping the method for as long
    as the counter is installed, so budgets can be compared without touching
    the algorithm files."""

    def __init__(self):
        self.count = 0
        self._original = None

    def __enter__(self):
        self._original = Optigob_Problem.evaluate
        counter, original = self, self._original

        def counting_evaluate(problem, solution):
            counter.count += 1
            return original(problem, solution)

        Optigob_Problem.evaluate = counting_evaluate
        return self

    def __exit__(self, *exc):
        Optigob_Problem.evaluate = self._original


# ---------------------------------------------------------------------------
# Non-dominated filtering and indicators (numpy, minimisation)
# ---------------------------------------------------------------------------
def non_dominated_mask(points: np.ndarray) -> np.ndarray:
    """True for points no other point dominates. Identical points do not dominate
    each other, so duplicates are all kept (same semantics as jMetalPy's ranking).
    Scanned in lexicographic order: a dominating point always sorts earlier."""
    order = np.lexsort(points.T[::-1])
    archive = np.empty_like(points)
    size = 0
    mask = np.zeros(len(points), dtype=bool)
    for idx in order:
        p = points[idx]
        if size:
            a = archive[:size]
            if np.any(np.all(a <= p, axis=1) & np.any(a < p, axis=1)):
                continue
        archive[size] = p
        size += 1
        mask[idx] = True
    return mask


def unique_non_dominated(points: np.ndarray) -> np.ndarray:
    return np.unique(points[non_dominated_mask(points)], axis=0)


def igd(front: np.ndarray, reference: np.ndarray, chunk: int = 512) -> float:
    """jMetalPy's IGD (pow=2): sqrt(sum of squared nearest distances) / N_reference."""
    total = 0.0
    for start in range(0, len(reference), chunk):
        nearest = cdist(reference[start:start + chunk], front).min(axis=1)
        total += float(np.sum(nearest ** 2))
    return total ** 0.5 / len(reference)


def additive_epsilon(front: np.ndarray, reference: np.ndarray, chunk: int = 256) -> float:
    """jMetalPy's additive epsilon: worst reference point's smallest max-objective gap."""
    worst = -np.inf
    for start in range(0, len(reference), chunk):
        gap = (front[None, :, :] - reference[start:start + chunk, None, :]).max(axis=2)
        worst = max(worst, float(gap.min(axis=1).max()))
    return worst


# ---------------------------------------------------------------------------
# Stored runs
# ---------------------------------------------------------------------------
def source_fingerprint() -> str:
    digest = hashlib.sha256()
    for pattern in FINGERPRINT_PATTERNS:
        for path in sorted(glob.glob(os.path.join(PROJECT_ROOT, pattern), recursive=True)):
            digest.update(os.path.relpath(path, PROJECT_ROOT).replace("\\", "/").encode())
            with open(path, "rb") as f:
                digest.update(f.read())
    return digest.hexdigest()


def load_stored_runs(path: str, fingerprint: str) -> dict:
    """Stored runs keyed by (algorithm, iteration). Refuses a file written with
    different code/data. A truncated last line (crash mid-write) is ignored."""
    stored = {}
    if not os.path.exists(path):
        return stored
    with open(path) as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"[compare] Ignoring unreadable line {line_number} of {path}")
                continue
            if record["fingerprint"] != fingerprint:
                raise RuntimeError(
                    f"{path} holds runs made with different algorithm/model code or data than the "
                    f"current files. Delete or rename it (or change FRONTS_PATH) to start a new batch.")
            record["front"] = np.array(record["front"], dtype=float)
            stored.setdefault((record["algorithm"], record["iteration"]), record)
    return stored


def append_run(path: str, record: dict) -> None:
    # A crash mid-write leaves a last line without a newline; start on a fresh
    # line so the new record is not glued onto that fragment.
    needs_newline = False
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            needs_newline = f.read(1) != b"\n"
    with open(path, "a") as f:
        if needs_newline:
            f.write("\n")
        f.write(json.dumps({**record, "front": record["front"].tolist()}) + "\n")
        f.flush()


def warn_if_budgets_differ(runs):
    evaluations = {name: sorted({r["evaluations"] for r in rs}) for name, rs in runs.items()}
    populations = {name: sorted({r["population_size"] for r in rs})
                   for name, rs in runs.items() if name not in NO_POPULATION}
    print(f"[compare] Evaluations per run: {evaluations}")
    print(f"[compare] Population size:     {populations}")

    if len({tuple(v) for v in evaluations.values()}) > 1:
        print("[compare] WARNING: the algorithms did not get the same evaluation budget "
              "(check the DEFAULT_PARAMS in moo/moaed.py and moo/random_search.py against the "
              "defaults in moo/nsga2.py). The metrics below are NOT like-for-like.")
    if len({tuple(v) for v in populations.values()}) > 1:
        print("[compare] WARNING: the algorithms used different population sizes; "
              "n_solutions / n_unique are capped by population size and not directly comparable.")


def main():
    # data/database.db and moo/results are relative paths; running this file by
    # path from another working directory otherwise fails to open the database.
    os.chdir(PROJECT_ROOT)

    objectives = list(ALL_OBJECTIVES)  # params=None means every objective, for all algorithms
    print(f"[compare] {N_ITERATIONS} runs each of {[name for name, _ in ALGORITHMS]}, "
          f"using the defaults from the algorithm files")

    # Load fixed bounds and stored runs up front so a bad file fails now, not after hours of runs.
    fixed_bounds = None
    if FIXED_BOUNDS_PATH is not None:
        fixed_bounds = load_bounds(FIXED_BOUNDS_PATH, objectives)
        print(f"[compare] Using fixed normalisation bounds from {FIXED_BOUNDS_PATH}")
    else:
        print("[compare] Normalisation bounds will be derived from the pooled runs of all algorithms")

    fingerprint = source_fingerprint()
    stored = load_stored_runs(FRONTS_PATH, fingerprint)
    if stored:
        print(f"[compare] {len(stored)} stored runs found in {FRONTS_PATH}; they will be reused")

    # -------------------------------------------------------------------
    # Pass 1 — run what is not stored yet; keep each run's de-duplicated front.
    # -------------------------------------------------------------------
    runs = {name: [] for name, _ in ALGORITHMS}
    with EvaluationCounter() as counter:
        for i in range(1, N_ITERATIONS + 1):
            for name, run_fn in ALGORITHMS:
                record = stored.get((name, i))
                if record is not None:
                    print(f"[compare] Iteration {i}/{N_ITERATIONS}: {name} (stored, {len(record['front'])} unique)")
                    runs[name].append(record)
                    continue

                print(f"[compare] Iteration {i}/{N_ITERATIONS}: {name}...")
                counter.count = 0
                started = time.time()
                result = run_fn(params=None, write_results=False)
                seconds = time.time() - started

                raw = np.array([s.objectives for s in result], dtype=float)
                non_dominated = raw[non_dominated_mask(raw)]
                record = {
                    "fingerprint": fingerprint,
                    "algorithm": name,
                    "iteration": i,
                    "front": np.unique(non_dominated, axis=0),
                    "n_solutions": len(non_dominated),
                    "population_size": None if name in NO_POPULATION else len(result),
                    "evaluations": counter.count,
                    "seconds": seconds,
                }
                append_run(FRONTS_PATH, record)
                runs[name].append(record)
                print(f"[compare]   -> {record['n_solutions']} non-dominated, {len(record['front'])} unique, "
                      f"{counter.count} evaluations, {seconds:.0f}s")

    warn_if_budgets_differ(runs)

    # -------------------------------------------------------------------
    # Shared normalisation bounds and reference front, from ALL algorithms.
    # -------------------------------------------------------------------
    pooled_raw = np.vstack([r["front"] for rs in runs.values() for r in rs])

    if fixed_bounds is not None:
        obj_min, obj_range = fixed_bounds
    else:
        obj_min = pooled_raw.min(axis=0)
        obj_range = pooled_raw.max(axis=0) - obj_min
        obj_range[obj_range == 0] = 1.0  # guard against a degenerate (constant) objective

    if SAVE_BOUNDS_PATH is not None:
        save_bounds(SAVE_BOUNDS_PATH, objectives, obj_min, obj_range)
        print(f"[compare] Normalisation bounds saved to {SAVE_BOUNDS_PATH}")

    def normalise(raw: np.ndarray) -> np.ndarray:
        return np.clip((raw - obj_min) / obj_range, 0.0, None)

    if fixed_bounds is not None:
        beyond = int(np.any(normalise(pooled_raw) > 1.1, axis=1).sum())
        print(f"[compare] {beyond}/{len(pooled_raw)} pooled points lie beyond the "
              f"hypervolume reference point under the fixed bounds")

    reference_raw = unique_non_dominated(pooled_raw)
    reference_front = normalise(reference_raw)

    n_objectives = pooled_raw.shape[1]
    hv_indicator = HyperVolume(reference_point=[1.1] * n_objectives)

    produced = {name: {tuple(row) for r in rs for row in r["front"]} for name, rs in runs.items()}
    contribution = {name: sum(1 for row in reference_raw if tuple(row) in produced[name])
                    for name in runs}  # a point several algorithms found counts for each
    print(f"[compare] Pooled reference front: {len(reference_raw)} solutions across "
          f"{n_objectives} objectives (contributed by: {contribution})")

    # -------------------------------------------------------------------
    # Pass 2 — score every run against the shared normalisation / reference.
    # -------------------------------------------------------------------
    rows = []
    for i in range(1, N_ITERATIONS + 1):
        for name, _ in ALGORITHMS:
            r = runs[name][i - 1]
            norm = normalise(r["front"])
            row = {
                "algorithm": name,
                "iteration": i,
                "hypervolume": hv_indicator.compute(norm),
                "igd": igd(norm, reference_front),
                "epsilon": additive_epsilon(norm, reference_front),
                "spacing": spacing(norm),
                "n_solutions": r["n_solutions"],
                "n_unique": len(r["front"]),
                "population_size": r["population_size"],
                "evaluations": r["evaluations"],
                "seconds": round(r["seconds"], 1),
            }
            rows.append(row)
            print(f"[compare] {name:<7} iteration {i:2d}: "
                  f"hypervolume={row['hypervolume']:.4f}  igd={row['igd']:.4f}  "
                  f"epsilon={row['epsilon']:.4f}  spacing={row['spacing']:.4f}  "
                  f"n_solutions={row['n_solutions']}  n_unique={row['n_unique']}")

    # -------------------------------------------------------------------
    # Log every run to CSV.
    # -------------------------------------------------------------------
    with open(LOG_CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[compare] Per-run log written to {LOG_CSV_PATH}")

    # -------------------------------------------------------------------
    # Summary statistics per metric, one line per algorithm.
    # -------------------------------------------------------------------
    print()
    print(f"[compare] Summary across {N_ITERATIONS} runs per algorithm:")
    for metric in METRIC_NAMES:
        print()
        print(f"{metric:<14}{'min':>14}{'max':>14}{'average':>14}{'median':>14}")
        for name, _ in ALGORITHMS:
            s = summarise([row[metric] for row in rows if row["algorithm"] == name])
            print(f"  {name:<12}{s['min']:>14.4f}{s['max']:>14.4f}{s['average']:>14.4f}{s['median']:>14.4f}")

    print()
    print("[compare] Average run time: " + ", ".join(
        f"{name} {np.mean([r['seconds'] for r in rs]):.0f}s" for name, rs in runs.items()))


if __name__ == "__main__":
    main()

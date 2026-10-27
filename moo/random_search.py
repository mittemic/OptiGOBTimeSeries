"""
Random-search baseline for moo.nsga2.run_nsga2() / moo.moaed.run_moead().

Draws uniformly random solutions (every variable uniform within its bounds, via
Optigob_Problem.create_solution()), evaluates each one, and returns the
non-dominated set of everything it evaluated. Given the same evaluation budget
this is the reference point for "does the evolutionary search add anything?".

The returned set is the full non-dominated archive and is NOT capped at a
population size, which makes this the strongest form of the baseline: it can only
help random search. The consequence is that its size (and so n_solutions, and
size-sensitive indicators such as IGD) is not comparable with the evolutionary
algorithms' fixed-size populations.

Same call convention as the other algorithms:
  params: None uses DEFAULT_PARAMS (mirrors run_nsga2's evaluation budget).
          used: max_evaluations, lower_bound, upper_bound, objectives.
          everything else in a run_nsga2-style params dict is ignored.
  write_results / on_generation: accepted for interface parity; there are no
          generations, so write_results=True is not supported.
"""

import numpy as np

from moo.optigob_problem2 import Optigob_Problem

# Mirror run_nsga2()'s evaluation budget so the baseline gets the same number of
# evaluations. Keep in sync if that changes.
DEFAULT_PARAMS = dict(max_evaluations=30000)


def run_random_search(params=None, on_generation=None, write_results=False):
    if write_results:
        raise NotImplementedError("Random search has no generations and does not write result CSVs")

    params = params or {}
    problem = Optigob_Problem(lower_bound=params.get("lower_bound"),
                              upper_bound=params.get("upper_bound"),
                              objectives=params.get("objectives"))
    max_evaluations = params.get("max_evaluations") or DEFAULT_PARAMS["max_evaluations"]
    n_objectives = problem.number_of_objectives()
    print(f"[random_search] Optimising objectives: {problem.objectives}")

    members = []                                    # non-dominated Solutions found so far
    objectives = np.empty((0, n_objectives))        # their objective vectors, row-aligned with members

    for _ in range(max_evaluations):
        solution = problem.create_solution()
        problem.evaluate(solution)
        point = np.asarray(solution.objectives, dtype=float)

        if len(members):
            no_worse = np.all(objectives <= point, axis=1)
            better = np.any(objectives < point, axis=1)
            if np.any(no_worse & better) or np.any(np.all(objectives == point, axis=1)):
                continue  # dominated by (or identical to) something already kept

            dominated_by_new = np.all(point <= objectives, axis=1) & np.any(point < objectives, axis=1)
            if np.any(dominated_by_new):
                keep = ~dominated_by_new
                members = [m for m, k in zip(members, keep) if k]
                objectives = objectives[keep]

        members.append(solution)
        objectives = np.vstack([objectives, point])

    return members

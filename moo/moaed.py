"""
MOEA/D (multi-objective evolutionary algorithm based on decomposition) for the
OptiGob problem, as a comparison algorithm for moo.nsga2.run_nsga2().

Same problem (moo.optigob_problem2.Optigob_Problem), same params dict, same
return value (the final population), so the two can be dropped into the same
test harness. Where NSGA-II/III rank solutions by dominance, MOEA/D splits the
problem into one scalar sub-problem per weight vector (Tchebycheff aggregation)
and lets neighbouring sub-problems share good solutions.

jMetalPy's MOEAD does not work on this problem out of the box, so this file
adds three things (nothing in nsga2.py / observer.py is touched):

  - Integer DE crossover. jMetalPy's DifferentialEvolutionCrossover writes float
    values into the solution; this subclass rounds them to integers.
  - Normalised Tchebycheff aggregation. The objectives differ by ~6 orders of
    magnitude (protein ~1e10 vs co2e ~1e4); jMetalPy's Tschebycheff works on raw
    values and would effectively optimise protein alone. Objectives are scaled by
    the running ideal/nadir seen so far.
  - Weight vectors for any population size. jMetalPy only reads weight vectors
    from pre-made files; here a simplex-lattice (Das-Dennis) set is generated,
    pruned to exactly population_size, and written to a temp file.

Parameters (same dict as run_nsga2):
  used:    population_size, mutation_probability, mutation_distribution_index,
           max_evaluations, lower_bound, upper_bound, objectives
  ignored: crossover_probability, crossover_distribution_index (DE crossover is
           controlled by de_cr / de_f instead)
  optional MOEA/D-only keys: neighbourhood_size (20), neighbourhood_selection_probability
           (0.9), max_replaced_solutions (2), de_cr (1.0), de_f (0.5)

MOEA/D evaluates one offspring per step, so "generation N" here means N *
population_size evaluations, matching how NSGA's generations are counted.
"""

import copy
import math
import os
import random
import shutil
import tempfile

import numpy as np
from jmetal.algorithm.multiobjective import MOEAD
from jmetal.algorithm.multiobjective.nsgaiii import UniformReferenceDirectionFactory
from jmetal.core.observer import Observer
from jmetal.operator.crossover import DifferentialEvolutionCrossover
from jmetal.operator.mutation import IntegerPolynomialMutation
from jmetal.util.aggregation_function import AggregationFunction
from jmetal.util.termination_criterion import StoppingByEvaluations

from moo.observer import MOO_Observer
from moo.optigob_problem2 import Optigob_Problem

# Mirror run_nsga2()'s built-in defaults so both run out of the box with the
# same budget. Keep in sync if those change.
DEFAULT_PARAMS = dict(
    population_size=250,
    mutation_probability=0.01,
    mutation_distribution_index=20,
    max_evaluations=30000,
)
DEFAULT_MOEAD_PARAMS = dict(
    neighbourhood_size=20,
    neighbourhood_selection_probability=0.9,
    max_replaced_solutions=2,
    de_cr=1.0,
    de_f=0.5,
)


class IntegerDifferentialEvolutionCrossover(DifferentialEvolutionCrossover):
    """DE/rand/1/bin for IntegerSolutions: same as jMetalPy's operator, but the
    trial value is clipped to the bounds and rounded to the nearest integer."""

    def execute(self, parents):
        if len(parents) != self.get_number_of_parents():
            raise Exception(f"The number of parents is not {self.get_number_of_parents()}: {len(parents)}")

        child = copy.deepcopy(self.current_individual)
        p0, p1, p2 = (p.variables for p in parents)  # .variables copies the list on every access
        values = child.variables
        forced = random.randint(0, len(values) - 1)

        for i in range(len(values)):
            if random.random() < self.CR or i == forced:
                value = p2[i] + self.F * (p0[i] - p1[i])
                value = min(max(value, child.lower_bound[i]), child.upper_bound[i])
                values[i] = int(math.floor(value + 0.5))

        child.variables = values
        return [child]


class NormalisedTschebycheff(AggregationFunction):
    """Tchebycheff aggregation on objectives scaled to [0, 1] by the running
    ideal (min) and nadir (max) seen so far, so every objective counts equally."""

    def __init__(self, dimension: int):
        self.ideal = np.full(dimension, np.inf)
        self.nadir = np.full(dimension, -np.inf)

    def update(self, vector) -> None:
        self.ideal = np.minimum(self.ideal, vector)
        self.nadir = np.maximum(self.nadir, vector)

    def compute(self, vector, weight_vector) -> float:
        span = self.nadir - self.ideal
        span = np.where(span > 0, span, 1.0)
        diff = np.abs(np.asarray(vector) - self.ideal) / span
        weights = np.asarray(weight_vector, dtype=float)
        weights = np.where(weights == 0, 0.0001, weights)  # same zero-weight handling as jMetalPy
        return float(np.max(diff * weights))


class _GenerationGate(Observer):
    """MOEA/D notifies observers after every single evaluation; NSGA does it once
    per generation. Forward only the notifications that complete a generation so
    MOO_Observer writes one CSV per generation, numbered exactly as for NSGA."""

    def __init__(self, inner: Observer, population_size: int):
        super().__init__()
        self.inner = inner
        self.population_size = population_size

    def update(self, *args, **kwargs):
        if kwargs["EVALUATIONS"] % self.population_size == 0:
            self.inner.update(*args, **kwargs)


def make_weight_vectors(n_objectives: int, n_vectors: int) -> np.ndarray:
    """Exactly n_vectors weight vectors (rows sum to 1) spread over the simplex.

    Takes the smallest Das-Dennis lattice with at least n_vectors points, then
    drops points one at a time (SPEA2-style truncation: the point whose sorted
    neighbour distances are lexicographically smallest) until n_vectors remain.
    The simplex corners are never dropped, so the extreme trade-offs stay covered.
    """
    n_partitions = 1
    while UniformReferenceDirectionFactory.get_n_points(n_partitions, n_objectives) < n_vectors:
        n_partitions += 1
    points = UniformReferenceDirectionFactory(n_dim=n_objectives, n_partitions=n_partitions).compute()

    diff = points[:, None, :] - points[None, :, :]
    dist = np.linalg.norm(diff, axis=2)
    protected = set(np.flatnonzero(points.max(axis=1) >= 1.0 - 1e-12))
    keep = list(range(len(points)))

    while len(keep) > n_vectors:
        sub = dist[np.ix_(keep, keep)].copy()
        np.fill_diagonal(sub, np.inf)
        sub.sort(axis=1)
        sub = np.round(sub, 9)  # lattice distances tie up to float error
        drop = min((pos for pos, i in enumerate(keep) if i not in protected),
                   key=lambda pos: tuple(sub[pos]))
        keep.pop(drop)

    return points[keep]


def run_moead(params=None, on_generation=None, write_results=False):
    """
    Run MOEA/D and return the final population (a list of IntegerSolutions).

    params: see the module docstring; None uses DEFAULT_PARAMS (matching run_nsga2).
    on_generation: optional callable(generation_number), called once per generation
            (only when write_results=True, as with run_nsga2).
    write_results: when True, writes moo/results/gen*_pareto.csv in the same format
            as run_nsga2 (so the Scenario Discovery evaluation page can read it)
            and wipes moo/results/ first. Defaults to False, unlike run_nsga2:
            this function is not wired into the UI, and a casual comparison run
            should not delete the results of a real NSGA run.
    """
    params = params or {}
    lower_bound = params.get("lower_bound")
    upper_bound = params.get("upper_bound")
    objectives = params.get("objectives")

    problem = Optigob_Problem(lower_bound=lower_bound, upper_bound=upper_bound, objectives=objectives)
    n_objectives = problem.number_of_objectives()
    if n_objectives < 2:
        raise ValueError("MOEA/D needs at least two objectives")
    print(f"[moaed] Optimising objectives: {problem.objectives}")

    run = {**DEFAULT_PARAMS, **DEFAULT_MOEAD_PARAMS, **{k: v for k, v in params.items() if v is not None}}
    population_size = run["population_size"]
    neighbourhood_size = min(run["neighbourhood_size"], population_size)

    weights = make_weight_vectors(n_objectives, population_size)

    # jMetalPy reads weight vectors from "<dir>/W<dims>D_<n>.dat" while constructing MOEAD.
    with tempfile.TemporaryDirectory() as weights_dir:
        file_name = f"W{n_objectives}D_{population_size}.dat"
        with open(os.path.join(weights_dir, file_name), "w") as f:
            for row in weights:
                f.write(" ".join(repr(float(x)) for x in row) + "\n")

        algorithm = MOEAD(
            problem=problem,
            population_size=population_size,
            mutation=IntegerPolynomialMutation(
                probability=run["mutation_probability"],
                distribution_index=run["mutation_distribution_index"],
            ),
            crossover=IntegerDifferentialEvolutionCrossover(CR=run["de_cr"], F=run["de_f"]),
            aggregation_function=NormalisedTschebycheff(n_objectives),
            neighbourhood_selection_probability=run["neighbourhood_selection_probability"],
            max_number_of_replaced_solutions=run["max_replaced_solutions"],
            neighbor_size=neighbourhood_size,
            weight_files_path=weights_dir,
            termination_criterion=StoppingByEvaluations(max_evaluations=run["max_evaluations"]),
        )

    if write_results:
        algorithm.observable.register(_GenerationGate(
            MOO_Observer(population_size, on_generation=on_generation, upper_bound=problem.upper_bound,
                         objectives=problem.objectives),
            population_size,
        ))

        results_dir = "moo/results/"
        if os.path.exists(results_dir):
            shutil.rmtree(results_dir)
        os.makedirs(results_dir)

    algorithm.run()
    return algorithm.result()

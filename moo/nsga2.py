from jmetal.algorithm.multiobjective import NSGAII
from jmetal.operator.crossover import IntegerSBXCrossover
from jmetal.operator.mutation import IntegerPolynomialMutation
from jmetal.util.termination_criterion import StoppingByEvaluations

from moo.observer import MOO_Observer
from moo.optigob_problem import Optigob_Problem, build_json_config


def run_nsga2(params=None, on_generation=None):
    """
    Run NSGA-II.

    params: dict with keys population_size, mutation_probability,
            mutation_distribution_index, crossover_probability,
            crossover_distribution_index, max_evaluations,
            and optionally lower_bound / upper_bound (lists of 83 ints).
            If None, uses the original hardcoded defaults.
    on_generation: optional callable(generation_number) called after each generation.
    """
    lower_bound = params.get("lower_bound") if params else None
    upper_bound = params.get("upper_bound") if params else None

    from moo.optigob_problem import DEFAULT_LOWER_BOUND, DEFAULT_UPPER_BOUND
    if lower_bound is not None:
        lb_changes = [i for i in range(len(DEFAULT_LOWER_BOUND)) if lower_bound[i] != DEFAULT_LOWER_BOUND[i]]
        ub_changes = [i for i in range(len(DEFAULT_UPPER_BOUND)) if upper_bound[i] != DEFAULT_UPPER_BOUND[i]]
        print(f"[nsga2] Custom bounds received: {len(lb_changes)} lower overrides, {len(ub_changes)} upper overrides")
        if lb_changes:
            print(f"[nsga2] Lower bound changes at indices: {lb_changes}")
        if ub_changes:
            print(f"[nsga2] Upper bound changes at indices: {ub_changes}")
    else:
        print("[nsga2] No custom bounds — using problem defaults")

    problem = Optigob_Problem(lower_bound=lower_bound, upper_bound=upper_bound)
    print(f"[nsga2] Problem created: lower_bound[7]={problem.lower_bound[7]}, upper_bound[7]={problem.upper_bound[7]} (Pigs WP1 year, raw)")

    if params is None:
        population_size = 300
        mutation_probability = 1.0 / float(problem.number_of_variables())
        mutation_distribution_index = 20
        crossover_probability = 0.9
        crossover_distribution_index = 20
        max_evaluations = 30000
    else:
        population_size = params["population_size"]
        mutation_probability = params["mutation_probability"]
        mutation_distribution_index = params["mutation_distribution_index"]
        crossover_probability = params["crossover_probability"]
        crossover_distribution_index = params["crossover_distribution_index"]
        max_evaluations = params["max_evaluations"]

    algorithm = NSGAII(
        problem=problem,
        population_size=population_size,
        offspring_population_size=population_size,
        mutation=IntegerPolynomialMutation(
            probability=mutation_probability,
            distribution_index=mutation_distribution_index,
        ),
        crossover=IntegerSBXCrossover(
            probability=crossover_probability,
            distribution_index=crossover_distribution_index,
        ),
        termination_criterion=StoppingByEvaluations(
            max_evaluations=max_evaluations,
        ),
    )

    algorithm.observable.register(
        MOO_Observer(population_size, on_generation=on_generation, upper_bound=problem.upper_bound)
    )
    algorithm.run()

    result = algorithm.result()

    print(f"Number of solutions: {len(result)}")
    for solution in result:
        print(
            f"Objectives: {solution.objectives}, "
            f"Variables: {solution.variables[:3]}, "
            f"Config: {build_json_config(solution.variables)}"
        )

    return result

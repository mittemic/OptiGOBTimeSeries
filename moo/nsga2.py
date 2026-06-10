from jmetal.algorithm.multiobjective import NSGAII
from jmetal.operator.crossover import IntegerSBXCrossover
from jmetal.operator.mutation import IntegerPolynomialMutation
from jmetal.util.termination_criterion import StoppingByEvaluations

from moo.observer import MOO_Observer
from moo.optigob_problem import Optigob_Problem, build_json_config

def run_nsga2():
    problem = Optigob_Problem()

    algorithm = NSGAII(
        problem=problem,
        population_size=300,
        offspring_population_size=300,
        mutation=IntegerPolynomialMutation(
            probability= 1.0 / float(problem.number_of_variables()),
            distribution_index=20),
        crossover=IntegerSBXCrossover(
            probability=0.9,
            distribution_index=20
        ),
        termination_criterion=StoppingByEvaluations(
            max_evaluations=30000,
        )
    )

    algorithm.observable.register(MOO_Observer(algorithm.offspring_population_size))
    algorithm.run()

    result = algorithm.result()

    print(f"Number of solution: {len(result)}")

    for solution in result:
        print(
            f"Objectives: {solution.objectives}, "
            f"Variables: {solution.variables[:3]}, "
            f"Config: {build_json_config(solution.variables)}"
        )
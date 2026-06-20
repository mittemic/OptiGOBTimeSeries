from jmetal.core.observer import Observer
from jmetal.util.ranking import FastNonDominatedRanking
from moo.optigob_problem import build_json_config, heal_variables
import csv

class MOO_Observer(Observer):

    def __init__(self, population_size, on_generation=None):
        super().__init__()
        self.population_size = population_size
        self.on_generation = on_generation  # optional callable(generation_number)

    def update(self, *args, **kwargs):

        evaluations = kwargs["EVALUATIONS"]
        generation = evaluations // self.population_size
        population = kwargs["SOLUTIONS"]

        ranking = FastNonDominatedRanking()
        ranking.compute_ranking(population)

        pareto_front = ranking.get_subfront(0)

        print("Generation " + str(generation)  + " complete")

        pareto_file = "moo/results/gen" + str(generation) + "_pareto.csv"

        with open(pareto_file, "w") as file:
            writer = csv.writer(file)

            writer.writerow(["co2e", "hnv", "protein", "hwp", "json"])

            for solution in pareto_front:
                vars_list = list(solution.variables)
                heal_variables(vars_list)
                writer.writerow([solution.objectives[0], solution.objectives[1], solution.objectives[2], solution.objectives[3], build_json_config(vars_list)])

        if self.on_generation is not None:
            self.on_generation(generation)
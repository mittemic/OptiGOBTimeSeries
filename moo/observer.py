from jmetal.core.observer import Observer
from jmetal.util.ranking import FastNonDominatedRanking
from moo.optigob_problem2 import build_json_config, ALL_OBJECTIVES#, heal_variables
import csv

class MOO_Observer(Observer):

    def __init__(self, population_size, on_generation=None, upper_bound=None, objectives=None):
        super().__init__()
        self.population_size = population_size
        self.on_generation = on_generation
        self.upper_bound = upper_bound
        self.objectives = list(objectives) if objectives is not None else list(ALL_OBJECTIVES)

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

            writer.writerow(self.objectives + ["json"])

            for solution in pareto_front:
                vars_list = list(solution.variables)
                #heal_variables(vars_list, self.upper_bound)
                row = [solution.objectives[i] for i in range(len(self.objectives))]
                row.append(build_json_config(vars_list))
                writer.writerow(row)

        if self.on_generation is not None:
            self.on_generation(generation)
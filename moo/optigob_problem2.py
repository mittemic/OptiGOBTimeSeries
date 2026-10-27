from jmetal.core.problem import IntegerProblem
from jmetal.core.solution import IntegerSolution

from configuration.keys import *
from optigob.optigob import Optigob

DEFAULT_LOWER_BOUND = [0,0,         # forestry
                       0,0,0,0,0,   # afforestation
                       0,0,         # pigs
                       0,0,         # poultry
                       0,0,         # sheep
                       0,0,         # crops
                       0,0,0,0,     # cattle
                       0,0,0,       # organic soils
                       0,2030, 0,   # ad implementation
                       0,2030,      # ad additional biomethane
                       0,2030]      # ad o2 removal
DEFAULT_UPPER_BOUND = [1,1,         # forestry
                       1,1,30,1,1,  # afforestation
                       2,200,       # pigs
                       2,200,       # poultry
                       2,200,       # sheep
                       2,200,       # crops
                       2,200,2,2,   # cattle
                       100,100,100, # organic soils
                       1,2050,1,    # ad implementation
                       20,2050,     # ad additional biomethane
                       20,2050]     # ad o2 removal

DEFAULT_INDICES = ["ef_harvest", "ef_ccs",
                   "af_harvest", "af_ccs", "af_rate", "af_broadleaf", "af_organic_soil",
                   "pigs_abatement", "pigs_scaler",
                   "poultry_abatement", "poultry_scaler",
                   "sheep_abatement", "sheep_scaler",
                   "crops_abatement", "crops_scaler",
                   "cattle_abatement", "cattle_scaler", "cattle_dairy_prod", "cattle_beef_prod",
                   "org_soil_under_grass", "industrial_peat", "domestic_peat",
                   "ad_impl", "ad_impl_year", "ad_ccs",
                   "ad_add_biomethane", "ad_add_biomethane_year",
                   "ad_co2_removal", "ad_co2_removal_year"
                   ]

# Canonical objective keys, in a fixed order shared with the CSV/UI layer
# (moo/observer.py, pages/03 and 04). Each maps to (parameter, get_objective
# filter, sign) — sign is +1 to minimise (co2e) or -1 to maximise (the rest),
# since NSGA-II always minimises.
ALL_OBJECTIVES = ["co2e", "hnv", "protein", "hwp"]
_OBJECTIVE_SPECS = {
    "co2e": (CO2E, "net_zero_co2e", 1.0),
    "hnv": (BIODIVERSITY, "total_", -1.0),
    "protein": (PROTEIN, "total_", -1.0),
    "hwp": (HWP, "total_", -1.0),
}
# Sign each objective is stored with in solution.objectives / the results CSV.
# Multiplying a stored value by its sign recovers the true (human-readable) value
# — used by the UI layer to display maximised objectives as positive numbers
# while the algorithm keeps minimising all four.
OBJECTIVE_SIGN = {k: v[2] for k, v in _OBJECTIVE_SPECS.items()}


class Optigob_Problem(IntegerProblem):
    def __init__(self, lower_bound=None, upper_bound=None, objectives=None):
        super().__init__()
        self.lower_bound = list(lower_bound) if lower_bound is not None else list(DEFAULT_LOWER_BOUND)
        self.upper_bound = list(upper_bound) if upper_bound is not None else list(DEFAULT_UPPER_BOUND)
        # Preserve canonical order regardless of the order `objectives` was given in.
        self.objectives = [k for k in ALL_OBJECTIVES if objectives is None or k in objectives]
        if not self.objectives:
            raise ValueError("Optigob_Problem needs at least one objective")

    def number_of_objectives(self) -> int:
        return len(self.objectives)

    def number_of_constraints(self) -> int:
        return 0

    def evaluate(self, solution: IntegerSolution) -> IntegerSolution:
        solution = self.heal(solution)
        json_config = build_json_config(solution.variables)

        optigob = Optigob(json_config=json_config, db_file_path="data/database.db")
        optigob.run()

        for i, key in enumerate(self.objectives):
            parameter, filter, sign = _OBJECTIVE_SPECS[key]
            solution.objectives[i] = sign * get_objective(optigob=optigob, parameter=parameter, filter=filter)

        return solution


    def name(self) -> str:
        return "Optigob_Problem"

    def heal(self, solution):
        vars_list = list(solution.variables)
        #heal_variables(vars_list, self.upper_bound)
        solution.variables = vars_list
        return solution


def build_json_config(solution):

    abatement_types = ["2020 BL", "MACC", "Frontier"]
    bool_types = [True, False]
    harvest_types = ["low", "high"]
    cattle_prod_types = ["2020 Prod", "Medium increase", "Strong increase"]

    ef_harvest = harvest_types[solution[DEFAULT_INDICES.index("ef_harvest")]]
    ef_ccs = bool_types[solution[DEFAULT_INDICES.index("ef_ccs")]]
    af_harvest = harvest_types[solution[DEFAULT_INDICES.index("af_harvest")]]
    af_ccs = bool_types[solution[DEFAULT_INDICES.index("af_ccs")]]
    af_rate = float(solution[DEFAULT_INDICES.index("af_rate")])
    broadleaf_frac = 0.5 if solution[DEFAULT_INDICES.index("af_broadleaf")] == 0 else 0.3
    organic_soil_frac = 0.15 if solution[DEFAULT_INDICES.index("af_organic_soil")] == 0 else 0
    pigs_waypoint1_abatement_type = abatement_types[solution[DEFAULT_INDICES.index("pigs_abatement")]]
    pigs_waypoint1_scaler = float(solution[DEFAULT_INDICES.index("pigs_scaler")]) / 100.0
    poultry_waypoint1_abatement_type = abatement_types[solution[DEFAULT_INDICES.index("poultry_abatement")]]
    poultry_waypoint1_scaler = float(solution[DEFAULT_INDICES.index("poultry_scaler")]) / 100.0
    sheep_waypoint1_abatement_type = abatement_types[solution[DEFAULT_INDICES.index("sheep_abatement")]]
    sheep_waypoint1_scaler = float(solution[DEFAULT_INDICES.index("sheep_scaler")]) / 100.0
    crops_waypoint1_abatement_type = abatement_types[solution[DEFAULT_INDICES.index("crops_abatement")]]
    crops_waypoint1_scaler = float(solution[DEFAULT_INDICES.index("crops_scaler")]) / 100.0

    cattle_waypoint1_abatement_type = abatement_types[solution[DEFAULT_INDICES.index("cattle_abatement")]]
    cattle_waypoint1_scaler = float(solution[DEFAULT_INDICES.index("cattle_scaler")]) / 100.0
    cattle_waypoint1_dairy_prod = cattle_prod_types[solution[DEFAULT_INDICES.index("cattle_dairy_prod")]]
    cattle_waypoint1_beef_prod = cattle_prod_types[solution[DEFAULT_INDICES.index("cattle_beef_prod")]]

    organic_soil_under_grass_waypoint1_rewetting_ratio = float(solution[DEFAULT_INDICES.index("org_soil_under_grass")]) / 100.0
    industrial_peat_waypoint1_rewetting_ratio = float(solution[DEFAULT_INDICES.index("industrial_peat")]) / 100.0
    domestic_peat_waypoint1_rewetting_ratio = float(solution[DEFAULT_INDICES.index("domestic_peat")]) / 100.0

    ad_implementation = bool_types[solution[DEFAULT_INDICES.index("ad_impl")]]
    ad_implementation_year = solution[DEFAULT_INDICES.index("ad_impl_year")]
    ad_ccs = bool_types[solution[DEFAULT_INDICES.index("ad_ccs")]]
    ad_grass_biomethane = solution[DEFAULT_INDICES.index("ad_add_biomethane")] * 1000
    ad_additional_biomethane_year = solution[DEFAULT_INDICES.index("ad_add_biomethane_year")]
    ad_co2_removal = solution[DEFAULT_INDICES.index("ad_co2_removal")] * 1000
    ad_co2_removal_year = solution[DEFAULT_INDICES.index("ad_co2_removal_year")]

    json_config = {
        "baseline_year": 2020,
        "target_year": 2120,
        "forestry": [
            {
                "name": "existing_forest",
                "harvest": ef_harvest,
                "ccs": ef_ccs,
            },
            {
                "name": "afforestation",
                "afforestation_rate": af_rate,
                "broadleaf_frac": broadleaf_frac,
                "organic_soil": organic_soil_frac,
                "harvest": af_harvest,
                "ccs": af_ccs,
            },
        ],
        "non_cattle_agriculture": [
            {
                "name": "Pigs",
                "abatement": "2020 BL",
                "productivity": "2020 Prod",
                "waypoints": [
                    {
                        "year": 2030,
                        "abatement": pigs_waypoint1_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": pigs_waypoint1_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    }
                ]
            },
            {
                "name": "Poultry",
                "abatement": "2020 BL",
                "productivity": "2020 Prod",
                "waypoints": [
                    {
                        "year": 2030,
                        "abatement": poultry_waypoint1_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": poultry_waypoint1_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    }
                ]
            },
            {
                "name": "Sheep",
                "abatement": "2020 BL",
                "productivity": "2020 Prod",
                "waypoints": [
                    {
                        "year": 2030,
                        "abatement": sheep_waypoint1_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": sheep_waypoint1_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    }
                ]
            },
            {
                "name": "Crops",
                "abatement": "2020 BL",
                "productivity": "2020 Prod",
                "waypoints": [
                    {
                        "year": 2030,
                        "abatement": crops_waypoint1_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": crops_waypoint1_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    }
                ]
            }
        ],
        "cattle_systems": {
            "abatement": "2020 BL",
            "productivity": "2020 Prod",
            "waypoints": [
                {
                    "year": 2030,
                    "abatement": cattle_waypoint1_abatement_type,
                    "scaler": cattle_waypoint1_scaler,
                    "scale_absolute_or_percentage": False,
                    "scale_parameter": "co2e",
                    "dairy_productivity": cattle_waypoint1_dairy_prod,
                    "beef_productivity": cattle_waypoint1_beef_prod,
                }
            ],
        },
        "organic_soils": [
            {
                "name": "Organic soil under grass",
                "drainage_status": [
                    "Drained",
                    "Rewetted"
                ],
                "waypoints": [
                    {
                        "year": 2030,
                        "rewetting_ratio": organic_soil_under_grass_waypoint1_rewetting_ratio
                    }
                ]
            },
            {
                "name": "Near natural wetlands",
                "drainage_status": ["Natural"]
            },
            {
                "name": "Industrial peat",
                "drainage_status": [
                    "Drained",
                    "Rewetted"
                ],
                "waypoints": [
                    {
                        "year": 2030,
                        "rewetting_ratio": industrial_peat_waypoint1_rewetting_ratio
                    }
                ]
            },
            {
                "name": "Domestic peat",
                "drainage_status": [
                    "Drained",
                    "Rewetted"
                ],
                "waypoints": [
                    {
                        "year": 2030,
                        "rewetting_ratio": domestic_peat_waypoint1_rewetting_ratio
                    }
                ]
            }
        ]
    }

    ad_emissions = {
        "implementation_year": ad_implementation_year,
        "ccs": ad_ccs,
        "additional_biomethane_year": ad_additional_biomethane_year,
        "additional_grass_biomethane": ad_grass_biomethane,
        "willow_year": ad_co2_removal_year,
        "cdr_bioenergy": ad_co2_removal
    }

    if ad_implementation:
        json_config["ad_emissions"] = ad_emissions

    return json_config

def get_objective(optigob, parameter, filter="total_"):
    parameter_list = optigob.get_evaluation(parameter)
    total = 0
    for n, l in parameter_list:
        if filter in n:
            total += l[30]

    return total
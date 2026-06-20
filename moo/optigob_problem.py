from jmetal.core.problem import IntegerProblem
from jmetal.core.solution import IntegerSolution

from configuration.keys import *
from optigob.optigob import Optigob

max_year = 212
min_year = 203

_WAYPOINT_GROUPS = [
    (7, 10, 13), (16, 19, 22), (25, 28, 31), (34, 37, 40),
    (43, 48, 53), (58, 60, 62), (64, 66, 68), (70, 72, 74), (77, 80, 82),
]

DEFAULT_LOWER_BOUND = [0,0,0,0,0,0,0,min_year,0,0,min_year,0,0,min_year,0,0,min_year,0,0,min_year,0,0,min_year,0,0,min_year,0,0,min_year,0,0,min_year,0,0,min_year,0,0,min_year,0,0,min_year,0,0,min_year,0,0,0,0,min_year,0,0,0,0,min_year,0,0,0,0,min_year,0,min_year,0,min_year,0,min_year,0,min_year,0,min_year,0,min_year,0,min_year,0,min_year,0,0,min_year,0,0,min_year,0,min_year]
DEFAULT_UPPER_BOUND = [1,1,1,1,20,1,1,max_year,2,200,max_year,2,200,max_year,2,200,max_year,2,200,max_year,2,200,max_year,2,200,max_year,2,200,max_year,2,200,max_year,2,200,max_year,2,200,max_year,2,200,max_year,2,200,max_year,2,200,2,2,max_year,2,200,2,2,max_year,2,200,2,2,max_year,100,max_year,100,max_year,100,max_year,100,max_year,100,max_year,100,max_year,100,max_year,100,max_year,100,1,max_year,1,20000,max_year,20000,max_year]


def heal_variables(variables, upper_bound=None):
    """Enforce strictly-increasing waypoint years within each system group.
    Modifies the list in-place and returns it. Safe to call on already-healed variables."""
    for wpi1, wpi2, wpi3 in _WAYPOINT_GROUPS:
        ub3 = upper_bound[wpi3] if upper_bound is not None else max_year
        temp = sorted([variables[wpi1], variables[wpi2], variables[wpi3]])
        temp[1] = max(temp[1], temp[0] + 1)
        temp[2] = max(temp[2], temp[1] + 1)
        if temp[2] > ub3:
            temp[2] = ub3
            temp[1] = min(temp[1], ub3 - 1)
            temp[0] = min(temp[0], ub3 - 2)
        variables[wpi1] = temp[0]
        variables[wpi2] = temp[1]
        variables[wpi3] = temp[2]
    return variables


class Optigob_Problem(IntegerProblem):
    def __init__(self, lower_bound=None, upper_bound=None):
        super().__init__()
        self.lower_bound = list(lower_bound) if lower_bound is not None else list(DEFAULT_LOWER_BOUND)
        self.upper_bound = list(upper_bound) if upper_bound is not None else list(DEFAULT_UPPER_BOUND)

    def number_of_objectives(self) -> int:
        return 4

    def number_of_constraints(self) -> int:
        return 0

    def evaluate(self, solution: IntegerSolution) -> IntegerSolution:
        solution = self.heal(solution)
        json_config = build_json_config(solution.variables)

        optigob = Optigob(json_config=json_config, db_file_path="data/database.db")
        optigob.run()

        solution.objectives[0] = get_objective(optigob=optigob, parameter=CO2E, filter="net_zero_co2e")
        solution.objectives[1] = -get_objective(optigob=optigob, parameter=BIODIVERSITY)
        solution.objectives[2] = -get_objective(optigob=optigob, parameter=PROTEIN)
        solution.objectives[3] = -get_objective(optigob=optigob, parameter=HWP)

        return solution


    def name(self) -> str:
        return "Optigob_Problem"

    def heal(self, solution):
        vars_list = list(solution.variables)
        heal_variables(vars_list, self.upper_bound)
        solution.variables = vars_list
        return solution


def build_json_config(solution):

    abatement_types = ["2020 BL", "MACC", "Frontier"]
    bool_types = [True, False]
    harvest_types = ["low", "high"]
    cattle_prod_types = ["2020 Prod", "Medium increase", "Strong increase"]

    ef_harvest = harvest_types[solution[0]]
    ef_ccs = bool_types[solution[1]]
    af_harvest = harvest_types[solution[2]]
    af_ccs = bool_types[solution[3]]
    af_rate = float(solution[4]) / 2.0
    broadleaf_frac = 0.5 if solution[5] == 0 else 0.3
    organic_soil_frac = 0.15 if solution[6] == 0 else 0
    pigs_waypoint1_year = solution[7] * 10
    pigs_waypoint1_abatement_type = abatement_types[solution[8]]
    pigs_waypoint1_scaler = float(solution[9]) / 100.0
    pigs_waypoint2_year = solution[10] * 10
    pigs_waypoint2_abatement_type = abatement_types[solution[11]]
    pigs_waypoint2_scaler = float(solution[12]) / 100.0
    pigs_waypoint3_year = solution[13] * 10
    pigs_waypoint3_abatement_type = abatement_types[solution[14]]
    pigs_waypoint3_scaler = float(solution[15]) / 100.0
    poultry_waypoint1_year = solution[16] * 10
    poultry_waypoint1_abatement_type = abatement_types[solution[17]]
    poultry_waypoint1_scaler = float(solution[18]) / 100.0
    poultry_waypoint2_year = solution[19] * 10
    poultry_waypoint2_abatement_type = abatement_types[solution[20]]
    poultry_waypoint2_scaler = float(solution[21]) / 100.0
    poultry_waypoint3_year = solution[22] * 10
    poultry_waypoint3_abatement_type = abatement_types[solution[23]]
    poultry_waypoint3_scaler = float(solution[24]) / 100.0
    sheep_waypoint1_year = solution[25] * 10
    sheep_waypoint1_abatement_type = abatement_types[solution[26]]
    sheep_waypoint1_scaler = float(solution[27]) / 100.0
    sheep_waypoint2_year = solution[28] * 10
    sheep_waypoint2_abatement_type = abatement_types[solution[29]]
    sheep_waypoint2_scaler = float(solution[30]) / 100.0
    sheep_waypoint3_year = solution[31] * 10
    sheep_waypoint3_abatement_type = abatement_types[solution[32]]
    sheep_waypoint3_scaler = float(solution[33]) / 100.0
    crops_waypoint1_year = solution[34] * 10
    crops_waypoint1_abatement_type = abatement_types[solution[35]]
    crops_waypoint1_scaler = float(solution[36]) / 100.0
    crops_waypoint2_year = solution[37] * 10
    crops_waypoint2_abatement_type = abatement_types[solution[38]]
    crops_waypoint2_scaler = float(solution[39]) / 100.0
    crops_waypoint3_year = solution[40] * 10
    crops_waypoint3_abatement_type = abatement_types[solution[41]]
    crops_waypoint3_scaler = float(solution[42]) / 100.0
    cattle_waypoint1_year = solution[43] * 10
    cattle_waypoint1_abatement_type = abatement_types[solution[44]]
    cattle_waypoint1_scaler = float(solution[45]) / 100.0
    cattle_waypoint1_dairy_prod = cattle_prod_types[solution[46]]
    cattle_waypoint1_beef_prod = cattle_prod_types[solution[47]]
    cattle_waypoint2_year = solution[48] * 10
    cattle_waypoint2_abatement_type = abatement_types[solution[49]]
    cattle_waypoint2_scaler = float(solution[50]) / 100.0
    cattle_waypoint2_dairy_prod = cattle_prod_types[solution[51]]
    cattle_waypoint2_beef_prod = cattle_prod_types[solution[52]]
    cattle_waypoint3_year = solution[53] * 10
    cattle_waypoint3_abatement_type = abatement_types[solution[54]]
    cattle_waypoint3_scaler = float(solution[55]) / 100.0
    cattle_waypoint3_dairy_prod = cattle_prod_types[solution[56]]
    cattle_waypoint3_beef_prod = cattle_prod_types[solution[57]]
    organic_soil_under_grass_waypoint1_year = solution[58] * 10
    organic_soil_under_grass_waypoint1_rewetting_ratio = float(solution[59]) / 100.0
    organic_soil_under_grass_waypoint2_year = solution[60] * 10
    organic_soil_under_grass_waypoint2_rewetting_ratio = float(solution[61]) / 100.0
    organic_soil_under_grass_waypoint3_year = solution[62] * 10
    organic_soil_under_grass_waypoint3_rewetting_ratio = float(solution[63]) / 100.0
    industrial_peat_waypoint1_year = solution[64] * 10
    industrial_peat_waypoint1_rewetting_ratio = float(solution[65]) / 100.0
    industrial_peat_waypoint2_year = solution[66] * 10
    industrial_peat_waypoint2_rewetting_ratio = float(solution[67]) / 100.0
    industrial_peat_waypoint3_year = solution[68] * 10
    industrial_peat_waypoint3_rewetting_ratio = float(solution[69]) / 100.0
    domestic_peat_waypoint1_year = solution[70] * 10
    domestic_peat_waypoint1_rewetting_ratio = float(solution[71]) / 100.0
    domestic_peat_waypoint2_year = solution[72] * 10
    domestic_peat_waypoint2_rewetting_ratio = float(solution[73]) / 100.0
    domestic_peat_waypoint3_year = solution[74] * 10
    domestic_peat_waypoint3_rewetting_ratio = float(solution[75]) / 100.0
    ad_implementation = bool_types[solution[76]]
    ad_implementation_year = solution[77] * 10
    ad_ccs = bool_types[solution[78]]
    ad_grass_biomethane = solution[79]
    ad_additional_biomethane_year = solution[80] * 10
    ad_co2_removal = solution[81]
    ad_co2_removal_year = solution[82] * 10

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
                        "year": pigs_waypoint1_year,
                        "abatement": pigs_waypoint1_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": pigs_waypoint1_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    },
                    {
                        "year": pigs_waypoint2_year,
                        "abatement": pigs_waypoint2_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": pigs_waypoint2_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    },
                    {
                        "year": pigs_waypoint3_year,
                        "abatement": pigs_waypoint3_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": pigs_waypoint3_scaler,
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
                        "year": poultry_waypoint1_year,
                        "abatement": poultry_waypoint1_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": poultry_waypoint1_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    },
                    {
                        "year": poultry_waypoint2_year,
                        "abatement": poultry_waypoint2_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": poultry_waypoint2_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    },
                    {
                        "year": poultry_waypoint3_year,
                        "abatement": poultry_waypoint3_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": poultry_waypoint3_scaler,
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
                        "year": sheep_waypoint1_year,
                        "abatement": sheep_waypoint1_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": sheep_waypoint1_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    },
                    {
                        "year": sheep_waypoint2_year,
                        "abatement": sheep_waypoint2_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": sheep_waypoint2_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    },
                    {
                        "year": sheep_waypoint3_year,
                        "abatement": sheep_waypoint3_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": sheep_waypoint3_scaler,
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
                        "year": crops_waypoint1_year,
                        "abatement": crops_waypoint1_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": crops_waypoint1_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    },
                    {
                        "year": crops_waypoint2_year,
                        "abatement": crops_waypoint2_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": crops_waypoint2_scaler,
                        "scale_parameter": "co2e",
                        "scale_absolute_or_percentage": False
                    },
                    {
                        "year": crops_waypoint3_year,
                        "abatement": crops_waypoint3_abatement_type,
                        "productivity": "2020 Prod",
                        "scaler": crops_waypoint3_scaler,
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
                    "year": cattle_waypoint1_year,
                    "abatement": cattle_waypoint1_abatement_type,
                    "scaler": cattle_waypoint1_scaler,
                    "scale_absolute_or_percentage": False,
                    "scale_parameter": "co2e",
                    "dairy_productivity": cattle_waypoint1_dairy_prod,
                    "beef_productivity": cattle_waypoint1_beef_prod,
                },
                {
                    "year": cattle_waypoint2_year,
                    "abatement": cattle_waypoint2_abatement_type,
                    "scaler": cattle_waypoint2_scaler,
                    "scale_absolute_or_percentage": False,
                    "scale_parameter": "co2e",
                    "dairy_productivity": cattle_waypoint2_dairy_prod,
                    "beef_productivity": cattle_waypoint2_beef_prod,
                },
                {
                    "year": cattle_waypoint3_year,
                    "abatement": cattle_waypoint3_abatement_type,
                    "scaler": cattle_waypoint3_scaler,
                    "scale_absolute_or_percentage": False,
                    "scale_parameter": "co2e",
                    "dairy_productivity": cattle_waypoint3_dairy_prod,
                    "beef_productivity": cattle_waypoint3_beef_prod,
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
                        "year": organic_soil_under_grass_waypoint1_year,
                        "rewetting_ratio": organic_soil_under_grass_waypoint1_rewetting_ratio
                    },
                    {
                        "year": organic_soil_under_grass_waypoint2_year,
                        "rewetting_ratio": organic_soil_under_grass_waypoint2_rewetting_ratio
                    },
                    {
                        "year": organic_soil_under_grass_waypoint3_year,
                        "rewetting_ratio": organic_soil_under_grass_waypoint3_rewetting_ratio
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
                        "year": industrial_peat_waypoint1_year,
                        "rewetting_ratio": industrial_peat_waypoint1_rewetting_ratio
                    },
                    {
                        "year": industrial_peat_waypoint2_year,
                        "rewetting_ratio": industrial_peat_waypoint2_rewetting_ratio
                    },
                    {
                        "year": industrial_peat_waypoint3_year,
                        "rewetting_ratio": industrial_peat_waypoint3_rewetting_ratio
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
                        "year": domestic_peat_waypoint1_year,
                        "rewetting_ratio": domestic_peat_waypoint1_rewetting_ratio
                    },
                    {
                        "year": domestic_peat_waypoint2_year,
                        "rewetting_ratio": domestic_peat_waypoint2_rewetting_ratio
                    },
                    {
                        "year": domestic_peat_waypoint3_year,
                        "rewetting_ratio": domestic_peat_waypoint3_rewetting_ratio
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
    sum = 0
    for n, l in parameter_list:
        if filter in n:
            for i in l:
                sum = sum + i

    return sum
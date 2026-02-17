from optigob.optigob import Optigob
from configuration.keys import *
import pytest

db_file_path = "data/database.db"

config1 = {
    "baseline_year":2020,
    "target_year":2100,
    "non_cattle_agriculture":[
        {
            "name":"Pigs",
            "abatement":"2020 BL",
            "productivity":"2020 Prod",
            "waypoints":[
                {
                    "year":2030,
                    "abatement":"2020 BL",
                    "productivity":"2020 Prod",
                    "scaler":376.2,
                    "scale_parameter":"co2e",
                    "scale_absolute_or_percentage":True
                },
                {
                    "year":2040,
                    "abatement":"2020 BL",
                    "productivity":"2020 Prod",
                    "scaler":276.2,
                    "scale_parameter":"co2e",
                    "scale_absolute_or_percentage":True
                }
            ]
        }],
    "cattle_systems":
        {
            "abatement":"2020 BL",
            "productivity":"2020 Prod",
            "waypoints":[
                {
                    "year":2030,
                    "abatement":"2020 BL",
                    "scaler":1,
                    "scale_parameter":"co2e",
                    "scale_absolute_or_percentage":False,
                    "dairy_productivity":"2020 Prod",
                    "beef_productivity":"Medium increase"
                },
                {
                    "year":2040,
                    "abatement":"2020 BL",
                    "scaler":0.7,
                    "scale_parameter":"co2e",
                    "scale_absolute_or_percentage":False,
                    "dairy_productivity":"Medium increase",
                    "beef_productivity":"Medium increase"
                },
                {
                    "year":2050,
                    "abatement":"MACC",
                    "scaler":0.7,
                    "scale_parameter":"co2e",
                    "scale_absolute_or_percentage":False,
                    "dairy_productivity":"Strong increase",
                    "beef_productivity":"Strong increase"
                }
            ]
        }
}

@pytest.mark.parametrize(
    "test_years, config, test_metric, expected_results",
    [
        ([2020, 2030, 2040, 2050], config1, ["co2e", "human_consumed_protein"], [[(11172.941, 6756.77), (8560998737.33, 286692610.1)],
                                                                                 [(11272.941, 6756.77), (8637621344.9078078484, 290960579.102347552247)],
                                                                                 [(11272.941, 1334.9967), (9507101947.4794075427, 57487736.4379315774405)],
                                                                                 [(11272.941, 1334.9967), (12733098399.409129082, 72102213.0620089766606)]])
    ],
)

def test_non_cattle_agriculture(test_years, config, test_metric, expected_results):
    optigob = Optigob(json_config=config, db_file_path=db_file_path)
    optigob.run()

    dairy = optigob.get_field(CATTLE_AGRICULTURE).get_system(CATTLE_AGRICULTURE_DAIRY)
    beef = optigob.get_field(CATTLE_AGRICULTURE).get_system(CATTLE_AGRICULTURE_BEEF)

    for i in range(len(test_years)):
        idx = test_years[i] - optigob.baseline_year
        for j in range(len(test_metric)):
            expected_result = expected_results[i][j][0]
            actual_result = dairy.time_series[test_metric[j]][idx]
            assert round(actual_result,2) == round(expected_result,2)
            expected_result = expected_results[i][j][1]
            actual_result = beef.time_series[test_metric[j]][idx]
            assert round(actual_result,2) == round(expected_result,2)

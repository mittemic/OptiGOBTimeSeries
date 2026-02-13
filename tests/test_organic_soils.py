from optigob.optigob import Optigob
from configuration.keys import *
import pytest

db_file_path = "data/database.db"

@pytest.mark.parametrize(
    "test_years, soil_name, way_points, test_metric, expected_results",
    [
        ([2020, 2030, 2040], "Organic soil under grass", [(2030, 0.1), (2040, 0.3)], "co2e", [(444.55, 1334.04), (400.09, 1428.98), (311.18, 1618.86)]),
        ([2020, 2030, 2040], "Organic soil under grass", [(2030, 0.1), (2040, 0.3)], "hnv_area_ratio", [(0, 198126.61), (0, 212226.61), (0, 240426.61)])
    ],
)

def test_organic_soils(test_years, soil_name, way_points, test_metric, expected_results):

    waypoints = []
    for (y, rr) in way_points:
        waypoints.append({"year":y, "rewetting_ratio":rr})

    config = {
        "baseline_year": 2020,
        "target_year": 2100,
        ORGANIC_SOILS: [
            {
                "name": soil_name,
                "drainage_status": ["Drained", "Rewetted"],
                "waypoints": waypoints
            }
        ],
    }

    optigob = Optigob(json_config=config, db_file_path=db_file_path)
    optigob.run()

    soil = optigob.get_field(ORGANIC_SOILS).get_system(soil_name)
    for i in range(len(test_years)):
        idx = test_years[i] - optigob.baseline_year
        expected_value = expected_results[i][0]
        actual_value = soil.time_series["Drained_" + test_metric][idx]
        assert  round(actual_value, 2) == round(expected_value, 2)
        assert round(soil.time_series["Rewetted_" + test_metric][idx],2) == round(expected_results[i][1],2)

from dataclasses import dataclass

from configuration.keys import *
from optigob.systems.abstract_factory import Field, WayPointSystem
from optigob.systems.agriculture import AgricultureSystem, AgricultureWayPoint

@dataclass()
class CattleWayPoint(AgricultureWayPoint):
    dairy_productivity: str
    beef_productivity:str

    def get_data(self, db_manager, system_name, agriculture):
        if system_name == CATTLE_AGRICULTURE_DAIRY:
            kwargs = db_manager.get_agriculture_data(abatement=self.abatement,
                                                     productivity=self.dairy_productivity,
                                                     system=system_name,
                                                     agriculture=agriculture)
            return kwargs
        elif system_name == CATTLE_AGRICULTURE_BEEF:
            kwargs = db_manager.get_agriculture_data(abatement=self.abatement,
                                                     productivity=self.beef_productivity,
                                                     system=system_name,
                                                     agriculture=agriculture)
            return kwargs

        return None

@dataclass
class CattleSystem(AgricultureSystem):

    def load_data(self, db_manager):
        kwargs = db_manager.get_agriculture_data(abatement=self.baseline_abatement,
                                                 productivity=self.baseline_productivity,
                                                 system=self.name,
                                                 agriculture=TABLE_CATTLE)
        self.init_timeseries(kwargs)

    def run(self, baseline_year, target_year, db_manager):
        pass

class CattleAgriculture(Field):
    def __init__(self, data):
        self.name = CATTLE_AGRICULTURE

        way_points = []
        for way_point in data[WAY_POINTS]:
            way_points.append(CattleWayPoint(**way_point))

        dairy = CattleSystem(name=CATTLE_AGRICULTURE_DAIRY,
                                  baseline_abatement=data[AGRICULTURE_BASELINE_ABATEMENT],
                                  baseline_productivity=data[AGRICULTURE_BASELINE_PRODUCTIVITY],
                                  waypoints=way_points,
                                  time_series={})

        beef = CattleSystem(name=CATTLE_AGRICULTURE_BEEF,
                                  baseline_abatement=data[AGRICULTURE_BASELINE_ABATEMENT],
                                  baseline_productivity=data[AGRICULTURE_BASELINE_PRODUCTIVITY],
                                  waypoints=way_points,
                                  time_series={})

        self.systems = [dairy, beef]

    def run_cattle_systems(self, baseline_year, target_year, db_manager, nca):
        for waypoint in self.systems[0].waypoints:
            assert isinstance(waypoint, CattleWayPoint)
            dairy_waypoint_data = waypoint.get_data(db_manager=db_manager,
                                                    system_name=CATTLE_AGRICULTURE_DAIRY,
                                                    agriculture=TABLE_CATTLE)
            beef_waypoint_data = waypoint.get_data(db_manager=db_manager,
                                                   system_name=CATTLE_AGRICULTURE_BEEF,
                                                   agriculture=TABLE_CATTLE)

            nca_values = []
            for system in nca.systems:
                if len(nca_values) == 0:
                    nca_values = system.time_series[waypoint.scale_parameter]
                else:
                    nca_values = [x+y for (x,y) in zip(nca_values, system.time_series[waypoint.scale_parameter])]

            baseline = (nca_values[0]
                        + self.systems[0].time_series[waypoint.scale_parameter][0]
                        + self.systems[1].time_series[waypoint.scale_parameter][0])

            if waypoint.scale_absolute_or_percentage:
                limit = waypoint.scaler
            else:
                limit = baseline * waypoint.scaler

            budget = limit - nca_values[waypoint.year - baseline_year]
            current_dairy = self.systems[0].get_parameters_by_index(-1)
            current_beef = self.systems[1].get_parameters_by_index(-1)

            if budget >= current_dairy[waypoint.scale_parameter] + current_beef[waypoint.scale_parameter]:
                beef_scaler = current_beef[waypoint.scale_parameter] / beef_waypoint_data[waypoint.scale_parameter]
                budget -= current_beef[waypoint.scale_parameter]
                dairy_scaler = budget / dairy_waypoint_data[waypoint.scale_parameter]
                pass
            elif current_dairy[waypoint.scale_parameter] + current_beef[waypoint.scale_parameter] > budget > current_dairy[waypoint.scale_parameter]:
                dairy_scaler = current_dairy[waypoint.scale_parameter] / dairy_waypoint_data[waypoint.scale_parameter]
                budget -= current_dairy[waypoint.scale_parameter]
                beef_scaler = budget / current_beef[waypoint.scale_parameter]
            else:
                beef_scaler = 0.0
                dairy_scaler = budget / dairy_waypoint_data[waypoint.scale_parameter]

            scaled_dairy_waypoint = {}
            for key, value in dairy_waypoint_data.items():
                if isinstance(value, int) or isinstance(value, float):
                    scaled_dairy_waypoint[key] = dairy_scaler * value
                else:
                    scaled_dairy_waypoint[key] = value
            self.systems[0].update_time_series(new_config=scaled_dairy_waypoint,
                                               baseline_year=baseline_year,
                                               target_year=waypoint.year)

            scaled_beef_waypoint = {}
            for key, value in beef_waypoint_data.items():
                if isinstance(value, int) or isinstance(value, float):
                    scaled_beef_waypoint[key] = beef_scaler * value
                else:
                    scaled_beef_waypoint[key] = value
            self.systems[1].update_time_series(new_config=scaled_beef_waypoint,
                                               baseline_year=baseline_year,
                                               target_year=waypoint.year)

        self.systems[0].update_time_series(new_config=self.systems[0].get_parameters_by_index(-1),
                                           baseline_year=baseline_year,
                                           target_year=target_year)

        self.systems[1].update_time_series(new_config=self.systems[1].get_parameters_by_index(-1),
                                           baseline_year=baseline_year,
                                           target_year=target_year)

    def get_protein(self, time_span):
        protein_milk = []
        protein_beef = []

        for s in self.systems:
            if CATTLE_AGRICULTURE_PROTEIN_MILK in s.time_series:
                time_series = s.time_series[CATTLE_AGRICULTURE_PROTEIN_MILK][:time_span]
                if len(protein_milk) == 0:
                    protein_milk = time_series
                else:
                    protein_milk = [x + y for (x, y) in zip(protein_milk, time_series)]
            if CATTLE_AGRICULTURE_PROTEIN_BEEF in s.time_series:
                time_series = s.time_series[CATTLE_AGRICULTURE_PROTEIN_BEEF][:time_span]
                if len(protein_beef) == 0:
                    protein_beef = time_series
                else:
                    protein_beef = [x + y for (x, y) in zip(protein_beef, time_series)]

        return [("Cattle Protein Milk", protein_milk), ("Cattle Protein Beef", protein_beef)]

    def get_co2e(self, time_span):
        pass

    def get_area(self, time_span):
        pass

    def get_protein(self, time_span):
        pass

    def get_bio_energy(self, time_span):
        pass

    def get_hwp(self, time_span):
        pass

    def get_substitution(self, time_span):
        pass

    def get_biodiversity(self, time_span):
        pass
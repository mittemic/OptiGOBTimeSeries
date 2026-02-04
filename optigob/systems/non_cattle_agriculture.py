from dataclasses import dataclass

from optigob.systems.abstract_factory import Field
from configuration.keys import *
from optigob.systems.agriculture import AgricultureWayPoint, AgricultureSystem

@dataclass
class NonCattleWayPoint(AgricultureWayPoint):
    productivity: str

    def get_data(self, db_manager, system_name, agriculture):
        kwargs = db_manager.get_agriculture_data(abatement=self.abatement,
                                                 productivity=self.productivity,
                                                 system=system_name,
                                                 agriculture=agriculture)
        return kwargs

@dataclass
class NonCattleSystem(AgricultureSystem):

    def load_data(self, db_manager):
        kwargs = db_manager.get_agriculture_data(abatement=self.baseline_abatement,
                                                 productivity=self.baseline_productivity,
                                                 system=self.name,
                                                 agriculture=TABLE_NON_CATTLE)
        self.init_timeseries(kwargs)


    def run(self, baseline_year, target_year, db_manager):
        for waypoint in self.waypoints:
            assert isinstance(waypoint, NonCattleWayPoint)
            waypoint_data = waypoint.get_data(db_manager=db_manager, system_name=self.name, agriculture=TABLE_NON_CATTLE)

            if waypoint.scale_absolute_or_percentage:
                scaler = waypoint_data[waypoint.scale_parameter] / waypoint.scaler
            else:
                scaler = self.time_series[waypoint.scale_parameter][0] / waypoint_data[waypoint.scale_parameter] * waypoint.scaler

            for key, value in waypoint_data.items():
                if isinstance(value, int) or isinstance(value, float):
                    waypoint_data[key] = scaler * value

            self.update_time_series(new_config=waypoint_data,
                                    baseline_year=baseline_year,
                                    target_year=waypoint.year)

        super().run(baseline_year, target_year, db_manager)

class NonCattleAgriculture(Field):
    def __init__(self, data):
        self.name = NON_CATTLE_AGRICULTURE
        self.systems = []

        for system in data:
            way_points = []
            for way_point in system[WAY_POINTS]:
                way_points.append(NonCattleWayPoint(**way_point))
            self.systems.append(NonCattleSystem(name=system[NAME],
                                                baseline_abatement=system[AGRICULTURE_BASELINE_ABATEMENT],
                                                baseline_productivity=system[AGRICULTURE_BASELINE_PRODUCTIVITY],
                                                waypoints=way_points,
                                                time_series={}))



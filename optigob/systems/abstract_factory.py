from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class System(ABC):
    name: str
    time_series: dict

    @abstractmethod
    def init_timeseries(self, parameters):
        pass

    @abstractmethod
    def load_data(self, db_manager):
        pass

    def get(self, key):
        if key == "co2e":
            return self.get_co2e()
        if key in self.time_series.keys():
            return [(self.name, self.time_series[key])]

        return []

    def get_co2e(self):
        return [(self.name, self.time_series["co2e"])]

    def get_current_year(self, baseline_year):
        current_year = None
        for key, value in self.time_series.items():
            if current_year is None:
                current_year = len(value)
            elif current_year != len(value):
                current_year = max(current_year, len(value))
                print("Warning! Inconsistent time series length in " + self.name)

        current_year += baseline_year - 1
        return current_year

    def get_parameters_by_index(self, index):
        parameters = {}
        for key, value in self.time_series.items():
            parameters[key] = value[index]
        return parameters

    def update_time_series_entry(self, index, parameters: dict):
        for key, value in parameters.items():
            self.time_series[key][index] = value

    def update_time_series(self, new_config: dict, baseline_year, target_year):
        if target_year <= self.get_current_year(baseline_year):
            target_index = target_year - baseline_year
            self.update_time_series_entry(target_index, new_config)
        else:
            baseline_dict = {}
            for key, value in self.time_series.items():
                if type(value) == list:
                    baseline_dict[key] = value[-1]
                else:
                    baseline_dict[key] = value

            timeframe = target_year - self.get_current_year(baseline_year)
            for i in range(timeframe):
                for key, value in new_config.items():
                    if type(value) == str:
                        self.time_series[key].append(value)
                    else:
                        new_value = (value - baseline_dict[key]) * ((i+1) / timeframe) + baseline_dict[key]
                        self.time_series[key].append(new_value)

    def run(self, baseline_year, target_year, db_manager):
        if self.get_current_year(baseline_year) < target_year:
            parameters = self.get_parameters_by_index(-1)
            self.update_time_series(new_config=parameters,
                                    baseline_year=baseline_year,
                                    target_year=target_year)

@dataclass
class WayPoint(ABC):
    year: int

@dataclass
class WayPointSystem(System, ABC):
    waypoints: list[WayPoint]

@dataclass
class Field(ABC):
    name: str
    systems: list[System]

    # this method reads the data from the configuration file to initialise each system in the field
    @abstractmethod
    def __init__(self, data):
        pass

    # this method starts the time series for each system by loading initial data from the database
    def load_data(self, db_manager):
        for system in self.systems:
            system.load_data(db_manager)

    # this method fills the time series for each system according to the database and the configuration
    def run(self, baseline_year, target_year, db_manager):
        for system in self.systems:
            system.run(baseline_year, target_year, db_manager)

    def get_system_names(self):
        system_names = []
        for s in self.systems:
            system_names.append(s.name)
        return system_names

    def get(self, parameter):
        totals = []
        for s in self.systems:
            entries = s.get(parameter)
            if len(totals) == 0:
                for e in entries:
                    totals.append(e)
            else:
                totals = [x+y for x,y in zip(totals, entries)]
        return totals
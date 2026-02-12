from dataclasses import dataclass

from optigob.systems.abstract_factory import Field, System
from configuration.keys import *

@dataclass
class ForestrySystem(System):
    ccs: bool
    harvest: str
    nz_metrics: list[str]

    def load_data(self, db_manager):
        self.init_nz_metrics(db_manager)

    def init_nz_metrics(self, db_manager):
        self.nz_metrics = db_manager.get_nz_metrics(self.name, self.ccs)

    def get_co2e(self):
        # include net zero calculation table
        co2e_emissions = []
        for metric in self.nz_metrics:
            if co2e_emissions == []:
                co2e_emissions = self.time_series[metric]
            else:
                co2e_emissions = [x + y for x, y in zip(co2e_emissions, self.time_series[metric])]

        return [(self.name, co2e_emissions)]

@dataclass
class ExistingForest(ForestrySystem):
    def load_data(self, db_manager):
        super().load_data(db_manager)
        kwargs = db_manager.get_existing_forest_data(harvest=self.harvest,
                                                     ccs=self.ccs)
        self.init_timeseries(kwargs)

@dataclass
class Afforestation(ForestrySystem):
    afforestation_rate: float
    broadleaf_frac: float
    organic_soil: float

    def load_data(self, db_manager):
        super().load_data(db_manager)
        kwargs = db_manager.get_afforestation_data(affor_rate=self.afforestation_rate,
                                                   broadleaf_frac=self.broadleaf_frac,
                                                   organic_soil_frac=self.organic_soil,
                                                   harvest=self.harvest,
                                                   ccs=self.ccs)
        self.init_timeseries(kwargs)

class Forestry(Field):
    def __init__(self, data):
        self.name = FORESTRY
        self.systems = []

        for s in data:
            s["time_series"] = {}
            s["nz_metrics"] = []
            if s[NAME] == FORESTRY_AFFORESTATION:
                self.systems.append(Afforestation(**s))
            if s[NAME] == FORESTRY_EXISTING_FOREST:
                self.systems.append(ExistingForest(**s))

    def run(self, baseline_year, target_year, db_manager):
        super().run(baseline_year, target_year, db_manager)
        for system in self.systems:
            (_, co2e_emissions) = system.get_co2e()[0]
            system.time_series["co2e"] = co2e_emissions

    def get_area(self, time_span):
        output_list = []
        for s in self.systems:
            output_list.append((s.name + "_area", s.time_series["area"]))

        total = super().get_total(output_list, time_span)
        output_list.append(("total_forestry", total))

        return output_list

    def get_protein(self, time_span):
        pass

    def get_bio_energy(self, time_span):
        pass

    def get_hwp(self, time_span):
        output_list = []
        for s in self.systems:
            output_list.append((s.name + "_harvest_volume", s.time_series["harvest_volume"]))

        total = super().get_total(output_list, time_span)
        output_list.append(("total_forestry", total))

        return output_list

    def get_substitution(self, time_span):
        output_list = []
        for s in self.systems:
            output_list.append((s.name + "_hwp_material_substitution_credit", s.time_series["hwp_material_substitution_credit"]))
            output_list.append((s.name + "_hwp_energy_substitution_credit", s.time_series["hwp_energy_substitution_credit"]))

        total = super().get_total(output_list, time_span)
        output_list.append(("total_forestry", total))

        return output_list

    def get_biodiversity(self, time_span):
        output_list = []
        for s in self.systems:
            output_list.append((s.name + "_hnv_area", s.time_series["hnv_area"]))

        total = super().get_total(output_list, time_span)
        output_list.append(("total_forestry", total))

        return output_list

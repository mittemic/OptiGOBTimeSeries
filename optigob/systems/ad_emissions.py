from dataclasses import dataclass

from optigob.systems.abstract_factory import Field, System
from configuration.keys import *

@dataclass
class ADSystem(System):
    implementation_year: int
    ccs: bool
    additional_biomethane_year: int
    additional_grass_biomethane: float
    willow_year: int
    cdr_bioenergy: float

    def load_data(self, db_manager):
        kwargs = db_manager.get_ad_emissions(self.implementation_year,
                                             self.ccs,
                                             self.additional_biomethane_year,
                                             self.additional_grass_biomethane,
                                             self.willow_year,
                                             self.cdr_bioenergy)
        self.init_timeseries(kwargs)


class AnaerobicDigestion(Field):
    def __init__(self, data):
        self.name = AD_EMISSIONS
        self.systems = []

        data[NAME] = AD_EMISSIONS
        data["time_series"] = {}
        self.systems.append(ADSystem(**data))
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

    def get_co2e(self, time_span):
        system = self.systems[0]
        co2 = system.time_series["co2_emissions"]
        ch4 = system.time_series["ch4_emissions"]
        n2o = system.time_series["n2o_emissions"]

        co2e = []
        for i in range(time_span):
            co2e.append(super().transform_to_c02e(co2=co2[i], ch4=ch4[i], n2o=n2o[i]))

        output_list = [("ad_emissions", co2e)]
        return output_list

    def get_area(self, time_span):
        output_list = []
        for system in self.systems:
            output_list.append(("ad_area", system.time_series["area"]))
            output_list.append(("ad_additional_area", system.time_series["additional_area"]))
            output_list.append(("ad_willow_area", system.time_series["willow_area"]))

        total = super().get_total(output_list, time_span)
        output_list.append(("total_ad", total))

        return output_list

    def get_protein(self, time_span):
        pass

    def get_bio_energy(self, time_span):
        output_list = []
        for system in self.systems:
            output_list.append(("ad_biomethane_energy", system.time_series["biomethane_energy"]))
            output_list.append(("ad_additional_biomethane_energy", system.time_series["additional_biomethane_energy"]))
            output_list.append(("ad_willow", system.time_series["willow_willow"]))

        total = super().get_total(output_list, time_span)
        output_list.append(("total_ad", total))

        return output_list

    def get_hwp(self, time_span):
        pass

    def get_substitution(self, time_span):
        output_list = []
        for system in self.systems:
            output_list.append(("ad_co2_substitution_credit", system.time_series["co2_substitution_credit"]))
            output_list.append(("ad_ch2_substitution_credit", system.time_series["ch4_substitution_credit"]))
            output_list.append(("ad_n2o_substitution_credit", system.time_series["n2o_substitution_credit"]))
            output_list.append(("ad_additional_co2_emission_credit", system.time_series["additional_co2_emission_credit"]))
            output_list.append(("ad_willow_lulucf_emission_credit", system.time_series["willow_lulucf_emissions_credit"]))
            output_list.append(("willow_substitution_credit", system.time_series["willow_substitution_credit"]))

        return output_list

    def get_biodiversity(self, time_span):
        output_list = []
        for system in self.systems:
            output_list.append(("ad_hnv_area", system.time_series["hnv_area"]))
            output_list.append(("ad_additional_hnv_area", system.time_series["additional_hnv_area"]))
            output_list.append(("ad_willow_hnv_area", system.time_series["willow_hnv_area"]))

        total = super().get_total(output_list, time_span)
        output_list.append(("total_ad", total))

        return output_list
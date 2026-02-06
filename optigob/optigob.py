from matplotlib import pyplot as plt

from configuration.keys import *
import json

from resource_manager.database_manager import DatabaseManager
from optigob.systems.cattle_agriculture import CattleAgriculture
from optigob.systems.forestry import Forestry
from optigob.systems.non_cattle_agriculture import NonCattleAgriculture
from optigob.systems.organic_soils import OrganicSoils
from optigob.systems.ad_emissions import AnaerobicDigestion


class Optigob:

    def __init__(self, json_config, db_file_path):
        self.baseline_year = json_config[BASELINE_YEAR]
        self.target_year = json_config[TARGET_YEAR]
        self.fields = []
        self.db_manager = DatabaseManager(db_file_path)

        if FORESTRY in json_config:
            self.fields.append(Forestry(json_config[FORESTRY]))

        if NON_CATTLE_AGRICULTURE in json_config:
            self.fields.append(NonCattleAgriculture(json_config[NON_CATTLE_AGRICULTURE]))

        if CATTLE_AGRICULTURE in json_config:
            self.fields.append((CattleAgriculture(json_config[CATTLE_AGRICULTURE])))

        if ORGANIC_SOILS in json_config:
            self.fields.append(OrganicSoils(json_config[ORGANIC_SOILS]))

        if AD_EMISSIONS in json_config:
            self.fields.append(AnaerobicDigestion(json_config[AD_EMISSIONS]))

        for fi in self.fields:
            fi.load_data(self.db_manager)

        self.apply_scalers()

    def apply_scalers(self):
        scalers = self.db_manager.get_scalers()
        for fi in self.fields:
            for system in fi.systems:
                if system.name in scalers.keys():
                    for i in range(len(scalers["Year"])):
                        system.update_by_scaler(scaler=scalers[system.name][i],
                                                baseline_year=self.baseline_year,
                                                target_year=scalers["Year"][i])

    def run(self):
        nca = None
        for fi in self.fields:
            fi.run(self.baseline_year, self.target_year, self.db_manager)

            if isinstance(fi, NonCattleAgriculture):
                nca = fi

        for fi in self.fields:
            if isinstance(fi, CattleAgriculture):
                fi.run_cattle_systems(self.baseline_year, self.target_year, self.db_manager, nca)

    def get_evaluation(self, parameter):
        output_list = []
        total = []
        time_span = self.target_year - self.baseline_year + 1

        for fi in self.fields:
            for system in fi.systems:
                if parameter in system.time_series:
                    system_time_series = system.time_series[parameter][:time_span]
                    if len(total) == 0:
                        total = system_time_series
                    else:
                        total = [x+y for (x,y) in zip(total, system_time_series)]
                    output_list.append((system.name, system_time_series))

        if parameter == PROTEIN:
            f = self.get_field(CATTLE_AGRICULTURE)
            if not f is None:
                assert isinstance(f, CattleAgriculture)
                protein_list =  f.get_protein(time_span)
                for (name, time_series) in protein_list:
                    total = [x+y for (x,y) in zip(total, time_series)]
                    output_list.append((name, time_series))

        output_list.append(("Total", total))
        return output_list

    def get_field(self, name):
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def visualise(self, parameter, systems):
        x = range(self.baseline_year, self.target_year + 1)

        totals = []
        for i in x:
            totals.append(0)

        vis_systems = []
        for f in self.fields:
            if f.name in systems:
                vis_systems.extend(f.systems)
            else:
                for system in f.systems:
                    if system.name in systems:
                        vis_systems.append(system)

        for s in vis_systems:
            results = s.get(parameter)
            for (label, y) in results:
                plt.plot(x, y, label=label)
                for i in range(len(y)):
                    totals[i] += y[i]

        plt.plot(x, totals, label="total")

        plt.xlabel("Timeline")
        plt.ylabel("parameter")
        plt.legend()
        plt.show()

    @staticmethod
    def transform_to_c02e(co2, n2o, ch4):
        return co2 + 260 * n2o + 25 * ch4
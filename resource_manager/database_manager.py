import os
import sqlite3
import pandas as pd

class DatabaseManager:
    def __init__(self, database_path):
        self.database_path = os.path.abspath(database_path)
        self.conn = sqlite3.connect(database_path)

    def get_existing_forest_data(self,
                                 harvest="high",
                                 ccs=True):
        query = """
            SELECT
                area,
                area_unit,
                hnv_area,
                hnv_area_unit,
                organic_soil_area,
                organic_soil_area_unit,
                ghg_fluxes,
                ghg_fluxes_unit,
                harvest_volume,
                harvest_volume_unit,
                hwp_c_storage,
                hwp_c_storage_unit,
                beccs,
                beccs_unit,
                hwp_material_substitution_credit,
                hwp_material_substitution_credit_unit,
                wood_energy,
                wood_energy_unit,
                hwp_energy_substitution_credit,
                hwp_energy_substitution_credit_unit 
            FROM existing_forest
            WHERE harvest_rate = ?
                  AND ccs = ?
            ORDER BY year;
        """
        if ccs:
            ccs = "yes"
        else:
            ccs = "no"

        params = (harvest, ccs)
        df = pd.read_sql_query(query, self.conn, params=params)
        kwargs = df.to_dict(orient="list")
        return kwargs

    def get_afforestation_data(self,
                               affor_rate=2,
                               broadleaf_frac=0.5,
                               organic_soil_frac=0.15,
                               harvest="high",
                               ccs="yes"):
        query = """
            SELECT
                area, 
                area_unit, 
                hnv_area, 
                hnv_area_unit, 
                organic_soil_area, 
                organic_soil_area_unit, 
                ghg_fluxes, 
                ghg_fluxes_unit, 
                harvest_volume, 
                harvest_volume_unit, 
                hwp_c_storage, 
                hwp_c_storage_unit, 
                beccs, 
                beccs_unit, 
                hwp_material_substitution_credit, 
                hwp_material_substitution_credit_unit, 
                wood_energy, 
                wood_energy_unit, 
                hwp_energy_substitution_credit, 
                hwp_energy_substitution_credit_unit
            FROM afforestation
            WHERE harvest_rate = ?
                  AND ccs = ?
                  AND bl_c_ratio = ?
                  AND o_m_ratio = ?
            ORDER BY year;
        """
        if ccs:
            ccs = "yes"
        else:
            ccs = "no"

        params = (harvest, ccs, broadleaf_frac, organic_soil_frac)
        df = pd.read_sql_query(query, self.conn, params=params)

        kwargs = df.to_dict(orient="list")
        for key, value in kwargs.items():
            for v in value:
                if isinstance(v, int) or isinstance(v, float):
                    v *= affor_rate

        return kwargs

    def get_nz_metrics(self,
                       system_name,
                       ccs):
        col = "ccs" if ccs else "no_ccs"

        query = f"""
            SELECT DISTINCT 
                metric 
            FROM 
                nz_calc_included 
            WHERE 
                system = ?
                AND {col} = 'yes';
        """

        df = pd.read_sql_query(query, self.conn, params=(system_name,))
        return df["metric"].tolist()

    def get_agriculture_data(self, abatement="2020 BL", productivity="2020 BL", agriculture="non_cattle", system="Pigs"):
        query = f"""
            SELECT
                metric,
                unit,
                value
            FROM {agriculture}
            WHERE Abatement = ?
                    AND Productivity = ?
                    AND System = ?
        """
        params = (abatement, productivity, system)
        df = pd.read_sql_query(query, self.conn, params=params)
        metric = df.get("metric").to_list()
        unit = df.get("unit").to_list()
        value = df.get("value").to_list()

        kwargs = {}
        for i in range(len(metric)):
            kwargs[metric[i].lower()] = value[i]
            kwargs[metric[i].lower() + "_unit"] = unit[i]

        return kwargs

    def get_scalers(self):
        query = "SELECT * FROM scalers"
        df = pd.read_sql_query(query, self.conn)
        return df

    def get_organic_soils(self, name="Organic soil under grass", drainage_status="Drained"):
        query = """
            SELECT
                metric,
                unit,
                value
            FROM organic_soils
            WHERE "Organic soil type" = ?
                    AND "Drainage status" = ?
        """
        params = (name, drainage_status)
        df = pd.read_sql_query(query, self.conn, params=params)
        metric = df.get("metric").to_list()
        unit = df.get("unit").to_list()
        value = df.get("value").to_list()

        kwargs = {}
        for i in range(len(metric)):
            kwargs[metric[i].lower()] = value[i]
            kwargs[metric[i].lower() + "_unit"] = unit[i]

        return kwargs

    def get_ad_emissions(self, implementation_year, ccs, additional_biomethane_year, additional_grass_biomethane, willow_year, cdr_bioenergy):
        implementation_offset = 2030 # year in the dataset when biomethane strategy is implemented
        additional_biomethane_offset = 2035
        additional_biomethane_scaler = 1000.0
        willow_offset = 2040
        willow_scaler = 1000.0

        query = """
            SELECT
                biomethane_energy,
                area,
                hnv_area,
                co2_emissions,
                ch4_emissions,
                n2o_emissions,
                co2_substitution_credit,
                ch4_substitution_credit,
                n2o_substitution_credit,
            	BECCS
            FROM ad_biomethane_strategy
            WHERE ccs = ?
        """
        ccs = "yes" if ccs else "no"
        params = (ccs,)
        df = pd.read_sql_query(query, self.conn, params=params)

        kwargs = df.to_dict(orient="list")
        offset = implementation_offset - implementation_year
        while offset < 0:
            for _, values in kwargs.items():
                del values[0]
            offset += 1
        while offset > 0:
            for key, values in kwargs.items():
                kwargs[key] = [values[0]] + values
            offset -= 1

        query = """
            SELECT
                biomethane_energy,
                grass_dry_matter,
                area,
                hnv_area,
                co2_emissions,
                ch4_emissions,
                n20_emissions,
                nh3_emissions,
                n_to_water_emissions,
                p_to_water_emissions,
                co2_emission_credit,
                beccs
            FROM additional_ad
            WHERE ccs = ?
        """
        df = pd.read_sql_query(query, self.conn, params=params)

        additional_kwargs = df.to_dict(orient="list")
        offset = additional_biomethane_year - additional_biomethane_offset
        while offset < 0:
            for key, values in additional_kwargs.items():
                del values[0]
            offset += 1
        while offset > 0:
            for key, values in additional_kwargs.items():
                additional_kwargs[key] = [values[0]] + values
            offset -= 1

        scaler = additional_grass_biomethane / additional_biomethane_scaler
        for key, values in additional_kwargs.items():
            if isinstance(values[0], int) or isinstance(values[0], float):
                for i in range(len(values)):
                    values[i] *= scaler
            kwargs["additional_" + key] = values

        query = """
            SELECT
                willow,
                willow_dry_matter,
                area,
                hnv_area,
                lulucf_emissions_credit,
                substitution_credit,
                BECCS            
            FROM willow_beccs
            WHERE ccs = ?
        """
        df = pd.read_sql_query(query, self.conn, params=params)

        willow_kwargs = df.to_dict(orient="list")
        offset = willow_year - willow_offset
        while offset < 0:
            for _, values in willow_kwargs.items():
                del values[0]
            offset += 1
        while offset > 0:
            for key, values in willow_kwargs.items():
                willow_kwargs[key] = [values[0]] + values
            offset -= 1

        scaler = cdr_bioenergy / willow_scaler
        for key, values in willow_kwargs.items():
            if isinstance(values[0], int) or isinstance(values[0], float):
                for i in range(len(values)):
                    values[i] *= scaler
            kwargs["willow_" + key] = values

        return kwargs
import pytest
from optigob.optigob import Optigob
from configuration.keys import *
from optigob.systems.ad_emissions import AnaerobicDigestion, ADSystem

db_file_path = "data/database.db"

def test_ad_emissions_not_implemented():
    config = {
        "baseline_year": 2020,
        "target_year": 2050,
        # No "ad_emissions" key
    }

    optigob = Optigob(json_config=config, db_file_path=db_file_path)
    optigob.run()

    ad_emissions = optigob.get_field(AD_EMISSIONS)
    assert ad_emissions is None
    print("test 'ad_emissions not implemented' ran successfully")

def test_ad_emissions_ccs():
    config = {
        "baseline_year": 2020,
        "target_year": 2050,
        "ad_emissions": {
            "implementation_year": 2030,
            "ccs": False,
            "additional_biomethane_year": 2035,
            "additional_grass_biomethane": 0,
            "willow_year": 2040,
            "cdr_bioenergy": 0
        }
    }

    optigob = Optigob(json_config=config, db_file_path=db_file_path)
    optigob.run()

    ad_emissions = optigob.get_field(AD_EMISSIONS)
    assert isinstance(ad_emissions, AnaerobicDigestion)
    assert len(ad_emissions.systems) == 1
    ad_system = ad_emissions.systems[0]
    assert isinstance(ad_system, ADSystem)
    assert ad_system.ccs == False
    assert ad_system.time_series["BECCS"][-1] == 0.0

    config = {
        "baseline_year": 2020,
        "target_year": 2050,
        "ad_emissions": {
            "implementation_year": 2030,
            "ccs": True,
            "additional_biomethane_year": 2035,
            "additional_grass_biomethane": 0,
            "willow_year": 2040,
            "cdr_bioenergy": 0
        }
    }

    optigob = Optigob(json_config=config, db_file_path=db_file_path)
    optigob.run()

    ad_emissions = optigob.get_field(AD_EMISSIONS)
    assert isinstance(ad_emissions, AnaerobicDigestion)
    assert len(ad_emissions.systems) == 1
    ad_system = ad_emissions.systems[0]
    assert isinstance(ad_system, ADSystem)
    assert ad_system.ccs == True
    assert ad_system.time_series["BECCS"][-1] != 0.0

    print("test 'ad_emissions ccs' ran successfully")

def test_ad_emissions_biomethane_strategy_implementation_year():
    config = {
        "baseline_year": 2020,
        "target_year": 2050,
        "ad_emissions": {
            "implementation_year": 2030,
            "ccs": False,
            "additional_biomethane_year": 2035,
            "additional_grass_biomethane": 0,
            "willow_year": 2040,
            "cdr_bioenergy": 0
        }
    }

    optigob = Optigob(json_config=config, db_file_path=db_file_path)
    optigob.run()

    ad_emissions = optigob.get_field(AD_EMISSIONS)
    assert isinstance(ad_emissions, AnaerobicDigestion)
    assert len(ad_emissions.systems) == 1
    ad_system = ad_emissions.systems[0]
    assert isinstance(ad_system, ADSystem)
    idx = config["implementation_year"] - config["baseline_year"]
    assert ad_system.time_series["biomethane_energy"][idx] == 5700 and ad_system.time_series["biomethane_energy"][idx - 1] < 5700

    config = {
        "baseline_year": 2020,
        "target_year": 2050,
        "ad_emissions": {
            "implementation_year": 2035,
            "ccs": False,
            "additional_biomethane_year": 2035,
            "additional_grass_biomethane": 0,
            "willow_year": 2040,
            "cdr_bioenergy": 0
        }
    }

    optigob = Optigob(json_config=config, db_file_path=db_file_path)
    optigob.run()

    ad_emissions = optigob.get_field(AD_EMISSIONS)
    assert isinstance(ad_emissions, AnaerobicDigestion)
    assert len(ad_emissions.systems) == 1
    ad_system = ad_emissions.systems[0]
    assert isinstance(ad_system, ADSystem)
    idx = config["implementation_year"] - config["baseline_year"]
    assert ad_system.time_series["biomethane_energy"][idx] == 5700 and ad_system.time_series["biomethane_energy"][idx - 1] < 5700

    config = {
        "baseline_year": 2020,
        "target_year": 2050,
        "ad_emissions": {
            "implementation_year": 2025,
            "ccs": False,
            "additional_biomethane_year": 2035,
            "additional_grass_biomethane": 0,
            "willow_year": 2040,
            "cdr_bioenergy": 0
        }
    }

    optigob = Optigob(json_config=config, db_file_path=db_file_path)
    optigob.run()

    ad_emissions = optigob.get_field(AD_EMISSIONS)
    assert isinstance(ad_emissions, AnaerobicDigestion)
    assert len(ad_emissions.systems) == 1
    ad_system = ad_emissions.systems[0]
    assert isinstance(ad_system, ADSystem)
    idx = config["implementation_year"] - config["baseline_year"]
    assert ad_system.time_series["biomethane_energy"][idx] == 5700 and ad_system.time_series["biomethane_energy"][idx - 1] < 5700

    print("test 'ad_emissions biomethane strategy' ran successfully")

def test_ad_emissions_additional_ad():
    config = {
        "baseline_year": 2020,
        "target_year": 2050,
        "ad_emissions": {
            "implementation_year": 2030,
            "ccs": False,
            "additional_biomethane_year": 2035,
            "additional_grass_biomethane": 0,
            "willow_year": 2040,
            "cdr_bioenergy": 0
        }
    }

    optigob = Optigob(json_config=config, db_file_path=db_file_path)
    optigob.run()

    ad_emissions = optigob.get_field(AD_EMISSIONS)
    assert isinstance(ad_emissions, AnaerobicDigestion)
    assert len(ad_emissions.systems) == 1
    ad_system = ad_emissions.systems[0]
    assert isinstance(ad_system, ADSystem)
    idx = config["implementation_year"] - config["baseline_year"]
    assert ad_system.time_series["biomethane_energy"][idx] == 5700 and ad_system.time_series["biomethane_energy"][idx - 1] < 5700


test_ad_emissions_not_implemented()
test_ad_emissions_ccs()
test_ad_emissions_biomethane_strategy_implementation_year()


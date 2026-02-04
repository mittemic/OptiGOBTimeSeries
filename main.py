import json

from optigob.optigob import Optigob
from configuration.keys import *

config_file_path = "configuration/config.json"
db_file_path = "data/database.db"

with open(config_file_path, "r") as f:
    json_config = json.load(f)

optigob = Optigob(json_config=json_config, db_file_path=db_file_path)
optigob.apply_scalers()
optigob.run()

optigob.visualise(parameter="co2e", systems=[NON_CATTLE_AGRICULTURE, CATTLE_AGRICULTURE])

#optigob.visualise(parameter="area", systems=[ORGANIC_SOILS])
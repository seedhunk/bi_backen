from dotenv import dotenv_values

config_credentials = dict(dotenv_values(".env"))
PY_DB_HOST = config_credentials['py_db_host']
PY_DB_DATABASE = config_credentials['py_db_database']
PY_DB_PORT = int(config_credentials['py_db_port'])
PY_DB_USER = config_credentials['py_db_user']
PY_DB_PASSWORD = config_credentials['py_db_ps']
HOST_URL = config_credentials["host_url"]
HOST_PORT = int(config_credentials["host_port"])
SECRET = config_credentials["SECRET"]
MAX_APPOINTMENT_NUM_IN_ONE_PERIOD = int(config_credentials["MAX_APPOINTMENT_NUM_IN_ONE_PERIOD"])

MORNING_OPEN = int(config_credentials["MORNING_OPEN"])
MORNING_CLOSE = int(config_credentials["MORNING_CLOSE"])
AFTERNOON_OPEN = int(config_credentials["AFTERNOON_OPEN"])
AFTERNOON_CLOSE = int(config_credentials["AFTERNOON_CLOSE"])
EVENING_OPEN = int(config_credentials["EVENING_OPEN"])
EVENING_CLOSE = int(config_credentials["EVENING_CLOSE"])

print(config_credentials)
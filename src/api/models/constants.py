# API-related constants
API_START_TIMESTAMP_KEY = "start_timestamp_api"
API_VERSION_FILE_PATH = "/app/.version"

# Logging-related constants
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_FILE_NAME = "app.log"
LOG_LEVEL = "INFO"

# ConfigMap-related constants
LABEL_SELECTOR = "rr-flag"

# Error messages
ERROR_FETCHING_ZONES = "Error fetching zones"
ERROR_FETCHING_CRITICAL_SERVICES = "Error fetching critical services"
ERROR_DESCRIBING_ZONE = "Error describing zone"
ERROR_DESCRIBING_SERVICE = "Error describing service"
ERROR_UPDATING_CRITICAL_SERVICES = "Error updating critical services"
ERROR_INVALID_JSON = "Invalid JSON format in request"
ERROR_MISSING_CRITICAL_SERVICES = "Missing 'critical-services' in payload"

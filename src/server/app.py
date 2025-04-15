"""
This Flask application exposes endpoints to interact with zone and critical service data.
It allows retrieving, describing, updating, and checking the status of zones and critical services.
"""

import logging
import datetime
from flask import Flask
from flask_restful import Api
from src.server.resources.healthz import Ready, Live
from src.server.resources.version import Version
from src.lib.lib_rms import Helper
from src.server.routes import (
    ZoneListResource,
    ZoneDescribeResource,
    CriticalServiceListResource,
    CriticalServiceDescribeResource,
    CriticalServiceUpdateResource,
    CriticalServiceStatusListResource,
    CriticalServiceStatusDescribeResource,
)

app = Flask(__name__)
api = Api(app)

# Logging setup
app.logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("app.log")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)


# Set server start timestamp
start_timestamp_api = datetime.datetime.utcnow().isoformat() + "Z"
app.logger.info("API server started at %s", start_timestamp_api)
with app.app_context():
    Helper.update_configmap_with_timestamp(
        "rrs-mon-dynamic", "rack-resiliency", start_timestamp_api, "start_timestamp_api"
    )

# Read version info
try:
    with open("/app/.version", encoding="utf-8") as version_file:
        app.config["VERSION"] = version_file.read().splitlines()[0]
except IOError:
    app.config["VERSION"] = "Unknown"

# Health & version endpoints
api.add_resource(Ready, "/healthz/ready")
api.add_resource(Live, "/healthz/live")
api.add_resource(Version, "/version")

# Zone and critical service endpoints
api.add_resource(ZoneListResource, "/zones")
api.add_resource(ZoneDescribeResource, "/zones/<zone_name>")
api.add_resource(CriticalServiceListResource, "/criticalservices")
api.add_resource(CriticalServiceDescribeResource, "/criticalservices/<service_name>")
api.add_resource(CriticalServiceUpdateResource, "/criticalservices")
api.add_resource(CriticalServiceStatusListResource, "/criticalservices/status")
api.add_resource(
    CriticalServiceStatusDescribeResource, "/criticalservices/status/<service_name>"
)

# Main entry point of the application
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True, threaded=True)

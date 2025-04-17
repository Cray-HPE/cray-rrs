#
# MIT License
#
#  (C) Copyright 2025 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#

"""
This Flask application exposes endpoints to interact with zone and critical service data.
It allows retrieving, describing, updating, and checking the status of zones and critical services.
"""

import logging
import datetime
from flask import Flask
from flask_restful import Api
from src.api.resources.healthz import Ready, Live
from src.api.resources.version import Version
from src.lib.lib_configmap import ConfigMapHelper
from src.api.routes import (
    ZoneListResource,
    ZoneDescribeResource,
    CriticalServiceListResource,
    CriticalServiceDescribeResource,
    CriticalServiceUpdateResource,
    CriticalServiceStatusListResource,
    CriticalServiceStatusDescribeResource,
)

# Initialize Flask application and RESTful API
app = Flask(__name__)
api = Api(app)

# Logging setup: Set logging level and format for file logging
app.logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("app.log")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)

# Set the server start timestamp and log it
start_timestamp_api = datetime.datetime.utcnow().isoformat() + "Z"
app.logger.info("API server started at %s", start_timestamp_api)

# Update ConfigMap with the server start timestamp for monitoring purposes
with app.app_context():
    ConfigMapHelper.update_configmap_data(
        "rack-resiliency",
        "rrs-mon-dynamic",
        None,
        "start_timestamp_api",
        start_timestamp_api,
    )

# Read the application version from a version file and set it in the app config
try:
    with open("/app/.version", encoding="utf-8") as version_file:
        app.config["VERSION"] = version_file.read().splitlines()[0]
except IOError:
    app.config["VERSION"] = "Unknown"

# Register health and version endpoints
api.add_resource(Ready, "/healthz/ready")  # Readiness check
api.add_resource(Live, "/healthz/live")  # Liveness check
api.add_resource(Version, "/version")  # Version info endpoint

# Register zone-related endpoints
api.add_resource(ZoneListResource, "/zones")  # List all zones
api.add_resource(ZoneDescribeResource, "/zones/<zone_name>")  # Describe a specific zone

# Register critical service-related endpoints
api.add_resource(
    CriticalServiceListResource, "/criticalservices"
)  # List all critical services
api.add_resource(
    CriticalServiceDescribeResource, "/criticalservices/<service_name>"
)  # Describe a specific service
api.add_resource(
    CriticalServiceUpdateResource, "/criticalservices"
)  # Update critical service data
api.add_resource(
    CriticalServiceStatusListResource, "/criticalservices/status"
)  # List statuses of critical services
api.add_resource(
    CriticalServiceStatusDescribeResource,
    "/criticalservices/status/<service_name>",  # Describe status of a specific service
)

# Main entry point of the application
if __name__ == "__main__":
    # Run the Flask application on all available IPs on port 80, enabling debug mode and threading
    app.run(host="0.0.0.0", port=80, debug=True, threaded=True)

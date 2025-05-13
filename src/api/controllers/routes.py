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
This module defines the API Server and its API routes for the Rack Resiliency Service (RRS).
It sets up the application, configures logging, initializes API endpoints, and handles versioning
and startup timestamp updates.

API Endpoints:
    - /healthz/ready: Readiness probe for the application
    - /healthz/live: Liveness probe for the application
    - /version: Returns the current version of the application
    - /zones: Lists all zones
    - /zones/<zone_name>: Describes a specific zone
    - /criticalservices: Lists all critical services
    - /criticalservices/<service_name>: Describes a specific critical service
    - /criticalservices/status: Lists the status of all critical services
    - /criticalservices/status/<service_name>: Describes the status of a specific critical service

Usage:
    Import and call `create_app` to initialize the Flask application with the defined routes
"""

import logging
import datetime, os
from flask import Flask
from flask_restful import Api
from src.api.models.healthz import Ready, Live
from src.api.models.version import Version
from src.api.controllers.controls import (
    ZoneListResource,
    ZoneDescribeResource,
    CriticalServiceListResource,
    CriticalServiceDescribeResource,
    CriticalServiceUpdateResource,
    CriticalServiceStatusListResource,
    CriticalServiceStatusDescribeResource,
)
from src.lib.lib_configmap import ConfigMapHelper


def create_app() -> Flask:
    app = Flask(__name__)
    api = Api(app)

    # Logging setup
    app.logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler("app.log")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)

    # Timestamp logging
    start_timestamp_api = datetime.datetime.utcnow().isoformat() + "Z"
    app.logger.info("API server started at %s", start_timestamp_api)
    CM_NAME = os.getenv("dynamic_cm_name")
    CM_NAMESPACE = os.getenv("namespace")
    with app.app_context():
        ConfigMapHelper.update_configmap_data(
            CM_NAMESPACE,
            CM_NAME,
            None,
            "start_timestamp_api",
            start_timestamp_api,
        )

    # Version reading
    try:
        with open("/app/.version", encoding="utf-8") as version_file:
            app.config["VERSION"] = version_file.read().splitlines()[0]
    except IOError:
        app.config["VERSION"] = "Unknown"

    # Register healthz and version endpoints
    api.add_resource(Ready, "/healthz/ready")
    api.add_resource(Live, "/healthz/live")
    api.add_resource(Version, "/version")

    # Register Zones endpoints
    api.add_resource(ZoneListResource, "/zones")
    api.add_resource(ZoneDescribeResource, "/zones/<zone_name>")

    # Register Criticalservices endpoints
    api.add_resource(CriticalServiceListResource, "/criticalservices")
    api.add_resource(
        CriticalServiceDescribeResource, "/criticalservices/<service_name>"
    )
    api.add_resource(CriticalServiceUpdateResource, "/criticalservices")
    api.add_resource(CriticalServiceStatusListResource, "/criticalservices/status")
    api.add_resource(
        CriticalServiceStatusDescribeResource, "/criticalservices/status/<service_name>"
    )

    return app

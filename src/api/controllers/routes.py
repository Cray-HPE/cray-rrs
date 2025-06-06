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

import sys
import logging
import time
from http import HTTPStatus
import requests
from flask import Flask
from flask_restful import Api
from src.lib.healthz import Ready, Live
from src.lib.version import Version
from src.api.controllers.controls import (
    ZoneListResource,
    ZoneDescribeResource,
    CriticalServiceListResource,
    CriticalServiceDescribeResource,
    CriticalServiceUpdateResource,
    CriticalServiceStatusListResource,
    CriticalServiceStatusDescribeResource,
)
from src.lib.rrs_constants import REQUESTS_TIMEOUT, MAX_RETRIES, RETRY_DELAY


def create_app() -> Flask:
    """
    Initialize and configure the Flask API server for the Rack Resiliency Service (RRS).

    This function performs the following steps:
    - Creates the Flask application and Flask-RESTful API instance.
    - Configures logging to stream container logs to stdout.
    - Calls an internal service endpoint to update the API start timestamp.
    - Sets the version information
    - Registers all API endpoints for health checks, version info, zones, and critical services.

    Returns:
        Flask: A fully configured Flask application instance ready to be run.
    """
    app = Flask(__name__)
    api = Api(app)

    # Logging setup
    if app.logger.hasHandlers():
        app.logger.handlers.clear()
    app.logger.setLevel(logging.INFO)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s in %(module)s - %(message)s"
    )
    stream_handler.setFormatter(formatter)
    app.logger.addHandler(stream_handler)

    # Timestamp logging via API call
    with app.app_context():
        app.logger.info("Update API start timestamp")
        ts_url = "http://localhost:8551/api-ts"

        try:
            success = False
            for attempt in range(MAX_RETRIES + 3):
                try:
                    response = requests.post(ts_url, timeout=REQUESTS_TIMEOUT)
                    if response.status_code == HTTPStatus.OK:
                        app.logger.info("Response: %s", response.text.strip())
                        success = True
                        break
                except (requests.exceptions.RequestException, ValueError) as e:
                    app.logger.error(
                        "Attempt %d: Failed to update timestamp: %s", attempt, e
                    )
                    if attempt == MAX_RETRIES:
                        app.logger.error(
                            "Max retries reached. Could not update timestamp"
                        )
                    time.sleep(RETRY_DELAY + 3)
                    sys.exit(1)
            if not success:
                app.logger.error(
                    "Failed to update API timestamp after all retries. Exiting."
                )
                sys.exit(1)
        except Exception as e:
            app.logger.exception("Error %s occurred. Exiting...", str(e))
            sys.exit(1)

    # This version value is substituted dynamically at build time
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

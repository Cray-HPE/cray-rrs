#
# MIT License
#
#  (C) Copyright [2025] Hewlett Packard Enterprise Development LP
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
# Standard library imports
import logging

# Third-party imports
from flask import Flask, request, jsonify

# Local application imports
from src.server.resources.rrs_logging import log_event
from src.server.models.zone_list import get_zones
from src.server.models.zone_describe import describe_zone
from src.server.models.criticalservice_list import get_critical_service_list
from src.server.models.criticalservice_describe import describe_service
from src.server.models.criticalservice_update import update_critical_services
from src.server.models.criticalservice_status_list import (
    get_criticalservice_status_list,
)
from src.server.models.criticalservice_status_describe import describe_service_status

app = Flask(__name__)


# Set up logging configuration using Flask's built-in logging system
app.logger.setLevel(logging.INFO)

# Add a handler to log into a file
file_handler = logging.FileHandler("app.log")  # Log to a file named 'app.log'
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

# Add the file handler to the Flask app's logger
app.logger.addHandler(file_handler)


# Endpoint to get the list of zones
@app.route("/zones", methods=["GET"])
def list_zones():
    """
    Get the list of all zones.

    Returns:
        JSON response with the list of zones.
    """
    try:
        log_event("Fetching the list of zones")
        zones = get_zones()
        return jsonify(zones), 200
    except Exception as e:
        log_event(f"Error fetching zones: {str(e)}", level="ERROR")
        return jsonify({"error": str(e)}), 500


# Endpoint to describe the zone entered
@app.route("/zones/<zone_name>", methods=["GET"])
def desc_zone(zone_name):
    """
    Get the description of a specific zone by its name.

    Args:
        zone_name (str): The name of the zone to describe.

    Returns:
        JSON response with the zone description or an error message.
    """
    try:
        log_event(f"Describing zone: {zone_name}")
        zone = describe_zone(zone_name)
        if not zone:
            log_event(f"Zone {zone_name} not found", level="ERROR")
            return jsonify({"error": "Zone not found"}), 404
        return jsonify(zone), 200
    except Exception as e:
        log_event(f"Error describing zone {zone_name}: {str(e)}", level="ERROR")
        return jsonify({"error": str(e)}), 500


# Endpoint to get the list of critical services
@app.route("/criticalservices", methods=["GET"])
def list_critical_service():
    """
    Get the list of all critical services.

    Returns:
        JSON response with the list of critical services.
    """
    try:
        log_event("Fetching the list of critical services")
        critical_services = get_critical_service_list()
        return jsonify(critical_services), 200
    except Exception as e:
        log_event(f"Error fetching critical services: {str(e)}", level="ERROR")
        return jsonify({"error": str(e)}), 500


# Endpoint to describe the critical service entered
@app.route("/criticalservices/<service_name>", methods=["GET"])
def describe_criticalservice(service_name):
    """
    Get the description of a specific critical service by its name.

    Args:
        service_name (str): The name of the critical service to describe.

    Returns:
        JSON response with the service description or an error message.
    """
    try:
        log_event(f"Describing critical service: {service_name}")
        service = describe_service(service_name)
        if not service:
            log_event(f"Critical service {service_name} not found", level="ERROR")
            return jsonify({"error": "Critical service not found"}), 404
        return jsonify(service), 200
    except Exception as e:
        log_event(f"Error describing service {service_name}: {str(e)}", level="ERROR")
        return jsonify({"error": str(e)}), 500


# Endpoint to update the critical services list
@app.route("/criticalservices", methods=["PATCH"])
def update_criticalservice():
    """
    Update the list of critical services.

    Returns:
        JSON response with the updated list of critical services.
    """
    try:
        log_event("Updating critical services list")
        new_data = request.get_json()
        if not new_data:
            log_event("No data provided for update", level="ERROR")
            return jsonify({"error": "No data provided"}), 400
        updated_services = update_critical_services(new_data)
        return jsonify(updated_services), 200
    except Exception as e:
        log_event(f"Error updating critical services: {str(e)}", level="ERROR")
        return jsonify({"error": str(e)}), 500


# Endpoint to get the list of critical services status
@app.route("/criticalservices/status", methods=["GET"])
def list_status_crtiticalservices():
    """
    Get the status of all critical services.

    Returns:
        JSON response with the status of critical services.
    """
    try:
        log_event("Fetching critical service statuses")
        status = get_criticalservice_status_list()
        return jsonify(status), 200
    except Exception as e:
        log_event(f"Error fetching critical service status: {str(e)}", level="ERROR")
        return jsonify({"error": str(e)}), 500


# Endpoint to describe the critical service entered
@app.route("/criticalservices/status/<service_name>", methods=["GET"])
def status_describe_criticalservice(service_name):
    """
    Get the description of a specific critical service by its name.

    Args:
        service_name (str): The name of the critical service to describe.

    Returns:
        JSON response with the service description or an error message.
    """
    try:
        log_event(f"Describing critical service status: {service_name}")
        service = describe_service_status(service_name)
        if not service:
            log_event(f"Critical service {service_name} not found", level="ERROR")
            return jsonify({"error": "Critical service not found"}), 404
        return jsonify(service), 200
    except Exception as e:
        log_event(
            f"Error describing critical service status {service_name}: {str(e)}",
            level="ERROR",
        )
        return jsonify({"error": str(e)}), 500


# Running the Flask app
if __name__ == "__main__":
    # Run the Flask app on host '0.0.0.0' and port '80' in debug mode.
    app.run(host="0.0.0.0", port=80, debug=True)

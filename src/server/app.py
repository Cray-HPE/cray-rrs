#
# MIT License
#
# (C) Copyright [2024-2025] Hewlett Packard Enterprise Development LP
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
from flask import Flask, request, jsonify
from models.zone_list import get_zones
from models.zone_describe import describe_zone
from models.criticalservice_list import get_critical_service_list
from models.criticalservice_describe import describe_service
from models.criticalservice_update import update_critical_services
from models.criticalservice_status_list import get_critical_services_status

app = Flask(__name__)

# Endpoint to get the list of zones
@app.route("/zones", methods=["GET"])
def list_zones():
    """
    Get the list of all zones.
    
    Returns:
        JSON response with the list of zones.
    """
    try:
        zones = get_zones()
        return jsonify(zones), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to describe the zone entered
@app.route('/zones/<zone_name>', methods=['GET'])
def desc_zone(zone_name):
    """
    Get the description of a specific zone by its name.
    
    Args:
        zone_name (str): The name of the zone to describe.
    
    Returns:
        JSON response with the zone description or an error message.
    """
    try:
        zone = describe_zone(zone_name)
        if not zone:
            return jsonify({"error": "Zone not found"}), 404
        return jsonify(zone), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to get the list of critical services
@app.route('/criticalservices', methods=['GET'])
def list_critical_service():
    """
    Get the list of all critical services.
    
    Returns:
        JSON response with the list of critical services.
    """
    try:
        critical_services = get_critical_service_list()
        return jsonify(critical_services), 200
    except Exception as e:
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
        service = describe_service(service_name)
        if not service:
            return jsonify({"error": "Critical service not found"}), 404
        return jsonify(service), 200
    except Exception as e:
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
        new_data = request.get_json()
        if not new_data:
            return jsonify({"error": "No data provided"}), 400
        updated_services = update_critical_services(new_data)
        return jsonify(updated_services), 200
    except Exception as e:
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
        status = get_critical_services_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Running the Flask app
if __name__ == "__main__":
    """
    Run the Flask app on host '0.0.0.0' and port '80' in debug mode.
    """
    app.run(host="0.0.0.0", port=80, debug=True)

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
Model handles updates to critical services in the ConfigMap.
"""

import json
import logging
from flask import jsonify
from kubernetes import client
from resources.critical_services import get_configmap
from resources.error_print import pretty_print_error
from models.criticalservice_list import CM_KEY, CM_NAME, CM_NAMESPACE

# Configure logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

def update_configmap(new_data, existing_data, test=False):
    """Update the ConfigMap with new critical services."""
    try:
        v1 = client.CoreV1Api()

        if "error" in existing_data:
            return existing_data

        existing_services = existing_data.get("critical-services", {})
        new_services = json.loads(new_data)["critical-services"]

        # Separate added and skipped services
        added_services = [s for s in new_services if s not in existing_services]
        skipped_services = [s for s in new_services if s in existing_services]

        for service_name in added_services:
            existing_services[service_name] = new_services[service_name]

        # Patch ConfigMap
        if not test:
            body = {"data": {CM_KEY: json.dumps({"critical-services": existing_services}, indent=2)}}
            v1.patch_namespaced_config_map(CM_NAME, CM_NAMESPACE, body)

        return {
            "Update": "Successful" if added_services else "Services Already Exist",
            "Successfully Added Services": added_services or [],
            "Already Existing Services": skipped_services or [],
        }

    except json.JSONDecodeError as json_err:
        return {"error": f"Invalid JSON format: {pretty_print_error(json_err)}"}
    except client.exceptions.ApiException as api_exc:
        return {"error": f"Failed to update ConfigMap: {pretty_print_error(api_exc)}"}
    except KeyError as key_exc:
        return {"error": f"Missing key: {pretty_print_error(key_exc)}"}
    except (TypeError, ValueError, AttributeError) as parse_exc:
        return {"error": f"Parsing error: {pretty_print_error(parse_exc)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {pretty_print_error(e)}"}

def update_critical_services(new_data):
    """Function to update critical services in the ConfigMap."""
    try:
        if not new_data or "from_file" not in new_data:
            return jsonify({"error": "Invalid request format"}), 400

        try:
            new_services = json.loads(new_data["from_file"])
        except json.JSONDecodeError as json_err:
            LOGGER.error("Invalid JSON format in request: %s", json_err)
            return jsonify({"error": "Invalid JSON format in services"}), 400

        if "critical-services" not in new_services:
            return jsonify({"error": "Missing 'critical-services' in payload"}), 400

        existing_data = get_configmap(CM_NAME, CM_NAMESPACE, CM_KEY)
        result = update_configmap(json.dumps(new_services), existing_data)
        return jsonify(result)

    except Exception as e:
        LOGGER.error("Unhandled error in update_critical_services: %s", e)
        return jsonify({"error": f"Unexpected error: {pretty_print_error(e)}"}), 500

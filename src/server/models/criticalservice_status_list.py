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
Model to fetch and format critical services from a Kubernetes ConfigMap.
"""

from flask import jsonify
from resources.critical_services import get_configmap
from resources.error_print import pretty_print_error

CM_NAME = "rrs-mon-static"
CM_NAMESPACE = "rack-resiliency"
CM_KEY = "critical-service-config.json"

def get_critical_services_status(services):
    """Fetch and format critical services grouped by namespace in the required structure."""
    try:
        result = {"namespace": {}}
        for name, details in services.items():
            namespace = details["namespace"]
            if namespace not in result["namespace"]:
                result["namespace"][namespace] = []
            result["namespace"][namespace].append({
                "name": name,
                "type": details["type"],
                "status": details["status"],
                "balanced": details["balanced"]
            })

        return result

    except Exception as e:
        return {"error": str(pretty_print_error(e))}

def get_critical_service_list():
    """
    Fetch critical services from the ConfigMap and return as a JSON response.

    Returns:
        Flask Response: JSON response containing critical services or an error message.
    """
    try:
        config_data = get_configmap(CM_NAME, CM_NAMESPACE, CM_KEY)
        services = config_data.get("critical-services", {})
        return jsonify({"critical-services": get_critical_services_status(services)})

    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": str(pretty_print_error(exc))}), 500

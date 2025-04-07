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
Model to fetch and format critical services from a Kubernetes ConfigMap.
"""

from flask import current_app as app

from src.server.resources.critical_services import get_configmap
from src.server.resources.error_print import pretty_print_error
from src.server.resources.rrs_logging import get_log_id

CM_NAME = "rrs-mon-static"
CM_NAMESPACE = "rack-resiliency"
CM_KEY = "critical-service-config.json"


def get_critical_services(services: dict) -> dict:
    """
    Fetch and format critical services grouped by namespace.

    Args:
        services (dict): A dictionary of services with their metadata.

    Returns:
        dict: A structured dictionary grouped by namespaces.
    """
    log_id = get_log_id()  # Generate a unique log ID
    result = {"namespace": {}}
    if "error" in services:
        app.logger.warning(f"[{log_id}] Could not critical services.")
        return services

    try:
        app.logger.info(f"[{log_id}] Starting to fetch and format critical services.")

        for name, details in services.items():
            namespace = details.get("namespace", "unknown")
            service_type = details.get("type", "unknown")

            if namespace not in result["namespace"]:
                result["namespace"][namespace] = []

            result["namespace"][namespace].append({"name": name, "type": service_type})

        app.logger.info(
            f"[{log_id}] Successfully fetched and formatted critical services."
        )

    except (KeyError, TypeError, ValueError) as exc:
        app.logger.error(
            f"[{log_id}] Error occurred while processing services: {pretty_print_error(exc)}"
        )
        return {"error": str(pretty_print_error(exc))}

    return result


def get_critical_service_list():
    """
    Fetch critical services from the ConfigMap and return as a JSON response.

    Returns:
        Flask Response: JSON response containing critical services or an error message.
    """
    log_id = get_log_id()  # Generate a unique log ID
    try:
        app.logger.info(f"[{log_id}] Fetching critical services from ConfigMap.")

        config_data = get_configmap(CM_NAME, CM_NAMESPACE, CM_KEY)
        services = config_data.get("critical-services", {})

        # app.logger.info(f"[{log_id}] Successfully fetched critical services from ConfigMap.")

        return {"critical-services": get_critical_services(services)}

    except (KeyError, TypeError, ValueError) as exc:
        app.logger.error(
            f"[{log_id}] Error while fetching critical services from ConfigMap: {pretty_print_error(exc)}"
        )
        return {"error": str(pretty_print_error(exc))}, 500

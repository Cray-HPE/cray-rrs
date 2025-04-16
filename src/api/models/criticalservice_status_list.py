# MIT License
#
# (C) Copyright [2025] Hewlett Packard Enterprise Development LP
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

import json
from typing import Dict, List, Any, Tuple, Union
from flask import current_app as app
from src.lib.rrs_logging import get_log_id
from src.lib.lib_configmap import ConfigMapHelper

CM_NAME = "rrs-mon-dynamic"  # Name of the ConfigMap
CM_NAMESPACE = "rack-resiliency"  # Namespace where the ConfigMap is located
CM_KEY = "critical-service-config.json"  # Key inside the ConfigMap that holds the critical services data


class CriticalServiceStatusLister:
    """Class to fetch and format critical services from the ConfigMap."""

    @staticmethod
    def get_critical_services_status(
        services: Union[Dict[str, Any], str],
    ) -> Dict[str, Any]:
        """Fetch and format critical services grouped by namespace in the required structure.

        Args:
            services: Dictionary of services or error string

        Returns:
            Formatted dictionary of services by namespace or error dictionary
        """
        log_id = get_log_id()  # Generate a unique log ID for logging
        # If services is a string indicating an error, log and return an empty namespace dictionary
        if isinstance(services, str) and "error" in services:
            app.logger.warning(f"[{log_id}] Could not fetch critical services.")
            return {
                "namespace": {}
            }  # Return empty namespace dictionary instead of unhashable set
        try:
            # Ensure the services are provided as a dictionary
            if not isinstance(services, dict):
                app.logger.error(
                    f"[{log_id}] Invalid format for services: {type(services)}"
                )
                return {"error": "Invalid format for services, expected a dictionary"}

            result: Dict[str, Dict[str, List[Dict[str, Any]]]] = {"namespace": {}}
            # Iterate over the services and group them by their namespace
            for name, details in services.items():
                namespace = details["namespace"]
                if namespace not in result["namespace"]:
                    result["namespace"][
                        namespace
                    ] = []  # Create a list if the namespace is not yet added
                result["namespace"][namespace].append(
                    {
                        "name": name,
                        "type": details["type"],
                        "status": details["status"],
                        "balanced": details["balanced"],
                    }
                )

            app.logger.info(f"[{log_id}] Formatted critical services by namespace.")
            return result  # Return the formatted services grouped by namespace

        except Exception as e:
            # Log and return an error if an exception occurs while formatting the services
            app.logger.error(
                f"[{log_id}] Error while formatting critical services: {(e)}"
            )
            return {"error": str((e))}

    @staticmethod
    def get_criticalservice_status_list() -> Tuple[Dict[str, Any], int]:
        """
        Fetch critical services from the ConfigMap and return as a JSON response.

        Returns:
            Tuple containing JSON response dict with critical services and HTTP status code
        """
        log_id = get_log_id()  # Generate a unique log ID for logging
        try:
            app.logger.info(
                f"[{log_id}] Fetching ConfigMap: {CM_NAME} from namespace: {CM_NAMESPACE}"
            )
            cm_data = ConfigMapHelper.get_configmap(
                CM_NAMESPACE, CM_NAME
            )  # Fetch ConfigMap data
            config_data = {}
            if CM_KEY in cm_data:
                config_data = json.loads(
                    cm_data[CM_KEY]
                )  # Parse the JSON from the ConfigMap
            services = config_data.get(
                "critical-services", {}
            )  # Get the 'critical-services' part
            # If no critical services are found, log and return an error response
            if not services:
                app.logger.warning(
                    f"[{log_id}] No 'critical-services' found in the ConfigMap"
                )
                return (
                    {"error": "'critical-services' not found in the ConfigMap"}
                ), 404  # Return a 404 error if no critical services found

            # Return the formatted critical services by namespace
            return {
                "critical-services": CriticalServiceStatusLister.get_critical_services_status(
                    services  # Call the helper method to format the services
                )
            }, 200  # Return a 200 HTTP status for a successful response

        except (KeyError, TypeError, ValueError) as exc:
            # Catch known exceptions related to invalid data or missing keys
            app.logger.error(
                f"[{log_id}] Error while processing the ConfigMap: {(exc)}"
            )
            return (
                {"error": str((exc))}
            ), 500  # Return a 500 HTTP error if a processing error occurs

        except Exception as e:
            # Catch all other unexpected exceptions and log them
            app.logger.error(
                f"[{log_id}] Unexpected error while fetching critical services: {(e)}"
            )
            return (
                {"error": str((e))}
            ), 500  # Return a 500 HTTP error for unexpected issues

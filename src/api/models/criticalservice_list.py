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
Model to retrive the criticalservices from Kubernetes ConfigMap in following format.
{
  "critical-services": {
    "namespace": {
      "ns-1": [
        {
          "name": "ns1-svc-1",
          "type": "Deployment"
        },
        {
          "name": "ns1-svc-2",
          "type": "StatefulSet"
        }
      ],
      "ns-2": [
        {
          "name": "ns2-svc-1",
          "type": "StatefulSet"
        }
      ]
    }
  }
}

"""

import json
from typing import Dict, List, Tuple, Any
from flask import current_app as app
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.error_print import pretty_print_error
from src.lib.rrs_logging import get_log_id

CM_NAME = "rrs-mon-static"  # Name of the ConfigMap
CM_NAMESPACE = "rack-resiliency"  # Namespace where the ConfigMap is located
CM_KEY = "critical-service-config.json"  # Key to access the specific configuration in the ConfigMap


class CriticalServicesLister:
    """Class to fetch and format critical services grouped by namespace."""

    @staticmethod
    def get_critical_services(services: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Fetch and format critical services grouped by namespace.

        Args:
            services (dict): A dictionary of services with their metadata.

        Returns:
            dict: A structured dictionary grouped by namespaces with service names and types.
        """
        log_id = get_log_id()  # Generate a unique log ID to track this request

        # Initialize result dictionary to store services grouped by namespaces
        result: Dict[str, Dict[str, List[Dict[str, str]]]] = {"namespace": {}}

        # Check if there was an error in the services data
        if "error" in services:
            app.logger.warning(f"[{log_id}] Could not fetch critical services.")
            return services

        try:
            # Log the start of the process
            app.logger.info(
                f"[{log_id}] Starting to fetch and format critical services."
            )

            # Loop through the services and organize them by their namespace
            for name, details in services.items():
                namespace = details.get("namespace", "unknown")
                service_type = details.get("type", "unknown")

                # If namespace is not already in the result, add it
                if namespace not in result["namespace"]:
                    result["namespace"][namespace] = []

                # Append the service name and type under the respective namespace
                result["namespace"][namespace].append(
                    {"name": name, "type": service_type}
                )

            # Log the successful completion of the service formatting process
            app.logger.info(
                f"[{log_id}] Successfully fetched and formatted critical services."
            )

        except (KeyError, TypeError, ValueError) as exc:
            # Log any errors that occur during the service formatting process
            app.logger.error(
                f"[{log_id}] Error occurred while processing services: {pretty_print_error(str(exc))}"
            )
            return {"error": str(pretty_print_error(str(exc)))}

        # Return the formatted result grouped by namespace
        return result

    @staticmethod
    def get_critical_service_list() -> Tuple[Dict[str, Any], int]:
        """
        Fetch critical services from the ConfigMap and return as a JSON response.

        Returns:
            Flask Response: JSON response containing critical services or an error message with status code.
        """
        log_id = get_log_id()  # Generate a unique log ID to track this request
        try:
            # Log the start of the fetching process
            app.logger.info(f"[{log_id}] Fetching critical services from ConfigMap.")

            # Fetch the ConfigMap data
            cm_data = ConfigMapHelper.get_configmap(CM_NAMESPACE, CM_NAME)
            config_data = {}
            if CM_KEY in cm_data:
                # Parse the data from the ConfigMap if available
                config_data = json.loads(cm_data[CM_KEY])

            # Extract the critical services from the ConfigMap data
            services = config_data.get("critical-services", {})

            # Return the formatted services as a JSON response
            return {
                "critical-services": CriticalServicesLister.get_critical_services(
                    services
                )
            }, 200

        except (KeyError, TypeError, ValueError) as exc:
            # Log any errors during the fetching process
            app.logger.error(
                f"[{log_id}] Error while fetching critical services from ConfigMap: {pretty_print_error(str(exc))}"
            )
            # Return an error response with status code 500
            return {"error": str(pretty_print_error(str(exc)))}, 500

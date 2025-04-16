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
Model to describe the status of critical services.
"""

import json
from typing import Dict, List, Any, Optional
from flask import current_app as app
from kubernetes import client  # type: ignore
from src.api.resources.critical_services import CriticalServiceHelper
from src.lib.lib_configmap import ConfigMapHelper
from src.api.models.criticalservice_status_list import CM_KEY, CM_NAME, CM_NAMESPACE
from src.lib.rrs_logging import get_log_id


class CriticalServiceStatusDescriber:
    """Class to describe the status of critical services."""

    @staticmethod
    def get_service_details(
        services: Dict[str, Dict[str, Any]], service_name: str, test: bool = False
    ) -> Dict[str, Any]:
        """
        Retrieve details of a specific critical service.

        Args:
            services: Dictionary of services from the ConfigMap.
            service_name: Name of the service to retrieve.
            test: Flag to indicate if this is a test run.

        Returns:
            Service details including name, namespace, type, configured instances,
            running instances, and pod details.
        """
        log_id = get_log_id()  # Generate a unique log ID for tracking

        try:
            # Check if the service exists in the services dictionary
            if service_name not in services:
                app.logger.warning(
                    f"[{log_id}] Service '{service_name}' not found in the ConfigMap."
                )
                return {"error": "Service not found"}

            # Retrieve the service info from the dictionary
            service_info = services[service_name]
            namespace, resource_type, balance, status = (
                service_info["namespace"],
                service_info["type"],
                service_info["balanced"],
                service_info["status"],
            )

            # Initialize variables for filtering pods and counting running pods
            filtered_pods: List[Dict[str, Any]] = []
            running_pods: int = 0
            configured_instances: Optional[int] = None

            # If not a test run, fetch real pod data
            if not test:
                # Get namespaced pods for the service using the helper
                filtered_pods, running_pods = CriticalServiceHelper.get_namespaced_pods(
                    service_info, service_name
                )

                # Initialize Kubernetes client for resource management
                apps_v1 = client.AppsV1Api()

                # Dictionary mapping resource types to their corresponding methods
                resource_methods = {
                    "Deployment": apps_v1.read_namespaced_deployment,
                    "StatefulSet": apps_v1.read_namespaced_stateful_set,
                    "DaemonSet": apps_v1.read_namespaced_daemon_set,
                }

                # Check the resource type and retrieve the configuration for the service
                if resource_type in resource_methods:
                    resource = resource_methods[resource_type](service_name, namespace)
                    # Retrieve configured instances (number of replicas or desired instances)
                    configured_instances = (
                        resource.spec.replicas
                        if hasattr(resource.spec, "replicas")
                        else resource.status.desired_number_scheduled
                    )

            # Log the success of retrieving service details
            app.logger.info(
                f"[{log_id}] Service '{service_name}' details retrieved successfully."
            )

            # Return a structured dictionary containing the service details
            return {
                "Critical Service": {
                    "Name": service_name,
                    "Namespace": namespace,
                    "Type": resource_type,
                    "Status": status,
                    "Balanced": balance,
                    "Configured Instances": configured_instances,
                    "Currently Running Instances": running_pods,
                    "Pods": filtered_pods,
                }
            }

        # Handling specific Kubernetes API exceptions
        except client.exceptions.ApiException as api_exc:
            app.logger.error(
                f"[{log_id}] API exception occurred while retrieving service '{service_name}': "
                f"{(api_exc)}"
            )
            return {"error": str((api_exc))}

        # Handling missing keys in the service data
        except KeyError as key_exc:
            app.logger.error(
                f"[{log_id}] Missing key while processing service '{service_name}': {key_exc}"
            )
            return {"error": f"Missing key: {key_exc}"}

        # Handling parsing errors during the service details processing
        except (TypeError, ValueError) as parse_exc:
            app.logger.error(
                f"[{log_id}] Parsing error occurred while processing service '{service_name}': {str(parse_exc)}"
            )
            return {"error": f"Parsing error: {parse_exc}"}

        # Catch-all for unexpected errors
        except Exception as exc:
            app.logger.error(
                f"[{log_id}] Unexpected error occurred while processing service '{service_name}': {(exc)}"
            )
            return {"error": str((exc))}

    @staticmethod
    def describe_service_status(service_name: str) -> Dict[str, Any]:
        """
        Retrieve service details and return as a JSON response.

        Args:
            service_name: Name of the critical service.

        Returns:
            JSON response with service details or error message.
        """
        log_id = get_log_id()  # Generate a unique log ID for tracking
        try:
            # Log the attempt to fetch service details
            app.logger.info(
                f"[{log_id}] Fetching details for service '{service_name}'."
            )

            # Fetch the ConfigMap data containing critical service information
            cm_data = ConfigMapHelper.get_configmap(CM_NAMESPACE, CM_NAME)
            config_data = {}
            if CM_KEY in cm_data:
                config_data = json.loads(cm_data[CM_KEY])

            # Retrieve the critical services from the configuration
            services = config_data.get("critical-services", {})

            # Get the service details using the helper method
            return CriticalServiceStatusDescriber.get_service_details(
                services, service_name
            )

        # Catch all exceptions during the process of fetching service details
        except Exception as exc:
            app.logger.error(
                f"[{log_id}] Error while fetching details for service '{service_name}': {(exc)}"
            )
            return {"error": str((exc))}

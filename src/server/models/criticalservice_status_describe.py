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

from flask import current_app as app
from kubernetes import client # type: ignore
from src.server.resources.critical_services import CriticalServiceHelper
from src.server.resources.error_print import pretty_print_error
from src.server.models.criticalservice_status_list import CM_KEY, CM_NAME, CM_NAMESPACE
from src.server.resources.rrs_logging import get_log_id

class CriticalServiceStatusDescriber:
    """Class to describe the status of critical services."""

    @staticmethod
    def get_service_details(services, service_name, test=False):
        """
        Retrieve details of a specific critical service.

        Args:
            services (dict): Dictionary of services from the ConfigMap.
            service_name (str): Name of the service to retrieve.

        Returns:
            dict: Service details including name, namespace, type, configured instances,
                  running instances, and pod details.
        """
        log_id = get_log_id()  # Generate a unique log ID
        try:
            if service_name not in services:
                app.logger.warning(
                    f"[{log_id}] Service '{service_name}' not found in the ConfigMap."
                )
                return {"error": "Service not found"}

            service_info = services[service_name]
            namespace, resource_type, balance, status = (
                service_info["namespace"],
                service_info["type"],
                service_info["balanced"],
                service_info["status"],
            )
            filtered_pods = []
            running_pods = 0
            configured_instances = None
            if not test:
                filtered_pods, running_pods = CriticalServiceHelper.get_namespaced_pods(
                    service_info, service_name
                )

                apps_v1 = client.AppsV1Api()

                resource_methods = {
                    "Deployment": apps_v1.read_namespaced_deployment,
                    "StatefulSet": apps_v1.read_namespaced_stateful_set,
                    "DaemonSet": apps_v1.read_namespaced_daemon_set,
                }

                if resource_type in resource_methods:
                    resource = resource_methods[resource_type](service_name, namespace)
                    configured_instances = (
                        resource.spec.replicas
                        if hasattr(resource.spec, "replicas")
                        else resource.status.desired_number_scheduled
                    )

            app.logger.info(
                f"[{log_id}] Service '{service_name}' details retrieved successfully."
            )

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

        except client.exceptions.ApiException as api_exc:
            app.logger.error(
                f"[{log_id}] API exception occurred while retrieving service '{service_name}': "
                f"{pretty_print_error(api_exc)}"
            )

            return {"error": str(pretty_print_error(api_exc))}
        except KeyError as key_exc:
            app.logger.error(
                f"[{log_id}] Missing key while processing service '{service_name}': {key_exc}"
            )
            return {"error": f"Missing key: {key_exc}"}
        except (TypeError, ValueError) as parse_exc:
            app.logger.error(
                f"[{log_id}] Parsing error occurred while processing service '{service_name}': {str(parse_exc)}"
            )
            return {"error": f"Parsing error: {parse_exc}"}
        except Exception as exc:  # Catch-all, but logs properly
            app.logger.error(
                f"[{log_id}] Unexpected error occurred while processing service '{service_name}': {pretty_print_error(exc)}"
            )
            return {"error": str(pretty_print_error(exc))}

    @staticmethod
    def describe_service_status(service_name):
        """
        Retrieve service details and return as a JSON response.

        Args:
            service_name (str): Name of the critical service.

        Returns:
            JSON: JSON response with service details or error message.
        """
        log_id = get_log_id()  # Generate a unique log ID
        try:
            app.logger.info(f"[{log_id}] Fetching details for service '{service_name}'.")
            services = CriticalServiceHelper.get_configmap(CM_NAME, CM_NAMESPACE, CM_KEY).get(
                "critical-services", {}
            )
            return CriticalServiceStatusDescriber.get_service_details(services, service_name)

        except Exception as exc:
            app.logger.error(
                f"[{log_id}] Error while fetching details for service '{service_name}': {pretty_print_error(exc)}"
            )
            return {"error": str(pretty_print_error(exc))}

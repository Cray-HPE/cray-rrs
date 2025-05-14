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
This module provides functionality for managing criticalservices related to Rack Resiliency.
It includes classes and methods to fetch, describe, update, and format critical services
stored in Kubernetes ConfigMaps.

Classes:
    - CriticalServices: Handles listing, describing, and updating critical services.
    - CriticalServicesStatus: Handles fetching and formatting the status of critical services.

Usage:
    This module is designed to be used as part of RRS for managing
    Rack Resiliency critical services. It provides static methods for interacting
    with Kubernetes ConfigMaps and formatting service data for API responses.
"""

import json
import os
from typing import Dict, List, Any, Union, Optional
from datetime import datetime
from flask import current_app as app
from kubernetes import client  # type: ignore
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.rrs_logging import get_log_id
from src.api.models.criticalservice import CriticalServiceHelper

CM_NAMESPACE = os.getenv("namespace", "")
CM_KEY = os.getenv("key_criticalservice", "")


class CriticalServices:
    """Class to list, describe and update criticalservices related to Rack Resiliency."""

    @staticmethod
    def fetch_critical_services(services: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
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

        try:
            # Log the start of the process
            app.logger.info(
                f"[{log_id}] Starting to fetch and format critical services."
            )

            # Loop through the services and organize them by their namespace
            for name, details in services.items():
                namespace = details.get("namespace")
                service_type = details.get("type")

                # If namespace is not already in the result, add it
                if namespace and namespace not in result["namespace"]:
                    result["namespace"][namespace] = []

                # Append the service name and type under the respective namespace
                if namespace:
                    result["namespace"][namespace].append(
                        {"name": name, "type": service_type or ""}
                    )

            # Log the successful completion of the service formatting process
            app.logger.info(
                f"[{log_id}] Successfully fetched and formatted critical services."
            )
            # Return the formatted result grouped by namespace
            return result

        except (KeyError, TypeError, ValueError) as exc:
            # Log any errors that occur during the service formatting process
            app.logger.error(
                f"[{log_id}] Error occurred while processing services: {str(exc)}"
            )
            return {"error": str(exc)}

    @staticmethod
    def get_critical_service_list() -> Dict[str, Any]:
        """
        Fetch critical services from the ConfigMap and return as a JSON response.

        Returns:
            Flask Response: JSON response containing critical services or an error message with status code.
        """
        log_id = get_log_id()  # Generate a unique log ID to track this request
        try:
            CM_NAME = os.getenv("static_cm_name", "")
            # Log the start of the fetching process
            app.logger.info(f"[{log_id}] Fetching critical services from ConfigMap.")
            # Fetch the ConfigMap data
            services = CriticalServiceHelper.fetch_service_list(
                CM_NAME, CM_NAMESPACE, CM_KEY
            )

            # Check if there was an error in the services data
            if "error" in services:
                app.logger.warning(f"[{log_id}] Could not fetch critical services.")
                return services

            # Return the formatted services as a JSON response
            return {
                "critical-services": CriticalServices.fetch_critical_services(services)
            }

        except (KeyError, TypeError, ValueError) as exc:
            # Log any errors during the fetching process
            app.logger.error(
                f"[{log_id}] Error while fetching critical services from ConfigMap: {str(exc)}"
            )
            # Return an error response with status code 500
            return {"error": str(exc)}

    @staticmethod
    def describe_service(
        service_name: str,
    ) -> Union[Dict[str, Any], Dict[str, str]]:
        """
        Retrieve service details and return as a JSON response.

        Args:
            service_name (str): The name of the critical service to describe.

        Returns:
            JSON response with service details or error message with status code.
        """
        log_id = get_log_id()  # Generate a unique log ID to track this request
        try:
            CM_NAME = os.getenv("dynamic_cm_name", "")
            # Log the start of the process to retrieve service details
            app.logger.info(
                f"[{log_id}] Attempting to retrieve details for service: {service_name}"
            )

            # Fetch the ConfigMap that contains the critical service details
            services = CriticalServiceHelper.fetch_service_list(
                CM_NAME, CM_NAMESPACE, CM_KEY
            )
            if service_name not in services:
                app.logger.warning(
                    f"[{log_id}] Service '{service_name}' not found in the ConfigMap."
                )
                return {"error": "Service not found"}
            # Use another helper to get the details of the service
            data = CriticalServicesStatus.get_service_details(services, service_name)

            # In case of error throw it
            if "error" in data:
                app.logger.warning(f"[{log_id}] Error encountered in result: {data}")
                return data

            # Pick up the relevant internal fields
            fields_to_exclude = [
                "Pods",
                "Balanced",
                "Status",
                "Currently Running Instances",
            ]
            # Build the result dictionary
            result = {
                "Critical Service": {
                    key: value
                    for key, value in data["Critical Service"].items()
                    if key not in fields_to_exclude
                }
            }
            # Log the successful retrieval of the service details
            app.logger.info(
                f"[{log_id}] Successfully retrieved details for service: {service_name}"
            )

            # Return the processed service details
            return result

        except Exception as exc:
            # Log any errors that occur during the process
            error_message = str(exc)
            app.logger.error(
                f"[{log_id}] Error occurred while describing service {service_name}: "
                f"{error_message}"
            )
            # Return an error response with status code 500
            return {"error": error_message}

    @staticmethod
    def update_configmap(
        new_data: Dict[str, Any], existing_data: Dict[str, Any], test: bool = False
    ) -> Dict[str, Any]:
        """
        Update the ConfigMap with new critical services.

        Args:
            new_data: Dictionary containing new critical services
            existing_data: Dictionary containing existing critical services
            test: Whether this is a test run (don't update ConfigMap if True)

        Returns:
            Dict containing update status and details
        """
        log_id = get_log_id()  # Generate a unique log ID for this operation
        try:
            CM_NAME = os.getenv("static_cm_name", "")
            # Extract existing critical services and the new critical services
            existing_services = existing_data
            new_services = new_data["critical-services"]

            # Separate added and skipped services
            added_services = [s for s in new_services if s not in existing_services]
            skipped_services = [s for s in new_services if s in existing_services]

            # Add new services to existing services
            for service_name in added_services:
                existing_services[service_name] = new_services[service_name]

            # Prepare new ConfigMap data
            new_cm_data = json.dumps({"critical-services": existing_services}, indent=2)
            if not test:  # Only update ConfigMap if not in test mode
                ConfigMapHelper.update_configmap_data(
                    CM_NAMESPACE, CM_NAME, None, CM_KEY, new_cm_data, ""
                )
                app.logger.info(f"[{log_id}] Updating timestamp in ConfigMap")
                # Update the timestamp of the last update in the ConfigMap
                ConfigMapHelper.update_configmap_data(
                    CM_NAMESPACE,
                    CM_NAME,
                    None,
                    "last_updated_timestamp",
                    datetime.utcnow().isoformat() + "Z",
                    "",
                )
            # Log the event using app.logger
            app.logger.info(
                f"[{log_id}] Successfully added {len(added_services)} services to ConfigMap"
            )
            app.logger.info(
                f"[{log_id}] Skipped {len(skipped_services)} services that already exist"
            )

            # Return the result of the update operation
            return {
                "Update": "Successful" if added_services else "Services Already Exist",
                "Successfully Added Services": added_services or [],
                "Already Existing Services": skipped_services or [],
            }

        except Exception as e:
            app.logger.error(f"[{log_id}] Unexpected error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

    @staticmethod
    def update_critical_services(
        new_data: Dict[str, str],
    ) -> Union[Dict[str, Any], Dict[str, str]]:
        """
        Function to update critical services in the ConfigMap.

        Args:
            new_data: Dictionary containing the new services data with 'from_file' key

        Returns:
            Either a dictionary with update results or a tuple with error dict and status code
        """
        log_id = get_log_id()  # Generate a unique log ID for this operation
        try:
            CM_NAME = os.getenv("static_cm_name", "")
            if "error" in new_data:
                app.logger.error(f"[{log_id}] Error in new data: {new_data}")
                return new_data

            # Try parsing the JSON string from the 'from_file' key
            try:
                new_services = json.loads(new_data["from_file"])
            except json.JSONDecodeError as json_err:
                app.logger.error(
                    f"[{log_id}] Invalid JSON format in request: {json_err}"
                )
                return {"error": "Invalid JSON format in services"}

            # Check if 'critical-services' key is present in the parsed data
            if "critical-services" not in new_services:
                app.logger.error(f"[{log_id}] Missing 'critical-services' in payload")
                return {"error": "Missing 'critical-services' in payload"}

            # Fetch the current ConfigMap data
            existing_data = CriticalServiceHelper.fetch_service_list(
                CM_NAME, CM_NAMESPACE, CM_KEY
            )

            if "error" in existing_data:
                app.logger.error(f"[{log_id}] Error in existing data: {existing_data}")
                return existing_data
            # Call the update_configmap function to update the critical services
            result = CriticalServices.update_configmap(new_services, existing_data)
            return result

        # Handle any exceptions and return error responses
        except Exception as e:
            app.logger.error(
                f"[{log_id}] Unhandled error in update_critical_services: {str(e)}"
            )
            return {"error": f"Unexpected error: {str(e)}"}


class CriticalServicesStatus:
    """Class to list, describe the status of criticalservices related to Rack Resiliency."""

    @staticmethod
    def fetch_critical_services_status(
        services: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fetch and format critical services grouped by namespace in the required structure.

        Args:
            services: Dictionary of services or error string

        Returns:
            Formatted dictionary of services by namespace or error dictionary
        """
        log_id = get_log_id()
        result: Dict[str, Dict[str, List[Dict[str, Any]]]] = {"namespace": {}}

        # Iterate over the services and group them by their namespace
        for name, details in services.items():
            namespace = details["namespace"]
            if namespace not in result["namespace"]:
                result["namespace"][namespace] = []

            result["namespace"][namespace].append(
                {
                    "name": name,
                    "type": details["type"],
                    "status": details["status"],
                    "balanced": details["balanced"],
                }
            )

        app.logger.info(f"[{log_id}] Formatted critical services by namespace.")
        return result

    @staticmethod
    def get_criticalservice_status_list() -> Dict[str, Any]:
        """
        Fetch critical services from the ConfigMap and return as a JSON response.

        Returns:
            Tuple containing JSON response dict with critical services and HTTP status code
        """
        log_id = get_log_id()  # Generate a unique log ID for logging
        try:
            CM_NAME = os.getenv("dynamic_cm_name", "")
            app.logger.info(
                f"[{log_id}] Fetching ConfigMap: {CM_NAME} from namespace: {CM_NAMESPACE}"
            )
            services = CriticalServiceHelper.fetch_service_list(
                CM_NAME, CM_NAMESPACE, CM_KEY
            )

            # Check if there was an error in the services data
            if "error" in services:
                app.logger.warning(f"[{log_id}] Could not fetch critical services.")
                return services

            # If no critical services are found, log and return an error response
            if not services:
                app.logger.warning(
                    f"[{log_id}] No 'critical-services' found in the ConfigMap"
                )
                return {"error": "'critical-services' not found in the ConfigMap"}

            # Return the critical services grouped by namespace
            return {
                "critical-services": CriticalServicesStatus.fetch_critical_services_status(
                    services
                )
            }
        except (KeyError, TypeError, ValueError) as exc:
            # Catch known exceptions related to invalid data or missing keys
            app.logger.error(
                f"[{log_id}] Error while processing the ConfigMap: {str(exc)}"
            )
            return {"error": str(exc)}

        except Exception as e:
            # Catch all other unexpected exceptions and log them
            app.logger.error(
                f"[{log_id}] Unexpected error while fetching critical services: {str(e)}"
            )
            return {"error": str(e)}

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
                f"{str(api_exc)}"
            )
            return {"error": str(api_exc)}

        # Catch-all for unexpected errors
        except Exception as e:
            app.logger.error(
                f"[{log_id}] Unexpected error occurred while processing service '{service_name}': {str(e)}"
            )
            return {"error": str(e)}

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
            CM_NAME = os.getenv("dynamic_cm_name", "")
            # Log the attempt to fetch service details
            app.logger.info(
                f"[{log_id}] Fetching details for service '{service_name}'."
            )
            services = CriticalServiceHelper.fetch_service_list(
                CM_NAME, CM_NAMESPACE, CM_KEY
            )
            # Check if the service exists in the services dictionary
            if service_name not in services:
                app.logger.warning(
                    f"[{log_id}] Service '{service_name}' not found in the ConfigMap."
                )
                return {"error": "Service not found"}

            # Get the service details using the helper method
            return CriticalServicesStatus.get_service_details(services, service_name)

        # Catch all exceptions during the process of fetching service details
        except Exception as e:
            app.logger.error(
                f"[{log_id}] Error while fetching details for service '{service_name}': {str(e)}"
            )
            return {"error": str(e)}

#
# MIT License
#
#  (C) Copyright 2025-2026 Hewlett Packard Enterprise Development LP
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
from typing import Optional
from datetime import datetime
from flask import current_app as app
from typing_extensions import assert_never
from kubernetes import client
from kubernetes.client import V1Deployment, V1StatefulSet
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.rrs_logging import get_log_id
from src.api.models.criticalservice import CriticalServiceHelper
from src.lib.rrs_constants import (
    NAMESPACE,
    CRITICAL_SERVICE_KEY,
    STATIC_CM,
    DYNAMIC_CM,
    CmType,
)
from src.lib.schema import (
    PodSchema,
    CriticalServicesListSchema,
    CriticalServicesStatusListSchema,
    CriticalServiceStatusDescribeSchema,
    CriticalServicesItem,
    CriticalServicesStatusItem,
    CriticalServiceDescribeSchema,
    CriticalServiceUpdateSchema,
    CriticalServiceCmStaticType,
    CriticalServiceCmDynamicSchema,
    CriticalServiceCmStaticSchema,
    ErrorDict,
)


class CriticalServices:
    """Class to list, describe and update criticalservices related to Rack Resiliency."""

    @staticmethod
    def fetch_critical_services(
        services: dict[str, CriticalServiceCmStaticSchema],
    ) -> CriticalServicesItem:
        """
        Fetch and format critical services grouped by namespace.

        Args:
            services (dict): A dictionary of services with their metadata.

        Returns:
            dict: A structured dictionary grouped by namespaces with service names and types.
        """
        log_id = get_log_id()  # Generate a unique log ID to track this request

        # Initialize result dictionary to store services grouped by namespaces
        result: CriticalServicesItem = {"namespace": {}}

        # Log the start of the process
        app.logger.info(f"[{log_id}] Starting to fetch and format critical services.")

        # Loop through the services and organize them by their namespace
        for name, details in services.items():
            namespace = details["namespace"]
            service_type = details["type"]

            # If namespace is not already in the result, add it
            if namespace and namespace not in result["namespace"]:
                result["namespace"][namespace] = []

            # Append the service name and type under the respective namespace
            if namespace:
                result["namespace"][namespace].append(
                    {"name": name, "type": service_type}
                )

        # Log the successful completion of the service formatting process
        app.logger.info(
            f"[{log_id}] Successfully fetched and formatted critical services."
        )
        # Return the formatted result grouped by namespace
        return result

    @staticmethod
    def get_critical_service_list() -> CriticalServicesListSchema:
        """
        Fetch critical services from the ConfigMap and return as a JSON response.

        Returns:
            Flask Response: JSON response containing critical services or an error message with status code.
        """
        log_id = get_log_id()  # Generate a unique log ID to track this request

        # Log the start of the fetching process
        app.logger.info(f"[{log_id}] Fetching critical services from ConfigMap.")
        # Fetch the ConfigMap data
        services = CriticalServiceHelper.fetch_service_list(
            CmType.STATIC, NAMESPACE, CRITICAL_SERVICE_KEY
        )

        data = CriticalServices.fetch_critical_services(services)

        return {"critical_services": data}

    @staticmethod
    def describe_service(
        service_name: str,
    ) -> CriticalServiceDescribeSchema | ErrorDict:
        """
        Retrieve service details and return as a JSON response.

        Args:
            service_name (str): The name of the critical service to describe.

        Returns:
            JSON response with service details or error message with status code.
        """
        log_id = get_log_id()  # Generate a unique log ID to track this request

        # Log the start of the process to retrieve service details
        app.logger.info(
            f"[{log_id}] Attempting to retrieve details for service: {service_name}"
        )

        # Fetch the ConfigMap that contains the critical service details
        services = CriticalServiceHelper.fetch_service_list(
            CmType.DYNAMIC, NAMESPACE, CRITICAL_SERVICE_KEY
        )

        if service_name not in services:
            app.logger.warning(
                f"[{log_id}] Service '{service_name}' not found in the ConfigMap."
            )
            return ErrorDict(error="Service not found")
        # Use another helper to get the details of the service
        data = CriticalServicesStatus.get_service_details(services, service_name)

        # Build the result dictionary
        result: CriticalServiceDescribeSchema = {
            "critical_service": {
                "name": data["critical_service"]["name"],
                "namespace": data["critical_service"]["namespace"],
                "type": data["critical_service"]["type"],
                "configured_instances": data["critical_service"][
                    "configured_instances"
                ],
            }
        }
        # Log the successful retrieval of the service details
        app.logger.info(
            f"[{log_id}] Successfully retrieved details for service: {service_name}"
        )

        # Return the processed service details
        return result

    @staticmethod
    def update_configmap(
        new_data: CriticalServiceCmStaticType,
        existing_data: dict[str, CriticalServiceCmStaticSchema],
        test: bool = False,
    ) -> CriticalServiceUpdateSchema:
        """
        Update the ConfigMap with new critical services.

        Args:
            new_data: Dictionary containing new critical services
            existing_data: Dictionary containing existing critical services
            test: Whether this is a test run (don't update ConfigMap if True)

        Returns:
            dict containing update status and details
        """
        log_id = get_log_id()  # Generate a unique log ID for this operation

        # Extract existing critical services and the new critical services
        existing_services = existing_data
        new_services = new_data["critical_services"]

        # Separate added and skipped services
        added_services = [s for s in new_services if s not in existing_services]
        skipped_services = [s for s in new_services if s in existing_services]

        # Add new services to existing services
        for service_name in added_services:
            existing_services[service_name] = new_services[service_name]

        # Prepare new ConfigMap data
        new_cm_data = json.dumps(
            CriticalServiceCmStaticType(critical_services=existing_services), indent=2
        )
        if not test:  # Only update ConfigMap if not in test mode
            ConfigMapHelper.update_configmap_data(
                None, CRITICAL_SERVICE_KEY, new_cm_data, NAMESPACE, STATIC_CM
            )
            app.logger.info(f"[{log_id}] Updating timestamp in ConfigMap")
            # Update the timestamp of the last update in the ConfigMap
            ConfigMapHelper.update_configmap_data(
                None,
                "last_updated_timestamp",
                datetime.utcnow().isoformat() + "Z",
                NAMESPACE,
                STATIC_CM,
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
            "Successfully_Added_Services": added_services or [],
            "Already_Existing_Services": skipped_services or [],
        }

    @staticmethod
    def update_critical_services(
        new_data: CriticalServiceCmStaticType,
    ) -> CriticalServiceUpdateSchema | ErrorDict:
        """
        Function to update critical services in the ConfigMap.

        Args:
            new_data: Dictionary containing the new services data with 'from_file' key

        Returns:
            Either a dictionary with update results or a tuple with error dict and status code
        """
        log_id = get_log_id()  # Generate a unique log ID for this operation
        try:
            # Check if 'critical_services' key is present in the parsed data
            if "critical_services" not in new_data:
                app.logger.error(f"[{log_id}] Missing 'critical_services' in payload")
                return {"error": "Missing 'critical_services' in payload"}

            # Fetch the current ConfigMap data
            existing_data = CriticalServiceHelper.fetch_service_list(
                CmType.STATIC, NAMESPACE, CRITICAL_SERVICE_KEY
            )

            # Call the update_configmap function to update the critical services
            result = CriticalServices.update_configmap(new_data, existing_data)

            return result

        # Handle any exceptions and return error responses
        except json.JSONDecodeError as json_err:
            app.logger.error(f"[{log_id}] Invalid JSON format in request: {json_err}")
            raise
        except Exception as e:
            app.logger.error(
                f"[{log_id}] Unhandled error in update_critical_services: {str(e)}"
            )
            raise


class CriticalServicesStatus:
    """Class to list, describe the status of criticalservices related to Rack Resiliency."""

    @staticmethod
    def fetch_critical_services_status(
        services: dict[str, CriticalServiceCmDynamicSchema],
    ) -> CriticalServicesStatusItem:
        """Fetch and format critical services grouped by namespace in the required structure.

        Args:
            services: Dictionary of services or error string

        Returns:
            Formatted dictionary of services by namespace or error dictionary
        """
        log_id = get_log_id()
        result: CriticalServicesStatusItem = {"namespace": {}}

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
    def get_criticalservice_status_list() -> (
        CriticalServicesStatusListSchema | ErrorDict
    ):
        """
        Fetch critical services from the ConfigMap and return as a JSON response.

        Returns:
            Tuple containing JSON response dict with critical services and HTTP status code
        """
        log_id = get_log_id()  # Generate a unique log ID for logging

        app.logger.info(
            f"[{log_id}] Fetching ConfigMap: {DYNAMIC_CM} from namespace: {NAMESPACE}"
        )
        services = CriticalServiceHelper.fetch_service_list(
            CmType.DYNAMIC, NAMESPACE, CRITICAL_SERVICE_KEY
        )

        # If no critical services are found, log and return an error response
        if not services:
            app.logger.warning(
                f"[{log_id}] No 'critical_services' found in the ConfigMap"
            )
            return ErrorDict(error="'critical_services' not found in the ConfigMap")

        # Return the critical services grouped by namespace
        return {
            "critical_services": CriticalServicesStatus.fetch_critical_services_status(
                services
            )
        }

    @staticmethod
    def get_service_details(
        services: dict[str, CriticalServiceCmDynamicSchema],
        service_name: str,
        test: bool = False,
    ) -> CriticalServiceStatusDescribeSchema:
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
            filtered_pods: list[PodSchema] = []
            running_pods: Optional[int] = None
            configured_instances: Optional[int] = None

            # If not a test run, fetch real pod data
            if not test:
                # Get namespaced pods for the service using the helper
                filtered_pods = CriticalServiceHelper.get_namespaced_pods(
                    service_info, service_name
                )

                # Initialize Kubernetes client for resource management
                apps_v1 = client.AppsV1Api()

                # Dictionary mapping resource types to their corresponding methods
                resource: V1Deployment | V1StatefulSet
                if resource_type == "Deployment":
                    resource = apps_v1.read_namespaced_deployment(
                        service_name, namespace
                    )
                elif resource_type == "StatefulSet":
                    resource = apps_v1.read_namespaced_stateful_set(
                        service_name, namespace
                    )
                else:
                    # Verify that the above conditional covers all valid resource types
                    assert_never(resource_type)

                # Retrieve configured instances (number of replicas or desired instances)
                configured_instances = (
                    resource.spec.replicas if resource.spec is not None else None
                )
                running_pods = (
                    resource.status.ready_replicas
                    if resource.status is not None
                    else None
                )

            # Log the success of retrieving service details
            app.logger.info(
                f"[{log_id}] Service '{service_name}' details retrieved successfully."
            )

            # Return a structured dictionary containing the service details
            return {
                "critical_service": {
                    "name": service_name,
                    "namespace": namespace,
                    "type": resource_type,
                    "status": status,
                    "balanced": balance,
                    "configured_instances": configured_instances,
                    "currently_running_instances": running_pods,
                    "pods": filtered_pods,
                }
            }

        # Handling specific Kubernetes API exceptions
        except client.exceptions.ApiException as api_exc:
            app.logger.error(
                f"[{log_id}] API exception occurred while retrieving service '{service_name}': "
                f"{str(api_exc)}"
            )
            raise

        # Catch-all for unexpected errors
        except Exception as e:
            app.logger.error(
                f"[{log_id}] Unexpected error occurred while processing service '{service_name}': {str(e)}"
            )
            raise

    @staticmethod
    def describe_service_status(
        service_name: str,
    ) -> CriticalServiceStatusDescribeSchema | ErrorDict:
        """
        Retrieve service details and return as a JSON response.

        Args:
            service_name: Name of the critical service.

        Returns:
            JSON response with service details or error message.
        """
        log_id = get_log_id()  # Generate a unique log ID for tracking

        # Log the attempt to fetch service details
        app.logger.info(f"[{log_id}] Fetching details for service '{service_name}'.")
        services = CriticalServiceHelper.fetch_service_list(
            CmType.DYNAMIC, NAMESPACE, CRITICAL_SERVICE_KEY
        )

        # Check if the service exists in the services dictionary
        if service_name not in services:
            app.logger.warning(
                f"[{log_id}] Service '{service_name}' not found in the ConfigMap."
            )
            return ErrorDict(error="Service not found")

        data = CriticalServicesStatus.get_service_details(services, service_name)

        return data

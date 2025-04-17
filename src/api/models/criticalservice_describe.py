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
Model to retrieve the details of desired criticalservice in following json format.
{
  "Critical Service": {
    "Name": "xyz-service",
    "Namespace": "abc-ns",
    "Type": "Deployment/StatefulSet/DaemonSet",
    "Configured Instances": <num>,
    "Currently Running Instances": <num>
  }
}
"""

import json
from typing import Dict, Any, Union, Tuple
from flask import current_app as app
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.error_print import pretty_print_error
from src.lib.rrs_logging import get_log_id
from src.api.models.criticalservice_status_list import CM_KEY, CM_NAME, CM_NAMESPACE
from src.api.models.criticalservice_status_describe import (
    CriticalServiceStatusDescriber,
)


class CriticalServiceDescriber:
    """Class to handle critical service description and retrieval of details."""

    @staticmethod
    def describe_service(
        service_name: str,
    ) -> Union[Dict[str, Any], Tuple[Dict[str, str], int]]:
        """
        Retrieve service details and return as a JSON response.

        Args:
            service_name (str): The name of the critical service to describe.

        Returns:
            JSON response with service details or error message with status code.
        """
        log_id = get_log_id()  # Generate a unique log ID to track this request
        try:
            # Log the start of the process to retrieve service details
            app.logger.info(
                f"[{log_id}] Attempting to retrieve details for service: {service_name}"
            )

            # Fetch the ConfigMap that contains the critical service details
            cm_data = ConfigMapHelper.get_configmap(CM_NAMESPACE, CM_NAME)
            config_data = {}
            if CM_KEY in cm_data:
                # Parse the data from the ConfigMap (if available)
                config_data = json.loads(cm_data[CM_KEY])

            # Extract the list of critical services from the ConfigMap
            services = config_data.get("critical-services", {})

            # Use another helper to get the details of the service
            result = CriticalServiceStatusDescriber.get_service_details(
                services, service_name
            )

            if "error" in result:
                app.logger.warning(
                    f"[{log_id}] Service '{service_name}' not found in ConfigMap."
                )
                return {"error": "Service not found"}, 404

            # Clean up the result by removing unnecessary internal fields
            del result["Critical Service"]["Pods"]
            del result["Critical Service"]["Balanced"]
            del result["Critical Service"]["Status"]

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
                f"{pretty_print_error(error_message)}"
            )
            # Return an error response with status code 500
            return {"error": str(pretty_print_error(error_message))}, 500

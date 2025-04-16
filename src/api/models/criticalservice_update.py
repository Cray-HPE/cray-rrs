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
Model handles updates to critical services in the ConfigMap.
"""

import json
from typing import Dict, Any, Tuple, Union
from datetime import datetime
from flask import current_app as app
from kubernetes import client  # type: ignore
from src.api.models.criticalservice_list import CM_KEY, CM_NAME, CM_NAMESPACE
from src.lib.rrs_logging import get_log_id
from src.lib.lib_configmap import ConfigMapHelper


class CriticalServiceUpdater:
    """Class to handle updates to critical services in the ConfigMap."""

    @staticmethod
    def update_configmap(
        new_data: str, existing_data: Dict[str, Any], test: bool = False
    ) -> Dict[str, Any]:
        """
        Update the ConfigMap with new critical services.

        Args:
            new_data: JSON string containing new critical services
            existing_data: Dictionary containing existing critical services
            test: Whether this is a test run (don't update ConfigMap if True)

        Returns:
            Dict containing update status and details
        """
        log_id = get_log_id()  # Generate a unique log ID for this operation
        try:
            # Check if there's an error in the new data
            if "error" in new_data:
                app.logger.error(f"[{log_id}] Error in new data: {new_data}")
                return new_data  # type: ignore
            # Check if there's an error in the existing data
            if "error" in existing_data:
                app.logger.error(f"[{log_id}] Error in existing data: {existing_data}")
                return existing_data

            # Extract existing critical services and the new critical services
            existing_services = existing_data.get("critical-services", {})
            new_services = json.loads(new_data)["critical-services"]

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

        # Handle different types of exceptions and log the errors accordingly
        except json.JSONDecodeError as json_err:
            app.logger.error(f"[{log_id}] Invalid JSON format: {(json_err)}")
            return {"error": f"Invalid JSON format: {(json_err)}"}
        except client.exceptions.ApiException as api_exc:
            app.logger.error(f"[{log_id}] Failed to update ConfigMap: {(api_exc)}")
            return {"error": f"Failed to update ConfigMap: {(api_exc)}"}
        except KeyError as key_exc:
            app.logger.error(f"[{log_id}] Missing key: {(key_exc)}")
            return {"error": f"Missing key: {(key_exc)}"}
        except (TypeError, ValueError, AttributeError) as parse_exc:
            app.logger.error(f"[{log_id}] Parsing error: {(parse_exc)}")
            return {"error": f"Parsing error: {(parse_exc)}"}
        except Exception as e:
            app.logger.error(f"[{log_id}] Unexpected error: {(e)}")
            return {"error": f"Unexpected error: {(e)}"}

    @staticmethod
    def update_critical_services(
        new_data: Dict[str, str],
    ) -> Union[Dict[str, Any], Tuple[Dict[str, str], int]]:
        """
        Function to update critical services in the ConfigMap.

        Args:
            new_data: Dictionary containing the new services data with 'from_file' key

        Returns:
            Either a dictionary with update results or a tuple with error dict and status code
        """
        log_id = get_log_id()  # Generate a unique log ID for this operation
        try:
            # Validate if 'from_file' key is present in the request data
            if not new_data or "from_file" not in new_data:
                app.logger.error(
                    f"[{log_id}] Invalid request format: Missing 'from_file' key"
                )
                return ({"error": "Invalid request format"}), 400

            # Try parsing the JSON string from the 'from_file' key
            try:
                new_services = json.loads(new_data["from_file"])
            except json.JSONDecodeError as json_err:
                app.logger.error(
                    f"[{log_id}] Invalid JSON format in request: {json_err}"
                )
                return ({"error": "Invalid JSON format in services"}), 400

            # Check if 'critical-services' key is present in the parsed data
            if "critical-services" not in new_services:
                app.logger.error(f"[{log_id}] Missing 'critical-services' in payload")
                return ({"error": "Missing 'critical-services' in payload"}), 400

            # Fetch the current ConfigMap data
            cm_data = ConfigMapHelper.get_configmap(CM_NAMESPACE, CM_NAME)
            config_data = {}
            if CM_KEY in cm_data:
                config_data = json.loads(cm_data[CM_KEY])
            existing_data = config_data  # Existing critical services data

            # Call the update_configmap function to update the critical services
            result = CriticalServiceUpdater.update_configmap(
                json.dumps(new_services), existing_data
            )
            return result

        # Handle any exceptions and return error responses
        except Exception as e:
            app.logger.error(
                f"[{log_id}] Unhandled error in update_critical_services: {e}"
            )
            return ({"error": f"Unexpected error: {(e)}"}), 500

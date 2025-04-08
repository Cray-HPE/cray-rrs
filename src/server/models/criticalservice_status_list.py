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

from flask import current_app as app
from src.server.resources.critical_services import CriticalServiceHelper
from src.server.resources.rrs_logging import get_log_id

CM_NAME = "rrs-mon-dynamic"
CM_NAMESPACE = "rack-resiliency"
CM_KEY = "critical-service-config.json"

class CriticalServiceStatusLister:
    """Class to fetch and format critical services from the ConfigMap."""

    @staticmethod
    def get_critical_services_status(services):
        """Fetch and format critical services grouped by namespace in the required structure."""
        log_id = get_log_id()  # Generate a unique log ID
        if isinstance(services, str) and "error" in services:
            app.logger.warning(f"[{log_id}] Could not fetch critical services.")
            return {("No Services Found",)}  # Fixed the unhashable set error
        try:
            result = {"namespace": {}}
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

        except Exception as e:
            app.logger.error(
                f"[{log_id}] Error while formatting critical services: {(e)}"
            )
            return {"error": str((e))}

    @staticmethod
    def get_criticalservice_status_list():
        """
        Fetch critical services from the ConfigMap and return as a JSON response.

        Returns:
            Flask Response: JSON response containing critical services or an error message.
        """
        log_id = get_log_id()  # Generate a unique log ID
        try:
            app.logger.info(
                f"[{log_id}] Fetching ConfigMap: {CM_NAME} from namespace: {CM_NAMESPACE}"
            )
            config_data = CriticalServiceHelper.get_configmap(CM_NAME, CM_NAMESPACE, CM_KEY)

            if not config_data:
                app.logger.warning(
                    f"[{log_id}] ConfigMap {CM_NAME} is empty or missing in {CM_NAMESPACE}"
                )
                return ({"error": "ConfigMap not found or empty"}), 404

            services = config_data.get("critical-services", {})
            if not services:
                app.logger.warning(
                    f"[{log_id}] No 'critical-services' found in the ConfigMap"
                )
                return ({"error": "'critical-services' not found in the ConfigMap"}), 404

            return {"critical-services": CriticalServiceStatusLister.get_critical_services_status(services)}

        except (KeyError, TypeError, ValueError) as exc:
            app.logger.error(
                f"[{log_id}] Error while processing the ConfigMap: {(exc)}"
            )
            return ({"error": str((exc))}), 500

        except Exception as e:
            app.logger.error(
                f"[{log_id}] Unexpected error while fetching critical services: {(e)}"
            )
            return ({"error": str((e))}), 500

# MIT License
#
# (C) Copyright 2025 Hewlett Packard Enterprise Development LP
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
"""Resource to fetch the K8s zone data"""

from typing import Any, Dict, Union
import yaml
from flask import current_app as app
from src.lib.rrs_logging import get_log_id
from src.lib.lib_configmap import ConfigMapHelper
# from resources.critical_services import CriticalServiceHelper

class K8sZoneService:
    """Service class to fetch and parse Kubernetes zone data."""

    @staticmethod
    def parse_k8s_zones() -> Union[Dict[str, Any], Dict[str, str]]:
        """Extract Kubernetes zone details from the ConfigMap."""
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching Kubernetes zone details from ConfigMap")

        try:
            configmap_yaml = ConfigMapHelper.get_configmap("rack-resiliency", "rrs-mon-dynamic")

            if isinstance(configmap_yaml, dict) and "error" in configmap_yaml:
                app.logger.error(f"[{log_id}] Error fetching ConfigMap: {configmap_yaml['error']}")
                return configmap_yaml

            if not configmap_yaml:
                app.logger.warning(f"[{log_id}] ConfigMap data is empty or missing.")
                return {"error": "ConfigMap data is empty or missing."}

            if not isinstance(configmap_yaml, dict):
                app.logger.error(f"[{log_id}] Invalid ConfigMap format (not a dict)")
                return {"error": "ConfigMap data is not a valid dictionary."}

            try:
                parsed_data = yaml.safe_load(configmap_yaml["dynamic-data.yaml"])
            except yaml.YAMLError as e:
                app.logger.exception(f"[{log_id}] YAML parsing failed.")
                return {"error": f"Failed to parse ConfigMap YAML: {str(e)}"}

            if not isinstance(parsed_data, dict):
                app.logger.error(f"[{log_id}] Invalid format: Expected a dictionary.")
                return {"error": "Invalid format: Expected a dictionary."}

            k8s_zones = parsed_data.get("zone", {}).get("k8s_zones_with_nodes", {})

            if not isinstance(k8s_zones, dict):
                k8s_zones = {}

            zone_mapping: Dict[str, Dict[str, Any]] = {}

            for zone_name, nodes in k8s_zones.items():
                zone_mapping[zone_name] = {"masters": [], "workers": []}

                if not isinstance(nodes, list):
                    continue

                for node in nodes:
                    if not isinstance(node, dict):
                        continue

                    node_name = node.get("name", "")
                    node_status = node.get("Status", "Unknown")

                    node_info = {"name": node_name, "status": node_status}

                    if node_name.startswith("ncn-m"):
                        zone_mapping[zone_name]["masters"].append(node_info)
                    elif node_name.startswith("ncn-w"):
                        zone_mapping[zone_name]["workers"].append(node_info)
                    else:
                        zone_mapping[zone_name].setdefault("unknown", []).append(node_info)

            if zone_mapping:
                app.logger.info(f"[{log_id}] Successfully parsed Kubernetes zone details")
                return zone_mapping

            app.logger.warning(f"[{log_id}] No Kubernetes zones present")
            return {"error": "No Kubernetes zones present"}

        except Exception as e:
            app.logger.exception(f"[{log_id}] Unexpected error while parsing Kubernetes zones.")
            return {"error": f"Unexpected error occurred: {str(e)}"}

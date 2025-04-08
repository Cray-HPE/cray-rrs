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
"""Resource to fetch the K8s zone data"""

import yaml
from flask import current_app as app
from kubernetes import client, config
from src.server.resources.rrs_logging import get_log_id


class K8sZoneService:
    """Service class to fetch and parse Kubernetes zone data."""

    @staticmethod
    def load_k8s_config():
        """Load Kubernetes configuration for API access."""
        try:
            config.load_incluster_config()
        except Exception:
            config.load_kube_config()

    @staticmethod
    def get_configmap_data(namespace="rack-resiliency", configmap_name="rrs-mon-dynamic"):
        """Fetch the specified ConfigMap data."""
        log_id = get_log_id()
        try:
            app.logger.info(
                f"[{log_id}] Fetching ConfigMap {configmap_name} from namespace {namespace}"
            )
            K8sZoneService.load_k8s_config()
            v1 = client.CoreV1Api()
            configmap = v1.read_namespaced_config_map(
                name=configmap_name, namespace=namespace
            )
            return configmap.data.get("dynamic-data.yaml", None)
        except client.exceptions.ApiException as e:
            app.logger.error(f"[{log_id}] API error fetching ConfigMap: {str(e)}")
            return {"error": f"API error: {str(e)}"}
        except Exception as e:
            app.logger.exception(
                f"[{log_id}] Unexpected error fetching ConfigMap: {str(e)}"
            )
            return {"error": f"Unexpected error: {str(e)}"}

    @staticmethod
    def parse_k8s_zones():
        """Extract Kubernetes zone details from the ConfigMap."""
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching Kubernetes zone details from ConfigMap")
        configmap_yaml = K8sZoneService.get_configmap_data()

        if isinstance(configmap_yaml, dict) and "error" in configmap_yaml:
            app.logger.error(
                f"[{log_id}] Error fetching ConfigMap: {configmap_yaml['error']}"
            )
            return configmap_yaml

        if not configmap_yaml:
            app.logger.warning(f"[{log_id}] ConfigMap data is empty or missing.")
            return {"error": "ConfigMap data is empty or missing."}

        try:
            parsed_data = yaml.safe_load(configmap_yaml)
            k8s_zones = parsed_data.get("zone", {}).get("k8s_zones_with_nodes", {})

            zone_mapping = {}

            for zone_name, nodes in k8s_zones.items():
                zone_mapping[zone_name] = {"masters": [], "workers": []}

                for node in nodes:
                    node_name = node.get("name")
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
            return "No Kubernetes zones present"

        except yaml.YAMLError as e:
            app.logger.error(f"[{log_id}] YAML parsing error: {str(e)}")
            return {"error": f"YAML parsing error: {str(e)}"}
        except Exception as e:
            app.logger.exception(f"[{log_id}] Unexpected error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

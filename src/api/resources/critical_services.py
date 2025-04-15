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
"""
critical_services.py

This module provides helper functions for interacting with Kubernetes resources
related to critical services. It includes utilities to fetch pod information,
resolve ownership relationships, and retrieve configuration from ConfigMaps.
These functions are essential for zone-aware monitoring and management of
critical workloads in the Kubernetes cluster.

Classes:
    - CriticalServiceHelper: Static methods to retrieve pods and ConfigMap data.

Dependencies:
    - Kubernetes Python client
    - Flask (for logging via current_app)
"""

from typing import Dict, Any, Tuple, List
from flask import current_app as app
from kubernetes import client  # type: ignore
from src.api.resources.k8s_zones import K8sZoneService
from src.lib.rrs_logging import get_log_id
from src.lib.lib_configmap import ConfigMapHelper


class CriticalServiceHelper:
    """Helper class for fetching critical services and pod data"""

    @staticmethod
    def get_namespaced_pods(
        service_info: Dict[str, str], service_name: str
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch the pods in a namespace and number of instances using Kube-config"""
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching namespaced pods")

        # Load Kubernetes config (this can be done just once per method call)
        ConfigMapHelper.load_k8s_config()

        # Initialize Kubernetes client
        v1 = client.CoreV1Api()

        namespace = service_info["namespace"]
        resource_type = service_info["type"]

        # Load K8s zone data
        nodes_data = K8sZoneService.parse_k8s_zones()
        if isinstance(nodes_data, dict) and "error" in nodes_data:
            app.logger.error(
                f"[{log_id}] Error fetching nodes data: {nodes_data['error']}"
            )
            return [{"error": nodes_data["error"]}], 0

        # Build node to zone mapping - refactored to reduce nesting
        node_zone_map = {}
        if isinstance(nodes_data, dict):
            for zone, node_types in nodes_data.items():
                if not isinstance(node_types, dict):
                    continue

                for node_type in ["masters", "workers"]:
                    node_list = node_types.get(node_type, [])
                    if not isinstance(node_list, list):
                        continue

                    for node in node_list:
                        if isinstance(node, dict) and "name" in node:
                            node_zone_map[node["name"]] = zone
        else:
            app.logger.error(f"Expected dictionary, got {type(nodes_data)}")
            return [{"error": "Invalid data format"}], 0

        try:
            pod_list = v1.list_namespaced_pod(namespace)
        except client.exceptions.ApiException as e:
            app.logger.error(f"[{log_id}] API error fetching pods: {str(e)}")
            return [{"error": f"Failed to fetch pods: {str(e)}"}], 0

        running_pods = 0
        result: List[Dict[str, Any]] = []
        zone_pod_count: Dict[str, int] = {}

        for pod in pod_list.items:
            if pod.metadata.owner_references and any(
                owner.kind == CriticalServiceHelper._resolve_owner_kind(resource_type)
                and owner.name.startswith(service_name)
                for owner in pod.metadata.owner_references
            ):
                pod_status = pod.status.phase
                if pod_status == "Running":
                    running_pods += 1

                node_name = pod.spec.node_name
                zone = node_zone_map.get(node_name, "unknown")

                zone_pod_count[zone] = zone_pod_count.get(zone, 0) + 1

                result.append(
                    {
                        "Name": pod.metadata.name,
                        "Status": pod_status,
                        "Node": node_name,
                        "Zone": zone,
                    }
                )

        app.logger.info(f"[{log_id}] Total running pods: {running_pods}")
        return result, running_pods

    @staticmethod
    def _resolve_owner_kind(resource_type: str) -> str:
        """Check and return correct Kubernetes owner kind"""
        return "ReplicaSet" if resource_type == "Deployment" else resource_type

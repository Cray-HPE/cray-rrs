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
This module provides helper functions for interacting with Kubernetes resources
related to critical services. It includes utilities to fetch pod information,
resolve ownership relationships, and retrieve configuration from ConfigMaps.

Classes:
    - CriticalServiceHelper: Static methods to retrieve pods and ConfigMap data.
"""

from typing import Dict, Any, Tuple, List
import json
from flask import current_app as app
from kubernetes import client  # type: ignore
from src.api.models.zones import ZoneTopologyService
from src.lib.rrs_logging import get_log_id
from src.lib.lib_configmap import ConfigMapHelper


class CriticalServiceHelper:
    """Helper class for fetching critical services and pod data"""

    @staticmethod
    def get_namespaced_pods(
        service_info: Dict[str, str], service_name: str
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Fetch the pods in a namespace and the number of instances using Kube-config.

        Args:
            service_info (Dict[str, str]): A dictionary containing service information: name, namespace and type,
            service_name (str): The name of the service for which pods are being fetched.

        Returns:
            Tuple[List[Dict[str, Any]], int]:
                - A list of dictionaries, where each dictionary contains details about a pod.
                  Example: {"name": "pod-1", "status": "Running", "node": "node-1", "zone": "zone-1"}
                - An integer representing the total number of pod instances running.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching namespaced pods")

        # Load Kubernetes config (this can be done just once per method call)
        ConfigMapHelper.load_k8s_config()

        # Initialize Kubernetes client
        v1 = client.CoreV1Api()

        namespace = service_info["namespace"]
        resource_type = service_info["type"]

        # Load K8s zone data
        nodes_data = ZoneTopologyService.fetch_k8s_zones()
        if isinstance(nodes_data, dict) and "error" in nodes_data:
            app.logger.error(
                f"[{log_id}] Error fetching nodes data: {nodes_data['error']}"
            )
            return [{"error": nodes_data["error"]}], 0

        # Build node to zone mapping
        node_zone_map = {
            node["name"]: zone
            for zone, node_types in ZoneTopologyService.fetch_k8s_zones().items()
            for node_type in ["masters", "workers"]
            for node in node_types.get(node_type, [])
        }

        try:
            pod_list = v1.list_namespaced_pod(namespace, label_selector="rrflag")
        except client.exceptions.ApiException as e:
            app.logger.error(f"[{log_id}] API error fetching pods: {str(e)}")
            return [{"error": f"Failed to fetch pods: {str(e)}"}], 0

        running_pods = 0
        result: List[Dict[str, Any]] = []

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
    def resolve_owner_kind(resource_type: str) -> str:
        """Check and return correct Kubernetes owner kind"""
        # Deployment creates ReplicaSet, so we map that accordingly
        return "ReplicaSet" if resource_type == "Deployment" else resource_type

    @staticmethod
    def fetch_service_list(
        cm_name: str, cm_namespace: str, cm_key: str
    ) -> Dict[str, Any]:
        """
        Fetch the list of services from a ConfigMap in the specified namespace.

        Args:
            cm_name (str): The name of the ConfigMap to fetch.
            cm_namespace (str): The namespace where the ConfigMap is located.
            cm_key (str): The key within the ConfigMap that contains the service list.

        Returns:
            Dict[str, Any]: A dictionary containing the service list if successful, 
            or an error message if the operation fails.
        """
        log_id = get_log_id()  # Generate a unique log ID for tracking
        try:
            # Log the attempt to fetch service details
            app.logger.info(f"[{log_id}] Fetching all services from confgMap.")

            # Fetch the ConfigMap data containing critical service information
            cm_data = ConfigMapHelper.read_configmap(cm_namespace, cm_name)
            config_data = {}
            if cm_key in cm_data:
                config_data = json.loads(cm_data[cm_key])

            # Retrieve the critical services from the configuration
            services = config_data.get("critical-services", {})
            return services

        except Exception as e:
            app.logger.error(f"[{log_id}] Error while fetching services: {(e)}")
            return {"error": str((e))}

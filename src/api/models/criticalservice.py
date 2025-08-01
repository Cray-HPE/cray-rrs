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

import json
from typing import Literal, cast, overload
from flask import current_app as app
from kubernetes import client
from src.api.models.zones import ZoneTopologyService
from src.lib.rrs_constants import CmType, DYNAMIC_CM, STATIC_CM
from src.lib.rrs_logging import get_log_id
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.schema import (
    k8sNodeTypeTuple,
    PodSchema,
    CriticalServiceCmStaticType,
    CriticalServiceCmDynamicType,
    CriticalServiceCmDynamicSchema,
    CriticalServiceCmStaticSchema,
)


class CriticalServiceHelper:
    """Helper class for fetching critical services and pod data"""

    @staticmethod
    def get_namespaced_pods(
        service_info: CriticalServiceCmDynamicSchema, service_name: str
    ) -> list[PodSchema]:
        """
        Fetch the pods in a namespace and the number of instances using Kube-config.

        Args:
            service_info (dict[str, str]): A dictionary containing service information: name, namespace and type,
            service_name (str): The name of the service for which pods are being fetched.

        Returns:
            tuple[list[dict[str, str]], int]:
                - A list of dictionaries, where each dictionary contains details about a pod.
                  Example: {"name": "pod-1", "status": "Running", "node": "node-1", "zone": "zone-1"}
                - An integer representing the total number of pod instances running.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching namespaced pods")

        # Load Kubernetes config
        ConfigMapHelper.load_k8s_config()

        # Initialize Kubernetes client
        v1 = client.CoreV1Api()

        namespace = service_info["namespace"]
        resource_type = service_info["type"]

        # Load K8s zone data
        nodes_data = ZoneTopologyService.fetch_k8s_zones()

        # Build node to zone mapping
        node_zone_map = {}

        for zone, node_types in nodes_data.items():
            for node_type in k8sNodeTypeTuple:
                if node_type not in node_types:
                    continue
                node_list = node_types[node_type]
                if not isinstance(node_list, list):
                    continue

                valid_nodes = {node["name"]: zone for node in node_list}
                node_zone_map.update(valid_nodes)

        try:
            pod_list = v1.list_namespaced_pod(namespace, label_selector="rrflag")
        except client.exceptions.ApiException as e:
            app.logger.error(f"[{log_id}] API error fetching pods: {str(e)}")
            raise

        result: list[PodSchema] = []
        expected_owner_kind = CriticalServiceHelper.resolve_owner_kind(resource_type)

        for pod in pod_list.items:
            # Use early continue to reduce nesting
            if not pod.metadata or not pod.metadata.owner_references:
                continue

            # Check if any owner reference matches our criteria
            is_matching = any(
                owner.kind == expected_owner_kind
                and service_name in (owner.name, owner.name.rsplit("-", 1)[0])
                for owner in pod.metadata.owner_references
            )

            if not is_matching:
                continue

            if not pod.status:
                continue

            is_terminating = pod.metadata.deletion_timestamp is not None
            pod_stat = pod.status.phase if not is_terminating else "Terminating"
            pod_status: Literal["Running", "Pending", "Failed", "Terminating"]
            if pod_stat == "Running":
                pod_status = "Running"
            elif pod_stat == "Terminating":
                pod_status = "Terminating"
            else:
                pod_status = "Pending"

            if not pod.spec:
                continue
            node_name = pod.spec.node_name
            if node_name is None:
                continue
            zone = node_zone_map.get(node_name, "unknown")

            if not pod.metadata.name:
                continue

            result.append(
                {
                    "name": pod.metadata.name,
                    "status": pod_status if pod_status else "Unknown",
                    "node": node_name,
                    "zone": zone,
                }
            )
        return result

    @staticmethod
    def resolve_owner_kind(resource_type: str) -> str:
        """Check and return correct Kubernetes owner kind"""
        # Deployment creates ReplicaSet, so we map that accordingly
        return "ReplicaSet" if resource_type == "Deployment" else resource_type

    @overload
    @staticmethod
    def fetch_service_list(
        cm_type: Literal[CmType.STATIC], cm_namespace: str, cm_key: str
    ) -> dict[str, CriticalServiceCmStaticSchema]: ...

    @overload
    @staticmethod
    def fetch_service_list(
        cm_type: Literal[CmType.DYNAMIC], cm_namespace: str, cm_key: str
    ) -> dict[str, CriticalServiceCmDynamicSchema]: ...

    @staticmethod
    def fetch_service_list(
        cm_type: Literal[CmType.STATIC, CmType.DYNAMIC], cm_namespace: str, cm_key: str
    ) -> (
        dict[str, CriticalServiceCmDynamicSchema]
        | dict[str, CriticalServiceCmStaticSchema]
    ):
        """
        Fetch the list of services from a ConfigMap in the specified namespace.

        Args:
            cm_name (str): The name of the ConfigMap to fetch.
            cm_namespace (str): The namespace where the ConfigMap is located.
            cm_key (str): The key within the ConfigMap that contains the service list.

        Returns:
            CriticalServiceCmDynamicType | CriticalServiceCmStaticType: A dictionary
            containing the service list if successful,
            or an error message if the operation fails.
        """
        log_id = get_log_id()  # Generate a unique log ID for tracking
        cm_name = STATIC_CM if cm_type == CmType.STATIC else DYNAMIC_CM
        try:
            # Log the attempt to fetch service details
            app.logger.info(f"[{log_id}] Fetching all services from configMap.")

            # Fetch the ConfigMap data containing critical service information
            cm_data = ConfigMapHelper.read_configmap(cm_namespace, cm_name)
            if isinstance(cm_data, str):
                # This means it contains an error message
                raise ValueError(cm_data)

            if cm_key in cm_data:
                config_data: (
                    CriticalServiceCmStaticType | CriticalServiceCmDynamicType
                ) = json.loads(cm_data[cm_key])

                # Retrieve the critical services from the configuration
                if "critical_services" in config_data:
                    return config_data["critical_services"]

            return cast(
                dict[str, CriticalServiceCmDynamicSchema]
                | dict[str, CriticalServiceCmStaticSchema],
                {},
            )

        except KeyError:
            app.logger.error(f"Key '{cm_key}' not found in cm_data.")
            raise
        except TypeError:
            app.logger.error(
                "cm_data is not a dict or the value is not a valid string/bytes."
            )
            raise
        except json.JSONDecodeError as e:
            app.logger.error(f"Invalid JSON: {e}")
            raise
        except Exception as e:
            app.logger.error(f"[{log_id}] Error while fetching services: {(e)}")
            raise

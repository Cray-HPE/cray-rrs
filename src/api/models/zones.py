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
Provides a model to fetch zone topology details from both Ceph and Kubernetes.
The data is retrieved from a ConfigMap and returned as structured dictionaries.
"""

from typing import Dict, List, Union, TypedDict, Any
import yaml, os
from flask import current_app as app
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.rrs_logging import get_log_id

CM_NAMESPACE = os.getenv("namespace")
CM_KEY = os.getenv("key_zones")
CM_NAME = os.getenv("dynamic_cm_name")


class OsdInfo(TypedDict):
    """TypedDict representing a Ceph OSD (Object Storage Daemon)."""

    name: str
    status: str


class NodeInfo(TypedDict):
    """TypedDict representing a node containing OSDs."""

    name: str
    status: str
    osds: List[OsdInfo]


ZoneMapping = Dict[str, List[NodeInfo]]
ErrorDict = Dict[str, str]
ResultType = Union[ZoneMapping, ErrorDict]


class ZoneTopologyService:
    """
    Service class to fetch zone details from Kubernetes and Ceph.

    Methods:
    fetch_ceph_zones() -> ResultType
        Fetches and parses Ceph zone data from the ConfigMap.

    fetch_k8s_zones() -> Dict[str, Dict[str, Any]]
        Fetches and parses Kubernetes zone data from the ConfigMap.
    """

    @staticmethod
    def fetch_ceph_zones() -> ResultType:
        """
        Extracts Ceph zone details from the ConfigMap.

        Returns:
            ResultType
                A dictionary mapping zone names to a list of node info including OSDs,
                or an error dictionary in case of failure.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching Ceph zone details from ConfigMap.")

        try:
            configmap_yaml = ConfigMapHelper.read_configmap(CM_NAMESPACE, CM_NAME)
            parsed_data = yaml.safe_load(configmap_yaml[CM_KEY])
            ceph_zones_with_nodes = parsed_data["zone"]["ceph_zones_with_nodes"]

            zone_mapping: ZoneMapping = {
                zone_name: [
                    NodeInfo(
                        name=node["name"],
                        status=node["status"],
                        osds=[
                            OsdInfo(name=osd["name"], status=osd["status"])
                            for osd in node["osds"]
                        ],
                    )
                    for node in nodes
                ]
                for zone_name, nodes in ceph_zones_with_nodes.items()
            }

            if zone_mapping:
                app.logger.info(f"[{log_id}] Successfully parsed Ceph zones.")
                return zone_mapping

            app.logger.warning(f"[{log_id}] No Ceph zones found.")
            return {"error": "No Ceph zones present"}

        except Exception as e:
            app.logger.exception(
                f"[{log_id}] Unexpected error while parsing Ceph zones."
            )
            return {"error": f"Unexpected error occurred: {str(e)}"}

    @staticmethod
    def fetch_k8s_zones() -> Dict[str, Dict[str, Any]]:
        """
        Extracts Kubernetes zone details from the ConfigMap.

        Returns:
            Dict[str, Dict[str, Any]]
                A dictionary mapping zone names to master and worker node lists,
                or an error dictionary in case of failure.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching Kubernetes zone details from ConfigMap")

        try:
            configmap_yaml = ConfigMapHelper.read_configmap(CM_NAMESPACE, CM_NAME)
            parsed_data = yaml.safe_load(configmap_yaml[CM_KEY])
            k8s_zones = parsed_data["zone"]["k8s_zones_with_nodes"]

            zone_mapping: Dict[str, Dict[str, Any]] = {}

            for zone_name, nodes in k8s_zones.items():
                zone_mapping[zone_name] = {"masters": [], "workers": []}
                for node in nodes:
                    node_name = node["name"]
                    node_status = node["Status"]
                    node_info = {"name": node_name, "status": node_status}

                    if node_name.startswith("ncn-m"):
                        zone_mapping[zone_name]["masters"].append(node_info)
                    else:
                        zone_mapping[zone_name]["workers"].append(node_info)

            if zone_mapping:
                app.logger.info(
                    f"[{log_id}] Successfully parsed Kubernetes zone details."
                )
                return zone_mapping

            app.logger.warning(f"[{log_id}] No Kubernetes zones present.")
            return {"error": "No Kubernetes zones present"}

        except Exception as e:
            app.logger.exception(f"[{log_id}] Failed to parse Kubernetes zone details")
            return {"error": f"Unexpected error occurred: {str(e)}"}

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

from typing import Dict, List, Union, TypedDict
import os
import yaml
from flask import current_app as app
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.rrs_logging import get_log_id
from src.lib.rrs_constants import DYNAMIC_DATA_KEY

CM_NAMESPACE: str = os.getenv("namespace", "")
CM_NAME: str = os.getenv("dynamic_cm_name", "")


class OsdInfo(TypedDict):
    """TypedDict representing a Ceph OSD (Object Storage Daemon)."""

    name: str
    status: str


class CephNodeInfo(TypedDict):
    """TypedDict representing a node containing OSDs."""

    name: str
    status: str
    osds: List[OsdInfo]


k8sNodeType = Dict[str, Dict[str, List[Dict[str, str]]]]
ZoneMapping = Dict[str, List[CephNodeInfo]]
ErrorDict = Dict[str, str]
k8sResultType = Union[k8sNodeType, Exception]
CephResultType = Union[ZoneMapping, Exception]


class ZoneTopologyService:
    """
    Service class to fetch zone details from Kubernetes and Ceph.

    Methods:
    fetch_ceph_zones() -> CephResultType
        Fetches and parses Ceph zone data from the ConfigMap.

    fetch_k8s_zones() -> k8sResultType
        Fetches and parses Kubernetes zone data from the ConfigMap.
    """

    @staticmethod
    def fetch_ceph_zones() -> CephResultType:
        """
        Extracts Ceph zone details from the ConfigMap.

        Returns:
            CephResultType
                A dictionary mapping zone names to a list of node info including OSDs,
                or an error dictionary in case of failure.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching Ceph zone details from ConfigMap.")

        try:
            configmap_yaml = ConfigMapHelper.read_configmap(CM_NAMESPACE, CM_NAME)
            parsed_data = yaml.safe_load(configmap_yaml[DYNAMIC_DATA_KEY])
            ceph_zones = parsed_data["zone"]["ceph_zones"]

            zone_mapping: ZoneMapping = {
                zone_name: [
                    CephNodeInfo(
                        name=node["name"],
                        status=node["status"],
                        osds=[
                            OsdInfo(name=osd["name"], status=osd["status"])
                            for osd in node["osds"]
                        ],
                    )
                    for node in nodes
                ]
                for zone_name, nodes in ceph_zones.items()
            }

            if zone_mapping:
                app.logger.info(f"[{log_id}] Successfully parsed Ceph zones.")
                return zone_mapping

            app.logger.warning(f"[{log_id}] No Ceph zones found.")
            return {}

        except Exception as e:
            app.logger.exception(
                f"[{log_id}] Unexpected error while parsing Ceph zones."
            )
            return e

    @staticmethod
    def fetch_k8s_zones() -> k8sResultType:
        """
        Extracts Kubernetes zone details from the ConfigMap.

        Returns:
            k8sResultType
                A dictionary mapping zone names to master and worker node lists,
                or an error dictionary in case of failure.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching Kubernetes zone details from ConfigMap")

        try:
            configmap_yaml = ConfigMapHelper.read_configmap(CM_NAMESPACE, CM_NAME)
            parsed_data = yaml.safe_load(configmap_yaml[DYNAMIC_DATA_KEY])
            k8s_zones = parsed_data["zone"]["k8s_zones"]

            zone_mapping: Dict[str, Dict[str, List[Dict[str, str]]]] = {}

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
            # Return empty dict of type k8sResultType
            app.logger.warning(f"[{log_id}] No Kubernetes zones present.")
            return {}

        except Exception as e:
            app.logger.exception(f"[{log_id}] Failed to parse Kubernetes zone details")
            return e

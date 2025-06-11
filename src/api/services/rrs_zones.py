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
This module provides the ZoneService class responsible for fetching, validating,
and mapping zone information from both Kubernetes and Ceph for RRS CLI.

Key functionalities:
- Detect existence and completeness of K8s and Ceph zone configurations.
- Map Kubernetes and Ceph zones into a structure.
- Provide detailed zone descriptions including node names, status, and OSD mapping.
"""

from typing import Optional
from flask import current_app as app
from src.api.models.zones import (
    ZoneTopologyService,
    CephResultType,
    k8sResultType,
)
from src.api.models.schema import (
    ZoneListSchema,
    ZoneItemSchema,
    KubernetesTopologyZoneSchema,
    ZoneDescribeSchema,
    StorageNodeSchema,
    NodeSchema,
    CephNodeInfo,
    ErrorDict,
    InformationDict,
)
from src.lib.rrs_logging import get_log_id


class ZoneService:
    """Service class responsible for fetching, validating, and mapping Kubernetes and Ceph zones."""

    @staticmethod
    def zone_exist(
        k8s_zones: k8sResultType, ceph_zones: CephResultType
    ) -> Optional[InformationDict]:
        """
        Checks whether Kubernetes and/or Ceph zones are configured.

        Args:
            k8s_zones (dict or str): Kubernetes zones data or an error string.
            ceph_zones (dict or str): Ceph zones data or an error string.

        Returns:
            dict or None: Returns a dictionary with zone info or error messages if no zones exist.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Checking if zones (K8s Topology or Ceph) exist")

        if not k8s_zones and not ceph_zones:
            app.logger.warning(
                f"[{log_id}] No zones (K8s topology and Ceph) configured"
            )
            return InformationDict(
                Information="No zones (K8s topology and Ceph) configured"
            )

        if not k8s_zones:
            app.logger.warning(f"[{log_id}] No K8s topology zones configured")
            return InformationDict(Information="No K8s topology zones configured")

        if not ceph_zones:
            app.logger.warning(f"[{log_id}] No CEPH zones configured")
            return InformationDict(Information="No CEPH zones configured")

        app.logger.info(f"[{log_id}] Zones found")
        return None

    @staticmethod
    def get_node_names(
        node_list: list[NodeSchema] | list[CephNodeInfo],
    ) -> list[str]:
        """
        Extracts node names from a list of node dictionaries.

        Args:
            node_list (list): list of node dictionaries containing 'name' keys.

        Returns:
            list: A list of node names.
        """
        return [node["name"] for node in node_list]

    @staticmethod
    def map_zones(
        k8s_zones: k8sResultType, ceph_zones: CephResultType
    ) -> ZoneListSchema:
        """
        Maps the Kubernetes and Ceph zones into a structured response.

        Args:
            k8s_zones (dict): Kubernetes zones data.
            ceph_zones (dict): Ceph zones data.

        Returns:
            dict: A structured dictionary representing the zone mapping.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Mapping Kubernetes and Ceph zones")

        zones_list: list[ZoneItemSchema] = []
        all_zone_names = set(k8s_zones.keys()) | set(ceph_zones.keys())
        app.logger.info(f"[{log_id}] All zone names: {all_zone_names}")

        for zone_name in all_zone_names:
            app.logger.info(f"[{log_id}] Processing zone: {zone_name}")
            k8s_zone_data = k8s_zones.get(zone_name, {})
            ceph_zone_data: list[CephNodeInfo] = ceph_zones.get(zone_name, [])

            masters = ZoneService.get_node_names(k8s_zone_data.get("masters", []))
            workers = ZoneService.get_node_names(k8s_zone_data.get("workers", []))
            storage = ZoneService.get_node_names(ceph_zone_data)

            zone_data: ZoneItemSchema = {"Zone_Name": zone_name}

            if masters or workers:
                k8s_topology: KubernetesTopologyZoneSchema = {}
                if masters:
                    k8s_topology["Management_Master_Nodes"] = masters
                if workers:
                    k8s_topology["Management_Worker_Nodes"] = workers
                zone_data["Kubernetes_Topology_Zone"] = k8s_topology

            if storage:
                zone_data["CEPH_Zone"] = {"Management_Storage_Nodes": storage}

            zones_list.append(zone_data)

        app.logger.info(f"[{log_id}] Mapped {len(zones_list)} zones")
        return {"Zones": zones_list}

    @staticmethod
    def get_zone_info(
        zone_name: str,
        k8s_zones: k8sResultType,
        ceph_zones: CephResultType,
    ) -> ZoneDescribeSchema | ErrorDict:
        """
        Retrieves detailed information for a specific zone.

        Args:
            zone_name (str): Name of the zone to describe.
            k8s_zones (dict): Dictionary of Kubernetes zones.
            ceph_zones (dict): Dictionary of Ceph zones.

        Returns:
            dict: A dictionary containing zone details or an error if not found.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching information for zone: {zone_name}")

        masters = k8s_zones.get(zone_name, {}).get("masters", [])
        workers = k8s_zones.get(zone_name, {}).get("workers", [])
        storage = ceph_zones.get(zone_name, [])

        if not (masters or workers or storage):
            app.logger.warning(f"[{log_id}] Zone '{zone_name}' not found")
            return ErrorDict(error="Zone not found")

        zone_data: ZoneDescribeSchema = {
            "Zone_Name": zone_name,
            "Management_Masters": len(masters),
            "Management_Workers": len(workers),
            "Management_Storages": len(storage),
        }

        if masters:
            zone_data["Management_Master"] = {
                "Type": "Kubernetes_Topology_Zone",
                "Nodes": [
                    {"name": node["name"], "status": node["status"]} for node in masters
                ],
            }

        if workers:
            zone_data["Management_Worker"] = {
                "Type": "Kubernetes_Topology_Zone",
                "Nodes": [
                    {"name": node["name"], "status": node["status"]} for node in workers
                ],
            }

        if storage:
            storage_nodes: list[StorageNodeSchema] = []
            for node in storage:
                osd_status_map: dict[str, list[str]] = {}
                for osd in node.get("osds", []):
                    osd_status_map.setdefault(osd["status"], []).append(osd["name"])

                storage_node: StorageNodeSchema = {
                    "name": node["name"],
                    "status": node["status"],
                    "osds": osd_status_map,
                }
                storage_nodes.append(storage_node)

            zone_data["Management_Storage"] = {
                "Type": "CEPH_Zone",
                "Nodes": storage_nodes,
            }

        app.logger.info(
            f"[{log_id}] Zone information fetched successfully for zone: {zone_name}"
        )
        return zone_data

    @staticmethod
    def fetch_zones() -> tuple[k8sResultType, CephResultType]:
        """
        Fetches zone information from the Kubernetes and Ceph zone providers.

        Returns:
            tuple: A tuple containing Kubernetes zones and Ceph zones.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching zones data")

        k8s_zones = ZoneTopologyService.fetch_k8s_zones()
        ceph_zones = ZoneTopologyService.fetch_ceph_zones()

        return k8s_zones, ceph_zones

    @staticmethod
    def list_zones() -> ZoneListSchema | InformationDict:
        """
        Returns a list of all zones with mapping between Kubernetes and Ceph.

        Returns:
            dict: A structured response containing zone mapping.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching zones data")
        k8s_zones, ceph_zones = ZoneService.fetch_zones()

        zone_check_result = ZoneService.zone_exist(k8s_zones, ceph_zones)
        if zone_check_result:
            app.logger.warning(f"[{log_id}] {zone_check_result.get('Information', '')}")
            return zone_check_result
        result = ZoneService.map_zones(k8s_zones, ceph_zones)
        app.logger.info(f"[{log_id}] Zones data fetched successfully")
        return result

    @staticmethod
    def describe_zone(
        zone_name: str,
    ) -> ZoneDescribeSchema | ErrorDict | InformationDict:
        """
        Provides detailed information for a given zone including nodes and OSDs.

        Args:
            zone_name (str): Name of the zone to describe.

        Returns:
            dict: Detailed information about the specified zone.
        """
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching zone description for: {zone_name}")
        k8s_zones, ceph_zones = ZoneService.fetch_zones()

        zone_check_result = ZoneService.zone_exist(k8s_zones, ceph_zones)
        if zone_check_result:
            app.logger.warning(f"[{log_id}] {zone_check_result.get('Information', '')}")
            return zone_check_result

        result = ZoneService.get_zone_info(zone_name, k8s_zones, ceph_zones)
        app.logger.info(f"[{log_id}] Zone {zone_name} data fetched successfully")
        return result

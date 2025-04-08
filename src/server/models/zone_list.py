#
# MIT License
#
#  (C) Copyright [2025] Hewlett Packard Enterprise Development LP
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
"""Model to handle and process Kubernetes and Ceph zones.
Maps zone data from K8s and Ceph, and returns summarized information.
"""
from flask import current_app as app

from src.server.resources.k8s_zones import K8sZoneService
from src.server.resources.ceph_zones import CephService
from src.server.resources.rrs_logging import get_log_id


class ZoneMapper:
    """Service class to process and map Kubernetes and Ceph zones."""

    @staticmethod
    def zone_exist(k8s_zones, ceph_zones):
        """Function to check if any types of zones (K8s Topology or CEPH) exist."""
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Checking if zones (K8s Topology or Ceph) exist")

        if isinstance(k8s_zones, str) and isinstance(ceph_zones, str):
            app.logger.warning(f"[{log_id}] No zones (K8s topology and Ceph) configured")
            return {
                "Zones": [],
                "Information": "No zones (K8s topology and Ceph) configured",
            }
        if isinstance(k8s_zones, str):
            app.logger.warning(f"[{log_id}] No K8s topology zones configured")
            return {"Zones": [], "Information": "No K8s topology zones configured"}
        if isinstance(ceph_zones, str):
            app.logger.warning(f"[{log_id}] No CEPH zones configured")
            return {"Zones": [], "Information": "No CEPH zones configured"}

        app.logger.info(f"[{log_id}] Zones found")
        return None

    @staticmethod
    def get_node_names(node_list):
        """Extracts node names from a list of node dictionaries."""
        node_names = [node.get("name") for node in node_list if "name" in node]
        app.logger.info(f"Extracted node names: {node_names}")
        return node_names

    @staticmethod
    def map_zones(k8s_zones, ceph_zones):
        """Map Kubernetes and Ceph zones and provide summarized data."""
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Mapping Kubernetes and Ceph zones")

        if isinstance(k8s_zones, dict) and "error" in k8s_zones:
            app.logger.error(f"[{log_id}] Error in K8s zones: {k8s_zones['error']}")
            return {"error": k8s_zones["error"]}

        if isinstance(ceph_zones, dict) and "error" in ceph_zones:
            app.logger.error(f"[{log_id}] Error in Ceph zones: {ceph_zones['error']}")
            return {"error": ceph_zones["error"]}

        zone_check_result = ZoneMapper.zone_exist(k8s_zones, ceph_zones)
        if zone_check_result:
            app.logger.warning(f"[{log_id}] {zone_check_result['Information']}")
            return zone_check_result

        zones_list = []
        all_zone_names = set(k8s_zones.keys()) | set(ceph_zones.keys())
        app.logger.info(f"[{log_id}] All zone names: {all_zone_names}")

        for zone_name in all_zone_names:
            app.logger.info(f"[{log_id}] Processing zone: {zone_name}")

            masters = ZoneMapper.get_node_names(k8s_zones.get(zone_name, {}).get("masters", []))
            workers = ZoneMapper.get_node_names(k8s_zones.get(zone_name, {}).get("workers", []))
            storage = ZoneMapper.get_node_names(ceph_zones.get(zone_name, []))

            zone_data = {"Zone Name": zone_name}

            if masters or workers:
                zone_data["Kubernetes Topology Zone"] = {}
                if masters:
                    zone_data["Kubernetes Topology Zone"]["Management Master Nodes"] = masters
                if workers:
                    zone_data["Kubernetes Topology Zone"]["Management Worker Nodes"] = workers

            if storage:
                zone_data["CEPH Zone"] = {"Management Storage Nodes": storage}

            zones_list.append(zone_data)

        app.logger.info(f"[{log_id}] Mapped {len(zones_list)} zones")
        return {"Zones": zones_list}

    @staticmethod
    def get_zones():
        """Endpoint to get summary of all zones in the new format."""
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Fetching zones data")
        k8s_zones = K8sZoneService.parse_k8s_zones()
        ceph_zones = CephService.parse_ceph_zones()
        result = ZoneMapper.map_zones(k8s_zones, ceph_zones)
        app.logger.info(f"[{log_id}] Zones data fetched successfully")
        return result

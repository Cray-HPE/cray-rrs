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
Model to describe the requested zone
{
  "Zone Name": "rack3",
  "Management Masters": 1,
  "Management Workers": 2,
  "Management Storages": 1,
  "Management Master": {
    "Type": "Kubernetes Topology Zone",
    "Nodes": [
      {
        "Name": "master1",
        "Status": "Ready"
      }
    ]
  },
  "Management Worker": {
    "Type": "Kubernetes Topology Zone",
    "Nodes": [
      {
        "Name": "worker1",
        "Status": "Ready"
      },
      {
        "Name": "worker2",
        "Status": "NotReady"
      }
    ]
  },
  "Management Storage": {
    "Type": "CEPH Zone",
    "Nodes": [
      {
        "Name": "storage1",
        "Status": "Ready",
        "OSDs": {
          "up": [
            "osd.1",
            "osd.2",
          ]
        }
      }
    ]
  }
}
"""

from typing import Dict, List, Any, Optional, Union, TypedDict, cast

from flask import current_app as app
from src.api.resources.k8s_zones import K8sZoneService
from src.api.resources.ceph_zones import CephService
from src.api.models.zone_list import ZoneMapper
from src.lib.rrs_logging import get_log_id

# Import the NodeInfo type from ceph_zones to ensure type compatibility
from src.api.resources.ceph_zones import NodeInfo as CephNodeInfo


class NodeInfo(TypedDict, total=False):
    """Information about a Ceph storage node including its OSDs."""

    name: str
    status: str
    osds: List[Dict[str, str]]


# Define a ZoneInfoDict type for clarity
ZoneInfoDict = Dict[str, Any]


class ZoneDescriber:
    """Class to describe Kubernetes and Ceph zones."""

    @staticmethod
    def get_zone_info(
        zone_name: str,
        k8s_zones: Union[Dict[str, Dict[str, List[NodeInfo]]], str],
        ceph_zones: Union[Dict[str, List[Union[NodeInfo, CephNodeInfo]]], str],
        log_id: Optional[str] = None,
    ) -> ZoneInfoDict:
        """Internal method to get detailed information of a specific zone."""

        # If no log_id is provided, generate one
        if log_id is None:
            log_id = get_log_id()

        # Log the request for zone information
        app.logger.info(f"[{log_id}] Fetching information for zone: {zone_name}")

        # Check if the K8s or Ceph zone data is invalid
        if isinstance(k8s_zones, str) or isinstance(ceph_zones, str):
            app.logger.error(
                f"[{log_id}] Invalid zone data: K8s Zones: {k8s_zones}, Ceph Zones: {ceph_zones}"
            )
            # Ensure this returns a Dict[str, Any] as promised
            return cast(ZoneInfoDict, ZoneMapper.zone_exist(k8s_zones, ceph_zones))

        # Extract the master, worker, and storage node data for the requested zone
        masters = k8s_zones.get(zone_name, {}).get("masters", [])
        workers = k8s_zones.get(zone_name, {}).get("workers", [])
        storage = ceph_zones.get(zone_name, [])

        # If no data is found for the requested zone, return an error message
        if not (masters or workers or storage):
            app.logger.warning(f"[{log_id}] Zone '{zone_name}' not found")
            return {"error": "Zone not found"}

        # Initialize the dictionary to store zone information
        zone_data: ZoneInfoDict = {
            "Zone Name": zone_name,
            "Management Masters": len(masters),
            "Management Workers": len(workers),
            "Management Storages": len(storage),
        }

        # Add details about the master nodes (Kubernetes)
        if masters:
            zone_data["Management Master"] = {
                "Type": "Kubernetes Topology Zone",
                "Nodes": [
                    {"Name": node["name"], "Status": node["status"]} for node in masters
                ],
            }
            app.logger.info(
                f"[{log_id}] Added {len(masters)} management master nodes for zone: {zone_name}"
            )

        # Add details about the worker nodes (Kubernetes)
        if workers:
            zone_data["Management Worker"] = {
                "Type": "Kubernetes Topology Zone",
                "Nodes": [
                    {"Name": node["name"], "Status": node["status"]} for node in workers
                ],
            }
            app.logger.info(
                f"[{log_id}] Added {len(workers)} management worker nodes for zone: {zone_name}"
            )

        # Add details about the storage nodes (Ceph)
        if storage:
            zone_data["Management Storage"] = {"Type": "CEPH Zone", "Nodes": []}
            for node in storage:
                osd_status_map: Dict[str, List[str]] = {}
                # Group OSDs by their status
                for osd in node.get("osds", []):
                    osd_status_map.setdefault(osd["status"], []).append(osd["name"])

                # Structure the storage node information
                storage_node = {
                    "Name": node["name"],
                    "Status": node["status"],
                    "OSDs": osd_status_map,
                }
                zone_data["Management Storage"]["Nodes"].append(storage_node)

            app.logger.info(
                f"[{log_id}] Added {len(storage)} management storage nodes for zone: {zone_name}"
            )

        # Log the success of the zone data retrieval
        app.logger.info(
            f"[{log_id}] Zone information fetched successfully for zone: {zone_name}"
        )
        return zone_data

    @staticmethod
    def describe_zone(zone_name: str) -> ZoneInfoDict:
        """Public method to describe a specific zone."""

        # Generate a log ID for the request
        log_id = get_log_id()
        app.logger.info(f"[{log_id}] Request received to describe zone: {zone_name}")

        # Fetch the zone data for Kubernetes and Ceph
        k8s_zones = K8sZoneService.parse_k8s_zones()
        ceph_zones = CephService.parse_ceph_zones()

        # Ensure type compatibility by using the correct type or casting
        result = ZoneDescriber.get_zone_info(
            zone_name,
            cast(Union[Dict[str, Dict[str, List[NodeInfo]]], str], k8s_zones),
            cast(
                Union[Dict[str, List[Union[NodeInfo, CephNodeInfo]]], str], ceph_zones
            ),
            log_id,
        )

        # Log the successful zone description response
        app.logger.info(
            f"[{log_id}] Zone description response generated for zone: {zone_name}"
        )
        return result

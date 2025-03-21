#
# MIT License
#
# (C) Copyright [2024-2025] Hewlett Packard Enterprise Development LP
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
"""

from flask import jsonify
from resources.k8s_zones import get_k8s_nodes_data
from resources.ceph_zones import get_ceph_storage_nodes
from models.zone_list import zone_exist  # Renamed to snake_case

def get_zone_info(zone_name, k8s_zones, ceph_zones):
    """Function to get detailed information of a specific zone."""
    # Check if K8s or Ceph zones contain an error and return the error message
    if isinstance(k8s_zones, dict) and "error" in k8s_zones:
        return {"error": k8s_zones["error"]}

    if isinstance(ceph_zones, dict) and "error" in ceph_zones:
        return {"error": ceph_zones["error"]}

    # Handle cases where zone data is missing
    if isinstance(k8s_zones, str) or isinstance(ceph_zones, str):
        return zone_exist(k8s_zones, ceph_zones)

    # Fetch nodes for the given zone
    masters = k8s_zones.get(zone_name, {}).get("masters", [])
    workers = k8s_zones.get(zone_name, {}).get("workers", [])
    storage = ceph_zones.get(zone_name, [])

    # Return an error if no valid nodes are found for the zone
    if not (masters or workers or storage):
        return {"error": "Zone not found"}

    # Prepare the zone data to be returned
    zone_data = {
        "Zone Name": zone_name,
        "Management Masters": len(masters),
        "Management Workers": len(workers),
        "Management Storages": len(storage)
    }

    # Include details about management master nodes if available
    if masters:
        zone_data["Management Master"] = {
            "Type": "Kubernetes Topology Zone",
            "Nodes": [{"Name": node["name"], "Status": node["status"]} for node in masters]
        }

    # Include details about management worker nodes if available
    if workers:
        zone_data["Management Worker"] = {
            "Type": "Kubernetes Topology Zone",
            "Nodes": [{"Name": node["name"], "Status": node["status"]} for node in workers]
        }

    # Include details about management storage nodes if available
    if storage:
        zone_data["Management Storage"] = {
            "Type": "CEPH Zone",
            "Nodes": []
        }
        for node in storage:
            # Map OSD statuses for each storage node
            osd_status_map = {}
            for osd in node.get("osds", []):
                osd_status_map.setdefault(osd["status"], []).append(osd["name"])

            storage_node = {
                "Name": node["name"],
                "Status": node["status"],
                "OSDs": osd_status_map
            }
            zone_data["Management Storage"]["Nodes"].append(storage_node)

    return zone_data

def describe_zone(zone_name):
    """Endpoint to describe a specific zone."""
    # Get K8s and Ceph zones data
    k8s_zones = get_k8s_nodes_data()
    ceph_zones = get_ceph_storage_nodes()
    # Return the zone information as a JSON response
    return jsonify(get_zone_info(zone_name, k8s_zones, ceph_zones))

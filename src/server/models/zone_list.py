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
Model to handle and process Kubernetes and Ceph zones.
Maps zone data from K8s and Ceph, and returns summarized information.
"""

from flask import jsonify
from resources.k8s_zones import get_k8s_nodes_data
from resources.ceph_zones import get_ceph_storage_nodes

def zone_exist(k8s_zones, ceph_zones):
    """Function to check if any types of zones (K8s Topology or CEPH) exist."""
    if isinstance(k8s_zones, str) and isinstance(ceph_zones, str):
        return {"Zones": [], "Information": "No zones (K8s topology and Ceph) configured"}
    if isinstance(k8s_zones, str):
        return {"Zones": [], "Information": "No K8s topology zones configured"}
    if isinstance(ceph_zones, str):
        return {"Zones": [], "Information": "No CEPH zones configured"}
    return None  # No error, zones exist

def get_node_names(node_list):
    """Extracts node names from a list of node dictionaries."""
    return [node.get("name") for node in node_list if "name" in node]

def map_zones(k8s_zones, ceph_zones):
    """Map Kubernetes and Ceph zones and provide summarized data in the new format."""

    # Check for error in zone data early and handle it
    if isinstance(k8s_zones, dict) and "error" in k8s_zones:
        return {"error": k8s_zones["error"]}

    if isinstance(ceph_zones, dict) and "error" in ceph_zones:
        return {"error": ceph_zones["error"]}

    # Early exit if any zone data is missing
    zone_check_result = zone_exist(k8s_zones, ceph_zones)
    if zone_check_result:
        return zone_check_result

    # Initialize the list to hold the mapped zone data
    zones_list = []

    # Merge keys from both K8s and Ceph zones
    all_zone_names = set(k8s_zones.keys()) | set(ceph_zones.keys())

    # Iterate over each zone and extract node data
    for zone_name in all_zone_names:
        # Extract node names for masters, workers, and storage nodes
        masters = get_node_names(k8s_zones.get(zone_name, {}).get("masters", []))
        workers = get_node_names(k8s_zones.get(zone_name, {}).get("workers", []))
        storage = get_node_names(ceph_zones.get(zone_name, []))

        # Initialize the zone data dictionary
        zone_data = {"Zone Name": zone_name}

        # Only add Kubernetes zone information if there are relevant nodes
        if masters or workers:
            zone_data["Kubernetes Topology Zone"] = {}
            if masters:
                zone_data["Kubernetes Topology Zone"]["Management Master Nodes"] = masters
            if workers:
                zone_data["Kubernetes Topology Zone"]["Management Worker Nodes"] = workers

        # Only add Ceph zone information if there are storage nodes
        if storage:
            zone_data["CEPH Zone"] = {"Management Storage Nodes": storage}

        zones_list.append(zone_data)

    return {"Zones": zones_list}

def get_zones():
    """Endpoint to get summary of all zones in the new format."""
    k8s_zones = get_k8s_nodes_data()
    ceph_zones = get_ceph_storage_nodes()
    return jsonify(map_zones(k8s_zones, ceph_zones))

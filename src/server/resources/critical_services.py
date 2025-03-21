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
"""Resource to get information about the criticalservices"""

from kubernetes import client
from flask import json
from resources.k8s_zones import get_k8s_nodes_data, load_k8s_config
# import os

load_k8s_config()

def get_namespaced_pods(service_info, service_name):
    """Fuction to fetch the pods in a namespace and number of instances using Kube-config"""
    namespace = service_info["namespace"]
    resource_type = service_info["type"]
    v1 = client.CoreV1Api()

    nodes_data = get_k8s_nodes_data()
    if isinstance(nodes_data, dict) and "error" in nodes_data:
        return {"error": nodes_data["error"]}

    node_zone_map = {
        node["name"]: zone
        for zone, node_types in nodes_data.items()
        for node_type in ["masters", "workers"]
        for node in node_types[node_type]
    }

    # Get all pods in the namespace and filter by owner reference
    pod_list = v1.list_namespaced_pod(namespace)
    running_pods = 0
    result = []
    zone_pod_count = {}

    for pod in pod_list.items:
        if pod.metadata.owner_references and any(
            owner.kind == isDeploy(resource_type) and owner.name.startswith(service_name)
            for owner in pod.metadata.owner_references
        ):
            pod_status = pod.status.phase
            if pod_status == "Running":
                running_pods += 1

            node_name = pod.spec.node_name
            zone = node_zone_map.get(node_name, "unknown")

            # Count pods in each zone
            zone_pod_count[zone] = zone_pod_count.get(zone, 0) + 1

            result.append({
                "Name": pod.metadata.name,
                "Status": pod_status,
                "Node": node_name,
                "Zone": zone
            })
    return result, running_pods

def isDeploy(resource_type):
    """To check if resource is Deployment"""
    return "ReplicaSet" if resource_type == "Deployment" else resource_type

def get_configmap(cm_name, cm_namespace, cm_key):
    """Fetch the current ConfigMap data from the Kubernetes cluster."""
    try:
        v1 = client.CoreV1Api()
        cm = v1.read_namespaced_config_map(cm_name, cm_namespace)
        if cm_key in cm.data:
            return json.loads(cm.data[cm_key])  # Convert JSON string to Python dictionary
        return {"critical-services": {}}
    except client.exceptions.ApiException as e:
        return {"error": f"Failed to fetch ConfigMap: {e}"}

# VOLUME_MOUNT_PATH = "/etc/config"
# def get_configmap():
#     """Fetch the current ConfigMap data from the mounted volume."""
#     try:
#         config_file_path = os.path.join(VOLUME_MOUNT_PATH, CONFIGMAP_KEY)
        
#         # Check if the file exists
#         if os.path.exists(config_file_path):
#             with open(config_file_path, "r") as file:
#                 config_data = json.load(file)  # Parse JSON data from the file
#                 return config_data
#         else:
#             return {"error": f"ConfigMap file not found at {config_file_path}"}
#     except Exception as e:
#         return {"error": f"Failed to read ConfigMap file: {e}"}
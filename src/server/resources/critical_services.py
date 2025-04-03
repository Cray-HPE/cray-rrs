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
"""Resource to get information about the critical services"""
from kubernetes import client
from flask import json
from resources.k8s_zones import parse_k8s_zones, load_k8s_config
from flask import current_app as app
from resources.rrs_logging import get_log_id

load_k8s_config()

def get_namespaced_pods(service_info, service_name):
    """Function to fetch the pods in a namespace and number of instances using Kube-config"""
    log_id = get_log_id()
    app.logger.info(f"[{log_id}] Fetching namespaced pods")
    
    namespace = service_info["namespace"]
    resource_type = service_info["type"]
    v1 = client.CoreV1Api()

    nodes_data = parse_k8s_zones()
    if isinstance(nodes_data, dict) and "error" in nodes_data:
        app.logger.error(f"[{log_id}] Error fetching nodes data: {nodes_data['error']}")
        return {"error": nodes_data["error"]}

    node_zone_map = {
        node["name"]: zone
        for zone, node_types in nodes_data.items()
        for node_type in ["masters", "workers"]
        for node in node_types[node_type]
    }

    try:
        pod_list = v1.list_namespaced_pod(namespace)
    except client.exceptions.ApiException as e:
        app.logger.error(f"[{log_id}] API error fetching pods: {str(e)}")
        return {"error": f"Failed to fetch pods: {str(e)}"}

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
    
    app.logger.info(f"[{log_id}] Total running pods: {running_pods}")
    return result, running_pods

def isDeploy(resource_type):
    """To check if resource is Deployment"""
    return "ReplicaSet" if resource_type == "Deployment" else resource_type

def get_configmap(cm_name, cm_namespace, cm_key):
    """Fetch the current ConfigMap data from the Kubernetes cluster."""
    log_id = get_log_id()
    try:
        app.logger.info(f"[{log_id}] Fetching ConfigMap {cm_name} from namespace {cm_namespace}")
        v1 = client.CoreV1Api()
        cm = v1.read_namespaced_config_map(cm_name, cm_namespace)
        if cm_key in cm.data:
            return json.loads(cm.data[cm_key])  # Convert JSON string to Python dictionary
        app.logger.error(f"[{log_id}] ConfigMap key '{cm_key}' not found.")
        return {"critical-services": {}}
    except client.exceptions.ApiException as e:
        app.logger.error(f"[{log_id}] API error fetching ConfigMap: {str(e)}")
        return {"error": f"Failed to fetch ConfigMap: {str(e)}"}
    except Exception as e:
        app.logger.exception(f"[{log_id}] Unexpected error fetching ConfigMap: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

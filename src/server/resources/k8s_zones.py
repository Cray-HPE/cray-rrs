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
"""Resource to fetch the K8s zone data"""
from kubernetes import client, config

def load_k8s_config():
    """Load Kubernetes configuration for API access."""
    try:
        config.load_incluster_config()  # Try to load in-cluster config.
    except Exception:
        config.load_kube_config()  # Fall back to kube config if in-cluster config fails.

def get_k8s_nodes():
    """Retrieve all Kubernetes nodes."""
    try:
        load_k8s_config()
        v1 = client.CoreV1Api()
        return v1.list_node().items
    except client.exceptions.ApiException as e:
        return {"error": f"API error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def get_node_status(node):
    """Extract and return the status of a node."""
    # If the node has conditions, we check the last one.
    status = node.status.conditions[-1].status if node.status.conditions else 'Unknown'
    return "Ready" if status == "True" else "NotReady"

def get_k8s_nodes_data():
    """Fetch Kubernetes nodes and organize them by topology zone."""
    nodes = get_k8s_nodes()

    if isinstance(nodes, dict) and "error" in nodes:
        return {"error": nodes["error"]}

    zone_mapping = {}

    for node in nodes:
        node_name = node.metadata.name
        node_status = get_node_status(node)  # Get status using the helper function.
        node_zone = node.metadata.labels.get('topology.kubernetes.io/zone')

        # Skip nodes without a zone label
        if not node_zone:
            continue

        # Initialize the zone if it doesn't exist
        if node_zone not in zone_mapping:
            zone_mapping[node_zone] = {'masters': [], 'workers': []}

        # Classify nodes as master or worker based on name prefix
        if node_name.startswith("ncn-m"):
            zone_mapping[node_zone]['masters'].append({"name": node_name, "status": node_status})
        elif node_name.startswith("ncn-w"):
            zone_mapping[node_zone]['workers'].append({"name": node_name, "status": node_status})

    return zone_mapping if zone_mapping else "No K8s topology zone present"

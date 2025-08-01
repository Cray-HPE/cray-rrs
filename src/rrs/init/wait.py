#
# MIT License
#
# (C) Copyright 2025 Hewlett Packard Enterprise Development LP
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
RRS Check Rack Resiliency(RR) enablement and zones Module.

This module checks to see if RR is enabled and Kubernetes and CEPH
zones are created. If RR is enabled and zones are craeted it will continue
to deploy RRS (Rack Resiliency Service) otherwise it will wait to deploy 
till RR is enabled and zones are created.
"""

import subprocess
import base64
import json
import time
from kubernetes import client, config


def get_ceph_details():
    """Get CEPH zones details."""
    host = "ncn-m002"
    cmd = f"ssh {host} 'ceph osd tree -f json-pretty'"
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if result.returncode != 0:
            raise ValueError(f"Error fetching CEPH details: {result.stderr}")
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}


def get_ceph_hosts():
    """Get CEPH hosts details."""
    host = "ncn-m002"
    cmd = f"ssh {host} 'ceph orch host ls -f json-pretty'"
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if result.returncode != 0:
            raise ValueError(f"Error fetching CEPH details: {result.stderr}")
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}


def get_ceph_zones():
    """Fetch CEPH storage nodes and their OSD statuses."""
    ceph_tree = get_ceph_details()
    ceph_hosts = get_ceph_hosts()

    if isinstance(ceph_tree, dict) and "error" in ceph_tree:
        return {"error": ceph_tree["error"]}

    if isinstance(ceph_hosts, dict) and "error" in ceph_hosts:
        return {"error": ceph_hosts["error"]}

    host_status_map = {host["hostname"]: host["status"] for host in ceph_hosts}
    zones = {}

    for item in ceph_tree.get("nodes", []):
        if item["type"] == "rack":  # Zone (Rack)
            rack_name = item["name"]
            storage_nodes = []

            for child_id in item.get("children", []):
                host_node = next(
                    (x for x in ceph_tree["nodes"] if x["id"] == child_id), None
                )

                if (
                    host_node
                    and host_node["type"] == "host"
                    and host_node["name"].startswith("ncn-s")
                ):
                    osd_ids = host_node.get("children", [])
                    osds = [
                        osd
                        for osd in ceph_tree["nodes"]
                        if osd["id"] in osd_ids and osd["type"] == "osd"
                    ]
                    osd_status_list = [
                        {"name": osd["name"], "status": osd.get("status", "unknown")}
                        for osd in osds
                    ]

                    node_status = host_status_map.get(host_node["name"], "No status")
                    if node_status in ["", "online"]:
                        node_status = "Ready"

                    storage_nodes.append(
                        {
                            "name": host_node["name"],
                            "status": node_status,
                            "osds": osd_status_list,
                        }
                    )

            zones[rack_name] = storage_nodes

    return zones if zones else {"error": "No CEPH zones present"}


def get_kubernetes_nodes():
    """Get Kubernetes nodes."""
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()
        nodes = v1.list_node().items
        return nodes
    except Exception as e:
        return {"error": str(e)}


def get_kubernetes_zones():
    """Get Kubernetes zones details."""
    nodes = get_kubernetes_nodes()
    if isinstance(nodes, dict) and "error" in nodes:
        return "No Kubernetes topology zone present"

    zone_mapping = {}
    for node in nodes:
        node_name = node.metadata.name
        node_status = (
            node.status.conditions[-1].type if node.status.conditions else "Unknown"
        )
        node_zone = node.metadata.labels.get("topology.kubernetes.io/zone", None)
        if node_zone:
            if node_zone not in zone_mapping:
                zone_mapping[node_zone] = {"masters": [], "workers": []}
            if node_name.startswith("ncn-m"):
                zone_mapping[node_zone]["masters"].append(
                    {"name": node_name, "status": node_status}
                )
            elif node_name.startswith("ncn-w"):
                zone_mapping[node_zone]["workers"].append(
                    {"name": node_name, "status": node_status}
                )
    return zone_mapping


def check_rr_enablement():
    """Check if RR is enabled or not."""
    namespace = "loftsman"
    secret_name = "site-init"

    kubectl_cmd = [
        "kubectl",
        "-n",
        namespace,
        "get",
        "secret",
        secret_name,
        "-o",
        "json",
    ]
    kubectl_output = subprocess.run(
        kubectl_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    )

    # Parse JSON output
    secret_data = json.loads(kubectl_output.stdout)

    # Extract and decode the base64 data
    encoded_yaml = secret_data["data"]["customizations.yaml"]
    decoded_yaml = base64.b64decode(encoded_yaml).decode("utf-8")

    # Write the yaml output to a file
    output_file = "/tmp/customization.yaml"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(decoded_yaml)

    # Define the key path
    output_file = "/tmp/customization.yaml"
    key_path = "spec.kubernetes.services.rack-resiliency.enabled"

    # Run yq command to extract the value
    yq_cmd = ["yq", "r", output_file, key_path]
    result = subprocess.run(
        yq_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    )

    # Extract and clean the output
    rr_check = result.stdout.strip()

    print(f"Rack Resiliency Enabled: {rr_check}")
    return rr_check


def check_rr_setup():
    """Check if RR is setup with Kubernetes and CEPH zones or not."""
    print("Checking Rack Resiliency enablement and Kubernetes/ CEPH creation...")
    rr_enabled = check_rr_enablement()
    if rr_enabled == "false":
        print("Rack Resiliency is disabled.")
        return False

    print("Checking zoning for Kubernetes and CEPH nodes...")
    ceph_zones = get_ceph_zones()
    if isinstance(ceph_zones, dict) and "error" not in ceph_zones:
        print("CEPH zones are created.")
    else:
        print("CEPH zones are not created.")
        return False

    kubernetes_zones = get_kubernetes_zones()
    if isinstance(kubernetes_zones, dict):
        print("Kubernetes zones are created.")
    else:
        print("Not deploying the cray-rrs chart.")
        return False
    return True


def main():
    """
    Check for RR enablement and Kubernetes and CEPH zoning.
    Wait till the RR is enabled and zones are created/ present.
    """
    while True:
        if check_rr_setup():
            break
        time.sleep(120)


if __name__ == "__main__":
    main()

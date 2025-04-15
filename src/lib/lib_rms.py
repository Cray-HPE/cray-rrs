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
"""File to keep all helper functions for the RMS application."""
import os
import json
import re
import subprocess
import base64
from typing import Dict, List, Tuple, Any, Union, Literal, Optional
import requests
from flask import current_app as _app
from kubernetes import client
from kubernetes.client.rest import ApiException
from kubernetes.client.models import V1Node
from src.lib.lib_configmap import ConfigMapHelper

# logger = logging.getLogger(__name__)

HOST = "ncn-m001"


class Helper:
    """
    Helper class to provide utility functions for the application.
    """

    @staticmethod
    def run_command(command: str):
        """Helper function to run a command and return the result.
        Returns:
            str: result of the command run."""
        _app.logger.debug(f"Running command: {command}")
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                shell=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Command {command} errored out with : {e.stderr}") from e
        return result.stdout

    @staticmethod
    def get_current_node() -> str:
        """Get the kubernetes node where the current RMS pod is running
        Returns:
            str: node name where pod is running."""
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        pod_name = os.getenv("HOSTNAME")
        pod = v1.read_namespaced_pod(name=pod_name, namespace="rack-resiliency")
        node_name = pod.spec.nodeName  # node_name if nodeName does not work
        return node_name

    @staticmethod
    def getNodeMonitorGracePeriod() -> int | None:
        """Get the nodeMonitorGracePeriod value from kube-controller-manager pod.
        Returns:
            int|None: getNodeMonitorGracePeriod value if present, otherwise None."""
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(
            namespace="kube-system", label_selector="component=kube-controller-manager"
        )
        if pods.items:
            command = pods.items[0].spec.containers[0].command
            grace_period_flag = next(
                (arg for arg in command if "--node-monitor-grace-period" in arg), None
            )
            if grace_period_flag:
                nodeMonitorGracePeriod = grace_period_flag.split("=")[1]
                return int(nodeMonitorGracePeriod.rstrip("s"))
        else:
            _app.logger.error("kube-controller-manager pod not found")
        return None

    @staticmethod
    def update_configmap_with_timestamp(
        configmap_name: str, namespace: str, timestamp: str, key: str
    ) -> None:
        """Patch configmap with the latest timestamp.
        Returns: None"""
        try:
            # Load in-cluster config
            ConfigMapHelper.load_k8s_config()
            v1 = client.CoreV1Api()
            # Update the key in the data dict
            body = {"data": {key: timestamp}}

            # Push the update back to the cluster
            v1.patch_namespaced_config_map(
                name=configmap_name, namespace=namespace, body=body
            )

            _app.logger.info(
                f"Updated ConfigMap '{configmap_name}' with start_timestamp_api = {timestamp}"
            )
        except ApiException as e:
            _app.logger.error(f"Failed to update ConfigMap: {e.reason}")
        except Exception as e:
            _app.logger.error(f"Unexpected error updating ConfigMap: {str(e)}")

    @staticmethod
    def token_fetch() -> str | None:
        """Fetch an access token from Keycloak using client credentials.
        Returns:
            str | None: The access token if the request is successful, otherwise None."""
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        try:
            secret = v1.read_namespaced_secret("admin-client-auth", "default")
            client_secret = base64.b64decode(secret.data["client-secret"]).decode(
                "utf-8"
            )
            # logger.debug(f"Client Secret: {client_secret}")

            keycloak_url = "https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token"
            data = {
                "grant_type": "client_credentials",
                "client_id": "admin-client",
                "client_secret": f"{client_secret}",
            }
            response = requests.post(keycloak_url, data=data, timeout=10)
            token = response.json()
            token = token.get("access_token")
            return token

        except requests.exceptions.RequestException as e:
            _app.logger.error(f"Request failed: {e}")
            # exit(1)
        except ValueError as e:
            _app.logger.error(f"Failed to parse JSON: {e}")
            # exit(1)
        except Exception as err:
            _app.logger.error(f"Error collecting secret from Kubernetes: {err}")
            # exit(1)


class cephHelper:
    """
    Helper class to provide CEPH related utility functions for the application.
    """

    @staticmethod
    def ceph_health_check():
        """Retrieves health status of CEPH and its services.
        Returns:
            bool: Boolean flag indicating whether the CEPH cluster is healthy."""
        # ceph_status_cmd = f"ssh {HOST} 'ceph -s -f json'"
        # ceph_services_cmd = f"ssh {HOST} 'ceph orch ps -f json'"

        ceph_status_cmd = "ceph -s -f json"
        ceph_services_cmd = "ceph orch ps -f json"
        ceph_services = json.loads(Helper.run_command(ceph_services_cmd))
        ceph_status = json.loads(Helper.run_command(ceph_status_cmd))

        ceph_healthy = True
        health_status = ceph_status.get("health", {}).get("status", "UNKNOWN")
        # print(health_status)

        if "HEALTH_OK" not in health_status:
            ceph_healthy = False
            _app.logger.warning(
                f"CEPH is not healthy with health status as {health_status}"
            )
            pg_degraded_message = (
                ceph_status.get("health", {})
                .get("checks", {})
                .get("PG_DEGRADED", {})
                .get("summary", {})
                .get("message", "")
            )

            if "Degraded" in pg_degraded_message:
                pgmap = ceph_status.get('pgmap', {})
                if ('recovering_objects_per_sec' in pgmap or 'recovering_bytes_per_sec' in pgmap):
                    _app.logger.info("CEPH recovery is in progress...")
                else:
                    _app.logger.warning(
                        "CEPH PGs are in degraded state, but recovery is not happening"
                    )
            else:
                health_checks = ceph_status.get("health", {}).get("checks", {})
                _app.logger.warning(
                    f"Reason for CEPH unhealthy state are - {list(health_checks.keys())}"
                )
        else:
            _app.logger.info("CEPH is healthy")

        failed_services = []
        for service in ceph_services:
            if service["status_desc"] != "running":
                ceph_healthy = False
                failed_services.append(service["service_name"])
                _app.logger.warning(
                    f"Service {service['service_name']} running on "
                    f"{service['hostname']} is in {service['status_desc']} state"
                )
            else:
                _app.logger.debug(
                    f"Service {service['service_name']} running on "
                    f"{service['hostname']} is in {service['status_desc']} state"
                )
        if failed_services:
            _app.logger.warning(
                f"{len(failed_services)} out of {len(ceph_services)} ceph services are not running"
            )

        return ceph_healthy

    @staticmethod
    def fetch_ceph_data() -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Fetch Ceph OSD and host details using SSH commands.
        This function retrieves the OSD tree and host status using ceph commands executed remotely.
        Returns:
            tuple: JSONs containing the Ceph OSD tree and host details.
        """
        # ceph_details_cmd = f"ssh {HOST} 'ceph osd tree -f json'"
        # ceph_hosts_cmd = f"ssh {HOST} 'ceph orch host ls -f json'"

        ceph_details_cmd = "ceph osd tree -f json"
        ceph_hosts_cmd = "ceph orch host ls -f json"

        ceph_tree = json.loads(Helper.run_command(ceph_details_cmd))
        ceph_hosts = json.loads(Helper.run_command(ceph_hosts_cmd))

        return ceph_tree, ceph_hosts

    @staticmethod
    def get_ceph_status() -> tuple[Dict[str, Any], bool]:
        """
        Fetch Ceph storage nodes and their OSD statuses.
        This function processes Ceph data fetched from the Ceph OSD tree and the host status.
        Returns:
            dict or str: A dictionary of storage nodes with their OSD status
        """
        ceph_tree, ceph_hosts = cephHelper.fetch_ceph_data()
        # print(ceph_hosts)
        host_status_map = {host["hostname"]: host["status"] for host in ceph_hosts}
        final_output = {}
        failed_hosts = []
        for item in ceph_tree.get("nodes", []):
            if item["type"] == "rack":
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
                            {
                                "name": osd["name"],
                                "status": osd.get("status", "unknown"),
                            }
                            for osd in osds
                        ]

                        node_status = host_status_map.get(
                            host_node["name"], "No Status"
                        )
                        if node_status in ["", "online"]:
                            node_status = "Ready"
                        else:
                            failed_hosts.append(host_node["name"])
                            _app.logger.warning(
                                f"Host {host_node['name']} is in - {node_status} state"
                            )

                        storage_nodes.append(
                            {
                                "name": host_node["name"],
                                "status": node_status,
                                "osds": osd_status_list,
                            }
                        )

                final_output[rack_name] = storage_nodes
        if failed_hosts:
            _app.logger.warning(
                f"{len(failed_hosts)} out of {len(ceph_hosts)} ceph nodes are not healthy"
            )

        ceph_healthy = cephHelper.ceph_health_check()

        return final_output, ceph_healthy


class k8sHelper:
    """
    Helper class to provide kubernetes related utility functions for the application.
    """

    @staticmethod
    def get_k8s_nodes() -> Union[List[V1Node], Dict[str, str]]:
        """Retrieve all Kubernetes nodes
        Returns:
            Union[List[V1Node], Dict[str, str]]: 
                - A list of V1Node objects representing Kubernetes nodes if successful.
                - A dictionary with an "error" key and error message string if an exception occurs."""
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        try:
            return v1.list_node().items
        except client.exceptions.ApiException as e:
            return {"error": f"API error: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    @staticmethod
    def get_node_status(
        node_name: str,
    ) -> Literal["Ready"] | Literal["NotReady"] | Literal["Unknown"]:
        """Extract and return the status of a node"""

        nodes = k8sHelper.get_k8s_nodes()
        for node in nodes:
            if node.metadata.name == node_name:
                # If the node has conditions, we check the last one
                status = (
                    node.status.conditions[-1].status
                    if node.status.conditions
                    else "Unknown"
                )
                return "Ready" if status == "True" else "NotReady"
        return "Unknown"

    @staticmethod
    def get_k8s_nodes_data() -> (
        Union[Dict[str, str], Dict[str, Dict[str, List[Dict[str, str]]]], str]
    ):
        """Fetch Kubernetes nodes and organize them by topology zone"""
        nodes = k8sHelper.get_k8s_nodes()
        if isinstance(nodes, dict) and "error" in nodes:
            return {"error": nodes["error"]}

        zone_mapping = {}

        for node in nodes:
            node_name = node.metadata.name
            status = (
                node.status.conditions[-1].status
                if node.status.conditions
                else "Unknown"
            )
            node_status = "Ready" if status == "True" else "NotReady"
            node_zone = node.metadata.labels.get("topology.kubernetes.io/zone")

            # Skip nodes without a zone label
            if not node_zone:
                continue

            # Initialize the zone if it doesn't exist
            if node_zone not in zone_mapping:
                zone_mapping[node_zone] = {"masters": [], "workers": []}

            # Classify nodes as master or worker based on name prefix
            if node_name.startswith("ncn-m"):
                zone_mapping[node_zone]["masters"].append(
                    {"name": node_name, "status": node_status}
                )
            elif node_name.startswith("ncn-w"):
                zone_mapping[node_zone]["workers"].append(
                    {"name": node_name, "status": node_status}
                )
        if zone_mapping:
            return zone_mapping
        else:
            _app.logger.error("No K8s topology zone present")
            return "No K8s topology zone present"

    @staticmethod
    def fetch_all_pods() -> Union[Dict[str, str], List[Dict[str, Any]]]:
        """Fetch all pods in a single API call to reduce request time."""
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        nodes_data = k8sHelper.get_k8s_nodes_data()
        # _app.logger.info(f"from fetch_all_pods - {nodes_data}")
        if isinstance(nodes_data, dict) and "error" in nodes_data:
            # _app.logger.info("nodes_data is disctionary")
            return {"error": nodes_data["error"]}

        node_zone_map = {
            node["name"]: zone
            for zone, node_types in nodes_data.items()
            for node_type in ["masters", "workers"]
            for node in node_types[node_type]
        }

        all_pods = v1.list_pod_for_all_namespaces(watch=False).items
        pod_info = []

        for pod in all_pods:
            node_name = pod.spec.node_name
            zone = node_zone_map.get(node_name, "unknown")
            pod_info.append(
                {
                    "Name": pod.metadata.name,
                    "Node": node_name,
                    "Zone": zone,
                    "labels": pod.metadata.labels,
                }
            )

        return pod_info


class criticalServicesHelper:
    """
    Helper class to provide utility functions related to critical services for the application.
    """

    @staticmethod
    def check_skew(service_name: str, pods: List[Dict[str, str]]) -> dict[str, Any]:
        """Check the replica skew across zones efficiently."""
        zone_pod_map = {}

        for pod in pods:
            zone = pod["Zone"]
            node = pod["Node"]
            pod_name = pod["Name"]

            if zone not in zone_pod_map:
                zone_pod_map[zone] = {}
            if node not in zone_pod_map[zone]:
                zone_pod_map[zone][node] = []
            zone_pod_map[zone][node].append(pod_name)

        counts = [
            sum(len(pods) for pods in zone.values()) for zone in zone_pod_map.values()
        ]

        if not counts:
            return {
                "service-name": service_name,
                "status": "no replicas found",
                "replicaDistribution": {},
            }

        balanced = "true" if max(counts) - min(counts) <= 1 else "false"

        return {
            "service-name": service_name,
            "balanced": balanced,
            "replicaDistribution": zone_pod_map,
        }

    @staticmethod
    def get_service_status(
        service_name: str, service_namespace: str, service_type: str
    ) -> Tuple[Optional[int], Optional[int], Optional[Dict[str, str]]]:
        """Helper function to fetch service status based on service type."""
        ConfigMapHelper.load_k8s_config()
        apps_v1 = client.AppsV1Api()
        try:
            if service_type == "Deployment":
                app = apps_v1.read_namespaced_deployment(
                    service_name, service_namespace
                )
                return (
                    app.status.replicas,
                    app.status.ready_replicas,
                    app.spec.selector.match_labels,
                )
            if service_type == "StatefulSet":
                app = apps_v1.read_namespaced_stateful_set(
                    service_name, service_namespace
                )
                return (
                    app.status.replicas,
                    app.status.ready_replicas,
                    app.spec.selector.match_labels,
                )
            if service_type == "DaemonSet":
                app = apps_v1.read_namespaced_daemon_set(
                    service_name, service_namespace
                )
                return (
                    app.status.desired_number_scheduled,
                    app.status.number_ready,
                    app.spec.selector.match_labels,
                )
            _app.logger.warning(f"Unsupported service type: {service_type}")
            return None, None, None
        except client.exceptions.ApiException as e:
            match = re.search(r"Reason: (.*?)\n", str(e))
            error_message = match.group(1) if match else str(e)
            _app.logger.error(
                f"Error fetching {service_type} {service_name}: {error_message}"
            )
            return None, None, None

    @staticmethod
    def get_critical_services_status(services_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update critical service info with status and balanced values"""

        # _app.logger.info(f"In lib_rms get_critical_services_status, input data is - {services_data}")
        # Fetch all pods in one API call
        all_pods = k8sHelper.fetch_all_pods()

        critical_services = services_data["critical-services"]
        _app.logger.info(f"Number of critical services are - {len(critical_services)}")
        imbalanced_services = []
        for service_name, service_info in critical_services.items():
            # print(service_name)
            # print(service_info)

            service_namespace = service_info["namespace"]
            service_type = service_info["type"]
            desired_replicas, ready_replicas, labels = (
                criticalServicesHelper.get_service_status(
                    service_name, service_namespace, service_type
                )
            )

            # If replicas data was returned
            if (
                desired_replicas is not None
                and ready_replicas is not None
                and labels is not None
            ):
                status = "Configured"
                if ready_replicas < desired_replicas:
                    imbalanced_services.append(service_name)
                    status = "PartiallyConfigured"
                    _app.logger.warning(
                        f"{service_type} '{service_name}' in namespace '{service_namespace}' is not ready. "
                        f"Only {ready_replicas} replicas are ready out of {desired_replicas} desired replicas"
                    )
                else:
                    _app.logger.debug(
                        f"Desired replicas and ready replicas are matching for '{service_name}'"
                    )

                filtered_pods = [
                    pod
                    for pod in all_pods
                    if pod.get("labels")
                    and all(
                        pod["labels"].get(key) == value for key, value in labels.items()
                    )
                ]

                balance_details = criticalServicesHelper.check_skew(
                    service_name, filtered_pods
                )
                if balance_details["balanced"] == "False":
                    imbalanced_services.append(service_name)
                service_info.update(
                    {"status": status, "balanced": balance_details["balanced"]}
                )
            else:
                service_info.update({"status": "Unconfigured", "balanced": "NA"})
        if imbalanced_services:
            _app.logger.warning(
                f"List of imbalanced services are - {imbalanced_services}"
            )
        return services_data

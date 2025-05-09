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
lib_rms.py

This module contains utility functions for managing and monitoring critical services,
including Kubernetes and Ceph zone discovery, status checking, and configuration updates.
"""

import os
import json
import re
import subprocess
import base64
import time
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any, Union, Literal, Optional, TypedDict
import requests
import yaml
from kubernetes import client  # type: ignore
from kubernetes.client.rest import ApiException
from kubernetes.client.models import V1Node
from src.lib.lib_configmap import ConfigMapHelper
from src.rrs.rms.rms_statemanager import RMSStateManager

fallback_logger = logging.getLogger(__name__)

def get_logger():
    try:
        from flask import has_app_context, current_app
        if has_app_context():
            return current_app.logger
    except ImportError:
        pass  # Flask not installed or not in Flask app context
    return fallback_logger

logger = get_logger()

HOST = "ncn-m001"


class Helper:
    """
    Helper class to provide utility functions for the application.
    """

    @staticmethod
    def run_command(command: str) -> str:
        """Helper function to run a command and return the result.
        Returns:
            str: result of the command run."""
        logger.debug(f"Running command: {command}")
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
    def update_state_timestamp(
        state_manager: RMSStateManager,
        state_field: Optional[str] = None,
        new_state: Optional[str] = None,
        timestamp_field: Optional[str] = None,
    ) -> None:
        """Update the RMS state and/or a timestamp field in the dynamic ConfigMap."""
        try:
            dynamic_cm_data = state_manager.get_dynamic_cm_data()
            yaml_content = dynamic_cm_data.get("dynamic-data.yaml", None)
            if yaml_content is not None:
                dynamic_data = yaml.safe_load(yaml_content)
                if new_state:
                    logger.info(f"Updating state {state_field} to {new_state}")
                    state = dynamic_data.get("state", {})
                    state[state_field] = new_state
                if timestamp_field:
                    logger.info(f"Updating timestamp {timestamp_field}")
                    timestamp = dynamic_data.get("timestamps", {})
                    timestamp[timestamp_field] = datetime.now().strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )

                dynamic_cm_data["dynamic-data.yaml"] = yaml.dump(
                    dynamic_data, default_flow_style=False
                )
                state_manager.set_dynamic_cm_data(dynamic_cm_data)
                ConfigMapHelper.update_configmap_data(
                    state_manager.namespace,
                    state_manager.dynamic_cm,
                    dynamic_cm_data,
                    "dynamic-data.yaml",
                    dynamic_cm_data["dynamic-data.yaml"],
                )
                # app.logger.info(f"Updated rms_state in rrs-dynamic configmap from {rms_state} to {new_state}")
        except ValueError as e:
            logger.error(f"Error during configuration check and update: {e}")
            state_manager.set_state("internal_failure")
            # exit(1)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            state_manager.set_state("internal_failure")
            # exit(1)

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

            logger.info(
                f"Updated ConfigMap '{configmap_name}' with start_timestamp_api = {timestamp}"
            )
        except ApiException as e:
            logger.error(f"Failed to update ConfigMap: {e.reason}")
        except Exception as e:
            logger.error(f"Unexpected error updating ConfigMap: {str(e)}")

    @staticmethod
    def token_fetch() -> Optional[str]:
        """Fetch an access token from Keycloak using client credentials.
        Returns:
            Optional[str]: The access token if the request is successful"""
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
            token_data = response.json()
            token: Optional[str] = token_data.get("access_token")
            return token

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
        except ValueError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None
        except Exception as err:
            logger.error(f"Error collecting secret from Kubernetes: {err}")
            return None

    @staticmethod
    def get_sls_hms_data() -> Tuple[Optional[Dict[str, List[Dict[str, Any]]]], Optional[List[Dict[str, Any]]]]:
        """
        Fetch data from HSM and SLS services.
        Returns:
            Tuple[Optional[Dict], Optional[Dict]]:
                - hsm_data (dict or None): Parsed HSM response.
                - sls_data (dict or None): Parsed SLS response.
        """
        token = Helper.token_fetch()
        hsm_url = "https://api-gw-service-nmn.local/apis/smd/hsm/v2/State/Components"
        sls_url = "https://api-gw-service-nmn.local/apis/sls/v1/search/hardware"
        params = {"type": "comptype_node"}
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        max_retries = 3
        retry_delay = 2  # in seconds
        hsm_data = None
        sls_data = None

        # Peform HSM fetch
        for attempt in range(1, max_retries + 1):
            try:
                hsm_response = requests.get(hsm_url, headers=headers, timeout=10)
                hsm_response.raise_for_status()
                hsm_data = hsm_response.json()
                break  # Success, exit retry loop
            except (requests.exceptions.RequestException, ValueError) as e:
                logger.error(f"Attempt {attempt}: Failed to fetch HSM data: {e}")
                if attempt == max_retries:
                    logger.error("Max retries reached. Could not fetch HSM data")
                    return None, None
                time.sleep(retry_delay)

        # Perform SLS fetch
        for attempt in range(1, max_retries + 1):
            try:
                sls_response = requests.get(
                    sls_url, headers=headers, params=params, timeout=10
                )
                sls_response.raise_for_status()
                sls_data = sls_response.json()
                break  # Success, exit retry loop
            except (requests.exceptions.RequestException, ValueError) as e:
                logger.error(f"Attempt {attempt}: Failed to fetch SLS data: {e}")
                if attempt == max_retries:
                    logger.error("Max retries reached. Could not fetch SLS data")
                    return None, None
                time.sleep(retry_delay)

        return hsm_data, sls_data


class cephHelper:
    """
    Helper class to provide CEPH related utility functions for the application.
    """

    @staticmethod
    def ceph_health_check() -> bool:
        """Retrieves health status of CEPH and its services.
        Returns:
            bool: Boolean flag indicating whether the CEPH cluster is healthy."""
        ceph_status_cmd = f"ssh {HOST} 'ceph -s -f json'"
        ceph_services_cmd = f"ssh {HOST} 'ceph orch ps -f json'"

        ceph_services = json.loads(Helper.run_command(ceph_services_cmd))
        ceph_status = json.loads(Helper.run_command(ceph_status_cmd))

        ceph_healthy = True
        health_status = ceph_status.get("health", {}).get("status", "UNKNOWN")
        # print(health_status)

        if "HEALTH_OK" not in health_status:
            ceph_healthy = False
            logger.warning(
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
                pgmap = ceph_status.get("pgmap", {})
                if (
                    "recovering_objects_per_sec" in pgmap
                    or "recovering_bytes_per_sec" in pgmap
                ):
                    logger.info("CEPH recovery is in progress...")
                else:
                    logger.warning(
                        "CEPH PGs are in degraded state, but recovery is not happening"
                    )
            else:
                health_checks = ceph_status.get("health", {}).get("checks", {})
                logger.warning(
                    f"Reason for CEPH unhealthy state are - {list(health_checks.keys())}"
                )
        else:
            logger.info("CEPH is healthy")

        failed_services = []
        for service in ceph_services:
            if service["status_desc"] != "running":
                ceph_healthy = False
                failed_services.append(service["service_name"])
                logger.warning(
                    f"Service {service['service_name']} running on "
                    f"{service['hostname']} is in {service['status_desc']} state"
                )
            else:
                logger.debug(
                    f"Service {service['service_name']} running on "
                    f"{service['hostname']} is in {service['status_desc']} state"
                )
        if failed_services:
            logger.warning(
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
        ceph_details_cmd = f"ssh {HOST} 'ceph osd tree -f json'"
        ceph_hosts_cmd = f"ssh {HOST} 'ceph orch host ls -f json'"

        ceph_tree = json.loads(Helper.run_command(ceph_details_cmd))
        ceph_hosts = json.loads(Helper.run_command(ceph_hosts_cmd))

        return ceph_tree, ceph_hosts

    @staticmethod
    def get_ceph_status() -> tuple[Dict[str, Any], bool]:
        """
        Fetch Ceph storage nodes and their OSD statuses.
        This function processes Ceph data fetched from the Ceph OSD tree and the host status.
        Returns:
            tuple[Dict[str, Any], bool]:
            A dictionary of storage nodes with their OSD status and a bool indicating health
        """
        ceph_tree, ceph_hosts = cephHelper.fetch_ceph_data()
        # print(ceph_hosts)
        host_status_map: Dict[str, str] = {}
        if isinstance(ceph_hosts, list):
            for host in ceph_hosts:
                if isinstance(host, dict) and "hostname" in host and "status" in host:
                    host_status_map[host["hostname"]] = host["status"]
        final_output: Dict[str, List[Dict[str, Any]]] = {}
        failed_hosts: List[str] = []
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
                            logger.warning(
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
            logger.warning(
                f"{len(failed_hosts)} out of {len(ceph_hosts)} ceph nodes are not healthy"
            )

        ceph_healthy = cephHelper.ceph_health_check()

        return final_output, ceph_healthy


class k8sHelper:
    """
    Helper class to provide kubernetes related utility functions for the application.
    """

    @staticmethod
    def get_current_node() -> str:
        """Get the kubernetes node where the current RMS pod is running
        Returns:
            str: node name where pod is running."""
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        pod_name = os.getenv("HOSTNAME")
        pod = v1.read_namespaced_pod(name=pod_name, namespace="rack-resiliency")
        node_name: str = str(pod.spec.nodeName) if pod.spec.nodeName else ""
        return node_name

    @staticmethod
    def getNodeMonitorGracePeriod() -> Optional[int]:
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
                grace_period_parts = grace_period_flag.split("=")
                if len(grace_period_parts) > 1:
                    nodeMonitorGracePeriod = grace_period_parts[1]
                    if nodeMonitorGracePeriod.endswith("s"):
                        return int(nodeMonitorGracePeriod[:-1])  # Remove the 's' suffix
                    return int(nodeMonitorGracePeriod)
        else:
            logger.error("kube-controller-manager pod not found")
        return None

    @staticmethod
    def get_k8s_nodes() -> Union[List[V1Node], Dict[str, str]]:
        """Retrieve all Kubernetes nodes
        Returns:
            Union[List[V1Node], Dict[str, str]]:
                - A list of V1Node objects representing Kubernetes nodes if successful.
                - A dictionary with an "error" key and error message string if an exception occurs.
        """
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        try:
            nodes: List[V1Node] = v1.list_node().items
            return nodes
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
        if isinstance(nodes, dict) and "error" in nodes:
            return "Unknown"

        for node in nodes:
            if isinstance(node, V1Node) and node.metadata.name == node_name:
                # If the node has conditions, we check the last one
                if node.status.conditions:
                    status = node.status.conditions[-1].status
                    result: Literal["Ready"] | Literal["NotReady"] = (
                        "Ready" if status == "True" else "NotReady"
                    )
                    return result
                return "Unknown"
        return "Unknown"

    @staticmethod
    def get_k8s_nodes_data() -> (
        Union[Dict[str, Dict[str, List[Dict[str, str]]]], Dict[str, str], str]
    ):
        """Fetch Kubernetes nodes and organize them by topology zone"""
        nodes = k8sHelper.get_k8s_nodes()
        if isinstance(nodes, dict) and "error" in nodes:
            return {"error": nodes["error"]}

        zone_mapping: Dict[str, Dict[str, List[Dict[str, str]]]] = {}

        for node in nodes:
            if not isinstance(node, V1Node):
                continue

            node_name = node.metadata.name
            if node.status.conditions:
                status = node.status.conditions[-1].status
                node_status = "Ready" if status == "True" else "NotReady"
            else:
                node_status = "Unknown"

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
        logger.error("No K8s topology zone present")
        return "No K8s topology zone present"

    @staticmethod
    def fetch_all_pods() -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Fetch all pods in a single API call to reduce request time."""
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        nodes_data = k8sHelper.get_k8s_nodes_data()
        # logger.info(f"from fetch_all_pods - {nodes_data}")

        # Handle error cases
        if isinstance(nodes_data, dict) and nodes_data.get("error"):
            return {"error": nodes_data["error"]}
        if isinstance(nodes_data, str):
            return {"error": nodes_data}

        # Ensure nodes_data is the correct type for future operations
        if not isinstance(nodes_data, dict):
            return {"error": "Invalid node data format"}

        node_zone_map: Dict[str, str] = {}
        for zone, node_types in nodes_data.items():
            if not isinstance(node_types, dict):
                continue  # Skip if node_types is not a dictionary

            for node_type in ["masters", "workers"]:
                if node_type not in node_types or not isinstance(
                    node_types[node_type], list
                ):
                    continue  # Skip if node_type key doesn't exist or value is not a list

                for node in node_types[node_type]:
                    if not isinstance(node, dict) or "name" not in node:
                        continue  # Skip if node is not a dictionary or doesn't have a name key

                    node_zone_map[node["name"]] = zone

        all_pods = v1.list_pod_for_all_namespaces(watch=False).items
        pod_info: List[Dict[str, Any]] = []

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


class PodInfo(TypedDict):
    """Type definition for pod information dictionary returned by the Kubernetes API."""

    Name: str
    Node: str
    Zone: str
    labels: Dict[str, str]


class criticalServicesHelper:
    """
    Helper class to provide utility functions related to critical services for the application.
    """

    @staticmethod
    def check_skew(service_name: str, pods: List[Dict[str, Any]]) -> dict[str, Any]:
        """Check the replica skew across zones efficiently."""
        zone_pod_map: Dict[str, Dict[str, List[str]]] = {}

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
            logger.warning(f"Unsupported service type: {service_type}")
            return None, None, None
        except client.exceptions.ApiException as e:
            match = re.search(r"Reason: (.*?)\n", str(e))
            error_message = match.group(1) if match else str(e)
            logger.error(
                f"Error fetching {service_type} {service_name}: {error_message}"
            )
            return None, None, None

    @staticmethod
    def get_critical_services_status(services_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update critical service info with status and balanced values"""

        # logger.info(f"In lib_rms get_critical_services_status, input data is - {services_data}")
        # Fetch all pods in one API call
        all_pods = k8sHelper.fetch_all_pods()

        critical_services = services_data.get("critical-services", {})
        logger.info(f"Number of critical services are - {len(critical_services)}")
        imbalanced_services: List[str] = []

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
                    logger.warning(
                        f"{service_type} '{service_name}' in namespace '{service_namespace}' is not ready. "
                        f"Only {ready_replicas} replicas are ready out of {desired_replicas} desired replicas"
                    )
                else:
                    logger.debug(
                        f"Desired replicas and ready replicas are matching for '{service_name}'"
                    )

                filtered_pods: List[Dict[str, Any]] = []
                if isinstance(all_pods, list):
                    filtered_pods = [
                        pod
                        for pod in all_pods
                        if pod.get("labels")
                        and all(
                            pod["labels"].get(key) == value
                            for key, value in labels.items()
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
            logger.warning(
                f"List of imbalanced services are - {imbalanced_services}"
            )
        return services_data

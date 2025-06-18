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
from logging import Logger
from datetime import datetime
from typing import Literal, Optional, cast
import requests
import urllib3
import yaml
from kubernetes import client
from kubernetes.client.exceptions import ApiException
from kubernetes.client.models import V1Node
from src.lib.lib_configmap import ConfigMapHelper
from src.rrs.rms.rms_statemanager import RMSStateManager
from src.lib.schema import (
    cephNodesStatusResultType,
    cephOrchPsService,
    cephStatus,
    k8sNodesResultType,
    CephNodeStatusInfo,
    OSDStatusSchema,
    CriticalServiceCmDynamicType,
    slsEntryDataType,
    podInfoType,
    hsmDataType,
    openidTokenResponse,
    cephTreeDataType,
    cephHostDataType,
    skewReturn,
    DynamicDataSchema,
    StateSchema,
    TimestampsSchema,
)
from src.lib.rrs_constants import (
    NAMESPACE,
    DYNAMIC_DATA_KEY,
    SECRET_NAME,
    SECRET_DEFAULT_NAMESPACE,
    SECRET_DATA_KEY,
    REQUESTS_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
    HOSTS,
)

# disables only the InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

sls_datatype = list[slsEntryDataType]
podInfoType_list = list[podInfoType]


def set_logger(custom_logger: Logger) -> None:
    """
    Sets a custom logger to be used globally within the module.
    This allows external modules (e.g., Flask apps) to inject their own logger instance,
    enabling unified logging across different parts of the application.
    Args:
        custom_logger (logging.Logger): A configured logger instance to override the default python logger.
    """
    global logger
    logger = custom_logger


class Helper:
    """
    Helper class to provide utility functions for the application.
    """

    @staticmethod
    def run_command_on_hosts(command: str) -> str:
        """Helper function that attempts to run a shell command on a list of hosts sequentially
        Args:
            command (str): The shell command to execute on the remote host.
        Returns:
            str: The output from the successful execution of the command,
                        or empty string if the command fails on all hosts.
        """
        for host in HOSTS:
            try:
                logger.debug("Running command: %s on host %s", command, host)
                formatted_command = command.format(host=host)
                result: subprocess.CompletedProcess[str] = subprocess.run(
                    formatted_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=True,
                    check=True,
                )
                return result.stdout
            except subprocess.CalledProcessError:
                logger.exception(
                    "Trying next host as command %s errored out on host %s",
                    command,
                    host,
                )
        logger.exception("All hosts failed for command: %s", command)
        return ""

    @staticmethod
    def update_state_timestamp(
        state_manager: RMSStateManager,
        state_field: Optional[
            Literal["ceph_monitoring", "k8s_monitoring", "rms_state"]
        ] = None,
        new_state: Optional[str] = None,
        timestamp_field: Optional[
            Literal[
                "end_timestamp_ceph_monitoring",
                "end_timestamp_k8s_monitoring",
                "init_timestamp",
                "last_update_timestamp",
                "start_timestamp_api",
                "start_timestamp_ceph_monitoring",
                "start_timestamp_k8s_monitoring",
                "start_timestamp_rms",
            ]
        ] = None,
    ) -> None:
        """
        Update the RMS state and/or a timestamp field in the dynamic ConfigMap.
        Args:
            state_manager (RMSStateManager): The state manager instance handling ConfigMap interactions.
            state_field (Optional[Literal]): The key in the 'state' section to update.
            new_state (Optional[str]): The value to assign to the specified state field.
            timestamp_field (Optional[Literal]): The key in the 'timestamps' section to update.
        Returns:
            None
        """
        try:
            dynamic_cm_data = state_manager.get_dynamic_cm_data()
            yaml_content = dynamic_cm_data.get(DYNAMIC_DATA_KEY, None)
            if yaml_content is None:
                return

            dynamic_data: DynamicDataSchema = yaml.safe_load(yaml_content)

            if state_field is not None and new_state is not None:
                logger.info("Updating state %s to %s", state_field, new_state)
                state = dynamic_data["state"]
                state[state_field] = new_state
                dynamic_data["state"] = state

            if timestamp_field is not None:
                logger.info("Updating timestamp %s", timestamp_field)
                timestamp = dynamic_data["timestamps"]
                timestamp[timestamp_field] = datetime.now().strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                dynamic_data["timestamps"] = timestamp

            dynamic_cm_data[DYNAMIC_DATA_KEY] = yaml.dump(
                dynamic_data, default_flow_style=False
            )
            state_manager.set_dynamic_cm_data(dynamic_cm_data)
            ConfigMapHelper.update_configmap_data(
                dynamic_cm_data,
                DYNAMIC_DATA_KEY,
                dynamic_cm_data[DYNAMIC_DATA_KEY],
            )
        except ValueError as e:
            logger.error("Error during configuration check and update: %s", e)
        except Exception as e:
            logger.error("Unexpected error: %s", e)

    @staticmethod
    def token_fetch() -> Optional[str]:
        """Fetch an access token from Keycloak using client credentials.
        Returns:
            Optional[str]: The access token if the request is successful"""
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        try:
            secret = v1.read_namespaced_secret(SECRET_NAME, SECRET_DEFAULT_NAMESPACE)
            if secret.data is not None:
                client_secret = base64.b64decode(secret.data[SECRET_DATA_KEY]).decode(
                    "utf-8"
                )
                keycloak_url = "https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token"
                data = {
                    "grant_type": "client_credentials",
                    "client_id": "admin-client",
                    "client_secret": f"{client_secret}",
                }
                response = requests.post(
                    keycloak_url, data=data, timeout=REQUESTS_TIMEOUT, verify=False
                )
                token_data: openidTokenResponse = response.json()
                token: Optional[str] = token_data.get("access_token")
                return token

        except requests.exceptions.RequestException as e:
            logger.error("Request failed: %s", e)
        except ValueError as e:
            logger.error("Failed to parse JSON: %s", e)
        except Exception as err:
            logger.error("Error collecting secret from Kubernetes: %s", err)

        return None

    @staticmethod
    def get_hsm_sls_data(get_hsm: bool, get_sls: bool) -> tuple[
        Optional[hsmDataType],
        Optional[sls_datatype],
    ]:
        """
        Fetch data from HSM and SLS services.
        Returns:
            tuple[Optional[dict], Optional[dict]]:
                - hsm_data (dict or None): Parsed HSM response.
                - sls_data (dict or None): Parsed SLS response.
        """
        token = Helper.token_fetch()
        hsm_url = "https://api-gw-service-nmn.local/apis/smd/hsm/v2/State/Components"
        sls_url = "https://api-gw-service-nmn.local/apis/sls/v1/search/hardware"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        hsm_data: hsmDataType | None = None
        sls_data: sls_datatype | None = None

        # Peform HSM fetch
        if get_hsm:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    params = {"role": "Management", "type": "Node"}
                    hsm_response = requests.get(
                        hsm_url,
                        headers=headers,
                        params=params,
                        timeout=REQUESTS_TIMEOUT,
                        verify=False,
                    )
                    hsm_response.raise_for_status()
                    hsm_data = cast(hsmDataType, hsm_response.json())

                    break  # Success, exit retry loop
                except (requests.exceptions.RequestException, ValueError) as e:
                    logger.error("Attempt %d: Failed to fetch HSM data: %s", attempt, e)
                    if attempt == MAX_RETRIES:
                        logger.error("Max retries reached. Could not fetch HSM data")
                        return None, None
                    time.sleep(RETRY_DELAY)

        # Perform SLS fetch
        if get_sls:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    params = {"type": "comptype_node"}
                    sls_response = requests.get(
                        sls_url,
                        headers=headers,
                        params=params,
                        timeout=REQUESTS_TIMEOUT,
                        verify=False,
                    )
                    sls_response.raise_for_status()
                    sls_data = cast(sls_datatype, sls_response.json())
                    break  # Success, exit retry loop
                except (requests.exceptions.RequestException, ValueError) as e:
                    logger.error("Attempt %d: Failed to fetch SLS data: %s", attempt, e)
                    if attempt == MAX_RETRIES:
                        logger.error("Max retries reached. Could not fetch SLS data")
                        return None, None
                    time.sleep(RETRY_DELAY)

        return hsm_data, sls_data

    @staticmethod
    def get_rack_name_for_node(node_name: str) -> Optional[str]:
        """
        Retrieve the rack (Xname) associated with a given node name.
        Args:
            node_name (str): The logical or alias name of the node to search for.
        Returns:
            Optional[str]: The rack Xname (e.g., "x3000") if found, otherwise None.
        """
        try:
            logger.debug("Retrieving rack name for a particular node")
            _, sls_data = Helper.get_hsm_sls_data(False, True)
            if not sls_data:
                logger.error("Failed to retrieve SLS data")
                return None
            for item in sls_data:
                extraProps = item.get("ExtraProperties", {})
                aliases = extraProps.get("Aliases", [])
                if node_name in aliases:
                    rack_xname = item.get("Xname")
                    logger.debug(
                        "Found rack xname '%s' for node '%s'",
                        rack_xname,
                        node_name,
                    )
                    return rack_xname
            logger.warning("No matching xname found for node: %s", node_name)
            return None
        except Exception as e:
            logger.exception(
                "Unexpected error occurred during pod location check: %s", str(e)
            )
            return None

    @staticmethod
    def check_failed_node(
        pod_node: str,
        pod_zone: str,
        sls_data: sls_datatype,
        hsm_data: hsmDataType,
    ) -> None:
        """
        Checks if the monitoring pod was previously running on a failed node based on SLS and HSM data.
        Args:
            pod_node (str): Name of the node where the pod was previously running.
            pod_zone (str): Rack or zone where the pod was running.
            sls_data (sls_datatype): list of SLS hardware components with xnames and aliases.
            hsm_data (hsmDataType): HSM component data filtered to relevant roles/subroles.
        Returns:
            None
        """
        try:
            # Retrieve the state of the node that previously hosted the RRS pod.
            # Log a message if the node is powered off
            for sls_entry in sls_data:
                extraProps = sls_entry.get("ExtraProperties", None)
                if extraProps is None:
                    return
                aliases = extraProps.get("Aliases", None)
                if aliases is None:
                    return
                alias = aliases[0]
                if pod_node not in alias:
                    continue

                for component in hsm_data.get("Components", []):
                    comp_id = component["ID"]
                    if sls_entry["Xname"] != comp_id:
                        continue
                    rack_id = comp_id.split("c")[
                        0
                    ]  # Extract "x3000" from "x3000c0s1b75n75"
                    comp_state = component["State"]
                    if comp_state in ["Off"] and rack_id in pod_zone:
                        logger.info(
                            "Monitoring pod was previously running on the "
                            "failed node %s under rack %s",
                            pod_node,
                            rack_id,
                        )
                    return
                return
        except Exception as e:
            logger.exception(
                "Error while checking if pod was on a failed node: %s", str(e)
            )


class cephHelper:
    """
    Helper class to provide CEPH related utility functions for the application.
    """

    @staticmethod
    def check_ceph_services() -> bool:
        """
        Checks the status of Ceph services
        Returns:
            bool: True if at least one service is in a 'running' state,
                False if the command fails on all hosts or if all services are in a failed state.
        """
        ceph_healthy = False
        try:
            ceph_services_cmd = (
                "ssh -o StrictHostKeyChecking=no "
                "-o UserKnownHostsFile=/dev/null "
                "{host} 'ceph orch ps -f json'"
            )
            services_output = Helper.run_command_on_hosts(ceph_services_cmd)
            if not services_output:
                logger.warning("Could not fetch CEPH services status")
                return ceph_healthy
            ceph_services: list[cephOrchPsService] = json.loads(services_output)
            failed_services = []
            for service in ceph_services:
                if service["status_desc"] != "running":
                    failed_services.append(service["service_name"])
                    logger.warning(
                        "Service %s running on %s is in %s state",
                        service["service_name"],
                        service["hostname"],
                        service["status_desc"],
                    )
                else:
                    ceph_healthy = True
                    logger.debug(
                        "Service %s running on %s is in %s state",
                        service["service_name"],
                        service["hostname"],
                        service["status_desc"],
                    )
            if failed_services:
                logger.warning(
                    "%d out of %d ceph services are not running",
                    len(failed_services),
                    len(ceph_services),
                )
            return ceph_healthy
        except json.JSONDecodeError:
            logger.exception("Invalid JSON output received from Ceph command")
        except ValueError as e:
            logger.exception("Command execution error: %s", str(e))
        except Exception as e:
            logger.exception("Unexpected error during CEPH health check: %s", str(e))
        # Ensure a boolean is always returned
        return ceph_healthy

    @staticmethod
    def check_ceph_health() -> bool:
        """Retrieves health status of CEPH.
        Returns:
            bool: Boolean flag indicating whether the CEPH cluster is healthy."""
        ceph_healthy = False
        try:

            ceph_status_cmd = "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {host} 'ceph -s -f json'"
            ceph_status_cmd = (
                "ssh -o StrictHostKeyChecking=no "
                "-o UserKnownHostsFile=/dev/null "
                "{host} 'ceph -s -f json'"
            )
            status_output = Helper.run_command_on_hosts(ceph_status_cmd)
            if not status_output:
                logger.warning("Could not fetch CEPH health")
                return ceph_healthy
            ceph_status: cephStatus = json.loads(status_output)
            health_status = ceph_status.get("health", {}).get("status", "UNKNOWN")

            if "HEALTH_OK" not in health_status:
                logger.warning(
                    "CEPH is not healthy with health status as %s", health_status
                )
                # Check the reason for CEPH failure
                # Explicitly check if PGs are degraded and recovery is in progess
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
                        "Reason for CEPH unhealthy state are - %s",
                        list(health_checks.keys()),
                    )
            else:
                # This case probably would not be happening in case of monitoring as
                # CEPH would not be healthy until and unless the node comes back up
                logger.info("CEPH is healthy")
                ceph_healthy = True

            return ceph_healthy
        except json.JSONDecodeError as e:
            logger.error("Failed to decode CEPH JSON response: %s", e)
        except ValueError as e:
            logger.error("Command execution error: %s", e)
        except Exception as e:
            logger.exception("Unexpected error during CEPH health check: %s", e)
        # Ensure a boolean is always returned
        return ceph_healthy

    @staticmethod
    def fetch_ceph_data() -> tuple[cephTreeDataType, list[cephHostDataType]]:
        """
        Fetch Ceph OSD and host details using SSH commands.
        This function retrieves the OSD tree and host status using ceph commands executed remotely.
        Returns:
            tuple: JSONs containing the Ceph OSD tree and host details.
        """
        try:
            ceph_tree_cmd = (
                "ssh -o StrictHostKeyChecking=no "
                "-o UserKnownHostsFile=/dev/null "
                "{host} 'ceph osd tree -f json'"
            )
            ceph_hosts_cmd = (
                "ssh -o StrictHostKeyChecking=no "
                "-o UserKnownHostsFile=/dev/null "
                "{host} 'ceph orch host ls -f json'"
            )
            tree_output = Helper.run_command_on_hosts(ceph_tree_cmd)
            host_output = Helper.run_command_on_hosts(ceph_hosts_cmd)
            if not tree_output or not host_output:
                logger.warning("Could not fetch CEPH output")
                return {}, []
            ceph_tree: cephTreeDataType = json.loads(tree_output)
            ceph_hosts: list[cephHostDataType] = json.loads(host_output)

            logger.debug("CEPH OSD Tree Output: %s", ceph_tree)
            logger.debug("CEPH Host list Output: %s", ceph_hosts)

            return ceph_tree, ceph_hosts

        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON from CEPH output: %s", e)
        except ValueError as e:
            logger.error("Command execution error: %s", e)
        except Exception as e:
            logger.exception("Unexpected error while fetching CEPH data: %s", e)

        # Safe fallback on failure
        return cephTreeDataType(), cast(list[cephHostDataType], [])

    @staticmethod
    def get_ceph_status() -> tuple[cephNodesStatusResultType, bool]:
        """
        Fetch Ceph storage nodes and their OSD statuses.
        This function processes Ceph data fetched from the Ceph OSD tree and the host status.
        """
        try:
            ceph_tree, ceph_hosts = cephHelper.fetch_ceph_data()
            if not ceph_tree or not ceph_hosts:
                return {}, False

            host_status_map: dict[str, str] = {}
            for host in ceph_hosts:
                if "hostname" in host and "status" in host:
                    host_status_map[host["hostname"]] = host["status"]

            final_output: cephNodesStatusResultType = {}
            failed_hosts: list[str] = []

            for item in ceph_tree.get("nodes", []):
                if "type" not in item or "name" not in item or item["type"] != "rack":
                    continue

                # rack_name = item["name"]

                storage_nodes: list[CephNodeStatusInfo] = []
                children = item.get("children")
                nodes = ceph_tree.get("nodes")
                if children is None or nodes is None:
                    continue

                for child_id in children:
                    host_node = next(
                        (x for x in nodes if x.get("id") == child_id),
                        None,
                    )
                    if not host_node:
                        continue

                    host_node_name = host_node.get("name", "")
                    if not (
                        host_node.get("type") == "host"
                        and host_node_name.startswith("ncn-s")
                    ):
                        continue

                    osd_ids = host_node.get("children", [])
                    ceph_nodes = ceph_tree.get("nodes")
                    osds = []
                    if ceph_nodes is not None and osd_ids is not None:
                        osds = [
                            osd
                            for osd in ceph_nodes
                            if osd.get("id") in osd_ids and osd.get("type") == "osd"
                        ]

                    osd_status_list: list[OSDStatusSchema] = []
                    for osd in osds:
                        osd_name = osd.get("name", "")
                        osd_status = osd["status"]
                        osd_status_list.append({"name": osd_name, "status": osd_status})

                    node_status = host_status_map.get(host_node_name, "No Status")
                    storage_node_status: Literal["Ready", "NotReady"]
                    if node_status in ["", "online"]:
                        storage_node_status = "Ready"
                    else:
                        failed_hosts.append(host_node_name)
                        logger.warning(
                            "Host %s is in - %s state",
                            host_node_name,
                            node_status,
                        )
                        storage_node_status = "NotReady"

                    storage_nodes.append(
                        {
                            "name": host_node_name,
                            "status": storage_node_status,
                            "osds": osd_status_list,
                        }
                    )

                final_output[item["name"]] = storage_nodes

            if failed_hosts:
                logger.warning(
                    "%d out of %d ceph nodes are not healthy",
                    len(failed_hosts),
                    len(ceph_hosts),
                )

            ceph_healthy = cephHelper.check_ceph_health()
            ceph_services_health = cephHelper.check_ceph_services()
            return final_output, ceph_healthy and ceph_services_health
        except Exception as e:
            logger.exception("Error occurred while processing CEPH status: %s", e)
            return {}, False


class k8sHelper:
    """
    Helper class to provide kubernetes related utility functions for the application.
    """

    @staticmethod
    def get_current_node() -> str:
        """Get the kubernetes node where the current RMS pod is running
        Returns:
            str: node name where pod is running."""
        try:
            ConfigMapHelper.load_k8s_config()
            v1 = client.CoreV1Api()
            pod_name = os.getenv("HOSTNAME")
            if not pod_name:
                logger.error("Environment variable HOSTNAME is not set")
                return ""
            pod = v1.read_namespaced_pod(name=pod_name, namespace=NAMESPACE)
            if pod.spec is None:
                return ""
            node_name: str = str(pod.spec.node_name) if pod.spec.node_name else ""
            return node_name
        except ApiException as e:
            logger.error("Kubernetes API error while fetching current pod: %s", e)
        except Exception as e:
            logger.exception("Unexpected error while retrieving current node: %s", e)
        return ""

    @staticmethod
    def getNodeMonitorGracePeriod() -> Optional[int]:
        """Get the nodeMonitorGracePeriod value from kube-controller-manager pod.
        Returns:
            int|None: getNodeMonitorGracePeriod value if present, otherwise None."""
        try:
            ConfigMapHelper.load_k8s_config()
            v1 = client.CoreV1Api()
            pods = v1.list_namespaced_pod(
                namespace="kube-system",
                label_selector="component=kube-controller-manager",
            )
            if not pods.items:
                logger.error("kube-controller-manager pod not found")
                return None
            first_pod = pods.items[0]
            if first_pod.spec is None or first_pod.spec.containers is None:
                return None
            command = first_pod.spec.containers[0].command
            if command is None:
                return None
            grace_period_flag = next(
                (arg for arg in command if "--node-monitor-grace-period" in arg), None
            )
            if grace_period_flag:
                grace_period_parts = grace_period_flag.split("=")
                if len(grace_period_parts) > 1:
                    nodeMonitorGracePeriod = grace_period_parts[1]
                    if nodeMonitorGracePeriod.endswith("s"):
                        return int(
                            nodeMonitorGracePeriod[:-1]
                        )  # Remove the 's' suffix indicating seconds
                    return int(nodeMonitorGracePeriod)
            logger.warning(
                "node-monitor-grace-period flag not found in kube-controller-manager pod"
            )
            return None

        except ApiException as e:
            logger.error(
                "Kubernetes API error while fetching kube-controller-manager pod: %s", e
            )
        except (IndexError, AttributeError, ValueError) as e:
            logger.error("Error parsing grace period from pod spec: %s", e)
        except Exception as e:
            logger.exception(
                "Unexpected error while retrieving node-monitor-grace-period: %s", e
            )
        return None

    @staticmethod
    def get_k8s_nodes() -> Optional[list[V1Node]]:
        """Retrieve all Kubernetes nodes
        Returns:
            Optional[list[V1Node]]:
                - A list of V1Node objects representing Kubernetes nodes if successful or None.
        """
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        try:
            nodes: list[V1Node] = v1.list_node().items
            return nodes
        except client.exceptions.ApiException as e:
            logger.exception("API error while fetching k8s nodes: %s ", str(e))
            return None
        except Exception as e:
            logger.exception("Unexpected error while fetching k8s nodes: %s ", str(e))
            return None

    @staticmethod
    def get_node_status(
        node_name: str, nodes: Optional[list[V1Node]]
    ) -> Literal["Ready", "NotReady", "Unknown"]:
        """
        Extract and return the status of a Kubernetes node
        Args:
            node_name (str): The name of the node to check.
            nodes (Optional[list[V1Node]]): list of V1Node objects to search. If None, fetches nodes via k8sHelper.
        Returns:
            Literal["Ready", "NotReady", "Unknown"]: Node readiness status.
        """
        try:
            if not nodes:
                nodes = k8sHelper.get_k8s_nodes()
                if not nodes:
                    logger.error("Failed to retrieve k8s nodes")
                    return "Unknown"

            for node in nodes:
                if node.metadata is not None and node.metadata.name == node_name:
                    # If the node has conditions, we check the last one
                    if node.status is not None and node.status.conditions:
                        status = node.status.conditions[-1].status
                        return "Ready" if status == "True" else "NotReady"
                    return "Unknown"
            logger.warning("Node %s not found in the node list", node_name)
            return "Unknown"
        except Exception as e:
            logger.exception(
                "Error while checking status for node %s: %s", node_name, e
            )
            return "Unknown"

    @staticmethod
    def get_k8s_nodes_data() -> Optional[k8sNodesResultType]:
        """
        Fetch Kubernetes nodes and organize them by topology zone.
        Returns:
            Optional[k8sNodesResultType]:
                - A dictionary organized by zone with 'masters' and 'workers' lists.
                - Returns None if nodes cannot be retrieved or no zone information is found.
        """
        try:
            nodes = k8sHelper.get_k8s_nodes()
            if not nodes:
                logger.debug("Failed to retrieve k8s nodes")
                return None

            zone_mapping: k8sNodesResultType = {}

            for node in nodes:
                if node.metadata is None:
                    continue
                node_name = node.metadata.name
                if node_name is None:
                    continue
                node_status = k8sHelper.get_node_status(node_name, nodes)
                if node.metadata.labels is None:
                    continue
                node_zone = node.metadata.labels.get("topology.kubernetes.io/zone")

                # Skip nodes without a zone label
                if not node_zone:
                    continue

                # Initialize the zone if it doesn't exist
                if node_zone not in zone_mapping:
                    zone_mapping[node_zone] = {"masters": [], "workers": []}

                # Classify nodes as master or worker based on name prefix
                if node_name.startswith("ncn-m"):
                    masters = zone_mapping[node_zone].get("masters", [])
                    masters.append({"name": node_name, "status": node_status})
                    zone_mapping[node_zone]["masters"] = masters
                elif node_name.startswith("ncn-w"):
                    workers = zone_mapping[node_zone].get("workers", [])
                    workers.append({"name": node_name, "status": node_status})
                    zone_mapping[node_zone]["workers"] = workers
            if zone_mapping:
                return zone_mapping
            logger.error("No K8s topology zone present")
            return None
        except Exception as e:
            logger.exception(
                "Unexpected error while building K8s node topology map: %s", e
            )
            return None

    @staticmethod
    def fetch_all_pods() -> Optional[podInfoType_list]:
        """
        Fetch all Kubernetes pods in a single API call and annotate them with their zone.
        Returns:
            Optional[podInfoType_list]
            Returns None on error or invalid node metadata.
        """
        try:
            ConfigMapHelper.load_k8s_config()
            v1 = client.CoreV1Api()
            nodes_data = k8sHelper.get_k8s_nodes_data()

            # Handle error cases
            if not nodes_data:
                logger.debug("Cannot fetch k8s node data or data format is not valid")
                return None

            node_zone_map = {}
            for zone, node_types in nodes_data.items():
                for node_type in ["masters", "workers"]:
                    node_list = node_types.get(node_type, [])
                    if not isinstance(node_list, list):
                        continue
                    valid_nodes = {node["name"]: zone for node in node_list}
                    node_zone_map.update(valid_nodes)

            all_pods = v1.list_pod_for_all_namespaces(watch=False).items
            pod_info: podInfoType_list = []

            for pod in all_pods:
                if pod.spec is None:
                    continue
                node_name = pod.spec.node_name
                if node_name is None:
                    continue
                zone = node_zone_map.get(node_name, "unknown")
                if pod.metadata is None:
                    continue
                pod_name = pod.metadata.name
                if pod_name is None:
                    continue
                pod_labels = pod.metadata.labels
                pod_info.append(
                    {
                        "Name": pod_name,
                        "Node": node_name,
                        "Zone": zone,
                        "labels": pod_labels if pod_labels is not None else {},
                    }
                )

            return pod_info
        except ApiException as e:
            logger.error("Kubernetes API error while fetching pods: %s", e)
        except Exception as e:
            logger.exception("Unexpected error while fetching pods: %s", e)
        return None


class criticalServicesHelper:
    """
    Helper class to provide utility functions related to critical services for the application.
    """

    @staticmethod
    def check_skew(service_name: str, pods: podInfoType_list) -> skewReturn:
        """
        Check whether pod replicas of a service are evenly distributed across zones.
        Args:
            service_name (str): Name of the service being evaluated.
            pods (podInfoType_list): list of pod metadata containing Zone, Node, and Name.
        Returns:
            skewReturn:
                - service-name: the name of the service
                - balanced: "true" or "false" depending on replica distribution
                - status: Indicates error if any
        """
        try:
            zone_pod_map: dict[str, dict[str, list[str]]] = {}

            for pod in pods:
                zone = pod.get("Zone")
                node = pod.get("Node")
                pod_name = pod.get("Name")

                if not zone or not node or not pod_name:
                    continue  # skip invalid pod entries
                zone_pod_map.setdefault(zone, {}).setdefault(node, []).append(pod_name)

            counts = [
                sum(len(pods) for pods in zone.values())
                for zone in zone_pod_map.values()
            ]

            balanced: Literal["true", "false"] = (
                "true" if max(counts) - min(counts) <= 1 else "false"
            )

        except Exception as e:
            logger.exception(
                "Error while checking skew for service %s: %s", service_name, e
            )
            return skewReturn(service_name=service_name, balanced="NA", error=True)

        return skewReturn(service_name=service_name, balanced=balanced)

    @staticmethod
    def get_service_status(
        service_name: str, service_namespace: str, service_type: str
    ) -> tuple[Optional[int], Optional[int], Optional[dict[str, str]]]:
        """
        Fetch the status of a Kubernetes service (Deployment, StatefulSet).
        Args:
            service_name (str): Name of the service.
            service_namespace (str): Namespace where the service is deployed.
            service_type (str): Type of the service ("Deployment", "StatefulSet").
        Returns:
            tuple:
                - desired replicas (int or None)
                - ready replicas (int or None)
                - label selector (dict or None)
        """
        try:
            ConfigMapHelper.load_k8s_config()
            apps_v1 = client.AppsV1Api()

            if service_type == "Deployment":
                deployment = apps_v1.read_namespaced_deployment(
                    service_name, service_namespace
                )
                if (
                    deployment.status is None
                    or deployment.spec is None
                    or deployment.spec.selector is None
                ):
                    return None, None, None
                return (
                    deployment.status.replicas,
                    deployment.status.ready_replicas,
                    deployment.spec.selector.match_labels,
                )
            if service_type == "StatefulSet":
                statefulset = apps_v1.read_namespaced_stateful_set(
                    service_name, service_namespace
                )
                if (
                    statefulset.status is None
                    or statefulset.spec is None
                    or statefulset.spec.selector is None
                ):
                    return None, None, None
                return (
                    statefulset.status.replicas,
                    statefulset.status.ready_replicas,
                    statefulset.spec.selector.match_labels,
                )
            logger.warning("Unsupported service type: %s", service_type)
            return None, None, None
        except client.exceptions.ApiException as e:
            match = re.search(r"Reason: (.*?)\n", str(e))
            error_message = match.group(1) if match else str(e)
            logger.error(
                "Error fetching %s %s: %s", service_type, service_name, error_message
            )
        except Exception as e:
            logger.exception(
                "Unexpected error while fetching %s '%s': %s",
                service_type,
                service_name,
                e,
            )
        return None, None, None

    @staticmethod
    def _filter_pods_by_labels(
        all_pods: podInfoType_list, labels: dict[str, str]
    ) -> podInfoType_list:
        """
        Filter pods based on matching labels.
        Args:
            all_pods (podInfoType_list): list of all pods
            labels (dict[str, str]): Labels to match against
        Returns:
            podInfoType_list: Filtered list of pods matching the labels
        """
        if not all_pods:
            return []

        filtered_pods = []
        for pod in all_pods:
            pod_labels = pod.get("labels")
            if not pod_labels:
                continue

            if all(pod_labels.get(key) == value for key, value in labels.items()):
                filtered_pods.append(pod)

        return filtered_pods

    @staticmethod
    def get_critical_services_status(
        services_data: CriticalServiceCmDynamicType,
    ) -> CriticalServiceCmDynamicType:
        """
        Update critical service info with status and balanced values
        Args:
            services_data (CriticalServiceCmType): The critical_services section from config.
        Returns:
            CriticalServiceCmType:
            Updated services_data with 'status' and 'balanced' flags added per service.
        """
        try:
            all_pods = k8sHelper.fetch_all_pods()
            if all_pods is None:
                logger.warning("Failed to fetch pods, returning original services data")
                return services_data

            critical_services = services_data["critical_services"]
            logger.info("Number of critical services are - %d", len(critical_services))
            imbalanced_services: list[str] = []
            unconfigured_services: list[str] = []
            partially_configured_services: list[str] = []

            for service_name, service_info in critical_services.items():
                service_namespace = service_info["namespace"]
                service_type = service_info["type"]
                desired_replicas, ready_replicas, labels = (
                    criticalServicesHelper.get_service_status(
                        service_name, service_namespace, service_type
                    )
                )

                if desired_replicas is None or ready_replicas is None or labels is None:
                    unconfigured_services.append(service_name)
                    service_info.update({"status": "Unconfigured", "balanced": "NA"})
                    continue

                if ready_replicas == 0:
                    unconfigured_services.append(service_name)
                    service_info.update({"status": "Unconfigured", "balanced": "NA"})
                    continue
                status: Literal[
                    "error",
                    "Configured",
                    "PartiallyConfigured",
                    "NotConfigured",
                    "Running",
                    "Unconfigured",
                ]
                status = "Configured"
                if ready_replicas < desired_replicas:
                    partially_configured_services.append(service_name)
                    status = "PartiallyConfigured"
                    logger.warning(
                        "%s '%s' in namespace '%s' is not ready. Only %d replicas are ready out of %d desired replicas",
                        service_type,
                        service_name,
                        service_namespace,
                        ready_replicas,
                        desired_replicas,
                    )
                elif ready_replicas == desired_replicas:
                    logger.debug(
                        "Desired replicas and ready replicas are matching for '%s'",
                        service_name,
                    )

                filtered_pods = criticalServicesHelper._filter_pods_by_labels(
                    all_pods, labels
                )
                balance_details = criticalServicesHelper.check_skew(
                    service_name, filtered_pods
                )
                if balance_details.error:
                    status = "error"

                if balance_details.balanced == "false":
                    imbalanced_services.append(service_name)

                service_info.update(
                    {
                        "status": status,
                        "balanced": balance_details.balanced,
                    }
                )

            if partially_configured_services:
                logger.warning(
                    "list of partially configured services are - %s",
                    partially_configured_services,
                )
            if imbalanced_services:
                logger.warning(
                    "list of imbalanced services are - %s", imbalanced_services
                )
            if unconfigured_services:
                logger.warning(
                    "list of unconfigured services are - %s", unconfigured_services
                )

            return services_data
        except Exception as e:
            logger.exception(
                "Unexpected error while updating critical service statuses: %s", e
            )
            return services_data  # Return original or partially updated data

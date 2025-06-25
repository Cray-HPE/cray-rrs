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
RRS Initialization and Zone Discovery Module

This module initializes the Rack Resiliency Service (RRS), retrieves node and zone
information for both Kubernetes and Ceph, and updates the dynamic configmap with
RRS metadata.
"""

import sys
from datetime import datetime
from collections import defaultdict
import logging
import json
import yaml
from src.lib.lib_rms import cephHelper, k8sHelper, Helper
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.schema import (
    cephNodesResultType,
    CriticalServiceCmStaticType,
    DynamicDataSchema,
    NodeSchema,
    RMSState,
)
from src.lib.rrs_constants import (
    NAMESPACE,
    DYNAMIC_CM,
    STATIC_CM,
    DYNAMIC_DATA_KEY,
    CRITICAL_SERVICE_KEY,
)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s in %(module)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

k8s_return_type = dict[str, list[NodeSchema]]


def check_previous_rrs_pod_node_status(pod_node: str, pod_zone: str) -> None:
    """
    Checks if the monitoring pod was previously running on a failed node
    Args:
        pod_node (str): The name of the node where the RRS pod was previously scheduled.
        pod_zone (str): The zone or rack associated with the pod's previous location.

    Returns:
        None
    """
    try:
        logger.info("Checking if previous running RMS pod was on the failed node")
        hsm_data, sls_data = Helper.get_hsm_sls_data(True, True)
        if not hsm_data or not sls_data:
            logger.error("Failed to retrieve HSM or SLS data")
            return
        Helper.check_failed_node(pod_node, pod_zone, sls_data, hsm_data)

    except Exception as e:
        logger.exception("Unexpected error occurred during pod location check: %s", e)


def zone_discovery() -> tuple[
    bool,
    k8s_return_type,
    cephNodesResultType,
]:
    """Retrieving zone information and status of k8s and Ceph nodes
    Returns:
        tuple containing:
            - A boolean indicating if discovery was successful.
            - A dict of updated k8s zone-node data.
            - A dict of updated Ceph zone-node data.
    """
    try:
        status = True
        updated_k8s_data: k8s_return_type = defaultdict(list)
        updated_ceph_data: cephNodesResultType = {}
        nodes = k8sHelper.get_k8s_nodes()
        logger.info("Retrieving zone information and status of k8s and CEPH nodes")

        if not nodes or not isinstance(nodes, list):
            logger.error("Failed to retrieve k8s nodes")
            return False, updated_k8s_data, updated_ceph_data

        for node in nodes:
            if not hasattr(node, "metadata") or node.metadata is None:
                logger.error("Invalid node object found without metadata")
                continue

            node_name = node.metadata.name
            if node_name is None:
                logger.error("Node has no name, skipping")
                continue

            if node.metadata.labels is None:
                logger.error("Node %s has no labels, skipping", node_name)
                continue

            zone = node.metadata.labels.get("topology.kubernetes.io/zone")
            if not zone:
                logger.error("Node %s does not have a zone marked for it", node_name)
                status = False
                updated_k8s_data = defaultdict(list)  # Reset the data
                break
            updated_k8s_data[zone].append(
                {
                    "status": k8sHelper.get_node_status(node_name, nodes),
                    "name": node_name,
                }
            )

        updated_k8s_data_dict = dict(updated_k8s_data)

        if status:
            updated_ceph_data, _ = cephHelper.get_ceph_status()
        return status, updated_k8s_data_dict, updated_ceph_data
    except Exception as e:
        logger.exception("Unexpected error occurred during zone discovery: %s", e)
        return False, {}, {}


def check_critical_services_and_timers() -> bool:
    """Validate if critical services and timers are present in RRS static configmap
    Returns:
        bool: True if all required configurations are present, False otherwise.
    """
    try:
        static_cm_data = ConfigMapHelper.read_configmap(NAMESPACE, STATIC_CM)
        if "error" in static_cm_data:
            logger.error(
                "Could not read static configmap %s: %s",
                STATIC_CM,
                static_cm_data["error"],
            )
            return False
        critical_svc = static_cm_data.get(CRITICAL_SERVICE_KEY, None)
        if critical_svc:
            services_data: CriticalServiceCmStaticType = json.loads(critical_svc)
            if not services_data["critical_services"]:
                logger.error(
                    "Critical services are not defined for Rack Resiliency Service"
                )
                return False
        else:
            logger.error(
                "%s not present in Rack Resiliency configmap", CRITICAL_SERVICE_KEY
            )
            return False

        k8s_delay_timer = static_cm_data.get("k8s_pre_monitoring_delay", None)
        k8s_polling_interval = static_cm_data.get(
            "k8s_monitoring_polling_interval", None
        )
        k8s_total_time = static_cm_data.get("k8s_monitoring_total_time", None)
        ceph_delay_timer = static_cm_data.get("ceph_pre_monitoring_delay", None)
        ceph_polling_interval = static_cm_data.get(
            "ceph_monitoring_polling_interval", None
        )
        ceph_total_time = static_cm_data.get("ceph_monitoring_total_time", None)
        if not all(
            [
                k8s_delay_timer,
                k8s_polling_interval,
                k8s_total_time,
                ceph_delay_timer,
                ceph_polling_interval,
                ceph_total_time,
            ]
        ):
            logger.warning(
                "One or all of expected timers for k8s and CEPH are not present in Rack Resiliency configmap. "
                "Default values would be used"
            )
        return True
    except json.JSONDecodeError as e:
        logger.error("Failed to parse %s: %s", CRITICAL_SERVICE_KEY, e)
        return False
    except Exception as e:
        logger.exception(
            "Unexpected error while checking critical services and timers: %s", e
        )
        return False


def init() -> None:
    """Initialize the Rack Resiliency Service (RRS)"""
    try:
        # Delete any stale configmap locks existing from previous runs
        ConfigMapHelper.release_lock(NAMESPACE, DYNAMIC_CM)
        ConfigMapHelper.release_lock(NAMESPACE, STATIC_CM)

        configmap_data = ConfigMapHelper.read_configmap(NAMESPACE, DYNAMIC_CM)
        if (
            not configmap_data
            or not isinstance(configmap_data, dict)
            or "error" in configmap_data
        ):
            logger.error(
                "Data is missing in configmap %s or not in expected format", DYNAMIC_CM
            )
            sys.exit(1)
        yaml_content = configmap_data.get(DYNAMIC_DATA_KEY, None)
        if yaml_content:
            dynamic_data: DynamicDataSchema = yaml.safe_load(yaml_content)
        else:
            logger.error(
                "No content found under %s in %s configmap",
                DYNAMIC_DATA_KEY,
                DYNAMIC_CM,
            )
            sys.exit(1)

        # update init timestamp in rrs-dynamic configmap
        timestamps = dynamic_data.get("timestamps", {})
        init_timestamp = timestamps.get("init_timestamp", None)
        state = dynamic_data["state"]
        rms_state = state.get("rms_state", None)
        if init_timestamp:
            logger.debug("Init time already present in configmap")
            logger.info(
                "Reinitializing the Rack Resiliency Service."
                "This could happen if previous RRS pod has been terminated"
            )
        if rms_state:
            logger.info("RMS is in %s state. Resetting to init state", rms_state)
            # Get the node and zone location of the previously running pod
            pod_zone = dynamic_data["cray_rrs_pod"]["zone"]
            pod_node = dynamic_data["cray_rrs_pod"]["node"]
            if pod_zone and pod_node:
                check_previous_rrs_pod_node_status(pod_node, pod_zone)
            if RMSState(rms_state) == RMSState.MONITORING:
                logger.info(
                    "Since the previous monitoring session did not complete, it will be relaunched in the RMS container"
                )
        state["rms_state"] = RMSState.INIT.value
        timestamps["init_timestamp"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        ConfigMapHelper.update_configmap_data(
            configmap_data,
            DYNAMIC_DATA_KEY,
            yaml.dump(dynamic_data, default_flow_style=False),
        )
        logger.debug("Updated init_timestamp and rms_state in %s configmap", DYNAMIC_CM)

        # Retrieve k8s and CEPH node/zone information and update in rrs-dynamic configmap
        discovery_status, updated_k8s_data, updated_ceph_data = zone_discovery()
        if discovery_status:
            zone_info = dynamic_data["zone"]
            zone_info["k8s_zones"] = updated_k8s_data
            zone_info["ceph_zones"] = updated_ceph_data

        # Retrieve current node and rack where the RMS pod is running
        node_name = k8sHelper.get_current_node()
        zone_name = None
        for rack, nodes_list in updated_k8s_data.items():
            for node in nodes_list:
                if node["name"] == node_name:
                    zone_name = rack
                    break
            if zone_name:
                break
        rack_name = Helper.get_rack_name_for_node(node_name)

        rrs_pod_placement = dynamic_data["cray_rrs_pod"]
        rrs_pod_placement["zone"] = zone_name
        rrs_pod_placement["node"] = node_name
        rrs_pod_placement["rack"] = rack_name
        logger.info(
            "RMS pod is running on node: %s in rack %s under zone %s",
            node_name,
            rack_name,
            zone_name,
        )

        if check_critical_services_and_timers() and discovery_status:
            state["rms_state"] = RMSState.READY.value
        else:
            logger.info(
                "Updating rms state to init_fail because of initialization failures"
            )
            # Normally we would set state["rms_state"] to RMSState.INIT_FAIL.value, but there
            # is no reason to do it here, because our next call is to sys.exit
            sys.exit(1)
        logger.debug(
            "Updating zone information, pod placement, state in rrs-dynamic configmap"
        )
        ConfigMapHelper.update_configmap_data(
            configmap_data,
            DYNAMIC_DATA_KEY,
            yaml.dump(dynamic_data, default_flow_style=False),
        )

    except KeyError as e:
        logger.exception("KeyError: Missing expected key in the configmap data - %s", e)
    except yaml.YAMLError as e:
        logger.exception("YAML parsing error occurred: %s", e)
    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)


if __name__ == "__main__":
    if not NAMESPACE or not DYNAMIC_CM or not STATIC_CM:
        logger.error(
            "One or more missing environment variables - NAMESPACE, DYNAMIC_CM, STATIC_CM"
        )
        sys.exit(1)
    init()

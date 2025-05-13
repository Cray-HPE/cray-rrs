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
from typing import Dict, List, Tuple, Any
import yaml
from src.rrs.rms.rms_statemanager import RMSStateManager
from src.lib.lib_rms import cephHelper, k8sHelper, Helper
from src.lib.lib_configmap import ConfigMapHelper

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

state_manager = RMSStateManager()


def _check_failed_node(
    pod_node: str,
    pod_zone: str,
    sls_data: List[Dict[str, Any]],
    filtered_data: List[Dict[str, Any]],
) -> None:
    for sls_entry in sls_data:
        aliases = sls_entry["ExtraProperties"]["Aliases"][0]
        if pod_node in aliases:
            for component in filtered_data:
                if sls_entry["Xname"] == component["ID"]:
                    rack_id = component["ID"].split("c")[
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


def check_pod_location() -> None:
    """Checks if the monitoring pod was previously running on a failed node"""

    logger.info("Checking if previous running RMS pod was on the failed node")
    hsm_data, sls_data = Helper.get_sls_hms_data()
    if not hsm_data or not sls_data:
        logger.error("Failed to retrieve HSM or SLS data")
        state_manager.set_state("internal_failure")
        return

    dynamic_cm_data = state_manager.get_dynamic_cm_data()
    yaml_content = dynamic_cm_data.get("dynamic-data.yaml", None)
    if yaml_content is None:
        logger.error("dynamic-data.yaml not found in the configmap")
        state_manager.set_state("internal_failure")
        return

    dynamic_data = yaml.safe_load(yaml_content)
    pod_zone = dynamic_data.get("rrs").get("zone")
    pod_node = dynamic_data.get("rrs").get("node")
    if not pod_zone or not pod_node:
        logger.error("zone or node information of the pod is missing in dynamic data")
        state_manager.set_state("internal_failure")
        return

    valid_subroles = {"Master", "Worker", "Storage"}
    filtered_data = [
        component
        for component in hsm_data.get("Components", [])
        if component.get("Role") == "Management"
        and component.get("SubRole") in valid_subroles
    ]
    _check_failed_node(pod_node, pod_zone, sls_data, filtered_data)


def zone_discovery() -> Tuple[bool, Dict[str, List[Dict[str, str]]], Dict[str, Any]]:
    """Retrieving zone information and status of k8s and CEPH nodes
    Returns:
        Tuple containing:
            - A boolean indicating if discovery was successful.
            - A dict of updated k8s zone-node data.
            - A dict of updated Ceph zone-node data.
    """
    status = True
    updated_k8s_data: defaultdict[str, List[Dict[str, str]]] = defaultdict(list)
    updated_ceph_data: Dict[str, Any] = {}
    nodes = k8sHelper.get_k8s_nodes()
    logger.info("Retrieving zone information and status of k8s and CEPH nodes")

    if not nodes or not isinstance(nodes, list):
        logger.error("Failed to retrieve valid k8s nodes")
        return False, {}, {}

    for node in nodes:
        if not hasattr(node, "metadata"):
            logger.error("Invalid node object found without metadata")
            continue

        node_name = node.metadata.name
        zone = node.metadata.labels.get("topology.kubernetes.io/zone")
        if not zone:
            logger.error("Node %s does not have a zone marked for it", node_name)
            status = False
            updated_k8s_data = defaultdict(list)  # Reset the data
            break
        updated_k8s_data[zone].append(
            {"Status": k8sHelper.get_node_status(node_name), "name": node_name}
        )

    updated_k8s_data_dict = dict(updated_k8s_data)

    if status:
        updated_ceph_data, _ = cephHelper.get_ceph_status()
    return status, updated_k8s_data_dict, updated_ceph_data


def check_critical_services_and_timers() -> bool:
    """Validate if critical services and timers are present in RRS static configmap
    Returns:
        bool: True if all required configurations are present, False otherwise.
    """
    static_cm_data = ConfigMapHelper.read_configmap(
        state_manager.namespace, state_manager.static_cm
    )
    critical_svc = static_cm_data.get("critical-service-config.json", None)
    if critical_svc:
        services_data = json.loads(critical_svc)
        if not services_data["critical-services"]:
            logger.error(
                "Critical services are not defined for Rack Resiliency Service"
            )
            return False
    else:
        logger.error(
            "critical-service-config.json not present in Rack Resiliency configmap"
        )
        return False

    k8s_delay_timer = static_cm_data.get("k8s_pre_monitoring_delay", None)
    k8s_polling_interval = static_cm_data.get("k8s_monitoring_polling_interval", None)
    k8s_total_time = static_cm_data.get("k8s_monitoring_total_time", None)
    ceph_delay_timer = static_cm_data.get("ceph_pre_monitoring_delay", None)
    ceph_polling_interval = static_cm_data.get("ceph_monitoring_polling_interval", None)
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
            "One or all of expected timers for k8s and CEPH are not present in Rack Resiliency configmap"
        )
    return True


def init() -> None:
    """Initialize the Rack Resiliency Service (RRS)."""
    configmap_data = ConfigMapHelper.read_configmap(
        state_manager.namespace, state_manager.dynamic_cm
    )
    try:
        yaml_content = configmap_data.get("dynamic-data.yaml", None)
        if yaml_content:
            dynamic_data = yaml.safe_load(yaml_content)
        else:
            logger.error(
                "No content found under dynamic-data.yaml in rrs-mon-dynamic configmap"
            )
            sys.exit(1)

        # update init timestamp in rrs-dynamic configmap
        timestamps = dynamic_data.get("timestamps", {})
        init_timestamp = timestamps.get("init_timestamp", None)
        state = dynamic_data.get("state", {})
        rms_state = state.get("rms_state", None)
        if init_timestamp:
            logger.debug("Init time already present in configmap")
            logger.info(
                "Reinitializing the Rack Resiliency Service."
                "This could happen if previous RRS pod has been terminated"
            )
        if rms_state:
            logger.info("RMS is in %s state. Resetting to init state", rms_state)
            if rms_state == "Monitoring":
                check_pod_location()
                logger.info(
                    "Since the previous monitoring session did not complete, it will be relaunched in the RMS container"
                )
        state["rms_state"] = "Init"
        timestamps["init_timestamp"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        ConfigMapHelper.update_configmap_data(
            state_manager.namespace,
            state_manager.dynamic_cm,
            configmap_data,
            "dynamic-data.yaml",
            yaml.dump(dynamic_data, default_flow_style=False),
        )
        logger.debug("Updated init_timestamp and rms_state in rrs-dynamic configmap")

        # Retrieve k8s and CEPH node/zone information and update in rrs-dynamic configmap
        zone_info = dynamic_data.get("zone", None)
        discovery_status, updated_k8s_data, updated_ceph_data = zone_discovery()
        if discovery_status:
            zone_info["k8s_zones_with_nodes"] = updated_k8s_data
            zone_info["ceph_zones_with_nodes"] = updated_ceph_data

        # Retrieve current node and rack where the RMS pod is running
        # node_name = "ncn-w004"
        node_name = k8sHelper.get_current_node()
        rack_name = next(
            (
                rack
                for rack, nodes in updated_k8s_data.items()
                if any(node["name"] == node_name for node in nodes)
            ),
            None,
        )

        rrs_pod_placement = dynamic_data.get("rrs", None)
        rrs_pod_placement["zone"] = rack_name
        rrs_pod_placement["node"] = node_name
        logger.info(
            "RMS pod is running on node: %s under zone %s", node_name, rack_name
        )

        if check_critical_services_and_timers() and discovery_status:
            state["rms_state"] = "Ready"
        else:
            logger.info("Updating rms state to init_fail due to above failures")
            state["rms_state"] = "init_fail"
            sys.exit(1)
        logger.debug(
            "Updating zone information, pod placement, state in rrs-dynamic configmap"
        )
        ConfigMapHelper.update_configmap_data(
            state_manager.namespace,
            state_manager.dynamic_cm,
            configmap_data,
            "dynamic-data.yaml",
            yaml.dump(dynamic_data, default_flow_style=False),
        )

    except KeyError as e:
        logger.error("KeyError: Missing expected key in the configmap data - %s", e)
    except yaml.YAMLError as e:
        logger.error("YAML parsing error occurred: %s", e)
    except Exception as e:
        logger.error("An unexpected error occurred: %s", e)


if __name__ == "__main__":
    init()

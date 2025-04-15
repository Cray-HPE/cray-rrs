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
from flask import Flask
import yaml
from src.rms.rms_statemanager import RMSStateManager
from src.lib.lib_rms import cephHelper, k8sHelper
from src.lib.lib_configmap import ConfigMapHelper

app = Flask(__name__)

# Logging setup
app.logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("app.log")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)

'''
logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
'''

state_manager = RMSStateManager()


def zone_discovery() -> Tuple[bool, Dict[str, List[Dict[str, str]]], Dict[str, Any]]:
    """Retrieving zone information and status of k8s and CEPH nodes
    Returns:
        Tuple containing:
            - A boolean indicating if discovery was successful.
            - A dict of updated k8s zone-node data.
            - A dict of updated Ceph zone-node data.
    """
    status = True
    updated_k8s_data = defaultdict(list)
    updated_ceph_data = {}
    nodes = k8sHelper.get_k8s_nodes()
    app.logger.info("Retrieving zone information and status of k8s and CEPH nodes")

    for node in nodes:
        node_name = node.metadata.name
        zone = node.metadata.labels.get("topology.kubernetes.io/zone")
        if not zone:
            app.logger.error("Node %s does not have a zone marked for it", node_name)
            status = False
            updated_k8s_data = {}
            break
        updated_k8s_data[zone].append(
            {"Status": k8sHelper.get_node_status(node_name), "name": node_name}
        )

    updated_k8s_data = dict(updated_k8s_data)

    if status:
        updated_ceph_data, _ = cephHelper.get_ceph_status()
    return status, updated_k8s_data, updated_ceph_data


def check_critical_services_and_timers() -> bool:
    """Validate if critical services and timers are present in RRS static configmap
    Returns:
        bool: True if all required configurations are present, False otherwise.
    """
    static_cm_data = ConfigMapHelper.get_configmap(
        state_manager.namespace, state_manager.static_cm
    )
    critical_svc = static_cm_data.get("critical-service-config.json", None)
    if critical_svc:
        services_data = json.loads(critical_svc)
        if not services_data["critical-services"]:
            app.logger.error(
                "Critical services are not defined for Rack Resiliency Service"
            )
            return False
    else:
        app.logger.error(
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
        app.logger.warning(
            "One or all of expected timers for k8s and CEPH are not present in Rack Resiliency configmap"
        )
    return True


def init() -> None:
    """Initialize the Rack Resiliency Service (RRS)."""
    configmap_data = ConfigMapHelper.get_configmap(
        state_manager.namespace, state_manager.dynamic_cm
    )
    try:
        yaml_content = configmap_data.get("dynamic-data.yaml", None)
        if yaml_content:
            dynamic_data = yaml.safe_load(yaml_content)
        else:
            app.logger.error(
                "No content found under dynamic-data.yaml in rrs-mon-dynamic configmap"
            )
            sys.exit(1)

        # update init timestamp in rrs-dynamic configmap
        timestamps = dynamic_data.get("timestamps", {})
        init_timestamp = timestamps.get("init_timestamp", None)
        state = dynamic_data.get("state", {})
        rms_state = state.get("rms_state", None)
        if init_timestamp:
            app.logger.debug("Init time already present in configmap")
            app.logger.info(
                "Reinitializing the Rack Resiliency Service. "
                "This could happen if previous RRS pod has terminated unexpectedly"
            )
        if not rms_state:
            state["rms_state"] = "Init"
        else:
            app.logger.debug("rms_state is already present in configmap")
            app.logger.info("RMS is already in %s state", rms_state)
        # check on condition here
        timestamps["init_timestamp"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        ConfigMapHelper.update_configmap_data(
            state_manager.namespace,
            state_manager.dynamic_cm,
            configmap_data,
            "dynamic-data.yaml",
            yaml.dump(dynamic_data, default_flow_style=False),
        )
        app.logger.debug(
            "Updated init_timestamp and rms_state in rrs-dynamic configmap"
        )

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
        app.logger.info(
            "RMS pod is running on node: %s under zone %s", node_name, rack_name
        )

        if check_critical_services_and_timers() and discovery_status:
            state["rms_state"] = "Ready"
        else:
            app.logger.info("Updating rms state to init_fail due to above failures")
            state["rms_state"] = "init_fail"
        app.logger.debug(
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
        app.logger.error("KeyError: Missing expected key in the configmap data - %s", e)
    except yaml.YAMLError as e:
        app.logger.error("YAML parsing error occurred: %s", e)
    except Exception as e:
        app.logger.error("An unexpected error occurred: %s", e)


if __name__ == "__main__":
    init()

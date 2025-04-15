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
RMS Monitoring Module

This module is responsible for monitoring Kubernetes and Ceph cluster health and
status using the RRS (Rack Resiliency Service) framework. It provides functionality
to update zone information, monitor critical service status, and orchestrate the
K8s and Ceph monitoring loops in separate threads.
"""

import time
import json
import copy
import threading
from flask import current_app as app
import yaml
from src.rms.rms_statemanager import RMSStateManager
from src.lib.lib_rms import Helper, cephHelper, k8sHelper, criticalServicesHelper
from src.lib.lib_configmap import ConfigMapHelper

# logger = logging.getlogger()


@staticmethod
def update_zone_status(state_manager: RMSStateManager) -> bool | None:
    """
    Update the zone information in the dynamic ConfigMap with the latest
    Kubernetes node statuses and Ceph health status.
    Args:
        state_manager (RMSStateManager): An instance of the RMS state manager used
        to fetch and update dynamic configmap data safely.

    Returns:
        bool | None: True if Ceph is healthy, False if unhealthy, or None if an error occurs.
    """
    app.logger.info("Getting latest status for zones and nodes")
    try:
        dynamic_cm_data = state_manager.get_dynamic_cm_data()
        yaml_content = dynamic_cm_data.get("dynamic-data.yaml", None)
        if yaml_content is None:
            app.logger.error("dynamic-data.yaml not found in the configmap")
            state_manager.set_state("internal_failure")
            return None
        dynamic_data = yaml.safe_load(yaml_content)
        zone_info = dynamic_data.get("zone")
        k8s_info = zone_info.get("k8s_zones_with_nodes")
        k8s_info_old = copy.deepcopy(k8s_info)

        for _, nodes in k8s_info.items():
            for node in nodes:
                node["Status"] = k8sHelper.get_node_status(node["name"])

        zone_info["k8s_zones_with_nodes"] = k8s_info

        ceph_info_old = zone_info.get("ceph_zones_with_nodes")
        updated_ceph_data, ceph_healthy_status = cephHelper.get_ceph_status()
        zone_info["ceph_zones_with_nodes"] = updated_ceph_data

        if k8s_info_old != k8s_info or ceph_info_old != updated_ceph_data:
            app.logger.info("Updating zone information in rrs-dynamic configmap")

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
        # return k8s_info, updated_ceph_data, ceph_healthy_status
        return ceph_healthy_status

    except KeyError as e:
        app.logger.error(f"Key error occurred: {e}")
        app.logger.error(
            "Ensure that 'zone' and 'k8s_zones_with_nodes' keys are present in the dynamic configmap data."
        )
        state_manager.set_state("internal_failure")
        return None
    except yaml.YAMLError as e:
        app.logger.error(f"YAML error occurred: {e}")
        state_manager.set_state("internal_failure")
        return None
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        state_manager.set_state("internal_failure")
        return None


@staticmethod
def update_critical_services(
    state_manager: RMSStateManager, reloading: bool = False
) -> str | None:
    """
    Update critical service status and configuration in the dynamic ConfigMap.
    Args:
        state_manager (RMSStateManager): State manager instance used to access and modify configmaps.
        reloading (bool, optional): If True, fetches the config from the static configmap instead of dynamic.
    Returns:
        str | None: A JSON-formatted string of the updated critical service configuration if successful,
        or None in case of failure
    """
    try:
        dynamic_cm_data = state_manager.get_dynamic_cm_data()
        if reloading:
            static_cm_data = ConfigMapHelper.get_configmap(
                state_manager.namespace, state_manager.static_cm
            )
            app.logger.info(
                "Retrieving critical services information from rrs-static configmap"
            )
            json_content = static_cm_data.get("critical-service-config.json", None)
            if json_content is None:
                app.logger.error(
                    "critical-service-config.json not found in the configmap"
                )
                state_manager.set_state("internal_failure")
                return None
        else:
            app.logger.info(
                "Retrieving critical services information from rrs-dynamic configmap"
            )
            json_content = dynamic_cm_data.get("critical-service-config.json", None)
            if json_content is None:
                app.logger.error(
                    "critical-service-config.json not found in the configmap"
                )
                state_manager.set_state("internal_failure")
                return None

        services_data = json.loads(json_content)
        updated_services = criticalServicesHelper.get_critical_services_status(
            services_data
        )
        services_json = json.dumps(updated_services, indent=2)
        app.logger.info(services_json)
        if services_json != dynamic_cm_data.get("critical-service-config.json", None):
            app.logger.debug(
                "critical services are modified. Updating dynamic configmap with latest information"
            )
            dynamic_cm_data["critical-service-config.json"] = services_json
            state_manager.set_dynamic_cm_data(dynamic_cm_data)
            ConfigMapHelper.update_configmap_data(
                state_manager.namespace,
                state_manager.dynamic_cm,
                dynamic_cm_data,
                "critical-service-config.json",
                services_json,
            )
        return services_json
    except json.JSONDecodeError:
        app.logger.error("Failed to decode critical-service-config.json from configmap")
        state_manager.set_state("internal_failure")
        return None
    except KeyError as e:
        app.logger.error(
            f"KeyError occurred: {str(e)} - Check if the configmap contains the expected keys"
        )
        state_manager.set_state("internal_failure")
        return None
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {str(e)}")
        state_manager.set_state("internal_failure")
        return None


class RMSMonitor:
    """
    RMSMonitor is responsible for monitoring Kubernetes and Ceph environments
    as part of the Rack Resiliency Service (RRS). It manages the coordination
    of monitoring loops for critical services and infrastructure health.
    """

    def __init__(self, state_manager: RMSStateManager) -> None:
        """
        Initialize the RMSMonitor with a reference to the state manager.
        Args:
            state_manager (RMSStateManager): The RMS state manager instance.
        """
        self.state_manager = state_manager

    def monitor_k8s(
        self, polling_interval: int, total_time: int, pre_delay: int
    ) -> None:
        """
        Monitor Kubernetes cluster status, focusing on critical service readiness and balance.
        This function updates the k8s monitoring state, polls service status at intervals,
        and logs any services that remain partially configured or imbalanced.
        """
        app.logger.info("Starting k8s monitoring")
        Helper.update_state_timestamp(
            self.state_manager,
            "k8s_monitoring",
            "Started",
            "start_timestamp_k8s_monitoring",
        )
        nodeMonitorGracePeriod = k8sHelper.getNodeMonitorGracePeriod()
        if nodeMonitorGracePeriod:
            time.sleep(nodeMonitorGracePeriod)
        else:
            time.sleep(pre_delay)
        start = time.time()
        while time.time() - start < total_time:
            # Retrieve and update critical services status
            latest_services_json = update_critical_services(self.state_manager)
            time.sleep(polling_interval)

        app.logger.info(f"Ending the k8s monitoring loop after {total_time} seconds")
        Helper.update_state_timestamp(
            self.state_manager,
            "k8s_monitoring",
            "Completed",
            "end_timestamp_k8s_monitoring",
        )

        if latest_services_json is None:
            app.logger.error("No services JSON data available to process")
            return

        try:
            services_data = json.loads(latest_services_json)
            unrecovered_services = []

            for service, details in services_data["critical-services"].items():
                if (
                    details["status"] == "PartiallyConfigured"
                    or details["balanced"] == "false"
                ):
                    unrecovered_services.append(service)

            if unrecovered_services:
                app.logger.error(
                    f"Services {unrecovered_services} are still not recovered even after {total_time} seconds"
                )
        except (json.JSONDecodeError, KeyError) as e:
            app.logger.error(f"Error processing services data: {e}")

    def monitor_ceph(
        self, polling_interval: int, total_time: int, pre_delay: int
    ) -> None:
        """Monitor Ceph storage system status, including health and zone node details."""
        app.logger.info("Starting CEPH monitoring")
        Helper.update_state_timestamp(
            self.state_manager,
            "ceph_monitoring",
            "Started",
            "start_timestamp_ceph_monitoring",
        )
        time.sleep(pre_delay)
        start = time.time()
        while time.time() - start < total_time:
            # Retrieve and update k8s/CEPH status and CEPH health
            ceph_health_status = update_zone_status(self.state_manager)
            time.sleep(polling_interval)

        Helper.update_state_timestamp(
            self.state_manager,
            "ceph_monitoring",
            "Completed",
            "end_timestamp_ceph_monitoring",
        )
        if ceph_health_status is False:
            app.logger.error(f"CEPH is still unhealthy after {total_time} seconds")

    def monitoring_loop(self) -> None:
        """Initiate monitoring of critical services and CEPH"""
        if not self.state_manager.start_monitoring():
            app.logger.warning(
                "Skipping launch of a new monitoring instance as a previous one is still active"
            )
            return  # Return early if the function is already running

        app.logger.info("Monitoring critical services and zone status...")
        state = "Monitoring"
        self.state_manager.set_state(state)
        Helper.update_state_timestamp(self.state_manager, "rms_state", state)
        # Read the 'rrs-mon' configmap and parse the data
        static_cm_data = ConfigMapHelper.get_configmap(
            self.state_manager.namespace, self.state_manager.static_cm
        )

        k8s_args = (
            int(static_cm_data.get("k8s_monitoring_polling_interval", 60)),
            int(static_cm_data.get("k8s_monitoring_total_time", 600)),
            int(static_cm_data.get("k8s_pre_monitoring_delay", 40)),
        )

        ceph_args = (
            int(static_cm_data.get("ceph_monitoring_polling_interval", 60)),
            int(static_cm_data.get("ceph_monitoring_total_time", 600)),
            int(static_cm_data.get("ceph_pre_monitoring_delay", 40)),
        )

        t1 = threading.Thread(target=self.monitor_k8s, args=k8s_args)
        t2 = threading.Thread(target=self.monitor_ceph, args=ceph_args)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        app.logger.info("Monitoring complete")
        self.state_manager.stop_monitoring()
        self.state_manager.set_state("Started")
        Helper.update_state_timestamp(self.state_manager, "rms_state", "Started")

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
from typing import List
from flask import Flask, current_app as app
import yaml
from src.rrs.rms.rms_statemanager import RMSStateManager
from src.lib.lib_rms import Helper, cephHelper, k8sHelper, criticalServicesHelper
from src.lib.lib_configmap import ConfigMapHelper

# logger = logging.getlogger()


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
            static_cm_data = ConfigMapHelper.read_configmap(
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

    def __init__(self, state_manager: RMSStateManager, app_arg: Flask) -> None:
        """
        Initialize the RMSMonitor with a reference to the state manager.
        Args:
            state_manager (RMSStateManager): The RMS state manager instance.
        """
        self.state_manager = state_manager
        self.app_arg = app_arg

    def monitor_k8s(
        self, polling_interval: int, total_time: int, pre_delay: int
    ) -> None:
        """
        Monitor Kubernetes cluster status, focusing on critical service readiness and balance.
        This function updates the k8s monitoring state, polls service status at intervals,
        and logs any services that remain partially configured or imbalanced.
        """
        with self.app_arg.app_context():
            nodeMonitorGracePeriod = k8sHelper.getNodeMonitorGracePeriod()
            if nodeMonitorGracePeriod:
                sleep_time = nodeMonitorGracePeriod
            else:
                sleep_time = pre_delay
            time.sleep(sleep_time)
            app.logger.info(
                f"Sleeping for {sleep_time} seconds before starting k8s monitoring"
            )
            Helper.update_state_timestamp(
                self.state_manager,
                "k8s_monitoring",
                "Started",
                "start_timestamp_k8s_monitoring",
            )
            start = time.time()
            latest_services_json = None
            unrecovered_services: List[str] = []
            while time.time() - start < total_time:
                app.logger.info("Checking k8s services")
                # Retrieve and update critical services status
                latest_services_json = update_critical_services(self.state_manager)

                try:
                    if latest_services_json:
                        services_data = json.loads(latest_services_json)
                        unrecovered_services = []

                        for service, details in services_data[
                            "critical-services"
                        ].items():
                            if (
                                details["status"] == "PartiallyConfigured"
                                or details["balanced"] == "false"
                            ):
                                unrecovered_services.append(service)
                    else:
                        app.logger.error(
                            "Services JSON data is not available to process"
                        )
                        return
                except (json.JSONDecodeError, KeyError) as e:
                    app.logger.error(f"Error processing services data: {e}")

                if not unrecovered_services:
                    app.logger.info(
                        f"Critical service became healthy after {time.time() - start} seconds. "
                        "Breaking the k8s monitoring loop"
                    )
                    break
                time.sleep(polling_interval)

            app.logger.info(
                f"Ending the k8s monitoring loop after {total_time} seconds"
            )
            Helper.update_state_timestamp(
                self.state_manager,
                "k8s_monitoring",
                "Completed",
                "end_timestamp_k8s_monitoring",
            )
            if unrecovered_services:
                app.logger.error(
                    f"Services {unrecovered_services} are still not recovered even after {total_time} seconds"
                )

    def monitor_ceph(
        self, polling_interval: int, total_time: int, pre_delay: int
    ) -> None:
        """Monitor Ceph storage system status, including health and zone node details."""
        with self.app_arg.app_context():
            app.logger.info(
                f"Sleeping for {pre_delay} seconds before starting CEPH monitoring"
            )
            time.sleep(pre_delay)
            Helper.update_state_timestamp(
                self.state_manager,
                "ceph_monitoring",
                "Started",
                "start_timestamp_ceph_monitoring",
            )
            start = time.time()
            while time.time() - start < total_time:
                app.logger.info("Checking CEPH")
                # Retrieve and update k8s/CEPH status and CEPH health
                ceph_health_status = update_zone_status(self.state_manager)
                if ceph_health_status:
                    app.logger.info(
                        f"CEPH became healthy after {time.time() - start} seconds. Breaking the CEPH monitoring loop"
                    )
                    break
                time.sleep(polling_interval)

            Helper.update_state_timestamp(
                self.state_manager,
                "ceph_monitoring",
                "Completed",
                "end_timestamp_ceph_monitoring",
            )
            if ceph_health_status is False:
                app.logger.error(f"CEPH is still unhealthy after {total_time} seconds")

    def check_running_monitoring_instance(self, monitoring_total_time: int) -> bool:
        """
        Check if another monitoring instance is running
        If it is, launch another instance only if it previous one passed 75% of its time
        Args:
            monitoring_total_time (int): Total monitoring time interval in seconds.
        Returns:
            bool:
                - True if a new monitoring instance should be launched (75% time passed).
                - False if a new instance should not be launched (less than 75% time passed).
        """
        dynamic_cm_data = ConfigMapHelper.read_configmap(
            self.state_manager.namespace, self.state_manager.dynamic_cm
        )
        yaml_content = dynamic_cm_data.get("dynamic-data.yaml", None)
        if yaml_content:
            dynamic_data = yaml.safe_load(yaml_content)
            monitor_k8s_start_time = dynamic_data.get("timestamps", {}).get(
                "start_timestamp_k8s_monitoring", None
            )
            if monitor_k8s_start_time:
                monitor_k8s_start_time = float(monitor_k8s_start_time)
                current_time = time.time()
                elapsed_time = current_time - monitor_k8s_start_time

                # Calculate percentage of interval completed
                percentage_completed = (elapsed_time / monitoring_total_time) * 100
                app.logger.info(
                    "Elapsed time since last monitoring instance start: %.2f seconds (%.2f%% completed)",
                    elapsed_time,
                    percentage_completed,
                )

                return bool(percentage_completed >= 75.0)
            app.logger.warning(
                "start_timestamp_k8s_monitoring not found in ConfigMap. Cannot determine elapsed time"
            )
            return False

        app.logger.error(
            "No content found under dynamic-data.yaml in rrs-mon-dynamic configmap"
        )
        return False

    def monitoring_loop(self) -> None:
        """Initiate monitoring of critical services and CEPH"""
        with self.app_arg.app_context():
            # Read the 'rrs-mon-static' configmap and parse the data
            static_cm_data = ConfigMapHelper.read_configmap(
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
                int(static_cm_data.get("ceph_pre_monitoring_delay", 60)),
            )

            if not self.state_manager.start_monitoring():
                app.logger.info("Another monitoring instance is already running")
                if not self.check_running_monitoring_instance(
                    int(static_cm_data.get("k8s_monitoring_total_time", 600))
                ):
                    app.logger.warning(
                        "Skipping launch of a new monitoring instance as a previous one is still active"
                    )
                    return
                app.logger.info(
                    "Launching new monitoring instance since "
                    "the previous one passed more than 75%% of monitoring interval"
                )

            app.logger.info("Monitoring critical services and zone status...")
            state = "Monitoring"
            self.state_manager.set_state(state)
            Helper.update_state_timestamp(self.state_manager, "rms_state", state)

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

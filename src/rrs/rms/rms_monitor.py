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
from datetime import datetime, timezone
import sys
import json
import copy
import threading
from logging import Logger
from typing import Optional
from flask import Flask, current_app as app
import yaml
from src.lib import lib_rms
from src.lib import lib_configmap
from src.rrs.rms.rms_statemanager import RMSStateManager, RMSState
from src.lib.lib_rms import Helper, cephHelper, k8sHelper, criticalServicesHelper
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.rrs_constants import (
    NAMESPACE,
    DYNAMIC_CM,
    STATIC_CM,
    DYNAMIC_DATA_KEY,
    CRITICAL_SERVICE_KEY,
    DEFAULT_K8S_MONITORING_POLLING_INTERVAL,
    DEFAULT_K8S_MONITORING_TOTAL_TIME,
    DEFAULT_K8S_PRE_MONITORING_DELAY,
    DEFAULT_CEPH_MONITORING_POLLING_INTERVAL,
    DEFAULT_CEPH_MONITORING_TOTAL_TIME,
    DEFAULT_CEPH_PRE_MONITORING_DELAY,
    STARTED_STATE,
    COMPLETED_STATE,
)


logger = None


def set_logger(custom_logger: Logger) -> None:
    """
    Sets a custom logger to be used globally within this module and propagates
    it to dependent modules for consistent logging across the system.
    Args:
        custom_logger (logging.Logger): A configured logger instance to override the default.
    """
    global logger
    logger = custom_logger
    lib_rms.set_logger(custom_logger)
    lib_configmap.set_logger(custom_logger)


def update_zone_status(state_manager: RMSStateManager) -> bool:
    """
    Update the zone information in the dynamic ConfigMap with the latest
    Kubernetes node statuses and Ceph health status.
    Args:
        state_manager (RMSStateManager): An instance of the RMS state manager used
        to fetch and update dynamic configmap data safely.
    Returns:
        bool: True if Ceph is healthy, False if unhealthy or if an error occurs.
    """
    app.logger.info("Getting latest status for zones and nodes")
    try:
        dynamic_cm_data = state_manager.get_dynamic_cm_data()
        yaml_content = dynamic_cm_data.get(DYNAMIC_DATA_KEY, None)
        if yaml_content is None:
            app.logger.error(f"{DYNAMIC_DATA_KEY} not found in the configmap")
            sys.exit(1)
        dynamic_data = yaml.safe_load(yaml_content)
        zone_info = dynamic_data[zone"]
        k8s_info = zone_info["k8s_zones"]
        k8s_info_old = copy.deepcopy(k8s_info)

        for _, nodes in k8s_info.items():
            for node in nodes:
                node["status"] = k8sHelper.get_node_status(node["name"], None)

        zone_info["k8s_zones"] = k8s_info
        ceph_info_old = zone_info.get("ceph_zones")
        ceph_info, ceph_healthy_status = cephHelper.get_ceph_status()
        zone_info["ceph_zones"] = ceph_info

        if k8s_info_old != k8s_info or ceph_info_old != ceph_info:
            app.logger.info(f"Updating zone information in {DYNAMIC_CM} configmap")

            dynamic_cm_data[DYNAMIC_DATA_KEY] = yaml.dump(
                dynamic_data, default_flow_style=False
            )
            state_manager.set_dynamic_cm_data(dynamic_cm_data)
            ConfigMapHelper.update_configmap_data(
                dynamic_cm_data,
                DYNAMIC_DATA_KEY,
                dynamic_cm_data[DYNAMIC_DATA_KEY],
            )
        else:
            app.logger.info(
                "No change in k8s or CEPH status and distribution. Nothing to do"
            )
        return ceph_healthy_status

    except KeyError as e:
        app.logger.error(f"Key error occurred: {e}")
        return False
    except yaml.YAMLError as e:
        app.logger.error(f"YAML error occurred: {e}")
        return False
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        return False


def update_critical_services(
    state_manager: RMSStateManager, reloading: bool = False
) -> Optional[str]:
    """
    Update critical service status and configuration in the dynamic ConfigMap.
    Args:
        state_manager (RMSStateManager): State manager instance used to access and modify configmaps.
        reloading (bool, optional): If True, fetches the config from the static configmap instead of dynamic.
    Returns:
        Optional[str]: A JSON-formatted string of the updated critical service configuration if successful,
        or None in case of failure
    """
    try:
        dynamic_cm_data = state_manager.get_dynamic_cm_data()
        if reloading:
            static_cm_data = ConfigMapHelper.read_configmap(NAMESPACE, STATIC_CM)
            app.logger.info(
                "Retrieving critical services information from rrs-static configmap"
            )
            json_content = static_cm_data.get(CRITICAL_SERVICE_KEY, None)
        else:
            app.logger.info(
                "Retrieving critical services information from rrs-dynamic configmap"
            )
            json_content = dynamic_cm_data.get(CRITICAL_SERVICE_KEY, None)
        if json_content is None:
            app.logger.error(f"{CRITICAL_SERVICE_KEY} not found in the configmap")
            sys.exit(1)

        services_data = json.loads(json_content)
        updated_services = criticalServicesHelper.get_critical_services_status(
            services_data
        )
        services_json = json.dumps(updated_services, indent=2)
        app.logger.debug(services_json)
        if services_json != dynamic_cm_data.get(CRITICAL_SERVICE_KEY, None):
            app.logger.debug(
                "critical services are modified. Updating dynamic configmap with latest information"
            )
            dynamic_cm_data[CRITICAL_SERVICE_KEY] = services_json
            state_manager.set_dynamic_cm_data(dynamic_cm_data)
            ConfigMapHelper.update_configmap_data(
                dynamic_cm_data,
                CRITICAL_SERVICE_KEY,
                services_json,
            )
        return services_json
    except json.JSONDecodeError:
        app.logger.error(f"Failed to decode {CRITICAL_SERVICE_KEY} from configmap")
        return None
    except KeyError as e:
        app.logger.error(
            f"KeyError occurred: {str(e)} - Check if the configmap contains the expected keys"
        )
        return None
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {str(e)}")
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
        Monitor Kubernetes node status, critical service readiness and balance.
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
                f"Waiting for {sleep_time} seconds before starting k8s monitoring"
            )
            Helper.update_state_timestamp(
                self.state_manager,
                "k8s_monitoring",
                STARTED_STATE,
                "start_timestamp_k8s_monitoring",
            )
            start = time.time()
            latest_services_json = None
            unrecovered_services: list[str] = []
            unconfigured_services: list[str] = []
            while time.time() - start < total_time:
                app.logger.info("Checking k8s services")
                # Retrieve and update critical services status
                latest_services_json = update_critical_services(self.state_manager)

                try:
                    if latest_services_json:
                        services_data = json.loads(latest_services_json)
                        unrecovered_services = []
                        unconfigured_services = []

                        for service, details in services_data[
                            "critical_services"
                        ].items():
                            if (
                                details["status"] == "PartiallyConfigured"
                                or details["balanced"] == "false"
                            ):
                                unrecovered_services.append(service)
                            elif details["status"] == "Unconfigured":
                                unconfigured_services.append(service)
                    else:
                        app.logger.critical(
                            "Services JSON data is not available to process"
                        )
                        sys.exit(1)
                except (json.JSONDecodeError, KeyError) as e:
                    app.logger.error(f"Error processing services data: {e}")

                if not unrecovered_services:
                    app.logger.info(
                        f"Critical services became healthy after {time.time() - start} seconds. "
                        "Completing k8s monitoring"
                    )
                    break
                time.sleep(polling_interval)

            app.logger.info(f"Ending k8s monitoring after {total_time} seconds")
            Helper.update_state_timestamp(
                self.state_manager,
                "k8s_monitoring",
                COMPLETED_STATE,
                "end_timestamp_k8s_monitoring",
            )
            if unrecovered_services:
                app.logger.error(
                    f"Services {unrecovered_services} are still not fully configured even after {total_time} seconds"
                )
            if unconfigured_services:
                app.logger.error(
                    f"Services {unconfigured_services} are not at all configured even after {total_time} seconds"
                )

    def monitor_ceph(
        self, polling_interval: int, total_time: int, pre_delay: int
    ) -> None:
        """Monitor Ceph storage system status, including health and zone node details."""
        with self.app_arg.app_context():
            app.logger.info(
                f"Waiting for {pre_delay} seconds before starting CEPH monitoring"
            )
            time.sleep(pre_delay)
            Helper.update_state_timestamp(
                self.state_manager,
                "ceph_monitoring",
                STARTED_STATE,
                "start_timestamp_ceph_monitoring",
            )
            start = time.time()
            ceph_health_status = False
            while time.time() - start < total_time:
                app.logger.info("Checking CEPH")
                # Retrieve and update k8s/CEPH status and CEPH health
                ceph_health_status = update_zone_status(self.state_manager)
                if ceph_health_status:
                    app.logger.info(
                        f"CEPH became healthy after {time.time() - start} seconds. Ending CEPH monitoring"
                    )
                    break
                time.sleep(polling_interval)

            Helper.update_state_timestamp(
                self.state_manager,
                "ceph_monitoring",
                COMPLETED_STATE,
                "end_timestamp_ceph_monitoring",
            )
            if ceph_health_status is False:
                app.logger.error(f"CEPH is still unhealthy after {total_time} seconds")

    def check_previous_monitoring_instance_status(
        self, monitoring_total_time: int
    ) -> bool:
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
        try:
            dynamic_cm_data = ConfigMapHelper.read_configmap(NAMESPACE, DYNAMIC_CM)
            yaml_content = dynamic_cm_data.get(DYNAMIC_DATA_KEY, None)
            if not yaml_content:
                app.logger.error(
                    f"No content found under {DYNAMIC_DATA_KEY} in rrs-mon-dynamic configmap"
                )
                sys.exit(1)
            dynamic_data = yaml.safe_load(yaml_content)
            monitor_k8s_start_time = dynamic_data.get("timestamps", {}).get(
                "start_timestamp_k8s_monitoring", None
            )
            if not monitor_k8s_start_time:
                app.logger.error(
                    "start_timestamp_k8s_monitoring not found in ConfigMap. Cannot determine elapsed time"
                )
                sys.exit(1)
            dt = datetime.strptime(monitor_k8s_start_time, "%Y-%m-%dT%H:%M:%SZ")
            dt = dt.replace(tzinfo=timezone.utc)
            monitor_k8s_start_time = dt.timestamp()
            current_time = time.time()
            elapsed_time = current_time - monitor_k8s_start_time

            # Calculate percentage of interval completed
            percentage_completed = (elapsed_time / monitoring_total_time) * 100
            app.logger.debug(
                "Elapsed time since last monitoring instance start: %.2f seconds (%.2f%% completed)",
                elapsed_time,
                percentage_completed,
            )
            return bool(percentage_completed >= 75.0)
        except Exception:
            app.logger.exception(
                "Error occurred while checking previous monitoring instance status"
            )
            return False

    def monitoring_loop(self) -> None:
        """Initiate monitoring of critical services and CEPH"""
        with self.app_arg.app_context():
            try:
                # Read the 'rrs-mon-static' configmap and parse the data
                static_cm_data = ConfigMapHelper.read_configmap(NAMESPACE, STATIC_CM)

                k8s_args = (
                    int(
                        static_cm_data.get(
                            "k8s_monitoring_polling_interval",
                            DEFAULT_K8S_MONITORING_POLLING_INTERVAL,
                        )
                    ),
                    int(
                        static_cm_data.get(
                            "k8s_monitoring_total_time",
                            DEFAULT_K8S_MONITORING_TOTAL_TIME,
                        )
                    ),
                    int(
                        static_cm_data.get(
                            "k8s_pre_monitoring_delay", DEFAULT_K8S_PRE_MONITORING_DELAY
                        )
                    ),
                )

                ceph_args = (
                    int(
                        static_cm_data.get(
                            "ceph_monitoring_polling_interval",
                            DEFAULT_CEPH_MONITORING_POLLING_INTERVAL,
                        )
                    ),
                    int(
                        static_cm_data.get(
                            "ceph_monitoring_total_time",
                            DEFAULT_CEPH_MONITORING_TOTAL_TIME,
                        )
                    ),
                    int(
                        static_cm_data.get(
                            "ceph_pre_monitoring_delay",
                            DEFAULT_CEPH_PRE_MONITORING_DELAY,
                        )
                    ),
                )

                if not self.state_manager.start_monitoring():
                    app.logger.warning("Another monitoring instance is already running")
                    if not self.check_previous_monitoring_instance_status(
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
                state = RMSState.MONITORING
                self.state_manager.set_state(state)
                Helper.update_state_timestamp(
                    self.state_manager, "rms_state", state.value
                )

                t1 = threading.Thread(
                    target=self.monitor_k8s, args=k8s_args, daemon=True
                )
                t2 = threading.Thread(
                    target=self.monitor_ceph, args=ceph_args, daemon=True
                )

                t1.start()
                t2.start()

                t1.join()
                t2.join()

                app.logger.info("Monitoring complete")
                self.state_manager.stop_monitoring()
                state = RMSState.STARTED
                self.state_manager.set_state(state)
                Helper.update_state_timestamp(
                    self.state_manager, "rms_state", state.value
                )
            except Exception:
                app.logger.exception("Unexpected error occurred during monitoring loop")

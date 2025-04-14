import time
import json
import logging
import yaml
import copy
import threading
from flask import current_app as app
from src.rms.rms_statemanager import RMSStateManager
from src.lib.lib_rms import Helper, cephHelper, k8sHelper, criticalServicesHelper
from src.lib.lib_configmap import ConfigMapHelper

# logger = logging.getlogger()


@staticmethod
def update_zone_status(state_manager: RMSStateManager) -> bool | None:
    app.logger.info("Getting latest status for zones and nodes")
    try:
        dynamic_cm_data = state_manager.get_dynamic_cm_data()
        yaml_content = dynamic_cm_data.get("dynamic-data.yaml", None)
        if yaml_content:
            dynamic_data = yaml.safe_load(yaml_content)
        else:
            app.logger.error(
                "No content found under dynamic-data.yaml in rrs-mon-dynamic configmap"
            )
            # exit(1)

        zone_info = dynamic_data.get("zone")
        k8s_info = zone_info.get("k8s_zones_with_nodes")
        k8s_info_old = copy.deepcopy(k8s_info)

        for zone, nodes in k8s_info.items():
            for node in nodes:
                node["Status"] = k8sHelper.get_node_status(node["name"])

        zone_info["k8s_zones_with_nodes"] = k8s_info

        ceph_info_old = zone_info.get("ceph_zones_with_nodes")
        updated_ceph_data, ceph_healthy_status = cephHelper.get_ceph_status()
        zone_info["ceph_zones_with_nodes"] = updated_ceph_data

        if k8s_info_old != k8s_info or ceph_info_old != updated_ceph_data:
            app.logger.info(f"Updating zone information in rrs-dynamic configmap")

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
    except yaml.YAMLError as e:
        app.logger.error(f"YAML error occurred: {e}")
        state_manager.set_state("internal_failure")
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        state_manager.set_state("internal_failure")


@staticmethod
def update_critical_services(
    state_manager: RMSStateManager, reloading: bool = False
) -> str | None:
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
        else:
            app.logger.info(
                "Retrieving critical services information from rrs-dynamic configmap"
            )
            json_content = dynamic_cm_data.get("critical-service-config.json", None)
        if json_content:
            services_data = json.loads(json_content)
        else:
            app.logger.error(
                "No content found under critical-service-config.json in rrs-mon configmap"
            )
            exit(1)

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
        return
    except KeyError as e:
        app.logger.error(
            f"KeyError occurred: {str(e)} - Check if the configmap contains the expected keys"
        )
        state_manager.set_state("internal_failure")
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {str(e)}")
        state_manager.set_state("internal_failure")


class RMSMonitor:
    def __init__(self, state_manager: RMSStateManager) -> None:
        self.state_manager = state_manager

    def monitor_k8s(
        self, polling_interval: int, total_time: int, pre_delay: int
    ) -> None:
        app.logger.info("Starting k8s monitoring")
        Helper.update_state_timestamp(
            "k8s_monitoring", "Started", "start_timestamp_k8s_monitoring"
        )
        nodeMonitorGracePeriod = k8sHelper.getNodeMonitorGracePeriod()
        if nodeMonitorGracePeriod:
            time.sleep(nodeMonitorGracePeriod)
        else:
            time.sleep(pre_delay)
        start = time.time()
        while time.time() - start < total_time:
            # Retrieve and update critical services status
            latest_services_json = update_critical_services()
            time.sleep(polling_interval)

        app.logger.info(f"Ending the k8s monitoring loop after {total_time} seconds")
        Helper.update_state_timestamp(
            "k8s_monitoring", "Completed", "end_timestamp_k8s_monitoring"
        )
        unrecovered_services = []
        for service, details in json.loads(latest_services_json)[
            "critical-services"
        ].items():
            if (
                details["status"] == "PartiallyConfigured"
                or details["balanced"] == "false"
            ):
                unrecovered_services.append(service)
        if unrecovered_services:
            app.logger.error(
                f"Services {unrecovered_services} are still not recovered even after {total_time} seconds"
            )

    def monitor_ceph(
        self, polling_interval: int, total_time: int, pre_delay: int
    ) -> None:
        app.logger.info("Starting CEPH monitoring")
        Helper.update_state_timestamp(
            "ceph_monitoring", "Started", "start_timestamp_ceph_monitoring"
        )
        time.sleep(pre_delay)
        start = time.time()
        while time.time() - start < total_time:
            # Retrieve and update k8s/CEPH status and CEPH health
            ceph_health_status = update_zone_status(self.state_manager)
            time.sleep(polling_interval)

        Helper.update_state_timestamp(
            "ceph_monitoring", "Completed", "end_timestamp_ceph_monitoring"
        )
        if ceph_health_status is False:
            app.logger.error(f"CEPH is still unhealthy after {total_time} seconds")

    def monitoring_loop(self) -> None:
        """Initiate monitoring critical services and CEPH"""
        if not self.state_manager.start_monitoring():
            app.logger.warn(
                f"Skipping launch of a new monitoring instance as a previous one is still active"
            )
            return  # Return early if the function is already running

        app.logger.info("Monitoring critical services and zone status...")
        state = "Monitoring"
        self.state_manager.set_state(state)
        Helper.update_state_timestamp("rms_state", state)
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
        Helper.update_state_timestamp("rms_state", "Started")

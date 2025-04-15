#!/usr/bin/python3
#
# MIT License
#
# (C) Copyright 2025 Hewlett Packard Enterprise Development LP
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
RMS Entry Point and Flask Service Handler

This module serves as the main entry point for the Rack Resiliency Service (RRS).
It initializes monitoring components, manages state transitions, and exposes a
Flask-based HTTP endpoint for handling State Change Notifications (SCNs) from HMNFD.
The module runs continuously and updates system state in a time-driven loop
to maintain rack-level resiliency awareness across the platform.
"""

import threading
import sys
import time
import logging
from datetime import datetime
import yaml
from flask import Flask, request, jsonify, Response
import requests
from src.rrs.rms.rms_statemanager import RMSStateManager
from src.lib.lib_rms import Helper
from src.lib.lib_configmap import ConfigMapHelper
from src.rrs.rms.rms_monitor import (
    RMSMonitor,
    update_zone_status,
    update_critical_services,
)

app = Flask(__name__)

# Logging setup
app.logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("app.log")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(threadName)s - %(message)s"
)
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)

# logging.basicConfig(
#     format="%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",  # Include thread name in logs
#     level=logging.INFO,
# )
# logger = logging.getlogger()

state_manager = RMSStateManager()
monitor = RMSMonitor(state_manager, app)


def check_failure_type(component_xname: str) -> None:
    """Check if it is a rack or node failure"""
    app.logger.info(
        "Checking failure type i.e., node or rack failure upon recieving SCN ..."
    )
    token = Helper.token_fetch()
    hsm_url = "https://api-gw-service-nmn.local/apis/smd/hsm/v2/State/Components"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        # Make the GET request to hsm endpoint
        hsm_response = requests.get(hsm_url, headers=headers, timeout=10)
        hsm_response.raise_for_status()
        hsm_data = hsm_response.json()

        valid_subroles = {"Master", "Worker", "Storage"}
        filtered_data = [
            component
            for component in hsm_data.get("Components", [])
            if component.get("Role") == "Management"
            and component.get("SubRole") in valid_subroles
        ]

        for component in filtered_data:
            if component["ID"] == component_xname:
                rack_id = component["ID"].split("c")[
                    0
                ]  # Extract "x3000" from "x3000c0s1b75n75"
                break

        # Extract the components with ID starting with rack_id
        rack_components = [
            {"ID": component["ID"], "State": component["State"]}
            # for component in hsm_data["Components"]
            for component in filtered_data
            if component["ID"].startswith(rack_id)
        ]

        rack_failure = True
        for component in rack_components:
            if component["State"] in ["On", "Ready", "Populated"]:
                rack_failure = False
            print(f"ID: {component['ID']}, State: {component['State']}")
        if rack_failure:
            app.logger.info(
                "All the components in the rack are not healthy. It is a RACK FAILURE"
            )
        else:
            app.logger.info(
                "Not all the components present in the rack are down. It is only a NODE FAILURE"
            )

        dynamic_cm_data = state_manager.get_dynamic_cm_data()
        yaml_content = dynamic_cm_data.get("dynamic-data.yaml", None)
        if yaml_content is None:
            app.logger.error("dynamic-data.yaml not found in the configmap")
            state_manager.set_state("internal_failure")
            return None
        dynamic_data = yaml.safe_load(yaml_content)
        pod_zone = dynamic_data.get("rrs").get("zone")
        # pod_node = dynamic_data.get("rrs").get("node")
        if rack_id in pod_zone:
            print("Monitoring pod was on the failed rack")
        return None
        # implement this

    except requests.exceptions.RequestException as e:
        app.logger.error("Request failed: %s", e)
        state_manager.set_state("internal_failure")
        return None
        # exit(1)
    except ValueError as e:
        app.logger.error("Failed to parse JSON: %s", e)
        state_manager.set_state("internal_failure")
        return None
        # exit(1)


@app.route("/scn", methods=["POST"])
def handleSCN() -> tuple[Response, int]:
    """Handle incoming POST requests and initiate monitoring"""
    app.logger.info("Notification received from HMNFD")
    state_manager.set_state("Fail_notified")
    # Get JSON data from request
    try:
        notification_json = request.get_json()
        app.logger.info("JSON data received: %s", notification_json)

        # Extract components and state
        components = notification_json.get("Components", [])
        state = notification_json.get("State", "")

        if not components or not state:
            app.logger.error("Missing 'Components' or 'State' in the request")
            return (
                jsonify({"error": "Missing 'Components' or 'State' in the request"}),
                400,
            )

        if state == "Off":
            for component in components:
                app.logger.info("Node %s is turned Off", component)
                check_failure_type(component)
            # Start monitoring services in a new thread
            threading.Thread(target=monitor.monitoring_loop).start()

        elif state == "On":
            for component in components:
                app.logger.info("Node %s is turned On", component)
            # Handle discovery of nodes
            # Handle cleanup or other actions here if needed

        else:
            app.logger.warning(
                "Unexpected state '%s' received for %s.", state, components
            )

        return jsonify({"message": "POST call received"}), 200

    except Exception as e:
        app.logger.error("Error processing the request: %s", e)
        state_manager.set_state("internal_failure")
        return jsonify({"error": "Internal server error."}), 500


def get_management_xnames() -> list[str] | None:
    """Get xnames for all the management nodes from HSM"""
    app.logger.info("Getting xnames for all the management nodes from HSM ...")
    token = Helper.token_fetch()
    hsm_url = "https://api-gw-service-nmn.local/apis/smd/hsm/v2/State/Components"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        # Make the GET request to hsm endpoint
        hsm_response = requests.get(hsm_url, headers=headers, timeout=10)
        hsm_response.raise_for_status()
        hsm_data = hsm_response.json()

        # Filter components with the given role and subroles
        valid_subroles = {"Master", "Worker", "Storage"}
        filtered_data = [
            component
            for component in hsm_data.get("Components", [])
            if component.get("Role") == "Management"
            and component.get("SubRole") in valid_subroles
        ]

        management_xnames = {component["ID"] for component in filtered_data}
        app.logger.info(list(management_xnames))
        return list(management_xnames)

    except requests.exceptions.RequestException as e:
        app.logger.error("Request failed: %s", e)
        state_manager.set_state("internal_failure")
        return None
        # exit(1)
    except ValueError as e:
        app.logger.error("Failed to parse JSON: %s", e)
        state_manager.set_state("internal_failure")
        return None
        # exit(1)


def check_and_create_hmnfd_subscription() -> None:
    """Create a subscription entry in hmnfd to recieve SCNs(state change notification) for the management components"""
    app.logger.info("Checking HMNFD subscription for SCN notifications ...")
    token = Helper.token_fetch()
    # subscriber_node = 'rack-resiliency'
    subscriber_node = "x3000c0s1b0n0"
    agent_name = "rms"

    get_url = "https://api-gw-service-nmn.local/apis/hmnfd/hmi/v2/subscriptions"
    post_url = f"https://api-gw-service-nmn.local/apis/hmnfd/hmi/v2/subscriptions/{subscriber_node}/agents/{agent_name}"

    subscribing_components = get_management_xnames()
    post_data = {
        "Components": subscribing_components,
        "Roles": ["Management"],
        "States": ["Ready", "on", "off", "empty", "unknown", "populated"],
        "Url": "http://10.102.193.27:3000/scn",
        # "Url": "https://api-gw-service-nmn.local/apis/rms/scn"
    }
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    try:
        get_response = requests.get(get_url, headers=headers, timeout=10)
        data = get_response.json()
        exists = any(
            "rms" in subscription["Subscriber"]
            for subscription in data["SubscriptionList"]
        )

        if not exists:
            app.logger.info(
                "rms not present in the HMNFD subscription list, creating it ..."
            )
            post_response = requests.post(
                post_url, json=post_data, headers=headers, timeout=10
            )
            post_response.raise_for_status()
            app.logger.info("Successfully subscribed to hmnfd for SCN notifications")
        else:
            app.logger.info("rms is already present in the subscription list")
    except requests.exceptions.RequestException as e:
        # Handle request errors (e.g., network issues, timeouts, non-2xx status codes)
        app.logger.error("Failed to make subscription request to hmnfd. Error: %s", e)
        state_manager.set_state("internal_failure")
        # exit(1)
    except ValueError as e:
        # Handle JSON parsing errors
        app.logger.error("Failed to parse JSON response: %s", e)
        state_manager.set_state("internal_failure")
        # exit(1)


def initial_check_and_update() -> bool:
    """Perform needed initialization checks and update configmap"""
    is_monitoring = False
    dynamic_cm_data = ConfigMapHelper.get_configmap(
        state_manager.namespace, state_manager.dynamic_cm
    )
    try:
        yaml_content = dynamic_cm_data.get("dynamic-data.yaml", None)
        if yaml_content:
            dynamic_data = yaml.safe_load(yaml_content)
        else:
            app.logger.error(
                "No content found under dynamic-data.yaml in rrs-mon-dynamic configmap"
            )
            sys.exit(1)

        state = dynamic_data.get("state", {})
        rms_state_value = state.get("rms_state", None)
        if rms_state_value != "Ready":
            app.logger.info("RMS state is %s", rms_state_value)
            if rms_state_value == "Monitoring":
                is_monitoring = True
            elif rms_state_value == "Init_fail":
                app.logger.error(
                    "RMS is in 'init_fail' state indicating init container failed — not starting the RMS service"
                )
                sys.exit(1)
            else:
                app.logger.info("Updating RMS state to Ready for this fresh run")
                rms_state_value = "Ready"
                state["rms_state"] = rms_state_value
                state_manager.set_state(rms_state_value)
        # Update RMS start timestamp in dynamic configmap
        timestamps = dynamic_data.get("timestamps", {})
        rms_start_timestamp = timestamps.get("start_timestamp_rms", None)
        if rms_start_timestamp:
            app.logger.debug("RMS start time already present in configmap")
            app.logger.info(
                "Rack Resiliency Monitoring Service is restarted because of a failure"
            )
        timestamps["start_timestamp_rms"] = datetime.now().strftime(
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
        app.logger.debug("Updated rms_start_timestamp in rrs-dynamic configmap")

    except ValueError as e:
        app.logger.error("Error during configuration check and update: %s", e)
        state_manager.set_state("internal_failure")
        # exit(1)
    except Exception as e:
        app.logger.error("Unexpected error: %s", e)
        state_manager.set_state("internal_failure")
        # exit(1)
    if is_monitoring:
        return True
    return False


def run_flask() -> None:
    """Run the Flask app in a separate thread for listening to HMNFD notifications"""
    app.logger.info(
        "Running flask on 3000 port on localhost to recieve notifications from HMNFD"
    )
    app.run(host="0.0.0.0", port=3000, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    with app.app_context():
        launch_monitoring = initial_check_and_update()
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.start()
        check_and_create_hmnfd_subscription()
        update_critical_services(state_manager, True)
        update_zone_status(state_manager)
        if launch_monitoring:
            app.logger.info(
                "RMS is in 'Monitoring' state - starting monitoring loop to resume previous incomplete process"
            )
            threading.Thread(target=monitor.monitoring_loop).start()
        time.sleep(600)
        while True:
            rms_state = "Started"
            state_manager.set_state(rms_state)
            Helper.update_state_timestamp(state_manager, "rms_state", rms_state)
            app.logger.info("Starting the main loop")
            check_and_create_hmnfd_subscription()
            update_critical_services(state_manager, True)
            update_zone_status(state_manager)
            rms_state = "Waiting"
            state_manager.set_state(rms_state)
            Helper.update_state_timestamp(state_manager, "rms_state", rms_state)
            time.sleep(600)

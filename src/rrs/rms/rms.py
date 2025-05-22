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
from typing import List, Tuple, Optional
from http import HTTPStatus
import yaml
from flask import Flask, request, jsonify, Response
from flask_restful import Api
import requests
from src.lib import lib_rms
from src.lib import lib_configmap
from src.rrs.rms import rms_monitor
from src.rrs.rms.rms_statemanager import RMSStateManager
from src.lib.lib_rms import Helper
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.rrs_constants import (
    NAMESPACE,
    DYNAMIC_CM,
    STATIC_CM,
    DYNAMIC_DATA_KEY,
    MAX_RETRIES,
    RETRY_DELAY,
    REQUESTS_TIMEOUT,
)
from src.lib.healthz import Ready, Live
from src.lib.version import Version
from src.rrs.rms.rms_monitor import (
    RMSMonitor,
    update_zone_status,
    update_critical_services,
)

app = Flask(__name__)
api = Api(app)

# Logging setup
app.logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
stream_handler.setFormatter(formatter)
app.logger.addHandler(stream_handler)

with app.app_context():
    lib_rms.set_logger(app.logger)
    lib_configmap.set_logger(app.logger)
    rms_monitor.set_logger(app.logger)

state_manager = RMSStateManager()
monitor = RMSMonitor(state_manager, app)


def check_failure_type(components: List[str]) -> None:
    """Check if it is a rack or node failure"""
    app.logger.debug(
        "Checking failure type i.e., node or rack failure upon recieving SCN ..."
    )
    hsm_data, _ = Helper.get_sls_hsm_data()
    if not hsm_data:
        app.logger.error("Failed to retrieve HSM data")
        state_manager.set_state("internal_failure")
        Helper.update_state_timestamp(state_manager, "rms_state", "internal_failure")
        return
    try:
        valid_subroles = {"Master", "Worker", "Storage"}
        filtered_data = [
            component
            for component in hsm_data.get("Components", [])
            if component.get("Role") == "Management"
            and component.get("SubRole") in valid_subroles
        ]
        for component_xname in components:
            app.logger.info("Node %s has failed", component_xname)
            rack_id = ""
            for component in filtered_data:
                if component["ID"] == component_xname:
                    rack_id = component["ID"].split("c")[
                        0
                    ]  # Extract "x3000" from "x3000c0s1b75n75"
                    break
            if not rack_id:
                app.logger.warning(
                    "No matching component found in HSM data for %s", component_xname
                )
                continue
            # Extract the components with ID starting with rack_id
            rack_components = [
                {"ID": component["ID"], "State": component["State"]}
                for component in filtered_data
                if component["ID"].startswith(rack_id)
            ]

            rack_failure = True
            for component in rack_components:
                if component["State"] in ["On", "Ready", "Populated"]:
                    rack_failure = False
                app.logger.debug(
                    "ID: %s, State: %s", component["ID"], component["State"]
                )
            if rack_failure:
                app.logger.info(
                    "All the nodes in the rack %s are not healthy - RACK FAILURE",
                    rack_id,
                )
            else:
                failed_nodes = [
                    c["ID"]
                    for c in rack_components
                    if c["State"] not in ["On", "Ready", "Populated"]
                ]
                app.logger.info(
                    "Some nodes in rack %s are down. Failed nodes: %s",
                    rack_id,
                    failed_nodes,
                )

    except (AttributeError, KeyError, IndexError, TypeError) as e:
        app.logger.error("Error occurred while checking rack failure: %s", e)
        state_manager.set_state("internal_failure")
        Helper.update_state_timestamp(state_manager, "rms_state", "internal_failure")


# Register healthz and version endpoints
api.add_resource(Ready, "/healthz/ready")
api.add_resource(Live, "/healthz/live")
api.add_resource(Version, "/version")


@app.route("/api-ts", methods=["POST"])
def update_api_timestamp() -> Tuple[str, int]:
    """
    Endpoint to update the API server start timestamp in dynamic configmap.
    Returns:
        Tuple[str, int]: A success message and HTTP status code.
    """
    app.logger.info("Request received from API server, updating API start timestamp")
    try:
        Helper.update_state_timestamp(
            state_manager, timestamp_field="start_timestamp_api"
        )
        return "API timestamp updated successfully", HTTPStatus.OK.value
    except Exception:
        app.logger.exception("Failed to update API timestamp")
        return "Failed to update API timestamp", HTTPStatus.INTERNAL_SERVER_ERROR


@app.route("/scn", methods=["POST"])
def handleSCN() -> Tuple[Response, int]:
    """
    Handle incoming POST requests from HMNFD (Hardware Management Notification Framework Daemon).
    This endpoint processes system component notifications and initiates monitoring accordingly.
    Returns:
        Tuple[Response, int]: A JSON response message and HTTP status code.
        - 200 for successful processing
        - 400 for bad requests (missing data)
        - 500 for internal server errors
    """
    app.logger.info("Notification received from HMNFD")
    try:
        notification_json = request.get_json()
        app.logger.debug("JSON data received: %s", notification_json)

        # Extract components and state
        components = notification_json.get("Components", [])
        comp_state = notification_json.get("State", "")

        if not components or not comp_state:
            app.logger.error("Missing 'Components' or 'State' in the request")
            return (
                jsonify({"error": "Missing 'Components' or 'State' in the request"}),
                HTTPStatus.BAD_REQUEST,
            )
        if comp_state == "Off":
            state_manager.set_state("Fail_notified")
            Helper.update_state_timestamp(state_manager, "rms_state", "Fail_notified")
            check_failure_type(components)
            # Start monitoring services in a new thread
            threading.Thread(target=monitor.monitoring_loop, daemon=True).start()

        elif comp_state == "On":
            for component in components:
                app.logger.info("Node %s is turned On", component)
            # Handle cleanup or other actions here if needed

        else:
            app.logger.warning(
                "Unexpected state '%s' received for %s.", comp_state, components
            )

        return jsonify({"message": "POST call received"}), HTTPStatus.OK.value

    except Exception as e:
        app.logger.error("Error processing the request: %s", e)
        state_manager.set_state("internal_failure")
        Helper.update_state_timestamp(state_manager, "rms_state", "internal_failure")
        return (
            jsonify({"error": "Internal server error."}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


def get_management_xnames() -> Optional[List[str]]:
    """Get xnames for all the management nodes from HSM"""
    app.logger.debug("Getting xnames for all the management nodes from HSM ...")
    hsm_data, _ = Helper.get_sls_hsm_data(True, False)
    if not hsm_data:
        app.logger.error("Failed to retrieve HSM data")
        return None
    try:
        # Filter components with the given role and subroles
        valid_subroles = ["Master", "Worker", "Storage"]
        filtered_data = [
            component
            for component in hsm_data.get("Components", [])
            if component.get("Role") == "Management"
            and component.get("SubRole") in valid_subroles
        ]
        management_xnames = {component["ID"] for component in filtered_data}
        app.logger.debug(list(management_xnames))
        return list(management_xnames)
    except (KeyError, TypeError, AttributeError) as e:
        app.logger.exception(
            "Error occurred while filtering management xnames from HSM data - %s",
            str(e),
        )
        state_manager.set_state("internal_failure")
        Helper.update_state_timestamp(state_manager, "rms_state", "internal_failure")
        return None


def check_and_create_hmnfd_subscription() -> None:
    """Create a subscription entry in hmnfd to recieve SCNs(state change notification) for the management components"""
    app.logger.info("Checking HMNFD subscription for SCN notifications ...")
    token = Helper.token_fetch()
    dynamic_cm_data = state_manager.get_dynamic_cm_data()
    yaml_content = dynamic_cm_data.get(DYNAMIC_DATA_KEY, None)
    if yaml_content is None:
        app.logger.error("%s not found in the configmap", DYNAMIC_DATA_KEY)
        return
    dynamic_data = yaml.safe_load(yaml_content)
    subscriber_node = dynamic_data.get("cray_rrs_pod").get("rack")
    agent_name = "rms"

    get_url = "https://api-gw-service-nmn.local/apis/hmnfd/hmi/v2/subscriptions"
    post_url = f"https://api-gw-service-nmn.local/apis/hmnfd/hmi/v2/subscriptions/{subscriber_node}/agents/{agent_name}"

    subscribing_components = get_management_xnames()
    if not subscribing_components:
        app.logger.error("Management xnames are empty or fetch failed")
        return
    post_data = {
        "Components": subscribing_components,
        "Roles": ["Management"],
        "States": ["Ready", "on", "off", "empty", "unknown", "populated"],
        "Url": "https://api-gw-service-nmn.local/apis/rms/scn",
    }
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            get_response = requests.get(
                get_url, headers=headers, timeout=REQUESTS_TIMEOUT, verify=False
            )
            get_response.raise_for_status()
            data = get_response.json()
            break  # GET succeeded
        except (requests.exceptions.RequestException, ValueError) as e:
            app.logger.error(
                "Attempt %s : Failed to fetch subscription list from hmnfd. Error: %s",
                attempt,
                e,
            )
            if attempt == MAX_RETRIES:
                app.logger.error("Max retries reached. Cannot fetch subscription list")
                state_manager.set_state("internal_failure")
                Helper.update_state_timestamp(
                    state_manager, "rms_state", "internal_failure"
                )
            time.sleep(RETRY_DELAY)

    # Check if rms exists in subscription
    exists = False
    if data:
        exists = any(
            "rms" in subscription.get("Subscriber", "")
            for subscription in data.get("SubscriptionList", [])
        )

    if not exists:
        app.logger.info(
            "rms not present in the HMNFD subscription list, creating it ..."
        )

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                post_response = requests.post(
                    post_url,
                    json=post_data,
                    headers=headers,
                    timeout=REQUESTS_TIMEOUT,
                    verify=False,
                )
                post_response.raise_for_status()
                app.logger.info(
                    "Successfully subscribed to hmnfd for SCN notifications"
                )
                break  # POST succeeded
            except requests.exceptions.RequestException as e:
                app.logger.error(
                    "Attempt %s : Failed to create subscription to hmnfd. Error: %s",
                    attempt,
                    e,
                )
                if attempt == MAX_RETRIES:
                    app.logger.error(
                        "Max retries reached. Cannot create subscription in hmnfd"
                    )
                    state_manager.set_state("internal_failure")
                    Helper.update_state_timestamp(
                        state_manager, "rms_state", "internal_failure"
                    )
                time.sleep(RETRY_DELAY)
    else:
        app.logger.info("rms is already present in the subscription list")


def initial_check_and_update() -> bool:
    """
    Perform needed initialization checks and update dynamic configmap
    Returns:
        bool:
            - True if unfinished monitoring instance was previously running
    """
    was_monitoring = False
    dynamic_cm_data = ConfigMapHelper.read_configmap(NAMESPACE, DYNAMIC_CM)
    try:
        yaml_content = dynamic_cm_data.get(DYNAMIC_DATA_KEY, None)
        if yaml_content:
            dynamic_data = yaml.safe_load(yaml_content)
        else:
            app.logger.error(
                "No content found under %s in rrs-mon-dynamic configmap",
                DYNAMIC_DATA_KEY,
            )
            sys.exit(1)

        state = dynamic_data.get("state", {})
        rms_state_value = state.get("rms_state", None)
        if rms_state_value != "Ready":
            app.logger.info("RMS state is %s", rms_state_value)
            k8s_state = state.get("k8s_monitoring", None)
            ceph_state = state.get("ceph_monitoring", None)
            # If either of k8s_monitoring, ceph_monitoring is in 'Started' state instead of empty or 'Completed',
            # it means monitoring was not finished in the previous run.
            if k8s_state == "Started" or ceph_state == "Started":
                was_monitoring = True
            elif rms_state_value == "Init_fail":
                app.logger.error(
                    "RMS is in 'init_fail' state as init container failed — not starting the RMS service"
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
            app.logger.debug(
                "RMS start time already present in configmap - %s", rms_start_timestamp
            )
            app.logger.info(
                "Rack Resiliency Monitoring Service is restarted post failure"
            )
        timestamps["start_timestamp_rms"] = datetime.now().strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        dynamic_cm_data[DYNAMIC_DATA_KEY] = yaml.dump(
            dynamic_data, default_flow_style=False
        )
        state_manager.set_dynamic_cm_data(dynamic_cm_data)
        ConfigMapHelper.update_configmap_data(
            dynamic_cm_data,
            DYNAMIC_DATA_KEY,
            dynamic_cm_data[DYNAMIC_DATA_KEY],
        )
        app.logger.debug("Updated rms_start_timestamp in rrs-dynamic configmap")

    except ValueError as e:
        app.logger.error("Error during configuration check and update: %s", e)
    except Exception as e:
        app.logger.error("Unexpected error: %s", e)
    return was_monitoring


def run_flask() -> None:
    """Run the Flask app in a separate thread for listening to HMNFD notifications"""
    app.logger.info(
        "Running flask on 8551 port on localhost to recieve notifications from HMNFD"
    )
    app.run(host="0.0.0.0", port=8551, threaded=True, debug=False)


if __name__ == "__main__":
    # Main entry point for the RMS service.
    # This block performs the following steps within the Flask application context:

    # 1. Performs initial checks and also determine whether a monitoring loop needs to be resumed.
    # 2. If RMS was previously in a 'Monitoring' state, resumes the monitoring loop in the background.
    # 3. Starts the Flask application server in a separate thread.
    # 4. Ensures HMNFD subscriptions are in place.
    # 5. Periodically updates critical service and zone status if monitoring is not actively running.
    # 6. Continuously manages RMS state transitions (`Waiting`, `Started`, `Monitoring`) based on current activity.

    # The loop runs indefinitely - checking HMNFD subscription, critical services and CEPH status every 600 seconds.

    with app.app_context():
        if not NAMESPACE or not DYNAMIC_CM or not STATIC_CM:
            app.logger.error(
                "One or more missing environment variables - namespace, static configmap, dynamic configmap"
            )
            sys.exit(1)
        launch_monitoring = initial_check_and_update()
        # check daemon=True
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        check_and_create_hmnfd_subscription()
        if launch_monitoring:
            app.logger.info(
                "RMS was in 'Monitoring' state - starting monitoring loop to resume previous incomplete process"
            )
            threading.Thread(target=monitor.monitoring_loop, daemon=True).start()
        update_critical_services(state_manager, True)
        update_zone_status(state_manager)
        app.logger.info("Starting the main loop")
        while True:
            if state_manager.get_state() != "monitoring":
                rms_state = "Waiting"
                state_manager.set_state(rms_state)
                Helper.update_state_timestamp(state_manager, "rms_state", rms_state)
                time.sleep(600)
                if state_manager.get_state() == "monitoring":
                    continue
                rms_state = "Started"
                state_manager.set_state(rms_state)
                Helper.update_state_timestamp(state_manager, "rms_state", rms_state)
                check_and_create_hmnfd_subscription()
                update_critical_services(state_manager, True)
                update_zone_status(state_manager)
            else:
                app.logger.info("Not running main loop as monitoring is running")
                time.sleep(600)
                # Development for future scope

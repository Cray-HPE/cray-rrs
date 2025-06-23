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
import subprocess
import signal
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Optional, Literal, cast
from http import HTTPStatus
import yaml
from flask import Flask, request, jsonify, Response
from flask_restful import Api
import requests
import urllib3
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
    STARTED_STATE,
    MAIN_LOOP_WAIT_TIME_INTERVAL,
)
from src.lib.schema import (
    hmnfdNotificationPost,
    hmnfdSubscribePostV2,
    hmnfdSubscriptionListArray,
    SCNSuccessResponse,
    SCNBadRequestResponse,
    SCNInternalServerErrorResponse,
    ApiTimestampSuccessResponse,
    ApiTimestampFailedResponse,
    DynamicDataSchema,
    RMSState,
    HMNFD_STATES,
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

# Production configuration
app.config.update(
    DEBUG=False,
    TESTING=False,
)

# Logging setup
if app.logger.hasHandlers():
    app.logger.handlers.clear()
app.logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s in %(module)s - %(message)s")
stream_handler.setFormatter(formatter)
app.logger.addHandler(stream_handler)

with app.app_context():
    lib_rms.set_logger(app.logger)
    lib_configmap.set_logger(app.logger)
    rms_monitor.set_logger(app.logger)

state_manager = RMSStateManager()
monitor = RMSMonitor(state_manager, app)

# Global variable to store the Gunicorn process
gunicorn_process: Optional[subprocess.Popen[str]] = None

# Until certificates are being used to talk to Redfish endpoints the basic
# auth method will be used. To do so, SSL verification needs to be turned
# off  which results in a InsecureRequestWarning. The following line
# disables only the InsecureRequestWarning.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def check_failure_type(components: list[str]) -> None:
    """Check if it is a rack or node failure"""
    app.logger.debug(
        "Checking failure type i.e., node or rack failure upon recieving SCN ..."
    )
    hsm_data, _ = Helper.get_hsm_sls_data(True, False)
    if not hsm_data:
        app.logger.error("Failed to retrieve HSM data")
        state_manager.set_state(RMSState.INTERNAL_FAILURE)
        Helper.update_state_timestamp(
            state_manager, "rms_state", RMSState.INTERNAL_FAILURE.value
        )
        return
    try:
        for component_xname in components:
            app.logger.info("Node %s has failed", component_xname)
            rack_id = ""
            for component in hsm_data.get("Components", []):
                comp_id = component["ID"]
                if comp_id == component_xname:
                    rack_id = comp_id.split("c")[
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
                for component in hsm_data.get("Components", [])
                if (comp_id := component["ID"]) and comp_id.startswith(rack_id)
            ]

            rack_failure = True
            for comp in rack_components:
                if comp["State"] in ["On", "Ready", "Populated"]:
                    rack_failure = False
                app.logger.debug("ID: %s, State: %s", comp["ID"], comp["State"])
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
        state_manager.set_state(RMSState.INTERNAL_FAILURE)
        Helper.update_state_timestamp(
            state_manager, "rms_state", RMSState.INTERNAL_FAILURE.value
        )


# Register healthz and version endpoints
api.add_resource(Ready, "/healthz/ready")
api.add_resource(Live, "/healthz/live")
api.add_resource(Version, "/version")


def jsonify_response[**P, T1, T2](
    func: Callable[P, tuple[T1, T2]],
) -> Callable[P, tuple[Response, T2]]:
    """
    Decorator for functions that return a tuple of 2 values.
    Calls jsonify() on the first value, and leaves the second unchanged.
    This allows the endpoint functions to have meaningful type signatures but still use jsonify for
    their responses.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> tuple[Response, T2]:
        """
        Calls the wrapper function with the specified arguments.
        Calls jsonify() on the first value, and leaves the second unchanged.
        Returns the resulting tuple.
        """
        a, b = func(*args, **kwargs)
        return jsonify(a), b

    return wrapper


@app.route("/api-ts", methods=["POST"])
@jsonify_response
def update_api_timestamp() -> (
    tuple[ApiTimestampSuccessResponse, Literal[HTTPStatus.OK]]
    | tuple[ApiTimestampFailedResponse, Literal[HTTPStatus.INTERNAL_SERVER_ERROR]]
):
    """
    RMS OAS: #/paths/api-ts (post)

    Endpoint to update the API server start timestamp in dynamic configmap.
    Returns:
        tuple[str, int]: A success message and HTTP status code.
    """
    app.logger.info("Request received from API server, updating API start timestamp")
    try:
        Helper.update_state_timestamp(
            state_manager, timestamp_field="start_timestamp_api"
        )
        return (
            ApiTimestampSuccessResponse(message="API timestamp updated successfully"),
            HTTPStatus.OK,
        )
    except Exception:
        app.logger.exception("Failed to update API timestamp")
        return (
            ApiTimestampFailedResponse(error="Failed to update API timestamp"),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


@app.route("/scn", methods=["POST"])
@jsonify_response
def handleSCN() -> (
    tuple[SCNSuccessResponse, Literal[HTTPStatus.OK]]
    | tuple[SCNBadRequestResponse, Literal[HTTPStatus.BAD_REQUEST]]
    | tuple[SCNInternalServerErrorResponse, Literal[HTTPStatus.INTERNAL_SERVER_ERROR]]
):
    """
    RMS OAS: #/paths/scn (post)

    Handle incoming POST requests from HMNFD (Hardware Management Notification Framework Daemon).
    This endpoint processes system component notifications and initiates monitoring accordingly.
    Returns:
        tuple[Response, int]: A JSON response message and HTTP status code.
        - 200 for successful processing
        - 400 for bad requests (missing data)
        - 500 for internal server errors
    """
    app.logger.info("Notification received from HMNFD")
    try:
        notification_json: hmnfdNotificationPost = request.get_json()
        app.logger.debug("JSON data received: %s", notification_json)

        # Extract components and state
        components = notification_json["Components"]
        comp_state = notification_json.get("State", "")

        if not components or not comp_state:
            app.logger.error("Missing 'Components' or 'State' in the request")
            return (
                SCNBadRequestResponse(
                    error="Missing 'Components' or 'State' in the request"
                ),
                HTTPStatus.BAD_REQUEST,
            )
        if comp_state in ("Off", "Standby"):
            app.logger.warning(
                "Components '%s' are changed to %s state.", components, comp_state
            )
            state_manager.set_state(RMSState.FAIL_NOTIFIED)
            Helper.update_state_timestamp(
                state_manager, "rms_state", RMSState.FAIL_NOTIFIED.value
            )
            check_failure_type(components)
            # Start monitoring services in a new thread
            threading.Thread(target=monitor.monitoring_loop, daemon=True).start()

        elif comp_state == "On":
            for component in components:
                app.logger.info("Node %s is turned On", component)
            # Handle cleanup or other actions here if needed

        else:
            app.logger.warning("state '%s' received for %s.", comp_state, components)

        return SCNSuccessResponse(message="POST call received"), HTTPStatus.OK

    except Exception as e:
        app.logger.error("Error processing the request: %s: %s", type(e).__name__, e)
        state_manager.set_state(RMSState.INTERNAL_FAILURE)
        Helper.update_state_timestamp(
            state_manager, "rms_state", RMSState.INTERNAL_FAILURE.value
        )
        return (
            SCNInternalServerErrorResponse(error="Internal server error"),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


def get_management_xnames() -> Optional[list[str]]:
    """Get xnames for all the management nodes from HSM"""
    app.logger.debug("Getting xnames for all the management nodes from HSM ...")
    hsm_data, _ = Helper.get_hsm_sls_data(True, False)
    if not hsm_data:
        app.logger.error("Failed to retrieve HSM data")
        return None
    try:
        management_xnames = {
            component["ID"] for component in hsm_data.get("Components", [])
        }
        app.logger.debug(list(management_xnames))
        return list(management_xnames)
    except (KeyError, TypeError, AttributeError) as e:
        app.logger.exception(
            "Error occurred while filtering management xnames from HSM data - %s",
            str(e),
        )
        state_manager.set_state(RMSState.INTERNAL_FAILURE)
        Helper.update_state_timestamp(
            state_manager, "rms_state", RMSState.INTERNAL_FAILURE.value
        )
        return None


def check_and_create_hmnfd_subscription() -> None:
    """Create a subscription entry in hmnfd to recieve SCNs(state change notification) for the management components"""
    app.logger.info("Checking HMNFD subscription for SCN notifications ...")
    try:
        token = Helper.token_fetch()
        dynamic_cm_data = state_manager.get_dynamic_cm_data()
        yaml_content = dynamic_cm_data.get(DYNAMIC_DATA_KEY, None)
        if yaml_content is None:
            app.logger.error("%s not found in the configmap", DYNAMIC_DATA_KEY)
            return
        dynamic_data: DynamicDataSchema = yaml.safe_load(yaml_content)
        cray_rrs_pod = dynamic_data["cray_rrs_pod"]
        if cray_rrs_pod is None:
            app.logger.error("cray_rrs_pod not found in dynamic data")
            return
        subscriber_node = cray_rrs_pod["rack"]

    except KeyError as e:
        app.logger.error("Missing key in dynamic data: %s", e)
    except yaml.YAMLError as e:
        app.logger.error("Error parsing YAML content: %s", e)
    except Exception as e:
        app.logger.error("An unexpected error occurred: %s", e)

    agent_name = "rms"
    get_url = "https://api-gw-service-nmn.local/apis/hmnfd/hmi/v2/subscriptions"
    post_url = f"https://api-gw-service-nmn.local/apis/hmnfd/hmi/v2/subscriptions/{subscriber_node}/agents/{agent_name}"

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data: hmnfdSubscriptionListArray | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            get_response = requests.get(
                get_url, headers=headers, timeout=REQUESTS_TIMEOUT, verify=False
            )
            get_response.raise_for_status()
            data = cast(hmnfdSubscriptionListArray, get_response.json())
            break  # GET succeeded
        except (requests.exceptions.RequestException, ValueError) as e:
            app.logger.error(
                "Attempt %s : Failed to fetch subscription list from hmnfd. Error: %s",
                attempt,
                e,
            )
            if attempt == MAX_RETRIES:
                app.logger.error("Max retries reached. Cannot fetch subscription list")
                state_manager.set_state(RMSState.INTERNAL_FAILURE)
                Helper.update_state_timestamp(
                    state_manager, "rms_state", RMSState.INTERNAL_FAILURE.value
                )
            time.sleep(RETRY_DELAY)

    # Check if rms exists in subscription
    exists = False
    if data:
        exists = any(
            "rms" == subscription.get("SubscriberAgent", "")
            for subscription in data.get("SubscriptionList", [])
        )

    if not exists:
        app.logger.info(
            "rms not present in the HMNFD subscription list, creating it ..."
        )
        subscribing_components = get_management_xnames()
        if not subscribing_components:
            app.logger.error("Management xnames are empty or fetch failed")
            return
        for attempt in range(1, MAX_RETRIES + 1):
            post_data: hmnfdSubscribePostV2 = {
                "Components": subscribing_components,
                "States": list(HMNFD_STATES),
                "Enabled": True,
                "Url": "http://cray-rrs-rms.rack-resiliency.svc.cluster.local:8551/scn",
            }
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
                    state_manager.set_state(RMSState.INTERNAL_FAILURE)
                    Helper.update_state_timestamp(
                        state_manager, "rms_state", RMSState.INTERNAL_FAILURE.value
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
            dynamic_data: DynamicDataSchema = yaml.safe_load(yaml_content)
        else:
            app.logger.error(
                "No content found under %s in rrs-mon-dynamic configmap",
                DYNAMIC_DATA_KEY,
            )
            sys.exit(1)

        state = dynamic_data.get("state", {})
        rms_state_value = state.get("rms_state", None)
        if rms_state_value is None or RMSState(rms_state_value) != RMSState.READY:
            app.logger.info("RMS state is %s", rms_state_value)
            k8s_state = state.get("k8s_monitoring", None)
            ceph_state = state.get("ceph_monitoring", None)
            # If either of k8s_monitoring, ceph_monitoring is in 'Started' state instead of empty or 'Completed',
            # it means monitoring was not finished in the previous run.
            if STARTED_STATE in (k8s_state, ceph_state):
                was_monitoring = True
            else:
                app.logger.info("Updating RMS state to Ready for this fresh run")
                rms_state_enum = RMSState.READY
                state["rms_state"] = rms_state_enum.value
                state_manager.set_state(rms_state_enum)
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


def signal_handler(signum: int, _frame: object) -> None:
    """Handle shutdown signals gracefully"""
    global gunicorn_process  # pylint: disable=global-statement
    app.logger.info("Received shutdown signal %s. Cleaning up...", signum)

    # Set RMS state to indicate shutdown
    try:
        state_manager.set_state(RMSState.INTERNAL_FAILURE)
        Helper.update_state_timestamp(
            state_manager, "rms_state", RMSState.INTERNAL_FAILURE.value
        )
    except Exception as e:
        app.logger.error("Failed to update state during shutdown: %s", e)

    # Terminate Gunicorn process
    if gunicorn_process and gunicorn_process.poll() is None:
        app.logger.info("Terminating Gunicorn process...")
        gunicorn_process.terminate()
        try:
            gunicorn_process.wait(timeout=10)
            app.logger.info("Gunicorn terminated gracefully")
        except subprocess.TimeoutExpired:
            app.logger.warning("Gunicorn didn't terminate gracefully, killing...")
            gunicorn_process.kill()
        finally:
            gunicorn_process = None

    app.logger.info("RMS shutdown complete")
    sys.exit(0)


def run_flask_with_gunicorn() -> None:
    """Run the Flask app using Gunicorn for production"""
    global gunicorn_process  # pylint: disable=global-statement

    app.logger.info(
        "Starting Gunicorn server on port 8551 to receive notifications from HMNFD"
    )

    # Gunicorn command using config file
    gunicorn_cmd = ["gunicorn", "-c", "src/rrs/rms/gunicorn.py", "src.rrs.rms.rms:app"]

    try:
        # Start Gunicorn as a subprocess
        # Note: We can't use 'with' here because we need the process to remain alive
        # after this function returns for the monitoring loop
        gunicorn_process = subprocess.Popen(  # pylint: disable=consider-using-with
            gunicorn_cmd,
            cwd="/app",
            universal_newlines=True,
            bufsize=1,
        )

        app.logger.info(
            "Gunicorn server started successfully with PID: %s", gunicorn_process.pid
        )

        # Monitor Gunicorn process in a separate thread
        def monitor_gunicorn() -> None:
            """Monitor Gunicorn process health"""
            while True:
                if gunicorn_process and gunicorn_process.poll() is not None:
                    app.logger.error(
                        "Gunicorn process died unexpectedly with return code: %s",
                        gunicorn_process.returncode,
                    )
                    # Update RMS state to indicate Flask service failure
                    state_manager.set_state(RMSState.INTERNAL_FAILURE)
                    Helper.update_state_timestamp(
                        state_manager, "rms_state", RMSState.INTERNAL_FAILURE.value
                    )
                    app.logger.critical(
                        "RMS Flask service is down - HMNFD notifications will not be received"
                    )
                    break
                time.sleep(5)

        monitor_thread = threading.Thread(target=monitor_gunicorn, daemon=True)
        monitor_thread.start()

        # Give Gunicorn a moment to start
        time.sleep(2)

        if gunicorn_process.poll() is not None:
            raise subprocess.SubprocessError(
                f"Gunicorn failed to start, return code: {gunicorn_process.returncode}"
            )

    except (OSError, subprocess.SubprocessError) as e:
        app.logger.error("Failed to start Gunicorn server: %s", e)
        state_manager.set_state(RMSState.INTERNAL_FAILURE)
        Helper.update_state_timestamp(
            state_manager, "rms_state", RMSState.INTERNAL_FAILURE.value
        )
        sys.exit(1)


if __name__ == "__main__":
    # Main entry point for the RMS service.
    # This block performs the following steps within the Flask (gunicorn) application context:

    # 1. Performs initial checks and also determine whether a monitoring loop needs to be resumed.
    # 2. If RMS was previously in a 'Monitoring' state, resumes the monitoring loop in the background.
    # 3. Starts the Flask application server in a separate thread.
    # 4. Ensures HMNFD subscriptions are in place.
    # 5. Periodically updates critical service and zone status if monitoring is not actively running.
    # 6. Continuously manages RMS state transitions (`Waiting`, `Started`, `Monitoring`) based on current activity.

    # The loop runs indefinitely - checking HMNFD subscription, critical services and CEPH status every 600 seconds.

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    with app.app_context():
        if not NAMESPACE or not DYNAMIC_CM or not STATIC_CM:
            app.logger.error(
                "One or more missing environment variables - namespace, static configmap, dynamic configmap"
            )
            sys.exit(1)

        launch_monitoring = initial_check_and_update()

        # Start Gunicorn server for Flask endpoints
        run_flask_with_gunicorn()

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
            if state_manager.get_state() != RMSState.MONITORING:
                rms_state = RMSState.WAITING
                state_manager.set_state(rms_state)
                Helper.update_state_timestamp(
                    state_manager, "rms_state", rms_state.value
                )
                time.sleep(600)
                if state_manager.get_state() == RMSState.MONITORING:
                    continue
                rms_state = RMSState.STARTED
                state_manager.set_state(rms_state)
                Helper.update_state_timestamp(
                    state_manager, "rms_state", rms_state.value
                )
                check_and_create_hmnfd_subscription()
                update_critical_services(state_manager, True)
                update_zone_status(state_manager)
            else:
                app.logger.info("Not running main loop as monitoring is running")
                time.sleep(MAIN_LOOP_WAIT_TIME_INTERVAL)

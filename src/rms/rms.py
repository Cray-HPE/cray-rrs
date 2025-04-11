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

import threading
import time
import json
import yaml
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from kubernetes import client, config
#from concurrent.futures import ThreadPoolExecutor
import requests
import sys
import base64
import copy
import lib_configmap
import lib_rms


app = Flask(__name__)
# Load kube config from local environment (use in local or non-cluster environments)
config.load_kube_config()  # Or use load_incluster_config() if running inside a Kubernetes pod
v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

logging.basicConfig(
    format='%(asctime)s [%(threadName)s] %(levelname)s: %(message)s',  # Include thread name in logs
    level=logging.INFO
)
logger = logging.getLogger()

#executor = ThreadPoolExecutor(max_workers=10)
# Global Lock for monitor_critical_services
#monitor_lock = threading.Lock()
#is_monitor_running = False           
#dynamic_cm = 'rrs-mon-dynamic'
#static_cm = 'rrs-mon-static'
#global_rms_state = ''
#global_dynamic_data = dict()


namespace = 'rack-resiliency'
dynamic_cm = 'dynamic-sravani-test'
static_cm = 'static-sravani-test'



class RMSStateManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.monitor_running = False
        self.rms_state = ""
        self.dynamic_cm_data = {}

    def set_state(self, new_state):
        with self.lock:
            self.rms_state = new_state

    def get_state(self):
        with self.lock:
            return self.rms_state

    def set_dynamic_cm_data(self, data):
        with self.lock:
            self.dynamic_cm_data = data

    def get_dynamic_cm_data(self):
        with self.lock:
            if not self.dynamic_cm_data:
                self.dynamic_cm_data = lib_configmap.get_configmap(namespace, dynamic_cm)
            return self.dynamic_cm_data

    def is_monitoring(self):
        with self.lock:
            return self.monitor_running

    def start_monitoring(self):
        with self.lock:
            if self.monitor_running:
                return False
            self.monitor_running = True
            return True

    def stop_monitoring(self):
        with self.lock:
            self.monitor_running = False


state_manager = RMSStateManager()


def update_zone_status():
    logger.info("Getting latest status for zones and nodes")
    try:
        dynamic_cm_data = state_manager.get_dynamic_cm_data()
        yaml_content = dynamic_cm_data.get('dynamic-data.yaml', None)
        if yaml_content:
            dynamic_data = yaml.safe_load(yaml_content)    
        else:
            logger.error("No content found under dynamic-data.yaml in rrs-mon-dynamic configmap")
            #exit(1)

        zone_info = dynamic_data.get('zone')
        k8s_info = zone_info.get('k8s_zones_with_nodes')
        k8s_info_old = copy.deepcopy(k8s_info)
    
        for zone, nodes in k8s_info.items():
            for node in nodes:
                node['Status'] = lib_rms.get_node_status(node['name'])
                
        zone_info['k8s_zones_with_nodes'] = k8s_info

        ceph_info_old = zone_info.get('ceph_zones_with_nodes')
        updated_ceph_data, ceph_healthy_status = lib_rms.get_ceph_status()
        zone_info['ceph_zones_with_nodes'] = updated_ceph_data

        if k8s_info_old != k8s_info or ceph_info_old != updated_ceph_data:
            logger.info(f"Updating zone information in rrs-dynamic configmap")

            dynamic_cm_data['dynamic-data.yaml'] = yaml.dump(dynamic_data, default_flow_style=False)
            state_manager.set_dynamic_cm_data(dynamic_cm_data)
            lib_configmap.update_configmap_data(namespace, dynamic_cm, dynamic_cm_data,'dynamic-data.yaml', dynamic_cm_data['dynamic-data.yaml'])        
        #return k8s_info, updated_ceph_data, ceph_healthy_status
        return ceph_healthy_status

    except KeyError as e:
        logger.error(f"Key error occurred: {e}")
        logger.error("Ensure that 'zone' and 'k8s_zones_with_nodes' keys are present in the dynamic configmap data.")
        state_manager.set_state("internal_failure")
    except yaml.YAMLError as e:
        logger.error(f"YAML error occurred: {e}")
        state_manager.set_state("internal_failure")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        state_manager.set_state("internal_failure")


def update_critical_services(reloading=False):      
    try:
        dynamic_cm_data = state_manager.get_dynamic_cm_data()
        if reloading:
            static_cm_data = lib_configmap.get_configmap(namespace, static_cm)
            logger.info('Retrieving critical services information from rrs-static configmap')
            json_content = static_cm_data.get('critical-service-config.json', None)
        else:
            logger.info('Retrieving critical services information from rrs-dynamic configmap')
            json_content = dynamic_cm_data.get('critical-service-config.json', None)
        if json_content:
            services_data = json.loads(json_content)    
        else:
            logger.error("No content found under critical-service-config.json in rrs-mon configmap")
            exit(1)

        updated_services = lib_rms.get_critical_services_status(services_data)
        services_json = json.dumps(updated_services, indent=2)
        logger.info(services_json)
        if services_json != dynamic_cm_data.get('critical-service-config.json', None):
            logger.debug('critical services are modified. Updating dynamic configmap with latest information')
            dynamic_cm_data['critical-service-config.json'] = services_json
            state_manager.set_dynamic_cm_data(dynamic_cm_data)        
            lib_configmap.update_configmap_data(namespace, dynamic_cm, dynamic_cm_data,'critical-service-config.json', services_json)
        return services_json
    except json.JSONDecodeError:
        logger.error("Failed to decode critical-service-config.json from configmap")
        state_manager.set_state("internal_failure")
        return
    except KeyError as e:
        logger.error(f"KeyError occurred: {str(e)} - Check if the configmap contains the expected keys")
        state_manager.set_state("internal_failure")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        state_manager.set_state("internal_failure")
    
def monitor_k8s(polling_interval, total_time, pre_delay):
    logger.info("Starting k8s monitoring")
    update_state_timestamp('k8s_monitoring', 'Started', 'start_timestamp_k8s_monitoring')
    nodeMonitorGracePeriod = lib_rms.getNodeMonitorGracePeriod()
    if nodeMonitorGracePeriod:
        time.sleep(nodeMonitorGracePeriod)
    else:
        time.sleep(pre_delay)
    start = time.time()
    while time.time() - start < total_time:
        #Retrieve and update critical services status 
        latest_services_json = update_critical_services()
        time.sleep(polling_interval)

    logger.info(f"Ending the k8s monitoring loop after {total_time} seconds")
    update_state_timestamp('k8s_monitoring', 'Completed', 'end_timestamp_k8s_monitoring')
    unrecovered_services = []
    for service, details in json.loads(latest_services_json)["critical-services"].items():
        if details["status"] == "PartiallyConfigured" or details["balanced"] == "false":
            unrecovered_services.append(service)
    if unrecovered_services:
        logger.error(f"Services {unrecovered_services} are still not recovered even after {monitoring_timeout} seconds")
    

def monitor_ceph(polling_interval, total_time, pre_delay):
    logger.info("Starting CEPH monitoring")
    update_state_timestamp('ceph_monitoring', 'Started', 'start_timestamp_ceph_monitoring')
    time.sleep(pre_delay)
    start = time.time()
    while time.time() - start < total_time:
        #Retrieve and update k8s/CEPH status and CEPH health
        fceph_healthy_status = update_zone_status()
        time.sleep(polling_interval)
    
    update_state_timestamp('ceph_monitoring', 'Completed', 'end_timestamp_ceph_monitoring')
    if ceph_healthy_status == False:
        logger.error(f"CEPH is still unhealthy after {total_time} seconds")

def monitoring_loop():
    """Initiate monitoring critical services and CEPH"""
    if not state_manager.start_monitoring():
        logger.warn(f"Skipping launch of a new monitoring instance as a previous one is still active")
        return  # Return early if the function is already running
    
    logger.info('Monitoring critical services and zone status...')
    state = 'Monitoring'
    state_manager.set_state(state)
    update_state_timestamp('rms_state', state)
    # Read the 'rrs-mon' configmap and parse the data
    static_cm_data = lib_configmap.get_configmap(namespace, static_cm)

    k8s_args = (
        int(static_cm_data.get('k8s_monitoring_polling_interval', 60)),
        int(static_cm_data.get('k8s_monitoring_total_time', 600)),
        int(static_cm_data.get('k8s_pre_monitoring_delay', 40))
    )
    
    ceph_args = (
        int(static_cm_data.get('ceph_monitoring_polling_interval', 60)),
        int(static_cm_data.get('ceph_monitoring_total_time', 600)),
        int(static_cm_data.get('ceph_pre_monitoring_delay', 40))
    )

    t1 = threading.Thread(target=monitor_k8s, args=k8s_args)
    t2 = threading.Thread(target=monitor_ceph, args=ceph_args)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    logger.info("Monitoring complete")
    state_manager.stop_monitoring()
    state_manager.set_state("Started")
    update_state_timestamp('rms_state', 'Started')


def token_fetch():
    try:
        secret = v1.read_namespaced_secret("admin-client-auth", "default")
        client_secret = base64.b64decode(secret.data['client-secret']).decode("utf-8")
        #logger.debug(f"Client Secret: {client_secret}")

        keycloak_url = "https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": "admin-client",
            "client_secret": f"{client_secret}",
        }
        response = requests.post(keycloak_url, data=data)
        token = response.json()
        token = token.get("access_token")
        return token
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)
    except ValueError as e:
        logger.error(f"Failed to parse JSON: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)
    except Exception as err:
        logger.error("Error collecting secret from Kubernetes: {}".format(err))
        state_manager.set_state("internal_failure")
        #exit(1)
    
                
        
def check_failure_type(component_xname):
    """Check if it is a rack or node failure"""
    logger.info("Checking failure type i.e., node or rack failure upon recieving SCN ...")
    token = token_fetch()
    
    #hsm_url = "http://cray-smd.services.svc.cluster.local/hsm/v2/State/Components"
    hsm_url = "https://api-gw-service-nmn.local/apis/smd/hsm/v2/State/Components"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    try:
        # Make the GET request to hsm endpoint
        hsm_response = requests.get(hsm_url, headers=headers)
        hsm_response.raise_for_status()
        hsm_data = hsm_response.json()   

        valid_subroles = {"Master", "Worker", "Storage"}
        filtered_data = [
            component for component in hsm_data.get("Components", [])
            if component.get("Role") == "Management" and component.get("SubRole") in valid_subroles
        ]

        for component in filtered_data:
            if component["ID"] == component_xname:
                rack_id = component["ID"].split("c")[0]  # Extract "x3000" from "x3000c0s1b75n75"
                break

        # Extract the components with ID starting with rack_id
        rack_components = [
            {"ID": component["ID"], "State": component["State"]}
            #for component in hsm_data["Components"]
            for component in filtered_data
            if component["ID"].startswith(rack_id)
        ]
        
        rack_failure = True
        for component in rack_components:
            if component['State'] in ['On', 'Ready','Populated']:
                rack_failure = False
            print(f"ID: {component['ID']}, State: {component['State']}")
        if rack_failure:
            logger.info("All the components in the rack are not healthy. It is a RACK FAILURE")
        else:
            logger.info("Not all the components present in the rack are down. It is only a NODE FAILURE")

        dynamic_cm_data = state_manager.get_dynamic_cm_data()
        yaml_content = dynamic_cm_data.get('dynamic-data.yaml', None)
        if yaml_content:
            dynamic_data = yaml.safe_load(yaml_content)    
        else:
            logger.error("No content found under dynamic-data.yaml in rrs-mon-dynamic configmap")
        pod_zone = dynamic_data.get('rrs').get('zone')
        pod_node = dynamic_data.get('rrs').get('node')
        if rack_id in pod_zone:
            print("Monitoring pod was on the failed rack")
        #implement this            

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)
    except ValueError as e:
        logger.error(f"Failed to parse JSON: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)


@app.route("/scn", methods=["POST"])
def handleSCN():
    """Handle incoming POST requests and initiate monitoring"""
    logger.info("Notification received from HMNFD")
    #global_rms_state = "Fail_notified"
    state_manager.set_state("Fail_notified")
    # Get JSON data from request
    try:
        notification_json = request.get_json()
        logger.info("JSON data received: %s", notification_json)

        # Extract components and state
        components = notification_json.get('Components', [])
        state = notification_json.get('State', '')

        if not components or not state:
            logger.error("Missing 'Components' or 'State' in the request")
            return jsonify({"error": "Missing 'Components' or 'State' in the request"}), 400

        if state == 'Off':
            for component in components:
                logger.info(f'Node {component} is turned Off')
            # Start monitoring services in a new thread
            check_failure_type(component)
            threading.Thread(target=monitoring_loop).start()
                
        elif state == 'On':
            for component in components:
                logger.info(f'Node {component} is turned On')
            # Handle discovery of nodes
            # Handle cleanup or other actions here if needed

        else:
            logger.warning(f"Unexpected state '{state}' received for {components}.")

        return jsonify({"message": "POST call received"}), 200

    except Exception as e:
        logger.error("Error processing the request: %s", e)
        state_manager.set_state("internal_failure")
        return jsonify({"error": "Internal server error."}), 500


            
def get_management_xnames():
    """Get xnames for all the management nodes from HSM"""
    logger.info("Getting xnames for all the management nodes from HSM ...")
    token = token_fetch()
    #hsm_url = "http://cray-smd.services.svc.cluster.local/hsm/v2/State/Components"
    hsm_url = "https://api-gw-service-nmn.local/apis/smd/hsm/v2/State/Components"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }   
    try:
        # Make the GET request to hsm endpoint
        hsm_response = requests.get(hsm_url, headers=headers)
        hsm_response.raise_for_status()
        hsm_data = hsm_response.json()
        
        # Filter components with the given role and subroles
        valid_subroles = {"Master", "Worker", "Storage"}
        filtered_data = [
            component for component in hsm_data.get("Components", [])
            if component.get("Role") == "Management" and component.get("SubRole") in valid_subroles
        ]
        
        management_xnames = {component['ID'] for component in filtered_data}
        logger.info(list(management_xnames))
        return list(management_xnames)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)
    except ValueError as e:
        logger.error(f"Failed to parse JSON: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)


def check_and_create_hmnfd_subscription(node_ip = ''):
    """Create a subscription entry in hmnfd to recieve SCNs(state change notification) for the management components"""
    logger.info("Checking HMNFD subscription for SCN notifications ...")
    token = token_fetch()
    #subscriber_node = 'rack-resiliency'
    subscriber_node = 'x3000c0s1b0n0'
    agent_name = 'rms'
    
    # URL for in mesh pod-to-pod communication
    #get_url = f"http://cray-hmnfd.services.svc.cluster.local/hmi/v2/subscriptions" 
    #post_url = f"http://cray-hmnfd.services.svc.cluster.local/hmi/v2/subscriptions/{subscriber_node}/agents/{agent_name}" 
    
    get_url = "https://api-gw-service-nmn.local/apis/hmnfd/hmi/v2/subscriptions"
    post_url = f"https://api-gw-service-nmn.local/apis/hmnfd/hmi/v2/subscriptions/{subscriber_node}/agents/{agent_name}"

    subscribing_components = get_management_xnames()
    post_data = {
        "Components": subscribing_components,
        "Roles": ["Management"],
        "States": ["Ready","on","off","empty","unknown","populated"],
        "Url": "http://10.102.193.27:3000/scn"
        #"Url": "https://api-gw-service-nmn.local/apis/rms/scn"
    }
    headers = {
        "Authorization": f"Bearer {token}",        
        "Accept": "application/json"
    }

    try:
        get_response = requests.get(get_url, headers=headers)
        data = get_response.json()
        exists = any("rms" in subscription['Subscriber'] for subscription in data['SubscriptionList'])

        if not exists:
            logger.info(f"rms not present in the HMNFD subscription list, creating it ...")
            post_response = requests.post(post_url, json=post_data, headers=headers)
            post_response.raise_for_status()
            logger.info(f"Successfully subscribed to hmnfd for SCN notifications")
        else:
            logger.info(f"rms is already present in the subscription list")
    except requests.exceptions.RequestException as e:
        # Handle request errors (e.g., network issues, timeouts, non-2xx status codes)
        logger.error(f"Failed to make subscription request to hmnfd. Error: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)
    except ValueError as e:
        # Handle JSON parsing errors
        logger.error(f"Failed to parse JSON response: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)

def initial_check_and_update():
    launch_monitoring = False
    dynamic_cm_data = lib_configmap.get_configmap(namespace, dynamic_cm)   
    try:
        yaml_content = dynamic_cm_data.get('dynamic-data.yaml', None)
        if yaml_content:
            dynamic_data = yaml.safe_load(yaml_content)    
        else:
            logger.error("No content found under dynamic-data.yaml in rrs-mon-dynamic configmap")
            exit(1)

        state = dynamic_data.get('state', {})
        rms_state = state.get('rms_state', None)
        if rms_state != "Ready":
            logger.info(f"RMS state is {rms_state}")
            if rms_state == "Monitoring":
                launch_monitoring = True
            elif rms_state == "Init_fail":
                logger.error("RMS is in 'init_fail' state indicating init container failed — not starting the RMS service")
                exit(1)
            else:
                logger.info("Updating RMS state to Ready for this fresh run")
                rms_state = "Ready"
                state['rms_state'] = rms_state
                state_manager.set_state(rms_state)
        #Update RMS start timestamp in dynamic configmap
        timestamps = dynamic_data.get('timestamps', {})
        rms_start_timestamp = timestamps.get('start_timestamp_rms', None)
        if rms_start_timestamp:
            logger.debug("RMS start time already present in configmap")
            logger.info(f"Rack Resiliency Monitoring Service is restarted because of a failure")  
        timestamps['start_timestamp_rms'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        dynamic_cm_data['dynamic-data.yaml'] = yaml.dump(dynamic_data, default_flow_style=False)
        state_manager.set_dynamic_cm_data(dynamic_cm_data)
        lib_configmap.update_configmap_data(namespace, dynamic_cm, dynamic_cm_data,'dynamic-data.yaml', dynamic_cm_data['dynamic-data.yaml'])  
        logger.debug(f"Updated rms_start_timestamp in rrs-dynamic configmap")

    except ValueError as e:
        logger.error(f"Error during configuration check and update: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)
    if launch_monitoring:
        return True
    return False    

def run_flask():
    """Run the Flask app in a separate thread for listening to HMNFD notifications"""
    logger.info(f"Running flask on 3000 port on localhost to recieve notifications from HMNFD")
    #app.config['ENV'] = 'production'
    #app.config['DEBUG'] = False
    #app.logger.setLevel(logging.ERROR)
        #node_ip = subprocess.check_output(["hostname", "-i"]).decode("utf-8").strip()
    app.run(host="0.0.0.0", port=3000, threaded=True, debug=False, use_reloader=False)

def update_state_timestamp(state_field = 'None', new_state = 'None', timestamp_field = 'None'):
    try:
        dynamic_cm_data = state_manager.get_dynamic_cm_data()
        yaml_content = dynamic_cm_data.get('dynamic-data.yaml', None)
        if yaml_content:
            dynamic_data = yaml.safe_load(yaml_content)    
        else:
            logger.error("No content found under dynamic-data.yaml in rrs-mon-dynamic configmap")
        if new_state:
            logger.info(f"Updating state {state_field} to {new_state}")
            state = dynamic_data.get('state', {})   
            state[state_field] = new_state
        if timestamp_field:
            logger.info(f"Updating timestamp {timestamp_field}")
            timestamp = dynamic_data.get('timestamps', {})   
            timestamp[timestamp_field] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        dynamic_cm_data['dynamic-data.yaml'] = yaml.dump(dynamic_data, default_flow_style=False)
        state_manager.set_dynamic_cm_data(dynamic_cm_data)
        lib_configmap.update_configmap_data(namespace, dynamic_cm, dynamic_cm_data,'dynamic-data.yaml', dynamic_cm_data['dynamic-data.yaml'])  
        #logger.info(f"Updated rms_state in rrs-dynamic configmap from {rms_state} to {new_state}")
    except ValueError as e:
        logger.error(f"Error during configuration check and update: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        state_manager.set_state("internal_failure")
        #exit(1)

if __name__ == "__main__": 
    launch_monitoring = initial_check_and_update()    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    check_and_create_hmnfd_subscription()
    update_critical_services(True)
    update_zone_status()
    if launch_monitoring:
        logger.info("RMS is in 'Monitoring' state - starting monitoring loop to resume previous incomplete process")
        threading.Thread(target=monitoring_loop).start()
    time.sleep(600)
    while True:
        #global_rms_state = "Started"
        state = 'Started'
        state_manager.set_state(state)
        update_state_timestamp('rms_state', state)
        logger.info("starting the loop")
        check_and_create_hmnfd_subscription()
        update_critical_services(True)
        update_zone_status()
        #break
        state = 'Waiting'
        state_manager.set_state(state)
        update_state_timestamp('rms_state', state)
        time.sleep(300)  #update it to 600 after demo
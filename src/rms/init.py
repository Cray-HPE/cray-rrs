import yaml
from datetime import datetime
from collections import defaultdict
import logging
import json
import lib_configmap
import re
import lib_rms

logging.basicConfig(
    format='%(asctime)s %(levelname)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

namespace = 'rack-resiliency'
dynamic_cm = 'dynamic-sravani-test'
static_cm = 'static-sravani-test'

def zone_discovery():
    logger.info(f"Retrieving zone information and status of k8s and CEPH nodes")
    status = True
    updated_k8s_data = defaultdict(list)
    updated_ceph_data = dict()
    nodes = lib_rms.get_k8s_nodes()

    for node in nodes:
        node_name = node.metadata.name
        zone = node.metadata.labels.get("topology.kubernetes.io/zone")
        if not zone:
            logger.error(f"Node {node_name} does not have a zone marked for it")
            status = False
            break
            updated_k8s_data = {}
        else:
            updated_k8s_data[zone].append({
                "Status": lib_rms.get_node_status(node_name),
                "name": node_name
            })

    updated_k8s_data = dict(updated_k8s_data)
    
    if status:
        updated_ceph_data, ceph_healthy_status = lib_rms.get_ceph_status()       
    return status, updated_k8s_data, updated_ceph_data    

def check_critical_services_and_timers():
    static_cm_data = lib_configmap.get_configmap(namespace, static_cm)
    critical_svc = static_cm_data.get('critical-service-config.json', None)
    if critical_svc:
        services_data = json.loads(critical_svc)
        if not services_data["critical-services"]:
            logger.error("Critical services are not defined for Rack Resiliency Service")
            return False
    else:
        logger.error("critical-service-config.json not present in Rack Resiliency configmap")
        return False
    
    k8s_delay_timer = static_cm_data.get('k8s_pre_monitoring_delay', None)
    k8s_polling_interval = static_cm_data.get('k8s_monitoring_polling_interval', None)
    k8s_total_time = static_cm_data.get('k8s_monitoring_total_time', None)
    ceph_delay_timer = static_cm_data.get('ceph_pre_monitoring_delay', None)
    ceph_polling_interval = static_cm_data.get('ceph_monitoring_polling_interval', None)
    ceph_total_time = static_cm_data.get('ceph_monitoring_total_time', None)
    if not all([k8s_delay_timer, k8s_polling_interval, k8s_total_time, ceph_delay_timer, ceph_polling_interval, ceph_total_time]):
        logger.warn("One or all of expected timers for k8s and CEPH are not present in Rack Resiliency configmap")
    return True

def init():
    configmap_data = lib_configmap.get_configmap(namespace, dynamic_cm)

    try:        
        yaml_content = configmap_data.get('dynamic-data.yaml', None)
        if yaml_content:
            dynamic_data = yaml.safe_load(yaml_content)    
        else:
            logger.error("No content found under dynamic-data.yaml in rrs-mon-dynamic configmap")
            exit(1)

        #update init timestamp in rrs-dynamic configmap
        timestamps = dynamic_data.get('timestamps', {})
        init_timestamp = timestamps.get('init_timestamp', None)
        state = dynamic_data.get('state', {})
        rms_state = state.get('rms_state', None)        
        if init_timestamp:            
            logger.debug("Init time already present in configmap")
            logger.info(f"Reinitializing the Rack Resiliency Service. This could happen if previous RRS pod has terminated unexpectedly")
        if not rms_state:
            state['rms_state'] = "Init"
        else:
            logger.debug("rms_state is already present in configmap")
            logger.info(f"RMS is already in {rms_state} state. ")    
#check on condition here
        timestamps['init_timestamp'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        lib_configmap.update_configmap_data(namespace, dynamic_cm, configmap_data, 'dynamic-data.yaml', yaml.dump(dynamic_data, default_flow_style=False))    
        logger.debug(f"Updated init_timestamp and rms_state in rrs-dynamic configmap")


        #Retrieve k8s and CEPH node/zone information and update in rrs-dynamic configmap
        zone_info = dynamic_data.get('zone', None)
        discovery_status, updated_k8s_data, updated_ceph_data = zone_discovery()
        if discovery_status:
            zone_info['k8s_zones_with_nodes'] = updated_k8s_data
            zone_info['ceph_zones_with_nodes'] = updated_ceph_data
        
        #Retrieve current node and rack where the RMS pod is running
        node_name = "ncn-w004"
        #node_name = lib_rms.get_current_node()
        rack_name = next((rack for rack, nodes in updated_k8s_data.items() if any(node["name"] == node_name for node in nodes)), None)       

        rrs_pod_placement = dynamic_data.get('rrs', None)
        rrs_pod_placement['zone'] = rack_name
        rrs_pod_placement['node'] = node_name
        logger.info(f"RMS pod is running on node: {node_name} under zone {rack_name}")

        if check_critical_services_and_timers() and discovery_status:
            state['rms_state'] = "Ready"
        else:
            logger.info("Updating rms state to init_fail due to above failures")
            state['rms_state'] = "init_fail"
        logger.debug(f"Updating zone information, pod placement, state in rrs-dynamic configmap")        
        lib_configmap.update_configmap_data(namespace, dynamic_cm, configmap_data, 'dynamic-data.yaml', yaml.dump(dynamic_data, default_flow_style=False))
        

    except KeyError as e:
        logger.error(f"KeyError: Missing expected key in the configmap data - {e}")
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error occurred: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")            
       
if __name__ == "__main__":
    init()
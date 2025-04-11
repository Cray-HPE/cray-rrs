from kubernetes import client, config
import yaml
from datetime import datetime
import logging
import json
import re
import subprocess

config.load_kube_config()  # Or use load_incluster_config() if running inside a Kubernetes pod
v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

'''
logging.basicConfig(
    format='%(asctime)s [%(threadName)s] %(levelname)s: %(message)s',  # Include thread name in logs
    level=logging.INFO
)'''
logger = logging.getLogger(__name__)


HOST = 'ncn-m001'

def run_command(command):
    """Helper function to run a command and return the result."""
    logger.debug(f"Running command: {command}")
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Command {command} errored out with : {e.stderr}")
    return result.stdout

def get_current_node():
    pod_name = os.getenv("HOSTNAME")
    pod = v1.read_namespaced_pod(name=pod_name, namespace='rack-resiliency')
    node_name = pod.spec.nodeName   #node_name if nodeName does not work    
    return node_name

def getNodeMonitorGracePeriod():
    # Get the kube-controller-manager pod which would be having nodeMonitorGracePeriod if configured
    pods = v1.list_namespaced_pod(namespace="kube-system", label_selector="component=kube-controller-manager")
    if pods.items:
        command = pods.items[0].spec.containers[0].command
        grace_period_flag = next((arg for arg in command if "--node-monitor-grace-period" in arg), None)
        if grace_period_flag:
            nodeMonitorGracePeriod = grace_period_flag.split("=")[1]
            return int(nodeMonitorGracePeriod.rstrip("s"))
    else:
        logger.error("kube-controller-manager pod not found")
    return None    

def ceph_health_check():
    
    #ceph_status_cmd = f"ssh {HOST} 'ceph -s -f json'"
    #ceph_services_cmd = f"ssh {HOST} 'ceph orch ps -f json'"

    ceph_status_cmd = "ceph -s -f json"
    ceph_services_cmd = "ceph orch ps -f json"
    ceph_services = json.loads(run_command(ceph_services_cmd))    
    ceph_status = json.loads(run_command(ceph_status_cmd))

    ceph_healthy = True    
    health_status = ceph_status.get("health", {}).get("status", "UNKNOWN")
    #print(health_status)
    
    if "HEALTH_OK" not in health_status:
        ceph_healthy = False
        logger.warning(f"CEPH is not healthy with health status as {health_status}")
        pg_degraded_message = ceph_status.get("health", {}).get("checks", {}).get("PG_DEGRADED", {}).get("summary", {}).get("message", "")
        
        if "Degraded" in pg_degraded_message:
            if 'recovering_objects_per_sec' or 'recovering_bytes_per_sec' in data.get('pgmap', {}):
                logger.info(f"CEPH recovery is in progress...")
            else:
                logger.warning("CEPH PGs are in degraded state, but recovery is not happening")
        else:
            health_checks = ceph_status.get("health", {}).get("checks", {})
            logger.warning(f"Reason for CEPH unhealthy state are - {list(health_checks.keys())}")
    else:
        logger.info("CEPH is healthy")

    failed_services = []
    for service in ceph_services:
        if service["status_desc"] != "running":
            ceph_healthy = False
            failed_services.append(service["service_name"])
            logger.warning(f"Service {service['service_name']} running on {service['hostname']} is in {service['status_desc']} state")
        else:
            logger.debug(f"Service {service['service_name']} running on {service['hostname']} is in {service['status_desc']} state")
    if failed_services:
        logger.warning(f"{len(failed_services)} out of {len(ceph_services)} ceph services are not running")       

    return ceph_healthy

def fetch_ceph_data():
    """
    Fetch Ceph OSD and host details using SSH commands.
    This function retrieves the OSD tree and host status using ceph commands executed remotely.
    Returns:
        tuple: JSONs containing the Ceph OSD tree and host details.
    """
    #ceph_details_cmd = f"ssh {HOST} 'ceph osd tree -f json'"
    #ceph_hosts_cmd = f"ssh {HOST} 'ceph orch host ls -f json'"
    
    ceph_details_cmd = "ceph osd tree -f json"
    ceph_hosts_cmd = "ceph orch host ls -f json"

    ceph_tree = json.loads(run_command(ceph_details_cmd))
    ceph_hosts = json.loads(run_command(ceph_hosts_cmd))

    return ceph_tree, ceph_hosts

def get_ceph_status():
    """
    Fetch Ceph storage nodes and their OSD statuses.
    This function processes Ceph data fetched from the Ceph OSD tree and the host status.
    Returns:
        dict or str: A dictionary of storage nodes with their OSD status
    """
    ceph_tree, ceph_hosts = fetch_ceph_data()
    #print(ceph_hosts)
    host_status_map = {host["hostname"]: host["status"] for host in ceph_hosts}
    final_output = {}
    failed_hosts = []
    for item in ceph_tree.get('nodes', []):
        if item['type'] == 'rack':
            rack_name = item['name']
            storage_nodes = []

            for child_id in item.get('children', []):
                host_node = next((x for x in ceph_tree['nodes'] if x['id'] == child_id), None)

                if host_node and host_node['type'] == 'host' and host_node['name'].startswith("ncn-s"):
                    osd_ids = host_node.get('children', [])

                    osds = [osd for osd in ceph_tree['nodes'] if osd['id'] in osd_ids and osd['type'] == 'osd']
                    osd_status_list = [{"name": osd['name'], "status": osd.get('status', 'unknown')} for osd in osds]

                    node_status = host_status_map.get(host_node['name'], "No Status")
                    if node_status in ["", "online"]:
                        node_status = "Ready"
                    else:
                        failed_hosts.append(host_node["name"])
                        logger.warning(f"Host {host_node['name']} is in - {node_status} state")                        

                    storage_nodes.append({
                        "name": host_node['name'],
                        "status": node_status,
                        "osds": osd_status_list
                    })
    
            final_output[rack_name] = storage_nodes
    if failed_hosts:
        logger.warning(f"{len(failed_hosts)} out of {len(ceph_hosts)} ceph nodes are not healthy")    
    
    ceph_healthy = ceph_health_check()
    
    return final_output, ceph_healthy


def get_k8s_nodes():
    """Retrieve all Kubernetes nodes"""
    try:
        return v1.list_node().items
    except client.exceptions.ApiException as e:
        return {"error": f"API error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def get_node_status(node_name):
    """Extract and return the status of a node"""
    
    nodes = get_k8s_nodes()
    for node in nodes:
        if node.metadata.name == node_name:
            # If the node has conditions, we check the last one
            status = node.status.conditions[-1].status if node.status.conditions else 'Unknown'
            return "Ready" if status == "True" else "NotReady"            
    return "Unknown"


def get_k8s_nodes_data():
    """Fetch Kubernetes nodes and organize them by topology zone"""
    nodes = get_k8s_nodes()
    if isinstance(nodes, dict) and "error" in nodes:
        return {"error": nodes["error"]}

    zone_mapping = {}

    for node in nodes:
        node_name = node.metadata.name
        status = node.status.conditions[-1].status if node.status.conditions else 'Unknown'
        node_status  = "Ready" if status == "True" else "NotReady"
        node_zone = node.metadata.labels.get('topology.kubernetes.io/zone')

        # Skip nodes without a zone label
        if not node_zone:
            continue

        # Initialize the zone if it doesn't exist
        if node_zone not in zone_mapping:
            zone_mapping[node_zone] = {'masters': [], 'workers': []}

        # Classify nodes as master or worker based on name prefix
        if node_name.startswith("ncn-m"):
            zone_mapping[node_zone]['masters'].append({"name": node_name, "status": node_status})
        elif node_name.startswith("ncn-w"):
            zone_mapping[node_zone]['workers'].append({"name": node_name, "status": node_status})
    if zone_mapping:
        return zone_mapping  
    else: 
        logger.error("No K8s topology zone present")
        return "No K8s topology zone present"


def fetch_all_pods():
    """Fetch all pods in a single API call to reduce request time."""
    nodes_data = get_k8s_nodes_data()
    #logger.info(f"from fetch_all_pods - {nodes_data}")
    if isinstance(nodes_data, dict) and "error" in nodes_data:
        #logger.info("nodes_data is disctionary")
        return {"error": nodes_data["error"]}

    node_zone_map = {
        node["name"]: zone
        for zone, node_types in nodes_data.items()
        for node_type in ["masters", "workers"]
        for node in node_types[node_type]
    }

    all_pods = v1.list_pod_for_all_namespaces(watch=False).items
    pod_info = []
    
    for pod in all_pods:
        node_name = pod.spec.node_name
        zone = node_zone_map.get(node_name, "unknown")
        pod_info.append({
            "Name": pod.metadata.name,
            "Node": node_name,
            "Zone": zone,
            "labels": pod.metadata.labels
        })

    return pod_info

def check_skew(service_name, pods):
    """Check the replica skew across zones efficiently."""
    zone_pod_map = {}

    for pod in pods:
        zone = pod["Zone"]
        node = pod["Node"]
        pod_name = pod["Name"]

        if zone not in zone_pod_map:
            zone_pod_map[zone] = {}
        if node not in zone_pod_map[zone]:
            zone_pod_map[zone][node] = []
        zone_pod_map[zone][node].append(pod_name)

    counts = [sum(len(pods) for pods in zone.values()) for zone in zone_pod_map.values()]

    if not counts:
        return {
            "service-name": service_name,
            "status": "no replicas found",
            "replicaDistribution": {}
        }

    balanced = "true" if max(counts) - min(counts) <= 1 else "false"

    return {
        "service-name": service_name,
        "balanced": balanced,
        "replicaDistribution": zone_pod_map
    }

def get_service_status(service_name, service_namespace, service_type):
    """Helper function to fetch service status based on service type."""
    try:
        if service_type == 'Deployment':
            app = apps_v1.read_namespaced_deployment(service_name, service_namespace)
            return app.status.replicas, app.status.ready_replicas, app.spec.selector.match_labels
        elif service_type == 'StatefulSet':
            app = apps_v1.read_namespaced_stateful_set(service_name, service_namespace)
            return app.status.replicas, app.status.ready_replicas, app.spec.selector.match_labels
        elif service_type == 'DaemonSet':
            app = apps_v1.read_namespaced_daemon_set(service_name, service_namespace)
            return app.status.desired_number_scheduled, app.status.number_ready, app.spec.selector.match_labels
        else:
            logger.warning(f"Unsupported service type: {service_type}")
            return None, None, None
    except client.exceptions.ApiException as e:
        match = re.search(r'Reason: (.*?)\n', str(e))
        if match:
            error_message = match.group(1)     
        logger.error(f"Error fetching {service_type} {service_name}: {error_message}")
        return None, None, None



def get_critical_services_status(services_data):
    """Update critical service info with status and balanced values"""
    
    #logger.info(f"In lib_rms get_critical_services_status, input data is - {services_data}")
    # Fetch all pods in one API call
    all_pods = fetch_all_pods()    

    critical_services = services_data['critical-services']
    logger.info(f"Number of critical services are - {len(critical_services)}")    
    imbalanced_services = []
    for service_name, service_info in critical_services.items():
        #print(service_name)
        #print(service_info)      
        
        service_namespace = service_info['namespace']
        service_type = service_info['type']
        desired_replicas, ready_replicas, labels = get_service_status(service_name, service_namespace , service_type)

        # If replicas data was returned
        if desired_replicas is not None and ready_replicas is not None and labels is not None:
            status = 'Configured'
            if ready_replicas < desired_replicas:
                imbalanced_services.append(service_name)
                status = 'PartiallyConfigured'
                logger.warning(f"{service_type} '{service_name}' in namespace '{service_namespace}' is not ready. "
                               f"Only {ready_replicas} replicas are ready out of {desired_replicas} desired replicas")
            else:
                logger.debug(f"Desired replicas and ready replicas are matching for '{service_name}'")
            
            
            label_selector = ','.join([f"{key}={value}" for key, value in labels.items()])
            filtered_pods = [pod for pod in all_pods
                if pod.get('labels') and all(pod['labels'].get(key) == value for key, value in labels.items())]
            
            balance_details = check_skew(service_name, filtered_pods)
            if balance_details['balanced'] == 'False':
                imbalanced_services.append(service_name)
            service_info.update({
                "status": status,
                "balanced": balance_details['balanced']
            })            
        else:
            service_info.update({
                "status": "Unconfigured",
                "balanced": "NA"
            })
    if imbalanced_services:
        logger.warning(f"List of imbalanced services are - {imbalanced_services}")   
    return services_data
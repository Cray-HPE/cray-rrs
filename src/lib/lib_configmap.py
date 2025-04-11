from kubernetes import client, config
import yaml
from datetime import datetime
import logging
import json
import time

config.load_kube_config()  # Or use load_incluster_config() if running inside a Kubernetes pod
v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()
'''
logging.basicConfig(
    format='%(asctime)s [%(threadName)s] %(levelname)s: %(message)s',  # Include thread name in logs
    level=logging.INFO
)
'''
logger = logging.getLogger(__name__)

def create_configmap(namespace, configmap_lock_name): 
    """Create a configmap with provided name in provided namespace"""
    try:
        config_map = client.V1ConfigMap(metadata=client.V1ObjectMeta(name=configmap_lock_name),data = {})
        v1.create_namespaced_config_map(namespace=namespace, body=config_map)
    except client.exceptions.ApiException as e:
        logger.error(f"Error creating ConfigMap {configmap_lock_name}: {e}")


def acquire_lock(namespace, configmap_name):
    """Acquire the lock by creating the configmap {configmap_lock_name}"""
    #print('In acquire_lock')
    while True:
        configmap_lock_name = configmap_name + "-lock"
        try:
            config_map = v1.read_namespaced_config_map(namespace=namespace, name=configmap_lock_name)
            #print(config_map)
            logger.info("Lock is already acquired by some other resource. Retrying in 1 second...")
            time.sleep(1)
        except client.exceptions.ApiException as e:
            if e.status == 404:
                logger.debug(f"Config map {configmap_lock_name} is not present. Acquiring the lock")
                create_configmap(namespace, configmap_lock_name)
                return True
            else:
                logger.error(f"Error checking for lock: {e}")
                break


def release_lock(namespace, configmap_name):
    """Release the lock by deleting the configmap {configmap_lock_name}"""
    
    configmap_lock_name = configmap_name + "-lock"
    try:
        v1.delete_namespaced_config_map(name=configmap_lock_name, namespace=namespace)
        logger.debug(f"ConfigMap {configmap_lock_name} deleted successfully from namespace {namespace}")
    except client.exceptions.ApiException as e:
        logger.error(f"Error deleting ConfigMap {configmap_lock_name}: {e}")


def update_configmap_data(namespace, configmap_name, configmap_data, key, new_data, mount_path=''):
    """Update a ConfigMap both in k8s and inside the pod"""
    
    configmap_body = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=configmap_name),
        data=configmap_data
    )

    if acquire_lock(namespace, configmap_name):
        try:
            #print("updating the configmap")
            v1.replace_namespaced_config_map(name=configmap_name, namespace=namespace, body=configmap_body)
            logger.debug(f"ConfigMap '{configmap_name}' in namespace '{namespace}' updated successfully")
            
            if mount_path:
                #Update mounted configmap volume from environment value
                file_path = os.path.join(mount_path, key)
                with open(file_path, 'w') as f:
                    f.write(new_data)          
                logger.debug(f"Mounted file {file_path} updated successfully inside the pod")
        except Exception as e:
            logger.error(f"Failed to update ConfigMap or mounted file: {str(e)}")
        finally:
            release_lock(namespace, configmap_name)
            

def get_configmap(namespace, configmap_name):
    """Get data from k8s configmap"""
    #print("In get_configmap")
    try:
        config_map = v1.read_namespaced_config_map(name=configmap_name, namespace=namespace)
        return config_map.data

    except client.exceptions.ApiException as e:
        logger.error(f"Error fetching ConfigMap {configmap_name}: {e}")
        return None
        

def read_configmap_data_from_mount(mount_path, key = ""):
    """Reads all files in the mounted directory and returns the content of each file.
       If key parameter is empty is will read entire contents from the mount location"""
    
    configmap_data = {}
    try:
        if not key:
            for file_name in os.listdir(mount_path):
                file_path = os.path.join(mount_path, file_name)

                if os.path.isfile(file_path):
                    with open(file_path, 'r') as file:
                        configmap_data[file_name] = file.read()
                        return configmap_data   
        else:
            file_path = os.path.join(mount_path, key)
            if os.path.isfile(file_path):
                with open(file_path, 'r') as file:
                    return file.read()
            else:
                logger.error(f"File for key {key} not found in the mount path {mount_path}")
                return None
        
    except Exception as e:
        logger.error(f"Error reading ConfigMap data from mount path {mount_path}: {e}")
        return None
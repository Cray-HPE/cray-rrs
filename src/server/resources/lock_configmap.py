"""
Module to manage Kubernetes ConfigMap-based locking mechanism.
This module includes functions to create, acquire, release, and update configmaps
in Kubernetes to manage a lock mechanism for resources.
"""

import logging
import time
import os
from src.server.resources.k8s_zones import load_k8s_config
from kubernetes import client

# Load Kubernetes config
load_k8s_config()

v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def create_configmap(namespace, configmap_lock_name):
    """Create a ConfigMap with the provided name in the given namespace."""
    try:
        config_map = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name=configmap_lock_name), data={}
        )
        v1.create_namespaced_config_map(namespace=namespace, body=config_map)
    except client.exceptions.ApiException as e:
        logger.error("Error creating ConfigMap %s: %s", configmap_lock_name, e)


def acquire_lock(namespace, configmap_name):
    """Acquire the lock by creating the ConfigMap {configmap_lock_name}."""
    print("In acquire_lock")
    configmap_lock_name = configmap_name + "-lock"

    while True:
        try:
            config_map = v1.read_namespaced_config_map(
                namespace=namespace, name=configmap_lock_name
            )
            print(config_map)
            logger.info(
                "Lock is already acquired by some other resource. Retrying in 1 second..."
            )
            time.sleep(1)
        except client.exceptions.ApiException as e:
            if e.status == 404:
                logger.debug(
                    "Config map %s is not present. Acquiring the lock",
                    configmap_lock_name,
                )
                create_configmap(namespace, configmap_lock_name)
                return True  # Returning True as the lock is acquired
            logger.error("Error checking for lock: %s", e)
            break  # Exit the loop in case of error

    return False  # Return False if lock could not be acquired


def release_lock(namespace, configmap_name):
    """Release the lock by deleting the ConfigMap {configmap_lock_name}."""
    configmap_lock_name = configmap_name + "-lock"
    try:
        v1.delete_namespaced_config_map(name=configmap_lock_name, namespace=namespace)
        logger.debug(
            "ConfigMap %s deleted successfully from namespace %s",
            configmap_lock_name,
            namespace,
        )
    except client.exceptions.ApiException as e:
        logger.error("Error deleting ConfigMap %s: %s", configmap_lock_name, e)

# pylint: disable=R0917
def update_configmap_data(
    namespace, configmap_name, configmap_data, key, new_data, mount_path=""
):
    """Update a ConfigMap in Kubernetes and the mounted file in the pod."""
    print(f"In update_configmap_data, key is {key} and data is {new_data}")
    configmap_data[key] = new_data
    print(configmap_data)
    configmap_body = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=configmap_name), data=configmap_data
    )

    if acquire_lock(namespace, configmap_name):
        try:
            print("updating the configmap")
            v1.replace_namespaced_config_map(
                name=configmap_name, namespace=namespace, body=configmap_body
            )
            logger.info(
                "ConfigMap '%s' in namespace '%s' updated successfully",
                configmap_name,
                namespace,
            )

            if mount_path:
                # Update mounted configmap volume from environment value
                file_path = os.path.join(mount_path, key)
                with open(file_path, "w", encoding="utf-8") as f:  # Specified encoding
                    f.write(new_data)
                logger.debug(
                    "Mounted file %s updated successfully inside the pod", file_path
                )

        finally:
            release_lock(namespace, configmap_name)


def get_configmap(namespace, configmap_name):
    """Fetch data from a Kubernetes ConfigMap."""
    print("In get_configmap")
    try:
        config_map = v1.read_namespaced_config_map(
            name=configmap_name, namespace=namespace
        )
        return config_map.data
    except client.exceptions.ApiException as e:
        logger.error("Error fetching ConfigMap %s: %s", configmap_name, e)
        return {}  # Consistent return type (empty dict instead of None)


def read_configmap_data_from_mount(mount_path, key=""):
    """Reads all files in the mounted directory and returns the content of each file.
    If key parameter is empty, it will read the entire contents from the mount location.
    """
    configmap_data = {}
    try:
        if not key:
            for file_name in os.listdir(mount_path):
                file_path = os.path.join(mount_path, file_name)

                if os.path.isfile(file_path):
                    with open(
                        file_path, "r", encoding="utf-8"
                    ) as file:  # Specified encoding
                        configmap_data[file_name] = file.read()
            return configmap_data

        # Removed unnecessary else block here
        file_path = os.path.join(mount_path, key)
        if os.path.isfile(file_path):
            with open(
                file_path, "r", encoding="utf-8"
            ) as file:  # Specified encoding
                return file.read()

        logger.error(
            "File for key %s not found in the mount path %s", key, mount_path
        )
        return None

    except Exception as e:
        logger.error(
            "Error reading ConfigMap data from mount path %s: %s", mount_path, e
        )
        return None

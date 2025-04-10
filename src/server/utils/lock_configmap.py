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
Module to manage Kubernetes ConfigMap-based locking mechanism.
This module includes functions to create, acquire, release, and update configmaps
in Kubernetes to manage a lock mechanism for resources.
"""

import logging
import time
import os
from typing import Dict, Optional, Union
from src.server.utils.helper import Helper
from kubernetes import client  # type: ignore

# Load Kubernetes config
Helper.load_k8s_config()

v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def create_configmap(namespace: str, configmap_lock_name: str) -> None:
    """Create a ConfigMap with the provided name in the given namespace."""
    try:
        config_map = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name=configmap_lock_name), data={}
        )
        v1.create_namespaced_config_map(namespace=namespace, body=config_map)
    except client.exceptions.ApiException as e:
        logger.error("Error creating ConfigMap %s: %s", configmap_lock_name, e)


def acquire_lock(namespace: str, configmap_name: str) -> bool:
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


def release_lock(namespace: str, configmap_name: str) -> None:
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
    namespace: str,
    configmap_name: str,
    configmap_data: Dict[str, str],
    key: str,
    new_data: str,
    mount_path: str = "",
) -> None:
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


def get_configmap(namespace: str, configmap_name: str) -> Dict[str, str]:
    """Fetch data from a Kubernetes ConfigMap."""
    print("In get_configmap")
    try:
        config_map = v1.read_namespaced_config_map(
            name=configmap_name, namespace=namespace
        )
        return config_map.data or {}  # Return empty dict if data is None
    except client.exceptions.ApiException as e:
        logger.error("Error fetching ConfigMap %s: %s", configmap_name, e)
        return {}  # Consistent return type (empty dict instead of None)


def read_configmap_data_from_mount(
    mount_path: str, key: str = ""
) -> Optional[Union[Dict[str, str], str]]:
    """Reads all files in the mounted directory and returns the content of each file.
    If key parameter is empty, it will read the entire contents from the mount location.
    """
    configmap_data: Dict[str, str] = {}
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
            with open(file_path, "r", encoding="utf-8") as file:  # Specified encoding
                return file.read()

        logger.error("File for key %s not found in the mount path %s", key, mount_path)
        return None

    except Exception as e:
        logger.error(
            "Error reading ConfigMap data from mount path %s: %s", mount_path, e
        )
        return None

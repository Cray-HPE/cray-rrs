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

import time
import os
from typing import Dict, Optional, Union
from kubernetes.client.exceptions import ApiException
from flask import current_app as app
from kubernetes import client, config  # type: ignore
from src.lib.rrs_logging import get_log_id


class ConfigMapHelper:
    """
    Helper class for managing ConfigMaps in Kubernetes.
    """

    # Load Kubernetes config
    @staticmethod
    def load_k8s_config() -> None:
        """Load Kubernetes configuration for API access."""
        try:
            config.load_incluster_config()
        except Exception:
            config.load_kube_config()

    @staticmethod
    def create_configmap(namespace: str, configmap_lock_name: str) -> None:
        """Create a ConfigMap with the provided name in the given namespace."""
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        try:
            config_map = client.V1ConfigMap(
                metadata=client.V1ObjectMeta(name=configmap_lock_name), data={}
            )
            v1.create_namespaced_config_map(namespace=namespace, body=config_map)
        except client.exceptions.ApiException as e:
            app.logger.error("Error creating ConfigMap %s: %s", configmap_lock_name, e)

    @staticmethod
    def acquire_lock(namespace: str, configmap_name: str) -> bool:
        """Acquire the lock by creating the ConfigMap {configmap_lock_name}."""
        configmap_lock_name = configmap_name + "-lock"
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        # Check if the ConfigMap already exists
        while True:
            try:
                v1.read_namespaced_config_map(
                    namespace=namespace, name=configmap_lock_name
                )
                # print(config_map)
                app.logger.info(
                    "Lock is already acquired by some other resource. Retrying in 1 second..."
                )
                time.sleep(1)
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    app.logger.debug(
                        "Config map %s is not present. Acquiring the lock",
                        configmap_lock_name,
                    )
                    ConfigMapHelper.create_configmap(namespace, configmap_lock_name)
                    return True  # Returning True as the lock is acquired
                app.logger.error("Error checking for lock: %s", e)
                break  # Exit the loop in case of error

        return False  # Return False if lock could not be acquired

    @staticmethod
    def release_lock(namespace: str, configmap_name: str) -> None:
        """Release the lock by deleting the ConfigMap {configmap_lock_name}."""
        configmap_lock_name = configmap_name + "-lock"
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()
        try:
            v1.delete_namespaced_config_map(
                name=configmap_lock_name, namespace=namespace
            )
            app.logger.debug(
                "ConfigMap %s deleted successfully from namespace %s",
                configmap_lock_name,
                namespace,
            )
        except client.exceptions.ApiException as e:
            app.logger.error("Error deleting ConfigMap %s: %s", configmap_lock_name, e)

    # pylint: disable=R0917
    @staticmethod
    def update_configmap_data(
        namespace: str,
        configmap_name: str,
        configmap_data: Union[Dict[str, str], None],
        key: str,
        new_data: str,
        mount_path: str = "",
    ) -> None:
        """Update a ConfigMap in Kubernetes and the mounted file in the pod."""
        # print(f"In update_configmap_data, key is {key} and data is {new_data}")
        try:
            ConfigMapHelper.load_k8s_config()
            v1 = client.CoreV1Api()
            if configmap_data is None:
                configmap_data = ConfigMapHelper.get_configmap(namespace, configmap_name)
            configmap_data[key] = new_data

            configmap_body = client.V1ConfigMap(
                metadata=client.V1ObjectMeta(name=configmap_name), data=configmap_data
            )
        except ApiException as e:
            app.logger.error(f"Failed to update ConfigMap: {e.reason}")
        except Exception as e:
            app.logger.error(f"Unexpected error updating ConfigMap: {str(e)}")

        if ConfigMapHelper.acquire_lock(namespace, configmap_name):
            try:
                # print("updating the configmap")
                app.logger.info(
                    f"Updating ConfigMap {configmap_name} in namespace {namespace}"
                )
                v1.replace_namespaced_config_map(
                    name=configmap_name, namespace=namespace, body=configmap_body
                )
                app.logger.info(
                    f"ConfigMap {configmap_name} in namespace {namespace} updated successfully"
                )

                if mount_path:
                    # Update mounted configmap volume from environment value
                    file_path = os.path.join(mount_path, key)
                    with open(
                        file_path, "w", encoding="utf-8"
                    ) as f:  # Specified encoding
                        f.write(new_data)
                    app.logger.debug(
                        f"Mounted file {file_path} updated successfully inside the pod"
                    )

            finally:
                ConfigMapHelper.release_lock(namespace, configmap_name)

    @staticmethod
    def get_configmap(namespace: str, configmap_name: str) -> Dict[str, str]:
        """Fetch data from a Kubernetes ConfigMap."""
        log_id = get_log_id()
        app.logger.info(
            f"[{log_id}] Fetching ConfigMap {configmap_name} from namespace {namespace}"
        )
        ConfigMapHelper.load_k8s_config()
        v1 = client.CoreV1Api()

        try:
            config_map = v1.read_namespaced_config_map(
                name=configmap_name, namespace=namespace
            )
            return config_map.data or {}  # Return empty dict if data is None

        except client.exceptions.ApiException as e:
            app.logger.error(f"[{log_id}] API error fetching ConfigMap: {str(e)}")
            return {"error": f"API error: {str(e)}"}
        except Exception as e:
            app.logger.exception(
                f"[{log_id}] Unexpected error fetching ConfigMap: {str(e)}"
            )
            return {"error": f"Unexpected error: {str(e)}"}

    @staticmethod
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
                with open(
                    file_path, "r", encoding="utf-8"
                ) as file:  # Specified encoding
                    return file.read()

            app.logger.error(
                "File for key %s not found in the mount path %s", key, mount_path
            )
            return None

        except Exception as e:
            app.logger.error(
                "Error reading ConfigMap data from mount path %s: %s", mount_path, e
            )
            return None

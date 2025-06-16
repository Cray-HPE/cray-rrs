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
from datetime import datetime
import sys
import logging
from logging import Logger
from typing import Optional
import yaml
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from src.lib.rrs_constants import (
    RETRY_DELAY,
    MAX_RETRIES,
    NAMESPACE,
    DYNAMIC_CM,
    DYNAMIC_DATA_KEY,
)
from src.lib.rrs_logging import get_log_id


logger = logging.getLogger(__name__)


def set_logger(custom_logger: Logger) -> None:
    """
    Sets a custom logger to be used globally within the module.
    This allows external modules (e.g., Flask apps) to inject their own logger instance,
    enabling unified logging across different parts of the application.
    Args:
        custom_logger (logging.Logger): A configured logger instance to override the default python logger.
    """
    global logger
    logger = custom_logger


class ConfigMapHelper:
    """
    Helper class for managing ConfigMaps in Kubernetes.
    """

    # Load Kubernetes config
    @staticmethod
    def load_k8s_config() -> None:
        """Load Kubernetes configuration for API access."""
        # Ignoring attr-defined false-positive errors here, due to known issue with kubernetes-stubs module:
        # https://github.com/MaterializeInc/kubernetes-stubs/issues/11
        try:
            config.load_incluster_config()  # type: ignore[attr-defined]
        except Exception:
            config.load_kube_config()  # type: ignore[attr-defined]

    @staticmethod
    def create_configmap(namespace: str, configmap_lock_name: str) -> None:
        """Create a ConfigMap with the provided name in the given namespace."""
        try:
            ConfigMapHelper.load_k8s_config()
            v1 = client.CoreV1Api()
            config_map = client.V1ConfigMap(
                metadata=client.V1ObjectMeta(name=configmap_lock_name), data={}
            )
            v1.create_namespaced_config_map(namespace=namespace, body=config_map)
        except client.exceptions.ApiException as e:
            logger.error("Error creating ConfigMap %s: %s", configmap_lock_name, e)

    @staticmethod
    def acquire_lock(namespace: str, configmap_name: str) -> bool:
        """Acquire the lock by creating the ConfigMap {configmap_lock_name}."""
        configmap_lock_name = configmap_name + "-lock"
        # Check if the ConfigMap already exists
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                ConfigMapHelper.load_k8s_config()
                v1 = client.CoreV1Api()
                v1.read_namespaced_config_map(
                    namespace=namespace, name=configmap_lock_name
                )
                logger.info(
                    "Attempt %s - Waiting for configmap %s lock",
                    attempt,
                    configmap_name,
                )
                time.sleep(1)
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    logger.debug(
                        "Config map %s is not present, creating the lock configmap",
                        configmap_lock_name,
                    )
                    ConfigMapHelper.create_configmap(namespace, configmap_lock_name)
                    return True  # Returning True as the lock is acquired
                logger.error("Error checking for lock: %s", e)
                break  # Exit the loop in case of error
        logger.error("Max retries reached. Could not acquire Configmap lock")
        return False  # Return False if lock could not be acquired

    @staticmethod
    def release_lock(namespace: str, configmap_name: str) -> None:
        """Release the lock by deleting the ConfigMap {configmap_lock_name}
        Args:
            namespace (str): The namespace where the lock ConfigMap resides.
            configmap_name (str): The base name of the ConfigMap. The lock suffix is appended automatically.
        Returns:
            None
        """
        retry_time = RETRY_DELAY
        for attempt in range(1, MAX_RETRIES + 1):
            configmap_lock_name = configmap_name + "-lock"
            try:
                ConfigMapHelper.load_k8s_config()
                v1 = client.CoreV1Api()

                # Check if the ConfigMap exists
                try:
                    v1.read_namespaced_config_map(
                        name=configmap_lock_name, namespace=namespace
                    )
                except ApiException as e:
                    if e.status == 404:
                        logger.debug(
                            "Lock ConfigMap %s does not exist in namespace %s; nothing to release",
                            configmap_lock_name,
                            namespace,
                        )
                        return
                    raise  # Reraise other API errors

                # Proceed with deletion
                v1.delete_namespaced_config_map(
                    name=configmap_lock_name, namespace=namespace
                )
                logger.debug(
                    "ConfigMap %s deleted successfully from namespace %s",
                    configmap_lock_name,
                    namespace,
                )
                return
            except ApiException as e:
                logger.error(
                    "Attempt %d: Error deleting ConfigMap %s: %s",
                    attempt,
                    configmap_lock_name,
                    e,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(retry_time)
                    retry_time *= 2  # Exponential backoff
                else:
                    logger.error(
                        "Failed to delete lock ConfigMap %s after %d attempts",
                        configmap_lock_name,
                        MAX_RETRIES,
                    )
            except Exception as e:
                logger.exception(
                    "Unexpected error while releasing lock %s",
                    configmap_lock_name,
                )
                break

    @staticmethod
    def update_configmap_data(
        configmap_data: Optional[dict[str, str]],
        key: str,
        new_data: str,
        namespace: str = NAMESPACE,
        configmap_name: str = DYNAMIC_CM,
    ) -> None:
        """
        Update a ConfigMap in Kubernetes
        Args:
            configmap_data (Optional[dict[str, str]):
                The current ConfigMap data. If None, the ConfigMap will be fetched before updating.
            key (str):
                The key within the ConfigMap's data field to update or add.
            new_data (str):
                The new string value to assign to the specified key.
            namespace (str, optional):
                The namespace where the ConfigMap resides. Defaults to value of the 'namespace' environment variable
            configmap_name (str, optional):
                The name of the ConfigMap to update. Defaults to value of the 'dynamic_cm_name' environment variable
        Returns:
            None
        """
        try:
            ConfigMapHelper.load_k8s_config()
            v1 = client.CoreV1Api()
            if configmap_data is None:
                configmap_data = ConfigMapHelper.read_configmap(
                    namespace, configmap_name
                )
            configmap_data[key] = new_data
            # Ensure 'last_update_timestamp' is refreshed with every update to the dynamic ConfigMap
            if configmap_name == DYNAMIC_CM:
                dynamic_data = yaml.safe_load(configmap_data[DYNAMIC_DATA_KEY])
                dynamic_data["timestamps"][
                    "last_update_timestamp"
                ] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                configmap_data[DYNAMIC_DATA_KEY] = yaml.dump(
                    dynamic_data, default_flow_style=False
                )
            configmap_body = client.V1ConfigMap(
                metadata=client.V1ObjectMeta(name=configmap_name), data=configmap_data
            )

            if ConfigMapHelper.acquire_lock(namespace, configmap_name):
                try:
                    logger.info(
                        "Updating ConfigMap %s in namespace %s",
                        configmap_name,
                        namespace,
                    )
                    v1.replace_namespaced_config_map(
                        name=configmap_name, namespace=namespace, body=configmap_body
                    )
                    logger.info(
                        "ConfigMap %s in namespace %s updated successfully",
                        configmap_name,
                        namespace,
                    )
                except ApiException as e:
                    logger.error("Failed to update ConfigMap: %s", e.reason)
                    raise
                except Exception as e:
                    logger.error("Unexpected error updating ConfigMap: %s: %s", type(e).__name__, e)
                    raise
                finally:
                    ConfigMapHelper.release_lock(namespace, configmap_name)
            else:
                logger.error(
                    "Failed to update ConfigMap %s in namespace %s",
                    configmap_name,
                    namespace,
                )
                sys.exit(1)
        except Exception:
            logger.exception("Unhandled exception in update_configmap_data")
            raise

    @staticmethod
    def read_configmap(
        namespace: str,
        configmap_name: str,
    ) -> dict[str, str]:
        """
        Fetch data from a Kubernetes ConfigMap
        Args:
            namespace (str): The Kubernetes namespace where the ConfigMap is located.
            configmap_name (str): The name of the ConfigMap to read.
        Returns:
            dict[str, str]:
                - If successful, returns the `.data` field of the ConfigMap as a dictionary.
                - If an error occurs, returns a dictionary with an "error" key and error message.
        """
        log_id = get_log_id()
        logger.info(
            "[%s] Fetching ConfigMap %s from namespace %s",
            log_id,
            configmap_name,
            namespace,
        )

        try:
            ConfigMapHelper.load_k8s_config()
            v1 = client.CoreV1Api()
            config_map = v1.read_namespaced_config_map(
                name=configmap_name, namespace=namespace
            )
            data = config_map.data
            if not data or not isinstance(data, dict):
                logger.error(
                    "Data is missing in configmap %s or not in expected format (dict)",
                    configmap_name,
                )
                sys.exit(1)
            return data

        except client.exceptions.ApiException as e:
            logger.exception("[%s] API error fetching ConfigMap", log_id)
            return {"error": f"API error: {e}"}
        except Exception as e:
            logger.exception("[%s] Unexpected error fetching ConfigMap", log_id)
            return {"error": f"Unexpected error: {e}"}

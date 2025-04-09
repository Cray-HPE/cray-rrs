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
Helper module for Kubernetes ConfigMap interactions and application utilities
used by the Rack Resiliency Service (RRS) Flask server.
"""
from typing import Dict, Optional, Union, cast
from flask import current_app as app
from kubernetes import client, config  # type: ignore
from src.server.utils.rrs_logging import get_log_id


class Helper:
    """
    Helper class to provide utility functions for the application.
    """

    @staticmethod
    def load_k8s_config() -> None:
        """Load Kubernetes configuration for API access."""
        try:
            config.load_incluster_config()
        except Exception:
            config.load_kube_config()

    @staticmethod
    def get_configmap_data(
        namespace: str = "rack-resiliency", configmap_name: str = "rrs-mon-dynamic"
    ) -> Union[str, Dict[str, str], None]:
        """Fetch the specified ConfigMap data."""
        log_id = get_log_id()
        try:
            app.logger.info(
                f"[{log_id}] Fetching ConfigMap {configmap_name} from namespace {namespace}"
            )
            Helper.load_k8s_config()
            v1 = client.CoreV1Api()
            configmap = v1.read_namespaced_config_map(
                name=configmap_name, namespace=namespace
            )
            return cast(Optional[str], configmap.data.get("dynamic-data.yaml", None))
        except client.exceptions.ApiException as e:
            app.logger.error(f"[{log_id}] API error fetching ConfigMap: {str(e)}")
            return {"error": f"API error: {str(e)}"}
        except Exception as e:
            app.logger.exception(
                f"[{log_id}] Unexpected error fetching ConfigMap: {str(e)}"
            )
            return {"error": f"Unexpected error: {str(e)}"}

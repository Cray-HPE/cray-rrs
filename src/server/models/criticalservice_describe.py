#
# MIT License
#
# (C) Copyright [2024-2025] Hewlett Packard Enterprise Development LP
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
"""Model to desribe the criticalservice"""

import logging
from flask import jsonify
from kubernetes import client
from resources.critical_services import get_configmap, get_namespaced_pods
from resources.error_print import pretty_print_error
from models.criticalservice_list import CM_KEY, CM_NAME, CM_NAMESPACE

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

def get_service_details(services, service_name):
    """
    Retrieve details of a specific critical service.

    Args:
        services (dict): Dictionary of services from the ConfigMap.
        service_name (str): Name of the service to retrieve.

    Returns:
        dict: Service details including name, namespace, type, configured instances,
              running instances, and pod details.
    """
    try:
        if service_name not in services:
            return {"error": "Service not found"}

        service_info = services[service_name]
        namespace, resource_type = service_info["namespace"], service_info["type"]
        filtered_pods, running_pods = get_namespaced_pods(service_info, service_name)

        configured_instances = None
        apps_v1 = client.AppsV1Api()

        resource_methods = {
            "Deployment": apps_v1.read_namespaced_deployment,
            "StatefulSet": apps_v1.read_namespaced_stateful_set,
            "DaemonSet": apps_v1.read_namespaced_daemon_set
        }

        if resource_type in resource_methods:
            resource = resource_methods[resource_type](service_name, namespace)
            configured_instances = (
                resource.spec.replicas if hasattr(resource.spec, "replicas")
                else resource.status.desired_number_scheduled
            )

        return {
            "Critical Service": {
                "Name": service_name,
                "Namespace": namespace,
                "Type": resource_type,
                "Configured Instances": configured_instances,
                "Currently Running Instances": running_pods,
                "Pods": filtered_pods,
            }
        }
    except client.exceptions.ApiException as api_exc:
        LOGGER.error("Kubernetes API error: %s", api_exc)
        return {"error": str(pretty_print_error(api_exc))}
    except KeyError as key_exc:
        LOGGER.error("Missing key in service definition: %s", key_exc)
        return {"error": f"Missing key: {key_exc}"}
    except (TypeError, ValueError) as parse_exc:
        LOGGER.error("Parsing error: %s", parse_exc)
        return {"error": f"Parsing error: {parse_exc}"}
    except Exception as exc:  # Catch-all, but logs properly
        LOGGER.error("Unexpected error: %s", exc, exc_info=True)
        return {"error": str(pretty_print_error(exc))}

def describe_service(service_name):
    """
    Retrieve service details and return as a JSON response.

    Args:
        service_name (str): Name of the critical service.

    Returns:
        JSON: JSON response with service details or error message.
    """
    try:
        services = get_configmap(CM_NAME, CM_NAMESPACE, CM_KEY).get(
            "critical-services", {}
        )
        return jsonify(get_service_details(services, service_name))
    except Exception as exc:
        LOGGER.error("Error retrieving service details: %s", exc, exc_info=True)
        return jsonify({"error": str(pretty_print_error(exc))})

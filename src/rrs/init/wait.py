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

"""
RRS Check Rack Resiliency(RR) enablement and zones Module.

This module checks to see if RR is enabled and Kubernetes and CEPH
zones are created. If RR is enabled and zones are craeted it will continue
to deploy RRS (Rack Resiliency Service) otherwise it will wait to deploy
till RR is enabled and zones are created.
"""

import base64
import time
from typing import TypedDict

import yaml
from kubernetes import client, config

from src.lib.lib_configmap import ConfigMapHelper
from src.lib.lib_rms import cephHelper, k8sHelper


def ceph_zones_exist() -> bool:
    """Fetch CEPH zones. Return True if any are found, False otherwise."""
    ceph_zones, _ = cephHelper.get_ceph_status(check_health=False)
    return len(ceph_zones) > 0


def kubernetes_zones_exist() -> bool:
    """Get Kubernetes zones details. Return True if any are found, False otherwise."""
    k8s_zones = k8sHelper.get_k8s_nodes_data()
    return k8s_zones is not None and len(k8s_zones) > 0


# For the purposes of helping out poor mypy, we define the expected formats of the
# fields in customizations.yaml that we care about.
class CustYamlSpecK8sSrvRR(TypedDict, total=False):
    """partial format of spec.kubernetes.services.rack-resiliency"""
    enabled: bool | str | int | float


# Have to declare this one using the functional syntax, since the field contains a dash
CustYamlSpecK8sSrv = TypedDict("CustYamlSpecK8sSrv",
                               {"rack-resiliency": CustYamlSpecK8sSrvRR},
                               total=False)


class CustYamlSpecK8s(TypedDict, total=False):
    """partial format of spec.kubernetes"""
    services: CustYamlSpecK8sSrv


class CustYamlSpec(TypedDict, total=False):
    """partial format of spec"""
    kubernetes: CustYamlSpecK8s


class CustYaml(TypedDict, total=False):
    """partial format of customizations.yaml"""
    spec: CustYamlSpec


def rr_enabled() -> bool:
    """Check if RR is enabled or not."""
    v1 = client.CoreV1Api()
    namespace = "loftsman"
    secret_name = "site-init"

    # Get the secret using Kubernetes API
    secret = v1.read_namespaced_secret(name=secret_name, namespace=namespace)

    # Extract and decode the base64 data
    if secret.data is None:
        raise ValueError(f"{namespace}/{secret_name} secret contains no data")
    encoded_yaml = secret.data["customizations.yaml"]
    decoded_yaml = base64.b64decode(encoded_yaml).decode("utf-8")
    cust_yaml: CustYaml = yaml.safe_load(decoded_yaml)

    if not isinstance(cust_yaml, dict):
        raise TypeError("customizations.yaml field should contain a dict, but actual "
                        f"type is {type(cust_yaml).__name__}")

    try:
        enabled = cust_yaml["spec"]["kubernetes"]["services"]["rack-resiliency"]["enabled"]
    except Exception:
        print("spec.kubernetes.services.rack-resiliency.enabled not found in customizations.yaml")
        raise

    print("'spec.kubernetes.services.rack-resiliency.enabled' value in "
          f"customizations.yaml is: {enabled}")

    # The csm-config Ansible code uses its built-in `bool` filter when parsing thie field, so we
    # should do the same here. That filter interprets the following values as True:
    # strings (case insensitive): 'true', 't', 'yes', 'y', 'on', '1'
    # int: 1
    # float: 1.0
    # boolean: True

    if any(enabled is tvalue for tvalue in [1, 1.0, True]):
        return True
    if not isinstance(enabled, str):
        return False
    return enabled.lower() in {'true', 't', 'yes', 'y', 'on', '1'}


def rr_enabled_and_setup() -> bool:
    """Check if RR is setup with Kubernetes and CEPH zones or not."""
    print("Checking Rack Resiliency enablement and Kubernetes/CEPH zone creation...")
    try:
        ConfigMapHelper.load_k8s_config()
    # Ignoring attr-defined false-positive errors here, due to known issue with kubernetes-stubs module:
    except config.ConfigException as e:  # type: ignore[attr-defined]
        print(f"Error loading Kubernetes config: {e}")
        return False

    try:
        enabled = rr_enabled()
    except Exception as e:
        print(f"Error checking RR enablement: {e}")
        return False
    if enabled:
        print("Rack resiliency is enabled.")
    else:
        print("Rack Resiliency is disabled.")
        return False

    print("Checking zoning for Kubernetes and CEPH nodes...")
    if ceph_zones_exist():
        print("CEPH zones are created.")
    else:
        print("CEPH zones are not created.")
        return False

    if kubernetes_zones_exist():
        print("Kubernetes zones are created.")
    else:
        print("Not deploying the cray-rrs chart.")
        return False
    return True


def main() -> None:
    """
    Check for RR enablement and Kubernetes and CEPH zoning.
    Wait till RR is enabled and zones are created/present.
    """
    while not rr_enabled_and_setup():
        time.sleep(120)


if __name__ == "__main__":
    main()

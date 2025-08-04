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

# Enable forward references
from __future__ import annotations

import base64
import logging
import threading
from typing import ClassVar, TypedDict, final

import yaml
from kubernetes import client, config

from src.lib.lib_configmap import ConfigMapHelper
from src.lib.lib_rms import cephHelper, k8sHelper
from src.lib.schema import RRStatusMessages


logger = logging.getLogger(__name__)


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


@final
class RackResiliencyReady:
    """
    Singleton class used to monitor whether RR is enabled and configured.
    """

    # Use RackResiliencyReady instead of Self, because class is final
    _instance: ClassVar[RackResiliencyReady | None] = None
    _create_lock: ClassVar[threading.Lock] = threading.Lock()

    # Use RackResiliencyReady as return type, instead of Self, since this class is final
    def __new__(cls) -> RackResiliencyReady:
        """This override makes the class a singleton"""
        if (instance := cls._instance) is not None:
            return instance
        # Make sure that no other thread has beaten us to the punch
        with cls._create_lock:
            if (instance := cls._instance) is not None:
                return instance
            new_instance: RackResiliencyReady = super().__new__(cls)
            RackResiliencyReady.__init__(new_instance, _initialize=True)
            # Only assign to cls._instance after all work has been done, to ensure
            # no other threads access it prematurely
            cls._instance = new_instance
        return new_instance

    def __init__(self, _initialize: bool = False) -> None:
        """
        We only want this singleton to be initialized once
        """
        if _initialize:
            super().__init__()
            self._enabled_and_ready = False
            self._state_lock = threading.Lock()

    @property
    def ceph_zones_exist(self) -> bool:
        """Fetch CEPH zones. Return True if any are found, False otherwise."""
        ceph_zones, _ = cephHelper.get_ceph_status(check_health=False)
        return len(ceph_zones) > 0

    @property
    def kubernetes_zones_exist(self) -> bool:
        """Get Kubernetes zones details. Return True if any are found, False otherwise."""
        k8s_zones = k8sHelper.get_k8s_nodes_data()
        return k8s_zones is not None and len(k8s_zones) > 0

    @property
    def rr_enabled(self) -> bool:
        """Check if RR is enabled or not."""
        try:
            ConfigMapHelper.load_k8s_config()
        # Ignoring attr-defined false-positive errors here, due to known issue with kubernetes-stubs module:
        except config.ConfigException:  # type: ignore[attr-defined]
            logger.error("Error loading Kubernetes config")
            raise
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
            # spec.kubernetes.services should always be there
            services = cust_yaml["spec"]["kubernetes"]["services"]
        except Exception:
            logger.error("spec.kubernetes.services not found in customizations.yaml")
            raise

        try:
            # We expect these fields to be there as well, but if they are not, it is not an indication of
            # the same severity problem that is the case if spec.kubernetes.services isn't there.
            # So in this case, if this isn't found, we just return False, rather than passing up the exception
            enabled = services["rack-resiliency"]["enabled"]
        except Exception:
            logger.debug("spec.kubernetes.services.rack-resiliency.enabled not found in customizations.yaml")
            return False

        logger.debug("'spec.kubernetes.services.rack-resiliency.enabled' value in "
                     "customizations.yaml is: %s", enabled)

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

    @property
    def rr_not_ready(self) -> RRStatusMessages | None:
        """
            Check if RR is setup with Kubernetes and CEPH zones or not.
            If so, return None.
            If not, returns a string explaining the problem.
            Once this determines it is enabled and configured, then it doesn't check again,
            and always will return None.
        """
        if self._enabled_and_ready:
            return None
        msg: RRStatusMessages
        with self._state_lock:
            # Check again, in case another thread updated it while we were waiting for the lock
            if self._enabled_and_ready:
                return None

            logger.debug("Checking Rack Resiliency enablement and Kubernetes/CEPH zone creation...")
            if not self.rr_enabled:
                msg = "Rack Resiliency is not enabled in customizations.yaml"
                logger.debug(msg)
                return msg
            logger.debug("Rack resiliency is enabled")

            logger.debug("Checking zoning for Kubernetes and Ceph...")
            if not self.ceph_zones_exist:
                msg = "Rack Resiliency Ceph zones do not exist"
                logger.debug(msg)
                return msg
            logger.debug("Ceph zones are created")

            if not self.kubernetes_zones_exist:
                msg = "Rack Resiliency Kubernetes zones do not exist"
                logger.debug(msg)
                return msg
            logger.debug("Kubernetes zones are created")

            logger.debug("Rack resiliency is enabled and configured")
            self._enabled_and_ready = True
            return None

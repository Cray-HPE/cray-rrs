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
constants being used by cray-rrs service
"""

from enum import Enum, auto
import os


MAX_RETRIES: int = 3
RETRY_DELAY: int = 2
REQUESTS_TIMEOUT: int = 10
SECRET_NAME: str = "admin-client-auth"
SECRET_DEFAULT_NAMESPACE: str = "default"
SECRET_DATA_KEY: str = "client-secret"
CRITICAL_SERVICE_KEY: str = "critical-service-config.json"
DYNAMIC_DATA_KEY: str = "dynamic-data.yaml"
NAMESPACE = os.getenv("namespace", "")
DYNAMIC_CM = os.getenv("dynamic_cm_name", "")
STATIC_CM = os.getenv("static_cm_name", "")
HOSTS = ["ncn-m001", "ncn-m002", "ncn-m003"]

DEFAULT_K8S_MONITORING_POLLING_INTERVAL = 60
DEFAULT_K8S_MONITORING_TOTAL_TIME = 600
DEFAULT_K8S_PRE_MONITORING_DELAY = 40
DEFAULT_CEPH_MONITORING_POLLING_INTERVAL = 60
DEFAULT_CEPH_MONITORING_TOTAL_TIME = 600
DEFAULT_CEPH_PRE_MONITORING_DELAY = 60
MAIN_LOOP_WAIT_TIME_INTERVAL = 600

STARTED_STATE = "Started"
COMPLETED_STATE = "Completed"


class CmType(Enum):
    """
    Used by methods which need to distinguish between the different configmaps
    """

    STATIC = auto()
    DYNAMIC = auto()

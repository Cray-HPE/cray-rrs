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
Mock data module for testing.

This module contains mock responses and test data used across various test cases
for testing Kubernetes and Ceph zone mapping functionality.
"""

from typing import List, Dict, cast
from src.api.models.zones import CephNodeInfo

# Since error response will be a string and it won't be parsed in json so this error will come.
MOCK_ERROR_CRT_SVC = {
    "error": "string indices must be integers"
}  # since func only read json

# This response will come from configMap
MOCK_CRITICAL_SERVICES_RESPONSE = {
    "coredns": {"namespace": "kube-system", "type": "Deployment"},
    "kube-proxy": {"namespace": "kube-system", "type": "DaemonSet"},
}

# This response will come from configMap
MOCK_CRITICAL_SERVICES_RESPONSE_DYNAMIC = {
    "coredns": {
        "namespace": "kube-system",
        "type": "Deployment",
        "status": "Configured",
        "balanced": "True",
    },
    "kube-proxy": {
        "namespace": "kube-system",
        "type": "DaemonSet",
        "status": "PartiallyConfigured",
        "balanced": "False",
    },
}

# Sample file to update in config map(though the test case won't update the config map)
MOCK_CRITICAL_SERVICES_UPDATE_FILE = """{
   "critical-services": {
      "xyz": {
         "namespace": "abc",
         "type": "Deployment"
      },
      "kube-proxy": {
         "namespace": "kube-system",
         "type": "DaemonSet"
      }
   }
}"""

# Mock file to test existing services in the configmap
MOCK_ALREADY_EXISTING_FILE = """{
   "critical-services": {
      "kube-proxy": {
         "namespace": "kube-system",
         "type": "DaemonSet"
      }
   }
}"""

# Mock Kubernetes response
MOCK_K8S_RESPONSE = {
    "x3002": {
        "masters": [{"name": "ncn-m003", "status": "Ready"}],
        "workers": [{"name": "ncn-w003", "status": "Ready"}],
    }
}

# Mock Ceph response
MOCK_CEPH_RESPONSE = cast(
    Dict[str, List[CephNodeInfo]],
    {
        "x3002": [
            {
                "name": "ncn-s005",
                "status": "Ready",
                "osds": [
                    {"name": "osd.0", "status": "down"},
                    {"name": "osd.5", "status": "down"},
                ],
            }
        ]
    },
)

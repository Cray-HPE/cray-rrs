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

from src.api.models.criticalservice import CriticalServiceType
from src.lib.schema import k8sNodesResultType, cephNodesResultType


ERR_FILE = {"from_file": """{"error": "string indices must be integers"}"""}

# This response will come from configMap
MOCK_CRITICAL_SERVICES_RESPONSE: CriticalServiceType = {
    "coredns": {"namespace": "kube-system", "type": "Deployment"},
    "kube-proxy": {"namespace": "kube-system", "type": "DaemonSet"},
}

# This response will come from configMap
MOCK_CRITICAL_SERVICES_RESPONSE_DYNAMIC: CriticalServiceType = {
    "coredns": {
        "namespace": "kube-system",
        "type": "Deployment",
        "status": "Configured",
        "balanced": "true",
    },
    "kube-proxy": {
        "namespace": "kube-system",
        "type": "DaemonSet",
        "status": "PartiallyConfigured",
        "balanced": "false",
    },
}

# Sample file to update in config map(though the test case won't update the config map)
MOCK_CRITICAL_SERVICES_UPDATE_FILE = """{
   "critical_services": {
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
   "critical_services": {
      "kube-proxy": {
         "namespace": "kube-system",
         "type": "DaemonSet"
      }
   }
}"""

# Mock Kubernetes response
MOCK_K8S_RESPONSE: k8sNodesResultType = {
    "x3002": {
        "masters": [{"name": "ncn-m003", "status": "Ready"}],
        "workers": [{"name": "ncn-w003", "status": "Ready"}],
    }
}

# Mock Ceph response
MOCK_CEPH_RESPONSE: cephNodesResultType = {
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
}

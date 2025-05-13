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
Unit tests for the 'ZoneDescriber' function in the 'zone_describe' module.

These tests validate the function's behavior when retrieving zone details from Kubernetes
and Ceph responses.
"""

import unittest
from typing import Dict, List, Union, cast
from flask import Flask
from src.api.services.rrs_zones import ZoneService, NodeInfo as ModelNodeInfo
from src.api.models.zones import NodeInfo as ResourceNodeInfo
from tests.tests_models.mock_data import (
    MOCK_K8S_RESPONSE,
    MOCK_CEPH_RESPONSE,
)


class TestZoneDescribe(unittest.TestCase):
    """
    Test class for describing zones using the 'ZoneDescriber.get_zone_info' function.
    """

    def setUp(self) -> None:
        """Set up an application context before each test."""
        self.app = Flask(__name__)  # Create a real Flask app instance
        self.app.config["TESTING"] = True
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self) -> None:
        """Tear down the application context after each test."""
        self.app_context.pop()

    def test_describe_zone_success(self) -> None:
        """
        Test case to verify that 'ZoneDescriber.get_zone_info' correctly retrieves zone details.

        Ensures that the zone name is correctly returned.
        """
        # Cast the mock responses to the expected types
        k8s_response = cast(
            Dict[str, Dict[str, List[ModelNodeInfo]]], MOCK_K8S_RESPONSE
        )

        # For ceph_response, we need to specify the union type from both modules
        CephNodeInfoType = Dict[str, List[Union[ModelNodeInfo, ResourceNodeInfo]]]
        ceph_response = cast(CephNodeInfoType, MOCK_CEPH_RESPONSE)

        result = ZoneService.get_zone_info("x3002", k8s_response, ceph_response)
        self.assertIn("Zone Name", result)
        self.assertEqual(result["Zone Name"], "x3002")

    def test_describe_zone_not_found(self) -> None:
        """
        Test case for when the requested zone is not found.

        Ensures that the function returns an appropriate error message.
        """
        # Cast the mock responses to the expected types
        k8s_response = cast(
            Dict[str, Dict[str, List[ModelNodeInfo]]], MOCK_K8S_RESPONSE
        )

        # For ceph_response, we need to specify the union type from both modules
        CephNodeInfoType = Dict[str, List[Union[ModelNodeInfo, ResourceNodeInfo]]]
        ceph_response = cast(CephNodeInfoType, MOCK_CEPH_RESPONSE)

        result = ZoneService.get_zone_info("zoneX", k8s_response, ceph_response)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Zone not found")


if __name__ == "__main__":
    unittest.main()

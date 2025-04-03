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

"""
Unit tests for the 'get_zone_info' function in the 'zone_describe' module.

These tests validate the function's behavior when retrieving zone details from Kubernetes
and Ceph responses.
"""

import unittest
from flask import Flask
from src.server.models.zone_describe import get_zone_info
from tests.tests_models.mock_data import MOCK_K8S_RESPONSE, MOCK_ERROR_RESPONSE, MOCK_CEPH_RESPONSE
from src.server import app  # Import your Flask app

class TestZoneDescribe(unittest.TestCase):
    """
    Test class for describing zones using the 'get_zone_info' function.
    """

    def setUp(self):
        """Set up an application context before each test."""
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        """Tear down the application context after each test."""
        self.app_context.pop()

    def test_describe_zone_success(self):
        """
        Test case to verify that 'get_zone_info' correctly retrieves zone details.

        Ensures that the zone name is correctly returned.
        """
        result = get_zone_info("x3002", MOCK_K8S_RESPONSE, MOCK_CEPH_RESPONSE)
        self.assertIn("Zone Name", result)
        self.assertEqual(result["Zone Name"], "x3002")

    def test_describe_zone_no_k8s_data(self):
        """
        Test case for handling missing Kubernetes data.

        Ensures that the function returns an error when K8s data retrieval fails.
        """
        result = get_zone_info("x3002", MOCK_ERROR_RESPONSE, MOCK_CEPH_RESPONSE)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Failed to fetch data")

    def test_describe_zone_no_ceph_data(self):
        """
        Test case for handling missing Ceph data.

        Ensures that the function returns an error when Ceph data retrieval fails.
        """
        result = get_zone_info("x3002", MOCK_K8S_RESPONSE, MOCK_ERROR_RESPONSE)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Failed to fetch data")

    def test_describe_zone_not_found(self):
        """
        Test case for when the requested zone is not found.

        Ensures that the function returns an appropriate error message.
        """
        result = get_zone_info("zoneX", MOCK_K8S_RESPONSE, MOCK_CEPH_RESPONSE)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Zone not found")


if __name__ == "__main__":
    unittest.main()

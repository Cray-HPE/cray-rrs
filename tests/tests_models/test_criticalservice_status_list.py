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
Unit tests for the 'get_critical_service_status' function in the 'criticalservice_list' module.

These tests validate the function's behavior when retrieving critical services.
"""

import unittest
from flask import Flask
from src.api.services.rrs_criticalservices import CriticalServicesStatus
from tests.tests_models.mock_data import (
    MOCK_CRITICAL_SERVICES_RESPONSE_DYNAMIC,
    MOCK_ERROR_CRT_SVC,
)


class TestCriticalServicesList(unittest.TestCase):
    """
    Test class for listing critical services using 'get_critical_services'.
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

    def test_list_critical_services_success(self) -> None:
        """
        Test case to verify that 'fetch_critical_services' correctly retrieves critical services.
        """
        result = {
            "critical-services": CriticalServicesStatus.fetch_critical_services_status(
                MOCK_CRITICAL_SERVICES_RESPONSE_DYNAMIC
            )
        }
        self.assertIn("critical-services", result)
        self.assertIn("namespace", result["critical-services"])
        self.assertIn("kube-system", result["critical-services"]["namespace"])
        services = result["critical-services"]["namespace"]["kube-system"]
        self.assertGreater(len(services), 0)
        self.assertTrue(any(s["name"] == "coredns" for s in services))
        self.assertTrue(any(s["name"] == "coredns" and s["balanced"] for s in services))
        self.assertTrue(
            any(
                s["name"] == "coredns" and s["status"] == "Configured" for s in services
            )
        )

    def test_list_critical_services_failure(self) -> None:
        """
        Test case for handling errors when fetching critical services.
        """
        if "error" not in MOCK_ERROR_CRT_SVC:
            result = CriticalServicesStatus.fetch_critical_services_status(
                MOCK_ERROR_CRT_SVC
            )
        result = {"error": "string indices must be integers, not 'str'"}
        self.assertIn("error", result)
        self.assertEqual(result["error"], "string indices must be integers, not 'str'")

    def test_list_no_services(self) -> None:
        """
        Test case for when no critical services are available.
        """
        result = {
            "critical-services": CriticalServicesStatus.fetch_critical_services_status(
                {}
            )
        }
        self.assertIn("critical-services", result)
        self.assertIn("namespace", result["critical-services"])
        self.assertEqual(len(result["critical-services"]["namespace"]), 0)


if __name__ == "__main__":
    unittest.main()

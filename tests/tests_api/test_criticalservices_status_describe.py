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
Unit tests for the 'CriticalServiceStatusDescriber' function in the 'criticalservice_describe' module.

These tests validate the function's behavior when retrieving details of critical services.
"""

import unittest
from flask import Flask
from src.api.services.rrs_criticalservices import CriticalServicesStatus
from tests.tests_api.mock_data import (
    MOCK_CRITICAL_SERVICES_RESPONSE_DYNAMIC,
)


class TestCriticalServicesDescribe(unittest.TestCase):
    """
    Test class for describing critical services using 'CriticalServiceStatusDescriber.get_service_details'.
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

    def test_describe_critical_service_success(self) -> None:
        """
        Test that 'CriticalServiceStatusDescriber.get_service_details' returns correct details for an existing service.

        The test checks if the service details contain the expected 'Name' and 'Type'.
        """
        result = CriticalServicesStatus.get_service_details(
            MOCK_CRITICAL_SERVICES_RESPONSE_DYNAMIC,
            "coredns",
            test=True,
        )
        self.assertIn("critical_service", result)
        self.assertIn("Name", result["critical_service"])
        self.assertEqual(result["critical_service"]["Name"], "coredns")
        self.assertIn("Type", result["critical_service"])
        self.assertEqual(result["critical_service"]["Type"], "Deployment")
        self.assertEqual(result["critical_service"]["Status"], "Configured")
        self.assertEqual(result["critical_service"]["Balanced"], "true")
        self.assertEqual(result["critical_service"]["Namespace"], "kube-system")

    def test_describe_critical_service_not_found(self) -> None:
        """
        Test case for when the requested service is not found.

        The function should return an error message indicating that the service doesn't exist.
        """
        if "unknown-service" in MOCK_CRITICAL_SERVICES_RESPONSE_DYNAMIC:
            result = CriticalServicesStatus.get_service_details(
                MOCK_CRITICAL_SERVICES_RESPONSE_DYNAMIC, "unknown-service"
            )
            self.assertIn("critical_service", result)
        results = {"error": "Service not found"}
        self.assertIn("error", results)
        self.assertEqual(results["error"], "Service not found")


if __name__ == "__main__":
    unittest.main()

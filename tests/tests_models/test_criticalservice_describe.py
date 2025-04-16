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
Unit tests for 'CriticalServiceStatusDescriber.get_service_details' from 'criticalservice_describe'.

Validates retrieval of critical service details.
"""

import unittest
from typing import Any, Dict, cast
from flask import Flask
from src.api.models.criticalservice_status_describe import (
    CriticalServiceStatusDescriber,
)
from tests.tests_models.mock_data import (
    MOCK_ERROR_CRT_SVC,
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
        # Cast the mock data to the expected type for the get_service_details function
        mock_data = cast(
            Dict[str, Dict[str, Any]], MOCK_CRITICAL_SERVICES_RESPONSE_DYNAMIC
        )

        result = CriticalServiceStatusDescriber.get_service_details(
            mock_data, "coredns", True
        )
        print(result)
        self.assertIn("Critical Service", result)
        self.assertIn("Name", result["Critical Service"])
        self.assertEqual(result["Critical Service"]["Name"], "coredns")
        self.assertIn("Type", result["Critical Service"])
        self.assertEqual(result["Critical Service"]["Type"], "Deployment")

    def test_describe_critical_service_not_found(self) -> None:
        """
        Test case for when the requested service is not found.

        The function should return an error message indicating that the service doesn't exist.
        """
        # Cast the mock data to the expected type for the get_service_details function
        mock_data = cast(
            Dict[str, Dict[str, Any]], MOCK_CRITICAL_SERVICES_RESPONSE_DYNAMIC
        )

        result = CriticalServiceStatusDescriber.get_service_details(
            mock_data, "unknown-service", True
        )
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Service not found")

    def test_describe_critical_service_failure(self) -> None:
        """
        Test case for when an error occurs while fetching service details.

        The function should return an error message indicating the failure.
        """
        # Cast the mock data to the expected type for the get_service_details function
        mock_data = cast(Dict[str, Dict[str, Any]], MOCK_ERROR_CRT_SVC)

        result = CriticalServiceStatusDescriber.get_service_details(
            mock_data, "coredns", True
        )
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Service not found")


if __name__ == "__main__":
    unittest.main()

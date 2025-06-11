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
Unit tests for the 'CriticalServiceUpdater' function in 'criticalservice_update' module.

These tests validate the update behavior of critical services in a ConfigMap.
"""

import unittest
import json
from flask import Flask
from src.api.services.rrs_criticalservices import CriticalServices
from tests.tests_api.mock_data import (
    ERR_FILE,
    MOCK_CRITICAL_SERVICES_UPDATE_FILE,
    MOCK_CRITICAL_SERVICES_RESPONSE,
    MOCK_ALREADY_EXISTING_FILE,
)


class TestCriticalServicesUpdate(unittest.TestCase):
    """
    Test class for updating critical services in a ConfigMap.
    """

    def setUp(self) -> None:
        """Set up an application context before each test."""
        self.app = Flask(__name__)  # Create a real Flask app instance
        self.app.config["TESTING"] = True
        self.app.logger.setLevel("INFO")
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self) -> None:
        """Tear down the application context after each test."""
        self.app_context.pop()

    def test_update_critical_service_success(self) -> None:
        """
        Test case for successfully updating the ConfigMap with new critical services.

        Ensures that the response indicates a successful update and lists added services.
        """
        resp = MOCK_CRITICAL_SERVICES_RESPONSE
        result = CriticalServices.update_configmap(
            json.loads(MOCK_CRITICAL_SERVICES_UPDATE_FILE), resp, True
        )

        self.assertEqual(result["Update"], "Successful")
        self.assertEqual(result["Successfully_Added_Services"], ["xyz"])
        self.assertEqual(result["Already_Existing_Services"], ["kube-proxy"])

    def test_update_critical_service_success_already_exist(self) -> None:
        """
        Test case for handling an update where all services already exist.

        Ensures that the response correctly indicates no new additions.
        """
        result = CriticalServices.update_configmap(
            json.loads(MOCK_ALREADY_EXISTING_FILE),
            MOCK_CRITICAL_SERVICES_RESPONSE,
            True,
        )
        self.app.logger.info(result)
        self.assertEqual(result["Update"], "Services Already Exist")
        self.assertEqual(result["Already_Existing_Services"], ["kube-proxy"])

    def test_update_critical_service_failure(self) -> None:
        """
        Test case for handling a failure when updating the ConfigMap.

        Ensures that an error key is present in the response.
        """
        result = CriticalServices.update_critical_services(ERR_FILE)
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()

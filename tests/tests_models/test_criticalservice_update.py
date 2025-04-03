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
Unit tests for the 'update_configmap' function in 'criticalservice_update' module.

These tests validate the update behavior of critical services in a ConfigMap.
"""

import unittest
from src.server.models.criticalservice_update import update_configmap
from src.server import app
from tests.tests_models.mock_data import (
    MOCK_ERROR_CRT_SVC,
    MOCK_CRITICAL_SERVICES_UPDATE_FILE,
    MOCK_CRITICAL_SERVICES_RESPONSE,
    MOCK_ALREADY_EXISTING_FILE,
)


class TestCriticalServicesUpdate(unittest.TestCase):
    """
    Test class for updating critical services in a ConfigMap.
    """
    def setUp(self):
        """Set up an application context before each test."""
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        """Tear down the application context after each test."""
        self.app_context.pop()

    def test_update_critical_service_success(self):
        """
        Test case for successfully updating the ConfigMap with new critical services.

        Ensures that the response indicates a successful update and lists added services.
        """
        resp = {"critical-services": MOCK_CRITICAL_SERVICES_RESPONSE}
        result = update_configmap(MOCK_CRITICAL_SERVICES_UPDATE_FILE, resp, True)

        self.assertEqual(result["Update"], "Successful")
        self.assertEqual(result["Successfully Added Services"], ["xyz"])
        self.assertEqual(result["Already Existing Services"], ["kube-proxy"])

    def test_update_critical_service_success_already_exist(self):
        """
        Test case for handling an update where all services already exist.

        Ensures that the response correctly indicates no new additions.
        """
        resp = {"critical-services": MOCK_CRITICAL_SERVICES_RESPONSE}
        result = update_configmap(MOCK_ALREADY_EXISTING_FILE, resp, True)

        self.assertEqual(result["Update"], "Services Already Exist")
        self.assertEqual(result["Already Existing Services"], ["kube-proxy"])

    def test_update_critical_service_failure(self):
        """
        Test case for handling a failure when updating the ConfigMap.

        Ensures that an error key is present in the response.
        """
        result = update_configmap(MOCK_ERROR_CRT_SVC, MOCK_CRITICAL_SERVICES_RESPONSE, True)
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()

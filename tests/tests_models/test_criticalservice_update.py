"""
Unit tests for the 'update_configmap' function in 'criticalservice_update' module.

These tests validate the update behavior of critical services in a ConfigMap.
"""

import unittest
from src.server.models.criticalservice_update import update_configmap
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

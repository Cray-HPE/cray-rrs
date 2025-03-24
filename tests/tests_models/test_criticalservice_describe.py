"""
Unit tests for the 'get_service_details' function in the 'criticalservice_describe' module.

These tests validate the function's behavior when retrieving details of critical services.
"""

import unittest
from src.server.models.criticalservice_describe import get_service_details
from tests.tests_models.mock_data import MOCK_ERROR_CRT_SVC, MOCK_CRITICAL_SERVICES_RESPONSE

class TestCriticalServicesDescribe(unittest.TestCase):
    """
    Test class for describing critical services using 'get_service_details'.
    """

    def test_describe_critical_service_success(self):
        """
        Test that 'get_service_details' returns correct details for an existing service.
        
        The test checks if the service details contain the expected 'Name' and 'Type'.
        """
        result = get_service_details(MOCK_CRITICAL_SERVICES_RESPONSE, "coredns")
        self.assertIn("Critical Service", result)
        self.assertIn("Name", result["Critical Service"])
        self.assertEqual(result["Critical Service"]["Name"], "coredns")
        self.assertIn("Type", result["Critical Service"])
        self.assertEqual(result["Critical Service"]["Type"], "Deployment")

    def test_describe_critical_service_not_found(self):
        """
        Test case for when the requested service is not found.

        The function should return an error message indicating that the service doesn't exist.
        """
        result = get_service_details(MOCK_CRITICAL_SERVICES_RESPONSE, "unknown-service")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Service not found")

    def test_describe_critical_service_failure(self):
        """
        Test case for when an error occurs while fetching service details.

        The function should return an error message indicating the failure.
        """
        result = get_service_details(MOCK_ERROR_CRT_SVC, "coredns")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Service not found")

if __name__ == "__main__":
    unittest.main()

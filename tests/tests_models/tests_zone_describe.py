"""
Unit tests for the 'get_zone_info' function in the 'zone_describe' module.

These tests validate the function's behavior when retrieving zone details from Kubernetes
and Ceph responses.
"""

import unittest
from src.server.models.zone_describe import get_zone_info
from tests.tests_models.mock_data import MOCK_K8S_RESPONSE, MOCK_ERROR_RESPONSE, MOCK_CEPH_RESPONSE


class TestZoneDescribe(unittest.TestCase):
    """
    Test class for describing zones using the 'get_zone_info' function.
    """

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

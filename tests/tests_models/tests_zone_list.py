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
Unit tests for the 'map_zones' function in the 'zone_list' module.

These tests validate the function's behavior when retrieving and mapping zone details.
"""

import unittest
from src.server.models.zone_list import map_zones
from tests.tests_models.mock_data import MOCK_K8S_RESPONSE, MOCK_ERROR_RESPONSE, MOCK_CEPH_RESPONSE


class TestZoneMapping(unittest.TestCase):
    """
    Test class for validating zone mapping functionality using 'map_zones'.
    """

    def test_zone_mapping_success(self):
        """
        Test case to verify successful zone mapping.

        Ensures that the function correctly maps zones and includes 'x3002' in the results.
        """
        result = map_zones(MOCK_K8S_RESPONSE, MOCK_CEPH_RESPONSE)
        self.assertIn("Zones", result)
        self.assertGreater(len(result["Zones"]), 0)
        self.assertTrue(any(zone["Zone Name"] == "x3002" for zone in result["Zones"]))

    def test_k8s_api_failure(self):
        """
        Test case to verify behavior when Kubernetes API fails.

        The function should return an error message indicating failure to fetch data.
        """
        result = map_zones(MOCK_ERROR_RESPONSE, MOCK_CEPH_RESPONSE)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Failed to fetch data")

    def test_ceph_api_failure(self):
        """
        Test case to verify behavior when Ceph API fails.

        The function should return an error message indicating failure to fetch data.
        """
        result = map_zones(MOCK_K8S_RESPONSE, MOCK_ERROR_RESPONSE)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Failed to fetch data")

    def test_no_zones_configured(self):
        """
        Test case for when no Kubernetes or Ceph zones are configured.

        The function should return an empty list and an informational message.
        """
        result = map_zones("No K8s topology zone present", "No Ceph zones present")
        self.assertIn("Zones", result)
        self.assertEqual(len(result["Zones"]), 0)
        self.assertEqual(result.get("Information"), "No zones (K8s topology and Ceph) configured")

    def test_node_status(self):
        """
        Test case to verify correct node status mapping in the response.

        Ensures that 'x3002' has both Kubernetes and Ceph details with expected nodes.
        """
        result = map_zones(MOCK_K8S_RESPONSE, MOCK_CEPH_RESPONSE)
        zone = next(zone for zone in result["Zones"] if zone["Zone Name"] == "x3002")

        self.assertIn("Kubernetes Topology Zone", zone)
        self.assertIn("Management Master Nodes", zone["Kubernetes Topology Zone"])
        self.assertIn("ncn-m001", zone["Kubernetes Topology Zone"]["Management Master Nodes"])

        self.assertIn("CEPH Zone", zone)
        self.assertIn("Management Storage Nodes", zone["CEPH Zone"])
        self.assertIn("ncn-s001", zone["CEPH Zone"]["Management Storage Nodes"])


if __name__ == "__main__":
    unittest.main()

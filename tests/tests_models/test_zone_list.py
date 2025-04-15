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
Unit tests for the 'ZoneMapper.map_zones' function in the 'zone_list' module.

These tests validate the function's behavior when retrieving and mapping zone details.
"""

import unittest

from src.api.app import app
from src.api.models.zone_list import ZoneMapper
from tests.tests_models.mock_data import (
    MOCK_K8S_RESPONSE,
    MOCK_CEPH_RESPONSE,
)


class TestZoneMapping(unittest.TestCase):
    """Test class for validating zone mapping functionality using 'ZoneMapper.map_zones'."""

    def setUp(self) -> None:
        """Set up an application context before each test."""
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self) -> None:
        """Tear down the application context after each test."""
        self.app_context.pop()

    def test_zone_mapping_success(self) -> None:
        """Test case to verify successful zone mapping."""
        result = ZoneMapper.map_zones(MOCK_K8S_RESPONSE, MOCK_CEPH_RESPONSE)
        self.assertIn("Zones", result)
        self.assertGreater(len(result["Zones"]), 0)
        self.assertTrue(any(zone["Zone Name"] == "x3002" for zone in result["Zones"]))

    def test_no_zones_configured(self) -> None:
        """Test case for when no Kubernetes or Ceph zones are configured."""
        result = ZoneMapper.map_zones(
            "No K8s topology zone present", "No Ceph zones present"
        )
        self.assertIn("Zones", result)
        self.assertEqual(len(result["Zones"]), 0)
        self.assertEqual(
            result.get("Information"), "No zones (K8s topology and Ceph) configured"
        )

    def test_node_status(self) -> None:
        """Test case to verify correct node status mapping in the response."""
        result = ZoneMapper.map_zones(MOCK_K8S_RESPONSE, MOCK_CEPH_RESPONSE)
        zone = next(zone for zone in result["Zones"] if zone["Zone Name"] == "x3002")

        self.assertIn("Kubernetes Topology Zone", zone)
        self.assertIn("Management Master Nodes", zone["Kubernetes Topology Zone"])
        self.assertIn(
            "ncn-m003", zone["Kubernetes Topology Zone"]["Management Master Nodes"]
        )

        self.assertIn("CEPH Zone", zone)
        self.assertIn("Management Storage Nodes", zone["CEPH Zone"])
        self.assertIn("ncn-s005", zone["CEPH Zone"]["Management Storage Nodes"])


if __name__ == "__main__":
    unittest.main()

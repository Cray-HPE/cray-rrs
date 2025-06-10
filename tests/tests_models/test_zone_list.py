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
import logging
import unittest
from flask import Flask
from src.api.services.rrs_zones import ZoneService
from tests.tests_models.mock_data import (
    MOCK_K8S_RESPONSE,
    MOCK_CEPH_RESPONSE,
)


class TestZoneMapping(unittest.TestCase):
    """Test class for validating zone mapping functionality using 'ZoneMapper.map_zones'."""

    def setUp(self) -> None:
        """Set up an application context before each test."""
        self.app = Flask(__name__)  # Create a real Flask app instance
        self.app.config["TESTING"] = True
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)  # You can change this level as needed
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
        )
        handler.setFormatter(formatter)

        if not self.app.logger.handlers:
            self.app.logger.addHandler(handler)

        self.app.logger.setLevel(logging.DEBUG)
        self.app.logger.debug("Flask test app created and logging is configured.")

        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self) -> None:
        """Tear down the application context after each test."""
        self.app_context.pop()

    def test_zone_mapping_success(self) -> None:
        """Test case to verify successful zone mapping."""
        result = ZoneService.map_zones(MOCK_K8S_RESPONSE, MOCK_CEPH_RESPONSE)
        self.app.logger.info(result)
        self.assertIn("Zones", result)
        self.assertGreater(len(result["Zones"]), 0)
        self.assertTrue(any(zone["Zone Name"] == "x3002" for zone in result["Zones"]))

    def test_node_status(self) -> None:
        """Test case to verify correct node status mapping in the response."""
        result = ZoneService.map_zones(MOCK_K8S_RESPONSE, MOCK_CEPH_RESPONSE)
        self.app.logger.info(result)
        zone = next(zone for zone in result["Zones"] if zone["Zone Name"] == "x3002")

        self.assertIn("Kubernetes_Topology_Zone", zone)
        k8s_zone_data = zone["Kubernetes_Topology_Zone"]
        if isinstance(k8s_zone_data, dict):
            self.assertIn("Management_Master_Nodes", k8s_zone_data)
            master_nodes = k8s_zone_data["Management_Master_Nodes"]
            if isinstance(master_nodes, (list, dict)):
                self.assertIn("ncn-m003", master_nodes)
            else:
                self.assertIn("ncn-m003", str(master_nodes))

        self.assertIn("CEPH_Zone", zone)
        ceph_zone_data = zone["CEPH_Zone"]
        if isinstance(ceph_zone_data, dict):
            self.assertIn("Management_Storage_Nodes", ceph_zone_data)
            storage_nodes = ceph_zone_data["Management_Storage_Nodes"]
            if isinstance(storage_nodes, (list, dict)):
                self.assertIn("ncn-s005", storage_nodes)
            else:
                self.assertIn("ncn-s005", str(storage_nodes))


if __name__ == "__main__":
    unittest.main()

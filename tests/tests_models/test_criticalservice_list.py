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
Unit tests for the 'get_critical_services' function in the 'criticalservice_list' module.

These tests validate the function's behavior when retrieving critical services.
"""

import unittest
from src.server.models.criticalservice_list import get_critical_services
from tests.tests_models.mock_data import MOCK_CRITICAL_SERVICES_RESPONSE, MOCK_ERROR_CRT_SVC


class TestCriticalServicesList(unittest.TestCase):
    """
    Test class for listing critical services using 'get_critical_services'.
    """

    def test_list_critical_services_success(self):
        """
        Test case to verify that 'get_critical_services' correctly retrieves critical services.

        The test ensures that the expected 'namespace' and 'kube-system' entries are present
        and that at least one critical service is listed.
        """
        result = {"critical-services": get_critical_services(MOCK_CRITICAL_SERVICES_RESPONSE)}
        self.assertIn("critical-services", result)
        self.assertIn("namespace", result["critical-services"])
        self.assertIn("kube-system", result["critical-services"]["namespace"])
        self.assertGreater(len(result["critical-services"]["namespace"]["kube-system"]), 0)
        self.assertTrue(
            any(
                service["name"] == "coredns"
                for service in result["critical-services"]["namespace"]["kube-system"]
            )
        )

    def test_list_critical_services_failure(self):
        """
        Test case for handling errors when fetching critical services.

        If an error occurs, the function should return an appropriate error message.
        """
        result = get_critical_services(MOCK_ERROR_CRT_SVC)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "string indices must be integers")

    def test_list_no_services(self):
        """
        Test case for when no critical services are available.

        The function should return an empty namespace dictionary.
        """
        result = {"critical-services": get_critical_services({})}
        self.assertIn("critical-services", result)
        self.assertIn("namespace", result["critical-services"])
        self.assertEqual(len(result["critical-services"]["namespace"]), 0)


if __name__ == "__main__":
    unittest.main()

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

"""Unit tests for the Resiliency Monitoring Service"""

import json
import unittest
from typing import ClassVar, Dict, cast
from unittest.mock import patch, MagicMock
from flask import Flask, Response
from flask.testing import FlaskClient
from flask.ctx import AppContext
from src.rrs.rms.rms import app
from src.lib.schema import (
    ApiTimestampFailedResponse,
    ApiTimestampSuccessResponse,
    VersionInfo,
)


class TestRMS(unittest.TestCase):
    """Unit tests for RMS Flask app and utility functions."""

    app: ClassVar[Flask]
    client: ClassVar['FlaskClient[Response]']
    app_context: ClassVar[AppContext]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the Flask app for testing."""
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up the Flask app context after testing."""
        cls.app_context.pop()

    def test_version_endpoint(self) -> None:
        """Test the /version endpoint for correct version information."""
        response: Response = self.client.get("/version")
        self.assertEqual(response.status_code, 200)
        data = cast(VersionInfo, json.loads(response.get_data(as_text=True)))
        self.assertIsInstance(data["version"], str)

    def test_healthz_ready(self) -> None:
        """Test the /healthz/ready endpoint for readiness check."""
        response: Response = self.client.get("/healthz/ready")
        self.assertEqual(response.status_code, 200)

    def test_healthz_live(self) -> None:
        """Test the /healthz/live endpoint for liveness check."""
        response: Response = self.client.get("/healthz/live")
        self.assertEqual(response.status_code, 200)

    @patch("src.lib.lib_rms.Helper.update_state_timestamp")
    def test_update_api_timestamp_success(self, _mock_update: MagicMock) -> None:
        """Test the /api-ts endpoint for successful timestamp update."""
        response: Response = self.client.post("/api-ts")
        self.assertEqual(response.status_code, 200)
        data = cast(ApiTimestampSuccessResponse, json.loads(response.get_data(as_text=True)))
        self.assertEqual(data["message"], "API timestamp updated successfully")

    @patch("src.lib.lib_rms.Helper.update_state_timestamp", side_effect=Exception)
    def test_update_api_timestamp_failure(self, _mock_update: MagicMock) -> None:
        """Test the /api-ts endpoint for failure in timestamp update."""
        response: Response = self.client.post("/api-ts")
        self.assertEqual(response.status_code, 500)
        data = cast(ApiTimestampFailedResponse, json.loads(response.get_data(as_text=True)))
        self.assertEqual(data["error"], "Failed to update API timestamp")

    def test_handle_scn_bad_request(self) -> None:
        """Test the /scn endpoint for bad request."""
        payload: Dict[str, object] = {}
        response: Response = self.client.post("/scn", json=payload)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()

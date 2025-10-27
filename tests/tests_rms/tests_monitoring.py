# language: python
import unittest
import json
from flask import Flask, Response
from flask.testing import FlaskClient
from flask.ctx import AppContext
from unittest.mock import patch, MagicMock
from typing import ClassVar, Dict, cast
from src.rrs.rms.rms import app


class TestRMS(unittest.TestCase):
    """Unit tests for RMS Flask app and utility functions."""

    app: ClassVar[Flask]
    client: ClassVar[FlaskClient[Response]]
    app_context: ClassVar[AppContext]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the Flask app for testing."""
        cls.app = app  # Use the Flask app from rms.py
        cls.app.config["TESTING"] = True
        # test_client() return type is already suitable; avoid redundant cast
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
        json_data = cast(Dict[str, object], json.loads(response.get_data(as_text=True)))
        self.assertIn("version", json_data)
        self.assertIsInstance(json_data["version"], str)

    def test_healthz_ready(self) -> None:
        """Test the /healthz/ready endpoint for readiness check."""
        response: Response = self.client.get("/healthz/ready")
        self.assertEqual(response.status_code, 200)

    def test_healthz_live(self) -> None:
        """Test the /healthz/live endpoint for liveness check."""
        response: Response = self.client.get("/healthz/live")
        self.assertEqual(response.status_code, 200)

    @patch("src.lib.lib_rms.Helper.update_state_timestamp")
    def test_update_api_timestamp_success(self, mock_update: MagicMock) -> None:
        """Test the /api-ts endpoint for successful timestamp update."""
        mock_update.return_value = None
        response: Response = self.client.post("/api-ts")
        self.assertEqual(response.status_code, 200)
        json_data = cast(Dict[str, object], json.loads(response.get_data(as_text=True)))
        self.assertEqual(json_data["message"], "API timestamp updated successfully")

    @patch("src.lib.lib_rms.Helper.update_state_timestamp", side_effect=Exception)
    def test_update_api_timestamp_failure(self, mock_update: MagicMock) -> None:
        """Test the /api-ts endpoint for failure in timestamp update."""
        response: Response = self.client.post("/api-ts")
        self.assertEqual(response.status_code, 500)
        json_data = cast(Dict[str, object], json.loads(response.get_data(as_text=True)))
        self.assertEqual(json_data["error"], "Failed to update API timestamp")

    def test_handle_scn_bad_request(self) -> None:
        """Test the /scn endpoint for bad request."""
        response: Response = self.client.post(
            "/scn", json=cast(Dict[str, object], {})
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()

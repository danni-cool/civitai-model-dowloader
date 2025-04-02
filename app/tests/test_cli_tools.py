import sys
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
import requests

from app.cli import download_status


class TestCliTools(unittest.TestCase):
    """Test case for CLI tools"""

    @patch("app.cli.download_status.requests.get")
    def test_get_downloads_success(self, mock_get):
        """Test get_downloads function with successful API response"""
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "1234",
                "model_name": "Test Model",
                "filename": "test.safetensors",
                "model_type": "Checkpoint",
                "status": "downloading",
                "progress": 45.5,
                "created_at": 1677246541,
            }
        ]
        mock_get.return_value = mock_response

        # Call function
        result = download_status.get_downloads()

        # Verify result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["model_name"], "Test Model")
        self.assertEqual(result[0]["status"], "downloading")

    @patch("app.cli.download_status.requests.get")
    def test_get_downloads_error(self, mock_get):
        """Test get_downloads function with API error"""
        # Mock API error
        mock_get.side_effect = requests.exceptions.RequestException(
            "Connection refused"
        )

        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            # Call function
            result = download_status.get_downloads()

            # Verify result
            self.assertEqual(result, [])
            self.assertIn(
                "Error: Could not connect to API server", captured_output.getvalue()
            )
            self.assertIn(
                "Please make sure the Civitai Browser Plus server is running",
                captured_output.getvalue(),
            )
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__

    @patch("app.cli.download_status.get_downloads")
    def test_display_downloads_empty(self, mock_get_downloads):
        """Test display_downloads function with empty downloads list"""
        # Mock empty downloads list
        mock_get_downloads.return_value = []

        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            # Call function
            download_status.display_downloads([])

            # Verify output
            self.assertIn(
                "No active downloads or queue items", captured_output.getvalue()
            )
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__

    @patch("app.cli.download_status.get_downloads")
    def test_display_downloads_with_items(self, mock_get_downloads):
        """Test display_downloads function with downloads list"""
        # Mock downloads list with different statuses
        mock_downloads = [
            {
                "id": "1",
                "model_name": "Current Download",
                "filename": "current.safetensors",
                "model_type": "Checkpoint",
                "status": "downloading",
                "progress": 33.5,
                "created_at": 1677246541,
            },
            {
                "id": "2",
                "model_name": "Queued Download",
                "filename": "queued.safetensors",
                "model_type": "Lora",
                "status": "queued",
                "created_at": 1677246542,
            },
            {
                "id": "3",
                "model_name": "Completed Download",
                "filename": "completed.safetensors",
                "model_type": "Embedding",
                "status": "completed",
                "created_at": 1677246543,
            },
        ]
        mock_get_downloads.return_value = mock_downloads

        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            # Call function
            download_status.display_downloads(mock_downloads)

            # Verify output contains various sections
            output = captured_output.getvalue()
            self.assertIn("CURRENT DOWNLOAD:", output)
            self.assertIn("Current Download", output)
            self.assertIn("33.5%", output)

            self.assertIn("DOWNLOAD QUEUE:", output)
            self.assertIn("Queued Download", output)

            self.assertIn("RECENT DOWNLOADS:", output)
            self.assertIn("Completed Download", output)
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__


if __name__ == "__main__":
    unittest.main()

import pytest
import os
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.civitai_api import CivitaiAPI
from app.core.download_manager import DownloadManager


# Create a new client for each test to avoid state leakage
@pytest.fixture
def client():
    # Reset the APIs for each test
    app.dependency_overrides = {}

    # Return a fresh TestClient for each test
    return TestClient(app)


@pytest.fixture
def default_settings_dict():
    """Return a default settings dictionary for testing"""
    return {
        "api_key": "test_api_key",
        "model_dir": "/models",
        "download_with_aria2": True,
        "show_nsfw": False,
        "aria2_url": "http://localhost:6800/jsonrpc",
        "aria2_secret": "",
        "aria2_flags": [],
        "create_model_json": True,
        "use_proxy": False,
        "proxy_url": "",
        "proxy_user": "",
        "proxy_pass": "",
        "timeout": 30,
    }


@pytest.fixture
def mock_settings(default_settings_dict):
    """Create a fresh mock settings object for each test"""
    with patch("os.makedirs", return_value=None), patch(
        "os.path.exists", return_value=True
    ):
        mock_settings = MagicMock()

        # Setup to_dict method
        mock_settings.to_dict.return_value = default_settings_dict.copy()

        # Add attributes that match the dict
        for key, value in default_settings_dict.items():
            setattr(mock_settings, key, value)

        # Ensure model_dirs is mocked to avoid filesystem errors
        mock_settings.ensure_model_dirs = MagicMock()

        yield mock_settings


@pytest.fixture
def mock_api_client(mock_settings):
    """Create a mock API client for testing"""
    api_client = MagicMock(spec=CivitaiAPI)

    # Setup the client with the mock settings
    api_client.settings = mock_settings

    yield api_client


@pytest.fixture
def mock_download_manager(mock_api_client):
    """Create a mock download manager for testing"""
    download_manager = MagicMock(spec=DownloadManager)

    # Setup the download manager with the mock API client
    download_manager.api_client = mock_api_client
    download_manager.current_download = None
    download_manager.queue = []

    yield download_manager

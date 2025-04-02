import pytest
import os
import sys
import tempfile
import json

# Add the app directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.settings import Settings


@pytest.fixture
def temp_config_path():
    """Create a temporary file for settings"""
    fd, temp_path = tempfile.mkstemp()
    os.close(fd)
    yield temp_path
    os.unlink(temp_path)


def test_default_settings(temp_config_path):
    """Test that default settings are created correctly"""
    settings = Settings(config_path=temp_config_path)
    # Create fresh settings with defaults
    settings.api_key = ""
    settings.save()

    # Load settings from temp path to ensure we get defaults
    settings = Settings(config_path=temp_config_path)
    settings.load()

    # Check default values
    assert settings.api_key == ""
    assert settings.model_dir == os.path.join(os.getcwd(), "models")
    assert settings.download_with_aria2 == True
    assert settings.aria2_flags == ""
    assert settings.show_nsfw == False
    assert settings.create_model_json == True
    assert settings.use_proxy == False
    assert settings.proxy_url == ""
    assert settings.disable_dns_lookup == False
    assert settings.base_model_filter == None
    assert settings.save_images == False
    assert settings.custom_image_dir == None


def test_save_and_load_settings(temp_config_path):
    """Test saving and loading settings"""
    # Create custom settings
    settings = Settings(config_path=temp_config_path)
    settings.api_key = "test_api_key"
    settings.model_dir = "/custom/model/path"
    settings.download_with_aria2 = False
    settings.show_nsfw = True

    # Save settings
    settings.save()

    # Create a new settings object and load from the same path
    new_settings = Settings(config_path=temp_config_path)
    new_settings.load()

    # Verify settings were loaded correctly
    assert new_settings.api_key == "test_api_key"
    assert new_settings.model_dir == "/custom/model/path"
    assert new_settings.download_with_aria2 == False
    assert new_settings.show_nsfw == True


def test_settings_file_format(temp_config_path):
    """Test that the settings file has the correct format"""
    # Create and save settings
    settings = Settings(config_path=temp_config_path)
    settings.api_key = "test_api_key"
    settings.save()

    # Read the file directly
    with open(temp_config_path, "r") as f:
        settings_data = json.load(f)

    # Verify structure
    assert isinstance(settings_data, dict)
    assert "api_key" in settings_data
    assert settings_data["api_key"] == "test_api_key"


def test_update_settings():
    """Test updating settings"""
    settings = Settings()

    # Update settings with a dictionary
    new_values = {
        "api_key": "new_api_key",
        "model_dir": "/new/model/path",
        "show_nsfw": True,
    }

    settings.update(new_values)

    # Verify updates
    assert settings.api_key == "new_api_key"
    assert settings.model_dir == "/new/model/path"
    assert settings.show_nsfw == True

    # Other settings should remain at default values
    assert settings.download_with_aria2 == True
    assert settings.create_model_json == True

import pytest
from unittest.mock import patch, MagicMock
import os
import sys
import json
import requests

# Add the app directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.civitai_api import CivitaiAPI
from core.settings import Settings


@pytest.fixture
def mock_response():
    """Mock successful response from Civitai API"""
    mock = MagicMock()
    mock.status_code = 200

    # Sample model data structure based on actual Civitai API
    mock.json.return_value = {
        "items": [
            {
                "id": 12345,
                "name": "Test Model",
                "description": "This is a test model",
                "type": "Checkpoint",
                "nsfw": False,
                "modelVersions": [
                    {
                        "id": 67890,
                        "name": "v1.0",
                        "baseModel": "SD 1.5",
                        "files": [
                            {
                                "id": 98765,
                                "name": "test_model_v1.safetensors",
                                "primary": True,
                                "size": 4500000000,
                                "type": "Model",
                                "downloadUrl": "https://example.com/test_model_v1.safetensors",
                                "hashes": {"SHA256": "abcdef1234567890"},
                            }
                        ],
                        "images": [
                            {
                                "id": 111222,
                                "url": "https://example.com/test_image.jpg",
                                "type": "image",
                            }
                        ],
                    }
                ],
            }
        ],
        "metadata": {
            "totalItems": 1,
            "currentPage": 1,
            "pageSize": 10,
            "totalPages": 1,
        },
    }

    return mock


@pytest.fixture
def api_client():
    """Create a CivitaiAPI client with default settings"""
    client = CivitaiAPI(api_key="test_key")
    return client


def test_search_models(api_client, mock_response):
    """Test searching for models"""
    with patch("requests.request", return_value=mock_response):
        results = api_client.search_models(query="test", type="Checkpoint", page=1)

        # Verify the results structure
        assert isinstance(results, dict)
        assert "items" in results
        assert len(results["items"]) == 1
        assert results["items"][0]["name"] == "Test Model"
        assert results["metadata"]["totalItems"] == 1


def test_get_model_versions(api_client, mock_response):
    """Test retrieving model versions for a specific model"""
    with patch.object(api_client, "get_model") as mock_get_model:
        # Create a custom response for the get_model method
        mock_get_model.return_value = {
            "id": 12345,
            "name": "Test Model",
            "description": "This is a test model",
            "type": "Checkpoint",
            "nsfw": False,
            "modelVersions": [
                {
                    "id": 67890,
                    "name": "v1.0",
                    "baseModel": "SD 1.5",
                    "files": [
                        {
                            "id": 98765,
                            "name": "test_model_v1.safetensors",
                            "primary": True,
                            "size": 4500000000,
                            "type": "Model",
                            "downloadUrl": "https://example.com/test_model_v1.safetensors",
                            "hashes": {"SHA256": "abcdef1234567890"},
                        }
                    ],
                }
            ],
        }

        versions = api_client.get_model_versions(model_id=12345)

        # Verify the versions
        assert isinstance(versions, list)
        assert len(versions) == 1
        assert versions[0]["name"] == "v1.0"
        assert versions[0]["id"] == 67890


def test_get_download_url(api_client, mock_response):
    """Test getting a download URL for a specific model file"""
    with patch.object(api_client, "get_model_versions") as mock_get_versions:
        # Create a custom response for the get_model_versions method
        mock_get_versions.return_value = [
            {
                "id": 67890,
                "name": "v1.0",
                "baseModel": "SD 1.5",
                "files": [
                    {
                        "id": 98765,
                        "name": "test_model_v1.safetensors",
                        "primary": True,
                        "size": 4500000000,
                        "type": "Model",
                        "downloadUrl": "https://example.com/test_model_v1.safetensors",
                        "hashes": {"SHA256": "abcdef1234567890"},
                    }
                ],
            }
        ]

        url = api_client.get_download_url(
            model_id=12345, version_id=67890, file_id=98765
        )

        # Verify the URL is correctly extracted
        assert url == "https://example.com/test_model_v1.safetensors"


def test_determine_model_folder():
    """Test determining the correct folder for different model types"""
    api_client = CivitaiAPI()

    # Define base directory for models
    base_dir = "/models"
    api_client.config = {"model_dir": base_dir}

    # Test different model types
    assert api_client.determine_model_folder("Checkpoint") == os.path.join(
        base_dir, "Stable-diffusion"
    )
    assert api_client.determine_model_folder("LORA") == os.path.join(base_dir, "Lora")
    assert api_client.determine_model_folder("VAE") == os.path.join(base_dir, "VAE")
    assert api_client.determine_model_folder("TextualInversion") == os.path.join(
        base_dir, "embeddings"
    )
    assert api_client.determine_model_folder("Controlnet") == os.path.join(
        base_dir, "ControlNet"
    )
    assert api_client.determine_model_folder("Upscaler") == os.path.join(
        base_dir, "ESRGAN"
    )


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.api_key = "test_api_key"
    settings.model_dir = "/test/models"
    settings.show_nsfw = False
    settings.use_proxy = False
    settings.proxy_url = ""
    settings.timeout = 30
    settings.disable_dns_lookup = False
    return settings


@pytest.fixture
def civitai_api(mock_settings):
    return CivitaiAPI(settings=mock_settings)


@patch("requests.request")
def test_search_models_nsfw_handling(mock_request, civitai_api):
    """测试搜索模型时对nsfw参数的处理"""
    # 模拟API响应
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [{"id": 1, "name": "Test Model"}],
        "metadata": {
            "totalItems": 1,
            "currentPage": 1,
            "pageSize": 20,
            "totalPages": 1,
        },
    }
    mock_request.return_value = mock_response

    # 测试nsfw=True
    civitai_api.search_models(query="test", nsfw=True)
    # 验证参数传递
    args, kwargs = mock_request.call_args
    assert kwargs["params"]["nsfw"] == "true"

    # 测试nsfw=False
    civitai_api.search_models(query="test", nsfw=False)
    args, kwargs = mock_request.call_args
    assert kwargs["params"]["nsfw"] == "false"

    # 测试nsfw=None (不传递参数)
    civitai_api.search_models(query="test", nsfw=None)
    args, kwargs = mock_request.call_args
    assert "nsfw" not in kwargs["params"]


@patch("requests.request")
def test_request_error_handling(mock_request, civitai_api):
    """测试API请求错误处理"""
    # 测试HTTP错误
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"
    mock_request.return_value = mock_response

    result = civitai_api.request("test_endpoint")
    assert result is None

    # 测试连接错误
    mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")
    result = civitai_api.request("test_endpoint")
    assert result is None

    # 测试超时
    mock_request.side_effect = requests.exceptions.Timeout("Request timed out")
    result = civitai_api.request("test_endpoint")
    assert result is None


@patch("requests.request")
def test_api_key_in_headers(mock_request, civitai_api):
    """测试API密钥是否正确包含在请求头中"""
    # 模拟响应
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    # 执行请求
    civitai_api.request("test_endpoint")

    # 验证请求头包含API密钥
    args, kwargs = mock_request.call_args
    assert "Authorization" in kwargs["headers"]
    assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"


@patch("requests.request")
def test_test_connection(mock_request, civitai_api):
    """测试API连接测试功能"""
    # 模拟响应
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [{"id": 1, "name": "Test Model"}],
        "metadata": {"totalItems": 1, "currentPage": 1, "pageSize": 1, "totalPages": 1},
    }
    mock_request.return_value = mock_response

    # 执行搜索（这个会在测试连接时被调用）
    result = civitai_api.search_models(page=1, page_size=1)

    # 验证结果
    assert result is not None
    assert "items" in result
    assert len(result["items"]) == 1


def test_get_model_version(civitai_api):
    """Test getting a specific model version"""
    with patch.object(civitai_api, "request") as mock_request:
        # Create a mock response
        mock_response = {
            "id": 67890,
            "name": "v1.0",
            "baseModel": "SD 1.5",
            "files": [
                {
                    "id": 98765,
                    "name": "test_model_v1.safetensors",
                    "primary": True,
                    "downloadUrl": "https://example.com/test_model_v1.safetensors",
                }
            ],
        }
        mock_request.return_value = mock_response

        # Get the model version
        version = civitai_api.get_model_version(67890)

        # Verify the result
        assert version is not None
        assert version["id"] == 67890
        assert version["name"] == "v1.0"

        # Verify the correct endpoint was called
        mock_request.assert_called_once_with("model-versions/67890")


def test_get_model_version_by_hash(civitai_api):
    """Test getting a model version by hash"""
    with patch.object(civitai_api, "request") as mock_request:
        # Create a mock response
        mock_response = {
            "id": 67890,
            "modelId": 12345,
            "name": "v1.0",
            "baseModel": "SD 1.5",
            "files": [
                {
                    "id": 98765,
                    "name": "test_model_v1.safetensors",
                    "primary": True,
                    "downloadUrl": "https://example.com/test_model_v1.safetensors",
                    "hashes": {"SHA256": "abcdef1234567890"},
                }
            ],
        }
        mock_request.return_value = mock_response

        # Get the model version by hash
        version = civitai_api.get_model_version_by_hash("abcdef1234567890")

        # Verify the result
        assert version is not None
        assert version["id"] == 67890
        assert version["modelId"] == 12345

        # Verify the correct endpoint was called
        mock_request.assert_called_once_with("model-versions/by-hash/abcdef1234567890")

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.settings import Settings
from app.core.civitai_api import CivitaiAPI
from app.api.civitai_endpoints import get_api_client, get_settings


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.api_key = "test_api_key"
    settings.save = MagicMock()
    return settings


@pytest.fixture
def mock_api_client():
    api_client = MagicMock()
    return api_client


def test_set_api_key(client, mock_settings):
    """测试设置 API 密钥端点"""
    with patch("app.api.civitai_endpoints.Settings", return_value=mock_settings):
        response = client.post("/api/civitai/api-key", json={"api_key": "new_api_key"})

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["message"] == "API 密钥已设置"

        # 验证设置被保存
        mock_settings.save.assert_called_once()
        assert mock_settings.api_key == "new_api_key"


def test_test_connection_success(client, mock_api_client):
    """测试 API 连接成功的情况"""
    # 模拟搜索结果
    mock_api_client.search_models.return_value = {
        "items": [{"name": "Test Model"}],
        "metadata": {"totalItems": 1},
    }
    mock_api_client.api_key = "test_api_key"

    # 替换依赖
    app.dependency_overrides[get_api_client] = lambda: mock_api_client

    # 测试端点
    response = client.get("/api/civitai/test-connection")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "成功连接到 Civitai API"
    assert data["has_api_key"] is True
    assert data["sample_model"] == "Test Model"

    # 清理
    app.dependency_overrides = {}


def test_test_connection_warning(client, mock_api_client):
    """测试 API 连接成功但无结果的情况"""
    # 模拟搜索结果 - 空列表
    mock_api_client.search_models.return_value = {
        "items": [],
        "metadata": {"totalItems": 0},
    }
    mock_api_client.api_key = "test_api_key"

    # 替换依赖
    app.dependency_overrides[get_api_client] = lambda: mock_api_client

    # 测试端点
    response = client.get("/api/civitai/test-connection")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "warning"
    assert "未返回任何模型" in data["message"]
    assert data["has_api_key"] is True

    # 清理
    app.dependency_overrides = {}


def test_test_connection_error(client, mock_api_client):
    """测试 API 连接失败的情况"""
    # 模拟搜索失败
    mock_api_client.search_models.side_effect = Exception("API 连接错误")
    mock_api_client.api_key = "test_api_key"

    # 替换依赖
    app.dependency_overrides[get_api_client] = lambda: mock_api_client

    # 测试端点
    response = client.get("/api/civitai/test-connection")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "出错" in data["message"]
    assert data["has_api_key"] is True

    # 清理
    app.dependency_overrides = {}


def test_set_api_key_validation(client):
    """测试设置 API 密钥端点的输入验证"""
    # 测试缺少必要字段的请求
    response = client.post("/api/civitai/api-key", json={})  # 空的请求体
    assert response.status_code == 422  # 验证错误

    # 测试字段类型错误的请求
    response = client.post(
        "/api/civitai/api-key",
        json={"api_key": 12345},  # API 密钥应该是字符串，不是数字
    )
    assert response.status_code == 422  # 验证错误

    # 测试错误的内容类型
    response = client.post("/api/civitai/api-key", data="this is not json")
    assert response.status_code == 422  # 验证错误

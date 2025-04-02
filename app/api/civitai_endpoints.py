from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from pydantic import BaseModel

from ..core.civitai_api import CivitaiAPI
from ..core.settings import Settings
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("civitai_endpoints")

# 创建路由器
router = APIRouter(prefix="/api/civitai", tags=["civitai"])


# API 密钥验证模型
class ApiKeyRequest(BaseModel):
    api_key: str


# 获取全局设置
def get_settings():
    return Settings()


# 获取 API 客户端
def get_api_client(settings: Settings = Depends(get_settings)):
    return CivitaiAPI(settings=settings)


@router.post("/api-key")
async def set_api_key(request: ApiKeyRequest):
    """设置 Civitai API 密钥"""
    settings = Settings()
    settings.api_key = request.api_key
    settings.save()
    logger.info("API 密钥已更新")
    return {"status": "success", "message": "API 密钥已设置"}


@router.get("/test-connection")
async def test_connection(api_client: CivitaiAPI = Depends(get_api_client)):
    """测试到 Civitai API 的连接"""
    try:
        # 尝试获取任何模型
        result = api_client.search_models(page=1, page_size=1)

        if result and "items" in result and len(result["items"]) > 0:
            # 连接成功且返回结果
            return {
                "status": "success",
                "message": "成功连接到 Civitai API",
                "has_api_key": bool(api_client.api_key),
                "sample_model": result["items"][0]["name"] if result["items"] else None,
            }
        else:
            # 连接成功但没有结果
            return {
                "status": "warning",
                "message": "已连接到 Civitai API，但未返回任何模型",
                "has_api_key": bool(api_client.api_key),
            }
    except Exception as e:
        # 连接失败
        logger.error(f"API 连接测试失败: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"连接到 Civitai API 时出错: {str(e)}",
            "has_api_key": bool(api_client.api_key),
        }

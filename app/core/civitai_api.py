import os
import json
import requests
import logging
from datetime import datetime
from urllib.parse import urlencode
from .settings import Settings

# 配置日志
logger = logging.getLogger("civitai_api")


class CivitaiAPI:
    """
    Client for interacting with the Civitai API.
    Provides methods for searching models, getting model details,
    and downloading models.
    """

    BASE_URL = "https://civitai.com/api/v1"

    def __init__(self, api_key=None, settings=None):
        """
        Initialize the API client.

        Args:
            api_key (str, optional): API key for Civitai. If None, uses the API key from settings.
            settings (Settings, optional): Settings object. If None, creates a new one.
        """
        self.settings = settings or Settings()
        self.api_key = api_key or self.settings.api_key
        self.config = {"model_dir": self.settings.model_dir}

        # 记录API密钥状态
        if self.api_key:
            logger.info("API密钥已设置")
        else:
            logger.warning("未设置API密钥，部分功能可能受限")

    def get_headers(self):
        """
        Get HTTP headers for API requests.

        Returns:
            dict: Headers dictionary.
        """
        headers = {
            "User-Agent": "Civitai-Browser-Docker/1.0",
            "Accept": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def request(self, endpoint, params=None, method="GET"):
        """
        Make a request to the Civitai API.

        Args:
            endpoint (str): API endpoint to request.
            params (dict, optional): Query parameters.
            method (str, optional): HTTP method. Defaults to "GET".

        Returns:
            dict or None: JSON response data, or None if request failed.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        proxies = self.settings.get_proxy_settings()

        # 记录请求详情
        logger.info(f"API请求: {method} {url}")
        logger.debug(f"请求参数: {params}")
        logger.debug(f"使用代理: {proxies}")

        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                headers=self.get_headers(),
                proxies=proxies,
                timeout=self.settings.timeout,
                verify=not self.settings.disable_dns_lookup,
            )

            # 记录响应状态
            logger.debug(f"响应状态码: {response.status_code}")

            if response.status_code >= 400:
                logger.error(f"API错误: {response.status_code} - {response.text}")
                return None

            # 尝试解析JSON
            try:
                data = response.json()
                logger.debug(
                    f"响应数据: {data if len(str(data)) < 500 else '(大量数据)'}"
                )
                return data
            except ValueError:
                logger.error(f"JSON解析错误: {response.text[:200]}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"请求超时: {url}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"连接错误: {url}")
            return None
        except requests.RequestException as e:
            logger.error(f"请求异常 ({url}): {str(e)}")
            return None
        except Exception as e:
            logger.error(f"未预期的错误 ({url}): {str(e)}", exc_info=True)
            return None

    def search_models(
        self,
        query=None,
        type=None,
        base_model=None,
        sort="Most Downloaded",
        page=1,
        page_size=20,
        nsfw=None,
    ):
        """
        Search for models on Civitai.

        Args:
            query (str, optional): Search query.
            type (str, optional): Model type filter.
            base_model (str, optional): Base model filter.
            sort (str, optional): Sort order. Defaults to "Most Downloaded".
                Valid values: "Highest Rated", "Most Downloaded", "Most Liked",
                "Most Discussed", "Most Collected", "Most Images", "Newest", "Oldest"
            page (int, optional): Page number. Defaults to 1.
            page_size (int, optional): Items per page. Defaults to 20.
            nsfw (bool, optional): Whether to include NSFW models.

        Returns:
            dict or None: Search results, or None if request failed.
        """
        params = {
            "limit": page_size,
            "page": page,
            "sort": sort,
            "primaryFileOnly": "true",
        }

        if query:
            params["query"] = query

        if type:
            params["types"] = type

        if base_model:
            params["baseModels"] = base_model

        # 明确处理nsfw参数
        if nsfw is not None:
            # Civitai API要求nsfw参数为字符串"true"或"false"
            params["nsfw"] = "true" if nsfw else "false"
            logger.debug(f"NSFW参数设置为: {params['nsfw']}")

        # 记录完整搜索参数
        logger.info(f"搜索模型: query={query}, type={type}, page={page}, nsfw={nsfw}")

        # 发送请求并处理响应
        result = self.request("models", params)

        if result:
            # 记录搜索结果统计
            items_count = len(result.get("items", []))
            total_items = result.get("metadata", {}).get("totalItems", 0)
            logger.info(f"搜索结果: 找到 {items_count} 个模型，总共 {total_items} 个")
        else:
            logger.warning("搜索请求失败或未返回结果")

        return result

    def get_model(self, model_id):
        """
        Get details for a specific model.

        Args:
            model_id (int): Model ID.

        Returns:
            dict or None: Model details, or None if request failed.
        """
        return self.request(f"models/{model_id}")

    def get_model_versions(self, model_id):
        """
        Get all versions for a specific model.

        Args:
            model_id (int): Model ID.

        Returns:
            list or None: List of model versions, or None if request failed.
        """
        model_data = self.get_model(model_id)
        if model_data and "modelVersions" in model_data:
            return model_data["modelVersions"]
        return []

    def get_download_url(self, model_id, version_id=None, file_id=None):
        """
        Get the download URL for a specific model file.

        Args:
            model_id (int): Model ID.
            version_id (int, optional): Version ID. If None, uses the latest version.
            file_id (int, optional): File ID. If None, uses the primary file.

        Returns:
            str or None: Download URL, or None if not found.
        """
        # Get model versions
        versions = self.get_model_versions(model_id)
        if not versions:
            return None

        # Find the requested version, or use the latest
        version = None
        if version_id:
            for v in versions:
                if v.get("id") == version_id:
                    version = v
                    break

        # If no specific version requested or not found, use the first one (latest)
        if not version:
            version = versions[0]

        # Find the requested file, or use the primary file
        files = version.get("files", [])
        if not files:
            return None

        file_data = None
        if file_id:
            for f in files:
                if f.get("id") == file_id:
                    file_data = f
                    break

        # If no specific file requested or not found, try to use the primary file
        if not file_data:
            # Look for primary file
            for f in files:
                if f.get("primary", False):
                    file_data = f
                    break

            # If no primary file, use the first one
            if not file_data and files:
                file_data = files[0]

        # Return the download URL if found
        return file_data.get("downloadUrl") if file_data else None

    def create_model_info_json(self, model_data, file_path, file_info=None):
        """
        Create a JSON file with model information.

        Args:
            model_data (dict): Model data.
            file_path (str): Path to the model file.
            file_info (dict, optional): Additional file information.

        Returns:
            str: Path to the created JSON file.
        """
        if not model_data:
            return None

        # Create a simplified info structure
        info = {
            "id": model_data.get("id"),
            "name": model_data.get("name"),
            "description": model_data.get("description"),
            "type": model_data.get("type"),
            "nsfw": model_data.get("nsfw", False),
            "tags": model_data.get("tags", []),
            "modelVersions": [],
        }

        # Add version information
        for version in model_data.get("modelVersions", []):
            version_info = {
                "id": version.get("id"),
                "name": version.get("name"),
                "baseModel": version.get("baseModel"),
                "trainedWords": version.get("trainedWords", []),
            }
            info["modelVersions"].append(version_info)

        # Add file information if provided
        if file_info:
            info["file"] = file_info

        # Save the JSON file
        json_path = os.path.splitext(file_path)[0] + ".json"
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=4)
            return json_path
        except Exception as e:
            print(f"Error creating model info JSON: {str(e)}")
            return None

    def determine_model_folder(self, model_type, description=None):
        """
        Determine the correct folder for a model type.

        Args:
            model_type (str): Model type.
            description (str, optional): Model description.

        Returns:
            str: Path to the model folder.
        """
        base_dir = self.config.get("model_dir", os.path.join(os.getcwd(), "models"))

        # Map model types to folders
        folder_map = {
            "Checkpoint": os.path.join(base_dir, "Stable-diffusion"),
            "Hypernetwork": os.path.join(base_dir, "hypernetworks"),
            "TextualInversion": os.path.join(base_dir, "embeddings"),
            "AestheticGradient": os.path.join(base_dir, "aesthetic_embeddings"),
            "LORA": os.path.join(base_dir, "Lora"),
            "LoCon": os.path.join(base_dir, "LyCORIS"),
            "DoRA": os.path.join(base_dir, "Lora"),
            "VAE": os.path.join(base_dir, "VAE"),
            "Controlnet": os.path.join(base_dir, "ControlNet"),
            "Poses": os.path.join(base_dir, "Poses"),
            "Upscaler": os.path.join(base_dir, "ESRGAN"),
            "MotionModule": os.path.join(base_dir, "MotionModule"),
            "Workflows": os.path.join(base_dir, "Workflows"),
            "Other": os.path.join(base_dir, "Other"),
        }

        # Special case for upscalers based on description
        if model_type == "Upscaler" and description:
            description = description.upper()
            upscaler_types = {
                "SWINIR": os.path.join(base_dir, "SwinIR"),
                "REALESRGAN": os.path.join(base_dir, "RealESRGAN"),
                "GFPGAN": os.path.join(base_dir, "GFPGAN"),
                "BSRGAN": os.path.join(base_dir, "BSRGAN"),
            }

            for upscaler_type, folder in upscaler_types.items():
                if upscaler_type in description:
                    return folder

        # Return the mapped folder or default to Other
        return folder_map.get(model_type, os.path.join(base_dir, "Other"))

    def clean_filename(self, filename):
        """
        Clean a filename to ensure it's valid.

        Args:
            filename (str): Original filename.

        Returns:
            str: Cleaned filename.
        """
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")

        return filename.strip()

    def get_model_version(self, version_id):
        """
        Get details for a specific model version.

        Args:
            version_id (int): Version ID.

        Returns:
            dict or None: Version details, or None if request failed.
        """
        return self.request(f"model-versions/{version_id}")

    def get_model_version_by_hash(self, hash_value):
        """
        Get model version details by hash.

        Args:
            hash_value (str): Hash value of the model file.

        Returns:
            dict or None: Version details, or None if request failed.
        """
        return self.request(f"model-versions/by-hash/{hash_value}")

    def get_download_url_from_link(
        self, download_url, model_type=None, use_preview=False
    ):
        """
        处理已获取的下载链接，如果需要可以添加预览参数

        Args:
            download_url (str): 文件的下载URL
            model_type (str, optional): 模型类型，用于记录
            use_preview (bool, optional): 是否使用预览版，默认为False

        Returns:
            str: 最终的下载URL
        """
        if not download_url:
            return None

        # 如果需要使用预览版本且模型类型为Checkpoint，可以在URL中添加预览参数
        # 注意：目前CivitAI API可能不支持直接获取预览版本，这里仅作为示例
        if use_preview and model_type == "Checkpoint":
            logger.info(f"请求使用预览版本 (模型类型: {model_type})")
            # 此处可能需要根据CivitAI的API规则修改URL
            # 例如：可能需要添加特定参数或更改路径

        return download_url

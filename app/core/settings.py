import os
import json
import tempfile
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("settings")


class Settings:
    """
    Manages application settings for the Civitai Browser application.
    Settings are saved to and loaded from a JSON file.
    """

    def __init__(self, config_path=None):
        """
        Initialize settings with default values.

        Args:
            config_path (str, optional): Path to the config file.
                If None, uses the default path or environment variable.
        """
        # 优先使用环境变量来设置配置路径
        self.config_path = config_path or os.environ.get(
            "CIVITAI_CONFIG_PATH", os.path.join(os.getcwd(), "config", "settings.json")
        )

        # 优先使用环境变量来设置模型目录
        default_model_dir = os.path.join(os.getcwd(), "models")

        # 初始化默认值
        self.api_key = os.environ.get("CIVITAI_API_KEY", "")
        self.model_dir = os.environ.get("CIVITAI_MODEL_DIR", default_model_dir)
        self.download_with_aria2 = self._parse_bool_env("CIVITAI_USE_ARIA2", True)
        self.aria2_url = os.environ.get(
            "CIVITAI_ARIA2_URL", "http://localhost:6800/jsonrpc"
        )
        self.aria2_secret = os.environ.get("CIVITAI_ARIA2_SECRET", "")
        self.aria2_flags = os.environ.get("CIVITAI_ARIA2_FLAGS", "")
        self.show_nsfw = self._parse_bool_env("CIVITAI_SHOW_NSFW", False)
        self.create_model_json = self._parse_bool_env("CIVITAI_CREATE_MODEL_JSON", True)
        self.use_proxy = self._parse_bool_env("CIVITAI_USE_PROXY", False)
        self.proxy_url = os.environ.get("CIVITAI_PROXY_URL", "")
        self.disable_dns_lookup = self._parse_bool_env("CIVITAI_DISABLE_DNS", False)
        self.base_model_filter = None
        self.save_images = self._parse_bool_env("CIVITAI_SAVE_IMAGES", False)
        self.custom_image_dir = os.environ.get("CIVITAI_IMAGE_DIR", None)
        self.timeout = int(os.environ.get("CIVITAI_TIMEOUT", "30"))

        # 确保配置目录存在，如果不能创建，使用临时目录
        self._ensure_config_dir()

        # 尝试加载现有设置
        self.load()

        # 检查目录可写性
        self._check_directory_permissions()

    def _parse_bool_env(self, env_var, default):
        """从环境变量解析布尔值"""
        val = os.environ.get(env_var)
        if val is None:
            return default
        return val.lower() in ("true", "yes", "1", "y")

    def _ensure_config_dir(self):
        """确保配置目录存在，如果不能创建则使用临时目录"""
        config_dir = os.path.dirname(self.config_path)
        try:
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
        except OSError as e:
            # 如果无法创建配置目录，使用临时目录
            logger.warning(f"无法创建配置目录 {config_dir}: {e}")
            logger.info("将使用临时目录存储配置")
            self.config_path = os.path.join(
                tempfile.gettempdir(), "civitai_settings.json"
            )

    def _check_directory_permissions(self):
        """检查目录权限，记录警告但不阻止运行"""
        # 检查模型目录是否可写
        if not os.path.exists(self.model_dir):
            try:
                os.makedirs(self.model_dir, exist_ok=True)
                logger.info(f"已创建模型目录: {self.model_dir}")
            except OSError as e:
                logger.warning(f"无法创建模型目录 {self.model_dir}: {e}")
                logger.warning("下载功能可能无法正常工作")
        else:
            # 尝试写入测试文件检查权限
            test_file = os.path.join(self.model_dir, ".write_test")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                logger.info(f"模型目录可写: {self.model_dir}")
            except OSError:
                logger.warning(
                    f"模型目录 {self.model_dir} 不可写。下载功能可能无法正常工作"
                )

        # 检查配置目录是否可写
        try:
            test_file = os.path.join(os.path.dirname(self.config_path), ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            logger.info(f"配置目录可写: {os.path.dirname(self.config_path)}")
        except OSError:
            logger.warning(
                f"配置目录 {os.path.dirname(self.config_path)} 不可写。设置将无法保存"
            )

    def to_dict(self):
        """
        Convert settings to a dictionary.

        Returns:
            dict: Dictionary representation of the settings.
        """
        return {
            "api_key": self.api_key,
            "model_dir": self.model_dir,
            "download_with_aria2": self.download_with_aria2,
            "aria2_url": self.aria2_url,
            "aria2_secret": self.aria2_secret,
            "aria2_flags": self.aria2_flags,
            "show_nsfw": self.show_nsfw,
            "create_model_json": self.create_model_json,
            "use_proxy": self.use_proxy,
            "proxy_url": self.proxy_url,
            "disable_dns_lookup": self.disable_dns_lookup,
            "base_model_filter": self.base_model_filter,
            "save_images": self.save_images,
            "custom_image_dir": self.custom_image_dir,
            "timeout": self.timeout,
        }

    def from_dict(self, data):
        """
        Update settings from a dictionary.

        Args:
            data (dict): Dictionary containing settings values.
        """
        if not isinstance(data, dict):
            return

        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def save(self):
        """Save settings to the config file."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=4)
            logger.info(f"设置已保存到 {self.config_path}")
            return True
        except OSError as e:
            logger.error(f"保存设置失败: {e}")
            return False

    def load(self):
        """
        Load settings from the config file.

        Returns:
            bool: True if settings were loaded successfully, False otherwise.
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.from_dict(data)
                logger.info(f"已从 {self.config_path} 加载设置")
                return True
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            logger.warning(f"加载设置失败: {e}")
        return False

    def update(self, new_values):
        """
        Update settings with new values.

        Args:
            new_values (dict): Dictionary containing the new values.
        """
        self.from_dict(new_values)

    def get_proxy_settings(self):
        """
        Get proxy settings in the format required by requests.

        Returns:
            dict or None: Proxy settings if enabled, None otherwise.
        """
        if not self.use_proxy or not self.proxy_url:
            return None

        return {"http": self.proxy_url, "https": self.proxy_url}

    def ensure_model_dirs(self):
        """
        Create all necessary model directories if they don't exist.

        Returns:
            dict: Dictionary of model type to directory path.
        """
        model_dirs = {
            "Checkpoint": os.path.join(self.model_dir, "Stable-diffusion"),
            "LORA": os.path.join(self.model_dir, "Lora"),
            "LoCon": os.path.join(self.model_dir, "LyCORIS"),
            "TextualInversion": os.path.join(self.model_dir, "embeddings"),
            "Hypernetwork": os.path.join(self.model_dir, "hypernetworks"),
            "VAE": os.path.join(self.model_dir, "VAE"),
            "Controlnet": os.path.join(self.model_dir, "ControlNet"),
            "Upscaler": os.path.join(self.model_dir, "ESRGAN"),
        }

        # 尝试创建所有目录，但处理错误而不中断
        created_dirs = {}
        for model_type, dir_path in model_dirs.items():
            try:
                os.makedirs(dir_path, exist_ok=True)
                created_dirs[model_type] = dir_path
                logger.debug(f"已创建目录: {dir_path}")
            except OSError as e:
                logger.warning(f"无法创建目录 {dir_path}: {e}")
                created_dirs[model_type] = dir_path  # 仍然返回路径，即使创建失败

        return created_dirs

    # 创建默认设置
    def _create_default_settings(self):
        """创建默认设置"""
        # 默认启用aria2下载
        return {
            # Civitai API 密钥
            "api_key": "",
            # 模型保存目录
            "model_dir": "models",
            # 始终默认使用aria2下载
            "download_with_aria2": True,
            # aria2 RPC 地址
            "aria2_url": "http://localhost:6800/jsonrpc",
            # aria2 密钥
            "aria2_secret": "",
            # 额外的aria2命令行参数
            "aria2_flags": "",
        }

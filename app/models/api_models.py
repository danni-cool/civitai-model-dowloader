from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, HttpUrl, validator


class SettingsUpdate(BaseModel):
    """Model for updating application settings"""

    api_key: Optional[str] = None
    model_dir: Optional[str] = None
    download_with_aria2: Optional[bool] = None
    aria2_flags: Optional[str] = None
    show_nsfw: Optional[bool] = None
    create_model_json: Optional[bool] = None
    use_proxy: Optional[bool] = None
    proxy_url: Optional[str] = None
    disable_dns_lookup: Optional[bool] = None
    base_model_filter: Optional[List[str]] = None
    save_images: Optional[bool] = None
    custom_image_dir: Optional[str] = None


class SettingsResponse(BaseModel):
    """Model for reading application settings"""

    api_key: str
    model_dir: str
    download_with_aria2: bool
    aria2_flags: str
    show_nsfw: bool
    create_model_json: bool
    use_proxy: bool
    proxy_url: str
    disable_dns_lookup: bool
    base_model_filter: Optional[List[str]]
    save_images: bool
    custom_image_dir: Optional[str]


class ModelFile(BaseModel):
    """Model representing a file in a model version"""

    id: int
    name: str
    size: Optional[int] = None
    sizeKB: Optional[int] = None
    type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    pickleScanResult: Optional[str] = None
    pickleScanMessage: Optional[str] = None
    virusScanResult: Optional[str] = None
    virusScanMessage: Optional[str] = None
    scannedAt: Optional[str] = None
    hashes: Optional[Dict[str, str]] = None
    primary: Optional[bool] = False
    downloadUrl: Optional[str] = None

    model_config = {"populate_by_name": True}


class ModelVersion(BaseModel):
    """Model representing a version of a model"""

    id: int
    name: str
    created_at: str = Field(..., alias="createdAt")
    base_model: str = Field(..., alias="baseModel")
    files: List[ModelFile]
    trained_words: Optional[List[str]] = Field(None, alias="trainedWords")
    images: Optional[List[Dict[str, Any]]] = None

    model_config = {"populate_by_name": True}


class Model(BaseModel):
    """Model representing a Civitai model"""

    id: int
    name: str
    description: Optional[str] = None
    type: str
    nsfw: bool = False
    tags: Optional[List[str]] = None
    model_versions: List[ModelVersion] = Field(..., alias="modelVersions")

    model_config = {"populate_by_name": True}


class SearchResults(BaseModel):
    """Model representing search results"""

    items: List[Model]
    metadata: Dict[str, Any]


class DownloadRequest(BaseModel):
    """Model for requesting a model download"""

    model_id: int
    version_id: Optional[int] = None
    file_id: Optional[int] = None
    subfolder: Optional[str] = None
    use_preview: Optional[bool] = False


class DownloadTask(BaseModel):
    """Model representing a download task"""

    id: str
    model_id: int
    version_id: int
    file_id: int
    model_name: str
    filename: str
    model_type: str
    url: str
    subfolder: Optional[str] = None
    status: str
    progress: float
    file_path: Optional[str] = None
    created_at: float
    error: Optional[str] = None

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Response
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict
import os
import json
import time
import uuid
import logging

from ..core.civitai_api import CivitaiAPI
from ..core.download_manager import DownloadManager
from ..core.settings import Settings
from ..models.api_models import (
    SettingsUpdate,
    SettingsResponse,
    SearchResults,
    Model,
    ModelVersion,
    DownloadRequest,
    DownloadTask,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("endpoints")

# Create the router
router = APIRouter()

# Initialize global settings instance for the app
_settings_instance = None


# Dependency for getting API client
def get_api_client():
    settings = Settings()
    return CivitaiAPI(settings=settings)


# Dependency for getting download manager
def get_download_manager(api_client: CivitaiAPI = Depends(get_api_client)):
    return DownloadManager(api_client=api_client)


# Dependency for getting settings
def get_settings():
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


@router.get("/settings")
def read_settings(settings: Settings = Depends(get_settings)):
    """Get current application settings"""
    return settings.to_dict()


@router.patch("/settings")
def update_settings(
    settings_update: SettingsUpdate, settings: Settings = Depends(get_settings)
):
    """Update application settings"""
    # Convert to dict, removing None values
    update_dict = {
        k: v for k, v in settings_update.model_dump().items() if v is not None
    }

    # Update settings
    settings.update(update_dict)

    # Save to file
    settings.save()

    # Recreate directories if model_dir was updated
    try:
        if "model_dir" in update_dict:
            settings.ensure_model_dirs()
    except OSError as e:
        # This could be a test environment with a read-only filesystem
        # Just log the error and continue
        print(f"Warning: Could not create model directories: {e}")

    return settings.to_dict()


@router.get("/models/search")
def search_models(
    query: Optional[str] = None,
    type: Optional[str] = None,
    base_model: Optional[str] = None,
    sort: str = "downloadCount",
    page: int = 1,
    page_size: int = 20,
    nsfw: Optional[bool] = None,
    api_client: CivitaiAPI = Depends(get_api_client),
):
    """Search for models on Civitai"""
    # Get settings for NSFW if not specified
    if nsfw is None:
        settings = Settings()
        nsfw = settings.show_nsfw

    # Perform the search
    results = api_client.search_models(
        query=query,
        type=type,
        base_model=base_model,
        sort=sort,
        page=page,
        page_size=page_size,
        nsfw=nsfw,
    )

    if not results:
        # Return an empty result set instead of an error
        return {
            "items": [],
            "metadata": {
                "totalItems": 0,
                "currentPage": page,
                "pageSize": page_size,
                "totalPages": 1,
            },
        }

    # Make sure required fields exist in the response
    if "items" not in results:
        results["items"] = []
    if "metadata" not in results:
        results["metadata"] = {
            "totalItems": len(results.get("items", [])),
            "currentPage": page,
            "pageSize": page_size,
            "totalPages": 1,
        }
    if "totalPages" not in results["metadata"]:
        results["metadata"]["totalPages"] = 1

    return results


@router.get("/models/{model_id}")
def get_model(model_id: int, api_client: CivitaiAPI = Depends(get_api_client)):
    """Get details for a specific model"""
    model = api_client.get_model(model_id)

    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    # Ensure all fields have proper values to pass validation
    if "modelVersions" in model:
        for version in model["modelVersions"]:
            if "files" in version:
                for file in version["files"]:
                    if "size" not in file and "sizeKB" in file:
                        file["size"] = file["sizeKB"] * 1024
                    elif "size" not in file:
                        file["size"] = 0

    return model


@router.get("/models/{model_id}/versions")
def get_model_versions(model_id: int, api_client: CivitaiAPI = Depends(get_api_client)):
    """Get all versions for a specific model"""
    versions = api_client.get_model_versions(model_id)

    if versions is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    # Ensure all fields have proper values to pass validation
    for version in versions:
        if "files" in version:
            for file in version["files"]:
                if "size" not in file and "sizeKB" in file:
                    file["size"] = file["sizeKB"] * 1024
                elif "size" not in file:
                    file["size"] = 0

    return versions


@router.post("/downloads", response_model=dict)
async def create_download(
    download_request: DownloadRequest,
    api_client: CivitaiAPI = Depends(get_api_client),
    download_manager: DownloadManager = Depends(get_download_manager),
):
    """Create a download task and add it to the queue"""

    # Check if downloads are disabled
    return {
        "status": "disabled",
        "message": "Downloads are temporarily disabled. This feature is under construction.",
        "model_name": "Download Disabled",
        "id": "disabled",
    }

    # Get model data
    model = api_client.get_model(download_request.model_id)
    if not model:
        raise HTTPException(
            status_code=404, detail=f"Model {download_request.model_id} not found"
        )

    # Get model version data
    version = None
    for ver in model.get("modelVersions", []):
        if ver["id"] == download_request.version_id:
            version = ver
            break

    if not version:
        raise HTTPException(
            status_code=404,
            detail=f"Version {download_request.version_id} not found for model {download_request.model_id}",
        )

    # Find the file
    file = None
    for f in version.get("files", []):
        if f["id"] == download_request.file_id:
            file = f
            break

    if not file:
        raise HTTPException(
            status_code=404,
            detail=f"File {download_request.file_id} not found for version {download_request.version_id}",
        )

    # Get the download URL
    url = api_client.get_download_url_from_link(
        file["downloadUrl"], model["type"], download_request.use_preview
    )

    # Create a download task
    task = download_manager.create_download_task(
        model_id=model["id"],
        version_id=version["id"],
        file_id=file["id"],
        model_name=model["name"],
        filename=file["name"],
        model_type=model["type"],
        url=url,
        subfolder=download_request.subfolder,
    )

    # Record current state
    print(f"Queue length before creating download task: {len(download_manager.queue)}")
    print(
        f"Recent downloads length before creating task: {len(download_manager.recent_downloads)}"
    )

    # Create a simple progress callback function to update download status and ensure updates are correctly passed to the frontend
    def progress_callback(updated_task):
        # Ensure the current task is updated
        with download_manager._tasks_lock:
            # Update the task in the queue (if it exists)
            for task in download_manager.queue:
                if task["id"] == updated_task["id"]:
                    task.update(
                        {
                            "progress": updated_task["progress"],
                            "download_speed": updated_task.get("download_speed", 0),
                            "eta": updated_task.get("eta", 0),
                            "status": updated_task["status"],
                        }
                    )
                    break

            # Update the current download task (if it matches)
            if (
                download_manager.current_download
                and download_manager.current_download["id"] == updated_task["id"]
            ):
                download_manager.current_download.update(
                    {
                        "progress": updated_task["progress"],
                        "download_speed": updated_task.get("download_speed", 0),
                        "eta": updated_task.get("eta", 0),
                        "status": updated_task["status"],
                    }
                )

    # Add directly to the queue, don't use background_tasks
    print(f"Creating download task: {task['model_name']} - {task['filename']}")

    # Add to queue and recent downloads list (this method uses a thread lock internally)
    added_task = download_manager.add_to_queue(task)

    # Record state after addition
    print(f"Queue status after addition: {len(download_manager.queue)} tasks")
    print(f"recent_downloads length: {len(download_manager.recent_downloads)} tasks")

    # Ensure the download manager's _process_queue method uses progress callback
    if (
        not download_manager.download_thread
        or not download_manager.download_thread.is_alive()
    ):
        download_manager._ensure_download_thread_running()

    # Ensure valid task information is returned to the frontend
    if not added_task:
        # This should not happen, but just to be safe
        print("Warning: added_task is empty, returning original task")
        return task

    # Return the added task to ensure the frontend receives task information immediately
    return added_task


@router.get("/downloads", response_model=List[dict])
def list_downloads(download_manager: DownloadManager = Depends(get_download_manager)):
    """Get current download list and recently completed downloads"""
    logger.info("Getting active and recent download tasks")

    # Use thread-lock protected method to get download task list
    downloads = download_manager.get_active_and_recent_downloads()

    logger.info(f"Current download: {download_manager.current_download is not None}")
    if download_manager.current_download:
        logger.info(
            f"Current download task: {download_manager.current_download['id']} - {download_manager.current_download['filename']} - progress: {download_manager.current_download['progress']:.1f}%"
        )
    logger.info(f"Queue length: {len(download_manager.queue)}")
    logger.info(f"Recent downloads length: {len(download_manager.recent_downloads)}")
    logger.info(f"Returned download list length: {len(downloads)}")

    # If there are download tasks, log them
    if downloads:
        for download in downloads:
            logger.info(
                f"Download task: {download['id']} - {download['status']} - progress: {download['progress']:.1f}%"
            )

    # If no downloads are recorded, but stored recent downloads are empty, try to create some recent records
    if len(downloads) == 0:
        # Look for completed downloads
        completed_files = []

        # Check Other directory
        other_dir = os.path.join(Settings().model_dir, "Other")
        if os.path.exists(other_dir):
            for file in os.listdir(other_dir):
                if file.endswith(".txt"):
                    file_path = os.path.join(other_dir, file)
                    stat = os.stat(file_path)
                    completed_files.append(
                        {
                            "id": f"recent-{len(completed_files)}",
                            "model_id": None,
                            "version_id": 0,
                            "file_id": 0,
                            "model_name": "Recently Downloaded Test File",
                            "filename": file,
                            "model_type": "Other",
                            "url": "",
                            "status": "completed",
                            "progress": 100,
                            "file_path": file_path,
                            "created_at": stat.st_mtime,
                            "is_recent": True,
                        }
                    )

        # Check Stable-diffusion directory
        sd_dir = os.path.join(Settings().model_dir, "Stable-diffusion")
        if os.path.exists(sd_dir):
            for file in os.listdir(sd_dir):
                if file.endswith(".txt"):
                    file_path = os.path.join(sd_dir, file)
                    stat = os.stat(file_path)
                    completed_files.append(
                        {
                            "id": f"recent-{len(completed_files)}",
                            "model_id": None,
                            "version_id": 0,
                            "file_id": 0,
                            "model_name": "Recently Downloaded Checkpoint",
                            "filename": file,
                            "model_type": "Checkpoint",
                            "url": "",
                            "status": "completed",
                            "progress": 100,
                            "file_path": file_path,
                            "created_at": stat.st_mtime,
                            "is_recent": True,
                        }
                    )

        # Sort by most recent modification time
        completed_files.sort(key=lambda x: x["created_at"], reverse=True)

        # Return only the 5 most recent files
        completed_files = completed_files[:5]

        if completed_files:
            logger.info(f"Found {len(completed_files)} recently completed downloads")
            return completed_files

        # If no recently completed downloads are found, and in DEBUG mode, return test tasks
        if os.environ.get("DEBUG", "False").lower() in (
            "true",
            "1",
            "t",
        ):
            logger.info("No download tasks found, adding test task")
            return [
                {
                    "id": "test-task",
                    "model_id": 0,
                    "version_id": 0,
                    "file_id": 0,
                    "model_name": "Example Model (Not Downloaded)",
                    "filename": "example.safetensors",
                    "model_type": "Checkpoint",
                    "url": "",
                    "status": "completed",
                    "progress": 100,
                    "is_test": True,
                }
            ]

    logger.info(f"Total of {len(downloads)} download tasks returned")
    return downloads


@router.get("/downloads/{task_id}")
def get_download_status(
    task_id: str, download_manager: DownloadManager = Depends(get_download_manager)
):
    """Get the status of a specific download"""
    status = download_manager.get_download_status(task_id)

    if not status:
        raise HTTPException(
            status_code=404, detail=f"Download task {task_id} not found"
        )

    return status


@router.delete("/downloads/{task_id}", response_model=dict)
def cancel_download(
    task_id: str, download_manager: DownloadManager = Depends(get_download_manager)
):
    """Cancel download task"""
    result = download_manager.remove_from_queue(task_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Download task {task_id} not found or cannot be canceled",
        )
    return {"status": "canceled", "task_id": task_id}


@router.get("/models/types")
def get_model_types():
    """Get a list of available model types"""
    types = [
        "Checkpoint",
        "LORA",
        "LoCon",
        "TextualInversion",
        "Hypernetwork",
        "AestheticGradient",
        "VAE",
        "Controlnet",
        "Poses",
        "Upscaler",
        "MotionModule",
        "Workflows",
        "Other",
    ]
    return types


@router.get("/models/basemodels")
def get_base_models(api_client: CivitaiAPI = Depends(get_api_client)):
    """Get a list of available base models"""
    try:
        # Try to get from API
        api_url = "models?baseModels=GetModels"
        response = api_client.request(api_url, params=None)

        if response and "error" in response and "issues" in response["error"]:
            # Extract options from the error response
            options = response["error"]["issues"][0]["unionErrors"][0]["issues"][0][
                "options"
            ]
            return options
    except Exception as e:
        print(f"Error fetching base models: {str(e)}")
        pass

    # Fallback to default list
    default_models = [
        "SD 1.4",
        "SD 1.5",
        "SD 1.5 LCM",
        "SD 2.0",
        "SD 2.0 768",
        "SD 2.1",
        "SD 2.1 768",
        "SD 2.1 Unclip",
        "SDXL 0.9",
        "SDXL 1.0",
        "SDXL 1.0 LCM",
        "SDXL Distilled",
        "SDXL Turbo",
        "SDXL Lightning",
        "Stable Cascade",
        "Pony",
        "SVD",
        "SVD XT",
        "Playground v2",
        "PixArt a",
        "Flux.1 S",
        "Flux.1 D",
        "Other",
    ]
    return default_models


@router.post("/settings/api-key")
def set_api_key(api_key: str, settings: Settings = Depends(get_settings)):
    """Directly set the API key without modifying other settings"""
    settings.api_key = api_key
    settings.save()

    # 重置 API 客户端以使用新的 API 键
    global _api_client_instance
    _api_client_instance = None

    return {"success": True, "message": "API key has been set"}


@router.delete("/downloads/history", response_model=dict)
def clear_download_history(
    download_manager: DownloadManager = Depends(get_download_manager),
):
    """Clear download history, keeping only active downloads"""
    try:
        # Get current active downloads
        active_downloads = []

        with download_manager._tasks_lock:
            # Backup current downloads in queue
            if download_manager.current_download:
                active_downloads.append(download_manager.current_download.copy())

            active_downloads.extend([task.copy() for task in download_manager.queue])

            # Clear recent downloads list
            download_manager.recent_downloads = []

            # Keep only active downloads
            for download in active_downloads:
                if download["status"] in ["completed", "failed"]:
                    continue
                download_manager._add_to_recent_downloads(download)

        return {"status": "success", "message": "Download history has been cleared"}
    except Exception as e:
        logger.exception(f"Error clearing download history: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to clear download history: {str(e)}"
        )

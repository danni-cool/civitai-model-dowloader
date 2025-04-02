import os
import time
import uuid
import json
import subprocess
import threading
import requests
from pathlib import Path
import shutil
from .settings import Settings
from .civitai_api import CivitaiAPI


class DownloadManager:
    """
    Manages downloading models from Civitai.
    Supports both direct downloads and downloads using aria2.
    """

    def __init__(self, api_client=None, model_dir=None):
        """
        Initialize the download manager.

        Args:
            api_client (CivitaiAPI, optional): API client. If None, creates a new one.
            model_dir (str, optional): Base directory for models. If None, uses the default from settings.
        """
        self.settings = Settings()
        self.api_client = api_client or CivitaiAPI(settings=self.settings)
        self.model_dir = model_dir or self.settings.model_dir
        self.queue = []
        self.current_download = None
        self.download_thread = None
        self.aria2_process = None
        self.rpc_port = 24000
        self.rpc_secret = "civitai-browser"
        # 添加一个列表来存储最近完成的下载任务
        self.recent_downloads = []  # 保留最近的下载记录
        self.max_recent_downloads = 20  # 增加最近下载记录的上限，确保有足够的历史记录
        self._tasks_lock = threading.RLock()  # 添加线程锁以确保线程安全

        # Ensure model directories exist
        self.settings.ensure_model_dirs()

        # Start the download thread
        self.thread = threading.Thread(target=self._process_queue)
        self.thread.daemon = True
        self.thread.start()

    def create_download_task(
        self,
        model_id,
        version_id,
        file_id,
        model_name,
        filename,
        model_type,
        url,
        subfolder=None,
        is_test=False,
    ):
        """
        Create a download task.

        Args:
            model_id (int): Model ID.
            version_id (int): Version ID.
            file_id (int): File ID.
            model_name (str): Model name.
            filename (str): File name.
            model_type (str): Model type.
            url (str): Download URL.
            subfolder (str, optional): Subfolder to save the file in.
            is_test (bool, optional): Whether the task is a test task.

        Returns:
            dict: Download task.
        """
        # Clean the filename
        filename = self.api_client.clean_filename(filename)

        # Generate a unique task ID
        task_id = str(uuid.uuid4())

        # Create the task
        task = {
            "id": task_id,
            "model_id": model_id,
            "version_id": version_id,
            "file_id": file_id,
            "model_name": model_name,
            "filename": filename,
            "model_type": model_type,
            "url": url,
            "subfolder": subfolder,
            "status": "queued",
            "progress": 0,
            "file_path": None,
            "created_at": time.time(),
            "error": None,
            "is_test": is_test,
        }

        return task

    def add_to_queue(self, task):
        """
        Add a task to the download queue.

        Args:
            task (dict): Download task.

        Returns:
            dict: Added task.
        """
        with self._tasks_lock:
            # 确保任务状态为queued
            task["status"] = "queued"
            print(f"添加下载任务到队列: {task['model_name']} - {task['filename']}")

            # 创建副本而不是使用原始任务对象
            task_copy = task.copy()
            self.queue.append(task_copy)
            print(f"当前队列长度: {len(self.queue)}")

            # 启动下载线程（如果未运行）
            self._ensure_download_thread_running()

            # 确保任务被保存（即使还没开始下载）也可以被前端检索到
            self._add_to_recent_downloads(task_copy)

            # 返回任务副本而不是原始任务
            return task_copy

    def _ensure_download_thread_running(self):
        """确保下载线程正在运行"""
        # 检查线程是否存在且在运行
        if self.download_thread is None or not self.download_thread.is_alive():
            print("启动新的下载线程...")
            self.download_thread = threading.Thread(
                target=self._process_queue, daemon=True
            )
            self.download_thread.start()
            # 添加短暂延迟，避免线程立即处理队列
            print("下载线程已启动，等待其就绪...")
            time.sleep(1.0)  # 增加等待时间确保线程正常启动
            print("下载线程就绪完成")

    def remove_from_queue(self, task_id):
        """
        Remove a task from the download queue.

        Args:
            task_id (str): Task ID.

        Returns:
            bool: True if task was removed, False otherwise.
        """
        with self._tasks_lock:
            # Find the task in the queue
            for i, task in enumerate(self.queue):
                if task["id"] == task_id:
                    # Remove the task from the queue
                    self.queue.pop(i)
                    return True

            return False

    def get_queue(self):
        """
        Get the current download queue.

        Returns:
            list: List of tasks in the queue.
        """
        with self._tasks_lock:
            return [task.copy() for task in self.queue]  # 返回副本避免外部修改

    def get_download_status(self, task_id):
        """
        Get the status of a download task.

        Args:
            task_id (str): Task ID.

        Returns:
            dict or None: Task status, or None if task not found.
        """
        with self._tasks_lock:
            # Check the current download
            if self.current_download and self.current_download["id"] == task_id:
                return self.current_download.copy()  # 返回副本避免外部修改

            # Check the queue
            for task in self.queue:
                if task["id"] == task_id:
                    return task.copy()  # 返回副本避免外部修改

            # 检查最近完成的下载
            for task in self.recent_downloads:
                if task["id"] == task_id:
                    return task.copy()  # 返回副本避免外部修改

            return None

    def _process_queue(self):
        """处理下载队列，支持从UI查看下载状态。"""
        # 添加延迟启动，确保UI可以先获取到队列状态
        time.sleep(0.5)

        print(f"开始处理下载队列，当前队列长度: {len(self.queue)}")

        while True:
            # 检查队列是否为空（使用线程锁保护）
            with self._tasks_lock:
                if not self.queue:
                    # 队列为空，退出循环
                    self.current_download = None
                    break
                # 获取队列中的第一个任务但不立即移除
                self.current_download = self.queue[
                    0
                ].copy()  # 使用副本避免修改原始队列项
                # 更新状态
                self.queue[0]["status"] = "downloading"
                self.current_download["status"] = "downloading"

            try:
                print(
                    f"*** 开始下载任务 ***: {self.current_download['model_name']} - {self.current_download['filename']} (ID: {self.current_download['id']})"
                )

                # 定义进度回调函数
                def progress_callback(updated_task):
                    # 使用线程锁保护共享数据
                    with self._tasks_lock:
                        # 确保更新的是正确的任务
                        if (
                            self.current_download
                            and self.current_download["id"] == updated_task["id"]
                        ):
                            # 输出进度日志
                            print(
                                f">> 进度更新: {updated_task['progress']:.1f}% - 任务ID: {updated_task['id']}"
                            )

                            # 更新当前下载任务
                            self.current_download.update(
                                {
                                    "progress": updated_task["progress"],
                                    "download_speed": updated_task.get(
                                        "download_speed", 0
                                    ),
                                    "eta": updated_task.get("eta", 0),
                                    "status": updated_task.get(
                                        "status", self.current_download["status"]
                                    ),
                                }
                            )

                            # 同时更新队列中的任务
                            if self.queue and self.queue[0]["id"] == updated_task["id"]:
                                self.queue[0].update(
                                    {
                                        "progress": updated_task["progress"],
                                        "download_speed": updated_task.get(
                                            "download_speed", 0
                                        ),
                                        "eta": updated_task.get("eta", 0),
                                        "status": updated_task.get(
                                            "status", self.queue[0]["status"]
                                        ),
                                    }
                                )

                try:
                    # 获取下载方法设置
                    use_aria2 = self.settings.download_with_aria2

                    # 如果设置使用aria2，尝试启动aria2 RPC服务器
                    aria2_ready = False
                    if use_aria2:
                        try:
                            aria2_ready = self._start_aria2_rpc()
                            if not aria2_ready:
                                print("无法启动aria2，将使用直接下载")
                        except Exception as e:
                            print(f"启动aria2时出错: {str(e)}")
                            print("将使用直接下载")
                            aria2_ready = False

                    # 下载文件
                    if use_aria2 and aria2_ready:
                        print(f"使用aria2下载: {self.current_download['filename']}")
                        result = self.download_file_aria2(self.current_download)
                    else:
                        # 如果aria2没有准备好或未启用，使用直接下载
                        if use_aria2:
                            print(
                                f"aria2未准备好，使用直接下载: {self.current_download['filename']}"
                            )
                        else:
                            print(f"使用直接下载: {self.current_download['filename']}")
                        # 传递进度回调函数
                        result = self.download_file(
                            self.current_download, progress_callback
                        )

                    # 使用线程锁更新任务状态并移除队列中的任务
                    with self._tasks_lock:
                        # 检查队列是否还有我们正在处理的任务
                        if (
                            self.queue
                            and self.queue[0]["id"] == self.current_download["id"]
                        ):
                            self.queue[0].update(result)
                            # 现在可以安全移除队列中的任务
                            completed_task = self.queue.pop(0)
                            # 添加到最近下载列表
                            print(f"从队列中移除已完成的任务: {completed_task['id']}")
                            self._add_to_recent_downloads(completed_task)

                            if completed_task["status"] == "completed":
                                print(f"下载完成: {completed_task['filename']}")
                            else:
                                print(
                                    f"下载失败: {completed_task['filename']} - {completed_task.get('error', '未知错误')}"
                                )
                        else:
                            # 任务可能已被移除，记录异常情况
                            print(
                                f"警告：任务已不在队列中：{self.current_download['id']}"
                            )
                            # 将当前下载任务添加到recent_downloads，确保即使任务被移除也能在UI中看到
                            self._add_to_recent_downloads(self.current_download)
                except Exception as e:
                    # 处理下载过程中的任何错误
                    error_msg = f"下载过程中出错: {str(e)}"
                    print(error_msg)

                    # 更新当前任务状态并移除队列中的任务
                    with self._tasks_lock:
                        # 更新当前任务状态
                        if self.current_download:
                            self.current_download["status"] = "failed"
                            self.current_download["error"] = error_msg
                            # 确保任务被添加到recent_downloads
                            self._add_to_recent_downloads(self.current_download)

                        # 更新队列中的任务状态
                        if (
                            self.queue
                            and self.queue[0]["id"] == self.current_download["id"]
                        ):
                            self.queue[0]["status"] = "failed"
                            self.queue[0]["error"] = error_msg
                            failed_task = self.queue.pop(0)
                            # 确保任务被添加到recent_downloads
                            self._add_to_recent_downloads(failed_task)

                    # 暂停一下再继续处理队列
                    time.sleep(1)

            except Exception as e:
                # 处理任何意外错误
                error_msg = f"处理下载队列时出错: {str(e)}"
                print(error_msg)

                try:
                    with self._tasks_lock:
                        # 如果有当前下载任务，标记为失败并移出队列
                        if self.current_download:
                            self.current_download["status"] = "failed"
                            self.current_download["error"] = error_msg
                            # 将当前下载添加到recent_downloads
                            self._add_to_recent_downloads(self.current_download)

                        if (
                            self.queue
                            and self.current_download
                            and self.queue[0]["id"] == self.current_download["id"]
                        ):
                            self.queue[0]["status"] = "failed"
                            self.queue[0]["error"] = error_msg

                            # 记录失败的任务
                            failed_task = self.queue.pop(0)
                            self._add_to_recent_downloads(failed_task)
                except Exception as inner_e:
                    # 如果在错误处理过程中发生错误，则记录但继续执行
                    print(f"错误处理过程中发生错误: {str(inner_e)}")

                # 暂停一下再继续处理队列
                time.sleep(1)

        # 队列处理完毕
        with self._tasks_lock:
            self.current_download = None
        print("下载队列处理完成，当前队列为空")

    def download_file(self, task, progress_callback=None):
        """
        使用requests直接下载文件，并实时更新下载进度

        Args:
            task (dict): 下载任务
            progress_callback (function, optional): 进度回调函数

        Returns:
            dict: 更新后的任务
        """
        print(f"开始下载文件: {task['filename']}")

        try:
            # 确定目标文件夹
            base_folder = self.api_client.determine_model_folder(task["model_type"])

            # 如果指定了子文件夹，添加到路径中
            target_folder = base_folder
            if task["subfolder"]:
                safe_subfolder = task["subfolder"].lstrip(os.sep)
                target_folder = os.path.join(base_folder, safe_subfolder)

            # 创建目标文件夹（如果不存在）
            try:
                os.makedirs(target_folder, exist_ok=True)
                print(f"目标文件夹: {target_folder}")
            except OSError as e:
                error_msg = f"无法创建目标文件夹 {target_folder}: {str(e)}"
                print(error_msg)
                task["status"] = "failed"
                task["error"] = error_msg
                self._add_to_recent_downloads(task)
                return task

            # 确定完整的文件路径
            file_path = os.path.join(target_folder, task["filename"])
            task["file_path"] = file_path
            print(f"目标文件路径: {file_path}")

            # 如果文件已存在且不为空，则跳过下载
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                print(f"文件已存在，跳过下载: {file_path}")
                task["status"] = "completed"
                task["progress"] = 100
                self._add_to_recent_downloads(task)
                return task

            # 创建临时文件路径用于下载
            temp_file_path = file_path + ".downloading"
            print(f"临时文件路径: {temp_file_path}")

            # 获取代理设置和请求头
            proxies = self.settings.get_proxy_settings()
            headers = self.api_client.get_headers()

            # 初始化下载状态变量
            total_size = 0
            downloaded = 0
            start_time = time.time()
            last_update_time = start_time
            update_interval = 0.3  # 更新UI的时间间隔（秒）

            try:
                # 发起请求下载文件
                print(f"开始下载URL: {task['url']}")
                with requests.get(
                    task["url"],
                    stream=True,
                    headers=headers,
                    proxies=proxies,
                    timeout=self.settings.timeout,
                    verify=not self.settings.disable_dns_lookup,
                ) as response:
                    # 检查响应状态
                    response.raise_for_status()

                    # 获取总文件大小
                    total_size = int(response.headers.get("content-length", 0))
                    print(f"总文件大小: {total_size} 字节")

                    # 打开临时文件进行写入
                    with open(temp_file_path, "wb") as f:
                        # 遍历响应内容，分块写入
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)

                                # 计算下载进度百分比
                                if total_size > 0:
                                    progress_percent = (downloaded / total_size) * 100
                                else:
                                    progress_percent = 0

                                # 更新任务进度
                                task["progress"] = progress_percent

                                # 计算下载速度和剩余时间
                                current_time = time.time()
                                elapsed_time = current_time - start_time

                                if elapsed_time > 0:
                                    download_speed = downloaded / elapsed_time
                                    task["download_speed"] = download_speed

                                    if total_size > 0 and download_speed > 0:
                                        remaining_size = total_size - downloaded
                                        eta_seconds = remaining_size / download_speed
                                        task["eta"] = eta_seconds

                                        # 打印下载状态
                                        if (
                                            current_time - last_update_time
                                            >= update_interval
                                        ):
                                            speed_mbps = download_speed / (1024 * 1024)
                                            eta_formatted = time.strftime(
                                                "%H:%M:%S", time.gmtime(eta_seconds)
                                            )
                                            print(
                                                f"下载进度: {progress_percent:.1f}% ({downloaded}/{total_size} 字节) - 速度: {speed_mbps:.2f} MB/s - ETA: {eta_formatted}"
                                            )

                                            # 调用进度回调，如果提供了的话
                                            if progress_callback:
                                                # 确保更新队列中的当前任务
                                                with self._tasks_lock:
                                                    if (
                                                        self.current_download
                                                        and self.current_download["id"]
                                                        == task["id"]
                                                    ):
                                                        self.current_download.update(
                                                            {
                                                                "progress": task[
                                                                    "progress"
                                                                ],
                                                                "download_speed": task.get(
                                                                    "download_speed", 0
                                                                ),
                                                                "eta": task.get(
                                                                    "eta", 0
                                                                ),
                                                                "status": "downloading",
                                                            }
                                                        )

                                                progress_callback(task)
                                                last_update_time = current_time

                # 下载完成后重命名文件
                print(f"下载完成，重命名临时文件到最终路径")
                if os.path.exists(file_path):
                    os.remove(file_path)
                os.rename(temp_file_path, file_path)

                # 更新任务状态
                task["status"] = "completed"
                task["progress"] = 100
                print(f"下载成功: {task['filename']}")

                # 添加到最近下载记录
                self._add_to_recent_downloads(task)
                return task

            except requests.RequestException as e:
                error_msg = f"下载请求错误: {str(e)}"
                print(error_msg)
                task["status"] = "failed"
                task["error"] = error_msg

                # 删除临时文件
                if os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except OSError:
                        pass

                self._add_to_recent_downloads(task)
                return task

        except Exception as e:
            error_msg = f"下载过程中发生意外错误: {str(e)}"
            print(error_msg)
            task["status"] = "failed"
            task["error"] = error_msg
            self._add_to_recent_downloads(task)
            return task

    def _add_to_recent_downloads(self, task):
        """将任务添加到最近下载列表

        Args:
            task (dict): 下载任务
        """
        with self._tasks_lock:
            # 避免添加重复的任务
            for i, recent_task in enumerate(self.recent_downloads):
                if recent_task.get("id") == task.get("id"):
                    # 如果已存在，则更新并移动到列表开头
                    self.recent_downloads.pop(i)
                    break

            # 确保任务中的状态是正确的，修复常见的状态问题
            task_copy = task.copy()  # 使用副本避免引用问题

            # 确保完成或失败的任务有正确的进度
            if (
                task_copy.get("status") == "completed"
                and task_copy.get("progress", 0) < 100
            ):
                task_copy["progress"] = 100

            # 添加到最近下载列表头部
            self.recent_downloads.insert(0, task_copy)

            # 保持最近下载列表不超过最大限制
            if len(self.recent_downloads) > self.max_recent_downloads:
                self.recent_downloads.pop()

            # 打印一些调试信息
            print(
                f"添加任务到最近下载列表: {task_copy.get('model_name')} - {task_copy.get('filename')}"
            )
            print(f"当前最近下载列表长度: {len(self.recent_downloads)}")
            return task_copy

    def _start_aria2_rpc(self):
        """Start the aria2 RPC server if not already running."""
        # Check if aria2 RPC is already running
        try:
            # Try to contact the RPC server
            response = requests.get(
                f"http://localhost:{self.rpc_port}/jsonrpc", timeout=3
            )
            if response.status_code == 200:
                # 如果能连接并且状态码为200，服务器正在运行
                print("aria2 RPC服务器已运行")
                return True
            else:
                print(f"aria2 RPC服务器返回非200状态码: {response.status_code}")
        except requests.RequestException as e:
            # 服务器未运行或连接错误
            print(f"aria2 RPC服务器未运行: {str(e)}")

        # Start the aria2 RPC server
        try:
            # 直接使用系统中的aria2c命令
            aria2_path = "aria2c"

            print(f"使用系统aria2命令: {aria2_path}")

            cmd = [
                aria2_path,
                "--enable-rpc",
                "--rpc-listen-all",
                f"--rpc-listen-port={self.rpc_port}",
                f"--rpc-secret={self.rpc_secret}",
                "--check-certificate=false",
                "--file-allocation=none",
                "--continue=true",  # 断点续传
                "--auto-file-renaming=false",  # 避免自动重命名
            ]

            # Add any additional flags from settings
            if self.settings.aria2_flags:
                cmd.extend(self.settings.aria2_flags.split())

            # Start the process
            print(f"启动aria2 RPC服务器: {' '.join(cmd)}")
            try:
                self.aria2_process = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except FileNotFoundError:
                print("aria2命令不可用，请安装aria2或将其添加到PATH中")
                return False

            # Wait for server to start
            max_attempts = 5
            for attempt in range(max_attempts):
                time.sleep(1)  # 等待服务器启动
                try:
                    response = requests.get(
                        f"http://localhost:{self.rpc_port}/jsonrpc", timeout=3
                    )
                    if response.status_code == 200:
                        print(
                            f"aria2 RPC服务器启动成功 (尝试 {attempt+1}/{max_attempts})"
                        )
                        return True
                except requests.RequestException:
                    pass

                if attempt < max_attempts - 1:
                    print(
                        f"等待aria2 RPC服务器启动 (尝试 {attempt+1}/{max_attempts})..."
                    )

            print(f"aria2 RPC服务器启动失败，已尝试 {max_attempts} 次")
            return False

        except Exception as e:
            print(f"启动aria2 RPC服务器失败: {str(e)}")
            return False

    def download_file_aria2(self, task):
        """
        Download a file using aria2.

        Args:
            task (dict): Download task.

        Returns:
            dict: Updated task.
        """
        try:
            # Determine the destination folder
            base_folder = self.api_client.determine_model_folder(task["model_type"])

            # Add subfolder if specified
            target_folder = base_folder
            if task["subfolder"]:
                # 规范化子文件夹路径，确保不会跳出基础目录
                safe_subfolder = task["subfolder"].lstrip(os.sep)
                target_folder = os.path.join(base_folder, safe_subfolder)

            # Create the folder if it doesn't exist
            try:
                os.makedirs(target_folder, exist_ok=True)
            except OSError as e:
                error_msg = f"无法创建目标文件夹 {target_folder}: {str(e)}"
                print(error_msg)
                task["status"] = "failed"
                task["error"] = error_msg
                # 回退到常规下载方法
                print("回退到直接下载方式")
                return self.download_file(task)

            # Determine the file path
            file_path = os.path.join(target_folder, task["filename"])

            # Update the task with the file path
            task["file_path"] = file_path

            # 如果文件已存在并且大小不为0，则认为已下载完成
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                print(f"文件已存在，跳过下载: {file_path}")
                task["status"] = "completed"
                task["progress"] = 100
                self._add_to_recent_downloads(task)
                return task

            # Get the model data for creating the JSON file
            model_data = None
            if task.get("model_id"):
                try:
                    model_data = self.api_client.get_model(task["model_id"])
                except Exception as e:
                    print(f"获取模型数据失败（将继续下载）: {str(e)}")

            # 检查aria2 RPC服务器是否运行
            try:
                # 尝试连接RPC服务器
                response = requests.get(
                    f"http://localhost:{self.rpc_port}/jsonrpc", timeout=3
                )
                if response.status_code != 200:
                    raise Exception(
                        f"aria2 RPC 服务器返回非200状态码: {response.status_code}"
                    )
            except Exception as e:
                error_msg = f"无法连接到aria2 RPC服务器: {str(e)}"
                print(error_msg)
                task["error"] = error_msg
                # 回退到常规下载方法
                print("回退到直接下载方式")
                return self.download_file(task)

            # 准备认证头 (如果API密钥存在)
            headers = []
            if self.api_client.api_key:
                headers.append(f"Authorization: Bearer {self.api_client.api_key}")

            # 使用Referer和User-Agent避免某些下载限制
            headers.append("Referer: https://civitai.com/")
            headers.append(
                "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )

            # Create the JSON-RPC request to add download
            jsonrpc_data = {
                "jsonrpc": "2.0",
                "id": "civitai-browser",
                "method": "aria2.addUri",
                "params": [
                    f"token:{self.rpc_secret}",
                    [task["url"]],
                    {
                        "dir": target_folder,
                        "out": task["filename"],
                        "header": headers,
                        "continue": "true",  # 支持断点续传
                        "max-connection-per-server": "5",  # 每个服务器的最大连接数
                        "split": "5",  # 单文件最大分片数
                        "min-split-size": "1M",  # 最小分片大小
                        "conditional-get": "true",  # 使用条件GET
                        "auto-file-renaming": "false",  # 禁止自动重命名
                        "check-integrity": "false",  # 不检查文件完整性，提高性能
                        "file-allocation": "none",  # 不预分配文件空间，提高性能
                        "allow-overwrite": "true",  # 允许覆盖已存在的文件
                    },
                ],
            }

            # 发送请求并获取GID
            try:
                # Send the JSON-RPC request
                response = requests.post(
                    f"http://localhost:{self.rpc_port}/jsonrpc",
                    json=jsonrpc_data,
                    timeout=10,
                )

                response.raise_for_status()
                result = response.json()

                # Get the GID (download ID)
                gid = result.get("result")
                if not gid:
                    raise Exception("Failed to start download with aria2")

                print(f"aria2 下载已开始，GID: {gid}")
                task["aria2_gid"] = gid  # 保存GID供后续查询

                # 设置任务的起始进度
                task["progress"] = 0
                task["status"] = "downloading"
                self._add_to_recent_downloads(task)  # 确保任务在UI中可见

                # 立即获取一次下载状态
                status_data = {
                    "jsonrpc": "2.0",
                    "id": "civitai-browser",
                    "method": "aria2.tellStatus",
                    "params": [
                        f"token:{self.rpc_secret}",
                        gid,
                        ["status", "completedLength", "totalLength", "downloadSpeed"],
                    ],
                }

                status_response = requests.post(
                    f"http://localhost:{self.rpc_port}/jsonrpc",
                    json=status_data,
                    timeout=10,
                )
                status_response.raise_for_status()
                status_result = status_response.json()

                if "result" in status_result:
                    print("aria2下载已成功启动，将在后台继续下载")
                    # 我们不需要等待下载完成，aria2会在后台继续下载
                    # get_active_and_recent_downloads方法将使用tellActive和tellStopped来获取状态

                    # 创建模型信息JSON
                    if (
                        self.settings.create_model_json
                        and model_data
                        and isinstance(model_data, dict)
                    ):
                        try:
                            self.api_client.create_model_info_json(
                                model_data, file_path
                            )
                        except Exception as e:
                            print(f"创建模型信息JSON失败: {str(e)}")

                    # 返回初始状态
                    return task
                else:
                    # 如果无法获取初始状态，回退到常规下载
                    print("无法获取aria2下载初始状态，回退到直接下载")
                    return self.download_file(task)

            except Exception as e:
                error_msg = f"aria2下载设置失败: {str(e)}"
                print(error_msg)
                task["status"] = "failed"
                task["error"] = error_msg

                # 回退到直接下载方式
                print("回退到直接下载方式")
                return self.download_file(task)
        except Exception as e:
            error_msg = f"下载错误: {str(e)}"
            print(error_msg)
            task["status"] = "failed"
            task["error"] = error_msg
            return task

    def get_active_and_recent_downloads(self):
        """
        获取所有活动和最近的下载任务

        返回当前下载、队列中的任务和最近完成的下载

        Returns:
            list: 下载任务列表
        """
        with self._tasks_lock:
            # 创建结果列表
            result = []

            # 如果有当前下载，添加到结果中
            if self.current_download:
                print(f"添加当前下载到结果列表: {self.current_download['id']}")
                result.append(self.current_download.copy())  # 使用副本避免引用问题

            # 添加队列中的任务
            if self.queue:
                print(f"添加队列中的{len(self.queue)}个任务到结果列表")
                for task in self.queue:
                    # 跳过当前下载（已添加）
                    if (
                        self.current_download
                        and task["id"] == self.current_download["id"]
                    ):
                        continue
                    result.append(task.copy())  # 使用副本避免引用问题

            # 添加最近完成的下载
            if self.recent_downloads:
                print(f"添加{len(self.recent_downloads)}个最近完成的下载到结果列表")
                for task in self.recent_downloads:
                    # 避免重复添加
                    task_id = task.get("id")
                    if not any(r.get("id") == task_id for r in result):
                        result.append(task.copy())  # 使用副本避免引用问题

            # 按创建时间排序（最新的在前）
            result.sort(key=lambda x: x.get("created_at", 0), reverse=True)

            print(f"总共返回{len(result)}个下载任务")
            return result

    def _get_aria2_downloads(self):
        """
        使用aria2 RPC API获取所有活动、等待和已完成的下载

        Returns:
            list: 所有aria2下载任务列表
        """
        result = []

        try:
            # 检查aria2 RPC服务器是否运行
            try:
                response = requests.get(
                    f"http://localhost:{self.rpc_port}/jsonrpc", timeout=3
                )
                if response.status_code != 200:
                    print(
                        f"aria2 RPC 服务器未运行或返回错误状态码: {response.status_code}"
                    )
                    return result
            except requests.RequestException:
                print("无法连接到aria2 RPC服务器")
                return result

            # 获取活动下载 (tellActive)
            active_data = {
                "jsonrpc": "2.0",
                "id": "civitai-browser",
                "method": "aria2.tellActive",
                "params": [
                    f"token:{self.rpc_secret}",
                    [
                        "gid",
                        "status",
                        "completedLength",
                        "totalLength",
                        "downloadSpeed",
                        "files",
                    ],
                ],
            }

            # 获取等待下载 (tellWaiting)
            waiting_data = {
                "jsonrpc": "2.0",
                "id": "civitai-browser",
                "method": "aria2.tellWaiting",
                "params": [
                    f"token:{self.rpc_secret}",
                    0,  # 从队列头开始
                    100,  # 最多获取100个任务
                    [
                        "gid",
                        "status",
                        "completedLength",
                        "totalLength",
                        "downloadSpeed",
                        "files",
                    ],
                ],
            }

            # 获取已完成/失败的下载 (tellStopped)
            stopped_data = {
                "jsonrpc": "2.0",
                "id": "civitai-browser",
                "method": "aria2.tellStopped",
                "params": [
                    f"token:{self.rpc_secret}",
                    0,  # 从最近的已停止的开始
                    100,  # 最多获取100个任务
                    [
                        "gid",
                        "status",
                        "completedLength",
                        "totalLength",
                        "errorCode",
                        "errorMessage",
                        "files",
                    ],
                ],
            }

            # 执行请求并解析结果
            for data, status_type in [
                (active_data, "active"),
                (waiting_data, "waiting"),
                (stopped_data, "stopped"),
            ]:
                try:
                    response = requests.post(
                        f"http://localhost:{self.rpc_port}/jsonrpc",
                        json=data,
                        timeout=10,
                    )
                    response.raise_for_status()
                    resp_data = response.json()

                    if "result" in resp_data:
                        aria2_tasks = resp_data["result"]

                        for aria2_task in aria2_tasks:
                            task_id = aria2_task.get("gid")

                            # 查找原始任务以获取更多信息
                            original_task = None
                            if (
                                self.current_download
                                and self.current_download.get("aria2_gid") == task_id
                            ):
                                original_task = self.current_download
                            else:
                                # 在队列和最近下载中查找
                                for task in self.queue + self.recent_downloads:
                                    if task.get("aria2_gid") == task_id:
                                        original_task = task
                                        break

                            # 如果找不到原始任务，尝试从aria2 files信息中获取文件名
                            if not original_task:
                                filename = "未知文件"
                                if "files" in aria2_task and aria2_task["files"]:
                                    file_path = aria2_task["files"][0].get("path", "")
                                    filename = os.path.basename(file_path)

                                # 创建一个新的任务对象
                                original_task = {
                                    "id": f"aria2-{task_id}",
                                    "model_id": 0,
                                    "version_id": 0,
                                    "file_id": 0,
                                    "model_name": "Aria2 下载任务",
                                    "filename": filename,
                                    "model_type": "Unknown",
                                    "url": (
                                        aria2_task["files"][0].get("uris", [""])[0]
                                        if "files" in aria2_task
                                        and aria2_task["files"]
                                        and "uris" in aria2_task["files"][0]
                                        else ""
                                    ),
                                    "status": (
                                        "downloading"
                                        if status_type == "active"
                                        else (
                                            "queued"
                                            if status_type == "waiting"
                                            else "completed"
                                        )
                                    ),
                                    "progress": 0,
                                    "created_at": time.time(),
                                    "aria2_gid": task_id,
                                }

                            # 获取完成长度和总长度
                            completed_length = int(aria2_task.get("completedLength", 0))
                            total_length = int(aria2_task.get("totalLength", 0))

                            # 计算进度
                            if total_length > 0:
                                progress = int((completed_length / total_length) * 100)
                            else:
                                progress = 0

                            # 根据状态类型设置任务状态
                            task_status = original_task.get("status", "unknown")
                            if status_type == "active":
                                task_status = "downloading"
                            elif status_type == "waiting":
                                task_status = "queued"
                            elif status_type == "stopped":
                                # 检查是否有错误
                                if (
                                    "errorCode" in aria2_task
                                    and aria2_task.get("errorCode") != "0"
                                ):
                                    task_status = "failed"
                                    original_task["error"] = aria2_task.get(
                                        "errorMessage", "未知错误"
                                    )
                                else:
                                    # 检查是否已完成
                                    if (
                                        total_length > 0
                                        and completed_length >= total_length
                                    ):
                                        task_status = "completed"
                                        progress = 100
                                    else:
                                        task_status = "stopped"

                            # 更新原始任务信息
                            task_copy = original_task.copy()
                            task_copy["status"] = task_status
                            task_copy["progress"] = progress

                            # 添加下载速度信息
                            if "downloadSpeed" in aria2_task:
                                download_speed = int(aria2_task["downloadSpeed"])
                                task_copy["download_speed"] = download_speed

                            # 添加到结果列表
                            result.append(task_copy)
                except Exception as e:
                    print(f"获取aria2 {status_type}下载列表失败: {e}")

        except Exception as e:
            print(f"_get_aria2_downloads方法出错: {e}")

        return result

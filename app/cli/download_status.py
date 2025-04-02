#!/usr/bin/env python
"""
命令行下载状态查看器
用于在命令行查看当前下载状态和队列

用法:
  python -m app.cli.download_status

选项:
  -h, --help    显示帮助信息
  -w, --watch   实时监控模式，每3秒刷新一次
"""

import sys
import time
import argparse
import requests
from datetime import datetime
from pathlib import Path

# API端点
API_URL = "http://localhost:8000/api/downloads"


def format_size(size_bytes):
    """将字节数格式化为人类可读的格式"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.1f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.1f} GB"


def format_time(timestamp):
    """将时间戳格式化为人类可读的格式"""
    if not timestamp:
        return "N/A"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def get_downloads():
    """获取当前下载状态和队列"""
    try:
        response = requests.get(API_URL, timeout=2)
        if response.status_code == 200:
            downloads = response.json()
            return downloads
        else:
            print(f"Error: API returned status code {response.status_code}")
            return []
    except requests.RequestException as e:
        print("\nError: Could not connect to API server.")
        print("\nPlease make sure the Civitai Browser Plus server is running.")
        print("You can start it with: 'python -m app.webui'")
        print(f"\nError details: {e}")
        return []


def display_downloads(downloads):
    """显示下载状态和队列"""
    if not downloads:
        print("No active downloads or queue items.")
        return

    print("\n" + "=" * 80)
    print("CIVITAI BROWSER PLUS - DOWNLOAD STATUS")
    print("=" * 80)

    # 首先处理当前正在下载的任务
    current_downloads = [d for d in downloads if d.get("status") == "downloading"]
    if current_downloads:
        print("\nCURRENT DOWNLOAD:")
        print("-" * 80)
        for download in current_downloads:
            print(f"Name:     {download.get('model_name')}")
            print(f"File:     {download.get('filename')}")
            print(f"Type:     {download.get('model_type')}")
            print(f"Progress: {download.get('progress', 0):.1f}%")
            print(f"Status:   {download.get('status')}")
            if download.get("error"):
                print(f"Error:    {download.get('error')}")
            print(f"Started:  {format_time(download.get('created_at'))}")
            print("-" * 80)

    # 然后显示队列中的任务
    queued_downloads = [d for d in downloads if d.get("status") == "queued"]
    if queued_downloads:
        print("\nDOWNLOAD QUEUE:")
        print("-" * 80)
        for i, download in enumerate(queued_downloads, 1):
            print(f"{i}. {download.get('model_name')} - {download.get('filename')}")
            print(f"   Type: {download.get('model_type')}")
            print(f"   Added: {format_time(download.get('created_at'))}")
            print()

    # 最后显示最近完成的下载
    completed_downloads = [
        d
        for d in downloads
        if d.get("status") in ["completed", "failed"] and not d.get("is_test", False)
    ]
    if completed_downloads:
        print("\nRECENT DOWNLOADS:")
        print("-" * 80)
        for i, download in enumerate(completed_downloads, 1):
            status_str = (
                "\033[32mCompleted\033[0m"
                if download.get("status") == "completed"
                else "\033[31mFailed\033[0m"
            )
            print(f"{i}. {download.get('model_name')} - {download.get('filename')}")
            print(f"   Status: {status_str}")
            if download.get("error"):
                print(f"   Error: {download.get('error')}")
            print(f"   Time: {format_time(download.get('created_at'))}")
            print()

    print("=" * 80)


def watch_downloads(interval=3):
    """实时监控下载状态，每隔指定的时间刷新一次"""
    try:
        while True:
            # 清屏
            print("\033c", end="")

            # 获取并显示下载
            downloads = get_downloads()
            display_downloads(downloads)

            # 显示时间
            print(f"\nLast updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Refresh interval: {interval} seconds")
            print("Press Ctrl+C to exit")

            # 等待
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nExiting watch mode...")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Command line download status viewer")
    parser.add_argument(
        "-w",
        "--watch",
        action="store_true",
        help="Watch mode, refreshes every 3 seconds",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=3,
        help="Refresh interval in seconds (only with watch mode)",
    )

    args = parser.parse_args()

    if args.watch:
        watch_downloads(args.interval)
    else:
        downloads = get_downloads()
        display_downloads(downloads)


if __name__ == "__main__":
    main()

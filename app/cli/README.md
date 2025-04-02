# Civitai Browser Plus CLI Tools

This directory contains command line tools for Civitai Browser Plus.

## Available Tools

### Download Status Viewer

View the current download status and queue from the command line.

**Usage:**

```bash
# Basic usage - show current downloads and queue
python -m app.cli.download_status

# Watch mode - refreshes every 3 seconds
python -m app.cli.download_status -w

# Watch mode with custom refresh interval (in seconds)
python -m app.cli.download_status -w -i 5
```

**Features:**

- Displays current downloads with progress
- Shows pending download queue
- Lists recently completed downloads
- Watch mode with auto-refresh
- Color-coded status indicators

**Requirements:**

- Civitai Browser Plus server must be running (`python -m app.webui`)
- The API server should be accessible at http://localhost:8000

**Note:**
This tool connects to the Civitai Browser Plus API to retrieve download information.
If you get a connection error, make sure the server is running.

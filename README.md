# Civitai Model Downloader

A standalone application for browsing and downloading models from Civitai.

## Features

- 🔍 Browse all models from Civitai
- 📥 Download any model, any version, and any file
- 🚄 High-speed downloads with built-in Aria2 support
- 🖌️ Sleek and intuitive user interface
- 🔒 Save your API key for accessing restricted models

## Running with Docker

### Using Docker Hub

```bash
docker run -d \
  --name civitai-browser \
  -p 8000:8000 \
  -v /your/models/folder:/app/models \
  civitai-browser:latest
```

### Building from Source

1. Clone this repository:

```bash
git clone https://github.com/yourusername/civitai-browser-docker.git
cd civitai-browser-docker
```

2. Build the Docker image:

```bash
docker build -t civitai-browser .
```

3. Run the container:

```bash
docker run -d \
  --name civitai-browser \
  -p 8000:8000 \
  -v /your/models/folder:/app/models \
  civitai-browser:latest
```

## File System Permissions

When using Docker, you may encounter file system permission issues. Ensure:

1. The mounted volume has the appropriate permissions
2. Use the correct user to run the container
3. Correctly configure the volume in docker-compose.yml

If you encounter "Read-only file system" errors, you can try the following methods:

```bash
# Change local directory ownership
sudo chown -R 1000:1000 ./models ./config

# Or give all users write permissions
chmod -R 777 ./models ./config
```

## Using Docker Compose

We recommend using Docker Compose to run the application, as it will automatically set up the Aria2 container and correctly mount volumes:

```bash
# Clone repository
git clone https://github.com/yourusername/sd-civitai-browser-plus.git
cd sd-civitai-browser-plus

# Create necessary directories
mkdir -p models config aria2-config

# Run container
docker-compose up -d
```

Access http://localhost:8000 to use the application.

## Configuration

All configuration can be done through the Settings page in the web interface. The following settings are available:

- **API Key**: Your Civitai API key (optional, but required for some downloads)
- **Models Directory**: Where to save downloaded models
- **Aria2 Settings**: Configure the built-in Aria2 downloader
- **Proxy Settings**: Configure a proxy for accessing Civitai
- **Content Settings**: Configure NSFW content visibility and more

## Model Folder Structure

The application creates the following folder structure for downloaded models:

- `Stable-diffusion/` - For checkpoint models
- `Lora/` - For LORA models
- `LyCORIS/` - For LoCon models
- `embeddings/` - For Textual Inversion models
- `hypernetworks/` - For Hypernetwork models
- `VAE/` - For VAE models
- `ControlNet/` - For ControlNet models
- Other folders for various model types

## Development

### Prerequisites

- Python 3.10 or later
- Node.js 14 or later (for frontend development)

### Setting Up the Development Environment

1. Clone the repository:

```bash
git clone https://github.com/yourusername/civitai-browser-docker.git
cd civitai-browser-docker
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the application:

```bash
python -m app.main
```

5. Access the application at `http://localhost:8000`

## Testing

Run the automated tests with:

```bash
pytest
```

## Acknowledgments

This project is based on the [SD-Civitai-Browser-Plus](https://github.com/BlafKing/sd-civitai-browser-plus) extension by BlafKing.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

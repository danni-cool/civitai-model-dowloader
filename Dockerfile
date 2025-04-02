FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
  curl \
  aria2 \
  gpg \
  openssl \
  && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p models/Stable-diffusion models/LORA models/LyCORIS models/VAE models/embeddings models/Other config \
  && chmod -R 777 models config

# Set environment variables
ENV MODEL_DIR=/app/models
ENV CONFIG_PATH=/app/config/settings.json
ENV PORT=8000

# Expose port
EXPOSE 8000

# Start command
CMD ["python", "-m", "app.main"] 
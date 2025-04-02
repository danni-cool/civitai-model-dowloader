#!/bin/bash

# Create a virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run tests
echo "Running tests..."
python -m pytest app/tests/ -v

# Deactivate the virtual environment
deactivate

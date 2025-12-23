#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Find the venv directory (usually .venv created by uv)
VENV_PATH=".venv"

# Check if the virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Virtual environment not found. Please run 'uv sync' or 'uv init' first."
    exit 1
fi

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Now run your application
python src/omega13/__main__.py "$@"

# The environment is active for the duration of this script

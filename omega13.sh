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

# Ensure podman socket is running (required for podman compose/docker-compose)
if ! systemctl --user is-active --quiet podman.socket; then
    echo "Starting podman.socket..."
    systemctl --user start podman.socket
fi

# Check if whisper-server is running, if not start it
if ! podman ps --filter "name=whisper-server" --filter "status=running" --quiet | grep -q . ; then
    echo "Starting whisper-server..."
    podman compose up -d
fi

# Now run your application
python src/omega13/__main__.py "$@"

# The environment is active for the duration of this script

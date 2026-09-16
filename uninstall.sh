#!/usr/bin/env bash
# Omega-13 Uninstaller Wrapper

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ] || [ ! -f ".venv/bin/python" ]; then
    echo "Virtual environment not found. Omega-13 may not be installed."
    echo "If it is installed globally, please remove it manually."
    exit 1
fi

exec .venv/bin/python -m omega13.installer --uninstall "$@"

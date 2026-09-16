#!/usr/bin/env bash
# Omega-13 Bootstrap Installer
# Prepares the Python environment and hands off to the Rich-powered installer.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}▸${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
fail()    { echo -e "${RED}✗${NC} $*"; exit 1; }

# Prevent root
if [ "$EUID" -eq 0 ]; then
    fail "Please run as your normal user, not root. sudo will be requested when needed."
fi

# 1. Detect Distro
info "Detecting distribution..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO_ID="$ID"
else
    fail "Cannot detect distribution (/etc/os-release not found)"
fi

# 2. Install System Dependencies
info "Installing system dependencies..."
case "$DISTRO_ID" in
    fedora|rhel|almalinux|rocky|centos)
        sudo dnf install -y python3 python3-devel python3-pip \
            pipewire-jack-audio-connection-kit-devel \
            ffmpeg sox libsndfile-devel \
            gtk4-layer-shell cairo-devel gobject-introspection-devel \
            cmake gcc gcc-c++ make git \
            cpulimit util-linux
        ;;
    debian|ubuntu|pop)
        sudo apt-get update && sudo apt-get install -y \
            python3 python3-dev python3-venv \
            libjack-jackd2-dev ffmpeg sox libsndfile1-dev \
            libgtk-4-dev libcairo2-dev libgirepository1.0-dev \
            cmake gcc g++ make git cpulimit
        ;;
    arch|manjaro)
        sudo pacman -S --noconfirm --needed \
            python jack2 ffmpeg sox libsndfile \
            gtk4-layer-shell cairo gobject-introspection \
            cmake gcc make git cpulimit
        ;;
    *)
        info "Unsupported distribution: $DISTRO_ID. Attempting to continue anyway..."
        ;;
esac
success "System dependencies ready"

# 3. Install uv if missing
if ! command -v uv >/dev/null 2>&1; then
    info "Installing 'uv' package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
success "uv is available"

# 4. Ensure Project Venv
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ] || [ ! -f ".venv/bin/python" ]; then
    info "Creating virtual environment..."
    uv venv
fi

info "Syncing dependencies (including rich for UI)..."
uv sync
success "Python environment ready"

# 5. Hand off to Python Installer
echo ""
info "Launching Omega-13 Installer..."
echo ""

exec .venv/bin/python -m omega13.installer "$@"

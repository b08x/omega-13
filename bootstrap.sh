#!/bin/bash

# Omega-13 Installer / Bootstrap Script
# Distro-agnostic setup for system dependencies and Python environment.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Helper Functions ---

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# --- 1. Detect Package Manager ---

detect_pkg_manager() {
    if command -v dnf >/dev/null 2>&1; then
        PKG_MANAGER="dnf"
    elif command -v apt-get >/dev/null 2>&1; then
        PKG_MANAGER="apt"
    elif command -v pacman >/dev/null 2>&1; then
        PKG_MANAGER="pacman"
    elif command -v zypper >/dev/null 2>&1; then
        PKG_MANAGER="zypper"
    else
        log_error "Unsupported package manager. Please install system dependencies manually."
        exit 1
    fi
    log_info "Detected package manager: $PKG_MANAGER"
}

# --- 2. Install System Dependencies ---

install_system_deps() {
    log_info "Installing system dependencies..."

    case $PKG_MANAGER in
        dnf)
            # Fedora / RHEL
            # Note: pipewire-jack-audio-connection-kit-devel provides jack headers
            sudo dnf install -y \
                python3 python3-pip python3-devel \
                libsndfile libsndfile-devel \
                pipewire-jack-audio-connection-kit-devel \
                gcc git podman
            ;;
        apt)
            # Debian / Ubuntu
            sudo apt-get update
            sudo apt-get install -y \
                python3 python3-pip python3-venv python3-dev \
                libsndfile1 libsndfile1-dev \
                libjack-jackd2-dev \
                build-essential git podman
            ;;
        pacman)
            # Arch Linux
            sudo pacman -S --noconfirm \
                python python-pip \
                libsndfile \
                jack2 \
                base-devel git podman
            ;;
        zypper)
            # OpenSUSE
            sudo zypper install -y \
                python3 python3-pip python3-devel \
                libsndfile libsndfile-devel \
                libjack-devel \
                gcc git podman
            ;;
    esac
    log_success "System dependencies installed."
}

# --- 3. Install uv (Python Package Manager) ---

install_uv() {
    if ! command -v uv >/dev/null 2>&1; then
        log_info "Installing 'uv' package manager..."
        # Install using the official standalone installer
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Ensure uv is in path for this session
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            export PATH="$HOME/.local/bin:$PATH"
        fi
    else
        log_info "'uv' is already installed."
    fi
}

# --- 4. Bootstrap Project ---

setup_project() {
    log_info "Bootstrapping Python environment..."

    if [ -f "pyproject.toml" ]; then
        if command -v uv >/dev/null 2>&1; then
            log_info "Syncing dependencies with uv..."
            uv sync
            source .venv/bin/activate
        else
            log_warn "uv installation failed or not found. Falling back to standard pip."
            python3 -m venv .venv
            source .venv/bin/activate
            pip install -e .
        fi
    else
        log_error "pyproject.toml not found. Are you in the project root?"
        exit 1
    fi
    log_success "Python environment ready."
}

# --- 5. Whisper Server Setup (Optional) ---

setup_whisper() {
    echo ""
    log_info "--- Whisper Transcription Server Setup ---"
    read -p "Do you want to build the CUDA-enabled Whisper Server image now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -d "whisper-server" ]; then
            cd whisper-server
            
            # Check for NVIDIA drivers
            if command -v nvidia-smi >/dev/null 2>&1; then
                log_info "NVIDIA GPU detected."
            else
                log_warn "NVIDIA GPU not detected. The container requires NVIDIA drivers for CUDA support."
            fi

            log_info "Building container image (this may take a while)..."
            if [ -f "./build-whisper-image.sh" ]; then
                chmod +x ./build-whisper-image.sh
                ./build-whisper-image.sh
            else
                podman build -t whisper-server-cuda:latest -f Containerfile .
            fi
            
            cd ..
            log_success "Whisper server image built."
            log_info "You can start the server later with: podman-compose -f whisper-server/compose.yml up -d"
        else
            log_warn "whisper-server directory not found. Skipping."
        fi
    else
        log_info "Skipping Whisper Server build."
    fi
}

# --- Main Execution ---

main() {
    echo "=========================================="
    echo "   Omega-13 Installer & Bootstrap"
    echo "=========================================="
    
    detect_pkg_manager
    install_system_deps
    install_uv
    setup_project
    setup_whisper

    echo ""
    echo "=========================================="
    echo -e "${GREEN}Installation Complete!${NC}"
    echo "To run the application:"
    echo "  uv run python -m omega13"
    echo "=========================================="
}

main
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
    echo -e "${BLUE}[INFO]${NC} "
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} "
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} "
}

log_error() {
    echo -e "${RED}[ERROR]${NC} "
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

# --- 5. Build Whisper Image ---
build_whisper_image() {
    log_info "Building whisper-server CUDA image."

    # Configuration
    local IMAGE_NAME="whisper-server-cuda"
    local IMAGE_TAG="latest"
    local FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

    # Build arguments
    local WHISPER_VERSION="${WHISPER_VERSION:-master}"
    # Default: support RTX 20xx/30xx/40xx, A100, H100
    # Customize with: CUDA_ARCHITECTURES="86" ./bootstrap.sh
    local CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES:-75;80;86;89;90}"

    echo ""
    log_info "Build Configuration:"
    echo "  Image:              ${FULL_IMAGE}"
    echo "  Whisper version:      ${WHISPER_VERSION}"
    echo "  CUDA architectures:   ${CUDA_ARCHITECTURES}"
    echo ""
    log_info "Reference for CUDA architectures:"
    echo "  75: RTX 20xx (Turing)   80: A100 (Ampere)"
    echo "  86: RTX 30xx (Ampere)   89: RTX 40xx (Ada)"
    echo "  90: H100 (Hopper)"
    echo ""

    # Build the image
    log_info "Starting build (this may take a while)..."
    podman build \
        --tag "${FULL_IMAGE}" \
        --build-arg WHISPER_VERSION="${WHISPER_VERSION}" \
        --build-arg CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES}" \
        --file Containerfile \
        .
    
    log_success "Image '${FULL_IMAGE}' built successfully."
    echo ""
    log_info "To run the server, use:"
    log_info "  podman-compose up -d"

}

# --- 6. Whisper Server Setup (Optional) ---

setup_whisper() {
    echo ""
    log_info "--- Whisper Transcription Server Setup ---"
    read -p "Do you want to build the CUDA-enabled Whisper Server image now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Check for NVIDIA drivers
        if command -v nvidia-smi >/dev/null 2>&1; then
            log_info "NVIDIA GPU detected."
        else
            log_warn "NVIDIA GPU not detected. The container may require NVIDIA drivers for CUDA support."
        fi

        build_whisper_image
        
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
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

# --- 5. GPU Detection ---

detect_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi &> /dev/null; then
            echo "cuda"
            return 0
        fi
    fi
    echo "cpu"
    return 1
}

# --- 6. Build Container Images (Multi-Variant) ---

build_whisper_cpu() {
    log_info "Building whisper-server-cpu image..."
    podman build \
        -t whisper-server-cpu:latest \
        -f Containerfile.cpu \
        .
    log_success "whisper-server-cpu image built successfully."
}

build_whisper_cuda() {
    log_info "Building whisper-server-cuda image..."
    local CUDA_ARCH="${CUDA_ARCH:-75;80;86;89;90}"

    echo ""
    log_info "CUDA Build Configuration:"
    echo "  CUDA architectures: ${CUDA_ARCH}"
    echo "  75: RTX 20xx (Turing)   80: A100 (Ampere)"
    echo "  86: RTX 30xx (Ampere)   89: RTX 40xx (Ada)"
    echo "  90: H100 (Hopper)"
    echo ""

    podman build \
        --build-arg CUDA_ARCHITECTURES="${CUDA_ARCH}" \
        -t whisper-server-cuda:latest \
        -f Containerfile \
        .
    log_success "whisper-server-cuda image built successfully."
}

build_spacy_cpu() {
    log_info "Building spacy-nlp-cpu image..."
    podman build \
        -t spacy-nlp-cpu:latest \
        -f containers/spacy-nlp/Containerfile.cpu \
        containers/spacy-nlp/
    log_success "spacy-nlp-cpu image built successfully."
}

build_spacy_cuda() {
    log_info "Building spacy-nlp-cuda image..."
    podman build \
        -t spacy-nlp-cuda:latest \
        -f containers/spacy-nlp/Containerfile.cuda \
        containers/spacy-nlp/
    log_success "spacy-nlp-cuda image built successfully."
}

build_images() {
    local gpu_mode=$(detect_gpu)

    echo ""
    log_info "=== Container Image Build ==="
    log_info "Detected mode: ${gpu_mode}"
    echo ""

    if [ "$gpu_mode" = "cuda" ]; then
        log_info "Building GPU-accelerated images..."

        log_info "Building whisper-server-cuda image..."
        if build_whisper_cuda; then
            echo "✓ Whisper CUDA build successful"
        else
            log_warn "Whisper CUDA build failed, falling back to CPU..."
            build_whisper_cpu
        fi

        log_info "Building spacy-nlp-cuda image..."
        if build_spacy_cuda; then
            echo "✓ SpaCy CUDA build successful"
        else
            log_warn "SpaCy CUDA build failed, falling back to CPU..."
            build_spacy_cpu
        fi
    else
        log_info "No GPU detected or nvidia-smi not available. Building CPU-only images..."
        build_whisper_cpu
        build_spacy_cpu
    fi

    echo ""
    log_success "All images built successfully!"
    echo ""
    log_info "To start services:"
    log_info "  podman compose -f compose-dev.yml up -d    # GPU variant"
    log_info "  podman compose -f compose-dev.cpu.yml up -d # CPU variant"
}

# --- 7. Command-Line Interface ---

show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  --all          Build all images (auto-detect GPU, fallback to CPU)"
    echo "  --cpu          Force CPU-only builds"
    echo "  --cuda         Force CUDA builds (requires GPU)"
    echo "  --whisper-only Build whisper image only (auto-detect)"
    echo "  --whisper-cpu  Build whisper CPU variant"
    echo "  --whisper-cuda Build whisper CUDA variant"
    echo "  --spacy-only   Build spaCy image only (auto-detect)"
    echo "  --spacy-cpu    Build spaCy CPU variant"
    echo "  --spacy-cuda   Build spaCy CUDA variant"
    echo "  --help         Show this help message"
    echo ""
}

handle_build_command() {
    case "${1:-}" in
        --whisper-only)
            gpu_mode=$(detect_gpu)
            if [ "$gpu_mode" = "cuda" ]; then
                build_whisper_cuda || build_whisper_cpu
            else
                build_whisper_cpu
            fi
            ;;
        --whisper-cpu)
            build_whisper_cpu
            ;;
        --whisper-cuda)
            build_whisper_cuda
            ;;
        --spacy-only)
            gpu_mode=$(detect_gpu)
            if [ "$gpu_mode" = "cuda" ]; then
                build_spacy_cuda || build_spacy_cpu
            else
                build_spacy_cpu
            fi
            ;;
        --spacy-cpu)
            build_spacy_cpu
            ;;
        --spacy-cuda)
            build_spacy_cuda
            ;;
        --cpu)
            log_info "Building CPU-only images..."
            build_whisper_cpu
            build_spacy_cpu
            ;;
        --cuda)
            log_info "Building CUDA images..."
            build_whisper_cuda
            build_spacy_cuda
            ;;
        --all|"")
            build_images
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
}

# --- 8. Interactive Container Setup (Optional) ---

setup_containers() {
    echo ""
    log_info "--- Container Image Setup ---"
    read -p "Do you want to build container images now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Check for NVIDIA drivers
        if command -v nvidia-smi >/dev/null 2>&1; then
            log_info "NVIDIA GPU detected - will build CUDA variants."
        else
            log_warn "NVIDIA GPU not detected - will build CPU variants."
        fi

        build_images
    else
        log_info "Skipping container builds."
        echo ""
        log_info "You can build images later with:"
        log_info "  ./bootstrap.sh --all"
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
    setup_containers

    echo ""
    echo "=========================================="
    echo -e "${GREEN}Installation Complete!${NC}"
    echo "To run the application:"
    echo "  uv run python -m omega13"
    echo "=========================================="
}

# Check if script was called with build arguments
if [ $# -gt 0 ]; then
    # Build-only mode (skip system setup)
    handle_build_command "$1"
else
    # Full installation mode
    main
fi
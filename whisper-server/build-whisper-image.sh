#!/bin/bash
# Build script for whisper-server CUDA image

set -e  # Exit on error

echo "========================================"
echo "Building whisper-server CUDA image"
echo "========================================"

# Configuration
IMAGE_NAME="whisper-server-cuda"
IMAGE_TAG="latest"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

# Build arguments
WHISPER_VERSION="${WHISPER_VERSION:-master}"
# Default: support RTX 20xx/30xx/40xx, A100, H100
# Customize with: CUDA_ARCHITECTURES="86" ./build-whisper-image.sh (RTX 30xx only)
CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES:-75;80;86;89;90}"

echo ""
echo "Build Configuration:"
echo "  Image: ${FULL_IMAGE}"
echo "  Whisper version: ${WHISPER_VERSION}"
echo "  CUDA architectures: ${CUDA_ARCHITECTURES}"
echo ""
echo "GPU Architecture Codes:"
echo "  75 = RTX 20xx (Turing)"
echo "  80 = A100 (Ampere)"
echo "  86 = RTX 30xx (Ampere)"
echo "  89 = RTX 40xx (Ada Lovelace)"
echo "  90 = H100 (Hopper)"
echo ""

# Build the image
echo "Building image..."
podman build \
    --tag "${FULL_IMAGE}" \
    --build-arg WHISPER_VERSION="${WHISPER_VERSION}" \
    --build-arg CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES}" \
    --file Containerfile \
    .

echo ""
echo "========================================"
echo "Build complete!"
echo "========================================"
echo ""
echo "Image: ${FULL_IMAGE}"
echo ""
echo "To run the server:"
echo "  podman-compose up -d"
echo ""
echo "Or manually:"
echo "  podman run -d \\"
echo "    --name whisper-server \\"
echo "    -p 8080:8080 \\"
echo "    -v \$HOME/LLMOS/whisper.cpp/models:/app/models:ro \\"
echo "    ${FULL_IMAGE}"
echo ""

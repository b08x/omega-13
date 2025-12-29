# Multi-stage build for whisper.cpp with CUDA support
# Stage 1: Build environment
FROM nvidia/cuda:12.6.1-devel-ubuntu22.04 AS builder

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    cmake \
    pkg-config \
    libopenblas-dev \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Clone whisper.cpp repository
ARG WHISPER_VERSION=master
RUN git clone https://github.com/ggerganov/whisper.cpp.git \
    && cd whisper.cpp \
    && git checkout ${WHISPER_VERSION}

# Build whisper.cpp with CUDA support
# CUDA architectures: 75=RTX20xx, 80=A100, 86=RTX30xx, 89=RTX40xx, 90=H100
ARG CUDA_ARCHITECTURES="75;80;86;89;90"

WORKDIR /build/whisper.cpp

# CRITICAL: Create libcuda.so.1 symlink in stubs directory
# This is the industry-standard workaround for Docker CUDA builds
# The linker expects libcuda.so.1 (versioned), but stubs only has libcuda.so (unversioned)
RUN ln -s /usr/local/cuda/lib64/stubs/libcuda.so \
    /usr/local/cuda/lib64/stubs/libcuda.so.1

# Use CUDA stubs for linking during build (required when no GPU present)
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64/stubs:${LD_LIBRARY_PATH}

RUN mkdir build && cd build \
    && cmake .. \
    -DGGML_CUDA=ON \
    -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_EXE_LINKER_FLAGS="-Wl,--allow-shlib-undefined" \
    && cmake --build . --config Release -j$(($(nproc) / 2))

# Reset LD_LIBRARY_PATH after build
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}

# Download models (optional - can be mounted from host instead)
# Uncomment to include models in image:
WORKDIR /build/whisper.cpp
# RUN bash ./models/download-ggml-model.sh base
RUN bash ./models/download-ggml-model.sh large-v3-turbo-q5_0

# Stage 2: Runtime environment
FROM nvidia/cuda:12.6.1-runtime-ubuntu22.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libopenblas0 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Create library directory
RUN mkdir -p /app/lib

# Copy built binaries from builder stage
COPY --from=builder /build/whisper.cpp/build/bin/whisper-server /app/whisper-server
COPY --from=builder /build/whisper.cpp/build/bin/whisper-cli /app/whisper-cli
COPY --from=builder /build/whisper.cpp/build/bin/quantize /app/quantize

# Copy ALL shared libraries (.so*) from build directories
# CRITICAL: Use cp -a to preserve symlinks (libwhisper.so.1 -> libwhisper.so.1.8.2, etc.)
COPY --from=builder /build/whisper.cpp/build/ /tmp/build/

# Extract .so* files to /app/lib - PRESERVE SYMLINKS with -P flag
RUN find /tmp/build -name "*.so*" \( -type f -o -type l \) -exec cp -P {} /app/lib/ \; && \
    rm -rf /tmp/build

# Set library path for runtime (include CUDA runtime libs)
ENV LD_LIBRARY_PATH=/app/lib:/usr/local/cuda/lib64:${LD_LIBRARY_PATH}

# Copy models if included in build (optional)
COPY --from=builder /build/whisper.cpp/models /app/models

# Create directory for models (can be mounted from host)
RUN mkdir -p /app/models /app/lib

# Expose whisper-server port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080 || exit 1

# Environment variables with defaults
ENV WHISPER_MODEL_DIR=/app/models
ENV WHISPER_MODEL=large-v3-turbo-q5_0
ENV WHISPER_THREADS=8
ENV WHISPER_HOST=0.0.0.0
ENV WHISPER_PORT=8080

# Default entrypoint
ENTRYPOINT ["/app/whisper-server"]

# Default command (can be overridden)
CMD ["-m", "${WHISPER_MODEL_DIR}/ggml-${WHISPER_MODEL}.bin", \
    "--host", "${WHISPER_HOST}", \
    "--port", "${WHISPER_PORT}", \
    "-t", "${WHISPER_THREADS}", \
    "--convert", \
    "-nf", \
    "--print-progress"]

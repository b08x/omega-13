# Building Whisper-Server CUDA Image

This guide covers building a production-ready CUDA-enabled whisper-server container image.

## Prerequisites

### Required

- **Podman** (or Docker) installed
- **NVIDIA GPU** with CUDA support
- **nvidia-container-toolkit** for GPU access in containers
- **Disk space**: ~10GB for build process

### Verify NVIDIA setup

```bash
# Check NVIDIA driver
nvidia-smi

# Check CUDA version
nvcc --version

# Test podman GPU access
podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.6.1-base-ubuntu22.04 nvidia-smi
```

## Quick Start

### 1. Build the Image

```bash
chmod +x build-whisper-image.sh
./build-whisper-image.sh
```

This creates: `whisper-server-cuda:latest`

### 2. Verify Build

```bash
podman images | grep whisper-server
```

Expected output:

```
localhost/whisper-server-cuda  latest  <image-id>  <size>
```

### 3. Deploy with Podman Compose

```bash
# Using production configuration
podman-compose -f podman-compose-production.yml up -d

# Check status
podman-compose -f podman-compose-production.yml ps

# View logs
podman-compose -f podman-compose-production.yml logs -f
```

## Build Configuration

### Containerfile Structure

```
Containerfile (multi-stage build)
├── Stage 1: Builder
│   ├── CUDA 12.6.1 development base
│   ├── Build whisper.cpp from source
│   ├── Compile with CUDA support
│   └── Optimize for native GPU architecture
│
└── Stage 2: Runtime
    ├── CUDA 12.6.1 runtime base (smaller)
    ├── Copy compiled binaries
    ├── Install runtime dependencies
    └── Configure server defaults
```

### Build Arguments

Customize the build:

```bash
# Specific whisper.cpp version/commit
podman build \
  --build-arg WHISPER_VERSION=v1.5.4 \
  -t whisper-server-cuda:v1.5.4 \
  -f Containerfile .

# Include models in image (larger but self-contained)
# Uncomment model download lines in Containerfile first
podman build \
  -t whisper-server-cuda:bundled \
  -f Containerfile .
```

### GPU Architecture Optimization

The Containerfile uses `CMAKE_CUDA_ARCHITECTURES=native` which optimizes for your GPU.

**For multi-GPU or deployment flexibility:**

```dockerfile
# In Containerfile, change:
-DCMAKE_CUDA_ARCHITECTURES=native
# To specific architectures:
-DCMAKE_CUDA_ARCHITECTURES="75;80;86;89"  # Common modern GPUs
```

**Architecture codes:**

- `75`: RTX 20xx (Turing)
- `80`: A100 (Ampere)
- `86`: RTX 30xx (Ampere)
- `89`: RTX 40xx (Ada Lovelace)
- `90`: H100 (Hopper)

## Deployment Options

### Option 1: Podman Compose (Recommended)

```bash
# Production deployment
podman-compose -f podman-compose-production.yml up -d
```

**Benefits:**

- Declarative configuration
- Easy updates and rollbacks
- Automatic restart on failure
- Resource limits enforced

### Option 2: Manual Podman Run

```bash
podman run -d \
  --name whisper-server \
  -p 8080:8080 \
  -v $HOME/LLMOS/whisper.cpp/models:/app/models:ro \
  --device nvidia.com/gpu=all \
  --restart unless-stopped \
  whisper-server-cuda:latest
```

### Option 3: Systemd Service

Create `/etc/systemd/system/whisper-server.service`:

```ini
[Unit]
Description=Whisper Transcription Server
After=network.target

[Service]
Type=simple
User=%i
ExecStartPre=/usr/bin/podman pull whisper-server-cuda:latest
ExecStart=/usr/bin/podman run \
  --rm \
  --name whisper-server \
  -p 8080:8080 \
  -v /home/%i/LLMOS/whisper.cpp/models:/app/models:ro \
  --device nvidia.com/gpu=all \
  whisper-server-cuda:latest
ExecStop=/usr/bin/podman stop -t 10 whisper-server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now whisper-server@$USER
```

## Model Management

### Download Models

Models are **not** included in the image by default (keeps image size small).

**Download to host:**

```bash
cd ~/LLMOS/whisper.cpp
./models/download-ggml-model.sh base
./models/download-ggml-model.sh large-v3-turbo-q5_0
```

**Available models:**

- `tiny`: ~75MB, fastest, lowest accuracy
- `base`: ~140MB, good balance
- `small`: ~460MB, better accuracy
- `medium`: ~1.5GB, high accuracy
- `large-v3`: ~3GB, best accuracy
- `large-v3-turbo`: ~1.6GB, fast + accurate
- `large-v3-turbo-q5_0`: ~1GB, quantized (recommended)

### Model in Image (Alternative)

To bundle models in the image (self-contained but larger):

**Uncomment in Containerfile:**

```dockerfile
# Uncomment these lines:
RUN bash ./models/download-ggml-model.sh large-v3-turbo-q5_0
```

**Rebuild:**

```bash
./build-whisper-image.sh
```

**Result:** ~5GB image with embedded model

## Configuration

### Environment Variables

Override in `podman-compose-production.yml`:

```yaml
environment:
  - WHISPER_MODEL=/app/models/ggml-base.bin  # Change model
  - WHISPER_THREADS=16  # Increase for more CPU cores
  - WHISPER_HOST=0.0.0.0
  - WHISPER_PORT=8080
```

### Resource Limits

Adjust based on your hardware:

```yaml
deploy:
  resources:
    limits:
      memory: 16G  # For large models
      cpus: '8.0'  # Limit CPU usage
```

### Whisper-Server Options

Modify `command` section in compose file:

```yaml
command:
  - "-m"
  - "/app/models/ggml-large-v3-turbo-q5_0.bin"
  - "-t"
  - "16"  # More threads
  - "--beam-size"
  - "5"  # Better quality (slower)
  - "--best-of"
  - "5"  # Multiple candidates
  - "-nf"  # No temperature fallback
  - "--convert"  # Audio format conversion
```

## Troubleshooting

### Build Fails

**CUDA version mismatch:**

```bash
# Check your CUDA version
nvidia-smi

# Update base image in Containerfile:
FROM nvidia/cuda:11.8.0-devel-ubuntu22.04  # For CUDA 11.x
FROM nvidia/cuda:12.6.1-devel-ubuntu22.04  # For CUDA 12.x
```

**Out of memory during build:**

```bash
# Reduce parallel jobs
# In Containerfile, change:
cmake --build . -j$(nproc)
# To:
cmake --build . -j4  # Use 4 jobs instead
```

### Runtime Issues

**GPU not detected:**

```bash
# Check nvidia-container-toolkit
podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.6.1-base-ubuntu22.04 nvidia-smi

# If fails, install/configure toolkit:
# For Fedora:
sudo dnf install nvidia-container-toolkit
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
```

**Model not found:**

```bash
# Verify volume mount
podman exec whisper-server ls -la /app/models/

# Check model file exists on host
ls -lh ~/LLMOS/whisper.cpp/models/
```

**Server not responding:**

```bash
# Check logs
podman logs whisper-server

# Common issues:
# - Model still loading (wait 30-60s)
# - Port already in use (change in compose file)
# - Insufficient memory (reduce model size or increase limit)
```

## Performance Optimization

### GPU Utilization

```bash
# Monitor GPU usage during transcription
watch -n 1 nvidia-smi
```

**Expected:**

- Model loading: High VRAM usage, low compute
- Transcription: High compute, steady VRAM

### CPU Threads

Optimal thread count = 2× physical cores:

```bash
# Check cores
nproc

# For 8 cores, use -t 16
```

### Memory Usage

**Model memory requirements:**

- `tiny`: ~1GB RAM
- `base`: ~2GB RAM
- `small`: ~3GB RAM
- `medium`: ~5GB RAM
- `large-v3-turbo-q5_0`: ~4GB RAM
- `large-v3`: ~10GB RAM

## Updates

### Rebuild Image

```bash
# Pull latest whisper.cpp
./build-whisper-image.sh

# Or specific version
WHISPER_VERSION=v1.6.0 ./build-whisper-image.sh
```

### Update Running Container

```bash
# Rebuild image
./build-whisper-image.sh

# Recreate container
podman-compose -f podman-compose-production.yml down
podman-compose -f podman-compose-production.yml up -d
```

## Security Considerations

### Read-Only Volumes

Models and recordings mounted read-only:

```yaml
volumes:
  - ${HOME}/LLMOS/whisper.cpp/models:/app/models:ro  # Read-only
```

### Non-Root User (Optional)

Add to Containerfile:

```dockerfile
# Create non-root user
RUN useradd -m -u 1000 whisper
USER whisper
```

### Network Isolation

Limit to localhost only:

```yaml
ports:
  - "127.0.0.1:8080:8080"  # Only accessible from host
```

## Monitoring

### Health Checks

```bash
# Check container health
podman inspect whisper-server | grep -A 10 Health

# Manual health check
curl -f http://localhost:8080 || echo "Server not responding"
```

### Logs

```bash
# Follow logs
podman logs -f whisper-server

# Last 100 lines
podman logs --tail 100 whisper-server

# With timestamps
podman logs -t whisper-server
```

## Cleanup

### Remove Container

```bash
podman-compose -f podman-compose-production.yml down
```

### Remove Image

```bash
podman rmi whisper-server-cuda:latest
```

### Full Cleanup

```bash
# Remove containers, volumes, and images
podman-compose -f podman-compose-production.yml down -v
podman rmi whisper-server-cuda:latest
podman system prune -a
```

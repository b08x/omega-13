# Quick Start Guide - TimeMachine Transcription

Get up and running with containerized transcription in 5 minutes.

## Prerequisites

- ✓ NVIDIA GPU with CUDA support
- ✓ Podman installed
- ✓ nvidia-container-toolkit configured
- ✓ Whisper models downloaded to `~/LLMOS/whisper.cpp/models/`

## Step-by-Step Setup

### 1. Build the Container Image

```bash
cd /var/home/b08x/Workspace/timemachine-py
./build-whisper-image.sh
```

**Expected output:**
```
========================================
Building whisper-server CUDA image
========================================
[...]
Build complete!
```

**Time:** ~5-10 minutes (depending on hardware)

### 2. Start the Server

```bash
podman-compose -f podman-compose-production.yml up -d
```

**Verify it's running:**
```bash
podman ps | grep whisper-server
```

**Check logs:**
```bash
podman logs -f whisper-server
```

Look for:
```
whisper_init_from_file_with_params_no_state: loading model from '...'
whisper_model_load: model size    = ... MB
Server listening on http://0.0.0.0:8080
```

### 3. Test the Server

```bash
curl http://localhost:8080
```

Should return HTML page with upload form.

**Test transcription:**
```bash
curl -X POST \
  -F "file=@/path/to/test.wav" \
  -F "response_format=json" \
  http://localhost:8080/inference | jq .
```

### 4. Run TimeMachine

```bash
python timemachine.py
```

The app will automatically connect to whisper-server and transcribe recordings!

## Architecture Overview

```
┌──────────────────────┐
│  TimeMachine TUI     │  Python app with Textual UI
│  (timemachine.py)    │
└──────────┬───────────┘
           │
           │ HTTP POST /inference
           ↓
┌──────────────────────┐
│  whisper-server      │  Container with CUDA
│  Port: 8080          │  Model loaded in memory
└──────────────────────┘
```

## File Structure

```
timemachine-py/
├── Containerfile                  # Multi-stage CUDA build
├── build-whisper-image.sh         # Build script
├── podman-compose-production.yml  # Production deployment
├── transcription.py               # HTTP API client
├── timemachine.py                 # Main TUI app
├── BUILD.md                       # Detailed build docs
├── TRANSCRIPTION.md               # API usage guide
└── QUICKSTART.md                  # This file
```

## Common Commands

### Server Management

```bash
# Start server
podman-compose -f podman-compose-production.yml up -d

# Stop server
podman-compose -f podman-compose-production.yml down

# Restart server
podman-compose -f podman-compose-production.yml restart

# View logs
podman-compose -f podman-compose-production.yml logs -f

# Check status
podman-compose -f podman-compose-production.yml ps
```

### Monitoring

```bash
# GPU usage
watch -n 1 nvidia-smi

# Container stats
podman stats whisper-server

# Health check
curl -f http://localhost:8080 && echo "OK" || echo "FAIL"
```

### Testing

```bash
# Test with curl
curl -X POST \
  -F "file=@recording.wav" \
  http://localhost:8080/inference

# Test with Python
python test_transcription_debug.py
```

## Troubleshooting

### Server won't start

**Check logs:**
```bash
podman logs whisper-server
```

**Common fixes:**
```bash
# Port already in use - change port in compose file
ports:
  - "8081:8080"  # Use different host port

# Model not found - verify path
ls -lh ~/LLMOS/whisper.cpp/models/
```

### GPU not working

**Verify NVIDIA setup:**
```bash
# Check driver
nvidia-smi

# Test container GPU access
podman run --rm --device nvidia.com/gpu=all \
  nvidia/cuda:12.6.1-base-ubuntu22.04 nvidia-smi
```

### Slow transcription

**Optimize threads:**
```yaml
# In podman-compose-production.yml
command:
  - "-t"
  - "16"  # Increase for more CPU cores
```

**Use smaller model:**
```yaml
environment:
  - WHISPER_MODEL=/app/models/ggml-base.bin
```

### Connection refused

**Check firewall:**
```bash
sudo firewall-cmd --list-ports
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --reload
```

**Verify server is listening:**
```bash
podman exec whisper-server netstat -tlnp | grep 8080
```

## Configuration

### Change Model

Edit `podman-compose-production.yml`:
```yaml
environment:
  - WHISPER_MODEL=/app/models/ggml-base.bin  # Faster, less accurate
  # or
  - WHISPER_MODEL=/app/models/ggml-large-v3.bin  # Slower, more accurate
```

Restart:
```bash
podman-compose -f podman-compose-production.yml restart
```

### Adjust Performance

**More threads (better CPU utilization):**
```yaml
command:
  - "-t"
  - "16"  # 2× your CPU cores
```

**Better quality (slower):**
```yaml
command:
  - "--beam-size"
  - "10"  # Higher = better quality
  - "--best-of"
  - "5"  # Multiple candidates
```

## Next Steps

- ✓ Read [BUILD.md](BUILD.md) for detailed build configuration
- ✓ Read [TRANSCRIPTION.md](TRANSCRIPTION.md) for API documentation
- ✓ Customize [podman-compose-production.yml](podman-compose-production.yml) for your hardware
- ✓ Set up systemd service for auto-start (see BUILD.md)

## Performance Expectations

**Typical transcription speeds (RTX 3090):**
- `tiny`: ~100x realtime (1 min audio in 0.6s)
- `base`: ~50x realtime (1 min audio in 1.2s)
- `small`: ~25x realtime (1 min audio in 2.4s)
- `large-v3-turbo-q5_0`: ~15x realtime (1 min audio in 4s)
- `large-v3`: ~8x realtime (1 min audio in 7.5s)

*Your mileage may vary based on GPU, CPU, and audio complexity*

## Getting Help

**Check logs first:**
```bash
podman logs whisper-server
```

**Enable debug logging:**
```python
# In test_transcription_debug.py
logging.basicConfig(level=logging.DEBUG)
```

**Common issues:**
1. GPU not detected → Check nvidia-container-toolkit
2. Model not found → Verify volume mount paths
3. Port conflict → Change host port in compose file
4. Out of memory → Use smaller model or increase limits

## Clean Uninstall

```bash
# Stop and remove container
podman-compose -f podman-compose-production.yml down

# Remove image
podman rmi whisper-server-cuda:latest

# Clean up build cache
podman system prune -a
```

---

**Ready to go!** Start the server and run TimeMachine. Your recordings will be automatically transcribed via the persistent whisper-server. 🚀

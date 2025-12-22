# Transcription Setup Guide

## Architecture Overview

The Omega-13 application uses a **persistent whisper-server** for audio transcription via HTTP API.

```shell
┌─────────────────┐         HTTP POST          ┌──────────────────┐
│  Omega-13       │────────────────────────────>│ whisper-server   │
│  (TUI App)      │    /inference endpoint     │  (Container)     │
│                 │<────────────────────────────│                  │
│  Python Client  │         JSON response       │  Model in Memory │
└─────────────────┘                             └──────────────────┘
```

**Benefits:**

- ✓ Model loaded once at startup (not per-request)
- ✓ Fast transcription (no container startup overhead)
- ✓ Concurrent request support
- ✓ Production-ready HTTP interface
- ✓ Automatic audio format conversion (ffmpeg)

## Quick Start

### 1. Start the Whisper Server

Using podman-compose:

```bash
podman-compose -f podman-compose.yml up -d
```

Or manually with podman:

```bash
podman run -d \
  --name whisper-server \
  -p 8080:8080 \
  -v $HOME:$HOME:ro \
  localhost/whisper-cuda:2025-12-21 \
  /home/b08x/LLMOS/whisper.cpp/build/bin/whisper-server \
  -m /home/b08x/LLMOS/whisper.cpp/models/ggml-large-v3-turbo-q5_0.bin \
  --host 0.0.0.0 \
  --port 8080 \
  -t 8 \
  --convert
```

### 2. Verify Server is Running

Check health:

```bash
curl http://localhost:8080
```

Expected output: HTML page with upload form

### 3. Run TimeMachine

The app will automatically connect to the server at `http://localhost:8080`:

```bash
python -m omega13
```

## Configuration

### Server Settings

Edit `podman-compose.yml` to customize:

```yaml
command:
  - "-m"  # Model path
  - "/home/b08x/LLMOS/whisper.cpp/models/ggml-large-v3-turbo-q5_0.bin"
  - "--host"
  - "0.0.0.0"  # Listen on all interfaces
  - "--port"
  - "8080"  # Server port
  - "-t"
  - "8"  # CPU threads (adjust for your system)
  - "--convert"  # Enable audio conversion (requires ffmpeg)
```

### Client Configuration

In `omega13` package, modify initialization:

```python
self.transcription_service = TranscriptionService(
    server_url="http://localhost:8080",  # Change if using different host/port
    inference_path="/inference",  # API endpoint
    timeout=600  # Request timeout in seconds (10 minutes)
)
```

## API Reference

### Endpoint: POST /inference

**Request:**

- Method: `POST`
- Content-Type: `multipart/form-data`
- File field: `file` (audio file)

**Optional Parameters:**

- `response_format`: `json` or `text` (default: `json`)
- `temperature`: `0.0` - `1.0` (deterministic vs creative)

**Response (JSON):**

```json
{
  "text": "Transcribed text here",
  "language": "en",
  "segments": [...]
}
```

### Example with curl

```bash
curl -X POST \
  -F "file=@recording.wav" \
  -F "response_format=json" \
  http://localhost:8080/inference
```

## Troubleshooting

### Server Won't Start

**Check logs:**

```bash
podman logs whisper-server
```

**Common issues:**

- Port 8080 already in use: Change port in `podman-compose.yml`
- Model file not found: Verify path in command
- Insufficient memory: Use smaller model (e.g., `base` instead of `large`)

### Connection Errors

**Verify server is running:**

```bash
podman ps | grep whisper-server
```

**Test connectivity:**

```bash
curl -v http://localhost:8080
```

**Check firewall:**

```bash
sudo firewall-cmd --list-ports  # Should show 8080/tcp
```

### Slow Transcription

**Optimize threads:**
Increase `-t` parameter based on CPU cores:

```yaml
command:
  - "-t"
  - "16"  # Use more threads
```

**Use GPU acceleration:**
Ensure container has GPU access (CUDA):

```bash
podman run --device nvidia.com/gpu=all ...
```

### Out of Memory

**Use smaller model:**

```yaml
command:
  - "-m"
  - "/home/b08x/LLMOS/whisper.cpp/models/ggml-base.bin"  # Smaller model
```

**Limit container memory:**

```yaml
deploy:
  resources:
    limits:
      memory: 8G
```

## Server Management

### Start server

```bash
podman-compose up -d
```

### Stop server

```bash
podman-compose down
```

### Restart server

```bash
podman-compose restart
```

### View logs

```bash
podman-compose logs -f whisper-server
```

### Check status

```bash
podman-compose ps
```

## Performance Tips

1. **Model Selection:**
   - `tiny`: Fastest, lowest accuracy (~1GB RAM)
   - `base`: Good balance (~2GB RAM)
   - `small`: Better accuracy (~3GB RAM)
   - `medium`: High accuracy (~5GB RAM)
   - `large`: Best accuracy (~10GB RAM)
   - `large-v3-turbo-q5_0`: Quantized, fast & accurate (~4GB RAM)

2. **Hardware:**
   - GPU: Use CUDA-enabled image for 10-20x speedup
   - CPU: Increase threads (`-t`) to match core count
   - RAM: Ensure enough memory for model + audio buffer

3. **Network:**
   - Local requests (localhost): < 1ms latency
   - Remote requests: Consider network bandwidth for large audio files

## Development

### Debug Mode

Enable verbose logging:

```bash
# In test script
logging.basicConfig(level=logging.DEBUG)
```

### Test Server Manually

```python
import requests

# Health check
response = requests.get("http://localhost:8080")
print(response.status_code)  # Should be 200

# Transcribe file
with open("test.wav", "rb") as f:
    files = {"file": f}
    response = requests.post("http://localhost:8080/inference", files=files)
    result = response.json()
    print(result["text"])
```

## Migration from Ephemeral Containers

**Old approach (deprecated):**

- Spun up new container per transcription
- Loaded model each time
- High latency (~10-30 seconds startup)

**New approach (current):**

- Persistent server with loaded model
- HTTP API requests
- Low latency (model already loaded)
- Better resource utilization

**Migration:** No changes needed to your audio files or workflows - just start the server and run the app!

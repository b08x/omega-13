# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Omega-13 is a terminal-based retroactive audio recorder and transcription tool for Linux. It maintains a continuous 13-second ring buffer in memory, allowing users to capture audio *after* they realize they wanted to record it. The application uses JACK/PipeWire for professional audio routing and delegates transcription to a local Docker-based whisper.cpp server for privacy.

**Key Innovation:** The retroactive recording mechanism means the buffer is *always* recording in memory, and the "record" hotkey triggers saving what has already been captured (past 13 seconds) plus whatever follows until the hotkey is pressed again.

## Architecture

### Core Components

**Audio Pipeline (`audio.py`):**

- `AudioEngine` manages the JACK client and implements the circular ring buffer using NumPy
- Ring buffer size: `samplerate * 13 seconds` (defaults to ~624,000 frames at 48kHz)
- **Critical:** The JACK `process()` callback runs in real-time audio thread - must be lock-free and fast
- Recording happens in two phases:
  1. Reconstruct past audio from ring buffer when recording starts
  2. Write live audio to queue while recording continues
- File writing happens in separate thread (`_file_writer`) to avoid blocking JACK

**TUI Application (`app.py`):**

- Built with Textual framework
- Main app class: `Omega13App`
- Lifecycle: `on_mount()` → start audio engine → load config → register signal handlers → start hotkey listener
- **Shutdown Sequence** (`on_unmount()`): Stop hotkeys → stop audio → wait for transcription threads (with 60s deadline) → cleanup sessions → remove PID file

**Session Management (`session.py`):**

- Sessions live in `/tmp/omega13` by default
- Each session has sequential numbered recordings: `001.wav`, `002.wav`, etc.
- Can be saved to permanent storage (e.g., `~/Recordings`)
- Metadata stored in `session.json` including timestamps, duration, channels, samplerate

**Transcription (`transcription.py`):**

- Async HTTP client for whisper.cpp server
- Implements retry logic (3 attempts) with exponential backoff
- Cooperative shutdown via `_shutdown_event` threading event
- Results saved as `.md` files alongside `.wav` recordings

**Configuration (`config.py`):**

- JSON-based config stored in `~/.config/omega13/config.json`
- Key settings: input ports, hotkeys, transcription server URL, clipboard behavior

**Global Hotkeys (`hotkeys.py`):**

- Uses `pynput` for cross-platform keyboard monitoring
- Wayland workaround: Application writes PID file, system keyboard shortcut runs `omega13 --toggle`, which sends SIGUSR1 to the process

## Development Commands

### Environment Setup

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .
```

### Running the Application

```bash
# Standard run
omega13

# With debug logging
omega13 --log-level DEBUG

# Toggle recording from external process (for hotkey testing)
omega13 --toggle
```

### Docker Backend (Transcription Server)

```bash
# Start transcription server
docker compose up -d

# View logs
docker logs -f whisper-server

# Check health
curl http://localhost:8080

# Stop server
docker compose down
```

### Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_deduplication.py -v

# Run with coverage
python -m pytest --cov=omega13 tests/
```

### Changelog Generation

```bash
# Generate changelog using git-cliff
git cliff --tag v2.2.0 -o CHANGELOG.md

# Preview next version's changes
git cliff --unreleased
```

## Critical Implementation Details

### Ring Buffer Mechanics

The ring buffer in `AudioEngine._write_to_ring_buffer()` uses modulo wrapping:

- When `write_ptr + frames > ring_size`, it wraps: write part1 to end of buffer, part2 to start
- `buffer_filled` flag tracks whether buffer has wrapped at least once
- On record start, reconstruction logic differs based on `buffer_filled` state

### Thread Safety

- JACK `process()` callback: NO locks, NO allocations, NO blocking operations
- Use `queue.Queue(maxsize=200)` for passing audio from JACK thread to writer thread
- `TranscriptionService` tracks active threads for clean shutdown
- Shutdown deadline: 60 seconds total, with data integrity priority over speed

### Signal Detection

`has_audio_activity()` prevents empty recordings:

- Tracks `last_activity_time` when signal exceeds threshold (default: -70 dB)
- Checks 0.5s window before allowing recording
- Fallback: if ports are connected, allow recording even if signal is quiet

### PID-Based IPC

For Wayland compatibility (no global key interception):

1. App writes PID to `~/.local/share/omega13/omega13.pid` on startup
2. System keyboard shortcut runs `omega13 --toggle`
3. Toggle command reads PID, sends SIGUSR1 signal
4. Signal handler calls `action_toggle_record()` via `call_from_thread()`

### Transcription Retry Logic

`_transcribe_worker()` implements smart retries:

- 3 attempts with exponential backoff (2^retry_count seconds)
- During shutdown, reduced timeout (3s) to fail fast
- Checks `_shutdown_event` before expensive operations

## Project Structure Insights

```
src/omega13/
├── app.py              # Main Textual application, lifecycle management
├── audio.py            # JACK client, ring buffer, real-time processing
├── transcription.py    # HTTP client for whisper.cpp server
├── session.py          # Session/recording metadata management
├── config.py           # JSON config persistence
├── ui.py               # Custom Textual widgets (VUMeter, TranscriptionDisplay)
├── hotkeys.py          # Global keyboard listener (pynput)
├── clipboard.py        # Cross-platform clipboard integration
└── notifications.py    # Desktop notifications (D-Bus/notify-send)

tests/
├── test_deduplication.py     # Session transcription deduplication tests
└── test_incremental_save.py  # Incremental session save tests
```

## Common Pitfalls

1. **Don't block JACK callback:** Any operation in `AudioEngine.process()` that takes >1ms can cause xruns
2. **Thread cleanup on exit:** Transcription threads must be joined with timeout to prevent hang on quit
3. **Session temp files:** Unsaved sessions in `/tmp` are deleted on exit unless user saves them
4. **SIGUSR1 handling:** On non-Linux systems, `signal.SIGUSR1` may not exist - code has hasattr check
5. **Docker model path:** The whisper model must be mounted at `/app/models` and match `WHISPER_MODEL` env var
6. **SELinux contexts:** Docker volume mounts need `:Z` suffix on Fedora/RHEL for proper labeling

## Conventional Commit Types

This project uses conventional commits (enforced by git-cliff):

- `feat:` - New features
- `fix:` - Bug fixes
- `refactor:` - Code restructuring
- `perf:` - Performance improvements
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `chore:` - Build/config changes

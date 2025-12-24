# Omega-13 Development Context

## Project Overview

Omega-13 is a terminal-based (TUI) retroactive audio recorder and transcription tool for Linux. It continuously buffers audio in memory, allowing users to capture the previous 13 seconds (plus subsequent audio) when they trigger a recording.

**Key Features:**
*   **Retroactive Recording:** Captures audio from a 13-second in-memory ring buffer.
*   **Local Privacy:** Uses a local `whisper.cpp` server (via Docker) for transcription.
*   **TUI:** Built with `Textual` for a keyboard-centric interface.
*   **Audio Backend:** Uses `JACK`/`PipeWire` for professional audio routing.

## Architecture

The system consists of a Python TUI frontend and a Dockerized C++ backend for transcription.

### Core Components (`src/omega13/`)

*   **Audio Pipeline (`audio.py`):** Manages the JACK client and a NumPy-based ring buffer. The `process()` callback runs in the real-time audio thread and must be lock-free. Audio is reconstructed from the ring buffer + live queue and written to disk by a separate thread.
*   **TUI Application (`app.py`):** The main entry point using the `Textual` framework. Handles lifecycle events, signal handlers, and UI updates.
*   **Session Management (`session.py`):** Manages temporary sessions in `/tmp/omega13`. Handles saving sessions (audio + transcripts + metadata) to permanent storage.
*   **Transcription (`transcription.py`):** An async HTTP client that sends `.wav` files to the local `whisper-server`. Implements retry logic and cooperative shutdown.
*   **Configuration (`config.py`):** JSON-based configuration persistence (`~/.config/omega13/config.json`).
*   **Global Hotkeys (`hotkeys.py`):** Uses `pynput` for keyboard monitoring. On Wayland, it relies on a PID-based IPC mechanism where a system shortcut sends `SIGUSR1` to the application.
*   **UI (`ui.py`):** Custom Textual widgets like VU meters and transcription displays.

## Building and Running

### Prerequisites
*   Python 3.12+
*   Docker & NVIDIA GPU (for hardware-accelerated transcription)
*   JACK or PipeWire (with `pipewire-jack`)

### Environment Setup
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Backend Setup (Whisper Server)
```bash
docker compose up -d
# Logs: docker logs -f whisper-server
```

### Running the Application
```bash
# Standard run
omega13

# Debug mode
omega13 --log-level DEBUG

# Toggle recording (simulating global hotkey)
omega13 --toggle
```

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest --cov=omega13 tests/
```

## Development Conventions

*   **Thread Safety:** The JACK `process()` callback must be non-blocking. Use `queue.Queue` for inter-thread communication.
*   **Shutdown:** Transcription threads must be joined with a timeout. Unsaved sessions in `/tmp` are cleaned up on exit.
*   **Signal Handling:** `SIGUSR1` is used for external toggle commands (Wayland compatibility).
*   **Commits:** Follow Conventional Commits (`feat:`, `fix:`, `chore:`, etc.).

## Key Files Map

*   `src/omega13/app.py`: Main application logic and lifecycle.
*   `src/omega13/audio.py`: Audio buffering and JACK interface.
*   `src/omega13/transcription.py`: API client for the Whisper server.
*   `src/omega13/session.py`: File handling for recordings.
*   `tests/`: Test suite (pytest).
*   `docker-compose.yml`: Definition for the transcription backend service.

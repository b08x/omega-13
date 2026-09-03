# GEMINI.md - Omega-13 Project Context

## Project Overview
**Omega-13** is a high-performance Linux daemon application for retroactive audio recording and transcription. It captures the last 13 seconds of audio on demand, transcribes it (locally or via cloud), and routes the results to various destinations (clipboard, active window, Obsidian).

### Core Features
- **Retroactive Ring Buffer:** Continuously maintains 13 seconds of JACK/PipeWire audio in memory.
- **Intelligent Auto-Record:** RMS-based voice activity detection (VAD) for automatic capture.
- **Dual Transcription Backends:** Supports local `whisper-server` (HTTP) and Groq Cloud Whisper API.
- **Multi-Destination Output:** Clipboard copy, text injection (Wayland/X11), and Obsidian daily note integration.
- **Wayland-Native IPC:** D-Bus and SIGUSR1 support for global hotkeys and external triggers.

### Technology Stack
- **Language:** Python 3.12+
- **OSD Framework:** GTK4 Layer Shell (via `PyGObject` and `pycairo`) for Wayland-native overlays
- **Audio Engine:** JACK (via `JACK-Client`), NumPy for buffer management
- **Audio Processing:** FFmpeg and SoX for silence trimming and downsampling
- **IPC:** D-Bus (`dbus-next`), `pynput` (injection), `pyperclip` (clipboard)
- **Package Manager:** [`uv`](https://github.com/astral-sh/uv)

---

## Architecture
The project follows a modular, event-driven architecture designed to run as a headless background daemon with a GTK4 OSD.

- **`omega13.app`**: Main entry point handling CLI arguments.
- **`omega13.headless_service`**: The primary background daemon coordinating the `RecordingController`, `AudioEngine`, and `osd_manager`.
- **`omega13.ui.osd`**: Wayland-native GTK4 Layer Shell OSD rendering via Cairo.
- **`omega13.audio`**: The `AudioEngine` manages the JACK client, the 13s ring buffer, and real-time recording.
- **`omega13.recording_controller`**: Orchestrates state transitions (ARMED, RECORDING, IDLE) and handles VAD triggers.
- **`omega13.audio_processor`**: Pipeline for post-processing audio (trimming silence, resampling to 16kHz mono) using FFmpeg/SoX.
- **`omega13.transcription`**: Async service managing Local and Groq providers.
- **`omega13.session`**: Manages timestamped recording sessions and metadata.
- **`omega13.config`**: Persistent settings management via `~/.config/omega13/config.json`.

---

## Building and Running

### Prerequisites
- Linux with JACK or PipeWire (with `pipewire-jack` bridge).
- `gtk4-layer-shell`, `cairo`, and `gobject-introspection` libraries.
- Python 3.12+.
- `ffmpeg` and `sox` installed in system PATH.

### Commands
- **Local User Installation (XDG):** `./install.sh`
- **Install Development Dependencies:** `uv sync`
- **Run Application:** `omega13 --no-daemon`
- **External Trigger:** `omega13 --toggle`

---

## Development Conventions

### Coding Style
- **Type Hinting:** Strictly required for all new functions and class methods.
- **Logging:** Use the standard `logging` module. Real-time audio callbacks (JACK process) should only log at `DEBUG` level to avoid performance issues.
- **Concurrency:** Audio capture happens in the JACK process thread. File writing and transcription must be handled in separate threads (managed by `AudioEngine` and `TranscriptionService`) to avoid blocking the main event loop.

### Audio Processing Pipeline
When saving a recording:
1. Reconstruct linear audio from circular ring buffer.
2. Append new real-time audio from the JACK process.
3. Trim silence from both ends (`AudioProcessor.trim_silence`).
4. Downsample to 16kHz Mono for optimal Whisper inference (`AudioProcessor.downsample`).
5. Encode to MP4 (AAC) for final storage.

### Configuration
Configuration resides in `~/.config/omega13/config.json`. Always use `ConfigManager` to access or modify settings to ensure persistence and default merging.

### Testing
- Place new tests in the `tests/` directory.
- Mock the `AudioEngine` and `obsidian_cli` when testing UI logic to avoid hardware/dependency requirements.

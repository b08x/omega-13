# GEMINI.md - Omega-13 Project Context

## Project Overview
**Omega-13** is a high-performance Linux TUI application for retroactive audio recording and transcription. It captures the last 13 seconds of audio on demand, transcribes it (locally or via cloud), and routes the results to various destinations (clipboard, active window, Obsidian).

### Core Features
- **Retroactive Ring Buffer:** Continuously maintains 13 seconds of JACK/PipeWire audio in memory.
- **Intelligent Auto-Record:** RMS-based voice activity detection (VAD) for automatic capture.
- **Dual Transcription Backends:** Supports local `whisper-server` (HTTP) and Groq Cloud Whisper API.
- **Multi-Destination Output:** Clipboard copy, text injection (Wayland/X11), and Obsidian daily note integration.
- **Wayland-Native IPC:** D-Bus and SIGUSR1 support for global hotkeys and external triggers.

### Technology Stack
- **Language:** Python 3.12+
- **TUI Framework:** [Textual](https://textual.textualize.io/)
- **Audio Engine:** JACK (via `JACK-Client`), NumPy for buffer management
- **Audio Processing:** FFmpeg and SoX for silence trimming and downsampling
- **IPC:** D-Bus (`dbus-next`), `pynput` (injection), `pyperclip` (clipboard)
- **Package Manager:** [`uv`](https://github.com/astral-sh/uv)

---

## Architecture
The project follows a modular, event-driven architecture centered around the Textual `App` loop.

- **`omega13.app`**: Main entry point and TUI coordinator.
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
- Python 3.12+.
- `ffmpeg` and `sox` installed in system PATH.

### Commands
- **Install Dependencies:** `uv sync`
- **Run Application:** `uv run omega13`
- **Run Test Suite:** `uv run pytest`
- **Run TUI Tests:** `uv run pytest tests/test_tui_bindings.py -v`
- **External Trigger:** `kill -USR1 $(cat /tmp/omega13.pid)` or `uv run omega13 --toggle`

---

## Development Conventions

### Coding Style
- **Type Hinting:** Strictly required for all new functions and class methods.
- **Logging:** Use the standard `logging` module. Real-time audio callbacks (JACK process) should only log at `DEBUG` level to avoid performance issues.
- **Concurrency:** Audio capture happens in the JACK process thread. File writing and transcription must be handled in separate threads (managed by `AudioEngine` and `TranscriptionService`) to avoid blocking the TUI.

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
- Use `pytest-textual-snapshot` for TUI regression testing.
- Mock the `AudioEngine` and `obsidian_cli` when testing UI logic to avoid hardware/dependency requirements.

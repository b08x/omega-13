# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Omega-13 is a headless application with a GTK4 OSD for retroactive audio recording and transcription on Linux. It maintains a 13-second JACK audio ring buffer and saves/transcribes on demand. Requires a running JACK/PipeWire server and optionally a local `whisper-server` or Groq API key for transcription.

## Commands

```bash
# Install (requires uv)
uv sync

# Run
uv run omega13

# Run tests
uv run pytest

# Run a single test file
uv run pytest tests/test_headless_acceptance.py -v

# Run a single test by name
uv run pytest tests/test_headless_acceptance.py::test_toggle_bindings -v
```

Config is stored at `~/.config/omega13/config.json`. Sessions land in `/tmp/omega13/` until saved.

## Architecture

```
JACK Audio → AudioEngine (ring buffer) → SignalDetector (RMS)
                                               ↓
                                    RecordingController (state machine)
                                               ↓ RecordingEvent
                                         HeadlessOmega13
                                               ↓
                                    TranscriptionService (async threads)
                                               ↓
                              clipboard / text injection / Obsidian daily note
```

**Key architectural decisions:**

- **`RecordingController`** owns the recording state machine (`IDLE → ARMED → RECORDING_AUTO/MANUAL → STOPPING`). The app registers a single `set_event_callback` and reacts to typed `RecordingEvent` enums — it never polls state directly.

- **`AudioEngine`** (`src/omega13/audio.py`) runs a zero-copy JACK callback that writes into a `numpy` ring buffer (13s × channels). `start_recording()` drains the ring buffer into a WAV file via a background thread/queue. The scratchpad and buffer pool pre-allocate to avoid GC pressure in the realtime callback.

- **`TranscriptionService`** (`src/omega13/transcription.py`) wraps either `LocalTranscriptionProvider` (whisper-server HTTP) or `GroqTranscriptionProvider`. Each transcription runs in a daemon thread with exponential-backoff retry. A cooperative `_shutdown_event` allows clean teardown. After completion the service optionally copies to clipboard, injects text, or appends to an Obsidian daily note.

- **`Session` / `SessionManager`** (`src/omega13/session.py`) manages a temp directory under `/tmp/omega13/`. Each session has `recordings/` (WAV/MP4) and `transcriptions/` (Markdown) subdirs. `add_transcription()` performs word-level overlap deduplication across rolling windows to suppress repeated phrases from overlapping audio clips.

- **`ConfigManager`** (`src/omega13/config.py`) persists JSON to `~/.config/omega13/config.json`. It is the single source of truth for thresholds, paths, provider selection, and feature flags. Many modules accept it as an optional constructor argument.


- **IPC**: The app responds to `SIGUSR1` via a PID file so that external tools (global hotkeys, D-Bus, `dbus_service.py`) can trigger recording without keyboard focus.

## Hub Files (High Import Count)

Modifying these affects many dependents — check importers before changing signatures:

- `src/omega13/audio_processor.py` — imported by 5 files
- `src/omega13/transcription.py` — imported by 4 files
- `src/omega13/config.py` — imported by 3 files

## Testing

Tests use `pytest-asyncio` . See tests for the pattern.

Most tests in `tests/` are demo scripts or integration-style tests that require real hardware (JACK, whisper-server). Run `pytest tests/test_headless_acceptance.py` for the reliably unit-testable suite.

## Context7 MCP Documentation

- `/websites/ffmpeg_documentation` — FFmpeg audio/video
- `/ggml-org/whisper.cpp` — Whisper ASR C++ implementation
- `/websites/jackclient-python_readthedocs_io_en_0_5_5` — JACK Python bindings
- `/rbouqueau/sox` — SoX audio processing
- `/websites/help_obsidian_md_cli` — Obsidian CLI

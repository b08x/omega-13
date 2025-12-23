# Omega-13 Project Context

## Project Overview

**Omega-13** is a retroactive audio recording tool for Linux, designed to salvage spoken ideas by continuously buffering the last 13 seconds of audio. It integrates with JACK or PipeWire to capture audio from any system source.

**Key Features:**

* **Retroactive Recording:** Always captures the last 13 seconds + subsequent audio.
* **Session Management:** Recordings are saved to temporary sessions (`/tmp/omega13`) and can be persisted to a user-defined location.
* **TUI Interface:** Built with **Textual**, featuring real-time VU meters and reactive controls.
* **Audio Backend:** Uses `JACK-Client` for low-latency audio processing.
* **Transcription:** Optional AI transcription using a separate Whisper server container.

## Architecture & Design Patterns

### 1. Multi-Threading & Real-Time Safety

**CRITICAL:** The application operates on a strict two-thread model to prevent audio dropouts (xruns).

* **Real-time Thread (JACK Callback):**
  * Runs in `AudioEngine.process()`.
  * **MUST NEVER BLOCK.** No file I/O, no lock acquisition, no memory allocation.
  * Writes audio data to a pre-allocated NumPy `ring_buffer`.
  * Calculates peak levels for the UI.
* **Background Writer Thread:**
  * Spawned via `AudioEngine._file_writer()`.
  * Reads from a thread-safe `queue.Queue` (`record_queue`).
  * Handles all disk I/O (writing WAV files).
  * Runs with `daemon=False` to ensure data integrity on exit.

**Data Flow:**
`Hardware → JACK Callback → Ring Buffer → Queue → Writer Thread → Disk`

### 2. Rolling Buffer Implementation

* **Mechanism:** A circular NumPy array (`ring_buffer`) holds 13 seconds of audio.
* **Capture Logic:** When recording starts, the buffer is "unwrapped" (if full) or sliced (if partially full) and written to disk immediately, followed by the stream of new audio.
* **Note:** The codebase implements a **13-second** buffer (`BUFFER_DURATION = 13` in `audio.py`), despite the README mentioning 10 seconds.

### 3. Session Management

* **Lifecycle:**
    1. **Launch:** Creates a unique session directory in `/tmp/omega13/`.
    2. **Record:** Saves `001.wav`, `002.wav` sequentially to the temp dir.
    3. **Save:** User triggers a save; files are copied to a permanent location.
    4. **Incremental Save:** Subsequent saves to the same location merge new recordings.
    5. **Cleanup:** Old temp sessions (>7 days) are auto-deleted on startup.

## Development Workflow

### Prerequisites

* **Python:** 3.12+
* **Package Manager:** `uv` (recommended)
* **Audio System:** JACK Server or PipeWire with `pipewire-jack`

### Key Commands

| Action | Command |
| :--- | :--- |
| **Install Dependencies** | `uv sync` |
| **Run App** | `uv run python -m omega13` |
| **Dev Mode (Textual)** | `textual run --dev src/omega13/app.py` |
| **Run Tests** | See "Testing" section below |
| **Build Whisper** | `./build-whisper-image.sh` (in `whisper-server/`) |

### Testing

Tests are currently manual or script-based script files in `tests/`.

```bash
# Example: Run incremental save test
cd tests && python -c "import sys; sys.path.append('../src'); import test_incremental_save; test_incremental_save.test_incremental_save()"
```

## Codebase Structure

* **`src/omega13/app.py`**: Main entry point and Textual `App` class. Orchestrates UI and state.
* **`src/omega13/audio.py`**: `AudioEngine`. Handles JACK client, ring buffer, and file writing.
* **`src/omega13/session.py`**: `SessionManager` and `Session`. Handles storage logic and metadata.
* **`src/omega13/ui.py`**: Custom Textual widgets (`VUMeter`, `InputSelectionScreen`).
* **`src/omega13/config.py`**: Persists settings to `~/.config/omega13/config.json`.
* **`src/omega13/transcription.py`**: Async client for the Whisper transcription service.

## Coding Conventions

* **Style:** Follows standard Python practices.
* **Type Hints:** Mandatory for all function signatures (PEP 695 style preferred).
* **Textual Handlers:** Use `on_*` for events and `action_*` for keybindings.
* **Docstrings:** Required for classes and public methods.
* **Imports:** Absolute imports from project root preferred (e.g., `from omega13.audio import AudioEngine`).

## Common Troubleshooting

* **Silent Recordings:** Check JACK connections (`jack_lsp -c`). Ensure VU meters show activity *before* recording.
* **JACK Errors:** Ensure `pipewire-jack` is installed on PipeWire systems. Run with `pw-jack python -m omega13` if needed.
* **UI Layout:** The transcription pane takes up 60% width even if disabled; this is a known quirk.

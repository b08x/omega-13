# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Omega-13 is a retroactive audio recording application for Linux that maintains a continuous 13-second rolling buffer. Users can press a button at any moment to save what was just said, plus everything that follows. It's built with Python, JACK Audio, and the Textual TUI framework.

**Core Concept**: The "time machine" functionality—capturing audio that has already occurred—is implemented via a NumPy circular buffer that continuously overwrites itself in the JACK real-time callback thread.

## Development Commands

### Environment Setup

```bash
# Install dependencies using uv (recommended)
uv sync

# Alternative: traditional venv
python -m venv .venv && source .venv/bin/activate && pip install -e .
```

### Running the Application

```bash
# Standard execution
uv run python -m omega13

# Alternative if uv is not available
python -m omega13

# Development mode with Textual inspector
textual run --dev src/omega13/app.py

# With debugging on crash
python -i -m omega13
```

### Testing

```bash
# Run specific test
python tests/test_incremental_save.py

# Run test with source path
cd tests && python -c "import sys; sys.path.append('../src'); import test_incremental_save; test_incremental_save.test_incremental_save()"
```

### Whisper Transcription Server (Optional)

The AI transcription feature requires a separate containerized Whisper server:

```bash
# Build the CUDA-enabled image
./build-whisper-image.sh

# Deploy with Podman Compose
podman-compose up -d

# Check status
podman-compose ps

# View logs
podman-compose logs -f
```

**Note**: Transcription is optional. The app will detect if the service is unavailable and disable the feature gracefully (though the UI still reserves space for it—a known quirk).

## Critical Architecture Patterns

### 1. Multi-Threading Safety Model

**THE CARDINAL RULE**: The JACK process callback (`AudioEngine.process()`) must NEVER block or perform I/O. This is enforced through strict separation:

- **Real-time Thread (JACK callback)**: Writes to NumPy ring buffer, calculates peak meters. Lock-free, non-allocating.
- **Background File Writer Thread**: Spawned on recording start. Drains `record_queue` and performs disk I/O.
- **UI Thread (Textual)**: Polls `AudioEngine.peaks` at 20 FPS for meter updates.

```python
# CORRECT: In JACK callback
self.ring_buffer[self.write_ptr : self.write_ptr + frames] = data
self.record_queue.put(data.copy())  # Non-blocking queue

# INCORRECT: Would cause xruns (audio dropouts)
# soundfile.write(filename, data)  # NEVER do I/O in callback
# with some_lock: ...              # NEVER acquire locks
```

**Data Flow Pattern**:

```shell
Hardware → JACK Thread → ring_buffer → record_queue → Writer Thread → Disk
                      ↓
                   peaks/dbs → UI Thread (polling)
```

### 2. Session Management Lifecycle

Omega-13 uses a **temporary-then-permanent** storage pattern to protect recordings from accidental loss:

1. **Launch**: Creates unique session in `/tmp/omega13/session_<timestamp>_<uuid>/`
2. **Record**: Saves sequentially numbered WAVs (`001.wav`, `002.wav`, etc.) to temp directory
3. **Save (S key)**: User chooses permanent location; files are copied with metadata
4. **Exit**: Prompts to save if unsaved recordings exist; otherwise cleans temp files

**Critical Session Paths**:

- Temp recordings: `/tmp/omega13/<session_id>/recordings/001.wav`
- Session metadata: `/tmp/omega13/<session_id>/session.json`
- Permanent saves: User-chosen directory with `omega13_session_<timestamp>/` structure

**Auto-Cleanup**: On startup, sessions older than 7 days in `/tmp/omega13/` are automatically purged.

### 3. The Rolling Buffer Implementation

The core "retroactive capture" mechanism is a circular array with manual wraparound:

```python
# Key attributes in AudioEngine
self.ring_size = self.samplerate * 13  # 13 seconds (not 10 as README states)
self.ring_buffer = np.zeros((self.ring_size, channels), dtype='float32')
self.write_ptr = 0
self.buffer_filled = False  # True after first wraparound
```

**How Retroactive Capture Works**:

1. User presses SPACE → `start_recording()` called
2. Current buffer state is "frozen" and passed to writer thread
3. If `buffer_filled == True`: Use `np.roll()` to unwrap circular buffer into linear sequence
4. If `buffer_filled == False`: Only write `ring_buffer[:write_ptr]` (may contain zeros if < 13s runtime)
5. Writer thread dumps buffer to WAV, then continuously appends new data from `record_queue`

**Warning**: Recording before the 13-second mark will include pre-allocated zeros (silence) at the start of the file. This is by design and not prevented.

### 4. Configuration & State Management

Configuration is stored at `~/.config/omega13/config.json` with a versioned schema (currently v2):

```json
{
  "version": 2,
  "input_ports": ["system:capture_1", "system:capture_2"],
  "save_path": "/home/user/Recordings",
  "transcription": {
    "enabled": true,
    "auto_transcribe": true,
    "model_size": "large-v3-turbo",
    "copy_to_clipboard": false
  },
  "sessions": {
    "temp_root": "/tmp/omega13",
    "default_save_location": "/home/user/Recordings",
    "auto_cleanup_days": 7
  }
}
```

**Port Validation**: On startup, `ConfigManager` validates that saved `input_ports` still exist in the JACK graph. If hardware changed (different audio interface), the app auto-opens the input selection dialog.

### 5. JACK Client Lifecycle

The application requires a running JACK server. Initialization sequence:

1. `AudioEngine.__init__()` → `jack.Client("Omega13")`
2. Registers input ports (mono or stereo based on `num_channels`)
3. Sets process callback: `client.set_process_callback(self.process)`
4. `client.activate()` → JACK thread starts calling `process()`

**Graceful Shutdown**:

```python
# Idempotent shutdown pattern
if self.client.status:
    self.client.deactivate()
self.client.close()
```

### 6. Transcription Async Pattern

Transcription uses background threads to avoid blocking the UI:

1. Recording completes → `TranscriptionService.transcribe_async()` called
2. Spawns worker thread (daemon=False) that POSTs WAV file to Whisper server
3. Worker receives JSON response, writes to `.txt` file
4. Calls back to UI via `call_from_thread()` to update display
5. `Session.add_transcription()` performs overlap deduplication to prevent redundant text

**Overlap Deduplication**: The session manager uses suffix-prefix matching to merge overlapping transcription segments when recording in chunks. This prevents "the the cat cat sat sat" artifacts.

## Code Organization

```
src/omega13/
├── __main__.py          # Entry point
├── app.py               # Omega13App (main Textual orchestrator)
├── audio.py             # AudioEngine (JACK client + ring buffer)
├── config.py            # ConfigManager (persistent JSON settings)
├── session.py           # SessionManager + Session (temp/permanent storage)
├── transcription.py     # TranscriptionService (HTTP API client)
├── clipboard.py         # Clipboard integration utilities
└── ui.py                # UI widgets (VUMeter, TranscriptionDisplay, modal screens)
```

**Dependency Flow**:

```
Omega13App (app.py)
    ├─ AudioEngine (audio.py)
    ├─ SessionManager (session.py)
    ├─ ConfigManager (config.py)
    └─ TranscriptionService (transcription.py) [optional]
```

## Common Patterns When Modifying Code

### Adding a New Keybinding

1. Add to `Omega13App.BINDINGS` list
2. Implement `action_<name>()` method in `Omega13App` class
3. Update help text in UI if user-facing

### Modifying Ring Buffer Duration

Edit `BUFFER_DURATION` constant in `audio.py`:

```python
BUFFER_DURATION = 13  # Change to desired seconds
```

**Warning**: Increasing buffer duration increases memory usage proportionally (`samplerate × duration × channels × 4 bytes`).

### Adding Session Metadata Fields

1. Update `Session.__init__()` and `Session.to_dict()` in `session.py`
2. Modify `session.json` serialization in `Session.save_metadata()`
3. Update `Session.load_from_directory()` deserialization logic

### Working with the File Writer Thread

The background writer runs in `AudioEngine._file_writer()`. Key considerations:

- Must continuously drain `record_queue` to prevent memory buildup
- Uses `stop_event.wait(timeout)` to check for termination
- Writes initial buffer dump, then streams from queue
- Thread is **not** daemonic—will finish writing before app exits

## Known Structural Quirks

1. **Buffer Duration Mismatch**: README says 10 seconds, code implements 13 seconds (`BUFFER_DURATION = 13` in `audio.py`). The 13-second implementation is correct.

2. **Transcription UI Pane**: The UI allocates 60% width to transcription display even if `TranscriptionService` import fails or is disabled. This creates an empty pane when transcription is unavailable.

3. **Daemon Thread Inconsistency**: File writer uses `daemon=False` (changed from `True`), transcription threads also use `daemon=False`. This ensures data integrity but may delay shutdown if network is slow.

4. **Magic -100 dB Floor**: The audio engine uses `-100.0` as the floor for dB calculations when peak is zero. The UI explicitly checks for `-100` to display `-inf dB`, creating a coupling between audio processing and UI formatting.

5. **Auto-Cleanup Timing**: The 7-day cleanup runs on **every** app launch, not on a scheduled background task. For frequently-used systems, this is aggressive but harmless.

## JACK Audio Environment

### Required Setup

- **JACK Server**: Must be running before launching Omega-13
- **PipeWire Alternative**: PipeWire's JACK compatibility layer works (`pipewire-jack`)
- **Sample Rate**: Inherited from JACK server (typically 44.1kHz or 48kHz)
- **Port Connections**: Must manually connect Omega-13 input ports to audio sources via `qjackctl`, `qpwgraph`, or `Helvum`

### Verifying JACK Status

```bash
# Check if JACK is running
jack_lsp

# List all ports with connections
jack_lsp -c

# Find Omega-13 ports
jack_lsp | grep Omega13
```

## Testing Strategy

The project uses manual testing with discrete test files:

- `tests/test_incremental_save.py`: Validates session save/load and incremental updates
- `tests/test_deduplication.py`: Tests transcription overlap removal logic

**Running Tests**:

```bash
# Ensure src is in Python path
python -c "import sys; sys.path.append('./src'); from tests import test_incremental_save; test_incremental_save.test_incremental_save()"
```

## Debugging Tips

### Audio Dropouts (Xruns)

If you hear pops/clicks in recordings:

1. Check JACK buffer size: `jackd -d alsa -r 48000 -p 1024`
2. Monitor process callback performance (should be < 5ms)
3. Verify no blocking operations in `AudioEngine.process()`

### Silent Recordings

1. Check VU meters show signal **before** pressing SPACE
2. Verify JACK connections: `jack_lsp -c | grep Omega13`
3. Use `qpwgraph` (PipeWire) or `qjackctl` (JACK) to visually inspect connections

### Transcription Failures

1. Check Whisper server: `curl http://localhost:8080`
2. View container logs: `podman-compose logs -f`
3. Verify GPU access: `podman exec whisper-server nvidia-smi`

### Config Not Persisting

1. Check directory permissions: `ls -la ~/.config/omega13/`
2. Verify JSON validity: `python -m json.tool ~/.config/omega13/config.json`

## Performance Considerations

### Memory Usage

- Ring buffer: `samplerate × 13s × channels × 4 bytes` (≈2.5 MB for 48kHz stereo)
- NumPy arrays are pre-allocated, no runtime allocation in JACK callback
- Session temp files accumulate in `/tmp` until saved or cleanup occurs

### CPU Impact

- JACK callback: Peak detection via `np.max(np.abs(data))` on every block
- UI updates: 20 FPS meter polling (minimal overhead)
- Transcription: Offloaded to GPU-accelerated container (not in Python process)

## Type Hints and Code Style

- **Type Hints**: Used throughout for function signatures
- **Docstrings**: Present on all classes and public methods
- **Naming Conventions**:
  - `snake_case` for functions/variables
  - `PascalCase` for classes
  - `UPPER_SNAKE_CASE` for constants
- **Textual Patterns**:
  - `on_*` methods for event handlers
  - `action_*` methods for keybinding actions
  - CSS defined in class docstrings

## External Dependencies

- **Core**: `textual`, `JACK-Client`, `numpy`, `soundfile`
- **Optional**: `requests` (for transcription), `pyperclip` (for clipboard)
- **System**: `libjack` or `pipewire-jack`, `libsndfile`

## Modifying the UI Layout

The layout is defined in `Omega13App.CSS` and `compose()` method. Key containers:

- `#left-pane`: Audio controls (40% width)
- `#transcription-pane`: Transcription display (60% width)
- `#meters`: VU meter container with reactive level updates

**CSS Color Scheme**: Uses Textual's themed variables (`$success`, `$error`, `$warning`, `$accent`).

## Session Incremental Save Pattern

A recent architectural change allows **incremental saves**: If a session is saved once, subsequent saves to the same location merge new recordings without overwriting:

1. First save: Creates `omega13_session_<timestamp>/` with initial recordings
2. User continues recording after save
3. Second save to same location: Appends new recordings, updates `session.json`

This enables "work in progress" sessions where users can save checkpoints without losing the ability to add more recordings.

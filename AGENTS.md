# AGENTS.md

**Generated:** Wed Jan 07 2026 21:22:01  
**Commit:** 4674c1f  
**Branch:** development

## OVERVIEW

Omega-13: retroactive audio recorder with 13-second ring buffer + transcription. Python 3.12+, Textual TUI, JACK/PipeWire audio, local whisper.cpp inference via Docker.

## STRUCTURE

```
omega-13/
├── src/omega13/           # 14 modules, 3586 lines
│   ├── app.py             # Main entry, Textual app lifecycle
│   ├── audio.py           # JACK client, ring buffer (NumPy)
│   ├── recording_controller.py  # State machine (IDLE→ARMED→RECORDING→STOPPING)
│   ├── signal_detector.py # RMS-based voice activity detection
│   ├── transcription.py   # HTTP client for whisper.cpp
│   ├── session.py         # Recording metadata, deduplication
│   ├── ui.py              # Textual widgets (VUMeter, TranscriptionDisplay)
│   ├── hotkeys.py         # Global keyboard (pynput)
│   ├── injection.py       # ydotool text injection
│   ├── clipboard.py       # Cross-platform clipboard
│   └── notifications.py   # D-Bus notifications
├── tests/                 # 6 test files, pytest + textual-snapshot
├── bootstrap.sh           # Distro-agnostic installer
└── compose.yml            # whisper-server (CUDA-accelerated)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Ring buffer logic | `audio.py:_write_to_ring_buffer()` | Modulo wrapping, buffer_filled flag |
| Recording state | `recording_controller.py` | State machine with 5 states |
| Voice detection | `signal_detector.py` | RMS thresholds, sustained signal validation |
| Transcription retry | `transcription.py:_transcribe_worker()` | 3 attempts, exponential backoff |
| Deduplication | `session.py:add_transcription()` | Overlap detection for consecutive recordings |
| PID-based IPC | `app.py:main()` + hotkeys setup | SIGUSR1 signal handling for Wayland |
| Test patterns | `tests/test_*.py` | Standalone runners, heavy mocking |

## COMMANDS

```bash
# Setup (recommended)
./bootstrap.sh --build                     # Auto-install deps + build CUDA image
source .venv/bin/activate

# Setup (manual)
uv sync                                    # Or: python3.12 -m venv .venv && pip install -e .
docker compose up -d                       # Start whisper-server

# Run
omega13                                    # Console script
python -m omega13                          # Module execution
omega13 --toggle                           # IPC: send SIGUSR1 to running instance
omega13 --log-level DEBUG                  # Debug logging

# Test
python -m pytest tests/                    # All tests
python -m pytest tests/test_deduplication.py -v
python tests/test_deduplication.py         # Standalone runner (unique pattern)

# Build
git cliff --tag v2.3.0 -o CHANGELOG.md     # Conventional commits
CUDA_ARCHITECTURES="86" ./bootstrap.sh --build  # Custom GPU arch
```

## BUILD SYSTEM

- **Package manager:** `uv` (fallback: pip + venv)
- **Build backend:** `hatchling` (NOT setuptools)
- **Entry point:** `omega13 = "omega13.app:main"`
- **Installer:** `bootstrap.sh` supports dnf/apt/pacman/zypper
- **No CI/CD:** Local-first development workflow
- **Launcher:** `omega13.sh` activates venv + starts podman services

## CRITICAL IMPLEMENTATION DETAILS

### Ring Buffer Mechanics
`AudioEngine._write_to_ring_buffer()` uses modulo wrapping:
- When `write_ptr + frames > ring_size`: write part1 to buffer end, part2 to start
- `buffer_filled` flag: has buffer wrapped ≥1 time?
- Record start reconstruction differs based on `buffer_filled` state

### Thread Safety (NEVER VIOLATE)
- JACK `process()` callback: **NO locks, NO allocations, NO blocking** (>1ms = xruns)
- Audio → writer thread: `queue.Queue(maxsize=200)`
- `TranscriptionService`: tracks threads for clean shutdown (60s deadline)

### Signal Detection
`has_audio_activity()` prevents empty recordings:
- RMS threshold: -70 dB (default)
- Window: 0.5s sustained signal required
- Fallback: if JACK ports connected, allow recording

### PID-Based IPC (Wayland workaround)
1. App writes PID → `~/.local/share/omega13/omega13.pid`
2. System hotkey → `omega13 --toggle`
3. Reads PID → sends `SIGUSR1`
4. Signal handler → `call_from_thread(action_toggle_record)`

### Auto-Record State Machine
`RecordingController` states:
- IDLE → ARMED (ports connected)
- ARMED → RECORDING_AUTO (voice detected: RMS > -35 dB for 0.5s+)
- RECORDING_AUTO → STOPPING (silence: 10s default)
- Discards recordings with avg RMS < -50 dB

### Transcription Retry
`_transcribe_worker()` smart retries:
- 3 attempts, backoff: `2^retry_count` seconds
- Shutdown mode: 3s timeout (fail fast)
- Checks `_shutdown_event` before HTTP POST

## ANTI-PATTERNS (THIS PROJECT)

1. **Blocking JACK callback:** >1ms operations in `AudioEngine.process()` → xruns
2. **Missing thread joins:** Transcription threads MUST join with timeout on exit
3. **Forgetting temp cleanup:** Sessions in `/tmp` deleted unless user saves
4. **Platform assumptions:** `signal.SIGUSR1` missing on non-Linux (code has `hasattr` check)
5. **Docker model mismatch:** Whisper model path MUST match `WHISPER_MODEL` env var
6. **SELinux volumes:** Docker mounts need `:Z` suffix on Fedora/RHEL

## TESTING CONVENTIONS

- **Standalone runners:** Many tests have `if __name__ == "__main__"` (unusual for pytest)
- **Heavy mocking:** `unittest.mock` for all external deps (JACK, Docker, HTTP, subprocess)
- **Async TUI:** `pytest-asyncio` + `run_test()` context manager
- **Error-first:** Emphasize failure paths over happy paths
- **No shared fixtures:** Each test file self-contained

## CONVENTIONAL COMMITS

Enforced by git-cliff:
- `feat:` New features
- `fix:` Bug fixes  
- `refactor:` Restructuring
- `perf:` Performance
- `docs:` Documentation
- `test:` Tests
- `chore:` Build/config

# AGENTS.md — omega-13 Agent Guide

**omega-13** is a headless retroactive audio recorder and transcription daemon with a three-tier GTK4 OSD. A JACK callback continuously fills a 13-second ring buffer (`BUFFER_DURATION = 13`, src/omega13/audio.py:16); on demand the daemon drains those 13 seconds into a WAV file, trims and downsamples the audio, transcribes it through the configured provider — by default an in-process GGUF model over the transcribe-cpp bindings (src/omega13/config.py:38; construction at src/omega13/headless_service.py:517-530; class at src/omega13/transcription.py:193), or, when configured, a local whisper-server HTTP API (src/omega13/transcription.py:87) or Groq (src/omega13/transcription.py:130), and routes the text to the clipboard, a window titled *Whisp*, or a daily markdown file. Version 2.7.5 pins this guide (pyproject.toml:3; src/omega13/__init__.py:20), and Python >= 3.12 bounds the runtime (pyproject.toml:6). This file is the repository's single authoritative agent guide — CLAUDE.md and GEMINI.md are pointer stubs that duplicate nothing, and tests/AGENTS.md governs the test suite — and every load-bearing claim below carries its own verification condition: a path:line anchor, an exact constant, or an escape hatch.

## Identity and build

- Package: *omega13*, version 2.7.5 (pyproject.toml:3), mirrored by `__version__` at src/omega13/__init__.py:20.
- Entry point: console script `omega13 = "omega13.app:main"` (pyproject.toml:20-21); `python -m omega13` reaches the same `main` via __main__.py.
- Build: hatchling (pyproject.toml:23-25); the wheel packages `src/omega13` (pyproject.toml:27-28).
- Dev dependencies: pytest>=9.0.2 and pytest-asyncio>=1.3.0 (pyproject.toml:30-34); pytest addopts are empty (pyproject.toml:36-37).

## Commands

*Installation, development runs, and tests enter through three separate doors.* Installation executes `./install.sh`; the Justfile recipe named *install* does not install — it prints a redirect and exits 1 (Justfile:7-10), which sounds like a broken task runner, but is a deliberate stub. Development runs go through uv: `just dev` executes `uv run omega13 --no-daemon` (Justfile:21-22). Tests run through `pytest`, or through `just test`, which wraps pytest in `dbus-run-session` when that helper exists on PATH (Justfile:13-18), because the headless acceptance tests open real D-Bus connections (tests/test_headless_acceptance.py).

The remaining Justfile recipes (Justfile:1-85) are *toggle* (`uv run omega13 --toggle`, Justfile:25-26), *model* (interactive GGUF model downloads into ~/.local/share/omega13/models, Justfile:1 and the model recipe at Justfile:29), *rpm-lint*, *rpm-srpm*, and *rpm-build* (packaging/rpm/build.sh). No *check* recipe exists in the Justfile.

### CLI flags (src/omega13/app.py:14-38)

| Flag | Behavior | Anchor |
|---|---|---|
| `--toggle` | Calls `hotkeys.send_dbus_toggle()`, prints the returned recording state, exits 0/1 | app.py:41-51 |
| `--stop` | Sends SIGTERM to the PID in /tmp/omega13.pid; unlinks stale or invalid PID files | app.py:87-111 (SIGTERM at :104) |
| `--retry` | Calls `hotkeys.send_dbus_retry()`; reports whether a failed transcription was retried | app.py:53-67 |
| `--status` | Reads /tmp/omega13.pid and shells out to `systemctl --user status omega13` | app.py:69-85 |
| `--daemon`, `--no-daemon` | Parsed for backwards compatibility only; `args.daemon` is never read after parsing | app.py:26-28 |
| `--config` | Launches the interactive wizard `config_ui.run_config_ui` | app.py:115-122 |
| `--log-level` | Sets the root logger; default *INFO* | app.py:33-39 |

The two daemon flags sound like they control daemonization — they do not: a full read of app.py's 136 lines shows `args.daemon` assigned at parse time (app.py:31) and never referenced again. The PID file /tmp/omega13.pid appears in the --status branch (app.py:70), the --stop branch (app.py:88), and the main start path, which wraps `main_headless()` in `pid_file_context(Path("/tmp/omega13.pid"))` (app.py:128-133).

## Architecture

### Dependency flow (top-down)

```
app.py / __main__.py          ← entry points
  └─ HeadlessOmega13          ← headless/daemon mode, D-Bus service, Systemd primary
       ├─ OSDManager          ← 3-Tier OSD Architecture, spawns `osd_process.py:OSDProcess` via subprocess
       ├─ RecordingController ← state machine (IDLE→ARMED→RECORDING→STOPPING)
       ├─ RecordingEventHandler ← business logic, dispatches events to UI/OSD callbacks
       ├─ SessionManager      ← session lifecycle, recording metadata
       ├─ AudioEngine         ← JACK client, ring buffer, file writer
       ├─ SignalDetector      ← RMS/silence threshold detection
       ├─ ConfigManager       ← persistent JSON config (~/.config/omega13/config.json)
       └─ GlobalHotkeyListener ← pynput hotkey → D-Bus toggle
```

### Key components

| Module | Role | Key dependency |
|---|---|---|
| `config.py:ConfigManager` | Pure config getters/setters, no UI deps | None (leaf) |
| `audio.py:AudioEngine` | JACK client, ring buffer, file writing | ConfigManager, AudioProcessor, SignalDetector |
| `recording_controller.py:RecordingController` | State machine, auto-record orchestration | AudioEngine, SignalDetector, ConfigManager |
| `core/recording_events.py:RecordingEventHandler` | Event dispatch, register-and-transcribe | RecordingController, SessionManager, AudioEngine, ConfigManager |
| `session.py:SessionManager` | Session lifecycle, temp/save paths | None (leaf: constructed with a `temp_root` path only, src/omega13/session.py:256-266) |
| `signal_detector.py:SignalDetector` | RMS calculation, silence detection | None (pure math) |
| `audio_processor.py:AudioProcessor` | ffmpeg/sox pipeline, trim/downsample/encode | None (subprocess wrapper) |
| `transcription.py:TranscriptionService` | Configured provider: default GGUF (local), opt-in whisper-server / Groq | requests + clipboard/injection/file_output (transcription.py:12, :17-19); ConfigManager imported lazily in the file-write branch |
| `headless_service.py:HeadlessOmega13` | Daemon mode, Systemd, D-Bus, hotkey | RecordingController, AudioEngine, SessionManager, OSDManager |
| `ui/osd.py:OSDManager` | 3-Tier OSD Architecture (GNOME native, wlroots GTK4 layer shell via `subprocess`, transient notifications) | PyGObject, Gtk4LayerShell, cairo, D-Bus, `subprocess` |
| `osd_process.py:OSDProcess` | Separate GTK4 process to prevent GLib event loop blocking | PyGObject, Gtk4LayerShell |
| `gnome-extension/` | GNOME Shell Extension for native OSD | D-Bus (`org.gnome.Shell.Extensions.Omega13`) |
| `pidfile.py` | PID file management, stale detection | None |
| `signals.py` | Unix signal handling (shutdown, reload, status) | None |
| `notifications.py:DesktopNotifier` | Desktop notifications | None |
| `clipboard.py` | Copy to clipboard | pyperclip |
| `injection.py` | Type into *Whisp* window (requires the *Whisp* window to be focusable, not the active window) | ydotool |
| `file_output.py:file_output` | Appends transcription results to a daily markdown file | None (logging + pathlib) |
| `config_ui.py:ConfigWizard` | Interactive configuration wizard (`--config`) | ConfigManager, rich, jack |
| `hotkeys.py:GlobalHotkeyListener` | Global hotkey via pynput | D-Bus (for toggle) |
| `install.sh` / `uninstall.sh` | XDG user-local installer scripts | `gum` CLI toolkit |

### Recording state machine

The controller enumerates exactly five states — `IDLE`, `ARMED`, `RECORDING_MANUAL`, `RECORDING_AUTO`, `STOPPING` (recording_controller.py:19-25). The D-Bus acceptance tests observe the string values *idle* and *recording_manual* round-tripping through GetState during toggle start/stop (tests/test_headless_acceptance.py, `test_dbus_toggle_starts_recording` and `test_dbus_toggle_stops_recording`).

### OSD: three tiers, verified order

1. **GNOME Shell extension.** `OSDManager._get_dbus_proxy` introspects org.gnome.Shell at /org/gnome/Shell/Extensions/Omega13 and drives the interface org.gnome.Shell.Extensions.Omega13 (src/omega13/ui/osd.py:330-337); under GNOME the manager skips the layer-shell subprocess entirely (ui/osd.py:291-294).
2. **GTK4 Layer Shell subprocess.** On non-GNOME desktops with WAYLAND_DISPLAY or DISPLAY set, `OSDManager.start_subprocess` spawns `sys.executable -m omega13.osd_process` (ui/osd.py:282, 299-301); osd_process.py bootstraps through `omega13.ui.osd._lazy_init()` (src/omega13/osd_process.py:10-11) and runs its own GLib loop.
3. **Notification fallback.** `OSDManager.update` routes to `DesktopNotifier` (notify-send) whenever no subprocess is running (ui/osd.py:360, 379-388).

With neither WAYLAND_DISPLAY nor DISPLAY set, the OSD disables itself with a logged warning (ui/osd.py:286-289). The manager is a module singleton, `osd_manager = OSDManager()` (ui/osd.py:390).

### D-Bus interface

The daemon serves org.omega13.Recorder at /org/omega13/Recorder (headless_service.py:52-54), implemented by `HeadlessRecorderInterface` (headless_service.py:57): methods `ToggleRecording()->b`, `RetryTranscription()->b`, `RetryFailedTranscriptions()->i`, `GetFailedTranscriptionCount()->i`, `SetAutoRecordEnabled(b)`, `SetAutoRecordThreshold(d)`, `SetOSDEnabled(b)`, `GetState()->s`, `GetHealth()->a{sv}`; signals `RecordingToggled(b)`, `OSDStateChanged(ssi)`, `HealthStatus(a{sv})`. The acceptance suite drives ToggleRecording, GetState, and GetHealth over a live dbus-next bus (tests/test_headless_acceptance.py), and the OSD test asserts OSDStateChanged's three-argument shape — ("recording", "Recording", 0) — which matches the ssi signature (tests/test_osd_signal.py:11-12).

### Data flow

1. Audio is captured by `AudioEngine` (JACK callback → ring buffer, 13 s × channels).
2. `SignalDetector` evaluates RMS thresholds on each audio block.
3. `RecordingController` fires `RecordingEvent` (SIGNAL_DETECTED, AUTO_STARTED, etc.).
4. `RecordingEventHandler` receives events → registers the recording in the session → starts transcription.
5. `TranscriptionService` runs async → calls `_on_transcription_complete`.
6. Results are routed per config: clipboard (`clipboard.py`), injection into the *Whisp* window (`injection.py`), daily markdown file (`file_output.py`).

## Runtime paths and configuration

*Configuration and session storage each have exactly one authoritative location.* ConfigManager persists JSON to ~/.config/omega13/config.json and supplies the defaults: temporary sessions under $XDG_RUNTIME_DIR/omega13, falling back to /run/user/\<uid\>/omega13 (config.py:58); saved sessions under ~/Recordings with auto_cleanup_days = 7 (config.py:59-60); auto-record disabled by default with begin/end thresholds of -35.0 dB and a 10.0-second silence duration (config.py:62-67). SessionManager adds one construction fallback: built without a temp_root argument, it uses /tmp/omega13 (session.py:264) — a constructor-layer fallback, not the configured default. The two layers differ.

## Audio processing pipeline

*Post-recording audio passes through named AudioProcessor methods in a fixed order.* `AudioProcessor.preprocess_for_transcription` chains exactly two operations — trim_silence, then downsample (src/omega13/audio_processor.py, `AudioProcessor.preprocess_for_transcription`). trim_silence scans RMS windows with defaults of -50.0 dB and 0.5 seconds (audio_processor.py:128-129) and writes through soundfile; downsample invokes ffmpeg with aresample to 16,000 Hz (default `target_sample_rate`, audio_processor.py:130), a highpass at 80 Hz, a lowpass at 7,500 Hz, and pcm_s16le mono WAV output. Final storage encoding is MP3: `encode_mp3` (audio_processor.py:273) runs ffmpeg with acodec mp3 at a 128k default bitrate (audio_processor.py:131), aresample=16000, and pan=mono — an MP4/AAC storage step sounds plausible for a media pipeline, but no method in audio_processor.py's 402 lines produces one; encode_mp3 and convert_to_pcm are the only encoders. `AudioProcessor.__init__` raises RuntimeError("FFmpeg not found") when ffmpeg is missing from PATH (audio_processor.py:139-140); SoX is optional and only logged when present.

## Hub files (change signatures here with care)

*Three modules sit at the import center of the package.* ConfigManager (src/omega13/config.py) is imported at module level by audio.py:10, headless_service.py:21, core/recording_events.py:15, and config_ui.py:10, and inside a function body by `OSDManager.update` (ui/osd.py:365). AudioProcessor (src/omega13/audio_processor.py) is imported at module level by audio.py:11 and exercised directly by five test files (tests/test_format_conversion.py:7, tests/test_mp3_encoding.py:7, and — per their docstrings — test_metadata_extraction.py, test_baseline_measurements.py, test_subprocess_wrapper.py). TranscriptionService (src/omega13/transcription.py) is imported at module level inside a try/except by headless_service.py:41-45, under TYPE_CHECKING by core/recording_events.py:18-19, and lazily through `__getattr__` by __init__.py:11-13. These lists are the module-level import statements I read directly; function-body imports elsewhere in the package are not enumerated — Escape Hatch: `rg -n "audio_processor|transcription|ConfigManager" src/ tests/` yields the complete importer set before any signature change. *Escape hatch: `rg -n 'audio_processor' tests/` confirms which test files import AudioProcessor before any signature change.*

## Conventions

- **Headless core:** recording_controller.py, core/recording_events.py, session.py, and signal_detector.py carry zero UI imports — verified at recording_controller.py:8-14, core/recording_events.py:7-18, session.py:11-16, signal_detector.py:8-10; *Escape hatch: `rg -n 'omega13\.ui|pyperclip|\bgi\b' src/omega13/recording_controller.py src/omega13/core/recording_events.py src/omega13/session.py src/omega13/signal_detector.py` returns nothing.*
- **Lazy imports:** __init__.py defers heavy dependencies through `__getattr__` (src/omega13/__init__.py:6-17).
- **ConfigManager is a leaf:** it imports nothing from omega13; other modules import it, never the reverse.
- **Event-driven:** RecordingController fires events via callback; it never directly calls UI code.
- **Thread safety:** RecordingController guards state transitions with `threading.Lock` (recording_controller.py imports threading at :12); capture happens in the JACK process thread, and file writing and transcription stay off that thread (audio.py imports queue and threading at :2-3).
- **Coding style:** strict type hinting on all new functions and class methods; real-time audio callbacks log at DEBUG level only.
- **Injection is window-targeted, not active-window:** inject_text focuses a window titled *Whisp* first (injection.py:36) and returns False without typing anything when focusing fails (injection.py:158-161).
- **Naming:** snake_case modules, PascalCase classes, snake_case functions.

## Tests

*The suite spans 22 test files and 144 test functions — of which test_baseline_measurements.py contributes none; it is a measurement script pytest collects but finds no tests in — and the full catalog lives one directory down.* The 22 files are the tests/test_*.py set, and the 144 functions are the count of `def test_` definitions across them. Run `pytest` or `pytest -x`; a single test runs as `uv run pytest "tests/test_headless_acceptance.py::test_dbus_toggle_starts_recording" -v`. Dev dependencies are pytest>=9.0.2 and pytest-asyncio>=1.3.0 (pyproject.toml:30-34), and pytest addopts are empty (pyproject.toml:36-37). For per-file purposes, the mock strategy, invocation forms, and suite conventions, read tests/AGENTS.md.

## External documentation (Context7 MCP)

- `/websites/ffmpeg_documentation` — FFmpeg
- `/ggml-org/whisper.cpp` — Whisper ASR C++ implementation
- `/websites/jackclient-python_readthedocs_io_en_0_5_5` — JACK Python bindings
- `/rbouqueau/sox` — SoX audio processing
- `/websites/help_obsidian_md_cli` — Obsidian CLI

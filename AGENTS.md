# Agent Guide

## Project Overview

**omega-13** is a retroactive audio recorder and transcription daemon (v2.3.0) with optional Textual TUI. It records audio via JACK, detects silence/signal for auto-record, transcribes via local whisper-server or Groq, and outputs to clipboard/injection/Obsidian.

- Python >=3.12, hatchling build, `src/omega13/` layout
- Entry point: `omega13.app:main` (CLI: `omega13`)
- Run tests: `pytest` (dev deps: pytest, pytest-asyncio, pytest-textual-snapshot)

## Architecture

### Dependency Flow (top-down)

```
app.py / __main__.py          ← entry points
  ├─ Omega13App (TUI)         ← Textual app, wires everything together
  └─ HeadlessOmega13          ← headless/daemon mode, D-Bus service
       ├─ RecordingController ← state machine (IDLE→ARMED→RECORDING→STOPPING)
       ├─ RecordingEventHandler ← business logic, dispatches events to UI callbacks
       ├─ SessionManager      ← session lifecycle, recording metadata
       ├─ AudioEngine         ← JACK client, ring buffer, file writer
       ├─ SignalDetector      ← RMS/silence threshold detection
       ├─ ConfigManager       ← persistent JSON config (~/.config/omega13/config.json)
       └─ GlobalHotkeyListener ← pynput hotkey → D-Bus toggle
```

### Key Components

| Module | Role | Key dependency |
|---|---|---|
| `config.py:ConfigManager` | Pure config getters/setters, no UI deps | None (leaf) |
| `audio.py:AudioEngine` | JACK client, ring buffer, file writing | ConfigManager, AudioProcessor, SignalDetector |
| `recording_controller.py:RecordingController` | State machine, auto-record orchestration | AudioEngine, SignalDetector, ConfigManager |
| `core/recording_events.py:RecordingEventHandler` | Event dispatch, register-and-transcribe | RecordingController, SessionManager, AudioEngine, ConfigManager |
| `session.py:SessionManager` | Session lifecycle, temp/save paths | None (uses ConfigManager at init) |
| `signal_detector.py:SignalDetector` | RMS calculation, silence detection | None (pure math) |
| `audio_processor.py:AudioProcessor` | ffmpeg/sox pipeline, trim/downsample | None (subprocess wrapper) |
| `transcription.py:TranscriptionService` | Groq/local whisper backends | ConfigManager |
| `app.py:Omega13App` | Textual TUI, wires all components | All of the above |
| `headless_service.py:HeadlessOmega13` | Daemon mode, D-Bus, hotkey | RecordingController, AudioEngine, SessionManager |
| `dbus_service.py:DBusService` | D-Bus interface for TUI mode | Omega13App |
| `ui/screens.py` | TUI screens (dir selection, input, settings) | Textual |
| `ui/layout.py` | Main layout, status bars | Textual |
| `ui/widgets.py` | VU meter, transcription display, countdown | Textual |
| `pidfile.py` | PID file management, stale detection | None |
| `signals.py` | Unix signal handling (shutdown, reload, status) | None |
| `notifications.py:DesktopNotifier` | Desktop notifications | None |
| `clipboard.py` | Copy to clipboard | pyperclip |
| `injection.py` | Type into active window | ydotool |
| `obsidian_cli.py:ObsidianCLI` | Obsidian daily note integration | None |
| `hotkeys.py:GlobalHotkeyListener` | Global hotkey via pynput | D-Bus (for toggle) |

### Data Flow

1. Audio captured by `AudioEngine` (JACK callback → ring buffer)
2. `SignalDetector` evaluates RMS thresholds on each audio block
3. `RecordingController` fires `RecordingEvent` (SIGNAL_DETECTED, AUTO_STARTED, etc.)
4. `RecordingEventHandler` receives events → registers recording in session → starts transcription
5. `TranscriptionService` runs async → calls `_on_transcription_complete`
6. Results routed via config: clipboard, injection, Obsidian daily note

## Conventions

- **Textual-free core**: `recording_controller.py`, `core/recording_events.py`, `session.py`, `signal_detector.py` have zero Textual imports. Headless and TUI share them.
- **Lazy imports**: `__init__.py` uses `__getattr__` to defer heavy deps (JACK, Textual)
- **ConfigManager is a leaf**: it imports nothing from omega13. All other modules import it, never the reverse.
- **Event-driven**: `RecordingController` fires events via callback, never directly calls UI code
- **Thread safety**: `RecordingController` uses `threading.Lock` for state transitions
- **File naming**: snake_case modules, PascalCase classes, snake_case functions

## Tests

- `tests/` — pytest, ~20 test files
- Key test areas: daemon lifecycle, headless acceptance, PID file, transcription workflow, audio processing, TUI bindings, Obsidian integration
- Run: `pytest` or `pytest -x` (stop on first failure)
- Snapshot tests: `pytest-textual-snapshot` for TUI rendering

<trackboi>
## trackboi Skill

When trackboi MCP tools are available, agents can load `.agents/skills/trackboi/SKILL.md` for details, then call `orient_agent` to catch up before updating cards, tracks, boards, or handoff notes. If `.trackboi`, `.etc/.trackboi`, or `.etc/trackboi` files are present but MCP tools are not available, agents may read those files to catch up on local context. Do not manually create, update, or delete trackboi records in the filesystem; use MCP tools for mutations.
</trackboi>

# Hotkeys & D-Bus IPC

> 25 nodes · cohesion 0.10

## Key Concepts

- **app.py** (15 connections) — `src/omega13/app.py`
- **GlobalHotkeyListener** (8 connections) — `src/omega13/hotkeys.py`
- **hotkeys.py** (6 connections) — `src/omega13/hotkeys.py`
- **audio.py** (5 connections) — `src/omega13/audio.py`
- **main()** (4 connections) — `src/omega13/app.py`
- **send_dbus_toggle()** (4 connections) — `src/omega13/hotkeys.py`
- **signal_detector.py** (4 connections) — `src/omega13/signal_detector.py`
- **_dbus_get_state_async()** (3 connections) — `src/omega13/hotkeys.py`
- **_dbus_toggle_async()** (3 connections) — `src/omega13/hotkeys.py`
- **get_dbus_state()** (3 connections) — `src/omega13/hotkeys.py`
- **config.py** (3 connections) — `src/omega13/config.py`
- **__init__.py** (3 connections) — `src/omega13/__init__.py`
- **configure_logging()** (2 connections) — `src/omega13/app.py`
- **.__init__()** (2 connections) — `src/omega13/hotkeys.py`
- **._resolve_hotkey()** (2 connections) — `src/omega13/hotkeys.py`
- **.start()** (2 connections) — `src/omega13/hotkeys.py`
- **.stop()** (1 connections) — `src/omega13/hotkeys.py`
- **Call ToggleRecording() on the running Omega-13 D-Bus service.      Returns:** (1 connections) — `src/omega13/hotkeys.py`
- **Send ToggleRecording() to the running Omega-13 instance via D-Bus.      Synchron** (1 connections) — `src/omega13/hotkeys.py`
- **Get recording state from the running Omega-13 D-Bus service.      Returns:** (1 connections) — `src/omega13/hotkeys.py`
- **Listens for a global hotkey combination.          On X11: Uses pynput for direct** (1 connections) — `src/omega13/hotkeys.py`
- **Get current recording state from a running Omega-13 instance.      Synchronous w** (1 connections) — `src/omega13/hotkeys.py`
- **Start the global hotkey listener.         Returns True if successful, False othe** (1 connections) — `src/omega13/hotkeys.py`
- **Omega-13: Retroactive Audio Recorder A tribute to Galaxy Quest's time-rewind dev** (1 connections) — `src/omega13/__init__.py`
- **Signal detection module for audio activity and silence detection.  Provides RMS** (1 connections) — `src/omega13/signal_detector.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `src/omega13/__init__.py`
- `src/omega13/app.py`
- `src/omega13/audio.py`
- `src/omega13/config.py`
- `src/omega13/hotkeys.py`
- `src/omega13/signal_detector.py`

## Audit Trail

- EXTRACTED: 77 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
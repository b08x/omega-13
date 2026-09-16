# Plan

## Solution Approach
This plan addresses the enhancements by updating configuration defaults, introducing a robust CLI config menu via `just`, expanding the GNOME extension UI to include new toggles and a retry button, building a failure manifest in the session manager, and adding a real-time streaming mode option.

## Steps

### 1. Update Config Defaults and Temporary Paths
- **Files Touched**: `src/omega13/config.py`
- **Actions**:
  - Update `desktop_notifications` default to `False` (logic to still show critical errors will be in the notification handler).
  - Change default `sessions.temp_root` from `/tmp/omega13` to `/run/user/1000/omega13` (or derive dynamically via `$XDG_RUNTIME_DIR` with fallback).
  - Add config entries for `transcription.streaming_mode` (default `False`).
- **Verification**: Run `pytest tests/test_config.py` and verify defaults.

### 2. Failed Transcription Manifest & Retry Logic
- **Files Touched**: `src/omega13/session.py`, `src/omega13/core/recording_events.py`
- **Actions**:
  - Implement a `FailedTranscriptionManifest` class or methods in `SessionManager` that read/write a JSON file in `temp_root`.
  - On failed transcription, append to manifest.
  - Implement a retention policy keeping only the 10 most recent entries.
  - Expose a `retry_failed_transcriptions` D-Bus method in `headless_service.py` to process the manifest.
- **Verification**: Write tests in `tests/test_session.py` to simulate failed transcriptions and verify manifest pruning.

### 3. GNOME Extension Updates (UI & DBus)
- **Files Touched**: `gnome-extension/omega13@b08x.github.io/extension.js`, `gnome-extension/omega13@b08x.github.io/dbus.js`, `src/omega13/headless_service.py`
- **Actions**:
  - Add a toggle for OSD display and a toggle for Auto-Record.
  - Add a slider/input for Auto-Record threshold.
  - Add a 'Retry Failed Transcription' button that polls the D-Bus interface for the failure count (and changes color to red if > 0).
  - Update D-Bus interface to accept these UI events and update `ConfigManager` dynamically.
- **Verification**: Restart GNOME shell extension and trigger the D-Bus endpoints via `gdbus` or `busctl` to verify UI responsiveness.

### 4. Streaming Transcription Mode
- **Files Touched**: `src/omega13/audio.py`, `src/omega13/transcription.py`, `src/omega13/recording_controller.py`
- **Actions**:
  - When `streaming_mode` is enabled, modify the `RecordingController` to stream audio chunks continuously to `TranscriptionService`.
  - Implement real-time transcription stubs (for Nematron or similar) in `TranscriptionService` that handle chunked data.
- **Verification**: Add tests ensuring audio chunks route to the streaming provider instead of standard retroactive trimming/downsampling.

### 5. Notifications Handling
- **Files Touched**: `src/omega13/notifications.py`
- **Actions**:
  - Modify `DesktopNotifier` so that normal notifications are silenced if `desktop_notifications` is `False`.
  - Ensure `notify_error` always executes regardless of the toggle, maintaining critical alerts.
- **Verification**: Manually or programmatically trigger an error and ensure the notification is dispatched.

### 6. Robust CLI Config Menu
- **Files Touched**: `src/omega13/config_ui.py`, `src/omega13/app.py`
- **Actions**:
  - Overhaul the existing `omega13 --config` interactive wizard in `config_ui.py`.
  - Use rich (or external modern CLI tools like `gum` via subprocess) to provide a more robust, user-friendly interactive menu for updating all configuration options (including new streaming and auto-record settings).
- **Verification**: Run `omega13 --config` and confirm the UI is robust and correctly updates `~/.config/omega13/config.json`.

## Risks & Unknowns
- Real-time streaming might have different performance characteristics than the retroactive 13s buffer.
- GNOME extension development requires careful lifecycle management to avoid memory leaks when updating UI elements dynamically.
- D-Bus updates for config values must ensure thread safety since `ConfigManager` is accessed by background audio threads.

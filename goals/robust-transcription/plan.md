# Plan: Robust Transcription Fallback and System Tray

## Solution Approach
We will introduce a top-bar system tray menu to the GNOME extension that houses transcription-related actions, notably a "Retry failed transcription" button that triggers a D-Bus method on the daemon. We will also implement a fallback chain in the daemon's transcription service, prioritizing a new `transcribe.cpp`-based local model provider before falling back to the REST API. Finally, we'll wrap the `ydotool` injection logic with a robust error recovery mechanism to restart the service on failure, preventing stuck keys.

## Ordered Steps
1. **Environment and Installation Script Updates (`install.sh`)**
   - Update `install.sh` to handle `transcribe.cpp` dependencies and model setup.
   - Add GPU detection (e.g., checking for NVIDIA/CUDA compatibility).
   - Use `uv` to install `transcribe.cpp` with the appropriate hardware-accelerated flags if a compatible GPU is detected.
   - Use `gum` (already part of the install script context) to prompt the user with a multi-select menu for downloading models (e.g., tiny.en, base.en).
   - Prompt the user to select which model to use as the default local model.
   - Prompt for additional model parameters if necessary (like threads, temperature).
   - Save these selections to `config.json`.
   - *Verification*: Run `./install.sh` in a test environment to verify prompts, GPU detection, and config generation.

2. **Configuration Updates (`src/omega13/config.py`)**
   - Add `local_model_path`, `local_model_name`, and any additional parameters selected during installation to the default configuration schema.
   - Update `ConfigManager` to expose getters for these new keys.
   - *Verification*: Ensure tests pass and the config file generates correctly with the new defaults if missing.

3. **Ydotool Recovery Mechanism (`src/omega13/injection.py`)**
   - Modify `inject_text` to handle `subprocess.TimeoutExpired` and non-zero return codes during `ydotool type`.
   - Add a cleanup block that executes `systemctl --user restart ydotoold` if the injection fails, releasing any stuck keys.
   - *Verification*: Simulate a failure (e.g. by passing a short timeout or mocking the subprocess) and verify the restart command is called.

4. **Transcription Fallback Mechanism (`src/omega13/transcription.py`)**
   - Create a new `GgufTranscriptionProvider` class implementing the `TranscriptionProvider` interface, which imports and uses the `transcribe.cpp` python package.
   - Modify `TranscriptionService` (or `RecordingEventHandler` where it creates the provider) to accept a list of providers instead of a single provider.
   - Update the `_transcribe_worker` to try the `GgufTranscriptionProvider` first. If it raises a `TranscriptionError` or `Exception`, fall back to the API provider (Groq or whisper-server).
   - *Verification*: Write a test that mocks `GgufTranscriptionProvider` to fail and verifies that the API provider is subsequently called.

5. **Daemon D-Bus Interface (`src/omega13/headless_service.py` & `src/omega13/app.py`)**
   - Add a `RetryTranscription` D-Bus method to `HeadlessRecorderInterface`.
   - Add logic to track the last failed transcription path in `RecordingEventHandler` or `SessionManager` so it can be retried.
   - Add a `--retry` flag to the `omega13` CLI (in `app.py`) to easily invoke this method.
   - *Verification*: Run `omega13 --retry` and check D-Bus logs to ensure the signal is processed.

6. **GNOME Extension System Tray (`gnome-extension/omega13@b08x.github.io/extension.js`)**
   - Import `PanelMenu` and `PopupMenu` in `extension.js`.
   - Create an indicator in the GNOME panel status area with a 'Transcription' submenu.
   - Add a 'Retry failed transcription' item to this submenu that invokes the `org.omega13.Recorder.RetryTranscription` D-Bus method.
   - *Verification*: Enable the extension in a GNOME session (or lookin-glass) and visually verify the menu and its D-Bus invocation upon clicking.

## Risks & Open Questions
- **GNOME Shell Version Compatibility**: `PanelMenu` APIs can sometimes vary across GNOME versions. We should stick to the standard imports supported by GNOME 45/46 (`resource:///org/gnome/shell/ui/panelMenu.js`).
- **transcribe.cpp Dependencies**: The python package `transcribe.cpp` will be installed interactively via `install.sh`, but users pulling the repo without running the install script might hit missing dependency errors. We'll ensure the daemon handles `ImportError` gracefully if `transcribe.cpp` is not present, skipping the local fallback.
- **Ydotool Restart Delay**: Restarting the `ydotoold` user service takes a fraction of a second, which might interrupt a user actively typing, but it's the safest way to clear a stuck key state at the system level.

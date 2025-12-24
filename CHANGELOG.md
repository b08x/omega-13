## [unreleased]

### 🚀 Features

- Implement multi-channel input support and add mono/stereo selection to UI.
- Add decibel (dB) level calculation and display to audio meters.
- Add configurable recording save path with a directory selection UI
- Add `CLAUDE.md` and `README.md` documentation, and refactor `timemachine.py` with type hints, docstrings, and improved audio processing.
- Add transcription feature with a dedicated module, configuration options, and a new UI display.
- Improve GPU/CPU detection and user notifications for transcription, and refine UI reset behavior.
- Add containerization for Whisper transcription server with build and deployment documentation.
- Add CUDA-enabled whisper-server with build scripts, Podman compose configurations, and comprehensive documentation.
- Implement session-based recording workflow with temporary storage and user-controlled saving, adding related documentation and refactor planning files.
- Implement graceful shutdown, structured logging, and robust resource cleanup, removing refactoring plan files.
- Introduce clipboard copy functionality with UI toggle, configuration, and extensive documentation.
- Restructure app layout to centralize transcription controls and update default session samplerate.
- Implement incremental session saving by updating existing save locations, allowing directory merging, and adding a dedicated test.
- Define advanced agent follow-up and context management protocols, update bootstrap and gitignore, and remove whisper build script.
- Add hotkey and notification functionality, introducing `pynput` and related dependencies.
- Add Claude local settings for `WebSearch` and `Bash` permissions, and dynamically update the help text with the configured global hotkey.
- Add automatic startup for podman socket and whisper-server.
- Introduce transcription server URL configuration, enhance logging, update transcription notifications, and remove various documentation files.
- Add automatic session syncing, implement transcription request retries, and introduce pre-recording audio activity detection.

### 🐛 Bug Fixes

- Increase audio buffer duration
- Resolve application hang on exit with cooperative shutdown

### 💼 Other

- Add project configuration files and update README with PipeWire support, Whisper server setup, and `uv` installation instructions.

### 🚜 Refactor

- Switch transcription to use a `whisper-server` HTTP API, adding debug scripts and documentation.
- Reorganize project into a standard Python package structure with dedicated modules for audio, UI, transcription, and deployment.
- Rename `timemachine` package to `omega13`, generate dependency lock, and update project configuration, tests, and documentation.
- Remove X11 keysym resolution and raw key listener for hotkeys.

### 📚 Documentation

- Introduce comprehensive refactoring plan for session management, add related state and summary files, and update the README.
- Improve README clarity and conciseness with minor wording adjustments and a new link.
- Add AI context files and launch script

### 🎨 Styling

- Increase input selection dialog height and adjust mode selection button layout.

### ⚙️ Miscellaneous Tasks

- Add `__pycache__` and `.venv` to `.gitignore`
- Add build params configuration for whisper-server.

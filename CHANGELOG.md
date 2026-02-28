## [2.4.0] - 2026-02-28

### 🚀 Features

- Add TUI key bindings for toggling app features, introduce new tests, and update project dependencies.
- Add UI and configuration for transcription server inference path.
- Refine signal detection with noise immunity and sustained signal logic, and improve signal metrics data flow.
- Embed large-v3-turbo-q5_0 model and quantize binary into container, update model path configuration, and ignore pytest cache.
- Enhance installation with automated bootstrap script, update documentation, and bump version to 2.3.0 with new features and fixes.
- Switch transcription output to markdown
- *(transcription)* Add Groq API support as a transcription provider
- *(audio)* Switch default recording format to WAV and enhance downsampling
- *(audio)* Add CLI binary availability validation utilities
- *(audio)* Add subprocess wrapper foundation for CLI tools
- *(audio)* Implement ffprobe-based metadata extraction
- *(audio)* Implement audio resampling with ffmpeg CLI
- *(audio)* Implement PCM format conversion with ffmpeg CLI

### 🐛 Bug Fixes

- Increase signal sustain duration from 0.5s to 1.25s.

### 🚜 Refactor

- Reorder mono/stereo button handlers in TranscriptionSettingsScreen.
- Implement real-time safety, D-Bus IPC, and MP3 processing pipeline
- Replace ffmpeg-python with subprocess in MP3 encoding
- Remove ffmpeg-python dependency
- *(audio)* Complete ffmpeg-python removal and optimize audio processing

### 📚 Documentation

- Consolidate agent documentation and remove obsolete files
- *(README)* Refactor project overview and architecture
- Consolidate agent documentation and add module-specific guides
- *(audio)* Update process_pipeline docstring for subprocess-based implementation

### 🎨 Styling

- *(ui)* Update TUI color scheme and styling
- *(ui)* Standardize button layouts and dialog sizes in modal screens

### 🧪 Testing

- Add comprehensive test audio files and baseline measurements

### ⚙️ Miscellaneous Tasks

- Updated changelog
- Relocate scripts and update project documentation with Context7 MCP
## [2.3.0] - 2025-12-26

### 🚀 Features

- *(app)* Implement new session command and confirmation workflow
- *(transcription)* Add health check for transcription server with UI feedback
- Add UI for session titling and incorporate the provided title into the saved session directory name.
- Add text injection via ydotool
- Add voice-activated auto-record with intelligent silence detection

### 🚜 Refactor

- Remove duplicate SessionManager import

### 📚 Documentation

- Document voice-activated auto-record feature and update roadmap.

### ⚡ Performance

- *(auto-record)* Add false positive prevention and optimize CPU usage
## [2.2.0] - 2025-12-24

### 🚀 Features

- Introduce clipboard copy functionality with UI toggle, configuration, and extensive documentation.
- Restructure app layout to centralize transcription controls and update default session samplerate.
- Implement incremental session saving by updating existing save locations, allowing directory merging, and adding a dedicated test.
- Define advanced agent follow-up and context management protocols, update bootstrap and gitignore, and remove whisper build script.
- Add hotkey and notification functionality, introducing `pynput` and related dependencies.
- Add Claude local settings for `WebSearch` and `Bash` permissions, and dynamically update the help text with the configured global hotkey.
- Add automatic startup for podman socket and whisper-server.
- Introduce transcription server URL configuration, enhance logging, update transcription notifications, and remove various documentation files.
- Add automatic session syncing, implement transcription request retries, and introduce pre-recording audio activity detection.
- Add `CHANGELOG.md` and `cliff.toml` for automated changelog generation.

### 🐛 Bug Fixes

- Resolve application hang on exit with cooperative shutdown

### 🚜 Refactor

- Remove X11 keysym resolution and raw key listener for hotkeys.

### 📚 Documentation

- Add AI context files and launch script
- Add new documentation files for AI agents, project overview, and update changelog.
## [2.1.0] - 2025-12-22

### 🚀 Features

- Implement graceful shutdown, structured logging, and robust resource cleanup, removing refactoring plan files.

### 🐛 Bug Fixes

- Increase audio buffer duration

### 💼 Other

- Add project configuration files and update README with PipeWire support, Whisper server setup, and `uv` installation instructions.

### 🚜 Refactor

- Rename `timemachine` package to `omega13`, generate dependency lock, and update project configuration, tests, and documentation.

### 📚 Documentation

- Improve README clarity and conciseness with minor wording adjustments and a new link.

### 🎨 Styling

- Increase input selection dialog height and adjust mode selection button layout.

### ⚙️ Miscellaneous Tasks

- Add build params configuration for whisper-server.
## [2.0.0] - 2025-12-22

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

### 🚜 Refactor

- Switch transcription to use a `whisper-server` HTTP API, adding debug scripts and documentation.
- Reorganize project into a standard Python package structure with dedicated modules for audio, UI, transcription, and deployment.

### 📚 Documentation

- Introduce comprehensive refactoring plan for session management, add related state and summary files, and update the README.

### ⚙️ Miscellaneous Tasks

- Add `__pycache__` and `.venv` to `.gitignore`

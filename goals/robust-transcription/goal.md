# Goal: Robust Transcription Fallback and System Tray

This goal refactors the Omega-13 GNOME extension to include a system tray menu with a "Retry failed transcription" option. It also implements a robust fallback chain that attempts local GGUF model transcription via `transcribe.cpp` before falling back to the REST API, alongside environment setup scripts to detect hardware and download models. Finally, it resolves a text injection bug by implementing a recovery mechanism that restarts `ydotoold` on failure to prevent stuck keys.

## Specifications
- **Facts**: See [facts.md](facts.md) for the shared understanding of the requirements.
- **Execution Plan**: See [plan.md](plan.md) for the step-by-step implementation guide.

## Done Condition
- The `install.sh` script detects GPUs and interactively downloads `transcribe.cpp` models.
- The `ydotool` injection logic gracefully restarts the service upon failure.
- The daemon successfully falls back from the local `transcribe.cpp` model to the API model when necessary.
- The GNOME extension displays a system tray menu with a functioning "Retry failed transcription" button that triggers the retry via D-Bus.

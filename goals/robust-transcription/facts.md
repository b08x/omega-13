# Facts

- The GNOME extension system tray menu will include a 'Transcription' submenu to house future transcription-related items.
- A 'Retry failed transcription' option will be added under the 'Transcription' submenu.
- The transcription service will first attempt to transcribe using a local GGUF model via the transcribe.cpp Python library.
- If the local GGUF model transcription fails, the system will automatically fall back to using the REST API transcription.
- The config.json schema will be updated to include 'local_model_path', 'local_model_name', and related settings, with sensible defaults.
- The ydotool injection logic will be wrapped with a robust timeout and a recovery mechanism (e.g., explicitly restarting the ydotoold service or sending key-up events) to prevent stuck keys when an injection fails or is interrupted.

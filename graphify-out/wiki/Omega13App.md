# Omega13App

> God node · 68 connections · `src/omega13/app.py`

## Connections by Relation

### calls
- [[main()]] `EXTRACTED`
- [[test_app_mutual_exclusivity()]] `INFERRED`
- [[test_recording_to_transcription_workflow()]] `INFERRED`
- [[test_toggle_bindings()]] `INFERRED`

### contains
- [[app.py]] `EXTRACTED`

### inherits
- [[App]] `EXTRACTED`

### method
- [[.on_mount()]] `EXTRACTED`
- [[._start_transcription()]] `EXTRACTED`
- [[.compose()]] `EXTRACTED`
- [[._update_session_status()]] `EXTRACTED`
- [[._register_and_transcribe_recording()]] `EXTRACTED`
- [[._update_meter_visibility()]] `EXTRACTED`
- [[._load_and_connect_saved_inputs()]] `EXTRACTED`
- [[._handle_recording_event()]] `EXTRACTED`
- [[.action_toggle_record()]] `EXTRACTED`
- [[.action_manual_transcribe()]] `EXTRACTED`
- [[.action_open_settings()]] `EXTRACTED`
- [[.action_save_session()]] `EXTRACTED`
- [[.action_new_session()]] `EXTRACTED`
- [[._start_new_session()]] `EXTRACTED`
- [[._register_signal_handlers()]] `EXTRACTED`
- [[.on_unmount()]] `EXTRACTED`
- [[.update_meters()]] `EXTRACTED`
- [[.update_slow_info()]] `EXTRACTED`
- [[.check_auto_triggers()]] `EXTRACTED`
- [[._update_connection_status()]] `EXTRACTED`

### uses
- [[ConfigManager]] `INFERRED`
- [[AudioEngine]] `INFERRED`
- [[RecordingController]] `INFERRED`
- [[TranscriptionService]] `INFERRED`
- [[TranscriptionDisplay]] `INFERRED`
- [[LocalTranscriptionProvider]] `INFERRED`
- [[SessionManager]] `INFERRED`
- [[SignalDetector]] `INFERRED`
- [[InputSelectionScreen]] `INFERRED`
- [[TranscriptionSettingsScreen]] `INFERRED`
- [[GroqTranscriptionProvider]] `INFERRED`
- [[VUMeter]] `INFERRED`
- [[DirectorySelectionScreen]] `INFERRED`
- [[SilenceCountdown]] `INFERRED`
- [[DBusService]] `INFERRED`
- [[SessionTitleScreen]] `INFERRED`
- [[GlobalHotkeyListener]] `INFERRED`
- [[RecorderInterface]] `INFERRED`
- [[DesktopNotifier]] `INFERRED`
- [[RecordingState]] `INFERRED`

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
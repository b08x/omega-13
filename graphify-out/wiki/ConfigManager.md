# ConfigManager

> God node · 51 connections · `src/omega13/config.py`

## Connections by Relation

### calls
- [[.on_mount()]] `EXTRACTED`
- [[.test_baseline_process_callback_allocations()]] `INFERRED`
- [[.test_ring_buffer_write_allocations()]] `INFERRED`
- [[.test_signal_detection_allocations()]] `INFERRED`
- [[test_auto_transcribe_config_persistence()]] `INFERRED`
- [[test_config_persistence()]] `INFERRED`

### contains
- [[config.py]] `EXTRACTED`

### method
- [[.save_config()]] `EXTRACTED`
- [[._load_config()]] `EXTRACTED`
- [[.set_auto_transcribe()]] `EXTRACTED`
- [[.set_transcription_provider()]] `EXTRACTED`
- [[.set_transcription_server_url()]] `EXTRACTED`
- [[.set_transcription_inference_path()]] `EXTRACTED`
- [[.set_copy_to_clipboard()]] `EXTRACTED`
- [[.set_inject_to_active_window()]] `EXTRACTED`
- [[.set_write_to_daily_note()]] `EXTRACTED`
- [[.set_auto_record_enabled()]] `EXTRACTED`
- [[.__init__()]] `EXTRACTED`
- [[.get_input_ports()]] `EXTRACTED`
- [[.set_input_ports()]] `EXTRACTED`
- [[.set_save_path()]] `EXTRACTED`
- [[.get_global_hotkey()]] `EXTRACTED`
- [[.get_desktop_notifications_enabled()]] `EXTRACTED`
- [[.validate_ports_exist()]] `EXTRACTED`
- [[.get_transcription_provider()]] `EXTRACTED`
- [[.get_groq_api_key()]] `EXTRACTED`
- [[.set_groq_model()]] `EXTRACTED`

### rationale_for
- [[Manages persistent configuration for Omega-13.]] `EXTRACTED`

### uses
- [[Omega13App]] `INFERRED`
- [[AudioEngine]] `INFERRED`
- [[AllocationTracker]] `INFERRED`
- [[TestJACKCallbackAllocations]] `INFERRED`
- [[TestAllocationTracking]] `INFERRED`

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
# AudioEngine

> God node · 27 connections · `src/omega13/audio.py`

## Connections by Relation

### calls
- [[.on_mount()]] `EXTRACTED`
- [[.test_baseline_process_callback_allocations()]] `INFERRED`
- [[.test_ring_buffer_write_allocations()]] `INFERRED`
- [[.test_signal_detection_allocations()]] `INFERRED`

### contains
- [[audio.py]] `EXTRACTED`

### method
- [[.has_audio_activity()]] `EXTRACTED`
- [[.start_recording()]] `EXTRACTED`
- [[._file_writer()]] `EXTRACTED`
- [[.__init__()]] `EXTRACTED`
- [[.start()]] `EXTRACTED`
- [[.stop()]] `EXTRACTED`
- [[._write_to_ring_buffer()]] `EXTRACTED`
- [[.process()]] `EXTRACTED`
- [[.get_peak_meters()]] `EXTRACTED`
- [[.stop_recording()]] `EXTRACTED`
- [[.get_current_connections()]] `EXTRACTED`
- [[.get_available_output_ports()]] `EXTRACTED`
- [[.disconnect_inputs()]] `EXTRACTED`
- [[.connect_inputs()]] `EXTRACTED`

### rationale_for
- [[Handles JACK client, ring buffer, and file writing logic.]] `EXTRACTED`

### uses
- [[Omega13App]] `INFERRED`
- [[ConfigManager]] `INFERRED`
- [[AudioProcessor]] `INFERRED`
- [[SignalDetector]] `INFERRED`
- [[AllocationTracker]] `INFERRED`
- [[TestJACKCallbackAllocations]] `INFERRED`
- [[TestAllocationTracking]] `INFERRED`

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
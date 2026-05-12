# Recording State Machine

> 34 nodes · cohesion 0.10

## Key Concepts

- **RecordingController** (20 connections) — `src/omega13/recording_controller.py`
- **.get_state()** (9 connections) — `src/omega13/recording_controller.py`
- **._stop_recording_internal()** (8 connections) — `src/omega13/recording_controller.py`
- **._transition_state()** (7 connections) — `src/omega13/recording_controller.py`
- **._fire_event()** (6 connections) — `src/omega13/recording_controller.py`
- **.check_auto_triggers()** (5 connections) — `src/omega13/recording_controller.py`
- **.disable_auto_record()** (5 connections) — `src/omega13/recording_controller.py`
- **.get_status_info()** (5 connections) — `src/omega13/recording_controller.py`
- **.is_recording()** (5 connections) — `src/omega13/recording_controller.py`
- **.manual_start_recording()** (5 connections) — `src/omega13/recording_controller.py`
- **.enable_auto_record()** (4 connections) — `src/omega13/recording_controller.py`
- **.get_silence_countdown()** (4 connections) — `src/omega13/recording_controller.py`
- **.manual_stop_recording()** (4 connections) — `src/omega13/recording_controller.py`
- **._validate_recording_energy()** (3 connections) — `src/omega13/recording_controller.py`
- **.__init__()** (2 connections) — `src/omega13/recording_controller.py`
- **.is_auto_record_enabled()** (2 connections) — `src/omega13/recording_controller.py`
- **.set_event_callback()** (2 connections) — `src/omega13/recording_controller.py`
- **Fire an event to the registered callback.** (1 connections) — `src/omega13/recording_controller.py`
- **Thread-safe state transition with logging.** (1 connections) — `src/omega13/recording_controller.py`
- **Get current recording state (thread-safe).** (1 connections) — `src/omega13/recording_controller.py`
- **Check if currently recording (any mode).** (1 connections) — `src/omega13/recording_controller.py`
- **Check if auto-record mode is enabled.** (1 connections) — `src/omega13/recording_controller.py`
- **Enable auto-record mode and transition to ARMED state.          Returns:** (1 connections) — `src/omega13/recording_controller.py`
- **Disable auto-record mode and transition to IDLE.          If currently recording** (1 connections) — `src/omega13/recording_controller.py`
- **Start recording manually (user-initiated).          Args:             output_pat** (1 connections) — `src/omega13/recording_controller.py`
- *... and 9 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `src/omega13/recording_controller.py`

## Audit Trail

- EXTRACTED: 112 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
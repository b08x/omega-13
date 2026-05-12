# AudioEngine / JACK Capture

> 61 nodes · cohesion 0.05

## Key Concepts

- **AudioEngine** (27 connections) — `src/omega13/audio.py`
- **AllocationTracker** (11 connections) — `tests/test_realtime_safety.py`
- **gc_disabled_allocation_tracking()** (11 connections) — `tests/test_realtime_safety.py`
- **TestJACKCallbackAllocations** (9 connections) — `tests/test_realtime_safety.py`
- **.format_report()** (8 connections) — `tests/test_realtime_safety.py`
- **.get_allocation_count()** (8 connections) — `tests/test_realtime_safety.py`
- **.test_baseline_process_callback_allocations()** (8 connections) — `tests/test_realtime_safety.py`
- **test_realtime_safety.py** (7 connections) — `tests/test_realtime_safety.py`
- **.test_ring_buffer_write_allocations()** (7 connections) — `tests/test_realtime_safety.py`
- **.test_signal_detection_allocations()** (7 connections) — `tests/test_realtime_safety.py`
- **TestAllocationTracking** (6 connections) — `tests/test_realtime_safety.py`
- **.test_tracker_detects_allocations()** (6 connections) — `tests/test_realtime_safety.py`
- **test_framework_demonstration()** (5 connections) — `tests/test_realtime_safety.py`
- **.test_tracker_detects_no_allocations()** (5 connections) — `tests/test_realtime_safety.py`
- **.get_total_allocated()** (4 connections) — `tests/test_realtime_safety.py`
- **._file_writer()** (3 connections) — `src/omega13/audio.py`
- **.has_audio_activity()** (3 connections) — `src/omega13/audio.py`
- **.start_recording()** (3 connections) — `src/omega13/audio.py`
- **.start_tracking()** (3 connections) — `tests/test_realtime_safety.py`
- **.stop_tracking()** (3 connections) — `tests/test_realtime_safety.py`
- **create_mock_jack_client()** (3 connections) — `tests/test_realtime_safety.py`
- **.setup_method()** (3 connections) — `tests/test_realtime_safety.py`
- **.get_current_connections()** (2 connections) — `src/omega13/audio.py`
- **.get_peak_meters()** (2 connections) — `src/omega13/audio.py`
- **.process()** (2 connections) — `src/omega13/audio.py`
- *... and 36 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `src/omega13/audio.py`
- `tests/test_realtime_safety.py`

## Audit Trail

- EXTRACTED: 176 (89%)
- INFERRED: 22 (11%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
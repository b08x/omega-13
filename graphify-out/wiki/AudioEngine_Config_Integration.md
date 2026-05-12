# AudioEngine Config Integration

> 11 nodes · cohesion 0.20

## Key Concepts

- **AudioEngine** (12 connections) — `src/omega13/audio.py`
- **ConfigManager** (7 connections) — `src/omega13/config.py`
- **Test JACK Callback Allocations** (3 connections) — `tests/test_realtime_safety.py`
- **Buffer Pool Design** (1 connections) — `src/omega13/audio.py`
- **Config Persistence and Merging** (1 connections) — `src/omega13/config.py`
- **file_type Rationale Convention** (1 connections) — `src/omega13/config.py`
- **MP4 AAC Encoding Pipeline** (1 connections) — `src/omega13/audio.py`
- **Ring Buffer Mechanics** (1 connections) — `src/omega13/audio.py`
- **Test Auto Transcription Workflow** (1 connections) — `tests/test_auto_transcription_workflow.py`
- **Test Realtime Safety** (1 connections) — `tests/test_realtime_safety.py`
- **Zero-Allocation JACK Callback** (1 connections) — `src/omega13/audio.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `src/omega13/audio.py`
- `src/omega13/config.py`
- `tests/test_auto_transcription_workflow.py`
- `tests/test_realtime_safety.py`

## Audit Trail

- EXTRACTED: 25 (83%)
- INFERRED: 5 (17%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
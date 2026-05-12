# Transcription Service

> 20 nodes · cohesion 0.14

## Key Concepts

- **TranscriptionService** (18 connections) — `src/omega13/transcription.py`
- **LocalTranscriptionProvider** (16 connections) — `src/omega13/transcription.py`
- **test_health_check.py** (4 connections) — `tests/test_health_check.py`
- **test_custom_inference_path()** (3 connections) — `tests/test_custom_config.py`
- **test_health_check_connection_error()** (3 connections) — `tests/test_health_check.py`
- **test_health_check_generic_error()** (3 connections) — `tests/test_health_check.py`
- **test_health_check_success()** (3 connections) — `tests/test_health_check.py`
- **test_health_check_timeout()** (3 connections) — `tests/test_health_check.py`
- **.check_health()** (2 connections) — `src/omega13/transcription.py`
- **.shutdown()** (2 connections) — `src/omega13/transcription.py`
- **.transcribe_async()** (2 connections) — `src/omega13/transcription.py`
- **test_custom_config.py** (2 connections) — `tests/test_custom_config.py`
- **test_inference_path_slash_handling()** (2 connections) — `tests/test_custom_config.py`
- **.check_health()** (1 connections) — `src/omega13/transcription.py`
- **.__init__()** (1 connections) — `src/omega13/transcription.py`
- **Check if the transcription backend is reachable and responding.** (1 connections) — `src/omega13/transcription.py`
- **Start async transcription with proper cleanup support.          Args:** (1 connections) — `src/omega13/transcription.py`
- **Shutdown service and wait for active transcriptions.** (1 connections) — `src/omega13/transcription.py`
- **Local whisper-server backend.** (1 connections) — `src/omega13/transcription.py`
- **.cleanup()** (1 connections) — `src/omega13/transcription.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `src/omega13/transcription.py`
- `tests/test_custom_config.py`
- `tests/test_health_check.py`

## Audit Trail

- EXTRACTED: 43 (61%)
- INFERRED: 27 (39%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
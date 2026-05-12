# Cross-Module Patterns

> 19 nodes · cohesion 0.13

## Key Concepts

- **AudioProcessor** (11 connections) — `src/omega13/audio_processor.py`
- **run_command** (5 connections) — `src/omega13/audio_processor.py`
- **Test Subprocess Wrapper** (5 connections) — `tests/test_subprocess_wrapper.py`
- **AllocationTracker** (3 connections) — `tests/test_realtime_safety.py`
- **build_ffmpeg_command** (3 connections) — `src/omega13/audio_processor.py`
- **Command Execution Error** (2 connections) — `tests/test_subprocess_wrapper.py`
- **Command Timeout Error** (2 connections) — `tests/test_subprocess_wrapper.py`
- **Build SoX Command** (2 connections) — `tests/test_subprocess_wrapper.py`
- **Test Baseline Measurements** (2 connections) — `tests/test_baseline_measurements.py`
- **Test Format Conversion** (2 connections) — `tests/test_format_conversion.py`
- **Test Metadata Extraction** (2 connections) — `tests/test_metadata_extraction.py`
- **Test MP3 Encoding** (2 connections) — `tests/test_mp3_encoding.py`
- **Baseline Measurement Runner** (1 connections) — `tests/test_baseline_measurements.py`
- **Audio Processing Pipeline** (1 connections) — `src/omega13/audio_processor.py`
- **Downsample Operation** (1 connections) — `src/omega13/audio_processor.py`
- **FFmpeg Subprocess Pipeline** (1 connections) — `src/omega13/audio_processor.py`
- **gc Disabled Allocation Tracking** (1 connections) — `tests/test_realtime_safety.py`
- **Silence Trimming Operation** (1 connections) — `src/omega13/audio_processor.py`
- **Test Framework Demonstration** (1 connections) — `tests/test_realtime_safety.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `src/omega13/audio_processor.py`
- `tests/test_baseline_measurements.py`
- `tests/test_format_conversion.py`
- `tests/test_metadata_extraction.py`
- `tests/test_mp3_encoding.py`
- `tests/test_realtime_safety.py`
- `tests/test_subprocess_wrapper.py`

## Audit Trail

- EXTRACTED: 36 (75%)
- INFERRED: 12 (25%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
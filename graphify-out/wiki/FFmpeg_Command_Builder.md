# FFmpeg Command Builder

> 24 nodes · cohesion 0.11

## Key Concepts

- **build_ffmpeg_command()** (16 connections) — `src/omega13/audio_processor.py`
- **TestBuildFFmpegCommand** (14 connections) — `tests/test_subprocess_wrapper.py`
- **.test_build_ffmpeg_all_options()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_build_ffmpeg_basic()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_build_ffmpeg_empty_filters()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_build_ffmpeg_none_filters()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_build_ffmpeg_numeric_codec_args()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_build_ffmpeg_output_order()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_build_ffmpeg_with_codec_args()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_build_ffmpeg_with_extra_args()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_build_ffmpeg_with_filters()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_ffmpeg_command_execution_simulation()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **Build FFmpeg command with proper argument ordering.** (1 connections) — `src/omega13/audio_processor.py`
- **Test suite for build_ffmpeg_command() function.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test basic FFmpeg command building.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test FFmpeg command with audio filters.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test FFmpeg command with codec arguments.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test FFmpeg command with extra arguments.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test FFmpeg command with all options combined.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test that output file and -y flag are at the end.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test FFmpeg command with empty filters list.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test FFmpeg command with None filters.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test FFmpeg command with numeric codec arguments.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test that built FFmpeg command can be executed (with mock).** (1 connections) — `tests/test_subprocess_wrapper.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `src/omega13/audio_processor.py`
- `tests/test_subprocess_wrapper.py`

## Audit Trail

- EXTRACTED: 48 (67%)
- INFERRED: 24 (33%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
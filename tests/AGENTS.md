# tests/ — Test Suite Guide

This directory holds the omega-13 test suite: 22 pytest files, 144 test functions — of which test_baseline_measurements.py contributes none; it is a measurement script pytest collects but finds no tests in — plus a fixtures directory and this guide. The 22 files are the tests/test_*.py set, and the 144 functions are the count of `def test_` definitions across them. No conftest.py exists, so every fixture is defined inside the file that uses it (tests/ directory listing). Tooling comes from the dev group — pytest>=9.0.2 and pytest-asyncio>=1.3.0 (pyproject.toml:30-34) — and pytest addopts are empty (pyproject.toml:36-37).

## What the suite covers

*Each file targets one bounded area of the daemon.* The areas that fall out of the catalog below are: config persistence; AudioProcessor operations and their ffmpeg/ffprobe/sox wrappers; transcription providers (local whisper-server HTTP, Groq, health, custom inference path); session lifecycle (creation, overlap deduplication, incremental save, failed-transcription manifest); headless daemon behavior (D-Bus acceptance, OSD signaling, PID files, daemon lifecycle); output routing (file output, injection, clipboard); OSD; and real-time allocation safety.

| File (tests/) | Covers | Anchor |
|---|---|---|
| test_auto_transcription_workflow.py | ConfigManager persistence of transcription toggles against a temp config path | :11-20 |
| test_baseline_measurements.py | Measurement runner, not a test: times every AudioProcessor operation against the seven synthetic WAV fixtures; defines zero test functions | :1-14 |
| test_custom_config.py | LocalTranscriptionProvider endpoint = server_url + custom inference_path | :6-10 |
| test_daemon_lifecycle.py | Real subprocess lifecycle: PID acquire, double-launch refusal, SIGTERM release | :1-9, :24-26 |
| test_deduplication.py | Session.add_transcription word-overlap deduplication | :6-13 |
| test_error_handling.py | Placeholder (pass-only, asserts nothing) | :5-7 |
| test_file_output_integration.py | file_output.append_to_daily_file failure paths (empty content, no directory) | :5-12 |
| test_format_conversion.py | convert_to_pcm codec/channel/rate validation (unittest.TestCase) | :1, :10 |
| test_groq_provider.py | GroqTranscriptionProvider and the TranscriptionError/PermanentTranscriptionError classes it imports | :6-12 |
| test_headless_acceptance.py | Headless D-Bus acceptance: registration, toggle start/stop, GetHealth | :1-10, :43-44 |
| test_headless_session.py | SessionManager plus clipboard, injection, and file_output in headless mode | :1, :6-9 |
| test_health_check.py | TranscriptionService health check over a mocked requests.get | :8-14 |
| test_incremental_save.py | Session/SessionManager incremental save round-trip | :8 |
| test_injection.py | inject_text input validation; _focus_whisp_window and ydotool patching | :7-14 |
| test_metadata_extraction.py | ffprobe-based get_audio_info parity with the original probe | :1-6 |
| test_mp3_encoding.py | AudioProcessor.encode_mp3 (unittest.TestCase) | :1, :10 |
| test_osd_process.py | Placeholder (pass-only, asserts nothing) | :3-5 |
| test_osd_signal.py | HeadlessOmega13._emit_osd_state → OSDStateChanged("recording", "Recording", 0) | :5-12 |
| test_pidfile.py | is_stale / read_pid / acquire_pid_file / release_pid_file | :10-14 |
| test_realtime_safety.py | tracemalloc AllocationTracker for allocation-free JACK callbacks | :1-6, :22-26 |
| test_session.py | Failed-transcription manifest cap: 12 added, 10 retained | :8-14 |
| test_subprocess_wrapper.py | run_command / build_ffmpeg_command / build_sox_command errors, timeouts, logging | :1-6 |

## Mock and fixture strategy

*JACK never needs a live audio graph in these tests — the engine is patched at its seam.* The acceptance suite patches omega13.headless_service.AudioEngine and omega13.headless_service.ConfigManager before `HeadlessOmega13()` constructs anything (tests/test_headless_acceptance.py:43-44); the mocked engine reports samplerate 48000 and 2 channels, and `start_recording` returns a Path — so the D-Bus workflow tests need no JACK server, no microphone, and no audio file. HTTP is patched at requests.get (tests/test_health_check.py:14, tests/test_custom_config.py:12); window focus and binary discovery are patched at omega13.injection._focus_whisp_window and shutil.which (tests/test_injection.py:12-13); the D-Bus interface object is a plain MagicMock in the OSD signal test (tests/test_osd_signal.py:8-10).

Five files instead exercise the real binaries: any test that instantiates AudioProcessor requires ffmpeg on PATH, because `AudioProcessor.__init__` raises RuntimeError("FFmpeg not found") otherwise (src/omega13/audio_processor.py:139-140) — that binds test_format_conversion.py, test_mp3_encoding.py, test_metadata_extraction.py, test_baseline_measurements.py, and test_subprocess_wrapper.py to a machine with ffmpeg installed. Those five draw on seven synthetic WAV fixtures in tests/fixtures/audio/ — mono_44100_1s.wav, stereo_48000_2s.wav, mono_16000_3s.wav, mono_44100_with_silence.wav, stereo_48000_with_silence.wav, mono_44100_short.wav, mono_16000_long.wav — regenerated by tests/fixtures/generate_test_audio.py (docstring at :1-10). *Escape hatch: `git ls-files tests/fixtures/audio | xargs ls -l` confirms nothing large is committed.*

Among the files whose import blocks I read in full, only tests/test_realtime_safety.py imports omega13.audio directly (tests/test_realtime_safety.py:22); it tracks allocations with tracemalloc through its AllocationTracker class (:26) rather than playing audio. Whether any of its callbacks touch a live JACK graph is unverified from the first 59 of its 410 lines — Escape Hatch: read the AllocationTracker call sites in test_realtime_safety.py:59-410, or run pytest with the JACK server stopped and confirm that no connection error surfaces.

## How to run

- Full suite: `pytest`, or `pytest -x` to stop on the first failure.
- D-Bus-dependent tests need a session bus; `just test` wraps pytest in dbus-run-session when that helper exists (Justfile:13-18).
- Single file: `uv run pytest tests/test_headless_acceptance.py -v`.
- Single test: `uv run pytest "tests/test_headless_acceptance.py::test_dbus_toggle_starts_recording" -v` — the acceptance file also defines test_daemon_registers_without_tui, test_dbus_health_response, test_dbus_toggle_stops_recording, and test_full_headless_acceptance_workflow (tests/test_headless_acceptance.py, async tests in the file's latter half).
- The acceptance file documents its own invocation — `pytest -o addopts="" tests/test_headless_acceptance.py -v` (tests/test_headless_acceptance.py:9-10) — and keeps a standalone runner: `if __name__ == "__main__": pytest.main([__file__, "-v", "-s", "-o", "addopts="])` (tests/test_headless_acceptance.py:227-229).
- tests/test_daemon_lifecycle.py hardcodes this checkout's interpreter and source paths — VENV_PYTHON = "/home/b08x/WorkspaceV3/omega-13/.venv/bin/python" and PROJECT_SRC = "/home/b08x/WorkspaceV3/omega-13/src" (tests/test_daemon_lifecycle.py:24-26) — and spawns real helper processes over PID files, which binds the test to this machine's absolute paths — Escape Hatch: parameterize those two constants before running it from a differently located clone.

## Conventions observable in the files

- **Naming:** tests/test_*.py; plain `def test_*()` functions dominate, with unittest.TestCase classes in tests/test_format_conversion.py:10 and tests/test_mp3_encoding.py:10.
- **Async:** async tests carry @pytest.mark.asyncio (tests/test_osd_signal.py:5; tests/test_headless_acceptance.py).
- **Per-file fixtures:** e.g. temp_config_path (tests/test_auto_transcription_workflow.py:11-17) and mock_audio_engine / headless_daemon (tests/test_headless_acceptance.py:38-86); no shared conftest.py.
- **Error-first emphasis:** failure paths are asserted before happy paths — file_output.append_to_daily_file rejects empty content and missing directories (tests/test_file_output_integration.py:5-12); inject_text rejects empty text (tests/test_injection.py:7-10).
- **Caps are tested as behavior:** SessionManager keeps at most 10 failed transcriptions — 12 added, 10 retained (tests/test_session.py:8-14).
- **Two placeholders exist:** tests/test_error_handling.py:5-7 and tests/test_osd_process.py:3-5 define pass-only tests that assert nothing — treat them as slots to fill, not as coverage.

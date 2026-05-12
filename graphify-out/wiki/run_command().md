# run_command()

> God node · 24 connections · `src/omega13/audio_processor.py`

## Connections by Relation

### calls
- [[CommandExecutionError]] `EXTRACTED`
- [[CommandTimeoutError]] `EXTRACTED`
- [[.downsample()]] `EXTRACTED`
- [[.encode_mp3()]] `EXTRACTED`
- [[.get_audio_info()]] `EXTRACTED`
- [[.convert_to_pcm()]] `EXTRACTED`
- [[.test_run_command_success()]] `INFERRED`
- [[.test_run_command_with_description()]] `INFERRED`
- [[.test_run_command_failure_with_check()]] `INFERRED`
- [[.test_run_command_failure_without_check()]] `INFERRED`
- [[.test_run_command_timeout()]] `INFERRED`
- [[.test_run_command_invalid_command_type()]] `INFERRED`
- [[.test_run_command_empty_command()]] `INFERRED`
- [[.test_run_command_invalid_timeout()]] `INFERRED`
- [[.test_run_command_timeout_not_integer()]] `INFERRED`
- [[.test_run_command_stderr_capture()]] `INFERRED`
- [[.test_run_command_logging_output()]] `INFERRED`
- [[.test_run_command_with_special_characters()]] `INFERRED`
- [[.test_run_command_long_output_truncation()]] `INFERRED`
- [[.test_run_command_with_built_command()]] `INFERRED`

### contains
- [[audio_processor.py]] `EXTRACTED`

### rationale_for
- [[Execute subprocess command with timeout and error handling.]] `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
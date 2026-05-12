# Subprocess Test Suite

> 34 nodes · cohesion 0.08

## Key Concepts

- **run_command()** (24 connections) — `src/omega13/audio_processor.py`
- **TestRunCommand** (19 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_with_built_command()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_empty_command()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_failure_with_check()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_failure_without_check()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_invalid_command_type()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_invalid_timeout()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_logging_output()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_long_output_truncation()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_stderr_capture()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_success()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_timeout()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_timeout_not_integer()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_with_description()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_run_command_with_special_characters()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.setUp()** (2 connections) — `tests/test_subprocess_wrapper.py`
- **Execute subprocess command with timeout and error handling.** (1 connections) — `src/omega13/audio_processor.py`
- **Test command output is logged at debug level.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test command with special characters in arguments.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test long output is truncated in logs.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test suite for run_command() function.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test run_command with a built command.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Set up test fixtures.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test successful command execution.** (1 connections) — `tests/test_subprocess_wrapper.py`
- *... and 9 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `src/omega13/audio_processor.py`
- `tests/test_subprocess_wrapper.py`

## Audit Trail

- EXTRACTED: 71 (68%)
- INFERRED: 33 (32%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
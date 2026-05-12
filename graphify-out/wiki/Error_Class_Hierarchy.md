# Error Class Hierarchy

> 17 nodes · cohesion 0.16

## Key Concepts

- **CommandExecutionError** (15 connections) — `src/omega13/audio_processor.py`
- **AudioProcessorError** (10 connections) — `src/omega13/audio_processor.py`
- **CommandTimeoutError** (9 connections) — `src/omega13/audio_processor.py`
- **TestCommandIntegration** (8 connections) — `tests/test_subprocess_wrapper.py`
- **TestExceptionHierarchy** (8 connections) — `tests/test_subprocess_wrapper.py`
- **.test_exception_instantiation()** (4 connections) — `tests/test_subprocess_wrapper.py`
- **.test_sox_command_execution_simulation()** (3 connections) — `tests/test_subprocess_wrapper.py`
- **.test_command_execution_error_is_audio_processor_error()** (2 connections) — `tests/test_subprocess_wrapper.py`
- **.test_command_timeout_error_is_audio_processor_error()** (2 connections) — `tests/test_subprocess_wrapper.py`
- **Base exception for audio processing.** (1 connections) — `src/omega13/audio_processor.py`
- **Command execution failed.** (1 connections) — `src/omega13/audio_processor.py`
- **Test exception class hierarchy.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test CommandExecutionError inherits from AudioProcessorError.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test CommandTimeoutError inherits from AudioProcessorError.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test exception instantiation.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Integration tests for command building and execution.** (1 connections) — `tests/test_subprocess_wrapper.py`
- **Test that built SoX command can be executed (with mock).** (1 connections) — `tests/test_subprocess_wrapper.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `src/omega13/audio_processor.py`
- `tests/test_subprocess_wrapper.py`

## Audit Trail

- EXTRACTED: 39 (57%)
- INFERRED: 30 (43%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
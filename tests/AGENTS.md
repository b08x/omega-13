# tests/ MODULE

**Standalone runners + heavy mocking**

## STRUCTURE

```
tests/
├── test_deduplication.py    # Session overlap detection
├── test_signal_detector.py  # RMS thresholds, voice activity
├── test_recording_flow.py   # Full recording lifecycle
├── test_transcription.py    # HTTP retry logic, thread safety
└── test_audio.py           # Ring buffer mechanics
```

## WHERE TO LOOK

| Test Type | Location | Pattern |
|-----------|----------|---------|
| Standalone execution | All `test_*.py` | `if __name__ == "__main__": pytest.main([__file__, "-v"])` |
| Mock factories | Each test file | Heavy `unittest.mock` for JACK/Docker/HTTP |
| Thread safety | `test_transcription.py` | Worker thread join() validation |
| Ring buffer edge cases | `test_audio.py` | Modulo wrapping, buffer_filled scenarios |
| Error-first testing | All files | Exception paths over happy paths |

## UNIQUE CONVENTIONS

### Standalone Runners (Non-Standard)
Each test file runs independently via `python tests/test_file.py`:
- Enables direct debugging with pdb
- Alternative to pytest for development
- Unusual pattern for pytest-based projects

### Mock Strategy
**Everything external is mocked:**
- JACK audio client → `mock_jack_client`
- Docker transcription → `mock_transcription_service` 
- HTTP requests → `responses` library
- Subprocess calls → `mock.patch('subprocess.run')`

### Error-First Philosophy
Tests emphasize failure scenarios:
- Timeout conditions (transcription, shutdown)
- Empty recordings (below RMS threshold)
- Thread cleanup on exceptions
- Network failures and retries

## ANTI-PATTERNS (TESTING-SPECIFIC)

1. **Real JACK in tests:** Always mock audio subsystem
2. **Network calls:** Mock all HTTP to whisper.cpp 
3. **Shared state:** Each test file self-contained
4. **Missing thread cleanup:** Must test join() with timeout
5. **UI without pilot:** Always use `run_test()` for TUI interactions
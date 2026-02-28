# Learnings - ffmpeg-cli-replacement

## Task 3: Binary Availability Validation Utilities

### Patterns Discovered
- Used `shutil.which()` for binary detection (follows pattern from injection.py)
- Version checking via `subprocess.run([binary, "-version"], capture_output=True)`
- Clear error messages with platform-specific installation instructions

### Conventions
- Function naming: `check_<tool>_available()` returns bool
- Version functions: `get_<tool>_version()` returns Optional[str]
- Validation method: `_validate_cli_tools_availability()` replaces old `_validate_ffmpeg_availability()`

### Gotchas
- SoX version retrieval may need different flags (`-V` didn't work, need `--version` or `-h`)
- Error messages should include installation instructions for multiple platforms

### Successful Approaches
- Platform-specific error messages improve user experience
- Optional tool (sox) should log warning, not raise error
- Required tool (ffmpeg) should raise RuntimeError with clear message

## Task 4: Comprehensive Test Audio Files and Baseline Measurements

### Patterns Discovered

- **Synthetic test audio generation**: Use NumPy + soundfile to generate test audio programmatically
  - Avoids large binary files in git repository
  - Ensures reproducibility and consistency
  - Can generate various audio properties (channels, sample rates, durations)
  
- **Baseline measurement framework**: Dataclass-based metrics collection
  - `AudioMetrics`: Captures file properties (channels, sample_rate, duration, size_bytes)
  - `OperationMetrics`: Captures operation performance (input/output metrics, processing_time_ms, success)
  - Enables regression testing and performance tracking

- **Performance characteristics**:
  - `get_audio_info`: ~180-200ms (includes ffmpeg startup overhead)
  - `trim_silence`: 2-5ms (very fast, minimal processing)
  - `downsample`: 550-600ms per 1-2s audio (CPU-intensive resampling)
  - `encode_mp3`: ~370ms per 1s audio (encoding overhead)
  - `preprocess_for_transcription`: ~550ms per 1s audio (dominated by resampling)

- **File size reductions**:
  - `trim_silence`: ~12% reduction (removes silence)
  - `downsample` (44100→16000Hz): ~64% reduction
  - `downsample` (48000→16000Hz, stereo→mono): ~83% reduction
  - `encode_mp3` (128k): ~80% reduction

### Conventions

- Test audio files stored in `tests/fixtures/audio/` directory
- Baseline measurements saved to `.sisyphus/evidence/task-4-baseline-measurements.json`
- Expected outputs documented in `tests/EXPECTED_OUTPUTS.md`
- Test runner pattern: `BaselineMeasurementRunner` class with setup/teardown
- Measurement dataclasses use `asdict()` for JSON serialization

### Gotchas

- FFmpeg startup overhead (~180ms) dominates `get_audio_info` performance
- Resampling operations are CPU-intensive and scale linearly with audio duration
- MP3 encoding automatically resamples to 16000Hz (transcription-friendly)
- Silence detection uses RMS energy in sliding windows (not frame-based)
- Thread safety verified through RLock implementation (reentrant locks)

### Successful Approaches

- Generate test audio synthetically to avoid git bloat
- Use dataclasses for structured metrics collection
- Measure both processing time and file size changes
- Document expected outputs with concrete examples
- Test all operations with multiple audio configurations
- Save measurements to JSON for regression testing
- Verify 100% success rate before considering task complete

### Testing Recommendations

- Unit tests: Test each operation with all test audio files
- Integration tests: Test operation pipelines (e.g., downsample → trim_silence)
- Performance tests: Measure processing times for different audio durations
- Thread safety: Verify concurrent calls with multiple threads
- Error handling: Test invalid inputs and missing files
- Regression testing: Compare new measurements against baseline


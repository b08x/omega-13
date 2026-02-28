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


## Task 5: Subprocess Wrapper and Command Builder Utilities

### Patterns Discovered

- **Subprocess execution pattern**: Use `subprocess.run()` with argument lists (not shell strings) to prevent injection
  - Always use `capture_output=True, text=True` for output capture
  - Use `check=False` and handle errors manually for better control
  - Timeout parameter prevents hanging processes
  
- **Command building approach**: Separate builder functions for each CLI tool
  - FFmpeg: Input → Filters → Codec args → Extra args → Output
  - SoX: Input → Rate → Channels → Effects → Output
  - Always return list[str] for subprocess compatibility

- **Error handling hierarchy**: Custom exception classes for different failure modes
  - AudioProcessorError: Base exception
  - CommandExecutionError: Command failed with non-zero exit
  - CommandTimeoutError: Command exceeded timeout

- **Logging strategy**: Debug-level logging with output truncation
  - Log full command for debugging
  - Truncate output to 500 chars to prevent log spam
  - Log description if provided for context

### Conventions

- Function naming: `run_command()`, `build_<tool>_command()`
- Type hints: Use modern syntax (list[str], dict[str, Any])
- Timeout defaults: 300s for processing, 30s for probe operations
- Exception messages: Descriptive with error details
- Command validation: Check for non-empty list, positive timeout

### Gotchas

- FFmpeg filter chain must be comma-separated (not space-separated)
- SoX channel conversion uses "remix -" for mono, "remix 1,2" for stereo
- Output truncation at 500 chars prevents log spam but may hide important details
- Timeout exceptions need proper exception chaining with 'from e'
- Type hints must use list[str] not list for proper type checking

### Successful Approaches

- Separate builder functions for each CLI tool (FFmpeg vs SoX)
- Argument lists prevent shell injection vulnerabilities
- Custom exception classes enable precise error handling
- Debug-level logging with truncation balances visibility and log size
- Integration tests verify command building + execution together
- Standalone test runners work with pytest

### Testing Recommendations

- Unit tests: Test each builder function with various options
- Error tests: Test timeout, failure, invalid input paths
- Integration tests: Test command building + execution together
- Logging tests: Verify debug output with mock logger
- Type checking: Verify type hints with mypy/pyright
- Edge cases: Empty filters, None values, special characters


## Task 6: Audio Metadata Extraction Implementation

### Patterns Discovered

- **ffprobe JSON output structure**: Use `-print_format json -show_streams -show_format` flags
  - Streams array contains codec_type, sample_rate, channels, codec_name, bit_rate
  - Format object contains duration, size, format_name, bit_rate
  - Always find audio stream by filtering `codec_type == "audio"`
  
- **JSON parsing strategy**: Parse ffprobe output with json.loads()
  - Handle missing fields gracefully with .get() and defaults
  - Duration from format object, sample_rate/channels from audio stream
  - Bitrate available in both format and stream (use format for consistency)

- **Error handling mapping**:
  - FileNotFoundError: File doesn't exist (check before calling ffprobe)
  - CommandExecutionError: ffprobe fails (invalid audio, corrupted file)
  - CommandTimeoutError: ffprobe exceeds timeout (rare, 30s is safe)
  - JSONDecodeError: Invalid JSON output (wrap with CommandExecutionError)

### Conventions

- Timeout for probe operations: 30s (much faster than processing)
- Metadata structure: dict with keys [duration, sample_rate, channels, codec, bitrate, size_bytes, format]
- Return types: float for duration, int for sample_rate/channels/bitrate/size_bytes, str for codec/format
- Logging: Debug level for successful extractions, error level for failures

### Gotchas

- ffprobe stderr contains version info on error (not just error message)
- Sample rate and channels are strings in JSON, must convert to int
- Duration is string in JSON, must convert to float
- Bitrate may be 0 if not available in format metadata
- Some audio files may not have bitrate in format (use 0 as default)
- File size comes from format.size, not from file system stat

### Successful Approaches

- Validate file exists before calling ffprobe (better error messages)
- Use safe defaults (.get() with 0) for optional metadata fields
- Parse JSON first, then extract fields (cleaner error handling)
- Test with multiple audio formats (mono/stereo, various sample rates)
- Compare with original ffmpeg.probe() for equivalence verification
- Create comprehensive test suite with edge cases (corrupted files, missing files)

### Testing Recommendations

- Unit tests: Test metadata extraction with all test audio files
- Equivalence tests: Compare ffprobe CLI vs ffmpeg.probe() output
- Error tests: Test missing files, corrupted files, invalid paths
- Performance tests: Measure ffprobe execution time (should be <100ms)
- Edge cases: Empty files, very short audio, unusual sample rates
- Regression tests: Verify metadata structure matches original implementation


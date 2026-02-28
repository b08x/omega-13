# AudioProcessor Expected Outputs Documentation

This document describes the expected outputs and behavior for each AudioProcessor operation, based on baseline measurements and implementation analysis.

## Test Audio Files

All test audio files are generated synthetically using NumPy and soundfile, ensuring reproducibility and avoiding large binary files in the repository.

### Available Test Files

| File | Channels | Sample Rate | Duration | Size | Purpose |
|------|----------|-------------|----------|------|---------|
| `mono_44100_1s.wav` | 1 | 44100 Hz | 1.0s | 88 KB | Standard mono audio |
| `stereo_48000_2s.wav` | 2 | 48000 Hz | 2.0s | 384 KB | Standard stereo audio |
| `mono_16000_3s.wav` | 1 | 16000 Hz | 3.0s | 96 KB | Transcription-ready mono |
| `mono_44100_with_silence.wav` | 1 | 44100 Hz | 2.0s | 176 KB | Mono with silence padding |
| `stereo_48000_with_silence.wav` | 2 | 48000 Hz | 2.0s | 384 KB | Stereo with silence padding |
| `mono_44100_short.wav` | 1 | 44100 Hz | 0.5s | 44 KB | Very short audio |
| `mono_16000_long.wav` | 1 | 16000 Hz | 5.0s | 160 KB | Longer audio for testing |

## AudioProcessor Operations

### 1. `get_audio_info(file_path: Union[str, Path]) -> Dict[str, Any]`

**Purpose:** Extract metadata from audio files without processing.

**Expected Output Structure:**
```python
{
    "filename": str,           # Original filename
    "channels": int,           # Number of channels (1=mono, 2=stereo, etc.)
    "sample_rate": int,        # Sample rate in Hz
    "duration": float,         # Duration in seconds
    "size_bytes": int,         # File size in bytes
    "codec": str,              # Audio codec (e.g., "pcm_s16le")
    "bitrate": str,            # Bitrate string (e.g., "705 kb/s")
}
```

**Baseline Measurements:**
- `mono_44100_1s.wav`: 181.18ms
- `stereo_48000_2s.wav`: 201.44ms
- `mono_16000_3s.wav`: 183.55ms

**Expected Behavior:**
- Returns accurate metadata for all WAV files
- Processing time: ~180-200ms per file (includes ffmpeg startup overhead)
- No file modification
- Thread-safe (uses RLock)

**Error Cases:**
- `FileNotFoundError`: If input file doesn't exist
- `RuntimeError`: If ffmpeg is not available

---

### 2. `trim_silence(input_path, output_path=None, threshold_db=-50.0, min_silence_duration=0.5) -> Path`

**Purpose:** Remove silence from beginning and end of audio files using RMS-based detection.

**Expected Output:**
- New WAV file with silence trimmed
- Original sample rate and channels preserved
- Shorter duration than input (unless no silence detected)
- Smaller file size (proportional to trimmed duration)

**Baseline Measurements:**
- `mono_44100_with_silence.wav` (2.0s) → `trimmed.wav` (1.75s): 2.02ms
  - Input: 176 KB, Output: 154 KB
  - Removed: 0.25s of silence
- `stereo_48000_with_silence.wav` (2.0s) → `trimmed_stereo.wav` (1.75s): 4.91ms
  - Input: 384 KB, Output: 336 KB
  - Removed: 0.25s of silence

**Expected Behavior:**
- Detects silence using RMS energy threshold (default: -50 dB)
- Requires sustained silence for minimum duration (default: 0.5s)
- Preserves audio quality (no re-encoding, direct sample trimming)
- Handles both mono and stereo files
- Thread-safe (uses RLock)

**Algorithm Details:**
1. Load audio file with soundfile
2. Convert stereo to mono for RMS analysis (uses first channel)
3. Calculate RMS in sliding windows
4. Find first window above threshold (start point)
5. Find last window above threshold (end point, searching backwards)
6. Trim audio data and write to output

**Error Cases:**
- `FileNotFoundError`: If input file doesn't exist
- `ValueError`: If threshold_db or min_silence_duration are invalid types
- `RuntimeError`: If audio file cannot be read or written

---

### 3. `downsample(input_path, output_path=None, target_rate=16000, filter_type="high_quality", channels=1) -> Path`

**Purpose:** Resample audio to lower sample rate and optionally convert channels.

**Expected Output:**
- New WAV file at target sample rate
- Specified number of channels (default: mono)
- Shorter duration (same as input, but fewer samples)
- Smaller file size (proportional to sample rate reduction)

**Baseline Measurements:**
- `mono_44100_1s.wav` → `downsampled_16k.wav` (44100Hz → 16000Hz): 556.26ms
  - Input: 88 KB, Output: 32 KB
  - Size reduction: ~64%
- `stereo_48000_2s.wav` → `downsampled_stereo_16k.wav` (48000Hz → 16000Hz, stereo → mono): 608.78ms
  - Input: 384 KB, Output: 64 KB
  - Size reduction: ~83%

**Expected Behavior:**
- Uses high-quality resampling (default filter_type)
- Converts stereo to mono if channels=1
- Skips resampling if already at target rate and channels
- Preserves audio quality through proper filtering
- Thread-safe (uses RLock)

**Filter Types:**
- `"fast"`: Quick resampling, lower quality
- `"medium"`: Balanced quality and speed
- `"high_quality"`: Best quality, slower processing

**Error Cases:**
- `FileNotFoundError`: If input file doesn't exist
- `ValueError`: If target_rate is invalid (≤0 or wrong type)
- `RuntimeError`: If ffmpeg is not available

---

### 4. `encode_mp3(input_path, output_path=None, bitrate="128k") -> Path`

**Purpose:** Encode audio to MP3 format with specified bitrate.

**Expected Output:**
- New MP3 file with specified bitrate
- Sample rate may be adjusted by encoder (typically 16000Hz for transcription)
- Channels preserved (mono/stereo)
- Significantly smaller file size

**Baseline Measurements:**
- `mono_44100_1s.wav` → `encoded.mp3` (128k bitrate): 377.02ms
  - Input: 88 KB (WAV), Output: 18 KB (MP3)
  - Size reduction: ~80%
  - Output sample rate: 16000Hz (encoder adjustment)

**Expected Behavior:**
- Encodes to MP3 using libmp3lame
- Applies resampling to 16000Hz (transcription-friendly)
- Reduces file size significantly
- Processing time: ~300-400ms per second of audio
- Thread-safe (uses RLock)

**Bitrate Options:**
- `"128k"`: Default, good quality for transcription
- `"96k"`: Lower quality, smaller files
- `"192k"`: Higher quality, larger files

**Error Cases:**
- `FileNotFoundError`: If input file doesn't exist
- `RuntimeError`: If ffmpeg is not available

---

### 5. `preprocess_for_transcription(input_path, output_path=None, target_sample_rate=16000) -> Path`

**Purpose:** Complete preprocessing pipeline for transcription (downsample + trim silence).

**Expected Output:**
- New WAV file optimized for transcription
- Sample rate: 16000Hz (standard for speech recognition)
- Channels: 1 (mono)
- Silence trimmed from beginning and end
- Smaller file size

**Baseline Measurements:**
- `mono_44100_1s.wav` → `preprocessed.wav`: 554.07ms
  - Input: 88 KB (44100Hz, mono), Output: 32 KB (16000Hz, mono)
  - Size reduction: ~64%

**Expected Behavior:**
- Combines downsample and trim_silence operations
- Optimizes for Whisper transcription (16000Hz, mono)
- Removes silence to improve transcription quality
- Processing time: ~500-600ms per second of audio
- Thread-safe (uses RLock)

**Pipeline Steps:**
1. Downsample to 16000Hz (mono)
2. Trim silence (threshold: -50dB, duration: 0.5s)
3. Write output WAV file

**Error Cases:**
- `FileNotFoundError`: If input file doesn't exist
- `RuntimeError`: If ffmpeg is not available

---

### 6. `process_pipeline(input_path, output_path=None, operations=None, quality="high") -> Path`

**Purpose:** Execute a custom sequence of audio processing operations.

**Expected Output:**
- Processed audio file with applied operations
- Output format depends on final operation
- File size varies based on operations applied

**Expected Behavior:**
- Executes operations in specified order
- Each operation receives output of previous operation
- Supports custom operation sequences
- Thread-safe (uses RLock)

**Supported Operations:**
- `"trim_silence"`: Remove silence
- `"downsample"`: Resample to lower rate
- `"encode_mp3"`: Encode to MP3
- `"normalize"`: Normalize audio levels

**Error Cases:**
- `ValueError`: If operations list is empty or invalid
- `RuntimeError`: If any operation fails

---

## Performance Characteristics

### Processing Time Estimates

| Operation | Input Duration | Estimated Time | Notes |
|-----------|----------------|-----------------|-------|
| `get_audio_info` | Any | ~180-200ms | Includes ffmpeg startup |
| `trim_silence` | 1-2s | 2-5ms | Very fast, minimal processing |
| `downsample` | 1s | ~550ms | Resampling is CPU-intensive |
| `downsample` | 2s | ~600ms | Linear scaling with duration |
| `encode_mp3` | 1s | ~370ms | Encoding overhead |
| `preprocess_for_transcription` | 1s | ~550ms | Dominated by resampling |

### File Size Reductions

| Operation | Input → Output | Reduction |
|-----------|----------------|-----------|
| `trim_silence` | 2.0s → 1.75s | ~12% |
| `downsample` (44100→16000Hz) | 88KB → 32KB | ~64% |
| `downsample` (48000→16000Hz, stereo→mono) | 384KB → 64KB | ~83% |
| `encode_mp3` (128k) | 88KB → 18KB | ~80% |
| `preprocess_for_transcription` | 88KB → 32KB | ~64% |

---

## Thread Safety

All AudioProcessor methods are thread-safe through use of `threading.RLock()`:
- Multiple threads can call different methods concurrently
- Same thread can call methods recursively (reentrant lock)
- No blocking operations in critical sections
- Safe for use in multi-threaded applications

---

## Error Handling

### Common Error Scenarios

1. **Missing FFmpeg**
   - Error: `RuntimeError: FFmpeg binary not found in system PATH`
   - Solution: Install ffmpeg system package

2. **Invalid Input File**
   - Error: `FileNotFoundError: Input file not found: {path}`
   - Solution: Verify file path and permissions

3. **Invalid Parameters**
   - Error: `ValueError: {parameter} must be {type}, got {actual_type}`
   - Solution: Check parameter types and values

4. **Audio Processing Failure**
   - Error: `RuntimeError: FFmpeg processing failed`
   - Solution: Check audio file format and ffmpeg logs

---

## Testing Recommendations

### Unit Tests
- Test each operation with all test audio files
- Verify output metadata matches expectations
- Validate error handling for invalid inputs
- Check thread safety with concurrent calls

### Integration Tests
- Test operation pipelines (e.g., downsample → trim_silence)
- Verify output quality (no artifacts, proper audio)
- Test with various audio formats and sample rates

### Performance Tests
- Measure processing times for different audio durations
- Profile CPU and memory usage
- Verify no memory leaks in long-running scenarios

---

## Baseline Measurements JSON

Baseline measurements are saved to `.sisyphus/evidence/task-4-baseline-measurements.json` with the following structure:

```json
{
  "ffmpeg_available": true,
  "sox_available": true,
  "measurements": [
    {
      "operation": "get_audio_info",
      "input_file": "mono_44100_1s.wav",
      "output_file": "",
      "input_metrics": {
        "filename": "mono_44100_1s.wav",
        "channels": 1,
        "sample_rate": 44100,
        "duration": 1.0,
        "size_bytes": 88244
      },
      "output_metrics": {
        "filename": "mono_44100_1s.wav",
        "channels": 1,
        "sample_rate": 44100,
        "duration": 1.0,
        "size_bytes": 88244
      },
      "processing_time_ms": 181.18,
      "success": true,
      "error": null
    }
  ]
}
```

---

## References

- FFmpeg Documentation: https://ffmpeg.org/documentation.html
- SoundFile Documentation: https://soundfile.readthedocs.io/
- NumPy Documentation: https://numpy.org/doc/
- JACK Audio Connection Kit: https://jackaudio.org/

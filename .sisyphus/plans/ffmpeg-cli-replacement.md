# Replace FFmpeg-Python with CLI Subprocess Calls

## TL;DR

> **Quick Summary**: Replace python-ffmpeg library with direct subprocess calls to ffmpeg/sox CLI tools while maintaining exact same AudioProcessor interface and behavior.
> 
> **Deliverables**: 
> - Modified AudioProcessor class using subprocess instead of ffmpeg-python
> - Updated pyproject.toml removing ffmpeg-python dependency
> - Test suite validating behavioral equivalence
> - Error mapping preserving existing exception types
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Implementation → Integration Testing → Validation → Cleanup

---

## Context

### Original Request
Replace python-ffmpeg library implementation with direct subprocess calls to `ffmpeg` and/or `sox` CLI tools in omega-13 audio recording system.

### Research Findings

**Current Implementation Analysis**:
- All ffmpeg-python usage isolated in `/home/b08x/Workspace/omega-13/src/omega13/audio_processor.py`
- Single integration point: `audio.py` line 346 in `_file_writer` thread
- Four main operations: `ffmpeg.probe()`, `ffmpeg.filter('aresample')`, `ffmpeg.output()`, `ffmpeg.run()`
- Audio pipeline: raw WAV → trim_silence(-50dB) → downsample(16kHz mono) → processed WAV
- Runs in non-real-time thread (no JACK timing constraints)

**CLI Command Mappings**:
- `ffmpeg.probe()` → `ffprobe -print_format json -show_streams -show_format`
- `ffmpeg.filter('aresample')` → `ffmpeg -af aresample=<params>` or `sox -r <rate>`
- `ffmpeg.output(acodec='pcm_s16le')` → `ffmpeg -acodec pcm_s16le -ac <channels>`
- Complex MP3 pipeline → `ffmpeg -ar 16000 -ac 1 -b:a <bitrate> -c:a libmp3lame`

### Metis Review

**Critical Gaps Identified**:
- Error mapping strategy from subprocess exceptions to existing types
- Platform compatibility and binary availability validation
- Performance regression limits and quality verification approach
- Edge case handling for corrupted audio, missing binaries, system issues

---

## Work Objectives

### Core Objective
Replace python-ffmpeg library with CLI subprocess calls while maintaining 100% behavioral compatibility and interface preservation.

### Concrete Deliverables
- `src/omega13/audio_processor.py` - Modified to use subprocess instead of ffmpeg-python
- `pyproject.toml` - Remove ffmpeg-python dependency
- `tests/test_audio_processor_cli.py` - New test suite for CLI implementation
- `.sisyphus/evidence/` - Audio processing comparison results

### Definition of Done
- [x] All AudioProcessor methods work with subprocess implementation
- [x] Same audio quality output verified by comparison testing
- [x] Same error types and messages preserved
- [x] Performance within 20% of original implementation
- [x] Integration with audio.py unchanged

### Must Have
- Exact same public interface (method signatures, return types, exceptions)
- Behavioral equivalence for all audio operations
- Error mapping preserving existing exception handling
- Binary availability validation at startup

### Must NOT Have (Guardrails)
- Interface changes requiring modifications to audio.py
- New audio processing features or optimizations
- Configuration management for CLI tool paths
- Breaking changes to error handling patterns
- Performance regressions >20% of current implementation

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.
> Acceptance criteria requiring "user manually tests/confirms" are FORBIDDEN.

### Test Decision
- **Infrastructure exists**: YES (pytest, existing test patterns)
- **Automated tests**: TDD approach - write failing tests first, then implement
- **Framework**: pytest with existing patterns from omega-13
- **Quality Verification**: Audio file comparison + metadata validation

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Module Testing**: Use pytest for unit/integration tests
- **Audio Quality**: Compare processed audio files (old vs new implementation)
- **Error Handling**: Trigger error conditions and verify exception types match
- **Performance**: Measure processing time for standard audio samples

---

## Execution Strategy

### Parallel Execution Waves

> Maximize throughput by grouping independent tasks into parallel waves.
> Each wave completes before the next begins.
> Target: 5-8 tasks per wave.

```
Wave 1 (Start Immediately — foundation + preparation):
├── Task 1: CLI command mapping research & validation [quick]
├── Task 2: Error mapping design & exception hierarchy [quick] 
├── Task 3: Binary availability validation utilities [quick]
├── Task 4: Test data preparation & baseline measurements [quick]
├── Task 5: Subprocess wrapper foundation [quick]
└── Task 6: Audio metadata extraction implementation [quick]

Wave 2 (After Wave 1 — core implementations):
├── [x] Task 7: Audio probing (ffprobe) implementation [unspecified-high]
├── [x] Task 8: Audio resampling (ffmpeg/sox) implementation [unspecified-high]
├── [x] Task 9: Format conversion (PCM) implementation [unspecified-high]
├── [x] Task 10: MP3 encoding pipeline implementation [unspecified-high]
├── [x] Task 11: Processing pipeline orchestration [unspecified-high]
└── [x] Task 12: Error handling & exception mapping [unspecified-high]

Wave 3 (After Wave 2 — integration & validation):
├── [x] Task 13: AudioProcessor class integration [deep]
├── [x] Task 14: Comprehensive test suite development [deep]
├── [x] Task 15: Audio quality comparison validation [deep]
├── [x] Task 16: Performance benchmarking [unspecified-high]
├── [x] Task 17: Edge case testing (corrupted files, missing binaries) [unspecified-high]
├── [x] Task 14: Comprehensive test suite development [deep]
├── [x] Task 15: Audio quality comparison validation [deep]
├── [x] Task 16: Performance benchmarking [unspecified-high]
├── [x] Task 17: Edge case testing (corrupted files, missing binaries) [unspecified-high]
├── [x] Task 18: Integration testing with audio.py [deep]

Wave 4 (After Wave 3 — finalization):
├── [x] Task 19: pyproject.toml dependency cleanup [quick]
├── [x] Task 20: Documentation updates [writing]
├── [x] Task 21: Final integration validation [deep]
└── [x] Task 22: Migration guide & rollback procedures [writing]
├── Task 15: Audio quality comparison validation [deep]
├── Task 16: Performance benchmarking [unspecified-high]
├── Task 17: Edge case testing (corrupted files, missing binaries) [unspecified-high]
└── Task 18: Integration testing with audio.py [deep]

Wave 4 (After Wave 3 — finalization):
├── Task 19: pyproject.toml dependency cleanup [quick]
├── Task 20: Documentation updates [writing]
├── Task 21: Final integration validation [deep]
└── Task 22: Migration guide & rollback procedures [writing]

Critical Path: Task 5 → Task 11 → Task 13 → Task 21
Parallel Speedup: ~75% faster than sequential
Max Concurrent: 6 (Wave 1)
```

### Agent Dispatch Summary

- **1**: **6** — T1-T6 → `quick`
- **2**: **6** — T7-T12 → `unspecified-high`
- **3**: **6** — T13, T15, T18 → `deep`, T14 → `deep`, T16-T17 → `unspecified-high`
- **4**: **4** — T19 → `quick`, T20, T22 → `writing`, T21 → `deep`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.

- [x] 1. CLI Command Mapping Research & Validation

  **What to do**:
  - Research exact ffmpeg/sox CLI equivalents for each ffmpeg-python operation
  - Document command syntax, parameters, and option mappings
  - Create reference mapping table for implementation
  - Test commands manually to verify equivalence

  **Must NOT do**:
  - Implement actual subprocess calls yet
  - Modify existing AudioProcessor code
  - Add new dependencies

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward research and documentation task
  - **Skills**: []
    - No special skills needed for command research

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2-6)
  - **Blocks**: Tasks 7-12 (need command mappings)
  - **Blocked By**: None (can start immediately)

  **References**:
  
  **Pattern References**:
  - `src/omega13/audio_processor.py:276-283` - Current ffmpeg-python resampling implementation
  - `src/omega13/audio_processor.py:356-361` - Current ffmpeg.probe() usage pattern
  - `src/omega13/audio_processor.py:375-382` - Current MP3 encoding pipeline

  **Research Sources**:
  - Context7 `/websites/ffmpeg_documentation` - Official FFmpeg CLI documentation
  - Context7 `/rbouqueau/sox` - SoX command-line tool documentation
  - Librarian research results - CLI command equivalents and best practices

  **Acceptance Criteria**:
  - [x] Complete mapping table: ffmpeg-python operation → CLI command
  - [x] Verified CLI commands produce equivalent output to current implementation
  - [x] Documentation includes error handling patterns and timeout values

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Verify ffprobe metadata extraction equivalence
    Tool: Bash (command line testing)
    Preconditions: Have test audio file (e.g., tests/fixtures/test.wav)
    Steps:
      1. Extract metadata using current ffmpeg-python implementation
      2. Extract same metadata using ffprobe CLI command
      3. Compare outputs field by field (sample_rate, channels, duration, codec)
    Expected Result: Identical metadata values for all key fields
    Failure Indicators: Any metadata field differs between implementations
    Evidence: .sisyphus/evidence/task-1-metadata-comparison.json

  Scenario: Validate resampling command equivalence
    Tool: Bash (command line testing)
    Preconditions: Test WAV file with known properties
    Steps:
      1. Resample using current ffmpeg-python filter
      2. Resample using ffmpeg CLI with equivalent parameters  
      3. Compare output file properties and first 1000 samples
    Expected Result: Same output sample rate, similar waveform characteristics
    Evidence: .sisyphus/evidence/task-1-resampling-comparison.wav
  ```

  **Commit**: NO (research task, no code changes)

- [x] 2. Error Mapping Design & Exception Hierarchy

  **What to do**:
  - Design mapping from subprocess exceptions to current AudioProcessor exceptions
  - Analyze existing error handling patterns in audio_processor.py
  - Create error message parsing utilities for ffmpeg/sox output
  - Document exception compatibility requirements

  **Must NOT do**:
  - Change existing exception types or error message formats
  - Add new exception types beyond what currently exists
  - Modify error handling in audio.py

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Design task focused on mapping existing patterns
  - **Skills**: []
    - No special skills needed for error design

  **Parallelization**:
  - **Can Run In Parallel**: YES  
  - **Parallel Group**: Wave 1 (with Tasks 1, 3-6)
  - **Blocks**: Task 12 (error handling implementation)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/omega13/audio_processor.py:95,216,330,395` - Current ffmpeg.Error exception usage
  - `src/omega13/audio_processor.py:51-67` - Current FFmpeg availability validation
  - `src/omega13/injection.py:37-65` - Existing subprocess error handling patterns

  **Error Handling Context**:
  - `src/omega13/audio.py:356-358` - How AudioProcessor errors propagate to _file_writer

  **Acceptance Criteria**:
  - [x] Complete exception mapping: subprocess errors → existing AudioProcessor exceptions
  - [x] Error message parsing utilities for ffmpeg stderr output
  - [x] Compatibility verification with existing error handling code

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Verify exception type preservation
    Tool: pytest (unit testing)
    Preconditions: Test cases for various error conditions
    Steps:
      1. Trigger FileNotFoundError (missing input file) with old and new implementation  
      2. Trigger processing error (corrupted file) with both implementations
      3. Compare exception types, messages, and stack traces
    Expected Result: Same exception types raised for same error conditions
    Evidence: .sisyphus/evidence/task-2-exception-mapping-test.txt

  Scenario: Test error message compatibility
    Tool: pytest (unit testing) 
    Preconditions: Known error-inducing inputs
    Steps:
      1. Capture error messages from current ffmpeg-python implementation
      2. Parse equivalent error messages from CLI tool stderr
      3. Verify error information content is preserved
    Expected Result: Key error information preserved in new implementation
    Evidence: .sisyphus/evidence/task-2-error-messages.json
  ```

  **Commit**: NO (design task, no implementation yet)


- [x] 3. Binary Availability Validation Utilities

  **What to do**:
  - Create utility functions to check for ffmpeg/sox binary availability
  - Design startup validation that fails gracefully if binaries missing
  - Implement version checking for compatibility requirements
  - Create clear error messages for missing dependencies

  **Must NOT do**:
  - Add complex binary management or installation logic
  - Modify existing AudioProcessor __init__ method signature
  - Add configuration management for binary paths

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward utility function implementation
  - **Skills**: []
    - Standard subprocess and file system operations

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-2, 4-6)
  - **Blocks**: Tasks 7-12 (need binary validation)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/omega13/audio_processor.py:49-69` - Current FFmpeg availability validation pattern
  - `src/omega13/injection.py:27-31,74-83` - Binary availability checking with shutil.which

  **Acceptance Criteria**:
  - [x] check_ffmpeg_available() function returns bool
  - [x] check_sox_available() function returns bool
  - [x] _validate_cli_tools_availability() method for AudioProcessor
  - [x] Clear error messages when binaries not found

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Binary availability detection
    Tool: pytest (unit testing)
    Preconditions: Known system state (with/without ffmpeg installed)
    Steps:
      1. Run check_ffmpeg_available() on system with ffmpeg
      2. Mock missing binary and test error handling
      3. Test version checking for supported ffmpeg versions
    Expected Result: Accurate detection of binary availability and version
    Failure Indicators: False positives/negatives in availability detection
    Evidence: .sisyphus/evidence/task-3-binary-detection.txt

  Scenario: Graceful degradation with missing tools
    Tool: pytest (mocking)
    Preconditions: Mocked environment without ffmpeg/sox
    Steps:
      1. Initialize AudioProcessor with missing ffmpeg binary
      2. Verify appropriate ImportError or RuntimeError raised
      3. Check error message provides clear guidance
    Expected Result: Clear error message indicating missing dependencies
    Evidence: .sisyphus/evidence/task-3-missing-binary-error.txt
  ```

  **Commit**: YES
  - Message: `feat(audio): add CLI binary availability validation utilities`
  - Files: `src/omega13/audio_processor.py`
  - Pre-commit: `pytest tests/test_audio_processor.py -v`

- [x] 4. Test Data Preparation & Baseline Measurements

  **What to do**:
  - Create comprehensive test audio files with known properties
  - Generate baseline measurements using current ffmpeg-python implementation
  - Document expected outputs for each AudioProcessor operation
  - Setup performance measurement framework

  **Must NOT do**:
  - Modify existing test files or directory structure
  - Change existing test patterns significantly
  - Add large binary files to git repository

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Data preparation and measurement setup
  - **Skills**: []
    - Standard file operations and measurement

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-3, 5-6)
  - **Blocks**: Tasks 14-17 (need test data for validation)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `tests/test_*.py` - Existing test patterns and fixture usage
  - `src/omega13/audio_processor.py:37-43` - Default processing parameters to replicate

  **Acceptance Criteria**:
  - [x] Test audio files: mono/stereo, various sample rates, different durations
  - [x] Baseline measurements: processing times, output file properties
  - [x] Expected output documentation: metadata, audio characteristics
  - [x] Performance measurement utilities ready

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Test data integrity verification
    Tool: Bash (audio analysis)
    Preconditions: Generated test audio files
    Steps:
      1. Verify each test file has expected properties (sample rate, channels, duration)
      2. Ensure test files cover edge cases (very short, long duration, unusual rates)
      3. Validate audio content is clean (no corruption, proper waveforms)
    Expected Result: All test files have documented, verified properties
    Failure Indicators: Any test file has unexpected or corrupted properties
    Evidence: .sisyphus/evidence/task-4-test-data-verification.json

  Scenario: Baseline measurement accuracy
    Tool: pytest (performance testing)
    Preconditions: Current ffmpeg-python implementation working
    Steps:
      1. Process each test file through current AudioProcessor implementation
      2. Measure processing time, memory usage, output file characteristics
      3. Record baseline measurements for comparison
    Expected Result: Consistent, reproducible baseline measurements
    Evidence: .sisyphus/evidence/task-4-baseline-measurements.json
  ```

  **Commit**: YES
  - Message: `test: add comprehensive test data and baseline measurements`
  - Files: `tests/fixtures/audio/`, `tests/test_baseline_measurements.py`
  - Pre-commit: `python tests/test_baseline_measurements.py`

- [x] 5. Subprocess Wrapper Foundation

  **What to do**:
  - Create robust subprocess execution wrapper with error handling
  - Implement command builder utilities for ffmpeg/sox CLI construction
  - Add timeout handling and process management
  - Create logging infrastructure for CLI command execution

  **Must NOT do**:
  - Add complex command caching or optimization
  - Implement progress tracking for long operations
  - Add shell execution (security risk)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Well-defined utility implementation
  - **Skills**: []
    - Standard subprocess and logging patterns

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-4, 6)
  - **Blocks**: Tasks 7-12 (need wrapper for CLI execution)
  - **Blocked By**: Task 2 (need error mapping design)

  **References**:

  **Pattern References**:
  - `src/omega13/injection.py:33-65` - Existing subprocess execution with error handling
  - `src/omega13/notifications.py:46` - Simple subprocess.run usage
  - Librarian research - Best practices for subprocess execution in Python

  **Acceptance Criteria**:
  - [x] run_command() function with timeout and error handling
  - [x] build_ffmpeg_command() / build_sox_command() utilities
  - [x] Command logging with debug output
  - [x] Exception mapping to AudioProcessor-compatible errors

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Command execution with proper error handling
    Tool: pytest (unit testing)
    Preconditions: Mock subprocess environment
    Steps:
      1. Execute successful command and verify return handling
      2. Test timeout scenario with long-running mock command
      3. Test failure scenario and verify exception mapping
    Expected Result: Proper error handling and timeout enforcement
    Failure Indicators: Hanging processes, unmapped exceptions
    Evidence: .sisyphus/evidence/task-5-subprocess-wrapper-test.txt

  Scenario: Command construction accuracy
    Tool: pytest (unit testing)
    Preconditions: Various parameter combinations
    Steps:
      1. Build ffmpeg command for resampling with multiple parameters
      2. Build sox command for format conversion
      3. Verify no shell injection vulnerabilities
    Expected Result: Properly escaped, secure command arrays
    Evidence: .sisyphus/evidence/task-5-command-construction.json
  ```

  **Commit**: YES
  - Message: `feat(audio): add subprocess wrapper foundation for CLI tools`
  - Files: `src/omega13/audio_processor.py`
  - Pre-commit: `pytest tests/test_subprocess_wrapper.py -v`

- [x] 6. Audio Metadata Extraction Implementation

  **What to do**:
  - Implement get_audio_info() method using ffprobe CLI
  - Replace ffmpeg.probe() calls with subprocess-based metadata extraction
  - Parse JSON output from ffprobe into AudioProcessor-compatible format
  - Handle edge cases: corrupted files, missing metadata

  **Must NOT do**:
  - Change metadata structure or return format
  - Add new metadata fields not in current implementation
  - Modify error handling for metadata extraction

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Direct mapping from existing implementation
  - **Skills**: []
    - JSON parsing and metadata handling

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-5)
  - **Blocks**: Tasks 7, 11 (metadata needed for processing)
  - **Blocked By**: Task 5 (need subprocess wrapper)

  **References**:

  **Pattern References**:
  - `src/omega13/audio_processor.py:543-575` - Current get_audio_info() implementation
  - `src/omega13/audio_processor.py:556-570` - ffmpeg.probe() usage and output parsing
  - Librarian research - ffprobe JSON output parsing patterns

  **Acceptance Criteria**:
  - [x] get_audio_info() returns same metadata structure as before
  - [x] JSON parsing handles all required fields: duration, sample_rate, channels, codec, bitrate
  - [x] Error handling preserves existing exception types
  - [x] Performance within 10% of current implementation

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Metadata extraction equivalence
    Tool: pytest (comparison testing)
    Preconditions: Test audio files with known properties
    Steps:
      1. Extract metadata using current ffmpeg.probe() implementation
      2. Extract same metadata using new ffprobe CLI implementation
      3. Compare all fields: duration, sample_rate, channels, codec, bitrate, size_bytes
    Expected Result: Identical metadata for all test files
    Failure Indicators: Any metadata field differs between implementations
    Evidence: .sisyphus/evidence/task-6-metadata-comparison.json

  Scenario: Error handling for corrupted files
    Tool: pytest (error testing)
    Preconditions: Intentionally corrupted audio file
    Steps:
      1. Attempt metadata extraction on corrupted file
      2. Verify appropriate exception type raised
      3. Check error message provides useful information
    Expected Result: Same exception type and behavior as current implementation
    Evidence: .sisyphus/evidence/task-6-error-handling.txt
  ```

  **Commit**: YES
  - Message: `feat(audio): implement ffprobe-based metadata extraction`
  - Files: `src/omega13/audio_processor.py`
  - Pre-commit: `pytest tests/test_metadata_extraction.py -v`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest tests/` + any linting. Review all changed files for: hardcoded paths, missing error handling, subprocess security issues, performance regressions. Check that AudioProcessor interface unchanged.
  Output: `Tests [N pass/N fail] | Lint [PASS/FAIL] | Security [PASS/FAIL] | Interface [UNCHANGED/CHANGED] | VERDICT`

- [x] F3. **Audio Quality Verification** — `unspecified-high`
  Process same test audio files with old (ffmpeg-python) and new (CLI) implementation. Compare outputs: identical metadata, equivalent audio quality, same file formats. Test complete audio workflow from audio.py integration.
  Output: `Quality [N/N equivalent] | Integration [PASS/FAIL] | Metadata [N/N match] | VERDICT`

- [x] F4. **Performance & Regression Check** — `deep`
  Measure processing time for new vs old implementation. Verify memory usage hasn't increased significantly. Test error handling preserves same exception types. Validate no breaking changes to existing workflow.
  Output: `Performance [±N% vs baseline] | Memory [±N% vs baseline] | Errors [N/N preserved] | VERDICT`

---

## Commit Strategy

- **Wave 1**: Individual commits per task with focused scope
- **Wave 2**: Feature commits grouping related functionality
- **Wave 3**: Integration commits with comprehensive testing
- **Wave 4**: Final cleanup and documentation commits

All commits follow: `type(scope): description`

---

## Success Criteria

### Verification Commands
```bash
# Test the new implementation
pytest tests/test_audio_processor.py -v
pytest tests/test_audio_processor_cli.py -v

# Performance comparison
python scripts/compare_performance.py

# Integration test
python -m omega13 --test-audio-processing
```

### Final Checklist
- [x] All AudioProcessor methods work with subprocess implementation
- [x] Same audio quality verified by comparison testing
- [x] Same error types and messages preserved
- [x] Performance within 20% of original
- [x] ffmpeg-python dependency removed from pyproject.toml
- [x] Integration with audio.py unchanged
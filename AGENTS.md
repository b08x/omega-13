# AGENTS.md

This file provides guidance for agentic coding assistants working with the Omega-13 codebase. It covers build/lint/test commands, code style guidelines, and development workflows.

## Project Overview

Omega-13 is a terminal-based retroactive audio recorder and transcription tool for Linux. It maintains a continuous 13-second ring buffer in memory, allowing users to capture audio *after* they realize they wanted to record it. The application uses JACK/PipeWire for professional audio routing and delegates transcription to a local Docker-based whisper.cpp server for privacy.

**Key Innovation:** The retroactive recording mechanism means the buffer is *always* recording in memory, and the "record" hotkey triggers saving what has already been captured (past 13 seconds) plus whatever follows until the hotkey is pressed again.

## Development Commands

### Environment Setup
```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .
```

### Running the Application
```bash
# Standard run
omega13

# With debug logging
omega13 --log-level DEBUG

# Toggle recording from external process (for hotkey testing)
omega13 --toggle
```

### Docker Backend (Transcription Server)
```bash
# Start transcription server
docker compose up -d

# View logs
docker logs -f whisper-server

# Check health
curl http://localhost:8080

# Stop server
docker compose down
```

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_deduplication.py -v

# Run specific test function
python -m pytest tests/test_deduplication.py::test_deduplication -v

# Run with coverage
python -m pytest --cov=omega13 tests/
```

### Linting and Formatting
```bash
# Run code formatting (if configured)
# black src/ tests/

# Run linting (if configured)
# flake8 src/ tests/

# Run type checking (if configured)
# mypy src/
```

### Changelog Generation
```bash
# Generate changelog using git-cliff
git cliff --tag v2.2.0 -o CHANGELOG.md

# Preview next version's changes
git cliff --unreleased
```

## Code Style Guidelines

### General Principles
- Follow existing code patterns and conventions
- Prioritize readability and maintainability
- Write clear, concise comments for complex logic
- Maintain consistency with the existing codebase

### Python Standards
- Python 3.12+ required
- Follow PEP 8 style guide
- Use 4 spaces for indentation (no tabs)
- Limit lines to 88 characters (default Black setting)
- Use meaningful variable and function names

### Imports
- Group imports in standard order: standard library, third-party, local
- Use absolute imports when possible
- Avoid wildcard imports
- Place imports at the top of the file

Example:
```python
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import requests
from textual.app import App

from omega13.audio import AudioEngine
from omega13.config import Config
```

### Type Hints
- Use type hints for function parameters and return values
- Import typing modules as needed
- Use `Optional[T]` for values that can be None
- Use `Union[T1, T2]` for multiple possible types

Example:
```python
from typing import Optional, List

def process_audio(audio_data: np.ndarray, sample_rate: int) -> Optional[str]:
    """Process audio data and return transcription."""
    # Implementation here
    pass

def get_active_recordings() -> List[str]:
    """Return list of active recording file paths."""
    pass
```

### Naming Conventions
- Use `snake_case` for variables and functions
- Use `PascalCase` for classes
- Use `UPPER_CASE` for constants
- Use descriptive names that convey purpose

Example:
```python
# Constants
DEFAULT_SAMPLE_RATE = 48000
MAX_BUFFER_SIZE = 1024

# Variables
audio_buffer: np.ndarray
is_recording: bool

# Functions
def start_recording() -> None:
    pass

def has_audio_activity(signal: np.ndarray) -> bool:
    pass

# Classes
class AudioEngine:
    pass

class TranscriptionService:
    pass
```

### Error Handling
- Use specific exception types when possible
- Provide meaningful error messages
- Log errors appropriately
- Handle exceptions gracefully without crashing

Example:
```python
import logging

logger = logging.getLogger(__name__)

def transcribe_audio(file_path: str) -> Optional[str]:
    try:
        # Transcription logic here
        pass
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to transcription service")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during transcription: {e}")
        return None
```

### Documentation
- Write docstrings for all public functions and classes
- Use Google-style docstrings
- Include parameter descriptions and return values
- Add examples for complex functions

Example:
```python
def add_transcription(self, new_text: str) -> None:
    """Add a new transcription, deduplicating overlapping content.
    
    This method handles overlapping transcriptions from consecutive recordings
    by removing redundant content from previous entries.
    
    Args:
        new_text: The transcription text to add
        
    Example:
        >>> session.transcriptions
        ['Hello world']
        >>> session.add_transcription('Hello world and then some')
        >>> session.transcriptions
        ['Hello world', 'and then some']
    """
    pass
```

## Critical Implementation Details

### Ring Buffer Mechanics
The ring buffer in `AudioEngine._write_to_ring_buffer()` uses modulo wrapping:
- When `write_ptr + frames > ring_size`, it wraps: write part1 to end of buffer, part2 to start
- `buffer_filled` flag tracks whether buffer has wrapped at least once
- On record start, reconstruction logic differs based on `buffer_filled` state

### Thread Safety
- JACK `process()` callback: NO locks, NO allocations, NO blocking operations
- Use `queue.Queue(maxsize=200)` for passing audio from JACK thread to writer thread
- `TranscriptionService` tracks active threads for clean shutdown
- Shutdown deadline: 60 seconds total, with data integrity priority over speed

### Signal Detection
`has_audio_activity()` prevents empty recordings:
- Tracks `last_activity_time` when signal exceeds threshold (default: -70 dB)
- Checks 0.5s window before allowing recording
- Fallback: if ports are connected, allow recording even if signal is quiet

### PID-Based IPC
For Wayland compatibility (no global key interception):
1. App writes PID to `~/.local/share/omega13/omega13.pid` on startup
2. System keyboard shortcut runs `omega13 --toggle`
3. Toggle command reads PID, sends SIGUSR1 signal
4. Signal handler calls `action_toggle_record()` via `call_from_thread()`

### Transcription Retry Logic
`_transcribe_worker()` implements smart retries:
- 3 attempts with exponential backoff (2^retry_count seconds)
- During shutdown, reduced timeout (3s) to fail fast
- Checks `_shutdown_event` before expensive operations

## Project Structure Insights

```
src/omega13/
├── app.py              # Main Textual application, lifecycle management
├── audio.py            # JACK client, ring buffer, real-time processing
├── transcription.py    # HTTP client for whisper.cpp server
├── session.py          # Session/recording metadata management
├── config.py           # JSON config persistence
├── ui.py               # Custom Textual widgets (VUMeter, TranscriptionDisplay)
├── hotkeys.py          # Global keyboard listener (pynput)
├── clipboard.py        # Cross-platform clipboard integration
└── notifications.py    # Desktop notifications (D-Bus/notify-send)

tests/
├── test_deduplication.py     # Session transcription deduplication tests
├── test_incremental_save.py  # Incremental session save tests
└── test_health_check.py      # Transcription service health checks
```

## Common Pitfalls

1. **Don't block JACK callback:** Any operation in `AudioEngine.process()` that takes >1ms can cause xruns
2. **Thread cleanup on exit:** Transcription threads must be joined with timeout to prevent hang on quit
3. **Session temp files:** Unsaved sessions in `/tmp` are deleted on exit unless user saves them
4. **SIGUSR1 handling:** On non-Linux systems, `signal.SIGUSR1` may not exist - code has hasattr check
5. **Docker model path:** The whisper model must be mounted at `/app/models` and match `WHISPER_MODEL` env var
6. **SELinux contexts:** Docker volume mounts need `:Z` suffix on Fedora/RHEL for proper labeling

## Conventional Commit Types

This project uses conventional commits (enforced by git-cliff):
- `feat:` - New features
- `fix:` - Bug fixes
- `refactor:` - Code restructuring
- `perf:` - Performance improvements
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `chore:` - Build/config changes
# src/omega13/ MODULE

**Audio+TUI hybrid system with strict thread safety constraints**

## STRUCTURE

```
src/omega13/
├── app.py              # Textual app lifecycle, signal handlers, IPC
├── audio.py            # JACK client, ring buffer, modulo wrapping  
├── recording_controller.py  # State machine (IDLE→ARMED→RECORDING→STOPPING)
├── signal_detector.py  # RMS energy detection, voice activity
├── transcription.py    # HTTP client, worker threads, retry logic
├── session.py          # Recording metadata, overlap deduplication
├── ui.py              # Textual widgets (VUMeter, TranscriptionDisplay)
├── hotkeys.py         # Global pynput keyboard capture
├── injection.py       # ydotool text insertion
├── clipboard.py       # Cross-platform clipboard access
└── notifications.py   # D-Bus desktop notifications
```

## WHERE TO LOOK

| Task | Location | Critical Notes |
|------|----------|----------------|
| Ring buffer logic | `audio.py:_write_to_ring_buffer()` | Modulo math, buffer_filled flag |
| Thread coordination | `audio.py:AudioEngine` | Producer→Queue→Consumer pattern |
| State transitions | `recording_controller.py:RecordingController` | 5-state FSM |
| Voice detection | `signal_detector.py:has_audio_activity()` | RMS thresholds, sustained signal |
| Transcription retry | `transcription.py:_transcribe_worker()` | 3 attempts, exponential backoff |
| Session dedup | `session.py:add_transcription()` | Overlap detection algorithm |
| TUI composition | `ui.py:OmegaThirteenApp` | Widget hierarchy, key bindings |
| Global hotkeys | `hotkeys.py:setup_hotkeys()` | pynput→signal bridge |
| PID-based IPC | `app.py:main()` | SIGUSR1 handling for Wayland |

## CRITICAL CONSTRAINTS

### JACK Audio Thread (NEVER VIOLATE)
- **NO blocking calls** in `AudioEngine.process()` (>1ms = xruns)
- **NO memory allocation** (malloc/new forbidden)
- **NO locks** (mutexes, semaphores)
- Use `queue.Queue(maxsize=200)` for thread handoff

### Transcription Threading
- **ALWAYS join() with timeout** on shutdown (60s deadline)
- Track all worker threads in `TranscriptionService._threads`
- Check `_shutdown_event` before HTTP requests

### Signal Handling
- **Thread-safe only**: Use `call_from_thread()` for TUI interaction
- PID file must be cleaned up on exit
- Handle missing `signal.SIGUSR1` on non-Linux

## MODULE INTERACTIONS

```
JACK → AudioEngine → Queue → RecordingController
                               ↓
SignalDetector ← RMS analysis ← Audio samples
                               ↓
Session ← WAV reconstruction ← Ring buffer
                               ↓
TranscriptionService → whisper.cpp HTTP → Session
                               ↓
TUI widgets ← State updates ← Transcription results
```

## ANTI-PATTERNS (MODULE-SPECIFIC)

1. **Audio thread blocking:** Any I/O, allocation, or lock in `process()`
2. **Orphaned transcription threads:** Missing join() on shutdown
3. **UI from wrong thread:** Direct widget updates outside main thread
4. **Buffer reconstruction errors:** Wrong modulo math in ring buffer
5. **Signal race conditions:** Non-thread-safe signal handlers
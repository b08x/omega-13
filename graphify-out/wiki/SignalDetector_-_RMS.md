# SignalDetector / RMS

> 19 nodes · cohesion 0.13

## Key Concepts

- **SignalDetector** (13 connections) — `src/omega13/signal_detector.py`
- **.update()** (5 connections) — `src/omega13/signal_detector.py`
- **.get_silence_duration()** (4 connections) — `src/omega13/signal_detector.py`
- **._calculate_rms()** (3 connections) — `src/omega13/signal_detector.py`
- **.is_silence_threshold_exceeded()** (3 connections) — `src/omega13/signal_detector.py`
- **.reset_silence_timer()** (3 connections) — `src/omega13/signal_detector.py`
- **.__init__()** (2 connections) — `src/omega13/audio.py`
- **.get_config()** (2 connections) — `src/omega13/signal_detector.py`
- **.__init__()** (2 connections) — `src/omega13/signal_detector.py`
- **.reconfigure()** (2 connections) — `src/omega13/signal_detector.py`
- **Process audio block and update RMS metrics.          Args:             audio_dat** (1 connections) — `src/omega13/signal_detector.py`
- **Calculates RMS energy and detects silence/signal thresholds.      Uses RMS (Root** (1 connections) — `src/omega13/signal_detector.py`
- **Calculate RMS levels from current buffer.** (1 connections) — `src/omega13/signal_detector.py`
- **Reset the silence duration counter.** (1 connections) — `src/omega13/signal_detector.py`
- **Get current silence duration in seconds.          Returns:             Seconds o** (1 connections) — `src/omega13/signal_detector.py`
- **Check if silence has exceeded the configured duration.          Returns:** (1 connections) — `src/omega13/signal_detector.py`
- **Update detection thresholds without recreating the detector.          Args:** (1 connections) — `src/omega13/signal_detector.py`
- **Get current detector configuration.          Returns:             Dictionary wit** (1 connections) — `src/omega13/signal_detector.py`
- **Initialize signal detector.          Args:             samplerate: Audio sample** (1 connections) — `src/omega13/signal_detector.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `src/omega13/audio.py`
- `src/omega13/signal_detector.py`

## Audit Trail

- EXTRACTED: 46 (96%)
- INFERRED: 2 (4%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*
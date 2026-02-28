# Omega-13 Real-Time Audio Analysis

## Executive Summary

This document provides a comprehensive audit of memory allocations in the JACK audio callback path, identifying critical real-time safety violations that cause audio dropouts (xruns).

**Key Finding**: The JACK `process()` callback contains **15+ memory allocations per invocation**, translating to ~5,600+ allocations/second at typical 48kHz/128-frame settings.

---

## 1. JACK Callback Violations (audio.py:159-195)

### Critical Allocations in process()

| Line | Code | Violation Type | Severity |
|------|------|----------------|----------|
| 161 | `[port.get_array() for port in self.input_ports]` | **List comprehension** - creates new Python list | CRITICAL |
| 162 | `data = np.stack(input_arrays, axis=-1)` | **np.stack()** - allocates new NumPy array | CRITICAL |
| 165 | `self.peaks = np.max(np.abs(data), axis=0).tolist()` | **np.max() + np.abs() + .tolist()** - 3 allocations | CRITICAL |
| 166 | `self.dbs = [20 * np.log10(p) if p > 1e-5 else -100.0 for p in self.peaks]` | **List comprehension + np.log10()** | CRITICAL |
| 169 | `self.last_signal_metrics = self.signal_detector.update(data)` | Calls signal detector (has MORE violations) | CRITICAL |
| 174 | `if any(db > self.activity_threshold_db for db in self.dbs)` | **any() with generator** | HIGH |
| 184 | `self.record_queue.put(data.copy(), block=False)` | **data.copy()** - allocates new array | CRITICAL |

### Violation Details

#### Line 161: List Comprehension
```python
input_arrays = [port.get_array() for port in self.input_ports]
```
- **Problem**: Creates new Python list every callback
- **Fix**: Use direct index access or pre-allocated list

#### Line 162: np.stack()
```python
data = np.stack(input_arrays, axis=-1)
```
- **Problem**: Allocates new multi-dimensional array every callback
- **Fix**: Pre-allocate scratchpad buffer, use slice assignment

#### Line 165: np.max().tolist()
```python
self.peaks = np.max(np.abs(data), axis=0).tolist()
```
- **Problem**: Three operations, three allocations
- **Fix**: Move to UI thread, compute at poll time

#### Line 166: List Comprehension + log10
```python
self.dbs = [20 * np.log10(p) if p > 1e-5 else -100.0 for p in self.peaks]
```
- **Problem**: Creates new list, calls log10 per element
- **Fix**: Pre-allocate dbs list, update in-place in UI thread

#### Line 184: data.copy()
```python
self.record_queue.put(data.copy(), block=False)
```
- **Problem**: Allocates full audio buffer for every queue put
- **Fix**: Implement memory pool with buffer rotation

---

## 2. Signal Detector Violations (signal_detector.py:178-210)

The `SignalDetector.update()` method is called from the JACK callback:

| Line | Code | Violation Type |
|------|------|----------------|
| 179 | `'rms_levels': self.rms_levels.copy()` | **.copy()** - creates new list |
| 180 | `'rms_db': self.rms_db.copy()` | **.copy()** - creates new list |
| 200 | `rms_squared = np.mean(data ** 2, axis=0)` | **np.mean() + power** - temporary array |
| 201 | `self.rms_levels = np.sqrt(rms_squared).tolist()` | **np.sqrt() + .tolist()** |
| 204-210 | `self.rms_db = [] ... for rms in ...` | **List building loop** |

---

## 3. Memory Pool Design

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  JACK Audio Thread (Real-Time)                │
├─────────────────────────────────────────────────────────────┤
│  Pre-allocated Buffer Pool (3-4 buffers)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Buffer 0 │ │ Buffer 1 │ │ Buffer 2 │ │ Buffer 3 │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       │            │            │            │                │
│       ▼            ▼            ▼            ▼                │
│  [write ptr] ──► Next ──► Next ──► Next ──► (wrap)        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Queue       │
                    │ (index only)│
                    └─────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │ Writer Thread (Async)  │
              │ Consumes buffer index  │
              └────────────────────────┘
```

### Buffer Pool Implementation

```python
class AudioEngine:
    def __init__(self, client):
        # Pre-allocate pool of buffers
        self.buffer_pool_size = 4
        self.buffer_pool = [
            np.zeros((client.blocksize, client.channels), dtype='float32')
            for _ in range(self.buffer_pool_size)
        ]
        self.current_buffer = 0
        
    def process(self, frames):
        # Get current buffer (no allocation)
        buf = self.buffer_pool[self.current_buffer]
        
        # Copy directly into pre-allocated buffer (slice assignment)
        for i, port in enumerate(self.input_ports):
            buf[:frames, i] = port.get_array()
        
        # Rotate buffer index (no allocation)
        self.current_buffer = (self.current_buffer + 1) % self.buffer_pool_size
        
        # Pass buffer INDEX to queue (not data)
        self.record_queue.put(self.current_buffer, block=False)
```

### Scratchpad for np.stack() Replacement

```python
class AudioEngine:
    def __init__(self, client):
        # Pre-allocate scratchpad for channel stacking
        self.scratchpad = np.zeros(
            (client.blocksize, client.channels), 
            dtype='float32'
        )
    
    def process(self, frames):
        # Replace np.stack() with direct slice
        self.scratchpad[:frames] = np.column_stack([
            port.get_array()[:frames] 
            for port in self.input_ports
        ])
        # OR even faster - use existing arrays directly
        # (if JACK port arrays are contiguous)
```

---

## 4. UI Metrics Offloading

### Current Architecture (WRONG)

```
JACK Callback (48kHz)     UI Thread (20Hz)
     │                          │
     ▼                          │
peaks = np.max().tolist() ◄─── Polls peaks
dbs = [log10()...]       ◄─── Polls dbs
rms_levels.copy()         ◄─── Polls rms
```

### Fixed Architecture (TARGET)

```
JACK Callback (48kHz)     UI Thread (20Hz)
     │                          │
     ├── peaks[:] = raw_max    │──► compute peaks, dbs
     ├── rms_raw = calc()      │──► compute rms_db
     │                          │
     (Minimal state only)       (All heavy computation)
```

### Implementation

```python
class AudioEngine:
    def __init__(self):
        # Pre-allocate raw values (not converted)
        self._raw_peaks = np.zeros(self.channels, dtype='float32')
        self._raw_rms = np.zeros(self.channels, dtype='float32')
    
    def process(self, frames):
        # Only compute raw metrics in callback
        self._raw_peaks[:] = np.max(np.abs(data), axis=0)
        
        # DON'T convert to dB here
        # DON'T create lists
        # DON'T copy for UI
        
    def get_peak_meters(self):
        """Call from UI thread only"""
        return (20 * np.log10(self._raw_peaks + 1e-10)).tolist()
```

---

## 5. Quantified Impact

### Current Allocations Per Callback

| Operation | Allocations | Frequency | Total/sec |
|-----------|-------------|-----------|-----------|
| List comprehension (input) | 1 | 375/sec | 375 |
| np.stack() | 1 | 375/sec | 375 |
| np.max().tolist() | 2 | 375/sec | 750 |
| List comprehension (dB) | 1 | 375/sec | 375 |
| signal_detector.update() | 6 | 375/sec | 2250 |
| data.copy() (recording) | 1 | 375/sec | 375 |
| **TOTAL** | **~15** | | **~5,600** |

### At Different Buffer Sizes

| Buffer Size | Callbacks/sec | Allocations/sec |
|-------------|---------------|-----------------|
| 64 frames | 750 | ~11,250 |
| 128 frames (typical) | 375 | ~5,625 |
| 256 frames | 187.5 | ~2,812 |
| 512 frames | 93.75 | ~1,406 |

---

## 6. Recommended Implementation Order

1. **Phase 1**: Pre-allocate scratchpad, replace np.stack()
2. **Phase 2**: Implement buffer pool, eliminate data.copy()
3. **Phase 3**: Move UI metrics to UI thread
4. **Phase 4**: Optimize signal detector

---

## 7. Testing Strategy

Use the allocation tracking framework in `tests/test_realtime_safety.py`:

```python
def test_callback_zero_allocations():
    """Verify JACK callback has zero allocations."""
    with gc_disabled_allocation_tracking() as tracker:
        engine.process(128)  # Run callback
    
    allocations = tracker.count
    assert allocations == 0, f"Found {allocations} allocations"
```

---

## 8. References

- JACK Real-Time Programming: http://www.rossbencina.com/code/real-time-audio-programming-101
- jackclient-python: https://github.com/spatialaudio/jackclient-python
- NumPy In-Place Operations: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html

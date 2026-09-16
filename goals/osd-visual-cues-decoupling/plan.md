# Plan: OSD Visual Cues & GTK4 Decoupling

## Solution Approach

Three workstreams converge on a shared D-Bus signal infrastructure:

1. **D-Bus signal foundation** — The daemon emits an `OSDStateChanged(s state_type, s text, i timeout_ms)` signal on `org.omega13.Recorder`. Both the GNOME extension and the decoupled GTK4 OSD process subscribe to it. Waveform data (high-frequency RMS) stays as method calls to avoid signal storm overhead.

2. **GTK4 OSD decoupling** — `OSDManager` no longer runs a `Gtk.Application` in a daemon thread. Instead it spawns a standalone subprocess (`osd_process.py`) that runs its own `Gtk.Application` and listens for the D-Bus signal. The daemon kills the subprocess on shutdown.

3. **GNOME extension visual cues** — The extension subscribes to `OSDStateChanged` and renders tally-light colors: blinking red (recording), pulsing amber (processing), solid green (success), steady red (error), dim green/blue (idle).

4. **Error handling** — All 25 broad `except Exception:` blocks narrowed with `logger.exception()` for imports and `logger.warning()` minimum for silent swallows.

## Ordered Steps

### Step 1: Add OSDStateChanged D-Bus signal to daemon

**Files:** `src/omega13/headless_service.py`

- Add `@dbus_signal()` method `OSDStateChanged(self, state_type: "s", text: "s", timeout_ms: "i") -> None` to `HeadlessRecorderInterface` (alongside existing `RecordingToggled` and `HealthStatus` signals).
- Add a helper method `_emit_osd_state(state_type, text, timeout_ms=0)` on `HeadlessOmega13` that calls `self.dbus_service.interface.OSDStateChanged(state_type, text, timeout_ms)`.
- In `initialize()`, update the `RecordingEventCallbacks` lambdas to call BOTH `osd_manager.update()` (for waveform/fallback) AND `self._emit_osd_state()` (for signal). This ensures both the GNOME extension and the subprocess receive state changes.
- Add `on_transcription_error` handling: if `TranscriptionResult.status == ERROR`, emit `OSDStateChanged("error", "Transcription Failed", 5000)`.

**Verification:** `pytest tests/test_daemon_lifecycle.py -x` passes. New test asserts signal is emitted on recording start/stop transitions.

### Step 2: Create standalone OSD process

**Files:** New `src/omega13/osd_process.py`

- A standalone script that:
  - Initializes `Gtk.Application` (application_id `org.omega13.osd`)
  - Creates `Omega13OSD` window (reuses existing class from `ui/osd.py`)
  - Connects to the session bus via `dbus_next.aio.MessageBus`
  - Subscribes to `OSDStateChanged` signal on `org.omega13.Recorder` at `/org/omega13/Recorder`
  - On signal: marshals to GTK main loop via `GLib.idle_add`, calls `window.show_status(text, state_type, timeout_ms)`
  - Handles SIGTERM/SIGINT for clean shutdown
- Entry point: `python -m omega13.osd_process` (add `__main__.py` entry or `osd_process:main` function)
- The process runs its own asyncio loop (for dbus_next) and GLib main loop (for GTK). Use `GLib.MainLoop` in the main thread and run dbus_next in a separate asyncio loop, or use `dbus_next` synchronously via `dbus_next.message_bus.MessageBus` (blocking variant) to avoid async complexity.

**Verification:** `python -m omega13.osd_process` starts without error. Manually emit signal via `dbus-send` and verify window appears. New test `tests/test_osd_process.py` verifies the process starts and responds to a mock signal.

### Step 3: Refactor OSDManager for process decoupling

**Files:** `src/omega13/ui/osd.py`

- **Split PyGObject imports:** Move `Omega13OSD` class and all `gi`/`Gtk`/`cairo` imports behind a lazy import guard. `OSDManager` itself uses only `dbus_next` and stdlib. The module-level `osd_manager = OSDManager()` singleton no longer triggers PyGObject import.
- **Remove `run_in_background()`:** Delete the method that starts the GTK thread.
- **Add `start_subprocess()`:** Spawns `sys.executable -m omega13.osd_process` as a `subprocess.Popen`. Stores the `Popen` object. Checks display availability first (same `Gdk.Display.get_default()` check, but via a subprocess call or env check to avoid importing PyGObject).
- **Add `stop_subprocess()`:** Calls `proc.terminate()` then `proc.wait(timeout=5)`. Falls back to `proc.kill()` if terminate doesn't work.
- **Update `update()`:** 
  - No longer calls `self.window.show_status()` directly (no in-process window).
  - Still handles GNOME extension D-Bus proxy for waveform streaming (Tier 1).
  - If neither GNOME extension nor subprocess is running: fallback to notify-send (Tier 3).
  - The actual state rendering is handled by subscribers to the D-Bus signal (Step 1).
- **Waveform streaming:** Replace `GLib.timeout_add` with `asyncio` task (daemon provides the event loop reference via `set_event_loop()`). The asyncio task calls `UpdateWaveform` on the GNOME extension proxy every 100ms via `dbus_next` async method call.
- **Remove `quit()`:** Replaced by `stop_subprocess()`.
- **`set_audio_engine()`:** Keep for waveform data access. The subprocess doesn't need this — it gets waveform data from the GNOME extension path only. The subprocess renders state visuals, not waveform (waveform stays on the GNOME extension's native OSD).

**Verification:** `pytest tests/ -x` passes. `osd_manager` importable without PyGObject installed. New test verifies `start_subprocess()` spawns and `stop_subprocess()` terminates cleanly.

### Step 4: GNOME extension — state-aware OSD

**Files:** `gnome-extension/omega13@b08x.github.io/extension.js`, `osd.js`, `dbus.js`

**extension.js:**
- In `enable()`, add signal subscription to `org.omega13.Recorder.OSDStateChanged` via `Gio.DBus.session.signal_subscribe(...)`:
  - Bus: `org.omega13.Recorder`
  - Path: `/org/omega13/Recorder`
  - Interface: `org.omega13.Recorder`
  - Signal: `OSDStateChanged`
  - Callback: calls `this._dbusService._osd.showState(state_type, text, timeout_ms)`
- In `disable()`, remove the signal subscription via `Gio.DBus.session.signal_unsubscribe(subId)`.

**osd.js:**
- Add state tracking: `this._stateType = "idle"`, `this._stateText = ""`, `this._animTick = 0`, `this._animTimerId = null`, `this._hideTimerId = null`.
- Add `showState(stateType, text, timeoutMs)` method:
  - Sets `this._stateType`, `this._stateText`
  - Shows the actor (if not visible)
  - Starts animation timer (if not running): `this._animTimerId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => { this._animTick++; this._actor.queue_repaint(); return GLib.SOURCE_CONTINUE; })`
  - If `timeoutMs > 0`: set hide timer via `GLib.timeout_add` to call `this.hide()` and stop animation
- Update `_onRepaint()` to draw state-based indicator:
  - `recording`: blinking red dot — `(this._animTick % 10) < 5 ? bright red : dim red`
  - `processing`: pulsing amber dot — alpha oscillates with `Math.abs((this._animTick % 20) - 10) / 10`
  - `success`: solid green dot
  - `error`: steady red dot
  - `idle`: dim green/blue dot
  - Draw text next to the indicator
  - Keep existing waveform rendering when data is present
- Add `destroy()` cleanup: remove animation timer.

**dbus.js:**
- Add `ShowOSDWithState(s state_type, s text, i timeout_ms)` method to the D-Bus interface XML and implementation (as a backup path — calls `this._osd.showState(state_type, text, timeout_ms)`). This preserves backward compatibility if signal subscription fails.

**Verification:** Extension loads without errors in GNOME Shell. Manual test: start daemon, trigger recording, verify blinking red appears in extension OSD. New test verifies the D-Bus interface accepts the new method.

### Step 5: Wire daemon to new OSD flow

**Files:** `src/omega13/headless_service.py`

- In `initialize()`:
  - Replace `osd_manager.run_in_background()` with `osd_manager.start_subprocess()`.
  - Pass the asyncio event loop to `osd_manager.set_event_loop(asyncio.get_running_loop())`.
  - Update recording event callbacks to also call `self._emit_osd_state()`:
    ```python
    on_recording_started=lambda path, mode: (
        osd_manager.update(f"Recording ({path.name})", state_type="recording"),
        self._emit_osd_state("recording", f"Recording ({path.name})")
    ),
    ```
  - Add error callback: when transcription result status is ERROR, emit `OSDStateChanged("error", "Transcription Failed", 5000)`.
- In `shutdown()`:
  - Replace `osd_manager.quit()` with `osd_manager.stop_subprocess()`.
  - Ensure subprocess is killed before audio engine stops.

**Verification:** `pytest tests/ -x` passes. Manual test: start daemon, verify OSD subprocess is running (`pgrep -f osd_process`). Trigger recording, verify both GNOME extension and subprocess show state. Stop daemon, verify subprocess is killed.

### Step 6: Narrow exception handling — headless_service.py

**Files:** `src/omega13/headless_service.py`

Address all 18 `except Exception` blocks:

| Line | Current | Change |
|------|---------|--------|
| 33 | `except Exception as e:` + `logger.error` | Split: `except ImportError: logger.exception(...)` + `except Exception: logger.exception(...)` |
| 126 | `except Exception as e:` → DBusError | Narrow to `except (RuntimeError, OSError, ValueError) as e:` — keep DBusError re-raise |
| 138 | `except Exception as e:` → DBusError | Narrow to `except (RuntimeError, ValueError, FileNotFoundError) as e:` |
| 150 | `except Exception as e:` → DBusError | Narrow to `except (RuntimeError, ValueError) as e:` |
| 162 | `except Exception as e:` → DBusError | Narrow to `except (RuntimeError, ValueError) as e:` |
| 204 | `except Exception as e:` → DBusError | Narrow to `except (RuntimeError, ValueError) as e:` |
| 233 | `except Exception as e:` → DBusError | Narrow to `except (RuntimeError, KeyError, ValueError) as e:` |
| 309 | `except Exception as e:` → DBusError | Narrow to `except (ConnectionError, OSError) as e:` |
| 320 | `except Exception: pass` | **Upgrade:** `except Exception as e: logger.warning(f"D-Bus unregister failed: {e}")` |
| 402 | `except Exception as e:` → `logger.debug` | **Upgrade:** `except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e: logger.warning(f"pactl failed: {e}")` |
| 514 | `except Exception as e:` → `logger.warning` + traceback | Narrow: `except (ImportError, RuntimeError, ValueError) as e: logger.exception(...)` |
| 571 | `except Exception as e:` → `logger.error` | Narrow: `except (RuntimeError, OSError) as e: logger.error(...)` |
| 578 | `except Exception as e:` → `logger.error` | Narrow: `except (ConnectionError, RuntimeError) as e: logger.error(...)` |
| 587 | `except Exception as e:` → `logger.error` | Narrow: `except (RuntimeError, TimeoutError) as e: logger.error(...)` |
| 597 | `except Exception as e:` → `logger.error` | Narrow: `except (RuntimeError, OSError) as e: logger.error(...)` |
| 610 | `except Exception as e:` → `logger.error` | Narrow: `except (RuntimeError, ValueError) as e: logger.error(...)` |
| 713 | `except Exception as e:` → `logger.debug` | **Upgrade:** `except Exception as e: logger.warning(f"Health status emission failed: {e}")` |
| 40-48 | `except ImportError:` (no logging) | **Add logging:** `except ImportError as e: logger.exception(f"Transcription module import failed: {e}")` |

**Verification:** `pytest tests/ -x` passes. `grep -n "except Exception" src/omega13/headless_service.py` returns 0 bare catches. New test verifies `ImportError` logging produces full traceback.

### Step 7: Narrow exception handling — transcription.py

**Files:** `src/omega13/transcription.py`

Address all 7 `except Exception` blocks:

| Line | Current | Change |
|------|---------|--------|
| 106 | `except Exception as e:` in check_health | Narrow: `except (requests.exceptions.RequestException, ValueError, KeyError) as e:` |
| 146 | `except Exception as e:` in Groq check_health | Narrow: `except (requests.exceptions.RequestException, ValueError) as e:` (currently unreachable but tighten for safety) |
| 251 | `except Exception as e:` in GgufTranscriptionProvider.transcribe | Narrow: `except (RuntimeError, ValueError, IOError) as e:` — keep `logger.error` + raise pattern |
| 298 | `except Exception as e:` in _transcribe_file provider loop | Narrow: `except (TranscriptionError, requests.exceptions.RequestException, IOError) as e:` — keep `logger.warning` |
| 446 | `except Exception as e:` in retry loop | Narrow: `except (RuntimeError, IOError, ValueError) as e:` — keep retry logic |
| 512 | `except Exception as e:` in worker final catch | Keep broad (this is the top-level catch-all) but add `logger.exception(...)` (already uses it — verify it's `logger.exception` not `logger.error`) |
| 552 | `except Exception as e:` in provider shutdown | Narrow: `except (RuntimeError, OSError) as e:` — keep `logger.error` |

**Verification:** `pytest tests/ -x` passes. `grep -n "except Exception" src/omega13/transcription.py` returns at most 1 (the top-level worker catch, which uses `logger.exception`). New test verifies `ImportError` in provider init logs full traceback.

### Step 8: Tests

**Files:** New `tests/test_osd_signal.py`, `tests/test_osd_process.py`, `tests/test_error_handling.py`

- `test_osd_signal.py`: Mock D-Bus interface, trigger recording events, assert `OSDStateChanged` signal emitted with correct state_type and text for each lifecycle event (recording_started, recording_stopped, transcription_started, transcription_complete, transcription_error).
- `test_osd_process.py`: Start `osd_process.py` as subprocess, verify it subscribes to D-Bus, emit a mock signal, verify process renders (or at minimum doesn't crash). Test subprocess lifecycle: start, stop, kill.
- `test_error_handling.py`: Test that `ImportError` in OSD module import produces `logger.exception` call (mock the import). Test that silent swallow blocks now log at `logger.warning` level.

**Verification:** `pytest tests/ -x` all pass. `pytest --cov=omega13.headless_service --cov=omega13.transcription` shows improved coverage on exception paths.

## Alternative Considered: OSC (Open Sound Control)

OSC was considered as an alternative to D-Bus for inter-process communication. OSC uses UDP, is real-time friendly, and fits omega-13's audio domain (JACK ecosystem). However, D-Bus is the better choice for this work because:

- The GNOME extension runs inside GJS, which has native `Gio.DBus` support. No OSC client exists for GJS without a native module.
- D-Bus signals provide built-in service discovery and name ownership — the daemon can detect if the extension is loaded.
- State changes are low-frequency (a few per recording cycle), so D-Bus overhead is negligible.

OSC could be added later for the high-frequency waveform path if the D-Bus method-call approach proves to be a bottleneck. For now, D-Bus method calls at 100ms intervals are sufficient.

## Risks and Open Questions

1. **dbus_next signal subscription in GNOME extension** — The GNOME extension uses GJS (Gio.DBus), while the daemon uses dbus_next. The signal is on the session bus, so both should see it. However, GJS signal subscription syntax needs verification. Risk: signal may not be received. Mitigation: keep `ShowOSDWithState` method as fallback path.

2. **OSD subprocess display availability** — The subprocess needs a display to show GTK windows. On headless systems without a display, it should exit gracefully. The daemon's `start_subprocess()` should check `DISPLAY` env var or `WAYLAND_DISPLAY` before spawning.

3. **Waveform streaming without GLib loop** — Moving from `GLib.timeout_add` to `asyncio` task for waveform streaming changes the threading model. The `dbus_next` async call to `UpdateWaveform` runs in the asyncio loop. JACK callbacks come from a separate thread. Need `asyncio.run_coroutine_threadsafe()` to schedule waveform streaming from the JACK thread. Risk: waveform updates may lag if the asyncio loop is busy. Mitigation: use a dedicated asyncio task with high priority.

4. **Process cleanup on crash** — If the daemon crashes without calling `shutdown()`, the OSD subprocess may be orphaned. Mitigation: subprocess should monitor parent PID and exit if parent dies (`PR_SET_PDEATHSIG` on Linux).

5. **Import narrowing accuracy** — The specific exception types listed in Step 6/7 are based on code analysis but may miss edge cases. Each narrowed catch should be reviewed against the actual operations in the try block. Risk: a narrow catch misses an exception type that was previously caught, causing unhandled exceptions. Mitigation: run full test suite after each file's changes.

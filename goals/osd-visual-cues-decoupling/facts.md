# Facts

- The GNOME extension OSD (osd.js) draws state-based colors: blinking red for recording, pulsing amber for processing/transcribing, solid green for success, steady red for error, and dim green or blue for idle/armed.
- The GNOME extension D-Bus interface (dbus.js) accepts a state-aware OSD method (e.g., ShowOSDWithState(s state_type, s text, i timeout_ms)) in addition to the existing ShowOSD/HideOSD/UpdateWaveform methods.
- The daemon emits D-Bus signals (e.g., OSDStateChanged(s state_type, s text, i timeout_ms)) on the org.omega13.Recorder interface that both the GNOME extension and the decoupled GTK4 OSD process subscribe to.
- The GTK4 OSD runs as a separate process spawned by the daemon on startup, not as a thread inside the daemon process. The daemon kills the OSD process on shutdown.
- The decoupled GTK4 OSD process subscribes to D-Bus signals from the daemon for state changes (recording, processing, success, error, idle) and renders the same state-based visual cues as the GNOME extension OSD.
- All 25 broad 'except Exception:' blocks in headless_service.py (18) and transcription.py (7) are replaced with narrowed exception catches specific to the expected failure modes of each block.
- ImportError and import-related exceptions in headless_service.py and transcription.py use logger.exception() so full tracebacks (including missing .so files) appear in journalctl.
- Silent exception swallows (blocks that catch and pass, or catch and only log at debug level) are upgraded to at least logger.warning() with context about what failed.
- The existing DBusError re-raise pattern in headless_service.py D-Bus method handlers is preserved — narrowed catches still re-raise as DBusError for the D-Bus client.
- The 3-tier OSD dispatch (GNOME native → GTK4 layer shell → notify-send fallback) is preserved. Decoupling only changes the GTK4 tier from in-process thread to separate process; the tier selection logic remains in OSDManager.
- Waveform data (high-frequency RMS levels) continues to flow via D-Bus method calls (UpdateWaveform) to the GNOME extension, not via signals, to avoid signal storm overhead.
- Existing tests pass after changes. New tests cover: D-Bus signal emission for OSD state changes, OSD subprocess lifecycle (spawn and kill), and narrowed exception handling paths.

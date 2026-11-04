# Omega-13 GNOME Extension

GNOME Shell extension for the Omega-13 retroactive audio recorder: native Cairo OSD rendering, window activation on Wayland, and a panel indicator for the daemon's runtime controls. Uuid `omega13@b08x.github.io` (metadata.json:4). *Note:* `metadata.json` contains no `version` field — only `name`, `description`, `uuid`, `shell-version`, and `url` (metadata.json:1-14).

## Compatibility

GNOME Shell 45 through 50 (`shell-version`, metadata.json:5-12).

## Build and Installation

1. Package the extension:
   ```bash
   gnome-extensions pack omega13@b08x.github.io
   ```
2. Install to your local extensions directory — the extension must live at:
   `~/.local/share/gnome-shell/extensions/omega13@b08x.github.io`
3. Activate:
   ```bash
   gnome-extensions enable omega13@b08x.github.io
   ```
   *(On Wayland, you may need to log out and log back in before the extension becomes visible; if it is still missing, confirm with `gnome-extensions list` before enabling.)*

The installer deploys the extension automatically under the same uuid (src/omega13/installer/steps/gnome.py:16).

## Panel Indicator

The extension adds an undocumented panel indicator: a `PanelMenu.Button(0.0, 'Omega-13', false)` (extension.js:17) carrying the `media-record-symbolic` icon (extension.js:20), placed with `Main.panel.addToStatusArea('omega13-indicator', ...)` (extension.js:62). Its menu maps straight onto the daemon's D-Bus methods on `org.omega13.Recorder` (bus.call targets at extension.js:90-92):

- *OSD Display* switch → `SetOSDEnabled(b)` (extension.js:27-29; daemon method at src/omega13/headless_service.py:188)
- *Auto-Record* switch → `SetAutoRecordEnabled(b)` (extension.js:34-36; daemon method at src/omega13/headless_service.py:167)
- *Auto-Record Threshold* slider → `SetAutoRecordThreshold(d)`, mapping slider value 0..1 to −60.0..0.0 dB via `threshold = -60.0 + (slider.value * 60.0)` (extension.js:41-46; daemon method at src/omega13/headless_service.py:176)
- *Transcription* submenu → *Retry failed transcription (0)* menu item → `RetryFailedTranscriptions` — the *plural* method, not `RetryTranscription` (extension.js:54-57; daemon method at src/omega13/headless_service.py:143)

The retry item polls `GetFailedTranscriptionCount() -> i` every 2000 ms via `GLib.timeout_add` (extension.js:66-69, polling body at :110-122) and rewrites its label with the count; when the count exceeds zero the label turns red `#ff5555` and bold (extension.js:116-118). The extension also subscribes to the daemon's `OSDStateChanged(ssi)` signal and forwards `(state_type, text, timeout_ms)` straight into `showState` (extension.js:72-83; signal defined at src/omega13/headless_service.py:259).

## D-Bus Public Interface

Bus framing, stated exactly: *the extension owns no bus name.* It exports its object on the GNOME Shell process's session-bus connection at object path `/org/gnome/Shell/Extensions/Omega13` (dbus.js:31), so callers address the Shell's well-known name `org.gnome.Shell` — which is precisely how Omega-13's injection module calls it (src/omega13/injection.py:52-56). Interface: `org.gnome.Shell.Extensions.Omega13` (dbus.js:6).

### Methods

- *`FocusWindow(s title) -> b`* (dbus.js:7-10, implementation :39-53) — walks `global.get_window_actors()` and activates the window whose title equals `title` *exactly*; returns `false` when no exact match exists.
- *`ShowOSD() -> void`* (dbus.js:11, implementation :55-57)
- *`HideOSD() -> void`* (dbus.js:12, implementation :59-61)
- *`ShowOSDWithState(s state_type, s text, i timeout_ms) -> void`* (dbus.js:13-17, implementation :63-65) — displays the OSD with a state cue, a text label, and an auto-hide timeout in milliseconds (0 = persistent).
- *`UpdateWaveform(ad rms_data) -> void`* (dbus.js:18-20, implementation :67-77) — pushes one array of doubles into the OSD's rolling waveform history.

## OSD State Cues

The visual cues are implemented at osd.js:135-150 with these exact colors:

| State | Rendering |
| --- | --- |
| `recording` | Alternating `RGB(1.0, 0.3, 0.3)` bright red and `RGB(0.5, 0.1, 0.1)` dim red, blinking on the 100 ms animation tick (osd.js:135-140) |
| `processing` | `RGBA(0.9, 0.8, 0.2, alpha)` amber, alpha pulsing 0.5→1.0 over a 20-tick cycle (osd.js:141-143) |
| `success` | `RGB(0.2, 0.9, 0.4)` solid green (osd.js:144-145) |
| `error` | `RGB(0.9, 0.2, 0.2)` steady red (osd.js:146-147) |

The daemon emits exactly five state types over `OSDStateChanged` — `recording`, `processing`, `success`, `error`, `idle` (src/omega13/headless_service.py:476-503). Both `"idle"` and `"hidden"` hide the OSD immediately on arrival (osd.js:67-71), which means the dim-green `else` branch at osd.js:148-149 — the documented *idle: Dim green* cue — never renders for any state the daemon actually sends.

## Waveform Data — Rationed Uncertainty

`UpdateWaveform` feeds a 25-sample rolling history: each call pushes `max(rms_data)` and shifts the history beyond 25 entries (osd.js:101-109). A producer *does* exist in the daemon — `OSDManager._stream_waveform` pushes `audio_engine.signal_detector.rms_levels` (src/omega13/signal_detector.py:83) every 0.1 s through a proxy call to this method (src/omega13/ui/osd.py:344-358) — but the stream starts only when the daemon's environment reports GNOME, i.e. `XDG_CURRENT_DESKTOP` containing `"GNOME"` (src/omega13/ui/osd.py:363-376). The installer-generated systemd unit imports only `DISPLAY` and `WAYLAND_DISPLAY` (src/omega13/installer/steps/systemd.py:34-35), and the RPM unit imports neither (packaging/rpm/omega13.service:7-12) — so under the deployed service the gate typically never opens and the waveform stays flat. *Escape hatch:* run `systemctl --user edit omega13`, add `Environment="XDG_CURRENT_DESKTOP=GNOME"`, restart the daemon, trigger a recording, and watch the OSD waveform (or `busctl --user monitor` for `UpdateWaveform` calls on `org.gnome.Shell`).

## Troubleshooting and CLI Inspection

Interact with the extension from the command line using `busctl` — useful for debugging and manual testing.

*Show the OSD:*
```bash
busctl --user call org.gnome.Shell \
  /org/gnome/Shell/Extensions/Omega13 \
  org.gnome.Shell.Extensions.Omega13 \
  ShowOSD
```

*Hide the OSD:*
```bash
busctl --user call org.gnome.Shell \
  /org/gnome/Shell/Extensions/Omega13 \
  org.gnome.Shell.Extensions.Omega13 \
  HideOSD
```

*Show OSD with a state cue:*
```bash
busctl --user call org.gnome.Shell \
  /org/gnome/Shell/Extensions/Omega13 \
  org.gnome.Shell.Extensions.Omega13 \
  ShowOSDWithState ssi "recording" "Recording..." 0
```

*Focus a specific window (exact title match):*
```bash
busctl --user call org.gnome.Shell \
  /org/gnome/Shell/Extensions/Omega13 \
  org.gnome.Shell.Extensions.Omega13 \
  FocusWindow s "Whisp"
```

*Update waveform data:*
```bash
busctl --user call org.gnome.Shell \
  /org/gnome/Shell/Extensions/Omega13 \
  org.gnome.Shell.Extensions.Omega13 \
  UpdateWaveform ad 3 0.1 0.5 0.3
```

*Check the daemon the extension talks to* — its methods live on `org.omega13.Recorder` at `/org/omega13/Recorder` (src/omega13/headless_service.py:52-54), a different bus name than the extension's own interface:
```bash
busctl --user call org.omega13.Recorder \
  /org/omega13/Recorder \
  org.omega13.Recorder \
  GetState
```

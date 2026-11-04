# Omega-13

![Omega-13 Header](assets/header.png)

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![JACK Audio Connection Kit](https://img.shields.io/badge/JACK-Audio_Connection_Kit-00A98F)](https://jackaudio.org/)

Omega-13 is named for the fictional device in *Galaxy Quest* that rewinds the last 13 seconds of time. This one rewinds the last 13 seconds of sound. It is a headless retroactive audio daemon for the Linux desktop: a JACK callback keeps the last 13 seconds of audio in a RAM-resident ring buffer, and on a trigger the daemon stops forgetting — the buffered audio drains into a WAV, is trimmed and downsampled, transcribed, and routed to your clipboard, a scratchpad window, or a dated markdown note.

The trigger is the whole idea. Omega-13 is always recording and never recording: audio is captured into RAM continuously and discarded continuously, so a capture doesn't start the recording — it stops the discarding. The sentence you started before you remembered the hotkey is already there.

Omega-13 is at version 2.7.5, requires Python 3.12+, installs the `omega13` console script (`omega13.app:main`), and runs as a systemd user service.

## Quick Start

1. Clone and install ([details](#setup)):

   ```bash
   git clone https://github.com/b08x/omega-13.git
   cd omega-13
   ./install.sh
   ```

2. Download a transcription model ([details](#setup)): `just model dl`
3. Enable the GNOME extension ([details](#setup)): `gnome-extensions enable omega13@b08x.github.io`
4. Start the daemon ([details](#running-it)):

   ```bash
   systemctl --user start omega13
   systemctl --user enable omega13
   ```

5. Capture ([details](#control)): `omega13 --toggle` — the last 13 seconds, plus everything said since the previous toggle, becomes a WAV and then a transcript in the session temp root.

> **Captures stay in tmpfs.** Nothing writes to `~/Recordings` automatically: nothing in the daemon's entry chain promotes a session to permanent storage, so captures and transcripts persist under `$XDG_RUNTIME_DIR/omega13` until systemd reclaims it. See [Session Management](#session-management).

## Table of Contents

- [What Omega-13 Does](#what-omega-13-does)
- [Why Omega-13 Exists](#why-omega-13-exists)
- [Requirements](#requirements)
- [Setup](#setup) — [RPM Packaging](#rpm-packaging-fedora--epel)
- [Running It](#running-it)
- [Control](#control) — [Settings](#settings)
- [Workflow](#workflow)
- [Session Management](#session-management)
- [Transcription & Models](#transcription--models)
- [The Architecture](#the-architecture)
- [Abstraction Leaks & Trade-offs](#abstraction-leaks--trade-offs)
- [Failure Recovery](#failure-recovery)
- [Development](#development)
- [License](#license)

## What Omega-13 Does

Short version: a retroactive audio daemon that runs as a systemd user service, buffers in memory, and touches no disk with audio data until a capture fires.

The AudioEngine runs a JACK client named `Omega13` that registers `DEFAULT_CHANNELS = 2` input ports. Its process callback copies each JACK block into a scratchpad, updates peak and RMS meters, and appends the block to the ring buffer. On capture, `start_recording` reconstructs the ring into a linear segment — everything from the write pointer forward is the oldest audio; everything behind it, the newest — and a writer thread produces the WAV. An ffmpeg pipeline then trims silence at the configured end threshold and downsamples the file to 16 kHz mono; every provider is fed that format regardless of whether it requires it. The processed WAV lands in the current session's `recordings/` directory under a sequential name — `001.wav`, `002.wav`, and so on.

If `transcription.auto_transcribe` is true — the default — the stop event hands the WAV to `RecordingEventHandler.register_and_transcribe`, which registers it with the session and starts the transcription worker. When the WAV sits under a session's `recordings/` directory, the worker writes the transcript to `transcriptions/<stem>.md` in the same session; audio captured outside a session gets a sibling `.md` file instead.

Three further output routes exist, and all three default to off:

- `copy_to_clipboard: false` — when enabled, the worker copies the text through the pyperclip-backed clipboard module.
- `inject_to_active_window: false` — when enabled, it types the text into a window titled "Whisp" via ydotool.
- `write_to_file: false` — when enabled, it appends `[HH:MM:SS] text` to a `YYYY-MM-DD.md` daily file in the directory you configure.

The three routes dispatch sequentially inside the transcription worker's daemon thread — not in a forked process.

What that looks like on disk:

```text
session_20260214_143205_ab12cd34/
├── recordings/
│   └── 001.wav
└── transcriptions/
    └── 001.md
```

And one line of the daily file, if `write_to_file` is enabled:

```text
[14:32:05] the transcribed sentence goes here
```

## Why Omega-13 Exists

The baseline inspiration was Steve Harris's `time machine`, an old JACK application that captured the last 10 seconds of the audio buffer when you hit record, built to emulate a mini-disc recorder for studio riffing. I applied the same concept to a dictation pipeline: if I start rambling into the microphone to capture notes and forget to hit the hotkey, the thought is gone. I bumped the buffer from 10 to 13 seconds — the ring costs `samplerate × 13 × 2 channels × float32`, under 5 MiB at 48 kHz — and pinned the value as `BUFFER_DURATION = 13` (src/omega13/audio.py:16). The name arrived when my partner pointed out that a 13-second rollback sounds exactly like the Omega-13 device from *Galaxy Quest*. For rambles that outrun 13 seconds, the auto-record threshold covers the gap: a 13-second retroactive buffer for manual triggers, an RMS threshold for longer stretches, and immediate writes to temporary session space cover the major failure modes where dictation would otherwise be lost.

## Requirements

| Requirement | Needed for | Note |
| --- | --- | --- |
| Python 3.12+ | everything | managed by `uv`; `./install.sh` bootstraps it |
| JACK or the PipeWire-JACK bridge | every capture | the daemon connects your saved input ports, or resolves the PulseAudio default source |
| A transcription backend | transcription | a local GGUF model (the default), a whisper-server at `http://localhost:8080`, or a `GROQ_API_KEY` in the environment |
| `ydotool` + the `ydotoold` daemon | text injection only | requires `/dev/uinput` and a running `ydotoold` |
| GNOME Shell 45–50 | the native OSD and the window-focus bypass only | other compositors get the GTK4 layer-shell OSD; below that, `notify-send` |
| A window titled "Whisp" | the injection route only | injection aborts entirely, without typing, if it cannot focus that window |

Only JACK and a transcription backend are hard requirements — everything else degrades gracefully, and the three-tier OSD under [Architecture](#the-architecture) is the proof.

## Setup

The installer runs as your normal user — it refuses to run as root — and requests `sudo` itself for the system-dependency step via `dnf`, `apt-get`, or `pacman`. Start it with:

```bash
git clone https://github.com/b08x/omega-13.git
cd omega-13
./install.sh
```

`just install` is *not* the installer — that recipe's entire body is a redirect message, and it exits 1; the heavy lifting lives in `./install.sh`. The shell script detects your distribution, installs system dependencies, bootstraps `uv` from astral.sh, creates a virtualenv and runs `uv sync`, then executes `.venv/bin/python -m omega13.installer`. The Python installer sequences seven steps: preflight checks, build ydotool, build transcribe-cpp, deploy application, install systemd service, install GNOME extension, summary.

Five of those steps deserve their mechanics stated plainly:

- The transcribe-cpp build configures CMake with `-DTRANSCRIBE_BUILD_SHARED=ON`, adds `-DTRANSCRIBE_CUDA=ON` when CUDA hardware is detected, and adds `-DTRANSCRIBE_VULKAN=ON` when `libvulkan.so` is present.
- The ydotool step enables `systemctl --user enable --now ydotoold` when the daemon is missing.
- The deploy step rsyncs the application to `~/.local/share/omega13` and symlinks `~/.local/bin/omega13`.
- The GNOME extension is installed under the uuid `omega13@b08x.github.io`.
- The systemd unit is generated at install time rather than shipped — the template points `ExecStart` at the deployed venv binary with `--no-daemon` and imports `DISPLAY` and `WAYLAND_DISPLAY` into the unit environment.

To download models, use the dedicated command:

```bash
just model dl
```

This launches a `gum`-based interactive menu offering three GGUF models — `nemotron-3.5-asr-streaming-0.6b`, `parakeet-unified-en-0.6b`, and `whisper-large-v3-turbo`; each downloads as `<model>-Q8_0.gguf` from `huggingface.co/handy-computer/<model>-gguf` into `~/.local/share/omega13/models`, and the recipe writes your chosen default plus `local_model_path` and `local_model_threads` straight into `config.json`.

Crucial step: the GNOME extension doesn't enable itself. Run:

```bash
gnome-extensions enable omega13@b08x.github.io
```

(On Wayland, if the extension is missing after install, log out and back in, then confirm with `gnome-extensions list` before enabling.)

There is no `just check` recipe. The Justfile defines exactly `install`, `test`, `dev`, `toggle`, `model`, `rpm-lint`, `rpm-srpm`, and `rpm-build`; environment verification is the installer's preflight step and the test suite. To remove everything, `./uninstall.sh` drives the installer's uninstall routine.

### RPM Packaging (Fedora & EPEL)

Production RPM spec files and automation tooling shipped in 2.7.5 under `packaging/rpm/`: `omega13.spec`, `python-transcribe-cpp.spec`, `python-JACK-Client.spec`, `python-dbus-next.spec`, `ydotool.spec`, the `build.sh` driver, and the systemd/D-Bus service units. The drive commands:

```bash
just rpm-lint    # validate all spec files
just rpm-srpm    # build Source RPMs
just rpm-build   # build binary RPMs
```

Under the RPM layout the unit runs `ExecStart=/usr/bin/omega13 --no-daemon` with `WantedBy=default.target`, and D-Bus activation is wired through `packaging/rpm/org.omega13.Recorder.service` with `SystemdService=omega13.service`.

## Running It

Start the daemon:

```bash
systemctl --user start omega13
systemctl --user enable omega13
```

Check the logs when it breaks:

```bash
journalctl --user -fu omega13
```

Health status arrives on a 30-second loop; a quiet journal does not by itself mean the daemon is dead.

Both daemon flags are backwards-compatibility no-ops, parsed at src/omega13/app.py:26-28 and never read afterwards — existing scripts and the service units pass `--no-daemon` on their ExecStart lines, and systemd, not Omega-13, is the daemonizer. Pass none of the control flags and `main()` runs the headless service in the foreground of its own process via `main_headless()` under a PID-file guard at `/tmp/omega13.pid`; each control flag exits over D-Bus or the PID file before that block.

## Control

Eight CLI flags exist, with these exact help strings:

| Flag | Help string |
| --- | --- |
| `--toggle` | Toggle recording on a running instance via D-Bus |
| `--stop` | Stop a running instance |
| `--retry` | Retry the last failed transcription via D-Bus |
| `--status` | Check if Omega-13 is running |
| `--daemon` | Run as background daemon (default) *(parsed for compatibility; never read — systemd is the daemonizer)* |
| `--no-daemon` | Run in foreground without daemonizing *(parsed for compatibility; never read — systemd is the daemonizer)* |
| `--config` | Launch the interactive configuration wizard |
| `--log-level` | Set logging level *(default `INFO`)* |

Send the capture signal with `omega13 --toggle`, which reaches the daemon's `ToggleRecording() -> b` method over D-Bus. The in-daemon global hotkey defaults to `<ctrl>+<alt>+space` and is normalized by `_resolve_hotkey`; on Wayland, pynput cannot capture global hotkeys reliably, and the listener logs exactly that warning — map a compositor or system-wide hotkey to `omega13 --toggle` instead.

### Settings

The config lives at `~/.config/omega13/config.json`. The only interactive configuration surface is the `--config` wizard, a `rich`-based menu covering audio input ports, the hotkey, auto-record, transcription, and output destinations. On "Exit & Apply" the wizard restarts the daemon via `systemctl --user restart omega13.service`.

```json
{
  "transcription": {
    "provider": "local",
    "server_url": "http://localhost:8080",
    "copy_to_clipboard": false,
    "inject_to_active_window": false,
    "write_to_file": false
  },
  "sessions": {
    "temp_root": "/run/user/1000/omega13",
    "default_save_location": "~/Recordings",
    "auto_cleanup_days": 7
  },
  "auto_record": {
    "enabled": false,
    "begin_threshold_db": -35.0,
    "end_threshold_db": -35.0,
    "silence_duration_seconds": 10.0
  }
}
```

Every key above matches a default in the code. Valid `transcription.provider` values: `"local"` (a downloaded GGUF model — see `just model dl`), `"whisper-server"` or `"network"` (a whisper-server reachable at `server_url`, default `http://localhost:8080`), `"groq"` (a `GROQ_API_KEY` in the environment). This is selection, not failover — see [Transcription & Models](#transcription--models).

## Workflow

Two capture modes cover the failure cases, and both end in the same session bookkeeping.

1. **Manual capture.** `omega13 --toggle` (or the `Ctrl+Alt+Space` default hotkey) calls `ToggleRecording` over D-Bus; starting a manual recording prepends the full 13-second ring — the retroactive part — and a second toggle stops it, fires `MANUAL_STOPPED`, and hands the WAV to `register_and_transcribe`.
2. **Auto-record mode.** Arming happens three ways: set `auto_record.enabled` in config (default `false`), call `SetAutoRecordEnabled(b)` on D-Bus, or flip the *Auto-Record* switch in the extension's panel menu. Once armed, the state machine watches the RMS: input crossing `begin_threshold_db` — default `-35.0` dB — starts `RECORDING_AUTO`; input staying below `end_threshold_db` — default `-35.0` dB — for `silence_duration_seconds` — default `10.0` s — stops it and re-arms. The threshold is adjustable at runtime through `SetAutoRecordThreshold(d)` or the extension slider, which maps 0..1 to −60.0..0.0 dB.
3. **Save flow.** On every stop, `register_and_transcribe` registers the WAV with the current session, and the transcription worker writes the transcript to `transcriptions/<stem>.md` in that session; audio outside a session gets a sibling `.md` file instead. Nothing in the daemon's entry chain ever calls `SessionManager.save_session` (src/omega13/session.py:294), the method that marks a session saved and copies it into `sessions.default_save_location` — `~/Recordings` by default — and its incremental helper `_sync_to_save_location` runs only after that call, so it never runs either. That is the tmpfs caveat from the Quick Start, stated at the code level.

## Session Management

Recordings accumulate under the session temp root, which defaults to `$XDG_RUNTIME_DIR/omega13` — that is, `/run/user/<uid>/omega13`. The `SessionManager` class carries its own fallback of `/tmp/omega13` when constructed without a `temp_root`, but the daemon always passes the config value, so the fallback is dead code in the deployed path. Each session directory is named `session_<YYYYMMDD_HHMMSS>_<uuid8>` and split into `recordings/` and `transcriptions/` subdirectories.

Cleanup is bounded: `SessionManager.cleanup_old_sessions(days=7)` sweeps by comparing directory mtimes against a days-scaled cutoff — but nothing in the daemon's entry chain calls it, so under the shipped service sessions persist until the OS reclaims the temp root; `$XDG_RUNTIME_DIR` is tmpfs that systemd clears when your last session ends.

When auto-record triggers back-to-back clips, `Session.add_transcription` runs suffix-prefix overlap deduplication: it joins the last five transcriptions into a word history, computes the longest suffix of that history matching a prefix of the new text, stores only the unique remainder, and skips a transcription entirely at 100% overlap. It is a text-level heuristic, not a semantic one — the session's own output feeding back on itself — it prevents duplicate sentences when the RMS threshold flaps, nothing more. Failed transcriptions are tracked in a `failed_transcriptions.json` manifest under the temp root, capped at the ten most recent entries.

## Transcription & Models

Transcription in 2.7.5 is *provider selection, not a fallback chain* (src/omega13/headless_service.py:514-551). The daemon reads `transcription.provider` from config and constructs exactly one provider:

- `"local"` builds a `GgufTranscriptionProvider` that runs an in-process GGUF model through the `transcribe-cpp` Python bindings;
- `"whisper-server"` or `"network"` builds a `LocalTranscriptionProvider` that POSTs the WAV to your whisper-server;
- `"groq"` builds a `GroqTranscriptionProvider` against `https://api.groq.com/openai/v1/audio/transcriptions`.

Setting `streaming_mode: true` replaces even that single provider with `StubStreamingProvider`.

A failover loop does exist — `TranscriptionService._transcribe_file` iterates `self.providers` and tries each in turn — which sounds like a cascade, but the list it iterates holds exactly one provider: each config branch appends a single entry. The loop is real structure anticipating a provider hierarchy that the current selection semantics never populate — a reader extending the code to multiple providers would be filling in a level the architecture already expects. What actually recovers a job is the retry wrapper: `max_retries = 3` attempts with the timeout scaled as `self.timeout * (1 + 0.5 * retry_count)` — baseline 600 s, then 900, then 1200. Timeouts back off for `2^retry` seconds plus jitter, retryable transcription errors for `4^retry` seconds plus jitter.

How models are acquired: `just model dl`, described under [Setup](#setup), downloads `*-Q8_0.gguf` files into `~/.local/share/omega13/models` and records the default in config. The matching defaults in code are `local_model_path = ~/.local/share/omega13/models`, `local_model_name = "ggml-base.en.bin"`, and `local_model_threads = 4`. If the GGUF file is missing at startup, the daemon logs an error naming the expected path and telling you to run `just model dl`.

## The Architecture

This is a headless daemon first; the UI is an overlay. Four components carry the load:

- **Audio Engine** (`src/omega13/audio.py`). Hooks into JACK through the `Omega13` client; captures raw float32 into a ring buffer sized `samplerate * 13`; the JACK callback is zero-allocation, drawing on pre-allocated scratchpads and a 2000-block buffer pool.
- **State Machine** (`src/omega13/recording_controller.py`). Five states — `IDLE`, `ARMED`, `RECORDING_MANUAL`, `RECORDING_AUTO`, `STOPPING` — and seven events — `AUTO_STARTED`, `AUTO_STOPPED`, `MANUAL_STARTED`, `MANUAL_STOPPED`, `SILENCE_DETECTED`, `SIGNAL_DETECTED`, `STATE_CHANGED`. The controller keeps its own transition table in its class docstring (src/omega13/recording_controller.py:40-52); it is quoted verbatim so the code maintains the claim:

  ```text
  IDLE → enable_auto_record() → ARMED
  ARMED → signal > begin_threshold → RECORDING_AUTO
  ARMED → manual_start() → RECORDING_MANUAL
  RECORDING_AUTO → silence > duration → STOPPING → ARMED
  RECORDING_AUTO → manual_stop() → STOPPING → ARMED
  RECORDING_MANUAL → silence > duration → STOPPING → IDLE
  RECORDING_MANUAL → manual_stop() → STOPPING → IDLE
  ARMED → disable_auto_record() → IDLE
  RECORDING_* → disable_auto_record() → STOPPING → IDLE
  ```

  RMS-based silence detection controls the auto transitions; `SignalDetector` computes RMS over a 100 ms window and exposes the per-channel `rms_levels` array.
- **IPC & D-Bus.** Wayland is locked down, so Omega-13 speaks two distinct D-Bus domains:
  - `org.omega13.Recorder` — the daemon's public interface, published under bus name `org.omega13.Recorder` at object path `/org/omega13/Recorder`. It provides methods `ToggleRecording() -> b`, `RetryTranscription() -> b`, `RetryFailedTranscriptions() -> i`, `GetFailedTranscriptionCount() -> i`, `SetAutoRecordEnabled(b)`, `SetAutoRecordThreshold(d)`, `SetOSDEnabled(b)`, `GetState() -> s`, and `GetHealth() -> a{sv}`; it emits the signals `RecordingToggled(b)`, `OSDStateChanged(ssi)`, and `HealthStatus(a{sv})`. The health signal fires on a 30-second loop.
  - `org.gnome.Shell.Extensions.Omega13` — the GNOME extension's interface, exported at object path `/org/gnome/Shell/Extensions/Omega13` on the GNOME Shell process's own session-bus connection. The extension owns no bus name of its own, which is why callers address the Shell's well-known name `org.gnome.Shell` — exactly how the injection module calls it.
- **Output Routing.** `ydotool` for text injection (requires `/dev/uinput` and a running `ydotoold`), pyperclip for the clipboard, native file I/O for the daily markdown note. All of it runs inside the transcription worker thread after a transcript returns.

## Abstraction Leaks & Trade-offs

If you're building functional Linux desktop tools right now, you're going to hit the Wayland security model. Here's where I ran into trouble and how the code handles it:

- **Targeted window injection.** Injecting long-winded transcriptions into whatever window happens to be active is dangerous; if you get distracted and change focus, you dump a paragraph into a terminal session. So injection strictly targets a scratchpad application titled "Whisp" through a three-step focus chain: first `busctl` calls `FocusWindow s "Whisp"` on the Omega-13 extension; second, `de.lucaswerkmeister.ActivateWindowByTitle.activateBySubstring`; third, a `org.gnome.Shell.Eval` JavaScript actor search that requires unsafe mode. If all three fail, injection aborts entirely before any typing occurs — a fail-safe, not a best-effort. Before typing, the text is preprocessed: a trailing "return" becomes two newlines, a trailing "new line" becomes one. The typing itself is `ydotool type --key-delay 2 --key-hold 2` under a 300-second timeout.
- **OSD subprocess model & fallbacks.** The daemon cannot draw on the screen, so it delegates sight to processes it spawns — the three OSD tiers are three levels at which the desktop can see itself. Native GTK4 Layer Shell (`zwlr_layer_shell_v1`) does not work on Mutter, so `OSDManager.start_subprocess` skips the GTK4 subprocess entirely when `XDG_CURRENT_DESKTOP` contains "GNOME". On non-GNOME compositors it spawns `python -m omega13.osd_process` — the OSD runs as a separate `Gtk.Application` process (id `org.omega13.osd.process`) so its GLib loop stays out of the daemon's threads; the subprocess bootstraps through the same `omega13.ui.osd._lazy_init()` entry the daemon uses, the same code instantiated twice as daemon and observer. The subprocess receives state updates over D-Bus, not standard input: it installs an AddMatch rule for the daemon's `OSDStateChanged` signal and repaints on arrival. On GNOME the Cairo OSD lives in the extension instead; where neither surface is available, the manager falls back to `notify-send`-style desktop notifications with sound cues. With neither `WAYLAND_DISPLAY` nor `DISPLAY` set, the OSD disables itself.
- **Audio routing.** You need JACK or the `pipewire-jack` bridge. At startup the daemon connects your saved input ports, and when none are saved it resolves the PulseAudio default source with `pactl get-default-source` and matches it against JACK capture ports. If your audio graph is mis-wired at the system level, you capture silence — and the daemon reports the condition instead of masking it: `ToggleRecording` raises `org.omega13.Recorder.NoAudioActivity` when there is neither recent signal nor any connected port. The daemon can't fix your routing.

## Failure Recovery

Moving from a TUI application to a headless daemon surfaced some architectural gaps that have since been engineered around:

- **Transcription failures & retries.** A failed provider call records the WAV path in the failed-transcriptions manifest, and two D-Bus methods recover it: `RetryTranscription() -> b` re-queues the *last* failed buffer, and `RetryFailedTranscriptions() -> i` re-queues *every* manifest entry and returns the count. From the CLI, `omega13 --retry` sends the singular retry over D-Bus. The GNOME extension's tray item — *Retry failed transcription (N)* — calls the *plural* `RetryFailedTranscriptions`, not `RetryTranscription`; it polls `GetFailedTranscriptionCount() -> i` every 2000 ms and renders the count in the label, turning it red and bold when the count exceeds zero.
- **The `ydotool` stuck-key bug.** There is a known bug where a pipeline failure mid-keystroke leaves `ydotoold` holding a logical key down. Omega-13 wraps the entire typing path in a recovery block: on ydotool failure, timeout, or unexpected exception it executes `systemctl --user restart ydotoold` to clear the stuck-key state at the system level.

## Development

Use `uv sync` to grab dependencies (`uv.lock` pins them); run `pytest` — or `just test`, which wraps pytest in `dbus-run-session` when that helper is available. The suite spans 22 test files with 144 test functions, of which `test_baseline_measurements.py` contributes none — it is a measurement script pytest collects but finds no tests in. A single test runs as:

```bash
uv run pytest "tests/test_headless_acceptance.py::test_dbus_toggle_starts_recording" -v
```

The D-Bus acceptance file patches `omega13.headless_service.AudioEngine` at its seam, so no live audio graph is needed for state-machine logic. Test-suite conventions live in `tests/AGENTS.md`. For a foreground dev run, `just dev` executes `uv run omega13 --no-daemon`. The package builds with the hatchling backend and exposes the single console script `omega13 = "omega13.app:main"`.

## License

Omega-13 is released under the [MIT License](LICENSE) — Copyright (c) 2026 b08x. Release history lives in [CHANGELOG.md](CHANGELOG.md).

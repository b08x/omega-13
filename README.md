# Omega-13

Short version: A retroactive audio daemon. It continuously buffers 13 seconds of audio in memory. When triggered, it stops, transcribes the buffer (locally or via Groq), and routes the text to your clipboard, a dedicated scratchpad window, or an Obsidian daily note.

What it is: The daemon runs a JACK/PipeWire client in a background systemd service. It maintains a circular ring buffer in memory. On capture, it pulls the segments, reconstructs a linear WAV, downsamples it for Whisper via `ffmpeg`, and fires it off to a local HTTP server or the cloud. No re-recording. Zero disk I/O until capture.

---

## The Origin Story

The baseline inspiration for this was Steve Harris's `time machine`—an old JACK application with a GTK2 overlay that captured the last 10 seconds of the audio buffer when you hit record. He built it to emulate an old mini-disc recorder for studio riffing.

I applied that concept to a dictation pipeline. If I start rambling into the microphone to capture notes and forget to hit the hotkey, the thought is gone. It's a frustrating failure point. I wanted to see how large a buffer I could maintain without impacting system performance. I bumped it from 10 to 13 seconds with nominal impact. (As for the name: while brainstorming the hotkey toggle flow, my partner pointed out the 13-second rollback sounded exactly like the Omega-13 device from *Galaxy Quest*).

However, I haven't worked out the math yet for sustaining a much longer buffer without affecting the pipeline flow, and there are definitely times I've neglected to hit the button for more than 13 seconds. That gap is why the **auto-record** threshold was implemented. By combining a 13-second retroactive buffer for manual triggers, an auto-record threshold for longer rambles, and immediate saves to temporary space, the system covers the major failure modes where dictation would otherwise be lost.

---

## The Architecture

This is built as a headless daemon first. The UI is just an overlay. 

- **Audio Engine**: Hooks into JACK. Captures raw float32 into a ring buffer.
- **State Machine**: Idle -> Armed -> Recording -> Stopping. RMS-based silence detection controls the transitions.
- **IPC**: Wayland is locked down. I use D-Bus (`org.gnome.Shell.Extensions.Omega13`) to bypass keyboard focus restrictions and `SIGUSR1` for dumb hotkey triggers. I map these to a physical Nuance Dictaphone device to paste, undo, and swap windows.
- **Output Routing**: `ydotool` for text injection (requires `/dev/uinput`), `pyperclip` for clipboard, native file I/O for Obsidian. In a forked process, outputs happen concurrently.

## Abstraction Leaks & Trade-offs

If you're building functional Linux desktop tools right now, you're going to hit the Wayland security model. Here's where I ran into trouble and how I decided to handle that:

- **Targeted Window Injection**: Injecting long-winded transcriptions into whatever window happens to be active is dangerous. If you get distracted and change focus, you might dump a paragraph into a terminal session. Instead, text injection strictly targets a specific ephemeral scratchpad application called "Whisp". To achieve this on Wayland, I had to generate a native GNOME Shell Extension just to expose a D-Bus method (`FocusWindow`). If the Whisp window isn't found, injection fails safely.
- **OSD Fallbacks**: Native GTK4 Layer Shell (`zwlr_layer_shell_v1`) doesn't work on Mutter (GNOME). So I built a 3-tier fallback: GNOME extension first (Cairo overlay), GTK4 Layer Shell for wlroots (Hyprland/Sway), and transient `notify-send` for everything else.
- **Audio Routing**: You need JACK or `pipewire-jack`. If your audio graph isn't wired right at the system level, you capture silence. The daemon can't fix your routing.

---

## Requirements

- Python 3.12+ (managed by `uv`)
- JACK or PipeWire-JACK bridge running
- `ydotool` + `ydotoold` daemon (if you want text injection)
- GNOME Shell >= 45 (for the native OSD and window focus bypass)
- A running `whisper-server` (or Groq API key in your env)

---

## Setup

The installation is managed via `just`. No `sudo` needed. 

```bash
git clone https://github.com/b08x/omega-13.git
cd omega-13
just install
```

What it actually does under the hood:
1. Bootstraps a virtualenv with `uv` and installs dependencies.
2. Dynamically evaluates hardware (CUDA, Vulkan) and compiles `transcribe-cpp` with appropriate acceleration flags (`CMAKE_ARGS`).
3. Compiles and enables `ydotool` as a user service if it's missing.

To download models, use the dedicated command:
```bash
just model dl
```
This launches a `gum`-based interactive UI presenting a menu of available GGUF models from HuggingFace (e.g. Parakeet, Nemotron, Whisper Turbo). You pick the ones you want, it downloads them into `~/.local/share/omega13/models`, and prompts you to select your default. It writes those choices into `config.json`. Zero manual `wget` nonsense required.

**Crucial step**: The GNOME extension doesn't enable itself. You have to run:
```bash
gnome-extensions enable omega13@b08x.github.io
```
*(On Wayland, you might need to log out and back in before the extension registers.)*

To verify your environment has all the necessary dependencies installed (including `ffmpeg`, `sox`, `ydotool`, `gum`, `JACK`, `GTK4 Layer Shell`, etc.), you can run:
```bash
just check
```

---

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

Debug in the foreground:
```bash
omega13 --no-daemon
```

## Control

Send the signal to trigger capture:
```bash
omega13 --toggle
```
Map `omega13 --toggle` to a global hotkey in your compositor.

### Settings

The config lives at `~/.config/omega13/config.json`. The Settings screen (`p`) handles most options at runtime if you run it interactively. For a headless setup, just edit the JSON and restart the service.

```json
{
  "transcription": {
    "provider": "local",
    "server_url": "http://localhost:8080",
    "inject_to_active_window": false
  },
  "auto_record": {
    "enabled": false,
    "begin_threshold_db": -35.0,
    "end_threshold_db": -35.0,
    "silence_duration_seconds": 10.0
  }
}
```

---

## Workflow

Using Omega-13 fits into a few distinct modes depending on how you've configured your compositor and `auto_record` settings:

1. **Manual Capture**: Map `omega13 --toggle` (or the internal `Ctrl+Alt+Space` hotkey) to trigger a 13-second retroactive recording. This is the core workflow for capturing something you *just* heard or said.
2. **Auto-Record Mode**: Press `a` (if running interactively) to arm the state machine. When the input audio crosses the `-35.0 dB` threshold, recording starts. When it drops below the threshold for a set silence duration, it stops, transcribes, and re-arms itself automatically.
3. **Transcription & Output**: By default (`auto_transcribe: true`), saving a capture automatically kicks off the transcription process. The text is sent concurrently to multiple destinations: it can be injected into the target "Whisp" window via `ydotool`, copied to the clipboard, and appended to an Obsidian daily note notebook.

---

## Session Management

Recordings accumulate in `/tmp/omega13/`. When you save (e.g., by pressing `s` in the interactive UI or via D-Bus/hotkeys), they move to permanent storage. 

The session manager runs suffix-prefix overlap deduplication if auto-record triggers back-to-back clips. It's a text-level heuristic. It's not perfect, but it prevents duplicate sentences in your notes when the RMS threshold flaps.

---

## Transcription & Models

The daemon operates with a resilient fallback chain for transcription. If configured, it attempts to use a local, in-process GGUF model via python bindings for `transcribe.cpp` ([github.com/handy-computer/transcribe.cpp](https://github.com/handy-computer/transcribe.cpp)) directly on bare metal. If that fails (or isn't installed), it seamlessly falls back to a REST API provider (either a local `whisper-server` or Groq in the cloud).

**How models are acquired:**
The `just install` target handles the heavy lifting. It uses `ldconfig -p` and `nvidia-smi` to sniff out your GPU hardware. If it finds a CUDA-compatible card or Vulkan runtime, it configures `transcribe-cpp` with hardware acceleration flags (`CMAKE_ARGS`).
After installation, you run `just model dl` to download models directly into `~/.local/share/omega13/models` interactively.

---

## Roadmap: RPM Packaging

Ultimately, Omega-13 will transition away from virtual environments to a native RPM package format. Doing so provides several crucial benefits:
1. **No Virtual Environments**: Once packaged as an RPM, the Python source drops directly into the system's `/usr/lib/python3.X/site-packages/`. We bypass PEP 668 and let `dnf` track the installed assets natively.
2. **First-class Dependencies**: System requirements (like `ffmpeg`, `sox`, `pipewire-jack`, `gtk4-layer-shell`, `ydotool`) will simply be standard `Requires:` declarations in the `.spec` file.
3. **Automated Placements**: D-Bus interface configs, systemd user service unit files, and GNOME extension directories will be installed deterministically.

Future iterations will incorporate Fedora's standard Python packaging macros (`%pyproject_buildrequires`, `%pyproject_install`) to cleanly bridge the gap between `hatchling` and the OS package manager.


## Failure Recovery

Moving from a TUI application to a headless daemon surfaced some architectural gaps that have since been engineered around:

- **Transcription Failures & Retries**: As a headless daemon, a failed REST API call silently breaks the dictation flow. To counter this, the GNOME extension provides a system tray menu with a "Retry failed transcription" action. This triggers a D-Bus method (`org.omega13.Recorder.RetryTranscription`) that re-queues the last failed buffer. You can also trigger this via the CLI: `omega13 --retry`.
- **The `ydotool` Stuck-Key Bug**: There is a known underlying bug in `ydotool` where if the pipeline fails while actively sending a keystroke, the daemon gets stuck holding that logical key down. To mitigate this, the text injection logic is wrapped in a recovery block. If `ydotool` times out or fails, Omega-13 automatically executes `systemctl --user restart ydotoold` to clear the stuck key state at the system level.

---

## Development

Use `uv sync` to grab deps. Run `pytest`. 

Most tests mock JACK so you don't need a live audio graph to verify the state machine logic. Integration tests will require the `whisper-server` and a real JACK connection.

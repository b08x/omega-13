# Omega-13

> Retroactive audio capture — holds 13 seconds in a ring buffer, transcribes on demand, routes the result wherever it needs to go.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![uv](https://img.shields.io/badge/managed%20by-uv-7c3aed)](https://github.com/astral-sh/uv)

---

## Features

- **Retroactive ring buffer** — continuously holds 13 seconds of JACK/PipeWire audio in memory; saving reconstructs a linear WAV from circular segments with zero re-recording
- **Local or cloud transcription** — routes audio to a self-hosted `whisper-server` (HTTP) or the Groq Whisper API; provider and credentials switch at runtime via the Settings screen
- **Auto-record mode** — RMS-based voice-activity detection arms recording when signal crosses a configurable dB threshold and stops automatically after a configurable silence window
- **Session management** — recordings accumulate in a timestamped temp session under `/tmp/omega13/`; the session saves to permanent storage on demand, with incremental sync for recordings added after the initial save
- **Multi-destination output** — transcription results can be written to a Markdown file, copied to the clipboard, typed into the active Wayland window via `pynput`, or appended to an Obsidian daily note
- **Wayland-native IPC** — the app writes a PID file and handles `SIGUSR1` so external tools (compositor hotkey daemons, D-Bus clients) can trigger recording without requiring keyboard focus
- **Overlap deduplication** — when auto-record produces consecutive clips with shared audio, the session de-duplicates transcriptions by matching word-level suffix–prefix overlaps before appending

---

## Requirements

- Linux with JACK or PipeWire-JACK bridge running
- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv) for dependency management
- For local transcription: a running `whisper-server` instance (default: `http://localhost:8080`)
- For cloud transcription: a Groq API key (set via `GROQ_API_KEY` environment variable)
- For Obsidian daily note integration: `obsidian-cli` installed and configured

---

## Installation

<details open>
<summary>System-wide User Installation (Recommended)</summary>

Omega-13 provides an interactive, XDG-compliant installer powered by [gum](https://github.com/charmbracelet/gum). It safely installs to your local user directories without requiring `sudo`.

```bash
git clone https://github.com/b08x/omega-13.git
cd omega-13
./install.sh
```

The installer will:
1. Copy the application to `~/.local/share/omega13`
2. Create a Python virtual environment and install dependencies
3. Symlink the executable to `~/.local/bin/omega13`
4. Register a systemd user service at `~/.config/systemd/user/omega13.service`

You can safely remove the installation at any time by running `./uninstall.sh`.
</details>

<details>
<summary>Development Setup (From source)</summary>

```bash
git clone https://github.com/b08x/omega-13.git
cd omega-13
uv sync
```
</details>

<details>
<summary>Docker (whisper-server)</summary>

A `compose.yml` is included for running the whisper-server dependency:

```bash
docker compose up -d
```

This brings up a GPU-accelerated whisper-server on port 8080. Adjust the model in `compose.yml` as needed.

</details>

---

## Usage

Omega-13 is designed to run as a **background daemon via systemd**. It features a native **GTK4 Layer Shell OSD** that displays recording and transcription status directly on your screen (Wayland/Hyprland supported).

### Managing the Daemon

```bash
# Start the daemon
systemctl --user start omega13

# Enable to run automatically on login
systemctl --user enable omega13

# Check logs
journalctl --user -fu omega13
```

You can also run it manually from the terminal for debugging:

```bash
omega13 --no-daemon
```



### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` / global hotkey | Capture last 13 seconds |
| `a` | Toggle auto-record mode |
| `t` | Manually trigger transcription |
| `c` | Toggle clipboard copy |
| `j` | Toggle text injection to active window |
| `d` | Toggle Obsidian daily note output |
| `i` | Open input port selector |
| `n` | Start a new session |
| `s` | Save current session to permanent storage |
| `p` | Open transcription settings |
| `q` | Quit |

The global hotkey defaults to `Ctrl+Alt+Space` and can be changed in `~/.config/omega13/config.json`.

### Examples

```bash
# Start the daemon via systemd
systemctl --user start omega13

# Run in foreground mode (for debugging)
omega13 --no-daemon

# Trigger a capture from an external script (e.g., a Hyprland keybind)
omega13 --toggle

# Override Groq API key at runtime
GROQ_API_KEY=gsk_... omega13 --no-daemon
```

---

## Configuration

Config lives at `~/.config/omega13/config.json` and is written on first run with defaults. The Settings screen (`p`) handles most options at runtime; manual edits require a restart.

```json
{
  "input_ports": ["system:capture_1", "system:capture_2"],
  "save_path": "/home/user/Recordings",
  "global_hotkey": "<ctrl>+<alt>+space",
  "transcription": {
    "provider": "local",
    "server_url": "http://localhost:8080",
    "inference_path": "/inference",
    "groq_model": "whisper-large-v3-turbo",
    "auto_transcribe": true,
    "copy_to_clipboard": false,
    "inject_to_active_window": false,
    "write_to_daily_note": false
  },
  "auto_record": {
    "enabled": false,
    "begin_threshold_db": -35.0,
    "end_threshold_db": -35.0,
    "silence_duration_seconds": 10.0
  },
  "sessions": {
    "temp_root": "/tmp/omega13",
    "default_save_location": "/home/user/Recordings",
    "auto_cleanup_days": 7
  }
}
```

### Configuration Options

**Transcription**

- `provider`: Transcription backend — `"local"` (whisper-server) or `"groq"`
- `server_url`: Base URL for the local whisper-server (default: `"http://localhost:8080"`)
- `inference_path`: Endpoint path on the local server (default: `"/inference"`)
- `groq_model`: Groq model identifier (default: `"whisper-large-v3-turbo"`)
- `auto_transcribe`: Automatically transcribe after each capture (default: `true`)
- `copy_to_clipboard`: Copy result text to clipboard after transcription (default: `false`)
- `inject_to_active_window`: Type result into the focused Wayland window (default: `false`)
- `write_to_daily_note`: Append result to the current Obsidian daily note (default: `false`)

**Auto-Record**

- `begin_threshold_db`: RMS level above which recording starts (default: `-35.0`)
- `end_threshold_db`: RMS level below which the silence timer starts (default: `-35.0`)
- `silence_duration_seconds`: Seconds of silence before auto-stop (default: `10.0`)

**Sessions**

- `temp_root`: Working directory for in-progress sessions (default: `"/tmp/omega13"`)
- `default_save_location`: Destination for saved sessions (default: `~/Recordings`)
- `auto_cleanup_days`: Age in days before unsaved temp sessions are pruned (default: `7`)

---

## Session Structure

Each saved session is a directory under the configured save location:

```
omega13_session_2024-01-15_10-30-00/
├── session.json          # metadata: timestamps, recording list, transcriptions
├── recordings/
│   ├── 001.mp4
│   └── 002.mp4
└── transcriptions/
    ├── 001.md
    └── 002.md
```

Sessions accumulate incrementally — recordings added after an initial save are synced to the permanent location automatically.

---

## Auto-Record Mode

Pressing `a` arms the auto-record state machine. From that point:

1. Signal above `begin_threshold_db` triggers a capture automatically
2. When the signal drops below `end_threshold_db`, a silence countdown begins
3. After `silence_duration_seconds` of continuous silence, the recording stops and (if `auto_transcribe` is on) transcription starts
4. The system returns to armed state, ready for the next event

Recordings with average RMS below -50 dB (near-silence false triggers) are discarded silently before transcription begins.

---

## Bootstrap

`bootstrap.sh` handles system dependencies and the local Python environment.

```bash
cd omega-13
./bootstrap.sh
```

After bootstrap, activate the environment if needed and launch the app.

---


## First Run

Complete these steps in order. After this, the app is running and controllable from the command line.

1. Ensure the daemon is running
2. Verify its status
```bash
systemctl --user start omega13
```

### 2. Verify its status

Check the service status:

```bash
systemctl --user status omega13
```

You should see it marked as `active (running)`.


### 4. Send a test control command

Toggle recording:

```bash
omega13 --toggle
```

If the daemon is running on Wayland, you should see the GTK4 OSD popup indicating recording status!

## Development

Most tests mock the full app and JACK-dependent audio engine so they run without hardware:

```bash
```

The `tests/` directory also includes demo and integration scripts that do require real JACK access and a reachable `whisper-server`.

---

## Contributing

Issues and pull requests are welcome. For significant changes, opening an issue first to discuss the approach tends to save iteration time.

---

## License

MIT

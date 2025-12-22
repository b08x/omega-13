# Omega-13

**Retroactive Audio Recording for JACK & PipeWire with Session Management**

Omega-13 is a retroactive audio recording tool designed to salvage the verbal drafts of your work. It continuously maintains a 10-second rolling buffer of audio—press a button at any moment to save what you just said, plus everything that follows. It is purpose-built for capturing ad-hoc technical notes, architectural brainstorms, and verbal planning sessions. Instead of losing a complex explanation or a fleeting solution to the air, Omega-13 ensures you can retroactively commit your spoken thoughts to storage.

> I used to always keep a minidisc recorder in my studio running in a mode where when you pressed record it wrote the last 10 seconds of audio to the disk and then caught up to realtime and kept recording. The recorder died and haven't been able to replace it, so this is a simple jack app to do the same job. It has the advantage that it never clips and can be wired to any part of the jack graph.
>
> The idea is that I doodle away with whatever is kicking around in my studio and when I heard an interesting noise, I'd press record and capture it, without having to try and recreate it. :)
>
> — Steve Harris, creator of TimeMachine

> "It appears to be some sort of weapon... but we have never been able to discover its function."
>
> — Mathesar, Galaxy Quest

## ✨ Features

- **🕐 Retroactive Recording** - Always recording the last 10 seconds in memory, ready to save instantly

- **💾 Session Management** - Recordings saved to temporary sessions, only persisted when you choose

- **🎚️ Pro Audio Integration** - Seamless routing with JACK or PipeWire's JACK compatibility layer

- **📊 Real-time Metering** - Live dB level visualization with color-coded VU meters

- **🎧 Multi-channel Support** - Record in mono or stereo with flexible port selection

- **🔒 Save Protection** - Exit prompt prevents accidental loss of unsaved recordings

- **⚙️ Persistent Configuration** - Remembers your input ports and save directory across sessions

- **🖥️ Terminal UI** - Clean, reactive text-based interface built with Textual

- **🧹 Auto-cleanup** - Automatically removes old temporary sessions (7 days default)

## 📋 Prerequisites

- **Operating System**: Linux

- **Python**: 3.12 or higher

- **Audio Server**: A running JACK server **OR** PipeWire with `pipewire-jack` installed

- **System Libraries**:

  - `libjack` (or the PipeWire equivalent `pipewire-jack-audio-connection-kit`)

  - `libsndfile` (for WAV file I/O)

### Audio Backend Installation

Omega-13 interacts with the JACK API. You can provide this API via the classic JACK2 server or the modern PipeWire implementation.

**Option A: PipeWire (Fedora Workstation, Ubuntu 22.10+)**

If you are on a standard modern distribution, you likely already use PipeWire. You just need the JACK compatibility libraries.

**Fedora (Standard):**

```bash
sudo dnf install pipewire-jack-audio-connection-kit pipewire-jack-audio-connection-kit-libs
```

**Fedora Atomic (Silverblue, Bluefin, Kinoite):**

If you are running an immutable desktop, you have two choices: use a mutable container (Toolbox/Distrobox) or layer the packages onto your base image.

- Method 1: Toolbox (Recommended)

    Inside your development container:

    ```bash
    sudo dnf install pipewire-jack-audio-connection-kit pipewire-jack-audio-connection-kit-libs libsndfile
    ```

- Method 2: Layering (Host)

    If you must install on the host:

    ```bash
    rpm-ostree install pipewire-jack-audio-connection-kit pipewire-jack-audio-connection-kit-libs
    # Reboot required
    ```

**Ubuntu/Debian:**

```bash
sudo apt install pipewire-jack
```

**Option B: Classic JACK2**

If you strictly use legacy JACK2 without PipeWire:

**Fedora/RHEL:**

```bash
sudo dnf install jack-audio-connection-kit
```

**Ubuntu/Debian:**

```bash
sudo apt install jackd2 libjack-jackd2-dev
```

**Arch Linux:**

```bash
sudo pacman -S jack2
```

## 🚀 Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/yourusername/omega-13.git
    cd omega-13
    ```

2. **Setup the Transcription Server (Optional):**

    If you want the "AI" to actually listen to you (and let's be honest, who doesn't want a machine judging their audio?), you'll need the Whisper server running.

    - **Option A: The Shell Script**

        ```bash
        cd whisper-server
        ./build-whisper-image.sh
        cd ..
        ```

    - **Option B: The Composer** (For the sophisticated Podman user)

        ```bash
        cd whisper-server
        podman-compose up --build -d
        cd ..
        ```

3. **Install the Application:**

    We use `uv` because life is too short for slow package managers.

    ```bash
    uv sync
    ```

    _If you insist on living in the past, `python -m venv .venv && source .venv/bin/activate && pip install -e .` still works, I guess._

## ⚡ Quick Start

1. **Ensure your Audio Server is ready**:

    - **Classic JACK Users**: Start your server:

        > **Note**: On Bluefin/Silverblue, pw-jack is often required to correctly map the libraries if they aren't in the standard linker path.

        ```bash
        jackd -d alsa -r 48000 -p 512
        ```

2. **Launch Omega-13:**

    ```bash
    uv run python -m omega13
    ```

3. **Configure your audio input:**

    - Press `I` to open the input selection dialog

        - Choose mono or stereo mode

        - Select your desired output ports (audio sources)

4. **Record in your session:**

    - Press `SPACE` to begin recording

    - The 10-second buffer is automatically included

    - Press `SPACE` again to stop (recording added to session)

    - Recordings are named sequentially: `001.wav`, `002.wav`, etc.

5. **Save your session:**

    - Press `S` to save session to permanent storage

    - Choose destination directory

    - All recordings copied with metadata

6. **Exit safely:**

    - Press `Q` to quit

    - If session has unsaved recordings, you'll be prompted:

        - **Save** - Choose location and save before exiting

        - **Discard** - Delete recordings and exit

        - **Cancel** - Return to app

## 🎹 Usage Guide

### Keybindings

| Key | Action |
|-----|--------|
| SPACE | Start/Stop recording |
| I | Select Input ports |
| S | Save session to permanent storage |
| T | Manually transcribe last recording |
| Q | Quit (prompts to save if needed) |

### Understanding the UI

When you launch Omega-13, you'll see several key interface elements:

```
┌─ Status ───────────────────────────┐
│ ● RECORDING / ○ IDLE               │
└────────────────────────────────────┘

┌─ Session ──────────────────────────┐
│ 2 recording(s) - Unsaved           │
└────────────────────────────────────┘

┌─ Audio Levels ─────────────────────┐
│ L: ████████████░░░░ -12.3 dB       │
│ R: ██████████████░░ -8.5 dB        │
└────────────────────────────────────┘

┌─ Connection ───────────────────────┐
│ Inputs: capture_1 | capture_2      │
└────────────────────────────────────┘

┌─ Buffer Status ────────────────────┐
│ Pre-record buffer: 100% filled     │
└────────────────────────────────────┘

```

**Status Bar:**

- Shows current recording state (RECORDING/IDLE)

- Updates in real-time

**Session Status:**

- Shows number of recordings in current session

- Indicates saved/unsaved state

- Updated after each recording

**VU Meters:**

- Visual bar graphs showing audio levels

- Numeric dB values for precise monitoring

- Color-coded: Green (safe), Yellow (moderate), Red (clipping)

- Updates 20 times per second for responsive feedback

**Connection Status:**

- Displays currently selected input ports

- Shows channel routing (mono or stereo)

- Press `I` to reconfigure

**Buffer Fill Indicator:**

- Shows pre-record buffer status

- Reaches 100% after 10 seconds of runtime

- Recording before 100% includes whatever buffer has accumulated

### Session Workflow

Omega-13 uses a **session-based workflow** to protect your recordings:

```
Launch → Create Session → Record → Save Session
         ↓                         ↓
    (Temp Storage)          (Permanent Storage)

```

**1. Session Creation (Automatic)**

- New session created automatically on launch

- Unique session ID: `session_20251221_143045_a3f7b9c1`

- Temporary directory: `/tmp/omega13/<session_id>/`

**2. Recording to Session**

- Each recording saved to session temp directory

- Sequential naming: `001.wav`, `002.wav`, `003.wav`, etc.

- Session metadata tracked in `session.json`

**3. Saving Session**

- Press `S` to save session permanently

- Choose destination directory

- Creates timestamped folder: `omega13_session_2025-12-21_14-30-45/`

- All recordings and metadata copied

**4. Exit Behavior**

- If session saved or empty: Clean exit

- If unsaved recordings exist: Prompt appears

  - **Save** - Choose location and save

  - **Discard** - Delete temp files

  - **Cancel** - Return to app

### Configuring Audio Inputs

When you press `I`, you'll go through a two-step process:

**Step 1: Channel Mode Selection**

- **Mono**: Records a single channel from one output port

- **Stereo**: Records two channels from two separate output ports

**Step 2: Port Selection**

- Browse available output ports (audio sources)

- Common ports include:

  - `system:capture_X` - Physical audio interface inputs

  - `application_name:output_X` - Software output from other apps

- Select different ports for left/right channels in stereo mode

- Can't select the same port twice in stereo mode

**Port Naming Convention:**

```
client_name:port_name
```

**Examples (PipeWire):**
- `ALSA:capture_FL` - Physical input Left
- `Firefox:output_FL` - Browser output

**Examples (Classic JACK):**
- `system:capture_1` - Physical input 1
- `ardour:master/out_1` - Ardour DAW master output

### Session File Structure

After saving a session, the directory structure looks like this:

```
~/Recordings/omega13_session_2025-12-21_14-30-45/
├── recordings/
│   ├── 001.wav          # First recording
│   ├── 002.wav          # Second recording
│   └── 003.wav          # Third recording
├── transcriptions/      # Optional: AI transcriptions
│   ├── 001.txt
│   └── 002.txt
└── session.json         # Session metadata

```

**session.json Example:**

```json
{
  "session_id": "session_20251221_143045_a3f7b9c1",
  "created_at": "2025-12-21T14:30:45.123456",
  "recordings": [
    {
      "filename": "001.wav",
      "timestamp": "2025-12-21T14:30:50.000000",
      "duration_seconds": 45.2,
      "channels": 2,
      "samplerate": 48000
    }
  ],
  "saved": true,
  "save_location": "/home/user/Recordings/omega13_session_2025-12-21_14-30-45"
}
```

### Audio File Details

- **Format:** Uncompressed WAV (PCM)
- **Sample Rate:** Inherited from server configuration (typically 44.1kHz or 48kHz)
- **Channels:** 1 (mono) or 2 (stereo) based on your selection
- **Bit Depth:** 32-bit float (preserves full dynamic range)

**Sequential Naming:**

- First recording: `001.wav`

- Second recording: `002.wav`

- And so on...

**Why Sequential Numbers?**

- Simpler than timestamps within a session

- Clear recording order

- Session metadata contains actual timestamps

## 🔧 How It Works

### The Rolling Buffer Concept

Omega-13 implements a **circular buffer** (ring buffer) that continuously stores the most recent 10 seconds of incoming audio:

1. **Always Listening:** From the moment you launch the app, audio flows into the buffer

2. **Circular Overwriting:** Old audio data is continuously replaced by new data

3. **Instant Snapshot:** When you press `SPACE`, the current buffer contents are frozen

4. **Continuous Recording:** After the buffer dump, new incoming audio is appended to the file

5. **Stop and Save:** Pressing `SPACE` again finalizes the file

<!-- end list -->

```
Time:     [-------|-------|-------|-------]
          -10s    -7s     -4s     NOW

Press SPACE here ↑
                  ↓
File contains: [-10s to -7s, -7s to -4s, -4s to NOW, NOW to STOP]

```

### Session Management System

Omega-13 uses a sophisticated session management system to protect your work:

**Session Lifecycle:**

```
1. Launch
   ↓
2. SessionManager creates new session
   - Generates unique ID
   - Creates /tmp/omega13/<session_id>/
   - Initializes metadata
   ↓
3. User records multiple times
   - Each recording → recordings/001.wav, 002.wav, etc.
   - Metadata updated in session.json
   ↓
4. User saves session (S key)
   - Choose destination directory
   - Copy all files to permanent location
   - Mark session as saved
   ↓
5. User quits (Q key)
   - If saved or empty → Clean exit
   - If unsaved → Prompt to save/discard/cancel

```

**Automatic Cleanup:**

- On launch, old temp sessions (>7 days) are automatically removed

- Prevents /tmp directory from filling up

- Configurable via `auto_cleanup_days` setting

### Architecture Overview

Omega-13 is built with a modular Python package structure:

**`ConfigManager`** ([src/omega13/config.py](https://www.google.com/search?q=src/omega13/config.py "null"))

- Loads/saves persistent configuration to `~/.config/omega13/config.json`

- Validates selected audio ports on startup

- Manages session settings and defaults

**`SessionManager`** ([src/omega13/session.py](https://www.google.com/search?q=src/omega13/session.py "null"))

- Creates and manages recording sessions

- Handles temp directory lifecycle

- Implements save/discard operations

- Auto-cleanup of old sessions

**`Session`** ([src/omega13/session.py](https://www.google.com/search?q=src/omega13/session.py "null"))

- Represents individual session with metadata

- Tracks all recordings in session

- Manages session.json persistence

**`AudioEngine`** ([src/omega13/audio.py](https://www.google.com/search?q=src/omega13/audio.py "null"))

- Creates and manages JACK/PipeWire client connection

- Implements ring buffer with NumPy arrays

- Processes audio in real-time callback

- Spawns background thread for file writing

- Calculates peak levels and dB values for metering

**`Omega13App`** ([src/omega13/app.py](https://www.google.com/search?q=src/omega13/app.py "null"))

- Main Textual application managing overall UI

- Coordinates all widgets and modal screens

- Handles keybindings and application lifecycle

- Updates meters at 20 FPS via timer callback

- Manages session lifecycle and save prompts

**UI Components** ([src/omega13/ui.py](https://www.google.com/search?q=src/omega13/ui.py "null"))

- `VUMeter` - Reactive widget for level visualization

- `TranscriptionDisplay` - Shows AI transcription results

- `InputSelectionScreen` - Modal for port selection

- `DirectorySelectionScreen` - Modal for choosing directories

### Multi-threading Design

Omega-13 uses a **two-thread architecture**:

1. **Real-time Audio Thread** (Audio callback)

    - Runs in `AudioEngine.process()`

    - High-priority, time-critical processing

    - Writes audio data to ring buffer

    - Calculates peak meters

    - **Must never block** (no file I/O, no locks)

2. **Background File Writer Thread**

    - Runs in `AudioEngine._file_writer()`

    - Spawned when recording starts

    - Safely writes audio data to disk

    - Terminates when recording stops

This design ensures the real-time audio callback never blocks waiting for disk I/O, preventing audio dropouts.

## ⚙️ Configuration

### Configuration File

**Location:** `~/.config/omega13/config.json`

**Full Schema:**

```json
{
  "version": 2,
  "input_ports": [
    "system:capture_1",
    "system:capture_2"
  ],
  "save_path": "/home/user/Recordings",
  "transcription": {
    "enabled": true,
    "auto_transcribe": true,
    "model_size": "large-v3-turbo",
    "save_to_file": true
  },
  "sessions": {
    "temp_root": "/tmp/omega13",
    "default_save_location": "/home/user/Recordings",
    "auto_cleanup_days": 7
  }
}
```

**Session Configuration:**

- `temp_root`: Where temporary sessions are created (default: `/tmp/omega13`)

- `default_save_location`: Default directory for saving sessions (default: `~/Recordings`)

- `auto_cleanup_days`: Days before auto-cleanup of old temp sessions (default: 7)

**Validation Behavior:**

- On startup, Omega-13 validates that saved ports exist in the current graph

- If ports are missing (e.g., different audio interface), the input selection dialog auto-opens

- Session temp directory is created if it doesn't exist

### Customizable Constants

Edit [src/omega13/audio.py](https://www.google.com/search?q=src/omega13/audio.py "null") to adjust these parameters:

**Buffer Duration:**

```python
BUFFER_DURATION = 13  # seconds of retroactive audio
```

**Default Channel Count:**

```python
DEFAULT_CHANNELS = 2  # 1=mono, 2=stereo
```

## 🐛 Troubleshooting

### Client Registration Failed

**Symptom:** Omega-13 exits with an error about connecting to the server.

**Solution (PipeWire):** Ensure the `pipewire-jack` compatibility layer is installed. You can also try:

```bash
pw-jack python -m omega13
```

**Solution (Classic JACK):**

```bash
# Check if JACK is running
jack_lsp
# If no output, start JACK server:
jackd -d alsa -r 48000 -p 512 &
```

### No Input Ports Available

**Symptom:** Input selection dialog shows empty list

**Causes:**

1. Audio interface not connected

2. Server not detecting hardware

3. No other apps running (in "output ports" view)

**Solutions:**

```bash
# List all ports
jack_lsp -p

# Check audio interface is visible to ALSA
aplay -l
```

### Permission Denied Errors

**Symptom:** `JACK requires real-time permissions` or similar

**Solution:**

```bash
# Add user to audio group
sudo usermod -a -G audio $USER
# Add user to jackuser group (if it exists)
sudo usermod -a -G jackuser $USER

# Verify real-time limits are set
ulimit -r  # Should return non-zero value
```

### Audio Dropouts / Xruns

**Symptom:** Crackling, pops, or gaps in recordings

**Causes:**

- Buffer size too small

- System under heavy load

- USB audio interface issues

**Solutions:**

```bash
# PipeWire: Adjust quantum
pw-metadata -n settings 0 clock.force-quantum 1024

# Classic JACK: Increase buffer
jackd -d alsa -r 48000 -p 1024
```

### Recordings Are Silent

**Symptom:** WAV files are created but contain no audio

**Checklist:**

1. Check VU meters are showing signal before recording

2. Verify correct ports selected with `I` key

3. Ensure connections are established:

    ```bash
    jack_lsp -c | grep Omega13
    ```

4. **PipeWire Users**: Use `qpwgraph` or `Helvum` to visually inspect if Omega-13 is connected to your source.

### Temp Directory Full

**Symptom:** "Disk full" errors when recording

**Causes:**

- /tmp partition full

- Many old unsaved sessions

**Solutions:**

```bash
# Check /tmp usage
df -h /tmp

# Manually clean old sessions
rm -rf /tmp/omega13/session_*

# Reduce auto_cleanup_days in config:
# Edit ~/.config/omega13/config.json
# Set "auto_cleanup_days": 3
```

### Configuration Not Saving

**Symptom:** Port selections reset every launch

**Solutions:**

```bash
# Check config directory permissions
ls -la ~/.config/omega13/

# If doesn't exist, create it:
mkdir -p ~/.config/omega13

# Verify Omega-13 can write there:
touch ~/.config/omega13/test && rm ~/.config/omega13/test
```

## 👨‍💻 Development

### Project Structure

```
omega-13/
├── src/
│   └── omega13/
│       ├── __init__.py
│       ├── __main__.py        # Entry point
│       ├── app.py             # Main Textual application
│       ├── audio.py           # AudioEngine (JACK client & ring buffer)
│       ├── config.py          # ConfigManager
│       ├── session.py         # Session management (NEW)
│       ├── transcription.py   # AI transcription service
│       └── ui.py              # UI widgets and screens
├── tests/                     # Test suite (TODO)
├── deployment/                # Container configs
├── docs/                      # Documentation
├── pyproject.toml            # Project metadata
├── requirements.txt          # Python dependencies
└── README.md                 # This file

```

### Key Classes and Responsibilities

| Class | File | Purpose |
|-------|------|---------|
| ConfigManager | config.py | Persistent settings storage in JSON |
| SessionManager | session.py | Session lifecycle and temp storage |
| Session | session.py | Individual session with metadata |
| AudioEngine | audio.py | JACK client, ring buffer, audio processing |
| TimeMachineApp | app.py | Main Textual application orchestrator |
| VUMeter | ui.py | Reactive TUI widget for level display |
| InputSelectionScreen | ui.py | Modal dialog for port selection |
| DirectorySelectionScreen | ui.py | Modal for choosing directories |

### Code Style Conventions

- **Type Hints:** Used for function signatures throughout

- **Docstrings:** Present on all classes and public methods

- **Naming:**

  - `snake_case` for functions/variables

  - `PascalCase` for classes

  - `UPPER_SNAKE_CASE` for constants

- **Line Length:** Generally kept under 100 characters

- **Textual Patterns:**

  - `on_*` methods for event handlers

  - `action_*` methods for keybinding actions

  - CSS defined in class docstrings

### Running in Development Mode

```bash
# Activate virtual environment
source .venv/bin/activate

# Run from package
python -m omega13

# Run with Python debugger on crash
python -i -m omega13

# Run with Textual development mode (shows layout inspector)
textual run --dev src/omega13/app.py

# Run with verbose JACK logging
JACK_DEFAULT_SERVER=default python -m omega13
```

### Testing Workflow

Manual testing checklist:

**Session Management:**

- $$ $$

    Launch creates new session in /tmp/omega13

- $$ $$

    Recording creates 001.wav in session temp directory

- $$ $$

    Multiple recordings numbered sequentially

- $$ $$

    Save session (S) copies all files to destination

- $$ $$

    Session status updates correctly

- $$ $$

    Exit with unsaved work prompts for save

- $$ $$

    Exit with saved session is clean

- $$ $$

    Auto-cleanup removes old sessions

**Audio Recording:**

- $$ $$

    Launch with server stopped (should fail gracefully)

- $$ $$

    Launch with no audio ports available

- $$ $$

    Switch between mono and stereo modes

- $$ $$

    Select same port for both channels in stereo (should prevent)

- $$ $$

    Record with buffer not yet full (< 10 seconds runtime)

- $$ $$

    Record with buffer full

**Configuration:**

- $$ $$

    Restart with saved configuration (should restore ports)

- $$ $$

    Restart with unavailable ports in config (should prompt re-selection)

## 📊 Technical Specifications

| Category | Details |
|----------|---------|
| Language | Python 3.12+ |
| UI Framework | Textual 0.70.0+ (reactive TUI) |
| Audio Backend | JACK Audio Connection Kit / PipeWire-JACK |
| Dependencies | textual, JACK-Client, numpy, soundfile |
| Buffer Implementation | NumPy circular array (10s × sample_rate × channels) |
| Thread Model | 2 threads (real-time audio + background file I/O) |
| Audio Format | WAV PCM, 32-bit float, JACK sample rate, 1-2 channels |
| Session Storage | Temp: /tmp/omega13/, Permanent: User-chosen |
| Config Storage | JSON at ~/.config/omega13/config.json |
| Platform | Linux (JACK dependency) |

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Reporting Bugs

Open an issue with:

- Omega-13 version / git commit hash

- Python version (`python --version`)

- Audio Server version (`jackd --version` or `pipewire --version`)

- Distribution and kernel version

- Steps to reproduce

- Expected vs actual behavior

- Relevant logs from console

### Feature Requests

Before requesting, check existing issues. When creating a new request:

- Describe the problem you're trying to solve

- Explain why existing features don't address it

- Propose a solution (optional)

- Consider implementation complexity

### Pull Requests

1. Fork the repository

2. Create a feature branch (`git checkout -b feature/amazing-feature`)

3. Make your changes

4. Test thoroughly (manual testing checklist above)

5. Update README if adding features or changing behavior

6. Commit with clear messages (`git commit -m 'Add amazing feature'`)

7. Push to branch (`git push origin feature/amazing-feature`)

8. Open Pull Request with description of changes

**Code Review Focus:**

- Does it maintain the real-time audio thread safety?

- Are there potential deadlocks or race conditions?

- Is the UI responsive during long operations?

- Does it handle errors gracefully?

- Does session management work correctly?

## 📄 License

This project is licensed under the MIT License. See `LICENSE` file for details.

## 🙏 Acknowledgments

Built with these excellent libraries:

- [**Textual**](https://textual.textualize.io/ "null") - Modern Python TUI framework by Textualize

- [**JACK Audio Connection Kit**](https://jackaudio.org/ "null") - Professional audio routing infrastructure

- [**NumPy**](https://numpy.org/ "null") - Fundamental package for scientific computing

- [**SoundFile**](https://python-soundfile.readthedocs.io/ "null") - Audio file I/O library

Inspired by the original [TimeMachine](https://plugin.org.uk/timemachine/ "null") by Steve Harris, a command-line JACK recording tool with similar retroactive capture capabilities.

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/omega-13/issues "null")

- **Discussions:** [GitHub Discussions](https://github.com/yourusername/omega-13/discussions "null")

- **JACK Help:** [JACK Audio Discord](https://discord.gg/jackaudio "null") or [Linux Audio Users Mailing List](https://lists.linuxaudio.org/listinfo/linux-audio-user "null")

**Built with ❤️ for the Linux audio community**

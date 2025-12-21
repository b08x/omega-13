# TimeMachine-py

**Retroactive Audio Recording for JACK**

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![JACK](https://img.shields.io/badge/JACK-Audio-orange.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

TimeMachine is a real-time audio recording application that lets you capture the immediate past. It continuously maintains a 10-second rolling buffer of audio—press a button at any moment to save what just happened, plus everything that follows until you stop recording. Perfect for capturing unexpected moments of brilliance during music production, live performance, or audio experimentation.

## ✨ Features

- **🕐 Retroactive Recording** - Always recording the last 10 seconds in memory, ready to save instantly
- **🎚️ JACK Integration** - Professional audio routing with low-latency real-time processing
- **📊 Real-time Metering** - Live dB level visualization with color-coded VU meters
- **🎧 Multi-channel Support** - Record in mono or stereo with flexible port selection
- **💾 Smart File Naming** - Automatic timestamp-based WAV file generation
- **⚙️ Persistent Configuration** - Remembers your input ports and save directory across sessions
- **🖥️ Terminal UI** - Clean, reactive text-based interface built with Textual

## 📋 Prerequisites

- **Operating System**: Linux (JACK Audio Connection Kit required)
- **Python**: 3.12 or higher
- **JACK Server**: Must be running and configured before launching TimeMachine
- **System Libraries**:
  - `libjack` (JACK development libraries)
  - `libsndfile` (for WAV file I/O)

### Installing JACK on Common Distributions

**Fedora/RHEL:**

```bash
sudo dnf install jack-audio-connection-kit jack-audio-connection-kit-devel
```

**Ubuntu/Debian:**

```bash
sudo apt install jackd2 libjack-jackd2-dev libsndfile1-dev
```

**Arch Linux:**

```bash
sudo pacman -S jack2 libsndfile
```

## 🚀 Installation

1. **Clone the repository:**

```bash
git clone https://github.com/yourusername/timemachine-py.git
cd timemachine-py
```

2. **Create and activate a virtual environment:**

```bash
python -m venv .venv
source .venv/bin/activate
```

3. **Install dependencies:**

```bash
pip install -r requirements.txt
```

## ⚡ Quick Start

1. **Start your JACK server** (if not already running):

```bash
# Example: Start JACK with ALSA backend at 48kHz
jackd -d alsa -r 48000 -p 512
```

2. **Launch TimeMachine:**

```bash
python timemachine.py
```

3. **Configure your audio input:**
   - Press `I` to open the input selection dialog
   - Choose mono or stereo mode
   - Select your desired JACK output ports (audio sources)

4. **Start recording:**
   - Press `SPACE` to begin recording
   - The 10-second buffer is automatically included in the recording
   - Press `SPACE` again to stop and save the file

5. **Find your recordings:**
   - Files are saved as `tm-YYYY-MM-DDTHH-MM-SS.wav`
   - Default location: current working directory
   - Change save path by pressing `P`

## 🎹 Usage Guide

### Keybindings

| Key | Action |
|-----|--------|
| `SPACE` | Start/Stop recording |
| `I` | Select JACK input ports |
| `P` | Choose recording save directory |
| `Q` | Quit application |

### Understanding the UI

When you launch TimeMachine, you'll see several key interface elements:

```
┌─ Status ───────────────────────────┐
│ ● RECORDING / ○ Stopped            │
└────────────────────────────────────┘

┌─ Audio Levels ─────────────────────┐
│ L: ████████████░░░░ -12.3 dB       │
│ R: ██████████████░░ -8.5 dB        │
└────────────────────────────────────┘

┌─ Connection ───────────────────────┐
│ system:capture_1 → Left            │
│ system:capture_2 → Right           │
└────────────────────────────────────┘

┌─ Save Path ────────────────────────┐
│ /home/user/Recordings              │
└────────────────────────────────────┘

┌─ Buffer Status ────────────────────┐
│ Pre-record buffer: 100% filled     │
└────────────────────────────────────┘
```

**Status Bar:**

- Shows current recording state (Recording/Stopped)
- Updates in real-time

**VU Meters:**

- Visual bar graphs showing audio levels
- Numeric dB values for precise monitoring
- Color-coded: Green (safe), Yellow (moderate), Red (clipping)
- Updates 20 times per second for responsive feedback

**Connection Status:**

- Displays currently selected JACK input ports
- Shows channel routing (mono or stereo)
- Click `I` to reconfigure

**Save Path:**

- Current directory for recorded files
- Click `P` to choose a new location via directory browser

**Buffer Fill Indicator:**

- Shows pre-record buffer status
- Reaches 100% after 10 seconds of runtime
- Recording before 100% includes whatever buffer has accumulated

### Configuring Audio Inputs

When you press `I`, you'll go through a two-step process:

**Step 1: Channel Mode Selection**

- **Mono**: Records a single channel from one JACK output port
- **Stereo**: Records two channels from two separate JACK output ports

**Step 2: Port Selection**

- Browse available JACK output ports (audio sources)
- Common ports include:
  - `system:capture_X` - Physical audio interface inputs
  - `application_name:output_X` - Software output from other JACK apps
- Select different ports for left/right channels in stereo mode
- Can't select the same port twice in stereo mode

**JACK Port Naming Convention:**

```
client_name:port_name

Examples:
- system:capture_1          (Physical input 1)
- ardour:master/out_1       (Ardour DAW master output)
- guitarix:output_0         (Guitar amp simulator)
```

### File Output Details

**Format:** Uncompressed WAV (PCM)
**Sample Rate:** Inherited from JACK server configuration (typically 44.1kHz or 48kHz)
**Channels:** 1 (mono) or 2 (stereo) based on your selection
**Bit Depth:** 32-bit float (preserves full dynamic range)

**Filename Format:**

```
tm-2025-12-20T14-30-45.wav
   │    │   │ │  │  │
   │    │   │ │  │  └─ Seconds
   │    │   │ │  └──── Minutes
   │    │   │ └─────── Hours (24-hour)
   │    │   └────────── Day
   │    └───────────── Month
   └────────────────── Year
```

**Important:** The timestamp reflects when the *audio content begins* (including the 10-second buffer), not when you pressed the record button. If you press record at 14:30:55, the filename will show 14:30:45 (10 seconds earlier).

## 🔧 How It Works

### The Rolling Buffer Concept

TimeMachine implements a **circular buffer** (ring buffer) that continuously stores the most recent 10 seconds of incoming audio:

1. **Always Listening:** From the moment you launch the app, audio flows into the buffer
2. **Circular Overwriting:** Old audio data is continuously replaced by new data
3. **Instant Snapshot:** When you press `SPACE`, the current buffer contents are frozen
4. **Continuous Recording:** After the buffer dump, new incoming audio is appended to the file
5. **Stop and Save:** Pressing `SPACE` again finalizes the file

```
Time:     [-------|-------|-------|-------]
          -10s    -7s     -4s     NOW

Press SPACE here ↑
                  ↓
File contains: [-10s to -7s, -7s to -4s, -4s to NOW, NOW to STOP]
```

### Architecture Overview

TimeMachine is built as a monolithic Python application with clear class separation:

**`ConfigManager`** (`timemachine.py:24-97`)

- Loads/saves persistent configuration to `~/.config/timemachine/config.json`
- Validates selected JACK ports on startup
- Handles configuration schema versioning

**`AudioEngine`** (`timemachine.py:119-343`)

- Creates and manages JACK client connection
- Implements ring buffer with NumPy arrays
- Processes audio in real-time callback (`process()` method)
- Spawns background thread for file writing during recording
- Calculates peak levels and dB values for metering

**`VUMeter`** (`timemachine.py:345-368`)

- Textual reactive widget for level visualization
- Renders color-coded bar graphs with numeric dB display
- Updates based on meter data pushed from audio engine

**`InputSelectionScreen`** (`timemachine.py:370-549`)

- Modal dialog for port selection workflow
- Two-stage UI: channel mode → port selection
- Validates selections and prevents duplicate port assignment

**`DirectorySelectionScreen`** (`timemachine.py:551-640`)

- Modal directory browser for choosing save location
- Interactive tree navigation with keyboard controls
- Updates main app UI with selected path

**`TimeMachineApp`** (`timemachine.py:642-934`)

- Main Textual application managing overall UI
- Coordinates all widgets and modal screens
- Handles keybindings and application lifecycle
- Updates meters at 20 FPS via timer callback

### Multi-threading Design

TimeMachine uses a **two-thread architecture**:

1. **Real-time Audio Thread** (JACK callback)
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

**Location:** `~/.config/timemachine/config.json`

**Schema:**

```json
{
  "version": 1,
  "input_ports": [
    "system:capture_1",
    "system:capture_2"
  ],
  "save_path": "/home/user/Recordings"
}
```

**Validation Behavior:**

- On startup, TimeMachine validates that saved ports exist in the current JACK graph
- If ports are missing (e.g., different audio interface), the input selection dialog auto-opens
- Save path is validated; if invalid, defaults to current working directory

### Customizable Constants

Edit `timemachine.py` to adjust these parameters:

**Buffer Duration** (`line 21`):

```python
BUFFER_DURATION = 10  # seconds of retroactive audio
```

**Default Channel Count** (`line 22`):

```python
DEFAULT_CHANNELS = 2  # 1=mono, 2=stereo
```

**Meter Update Rate** (`line 687` in `TimeMachineApp`):

```python
self.update_meters = self.set_interval(1/20, self._update_meters)  # 20 FPS
```

## 🐛 Troubleshooting

### JACK Server Not Running

**Symptom:** TimeMachine exits immediately with error about JACK connection

**Solution:**

```bash
# Check if JACK is running
jack_lsp

# If no output, start JACK server:
jackd -d alsa -r 48000 -p 512 &

# Or use QjackCtl GUI:
qjackctl
```

### No Input Ports Available

**Symptom:** Input selection dialog shows empty list

**Causes:**

1. Audio interface not connected
2. JACK not detecting hardware
3. No other JACK applications running (in "output ports" view)

**Solutions:**

```bash
# List all JACK ports
jack_lsp -p

# Check audio interface is visible to ALSA
aplay -l

# Restart JACK with correct device:
jackd -d alsa -d hw:2 -r 48000 -p 512  # Replace hw:2 with your device
```

### Permission Denied Errors

**Symptom:** `JACK requires real-time permissions` or similar

**Solution:**

```bash
# Add user to audio group
sudo usermod -a -G audio $USER

# Logout and login again for group change to take effect

# Verify real-time limits are set
ulimit -r  # Should return non-zero value

# If zero, edit /etc/security/limits.conf:
@audio   -  rtprio     95
@audio   -  memlock    unlimited
```

### Audio Dropouts / Xruns

**Symptom:** Crackling, pops, or gaps in recordings

**Causes:**

- JACK buffer too small
- System under heavy load
- USB audio interface issues

**Solutions:**

```bash
# Increase JACK buffer size (lower values = lower latency but higher risk)
jackd -d alsa -r 48000 -p 1024  # Increased from 512

# Check for xruns in JACK logs
# Use QjackCtl to monitor xrun count

# Reduce system load:
# - Close unnecessary applications
# - Disable desktop composition/effects
# - Use a real-time kernel
```

### Recordings Are Silent

**Symptom:** WAV files are created but contain no audio

**Checklist:**

1. Check VU meters are showing signal before recording
2. Verify correct ports selected with `I` key
3. Ensure JACK connections are established:

   ```bash
   jack_lsp -c | grep timemachine
   ```

4. Test audio interface with another application
5. Check if other JACK apps can receive audio from same source

### Configuration Not Saving

**Symptom:** Port selections reset every launch

**Solutions:**

```bash
# Check config directory permissions
ls -la ~/.config/timemachine/

# If doesn't exist, create it:
mkdir -p ~/.config/timemachine

# Verify TimeMachine can write there:
touch ~/.config/timemachine/test && rm ~/.config/timemachine/test
```

## 👨‍💻 Development

### Project Structure

```
timemachine-py/
├── timemachine.py          # Main application (935 lines)
├── requirements.txt        # Python dependencies
├── .venv/                 # Virtual environment (excluded from git)
├── __pycache__/           # Python bytecode cache (excluded)
├── logs/                  # Application logs
├── results/               # Example recordings
└── README.md              # This file
```

### Key Classes and Responsibilities

| Class | Lines | Purpose |
|-------|-------|---------|
| `ConfigManager` | 24-97 | Persistent settings storage in JSON |
| `AudioEngine` | 119-343 | JACK client, ring buffer, audio processing |
| `VUMeter` | 345-368 | Reactive TUI widget for level display |
| `InputSelectionScreen` | 370-549 | Modal dialog for port selection |
| `DirectorySelectionScreen` | 551-640 | Modal dialog for save path selection |
| `TimeMachineApp` | 642-934 | Main Textual application orchestrator |

### Adding Features

**Modify Buffer Duration:**

```python
# timemachine.py:21
BUFFER_DURATION = 30  # Change from 10 to 30 seconds
```

**Add New Keybinding:**

```python
# timemachine.py - Add method to TimeMachineApp class
def key_m(self) -> None:
    """Toggle mute (example)"""
    self.audio_engine.toggle_mute()
```

**Customize UI Styling:**

```python
# Each widget class has CSS in its docstring
class VUMeter(Static):
    DEFAULT_CSS = """
    VUMeter {
        background: red;  /* Change background color */
    }
    """
```

**Add Recording Formats:**

```python
# AudioEngine._file_writer() method (line 295)
# Change soundfile.write() parameters:
soundfile.write(
    filepath,
    data,
    self.jack_client.samplerate,
    format='FLAC'  # Instead of default WAV
)
```

### Code Style Conventions

- **Type Hints:** Used for function signatures
- **Docstrings:** Present on all classes; methods have inline comments
- **Naming:**
  - `snake_case` for functions/variables
  - `PascalCase` for classes
  - `UPPER_SNAKE_CASE` for constants
- **Line Length:** Generally kept under 100 characters
- **Textual Patterns:**
  - `on_*` methods for event handlers
  - `key_*` methods for keybindings
  - `DEFAULT_CSS` for widget styling

### Running in Development Mode

```bash
# Activate virtual environment
source .venv/bin/activate

# Run with Python debugger on crash
python -i timemachine.py

# Run with Textual development mode (shows layout inspector)
textual run --dev timemachine.py

# Run with verbose JACK logging
JACK_DEFAULT_SERVER=default python timemachine.py
```

### Testing Workflow

Currently no automated tests exist. Manual testing checklist:

- [ ] Launch with JACK server stopped (should fail gracefully)
- [ ] Launch with no audio ports available
- [ ] Switch between mono and stereo modes
- [ ] Select same port for both channels in stereo (should prevent)
- [ ] Record with buffer not yet full (< 10 seconds runtime)
- [ ] Record with buffer full
- [ ] Change save directory to read-only location (should handle error)
- [ ] Fill disk during recording (should handle gracefully)
- [ ] Restart with saved configuration (should restore ports)
- [ ] Restart with unavailable ports in config (should prompt re-selection)

## 📊 Technical Specifications

| Category | Details |
|----------|---------|
| **Language** | Python 3.12+ |
| **UI Framework** | Textual 0.70.0+ (reactive TUI) |
| **Audio Backend** | JACK Audio Connection Kit |
| **Dependencies** | `textual`, `JACK-Client`, `numpy`, `soundfile` |
| **Buffer Implementation** | NumPy circular array (10s × sample_rate × channels) |
| **Thread Model** | 2 threads (real-time audio + background file I/O) |
| **Audio Format** | WAV PCM, 32-bit float, JACK sample rate, 1-2 channels |
| **Config Storage** | JSON at `~/.config/timemachine/config.json` |
| **Platform** | Linux (JACK dependency) |

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Reporting Bugs

Open an issue with:

- TimeMachine version / git commit hash
- Python version (`python --version`)
- JACK version (`jackd --version`)
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

## 📄 License

This project is licensed under the MIT License. See `LICENSE` file for details.

## 🙏 Acknowledgments

Built with these excellent libraries:

- **[Textual](https://textual.textualize.io/)** - Modern Python TUI framework by Textualize
- **[JACK Audio Connection Kit](https://jackaudio.org/)** - Professional audio routing infrastructure
- **[NumPy](https://numpy.org/)** - Fundamental package for scientific computing
- **[SoundFile](https://python-soundfile.readthedocs.io/)** - Audio file I/O library

Inspired by the original [TimeMachine](https://plugin.org.uk/timemachine/) by Steve Harris, a command-line JACK recording tool with similar retroactive capture capabilities.

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/timemachine-py/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/timemachine-py/discussions)
- **JACK Help:** [JACK Audio Discord](https://discord.gg/jackaudio) or [Linux Audio Users Mailing List](https://lists.linuxaudio.org/listinfo/linux-audio-user)

---

**Built with ❤️ for the Linux audio community**

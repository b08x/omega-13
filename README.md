# Omega-13 🌌

**A Retroactive Audio Recorder & Transcription TUI**

> *"It's a time machine... but it only goes back 13 seconds."*

Omega-13 is a retroactive audio recording system designed to capture audio from the past (defaulting to 13 seconds) and process it into transcriptions. The system architecture relies on a JACK/PipeWire audio backend, a Python-based Textual TUI, and a containerized Whisper inference server. Installation involves a multi-stage setup: deploying the inference container, installing the Python package, and configuring system-level global hotkeys to bypass Wayland security constraints.

<!-- ![Omega-13 Main Interface](images/01_main_interface.png)
*(The main TUI showing audio levels and transcription status)* -->

## 🤖 About This Project

This is a **personal workflow tool** built through **Natural Language Programming**. Not "AI-assisted development"—actual programming where natural language is the source code and AI is the compiler.

**The Development Process:**
I had a problem: wanting to capture fleeting thoughts retroactively. Instead of learning audio programming, threading, or JACK APIs, I described what I needed in English. The language models translated those requirements into working code. When something broke, I described the problem. They debugged it. When I wanted new features, I explained them. They implemented them.

**The Toolchain:**
- **Claude** (Anthropic) - Primary compiler: requirements → architecture → implementation
- **Gemini** (Google) - Secondary compiler: feature specs → code
- **GLM-4** (Zhipu AI) - Experimental runtime for specialized features
- **Development Environments:**
  - `claude-code` - IDE for natural language programming
  - `gemini-cli` - Rapid iteration interface
  - `opencode` with `oh-my-opencode` - Advanced NLP workflows, automated refactoring

**Why this matters:** This isn't a toy project. It's a fully functional real-time audio system with ring buffers, JACK integration, multi-threaded transcription, Docker orchestration, and Wayland IPC workarounds. The entire system—including the gnarly bits like real-time audio constraints and thread-safe ring buffer wrapping—was specified in natural language and compiled to Python by AI.

**Programming paradigm shift:** Traditional programming: human writes code → computer executes. Natural Language Programming: human writes requirements → AI writes code → computer executes. The human is still the programmer. The language just changed from Python to English.

The extensive documentation below? Also written by AI. Do I read it? Never. It's for the *next* AI session that works on this codebase.

## ✨ Key Features

* **🕰️ Retroactive Recording:** Always listens (locally), never misses a thought. Captures the 13 seconds *before* you pressed the key.
* **🎙️ Voice-Activated Auto-Record:** Automatically starts recording when it detects voice activity and stops when silence is detected. Configurable RMS thresholds and sustained signal validation prevent false triggers.
* **🔒 Local Privacy:** Uses `whisper.cpp` running locally via Docker. No audio is ever sent to the cloud.
* **🖥️ Textual TUI:** A beautiful, keyboard-centric terminal interface.
* **📋 Clipboard Sync:** Automatically copies transcribed text to your clipboard for immediate pasting into IDEs or notes.
* **🎹 Global Hotkeys:** Trigger recording from anywhere in your OS (supports Wayland/GNOME workarounds).
* **🎛️ JACK/PipeWire Support:** Professional audio routing (supports Mono and Stereo inputs).

---

## 📚 Documentation (For the AI, Mostly)

The sections below are absurdly detailed for a personal tool. But they're not really for me—they're for the AI assistants that maintain this. When Claude needs to add a feature or fix a bug, it reads this. When Gemini picks up where Claude left off, it needs context. This is AI-to-AI documentation.

That said, if you're a human who stumbled here and wants to try it, the instructions actually work.

---

## 🚀 Quick Start

*(Meticulously documented by AI. Will I ever run these commands again? Doubtful. But the next AI assistant will appreciate it.)*

### Prerequisites

* **Linux** (Tested on Fedora, Ubuntu, Arch, OpenSUSE)
* **Python 3.12+**
* **Docker/Podman**
* **[Optional]** NVIDIA GPU with CUDA support for accelerated transcription

### Automated Installation

The `bootstrap.sh` script automates the entire setup process:

1. **Detects your Linux distribution** and installs system dependencies
2. **Sets up Python environment** using modern `uv` package manager (with pip fallback)
3. **Optionally builds the Whisper transcription server** with CUDA support

```bash
# Clone the repository
cd omega-13

# Run the installer (interactive mode)
./bootstrap.sh

# Or auto-build the Whisper server
./bootstrap.sh --build
```

**What bootstrap.sh does:**
* Installs: Python 3.12+, development headers, libsndfile, JACK/PipeWire libraries, build tools, Podman
* Supports package managers: `dnf` (Fedora), `apt` (Debian/Ubuntu), `pacman` (Arch), `zypper` (OpenSUSE)
* Creates Python virtual environment using `uv sync`
* Optionally builds the `whisper-server-cuda` Docker image

### Custom CUDA Architecture (Optional)

For optimal GPU performance, you can specify your GPU architecture during the build:

```bash
# RTX 30xx series (Ampere)
CUDA_ARCHITECTURES="86" ./bootstrap.sh --build

# RTX 40xx series (Ada Lovelace)
CUDA_ARCHITECTURES="89" ./bootstrap.sh --build

# Multiple architectures (default: 75;80;86;89;90)
CUDA_ARCHITECTURES="86;89" ./bootstrap.sh --build
```

**CUDA Architecture Reference:**
* `75`: RTX 20xx (Turing)
* `80`: A100 (Ampere)
* `86`: RTX 30xx (Ampere)
* `89`: RTX 40xx (Ada Lovelace)
* `90`: H100 (Hopper)

See [NVIDIA CUDA GPU Architectures](https://developer.nvidia.com/cuda-gpus) for your specific GPU.

### Start the Application

```bash
# Using uv (recommended by bootstrap)
uv run python -m omega13

# Or activate venv manually
source .venv/bin/activate
omega13
```

---

## 📦 Manual Installation (Alternative)

For advanced users who prefer manual control:

### 1. Set up the Backend (Whisper Server)

Omega-13 delegates heavy AI lifting to a Docker container to keep the TUI snappy.

1. Navigate to the project directory.
2. Start the transcription server:

    ```bash
    docker compose up -d
    ```

    *Note: This pulls a custom image based on `nvidia/cuda` and builds `whisper.cpp` with CUDA support. The first run will take time to compile.*

### 2. Install the Application

Install the Python package locally:

```bash
# Using pip
pip install .

# Or using uv (faster)
uv pip install -e .
```

---

## ⚙️ Configuration & Audio Setup

### 1. Launching

Run the application from your terminal:

```bash
omega13
```

### 2. Selecting Audio Inputs

By default, Omega-13 listens to nothing. You must connect it to an audio source.

1. Press `i` (or `I`) to open the **Input Selector**.
2. Choose **Mono** or **Stereo**.
3. Select your microphone from the list.
    * *Tip:* If you use **NoiseTorch** (as seen in the screenshots), select the `NoiseTorch Microphone` stream for cleaner audio.
4. Verify the **VU Meter** on the left is moving when you speak.

### 3. Setting the Global Hotkey (Important!)

Because Wayland prevents applications from spying on global keystrokes, you must configure a system-level shortcut to "poke" Omega-13.

**The default trigger is `Ctrl + Alt + Space`.**

**For GNOME Users:**

1. Go to **Settings** -> **Keyboard** -> **View and Customize Shortcuts**.
2. Add a **Custom Shortcut**.
3. **Name:** `Omega-13 Toggle`
4. **Command:** `omega13 --toggle`
5. **Shortcut:** `Ctrl + Alt + Space` (or your preference).

Now, pressing this key combination will start/stop recording even if the terminal is not focused.

---

## 🚀 Usage Workflow

1. **Speak your thought.** (Don't worry, you haven't hit record yet).
2. **Trigger the Hotkey** (`Ctrl+Alt+Space`).
    * Omega-13 grabs the audio from 13 seconds ago up to now.
    * The status bar turns **RED** (`RECORDING...`).
3. **Finish speaking.**
4. **Trigger the Hotkey again.**
    * Recording stops.
    * Audio is saved to a temporary session.
    * Transcription begins immediately (Status: `Transcribing...`).
5. **Paste.**
    * Once complete, the text is automatically copied to your clipboard (if enabled).

### Session Management

* **Sessions** are temporary by default (`/tmp/omega13`).
* Press `s` to **Save Session** to a permanent location (e.g., `~/Notebooks`).
* This saves the `.wav` audio, `.md` transcriptions, and a `session.json` metadata file.

### Voice-Activated Auto-Record

Omega-13 includes an intelligent auto-record mode that automatically starts and stops recording based on voice activity.

**Enabling Auto-Record:**

1. Toggle the **Auto-Record** checkbox in the main interface.
2. When enabled, the application monitors audio for voice activity using RMS energy detection.

**How It Works:**

* **Automatic Start:** Recording begins when sustained voice activity is detected (default: -35 dB threshold for 0.5+ seconds).
* **Automatic Stop:** Recording stops after a configurable period of silence (default: 10 seconds).
* **Visual Feedback:** A countdown timer with progress bar shows when auto-stop will occur.
* **Smart Filtering:**
  * Brief transients (coughs, clicks) under 0.5 seconds won't trigger recording.
  * Recordings with average RMS below -50 dB are automatically discarded.
* **Retroactive Buffer:** The 13-second pre-buffer is preserved for auto-triggered recordings.

**Performance:**

* Optimized for minimal CPU overhead (~70-80% reduction vs naive implementation).
* RMS calculation occurs every 10th audio callback.
* UI updates are debounced to maintain responsiveness.

---

## ⌨️ TUI Shortcuts

| Key | Action |
| :--- | :--- |
| `I` | **Inputs:** Configure audio sources. |
| `S` | **Save:** Move current session to permanent storage. |
| `T` | **Transcribe:** Manually re-transcribe the last recording. |
| `Q` | **Quit:** Exit the application. |
| `Ctrl+P` | **Command Palette:** Change themes (Dracula, Monokai, etc). |

---

## 🔧 Development

If you're an AI agent working on this codebase:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests
python -m pytest tests/

# Run with debug logging
omega13 --log-level DEBUG

# Toggle recording (hotkey simulation)
omega13 --toggle
```

**For AI assistants:** See [AGENTS.md](AGENTS.md) for critical implementation details. Don't skip the "ANTI-PATTERNS" section—those are mistakes previous AIs made. Learn from them. Also note the threading constraints: the JACK callback is real-time and will punish you for blocking.

---

## 🔧 Troubleshooting

**"Capture Blocked - No Input Signal"**

* Omega-13 checks for silence to prevent empty recordings.
* Ensure your mic is not muted.
* Press `I` to ensure the correct JACK/PipeWire port is connected.

**Global Hotkey not working**

* Ensure the `omega13 --toggle` command works in a separate terminal window.
* Verify your Desktop Environment's keyboard shortcut settings.

**Transcription Failed / Slow**

* Check the Docker container: `docker logs -f whisper-server`.
* Ensure your GPU is accessible to Docker (`nvidia-smi`).

**bootstrap.sh fails to detect package manager**

* Supported: `dnf`, `apt`, `pacman`, `zypper`
* Manually install system dependencies for unsupported distros
* See `bootstrap.sh` lines 56-91 for required packages

**uv installation fails**

* The bootstrap script automatically falls back to standard `pip` and `venv`
* You can manually use: `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`

**Whisper build fails with OOM (Out of Memory)**

* Reduce CUDA architectures: `CUDA_ARCHITECTURES="86" ./bootstrap.sh --build` (single architecture)
* Use the pre-built image from Docker Hub (if available)
* Increase Docker memory limits in `compose.yml`

---

## 🏗️ Architecture (Natural Language Specification → Implementation)

**What I specified in natural language:**
- "Terminal UI, keyboard-driven"
- "Always recording in memory, save the past 13 seconds when triggered"
- "Detect voice activity automatically"
- "Transcribe locally, no cloud"
- "Work from anywhere in the OS, even on Wayland"

**What the AI compiled it into:**
* **Frontend:** Python `Textual` TUI - because terminals are timeless
* **Audio Backend:** `JACK` Client with ring buffer - real-time audio is hard, JACK handles it
* **Signal Detection:** RMS-based energy monitoring - math that actually works
* **Recording Controller:** State machine with 5 states - finite state machines prevent chaos
* **Transcription:** Local Docker whisper.cpp - privacy over convenience
* **IPC:** PID files + SIGUSR1 signals - Wayland workaround that actually works

**The implementation detail I never had to learn:** When you press record, it's already been recording in memory for 13 seconds. The ring buffer uses modulo wrapping. The write pointer continuously advances. On trigger, it reconstructs the temporal sequence from the pre-buffer (past) and live queue (present) into a linear WAV file. Then ships it to whisper.cpp.

I specified *what*. The AI figured out *how*.

**For AI agents:** [AGENTS.md](AGENTS.md) has the deep technical details. Ring buffer wrapping, thread safety, IPC via SIGUSR1—all the sharp edges are documented there.

---

## 💭 Things I Thought Might Be Cool (Maybe)

**Stuff that actually got built:**
* ✅ Voice-activated auto-record (turned out pretty useful)
* ✅ New session button (obvious in hindsight)

**Ideas that seemed good at 2am:**
* Load old sessions (do I ever actually go back and read things? no.)
* Fancy 3-pane layout with AI assistant (scope creep detected)
* Edit transcriptions in the UI (or just... re-record?)
* OpenCode integration for task lists (meta: AI writing tasks for AI)
* Live AI chat pane (at that point just use the AI directly?)
* Screenshot capture + vision model analysis (because why not add computer vision to an audio tool)
* Screencast recording (feature creep intensifies)

**Probably actually useful:**
* Transcription failover: GPU → CPU → Cloud (when the CUDA gods are angry)
* Health checks so it doesn't silently fail on startup
* Better formatting in the transcription buffer (it's a bit ugly)

Will any of these happen? Ask an AI to decide. That's how this works now.

---

## 🎭 The Bigger Picture

This project is an existence proof for **Natural Language Programming as a viable paradigm**. Not just CRUD apps or toy examples—actual systems programming with real-time constraints, threading, IPC, and all the gnarly bits. All specified in English.

**What this demonstrates:**
- **You don't need to know the implementation language.** I didn't write Python. I wrote requirements.
- **The AI is the compiler, not the programmer.** I'm still the programmer. I just program in English instead of Python.
- **Complex systems can be specified declaratively.** "I need a 13-second ring buffer for retroactive recording" → working JACK integration with modulo wrapping.
- **Iteration happens at the requirement level.** Bugs are described, not debugged. Features are specified, not implemented.

Is the generated code perfect? Probably not. Do I understand every line? Definitely not. Do I *need* to? No. Does it work? Yes. Did it solve my problem? Absolutely.

**The future of personal software:** You shouldn't need to learn programming languages to have custom software. You should just describe what you need. Natural Language Programming isn't the future—it's the present, running in a terminal near you.

---

*Programmed in English. Compiled by AI. Built for a human who thinks faster than they can type.*

import json
import queue
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import jack
import numpy as np
import soundfile as sf

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Label,
    OptionList,
    RichLog,
    Static,
)

# --- Transcription Module (uses podman containers) ---
try:
    from transcription import TranscriptionService, TranscriptionStatus, TranscriptionResult
    TRANSCRIPTION_AVAILABLE = True
except ImportError:
    TRANSCRIPTION_AVAILABLE = False
    TranscriptionService = None
    TranscriptionStatus = None
    TranscriptionResult = None

# --- Type Aliases ---
PortName = str
PortList = list[PortName]
ConfigDict = dict[str, Any]
MeterValue = tuple[float, ...]  # (peak_left, peak_right, ...)

# --- Configuration ---
BUFFER_DURATION = 10  # Seconds of history to keep
DEFAULT_CHANNELS = 2

class ConfigManager:
    """Manages persistent configuration for TimeMachine."""

    def __init__(self, config_path: Path = None):
        """
        Args:
            config_path: Optional custom path. Defaults to ~/.config/timemachine/config.json
        """
        if config_path is None:
            config_dir = Path.home() / ".config" / "timemachine"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_path = config_dir / "config.json"
        else:
            self.config_path = config_path

        self.config = self._load_config()

    def _load_config(self) -> ConfigDict:
        """Load configuration from disk, return defaults if not found."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # Ensure transcription config exists (for backward compatibility)
                    if "transcription" not in config:
                        config["transcription"] = {
                            "enabled": True,
                            "auto_transcribe": True,
                            "model_size": "large-v3-turbo",
                            "save_to_file": True
                        }
                    if "version" not in config or config["version"] < 2:
                        config["version"] = 2
                    return config
            else:
                # No config file, return defaults with transcription
                return {
                    "version": 2,
                    "input_ports": None,
                    "save_path": str(Path.cwd()),
                    "transcription": {
                        "enabled": True,
                        "auto_transcribe": True,
                        "model_size": "large-v3-turbo",
                        "save_to_file": True
                    }
                }
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load config: {e}")
            return {
                "version": 2,
                "input_ports": None,
                "save_path": str(Path.cwd()),
                "transcription": {
                    "enabled": True,
                    "auto_transcribe": True,
                    "model_size": "large-v3-turbo",
                    "save_to_file": True
                }
            }

    def save_config(self, config: ConfigDict) -> bool:
        """Save configuration to disk. Returns True on success."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except IOError as e:
            print(f"Error: Failed to save config: {e}")
            return False

    def get_input_ports(self) -> list[str] | None:
        """
        Get saved input port names from configuration.

        Returns:
            list[str] | None: List of JACK port names if configured and valid,
                              None if not configured or empty

        Note:
            Returned ports should be validated against current JACK graph
            using validate_ports_exist() before attempting connections.
        """
        saved_port_names = self.config.get("input_ports")
        if saved_port_names and isinstance(saved_port_names, list) and len(saved_port_names) > 0:
            return saved_port_names
        return None

    def set_input_ports(self, ports: list[str]) -> None:
        """
        Save input port configuration to disk.

        Args:
            ports: List of JACK port names to persist

        Side Effects:
            Immediately writes configuration to disk via save_config()
        """
        self.config["input_ports"] = ports
        self.save_config(self.config)

    def get_save_path(self) -> Path:
        """Get saved path for recordings. Defaults to CWD."""
        path_str = self.config.get("save_path")
        if path_str:
            path = Path(path_str)
            if path.exists() and path.is_dir():
                return path
        return Path.cwd()

    def set_save_path(self, path: str | Path):
        """Save the recording directory path."""
        self.config["save_path"] = str(path)
        self.save_config(self.config)

    def validate_ports_exist(self, client: jack.Client) -> tuple[bool, list[str]]:
        """
        Check if configured ports exist in current JACK graph.
        Returns: (all_exist: bool, missing_ports: list[str])
        """
        saved_ports = self.get_input_ports()
        if not saved_ports:
            return True, []

        # Get all available port names
        all_ports = client.get_ports()
        available_names = [port.name for port in all_ports]

        missing = []
        for port in saved_ports:
            if port not in available_names:
                missing.append(port)

        return len(missing) == 0, missing

    def get_transcription_enabled(self) -> bool:
        """Check if transcription feature is enabled."""
        return self.config.get("transcription", {}).get("enabled", True)

    def get_auto_transcribe(self) -> bool:
        """Check if auto-transcription after recording is enabled."""
        return self.config.get("transcription", {}).get("auto_transcribe", True)

    def get_transcription_model(self) -> str:
        """Get configured Whisper model size."""
        return self.config.get("transcription", {}).get("model_size", "large-v3-turbo")

    def get_save_transcription_to_file(self) -> bool:
        """Check if transcriptions should be saved to .txt files."""
        return self.config.get("transcription", {}).get("save_to_file", True)

    def set_transcription_config(
        self,
        enabled: Optional[bool] = None,
        auto_transcribe: Optional[bool] = None,
        model_size: Optional[str] = None,
        save_to_file: Optional[bool] = None
    ):
        """Update transcription configuration."""
        if "transcription" not in self.config:
            self.config["transcription"] = {}

        if enabled is not None:
            self.config["transcription"]["enabled"] = enabled
        if auto_transcribe is not None:
            self.config["transcription"]["auto_transcribe"] = auto_transcribe
        if model_size is not None:
            self.config["transcription"]["model_size"] = model_size
        if save_to_file is not None:
            self.config["transcription"]["save_to_file"] = save_to_file

        self.save_config(self.config)

class AudioEngine:
    """Handles JACK client, ring buffer, and file writing logic."""
    def __init__(
        self,
        buffer_duration: int = BUFFER_DURATION,
        config_manager: "ConfigManager | None" = None,
        num_channels: int = DEFAULT_CHANNELS
    ) -> None:
        self.buffer_duration = buffer_duration
        self.config_manager = config_manager
        self.client = jack.Client("TimeMachinePy")

        # Setup input ports
        self.input_ports = []
        for i in range(num_channels):
            self.input_ports.append(self.client.inports.register(f"in_{i+1}"))

        self.samplerate = int(self.client.samplerate)
        self.blocksize = self.client.blocksize
        self.channels = len(self.input_ports)

        # Ring Buffer setup
        self.ring_size = self.samplerate * self.buffer_duration
        self.ring_buffer = np.zeros((self.ring_size, self.channels), dtype='float32')
        self.write_ptr = 0
        self.buffer_filled = False

        # Recording state
        self.is_recording = False
        self.record_queue = queue.Queue()
        self.writer_thread = None
        self.stop_event = threading.Event()

        # Metering
        self.peaks = [0.0] * self.channels
        self.dbs = [-100.0] * self.channels

        # Connection tracking
        self.connected_sources = [None] * self.channels

        # Recording Path
        self.save_path = Path.cwd()
        if self.config_manager:
            self.save_path = self.config_manager.get_save_path()

        # Register callback
        self.client.set_process_callback(self.process)

    def start(self) -> None:
        """
        Activate JACK client and begin audio processing.

        Starts the JACK audio callback which will:
        - Continuously fill the ring buffer with incoming audio
        - Update peak meters in real-time
        - Send audio to file writer when recording
        """
        self.client.activate()
        print(f"JACK Client started. Sample rate: {self.samplerate}, Buffer: {self.buffer_duration}s")

    def stop(self) -> None:
        """
        Deactivate JACK client and release resources.

        Stops all audio processing and cleanly closes the JACK connection.
        Should be called before application exit.
        """
        self.client.deactivate()
        self.client.close()

    def _write_to_ring_buffer(self, data: np.ndarray, frames: int) -> None:
        """
        Write audio data to ring buffer, handling wrap-around.

        Args:
            data: Audio data array of shape (frames, channels)
            frames: Number of frames to write
        """
        remaining_space = self.ring_size - self.write_ptr

        if frames <= remaining_space:
            # Simple case: all data fits before end of buffer
            self.ring_buffer[self.write_ptr : self.write_ptr + frames] = data
            self.write_ptr += frames
        else:
            # Wrap-around case: split data into two parts
            part1 = remaining_space
            part2 = frames - remaining_space

            self.ring_buffer[self.write_ptr : self.write_ptr + part1] = data[:part1]
            self.ring_buffer[0 : part2] = data[part1:]
            self.write_ptr = part2
            self.buffer_filled = True

        if self.write_ptr >= self.ring_size:
            self.write_ptr = 0
            self.buffer_filled = True

    def process(self, frames: int) -> None:
        """High-priority audio callback."""
        try:
            # 1. Gather input data from all ports
            # Stack ports into a (frames, channels) array
            input_arrays = [port.get_array() for port in self.input_ports]
            data = np.stack(input_arrays, axis=-1)

            # 2. Update Meters
            self.peaks = np.max(np.abs(data), axis=0).tolist()
            # Convert linear peak to dB using 20*log10 formula
            # Clip noise floor at -100 dB for silence (1e-5 threshold)
            self.dbs = [20 * np.log10(p) if p > 1e-5 else -100.0 for p in self.peaks]

            # 3. Write to Ring Buffer (Memory)
            self._write_to_ring_buffer(data, frames)

            # 4. If Recording, send copy to file writer
            if self.is_recording:
                # We copy to avoid race conditions with the audio buffer being overwritten
                self.record_queue.put(data.copy())

        except Exception as e:
            # Avoid print in realtime thread usually, but okay for debugging
            pass

    def start_recording(self) -> str | None:
        """
        Begin recording audio to file, including buffered past audio.

        Reconstructs the ring buffer to include the full retroactive buffer
        (up to 10 seconds of past audio), then continues recording new
        incoming audio to a timestamped WAV file.

        Returns:
            str | None: Filename of created recording, or None if already recording

        Thread Safety:
            Safe to call from main thread; spawns background writer thread
        """
        if self.is_recording:
            return None

        self.is_recording = True
        self.stop_event.clear()

        # Reconstruct chronological buffer from ring buffer:
        # If buffer wrapped, combine tail (older audio) + head (recent audio)
        # Otherwise, just copy the filled portion
        if self.buffer_filled:
            part_old = self.ring_buffer[self.write_ptr:]  # Older audio after cursor
            part_new = self.ring_buffer[:self.write_ptr]  # Recent audio before cursor
            past_data = np.concatenate((part_old, part_new))
        else:
            past_data = self.ring_buffer[:self.write_ptr].copy()

        # Determine filename (tm-YYYY-MM-DD-THH-MM-SS.wav)
        # We subtract buffer duration to match the C code's logic (time recording 'started')
        start_time = datetime.now() - timedelta(seconds=self.buffer_duration)
        filename = start_time.strftime("tm-%Y-%m-%dT%H-%M-%S.wav")
        full_path = self.save_path / filename

        self.writer_thread = threading.Thread(
            target=self._file_writer,
            args=(str(full_path), past_data)
        )
        self.writer_thread.start()
        return filename

    def stop_recording(self) -> None:
        """
        Stop recording and finalize the audio file.

        Signals the file writer thread to stop, waits for it to finish
        writing all queued audio data, and cleans up the recording queue.

        Thread Safety:
            Safe to call from main thread; blocks until writer thread completes
        """
        self.is_recording = False
        self.stop_event.set()
        if self.writer_thread:
            self.writer_thread.join()

        # Drain queue to prevent memory leaks
        while not self.record_queue.empty():
            self.record_queue.get()

    def _file_writer(self, filename: str, pre_buffer_data: np.ndarray) -> None:
        """Background thread that writes audio to disk."""
        try:
            with sf.SoundFile(filename, mode='w', samplerate=self.samplerate, channels=self.channels) as file:
                # 1. Write the history buffer first
                file.write(pre_buffer_data)
                
                # 2. Continuously write incoming blocks
                while self.is_recording or not self.record_queue.empty():
                    try:
                        # Blocking get with timeout allows us to check is_recording flag
                        block = self.record_queue.get(timeout=0.1)
                        file.write(block)
                    except queue.Empty:
                        if not self.is_recording:
                            break
                            
        except Exception as e:
            print(f"File writer error: {e}")

    def get_available_output_ports(self) -> list[jack.Port]:
        """
        Get all available JACK output ports (audio sources).
        Returns list of Port objects with .name attribute.
        """
        try:
            # Get all audio output ports (sources that can be connected to our inputs)
            ports = self.client.get_ports(is_audio=True, is_output=True)
            return ports
        except Exception as e:
            print(f"Error getting available ports: {e}")
            return []

    def get_current_connections(self) -> list[str | None]:
        """
        Returns the currently connected source ports for registered input ports.
        Returns: [port_name_1, port_name_2, ...] or [None, ...] if not connected
        """
        try:
            current_connections = []
            for inport in self.input_ports:
                connections = self.client.get_all_connections(inport)
                name = connections[0].name if connections else None
                current_connections.append(name)

            return current_connections
        except Exception as e:
            print(f"Error getting current connections: {e}")
            return [None] * self.channels

    def disconnect_inputs(self):
        """
        Disconnect all inputs from in_1 and in_2.
        Safe to call even if not connected.
        """
        try:
            for inport in self.client.inports:
                connections = self.client.get_all_connections(inport)
                for source_port in connections:
                    self.client.disconnect(source_port, inport)
                    print(f"Disconnected {source_port.name} from {inport.name}")

            self.connected_sources = [None] * self.channels
        except Exception as e:
            print(f"Error disconnecting inputs: {e}")

    def connect_inputs(self, source_ports: list[str]) -> bool:
        """
        Connect source ports to our input ports.
        Returns: True on success, False on failure
        """
        # Safety check: Don't allow connection changes during recording
        if self.is_recording:
            print("Cannot change inputs while recording")
            return False

        if len(source_ports) != self.channels:
            print(f"Expected {self.channels} source ports, got {len(source_ports)}")
            return False

        try:
            for i, source in enumerate(source_ports):
                if source:
                    self.client.connect(source, self.input_ports[i])
                    print(f"Connected {source} → {self.input_ports[i].name}")

            # Update tracking
            self.connected_sources = source_ports.copy()

            return True
        except Exception as e:
            print(f"Error connecting inputs: {e}")
            return False

class VUMeter(Static):
    """A vertical bar displaying audio level."""
    level = reactive(0.0)
    db_level = reactive(-100.0)
    
    def watch_level(self, level: float) -> None:
        self.update_bar()

    def watch_db_level(self, db_level: float) -> None:
        self.update_bar()

    def _get_level_color(self, percentage: float) -> str:
        """
        Determine bar color based on audio level percentage.

        Args:
            percentage: Audio level as percentage (0-100)

        Returns:
            Color name: "green", "yellow", or "red"
        """
        if percentage > 90:
            return "red"
        elif percentage > 70:
            return "yellow"
        else:
            return "green"

    def _format_db_display(self, db_value: float) -> str:
        """
        Format dB value for display.

        Args:
            db_value: Decibel level

        Returns:
            Formatted string (e.g., " -12.3 dB" or "  -inf dB")
        """
        if db_value > -100:
            return f"{db_value:>5.1f} dB"
        else:
            return "-inf dB"

    def update_bar(self) -> None:
        """Update the visual bar display based on current level and dB values."""
        # Convert 0-1 float to 0-100 percentage
        pct = min(100, int(self.level * 100))

        # Determine color and formatting
        color = self._get_level_color(pct)
        level_bar_display = "|" * (pct // 2)
        db_str = self._format_db_display(self.db_level)

        self.update(f"[{color}]{level_bar_display:50s}[/] [bold]{db_str}[/]")


class TranscriptionDisplay(Static):
    """
    Widget for displaying transcription status and results.

    Shows loading states, progress, errors, and final transcription text
    in a scrollable RichLog widget with status indicators.
    """

    # Reactive properties for UI updates
    status = reactive("idle")
    progress = reactive(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.text_log = None
        self.status_label = None

    def compose(self) -> ComposeResult:
        """Build widget structure."""
        with Vertical():
            yield Label("Transcription", classes="transcription-title")
            yield Static("Ready", id="transcription-status", classes="status-idle")
            yield RichLog(id="transcription-log", wrap=True, highlight=True)

    def on_mount(self):
        """Cache widget references on mount."""
        self.text_log = self.query_one("#transcription-log", RichLog)
        self.status_label = self.query_one("#transcription-status", Static)

        # Set max lines to prevent memory issues with long transcriptions
        self.text_log.max_lines = 1000

    def watch_status(self, new_status: str) -> None:
        """React to status changes."""
        status_messages = {
            "idle": ("Ready", "status-idle"),
            "loading_model": ("Loading model...", "status-loading"),
            "processing": ("Transcribing...", "status-processing"),
            "completed": ("Complete", "status-complete"),
            "error": ("Error", "status-error")
        }

        message, css_class = status_messages.get(
            new_status,
            ("Unknown", "status-idle")
        )

        # Update status label
        self.status_label.update(message)

        # Update CSS classes
        self.status_label.remove_class(
            "status-idle", "status-loading", "status-processing",
            "status-complete", "status-error"
        )
        self.status_label.add_class(css_class)

    def watch_progress(self, new_progress: float):
        """React to progress updates."""
        if self.status == "processing":
            pct = int(new_progress * 100)
            self.status_label.update(f"Transcribing... {pct}%")

    def update_text(self, text: str):
        """Update transcription text (thread-safe via Textual's message queue)."""
        self.text_log.clear()
        self.text_log.write(text)

    def append_segment(self, segment_text: str, timestamp: str = ""):
        """Append a single segment (for streaming updates)."""
        if timestamp:
            self.text_log.write(f"[dim]{timestamp}[/dim] {segment_text}")
        else:
            self.text_log.write(segment_text)

    def show_error(self, error_message: str):
        """Display error message."""
        self.status = "error"
        self.text_log.clear()
        self.text_log.write(f"[red]Error:[/red] {error_message}")

    def clear(self):
        """Clear transcription text content only."""
        # Don't reset status - preserve current state
        self.text_log.clear()

    def reset(self):
        """Reset widget to idle state."""
        self.status = "idle"
        self.progress = 0.0
        self.text_log.clear()


class InputSelectionScreen(ModalScreen[tuple[str, str] | None]):
    """Modal screen for selecting two JACK input ports."""

    CSS = """
    InputSelectionScreen {
        align: center middle;
    }

    #selection-dialog {
        width: 70;
        height: 25;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #selection-dialog #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #selection-dialog #help {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    #port-list {
        height: 15;
        border: solid $primary;
        margin: 1 0;
        background: $surface-lighten-1;
    }

    #button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    #button-row Button {
        margin: 0 1;
    }

    #mode-selection {
        height: 5;
        border: solid $primary;
        margin: 1 0;
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm Selection"),
    ]

    def __init__(self, available_ports: list[jack.Port], current_ports: list[str | None]):
        """
        Args:
            available_ports: List of JACK output ports to choose from
            current_ports: Currently connected ports (for highlighting)
        """
        super().__init__()
        self.available_ports = available_ports
        self.current_ports = current_ports
        self.selection_step = 0  # 0 = Mode Selection, 1 = Port 1, 2 = Port 2
        self.selected_mode = "Stereo" if len(current_ports) == 2 else "Mono"
        self.selected_port1 = None
        self.selected_port2 = None

    def compose(self) -> ComposeResult:
        with Container(id="selection-dialog"):
            yield Label("Select Input Mode", id="title")
            yield Static("Choose whether you want Mono or Stereo input:", id="help")
            
            with Vertical(id="mode-selection"):
                yield Button("Mono", id="mono-btn", variant="primary")
                yield Button("Stereo", id="stereo-btn", variant="primary")

            yield OptionList(id="port-list")

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="error", id="cancel-btn")
                yield Button("Confirm", variant="primary", id="confirm-btn")

    def on_mount(self):
        """Populate option list with available ports and set initial UI state."""
        # Initial display states
        self.query_one("#port-list").display = False
        self.query_one("#confirm-btn").display = False

        option_list = self.query_one("#port-list", OptionList)
        for port in self.available_ports:
            # Format: "Device Name: port_name [PHYSICAL]"
            display_name = self._format_port_name(port)
            option_list.add_option(display_name)

        # Highlight currently connected port if in list
        if self.selection_step == 1 and self.current_ports[0]:
            self._highlight_port(self.current_ports[0])

    def _format_port_name(self, port: jack.Port) -> str:
        """Format port for display with visual indicators."""
        is_physical = "[PHYSICAL]" if port.is_physical else ""
        return f"{port.name} {is_physical}".strip()

    def _highlight_port(self, port_name: str):
        """Highlight a port in the list if it exists."""
        option_list = self.query_one("#port-list", OptionList)
        for idx, port in enumerate(self.available_ports):
            if port.name == port_name:
                option_list.highlighted = idx
                break

    def action_confirm(self):
        """Handle confirmation of port selection."""
        if self.selection_step == 0:
            return

        option_list = self.query_one("#port-list", OptionList)
        selected_option_index = option_list.highlighted

        if selected_option_index is None:
            self.notify("Please select a port", severity="warning")
            return

        selected_port = self.available_ports[selected_option_index]

        if self.selection_step == 1:
            self.selected_port1 = selected_port.name
            if self.selected_mode == "Mono":
                self.dismiss([self.selected_port1])
            else:
                self._switch_to_step_2()
        else:
            self.selected_port2 = selected_port.name
            if self.selected_port1 == self.selected_port2:
                self.notify("Cannot use the same port for both channels", severity="error")
                return
            self.dismiss([self.selected_port1, self.selected_port2])

    def _switch_to_port_selection(self, mode: str):
        self.selected_mode = mode
        self.selection_step = 1

        # Cache widget queries for visibility updates
        self.query_one("#mode-selection").display = False
        self.query_one("#port-list").display = True
        self.query_one("#confirm-btn").display = True

        self.query_one("#title", Label).update(f"Select Input Port (Channel 1 of {'2' if mode == 'Stereo' else '1'})")
        self.query_one("#help", Static).update("Choose from available JACK output ports:")
        
        # Repopulate/Refresh list if needed (it was already populated in on_mount)
        if len(self.current_ports) > 0 and self.current_ports[0]:
            self._highlight_port(self.current_ports[0])

    def _switch_to_step_2(self):
        """Transition to selecting the second port."""
        self.selection_step = 2
        self.query_one("#title", Label).update("Select Input Port (Channel 2 of 2)")

        if len(self.current_ports) > 1 and self.current_ports[1]:
            self._highlight_port(self.current_ports[1])

    def action_cancel(self):
        """Cancel selection and close dialog."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        """Handle button clicks."""
        if event.button.id == "cancel-btn":
            self.action_cancel()
        elif event.button.id == "confirm-btn":
            self.action_confirm()
        elif event.button.id == "mono-btn":
            self._switch_to_port_selection("Mono")
        elif event.button.id == "stereo-btn":
            self._switch_to_port_selection("Stereo")

class DirectorySelectionScreen(ModalScreen[Path | None]):
    """Modal screen for selecting a directory to save recordings."""
    
    CSS = """
    DirectorySelectionScreen {
        align: center middle;
    }

    #directory-dialog {
        width: 80;
        height: 30;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #directory-dialog #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #directory-dialog #help {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    #directory-tree {
        height: 18;
        border: solid $primary;
        margin: 1 0;
    }

    #button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    #button-row Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Select Directory"),
    ]

    def __init__(self, initial_path: Path):
        super().__init__()
        self.initial_path = initial_path
        self.selected_path = initial_path

    def compose(self) -> ComposeResult:
        with Container(id="directory-dialog"):
            yield Label("Select Save Directory", id="title")
            yield Static(f"Current selection: {self.initial_path}", id="help")
            
            yield DirectoryTree(str(self.initial_path.anchor), id="directory-tree")

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="error", id="cancel-btn")
                yield Button("Select Current", variant="primary", id="confirm-btn")

    def on_mount(self):
        # Focus the tree and try to expand to the initial path if possible
        tree = self.query_one("#directory-tree", DirectoryTree)
        tree.focus()

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected):
        """Update the help text when a directory is selected in the tree."""
        self.selected_path = Path(event.path)
        self.query_one("#help", Static).update(f"Current selection: {self.selected_path}")

    def action_confirm(self):
        """Confirm the current selection."""
        self.dismiss(self.selected_path)

    def action_cancel(self):
        """Cancel and close."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel-btn":
            self.action_cancel()
        elif event.button.id == "confirm-btn":
            self.action_confirm()

class TimeMachineApp(App):
    CSS = """
    Screen {
        align: center middle;
        background: $surface;
    }

    /* Two-Pane Layout */
    #app-layout {
        width: 100%;
        height: 100%;
    }

    /* Left Pane: Audio Controls */
    #audio-pane {
        width: 50%;
        border: solid $accent;
        padding: 1 2;
        background: $surface-lighten-1;
    }

    /* Right Pane: Transcription */
    #transcription-pane {
        width: 50%;
        border: solid $accent;
        padding: 1 2;
        background: $surface-lighten-1;
        margin-left: 1;
    }

    .title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .status-idle {
        color: $text;
        background: $success;
        padding: 1;
        text-align: center;
        text-style: bold;
    }

    .status-recording {
        color: $text;
        background: $error;
        padding: 1;
        text-align: center;
        text-style: bold;
    }

    #connection-status {
        text-align: center;
        padding: 0 1;
        margin-top: 1;
        border: solid $primary;
        background: $surface-darken-1;
    }

    #meters {
        height: 5;
        margin-top: 1;
        border: heavy $primary;
    }

    .help-text {
        text-align: center;
        width: 100%;
        margin-top: 1;
    }

    Label {
        width: 100%;
    }

    /* Transcription Widget Styles */
    .transcription-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }

    #transcription-status {
        text-align: center;
        padding: 1;
        margin-bottom: 1;
        border: solid $primary;
    }

    .status-loading {
        color: $text;
        background: $warning;
    }

    .status-processing {
        color: $text;
        background: $warning;
    }

    .status-complete {
        color: $text;
        background: $success;
    }

    .status-error {
        color: $text;
        background: $error;
    }

    #transcription-log {
        height: 100%;
        border: solid $primary;
        background: $surface-darken-1;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_record", "Record/Stop", priority=True),
        Binding("i", "open_input_selector", "Select Inputs"),
        Binding("p", "open_directory_selector", "Set Save Path"),
        Binding("t", "manual_transcribe", "Transcribe"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        # Main horizontal container for two-pane layout
        with Horizontal(id="app-layout"):

            # LEFT PANE: Audio Controls (existing UI)
            with Container(id="audio-pane", classes="left-pane"):
                yield Label("TIME MACHINE", classes="title")
                yield Static("IDLE - Ready to Capture", id="status-bar", classes="status-idle")
                yield Static("Inputs: Loading...", id="connection-status")
                yield Static("Save Path: Loading...", id="path-status")
                yield Static("\nBuffers filled: ", id="buffer-info")

                with Vertical(id="meters"):
                    yield Label("Channel 1", id="label-1")
                    yield VUMeter(id="meter-1")
                    yield Label("Channel 2", id="label-2")
                    yield VUMeter(id="meter-2")

                yield Static(
                    "\n[dim]SPACE to Capture | I Inputs | P Save Path | T Transcribe[/dim]",
                    classes="help-text"
                )

            # RIGHT PANE: Transcription Display (new feature)
            with Container(id="transcription-pane", classes="right-pane"):
                yield TranscriptionDisplay(id="transcription-display")

        yield Footer()

    def on_mount(self):
        # Initialize Audio Engine
        try:
            self.config_manager = ConfigManager()
            saved_ports = self.config_manager.get_input_ports()
            num_channels = len(saved_ports) if saved_ports else DEFAULT_CHANNELS

            self.engine = AudioEngine(config_manager=self.config_manager, num_channels=num_channels)
            self.engine.start()

            # Attempt to load and connect saved configuration
            self._load_and_connect_saved_inputs()
            self._update_path_status()
            self._update_meter_visibility()

            # Initialize Transcription Service (HTTP API to whisper-server)
            if TRANSCRIPTION_AVAILABLE:
                try:
                    self.transcription_service = TranscriptionService(
                        server_url="http://localhost:8080",
                        inference_path="/inference",
                        timeout=600  # 10 minutes
                    )

                    self.notify(
                        "Transcription ready (whisper-server API)",
                        severity="information",
                        timeout=3
                    )

                except Exception as e:
                    self.transcription_service = None
                    self.notify(
                        f"Transcription initialization failed: {e}",
                        severity="warning",
                        timeout=5
                    )
            else:
                self.transcription_service = None
                self.notify(
                    "Transcription module not found. Check transcription.py is present.",
                    severity="information",
                    timeout=5
                )

            self.set_interval(0.05, self.update_meters) # Update UI at 20FPS
        except Exception as e:
            self.exit(message=f"Failed to start JACK client: {e}")

    def _update_meter_visibility(self):
        """Show/hide meters based on engine channels."""
        is_stereo = self.engine.channels == 2
        self.query_one("#label-2").display = is_stereo
        self.query_one("#meter-2").display = is_stereo
        
        if not is_stereo:
            self.query_one("#label-1").update("Channel (Mono)")
        else:
            self.query_one("#label-1").update("Channel 1")

    def on_unmount(self):
        if hasattr(self, 'engine'):
            self.engine.stop_recording()
            self.engine.stop()

        if hasattr(self, 'transcription_service') and self.transcription_service is not None:
            self.transcription_service.cleanup()

    def update_meters(self):
        """Poll audio engine for levels."""
        peaks = self.engine.peaks

        # Update VU Meters (cache queries to avoid redundant DOM traversal)
        meter_1 = self.query_one("#meter-1", VUMeter)
        meter_1.level = peaks[0]
        meter_1.db_level = self.engine.dbs[0]

        if len(peaks) > 1 and self.engine.channels > 1:
            meter_2 = self.query_one("#meter-2", VUMeter)
            meter_2.level = peaks[1]
            meter_2.db_level = self.engine.dbs[1]

        # Update Buffer Info
        if not self.engine.is_recording:
            fill_pct = (self.engine.write_ptr / self.engine.ring_size) * 100
            if self.engine.buffer_filled:
                fill_pct = 100
            self.query_one("#buffer-info").update(f"Pre-Record Buffer: {fill_pct:.1f}%")

    def _load_and_connect_saved_inputs(self):
        """Load saved input configuration and attempt connection."""
        saved_ports = self.config_manager.get_input_ports()

        if not saved_ports:
            self.query_one("#connection-status").update("Inputs: [yellow]Not configured[/yellow]")
            self.notify("No input configuration found. Press 'i' to select inputs.", severity="information")
            return

        # Validate ports exist
        valid, missing = self.config_manager.validate_ports_exist(self.engine.client)

        if not valid:
            self.query_one("#connection-status").update("Inputs: [red]Invalid config[/red]")
            self.notify(f"Saved ports not found: {', '.join(missing)}. Press 'i' to reconfigure.", severity="warning")
            return

        # Attempt connection
        try:
            success = self.engine.connect_inputs(saved_ports)
            if success:
                self._update_connection_status(saved_ports)
                self.notify("Input connections restored", severity="information")
            else:
                raise Exception("Connection failed")
        except Exception as e:
            self.query_one("#connection-status").update("Inputs: [red]Connection failed[/red]")
            self.notify(f"Failed to connect inputs: {e}", severity="error")

    def _update_connection_status(self, ports: list[str]):
        """Update the connection status display in the UI."""
        short_names = [port_name.split(':')[-1] if ':' in port_name else port_name for port_name in ports]
        
        if len(short_names) == 2:
            status_text = f"Inputs: [green]{short_names[0]}[/green] | [green]{short_names[1]}[/green]"
        else:
            status_text = f"Input: [green]{short_names[0]}[/green] (Mono)"
            
        self.query_one("#connection-status").update(status_text)

    def _update_path_status(self):
        """Update the save path display in the UI."""
        path = self.engine.save_path
        # Truncate if too long for display
        path_str = str(path)
        if len(path_str) > 50:
            path_str = f"...{path_str[-47:]}"
        self.query_one("#path-status").update(f"Save Path: [cyan]{path_str}[/cyan]")

    def action_toggle_record(self):
        """Toggle recording with automatic transcription trigger."""
        status_bar = self.query_one("#status-bar")

        if self.engine.is_recording:
            # STOP RECORDING
            self.engine.stop_recording()
            status_bar.update("IDLE - Saved.")
            status_bar.remove_class("status-recording")
            status_bar.add_class("status-idle")

            # TRIGGER AUTO-TRANSCRIPTION (if enabled)
            if TRANSCRIPTION_AVAILABLE and self.config_manager.get_auto_transcribe():
                last_file = self._get_last_recording_path()
                if last_file and last_file.exists():
                    self._start_transcription(last_file)
        else:
            # START RECORDING
            fname = self.engine.start_recording()
            if fname:
                self._current_recording_filename = fname  # Track for transcription
                status_bar.update(f"RECORDING... \nFile: {fname}")
                status_bar.remove_class("status-idle")
                status_bar.add_class("status-recording")

    def _restart_engine_with_channels(self, num_channels: int) -> None:
        """
        Restart audio engine with a different channel count.

        Args:
            num_channels: New number of input channels (1 for mono, 2 for stereo)
        """
        self.engine.stop()
        self.engine = AudioEngine(
            config_manager=self.config_manager,
            num_channels=num_channels
        )
        self.engine.start()
        self._update_meter_visibility()

    def _apply_input_connections(self, selected_ports: list[str]) -> None:
        """
        Apply new input port connections and update configuration.

        Args:
            selected_ports: List of JACK port names to connect

        Raises:
            Exception: If connection fails
        """
        success = self.engine.connect_inputs(selected_ports)
        if success:
            # Save configuration
            self.config_manager.set_input_ports(selected_ports)

            # Update UI
            self._update_connection_status(selected_ports)
            self.notify("Input connections updated", severity="success")
        else:
            raise Exception("Connection returned False")

    def _get_last_recording_path(self) -> Optional[Path]:
        """Get path to the most recently saved recording."""
        if hasattr(self, '_current_recording_filename'):
            return self.engine.save_path / self._current_recording_filename
        return None

    def _start_transcription(self, audio_file: Path):
        """Start async transcription of audio file."""
        if not TRANSCRIPTION_AVAILABLE:
            return

        if not hasattr(self, 'transcription_service') or self.transcription_service is None:
            self.notify("Transcription service not initialized", severity="warning")
            return

        # Update UI to show processing state
        transcription_display = self.query_one("#transcription-display", TranscriptionDisplay)
        transcription_display.clear()  # Clear old text first
        transcription_display.status = "processing"  # Then set status
        transcription_display.progress = 0.0

        # Define callback for transcription completion
        def on_complete(result: TranscriptionResult):
            """Handle transcription result (called from worker thread)."""
            # Use call_from_thread to safely update UI from background thread
            self.call_from_thread(self._handle_transcription_result, result, audio_file)

        def on_progress(progress: float):
            """Handle progress updates (called from worker thread)."""
            self.call_from_thread(self._update_transcription_progress, progress)

        # Start async transcription
        self.transcription_service.transcribe_async(
            audio_file,
            callback=on_complete,
            progress_callback=on_progress
        )

    def _update_transcription_progress(self, progress: float):
        """Update transcription progress (thread-safe UI update)."""
        transcription_display = self.query_one("#transcription-display", TranscriptionDisplay)
        transcription_display.progress = progress

    def _handle_transcription_result(self, result: TranscriptionResult, audio_file: Path):
        """Handle completed transcription (thread-safe UI update)."""
        transcription_display = self.query_one("#transcription-display", TranscriptionDisplay)

        if result.status == TranscriptionStatus.COMPLETED:
            transcription_display.update_text(result.text)
            transcription_display.status = "completed"

            # Save to file if enabled
            if self.config_manager.get_save_transcription_to_file():
                self._save_transcription_file(result.text, audio_file)

            self.notify(
                f"Transcription complete ({result.language})",
                severity="information"
            )
        else:
            transcription_display.show_error(result.error or "Unknown error")
            self.notify(
                "Transcription failed",
                severity="error"
            )

    def _save_transcription_file(self, text: str, audio_file: Path):
        """Save transcription text to .txt file alongside WAV."""
        try:
            # Create .txt filename with same timestamp as WAV
            txt_file = audio_file.with_suffix('.txt')

            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(text)

            self.notify(f"Transcription saved: {txt_file.name}", severity="information")
        except IOError as e:
            self.notify(f"Failed to save transcription: {e}", severity="error")

    def action_manual_transcribe(self):
        """Manual transcription trigger (bound to 'T' key)."""
        if not TRANSCRIPTION_AVAILABLE:
            self.notify("Transcription module not found. Check transcription.py is present.", severity="warning")
            return

        last_file = self._get_last_recording_path()
        if not last_file or not last_file.exists():
            self.notify("No recording to transcribe", severity="warning")
            return

        self._start_transcription(last_file)

    def action_open_input_selector(self):
        """Open the input selection modal screen."""

        # Safety check: don't allow changes during recording
        if self.engine.is_recording:
            self.notify("Cannot change inputs while recording", severity="warning")
            return

        # Get available ports and current connections
        try:
            available_ports = self.engine.get_available_output_ports()

            if not available_ports:
                self.notify("No JACK output ports available", severity="error")
                return

            current_ports = self.engine.get_current_connections()

            # Push the modal screen
            def handle_selection(result: list[str] | None):
                """Callback when selection screen closes."""
                if result is None:
                    # User cancelled
                    return

                # Check if we need to restart the engine due to channel count change
                if len(result) != self.engine.channels:
                    self._restart_engine_with_channels(len(result))
                else:
                    # Disconnect old connections (if engine wasn't restarted)
                    self.engine.disconnect_inputs()

                # Connect new ports
                try:
                    self._apply_input_connections(result)
                except Exception as e:
                    self.notify(f"Failed to connect: {e}", severity="error")
                    self.query_one("#connection-status").update("Inputs: [red]Connection failed[/red]")

            self.push_screen(
                InputSelectionScreen(available_ports, current_ports),
                handle_selection
            )

        except Exception as e:
            self.notify(f"Error opening input selector: {e}", severity="error")

    def action_open_directory_selector(self):
        """Open the directory selection modal screen."""
        if self.engine.is_recording:
            self.notify("Cannot change save path while recording", severity="warning")
            return

        def handle_path_selection(result: Path | None):
            if result:
                self.engine.save_path = result
                self.config_manager.set_save_path(result)
                self._update_path_status()
                self.notify(f"Save path updated: {result.name}", severity="success")

        self.push_screen(
            DirectorySelectionScreen(self.engine.save_path),
            handle_path_selection
        )

if __name__ == "__main__":
    app = TimeMachineApp()
    app.run()

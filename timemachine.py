import sys
import threading
import queue
import time
import datetime
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import jack

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, ProgressBar, Label, Button, OptionList
from textual.screen import ModalScreen
from textual.reactive import reactive
from textual.binding import Binding

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

    def _load_config(self) -> dict:
        """Load configuration from disk, return defaults if not found."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    return config
            else:
                # No config file, return empty defaults
                return {"version": 1, "input_ports": None}
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load config: {e}")
            return {"version": 1, "input_ports": None}

    def save_config(self, config: dict) -> bool:
        """Save configuration to disk. Returns True on success."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except IOError as e:
            print(f"Error: Failed to save config: {e}")
            return False

    def get_input_ports(self) -> list[str] | None:
        """Get saved input port names. Returns None if not configured."""
        ports = self.config.get("input_ports")
        if ports and isinstance(ports, list) and len(ports) == 2:
            return ports
        return None

    def set_input_ports(self, port1: str, port2: str):
        """Save input port configuration."""
        self.config["input_ports"] = [port1, port2]
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

class AudioEngine:
    """Handles JACK client, ring buffer, and file writing logic."""
    def __init__(self, buffer_duration=BUFFER_DURATION, config_manager=None):
        self.buffer_duration = buffer_duration
        self.config_manager = config_manager
        self.client = jack.Client("TimeMachinePy")

        # Setup input ports
        self.client.inports.register("in_1")
        self.client.inports.register("in_2")

        self.samplerate = int(self.client.samplerate)
        self.blocksize = self.client.blocksize
        self.channels = len(self.client.inports)

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

        # Connection tracking
        self.connected_sources = [None, None]

        # Register callback
        self.client.set_process_callback(self.process)

    def start(self):
        self.client.activate()
        print(f"JACK Client started. Sample rate: {self.samplerate}, Buffer: {self.buffer_duration}s")

    def stop(self):
        self.client.deactivate()
        self.client.close()

    def process(self, frames):
        """High-priority audio callback."""
        try:
            # 1. Gather input data from all ports
            # Stack ports into a (frames, channels) array
            input_arrays = [port.get_array() for port in self.client.inports]
            data = np.stack(input_arrays, axis=-1)
            
            # 2. Update Meters (Peak decay logic could go here, keeping it simple for now)
            self.peaks = np.max(np.abs(data), axis=0).tolist()
            
            # 3. Write to Ring Buffer (Memory)
            # Handle wrap-around writing
            remaining_space = self.ring_size - self.write_ptr
            
            if frames <= remaining_space:
                self.ring_buffer[self.write_ptr : self.write_ptr + frames] = data
                self.write_ptr += frames
            else:
                # We need to wrap around
                part1 = remaining_space
                part2 = frames - remaining_space
                
                self.ring_buffer[self.write_ptr : self.write_ptr + part1] = data[:part1]
                self.ring_buffer[0 : part2] = data[part1:]
                self.write_ptr = part2
                self.buffer_filled = True
                
            if self.write_ptr >= self.ring_size:
                self.write_ptr = 0
                self.buffer_filled = True

            # 4. If Recording, send copy to file writer
            if self.is_recording:
                # We copy to avoid race conditions with the audio buffer being overwritten
                self.record_queue.put(data.copy())
                
        except Exception as e:
            # Avoid print in realtime thread usually, but okay for debugging
            pass

    def start_recording(self):
        if self.is_recording:
            return
            
        self.is_recording = True
        self.stop_event.clear()
        
        # Construct the 'past' audio from the ring buffer
        # The oldest data is at self.write_ptr (current cursor), going forward to end, then 0 to cursor
        if self.buffer_filled:
            part_old = self.ring_buffer[self.write_ptr:]
            part_new = self.ring_buffer[:self.write_ptr]
            past_data = np.concatenate((part_old, part_new))
        else:
            past_data = self.ring_buffer[:self.write_ptr].copy()
            
        # Determine filename (tm-YYYY-MM-DD-THH-MM-SS.wav)
        # We subtract buffer duration to match the C code's logic (time recording 'started')
        start_time = datetime.datetime.now() - datetime.timedelta(seconds=self.buffer_duration)
        filename = start_time.strftime("tm-%Y-%m-%dT%H-%M-%S.wav")
        
        self.writer_thread = threading.Thread(
            target=self._file_writer,
            args=(filename, past_data)
        )
        self.writer_thread.start()
        return filename

    def stop_recording(self):
        self.is_recording = False
        self.stop_event.set()
        if self.writer_thread:
            self.writer_thread.join()
        
        # Drain queue
        while not self.record_queue.empty():
            self.record_queue.get()

    def _file_writer(self, filename, pre_buffer_data):
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

    def get_current_connections(self) -> tuple[str | None, str | None]:
        """
        Returns the currently connected source ports for in_1 and in_2.
        Returns: (port_name_1, port_name_2) or (None, None) if not connected
        """
        try:
            connections_1 = self.client.get_all_connections(self.client.inports[0])
            connections_2 = self.client.get_all_connections(self.client.inports[1])

            port1 = connections_1[0].name if connections_1 else None
            port2 = connections_2[0].name if connections_2 else None

            return (port1, port2)
        except Exception as e:
            print(f"Error getting current connections: {e}")
            return (None, None)

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

            self.connected_sources = [None, None]
        except Exception as e:
            print(f"Error disconnecting inputs: {e}")

    def connect_inputs(self, source_port1: str, source_port2: str) -> bool:
        """
        Connect two source ports to in_1 and in_2 respectively.
        Returns: True on success, False on failure
        Raises: JackError if ports don't exist or connection fails
        """
        # Safety check: Don't allow connection changes during recording
        if self.is_recording:
            print("Cannot change inputs while recording")
            return False

        try:
            # Connect the source ports to our input ports
            self.client.connect(source_port1, self.client.inports[0])
            self.client.connect(source_port2, self.client.inports[1])

            # Update tracking
            self.connected_sources = [source_port1, source_port2]

            print(f"Connected {source_port1} → {self.client.inports[0].name}")
            print(f"Connected {source_port2} → {self.client.inports[1].name}")

            return True
        except Exception as e:
            print(f"Error connecting inputs: {e}")
            return False

class VUMeter(Static):
    """A vertical bar displaying audio level."""
    level = reactive(0.0)
    
    def watch_level(self, level: float):
        self.update_bar()

    def update_bar(self):
        # Logarithmic scale approximation for display
        # Convert 0-1 float to 0-100 percentage
        pct = min(100, int(self.level * 100))
        
        # Visual color changes based on level
        color = "green"
        if pct > 70: color = "yellow"
        if pct > 90: color = "red"
        
        bar_str = "|" * (pct // 2)
        self.update(f"[{color}]{bar_str}[/]")

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
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm Selection"),
    ]

    def __init__(self, available_ports: list[jack.Port], current_ports: tuple[str, str]):
        """
        Args:
            available_ports: List of JACK output ports to choose from
            current_ports: Currently connected ports (for highlighting)
        """
        super().__init__()
        self.available_ports = available_ports
        self.current_ports = current_ports
        self.selection_step = 1  # 1 = selecting for Channel 1, 2 = selecting for Channel 2
        self.selected_port1 = None
        self.selected_port2 = None

    def compose(self) -> ComposeResult:
        with Container(id="selection-dialog"):
            yield Label("Select Input Port for Channel 1", id="title")
            yield Static("Choose from available JACK output ports:", id="help")
            yield OptionList(id="port-list")
            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="error", id="cancel-btn")
                yield Button("Confirm", variant="primary", id="confirm-btn")

    def on_mount(self):
        """Populate option list with available ports."""
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
        option_list = self.query_one("#port-list", OptionList)
        selected_idx = option_list.highlighted

        if selected_idx is None:
            self.notify("Please select a port", severity="warning")
            return

        selected_port = self.available_ports[selected_idx]

        if self.selection_step == 1:
            # Save first selection, move to step 2
            self.selected_port1 = selected_port.name
            self._switch_to_step_2()
        else:
            # Save second selection, return result
            self.selected_port2 = selected_port.name

            # Validate: can't select same port twice
            if self.selected_port1 == self.selected_port2:
                self.notify("Cannot use the same port for both channels", severity="error")
                return

            self.dismiss((self.selected_port1, self.selected_port2))

    def _switch_to_step_2(self):
        """Transition to selecting the second port."""
        self.selection_step = 2
        self.query_one("#title", Label).update("Select Input Port for Channel 2")

        # Highlight currently selected port if applicable
        if self.current_ports[1]:
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

class TimeMachineApp(App):
    CSS = """
    Screen {
        align: center middle;
        background: $surface;
    }
    
    #main-container {
        width: 80%;
        height: auto;
        border: solid $accent;
        padding: 1 2;
        background: $surface-lighten-1;
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
    """

    BINDINGS = [
        Binding("space", "toggle_record", "Record/Stop", priority=True),
        Binding("i", "open_input_selector", "Select Inputs"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Label("TIME MACHINE", classes="title")
            yield Static("IDLE - Ready to Capture", id="status-bar", classes="status-idle")

            yield Static("Inputs: Loading...", id="connection-status")

            yield Static("\nBuffers filled: ", id="buffer-info")

            with Vertical(id="meters"):
                yield Label("Channel 1")
                yield VUMeter(id="meter-1")
                yield Label("Channel 2")
                yield VUMeter(id="meter-2")

            yield Static("\n[dim]Press SPACE to Capture | Press I for Inputs[/dim]", classes="help-text")
        yield Footer()

    def on_mount(self):
        # Initialize Audio Engine
        try:
            self.config_manager = ConfigManager()
            self.engine = AudioEngine(config_manager=self.config_manager)
            self.engine.start()

            # Attempt to load and connect saved configuration
            self._load_and_connect_saved_inputs()

            self.set_interval(0.05, self.update_meters) # Update UI at 20FPS
        except Exception as e:
            self.exit(message=f"Failed to start JACK client: {e}")

    def on_unmount(self):
        if hasattr(self, 'engine'):
            self.engine.stop_recording()
            self.engine.stop()

    def update_meters(self):
        """Poll audio engine for levels."""
        peaks = self.engine.peaks
        
        # Update VU Meters
        self.query_one("#meter-1", VUMeter).level = peaks[0]
        if len(peaks) > 1:
            self.query_one("#meter-2", VUMeter).level = peaks[1]

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
            success = self.engine.connect_inputs(saved_ports[0], saved_ports[1])
            if success:
                self._update_connection_status(saved_ports[0], saved_ports[1])
                self.notify("Input connections restored", severity="information")
            else:
                raise Exception("Connection failed")
        except Exception as e:
            self.query_one("#connection-status").update("Inputs: [red]Connection failed[/red]")
            self.notify(f"Failed to connect inputs: {e}", severity="error")

    def _update_connection_status(self, port1: str, port2: str):
        """Update the connection status display in the UI."""
        # Shorten port names for display
        short1 = port1.split(':')[-1] if ':' in port1 else port1
        short2 = port2.split(':')[-1] if ':' in port2 else port2

        status_text = f"Inputs: [green]{short1}[/green] | [green]{short2}[/green]"
        self.query_one("#connection-status").update(status_text)

    def action_toggle_record(self):
        status_bar = self.query_one("#status-bar")

        if self.engine.is_recording:
            # STOP
            self.engine.stop_recording()
            status_bar.update("IDLE - Saved.")
            status_bar.remove_class("status-recording")
            status_bar.add_class("status-idle")
        else:
            # START
            fname = self.engine.start_recording()
            status_bar.update(f"RECORDING... \nFile: {fname}")
            status_bar.remove_class("status-idle")
            status_bar.add_class("status-recording")

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
            def handle_selection(result: tuple[str, str] | None):
                """Callback when selection screen closes."""
                if result is None:
                    # User cancelled
                    return

                port1, port2 = result

                # Disconnect old connections
                self.engine.disconnect_inputs()

                # Connect new ports
                try:
                    success = self.engine.connect_inputs(port1, port2)
                    if success:
                        # Save configuration
                        self.config_manager.set_input_ports(port1, port2)

                        # Update UI
                        self._update_connection_status(port1, port2)
                        self.notify("Input connections updated", severity="success")
                    else:
                        raise Exception("Connection returned False")

                except Exception as e:
                    self.notify(f"Failed to connect: {e}", severity="error")
                    self.query_one("#connection-status").update("Inputs: [red]Connection failed[/red]")

            self.push_screen(
                InputSelectionScreen(available_ports, current_ports),
                handle_selection
            )

        except Exception as e:
            self.notify(f"Error opening input selector: {e}", severity="error")

if __name__ == "__main__":
    app = TimeMachineApp()
    app.run()

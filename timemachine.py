import sys
import threading
import queue
import time
import datetime
from pathlib import Path

import numpy as np
import soundfile as sf
import jack

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, ProgressBar, Label
from textual.reactive import reactive
from textual.binding import Binding

# --- Configuration ---
BUFFER_DURATION = 10  # Seconds of history to keep
DEFAULT_CHANNELS = 2

class AudioEngine:
    """Handles JACK client, ring buffer, and file writing logic."""
    def __init__(self, buffer_duration=BUFFER_DURATION):
        self.buffer_duration = buffer_duration
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
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Label("TIME MACHINE", classes="title")
            yield Static("IDLE - Ready to Capture", id="status-bar", classes="status-idle")
            
            yield Static("\nBuffers filled: ", id="buffer-info")
            
            with Vertical(id="meters"):
                yield Label("Channel 1")
                yield VUMeter(id="meter-1")
                yield Label("Channel 2")
                yield VUMeter(id="meter-2")
                
            yield Static("\n[dim]Press SPACE to Capture History + Record[/dim]", classes="help-text")
        yield Footer()

    def on_mount(self):
        # Initialize Audio Engine
        try:
            self.engine = AudioEngine()
            self.engine.start()
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

if __name__ == "__main__":
    app = TimeMachineApp()
    app.run()

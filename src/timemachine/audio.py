import queue
import threading
from pathlib import Path
import jack
import numpy as np
import soundfile as sf
from typing import Optional
from .config import ConfigManager

BUFFER_DURATION = 10
DEFAULT_CHANNELS = 2

class AudioEngine:
    """Handles JACK client, ring buffer, and file writing logic."""
    def __init__(
        self,
        buffer_duration: int = BUFFER_DURATION,
        config_manager: Optional[ConfigManager] = None,
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

        self.client.set_process_callback(self.process)

    def start(self) -> None:
        self.client.activate()
        print(f"JACK Client started. Sample rate: {self.samplerate}, Buffer: {self.buffer_duration}s")

    def stop(self) -> None:
        self.client.deactivate()
        self.client.close()

    def _write_to_ring_buffer(self, data: np.ndarray, frames: int) -> None:
        remaining_space = self.ring_size - self.write_ptr
        if frames <= remaining_space:
            self.ring_buffer[self.write_ptr : self.write_ptr + frames] = data
            self.write_ptr += frames
        else:
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
        try:
            input_arrays = [port.get_array() for port in self.input_ports]
            data = np.stack(input_arrays, axis=-1)

            # Update Meters
            self.peaks = np.max(np.abs(data), axis=0).tolist()
            self.dbs = [20 * np.log10(p) if p > 1e-5 else -100.0 for p in self.peaks]

            # Write to Ring Buffer
            self._write_to_ring_buffer(data, frames)

            # Write to File Queue if recording
            if self.is_recording:
                self.record_queue.put(data.copy())

        except Exception:
            pass

    def start_recording(self, output_path: Path) -> Path | None:
        """
        Start recording to specified output path.

        Args:
            output_path: Full path where recording should be saved

        Returns:
            Path object of the recording file, or None if already recording
        """
        if self.is_recording:
            return None

        self.is_recording = True
        self.stop_event.clear()

        # Reconstruct buffer
        if self.buffer_filled:
            part_old = self.ring_buffer[self.write_ptr:]
            part_new = self.ring_buffer[:self.write_ptr]
            past_data = np.concatenate((part_old, part_new))
        else:
            past_data = self.ring_buffer[:self.write_ptr].copy()

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.writer_thread = threading.Thread(
            target=self._file_writer,
            args=(str(output_path), past_data)
        )
        self.writer_thread.start()
        return output_path

    def stop_recording(self) -> None:
        self.is_recording = False
        self.stop_event.set()
        if self.writer_thread:
            self.writer_thread.join()
        
        while not self.record_queue.empty():
            self.record_queue.get()

    def _file_writer(self, filename: str, pre_buffer_data: np.ndarray) -> None:
        try:
            with sf.SoundFile(filename, mode='w', samplerate=self.samplerate, channels=self.channels) as file:
                file.write(pre_buffer_data)
                while self.is_recording or not self.record_queue.empty():
                    try:
                        block = self.record_queue.get(timeout=0.1)
                        file.write(block)
                    except queue.Empty:
                        if not self.is_recording:
                            break
        except Exception as e:
            print(f"File writer error: {e}")

    def get_available_output_ports(self) -> list[jack.Port]:
        try:
            return self.client.get_ports(is_audio=True, is_output=True)
        except Exception as e:
            print(f"Error getting ports: {e}")
            return []

    def get_current_connections(self) -> list[str | None]:
        try:
            current_connections = []
            for inport in self.input_ports:
                connections = self.client.get_all_connections(inport)
                name = connections[0].name if connections else None
                current_connections.append(name)
            return current_connections
        except Exception:
            return [None] * self.channels

    def disconnect_inputs(self):
        try:
            for inport in self.client.inports:
                connections = self.client.get_all_connections(inport)
                for source_port in connections:
                    self.client.disconnect(source_port, inport)
        except Exception as e:
            print(f"Error disconnecting: {e}")

    def connect_inputs(self, source_ports: list[str]) -> bool:
        if self.is_recording:
            return False
        if len(source_ports) != self.channels:
            return False

        try:
            for i, source in enumerate(source_ports):
                if source:
                    self.client.connect(source, self.input_ports[i])
            self.connected_sources = source_ports.copy()
            return True
        except Exception as e:
            print(f"Error connecting: {e}")
            return False
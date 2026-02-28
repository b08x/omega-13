import logging
import queue
import threading
import time
from pathlib import Path
import jack
import numpy as np
import soundfile as sf
from typing import Optional, Dict, Any
from .config import ConfigManager
from .audio_processor import AudioProcessor
from .signal_detector import SignalDetector

logger = logging.getLogger(__name__)

BUFFER_DURATION = 13
DEFAULT_CHANNELS = 2


class AudioEngine:
    """Handles JACK client, ring buffer, and file writing logic."""

    def __init__(
        self,
        buffer_duration: int = BUFFER_DURATION,
        config_manager: Optional[ConfigManager] = None,
        num_channels: int = DEFAULT_CHANNELS,
    ) -> None:
        self.buffer_duration = buffer_duration
        self.config_manager = config_manager
        self.client = jack.Client("Omega13")

        # Setup input ports
        self.input_ports = []
        for i in range(num_channels):
            self.input_ports.append(self.client.inports.register(f"in_{i + 1}"))

        self.samplerate = int(self.client.samplerate)
        self.channels = len(self.input_ports)

        # Ring Buffer setup
        self.ring_size = self.samplerate * self.buffer_duration
        self.ring_buffer = np.zeros((self.ring_size, self.channels), dtype="float32")
        self.write_ptr = 0
        self.buffer_filled = False
        # Zero-allocation JACK callback buffers
        try:
            self.max_block_size = int(self.client.blocksize)
        except (TypeError, ValueError, AttributeError):
            self.max_block_size = 4096
        self.scratchpad = np.zeros(
            (self.max_block_size, self.channels), dtype="float32"
        )
        self.abs_scratchpad = np.zeros(
            (self.max_block_size, self.channels), dtype="float32"
        )

        self.buffer_pool_size = 200  # Matches record_queue maxsize
        self.buffer_pool = np.zeros(
            (self.buffer_pool_size, self.max_block_size, self.channels), dtype="float32"
        )
        self.buffer_pool_index = 0

        # Recording state
        self.is_recording = False
        self.record_queue = queue.Queue(maxsize=200)  # ~4s buffer @ 48kHz
        self.writer_thread = None
        self.stop_event = threading.Event()

        # Metering (peak-based for VU meters)
        self.peaks = np.zeros(self.channels, dtype="float32")

        # RMS metering (energy-based for intelligent recording)
        self.rms_levels = np.zeros(self.channels, dtype="float32")
        self.rms_db = np.full(self.channels, -100.0, dtype="float32")

        # Signal detector for auto-record
        begin_threshold = (
            config_manager.get_auto_record_begin_threshold()
            if config_manager
            else -35.0
        )
        end_threshold = (
            config_manager.get_auto_record_end_threshold() if config_manager else -35.0
        )
        silence_duration = (
            config_manager.get_auto_record_silence_duration()
            if config_manager
            else 10.0
        )

        self.signal_detector = SignalDetector(
            samplerate=self.samplerate,
            channels=self.channels,
            begin_threshold_db=begin_threshold,
            end_threshold_db=end_threshold,
            silence_duration_sec=silence_duration,
        )

        # Signal detector metrics (last update result)
        self.last_signal_metrics: Dict[str, Any] = {
            "rms_levels": self.rms_levels,
            "rms_db": self.rms_db,
            "is_above_begin": False,
            "is_above_end": False,
            "silence_duration": 0.0,
        }

        # Connection tracking
        self.connected_sources = [None] * self.channels

        # Activity tracking (legacy - kept for backward compatibility)
        self.last_activity_time = 0.0
        self.activity_threshold_db = -70.0  # Slightly more sensitive default
        self.activity_threshold_linear = 10 ** (self.activity_threshold_db / 20)

        # Shutdown state
        self._stopped = False

        self.client.set_process_callback(self.process)

    def start(self) -> None:
        self.client.activate()
        logger.info(
            f"JACK Client started. Sample rate: {self.samplerate}, Buffer: {self.buffer_duration}s"
        )

    def has_audio_activity(self, window_seconds: float = 0.5) -> bool:
        """
        Check if there was any audio activity above threshold within the last window_seconds.

        Args:
            window_seconds: Time window to look back for activity (default 0.5s)

        Returns:
            True if activity was detected recently OR if ports are connected and engine is safe,
            False otherwise.
        """
        # 1. Check for recent signal peaks
        if (time.time() - self.last_activity_time) < window_seconds:
            return True

        # 2. Fallback: check if ports are actually connected
        connections = self.get_current_connections()
        if any(c is not None for c in connections):
            return True

        return False

    def stop(self) -> None:
        """Idempotent JACK client shutdown."""
        if self._stopped:
            logger.debug("AudioEngine already stopped")
            return

        try:
            if hasattr(self, "client"):
                if self.client.status:  # Check if active
                    logger.debug("Deactivating JACK client")
                    self.client.deactivate()
                logger.debug("Closing JACK client")
                self.client.close()
            self._stopped = True
            logger.info("AudioEngine stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping AudioEngine: {e}")
            self._stopped = True  # Mark as stopped even on error

    def _write_to_ring_buffer(self, data: np.ndarray, frames: int) -> None:
        remaining_space = self.ring_size - self.write_ptr
        if frames <= remaining_space:
            self.ring_buffer[self.write_ptr : self.write_ptr + frames] = data
            self.write_ptr += frames
        else:
            part1 = remaining_space
            part2 = frames - remaining_space
            self.ring_buffer[self.write_ptr : self.write_ptr + part1] = data[:part1]
            self.ring_buffer[0:part2] = data[part1:]
            self.write_ptr = part2
            self.buffer_filled = True

        if self.write_ptr >= self.ring_size:
            self.write_ptr = 0
            self.buffer_filled = True

    def process(self, frames: int) -> None:
        try:
            for i, port in enumerate(self.input_ports):
                self.scratchpad[:frames, i] = port.get_array()
            data = self.scratchpad[:frames]

            # Update Peak Meters (for VU display) - raw peaks only
            np.abs(data, out=self.abs_scratchpad[:frames])
            np.max(self.abs_scratchpad[:frames], axis=0, out=self.peaks)

            # Update RMS Meters (for intelligent recording decisions)
            self.last_signal_metrics = self.signal_detector.update(data)
            self.rms_levels = self.last_signal_metrics["rms_levels"]
            self.rms_db = self.last_signal_metrics["rms_db"]

            # Update Activity Tracking (legacy - kept for backward compatibility)
            if np.any(self.peaks > self.activity_threshold_linear):
                self.last_activity_time = time.time()

            # Write to Ring Buffer
            self._write_to_ring_buffer(data, frames)

            # Write to File Queue if recording
            if self.is_recording:
                try:
                    # Non-blocking put to prevent JACK callback hang
                    idx = self.buffer_pool_index
                    self.buffer_pool[idx, :frames, :] = data
                    self.record_queue.put((idx, frames), block=False)
                    self.buffer_pool_index = (idx + 1) % self.buffer_pool_size
                except queue.Full:
                    # Queue full - log but don't block (rare case)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("Record queue full - frame dropped")

        except Exception as e:
            # Only log in debug mode (performance-sensitive callback)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"JACK process error: {e}")
            # Must swallow exception for JACK stability
            pass

    def get_peak_meters(self) -> tuple[list[float], list[float]]:
        """
        Compute dB values from raw peaks in UI thread.

        Returns:
            Tuple of (linear_peaks, db_peaks)
        """
        peaks_list = self.peaks.tolist()
        dbs = [20 * np.log10(p) if p > 1e-5 else -100.0 for p in peaks_list]
        return peaks_list, dbs

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
            part_old = self.ring_buffer[self.write_ptr :]
            part_new = self.ring_buffer[: self.write_ptr]
            past_data = np.concatenate((part_old, part_new))
        else:
            past_data = self.ring_buffer[: self.write_ptr].copy()

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.writer_thread = threading.Thread(
            target=self._file_writer,
            args=(str(output_path), past_data),
            daemon=True,  # Daemon thread allows clean shutdown without blocking
        )
        self.writer_thread.start()
        return output_path

    def stop_recording(self) -> None:
        """Stop recording with timeout protection."""
        if not self.is_recording:
            return

        logger.info("Stopping recording...")
        logger.info(f"Queue depth: {self.record_queue.qsize()} blocks")

        self.is_recording = False
        self.stop_event.set()

        if self.writer_thread and self.writer_thread.is_alive():
            logger.info("Waiting for writer thread (5s timeout)...")
            # Wait up to 5 seconds for writer thread to finish
            self.writer_thread.join(timeout=5.0)

            if self.writer_thread.is_alive():
                # Log the hang but continue cleanup
                logger.warning(
                    f"Writer thread still alive. "
                    f"Remaining queue: {self.record_queue.qsize()} blocks. "
                    f"File may be incomplete."
                )
            else:
                logger.info("Writer thread completed successfully")

        # Clear any remaining queue items
        try:
            while not self.record_queue.empty():
                self.record_queue.get_nowait()
        except Exception as e:
            logger.debug(f"Queue cleanup error (non-critical): {e}")

    def _file_writer(self, filename: str, pre_buffer_data: np.ndarray) -> None:
        """Write audio data to MP3 file with 16kHz mono encoding."""
        import tempfile
        import os

        # Replace .wav extension with .mp3 in filename
        if filename.endswith(".wav"):
            mp3_filename = filename[:-4] + ".mp3"
        else:
            mp3_filename = (
                filename + ".mp3" if not filename.endswith(".mp3") else filename
            )

        # Create temporary WAV file for intermediate processing
        temp_wav = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_wav = temp_file.name

            # Write audio data to temporary WAV file
            with sf.SoundFile(
                temp_wav, mode="w", samplerate=self.samplerate, channels=self.channels
            ) as wav_file:
                wav_file.write(pre_buffer_data)

                # Continue writing blocks from queue
                while self.is_recording or not self.record_queue.empty():
                    try:
                        item = self.record_queue.get(timeout=0.1)
                        if isinstance(item, tuple):
                            idx, frames = item
                            block = self.buffer_pool[idx, :frames, :]
                        else:
                            block = item
                        wav_file.write(block)
                    except queue.Empty:
                        if not self.is_recording:
                            break

            # Apply audio processing pipeline (Trim silence -> Resample -> Encode MP3)
            processor = AudioProcessor()
            operations = [
                {"op": "trim_silence", "threshold_db": -50.0},
                {"op": "encode_mp3", "bitrate": "128k"}
            ]
            
            final_path = processor.process_pipeline(temp_wav, mp3_filename, operations)
            
            logger.info(f"Audio processed and saved: {final_path}")

        except Exception as e:
            logger.error(f"File writer error: {e}")
            raise
        finally:
            # Clean up temporary WAV file
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.unlink(temp_wav)
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to cleanup temporary file {temp_wav}: {cleanup_error}"
                    )

    def get_available_output_ports(self) -> list[jack.Port]:
        try:
            return self.client.get_ports(is_audio=True, is_output=True)
        except Exception as e:
            logger.error(f"Error getting ports: {e}")
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
            logger.error(f"Error disconnecting: {e}")

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

"""
Signal detection module for audio activity and silence detection.

Provides RMS (Root Mean Square) energy calculation and threshold-based
detection for auto-record functionality.
"""

import logging
import time
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class SignalDetector:
    """
    Calculates RMS energy and detects silence/signal thresholds.

    Uses RMS (Root Mean Square) for energy-based detection, which is more
    robust for voice activity detection than peak amplitude as it measures
    sustained energy rather than transient spikes.

    Thread-safe for use in JACK callback and timer contexts.
    """

    def __init__(
        self,
        samplerate: int,
        channels: int = 2,
        begin_threshold_db: float = -35.0,
        end_threshold_db: float = -35.0,
        silence_duration_sec: float = 10.0,
        rms_window_sec: float = 0.1,  # 100ms window
    ) -> None:
        """
        Initialize signal detector.

        Args:
            samplerate: Audio sample rate (Hz)
            channels: Number of audio channels
            begin_threshold_db: dB level to trigger recording start
            end_threshold_db: dB level below which silence is detected
            silence_duration_sec: Duration of continuous silence to trigger stop
            rms_window_sec: RMS calculation window duration (seconds)
        """
        # Validate parameters
        if samplerate <= 0:
            raise ValueError(f"Invalid samplerate: {samplerate}")
        if channels <= 0:
            raise ValueError(f"Invalid channels: {channels}")
        if begin_threshold_db < -100 or begin_threshold_db > 0:
            logger.warning(
                f"Begin threshold {begin_threshold_db} dB is outside typical range (-100 to 0 dB)"
            )
        if end_threshold_db < -100 or end_threshold_db > 0:
            logger.warning(
                f"End threshold {end_threshold_db} dB is outside typical range (-100 to 0 dB)"
            )
        if silence_duration_sec < 0.1 or silence_duration_sec > 300:
            logger.warning(
                f"Silence duration {silence_duration_sec}s is outside typical range (0.1 to 300s)"
            )
        if rms_window_sec < 0.01 or rms_window_sec > 1.0:
            logger.warning(
                f"RMS window {rms_window_sec}s is outside typical range (0.01 to 1.0s)"
            )

        self.samplerate = samplerate
        self.channels = channels
        self.begin_threshold_db = begin_threshold_db
        self.end_threshold_db = end_threshold_db
        self.silence_duration_sec = silence_duration_sec
        self.rms_window_sec = rms_window_sec

        # RMS calculation state
        self.rms_window_frames = int(samplerate * rms_window_sec)
        self.rms_buffer = np.zeros((self.rms_window_frames, channels), dtype="float32")
        self.rms_write_pos = 0
        self.rms_buffer_filled = False

        # Current RMS levels
        self.rms_levels = np.zeros(channels, dtype="float32")
        self.rms_db = np.full(channels, -100.0, dtype="float32")
        self.rms_sq_scratchpad = np.zeros(
            (self.rms_window_frames, channels), dtype="float32"
        )
        self.rms_squared_buffer = np.zeros(channels, dtype="float32")

        # Performance optimization: only calculate RMS every N frames to reduce CPU
        self.rms_calc_interval = (
            10  # Calculate every 10th callback (~50ms at typical buffer sizes)
        )
        self.rms_calc_counter = 0

        # Silence tracking (with noise immunity)
        self.silence_start_time: Optional[float] = None
        self.is_currently_silent = True
        self.noise_start_time: Optional[float] = None
        self.noise_sustain_duration = 0.2  # Ignore noises < 0.2s

        # Sustained signal tracking (start trigger)
        self.signal_sustain_duration = 0.2  # Trigger after 0.2s of signal
        self.signal_start_time: Optional[float] = None
        self.is_signal_sustained = False

        # Pre-allocated metrics dictionary for zero-allocation update
        self._metrics_dict: Dict[str, Any] = {
            "rms_levels": self.rms_levels,
            "rms_db": self.rms_db,
            "is_above_begin": False,
            "is_above_end": False,
            "silence_duration": 0.0,
        }

        logger.info(
            f"SignalDetector initialized: "
            f"begin={begin_threshold_db}dB, end={end_threshold_db}dB, "
            f"silence={silence_duration_sec}s, rms_window={rms_window_sec}s, "
            f"signal_sustain={self.signal_sustain_duration}s, "
            f"noise_sustain={self.noise_sustain_duration}s"
        )

    def update(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """
        Process audio block and update RMS metrics.

        Args:
            audio_data: Audio samples (frames × channels)

        Returns:
            Dictionary with current signal metrics:
            {
                'rms_levels': [float, ...],   # Per-channel RMS (0.0-1.0)
                'rms_db': [float, ...],        # RMS in dB
                'is_above_begin': bool,        # Any channel > begin threshold
                'is_above_end': bool,          # Any channel > end threshold
                'silence_duration': float      # Seconds of continuous silence
            }
        """
        frames = len(audio_data)

        # Update RMS buffer (circular)
        remaining = self.rms_window_frames - self.rms_write_pos

        if frames <= remaining:
            self.rms_buffer[self.rms_write_pos : self.rms_write_pos + frames] = (
                audio_data
            )
            self.rms_write_pos += frames
        else:
            # Wrap around
            self.rms_buffer[self.rms_write_pos :] = audio_data[:remaining]
            self.rms_buffer[: frames - remaining] = audio_data[remaining:]
            self.rms_write_pos = frames - remaining
            self.rms_buffer_filled = True

        if self.rms_write_pos >= self.rms_window_frames:
            self.rms_write_pos = 0
            self.rms_buffer_filled = True

        # Calculate RMS periodically (performance optimization)
        self.rms_calc_counter += 1
        if self.rms_calc_counter >= self.rms_calc_interval:
            self._calculate_rms()
            self.rms_calc_counter = 0

        # Check instantaneous thresholds
        is_above_begin_instantaneous = np.any(self.rms_db > self.begin_threshold_db)
        is_above_end_instantaneous = np.any(self.rms_db > self.end_threshold_db)

        current_time = time.time()

        # 1. Update sustained signal tracking (Trigger Start)
        if is_above_begin_instantaneous:
            if self.signal_start_time is None:
                self.signal_start_time = current_time
            if current_time - self.signal_start_time >= self.signal_sustain_duration:
                self.is_signal_sustained = True
        else:
            self.signal_start_time = None
            self.is_signal_sustained = False

        # 2. Update silence tracking (Trigger Stop / UI Timer)
        # We want silence_duration to start immediately, but only reset if noise/speech is sustained.
        if is_above_end_instantaneous:
            # Potential noise or start of talking
            if self.noise_start_time is None:
                self.noise_start_time = current_time

            # If noise is sustained, reset the silence timer
            if current_time - self.noise_start_time >= self.noise_sustain_duration:
                self.reset_silence_timer()
                self.is_currently_silent = False
        else:
            # Back into confirmed silence
            self.noise_start_time = None
            if self.silence_start_time is None:
                # Start the clock immediately when it becomes quiet
                self.silence_start_time = current_time
            self.is_currently_silent = True

        self._metrics_dict["is_above_begin"] = self.is_signal_sustained
        self._metrics_dict["is_above_end"] = is_above_end_instantaneous
        self._metrics_dict["silence_duration"] = self.get_silence_duration()
        return self._metrics_dict

    def _calculate_rms(self) -> None:
        """Calculate RMS levels from current buffer."""
        # Use the filled portion of the buffer
        if self.rms_buffer_filled:
            data = self.rms_buffer
        else:
            data = self.rms_buffer[: self.rms_write_pos]

        if len(data) == 0:
            self.rms_levels.fill(0.0)
            self.rms_db.fill(-100.0)
            return

        # RMS = sqrt(mean(x^2))
        np.square(data, out=self.rms_sq_scratchpad[: len(data)])
        np.mean(
            self.rms_sq_scratchpad[: len(data)], axis=0, out=self.rms_squared_buffer
        )
        np.sqrt(self.rms_squared_buffer, out=self.rms_levels)

        # Convert to dB (20 * log10(rms))
        mask = self.rms_levels > 1e-5
        self.rms_db.fill(-100.0)
        if np.any(mask):
            np.log10(self.rms_levels, out=self.rms_db, where=mask)
            np.multiply(self.rms_db, 20.0, out=self.rms_db, where=mask)

    def reset_silence_timer(self) -> None:
        """Reset the silence duration counter."""
        self.silence_start_time = None
        self.noise_start_time = None
        self.is_currently_silent = False

    def get_silence_duration(self) -> float:
        """
        Get current silence duration in seconds.

        Returns:
            Seconds of continuous silence, or 0.0 if not silent
        """
        if self.silence_start_time is None:
            return 0.0
        return time.time() - self.silence_start_time

    def is_silence_threshold_exceeded(self) -> bool:
        """
        Check if silence has exceeded the configured duration.

        Returns:
            True if silence duration >= silence_duration_sec
        """
        return self.get_silence_duration() >= self.silence_duration_sec

    def reconfigure(
        self,
        begin_threshold_db: Optional[float] = None,
        end_threshold_db: Optional[float] = None,
        silence_duration_sec: Optional[float] = None,
    ) -> None:
        """
        Update detection thresholds without recreating the detector.

        Args:
            begin_threshold_db: New begin threshold (optional)
            end_threshold_db: New end threshold (optional)
            silence_duration_sec: New silence duration (optional)
        """
        if begin_threshold_db is not None:
            self.begin_threshold_db = begin_threshold_db
            logger.info(f"Begin threshold updated to {begin_threshold_db} dB")

        if end_threshold_db is not None:
            self.end_threshold_db = end_threshold_db
            logger.info(f"End threshold updated to {end_threshold_db} dB")

        if silence_duration_sec is not None:
            self.silence_duration_sec = silence_duration_sec
            logger.info(f"Silence duration updated to {silence_duration_sec}s")

    def get_config(self) -> Dict[str, float]:
        """
        Get current detector configuration.

        Returns:
            Dictionary with current threshold and duration settings
        """
        return {
            "begin_threshold_db": self.begin_threshold_db,
            "end_threshold_db": self.end_threshold_db,
            "silence_duration_sec": self.silence_duration_sec,
            "rms_window_sec": self.rms_window_sec,
        }

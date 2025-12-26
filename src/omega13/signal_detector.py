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
        rms_window_sec: float = 0.1  # 100ms window
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
            logger.warning(f"Begin threshold {begin_threshold_db} dB is outside typical range (-100 to 0 dB)")
        if end_threshold_db < -100 or end_threshold_db > 0:
            logger.warning(f"End threshold {end_threshold_db} dB is outside typical range (-100 to 0 dB)")
        if silence_duration_sec < 0.1 or silence_duration_sec > 300:
            logger.warning(f"Silence duration {silence_duration_sec}s is outside typical range (0.1 to 300s)")
        if rms_window_sec < 0.01 or rms_window_sec > 1.0:
            logger.warning(f"RMS window {rms_window_sec}s is outside typical range (0.01 to 1.0s)")

        self.samplerate = samplerate
        self.channels = channels
        self.begin_threshold_db = begin_threshold_db
        self.end_threshold_db = end_threshold_db
        self.silence_duration_sec = silence_duration_sec
        self.rms_window_sec = rms_window_sec

        # RMS calculation state
        self.rms_window_frames = int(samplerate * rms_window_sec)
        self.rms_buffer = np.zeros((self.rms_window_frames, channels), dtype='float32')
        self.rms_write_pos = 0
        self.rms_buffer_filled = False

        # Current RMS levels
        self.rms_levels = [0.0] * channels
        self.rms_db = [-100.0] * channels

        # Silence tracking
        self.silence_start_time: Optional[float] = None
        self.is_currently_silent = True

        logger.info(
            f"SignalDetector initialized: "
            f"begin={begin_threshold_db}dB, end={end_threshold_db}dB, "
            f"silence={silence_duration_sec}s, rms_window={rms_window_sec}s"
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
            self.rms_buffer[self.rms_write_pos:self.rms_write_pos + frames] = audio_data
            self.rms_write_pos += frames
        else:
            # Wrap around
            self.rms_buffer[self.rms_write_pos:] = audio_data[:remaining]
            self.rms_buffer[:frames - remaining] = audio_data[remaining:]
            self.rms_write_pos = frames - remaining
            self.rms_buffer_filled = True

        if self.rms_write_pos >= self.rms_window_frames:
            self.rms_write_pos = 0
            self.rms_buffer_filled = True

        # Calculate RMS over the buffer
        self._calculate_rms()

        # Check thresholds
        is_above_begin = any(db > self.begin_threshold_db for db in self.rms_db)
        is_above_end = any(db > self.end_threshold_db for db in self.rms_db)

        # Update silence tracking
        if is_above_end:
            # Signal detected - reset silence timer
            self.reset_silence_timer()
            self.is_currently_silent = False
        else:
            # Below end threshold - count as silence
            if self.silence_start_time is None:
                self.silence_start_time = time.time()
            self.is_currently_silent = True

        return {
            'rms_levels': self.rms_levels.copy(),
            'rms_db': self.rms_db.copy(),
            'is_above_begin': is_above_begin,
            'is_above_end': is_above_end,
            'silence_duration': self.get_silence_duration()
        }

    def _calculate_rms(self) -> None:
        """Calculate RMS levels from current buffer."""
        # Use the filled portion of the buffer
        if self.rms_buffer_filled:
            data = self.rms_buffer
        else:
            data = self.rms_buffer[:self.rms_write_pos]

        if len(data) == 0:
            self.rms_levels = [0.0] * self.channels
            self.rms_db = [-100.0] * self.channels
            return

        # RMS = sqrt(mean(x^2))
        rms_squared = np.mean(data ** 2, axis=0)
        self.rms_levels = np.sqrt(rms_squared).tolist()

        # Convert to dB (20 * log10(rms))
        self.rms_db = []
        for rms in self.rms_levels:
            if rms > 1e-5:  # Avoid log(0)
                db = 20 * np.log10(rms)
            else:
                db = -100.0  # Effective silence
            self.rms_db.append(db)

    def reset_silence_timer(self) -> None:
        """Reset the silence duration counter."""
        self.silence_start_time = None
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
        silence_duration_sec: Optional[float] = None
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
            'begin_threshold_db': self.begin_threshold_db,
            'end_threshold_db': self.end_threshold_db,
            'silence_duration_sec': self.silence_duration_sec,
            'rms_window_sec': self.rms_window_sec
        }

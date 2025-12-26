"""
Recording state machine and auto-record orchestration.

Manages recording lifecycle with explicit state transitions and event-driven
architecture for clean UI integration.
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import threading

logger = logging.getLogger(__name__)


class RecordingState(Enum):
    """Recording state machine states."""
    IDLE = "idle"                          # Not recording, auto-record disabled
    ARMED = "armed"                        # Auto-record enabled, monitoring for signal
    RECORDING_MANUAL = "recording_manual"  # User-initiated recording
    RECORDING_AUTO = "recording_auto"      # Auto-triggered recording
    STOPPING = "stopping"                  # Cleanup in progress


class RecordingEvent(Enum):
    """Events fired by the recording controller."""
    AUTO_STARTED = "auto_started"        # Auto-record triggered
    AUTO_STOPPED = "auto_stopped"        # Auto-stopped due to silence
    MANUAL_STARTED = "manual_started"    # User started recording
    MANUAL_STOPPED = "manual_stopped"    # User stopped recording
    SILENCE_DETECTED = "silence_detected"  # Silence countdown active
    SIGNAL_DETECTED = "signal_detected"    # Signal detected while armed
    STATE_CHANGED = "state_changed"        # State transition occurred


class RecordingController:
    """
    Orchestrates recording state machine and auto-record logic.

    State Transitions:
        IDLE → enable_auto_record() → ARMED
        ARMED → signal > begin_threshold → RECORDING_AUTO
        ARMED → manual_start() → RECORDING_MANUAL
        RECORDING_AUTO → silence > duration → STOPPING → ARMED
        RECORDING_AUTO → manual_stop() → STOPPING → ARMED
        RECORDING_MANUAL → silence > duration → STOPPING → IDLE
        RECORDING_MANUAL → manual_stop() → STOPPING → IDLE
        ARMED → disable_auto_record() → IDLE
        RECORDING_* → disable_auto_record() → STOPPING → IDLE
    """

    def __init__(
        self,
        audio_engine,  # AudioEngine instance
        signal_detector,  # SignalDetector instance
        config_manager=None  # Optional ConfigManager
    ) -> None:
        """
        Initialize recording controller.

        Args:
            audio_engine: AudioEngine instance for audio I/O
            signal_detector: SignalDetector instance for threshold detection
            config_manager: Optional ConfigManager for state persistence
        """
        self.audio_engine = audio_engine
        self.signal_detector = signal_detector
        self.config_manager = config_manager

        # State machine
        self._state = RecordingState.IDLE
        self._state_lock = threading.Lock()

        # Auto-record configuration
        self._auto_record_enabled = False
        if config_manager:
            self._auto_record_enabled = config_manager.get_auto_record_enabled()

        # Current recording path (for cleanup)
        self._current_recording_path: Optional[Path] = None

        # Event callback
        self._event_callback: Optional[Callable[[RecordingEvent, Dict[str, Any]], None]] = None

        logger.info(f"RecordingController initialized in {self._state.value} state")

    def set_event_callback(
        self,
        callback: Callable[[RecordingEvent, Dict[str, Any]], None]
    ) -> None:
        """
        Register callback for recording events.

        Args:
            callback: Function(event: RecordingEvent, data: Dict) to be called on events
        """
        self._event_callback = callback

    def _fire_event(self, event: RecordingEvent, data: Optional[Dict[str, Any]] = None) -> None:
        """Fire an event to the registered callback."""
        if self._event_callback:
            try:
                self._event_callback(event, data or {})
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    def _transition_state(self, new_state: RecordingState, reason: str = "") -> None:
        """Thread-safe state transition with logging."""
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            logger.info(f"State transition: {old_state.value} → {new_state.value} ({reason})")
            self._fire_event(RecordingEvent.STATE_CHANGED, {
                'old_state': old_state.value,
                'new_state': new_state.value,
                'reason': reason
            })

    def get_state(self) -> RecordingState:
        """Get current recording state (thread-safe)."""
        with self._state_lock:
            return self._state

    def is_recording(self) -> bool:
        """Check if currently recording (any mode)."""
        state = self.get_state()
        return state in (RecordingState.RECORDING_MANUAL, RecordingState.RECORDING_AUTO)

    def is_auto_record_enabled(self) -> bool:
        """Check if auto-record mode is enabled."""
        return self._auto_record_enabled

    def enable_auto_record(self) -> bool:
        """
        Enable auto-record mode and transition to ARMED state.

        Returns:
            True if successful, False if invalid state
        """
        state = self.get_state()

        if state == RecordingState.ARMED:
            logger.debug("Auto-record already enabled")
            return True

        if state != RecordingState.IDLE:
            logger.warning(f"Cannot enable auto-record from {state.value} state")
            return False

        self._auto_record_enabled = True
        if self.config_manager:
            self.config_manager.set_auto_record_enabled(True)

        self._transition_state(RecordingState.ARMED, "auto-record enabled")
        self.signal_detector.reset_silence_timer()
        return True

    def disable_auto_record(self) -> bool:
        """
        Disable auto-record mode and transition to IDLE.

        If currently recording in auto mode, stops the recording first.

        Returns:
            True if successful
        """
        self._auto_record_enabled = False
        if self.config_manager:
            self.config_manager.set_auto_record_enabled(False)

        state = self.get_state()

        if state == RecordingState.RECORDING_AUTO:
            # Stop auto-recording
            self._stop_recording_internal(return_to_armed=False)
            return True
        elif state == RecordingState.ARMED:
            self._transition_state(RecordingState.IDLE, "auto-record disabled")
            return True
        elif state == RecordingState.IDLE:
            logger.debug("Auto-record already disabled")
            return True
        else:
            # Manual recording in progress - just disable auto mode flag
            logger.info("Auto-record disabled (manual recording continues)")
            return True

    def manual_start_recording(self, output_path: Path) -> bool:
        """
        Start recording manually (user-initiated).

        Args:
            output_path: Path where recording will be saved

        Returns:
            True if recording started, False if invalid state
        """
        state = self.get_state()

        if state in (RecordingState.RECORDING_MANUAL, RecordingState.RECORDING_AUTO):
            logger.warning("Already recording")
            return False

        if state == RecordingState.STOPPING:
            logger.warning("Cannot start while stopping previous recording")
            return False

        # Start recording via audio engine
        result = self.audio_engine.start_recording(output_path)
        if result is None:
            logger.error("AudioEngine failed to start recording")
            return False

        self._current_recording_path = result
        self.signal_detector.reset_silence_timer()

        # Determine target state based on whether auto-record is enabled
        if state == RecordingState.ARMED:
            new_state = RecordingState.RECORDING_AUTO
            event = RecordingEvent.AUTO_STARTED
        else:
            new_state = RecordingState.RECORDING_MANUAL
            event = RecordingEvent.MANUAL_STARTED

        self._transition_state(new_state, "manual start requested")
        self._fire_event(event, {'path': str(output_path)})
        return True

    def manual_stop_recording(self) -> bool:
        """
        Stop recording manually (user-initiated).

        Returns:
            True if recording stopped, False if not recording
        """
        state = self.get_state()

        if state not in (RecordingState.RECORDING_MANUAL, RecordingState.RECORDING_AUTO):
            logger.warning(f"Not recording (state: {state.value})")
            return False

        # Determine return state
        return_to_armed = (state == RecordingState.RECORDING_AUTO and self._auto_record_enabled)
        self._stop_recording_internal(return_to_armed)
        return True

    def _stop_recording_internal(self, return_to_armed: bool) -> None:
        """
        Internal method to stop recording and transition state.

        Args:
            return_to_armed: If True, transition to ARMED; otherwise IDLE
        """
        self._transition_state(RecordingState.STOPPING, "stopping recording")

        # Stop audio engine
        self.audio_engine.stop_recording()

        # Fire appropriate event
        if return_to_armed:
            self._fire_event(RecordingEvent.AUTO_STOPPED, {
                'path': str(self._current_recording_path) if self._current_recording_path else None
            })
            target_state = RecordingState.ARMED
        else:
            self._fire_event(RecordingEvent.MANUAL_STOPPED, {
                'path': str(self._current_recording_path) if self._current_recording_path else None
            })
            target_state = RecordingState.IDLE

        self._current_recording_path = None
        self.signal_detector.reset_silence_timer()
        self._transition_state(target_state, "recording stopped")

    def check_auto_triggers(self, signal_metrics: Dict[str, Any]) -> None:
        """
        Check signal metrics and trigger auto-start/stop if appropriate.

        Should be called periodically (e.g., every 100ms) with current signal metrics.

        Args:
            signal_metrics: Dict from SignalDetector.update() containing:
                - is_above_begin: bool
                - is_above_end: bool
                - silence_duration: float
        """
        state = self.get_state()

        # ARMED state: check for auto-start trigger
        if state == RecordingState.ARMED:
            if signal_metrics['is_above_begin']:
                self._fire_event(RecordingEvent.SIGNAL_DETECTED, {
                    'rms_db': signal_metrics['rms_db']
                })
                # Note: Actual recording start happens via manual_start_recording()
                # called by the app in response to SIGNAL_DETECTED event

        # RECORDING states: check for silence-based auto-stop
        elif state in (RecordingState.RECORDING_MANUAL, RecordingState.RECORDING_AUTO):
            silence_duration = signal_metrics['silence_duration']

            if silence_duration > 0:
                # Fire silence detected event for UI countdown
                self._fire_event(RecordingEvent.SILENCE_DETECTED, {
                    'silence_duration': silence_duration,
                    'silence_threshold': self.signal_detector.silence_duration_sec,
                    'remaining': max(0, self.signal_detector.silence_duration_sec - silence_duration)
                })

                # Check if silence threshold exceeded
                if self.signal_detector.is_silence_threshold_exceeded():
                    logger.info("Silence threshold exceeded - auto-stopping recording")
                    return_to_armed = (state == RecordingState.RECORDING_AUTO and self._auto_record_enabled)
                    self._stop_recording_internal(return_to_armed)

    def get_silence_countdown(self) -> Optional[float]:
        """
        Get remaining time before silence auto-stop (if recording and silent).

        Returns:
            Seconds remaining, or None if not applicable
        """
        if not self.is_recording():
            return None

        silence_duration = self.signal_detector.get_silence_duration()
        if silence_duration == 0:
            return None

        remaining = self.signal_detector.silence_duration_sec - silence_duration
        return max(0.0, remaining)

    def get_status_info(self) -> Dict[str, Any]:
        """
        Get comprehensive status information for UI display.

        Returns:
            Dictionary with current state, auto-record status, and countdown info
        """
        return {
            'state': self.get_state().value,
            'is_recording': self.is_recording(),
            'auto_record_enabled': self._auto_record_enabled,
            'silence_countdown': self.get_silence_countdown(),
            'current_recording_path': str(self._current_recording_path) if self._current_recording_path else None
        }

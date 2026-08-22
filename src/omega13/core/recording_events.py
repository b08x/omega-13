"""Recording Event Handler - Textual-free business logic for recording events.

Extracts recording event handling logic from the Textual TUI app into a
reusable module that both TUI and headless modes can use.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from omega13.recording_controller import RecordingController, RecordingEvent, RecordingState
from omega13.session import SessionManager
from omega13.audio import AudioEngine
from omega13.config import ConfigManager
from omega13.notifications import DesktopNotifier

if TYPE_CHECKING:
    from omega13.transcription import TranscriptionService


@dataclass
class RecordingEventCallbacks:
    """Callback protocol for UI updates - implemented by TUI/headless consumers.

    All callbacks are optional and receive only primitive/serializable data
    to maintain Textual-free operation.
    """

    on_recording_started: Optional[Callable[[Path, str], None]] = None
    # (path, mode) - mode is "auto" or "manual"
    on_recording_stopped: Optional[Callable[[Optional[Path]], None]] = None
    # (path) - path is None if recording was discarded (low energy)
    on_silence_countdown: Optional[Callable[[float], None]] = None
    # (remaining_seconds)
    on_state_changed: Optional[Callable[[str, str], None]] = None
    # (old_state, new_state)
    on_session_status_changed: Optional[Callable[[], None]] = None
    on_transcription_started: Optional[Callable[[Path], None]] = None
    on_transcription_progress: Optional[Callable[[float], None]] = None
    on_transcription_complete: Optional[Callable[["TranscriptionResult", Path], None]] = None


class RecordingEventHandler:
    """Handles recording event business logic without Textual dependencies.

    Encapsulates the dispatcher for RecordingEvent enum (SIGNAL_DETECTED,
    AUTO_STARTED, MANUAL_STARTED, SILENCE_DETECTED, AUTO_STOPPED,
    MANUAL_STOPPED, STATE_CHANGED) and the register-and-transcribe logic.

    All UI updates are delegated via the RecordingEventCallbacks protocol,
    allowing TUI and headless modes to register their own update handlers.
    """

    def __init__(
        self,
        recording_controller: RecordingController,
        session_manager: SessionManager,
        audio_engine: AudioEngine,
        config_manager: ConfigManager,
        notifier: Optional[DesktopNotifier] = None,
        transcription_service: Optional["TranscriptionService"] = None,
    ) -> None:
        """Initialize the recording event handler.

        Args:
            recording_controller: Manages recording state machine
            session_manager: Manages session lifecycle and recordings
            audio_engine: Audio I/O engine
            config_manager: Configuration manager
            notifier: Optional desktop notifier for system notifications
            transcription_service: Optional transcription service (can be set later)
        """
        self.recording_controller = recording_controller
        self.session_manager = session_manager
        self.audio_engine = audio_engine
        self.config_manager = config_manager
        self.notifier = notifier
        self.transcription_service = transcription_service

        # Callbacks for UI updates
        self._callbacks = RecordingEventCallbacks()

        # Current recording path (tracked for SIGNAL_DETECTED -> manual_start)
        self._current_recording_path: Optional[Path] = None

    def set_callbacks(self, callbacks: RecordingEventCallbacks) -> None:
        """Register UI callback handlers.

        Args:
            callbacks: RecordingEventCallbacks instance with desired handlers
        """
        self._callbacks = callbacks

    def set_transcription_service(self, service: "TranscriptionService") -> None:
        """Set transcription service (can be called after initialization).

        Args:
            service: TranscriptionService instance
        """
        self.transcription_service = service

    def handle_event(self, event: RecordingEvent, data: dict) -> None:
        """Handle a recording event from the controller.

        This is the main entry point called by RecordingController's event callback.

        Args:
            event: The RecordingEvent that occurred
            data: Event data dictionary (path, remaining, old_state, new_state, etc.)
        """
        if event == RecordingEvent.SIGNAL_DETECTED:
            self._handle_signal_detected(data)
        elif event == RecordingEvent.AUTO_STARTED:
            self._handle_auto_started(data)
        elif event == RecordingEvent.MANUAL_STARTED:
            self._handle_manual_started(data)
        elif event == RecordingEvent.SILENCE_DETECTED:
            self._handle_silence_detected(data)
        elif event == RecordingEvent.AUTO_STOPPED:
            self._handle_auto_stopped(data)
        elif event == RecordingEvent.MANUAL_STOPPED:
            self._handle_manual_stopped(data)
        elif event == RecordingEvent.STATE_CHANGED:
            self._handle_state_changed(data)

    def _handle_signal_detected(self, data: dict) -> None:
        """Handle SIGNAL_DETECTED - auto-record triggered by signal.

        Asks session for next recording path, starts recording via controller.
        No UI updates in this method - UI responds to AUTO_STARTED event.
        """
        session = self.session_manager.get_current_session()
        if session:
            recording_path = session.get_next_recording_path()
            self._current_recording_path = recording_path
            self.recording_controller.manual_start_recording(recording_path)

    def _handle_auto_started(self, data: dict) -> None:
        """Handle AUTO_STARTED - recording started automatically."""
        path_str = data.get("path", "")
        path = Path(path_str) if path_str else None
        self._current_recording_path = path

        if self._callbacks.on_recording_started and path:
            self._callbacks.on_recording_started(path, "auto")

        if self.notifier and path:
            self.notifier.notify(
                "Auto-Recording Started",
                f"Signal detected, capturing to {path.name}",
            )

    def _handle_manual_started(self, data: dict) -> None:
        """Handle MANUAL_STARTED - user started recording."""
        path_str = data.get("path", "")
        path = Path(path_str) if path_str else None
        self._current_recording_path = path

        if self._callbacks.on_recording_started and path:
            self._callbacks.on_recording_started(path, "manual")

    def _handle_silence_detected(self, data: dict) -> None:
        """Handle SILENCE_DETECTED - silence countdown during recording."""
        remaining = data.get("remaining", 0.0)

        if self._callbacks.on_silence_countdown:
            self._callbacks.on_silence_countdown(remaining)

    def _handle_auto_stopped(self, data: dict) -> None:
        """Handle AUTO_STOPPED - auto-recording stopped due to silence."""
        path_str = data.get("path", "")
        path = Path(path_str) if path_str else None

        # Register and transcribe if path is valid
        if path and path.exists():
            self.register_and_transcribe(path)

        if self._callbacks.on_recording_stopped:
            self._callbacks.on_recording_stopped(path)

        if self.notifier:
            self.notifier.notify("Recording Stopped", "Audio capture saved.")

    def _handle_manual_stopped(self, data: dict) -> None:
        """Handle MANUAL_STOPPED - user stopped recording."""
        path_str = data.get("path", "")
        path = Path(path_str) if path_str else None

        # Register and transcribe if path is valid
        if path and path.exists():
            self.register_and_transcribe(path)

        if self._callbacks.on_recording_stopped:
            self._callbacks.on_recording_stopped(path)

        if self.notifier:
            self.notifier.notify("Recording Stopped", "Audio capture saved.")

    def _handle_state_changed(self, data: dict) -> None:
        """Handle STATE_CHANGED - state transition occurred."""
        old_state = data.get("old_state", "")
        new_state = data.get("new_state", "")

        if self._callbacks.on_state_changed:
            self._callbacks.on_state_changed(old_state, new_state)

    def register_and_transcribe(self, path: Path) -> None:
        """Register recording in session and start transcription if enabled.

        Args:
            path: Path to the recorded audio file
        """
        if not path or not path.exists():
            return

        duration = 0.0
        try:
            import soundfile as sf

            info = sf.info(path)
            duration = info.duration
        except ImportError:
            # soundfile not available, duration stays 0.0
            pass
        except Exception:
            # Other errors (corrupt file, etc.) - duration stays 0.0
            pass

        session = self.session_manager.get_current_session()
        if session:
            session.register_recording(
                path,
                duration_seconds=duration,
                channels=self.audio_engine.channels,
                samplerate=self.audio_engine.samplerate,
            )

        # Fire session status changed callback
        if self._callbacks.on_session_status_changed:
            self._callbacks.on_session_status_changed()

        # Start transcription if enabled
        if self.config_manager.get_auto_transcribe() and self.transcription_service:
            def on_clipboard_error(error_msg: str):
                if self.notifier:
                    self.notifier.notify("Clipboard Error", error_msg, urgency="normal")
                    
            def on_injection_error(error_msg: str):
                if self.notifier:
                    self.notifier.notify("Injection Error", error_msg, urgency="critical")
                    
            def on_daily_note_error(error_msg: str):
                if self.notifier:
                    self.notifier.notify("Daily Note Error", error_msg, urgency="normal")

            def wrapped_on_complete(result):
                self._on_transcription_complete(result, path)

            def wrapped_on_progress(progress: float):
                if self._callbacks.on_transcription_progress:
                    self._callbacks.on_transcription_progress(progress)

            if self._callbacks.on_transcription_started:
                self._callbacks.on_transcription_started(path)

            self.transcription_service.transcribe_async(
                path,
                wrapped_on_complete,
                progress_callback=wrapped_on_progress,
                copy_to_clipboard_enabled=self.config_manager.get_copy_to_clipboard(),
                clipboard_error_callback=on_clipboard_error,
                inject_to_active_window_enabled=self.config_manager.get_inject_to_active_window(),
                injection_error_callback=on_injection_error,
                write_to_daily_note_enabled=self.config_manager.get_write_to_daily_note(),
                daily_note_error_callback=on_daily_note_error,
            )

    def _on_transcription_complete(self, result, path: Optional[Path] = None) -> None:
        """Handle transcription completion."""
        # Add to session
        if getattr(result, "status", None) and (
            getattr(result.status, "name", "") == "COMPLETED" or 
            getattr(result.status, "value", result.status) == "completed" or 
            str(result.status) == "TranscriptionStatus.COMPLETED"
        ) and getattr(result, "text", None):
            session = self.session_manager.get_current_session()
            if session:
                session.add_transcription(result.text)
                
        # Notify UI if callback exists
        if self._callbacks.on_transcription_complete:
            self._callbacks.on_transcription_complete(result, path)
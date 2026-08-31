"""Headless D-Bus service for Omega-13.

Provides D-Bus service registration without Textual TUI dependencies.
Enables global hotkey toggle via `omega13 --toggle` in headless environments.
"""

import asyncio
import logging
import signal
from typing import Optional

logger = logging.getLogger(__name__)

from dbus_next.errors import DBusError
from dbus_next.service import ServiceInterface, method, signal as dbus_signal
from dbus_next.aio.message_bus import MessageBus
from dbus_next import Variant
DBUS_AVAILABLE = True

from .config import ConfigManager
from .audio import AudioEngine, DEFAULT_CHANNELS
from .session import SessionManager
from .recording_controller import RecordingController, RecordingState, RecordingEvent
from .signal_detector import SignalDetector
from .hotkeys import GlobalHotkeyListener
from .core.recording_events import RecordingEventHandler, RecordingEventCallbacks
from .notifications import DesktopNotifier

try:
    from .ui.osd import osd_manager
    OSD_AVAILABLE = True
except Exception as e:
    logger.error(f"Failed to load OSD: {e}")
    import traceback
    logger.error(traceback.format_exc())
    osd_manager = None
    OSD_AVAILABLE = False
# Optional import for transcription - same pattern as app.py
try:
    from .transcription import (
        TranscriptionService,
        LocalTranscriptionProvider,
        GroqTranscriptionProvider,
    )
    TRANSCRIPTION_AVAILABLE = True
except ImportError:
    TRANSCRIPTION_AVAILABLE = False

# D-Bus constants
DBUS_SERVICE_NAME = "org.omega13.Recorder"
DBUS_OBJECT_PATH = "/org/omega13/Recorder"
DBUS_INTERFACE_NAME = "org.omega13.Recorder"


class HeadlessRecorderInterface(ServiceInterface):
    """D-Bus interface for headless Omega-13 recorder control."""

    def __init__(
        self,
        recording_controller: RecordingController,
        audio_engine: AudioEngine,
        session_manager: SessionManager,
        config_manager: ConfigManager,
        transcription_service: Optional[TranscriptionService] = None,
    ) -> None:
        super().__init__(DBUS_INTERFACE_NAME)
        self.recording_controller = recording_controller
        self.audio_engine = audio_engine
        self.session_manager = session_manager
        self.config_manager = config_manager
        self.transcription_service = transcription_service

    @method()
    async def ToggleRecording(self) -> "b":  # type: ignore
        """Toggle recording state.

        Returns:
            bool: New recording state (True = recording, False = stopped)

        Raises:
            DBusError: If toggle operation fails
        """
        try:
            if self.recording_controller.is_recording():
                self.recording_controller.manual_stop_recording()
            else:
                # Check for audio activity before starting
                if not self.audio_engine.has_audio_activity():
                    raise DBusError(
                        "org.omega13.Recorder.NoAudioActivity",
                        "No audio activity or connections detected"
                    )

                session = self.session_manager.get_current_session()
                if not session:
                    raise DBusError(
                        "org.omega13.Recorder.NoSession",
                        "No active session"
                    )

                recording_path = session.get_next_recording_path()
                success = self.recording_controller.manual_start_recording(recording_path)
                if not success:
                    raise DBusError(
                        "org.omega13.Recorder.StartFailed",
                        "Failed to start recording"
                    )

            is_recording = self.recording_controller.is_recording()
            # Emit signal for state change
            self.RecordingToggled(is_recording)
            return is_recording
        except DBusError:
            raise
        except Exception as e:
            raise DBusError("org.omega13.Recorder.ToggleError", str(e))

    @method()
    async def GetState(self) -> "s":  # type: ignore
        """Get current recording state.

        Returns:
            str: Current state (IDLE, ARMED, RECORDING_AUTO, RECORDING_MANUAL, STOPPING)

        Raises:
            DBusError: If state query fails
        """
        try:
            state = self.recording_controller.get_state()
            return state.value
        except Exception as e:
            raise DBusError("org.omega13.Recorder.StateError", str(e))

    def _get_health_data(self) -> dict:
        try:
            session = self.session_manager.current_session
            health = {
                "state": Variant("s", self.recording_controller.get_state().value),
                "is_recording": Variant("b", self.recording_controller.is_recording()),
                "auto_record_enabled": Variant("b", self.recording_controller.is_auto_record_enabled()),
                "audio": Variant("a{sv}", {
                    "connected": Variant("b", self.audio_engine.client is not None),
                    "sample_rate": Variant("i", self.audio_engine.samplerate if self.audio_engine.client else 0),
                    "channels": Variant("i", self.audio_engine.channels if self.audio_engine.client else 0),
                    "has_activity": Variant("b", self.audio_engine.has_audio_activity() if self.audio_engine.client else False),
                    "is_recording": Variant("b", self.audio_engine.is_recording if self.audio_engine.client else False),
                }),
                "session": Variant("a{sv}", {
                    "active": Variant("b", session is not None),
                    "session_id": Variant("s", session.session_id if session else ""),
                    "recording_count": Variant("i", len(session.recordings) if session else 0),
                    "saved": Variant("b", session.saved if session else True),
                }),
                "transcription": Variant("a{sv}", {
                    "available": Variant("b", self.transcription_service is not None),
                    "provider": Variant("s", self.config_manager.get_transcription_provider()),
                }),
            }
            return health
        except Exception as e:
            raise DBusError("org.omega13.Recorder.HealthError", str(e))

    @method()
    async def GetHealth(self) -> "a{sv}":  # type: ignore
        """Get comprehensive health status.

        Returns:
            dict: Health status including state, audio, session, transcription

        Raises:
            DBusError: If health query fails
        """
        return self._get_health_data()

    @dbus_signal()
    def RecordingToggled(self, is_recording: "b") -> None:  # type: ignore
        """Signal emitted when recording state changes.
        
        Args:
            is_recording: True if now recording, False if stopped
        """
        pass

    @dbus_signal()
    def HealthStatus(self, status: "a{sv}") -> None:  # type: ignore
        """Signal emitted for periodic health status updates.
        
        Args:
            status: Dictionary with health status information
        """
        pass


class HeadlessDBusService:
    """Headless D-Bus service manager for Omega-13."""

    SERVICE_NAME: str = DBUS_SERVICE_NAME
    OBJECT_PATH: str = DBUS_OBJECT_PATH
    INTERFACE_NAME: str = DBUS_INTERFACE_NAME

    def __init__(
        self,
        recording_controller: RecordingController,
        audio_engine: AudioEngine,
        session_manager: SessionManager,
        config_manager: ConfigManager,
        transcription_service: Optional[TranscriptionService] = None,
    ) -> None:
        self.recording_controller = recording_controller
        self.audio_engine = audio_engine
        self.session_manager = session_manager
        self.config_manager = config_manager
        self.transcription_service = transcription_service
        self.bus: Optional[MessageBus] = None
        self.interface: Optional[HeadlessRecorderInterface] = None
        self._is_registered: bool = False

    async def register(self) -> None:
        """Register the D-Bus service."""
        try:
            self.bus = await MessageBus().connect()
            self.interface = HeadlessRecorderInterface(
                self.recording_controller,
                self.audio_engine,
                self.session_manager,
                self.config_manager,
                self.transcription_service,
            )
            self.bus.export(self.OBJECT_PATH, self.interface)
            await self.bus.request_name(self.SERVICE_NAME)
            self._is_registered = True
            logger.info("Headless D-Bus service registered successfully")
        except Exception as e:
            raise DBusError("org.omega13.Recorder.RegistrationError", str(e))

    async def unregister(self) -> None:
        """Unregister the D-Bus service."""
        try:
            if self.bus and self._is_registered:
                await self.bus.release_name(self.SERVICE_NAME)
                self.bus.unexport(self.OBJECT_PATH)
                self._is_registered = False
                logger.info("Headless D-Bus service unregistered")
        except Exception:
            pass

    def is_registered(self) -> bool:
        return self._is_registered

    async def get_health(self) -> dict:
        if self.interface is None:
            raise DBusError("org.omega13.Recorder.HealthError", "D-Bus interface not initialized")
        return self.interface._get_health_data()


class HeadlessOmega13:
    """Headless Omega-13 core without TUI.

    Initializes audio, recording, session management, and D-Bus service.
    Runs on asyncio event loop without Textual.
    """

    def __init__(self) -> None:
        self.config_manager: Optional[ConfigManager] = None
        self.audio_engine: Optional[AudioEngine] = None
        self.session_manager: Optional[SessionManager] = None
        self.recording_controller: Optional[RecordingController] = None
        self.dbus_service: Optional[HeadlessDBusService] = None
        self.hotkey_listener: Optional[GlobalHotkeyListener] = None
        self._recording_event_handler: Optional[RecordingEventHandler] = None
        self.transcription_service: Optional[TranscriptionService] = None
        self._shutdown_initiated = False

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing headless Omega-13...")

        # Initialize config
        self.config_manager = ConfigManager()

        # Initialize session manager
        temp_root = self.config_manager.get_session_temp_root()
        self.session_manager = SessionManager(temp_root=temp_root)
        self.session_manager.create_session()

        # Initialize audio engine
        saved_ports = self.config_manager.get_input_ports()
        num_channels = len(saved_ports) if saved_ports else DEFAULT_CHANNELS

        self.audio_engine = AudioEngine(
            config_manager=self.config_manager, num_channels=num_channels
        )
        self.audio_engine.start()

        # Connect saved inputs or fallback to defaults
        connection_success = False
        if saved_ports:
            connection_success = self.audio_engine.connect_inputs(saved_ports)
            if not connection_success:
                logger.warning(f"Failed to connect saved ports {saved_ports}, falling back to defaults")

        if not connection_success:
            logger.info("Attempting to auto-connect to default capture ports")
            available_ports = self.audio_engine.get_available_output_ports()
            default_ports = [p.name for p in available_ports if "system:capture" in p.name]
            if not default_ports and available_ports:
                default_ports = [p.name for p in available_ports]
            
            if default_ports:
                if len(default_ports) < self.audio_engine.channels:
                    default_ports.extend([default_ports[0]] * (self.audio_engine.channels - len(default_ports)))
                default_ports = default_ports[:self.audio_engine.channels]
                logger.info(f"Auto-connecting to: {default_ports}")
                self.audio_engine.connect_inputs(default_ports)
                self.config_manager.set_input_ports(default_ports)

        # Initialize signal detector and recording controller
        # Use audio engine's samplerate and channels (available after start())
        signal_detector = SignalDetector(
            samplerate=self.audio_engine.samplerate,
            channels=self.audio_engine.channels,
            begin_threshold_db=self.config_manager.get_auto_record_begin_threshold(),
            end_threshold_db=self.config_manager.get_auto_record_end_threshold(),
            silence_duration_sec=self.config_manager.get_auto_record_silence_duration(),
        )

        self.recording_controller = RecordingController(
            audio_engine=self.audio_engine,
            signal_detector=signal_detector,
            config_manager=self.config_manager,
        )

        # Initialize recording event handler (Textual-free business logic)
        notifier = DesktopNotifier() if self.config_manager.get_desktop_notifications_enabled() else None
        self._recording_event_handler = RecordingEventHandler(
            recording_controller=self.recording_controller,
            session_manager=self.session_manager,
            audio_engine=self.audio_engine,
            config_manager=self.config_manager,
            notifier=notifier,
        )
        self.recording_controller.set_event_callback(self._recording_event_handler.handle_event)
        
        if OSD_AVAILABLE and osd_manager:
            osd_manager.run_in_background()
            self._recording_event_handler.set_callbacks(
                RecordingEventCallbacks(
                    on_recording_started=lambda path, mode: osd_manager.update("Recording", state_type="recording"),
                    on_recording_stopped=lambda path: osd_manager.update("Processing...", state_type="processing"),
                    on_transcription_started=lambda path: osd_manager.update("Transcribing...", state_type="processing"),
                    on_transcription_complete=lambda result, path: osd_manager.update(f"Copied: {result.text[:20]}...", state_type="success", timeout_ms=4000) if hasattr(result, "text") else osd_manager.update("Transcription Done", state_type="success", timeout_ms=4000),
                )
            )

        # Initialize transcription service if available and enabled
        if TRANSCRIPTION_AVAILABLE and self.config_manager.get_transcription_enabled():
            try:
                provider_type = self.config_manager.get_transcription_provider()
                logger.info(f"Loading transcription provider: {provider_type}")
                if provider_type == "groq":
                    provider = GroqTranscriptionProvider(
                        api_key=self.config_manager.get_groq_api_key(),
                        model=self.config_manager.get_groq_model(),
                    )
                else:
                    provider = LocalTranscriptionProvider(
                        server_url=self.config_manager.get_transcription_server_url(),
                        inference_path=self.config_manager.get_transcription_inference_path(),
                    )
                self.transcription_service = TranscriptionService(
                    provider=provider, notifier=notifier
                )
                # Set transcription service on event handler
                self._recording_event_handler.set_transcription_service(self.transcription_service)
                logger.info(f"Transcription service initialized with {provider_type} provider")
            except Exception as e:
                logger.warning(f"Failed to initialize transcription service: {e}")
                self.transcription_service = None

        # Enable auto-record if configured
        if self.config_manager.get_auto_record_enabled():
            self.recording_controller.enable_auto_record()

        # Initialize and register D-Bus service
        self.dbus_service = HeadlessDBusService(
            self.recording_controller,
            self.audio_engine,
            self.session_manager,
            self.config_manager,
            self.transcription_service,
        )
        await self.dbus_service.register()

        # Start periodic health status emission
        health_task = asyncio.create_task(self._periodic_health_status())

        # Initialize global hotkeys
        global_hotkey_str = self.config_manager.get_global_hotkey()
        if global_hotkey_str:
            self.hotkey_listener = GlobalHotkeyListener(
                global_hotkey_str,
                lambda: self._handle_hotkey_toggle(),
            )
            if self.hotkey_listener.start():
                resolved = self.hotkey_listener.resolved_hotkey_str
                logger.info(f"Hotkey listener started successfully with: {resolved}")
            else:
                resolved = self.hotkey_listener.resolved_hotkey_str or "unresolved"
                logger.error(
                    f"Failed to activate hotkey: {global_hotkey_str} (parsed as: {resolved})"
                )

        logger.info("Headless Omega-13 initialized successfully")

    async def shutdown(self) -> None:
        """Shutdown all components."""
        if self._shutdown_initiated:
            return
        self._shutdown_initiated = True

        logger.info("Shutting down headless Omega-13...")
        
        if OSD_AVAILABLE and osd_manager:
            osd_manager.quit()

        # Stop hotkey listener
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
                logger.info("Hotkey listener stopped")
            except Exception as e:
                logger.error(f"Hotkey stop error: {e}")

        # Stop D-Bus service
        if self.dbus_service and self.dbus_service.is_registered():
            try:
                await self.dbus_service.unregister()
            except Exception as e:
                logger.error(f"D-Bus service stop error: {e}")

        # Stop transcription service
        if self.transcription_service:
            try:
                logger.info("Shutting down transcription service...")
                self.transcription_service.shutdown(timeout=10.0)
                logger.info("Transcription service stopped")
            except Exception as e:
                logger.error(f"Transcription service shutdown error: {e}")

        # Stop audio engine
        if self.audio_engine:
            try:
                if self.audio_engine.is_recording:
                    logger.info("Stopping active recording...")
                    self.audio_engine.stop_recording()
                self.audio_engine.stop()
            except Exception as e:
                logger.error(f"Audio engine error: {e}")

        # Session cleanup
        if self.session_manager:
            try:
                if (
                    not self.session_manager.is_saved()
                    and self.session_manager.has_recordings()
                ):
                    logger.info("Leaving unsaved session intact")
                else:
                    self.session_manager.discard_session()
            except Exception as e:
                logger.error(f"Session cleanup error: {e}")

        logger.info("Headless Omega-13 shutdown complete")

    def _handle_hotkey_toggle(self) -> None:
        """Handle global hotkey toggle recording (called from pynput thread)."""
        if self.recording_controller:
            # Schedule the toggle on the asyncio event loop
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self._async_toggle_recording)
            except RuntimeError:
                # No running loop, ignore
                pass

    async def _async_toggle_recording(self) -> None:
        """Async recording toggle for hotkey."""
        if self.recording_controller.is_recording():
            self.recording_controller.manual_stop_recording()
        else:
            if not self.audio_engine.has_audio_activity():
                logger = logging.getLogger(__name__)
                logger.warning("No audio activity detected, ignoring hotkey")
                return

            session = self.session_manager.get_current_session()
            if not session:
                logger = logging.getLogger(__name__)
                logger.warning("No active session, ignoring hotkey")
                return

            recording_path = session.get_next_recording_path()
            self.recording_controller.manual_start_recording(recording_path)

    async def run(self) -> None:
        """Run the headless service event loop."""
        await self.initialize()

        # Setup signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGUSR1):
            if sig == signal.SIGUSR1:
                # SIGUSR1 toggles recording (for external tools / PID file mechanism)
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._handle_sigusr1()))
            else:
                # Bind sig by default argument to avoid late-binding closure bug
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown()))

        # Keep running until shutdown
        try:
            while not self._shutdown_initiated:
                await asyncio.sleep(1)
        finally:
            await self.shutdown()

    async def _handle_sigusr1(self) -> None:
        """Handle SIGUSR1 - toggle recording (for PID file / signal mechanism)."""
        logger.info("Received SIGUSR1, toggling recording")
        if self.recording_controller.is_recording():
            self.recording_controller.manual_stop_recording()
        else:
            # Check for audio activity before starting
            if not self.audio_engine.has_audio_activity():
                logger.warning("No audio activity or connections detected - cannot start recording")
                return

            session = self.session_manager.get_current_session()
            if not session:
                logger.warning("No active session")
                return

            recording_path = session.get_next_recording_path()
            success = self.recording_controller.manual_start_recording(recording_path)
            if not success:
                logger.error("Failed to start recording")

    async def _periodic_health_status(self) -> None:
        """Emit periodic HealthStatus D-Bus signals."""
        while not self._shutdown_initiated:
            await asyncio.sleep(30)
            if self._shutdown_initiated or not self.dbus_service or not self.dbus_service.is_registered():
                continue
            try:
                health = await self.dbus_service.get_health()
                self.dbus_service.interface.HealthStatus(health)
            except Exception as e:
                logger.debug(f"Periodic health status emission failed: {e}")


async def run_headless() -> None:
    """Entry point for headless mode."""
    headless = HeadlessOmega13()
    await headless.run()


def main_headless() -> None:
    """Synchronous entry point for headless mode."""
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_headless())
import asyncio
import logging
import signal
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import refactored modules
from .config import ConfigManager
from .audio import AudioEngine, DEFAULT_CHANNELS
from .core import RecordingEventHandler, RecordingEventCallbacks
from .ui import (
    VUMeter,
    TranscriptionDisplay,
    InputSelectionScreen,
    DirectorySelectionScreen,
    SessionTitleScreen,
    SilenceCountdown,
    TranscriptionSettingsScreen,
)
from .session import SessionManager
from .hotkeys import GlobalHotkeyListener
from .notifications import DesktopNotifier
from .signal_detector import SignalDetector
from .recording_controller import RecordingController, RecordingState, RecordingEvent
from .dbus_service import DBusService
from .obsidian_cli import obsidian_cli
# Optional import for transcription
try:
    from .transcription import (
        TranscriptionService,
        TranscriptionStatus,
        TranscriptionResult,
        LocalTranscriptionProvider,
        GroqTranscriptionProvider,
    )

    TRANSCRIPTION_AVAILABLE = True
except ImportError:
    TRANSCRIPTION_AVAILABLE = False


# Textual and UI imports are loaded lazily in main() when --tui is used
# This ensures headless mode never imports or initializes Textual
def _import_textual_and_ui():
    """Lazy import of Textual and UI components for TUI mode."""
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Header, Footer, Label, Static
    from textual.reactive import reactive
    from textual.css.query import NoMatches

    from .ui import (
        VUMeter,
        TranscriptionDisplay,
        InputSelectionScreen,
        DirectorySelectionScreen,
        SessionTitleScreen,
        SilenceCountdown,
        TranscriptionSettingsScreen,
    )

    return {
        "App": App,
        "ComposeResult": ComposeResult,
        "Binding": Binding,
        "Container": Container,
        "Horizontal": Horizontal,
        "Vertical": Vertical,
        "Header": Header,
        "Footer": Footer,
        "Label": Label,
        "Static": Static,
        "reactive": reactive,
        "NoMatches": NoMatches,
        "VUMeter": VUMeter,
        "TranscriptionDisplay": TranscriptionDisplay,
        "InputSelectionScreen": InputSelectionScreen,
        "DirectorySelectionScreen": DirectorySelectionScreen,
        "SessionTitleScreen": SessionTitleScreen,
        "SilenceCountdown": SilenceCountdown,
        "TranscriptionSettingsScreen": TranscriptionSettingsScreen,
    }




# Module-level placeholder Omega13App for import compatibility
# This class has the same attributes as the real Textual App but doesn't import Textual
# The real Textual-based class is defined inside main() when --tui is used
class Omega13App:
    """Placeholder class for headless mode - provides same interface without Textual."""
    
    CSS = """
    /* --- CUSTOM COLOR SCHEME --- */
    $background: #0F0F1F;
    $surface: #161526;
    $surface-lighten-1: #271D37;
    $surface-darken-1: #13101D;
    
    $primary: #7726C4;
    $secondary: #1B544C;
    $accent: #119EDE;
    
    $success: #00F698;
    $warning: #AD5CC8;
    $error: #934167;
    
    $text: #D5CEDB;
    $text-muted: #9999A1;
    /* --------------------------- */

    Screen { align: center middle; background: $background; }
    #app-layout { width: 100%; height: 100%; }
    
    #left-pane { width: 40%; height: 100%; border: solid $accent; margin-right: 1; }
    #audio-controls { height: 75%; padding: 1 2; background: $surface-lighten-1; border-bottom: solid $accent; }
    #transcription-controls { height: 25%; padding: 1 2; background: $surface-darken-1; }
    
    #transcription-pane { width: 60%; height: 100%; border: solid $accent; padding: 1 2; background: $surface-lighten-1; }
    
    .title { text-align: center; text-style: bold; margin-bottom: 1; color: $primary; }
    .status-idle { color: $background; background: $success; padding: 1; text-align: center; text-style: bold; }
    .status-recording { color: $text; background: $error; padding: 1; text-align: center; text-style: bold; }
    
    #connection-status, #path-status, #buffer-info { text-align: center; padding: 0 1; margin-top: 1; }
    #connection-status { border: solid $primary; background: $surface-darken-1; }
    #meters { height: 5; margin-top: 1; border: heavy $primary; }
    
    .help-text { text-align: center; width: 100%; margin-top: 1; color: $text-muted; }
    Label { width: 100%; color: $text; }
    
    /* UI Imports CSS */
    #transcription-status { text-align: center; padding: 1; margin-bottom: 1; border: solid $primary; }
    .status-loading, .status-processing { color: $background; background: $warning; }
    .status-complete { color: $background; background: $success; }
    .status-error { color: $text; background: $error; }
    
    #clipboard-toggle { margin-bottom: 1; padding: 0 1; }
    #transcription-log { height: 1fr; border: solid $primary; background: $surface-darken-1; padding: 1; color: $text; }
    
    .transcription-header { height: auto; align: center middle; margin-bottom: 1; }
    .transcription-title { width: auto; text-align: center; text-style: bold; color: $accent; }
    
    .provider-badge { width: auto; padding: 0 1; background: $accent; color: $background; text-style: bold; margin-left: 1; }
    .provider-local { background: $primary; }
    .provider-groq { background: $secondary; }
    """

    BINDINGS = [
        ("i", "open_input_selector", "Select Inputs"),
        ("n", "new_session", "New Session"),
        ("s", "save_session", "Save Session"),
        ("t", "manual_transcribe", "Transcribe"),
        ("a", "toggle_auto_record", "Toggle Auto-record"),
        ("c", "toggle_clipboard", "Toggle Clipboard"),
        ("j", "toggle_injection", "Toggle Injection"),
        ("d", "toggle_daily_note", "Toggle Daily Note"),
        ("p", "open_settings", "Settings"),
        ("q", "quit", "Quit"),
    ]

    # Reactive attributes (using plain class attributes for headless mode)
    auto_record_enabled = False
    copy_to_clipboard = False
    inject_to_active_window = False
    write_to_daily_note = False




def configure_logging(level: str = "INFO") -> None:
    log_dir = Path.home() / ".local" / "share" / "omega13" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"omega13_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file)],
    )
    logging.getLogger(__name__).info(f"Logging initialized: {log_file}")


def _daemonize() -> None:
    """Standard double-fork Unix daemonization."""
    # First fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)  # Parent exits
    if pid < 0:
        sys.exit(1)

    # Decouple from parent environment
    os.setsid()
    os.chdir("/")

    # Second fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)  # First child exits
    if pid < 0:
        sys.exit(1)

    # Redirect standard file descriptors to /dev/null
    sys.stdout.flush()
    sys.stderr.flush()
    null_fd = os.open(os.devnull, os.O_RDWR)
    os.dup2(null_fd, sys.stdin.fileno())
    os.dup2(null_fd, sys.stdout.fileno())
    os.dup2(null_fd, sys.stderr.fileno())
    if null_fd > 2:
        os.close(null_fd)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Omega-13 retroactive audio recorder")
    parser.add_argument(
        "--toggle", action="store_true", help="Toggle recording on a running instance"
    )
    parser.add_argument(
        "--stop", action="store_true", help="Stop a running instance"
    )
    parser.add_argument("--tui", action="store_true", help="Launch with the Textual TUI")
    parser.add_argument("--daemon", action="store_true", default=True, help="Run as background daemon (default)")
    parser.add_argument("--no-daemon", action="store_false", dest="daemon", help="Run in foreground without daemonizing")
    parser.add_argument("--log-level", default="INFO", help="Set logging level")
    args = parser.parse_args()

    if args.toggle:
        # Use D-Bus to toggle recording on running instance
        from .hotkeys import send_dbus_toggle
        try:
            state = send_dbus_toggle()
            print(f"Toggle signal sent. Recording state: {state}")
            sys.exit(0)
        except ConnectionError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)

    if args.stop:
        from .pidfile import read_pid, is_stale
        pid_file = Path("/tmp/omega13.pid")
        if not pid_file.exists():
            print("Omega-13 is not running (PID file not found).")
            sys.exit(0)
            
        pid = read_pid(pid_file)
        if pid is None or is_stale(pid_file):
            print("Omega-13 is not running (stale or invalid PID file).")
            try:
                pid_file.unlink()
            except OSError:
                pass
            sys.exit(0)
            
        try:
            print(f"Stopping Omega-13 (PID {pid})...")
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to exit
            for _ in range(50):
                if is_stale(pid_file):
                    print("Omega-13 stopped successfully.")
                    sys.exit(0)
                time.sleep(0.1)
                
            print("Process did not exit in time. Sending SIGKILL...")
            os.kill(pid, signal.SIGKILL)
            try:
                pid_file.unlink()
            except OSError:
                pass
            print("Omega-13 killed.")
            sys.exit(0)
        except ProcessLookupError:
            print("Omega-13 is no longer running.")
            try:
                pid_file.unlink()
            except OSError:
                pass
            sys.exit(0)
        except PermissionError:
            print(f"Error: Permission denied to stop process {pid}.")
            sys.exit(1)
        except Exception as e:
            print(f"Error stopping process: {e}")
            sys.exit(1)

    configure_logging(level=args.log_level)

    if args.tui:
        # TUI mode: always runs in foreground for terminal access
        # Import Textual and UI components lazily - only when --tui is used
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Container, Horizontal, Vertical
        from textual.widgets import Header, Footer, Label, Static
        from textual.reactive import reactive
        from textual.css.query import NoMatches

        from .ui import (
            VUMeter,
            TranscriptionDisplay,
            InputSelectionScreen,
            DirectorySelectionScreen,
            SessionTitleScreen,
            SilenceCountdown,
            TranscriptionSettingsScreen,
        )

        # Define the Textual App class here (only in TUI mode)
        class Omega13App(App):
            """Placeholder class for headless mode - replaced by real Textual App when --tui is used."""
            pass
            CSS = """
            /* --- CUSTOM COLOR SCHEME --- */
            $background: #0F0F1F;
            $surface: #161526;
            $surface-lighten-1: #271D37;
            $surface-darken-1: #13101D;
            
            $primary: #7726C4;
            $secondary: #1B544C;
            $accent: #119EDE;
            
            $success: #00F698;
            $warning: #AD5CC8;
            $error: #934167;
            
            $text: #D5CEDB;
            $text-muted: #9999A1;
            /* --------------------------- */
        
            Screen { align: center middle; background: $background; }
            #app-layout { width: 100%; height: 100%; }
            
            #left-pane { width: 40%; height: 100%; border: solid $accent; margin-right: 1; }
            #audio-controls { height: 75%; padding: 1 2; background: $surface-lighten-1; border-bottom: solid $accent; }
            #transcription-controls { height: 25%; padding: 1 2; background: $surface-darken-1; }
            
            #transcription-pane { width: 60%; height: 100%; border: solid $accent; padding: 1 2; background: $surface-lighten-1; }
            
            .title { text-align: center; text-style: bold; margin-bottom: 1; color: $primary; }
            .status-idle { color: $background; background: $success; padding: 1; text-align: center; text-style: bold; }
            .status-recording { color: $text; background: $error; padding: 1; text-align: center; text-style: bold; }
            
            #connection-status, #path-status, #buffer-info { text-align: center; padding: 0 1; margin-top: 1; }
            #connection-status { border: solid $primary; background: $surface-darken-1; }
            #meters { height: 5; margin-top: 1; border: heavy $primary; }
            
            .help-text { text-align: center; width: 100%; margin-top: 1; color: $text-muted; }
            Label { width: 100%; color: $text; }
            
            /* UI Imports CSS */
            #transcription-status { text-align: center; padding: 1; margin-bottom: 1; border: solid $primary; }
            .status-loading, .status-processing { color: $background; background: $warning; }
            .status-complete { color: $background; background: $success; }
            .status-error { color: $text; background: $error; }
            
            #clipboard-toggle { margin-bottom: 1; padding: 0 1; }
            #transcription-log { height: 1fr; border: solid $primary; background: $surface-darken-1; padding: 1; color: $text; }
            
            .transcription-header { height: auto; align: center middle; margin-bottom: 1; }
            .transcription-title { width: auto; text-align: center; text-style: bold; color: $accent; }
            
            .provider-badge { width: auto; padding: 0 1; background: $accent; color: $background; text-style: bold; margin-left: 1; }
            .provider-local { background: $primary; }
            .provider-groq { background: $secondary; }
            """
        
            BINDINGS = [
                Binding("i", "open_input_selector", "Select Inputs"),
                Binding("n", "new_session", "New Session"),
                Binding("s", "save_session", "Save Session"),
                Binding("t", "manual_transcribe", "Transcribe"),
                Binding("a", "toggle_auto_record", "Toggle Auto-record"),
                Binding("c", "toggle_clipboard", "Toggle Clipboard"),
                Binding("j", "toggle_injection", "Toggle Injection"),
                Binding("d", "toggle_daily_note", "Toggle Daily Note"),
                Binding("p", "open_settings", "Settings"),
                Binding("q", "quit", "Quit"),
            ]
        
            auto_record_enabled = reactive(False)
            copy_to_clipboard = reactive(False)
            inject_to_active_window = reactive(False)
            write_to_daily_note = reactive(False)
        
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._shutdown_initiated = False
                self._signal_handlers_registered = False
                self.hotkey_listener: Optional[GlobalHotkeyListener] = None
                self.notifier: Optional[DesktopNotifier] = None
                self.dbus_service: Optional[DBusService] = None
        
            def compose(self) -> ComposeResult:
                yield Header()
                with Horizontal(id="app-layout"):
                    with Vertical(id="left-pane"):
                        with Vertical(id="audio-controls"):
                            yield Label("OMEGA-13", classes="title")
                            yield Static(
                                "IDLE - Ready to Capture",
                                id="status-bar",
                                classes="status-idle",
                            )
                            yield Static("Session: New (Unsaved)", id="session-status")
                            yield Static("Inputs: Loading...", id="connection-status")
                            yield Static("\nBuffers filled: ", id="buffer-info")
                            with Vertical(id="meters"):
                                yield Label("Channel 1", id="label-1")
                                yield VUMeter(id="meter-1")
                                yield Label("Channel 2", id="label-2")
                                yield VUMeter(id="meter-2")
                            yield SilenceCountdown(id="silence-countdown")
                            yield Static(
                                "\n[dim]REC Key to Capture | I Inputs | N New | S Save | T Transcribe | A Auto-Rec | C Clip | J Inject | P Settings[/dim]",
                                id="help-text",
                                classes="help-text",
                            )
        
                        with Vertical(id="transcription-controls"):
                            yield Label("Transcription Status", classes="transcription-title")
                            yield Static(
                                "Ready", id="transcription-status", classes="status-idle"
                            )
        
                    with Container(id="transcription-pane"):
                        yield TranscriptionDisplay(id="transcription-display")
                yield Footer()
        
            def _register_signal_handlers(self) -> None:
                def signal_handler(signum, frame):
                    signal_name = signal.Signals(signum).name
                    logger = logging.getLogger(__name__)
                    logger.info(f"Received signal {signal_name}, initiating graceful shutdown")
        
                    if self._shutdown_initiated:
                        return
        
                    self._shutdown_initiated = True
                    self.call_from_thread(self._graceful_shutdown)
        
                signal.signal(signal.SIGINT, signal_handler)
                signal.signal(signal.SIGTERM, signal_handler)
        
        
            def _graceful_shutdown(self) -> None:
                if hasattr(self, "session_manager"):
                    if (
                        not self.session_manager.is_saved()
                        and self.session_manager.has_recordings()
                    ):
                        self.session_manager.discard_session()
                self.exit()
        
            async def on_mount(self):
                if not self._signal_handlers_registered:
                    self._register_signal_handlers()
                    self._signal_handlers_registered = True
        
                try:
                    self.config_manager = ConfigManager()
        
                    # Initialize desktop notifier
                    if self.config_manager.get_desktop_notifications_enabled():
                        self.notifier = DesktopNotifier()
        
                    transcription_display = self.query_one(
                        "#transcription-display", TranscriptionDisplay
                    )
                    transcription_display.config_manager = self.config_manager
        
                    # Initialize reactive states from config
                    self.copy_to_clipboard = self.config_manager.get_copy_to_clipboard()
                    self.inject_to_active_window = (
                        self.config_manager.get_inject_to_active_window()
                    )
                    self.write_to_daily_note = self.config_manager.get_write_to_daily_note()
                    self.auto_record_enabled = self.config_manager.get_auto_record_enabled()
        
                    # Open daily note on launch if enabled
                    if self.write_to_daily_note:
                        result = obsidian_cli.open_daily_note_if_enabled()
                        if result.success:
                            self.notify("Daily note opened", severity="information", timeout=2)
                        elif "not configured" not in result.message.lower():
                            # Only show error if it's not just unconfigured
                            self.notify(f"Daily note: {result.message}", severity="warning", timeout=3)
        
                    temp_root = self.config_manager.get_session_temp_root()
                    self.session_manager = SessionManager(temp_root=temp_root)
        
                    # Update help text with configured hotkey
                    hotkey = self.config_manager.get_global_hotkey()
                    formatted_hotkey = (
                        hotkey.replace("<", "").replace(">", "").replace("+", " + ").title()
                    )
        
                    help_text = self.query_one("#help-text", Static)
                    help_text.update(
                        f"\n[dim]{formatted_hotkey} to Capture | I Inputs | N New | S Save | T Transcribe | A Auto-Rec | C Clip | J Inject | D Daily | P Settings[/dim]"
                    )
                    self.session_manager.create_session()
                    self._update_session_status()
        
                    days = self.config_manager.get_auto_cleanup_days()
                    self.session_manager.cleanup_old_sessions(days)
        
                    saved_ports = self.config_manager.get_input_ports()
                    num_channels = len(saved_ports) if saved_ports else DEFAULT_CHANNELS
        
                    self.engine = AudioEngine(
                        config_manager=self.config_manager, num_channels=num_channels
                    )
                    self.engine.start()
        
                    # Initialize recording controller
                    self.recording_controller = RecordingController(
                        audio_engine=self.engine,
                        signal_detector=self.engine.signal_detector,
                        config_manager=self.config_manager,
                    )
        
                    # Initialize recording event handler (Textual-free business logic)
                    self._recording_event_handler = RecordingEventHandler(
                        recording_controller=self.recording_controller,
                        session_manager=self.session_manager,
                        audio_engine=self.engine,
                        config_manager=self.config_manager,
                        notifier=self.notifier,
                    )
                    self.recording_controller.set_event_callback(self._recording_event_handler.handle_event)
        
                    # Set up UI callbacks for the event handler
                    self._recording_event_handler.set_callbacks(
                        RecordingEventCallbacks(
                            on_recording_started=self._on_recording_started,
                            on_recording_stopped=self._on_recording_stopped,
                            on_silence_countdown=self._on_silence_countdown,
                            on_state_changed=self._on_state_changed,
                            on_session_status_changed=self._update_session_status,
                            on_transcription_started=self._handle_transcription_started_from_event,
                            on_transcription_progress=self._handle_transcription_progress_from_event,
                            on_transcription_complete=self._handle_result_from_event,
                        )
                    )
        
                    # Enable auto-record if configured
                    if self.auto_record_enabled:
                        self.recording_controller.enable_auto_record()
        
        
                    self._load_and_connect_saved_inputs()
                    self._update_meter_visibility()
        
                    # Initialize Global Hotkeys
                    global_hotkey_str = self.config_manager.get_global_hotkey()
                    if global_hotkey_str:
                        self.hotkey_listener = GlobalHotkeyListener(
                            global_hotkey_str,
                            lambda: self.call_from_thread(self.action_toggle_record),
                        )
                        if self.hotkey_listener.start():
                            resolved = self.hotkey_listener.resolved_hotkey_str
                            logging.getLogger(__name__).info(
                                f"Hotkey listener started successfully with: {resolved}"
                            )
                            self.notify(f"Global hotkey active: {resolved}", timeout=5)
                        else:
                            resolved = self.hotkey_listener.resolved_hotkey_str or "unresolved"
                            self.notify(
                                f"Failed to activate hotkey: {global_hotkey_str} (parsed as: {resolved})",
                                severity="error",
                                timeout=10,
                            )
        
                    if TRANSCRIPTION_AVAILABLE:
                        try:
                            logger = logging.getLogger(__name__)
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
                                provider=provider, notifier=self.notifier
                            )
        
                            # Set transcription service on event handler
                            self._recording_event_handler.set_transcription_service(self.transcription_service)
        
                            # Update initial provider badge
                            display = self.query_one(
                                "#transcription-display", TranscriptionDisplay
                            )
                            display.provider = provider_type
        
                            # Perform startup health check (only for local, or minimal for Groq)
                            alive, error = self.transcription_service.check_health()
                            if alive:
                                self.notify(
                                    f"Transcription ready ({provider_type.title()})",
                                    severity="information",
                                    timeout=3,
                                )
                            else:
                                logger = logging.getLogger(__name__)
                                logger.warning(
                                    f"Transcription backend health check failed: {error}"
                                )
                                self.notify(
                                    f"Transcription host offline: {error}",
                                    severity="warning",
                                    timeout=10,
                                )
        
                                # Set initial UI status to error/offline
                                display.status = "error"
        
                        except Exception as e:
                            self.transcription_service = None
                            self.notify(f"Transcription init failed: {e}", severity="warning")
        
                    # Initialize and register D-Bus service (skip in tests)
                    import os
                    if "PYTEST_CURRENT_TEST" not in os.environ:
                        try:
                            self.dbus_service = DBusService(self)
                            # Register D-Bus service
                            await self.dbus_service.register()
                            logger = logging.getLogger(__name__)
                            logger.info("D-Bus service registered successfully")
                        except Exception as e:
                            logger = logging.getLogger(__name__)
                            logger.warning(f"D-Bus service registration failed: {e}")
                            self.dbus_service = None
                    
                    # Performance Optimization: Reduced UI refresh rates
                    self.set_interval(0.1, self.update_meters) # 10Hz for meters (was 20Hz)
                    self.set_interval(
                        0.2, self.check_auto_triggers
                    )  # 5Hz for auto-record logic
                    
                    # Throttle slow-changing info (once per second)
                    self.set_interval(1.0, self.update_slow_info)
                except Exception as e:
                    self.exit(message=f"Failed to start: {e}")
        
            async def on_unmount(self) -> None:
                """Async cleanup during app shutdown - Textual awaits this automatically."""
                logger = logging.getLogger(__name__)
                logger.info("=== SHUTDOWN SEQUENCE STARTING ===")
        
                # Emergency deadline: 60 seconds total (data integrity priority)
                shutdown_deadline = time.time() + 60.0
        
                # 1. Stop hotkey listener
                if self.hotkey_listener:
                    try:
                        self.hotkey_listener.stop()
                        logger.info("Hotkey listener stopped")
                    except Exception as e:
                        logger.error(f"Hotkey stop error: {e}")
        
                # 2. Stop D-Bus service (properly awaited)
                if self.dbus_service and self.dbus_service.is_registered():
                    try:
                        await self.dbus_service.unregister()
                        logger.info("D-Bus service stopped")
                    except Exception as e:
                        logger.error(f"D-Bus service stop error: {e}")
                # 3. Stop audio engine
                if hasattr(self, "engine"):
                    try:
                        if self.engine.is_recording:
                            logger.info("Stopping active recording...")
                            self.engine.stop_recording()
                        self.engine.stop()
                        logger.info("Audio engine stopped")
                    except Exception as e:
                        logger.error(f"Audio engine error: {e}")
        
                # Check deadline before transcription
                if time.time() > shutdown_deadline:
                    logger.critical(
                        "EMERGENCY SHUTDOWN: Deadline exceeded before transcription"
                    )
                    return
        
                # 4. Shutdown transcription service
                if hasattr(self, "transcription_service") and self.transcription_service:
                    try:
                        active = len(
                            [
                                t
                                for t in self.transcription_service.active_threads
                                if t.is_alive()
                            ]
                        )
                        logger.info(f"Shutting down transcription ({active} active threads)")
        
                        # Give more time for transcription (data integrity priority)
                        remaining_time = max(5.0, shutdown_deadline - time.time())
                        self.transcription_service.shutdown(timeout=min(remaining_time, 30.0))
        
                        # Check for orphaned threads
                        orphaned = [
                            t for t in self.transcription_service.active_threads if t.is_alive()
                        ]
                        if orphaned:
                            logger.warning(f"Orphaned threads: {[t.name for t in orphaned]}")
                            logger.warning("Transcriptions may continue in background")
                    except Exception as e:
                        logger.error(f"Transcription shutdown error: {e}")
        
                # 4. Session cleanup
                if hasattr(self, "session_manager"):
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
        
        
                total_time = time.time() - (shutdown_deadline - 60.0)
                logger.info(f"=== SHUTDOWN COMPLETE: {total_time:.2f}s ===")
        
            def update_meters(self):
                """Update VU meters (called at 10Hz)."""
                try:
                    peaks, dbs = self.engine.get_peak_meters()
                    meter_1 = self.query_one("#meter-1", VUMeter)
                    # Use atomic update to avoid double layout trigger
                    meter_1.update_levels(peaks[0], dbs[0])
        
                    if len(peaks) > 1 and self.engine.channels > 1:
                        meter_2 = self.query_one("#meter-2", VUMeter)
                        meter_2.update_levels(peaks[1], dbs[1])
                except NoMatches:
                    pass
        
            def update_slow_info(self):
                """Update slow-changing UI elements (called at 1Hz)."""
                try:
                    from .recording_controller import RecordingState
                    state = self.recording_controller.get_state()
                    if state == RecordingState.ARMED:
                        # Show armed status when monitoring
                        fill_pct = (self.engine.write_ptr / self.engine.ring_size) * 100
                        if self.engine.buffer_filled:
                            fill_pct = 100
                        self.query_one("#buffer-info").update(
                            f"[green]ARMED[/green] - Buffer: {fill_pct:.1f}%"
                        )
                    elif not self.recording_controller.is_recording():
                        # Show normal buffer fill when idle
                        fill_pct = (self.engine.write_ptr / self.engine.ring_size) * 100
                        if self.engine.buffer_filled:
                            fill_pct = 100
                        self.query_one("#buffer-info").update(
                            f"Pre-Record Buffer: {fill_pct:.1f}%"
                        )
                except NoMatches:
                    pass
        
            def check_auto_triggers(self):
                """Periodically check for auto-record triggers and silence detection."""
                if not hasattr(self, "recording_controller"):
                    return
        
                # Get current signal metrics (calculated in JACK callback, respects sustain logic)
                signal_metrics = self.engine.last_signal_metrics
        
                # Let controller handle state transitions
                self.recording_controller.check_auto_triggers(signal_metrics)
        
            def _update_meter_visibility(self):
                is_stereo = self.engine.channels == 2
                self.query_one("#label-2").display = is_stereo
                self.query_one("#meter-2").display = is_stereo
                self.query_one("#label-1").update(
                    "Channel 1" if is_stereo else "Channel (Mono)"
                )
        
            def _load_and_connect_saved_inputs(self):
                saved_ports = self.config_manager.get_input_ports()
                if not saved_ports:
                    self.query_one("#connection-status").update(
                        "Inputs: [yellow]Not configured[/yellow]"
                    )
                    return
        
                valid, missing = self.config_manager.validate_ports_exist(self.engine.client)
                if not valid:
                    self.query_one("#connection-status").update(
                        "Inputs: [red]Invalid config[/red]"
                    )
                    return
        
                if self.engine.connect_inputs(saved_ports):
                    self._update_connection_status(saved_ports)
        
            def _update_connection_status(self, ports: list[str]):
                short_names = [p.split(":")[-1] if ":" in p else p for p in ports]
                txt = f"Inputs: [green]{' | '.join(short_names)}[/green]"
                self.query_one("#connection-status").update(txt)
        
            def _update_session_status(self):
                if not hasattr(self, "session_manager"):
                    return
        
                session = self.session_manager.get_current_session()
                if not session:
                    self.query_one("#session-status").update("Session: None")
                    return
        
                info = session.get_info()
                status = "[green]Saved[/green]" if info["saved"] else "[yellow]Unsaved[/yellow]"
                count = info["recording_count"]
        
                if count == 0:
                    text = f"Session: New ({status})"
                else:
                    text = f"Session: {count} recording(s) - {status}"
        
                self.query_one("#session-status").update(text)
        
            # --- Recording Event Callbacks (UI updates) ---
            # These are called by RecordingEventHandler via RecordingEventCallbacks
        
            def _on_recording_started(self, path: Path, mode: str) -> None:
                """UI callback: recording started (auto or manual)."""
                try:
                    status_bar = self.query_one("#status-bar")
                    countdown_widget = self.query_one("#silence-countdown", SilenceCountdown)
                except NoMatches:
                    return
        
                filename = path.name if path else "unknown"
                if mode == "auto":
                    status_bar.update(f"[yellow]AUTO-REC[/yellow]... \nFile: {filename}")
                else:
                    status_bar.update(f"RECORDING... \nFile: {filename}")
                status_bar.remove_class("status-idle").add_class("status-recording")
                self._current_recording_path = path
                countdown_widget.visible = False
        
            def _on_recording_stopped(self, path: Optional[Path]) -> None:
                """UI callback: recording stopped (auto or manual)."""
                try:
                    status_bar = self.query_one("#status-bar")
                    countdown_widget = self.query_one("#silence-countdown", SilenceCountdown)
                except NoMatches:
                    return
        
                countdown_widget.visible = False
        
                # Update status bar based on current controller state
                if self.recording_controller.get_state() == RecordingState.ARMED:
                    status_bar.update("[green]ARMED[/green] - Monitoring for signal")
                else:
                    status_bar.update("IDLE - Recording saved to session.")
                status_bar.remove_class("status-recording").add_class("status-idle")
        
            def _on_silence_countdown(self, remaining: float) -> None:
                """UI callback: silence countdown during recording."""
                try:
                    countdown_widget = self.query_one("#silence-countdown", SilenceCountdown)
                except NoMatches:
                    return
        
                countdown_widget.countdown = remaining
                countdown_widget.visible = True
        
            def _on_state_changed(self, old_state: str, new_state: str) -> None:
                """UI callback: recording state changed."""
                try:
                    status_bar = self.query_one("#status-bar")
                except NoMatches:
                    return
        
                if new_state == "armed":
                    status_bar.update("[green]ARMED[/green] - Monitoring for signal")
                    status_bar.remove_class("status-recording").add_class("status-idle")
                elif new_state == "idle":
                    status_bar.update("IDLE - Ready to Capture")
                    status_bar.remove_class("status-recording").add_class("status-idle")
        
            # --- Delegation to RecordingEventHandler ---
            # The old _handle_recording_event and _register_and_transcribe_recording
            # are now handled by RecordingEventHandler. These methods remain for
            # any external callers that might reference them directly.
        
            def _handle_recording_event(self, event: RecordingEvent, data: dict) -> None:
                """Delegate to RecordingEventHandler (kept for backward compatibility)."""
                if hasattr(self, "_recording_event_handler"):
                    self._recording_event_handler.handle_event(event, data)
        
            def _register_and_transcribe_recording(self, path: Path) -> None:
                """Delegate to RecordingEventHandler (kept for backward compatibility)."""
                if hasattr(self, "_recording_event_handler"):
                    self._recording_event_handler.register_and_transcribe(path)
        
            def watch_auto_record_enabled(self, value: bool) -> None:
                if hasattr(self, "recording_controller"):
                    if value:
                        success = self.recording_controller.enable_auto_record()
                        if success:
                            self.notify(
                                "Auto-record mode enabled", severity="information", timeout=2
                            )
                        else:
                            self.auto_record_enabled = False
                            self.notify(
                                "Cannot enable auto-record while recording",
                                severity="warning",
                                timeout=3,
                            )
                    else:
                        self.recording_controller.disable_auto_record()
                        self.notify(
                            "Auto-record mode disabled", severity="information", timeout=2
                        )
                if hasattr(self, "config_manager"):
                    self.config_manager.set_auto_record_enabled(value)
        
            def watch_copy_to_clipboard(self, value: bool) -> None:
                if hasattr(self, "config_manager"):
                    self.config_manager.set_copy_to_clipboard(value)
                    status = "enabled" if value else "disabled"
                    self.notify(f"Clipboard copy {status}", severity="information", timeout=2)
        
                    # Mutual exclusivity: disable daily note when copy/inject is enabled
                    if value and self.write_to_daily_note:
                        self.write_to_daily_note = False
        
            def watch_inject_to_active_window(self, value: bool) -> None:
                if hasattr(self, "config_manager"):
                    self.config_manager.set_inject_to_active_window(value)
                    status = "enabled" if value else "disabled"
                    self.notify(f"Text injection {status}", severity="information", timeout=2)
        
                    # Mutual exclusivity: disable daily note when copy/inject is enabled
                    if value and self.write_to_daily_note:
                        self.write_to_daily_note = False
        
            def watch_write_to_daily_note(self, value: bool) -> None:
                if hasattr(self, "config_manager"):
                    self.config_manager.set_write_to_daily_note(value)
                    status = "enabled" if value else "disabled"
                    self.notify(f"Daily note writing {status}", severity="information", timeout=2)
        
                    # Mutual exclusivity: disable copy/inject when daily note is enabled
                    if value:
                        if self.copy_to_clipboard:
                            self.copy_to_clipboard = False
                        if self.inject_to_active_window:
                            self.inject_to_active_window = False
        
            def action_toggle_record(self) -> None:
                """Toggle recording on/off (manual control)."""
                if self.recording_controller.is_recording():
                    # Stop recording via controller
                    self.recording_controller.manual_stop_recording()
                    self._update_meter_visibility()
                else:
                    # Check for audio activity before starting
                    if not self.engine.has_audio_activity():
                        msg = (
                            "No audio activity or connections detected.\n\n"
                            "Please check:\n"
                            "1. JACK/PipeWire connections (using QjackCtl or Helvum)\n"
                            "2. Microphone mute status\n"
                            "3. Input port configuration in OMEGA-13 (Press 'I')"
                        )
                        if self.notifier:
                            self.notifier.notify("Capture Blocked", msg, urgency="critical")
        
                        self.notify(msg, severity="error", timeout=10)
                        status_bar = self.query_one("#status-bar")
                        status_bar.update("CAPTURE BLOCKED - No Input Signal")
                        return
        
                    # Start recording via controller
                    session = self.session_manager.get_current_session()
                    if not session:
                        self.notify("No active session", severity="error")
                        return
        
                    recording_path = session.get_next_recording_path()
                    success = self.recording_controller.manual_start_recording(recording_path)
                    self._update_meter_visibility()
        
                    if not success:
                        self.notify("Failed to start recording", severity="error")
        
            def _get_last_recording_path(self) -> Optional[Path]:
                if hasattr(self, "_current_recording_path"):
                    return self._current_recording_path
                return None
        
            async def get_health_status(self) -> dict:
                """Return D-Bus health payload for the running TUI instance."""
                transcription = {
                    "available": False,
                    "provider": None,
                }
                if hasattr(self, "transcription_service") and self.transcription_service is not None:
                    try:
                        provider_type = getattr(
                            getattr(self, "config_manager", None),
                            "get_transcription_provider",
                            lambda: None,
                        )()
                        transcription["available"] = True
                        transcription["provider"] = provider_type
                    except Exception:
                        pass
        
                return {
                    "state": self.recording_controller.get_state().value,
                    "is_recording": self.recording_controller.is_recording(),
                    "auto_record_enabled": self.recording_controller.is_auto_record_enabled(),
                    "audio": {
                        "connected": self.engine.client is not None,
                        "sample_rate": self.engine.samplerate if self.engine.client else 0,
                        "channels": self.engine.channels if self.engine.client else 0,
                        "has_activity": self.engine.has_audio_activity(),
                        "is_recording": self.engine.is_recording if self.engine.client else False,
                    },
                    "session": {
                        "active": self.session_manager.current_session is not None,
                        "session_id": self.session_manager.current_session.session_id if self.session_manager.current_session else None,
                        "recording_count": len(self.session_manager.current_session.recordings) if self.session_manager.current_session else 0,
                        "saved": self.session_manager.current_session.saved if self.session_manager.current_session else True,
                    },
                    "transcription": transcription,
                }
        
            def _start_transcription(self, audio_file: Path):
                if not self.transcription_service:
                    # Re-instantiate service if needed
                    provider_type = self.config_manager.get_transcription_provider()
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
                        provider=provider, notifier=self.notifier
                    )
                    # Pass the newly created service to the event handler
                    if hasattr(self, "_recording_event_handler"):
                        self._recording_event_handler.set_transcription_service(self.transcription_service)
        
                display = self.query_one("#transcription-display", TranscriptionDisplay)
                display.status = "processing"
                display.progress = 0.0
                display.provider = self.config_manager.get_transcription_provider()
        
                def on_complete(result):
                    self.call_from_thread(self._handle_result, result, audio_file)
        
                def on_progress(p):
                    self.call_from_thread(lambda: setattr(display, "progress", p))
        
                def on_clipboard_error(error_msg):
                    self.call_from_thread(self._handle_clipboard_error, error_msg)
        
                def on_injection_error(error_msg):
                    self.call_from_thread(self._handle_injection_error, error_msg)
        
                def on_daily_note_error(error_msg):
                    self.call_from_thread(self._handle_daily_note_error, error_msg)
        
                copy_enabled = self.config_manager.get_copy_to_clipboard()
                inject_enabled = self.config_manager.get_inject_to_active_window()
        
                self.transcription_service.transcribe_async(
                    audio_file,
                    on_complete,
                    on_progress,
                    copy_to_clipboard_enabled=self.copy_to_clipboard,  # Use reactive state
                    clipboard_error_callback=on_clipboard_error,
                    inject_to_active_window_enabled=self.inject_to_active_window,  # Use reactive state
                    injection_error_callback=on_injection_error,
                    write_to_daily_note_enabled=self.write_to_daily_note,  # Use reactive state
                    daily_note_error_callback=on_daily_note_error,
                )
        
            def action_toggle_auto_record(self) -> None:
                """Toggle auto-record mode."""
                self.auto_record_enabled = not self.auto_record_enabled
        
            def action_toggle_clipboard(self) -> None:
                """Toggle clipboard copy."""
                self.copy_to_clipboard = not self.copy_to_clipboard
        
            def action_toggle_injection(self) -> None:
                """Toggle text injection."""
                self.inject_to_active_window = not self.inject_to_active_window
        
            def action_toggle_daily_note(self) -> None:
                """Toggle daily note writing."""
                self.write_to_daily_note = not self.write_to_daily_note
        
            def _handle_result(self, result, audio_file):
                display = self.query_one("#transcription-display", TranscriptionDisplay)
                if result.status == TranscriptionStatus.COMPLETED:
                    session = self.session_manager.get_current_session()
                    if session:
                        session.add_transcription(result.text)
                        display.update_buffer(session.transcriptions)
                    else:
                        display.update_text(result.text)
                    display.status = "completed"
                else:
                    display.show_error(result.error or "Unknown error")

            def _safe_update(self, update_fn):
                try:
                    self.call_from_thread(update_fn)
                except RuntimeError as e:
                    if "different thread" in str(e):
                        update_fn()
                    else:
                        raise

            def _handle_result_from_event(self, result, audio_file):
                def update():
                    display = self.query_one("#transcription-display", TranscriptionDisplay)
                    if getattr(result, "status", None) and (result.status.name == "COMPLETED" or getattr(result.status, "value", result.status) == "completed" or str(result.status) == "TranscriptionStatus.COMPLETED"):
                        session = self.session_manager.get_current_session()
                        if session:
                            # It's already added to session by RecordingEventHandler, just update display
                            display.update_buffer(session.transcriptions)
                        else:
                            display.update_text(result.text)
                        display.status = "completed"
                    else:
                        display.show_error(getattr(result, "error", "Unknown error"))
                self._safe_update(update)

            def _handle_transcription_started_from_event(self, path: Path):
                def update():
                    display = self.query_one("#transcription-display", TranscriptionDisplay)
                    display.status = "processing"
                    display.progress = 0.0
                    display.provider = self.config_manager.get_transcription_provider()
                self._safe_update(update)

            def _handle_transcription_progress_from_event(self, progress: float):
                def update():
                    display = self.query_one("#transcription-display", TranscriptionDisplay)
                    display.progress = progress
                self._safe_update(update)
        
            def _handle_clipboard_error(self, error_msg: str):
                self.notify(
                    f"Clipboard copy failed: {error_msg}", severity="warning", timeout=4
                )
        
            def _handle_injection_error(self, error_msg: str):
                self.notify(
                    f"Text injection failed: {error_msg}", severity="warning", timeout=4
                )
        
            def _handle_daily_note_error(self, error_msg: str):
                self.notify(
                    f"Daily note writing failed: {error_msg}", severity="warning", timeout=4
                )
        
            def action_manual_transcribe(self):
                if last := self._get_last_recording_path():
                    self._start_transcription(last)
                else:
                    self.notify("No recording to transcribe", severity="warning")
        
            def action_open_settings(self):
                """Open transcription settings modal."""
                current_config = {
                    "provider": self.config_manager.get_transcription_provider(),
                    "server_url": self.config_manager.get_transcription_server_url(),
                    "inference_path": self.config_manager.get_transcription_inference_path(),
                    "groq_model": self.config_manager.get_groq_model(),
                }
        
                def handle_settings(result):
                    if not result:
                        return
        
                    # Save all to config
                    self.config_manager.set_transcription_provider(result["provider"])
                    self.config_manager.set_transcription_server_url(result["server_url"])
                    self.config_manager.set_transcription_inference_path(
                        result["inference_path"]
                    )
                    self.config_manager.set_groq_model(result["groq_model"])
        
                    # Update transcription service
                    if TRANSCRIPTION_AVAILABLE:
                        provider_type = result["provider"]
                        if provider_type == "groq":
                            provider = GroqTranscriptionProvider(
                                api_key=self.config_manager.get_groq_api_key(),
                                model=result["groq_model"],
                            )
                        else:
                            provider = LocalTranscriptionProvider(
                                server_url=result["server_url"],
                                inference_path=result["inference_path"],
                            )
        
                        self.transcription_service = TranscriptionService(
                            provider=provider, notifier=self.notifier
                        )
        
                        # Update UI badge
                        display = self.query_one("#transcription-display", TranscriptionDisplay)
                        display.provider = provider_type
        
                        # Check health of new configuration
                        alive, error = self.transcription_service.check_health()
                        if alive:
                            self.notify(
                                f"Settings saved. {provider_type.title()} service ready.",
                                severity="information",
                            )
                            # Clear error status if it was set
                            if display.status == "error":
                                display.status = "idle"
                        else:
                            self.notify(
                                f"Settings saved, but service offline: {error}",
                                severity="warning",
                                timeout=10,
                            )
                            display.status = "error"
        
                self.push_screen(TranscriptionSettingsScreen(current_config), handle_settings)
        
            def action_open_input_selector(self):
                if self.engine.is_recording:
                    self.notify("Cannot change inputs while recording", severity="warning")
                    return
        
                try:
                    available = self.engine.get_available_output_ports()
                    current = self.engine.get_current_connections()
        
                    def handle(result):
                        if not result:
                            return
                        if len(result) != self.engine.channels:
                            self.engine.stop()
                            self.engine = AudioEngine(
                                config_manager=self.config_manager, num_channels=len(result)
                            )
                            self.engine.start()
                            self._update_meter_visibility()
                        else:
                            self.engine.disconnect_inputs()
        
                        self.engine.connect_inputs(result)
                        self.config_manager.set_input_ports(result)
                        self._update_connection_status(result)
        
                    self.push_screen(InputSelectionScreen(available, current), handle)
                except Exception as e:
                    self.notify(str(e), severity="error")
        
            def action_save_session(self):
                if self.engine.is_recording:
                    self.notify("Stop recording before saving session", severity="warning")
                    return
        
                session = self.session_manager.get_current_session()
                if not session or len(session.recordings) == 0:
                    self.notify("No recordings to save in this session", severity="warning")
                    return
        
                if session.saved and session.save_location:
                    parent_dir = session.save_location.parent
                    success = self.session_manager.save_session(parent_dir)
                    if success:
                        self._update_session_status()
                        self.notify(
                            f"Session snapshot updated: {session.save_location.name}",
                            severity="information",
                            timeout=5,
                        )
                    else:
                        self.notify("Failed to update session snapshot", severity="error")
                    return
        
                def handle_directory(location):
                    if location:
        
                        def handle_title(title: Optional[str]):
                            if title is not None:  # title could be empty string for "Skip"
                                success = self.session_manager.save_session(
                                    location, title=title
                                )
                                if success:
                                    self._update_session_status()
                                    save_loc = session.save_location
                                    self.notify(
                                        f"Session saved to: {save_loc}",
                                        severity="information",
                                        timeout=5,
                                    )
                                else:
                                    self.notify("Failed to save session", severity="error")
        
                        self.push_screen(SessionTitleScreen(), handle_title)
        
                default_location = self.config_manager.get_default_save_location()
                self.push_screen(DirectorySelectionScreen(default_location), handle_directory)
        
            def action_new_session(self):
                if self.engine.is_recording:
                    self.notify(
                        "Stop recording before starting a new session", severity="warning"
                    )
                    return
        
                session = self.session_manager.get_current_session()
                if session and not session.saved and len(session.recordings) > 0:
                    self._prompt_new_session_confirmation()
                    return
        
                self._start_new_session()
        
            def _start_new_session(self):
                self.session_manager.create_session()
                self._update_session_status()
        
                display = self.query_one("#transcription-display", TranscriptionDisplay)
                display.clear()
        
                self.notify("New session started", severity="information")
        
            def _prompt_new_session_confirmation(self):
                from textual.screen import ModalScreen
                from textual.widgets import Button
                from textual.containers import Grid
        
                class NewSessionPromptScreen(ModalScreen):
                    CSS = """
                    NewSessionPromptScreen { align: center middle; }
                    #dialog { width: 60; height: 16; border: thick $accent; background: $surface; padding: 2; }
                    #question { width: 100%; height: 3; content-align: center middle; text-style: bold; }
                    #message { width: 100%; height: 3; content-align: center middle; color: $text-muted; }
                    #button-row { width: 100%; height: 3; align: center middle; margin-top: 1; }
                    Button { width: 14; margin: 0 1; }
                    """
        
                    def __init__(self, session_manager):
                        super().__init__()
                        self.session_manager = session_manager
        
                    def compose(self) -> ComposeResult:
                        session = self.session_manager.get_current_session()
                        count = len(session.recordings) if session else 0
                        with Container(id="dialog"):
                            yield Static("Start New Session?", id="question")
                            yield Static(
                                f"Current session has {count} unsaved recording(s)",
                                id="message",
                            )
                            with Horizontal(id="button-row"):
                                yield Button("Save & New", variant="primary", id="save")
                                yield Button("Discard", variant="error", id="discard")
                                yield Button("Cancel", id="cancel")
        
                    def on_button_pressed(self, event: Button.Pressed) -> None:
                        self.dismiss(event.button.id)
        
                def handle_choice(choice: str):
                    if choice == "cancel":
                        return
                    if choice == "discard":
                        self.session_manager.discard_session()
                        self._start_new_session()
                        return
                    if choice == "save":
        
                        def handle_save_location(location):
                            if location:
        
                                def handle_title(title: Optional[str]):
                                    if title is not None:
                                        success = self.session_manager.save_session(
                                            location, title=title
                                        )
                                        if success:
                                            self.notify(
                                                "Session saved successfully",
                                                severity="information",
                                            )
                                            self._start_new_session()
                                        else:
                                            self.notify(
                                                "Failed to save session", severity="error"
                                            )
        
                                self.push_screen(SessionTitleScreen(), handle_title)
        
                        default_location = self.config_manager.get_default_save_location()
                        self.push_screen(
                            DirectorySelectionScreen(default_location), handle_save_location
                        )
        
                self.push_screen(NewSessionPromptScreen(self.session_manager), handle_choice)
        
            def action_quit(self) -> None:
                if hasattr(self, "session_manager"):
                    if (
                        not self.session_manager.is_saved()
                        and self.session_manager.has_recordings()
                    ):
                        self._prompt_save_before_quit()
                        return
                self.exit()
        
            def _prompt_save_before_quit(self):
                from textual.screen import ModalScreen
                from textual.widgets import Button
                from textual.containers import Grid
        
                class SavePromptScreen(ModalScreen):
                    CSS = """
                    SavePromptScreen { align: center middle; }
                    #dialog { width: 60; height: 16; border: thick $accent; background: $surface; padding: 2; }
                    #question { width: 100%; height: 3; content-align: center middle; text-style: bold; }
                    #message { width: 100%; height: 3; content-align: center middle; color: $text-muted; }
                    #button-row { width: 100%; height: 3; align: center middle; margin-top: 1; }
                    Button { width: 14; margin: 0 1; }
                    """
        
                    def __init__(self, session_manager, config_manager):
                        super().__init__()
                        self.session_manager = session_manager
                        self.config_manager = config_manager
        
                    def compose(self) -> ComposeResult:
                        session = self.session_manager.get_current_session()
                        count = len(session.recordings) if session else 0
                        with Container(id="dialog"):
                            yield Static("Save Session Before Quitting?", id="question")
                            yield Static(f"You have {count} unsaved recording(s)", id="message")
                            with Horizontal(id="button-row"):
                                yield Button("Save", variant="primary", id="save")
                                yield Button("Discard", variant="error", id="discard")
                                yield Button("Cancel", id="cancel")
        
                    def on_button_pressed(self, event: Button.Pressed) -> None:
                        self.dismiss(event.button.id)
        
                def handle_choice(choice: str):
                    if choice == "cancel":
                        return
                    if choice == "discard":
                        self.session_manager.discard_session()
                        self.exit()
                        return
                    if choice == "save":
        
                        def handle_save_location(location):
                            if location:
        
                                def handle_title(title: Optional[str]):
                                    if title is not None:
                                        success = self.session_manager.save_session(
                                            location, title=title
                                        )
                                        if success:
                                            self.notify(
                                                "Session saved successfully",
                                                severity="information",
                                            )
                                        else:
                                            self.notify(
                                                "Failed to save session", severity="error"
                                            )
                                    self.exit()
        
                                self.push_screen(SessionTitleScreen(), handle_title)
        
                        default_location = self.config_manager.get_default_save_location()
                        self.push_screen(
                            DirectorySelectionScreen(default_location), handle_save_location
                        )
        
                self.push_screen(
                    SavePromptScreen(self.session_manager, self.config_manager), handle_choice
                )
        

        from .pidfile import PidFile, PidFileError
        if args.daemon:
            try:
                pf = PidFile(Path("/tmp/omega13.pid"))
                with pf:
                    app = Omega13App()
                    app.run()
            except PidFileError as e:
                print(f"Error: {e}")
                sys.exit(1)
        else:
            app = Omega13App()
            app.run()
    elif args.daemon:
        # Default: background daemon, headless mode
        _daemonize()
        from .pidfile import PidFile, PidFileError
        pf = None
        try:
            pf = PidFile(Path("/tmp/omega13.pid"))
            pf.acquire()
        except PidFileError as e:
            logging.getLogger(__name__).warning(f"PID file creation failed: {e}")
        from .headless_service import run_headless
        try:
            asyncio.run(run_headless())
        finally:
            if pf is not None:
                pf.release()
    else:
        # Foreground headless
        from .pidfile import PidFile, PidFileError
        pf = None
        try:
            pf = PidFile(Path("/tmp/omega13.pid"))
            pf.acquire()
        except PidFileError as e:
            logging.getLogger(__name__).warning(f"PID file creation failed: {e}")
        from .headless_service import run_headless
        try:
            asyncio.run(run_headless())
        finally:
            if pf is not None:
                pf.release()


def main_daemon():
    """Synchronous entry point for daemon mode."""
    configure_logging()
    _daemonize()
    from .pidfile import PidFile, PidFileError
    pf = None
    try:
        pf = PidFile(Path("/tmp/omega13.pid"))
        pf.acquire()
    except PidFileError as e:
        logging.getLogger(__name__).warning(f"PID file creation failed: {e}")
    from .headless_service import run_headless
    try:
        asyncio.run(run_headless())
    finally:
        if pf is not None:
            pf.release()

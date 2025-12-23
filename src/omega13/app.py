import logging
import signal
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Label, Static, Checkbox

# Import refactored modules
from .config import ConfigManager
from .audio import AudioEngine, DEFAULT_CHANNELS
from .ui import VUMeter, TranscriptionDisplay, InputSelectionScreen, DirectorySelectionScreen
from .session import SessionManager

# Optional import for transcription
try:
    from .transcription import TranscriptionService, TranscriptionStatus, TranscriptionResult
    TRANSCRIPTION_AVAILABLE = True
except ImportError:
    TRANSCRIPTION_AVAILABLE = False

class Omega13App(App):
    CSS = """
    Screen { align: center middle; background: $surface; }
    #app-layout { width: 100%; height: 100%; }
    
    #left-pane { width: 40%; height: 100%; border: solid $accent; margin-right: 1; }
    #audio-controls { height: 75%; padding: 1 2; background: $surface-lighten-1; border-bottom: solid $accent; }
    #transcription-controls { height: 25%; padding: 1 2; background: $surface-darken-1; }
    
    #transcription-pane { width: 60%; height: 100%; border: solid $accent; padding: 1 2; background: $surface-lighten-1; }
    
    .title { text-align: center; text-style: bold; margin-bottom: 1; }
    .status-idle { color: $text; background: $success; padding: 1; text-align: center; text-style: bold; }
    .status-recording { color: $text; background: $error; padding: 1; text-align: center; text-style: bold; }
    #connection-status, #path-status, #buffer-info { text-align: center; padding: 0 1; margin-top: 1; }
    #connection-status { border: solid $primary; background: $surface-darken-1; }
    #meters { height: 5; margin-top: 1; border: heavy $primary; }
    .help-text { text-align: center; width: 100%; margin-top: 1; }
    Label { width: 100%; }
    
    /* UI Imports CSS */
    .transcription-title { text-align: center; text-style: bold; margin-bottom: 1; color: $accent; }
    #transcription-status { text-align: center; padding: 1; margin-bottom: 1; border: solid $primary; }
    .status-loading, .status-processing { color: $text; background: $warning; }
    .status-complete { color: $text; background: $success; }
    .status-error { color: $text; background: $error; }
    #clipboard-toggle { margin-bottom: 1; padding: 0 1; }
    #transcription-log { height: 1fr; border: solid $primary; background: $surface-darken-1; padding: 1; }
    """

    BINDINGS = [
        Binding("space", "toggle_record", "Record/Stop", priority=True),
        Binding("i", "open_input_selector", "Select Inputs"),
        Binding("s", "save_session", "Save Session"),
        Binding("t", "manual_transcribe", "Transcribe"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown_initiated = False
        self._signal_handlers_registered = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="app-layout"):
            with Vertical(id="left-pane"):
                with Vertical(id="audio-controls"):
                    yield Label("OMEGA-13", classes="title")
                    yield Static("IDLE - Ready to Capture", id="status-bar", classes="status-idle")
                    yield Static("Session: New (Unsaved)", id="session-status")
                    yield Static("Inputs: Loading...", id="connection-status")
                    yield Static("\nBuffers filled: ", id="buffer-info")
                    with Vertical(id="meters"):
                        yield Label("Channel 1", id="label-1")
                        yield VUMeter(id="meter-1")
                        yield Label("Channel 2", id="label-2")
                        yield VUMeter(id="meter-2")
                    yield Static("\n[dim]SPACE Capture | I Inputs | S Save | T Transcribe[/dim]", classes="help-text")

                with Vertical(id="transcription-controls"):
                    yield Label("Transcription Status", classes="transcription-title")
                    yield Static("Ready", id="transcription-status", classes="status-idle")
                    yield Checkbox("Copy to clipboard", id="clipboard-toggle", classes="clipboard-checkbox")

            with Container(id="transcription-pane"):
                # Note: config_manager will be set after on_mount
                yield TranscriptionDisplay(id="transcription-display")
        yield Footer()

    def _register_signal_handlers(self) -> None:
        """Register handlers for graceful shutdown on signals."""
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            logger = logging.getLogger(__name__)
            logger.info(f"Received signal {signal_name}, initiating graceful shutdown")

            # Prevent multiple shutdown attempts
            if self._shutdown_initiated:
                logger.warning("Shutdown already in progress")
                return

            self._shutdown_initiated = True

            # Post exit to main event loop (thread-safe)
            self.call_from_thread(self._graceful_shutdown)

        # Register for common termination signals
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger = logging.getLogger(__name__)
        logger.debug("Signal handlers registered")

    def _graceful_shutdown(self) -> None:
        """Perform graceful shutdown from signal handler."""
        logger = logging.getLogger(__name__)
        logger.info("Starting graceful shutdown sequence")

        # Skip save prompt if shutdown via signal
        # User pressed Ctrl+C, they want to quit NOW
        if hasattr(self, 'session_manager'):
            if not self.session_manager.is_saved() and self.session_manager.has_recordings():
                logger.info("Discarding unsaved session due to signal termination")
                self.session_manager.discard_session()

        # Exit without further prompts
        self.exit()

    def on_mount(self):
        # Register signal handlers AFTER Textual is ready
        if not self._signal_handlers_registered:
            self._register_signal_handlers()
            self._signal_handlers_registered = True

        try:
            self.config_manager = ConfigManager()

            # Pass config_manager to TranscriptionDisplay widget
            transcription_display = self.query_one("#transcription-display", TranscriptionDisplay)
            transcription_display.config_manager = self.config_manager
            # Re-initialize checkbox state now that config_manager is available
            if transcription_display.clipboard_checkbox:
                initial_state = self.config_manager.get_copy_to_clipboard()
                transcription_display.clipboard_checkbox.value = initial_state

            # Initialize session manager
            temp_root = self.config_manager.get_session_temp_root()
            self.session_manager = SessionManager(temp_root=temp_root)
            self.session_manager.create_session()
            self._update_session_status()

            # Cleanup old sessions
            days = self.config_manager.get_auto_cleanup_days()
            cleaned = self.session_manager.cleanup_old_sessions(days)
            if cleaned > 0:
                self.notify(f"Cleaned up {cleaned} old session(s)", severity="information", timeout=2)

            saved_ports = self.config_manager.get_input_ports()
            num_channels = len(saved_ports) if saved_ports else DEFAULT_CHANNELS

            self.engine = AudioEngine(config_manager=self.config_manager, num_channels=num_channels)
            self.engine.start()

            self._load_and_connect_saved_inputs()
            self._update_meter_visibility()

            if TRANSCRIPTION_AVAILABLE:
                try:
                    self.transcription_service = TranscriptionService()
                    self.notify("Transcription ready (API)", severity="information", timeout=3)
                except Exception as e:
                    self.transcription_service = None
                    self.notify(f"Transcription init failed: {e}", severity="warning")

            self.set_interval(0.05, self.update_meters)
        except Exception as e:
            self.exit(message=f"Failed to start: {e}")

    def on_unmount(self):
        """Cleanup resources in correct order."""
        logger = logging.getLogger(__name__)
        logger.info("Application unmounting, cleaning up resources")

        # Step 1: Cancel interval timers FIRST to prevent callbacks during teardown
        try:
            # Textual automatically cancels timers, but be explicit
            logger.debug("Canceling interval timers")
        except Exception as e:
            logger.error(f"Error canceling timers: {e}")

        # Step 2: Stop recording and audio engine
        if hasattr(self, 'engine'):
            try:
                logger.debug("Stopping audio engine")
                if self.engine.is_recording:
                    logger.debug("Stopping active recording")
                    self.engine.stop_recording()  # Now has timeout
                self.engine.stop()  # Deactivate JACK client
                logger.debug("Audio engine stopped")
            except Exception as e:
                logger.error(f"Error stopping audio engine: {e}")

        # Step 3: Stop transcription service
        if hasattr(self, 'transcription_service') and self.transcription_service:
            try:
                logger.debug("Shutting down transcription service")
                self.transcription_service.shutdown(timeout=5.0)
                logger.debug("Transcription service stopped")
            except Exception as e:
                logger.error(f"Error stopping transcription: {e}")

        # Step 4: Handle session cleanup
        if hasattr(self, 'session_manager'):
            try:
                if not self.session_manager.is_saved() and self.session_manager.has_recordings():
                    # User will be prompted via action_quit override
                    # If we got here via signal handler, session was already discarded
                    logger.debug("Session cleanup will be handled by action_quit")
                else:
                    # Auto-discard empty or saved sessions
                    logger.debug("Auto-discarding empty/saved session")
                    self.session_manager.discard_session()
            except Exception as e:
                logger.error(f"Error during session cleanup: {e}")

        logger.info("Resource cleanup complete")

    def update_meters(self):
        peaks = self.engine.peaks
        meter_1 = self.query_one("#meter-1", VUMeter)
        meter_1.level = peaks[0]
        meter_1.db_level = self.engine.dbs[0]

        if len(peaks) > 1 and self.engine.channels > 1:
            meter_2 = self.query_one("#meter-2", VUMeter)
            meter_2.level = peaks[1]
            meter_2.db_level = self.engine.dbs[1]

        if not self.engine.is_recording:
            fill_pct = (self.engine.write_ptr / self.engine.ring_size) * 100
            if self.engine.buffer_filled: fill_pct = 100
            self.query_one("#buffer-info").update(f"Pre-Record Buffer: {fill_pct:.1f}%")

    def _update_meter_visibility(self):
        is_stereo = self.engine.channels == 2
        self.query_one("#label-2").display = is_stereo
        self.query_one("#meter-2").display = is_stereo
        self.query_one("#label-1").update("Channel 1" if is_stereo else "Channel (Mono)")

    def _load_and_connect_saved_inputs(self):
        saved_ports = self.config_manager.get_input_ports()
        if not saved_ports:
            self.query_one("#connection-status").update("Inputs: [yellow]Not configured[/yellow]")
            return

        valid, missing = self.config_manager.validate_ports_exist(self.engine.client)
        if not valid:
            self.query_one("#connection-status").update("Inputs: [red]Invalid config[/red]")
            return

        if self.engine.connect_inputs(saved_ports):
            self._update_connection_status(saved_ports)

    def _update_connection_status(self, ports: list[str]):
        short_names = [p.split(':')[-1] if ':' in p else p for p in ports]
        txt = f"Inputs: [green]{' | '.join(short_names)}[/green]"
        self.query_one("#connection-status").update(txt)

    def _update_session_status(self):
        """Update session status display in UI."""
        if not hasattr(self, 'session_manager'):
            return

        session = self.session_manager.get_current_session()
        if not session:
            self.query_one("#session-status").update("Session: None")
            return

        info = session.get_info()
        status = "[green]Saved[/green]" if info['saved'] else "[yellow]Unsaved[/yellow]"
        count = info['recording_count']

        if count == 0:
            text = f"Session: New ({status})"
        else:
            text = f"Session: {count} recording(s) - {status}"

        self.query_one("#session-status").update(text)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle clipboard toggle state changes."""
        if event.checkbox.id == "clipboard-toggle":
            if hasattr(self, 'config_manager'):
                self.config_manager.set_copy_to_clipboard(event.value)
                status = "enabled" if event.value else "disabled"
                self.notify(f"Clipboard copy {status}", severity="information", timeout=2)

    def action_toggle_record(self):
        status_bar = self.query_one("#status-bar")
        if self.engine.is_recording:
            self.engine.stop_recording()
            status_bar.update("IDLE - Recording saved to session.")
            status_bar.remove_class("status-recording").add_class("status-idle")

            # Register recording with session
            if hasattr(self, '_current_recording_path'):
                session = self.session_manager.get_current_session()
                if session:
                    session.register_recording(
                        self._current_recording_path,
                        duration_seconds=0.0,  # TODO: Calculate actual duration
                        channels=self.engine.channels,
                        samplerate=self.engine.samplerate
                    )
                    self._update_session_status()

            if TRANSCRIPTION_AVAILABLE and self.config_manager.get_auto_transcribe():
                if last_file := self._get_last_recording_path():
                    self._start_transcription(last_file)
        else:
            # Get next recording path from session
            session = self.session_manager.get_current_session()
            if not session:
                self.notify("No active session", severity="error")
                return

            recording_path = session.get_next_recording_path()
            result = self.engine.start_recording(recording_path)

            if result:
                self._current_recording_path = result
                filename = result.name
                status_bar.update(f"RECORDING... \nFile: {filename}")
                status_bar.remove_class("status-idle").add_class("status-recording")

    def _get_last_recording_path(self) -> Optional[Path]:
        if hasattr(self, '_current_recording_path'):
            return self._current_recording_path
        return None

    def _start_transcription(self, audio_file: Path):
        if not TRANSCRIPTION_AVAILABLE or not self.transcription_service: return

        display = self.query_one("#transcription-display", TranscriptionDisplay)
        # Don't clear here, we want to keep history
        display.status = "processing"
        display.progress = 0.0

        def on_complete(result): self.call_from_thread(self._handle_result, result, audio_file)
        def on_progress(p): self.call_from_thread(lambda: setattr(display, 'progress', p))
        def on_clipboard_error(error_msg): self.call_from_thread(self._handle_clipboard_error, error_msg)

        # Get clipboard configuration
        copy_enabled = self.config_manager.get_copy_to_clipboard()

        self.transcription_service.transcribe_async(
            audio_file,
            on_complete,
            on_progress,
            copy_to_clipboard_enabled=copy_enabled,
            clipboard_error_callback=on_clipboard_error
        )

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

    def _handle_clipboard_error(self, error_msg: str):
        """Handle clipboard copy errors with UI notification."""
        self.notify(f"Clipboard copy failed: {error_msg}", severity="warning", timeout=4)

    def action_manual_transcribe(self):
        if last := self._get_last_recording_path():
            self._start_transcription(last)
        else:
            self.notify("No recording to transcribe", severity="warning")

    def action_open_input_selector(self):
        if self.engine.is_recording:
            self.notify("Cannot change inputs while recording", severity="warning")
            return
        
        try:
            available = self.engine.get_available_output_ports()
            current = self.engine.get_current_connections()

            def handle(result):
                if not result: return
                if len(result) != self.engine.channels:
                    self.engine.stop()
                    self.engine = AudioEngine(config_manager=self.config_manager, num_channels=len(result))
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
        """Save current session to permanent storage."""
        if self.engine.is_recording:
            self.notify("Stop recording before saving session", severity="warning")
            return

        session = self.session_manager.get_current_session()
        if not session or len(session.recordings) == 0:
            self.notify("No recordings to save in this session", severity="warning")
            return

        if session.saved:
            self.notify("Session already saved", severity="information")
            return

        def handle(result):
            if result:
                success = self.session_manager.save_session(result)
                if success:
                    self._update_session_status()
                    save_loc = session.save_location
                    self.notify(f"Session saved to: {save_loc}", severity="information", timeout=5)
                else:
                    self.notify("Failed to save session", severity="error")

        default_location = self.config_manager.get_default_save_location()
        self.push_screen(DirectorySelectionScreen(default_location), handle)

    def action_quit(self) -> None:
        """Override quit action to prompt for save if needed."""
        # Check if we have unsaved recordings
        if hasattr(self, 'session_manager'):
            if not self.session_manager.is_saved() and self.session_manager.has_recordings():
                self._prompt_save_before_quit()
                return

        # No unsaved work, quit normally
        self.exit()

    def _prompt_save_before_quit(self):
        """Show modal to save, discard, or cancel quit."""
        from textual.screen import ModalScreen
        from textual.widgets import Button
        from textual.containers import Grid

        class SavePromptScreen(ModalScreen):
            """Modal dialog prompting user to save before quitting."""

            CSS = """
            SavePromptScreen {
                align: center middle;
            }

            #dialog {
                width: 60;
                height: 15;
                border: thick $accent;
                background: $surface;
                padding: 2;
            }

            #question {
                width: 100%;
                height: 3;
                content-align: center middle;
                text-style: bold;
            }

            #message {
                width: 100%;
                height: 3;
                content-align: center middle;
                color: $text-muted;
            }

            Grid {
                width: 100%;
                height: auto;
                grid-size: 3 1;
                grid-gutter: 1;
                margin-top: 1;
            }

            Button {
                width: 100%;
            }
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
                    with Grid():
                        yield Button("Save", variant="primary", id="save")
                        yield Button("Discard", variant="error", id="discard")
                        yield Button("Cancel", id="cancel")

            def on_button_pressed(self, event: Button.Pressed) -> None:
                button_id = event.button.id
                if button_id == "save":
                    self.dismiss("save")
                elif button_id == "discard":
                    self.dismiss("discard")
                else:  # cancel
                    self.dismiss("cancel")

        def handle_choice(choice: str):
            if choice == "cancel":
                return  # Stay in app

            if choice == "discard":
                self.session_manager.discard_session()
                self.exit()
                return

            if choice == "save":
                # Open directory selector for save location
                def handle_save_location(location):
                    if location:
                        success = self.session_manager.save_session(location)
                        if success:
                            self.notify("Session saved successfully", severity="information")
                        else:
                            self.notify("Failed to save session", severity="error")
                    # Exit after save attempt (or if user cancelled directory selection)
                    self.exit()

                default_location = self.config_manager.get_default_save_location()
                self.push_screen(DirectorySelectionScreen(default_location), handle_save_location)

        self.push_screen(SavePromptScreen(self.session_manager, self.config_manager), handle_choice)

def configure_logging(level: str = "INFO") -> None:
    """Configure application logging."""
    log_dir = Path.home() / ".local" / "share" / "omega13" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"omega13_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized: {log_file}")

def main():
    configure_logging(level="INFO")  # Change to DEBUG for troubleshooting
    app = Omega13App()
    app.run()
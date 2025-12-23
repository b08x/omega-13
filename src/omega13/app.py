import logging
import signal
import os
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
from .session import SessionManager
from .hotkeys import GlobalHotkeyListener
from .notifications import DesktopNotifier

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
        Binding("i", "open_input_selector", "Select Inputs"),
        Binding("s", "save_session", "Save Session"),
        Binding("t", "manual_transcribe", "Transcribe"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown_initiated = False
        self._signal_handlers_registered = False
        self._signal_handlers_registered = False
        self.hotkey_listener: Optional[GlobalHotkeyListener] = None
        self.notifier: Optional[DesktopNotifier] = None

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
                    yield Static("\n[dim]REC Key to Capture | I Inputs | S Save | T Transcribe[/dim]", classes="help-text")

                with Vertical(id="transcription-controls"):
                    yield Label("Transcription Status", classes="transcription-title")
                    yield Static("Ready", id="transcription-status", classes="status-idle")
                    yield Checkbox("Copy to clipboard", id="clipboard-toggle", classes="clipboard-checkbox")

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
        
        # Add SIGUSR1 handler for external toggle triggering
        if hasattr(signal, "SIGUSR1"):
            signal.signal(signal.SIGUSR1, lambda s, f: self.call_later(self.action_toggle_record))

    def _graceful_shutdown(self) -> None:
        if hasattr(self, 'session_manager'):
            if not self.session_manager.is_saved() and self.session_manager.has_recordings():
                self.session_manager.discard_session()
        self.exit()

    def on_mount(self):
        if not self._signal_handlers_registered:
            self._register_signal_handlers()
            self._signal_handlers_registered = True

        try:
            self.config_manager = ConfigManager()
            
            # Initialize desktop notifier
            if self.config_manager.get_desktop_notifications_enabled():
                self.notifier = DesktopNotifier()

            transcription_display = self.query_one("#transcription-display", TranscriptionDisplay)
            transcription_display.config_manager = self.config_manager
            if transcription_display.clipboard_checkbox:
                initial_state = self.config_manager.get_copy_to_clipboard()
                transcription_display.clipboard_checkbox.value = initial_state

            temp_root = self.config_manager.get_session_temp_root()
            self.session_manager = SessionManager(temp_root=temp_root)
            self.session_manager.create_session()
            self._update_session_status()

            days = self.config_manager.get_auto_cleanup_days()
            self.session_manager.cleanup_old_sessions(days)

            saved_ports = self.config_manager.get_input_ports()
            num_channels = len(saved_ports) if saved_ports else DEFAULT_CHANNELS

            self.engine = AudioEngine(config_manager=self.config_manager, num_channels=num_channels)
            self.engine.start()

            # Write PID file for CLI toggle support
            try:
                self._pid_file = Path.home() / ".local" / "share" / "omega13" / "omega13.pid"
                self._pid_file.parent.mkdir(parents=True, exist_ok=True)
                self._pid_file.write_text(str(os.getpid()))
                logger = logging.getLogger(__name__)
                logger.info(f"PID file written: {self._pid_file} (PID: {os.getpid()})")
            except Exception as e:
                logging.getLogger(__name__).error(f"Failed to write PID file: {e}")

            self._load_and_connect_saved_inputs()
            self._update_meter_visibility()

            # Initialize Global Hotkeys
            global_hotkey_str = self.config_manager.get_global_hotkey()
            if global_hotkey_str:
                self.hotkey_listener = GlobalHotkeyListener(
                    global_hotkey_str, 
                    lambda: self.call_from_thread(self.action_toggle_record)
                )
                if self.hotkey_listener.start():
                    resolved = self.hotkey_listener.resolved_hotkey_str
                    logging.getLogger(__name__).info(f"Hotkey listener started successfully with: {resolved}")
                    self.notify(f"Global hotkey active: {resolved}", timeout=5)
                else:
                    self.notify(f"Failed to activate hotkey: {global_hotkey_str}", severity="error", timeout=10)

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
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass

        if hasattr(self, 'engine'):
            try:
                if self.engine.is_recording:
                    self.engine.stop_recording()
                self.engine.stop()
            except Exception:
                pass

        if hasattr(self, 'transcription_service') and self.transcription_service:
            try:
                self.transcription_service.shutdown(timeout=5.0)
            except Exception:
                pass

        if hasattr(self, 'session_manager'):
            try:
                if not self.session_manager.is_saved() and self.session_manager.has_recordings():
                    pass 
                else:
                    self.session_manager.discard_session()
            except Exception:
                pass

        if hasattr(self, '_pid_file') and self._pid_file.exists():
            try:
                self._pid_file.unlink()
            except Exception:
                pass

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
        if event.checkbox.id == "clipboard-toggle":
            if hasattr(self, 'config_manager'):
                self.config_manager.set_copy_to_clipboard(event.value)
                status = "enabled" if event.value else "disabled"
                self.notify(f"Clipboard copy {status}", severity="information", timeout=2)

    def action_toggle_record(self):
        status_bar = self.query_one("#status-bar")
        if self.engine.is_recording:
            self.engine.stop_recording()
            
            # Notify recording stopped
            if self.notifier:
                self.notifier.notify("Recording Stopped", "Audio capture saved.")

            status_bar.update("IDLE - Recording saved to session.")
            status_bar.remove_class("status-recording").add_class("status-idle")

            if hasattr(self, '_current_recording_path'):
                session = self.session_manager.get_current_session()
                if session:
                    session.register_recording(
                        self._current_recording_path,
                        duration_seconds=0.0,
                        channels=self.engine.channels,
                        samplerate=self.engine.samplerate
                    )
                    self._update_session_status()

            if TRANSCRIPTION_AVAILABLE and self.config_manager.get_auto_transcribe():
                if last_file := self._get_last_recording_path():
                    self._start_transcription(last_file)
        else:
            session = self.session_manager.get_current_session()
            if not session:
                self.notify("No active session", severity="error")
                return

            recording_path = session.get_next_recording_path()
            result = self.engine.start_recording(recording_path)

            if result:
                self._current_recording_path = result
                filename = result.name
                
                # Notify recording started
                if self.notifier:
                    self.notifier.notify("Recording Started", f"Capturing to {filename}")

                status_bar.update(f"RECORDING... \nFile: {filename}")
                status_bar.remove_class("status-idle").add_class("status-recording")

    def _get_last_recording_path(self) -> Optional[Path]:
        if hasattr(self, '_current_recording_path'):
            return self._current_recording_path
        return None

    def _start_transcription(self, audio_file: Path):
        if not self.transcription_service:
            # Re-instantiate service if needed or create new one
            # Note: We should ideally persist the service, but if it's missing:
            self.transcription_service = TranscriptionService(
                server_url=self.config_manager.config["transcription"]["server_url"],
                notifier=self.notifier
            )

        display = self.query_one("#transcription-display", TranscriptionDisplay)
        display.status = "processing"
        display.progress = 0.0

        def on_complete(result): self.call_from_thread(self._handle_result, result, audio_file)
        def on_progress(p): self.call_from_thread(lambda: setattr(display, 'progress', p))
        def on_clipboard_error(error_msg): self.call_from_thread(self._handle_clipboard_error, error_msg)

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
                self.notify(f"Session snapshot updated: {session.save_location.name}", severity="information", timeout=5)
            else:
                self.notify("Failed to update session snapshot", severity="error")
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
        if hasattr(self, 'session_manager'):
            if not self.session_manager.is_saved() and self.session_manager.has_recordings():
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
            #dialog { width: 60; height: 15; border: thick $accent; background: $surface; padding: 2; }
            #question { width: 100%; height: 3; content-align: center middle; text-style: bold; }
            #message { width: 100%; height: 3; content-align: center middle; color: $text-muted; }
            Grid { width: 100%; height: auto; grid-size: 3 1; grid-gutter: 1; margin-top: 1; }
            Button { width: 100%; }
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
                self.dismiss(event.button.id)

        def handle_choice(choice: str):
            if choice == "cancel": return
            if choice == "discard":
                self.session_manager.discard_session()
                self.exit()
                return
            if choice == "save":
                def handle_save_location(location):
                    if location:
                        success = self.session_manager.save_session(location)
                        if success: self.notify("Session saved successfully", severity="information")
                        else: self.notify("Failed to save session", severity="error")
                    self.exit()
                default_location = self.config_manager.get_default_save_location()
                self.push_screen(DirectorySelectionScreen(default_location), handle_save_location)

        self.push_screen(SavePromptScreen(self.session_manager, self.config_manager), handle_choice)

def configure_logging(level: str = "INFO") -> None:
    log_dir = Path.home() / ".local" / "share" / "omega13" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"omega13_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
    )
    logging.getLogger(__name__).info(f"Logging initialized: {log_file}")

def main():
    import argparse
    import sys
    import os
    
    parser = argparse.ArgumentParser(description="Omega-13 retroactive audio recorder")
    parser.add_argument("--toggle", action="store_true", help="Toggle recording on a running instance")
    parser.add_argument("--log-level", default="INFO", help="Set logging level")
    args = parser.parse_args()

    if args.toggle:
        # Find the PID of the running omega13 instance using the PID file
        try:
            pid_file = Path.home() / ".local" / "share" / "omega13" / "omega13.pid"
            if not pid_file.exists():
                print("No running Omega-13 instance found (PID file missing).")
                sys.exit(1)
            
            try:
                target_pid = int(pid_file.read_text().strip())
            except ValueError:
                print("Invalid PID file content.")
                sys.exit(1)

            # verify the process is actually running
            try:
                 # sending signal 0 does not actually kill the process but checks if it running (and we have permission)
                os.kill(target_pid, 0)
            except OSError:
                 print(f"Stale PID file found. Process {target_pid} is not running.")
                 sys.exit(1)

            print(f"Sending toggle signal to Omega-13 (PID: {target_pid})...")
            os.kill(target_pid, signal.SIGUSR1)
            sys.exit(0)
        except Exception as e:
            print(f"Error sending toggle signal: {e}")
            sys.exit(1)

    configure_logging(level=args.log_level)
    app = Omega13App()
    app.run()
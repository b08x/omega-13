import logging
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Label, Static

# Import refactored modules
from .config import ConfigManager
from .audio import AudioEngine, DEFAULT_CHANNELS
from .ui import VUMeter, TranscriptionDisplay, InputSelectionScreen, DirectorySelectionScreen

# Optional import for transcription
try:
    from .transcription import TranscriptionService, TranscriptionStatus, TranscriptionResult
    TRANSCRIPTION_AVAILABLE = True
except ImportError:
    TRANSCRIPTION_AVAILABLE = False

class TimeMachineApp(App):
    CSS = """
    Screen { align: center middle; background: $surface; }
    #app-layout { width: 100%; height: 100%; }
    #audio-pane { width: 50%; border: solid $accent; padding: 1 2; background: $surface-lighten-1; }
    #transcription-pane { width: 50%; border: solid $accent; padding: 1 2; background: $surface-lighten-1; margin-left: 1; }
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
    #transcription-log { height: 100%; border: solid $primary; background: $surface-darken-1; padding: 1; }
    """

    BINDINGS = [
        Binding("space", "toggle_record", "Record/Stop", priority=True),
        Binding("i", "open_input_selector", "Select Inputs"),
        Binding("p", "open_directory_selector", "Set Save Path"),
        Binding("t", "manual_transcribe", "Transcribe"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="app-layout"):
            with Container(id="audio-pane"):
                yield Label("TIME MACHINE", classes="title")
                yield Static("IDLE - Ready to Capture", id="status-bar", classes="status-idle")
                yield Static("Inputs: Loading...", id="connection-status")
                yield Static("Save Path: Loading...", id="path-status")
                yield Static("\nBuffers filled: ", id="buffer-info")
                with Vertical(id="meters"):
                    yield Label("Channel 1", id="label-1")
                    yield VUMeter(id="meter-1")
                    yield Label("Channel 2", id="label-2")
                    yield VUMeter(id="meter-2")
                yield Static("\n[dim]SPACE Capture | I Inputs | P Path | T Transcribe[/dim]", classes="help-text")
            
            with Container(id="transcription-pane"):
                yield TranscriptionDisplay(id="transcription-display")
        yield Footer()

    def on_mount(self):
        try:
            self.config_manager = ConfigManager()
            saved_ports = self.config_manager.get_input_ports()
            num_channels = len(saved_ports) if saved_ports else DEFAULT_CHANNELS

            self.engine = AudioEngine(config_manager=self.config_manager, num_channels=num_channels)
            self.engine.start()

            self._load_and_connect_saved_inputs()
            self._update_path_status()
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
        if hasattr(self, 'engine'):
            self.engine.stop_recording()
            self.engine.stop()

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

    def _update_path_status(self):
        path_str = str(self.engine.save_path)
        if len(path_str) > 50: path_str = f"...{path_str[-47:]}"
        self.query_one("#path-status").update(f"Save Path: [cyan]{path_str}[/cyan]")

    def action_toggle_record(self):
        status_bar = self.query_one("#status-bar")
        if self.engine.is_recording:
            self.engine.stop_recording()
            status_bar.update("IDLE - Saved.")
            status_bar.remove_class("status-recording").add_class("status-idle")
            
            if TRANSCRIPTION_AVAILABLE and self.config_manager.get_auto_transcribe():
                if last_file := self._get_last_recording_path():
                    self._start_transcription(last_file)
        else:
            fname = self.engine.start_recording()
            if fname:
                self._current_recording_filename = fname
                status_bar.update(f"RECORDING... \nFile: {fname}")
                status_bar.remove_class("status-idle").add_class("status-recording")

    def _get_last_recording_path(self) -> Optional[Path]:
        if hasattr(self, '_current_recording_filename'):
            return self.engine.save_path / self._current_recording_filename
        return None

    def _start_transcription(self, audio_file: Path):
        if not TRANSCRIPTION_AVAILABLE or not self.transcription_service: return
        
        display = self.query_one("#transcription-display", TranscriptionDisplay)
        display.clear()
        display.status = "processing"
        display.progress = 0.0

        def on_complete(result): self.call_from_thread(self._handle_result, result, audio_file)
        def on_progress(p): self.call_from_thread(lambda: setattr(display, 'progress', p))

        self.transcription_service.transcribe_async(audio_file, on_complete, on_progress)

    def _handle_result(self, result, audio_file):
        display = self.query_one("#transcription-display", TranscriptionDisplay)
        if result.status == TranscriptionStatus.COMPLETED:
            display.update_text(result.text)
            display.status = "completed"
        else:
            display.show_error(result.error or "Unknown error")

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

    def action_open_directory_selector(self):
        if self.engine.is_recording:
            self.notify("Cannot change path while recording", severity="warning")
            return
            
        def handle(result):
            if result:
                self.engine.save_path = result
                self.config_manager.set_save_path(result)
                self._update_path_status()
        
        self.push_screen(DirectorySelectionScreen(self.engine.save_path), handle)

def main():
    app = TimeMachineApp()
    app.run()
from pathlib import Path
import jack
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button, DirectoryTree, Label, OptionList, RichLog, Static
)
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding
from textual.app import ComposeResult

class VUMeter(Static):
    """A vertical bar displaying audio level."""
    level = reactive(0.0)
    db_level = reactive(-100.0)
    
    def watch_level(self, level: float) -> None:
        self.update_bar()

    def watch_db_level(self, db_level: float) -> None:
        self.update_bar()

    def _get_level_color(self, percentage: float) -> str:
        if percentage > 90: return "red"
        elif percentage > 70: return "yellow"
        else: return "green"

    def update_bar(self) -> None:
        pct = min(100, int(self.level * 100))
        color = self._get_level_color(pct)
        level_bar_display = "|" * (pct // 2)
        db_str = f"{self.db_level:>5.1f} dB" if self.db_level > -100 else "-inf dB"
        self.update(f"[{color}]{level_bar_display:50s}[/] [bold]{db_str}[/]")

class TranscriptionDisplay(Static):
    """Widget for displaying transcription status and results."""
    status = reactive("idle")
    progress = reactive(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.text_log = None
        self.status_label = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Transcription", classes="transcription-title")
            yield Static("Ready", id="transcription-status", classes="status-idle")
            yield RichLog(id="transcription-log", wrap=True, highlight=True)

    def on_mount(self):
        self.text_log = self.query_one("#transcription-log", RichLog)
        self.status_label = self.query_one("#transcription-status", Static)
        self.text_log.max_lines = 1000

    def watch_status(self, new_status: str) -> None:
        status_map = {
            "idle": ("Ready", "status-idle"),
            "loading_model": ("Loading model...", "status-loading"),
            "processing": ("Transcribing...", "status-processing"),
            "completed": ("Complete", "status-complete"),
            "error": ("Error", "status-error")
        }
        msg, cls = status_map.get(new_status, ("Unknown", "status-idle"))
        self.status_label.update(msg)
        self.status_label.remove_class("status-idle", "status-loading", "status-processing", "status-complete", "status-error")
        self.status_label.add_class(cls)

    def watch_progress(self, new_progress: float):
        if self.status == "processing":
            self.status_label.update(f"Transcribing... {int(new_progress * 100)}%")

    def update_text(self, text: str):
        self.text_log.clear()
        self.text_log.write(text)

    def show_error(self, error_message: str):
        self.status = "error"
        self.text_log.clear()
        self.text_log.write(f"[red]Error:[/red] {error_message}")

    def clear(self):
        self.text_log.clear()

class InputSelectionScreen(ModalScreen[tuple[str, str] | None]):
    """Modal screen for selecting two JACK input ports."""
    CSS = """
    InputSelectionScreen { align: center middle; }
    #selection-dialog { width: 70; height: 25; border: thick $accent; background: $surface; padding: 1 2; }
    #port-list { height: 15; border: solid $primary; margin: 1 0; background: $surface-lighten-1; }
    #button-row { height: 3; align: center middle; margin-top: 1; }
    #button-row Button { margin: 0 1; }
    #mode-selection { height: 5; border: solid $primary; margin: 1 0; align: center middle; }
    """
    BINDINGS = [("escape", "cancel", "Cancel"), ("enter", "confirm", "Confirm Selection")]

    def __init__(self, available_ports: list[jack.Port], current_ports: list[str | None]):
        super().__init__()
        self.available_ports = available_ports
        self.current_ports = current_ports
        self.selection_step = 0
        self.selected_mode = "Stereo" if len(current_ports) == 2 else "Mono"
        self.selected_port1 = None
        self.selected_port2 = None

    def compose(self) -> ComposeResult:
        with Container(id="selection-dialog"):
            yield Label("Select Input Mode", id="title")
            yield Static("Choose whether you want Mono or Stereo input:", id="help")
            with Vertical(id="mode-selection"):
                yield Button("Mono", id="mono-btn", variant="primary")
                yield Button("Stereo", id="stereo-btn", variant="primary")
            yield OptionList(id="port-list")
            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="error", id="cancel-btn")
                yield Button("Confirm", variant="primary", id="confirm-btn")

    def on_mount(self):
        self.query_one("#port-list").display = False
        self.query_one("#confirm-btn").display = False
        opt_list = self.query_one("#port-list", OptionList)
        for port in self.available_ports:
            is_phys = "[PHYSICAL]" if port.is_physical else ""
            opt_list.add_option(f"{port.name} {is_phys}".strip())

    def action_confirm(self):
        if self.selection_step == 0: return
        opt_list = self.query_one("#port-list", OptionList)
        idx = opt_list.highlighted
        if idx is None: return
        
        selected_port = self.available_ports[idx]
        if self.selection_step == 1:
            self.selected_port1 = selected_port.name
            if self.selected_mode == "Mono":
                self.dismiss([self.selected_port1])
            else:
                self._switch_to_step_2()
        else:
            self.selected_port2 = selected_port.name
            if self.selected_port1 == self.selected_port2: return
            self.dismiss([self.selected_port1, self.selected_port2])

    def _switch_to_port_selection(self, mode: str):
        self.selected_mode = mode
        self.selection_step = 1
        self.query_one("#mode-selection").display = False
        self.query_one("#port-list").display = True
        self.query_one("#confirm-btn").display = True
        self.query_one("#title", Label).update(f"Select Input 1 ({mode})")

    def _switch_to_step_2(self):
        self.selection_step = 2
        self.query_one("#title", Label).update("Select Input 2")

    def action_cancel(self): self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel-btn": self.action_cancel()
        elif event.button.id == "confirm-btn": self.action_confirm()
        elif event.button.id == "mono-btn": self._switch_to_port_selection("Mono")
        elif event.button.id == "stereo-btn": self._switch_to_port_selection("Stereo")

class DirectorySelectionScreen(ModalScreen[Path | None]):
    CSS = """
    DirectorySelectionScreen { align: center middle; }
    #directory-dialog { width: 80; height: 30; border: thick $accent; background: $surface; padding: 1 2; }
    #directory-tree { height: 18; border: solid $primary; margin: 1 0; }
    #button-row { height: 3; align: center middle; margin-top: 1; }
    #button-row Button { margin: 0 1; }
    """
    BINDINGS = [("escape", "cancel", "Cancel"), ("enter", "confirm", "Select")]

    def __init__(self, initial_path: Path):
        super().__init__()
        self.initial_path = initial_path
        self.selected_path = initial_path

    def compose(self) -> ComposeResult:
        with Container(id="directory-dialog"):
            yield Label("Select Save Directory", id="title")
            yield Static(f"Current: {self.initial_path}", id="help")
            yield DirectoryTree(str(self.initial_path.anchor), id="directory-tree")
            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="error", id="cancel-btn")
                yield Button("Select Current", variant="primary", id="confirm-btn")

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected):
        self.selected_path = Path(event.path)
        self.query_one("#help", Static).update(f"Selection: {self.selected_path}")

    def action_confirm(self): self.dismiss(self.selected_path)
    def action_cancel(self): self.dismiss(None)
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel-btn": self.action_cancel()
        elif event.button.id == "confirm-btn": self.action_confirm()
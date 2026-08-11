"""UI Modal Screens for Omega-13 TUI.

This module contains all modal screen classes used in the Omega-13 application.
Screens are self-contained and import Textual internally.
"""

import jack
from pathlib import Path
from typing import Optional

from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DirectoryTree,
    Input,
    Label,
    OptionList,
    RichLog,
    Static,
    RadioSet,
    RadioButton,
)
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding
from textual.app import ComposeResult


class InputSelectionScreen(ModalScreen[tuple[str, str] | None]):
    """Modal screen for selecting two JACK input ports."""

    CSS = """
    InputSelectionScreen { align: center middle; }
    #selection-dialog { width: 70; height: 30; border: thick $accent; background: $surface; padding: 1 2; }
    #port-list { height: 15; border: solid $primary; margin: 1 0; background: $surface-lighten-1; }
    #button-row { height: 3; align: center middle; margin-top: 1; }
    #button-row Button { width: 14; margin: 0 1; }
    #mode-selection { height: auto; min-height: 10; border: solid $primary; margin: 1 0; padding: 1; }
    #mode-selection Button { width: 100%; margin: 1 0; }
    """
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "confirm", "Confirm Selection"),
    ]

    def __init__(
        self, available_ports: list[jack.Port], current_ports: list[str | None]
    ):
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
        if self.selection_step == 0:
            return
        opt_list = self.query_one("#port-list", OptionList)
        idx = opt_list.highlighted
        if idx is None:
            return

        selected_port = self.available_ports[idx]
        if self.selection_step == 1:
            self.selected_port1 = selected_port.name
            if self.selected_mode == "Mono":
                self.dismiss([self.selected_port1])
            else:
                self._switch_to_step_2()
        else:
            self.selected_port2 = selected_port.name
            if self.selected_port1 == self.selected_port2:
                return
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

    def action_cancel(self):
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel-btn":
            self.action_cancel()
        elif event.button.id == "confirm-btn":
            self.action_confirm()
        elif event.button.id == "mono-btn":
            self._switch_to_port_selection("Mono")
        elif event.button.id == "stereo-btn":
            self._switch_to_port_selection("Stereo")


class TranscriptionSettingsScreen(ModalScreen[dict | None]):
    """Modal screen for configuring transcription settings."""

    CSS = """
    TranscriptionSettingsScreen { align: center middle; }
    #settings-dialog { width: 60; height: auto; border: thick $accent; background: $surface; padding: 1 2; }
    .settings-input { margin: 1 0; }
    .settings-label { margin-top: 1; text-style: bold; }
    #button-row { height: 3; align: center middle; margin-top: 1; }
    #button-row Button { width: 14; margin: 0 1; }
    RadioSet { margin: 1 0; border: solid $primary; padding: 1; }
    .hidden { display: none; }
    """
    BINDINGS = [("escape", "cancel", "Cancel"), ("enter", "confirm", "Save")]

    def __init__(self, config: dict):
        super().__init__()
        self.provider = config.get("provider", "local")
        self.server_url = config.get("server_url", "http://localhost:8080")
        self.inference_path = config.get("inference_path", "/inference")
        self.groq_model = config.get("groq_model", "whisper-large-v3-turbo")

    def compose(self) -> ComposeResult:
        with Container(id="settings-dialog"):
            yield Label("Transcription Settings", id="title", classes="settings-title")

            yield Label("Provider:", classes="settings-label")
            with RadioSet(id="provider-radio"):
                yield RadioButton(
                    "Local (whisper-server)",
                    id="local-provider",
                    value=self.provider == "local",
                )
                yield RadioButton(
                    "Groq (Cloud)", id="groq-provider", value=self.provider == "groq"
                )

            with Vertical(
                id="local-settings",
                classes="" if self.provider == "local" else "hidden",
            ):
                yield Label("Server URL:", classes="settings-label")
                yield Input(
                    value=self.server_url,
                    placeholder="http://localhost:8080",
                    id="server-url-input",
                    classes="settings-input",
                )

                yield Label("Inference Path:", classes="settings-label")
                yield Input(
                    value=self.inference_path,
                    placeholder="/inference",
                    id="inference-path-input",
                    classes="settings-input",
                )

            with Vertical(
                id="groq-settings", classes="" if self.provider == "groq" else "hidden"
            ):
                yield Label(
                    "Note: Groq API Key must be set in the 'GROQ_API_KEY' environment variable.",
                    classes="settings-label",
                )

                yield Label("Groq Model:", classes="settings-label")
                yield Input(
                    value=self.groq_model,
                    placeholder="whisper-large-v3-turbo",
                    id="groq-model-input",
                    classes="settings-input",
                )

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="error", id="cancel-btn")
                yield Button("Save", variant="primary", id="confirm-btn")

    def on_mount(self):
        if self.provider == "local":
            self.query_one("#server-url-input").focus()
        else:
            self.query_one("#groq-model-input").focus()

    def on_radio_set_changed(self, event: RadioSet.Changed):
        is_local = event.pressed.id == "local-provider"
        self.query_one("#local-settings").set_class(not is_local, "hidden")
        self.query_one("#groq-settings").set_class(is_local, "hidden")

    def action_confirm(self):
        provider = "local" if self.query_one("#local-provider").value else "groq"
        url = self.query_one("#server-url-input").value.strip()
        path = self.query_one("#inference-path-input").value.strip()
        model = self.query_one("#groq-model-input").value.strip()

        if provider == "local" and not url:
            self.app.notify("Server URL cannot be empty", severity="error")
            return

        self.dismiss(
            {
                "provider": provider,
                "server_url": url,
                "inference_path": path or "/inference",
                "groq_model": model or "whisper-large-v3-turbo",
            }
        )

    def action_cancel(self):
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel-btn":
            self.action_cancel()
        elif event.button.id == "confirm-btn":
            self.action_confirm()


class SessionTitleScreen(ModalScreen[str | None]):
    """Modal screen for entering a session title."""

    CSS = """
    SessionTitleScreen { align: center middle; }
    #title-dialog { width: 50; height: 15; border: thick $accent; background: $surface; padding: 1 2; }
    #title-input { margin: 1 0; }
    #button-row { height: 3; align: center middle; margin-top: 1; }
    #button-row Button { width: 14; margin: 0 1; }
    """
    BINDINGS = [("escape", "cancel", "Cancel"), ("enter", "confirm", "Confirm")]

    def compose(self) -> ComposeResult:
        with Container(id="title-dialog"):
            yield Label("Enter Session Title (Optional)", id="title")
            yield Input(placeholder="e.g. Brainstorming Session", id="title-input")
            with Horizontal(id="button-row"):
                yield Button("Skip", variant="default", id="skip-btn")
                yield Button("Save", variant="primary", id="confirm-btn")

    def on_mount(self):
        self.query_one("#title-input").focus()

    def action_confirm(self):
        title = self.query_one("#title-input").value.strip()
        self.dismiss(title if title else "")

    def action_cancel(self):
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "skip-btn":
            self.dismiss("")
        elif event.button.id == "confirm-btn":
            self.action_confirm()


class DirectorySelectionScreen(ModalScreen[Path | None]):
    CSS = """
    DirectorySelectionScreen { align: center middle; }
    #directory-dialog { width: 80; height: 30; border: thick $accent; background: $surface; padding: 1 2; }
    #directory-tree { height: 18; border: solid $primary; margin: 1 0; }
    #button-row { height: 3; align: center middle; margin-top: 1; }
    #button-row Button { width: 18; margin: 0 1; }
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

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ):
        self.selected_path = Path(event.path)
        self.query_one("#help", Static).update(f"Selection: {self.selected_path}")

    def action_confirm(self):
        self.dismiss(self.selected_path)

    def action_cancel(self):
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel-btn":
            self.action_cancel()
        elif event.button.id == "confirm-btn":
            self.action_confirm()


class NewSessionPromptScreen(ModalScreen):
    """Modal screen for confirming new session with unsaved recordings."""

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


class SavePromptScreen(ModalScreen):
    """Modal screen for confirming save before quit."""

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
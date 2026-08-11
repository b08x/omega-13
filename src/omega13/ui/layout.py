"""Layout and styling for Omega-13 TUI.

This module contains the main app CSS, key bindings, and composition logic.
All Textual imports are contained within this module.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Label, Static

from .widgets import VUMeter, SilenceCountdown, TranscriptionDisplay


# Main application CSS
APP_CSS = """
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

# Key bindings for the main app
APP_BINDINGS = [
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


def compose_main_layout() -> ComposeResult:
    """Compose the main application layout.

    This function can be used by any Textual App subclass to create
    the standard Omega-13 layout.
    """
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


def update_help_text(app, config_manager):
    """Update help text with configured hotkey."""
    hotkey = config_manager.get_global_hotkey()
    formatted_hotkey = (
        hotkey.replace("<", "").replace(">", "").replace("+", " + ").title()
    )

    help_text = app.query_one("#help-text", Static)
    help_text.update(
        f"\n[dim]{formatted_hotkey} to Capture | I Inputs | N New | S Save | T Transcribe | A Auto-Rec | C Clip | J Inject | D Daily | P Settings[/dim]"
    )


def update_meter_visibility(app, is_stereo: bool):
    """Update meter visibility based on channel count."""
    app.query_one("#label-2").display = is_stereo
    app.query_one("#meter-2").display = is_stereo
    app.query_one("#label-1").update(
        "Channel 1" if is_stereo else "Channel (Mono)"
    )


def update_connection_status(app, ports: list[str]):
    """Update the connection status display."""
    short_names = [p.split(":")[-1] if ":" in p else p for p in ports]
    txt = f"Inputs: [green]{' | '.join(short_names)}[/green]"
    app.query_one("#connection-status").update(txt)


def update_session_status(app, session_manager):
    """Update the session status display."""
    session = session_manager.get_current_session()
    if not session:
        app.query_one("#session-status").update("Session: None")
        return

    info = session.get_info()
    status = "[green]Saved[/green]" if info["saved"] else "[yellow]Unsaved[/yellow]"
    count = info["recording_count"]

    if count == 0:
        text = f"Session: New ({status})"
    else:
        text = f"Session: {count} recording(s) - {status}"

    app.query_one("#session-status").update(text)
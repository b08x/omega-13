"""UI Widgets for Omega-13 TUI.

This module contains all custom Textual widgets used in the Omega-13 application.
Widgets are self-contained and import Textual internally.
"""

from textual.reactive import reactive
from textual.widgets import RichLog, Static
from textual.css.query import NoMatches


class VUMeter(Static):
    """A vertical bar displaying audio level."""

    level = reactive(0.0)
    db_level = reactive(-100.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_rendered_level = -1.0
        self._last_rendered_db = -200.0

    def update_levels(self, level: float, db: float) -> None:
        """Atomic update of levels to reduce reactive overhead."""
        # Only update reactive attributes if change is significant (> 1%)
        # or if we are crossing important thresholds (e.g. 0 level)
        if abs(self.level - level) > 0.01 or (level == 0 and self.level > 0):
            self.level = level

        if abs(self.db_level - db) > 0.5 or (db == -100.0 and self.db_level > -100.0):
            self.db_level = db

    def watch_level(self, level: float) -> None:
        self.update_bar()

    def watch_db_level(self, db_level: float) -> None:
        self.update_bar()

    def _get_level_color(self, percentage: float) -> str:
        if percentage > 90:
            return "red"
        elif percentage > 70:
            return "yellow"
        else:
            return "green"

    def update_bar(self) -> None:
        # Extra safeguard: don't thrash the DOM if visual state is same
        pct = min(100, int(self.level * 100))
        if pct == self._last_rendered_level and abs(self.db_level - self._last_rendered_db) < 0.2:
            return

        self._last_rendered_level = pct
        self._last_rendered_db = self.db_level

        color = self._get_level_color(pct)
        level_bar_display = "|" * (pct // 2)
        db_str = f"{self.db_level:>5.1f} dB" if self.db_level > -100 else "-inf dB"
        self.update(f"[{color}]{level_bar_display:50s}[/] [bold]{db_str}[/]")


class SilenceCountdown(Static):
    """
    Displays countdown timer when silence is detected during recording.

    Shows remaining time before auto-stop is triggered.
    """

    countdown = reactive(0.0)  # Seconds remaining until auto-stop
    visible = reactive(False)  # Whether to show the countdown

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_displayed_countdown = -1.0  # For debouncing

    def watch_countdown(self, value: float) -> None:
        """Update display when countdown value changes (with debouncing)."""
        # Debounce: only update if change is > 0.3s to reduce UI overhead
        if abs(value - self._last_displayed_countdown) > 0.3 or value == 0:
            self._last_displayed_countdown = value
            self.update_display()

    def watch_visible(self, is_visible: bool) -> None:
        """Update display when visibility changes."""
        self.update_display()

    def update_display(self) -> None:
        """Render the countdown display."""
        if self.visible and self.countdown > 0:
            # Show countdown with visual emphasis
            bar_width = 30
            filled = int((self.countdown / 10.0) * bar_width)  # Assuming 10s max
            bar = "█" * filled + "░" * (bar_width - filled)
            self.update(f"[yellow]Silence:[/yellow] {self.countdown:.1f}s [{bar}]")
        elif self.visible:
            # Silence detected but countdown not active
            self.update("[dim]Monitoring silence...[/dim]")
        else:
            # Hide countdown
            self.update("")


class TranscriptionDisplay(Static):
    """Widget for displaying transcription status and results."""

    status = reactive("idle")
    progress = reactive(0.0)
    provider = reactive("local")

    def __init__(self, config_manager=None, **kwargs):
        super().__init__(**kwargs)
        self.config_manager = config_manager
        self.text_log = None
        self.status_label = None
        self.clipboard_checkbox = None
        self.injection_checkbox = None

    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label

        with Vertical():
            with Horizontal(classes="transcription-header"):
                yield Label("Transcription", classes="transcription-title")
                yield Static("", id="provider-badge", classes="provider-badge")
            yield RichLog(id="transcription-log", wrap=True, highlight=True)

    def on_mount(self):
        self.text_log = self.query_one("#transcription-log", RichLog)
        # These are now external to this widget, queried from the app
        self.status_label = self.app.query_one("#transcription-status", Static)
        self.text_log.max_lines = 1000

    def watch_status(self, new_status: str) -> None:
        status_map = {
            "idle": ("Ready", "status-idle"),
            "loading_model": ("Loading model...", "status-loading"),
            "processing": ("Transcribing...", "status-processing"),
            "completed": ("Complete", "status-complete"),
            "error": ("Error", "status-error"),
        }
        msg, cls = status_map.get(new_status, ("Unknown", "status-idle"))
        self.status_label.update(msg)
        self.status_label.remove_class(
            "status-idle",
            "status-loading",
            "status-processing",
            "status-complete",
            "status-error",
        )
        self.status_label.add_class(cls)

    def watch_provider(self, new_provider: str) -> None:
        badge = self.query_one("#provider-badge", Static)
        if new_provider == "groq":
            badge.update("☁️ Groq")
            badge.remove_class("provider-local").add_class("provider-groq")
        else:
            badge.update("🏠 Local")
            badge.remove_class("provider-groq").add_class("provider-local")

    def watch_progress(self, new_progress: float):
        if self.status == "processing":
            self.status_label.update(f"Transcribing... {int(new_progress * 100)}%")

    def update_text(self, text: str):
        """Append a single transcription to the log."""
        self.text_log.write(text)

    def update_buffer(self, transcriptions: list[str]):
        """Update the log with the full session buffer."""
        self.text_log.clear()
        for text in transcriptions:
            self.text_log.write(text)
            self.text_log.write("")  # Add spacing between transcriptions

    def show_error(self, error_message: str):
        self.status = "error"
        self.text_log.write(f"[red]Error:[/red] {error_message}")

    def clear(self):
        self.text_log.clear()
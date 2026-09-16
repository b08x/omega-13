"""Console wrapper and UI components for the installer.

Provides the themed Console singleton and reusable rendering helpers:
banners, step headers, status lines, confirmation prompts.
"""

import os
import shutil
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Confirm
from rich import box

from omega13.installer.theme import SYNCOPATED_THEME, COLORS

# Module-level themed console — import this everywhere
console = Console(theme=SYNCOPATED_THEME)

# Version pulled from pyproject.toml at build time
_VERSION = "2.5.0"


def banner() -> None:
    """Render the installer banner."""
    width = min(shutil.get_terminal_size().columns, 56)
    title = Text()
    title.append("Ω  ", style=f"bold {COLORS['accent_hi']}")
    title.append("Omega-13 Installer", style=f"bold {COLORS['foreground']}")

    subtitle = Text()
    subtitle.append("Retroactive Audio Recorder ", style=f"{COLORS['text_2']}")
    subtitle.append(f"v{_VERSION}", style=f"{COLORS['special']}")

    content = Text.from_markup("")
    content.append_text(title)
    content.append("\n")
    content.append_text(subtitle)

    panel = Panel(
        content,
        box=box.DOUBLE,
        border_style=f"{COLORS['accent']}",
        width=width,
        padding=(1, 2),
    )
    console.print()
    console.print(panel, justify="center")
    console.print()


def uninstall_banner() -> None:
    """Render the uninstaller banner."""
    width = min(shutil.get_terminal_size().columns, 56)
    title = Text()
    title.append("Ω  ", style=f"bold {COLORS['danger']}")
    title.append("Omega-13 Uninstaller", style=f"bold {COLORS['foreground']}")

    panel = Panel(
        title,
        box=box.DOUBLE,
        border_style=f"{COLORS['danger']}",
        width=width,
        padding=(1, 2),
    )
    console.print()
    console.print(panel, justify="center")
    console.print()


def step_header(number: int, title: str, total: int = 7) -> None:
    """Print a step header line.

    Example: ❯ [2/7] Building ydotool from source
    """
    console.print()
    text = Text()
    text.append(" ❯ ", style=f"{COLORS['accent']}")
    text.append(f"[{number}/{total}] ", style=f"bold {COLORS['muted']}")
    text.append(title, style=f"bold {COLORS['foreground']}")
    console.print(text)


def status_done(message: str) -> None:
    """Print a success status line."""
    console.print(f"   [success]✓[/success] {message}")


def status_skip(message: str) -> None:
    """Print a skipped status line."""
    console.print(f"   [step.skip]⏭ {message}[/step.skip]")


def status_fail(message: str) -> None:
    """Print a failure status line."""
    console.print(f"   [step.fail]✗ {message}[/step.fail]")


def status_info(message: str) -> None:
    """Print an info status line."""
    console.print(f"   [info]ℹ {message}[/info]")


def status_warn(message: str) -> None:
    """Print a warning status line."""
    console.print(f"   [warning]⚠ {message}[/warning]")


def confirm(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no confirmation using the themed console."""
    return Confirm.ask(
        f"   [question]❯[/question] {prompt}",
        console=console,
        default=default,
    )


def show_path(label: str, path: str) -> None:
    """Print a labeled path."""
    console.print(f"   {label}: [path]{path}[/path]")


def show_command(cmd: str) -> None:
    """Print a command hint."""
    console.print(f"   [cmd]$ {cmd}[/cmd]")


def completion_panel(lines: list[str]) -> None:
    """Render the final completion panel."""
    width = min(shutil.get_terminal_size().columns, 56)
    content = Text()
    for i, line in enumerate(lines):
        content.append(line)
        if i < len(lines) - 1:
            content.append("\n")

    panel = Panel(
        content,
        title="[success]🎉 Installation Complete![/success]",
        box=box.DOUBLE,
        border_style=f"{COLORS['success']}",
        width=width,
        padding=(1, 2),
    )
    console.print()
    console.print(panel, justify="center")
    console.print()


def removal_panel() -> None:
    """Render the uninstall completion panel."""
    width = min(shutil.get_terminal_size().columns, 56)
    panel = Panel(
        Text("Omega-13 has been removed.", style=f"{COLORS['text_2']}"),
        title="[info]👋 Uninstallation Complete[/info]",
        box=box.DOUBLE,
        border_style=f"{COLORS['info']}",
        width=width,
        padding=(1, 2),
    )
    console.print()
    console.print(panel, justify="center")
    console.print()


def xdg_paths() -> dict[str, str]:
    """Return XDG-compliant installation paths."""
    home = os.path.expanduser("~")
    return {
        "data_home":    os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share")),
        "bin_home":     os.environ.get("XDG_BIN_HOME", os.path.join(home, ".local", "bin")),
        "config_home":  os.environ.get("XDG_CONFIG_HOME", os.path.join(home, ".config")),
        "dest_dir":     os.path.join(
            os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share")),
            "omega13",
        ),
        "bin_link":     os.path.join(
            os.environ.get("XDG_BIN_HOME", os.path.join(home, ".local", "bin")),
            "omega13",
        ),
        "config_dir":   os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.path.join(home, ".config")),
            "omega13",
        ),
        "systemd_dir":  os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.path.join(home, ".config")),
            "systemd", "user",
        ),
        "model_dir":    os.path.join(
            os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share")),
            "omega13", "models",
        ),
    }

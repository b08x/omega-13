"""Generate and install the systemd user service file.

Generates the service file at install time with correct paths
instead of shipping a hardcoded file in the repo.
"""

import os
import subprocess
import textwrap

from rich.panel import Panel
from rich.syntax import Syntax
from rich import box

from omega13.installer.ui import (
    console, step_header, status_done, status_fail,
    status_info, show_path, xdg_paths,
)
from omega13.installer.theme import COLORS


SERVICE_TEMPLATE = """\
[Unit]
Description=Omega-13 Retroactive Audio Recorder
After=sound.target pipewire.service jack.service graphical-session.target
Wants=sound.target

[Service]
Type=simple
ExecStart={exec_start}
WorkingDirectory={working_dir}
Restart=on-failure
RestartSec=5
Environment="DISPLAY=:0"
Environment="WAYLAND_DISPLAY=wayland-0"

[Install]
WantedBy=graphical-session.target
"""


def install_systemd_service(step_num: int = 5, total_steps: int = 7) -> bool:
    """Generate and install the systemd user service file.

    Args:
        step_num: Step number for display.
        total_steps: Total number of steps for display.

    Returns:
        True if service was installed successfully.
    """
    step_header(step_num, "Install systemd service", total_steps)

    paths = xdg_paths()
    exec_start = os.path.join(paths["dest_dir"], ".venv", "bin", "omega13") + " --no-daemon"
    working_dir = paths["dest_dir"]

    service_content = SERVICE_TEMPLATE.format(
        exec_start=exec_start,
        working_dir=working_dir,
    )

    # Write service file
    os.makedirs(paths["systemd_dir"], exist_ok=True)
    service_path = os.path.join(paths["systemd_dir"], "omega13.service")

    try:
        with open(service_path, "w") as f:
            f.write(service_content)
    except OSError as e:
        status_fail(f"Failed to write service file: {e}")
        return False

    show_path("Service file", service_path)

    # Show the generated service content
    syntax = Syntax(
        service_content.strip(),
        "ini",
        theme="monokai",
        line_numbers=False,
        padding=1,
    )
    panel = Panel(
        syntax,
        title=f"[accent]omega13.service[/accent]",
        border_style=f"{COLORS['border_2']}",
        box=box.ROUNDED,
        width=60,
    )
    console.print(panel)

    # Reload systemd
    try:
        result = subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            status_fail(f"daemon-reload failed: {result.stderr.strip()}")
            return False
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        status_fail(f"Could not reload systemd: {e}")
        return False

    status_done("Systemd service installed")
    status_info("Enable with: systemctl --user enable --now omega13")

    return True

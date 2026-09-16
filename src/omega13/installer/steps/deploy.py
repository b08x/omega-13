"""Deploy application to XDG-compliant user directory.

Handles:
- Stopping existing systemd service
- rsync to ~/.local/share/omega13
- Creating venv + uv sync in deploy dir
- Symlink to ~/.local/bin/omega13
"""

import os
import shutil
import subprocess

from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from omega13.installer.ui import (
    console, step_header, status_done, status_skip, status_fail,
    status_info, status_warn, show_path, xdg_paths,
)
from omega13.installer.theme import COLORS


def _stop_existing_service() -> None:
    """Stop and disable the omega13 systemd service if running."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "omega13"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            status_info("Stopping existing omega13 service...")
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", "omega13"],
                capture_output=True, timeout=30,
            )
            status_done("Stopped existing service")
    except (subprocess.SubprocessError, FileNotFoundError):
        pass


def _find_project_root() -> str | None:
    """Find the omega13 project root by looking for pyproject.toml."""
    # Start from the installer module's location and walk up
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if os.path.isfile(os.path.join(current, "pyproject.toml")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def _run_with_spinner(cmd: list[str], label: str, cwd: str | None = None,
                      env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command with a spinner."""
    spinner = Spinner("dots", text=Text(label, style=f"{COLORS['text_2']}"))

    with Live(spinner, console=console, refresh_per_second=10):
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            cwd=cwd, env=env,
            timeout=300,
        )

    return result


def deploy_app(force: bool = False, step_num: int = 4, total_steps: int = 7) -> bool:
    """Deploy omega13 to the XDG user directory.

    Args:
        force: If True, overwrite config files.
        step_num: Step number for display.
        total_steps: Total number of steps for display.

    Returns:
        True if deployment succeeded.
    """
    step_header(step_num, "Deploy application", total_steps)

    paths = xdg_paths()
    project_root = _find_project_root()

    if not project_root:
        status_fail("Cannot find project root (pyproject.toml not found)")
        return False

    # Stop existing service
    _stop_existing_service()

    # Create destination
    os.makedirs(paths["dest_dir"], exist_ok=True)

    # rsync project files (exclude dev/build artifacts)
    rsync_excludes = [
        "--exclude=.git",
        "--exclude=.venv",
        "--exclude=__pycache__",
        "--exclude=.pytest_cache",
        "--exclude=.cache",
        "--exclude=logs",
        "--exclude=tests",
        "--exclude=goals",
        "--exclude=graphify-out",
        "--exclude=.claude",
        "--exclude=.codemap",
        "--exclude=.codebase-memory",
        "--exclude=.crush",
        "--exclude=.opencode",
        "--exclude=.trackboi",
        "--exclude=.agents",
        "--exclude=models",
    ]

    rsync_cmd = [
        "rsync", "-a", "--delete",
        *rsync_excludes,
        f"{project_root}/",
        f"{paths['dest_dir']}/",
    ]

    status_info(f"Syncing files to {paths['dest_dir']}")
    result = _run_with_spinner(rsync_cmd, f"rsync → {paths['dest_dir']}")

    if result.returncode != 0:
        status_fail(f"rsync failed: {result.stderr.strip()}")
        return False

    status_done("Files synced")

    # Preserve models directory (always)
    model_dir = paths["model_dir"]
    if os.path.isdir(model_dir):
        status_info(f"Preserving models at {model_dir}")

    # Preserve config (unless --force)
    config_file = os.path.join(paths["config_dir"], "config.json")
    if os.path.isfile(config_file) and not force:
        status_info("Preserving existing config.json")
    elif force and os.path.isfile(config_file):
        status_warn("--force: config.json will be reset on next run")

    # Setup venv in deploy directory
    deploy_venv = os.path.join(paths["dest_dir"], ".venv")
    if not os.path.isdir(deploy_venv):
        status_info("Creating virtual environment...")
        result = _run_with_spinner(
            ["uv", "venv"],
            "uv venv",
            cwd=paths["dest_dir"],
        )
        if result.returncode != 0:
            status_fail(f"uv venv failed: {result.stderr.strip()}")
            return False

    status_info("Syncing dependencies...")
    result = _run_with_spinner(
        ["uv", "sync"],
        "uv sync",
        cwd=paths["dest_dir"],
    )
    if result.returncode != 0:
        status_fail(f"uv sync failed: {result.stderr.strip()}")
        return False

    status_done("Virtual environment ready")

    # Create symlink
    os.makedirs(paths["bin_home"], exist_ok=True)
    venv_bin = os.path.join(paths["dest_dir"], ".venv", "bin", "omega13")

    if os.path.islink(paths["bin_link"]):
        os.unlink(paths["bin_link"])
    elif os.path.exists(paths["bin_link"]):
        os.remove(paths["bin_link"])

    os.symlink(venv_bin, paths["bin_link"])

    show_path("Symlink", f"{paths['bin_link']} → {venv_bin}")
    status_done("Application deployed")

    # Check PATH
    user_path = os.environ.get("PATH", "")
    if paths["bin_home"] not in user_path:
        status_warn(f"Ensure {paths['bin_home']} is in your PATH")

    return True

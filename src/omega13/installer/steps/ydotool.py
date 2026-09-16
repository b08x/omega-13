"""Build ydotool from source.

Required for text injection on Wayland. Built from source because
there is no EL10/EPEL package for AlmaLinux/Rocky.

Cached at ~/.local/src/ydotool — skipped on reinstall unless --force.
"""

import os
import shutil
import subprocess

from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from omega13.installer.ui import (
    console, step_header, status_done, status_skip, status_fail,
    status_info, status_warn, xdg_paths,
)
from omega13.installer.theme import COLORS


def _has_ydotool() -> bool:
    """Check if ydotool is installed and ydotoold service is enabled."""
    if not shutil.which("ydotool"):
        return False
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-enabled", "ydotoold"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _resource_limited_available() -> bool:
    """Check if resource-limiting tools are available."""
    return all(shutil.which(cmd) for cmd in ("nice", "ionice", "taskset", "cpulimit"))


def _run_with_spinner(cmd: list[str], label: str, cwd: str | None = None,
                      env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command with a spinner showing progress."""
    spinner = Spinner("dots", text=Text(label, style=f"{COLORS['text_2']}"))

    with Live(spinner, console=console, refresh_per_second=10):
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            cwd=cwd, env=env,
            timeout=600,  # 10 minute timeout
        )

    return result


def build_ydotool(force: bool = False, step_num: int = 2, total_steps: int = 7) -> bool:
    """Build and install ydotool from source.

    Args:
        force: If True, rebuild even if ydotool is already installed.
        step_num: Step number for display.
        total_steps: Total number of steps for display.

    Returns:
        True if ydotool is available after this step.
    """
    step_header(step_num, "Build ydotool (text injection)", total_steps)

    if _has_ydotool() and not force:
        ydotool_path = shutil.which("ydotool")
        status_skip(f"ydotool already installed at {ydotool_path}")
        return True

    # Source directory
    src_dir = os.path.expanduser("~/.local/src/ydotool")

    # Clone or update
    if os.path.isdir(src_dir):
        status_info("Updating ydotool source...")
        result = _run_with_spinner(
            ["git", "pull", "--ff-only"],
            "git pull ~/.local/src/ydotool",
            cwd=src_dir,
        )
        if result.returncode != 0:
            status_warn("git pull failed, continuing with existing source")
    else:
        status_info("Cloning ydotool source...")
        os.makedirs(os.path.dirname(src_dir), exist_ok=True)
        result = _run_with_spinner(
            ["git", "clone", "https://github.com/ReimuNotMoe/ydotool.git", src_dir],
            "git clone ydotool",
        )
        if result.returncode != 0:
            status_fail(f"Failed to clone ydotool: {result.stderr.strip()}")
            return False

    # Configure
    build_dir = os.path.join(src_dir, "build")
    result = _run_with_spinner(
        ["cmake", "-B", "build", "-DSYSTEMD_USER_SERVICE=ON"],
        "cmake -B build -DSYSTEMD_USER_SERVICE=ON",
        cwd=src_dir,
    )
    if result.returncode != 0:
        status_fail(f"cmake configure failed: {result.stderr.strip()}")
        return False

    # Build (resource-limited if possible)
    if _resource_limited_available():
        build_cmd = [
            "nice", "-n", "19",
            "ionice", "-c", "3",
            "taskset", "-c", "0-3",
            "cpulimit", "-l", "150", "--",
            "make", "-C", "build", "-j4",
        ]
    else:
        build_cmd = ["make", "-C", "build", "-j4"]
        status_warn("Building without resource limits (cpulimit/taskset not found)")

    result = _run_with_spinner(
        build_cmd,
        "make -C build -j4 (resource-limited)",
        cwd=src_dir,
    )
    if result.returncode != 0:
        status_fail(f"Build failed: {result.stderr.strip()}")
        return False

    # Install (requires sudo)
    status_info("Installing ydotool (requires sudo)...")
    result = subprocess.run(
        ["sudo", "make", "-C", "build", "install"],
        cwd=src_dir,
        timeout=60,
    )
    if result.returncode != 0:
        status_fail("sudo make install failed")
        return False

    # Enable service
    result = subprocess.run(
        ["systemctl", "--user", "enable", "--now", "ydotoold"],
        capture_output=True, text=True,
        timeout=30,
    )
    if result.returncode != 0:
        status_warn(f"Could not enable ydotoold service: {result.stderr.strip()}")
    else:
        status_done("ydotoold service enabled")

    status_done("ydotool installed successfully")
    return True

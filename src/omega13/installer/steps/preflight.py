"""Preflight checks — verify dependencies and detect existing installation.

Renders a Rich table showing the status of each required executable,
library, and optional component.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass

from rich.table import Table
from rich import box

from omega13.installer.ui import console, step_header, status_done, status_warn, status_fail, xdg_paths
from omega13.installer.theme import COLORS


@dataclass
class CheckResult:
    """Result of a single dependency check."""
    name: str
    found: bool
    location: str = "—"
    required: bool = True
    note: str = ""


def _check_cmd(name: str, required: bool = True) -> CheckResult:
    """Check if a command is available on PATH."""
    path = shutil.which(name)
    if path:
        return CheckResult(name=name, found=True, location=path, required=required)
    return CheckResult(name=name, found=False, required=required)


def _check_lib(name: str, ldconfig_pattern: str, pkg_config_name: str, required: bool = True) -> CheckResult:
    """Check if a shared library is available via ldconfig or pkg-config."""
    # Try ldconfig
    try:
        result = subprocess.run(
            ["ldconfig", "-p"],
            capture_output=True, text=True, timeout=10,
        )
        if ldconfig_pattern in result.stdout:
            return CheckResult(name=name, found=True, location=f"ldconfig: {ldconfig_pattern}", required=required)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Try pkg-config
    try:
        result = subprocess.run(
            ["pkg-config", "--exists", pkg_config_name],
            capture_output=True, timeout=10,
        )
        if result.returncode == 0:
            return CheckResult(name=name, found=True, location=f"pkg-config: {pkg_config_name}", required=required)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return CheckResult(name=name, found=False, required=required)


def _check_hardware(name: str, ldconfig_pattern: str, extra_cmd: str | None = None) -> CheckResult:
    """Detect optional hardware acceleration (CUDA, Vulkan)."""
    try:
        result = subprocess.run(
            ["ldconfig", "-p"],
            capture_output=True, text=True, timeout=10,
        )
        found = ldconfig_pattern in result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        found = False

    if found and extra_cmd:
        try:
            subprocess.run(
                extra_cmd.split(),
                capture_output=True, timeout=10,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            found = False

    location = f"ldconfig: {ldconfig_pattern}" if found else "—"
    return CheckResult(name=name, found=found, location=location, required=False)


def run_preflight(step_num: int = 1, total_steps: int = 7) -> tuple[list[CheckResult], dict[str, bool]]:
    """Run all preflight checks and render results.

    Returns:
        Tuple of (all check results, hardware detection dict).
    """
    step_header(step_num, "Preflight checks", total_steps)

    checks: list[CheckResult] = []

    # Executables
    checks.append(_check_cmd("python3"))
    checks.append(_check_cmd("uv"))
    checks.append(_check_cmd("ffmpeg"))
    checks.append(_check_cmd("sox"))
    checks.append(_check_cmd("ydotool"))
    checks.append(_check_cmd("cmake"))
    checks.append(_check_cmd("make"))
    checks.append(_check_cmd("git"))
    checks.append(_check_cmd("cpulimit", required=False))
    checks.append(_check_cmd("taskset", required=False))
    checks.append(_check_cmd("ionice", required=False))

    # Libraries
    checks.append(_check_lib("JACK/PipeWire-JACK", "libjack.so", "jack"))
    checks.append(_check_lib("GTK4 Layer Shell", "libgtk4-layer-shell.so", "gtk4-layer-shell-0"))
    checks.append(_check_lib("Cairo", "libcairo.so", "cairo"))
    checks.append(_check_lib("GObject Introspection", "libgirepository", "gobject-introspection-1.0"))

    # Hardware (optional)
    cuda = _check_hardware("CUDA", "libcuda.so", "nvidia-smi")
    vulkan = _check_hardware("Vulkan", "libvulkan.so")
    checks.append(cuda)
    checks.append(vulkan)

    # Existing installation
    paths = xdg_paths()
    existing = os.path.isdir(paths["dest_dir"])

    # Render table
    table = Table(
        box=box.ROUNDED,
        border_style=f"{COLORS['border_2']}",
        header_style=f"bold {COLORS['accent']}",
        padding=(0, 1),
    )
    table.add_column("Dependency", style=f"{COLORS['foreground']}")
    table.add_column("Status", justify="center", width=6)
    table.add_column("Location", style=f"{COLORS['cyan']}")

    for check in checks:
        if check.found:
            status = f"[success]✅[/success]"
        elif check.required:
            status = f"[danger]❌[/danger]"
        else:
            status = f"[dim]—[/dim]"

        name_style = "" if check.found or not check.required else f"[danger]{check.name}[/danger]"
        table.add_row(
            check.name if check.found or not check.required else f"[danger]{check.name}[/danger]",
            status,
            check.location,
        )

    console.print()
    console.print(table, justify="center")

    # Summary
    missing_required = [c for c in checks if not c.found and c.required]
    if missing_required:
        console.print()
        status_fail(f"{len(missing_required)} required dependencies missing")
        for c in missing_required:
            status_fail(f"  {c.name}")
    else:
        status_done("All required dependencies satisfied")

    if existing:
        status_warn(f"Existing installation found at {paths['dest_dir']}")

    hardware = {
        "cuda": cuda.found,
        "vulkan": vulkan.found,
    }

    return checks, hardware

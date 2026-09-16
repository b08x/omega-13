"""Build transcribe-cpp with hardware-specific CMAKE_ARGS.

This is the long build step (10-15 minutes with CUDA). Cached by
checking if `transcribe` is importable in the target venv.
"""

import os
import shutil
import subprocess
import sys
import time

from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich.panel import Panel
from rich import box

from omega13.installer.ui import (
    console, step_header, status_done, status_skip, status_fail,
    status_info, status_warn, xdg_paths,
)
from omega13.installer.theme import COLORS


def _transcribe_importable() -> bool:
    """Check if transcribe-cpp is importable in the deployed Python venv."""
    paths = xdg_paths()
    venv_python = os.path.join(paths["dest_dir"], ".venv", "bin", "python")
    if not os.path.exists(venv_python):
        return False
    
    try:
        result = subprocess.run(
            [venv_python, "-c", "import transcribe_cpp"],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _resource_limited_available() -> bool:
    """Check if resource-limiting tools are available."""
    return all(shutil.which(cmd) for cmd in ("nice", "taskset", "cpulimit"))


def build_transcribe(
    hardware: dict[str, bool],
    force: bool = False,
    step_num: int = 3,
    total_steps: int = 7,
) -> bool:
    """Build and install transcribe-cpp via uv pip install.

    Args:
        hardware: Dict with 'cuda' and 'vulkan' bool keys from preflight.
        force: If True, rebuild even if already importable.
        step_num: Step number for display.
        total_steps: Total number of steps for display.

    Returns:
        True if transcribe-cpp is available after this step.
    """
    step_header(step_num, "Build transcribe-cpp (speech recognition)", total_steps)

    if _transcribe_importable() and not force:
        status_skip("transcribe-cpp already installed")
        return True

    # Build CMAKE_ARGS
    cmake_args = ["-DTRANSCRIBE_BUILD_SHARED=ON"]

    if hardware.get("cuda"):
        cmake_args.append("-DTRANSCRIBE_CUDA=ON")
        # Find nvcc
        nvcc_path = shutil.which("nvcc")
        if not nvcc_path:
            nvcc_path = "/usr/local/cuda/bin/nvcc"
        if os.path.exists(nvcc_path):
            cmake_args.append(f"-DCMAKE_CUDA_COMPILER={nvcc_path}")
        status_info(f"CUDA enabled (nvcc: {nvcc_path})")
    else:
        status_info("CUDA not detected — building CPU-only")

    if hardware.get("vulkan"):
        cmake_args.append("-DTRANSCRIBE_VULKAN=ON")
        status_info("Vulkan enabled")

    cmake_args_str = " ".join(cmake_args)
    env = os.environ.copy()
    env["CMAKE_ARGS"] = cmake_args_str

    # Show build config
    config_parts = []
    if hardware.get("cuda"):
        config_parts.append(f"[success]CUDA: ON[/success]")
    else:
        config_parts.append(f"[dim]CUDA: OFF[/dim]")
    if hardware.get("vulkan"):
        config_parts.append(f"[success]Vulkan: ON[/success]")
    else:
        config_parts.append(f"[dim]Vulkan: OFF[/dim]")

    console.print(f"   Build config: {' │ '.join(config_parts)}")
    console.print(f"   [cmd]CMAKE_ARGS={cmake_args_str}[/cmd]")

    # Build command
    if _resource_limited_available():
        install_cmd = [
            "nice", "-n", "19",
            "taskset", "-c", "0-3",
            "cpulimit", "-l", "150", "--",
            "uv", "pip", "install", "transcribe-cpp",
        ]
        status_info("Building with resource limits (this may take 10-15 minutes)")
    else:
        install_cmd = ["uv", "pip", "install", "transcribe-cpp"]
        status_warn("Building without resource limits — may consume significant CPU")
        status_info("This may take 10-15 minutes")

    # Run with live elapsed timer
    start_time = time.time()
    spinner = Spinner("dots", text=Text(
        "uv pip install transcribe-cpp",
        style=f"{COLORS['text_2']}",
    ))

    paths = xdg_paths()
    process = subprocess.Popen(
        install_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        cwd=paths["dest_dir"],
    )

    with Live(spinner, console=console, refresh_per_second=4) as live:
        while process.poll() is None:
            elapsed = time.time() - start_time
            minutes, seconds = divmod(int(elapsed), 60)
            spinner.text = Text.from_markup(
                f"uv pip install transcribe-cpp   "
                f"[progress.elapsed]\\[elapsed: {minutes}:{seconds:02d}][/progress.elapsed]"
            )
            time.sleep(0.25)

    elapsed = time.time() - start_time
    minutes, seconds = divmod(int(elapsed), 60)

    if process.returncode != 0:
        stderr = process.stderr.read() if process.stderr else ""
        status_fail(f"Build failed after {minutes}m {seconds}s")
        if stderr:
            console.print(Panel(
                stderr[-500:],  # Last 500 chars of error
                title="[danger]Build Error[/danger]",
                border_style=f"{COLORS['danger']}",
                box=box.ROUNDED,
            ))
        return False

    status_done(f"transcribe-cpp installed in {minutes}m {seconds}s")
    return True

"""Main orchestrator for the omega13 installer.

Sequences the install steps in order:
  1. Preflight checks
  2. Build ydotool
  3. Build transcribe-cpp
  4. Deploy application
  5. Install systemd service
  6. Install GNOME extension
  7. Summary
"""

import sys

from omega13.installer.ui import (
    console, banner, step_header, status_done, status_fail,
    status_info, show_command, completion_panel, xdg_paths,
)
from omega13.installer.steps.preflight import run_preflight
from omega13.installer.steps.ydotool import build_ydotool
from omega13.installer.steps.transcribe import build_transcribe
from omega13.installer.steps.deploy import deploy_app
from omega13.installer.steps.systemd import install_systemd_service
from omega13.installer.steps.gnome import install_gnome_extension
from omega13.installer.uninstall import run_uninstall


TOTAL_STEPS = 7


def run_installer(force: bool = False) -> int:
    """Run the full installation pipeline.

    Args:
        force: If True, bypass caches and rebuild everything.

    Returns:
        0 on success, 1 on failure.
    """
    banner()

    if force:
        status_info("--force: rebuilding all cached components")

    # Step 1: Preflight
    checks, hardware = run_preflight(step_num=1, total_steps=TOTAL_STEPS)

    missing_required = [c for c in checks if not c.found and c.required]
    if missing_required:
        console.print()
        status_fail("Cannot proceed — install missing dependencies first")
        status_info("The bootstrap script (install.sh) should have installed these.")
        status_info("Run: ./install.sh to retry system dependency installation.")
        return 1

    # Step 2: Build ydotool
    if not build_ydotool(force=force, step_num=2, total_steps=TOTAL_STEPS):
        status_fail("ydotool build failed — text injection will not work")
        # Non-fatal: continue without ydotool

    # Step 3: Deploy application (creates the final .venv)
    if not deploy_app(force=force, step_num=3, total_steps=TOTAL_STEPS):
        status_fail("Deployment failed")
        return 1

    # Step 4: Build transcribe-cpp (must happen in the deployed .venv)
    if not build_transcribe(
        hardware=hardware,
        force=force,
        step_num=4,
        total_steps=TOTAL_STEPS,
    ):
        status_fail("transcribe-cpp build failed — local transcription unavailable")
        # Non-fatal: Groq cloud backend still works

    # Step 5: Install systemd service
    if not install_systemd_service(step_num=5, total_steps=TOTAL_STEPS):
        status_fail("Systemd service installation failed")
        # Non-fatal: can still run manually

    # Step 6: GNOME extension
    if not install_gnome_extension(step_num=6, total_steps=TOTAL_STEPS):
        status_fail("GNOME extension installation failed")
        # Non-fatal

    # Step 7: Summary
    step_header(7, "Summary", TOTAL_STEPS)

    paths = xdg_paths()
    completion_panel([
        "Start:    systemctl --user enable --now omega13",
        "Toggle:   omega13 --toggle",
        "Models:   just model dl",
        "Status:   omega13 --status",
        "",
        f"App:      {paths['dest_dir']}",
        f"Config:   {paths['config_dir']}",
    ])

    return 0


def run_uninstaller() -> int:
    """Run the uninstaller.

    Returns:
        0 always.
    """
    run_uninstall()
    return 0

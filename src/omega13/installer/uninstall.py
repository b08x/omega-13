"""Uninstall omega13 — clean removal with confirmation."""

import os
import shutil
import subprocess

from omega13.installer.ui import (
    console, uninstall_banner, step_header, status_done, status_skip,
    status_fail, status_info, status_warn, confirm, show_path,
    removal_panel, xdg_paths,
)


def run_uninstall() -> None:
    """Run the interactive uninstaller."""
    uninstall_banner()

    paths = xdg_paths()

    # Check if anything is installed
    has_service = os.path.isfile(os.path.join(paths["systemd_dir"], "omega13.service"))
    has_symlink = os.path.islink(paths["bin_link"])
    has_app = os.path.isdir(paths["dest_dir"])
    has_config = os.path.isdir(paths["config_dir"])

    if not any([has_service, has_symlink, has_app]):
        status_info("No omega13 installation found")
        return

    # Confirmation
    if not confirm("Remove Omega-13 from this system?", default=False):
        status_info("Uninstallation cancelled")
        return

    step = 0
    total = sum([has_service, has_symlink, has_app]) + 1  # +1 for optional data

    # Step 1: Stop and disable systemd service
    if has_service:
        step += 1
        step_header(step, "Stop and remove systemd service", total)

        try:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", "omega13"],
                capture_output=True, timeout=30,
            )
            status_done("Service stopped and disabled")
        except (subprocess.SubprocessError, FileNotFoundError):
            status_warn("Could not stop service (may not be running)")

        service_file = os.path.join(paths["systemd_dir"], "omega13.service")
        try:
            os.remove(service_file)
            status_done(f"Removed {service_file}")
        except OSError:
            status_warn(f"Could not remove {service_file}")

        try:
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True, timeout=30,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Step 2: Remove symlink
    if has_symlink:
        step += 1
        step_header(step, "Remove command symlink", total)

        try:
            os.unlink(paths["bin_link"])
            status_done(f"Removed {paths['bin_link']}")
        except OSError as e:
            status_warn(f"Could not remove symlink: {e}")

    # Step 3: Remove application directory
    if has_app:
        step += 1
        step_header(step, "Remove application files", total)

        try:
            shutil.rmtree(paths["dest_dir"])
            status_done(f"Removed {paths['dest_dir']}")
        except OSError as e:
            status_fail(f"Could not remove app directory: {e}")

    # Step 4: Optionally remove config and models
    step += 1
    step_header(step, "User data", total)

    if has_config:
        if confirm("Also remove configuration and downloaded models?", default=False):
            try:
                shutil.rmtree(paths["config_dir"])
                status_done(f"Removed {paths['config_dir']}")
            except OSError as e:
                status_warn(f"Could not remove config: {e}")

            model_dir = paths["model_dir"]
            if os.path.isdir(model_dir):
                try:
                    shutil.rmtree(model_dir)
                    status_done(f"Removed {model_dir}")
                except OSError as e:
                    status_warn(f"Could not remove models: {e}")
        else:
            status_info("Configuration and models preserved")
    else:
        status_skip("No user configuration found")

    # Remove GNOME extension
    ext_dir = os.path.join(
        os.path.expanduser("~"),
        ".local", "share", "gnome-shell", "extensions",
        "omega13@b08x.github.io",
    )
    if os.path.isdir(ext_dir):
        try:
            shutil.rmtree(ext_dir)
            status_done("Removed GNOME extension")
        except OSError:
            status_warn("Could not remove GNOME extension")

    removal_panel()

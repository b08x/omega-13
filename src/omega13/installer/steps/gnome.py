"""Install the GNOME Shell extension for native OSD.

Copies extension files to the user's GNOME extensions directory.
Only runs if the current desktop is GNOME.
"""

import os
import shutil

from omega13.installer.ui import (
    console, step_header, status_done, status_skip, status_fail,
    status_info, show_path, show_command, xdg_paths,
)


EXTENSION_UUID = "omega13@b08x.github.io"


def _is_gnome() -> bool:
    """Check if the current desktop environment is GNOME."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    return "GNOME" in desktop


def _find_extension_source() -> str | None:
    """Find the gnome-extension source directory in the project."""
    # Walk up from this module to find the project root
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        ext_dir = os.path.join(current, "gnome-extension", EXTENSION_UUID)
        if os.path.isdir(ext_dir):
            return ext_dir
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def install_gnome_extension(step_num: int = 6, total_steps: int = 7) -> bool:
    """Install the GNOME Shell extension.

    Args:
        step_num: Step number for display.
        total_steps: Total number of steps for display.

    Returns:
        True if extension was installed or step was skipped (not GNOME).
    """
    step_header(step_num, "GNOME Shell extension", total_steps)

    if not _is_gnome():
        status_skip("Not a GNOME desktop — skipping extension install")
        return True

    # Find source
    source_dir = _find_extension_source()
    if not source_dir:
        # Also check the deployed location
        paths = xdg_paths()
        alt_source = os.path.join(paths["dest_dir"], "gnome-extension", EXTENSION_UUID)
        if os.path.isdir(alt_source):
            source_dir = alt_source
        else:
            status_fail("GNOME extension source not found in project")
            return False

    # Destination
    dest_dir = os.path.join(
        os.path.expanduser("~"),
        ".local", "share", "gnome-shell", "extensions",
        EXTENSION_UUID,
    )

    # Copy
    os.makedirs(dest_dir, exist_ok=True)

    try:
        # Copy all files from source to destination
        for item in os.listdir(source_dir):
            src_path = os.path.join(source_dir, item)
            dst_path = os.path.join(dest_dir, item)

            if os.path.isdir(src_path):
                if os.path.exists(dst_path):
                    shutil.rmtree(dst_path)
                shutil.copytree(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)
    except OSError as e:
        status_fail(f"Failed to copy extension files: {e}")
        return False

    show_path("Extension", dest_dir)
    status_done("GNOME extension installed")
    status_info(f"Enable with:")
    show_command(f"gnome-extensions enable {EXTENSION_UUID}")

    return True

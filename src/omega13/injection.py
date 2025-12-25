"""
Injection utility module for typing transcription results into active windows.
Uses ydotool for cross-platform (X11/Wayland) input automation.
"""

import logging
import subprocess
import shutil
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def inject_text(text: str) -> Tuple[bool, Optional[str]]:
    """
    Inject text into the currently active window using ydotool.
    
    Args:
        text: The text content to type
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    if not text or not isinstance(text, str):
        return False, "Invalid text provided for injection"

    # 1. Check if ydotool is present
    ydotool_path = shutil.which("ydotool")
    if not ydotool_path:
        error_msg = "ydotool not found in PATH. Please install it to use text injection."
        logger.error(error_msg)
        return False, error_msg

    try:
        # 2. Run ydotool type
        # We use a list for subprocess.run to avoid shell injection issues
        # Note: ydotool type can be slow for very long strings
        result = subprocess.run(
            [ydotool_path, "type", text],
            capture_output=True,
            text=True,
            timeout=30  # Safety timeout
        )

        if result.returncode == 0:
            logger.info(f"Successfully injected {len(text)} characters via ydotool")
            return True, None
        else:
            error_msg = result.stderr.strip() if result.stderr else f"Exit code {result.returncode}"
            # Common error: ydotoold not running or permission denied on /dev/uinput
            if "failed to connect" in error_msg.lower():
                error_msg = "ydotoold daemon not running or unreachable"
            elif "permission denied" in error_msg.lower():
                error_msg = "Permission denied for /dev/uinput (check uinput group)"
                
            logger.warning(f"ydotool injection failed: {error_msg}")
            return False, error_msg

    except subprocess.TimeoutExpired:
        error_msg = "ydotool injection timed out"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = str(e)
        logger.exception("Unexpected error during text injection")
        return False, f"Injection error: {error_msg}"

def is_ydotool_available() -> bool:
    """
    Check if ydotool is installed and functional.
    
    Returns:
        True if ydotool is found and ydotoold is likely reachable
    """
    ydotool_path = shutil.which("ydotool")
    if not ydotool_path:
        return False
        
    try:
        # Just check help or version to see if it executes
        subprocess.run([ydotool_path, "--help"], capture_output=True, timeout=2)
        return True
    except Exception:
        return False

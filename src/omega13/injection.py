"""
Injection utility module for typing transcription results into active windows.
Uses ydotool for cross-platform (X11/Wayland) input automation.
"""

import logging
import os
import subprocess
import shutil
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def _get_ydotool_env() -> dict:
    """Get the environment variables for ydotool, setting YDOTOOL_SOCKET if needed."""
    env = os.environ.copy()
    
    user_socket = f"/run/user/{os.getuid()}/.ydotool_socket"
    tmp_socket = "/tmp/.ydotool_socket"
    
    current_socket = env.get("YDOTOOL_SOCKET")
    # If the current socket is set and we can write to it, use it
    if current_socket and os.path.exists(current_socket) and os.access(current_socket, os.W_OK):
        return env
        
    # Otherwise fallback to user socket if it's writable
    if os.path.exists(user_socket) and os.access(user_socket, os.W_OK):
        env["YDOTOOL_SOCKET"] = user_socket
    # Or tmp socket if it's writable
    elif os.path.exists(tmp_socket) and os.access(tmp_socket, os.W_OK):
        env["YDOTOOL_SOCKET"] = tmp_socket
            
    return env

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
        env = _get_ydotool_env()
        result = subprocess.run(
            [ydotool_path, "type", text],
            capture_output=True,
            text=True,
            timeout=30,  # Safety timeout
            env=env
        )

        if result.returncode == 0:
            logger.info(f"Successfully injected {len(text)} characters via ydotool")
            return True, None
        else:
            out_msg = result.stdout.strip() if result.stdout else ""
            err_msg = result.stderr.strip() if result.stderr else ""
            error_msg = err_msg or out_msg or f"Exit code {result.returncode}"
            
            # Common error: ydotoold not running or permission denied on socket
            if "failed to connect" in error_msg.lower():
                error_msg = f"ydotoold daemon not running or socket unreachable (socket={env.get('YDOTOOL_SOCKET', 'default')})"
            elif "permission denied" in error_msg.lower():
                error_msg = f"Permission denied for ydotool socket ({env.get('YDOTOOL_SOCKET', 'default')}) or /dev/uinput"
                
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
        env = _get_ydotool_env()
        subprocess.run([ydotool_path, "--help"], capture_output=True, timeout=2, env=env)
        return True
    except Exception:
        return False

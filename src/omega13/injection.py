"""
Injection utility module for typing transcription results into active windows.
Uses ydotool for cross-platform (X11/Wayland) input automation.
"""

import logging
import os
import subprocess
import shutil
import time
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

def _focus_whisp_window() -> Tuple[bool, Optional[str]]:
    """
    Locate and focus the window named "Whisp" using GNOME Shell D-Bus.
    Attempts to use the safe 'Activate Window By Title' extension first.
    Falls back to org.gnome.Shell.Eval if necessary.
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    
    # Attempt 1: Native Omega-13 GNOME Extension
    try:
        native_result = subprocess.run(
            [
                "busctl", "--user", "call", 
                "org.gnome.Shell", 
                "/org/gnome/Shell/Extensions/Omega13", 
                "org.gnome.Shell.Extensions.Omega13", 
                "FocusWindow", "s", "Whisp"
            ],
            capture_output=True,
            text=True,
            timeout=2
        )
        if native_result.returncode == 0:
            out = native_result.stdout.strip()
            if "true" in out.lower():
                logger.info("Successfully focused the 'Whisp' window via native Omega-13 extension")
                return True, None
            else:
                return False, "Whisp window not found via Omega-13 extension"
    except Exception as e:
        logger.debug(f"Omega-13 native extension not found or failed: {e}")

    # Attempt 2: Safe method using 'Activate Window By Title' extension
    try:
        safe_result = subprocess.run(
            [
                "busctl", "--user", "call", 
                "org.gnome.Shell", 
                "/de/lucaswerkmeister/ActivateWindowByTitle", 
                "de.lucaswerkmeister.ActivateWindowByTitle", 
                "activateBySubstring", "s", "Whisp"
            ],
            capture_output=True,
            text=True,
            timeout=2
        )
        if safe_result.returncode == 0:
            logger.info("Successfully focused the 'Whisp' window via ActivateWindowByTitle D-Bus extension")
            return True, None
    except Exception as e:
        logger.debug(f"ActivateWindowByTitle extension not found or failed: {e}")

    # Attempt 2: Fallback to JS Eval (Requires Unsafe Mode or Eval-GJS)
    script = (
        "var w = global.get_window_actors().find(a => a.meta_window && a.meta_window.get_title() === 'Whisp'); "
        "if (w) { w.meta_window.activate(global.get_current_time()); 'true'; } else { 'false'; }"
    )
    
    try:
        result = subprocess.run(
            [
                "gdbus", "call", "--session", 
                "--dest", "org.gnome.Shell", 
                "--object-path", "/org/gnome/Shell", 
                "--method", "org.gnome.Shell.Eval", 
                script
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            out = result.stdout.strip()
            if out.startswith("(true"):
                if "'true'" in out:
                    logger.info("Successfully focused the 'Whisp' window via D-Bus Eval")
                    return True, None
                elif "'false'" in out:
                    return False, "Whisp window not found"
                else:
                    return False, f"Unexpected D-Bus Eval result: {out}"
            else:
                return False, "GNOME Shell Eval is restricted (install 'Activate Window By Title' extension)"
        else:
            err = result.stderr.strip()
            return False, f"D-Bus call failed: {err}"
            
    except subprocess.TimeoutExpired:
        return False, "D-Bus call to GNOME Shell timed out"
    except Exception as e:
        return False, f"Error focusing Whisp window: {str(e)}"

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

    # Focus the "Whisp" window before injecting text
    focus_success, focus_error = _focus_whisp_window()
    if not focus_success:
        logger.error(f"Injection aborted: {focus_error}")
        return False, focus_error

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
        cmd = [ydotool_path, "type", text]
        logger.debug(f"Executing ydotool cmd: {cmd} with env: YDOTOOL_SOCKET={env.get('YDOTOOL_SOCKET', 'Not set')}")
        
        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # Safety timeout for long text injections
            env=env
        )
        exec_time = time.time() - start_time
        logger.debug(f"ydotool execution finished in {exec_time:.2f}s. Return code: {result.returncode}")
        logger.debug(f"ydotool stdout: {result.stdout.strip()}")
        if result.stderr:
            logger.debug(f"ydotool stderr: {result.stderr.strip()}")

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
            
            try:
                subprocess.run(["systemctl", "--user", "restart", "ydotoold"], timeout=5, check=False)
                logger.info("Restarted ydotoold to clear stuck keys.")
            except Exception as e_restart:
                logger.warning(f"Failed to restart ydotoold: {e_restart}")
            
            return False, error_msg

    except subprocess.TimeoutExpired:
        error_msg = "ydotool injection timed out"
        logger.error(error_msg)
        
        try:
            subprocess.run(["systemctl", "--user", "restart", "ydotoold"], timeout=5, check=False)
            logger.info("Restarted ydotoold to clear stuck keys after timeout.")
        except Exception as e_restart:
            logger.warning(f"Failed to restart ydotoold: {e_restart}")
            
        return False, error_msg
    except Exception as e:
        error_msg = str(e)
        logger.exception("Unexpected error during text injection")
        
        try:
            subprocess.run(["systemctl", "--user", "restart", "ydotoold"], timeout=5, check=False)
            logger.info("Restarted ydotoold to clear stuck keys after exception.")
        except Exception as e_restart:
            logger.warning(f"Failed to restart ydotoold: {e_restart}")
            
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

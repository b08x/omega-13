"""
Clipboard utility module for copying transcription results.
Provides cross-platform clipboard support with graceful degradation.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def copy_to_clipboard(text: str) -> Tuple[bool, Optional[str]]:
    """
    Copy text to system clipboard with error handling.

    Args:
        text: The text content to copy to clipboard

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        - (True, None) if copy succeeded
        - (False, error_message) if copy failed
    """
    if not text or not isinstance(text, str):
        return False, "Invalid text provided for clipboard copy"

    try:
        import pyperclip

        # Attempt to copy to clipboard
        pyperclip.copy(text)

        # Verify the copy operation (pyperclip provides this)
        # This will raise an exception if clipboard is unavailable
        copied = pyperclip.paste()

        if copied == text:
            logger.info(f"Successfully copied {len(text)} characters to clipboard")
            return True, None
        else:
            # Copy succeeded but verification failed (rare edge case)
            logger.warning("Clipboard copy completed but verification failed")
            return True, None  # Still return success since copy() didn't error

    except ImportError:
        error_msg = "pyperclip library not installed"
        logger.error(f"Clipboard copy failed: {error_msg}")
        return False, error_msg

    except Exception as e:
        # Handle various clipboard-related errors:
        # - No clipboard mechanism available (headless systems)
        # - Permission denied
        # - X11/Wayland/clipboard daemon issues
        error_msg = str(e)
        logger.warning(f"Failed to copy to clipboard: {error_msg}")
        return False, f"Clipboard unavailable: {error_msg}"


def is_clipboard_available() -> bool:
    """
    Check if clipboard functionality is available on this system.

    Returns:
        True if clipboard operations are likely to succeed, False otherwise
    """
    try:
        import pyperclip

        # Test with a small operation
        test_text = "test"
        pyperclip.copy(test_text)
        result = pyperclip.paste()

        return result == test_text

    except Exception as e:
        logger.debug(f"Clipboard availability check failed: {e}")
        return False

import logging
from typing import Callable, Optional

import os

logger = logging.getLogger(__name__)

IS_WAYLAND = os.environ.get('XDG_SESSION_TYPE') == 'wayland'

# Graceful degradation if pynput is missing or fails
try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    logger.warning("pynput not installed. Global hotkeys will be disabled.")
    PYNPUT_AVAILABLE = False

class GlobalHotkeyListener:
    """
    Listens for a global hotkey combination.
    """

    def __init__(self, hotkey_str: str, callback: Callable):
        self.raw_hotkey_str = hotkey_str
        self.callback = callback
        self.listener = None
        self.resolved_hotkey_str = self._resolve_hotkey(hotkey_str)

    def _resolve_hotkey(self, hotkey: str) -> Optional[str]:
        # 1. Normalize by removing all brackets first, then we'll add them back consistently
        # This prevents issues with mix formats like "<ctrl>+space"
        normalized = hotkey.replace('<', '').replace('>', '')

        # 2. Handle common key names and resolve to pynput format
        key_aliases = {
            "enter": "<enter>",
            "return": "<enter>",
            "space": "<space>",
            "esc": "<esc>",
            "escape": "<esc>",
            "tab": "<tab>",
            "backspace": "<backspace>",
            "delete": "<delete>",
            "insert": "<insert>",
            "up": "<up>",
            "down": "<down>",
            "left": "<left>",
            "right": "<right>",
            "home": "<home>",
            "end": "<end>",
            "page_up": "<page_up>",
            "page_down": "<page_down>",
        }

        if '+' in normalized:
            parts = normalized.split('+')
            resolved_parts = []
            for part in parts:
                p = part.strip().lower()
                if p in key_aliases:
                    resolved_parts.append(key_aliases[p])
                elif len(p) > 1:
                    resolved_parts.append(f"<{p}>")
                else:
                    resolved_parts.append(p)
            return "+".join(resolved_parts)

        lower_hotkey = normalized.strip().lower()
        if lower_hotkey in key_aliases:
            return key_aliases[lower_hotkey]

        # 2.5 If it's a simple single character, assume valid.
        if len(lower_hotkey) == 1:
            return lower_hotkey

        if len(lower_hotkey) > 1:
            logger.error(f"Could not resolve special key '{lower_hotkey}'. Global hotkey disabled.")
            return None
        
        return lower_hotkey



    def start(self) -> bool:
        """
        Start the global hotkey listener.
        Returns True if successful, False otherwise.
        """
        if not PYNPUT_AVAILABLE:
            return False

        if not self.resolved_hotkey_str:
            logger.warning(f"Cannot start listener: Hotkey '{self.raw_hotkey_str}' could not be resolved.")
            return False

        try:


            if IS_WAYLAND:
                logger.warning("Running on Wayland. Global hotkeys may not work unless the application has focus or specific permissions.")
            
            # Fallback to standard string-based GlobalHotKeys
            self.listener = keyboard.GlobalHotKeys({
                self.resolved_hotkey_str: self.callback
            })
            self.listener.start()
            logger.info(f"Global hotkey listener started: {self.resolved_hotkey_str}")
            return True

        except ValueError as e:
            logger.error(f"Invalid hotkey configuration '{self.resolved_hotkey_str}': {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to start global hotkey listener: {e}")
            return False

    def stop(self) -> None:
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass
            finally:
                self.listener = None
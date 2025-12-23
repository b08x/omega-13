import logging
import subprocess
import shutil
import re
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
        self.target_vk: Optional[int] = None
        self._last_pressed_vk: Optional[int] = None

    def _resolve_hotkey(self, hotkey: str) -> Optional[str]:
        """
        Resolve special keys to pynput-compatible format.
        """
        # 1. If it's a pynput format (<...> or + combination), assume valid.
        if '<' in hotkey and '>' in hotkey and not hotkey.startswith("XF86"):
             return hotkey

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

        if '+' in hotkey:
            parts = hotkey.split('+')
            resolved_parts = []
            for part in parts:
                p = part.strip().lower()
                if p in key_aliases:
                    resolved_parts.append(key_aliases[p])
                elif len(p) > 1 and not (p.startswith('<') and p.endswith('>')):
                    resolved_parts.append(f"<{p}>")
                else:
                    resolved_parts.append(p)
            return "+".join(resolved_parts)

        lower_hotkey = hotkey.strip().lower()
        if lower_hotkey in key_aliases:
            return key_aliases[lower_hotkey]

        # 2.5 If it's a simple single character, assume valid.
        if len(hotkey) == 1:
            return hotkey

        # 3. Handle X11 Keysyms (starting with XF86 or similar)
        if PYNPUT_AVAILABLE and shutil.which('xmodmap'):
            # Try a few common variations if the provided one doesn't work
            variations = [hotkey]
            if hotkey == "XF86AudioRecord":
                variations.append("XF86Record")
            elif hotkey == "XF86Record":
                variations.append("XF86AudioRecord")

            for variant in variations:
                try:
                    # Run xmodmap -pke to get the keymap table
                    result = subprocess.run(['xmodmap', '-pke'], capture_output=True, text=True)
                    if result.returncode == 0:
                        # pattern matches: keycode 176 = XF86AudioRecord
                        pattern = r'keycode\s+(\d+)\s+=.*\b' + re.escape(variant) + r'\b'
                        match = re.search(pattern, result.stdout)
                        if match:
                            code = match.group(1)
                            logger.info(f"Resolved keysym '{variant}' to keycode <{code}>")
                            return f"<{code}>"
                except Exception as e:
                    logger.error(f"Failed to resolve key via xmodmap: {e}")

        # 4. Fallback: If we couldn't resolve an XF86 key, fail safely
        if hotkey.startswith("XF86") or len(hotkey) > 1:
            logger.error(f"Could not resolve special key '{hotkey}' to a keycode. Global hotkey disabled.")
            return None
        
        return hotkey

    def _on_press_raw(self, key):
        """
        Callback for raw listener. Checks if the pressed key matches our target VK.
        """
        try:
            pressed_vk = getattr(key, 'vk', None)
            
            # Reduce logging noise but keep enough for debugging
            if pressed_vk != self._last_pressed_vk:
                 # logger.debug(f"Key press: {key} (vk={pressed_vk})")
                 self._last_pressed_vk = pressed_vk

            if pressed_vk is not None and pressed_vk == self.target_vk:
                logger.info(f"Global hotkey triggered by VK: {pressed_vk}")
                self.callback()
        except Exception as e:
            logger.error(f"Error in raw key listener: {e}")

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
            # Check if we have a single raw keycode (e.g., "<175>")
            # In this case, we use a raw Listener instead of GlobalHotKeys for better reliability with media keys
            is_single_code = self.resolved_hotkey_str.startswith('<') and \
                             self.resolved_hotkey_str.endswith('>') and \
                             '+' not in self.resolved_hotkey_str
            
            if is_single_code:
                try:
                    # Extract 175 from <175>
                    self.target_vk = int(self.resolved_hotkey_str.strip('<>'))
                    self.listener = keyboard.Listener(on_press=self._on_press_raw)
                    self.listener.start()
                    logger.info(f"Raw key listener started for VK code: {self.target_vk}")
                    return True
                except ValueError:
                    logger.warning("Failed to parse raw keycode, falling back to GlobalHotKeys")

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
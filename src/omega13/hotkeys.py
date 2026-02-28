import asyncio
import logging
from typing import Callable, Optional

import os

logger = logging.getLogger(__name__)

IS_WAYLAND = os.environ.get('XDG_SESSION_TYPE') == 'wayland'

# D-Bus constants matching dbus_service.py
DBUS_SERVICE_NAME = "org.omega13.Recorder"
DBUS_OBJECT_PATH = "/org/omega13/Recorder"
DBUS_INTERFACE_NAME = "org.omega13.Recorder"

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
    
    On X11: Uses pynput for direct keyboard capture.
    On Wayland: pynput cannot capture global hotkeys reliably.
    Configure your desktop environment to run 'omega13 --toggle'
    which uses D-Bus IPC to toggle recording on the running instance.
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
                logger.warning(
                    "Running on Wayland. pynput global hotkeys are unreliable. "
                    "Configure your desktop environment to run 'omega13 --toggle' "
                    "as a system-wide hotkey for reliable D-Bus-based recording toggle."
                )
            
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


async def _dbus_toggle_async() -> str:
    """Call ToggleRecording() on the running Omega-13 D-Bus service.

    Returns:
        str: New recording state description

    Raises:
        ConnectionError: If no running Omega-13 instance found
        RuntimeError: If D-Bus call fails
    """
    try:
        from dbus_next.aio.message_bus import MessageBus
        from dbus_next.errors import DBusError
    except ImportError:
        raise RuntimeError("dbus-next not installed. Cannot toggle recording.")

    bus = None
    try:
        import asyncio
        
        # Connect to D-Bus with timeout
        bus = await asyncio.wait_for(
            MessageBus().connect(), timeout=3.0
        )
        
        # Introspect with timeout to prevent hanging
        introspection = await asyncio.wait_for(
            bus.introspect(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH), timeout=5.0
        )
        
        proxy = bus.get_proxy_object(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH, introspection)
        iface = proxy.get_interface(DBUS_INTERFACE_NAME)
        
        # Call method with timeout to prevent hanging
        is_recording = await asyncio.wait_for(
            iface.call_toggle_recording(), timeout=10.0
        )
        
        state = "recording" if is_recording else "stopped"
        return state
        
    except asyncio.TimeoutError:
        raise ConnectionError(
            "Timeout: Omega-13 instance found but not responding. "
            "The application may be frozen or busy."
        )
    except DBusError as e:
        if "NameHasNoOwner" in str(e) or "ServiceUnknown" in str(e):
            raise ConnectionError(
                "No running Omega-13 instance found. Start omega13 first."
            )
        else:
            raise ConnectionError(
                f"D-Bus communication error: {e}"
            )
    except asyncio.CancelledError:
        raise ConnectionError(
            "Operation cancelled (likely by Ctrl+C). Omega-13 may be starting up."
        )
    except Exception as e:
        raise RuntimeError(f"Failed to toggle recording via D-Bus: {e}")
    finally:
        # Ensure bus is properly disconnected
        if bus and hasattr(bus, 'disconnect'):
            try:
                bus.disconnect()
            except Exception:
                pass  # Ignore cleanup errors


def send_dbus_toggle() -> str:
    """Send ToggleRecording() to the running Omega-13 instance via D-Bus.

    Synchronous wrapper for the async D-Bus call.

    Returns:
        str: New recording state ("recording" or "stopped")

    Raises:
        ConnectionError: If no running Omega-13 instance found
        RuntimeError: If D-Bus call fails or dbus-next not installed
    """
    return asyncio.run(_dbus_toggle_async())


async def _dbus_get_state_async() -> str:
    """Get recording state from the running Omega-13 D-Bus service.

    Returns:
        str: Current recording state name

    Raises:
        ConnectionError: If no running Omega-13 instance found
        RuntimeError: If D-Bus call fails
    """
    try:
        from dbus_next.aio.message_bus import MessageBus
        from dbus_next.errors import DBusError
    except ImportError:
        raise RuntimeError("dbus-next not installed. Cannot query state.")

    bus = None
    try:
        import asyncio
        
        # Connect to D-Bus with timeout
        bus = await asyncio.wait_for(
            MessageBus().connect(), timeout=3.0
        )
        
        # Introspect with timeout
        introspection = await asyncio.wait_for(
            bus.introspect(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH), timeout=5.0
        )
        
        proxy = bus.get_proxy_object(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH, introspection)
        iface = proxy.get_interface(DBUS_INTERFACE_NAME)
        
        # Call method with timeout
        state = await asyncio.wait_for(
            iface.call_get_state(), timeout=5.0
        )
        
        return state
        
    except asyncio.TimeoutError:
        raise ConnectionError(
            "Timeout: Omega-13 instance found but not responding."
        )
    except DBusError as e:
        if "NameHasNoOwner" in str(e) or "ServiceUnknown" in str(e):
            raise ConnectionError(
                "No running Omega-13 instance found. Start omega13 first."
            )
        else:
            raise ConnectionError(
                f"D-Bus communication error: {e}"
            )
    except asyncio.CancelledError:
        raise ConnectionError("Operation cancelled.")
    except Exception as e:
        raise RuntimeError(f"Failed to get state via D-Bus: {e}")
    finally:
        if bus and hasattr(bus, 'disconnect'):
            try:
                bus.disconnect()
            except Exception:
                pass


def get_dbus_state() -> str:
    """Get current recording state from a running Omega-13 instance.

    Synchronous wrapper for the async D-Bus call.

    Returns:
        str: Current recording state

    Raises:
        ConnectionError: If no running Omega-13 instance found
        RuntimeError: If D-Bus call fails or dbus-next not installed
    """
    return asyncio.run(_dbus_get_state_async())
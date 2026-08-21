import logging
import subprocess
import shutil
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class DesktopNotifier:
    """
    Handles sending desktop notifications using system utilities (notify-send).
    """

    def __init__(self, app_name: str = "Omega-13"):
        self.app_name = app_name
        self.notify_send_path = shutil.which("notify-send")
        if not self.notify_send_path:
            logger.warning("notify-send not found. Desktop notifications will be disabled.")

    def notify(self, title: str, message: str, urgency: str = "normal", timeout: int = 2000) -> None:
        """
        Send a desktop notification.
        
        Args:
            title: The summary/title of the notification.
            message: The body of the notification.
            urgency: 'low', 'normal', or 'critical'.
            timeout: Expiration time in milliseconds (default 2s).
        """
        if not self.notify_send_path:
            return

        try:
            # Construct the command
            # -a app_name: Application name
            # -u urgency: Urgency level
            # -t timeout: Expiration time in ms
            cmd = [
                self.notify_send_path,
                "-a", self.app_name,
                "-u", urgency,
                "-t", str(timeout),
                title,
                message
            ]
            
            subprocess.run(cmd, check=False)
            logger.debug(f"Sent notification: {title} - {message}")

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    def play_sound(self, sound_name: str = "device-added") -> None:
        """
        Play a short notification sound using paplay and standard freedesktop sounds.
        
        Args:
            sound_name: The base name of the sound in /usr/share/sounds/freedesktop/stereo/
                        (e.g., 'device-added', 'device-removed', 'complete')
        """
        sound_path = Path(f"/usr/share/sounds/freedesktop/stereo/{sound_name}.oga")
        if not sound_path.exists():
            # Fallback to beep if specific file doesn't exist
            sound_path = Path("/usr/share/sounds/freedesktop/stereo/bell.oga")
            
        if not sound_path.exists():
            return
            
        paplay_path = shutil.which("paplay")
        if not paplay_path:
            return
            
        try:
            # Run asynchronously so we don't block
            subprocess.Popen(
                [paplay_path, str(sound_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            logger.debug(f"Failed to play sound: {e}")

import json
from pathlib import Path
from typing import Any, Optional, Dict
import jack
import logging

logger = logging.getLogger(__name__)

# --- Type Aliases ---
ConfigDict = Dict[str, Any]

class ConfigManager:
    """Manages persistent configuration for Omega-13."""

    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_dir = Path.home() / ".config" / "omega13"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_path = config_dir / "config.json"
        else:
            self.config_path = config_path

        self.config = self._load_config()

    def _load_config(self) -> ConfigDict:
        """Load configuration from disk, return defaults if not found."""
        default_config = {
            "version": 2,
            "input_ports": None,
            "save_path": str(Path.cwd()),
            "global_hotkey": "<ctrl>+<alt>+space",  # Default global shortcut updated to Ctrl+Alt+Space
            "transcription": {
                "enabled": True,
                "auto_transcribe": True,
                "server_url": "http://localhost:8080",
                "inference_path": "/inference",
                "model_size": "large-v3-turbo",
                "save_to_file": True,
                "copy_to_clipboard": False,
                "inject_to_active_window": False
            },
            "desktop_notifications": True,
            "sessions": {
                "temp_root": "/tmp/omega13",
                "default_save_location": str(Path.home() / "Recordings"),
                "auto_cleanup_days": 7
            },
            "auto_record": {
                "enabled": False,
                "begin_threshold_db": -35.0,
                "end_threshold_db": -35.0,
                "silence_duration_seconds": 10.0
            }
        }
        
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # Merge defaults for missing keys (simple shallow merge)
                    if "transcription" not in config:
                        config["transcription"] = default_config["transcription"]
                    if "sessions" not in config:
                        config["sessions"] = default_config["sessions"]
                    if "global_hotkey" not in config:
                        config["global_hotkey"] = default_config["global_hotkey"]
                    if "auto_record" not in config:
                        config["auto_record"] = default_config["auto_record"]
                    
                    # Ensure inference_path exists if transcription exists
                    if "transcription" in config and "inference_path" not in config["transcription"]:
                        config["transcription"]["inference_path"] = default_config["transcription"]["inference_path"]
                        
                    return config
            return default_config
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load config: {e}")
            return default_config

    def save_config(self, config: ConfigDict) -> bool:
        """Save configuration to disk."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except IOError as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def get_input_ports(self) -> list[str] | None:
        return self.config.get("input_ports")

    def set_input_ports(self, ports: list[str]) -> None:
        self.config["input_ports"] = ports
        self.save_config(self.config)

    def get_save_path(self) -> Path:
        path_str = self.config.get("save_path")
        if path_str:
            path = Path(path_str)
            if path.exists() and path.is_dir():
                return path
        return Path.cwd()

    def set_save_path(self, path: str | Path):
        self.config["save_path"] = str(path)
        self.save_config(self.config)
        
    def get_global_hotkey(self) -> str:
        """Get the global hotkey combination string."""
        return self.config.get("global_hotkey", "<ctrl>+<alt>+space")

    def get_desktop_notifications_enabled(self) -> bool:
        """Check if desktop notifications are enabled."""
        return self.config.get("desktop_notifications", True)

    def validate_ports_exist(self, client: jack.Client) -> tuple[bool, list[str]]:
        saved_ports = self.get_input_ports()
        if not saved_ports:
            return True, []

        all_ports = client.get_ports()
        available_names = [port.name for port in all_ports]
        missing = [p for p in saved_ports if p not in available_names]

        return len(missing) == 0, missing

    # Transcription Getters/Setters
    def get_transcription_enabled(self) -> bool:
        return self.config.get("transcription", {}).get("enabled", True)

    def get_auto_transcribe(self) -> bool:
        return self.config.get("transcription", {}).get("auto_transcribe", True)

    def get_transcription_model(self) -> str:
        return self.config.get("transcription", {}).get("model_size", "large-v3-turbo")

    def get_save_transcription_to_file(self) -> bool:
        return self.config.get("transcription", {}).get("save_to_file", True)

    def get_copy_to_clipboard(self) -> bool:
        """Get whether to copy transcription results to clipboard."""
        return self.config.get("transcription", {}).get("copy_to_clipboard", False)

    def get_transcription_server_url(self) -> str:
        """Get the whisper-server URL."""
        return self.config.get("transcription", {}).get("server_url", "http://localhost:8080")

    def set_transcription_server_url(self, url: str) -> None:
        """Set the whisper-server URL."""
        if "transcription" not in self.config:
            self.config["transcription"] = {}
        self.config["transcription"]["server_url"] = url
        self.save_config(self.config)

    def get_transcription_inference_path(self) -> str:
        """Get the whisper-server inference path."""
        return self.config.get("transcription", {}).get("inference_path", "/inference")

    def set_transcription_inference_path(self, path: str) -> None:
        """Set the whisper-server inference path."""
        if "transcription" not in self.config:
            self.config["transcription"] = {}
        self.config["transcription"]["inference_path"] = path
        self.save_config(self.config)

    def get_inject_to_active_window(self) -> bool:
        """Get whether to inject transcription results to the active window."""
        return self.config.get("transcription", {}).get("inject_to_active_window", False)

    def set_copy_to_clipboard(self, enabled: bool) -> None:
        """Set whether to copy transcription results to clipboard."""
        if "transcription" not in self.config:
            self.config["transcription"] = {}
        self.config["transcription"]["copy_to_clipboard"] = enabled
        self.save_config(self.config)

    def set_inject_to_active_window(self, enabled: bool) -> None:
        """Set whether to inject transcription results to the active window."""
        if "transcription" not in self.config:
            self.config["transcription"] = {}
        self.config["transcription"]["inject_to_active_window"] = enabled
        self.save_config(self.config)

    # Session Getters
    def get_session_temp_root(self) -> Path:
        """Get temporary root directory for sessions."""
        temp_root = self.config.get("sessions", {}).get("temp_root", "/tmp/omega13")
        return Path(temp_root)

    def get_default_save_location(self) -> Path:
        """Get default location for saving sessions."""
        save_loc = self.config.get("sessions", {}).get("default_save_location")
        if not save_loc:
            save_loc = str(Path.home() / "Recordings")

        path = Path(save_loc)
        # Create directory if it doesn't exist
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_auto_cleanup_days(self) -> int:
        """Get number of days before auto-cleanup of temp sessions."""
        return self.config.get("sessions", {}).get("auto_cleanup_days", 7)

    # Auto-Record Getters/Setters
    def get_auto_record_enabled(self) -> bool:
        """Get whether auto-record mode is enabled."""
        return self.config.get("auto_record", {}).get("enabled", False)

    def set_auto_record_enabled(self, enabled: bool) -> None:
        """Set whether auto-record mode is enabled."""
        if "auto_record" not in self.config:
            self.config["auto_record"] = {}
        self.config["auto_record"]["enabled"] = enabled
        self.save_config(self.config)

    def get_auto_record_begin_threshold(self) -> float:
        """Get auto-record begin threshold in dB."""
        return self.config.get("auto_record", {}).get("begin_threshold_db", -35.0)

    def get_auto_record_end_threshold(self) -> float:
        """Get auto-record end (silence) threshold in dB."""
        return self.config.get("auto_record", {}).get("end_threshold_db", -35.0)

    def get_auto_record_silence_duration(self) -> float:
        """Get auto-record silence duration in seconds."""
        return self.config.get("auto_record", {}).get("silence_duration_seconds", 10.0)
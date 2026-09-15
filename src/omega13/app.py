import argparse
import logging
import os
import signal
import sys
from pathlib import Path

from .headless_service import main_headless
from .hotkeys import send_dbus_toggle
from .pidfile import read_pid, is_stale

def main():
    parser = argparse.ArgumentParser(description="Omega-13 retroactive audio recorder daemon")
    parser.add_argument(
        "--toggle", action="store_true", help="Toggle recording on a running instance via D-Bus"
    )
    parser.add_argument(
        "--stop", action="store_true", help="Stop a running instance"
    )
    # Keeping these for backwards compatibility with any existing scripts, but they are no-ops or default
    parser.add_argument("--daemon", action="store_true", default=True, help="Run as background daemon (default)")
    parser.add_argument("--no-daemon", action="store_false", dest="daemon", help="Run in foreground without daemonizing")
    parser.add_argument("--config", action="store_true", help="Launch the interactive configuration wizard")
    parser.add_argument("--log-level", default="INFO", help="Set logging level")
    args = parser.parse_args()

    # Configure logging
    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    # We configure root logger for the foreground mode
    logging.basicConfig(level=numeric_level)

    if args.toggle:
        try:
            state = send_dbus_toggle()
            print(f"Toggle signal sent. Recording state: {state}")
            sys.exit(0)
        except ConnectionError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)

    if args.stop:
        pid_file = Path("/tmp/omega13.pid")
        if not pid_file.exists():
            print("Omega-13 is not running (PID file not found).")
            sys.exit(0)
            
        pid = read_pid(pid_file)
        if pid is None or is_stale(pid_file):
            print("Omega-13 is not running (stale or invalid PID file).")
            try:
                pid_file.unlink()
            except OSError:
                pass
            sys.exit(0)
            
        try:
            print(f"Stopping Omega-13 (PID {pid})...")
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            print("Process not found.")
            try:
                pid_file.unlink()
            except OSError:
                pass
        sys.exit(0)

        print("Falling back to headless daemon mode.")

    if args.config:
        try:
            from .config_ui import run_config_ui
            run_config_ui()
            sys.exit(0)
        except ImportError as e:
            print(f"Error: Could not load configuration UI. Make sure 'rich' is installed. ({e})")
            sys.exit(1)

    # Main execution (daemon mode handles its own PID file internally)
    print("Starting Omega-13 headless service...")
    main_headless()

if __name__ == "__main__":
    main()

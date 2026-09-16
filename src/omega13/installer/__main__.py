"""Entry point for `python -m omega13.installer`.

Usage:
    python -m omega13.installer [--force] [--uninstall]

Future RPM usage:
    omega13 setup [--force]
    omega13 setup --uninstall
"""

import argparse
import os
import sys

from omega13.installer.main import run_installer, run_uninstaller


def main() -> None:
    """Parse arguments and dispatch to installer or uninstaller."""
    parser = argparse.ArgumentParser(
        prog="omega13-installer",
        description="Omega-13 installation and deployment manager",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild cached components (ydotool, transcribe-cpp) and reset config",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove omega13 from this system",
    )

    args = parser.parse_args()

    # Refuse to run as root
    if os.geteuid() == 0:
        print("❌ This installer should not be run as root.")
        print("   Run as your normal user. sudo will be requested only when needed.")
        sys.exit(1)

    if args.uninstall:
        sys.exit(run_uninstaller())
    else:
        sys.exit(run_installer(force=args.force))


if __name__ == "__main__":
    main()

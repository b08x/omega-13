"""Omega-13 installer — Rich-powered setup and deployment.

Can be invoked as:
  python -m omega13.installer [--force] [--uninstall]

Or programmatically:
  from omega13.installer import run_installer
  run_installer(force=False)
"""

from omega13.installer.main import run_installer, run_uninstaller

__all__ = ["run_installer", "run_uninstaller"]

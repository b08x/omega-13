"""
Obsidian CLI integration for omega-13.

This module provides safe integration with Obsidian CLI for writing transcription
results to daily notes. Follows Poka-Yoke principles for error prevention.
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ObsidianResult:
    """Result container for Obsidian CLI operations."""
    success: bool
    message: str
    error_code: Optional[int] = None


class ObsidianCLI:
    """Safe wrapper for Obsidian CLI operations."""

    def __init__(self):
        self._cli_available: Optional[bool] = None
        self._last_check_time = 0

    def is_available(self, force_check: bool = False) -> bool:
        """
        Check if Obsidian CLI is available and properly configured.

        Poka-Yoke: Validates CLI availability before any operations.
        Caches result to avoid repeated subprocess calls.
        """
        import time

        # Cache for 30 seconds to avoid repeated checks
        current_time = time.time()
        if (not force_check and
            self._cli_available is not None and
            current_time - self._last_check_time < 30):
            return self._cli_available

        try:
            # Try to run obsidian help - this will fail if CLI is not available
            result = subprocess.run(
                ["obsidian", "help"],
                capture_output=True,
                text=True,
                timeout=10  # Prevent hanging
            )

            self._cli_available = result.returncode == 0
            self._last_check_time = current_time

            if not self._cli_available:
                logger.warning(f"Obsidian CLI check failed: {result.stderr}")

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"Obsidian CLI not available: {e}")
            self._cli_available = False
            self._last_check_time = current_time

        return self._cli_available

    def open_daily_note(self) -> ObsidianResult:
        """
        Open today's daily note in Obsidian.

        Poka-Yoke: Validates CLI before attempting operation.
        """
        if not self.is_available():
            return ObsidianResult(
                success=False,
                message="Obsidian CLI not available. Ensure Obsidian is installed and CLI is enabled."
            )

        try:
            result = subprocess.run(
                ["obsidian", "daily"],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                logger.info("Successfully opened daily note")
                return ObsidianResult(success=True, message="Daily note opened")
            else:
                error_msg = result.stderr.strip() or "Failed to open daily note"
                logger.error(f"Failed to open daily note: {error_msg}")
                return ObsidianResult(
                    success=False,
                    message=error_msg,
                    error_code=result.returncode
                )

        except subprocess.TimeoutExpired:
            return ObsidianResult(
                success=False,
                message="Timeout opening daily note"
            )
        except Exception as e:
            logger.error(f"Unexpected error opening daily note: {e}")
            return ObsidianResult(
                success=False,
                message=f"Unexpected error: {str(e)}"
            )

    def append_to_daily_note(self, content: str) -> ObsidianResult:
        """
        Append content to today's daily note.

        Poka-Yoke:
        - Validates CLI availability
        - Sanitizes content to prevent injection
        - Uses safe subprocess execution
        """
        if not self.is_available():
            return ObsidianResult(
                success=False,
                message="Obsidian CLI not available"
            )

        if not content or not content.strip():
            return ObsidianResult(
                success=False,
                message="Cannot append empty content"
            )

        # Sanitize content to prevent issues
        sanitized_content = self._sanitize_content(content.strip())

        try:
            # Use the daily:append command with content parameter
            result = subprocess.run(
                ["obsidian", "daily:append", f"content={sanitized_content}"],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                logger.info(f"Successfully appended to daily note: {sanitized_content[:50]}...")
                return ObsidianResult(
                    success=True,
                    message="Content appended to daily note"
                )
            else:
                error_msg = result.stderr.strip() or "Failed to append to daily note"
                logger.error(f"Failed to append to daily note: {error_msg}")
                return ObsidianResult(
                    success=False,
                    message=error_msg,
                    error_code=result.returncode
                )

        except subprocess.TimeoutExpired:
            return ObsidianResult(
                success=False,
                message="Timeout appending to daily note"
            )
        except Exception as e:
            logger.error(f"Unexpected error appending to daily note: {e}")
            return ObsidianResult(
                success=False,
                message=f"Unexpected error: {str(e)}"
            )

    def _sanitize_content(self, content: str) -> str:
        """
        Sanitize content for safe CLI usage.

        Poka-Yoke: Prevents shell injection and formatting issues.
        """
        # Add timestamp prefix for organization
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Ensure content is on a new line with timestamp
        sanitized = f"\n[{timestamp}] {content}"

        # Basic sanitization (could be expanded)
        # Remove or escape problematic characters that could break CLI
        sanitized = sanitized.replace('"', "'").replace('`', "'")

        return sanitized

    def open_daily_note_if_enabled(self) -> ObsidianResult:
        """
        Open daily note only if CLI is available.
        Used for optional launch behavior.
        """
        if self.is_available():
            return self.open_daily_note()
        else:
            return ObsidianResult(
                success=False,
                message="Obsidian CLI not configured, skipping daily note open"
            )


# Global instance for app-wide usage
obsidian_cli = ObsidianCLI()
"""
PID file management for daemon uniqueness and clean shutdown.

Provides atomic PID file creation, stale PID detection, and cleanup utilities
to prevent double-launch conflicts for daemon processes.
"""

import os
import atexit
import logging
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PidFileError(Exception):
    """Raised when PID file operations fail."""

    pass


class PidAlreadyRunningError(PidFileError):
    """Raised when another instance is already running."""

    def __init__(self, pid: int, pid_file: Path):
        self.pid = pid
        self.pid_file = pid_file
        super().__init__(f"Daemon already running with PID {pid} (PID file: {pid_file})")


def is_stale(pid_file: Path) -> bool:
    """
    Check if a PID file contains a stale (dead) process ID.

    Args:
        pid_file: Path to the PID file.

    Returns:
        True if the PID file is missing, empty, contains invalid data,
        or the process is no longer running. False if the process is alive.
    """
    if not pid_file.exists():
        return True

    try:
        pid_text = pid_file.read_text().strip()
        if not pid_text:
            return True
        pid = int(pid_text)
    except (ValueError, OSError):
        logger.warning(f"Invalid PID file content: {pid_file}")
        return True

    if pid <= 0:
        return True

    # Check if process exists using signal 0 (existence check)
    try:
        os.kill(pid, 0)
        return False  # Process exists and we can signal it
    except ProcessLookupError:
        return True  # Process does not exist
    except PermissionError:
        # Process exists but owned by different user - treat as alive
        return False


def read_pid(pid_file: Path) -> Optional[int]:
    """
    Read PID from file if it exists and contains a valid PID.

    Args:
        pid_file: Path to the PID file.

    Returns:
        PID as integer, or None if file doesn't exist or contains invalid data.
    """
    if not pid_file.exists():
        return None

    try:
        pid_text = pid_file.read_text().strip()
        if not pid_text:
            return None
        return int(pid_text)
    except (ValueError, OSError):
        return None


def acquire_pid_file(pid_file: Path) -> int:
    """
    Atomically create a PID file with the current process ID.

    Uses atomic rename (write to .tmp then rename) to avoid race conditions.
    Checks for stale PID files and removes them before creating a new one.

    Args:
        pid_file: Path to the PID file to create.

    Returns:
        The current process ID.

    Raises:
        PidAlreadyRunningError: If another instance is already running.
        PidFileError: If the PID file cannot be created.
    """
    pid = os.getpid()

    # Ensure parent directory exists
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Check for existing PID file
    if pid_file.exists():
        existing_pid = read_pid(pid_file)
        if existing_pid is not None and not is_stale(pid_file):
            raise PidAlreadyRunningError(existing_pid, pid_file)
        # Stale PID file - remove it
        logger.warning(f"Removing stale PID file: {pid_file} (PID {existing_pid})")
        try:
            pid_file.unlink()
        except OSError as e:
            raise PidFileError(f"Failed to remove stale PID file {pid_file}: {e}") from e

    # Atomic write: write to .tmp then rename
    tmp_file = pid_file.with_suffix(".tmp")
    try:
        tmp_file.write_text(f"{pid}\n")
        tmp_file.rename(pid_file)  # atomic on same filesystem
    except OSError as e:
        # Clean up temp file on failure
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass
        raise PidFileError(f"Failed to create PID file {pid_file}: {e}") from e

    logger.info(f"PID file locked: {pid_file} (PID {pid})")
    return pid


def release_pid_file(pid_file: Path, expected_pid: Optional[int] = None) -> bool:
    """
    Remove the PID file if it matches the expected PID.

    Args:
        pid_file: Path to the PID file.
        expected_pid: If provided, only remove if the file contains this PID.
                      If None, remove regardless of content.

    Returns:
        True if the file was removed, False if it didn't exist or didn't match.
    """
    if not pid_file.exists():
        return False

    if expected_pid is not None:
        actual_pid = read_pid(pid_file)
        if actual_pid != expected_pid:
            logger.warning(
                f"PID file {pid_file} contains PID {actual_pid}, "
                f"expected {expected_pid}; not removing"
            )
            return False

    try:
        pid_file.unlink()
        logger.info(f"PID file removed: {pid_file}")
        return True
    except OSError as e:
        logger.error(f"Failed to remove PID file {pid_file}: {e}")
        return False


@contextmanager
def pid_file_context(pid_file: Path):
    """
    Context manager for PID file lifecycle.

    Acquires the PID file on entry, releases it on exit (even on exception).
    Raises PidAlreadyRunningError if another instance is running.

    Usage:
        with pid_file_context(Path("/tmp/mydaemon.pid")):
            run_daemon()

    Args:
        pid_file: Path to the PID file.

    Yields:
        The current process PID.

    Raises:
        PidAlreadyRunningError: If another instance is running.
    """
    pid = acquire_pid_file(pid_file)
    try:
        yield pid
    finally:
        release_pid_file(pid_file, expected_pid=pid)


class PidFile:
    """
    Context manager class for PID file management with automatic cleanup.

    Can be used as a context manager or with explicit acquire/release calls.
    Registers automatic cleanup via atexit on acquire.

    Example:
        pf = PidFile(Path("/tmp/mydaemon.pid"))
        with pf:
            run_daemon()
    """

    def __init__(self, pid_file: Path):
        self.pid_file = Path(pid_file)
        self._pid: Optional[int] = None
        self._acquired = False

    def acquire(self) -> int:
        """
        Acquire the PID file.

        Returns:
            The current process PID.

        Raises:
            PidAlreadyRunningError: If another instance is running.
            PidFileError: If the PID file cannot be created.
        """
        if self._acquired:
            raise PidFileError("PidFile already acquired")
        self._pid = acquire_pid_file(self.pid_file)
        self._acquired = True
        # Register atexit cleanup
        atexit.register(self.release)
        return self._pid

    def release(self) -> bool:
        """
        Release the PID file.

        Returns:
            True if released, False if not acquired or already released.
        """
        if not self._acquired:
            return False
        atexit.unregister(self.release)
        result = release_pid_file(self.pid_file, expected_pid=self._pid)
        self._acquired = False
        self._pid = None
        return result

    def __enter__(self) -> int:
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


class PidFileManager:
    """
    Simplified PID file manager for daemon processes.

    Provides a clean API for creating/removing PID files without context manager semantics.
    """

    def __init__(self, pid_file: Path):
        self.pid_file = Path(pid_file)
        self._pid: Optional[int] = None

    def create(self) -> int:
        """Create the PID file. Raises PidFileError if another instance is running."""
        self._pid = acquire_pid_file(self.pid_file)
        atexit.register(self.remove)
        return self._pid

    def remove(self) -> bool:
        """Remove the PID file. Returns True if removed."""
        if self._pid is None:
            return False
        atexit.unregister(self.remove)
        result = release_pid_file(self.pid_file, expected_pid=self._pid)
        self._pid = None
        return result
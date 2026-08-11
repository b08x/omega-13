"""
Unit tests for PID file management module.
"""

import os
import tempfile
import pytest
from pathlib import Path

from omega13.pidfile import (
    is_stale,
    read_pid,
    acquire_pid_file,
    release_pid_file,
    pid_file_context,
    PidFile,
    PidFileError,
    PidAlreadyRunningError,
)


class TestPidFileUtils:
    """Test basic PID file utility functions."""

    def test_read_pid_nonexistent(self, tmp_path: Path):
        """Reading PID from non-existent file returns None."""
        pid_file = tmp_path / "nonexistent.pid"
        assert read_pid(pid_file) is None

    def test_read_pid_valid(self, tmp_path: Path):
        """Reading valid PID file returns the PID."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("12345\n")
        assert read_pid(pid_file) == 12345

    def test_read_pid_invalid_content(self, tmp_path: Path):
        """Reading PID file with invalid content returns None."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("not-a-number\n")
        assert read_pid(pid_file) is None

    def test_read_pid_empty(self, tmp_path: Path):
        """Reading empty PID file returns None."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("")
        assert read_pid(pid_file) is None

    def test_is_stale_nonexistent(self, tmp_path: Path):
        """Non-existent PID file is considered stale."""
        pid_file = tmp_path / "nonexistent.pid"
        assert is_stale(pid_file) is True

    def test_is_stale_empty(self, tmp_path: Path):
        """Empty PID file is considered stale."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("")
        assert is_stale(pid_file) is True

    def test_is_stale_invalid_content(self, tmp_path: Path):
        """PID file with invalid content is considered stale."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("abc\n")
        assert is_stale(pid_file) is True

    def test_is_stale_dead_process(self, tmp_path: Path):
        """PID file with dead process PID is stale."""
        pid_file = tmp_path / "test.pid"
        # Use a PID that's very unlikely to exist
        pid_file.write_text("999999\n")
        assert is_stale(pid_file) is True

    def test_is_stale_current_process(self, tmp_path: Path):
        """PID file with current process PID is not stale."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text(f"{os.getpid()}\n")
        assert is_stale(pid_file) is False


class TestAcquirePidFile:
    """Test PID file acquisition."""

    def test_acquire_new_pid_file(self, tmp_path: Path):
        """Creating PID file for new process succeeds."""
        pid_file = tmp_path / "test.pid"
        pid = acquire_pid_file(pid_file)
        assert pid == os.getpid()
        assert pid_file.exists()
        assert pid_file.read_text().strip() == str(pid)

    def test_acquire_existing_stale_pid_file(self, tmp_path: Path):
        """Creating PID file over stale one succeeds."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("999999\n")  # Dead PID
        pid = acquire_pid_file(pid_file)
        assert pid == os.getpid()
        assert pid_file.read_text().strip() == str(pid)

    def test_acquire_existing_live_pid_file_raises(self, tmp_path: Path):
        """Creating PID file when live process exists raises error."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text(f"{os.getpid()}\n")

        with pytest.raises(PidAlreadyRunningError) as exc_info:
            acquire_pid_file(pid_file)

        assert exc_info.value.pid == os.getpid()
        assert exc_info.value.pid_file == pid_file

    def test_acquire_creates_parent_dirs(self, tmp_path: Path):
        """PID file creation creates parent directories."""
        pid_file = tmp_path / "subdir" / "test.pid"
        pid = acquire_pid_file(pid_file)
        assert pid == os.getpid()
        assert pid_file.exists()

    def test_acquire_atomic_write(self, tmp_path: Path):
        """PID file is written atomically via temp file."""
        pid_file = tmp_path / "test.pid"
        # Write initial content
        pid_file.write_text("old\n")

        # Acquire should replace atomically
        pid = acquire_pid_file(pid_file)
        assert pid_file.read_text().strip() == str(pid)


class TestReleasePidFile:
    """Test PID file release."""

    def test_release_existing_pid_file(self, tmp_path: Path):
        """Releasing matching PID file succeeds."""
        pid_file = tmp_path / "test.pid"
        pid = acquire_pid_file(pid_file)
        assert release_pid_file(pid_file, expected_pid=pid) is True
        assert not pid_file.exists()

    def test_release_nonexistent_file(self, tmp_path: Path):
        """Releasing non-existent file returns False."""
        pid_file = tmp_path / "nonexistent.pid"
        assert release_pid_file(pid_file, expected_pid=os.getpid()) is False

    def test_release_mismatched_pid(self, tmp_path: Path):
        """Releasing with mismatched PID returns False and keeps file."""
        pid_file = tmp_path / "test.pid"
        acquire_pid_file(pid_file)
        assert release_pid_file(pid_file, expected_pid=999999) is False
        assert pid_file.exists()

    def test_release_without_expected_pid(self, tmp_path: Path):
        """Releasing without expected PID removes any file."""
        pid_file = tmp_path / "test.pid"
        acquire_pid_file(pid_file)
        # Manually corrupt the PID file
        pid_file.write_text("999999\n")
        assert release_pid_file(pid_file) is True
        assert not pid_file.exists()


class TestPidFileContextManager:
    """Test context manager usage."""

    def test_context_manager_success(self, tmp_path: Path):
        """Context manager acquires and releases PID file."""
        pid_file = tmp_path / "test.pid"
        with pid_file_context(pid_file) as pid:
            assert pid == os.getpid()
            assert pid_file.exists()
            assert pid_file.read_text().strip() == str(pid)
        assert not pid_file.exists()

    def test_context_manager_exception(self, tmp_path: Path):
        """Context manager releases PID file even on exception."""
        pid_file = tmp_path / "test.pid"
        try:
            with pid_file_context(pid_file):
                assert pid_file.exists()
                raise ValueError("test error")
        except ValueError:
            pass
        assert not pid_file.exists()

    def test_context_manager_already_running(self, tmp_path: Path):
        """Context manager raises if already running."""
        pid_file = tmp_path / "test.pid"
        with pid_file_context(pid_file):
            # Try to acquire again in nested context - should fail
            with pytest.raises(PidAlreadyRunningError):
                with pid_file_context(pid_file):
                    pass
        # First context should have cleaned up
        assert not pid_file.exists()


class TestPidFileClass:
    """Test PidFile class."""

    def test_acquire_release(self, tmp_path: Path):
        """Explicit acquire and release works."""
        pid_file = tmp_path / "test.pid"
        pf = PidFile(pid_file)
        pid = pf.acquire()
        assert pid == os.getpid()
        assert pf.release() is True
        assert not pid_file.exists()

    def test_double_acquire_raises(self, tmp_path: Path):
        """Double acquire raises error."""
        pid_file = tmp_path / "test.pid"
        pf = PidFile(pid_file)
        pf.acquire()
        with pytest.raises(PidFileError):
            pf.acquire()
        pf.release()

    def test_release_without_acquire(self, tmp_path: Path):
        """Release without acquire returns False."""
        pid_file = tmp_path / "test.pid"
        pf = PidFile(pid_file)
        assert pf.release() is False

    def test_context_manager(self, tmp_path: Path):
        """PidFile as context manager works."""
        pid_file = tmp_path / "test.pid"
        with PidFile(pid_file) as pid:
            assert pid == os.getpid()
            assert pid_file.exists()
        assert not pid_file.exists()

    def test_context_manager_exception(self, tmp_path: Path):
        """PidFile context manager releases on exception."""
        pid_file = tmp_path / "test.pid"
        try:
            with PidFile(pid_file):
                assert pid_file.exists()
                raise ValueError("test")
        except ValueError:
            pass
        assert not pid_file.exists()

    def test_context_manager_already_running(self, tmp_path: Path):
        """Nested context managers on same file raises."""
        pid_file = tmp_path / "test.pid"
        with PidFile(pid_file):
            with pytest.raises(PidAlreadyRunningError):
                with PidFile(pid_file):
                    pass
        assert not pid_file.exists()


class TestPidFileIntegration:
    """Integration tests simulating daemon scenarios."""

    def test_daemon_restart_after_crash(self, tmp_path: Path):
        """Simulate daemon crash and restart - stale PID should be cleaned."""
        pid_file = tmp_path / "daemon.pid"

        # First run - acquire PID file
        with pid_file_context(pid_file) as pid1:
            assert pid1 == os.getpid()

        # Simulate crash (PID file remains but process is gone)
        pid_file.write_text("999999\n")  # Dead PID

        # Second run - should succeed after cleaning stale file
        with pid_file_context(pid_file) as pid2:
            assert pid2 == os.getpid()

    def test_daemon_prevents_double_launch(self, tmp_path: Path):
        """Two simultaneous daemons - second should fail."""
        pid_file = tmp_path / "daemon.pid"

        # First daemon acquires
        with pid_file_context(pid_file):
            # Second daemon tries to acquire - should fail
            with pytest.raises(PidAlreadyRunningError):
                with pid_file_context(pid_file):
                    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
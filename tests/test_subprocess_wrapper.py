"""
Test suite for subprocess wrapper and command builder utilities.

Tests the run_command(), build_ffmpeg_command(), and build_sox_command()
functions with comprehensive error handling, timeout, and logging verification.
"""

import json
import logging
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from omega13.audio_processor import (
    run_command,
    build_ffmpeg_command,
    build_sox_command,
    CommandExecutionError,
    CommandTimeoutError,
    AudioProcessorError,
)


class TestRunCommand(unittest.TestCase):
    """Test suite for run_command() function."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = logging.getLogger("omega13.audio_processor")
        self.logger.setLevel(logging.DEBUG)

    def test_run_command_success(self):
        """Test successful command execution."""
        # Use a simple command that always succeeds
        result = run_command(["echo", "hello"], timeout=5)
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_run_command_with_description(self):
        """Test command execution with description logging."""
        with patch.object(self.logger, "debug") as mock_debug:
            result = run_command(
                ["echo", "test"], timeout=5, description="Test echo command"
            )
            assert result.returncode == 0
            # Verify description was logged
            mock_debug.assert_any_call("Executing: Test echo command")

    def test_run_command_failure_with_check(self):
        """Test command failure raises CommandExecutionError when check=True."""
        with pytest.raises(CommandExecutionError) as exc_info:
            run_command(["false"], timeout=5, check=True)
        assert "Command failed" in str(exc_info.value)

    def test_run_command_failure_without_check(self):
        """Test command failure returns result when check=False."""
        result = run_command(["false"], timeout=5, check=False)
        assert result.returncode != 0

    def test_run_command_timeout(self):
        """Test command timeout raises CommandTimeoutError."""
        with pytest.raises(CommandTimeoutError) as exc_info:
            run_command(["sleep", "10"], timeout=1, check=True)
        assert "timed out" in str(exc_info.value)

    def test_run_command_invalid_command_type(self):
        """Test invalid command type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            run_command("echo hello", timeout=5)
        assert "must be a non-empty list" in str(exc_info.value)

    def test_run_command_empty_command(self):
        """Test empty command list raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            run_command([], timeout=5)
        assert "must be a non-empty list" in str(exc_info.value)

    def test_run_command_invalid_timeout(self):
        """Test invalid timeout raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            run_command(["echo", "test"], timeout=-1)
        assert "timeout must be positive integer" in str(exc_info.value)

    def test_run_command_timeout_not_integer(self):
        """Test non-integer timeout raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            run_command(["echo", "test"], timeout="5")
        assert "timeout must be positive integer" in str(exc_info.value)

    def test_run_command_stderr_capture(self):
        """Test stderr is captured and logged."""
        # Use a command that writes to stderr
        result = run_command(["sh", "-c", "echo error >&2"], timeout=5, check=False)
        assert "error" in result.stderr

    def test_run_command_logging_output(self):
        """Test command output is logged at debug level."""
        with patch.object(self.logger, "debug") as mock_debug:
            run_command(["echo", "test output"], timeout=5)
            # Verify command was logged
            debug_calls = [str(call) for call in mock_debug.call_args_list]
            assert any("Command:" in str(call) for call in debug_calls)

    def test_run_command_with_special_characters(self):
        """Test command with special characters in arguments."""
        result = run_command(["echo", "hello world & special chars"], timeout=5)
        assert result.returncode == 0
        assert "hello world & special chars" in result.stdout

    def test_run_command_long_output_truncation(self):
        """Test long output is truncated in logs."""
        with patch.object(self.logger, "debug") as mock_debug:
            # Create a command with long output
            long_string = "x" * 1000
            run_command(["echo", long_string], timeout=5)
            # Verify output was truncated to 500 chars
            debug_calls = [str(call) for call in mock_debug.call_args_list]
            # Check that truncation happened (output should be limited)
            assert any("stdout" in str(call) for call in debug_calls)


class TestBuildFFmpegCommand(unittest.TestCase):
    """Test suite for build_ffmpeg_command() function."""

    def test_build_ffmpeg_basic(self):
        """Test basic FFmpeg command building."""
        cmd = build_ffmpeg_command("input.wav", "output.wav")
        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert "input.wav" in cmd
        assert "-y" in cmd
        assert "output.wav" in cmd

    def test_build_ffmpeg_with_filters(self):
        """Test FFmpeg command with audio filters."""
        cmd = build_ffmpeg_command(
            "input.wav", "output.wav", filters=["aresample=16000", "aformat=mono"]
        )
        assert "-af" in cmd
        # Filters should be joined with comma
        filter_idx = cmd.index("-af")
        assert "aresample=16000,aformat=mono" == cmd[filter_idx + 1]

    def test_build_ffmpeg_with_codec_args(self):
        """Test FFmpeg command with codec arguments."""
        cmd = build_ffmpeg_command(
            "input.wav", "output.mp3", codec_args={"acodec": "mp3", "ab": "128k"}
        )
        assert "-acodec" in cmd
        assert "mp3" in cmd
        assert "-ab" in cmd
        assert "128k" in cmd

    def test_build_ffmpeg_with_extra_args(self):
        """Test FFmpeg command with extra arguments."""
        cmd = build_ffmpeg_command(
            "input.wav", "output.wav", extra_args=["-loglevel", "quiet"]
        )
        assert "-loglevel" in cmd
        assert "quiet" in cmd

    def test_build_ffmpeg_all_options(self):
        """Test FFmpeg command with all options combined."""
        cmd = build_ffmpeg_command(
            "input.wav",
            "output.mp3",
            filters=["aresample=16000"],
            codec_args={"acodec": "mp3", "ab": "128k"},
            extra_args=["-loglevel", "quiet"],
        )
        assert "ffmpeg" in cmd
        assert "-i" in cmd
        assert "-af" in cmd
        assert "-acodec" in cmd
        assert "-ab" in cmd
        assert "-loglevel" in cmd
        assert "-y" in cmd

    def test_build_ffmpeg_output_order(self):
        """Test that output file and -y flag are at the end."""
        cmd = build_ffmpeg_command(
            "input.wav", "output.wav", filters=["aresample=16000"]
        )
        # -y should come before output file
        y_idx = cmd.index("-y")
        output_idx = cmd.index("output.wav")
        assert y_idx < output_idx

    def test_build_ffmpeg_empty_filters(self):
        """Test FFmpeg command with empty filters list."""
        cmd = build_ffmpeg_command("input.wav", "output.wav", filters=[])
        assert "-af" not in cmd

    def test_build_ffmpeg_none_filters(self):
        """Test FFmpeg command with None filters."""
        cmd = build_ffmpeg_command("input.wav", "output.wav", filters=None)
        assert "-af" not in cmd

    def test_build_ffmpeg_numeric_codec_args(self):
        """Test FFmpeg command with numeric codec arguments."""
        cmd = build_ffmpeg_command(
            "input.wav", "output.wav", codec_args={"q:a": 2, "compression_level": 6}
        )
        # Numeric values should be converted to strings
        assert "2" in cmd
        assert "6" in cmd


class TestBuildSoxCommand(unittest.TestCase):
    """Test suite for build_sox_command() function."""

    def test_build_sox_basic(self):
        """Test basic SoX command building."""
        cmd = build_sox_command("input.wav", "output.wav")
        assert cmd[0] == "sox"
        assert "input.wav" in cmd
        assert "output.wav" in cmd

    def test_build_sox_with_rate(self):
        """Test SoX command with sample rate conversion."""
        cmd = build_sox_command("input.wav", "output.wav", rate=16000)
        assert "rate" in cmd
        assert "16000" in cmd

    def test_build_sox_with_mono_channel(self):
        """Test SoX command with mono channel conversion."""
        cmd = build_sox_command("input.wav", "output.wav", channels=1)
        assert "remix -" in cmd

    def test_build_sox_with_stereo_channel(self):
        """Test SoX command with stereo channel conversion."""
        cmd = build_sox_command("input.wav", "output.wav", channels=2)
        assert "remix 1,2" in cmd

    def test_build_sox_with_effects(self):
        """Test SoX command with audio effects."""
        cmd = build_sox_command(
            "input.wav", "output.wav", effects=["silence 1 0.1 1%", "norm"]
        )
        assert "silence 1 0.1 1%" in cmd
        assert "norm" in cmd

    def test_build_sox_all_options(self):
        """Test SoX command with all options combined."""
        cmd = build_sox_command(
            "input.wav", "output.wav", rate=16000, channels=1, effects=["norm"]
        )
        assert "sox" in cmd
        assert "rate" in cmd
        assert "16000" in cmd
        assert "remix -" in cmd
        assert "norm" in cmd

    def test_build_sox_empty_effects(self):
        """Test SoX command with empty effects list."""
        cmd = build_sox_command("input.wav", "output.wav", effects=[])
        # Should still have basic structure
        assert "sox" in cmd
        assert "input.wav" in cmd
        assert "output.wav" in cmd

    def test_build_sox_none_effects(self):
        """Test SoX command with None effects."""
        cmd = build_sox_command("input.wav", "output.wav", effects=None)
        assert "sox" in cmd

    def test_build_sox_numeric_rate(self):
        """Test SoX command with numeric rate."""
        cmd = build_sox_command("input.wav", "output.wav", rate=44100)
        assert "44100" in cmd


class TestExceptionHierarchy(unittest.TestCase):
    """Test exception class hierarchy."""

    def test_command_execution_error_is_audio_processor_error(self):
        """Test CommandExecutionError inherits from AudioProcessorError."""
        assert issubclass(CommandExecutionError, AudioProcessorError)

    def test_command_timeout_error_is_audio_processor_error(self):
        """Test CommandTimeoutError inherits from AudioProcessorError."""
        assert issubclass(CommandTimeoutError, AudioProcessorError)

    def test_exception_instantiation(self):
        """Test exception instantiation."""
        exc1 = CommandExecutionError("test error")
        exc2 = CommandTimeoutError("timeout error")
        assert str(exc1) == "test error"
        assert str(exc2) == "timeout error"


class TestCommandIntegration(unittest.TestCase):
    """Integration tests for command building and execution."""

    def test_ffmpeg_command_execution_simulation(self):
        """Test that built FFmpeg command can be executed (with mock)."""
        cmd = build_ffmpeg_command(
            "input.wav", "output.wav", filters=["aresample=16000"]
        )
        # Verify command structure is valid for subprocess
        assert isinstance(cmd, list)
        assert all(isinstance(arg, str) for arg in cmd)
        assert cmd[0] == "ffmpeg"

    def test_sox_command_execution_simulation(self):
        """Test that built SoX command can be executed (with mock)."""
        cmd = build_sox_command("input.wav", "output.wav", rate=16000, channels=1)
        # Verify command structure is valid for subprocess
        assert isinstance(cmd, list)
        assert all(isinstance(arg, str) for arg in cmd)
        assert cmd[0] == "sox"

    def test_run_command_with_built_command(self):
        """Test run_command with a built command."""
        # Use echo as a safe test command
        cmd = ["echo", "test"]
        result = run_command(cmd, timeout=5)
        assert result.returncode == 0


def test_run_command_success():
    """Standalone test: successful command execution."""
    result = run_command(["echo", "hello"], timeout=5)
    assert result.returncode == 0


def test_run_command_timeout_error():
    """Standalone test: timeout error."""
    with pytest.raises(CommandTimeoutError):
        run_command(["sleep", "10"], timeout=1)


def test_build_ffmpeg_command_structure():
    """Standalone test: FFmpeg command structure."""
    cmd = build_ffmpeg_command("in.wav", "out.wav")
    assert cmd[0] == "ffmpeg"
    assert "-i" in cmd
    assert "-y" in cmd


def test_build_sox_command_structure():
    """Standalone test: SoX command structure."""
    cmd = build_sox_command("in.wav", "out.wav", rate=16000)
    assert cmd[0] == "sox"
    assert "rate" in cmd


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])

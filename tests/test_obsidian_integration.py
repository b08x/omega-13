import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from omega13.obsidian_cli import ObsidianCLI, ObsidianResult


@pytest.fixture
def obsidian_cli():
    """Fixture for ObsidianCLI instance."""
    return ObsidianCLI()


def test_obsidian_cli_availability_success(obsidian_cli):
    """Test that is_available returns True when 'obsidian help' succeeds."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert obsidian_cli.is_available(force_check=True) is True
        mock_run.assert_called_once_with(
            ["obsidian", "help"], capture_output=True, text=True, timeout=10
        )


def test_obsidian_cli_availability_failure(obsidian_cli):
    """Test that is_available returns False when 'obsidian help' fails."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Not found")
        assert obsidian_cli.is_available(force_check=True) is False


def test_open_daily_note_success(obsidian_cli):
    """Test that open_daily_note returns success when CLI succeeds."""
    with patch.object(ObsidianCLI, "is_available", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = obsidian_cli.open_daily_note()
            assert result.success is True
            assert result.message == "Daily note opened"
            mock_run.assert_called_once_with(
                ["obsidian", "daily"], capture_output=True, text=True, timeout=15
            )


def test_open_daily_note_unavailable(obsidian_cli):
    """Test that open_daily_note returns failure when CLI is unavailable."""
    with patch.object(ObsidianCLI, "is_available", return_value=False):
        result = obsidian_cli.open_daily_note()
        assert result.success is False
        assert "not available" in result.message.lower()


def test_append_to_daily_note_success(obsidian_cli):
    """Test that append_to_daily_note returns success when CLI succeeds."""
    with patch.object(ObsidianCLI, "is_available", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            test_content = "Test content"
            result = obsidian_cli.append_to_daily_note(test_content)
            assert result.success is True
            assert result.message == "Content appended to daily note"
            
            # Check that subprocess.run was called with sanitized content (contains timestamp)
            args, kwargs = mock_run.call_args
            command = args[0]
            assert command[0] == "obsidian"
            assert command[1] == "daily:append"
            assert "content=" in command[2]
            assert test_content in command[2]


def test_append_empty_content(obsidian_cli):
    """Test that append_to_daily_note returns failure for empty content."""
    with patch.object(ObsidianCLI, "is_available", return_value=True):
        result = obsidian_cli.append_to_daily_note("")
        assert result.success is False
        assert "empty" in result.message.lower()


def test_sanitize_content(obsidian_cli):
    """Test content sanitization logic."""
    content = 'Hello "World" `test`'
    sanitized = obsidian_cli._sanitize_content(content)
    
    # Check that quotes and backticks are replaced
    assert '"' not in sanitized
    assert '`' not in sanitized
    assert "World" in sanitized
    assert "test" in sanitized
    
    # Check for timestamp format [HH:MM:SS]
    import re
    assert re.search(r"\[\d{2}:\d{2}:\d{2}\]", sanitized)

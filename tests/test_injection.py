import pytest
from unittest.mock import patch, MagicMock
import subprocess
from omega13.injection import inject_text, is_ydotool_available

def test_inject_text_invalid_input():
    success, error = inject_text("")
    assert not success
    assert "Invalid text" in error

@patch("shutil.which")
def test_inject_text_no_ydotool(mock_which):
    mock_which.return_value = None
    success, error = inject_text("hello")
    assert not success
    assert "ydotool not found" in error

@patch("shutil.which")
@patch("subprocess.run")
def test_inject_text_success(mock_run, mock_which):
    mock_which.return_value = "/usr/bin/ydotool"
    mock_run.return_value = MagicMock(returncode=0)
    
    success, error = inject_text("hello world")
    
    assert success
    assert error is None
    mock_run.assert_called_once_with(
        ["/usr/bin/ydotool", "type", "hello world"],
        capture_output=True,
        text=True,
        timeout=30
    )

@patch("shutil.which")
@patch("subprocess.run")
def test_inject_text_daemon_error(mock_run, mock_which):
    mock_which.return_value = "/usr/bin/ydotool"
    mock_run.return_value = MagicMock(
        returncode=1, 
        stderr="failed to connect to ydotoold"
    )
    
    success, error = inject_text("hello")
    
    assert not success
    assert "daemon not running" in error

@patch("shutil.which")
@patch("subprocess.run")
def test_inject_text_permission_error(mock_run, mock_which):
    mock_which.return_value = "/usr/bin/ydotool"
    mock_run.return_value = MagicMock(
        returncode=1, 
        stderr="permission denied on /dev/uinput"
    )
    
    success, error = inject_text("hello")
    
    assert not success
    assert "Permission denied" in error

@patch("shutil.which")
def test_is_ydotool_available(mock_which):
    mock_which.return_value = "/usr/bin/ydotool"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert is_ydotool_available() is True
        
    mock_which.return_value = None
    assert is_ydotool_available() is False

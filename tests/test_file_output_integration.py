import pytest
from pathlib import Path
from omega13.file_output import file_output, FileOutputResult

def test_append_empty_content():
    result = file_output.append_to_daily_file("", "/tmp/omega13_test")
    assert not result.success
    assert "empty" in result.message

def test_append_no_directory():
    result = file_output.append_to_daily_file("Test content", "")
    assert not result.success
    assert "not configured" in result.message

def test_append_success(tmp_path):
    out_dir = tmp_path / "output"
    result = file_output.append_to_daily_file("Test content", str(out_dir))
    
    assert result.success
    assert out_dir.exists()
    files = list(out_dir.glob("*.md"))
    assert len(files) == 1
    
    with open(files[0], "r") as f:
        content = f.read()
    assert "Test content" in content


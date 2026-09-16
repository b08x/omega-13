import pytest
from pathlib import Path
from omega13.session import SessionManager

def test_failed_transcription_manifest(tmp_path):
    manager = SessionManager(temp_root=tmp_path)
    
    # Add 12 failed transcriptions
    for i in range(12):
        manager.add_failed_transcription(Path(f"/tmp/file_{i}.wav"), error=f"error_{i}")
    
    # Should only keep 10
    failures = manager.get_failed_transcriptions()
    assert len(failures) == 10
    
    # Should be the most recent 10 (2 through 11)
    assert failures[0]["error"] == "error_2"
    assert failures[9]["error"] == "error_11"
    
    # Clear manifest
    manager.clear_failed_transcriptions()
    assert len(manager.get_failed_transcriptions()) == 0

import pytest
import tempfile
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from omega13.config import ConfigManager
from omega13.app import Omega13App


@pytest.fixture
def temp_config_path():
    """Fixture for temporary config file path."""
    temp_dir = tempfile.mkdtemp()
    config_path = Path(temp_dir) / "test_config.json"
    yield config_path
    shutil.rmtree(temp_dir)


def test_auto_transcribe_config_persistence(temp_config_path):
    """Test that auto-transcribe setting is persisted in config."""
    # Session 1: Enable auto-transcription
    config1 = ConfigManager(temp_config_path)
    config1.set_write_to_daily_note(False) # Initial state
    
    # Transcription section doesn't have a direct setter for auto_transcribe in config.py
    # but app.py uses it. Let's check config.py again.
    # Ah, it has get_auto_transcribe but NOT a direct set_auto_transcribe!
    # Wait, app.py calls self.config_manager.set_auto_transcribe(value) but I don't see it in config.py.
    
    # Let's check if I should add it to config.py.
    # app.py:
    # def watch_auto_record_enabled(self, value: bool) -> None:
    #    if hasattr(self, "config_manager"):
    #        self.config_manager.set_auto_record_enabled(value)
    
    # Wait, app.py:
    # def watch_copy_to_clipboard(self, value: bool) -> None:
    #    if hasattr(self, "config_manager"):
    #        self.config_manager.set_copy_to_clipboard(value)
            
    # I see set_copy_to_clipboard in config.py.
    # But I don't see set_auto_transcribe in config.py.
    # Let's check config.py again.

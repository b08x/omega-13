import pytest
import tempfile
import shutil
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch
from omega13.config import ConfigManager
from omega13.app import Omega13App
from omega13.obsidian_cli import obsidian_cli
from omega13.transcription import TranscriptionStatus, TranscriptionResult


@pytest.fixture
def temp_dir():
    """Fixture for temporary directory."""
    dir_path = tempfile.mkdtemp()
    yield Path(dir_path)
    shutil.rmtree(dir_path)


def test_config_persistence(temp_dir):
    """Test config persistence (from demo_auto_transcription_usage.py)."""
    config_path = temp_dir / "test_config.json"
    
    # Session 1: Enable auto-transcription
    config1 = ConfigManager(config_path)
    config1.set_auto_transcribe(True)
    assert config1.get_auto_transcribe() is True
    
    # Session 2: Reload config
    config2 = ConfigManager(config_path)
    assert config2.get_auto_transcribe() is True
    
    # Session 3: Disable
    config2.set_auto_transcribe(False)
    assert config2.get_auto_transcribe() is False
    
    # Session 4: Verify
    config3 = ConfigManager(config_path)
    assert config3.get_auto_transcribe() is False


@pytest.mark.asyncio
async def test_app_mutual_exclusivity():
    """Test mutual exclusivity logic in Omega13App (from demo_daily_note_feature.py)."""
    with patch('omega13.app.obsidian_cli') as mock_obsidian:
        mock_result = MagicMock()
        mock_result.success = True
        mock_obsidian.open_daily_note_if_enabled.return_value = mock_result
        
        app = Omega13App()
        async with app.run_test() as pilot:
            # 1. Enable daily note
            app.write_to_daily_note = True
            await asyncio.sleep(0.1)
            
            # 2. Enabling daily note should disable copy/inject
            app.copy_to_clipboard = True
            app.inject_to_active_window = True
            
            # Now trigger daily note via setter (which app does via keybind 'd')
            # Actually, the watch_write_to_daily_note handles this.
            app.write_to_daily_note = True # Re-trigger
            
            # Check mutual exclusivity
            assert app.copy_to_clipboard is False
            assert app.inject_to_active_window is False
            
            # 3. Enabling copy should disable daily note
            app.copy_to_clipboard = True
            assert app.write_to_daily_note is False
            
            # 4. Enabling inject should disable daily note
            app.write_to_daily_note = True
            app.inject_to_active_window = True
            assert app.write_to_daily_note is False


def test_transcription_display_status_updates():
    """Test TranscriptionDisplay status updates (from demo_transcription_progress.py)."""
    # We test the real widget logic
    from omega13.ui import TranscriptionDisplay
    
    display = TranscriptionDisplay()
    # Mock status_label which is usually set by app
    display.status_label = MagicMock()
    
    display.status = "processing"
    display.status_label.update.assert_called_with("Transcribing...")
    
    display.status = "completed"
    display.status_label.update.assert_called_with("Complete")
    
    display.status = "error"
    display.status_label.update.assert_called_with("Error")


def test_obsidian_cli_result_structure():
    """Test ObsidianResult structure (from demo_daily_note_feature.py)."""
    from omega13.obsidian_cli import ObsidianResult
    
    res = ObsidianResult(success=True, message="Test success")
    assert res.success is True
    assert res.message == "Test success"
    
    res = ObsidianResult(success=False, message="Test failure", error_code=1)
    assert res.success is False
    assert res.error_code == 1


@pytest.mark.asyncio
async def test_transcription_settings_screen_init():
    """Test TranscriptionSettingsScreen initialization (from demo_auto_transcription_usage.py)."""
    from omega13.ui import TranscriptionSettingsScreen
    
    config = {
        "provider": "groq",
        "server_url": "http://test:8080",
        "inference_path": "/test",
        "groq_model": "test-model"
    }
    
    screen = TranscriptionSettingsScreen(config)
    assert screen.provider == "groq"
    assert screen.server_url == "http://test:8080"
    assert screen.inference_path == "/test"
    assert screen.groq_model == "test-model"


@pytest.mark.asyncio
async def test_recording_to_transcription_workflow():
    """Test that transcription is triggered when recording stops (from example_auto_transcription.py)."""
    with patch('omega13.app.obsidian_cli'), \
         patch('omega13.app.AudioEngine') as mock_engine_class, \
         patch('omega13.app.TranscriptionService') as mock_trans_service_class:
        
        mock_engine = MagicMock()
        mock_engine.get_peak_meters.return_value = ([0.0, 0.0], [-100.0, -100.0])
        mock_engine.channels = 2
        mock_engine_class.return_value = mock_engine
        
        mock_trans_service = MagicMock()
        mock_trans_service_class.return_value = mock_trans_service
        
        app = Omega13App()
        async with app.run_test() as pilot:
            # 1. Enable auto-transcription
            app.config_manager.set_auto_transcribe(True)
            
            # 2. Simulate recording stop event
            test_path = Path("/tmp/test_recording.mp4")
            # Create a dummy file so exists() returns true
            with patch.object(Path, 'exists', return_value=True):
                # We need to mock session_manager to return a session
                app.session_manager = MagicMock()
                
                # Manually trigger the event handler
                from omega13.recording_controller import RecordingEvent
                app._handle_recording_event(RecordingEvent.MANUAL_STOPPED, {"path": test_path})
                
                # Check if transcription was started
                mock_trans_service.transcribe_async.assert_called()
                args, kwargs = mock_trans_service.transcribe_async.call_args
                assert args[0] == test_path

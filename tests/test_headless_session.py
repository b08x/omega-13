"""Test session manager and clipboard/injection in headless mode."""
import tempfile
from pathlib import Path
import pytest

from omega13.session import SessionManager, Session
from omega13.clipboard import copy_to_clipboard, is_clipboard_available
from omega13.injection import inject_text, is_ydotool_available
from omega13.obsidian_cli import ObsidianCLI, obsidian_cli


def test_session_creation_headless():
    """Test session creation without TUI."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_root = Path(tmpdir)
        manager = SessionManager(temp_root=temp_root)
        session = manager.create_session()

        assert session is not None
        assert session.session_id.startswith("session_")
        assert session.session_dir.exists()
        assert (session.session_dir / "recordings").exists()
        assert (session.session_dir / "transcriptions").exists()
        assert (session.session_dir / "session.json").exists()


def test_session_persistence_and_restore():
    """Test session can be saved and restored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_root = Path(tmpdir)
        manager = SessionManager(temp_root=temp_root)
        session = manager.create_session()

        # Add some data
        session.add_transcription("First transcription")
        session.add_transcription("Second transcription")
        recording_path = session.get_next_recording_path()
        session.register_recording(recording_path, duration_seconds=5.0)

        # Save metadata
        session.save_metadata()

        # Load from directory
        restored = Session.load_from_directory(session.session_dir)

        assert restored.session_id == session.session_id
        assert len(restored.transcriptions) == 2
        assert restored.transcriptions[0] == "First transcription"
        assert restored.transcriptions[1] == "Second transcription"
        assert len(restored.recordings) == 1


def test_session_save_to_permanent():
    """Test saving session to permanent location."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_root = Path(tmpdir) / "temp"
        permanent = Path(tmpdir) / "permanent"
        permanent.mkdir()

        manager = SessionManager(temp_root=temp_root)
        session = manager.create_session()
        session.add_transcription("Test transcription")

        success = manager.save_session(permanent, title="test-session")
        assert success
        assert session.saved
        assert session.save_location is not None
        assert session.save_location.name.startswith("omega13_session_")
        assert "test_session" in session.save_location.name

        # Verify saved session can be loaded
        saved_session = Session.load_from_directory(session.save_location)
        assert saved_session.session_id == session.session_id
        assert len(saved_session.transcriptions) == 1


def test_clipboard_operations_headless():
    """Test clipboard operations work in headless mode."""
    # Test clipboard availability check
    available = is_clipboard_available()
    assert isinstance(available, bool)

    # Test copy operation - should not crash
    test_text = "Test clipboard content"
    success, error = copy_to_clipboard(test_text)

    # In headless environments, clipboard may not be available
    # This should not raise an exception
    assert isinstance(success, bool)
    if not success:
        assert error is not None


def test_injection_headless():
    """Test text injection in headless mode."""
    # Check ydotool availability
    available = is_ydotool_available()
    assert isinstance(available, bool)

    # Test injection - should fail gracefully if not available
    success, error = inject_text("Test injection")

    assert isinstance(success, bool)
    if not success:
        assert error is not None
        # Should fail gracefully with a meaningful error
        # ydotool may return "Exit code 2" when ydotoold is not running
        assert len(error) > 0


def test_obsidian_cli_headless():
    """Test Obsidian CLI operations in headless mode."""
    # Check availability
    available = obsidian_cli.is_available(force_check=True)
    assert isinstance(available, bool)

    # Test operations - should fail gracefully if not available
    result = obsidian_cli.open_daily_note()
    assert result.success is False or result.success is True
    assert isinstance(result.message, str)

    result = obsidian_cli.append_to_daily_note("Test content")
    assert result.success is False or result.success is True
    assert isinstance(result.message, str)

    # Test empty content handling
    result = obsidian_cli.append_to_daily_note("")
    assert result.success is False
    assert "empty" in result.message.lower()


def test_headless_omega13_init():
    """Test HeadlessOmega13 initialization without full run."""
    from omega13.headless_service import HeadlessOmega13

    headless = HeadlessOmega13()
    assert headless.config_manager is None
    assert headless.audio_engine is None
    assert headless.session_manager is None
    assert headless.recording_controller is None
    assert headless.dbus_service is None


@pytest.mark.asyncio
async def test_headless_omega13_initialize_shutdown():
    """Test HeadlessOmega13 async initialize and shutdown."""
    from omega13.headless_service import HeadlessOmega13

    headless = HeadlessOmega13()
    await headless.initialize()

    # Verify components initialized
    assert headless.config_manager is not None
    assert headless.session_manager is not None
    assert headless.session_manager.get_current_session() is not None

    await headless.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

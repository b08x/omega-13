import pytest
import asyncio
from unittest.mock import patch, MagicMock
from textual.widgets import Checkbox
from omega13.app import Omega13App

@pytest.mark.asyncio
async def test_toggle_bindings():
    # Mock Obsidian CLI to prevent subprocess calls during testing
    with patch('omega13.app.obsidian_cli') as mock_obsidian:
        # Create a proper mock result object
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.message = "CLI not configured"
        mock_obsidian.open_daily_note_if_enabled.return_value = mock_result

        app = Omega13App()
        # Mocking AudioEngine to prevent it from trying to access real audio hardware
        # or failing in environments without JACK/Pipewire
        async with app.run_test() as pilot:
            # Give it a moment to mount and settle
            await asyncio.sleep(0.5)

            try:
                # Test each toggle independently to avoid mutual exclusivity interference

                # Test auto-record toggle (should not be affected by mutual exclusivity)
                initial_auto = app.auto_record_enabled
                await pilot.press("a")
                assert app.auto_record_enabled == (not initial_auto)
                await pilot.press("a")  # Toggle back
                assert app.auto_record_enabled == initial_auto

                # Test daily note toggle in isolation
                initial_daily = app.write_to_daily_note
                await pilot.press("d")
                toggled_daily = app.write_to_daily_note
                assert toggled_daily == (not initial_daily)

                # Test mutual exclusivity: when daily note is enabled, copy/inject should be disabled
                if toggled_daily:
                    assert app.copy_to_clipboard == False
                    assert app.inject_to_active_window == False

                # Test clipboard toggle
                initial_clip = app.copy_to_clipboard
                await pilot.press("c")
                assert app.copy_to_clipboard == (not initial_clip)
                # Due to mutual exclusivity, daily note should be disabled
                if not initial_clip:  # If we just enabled clipboard
                    assert app.write_to_daily_note == False

                # Test injection toggle
                initial_inject = app.inject_to_active_window
                await pilot.press("j")
                assert app.inject_to_active_window == (not initial_inject)

                # Test mutual exclusivity: enabling daily note disables copy/inject
                await pilot.press("d")  # Enable daily note
                if app.write_to_daily_note:
                    assert app.copy_to_clipboard == False
                    assert app.inject_to_active_window == False
            except Exception as e:
                pytest.fail(f"Test failed due to error: {e}")

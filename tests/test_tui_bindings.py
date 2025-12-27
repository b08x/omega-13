import pytest
import asyncio
from textual.widgets import Checkbox
from omega13.app import Omega13App

@pytest.mark.asyncio
async def test_toggle_bindings():
    app = Omega13App()
    # Mocking AudioEngine to prevent it from trying to access real audio hardware
    # or failing in environments without JACK/Pipewire
    async with app.run_test() as pilot:
        # Give it a moment to mount and settle
        await asyncio.sleep(0.5)
        
        try:
            # Check initial states via reactives
            initial_auto = app.auto_record_enabled
            initial_clip = app.copy_to_clipboard
            initial_inject = app.inject_to_active_window
            
            # Toggle auto-record
            await pilot.press("a")
            assert app.auto_record_enabled == (not initial_auto)
            
            # Toggle clipboard
            await pilot.press("c")
            assert app.copy_to_clipboard == (not initial_clip)
            
            # Toggle injection
            await pilot.press("j")
            assert app.inject_to_active_window == (not initial_inject)
            
            # Toggle back
            await pilot.press("a")
            await pilot.press("c")
            await pilot.press("j")
            
            assert app.auto_record_enabled == initial_auto
            assert app.copy_to_clipboard == initial_clip
            assert app.inject_to_active_window == initial_inject
        except Exception as e:
            pytest.fail(f"Test failed due to error: {e}")

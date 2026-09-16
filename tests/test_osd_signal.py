import pytest
from unittest.mock import MagicMock
from omega13.headless_service import HeadlessOmega13

@pytest.mark.asyncio
async def test_osd_state_changed_signal():
    headless = HeadlessOmega13()
    headless.dbus_service = MagicMock()
    headless.dbus_service.interface = MagicMock()
    
    headless._emit_osd_state("recording", "Recording")
    headless.dbus_service.interface.OSDStateChanged.assert_called_once_with("recording", "Recording", 0)

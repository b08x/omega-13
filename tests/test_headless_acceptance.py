"""Acceptance test suite for Omega-13 headless D-Bus mode.

Validates the complete headless daemon workflow:
1. Daemon launches and registers D-Bus service
2. D-Bus toggle signal starts recording
3. D-Bus health signal confirms valid response
4. D-Bus toggle signal stops recording

Run with:
    pytest -o addopts="" tests/test_headless_acceptance.py -v
"""

from pathlib import Path

import pytest
from unittest.mock import patch, MagicMock

from omega13.headless_service import HeadlessOmega13
from dbus_next.aio.message_bus import MessageBus
from dbus_next import Variant

DBUS_SERVICE_NAME = "org.omega13.Recorder"
DBUS_OBJECT_PATH = "/org/omega13/Recorder"
DBUS_INTERFACE_NAME = "org.omega13.Recorder"


def unwrap(obj):
    """Unwrap dbus_next Variant objects recursively."""
    if isinstance(obj, Variant):
        return unwrap(obj.value)
    if isinstance(obj, dict):
        return {k: unwrap(v) for k, v in obj.items()}
    return obj


@pytest.fixture
def mock_audio_engine():
    """Provide a mocked AudioEngine that avoids JACK hardware dependency.

    Synchronous setup contract: plain MagicMock values only; tests are
    responsible for awaiting async life-cycle steps on the D-Bus loop.
    """
    with patch('omega13.headless_service.AudioEngine') as MockEngine:
        ae = MockEngine.return_value
        ae.samplerate = 48000
        ae.channels = 2
        ae.has_audio_activity.return_value = True
        ae.start_recording.return_value = Path("/tmp/test_acceptance.wav")
        ae.stop_recording = MagicMock()
        ae.is_recording = False
        ae.client = MagicMock()
        ae.client.__class__.__name__ = 'MockClient'
        yield ae


@pytest.fixture
def headless_daemon(mock_audio_engine):
    """Factory fixture: call `headless_daemon()` inside each async test to
    build a fresh HeadlessOmega13 on the current event loop."""
    ae = mock_audio_engine

    async def factory():
        headless = HeadlessOmega13()
        await headless.initialize()
        return headless

    return factory


@pytest.mark.asyncio
async def test_daemon_registers_without_tui(headless_daemon):
    """(1) Daemon launches, (2) verify running."""
    headless = await headless_daemon()
    assert headless.dbus_service is not None
    assert headless.dbus_service.is_registered() is True
    await headless.shutdown()


@pytest.mark.asyncio
async def test_dbus_toggle_starts_recording(headless_daemon):
    """(3) Send D-Bus toggle to start, (4) verify recording begins."""
    headless = await headless_daemon()

    bus = await MessageBus().connect()
    try:
        introspection = await bus.introspect(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH)
        proxy = bus.get_proxy_object(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH, introspection)
        iface = proxy.get_interface(DBUS_INTERFACE_NAME)

        state_before = await iface.call_get_state()
        assert state_before == "idle"

        recording = await iface.call_toggle_recording()
        assert recording is True

        state_after = await iface.call_get_state()
        assert state_after == "recording_manual"
    finally:
        bus.disconnect()
        await headless.shutdown()


@pytest.mark.asyncio
async def test_dbus_health_response(headless_daemon):
    """(5) Send health signal and confirm a valid response."""
    headless = await headless_daemon()

    bus = await MessageBus().connect()
    try:
        introspection = await bus.introspect(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH)
        proxy = bus.get_proxy_object(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH, introspection)
        iface = proxy.get_interface(DBUS_INTERFACE_NAME)

        health = await iface.call_get_health()
        assert health is not None

        unwrapped = unwrap(health)
        assert isinstance(unwrapped, dict)
        assert "state" in unwrapped
        assert "is_recording" in unwrapped
        assert "auto_record_enabled" in unwrapped
        assert "audio" in unwrapped
        assert "session" in unwrapped
        assert "transcription" in unwrapped

        assert unwrapped["audio"]["connected"] is True
        assert unwrapped["audio"]["sample_rate"] == 48000
        assert unwrapped["audio"]["channels"] == 2
        assert unwrapped["session"]["active"] is True
    finally:
        bus.disconnect()
        await headless.shutdown()


@pytest.mark.asyncio
async def test_dbus_toggle_stops_recording(headless_daemon):
    """(6) Toggle to stop recording and verify state returns to idle."""
    headless = await headless_daemon()

    bus = await MessageBus().connect()
    try:
        introspection = await bus.introspect(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH)
        proxy = bus.get_proxy_object(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH, introspection)
        iface = proxy.get_interface(DBUS_INTERFACE_NAME)

        start_state = await iface.call_toggle_recording()
        assert start_state is True

        state_mid = await iface.call_get_state()
        assert state_mid == "recording_manual"

        stop_state = await iface.call_toggle_recording()
        assert stop_state is False

        state_end = await iface.call_get_state()
        assert state_end == "idle"
    finally:
        bus.disconnect()
        await headless.shutdown()


@pytest.mark.asyncio
async def test_full_headless_acceptance_workflow(headless_daemon):
    """End-to-end acceptance test covering all 6 criteria in sequence.

    1. Daemon launches, registers D-Bus
    2. Initial state is idle
    3. Toggle starts recording -> state becomes recording_manual
    4. Recording began (controller confirms)
    5. Health check returns valid structured data
    6. Toggle stops recording -> state returns to idle
    """
    headless = await headless_daemon()

    bus = await MessageBus().connect()
    try:
        introspection = await bus.introspect(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH)
        proxy = bus.get_proxy_object(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH, introspection)
        iface = proxy.get_interface(DBUS_INTERFACE_NAME)

        state = await iface.call_get_state()
        assert state == "idle"

        is_recording = await iface.call_toggle_recording()
        assert is_recording is True
        state = await iface.call_get_state()
        assert state == "recording_manual"

        assert headless.recording_controller.is_recording() is True

        health = await iface.call_get_health()
        unwrapped = unwrap(health)
        assert unwrapped["state"] == "recording_manual"
        assert unwrapped["is_recording"] is True

        is_recording = await iface.call_toggle_recording()
        assert is_recording is False
        state = await iface.call_get_state()
        assert state == "idle"
    finally:
        bus.disconnect()
        await headless.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-o", "addopts="])

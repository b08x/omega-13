"""D-Bus service interface for Omega-13 recorder control.

Provides org.omega13.Recorder service with methods for remote recording control.
"""

from typing import TYPE_CHECKING
from dbus_next.errors import DBusError
from dbus_next.service import ServiceInterface, method
from dbus_next.aio.message_bus import MessageBus

if TYPE_CHECKING:
    from .app import Omega13App


class RecorderInterface(ServiceInterface):
    """D-Bus interface for Omega-13 recorder control.

    Service name: org.omega13.Recorder
    Object path: /org/omega13/Recorder
    Interface: org.omega13.Recorder
    """

    def __init__(self, app_instance: "Omega13App") -> None:
        """Initialize the recorder interface.

        Args:
            app_instance: Reference to the Omega13App instance
        """
        super().__init__("org.omega13.Recorder")
        self._app: "Omega13App" = app_instance

    @method()
    async def ToggleRecording(self) -> "b":  # type: ignore  # noqa: F821
        """Toggle recording state.

        Returns:
            bool: New recording state (True = recording, False = stopped)

        Raises:
            DBusError: If toggle operation fails
        """
        try:
            # We are in the app's event loop (asynchronous D-Bus)
            # Safe to call the action directly or via call_next
            self._app.action_toggle_record()
            
            # Get the updated recording state
            is_recording = self._app.recording_controller.is_recording()
            return is_recording
        except Exception as e:
            raise DBusError("org.omega13.Recorder.ToggleError", str(e))

    @method()
    async def GetState(self) -> "s":  # type: ignore  # noqa: F821
        """Get current recording state.

        Returns:
            str: Current state (IDLE, ARMED, RECORDING_AUTO, RECORDING_MANUAL, STOPPING)

        Raises:
            DBusError: If state query fails
        """
        try:
            # Get the current state from recording controller
            state = self._app.recording_controller.get_state()
            return state.value
        except Exception as e:
            raise DBusError("org.omega13.Recorder.StateError", str(e))


class DBusService:
    """D-Bus service manager for Omega-13.

    Handles service registration and lifecycle management.
    """

    SERVICE_NAME: str = "org.omega13.Recorder"
    OBJECT_PATH: str = "/org/omega13/Recorder"
    INTERFACE_NAME: str = "org.omega13.Recorder"

    def __init__(self, app_instance: "Omega13App") -> None:
        """Initialize D-Bus service.

        Args:
            app_instance: Reference to the Omega13App instance
        """
        self.app: "Omega13App" = app_instance
        self.bus: MessageBus | None = None
        self.interface: RecorderInterface | None = None
        self._is_registered: bool = False

    async def register(self) -> None:
        """Register the D-Bus service.

        Connects to session bus and exports the service interface.

        Raises:
            DBusError: If service registration fails
        """
        try:
            # Connect to session bus
            self.bus = await MessageBus().connect()
            # Create interface with app reference
            self.interface = RecorderInterface(self.app)
            # Export the service
            self.bus.export(self.OBJECT_PATH, self.interface)
            # Request the service name
            _ = await self.bus.request_name(self.SERVICE_NAME)
            self._is_registered = True
        except Exception as e:
            raise DBusError("org.omega13.Recorder.RegistrationError", str(e))

    async def unregister(self) -> None:
        """Unregister the D-Bus service.

        Releases the service name and unexports the interface.
        """
        try:
            if self.bus and self._is_registered:
                # Release the service name
                _ = await self.bus.release_name(self.SERVICE_NAME)
                # Unexport the interface
                self.bus.unexport(self.OBJECT_PATH)
                self._is_registered = False
        except Exception:
            # Ignore errors during shutdown
            pass

    def is_registered(self) -> bool:
        """Check if service is currently registered.

        Returns:
            bool: True if service is active, False otherwise
        """
        return self._is_registered

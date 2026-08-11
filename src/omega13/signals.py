"""Signal handling for clean daemon shutdown."""

import signal
import logging
import threading
from typing import Callable, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Supported signal types for daemon control."""
    SIGTERM = signal.SIGTERM
    SIGINT = signal.SIGINT
    SIGHUP = signal.SIGHUP
    SIGUSR1 = signal.SIGUSR1


class ShutdownReason(Enum):
    """Reason for shutdown initiation."""
    SIGTERM = "SIGTERM"
    SIGINT = "SIGINT"
    ERROR = "ERROR"
    MANUAL = "MANUAL"


class SignalHandler:
    """
    Thread-safe signal handler for daemon lifecycle.

    Design principles from daemon-lifecycle-design.md:
    - Signal handlers must not perform I/O or acquire locks
    - Main loop checks flags at next iteration
    - Uses signal.siginterrupt(sig, False) to ensure system calls return EINTR
    - Python 3.5+ delivers signals to main thread automatically
    """

    def __init__(
        self,
        shutdown_callback: Optional[Callable[[ShutdownReason], None]] = None,
        reload_callback: Optional[Callable[[], None]] = None,
        status_callback: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize signal handler.

        Args:
            shutdown_callback: Called on SIGTERM/SIGINT with shutdown reason.
            reload_callback: Called on SIGHUP for config reload.
            status_callback: Called on SIGUSR1 for status dump.
        """
        self._shutdown_event = threading.Event()
        self._reload_event = threading.Event()
        self._status_event = threading.Event()
        self._shutdown_reason: Optional[ShutdownReason] = None
        self._shutdown_callback = shutdown_callback
        self._reload_callback = reload_callback
        self._status_callback = status_callback
        self._registered_signals: Set[int] = set()
        self._shutdown_initiated = False
        self._lock = threading.Lock()

    def _handle_signal(self, signum: int, frame) -> None:
        """Internal signal handler - sets flags only, no I/O."""
        signal_name = signal.Signals(signum).name

        with self._lock:
            if signum in (signal.SIGTERM, signal.SIGINT):
                if self._shutdown_initiated:
                    logger.debug("Duplicate %s signal ignored", signal_name)
                    return

                self._shutdown_initiated = True
                self._shutdown_reason = (
                    ShutdownReason.SIGTERM if signum == signal.SIGTERM
                    else ShutdownReason.SIGINT
                )
                logger.info("Received %s, initiating graceful shutdown", signal_name)
                self._shutdown_event.set()

                if self._shutdown_callback:
                    # Call from main thread via thread-safe mechanism
                    try:
                        self._shutdown_callback(self._shutdown_reason)
                    except Exception as e:
                        logger.error("Shutdown callback error: %s", e)

            elif signum == signal.SIGHUP:
                logger.info("Received SIGHUP, scheduling config reload")
                self._reload_event.set()
                if self._reload_callback:
                    try:
                        self._reload_callback()
                    except Exception as e:
                        logger.error("Reload callback error: %s", e)

            elif signum == signal.SIGUSR1:
                logger.info("Received SIGUSR1, scheduling status dump")
                self._status_event.set()
                if self._status_callback:
                    try:
                        self._status_callback()
                    except Exception as e:
                        logger.error("Status callback error: %s", e)

    def register(self, signals: Optional[list] = None) -> None:
        """
        Register signal handlers.

        Args:
            signals: List of signal numbers to handle. Defaults to SIGTERM, SIGINT, SIGHUP, SIGUSR1.
        """
        if signals is None:
            signals = [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGUSR1]

        for sig in signals:
            if sig in self._registered_signals:
                continue

            try:
                # Ensure system calls are interrupted (EINTR) so main loop can check flags
                signal.siginterrupt(sig, False)
                signal.signal(sig, self._handle_signal)
                self._registered_signals.add(sig)
                logger.debug("Registered handler for %s", signal.Signals(sig).name)
            except (OSError, ValueError) as e:
                logger.warning("Could not register handler for %s: %s", signal.Signals(sig).name, e)

    def unregister(self) -> None:
        """Unregister all signal handlers, restoring defaults."""
        for sig in self._registered_signals:
            try:
                signal.signal(sig, signal.SIG_DFL)
                logger.debug("Unregistered handler for %s", signal.Signals(sig).name)
            except (OSError, ValueError) as e:
                logger.warning("Could not unregister handler for %s: %s", signal.Signals(sig).name, e)
        self._registered_signals.clear()

    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Block until shutdown signal received.

        Args:
            timeout: Maximum time to wait in seconds. None = wait forever.

        Returns:
            True if shutdown event was set, False if timeout.
        """
        return self._shutdown_event.wait(timeout)

    def wait_for_reload(self, timeout: Optional[float] = None) -> bool:
        """Block until reload signal received."""
        return self._reload_event.wait(timeout)

    def wait_for_status(self, timeout: Optional[float] = None) -> bool:
        """Block until status dump signal received."""
        return self._status_event.wait(timeout)

    def clear_shutdown(self) -> None:
        """Clear shutdown flag (for testing or cancellation)."""
        with self._lock:
            self._shutdown_initiated = False
            self._shutdown_reason = None
            self._shutdown_event.clear()

    def clear_reload(self) -> None:
        """Clear reload flag."""
        self._reload_event.clear()

    def clear_status(self) -> None:
        """Clear status flag."""
        self._status_event.clear()

    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown was requested."""
        return self._shutdown_event.is_set()

    @property
    def reload_requested(self) -> bool:
        """Check if reload was requested."""
        return self._reload_event.is_set()

    @property
    def status_requested(self) -> bool:
        """Check if status dump was requested."""
        return self._status_event.is_set()

    @property
    def shutdown_reason(self) -> Optional[ShutdownReason]:
        """Get the reason for shutdown."""
        return self._shutdown_reason

    @property
    def is_shutdown_initiated(self) -> bool:
        """Check if shutdown has been initiated."""
        return self._shutdown_initiated


def create_signal_handler(
    shutdown_callback: Optional[Callable[[ShutdownReason], None]] = None,
    reload_callback: Optional[Callable[[], None]] = None,
    status_callback: Optional[Callable[[], None]] = None,
) -> SignalHandler:
    """
    Factory function to create and register a SignalHandler.

    Args:
        shutdown_callback: Called on SIGTERM/SIGINT.
        reload_callback: Called on SIGHUP.
        status_callback: Called on SIGUSR1.

    Returns:
        Configured SignalHandler instance.
    """
    handler = SignalHandler(
        shutdown_callback=shutdown_callback,
        reload_callback=reload_callback,
        status_callback=status_callback,
    )
    handler.register()
    return handler
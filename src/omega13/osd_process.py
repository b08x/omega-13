import sys
import logging
import signal
import gi
from dbus_next.glib import MessageBus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("osd_process")

from omega13.ui.osd import _lazy_init
_lazy_init()
from gi.repository import Gtk, GLib
from omega13.ui.osd import Omega13OSD

class OSDProcess:
    def __init__(self):
        self.app = Gtk.Application(application_id="org.omega13.osd.process")
        self.app.connect("activate", self._on_activate)
        self.window = None
        self.bus = None

    def _on_activate(self, app):
        self.window = Omega13OSD()
        self.window.set_application(app)
        
        # Connect to D-Bus
        try:
            self.bus = MessageBus().connect_sync()
            self.bus.add_match_string_sync("type='signal',interface='org.omega13.Recorder',member='OSDStateChanged'")
            self.bus.add_message_handler(self._on_message)
            logger.info("Connected to D-Bus and listening for OSDStateChanged signals")
        except Exception as e:
            logger.error(f"Failed to connect to D-Bus: {e}")

    def _on_message(self, msg):
        if msg.interface == "org.omega13.Recorder" and msg.member == "OSDStateChanged":
            try:
                state_type, text, timeout_ms = msg.body
                GLib.idle_add(self.window.show_status, text, state_type, timeout_ms)
            except Exception as e:
                logger.error(f"Error handling OSDStateChanged: {e}")
            return True
        return False

    def run(self):
        def on_quit(*args):
            logger.info("Shutting down OSD process")
            self.app.quit()
        signal.signal(signal.SIGTERM, on_quit)
        signal.signal(signal.SIGINT, on_quit)
        
        self.app.run(None)

def main():
    process = OSDProcess()
    process.run()

if __name__ == "__main__":
    main()

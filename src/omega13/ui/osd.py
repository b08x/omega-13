import gi
import cairo
import sys
from typing import Optional

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
try:
    gi.require_version('Gtk4LayerShell', '1.0')
    LAYER_SHELL_AVAILABLE = True
except ValueError:
    LAYER_SHELL_AVAILABLE = False

from gi.repository import Gtk, Gdk, GLib
if LAYER_SHELL_AVAILABLE:
    from gi.repository import Gtk4LayerShell

class Omega13OSD(Gtk.Window):
    def __init__(self):
        super().__init__()
        
        self.set_default_size(300, 60)
        self.set_title("Omega-13 OSD")
        self.set_decorated(False)
        
        self._status_text = "Ready"
        self._is_recording = False
        
        if LAYER_SHELL_AVAILABLE:
            Gtk4LayerShell.init_for_window(self)
            Gtk4LayerShell.set_namespace(self, "omega13-osd")
            Gtk4LayerShell.set_layer(self, Gtk4LayerShell.Layer.OVERLAY)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.BOTTOM, True)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.LEFT, False)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.RIGHT, False)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.TOP, False)
            Gtk4LayerShell.set_margin(self, Gtk4LayerShell.Edge.BOTTOM, 80)
            Gtk4LayerShell.set_exclusive_zone(self, -1)
            Gtk4LayerShell.set_keyboard_mode(self, Gtk4LayerShell.KeyboardMode.NONE)

        # Drawing area for Cairo
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_draw_func(self._on_draw)
        self.set_child(self.drawing_area)
        
        self._hide_timeout_id = 0

    def _on_draw(self, drawing_area, cr, width, height):
        # Allow drawing transparent background
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        # Draw background pill
        cr.set_source_rgba(0.1, 0.1, 0.1, 0.85)
        radius = min(width, height) / 2
        cr.arc(radius, radius, radius, 3.14159/2, 3.14159*3/2)
        cr.arc(width - radius, radius, radius, -3.14159/2, 3.14159/2)
        cr.fill()
        
        # Draw border
        cr.set_source_rgba(0.3, 0.3, 0.3, 1.0)
        cr.set_line_width(2.0)
        cr.arc(radius, radius, radius, 3.14159/2, 3.14159*3/2)
        cr.arc(width - radius, radius, radius, -3.14159/2, 3.14159/2)
        cr.close_path()
        cr.stroke()
        
        # Draw text
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(16)
        
        if self._is_recording:
            cr.set_source_rgb(1.0, 0.2, 0.2)
            cr.arc(radius + 5, height / 2, 6, 0, 2 * 3.14159)
            cr.fill()
            text_x = radius + 25
        else:
            text_x = radius + 10

        cr.set_source_rgb(0.9, 0.9, 0.9)
        te = cr.text_extents(self._status_text)
        
        # Auto-adjust width if text is too long (basic layout)
        if text_x + te.width + radius > width:
            # We don't dynamically resize the window here to avoid GTK warnings, 
            # but we can set the default size in show_status based on length.
            pass
            
        cr.move_to(text_x, height/2 + te.height/2 - 2)
        cr.show_text(self._status_text)

    def show_status(self, text: str, recording: bool = False, timeout_ms: int = 0):
        self._status_text = text
        self._is_recording = recording
        
        # Rough width calculation
        estimated_width = 150 + (len(text) * 8)
        self.set_size_request(estimated_width, 50)
        
        self.drawing_area.queue_draw()
        
        if not self.get_visible():
            self.set_visible(True)
            
        if self._hide_timeout_id:
            GLib.source_remove(self._hide_timeout_id)
            self._hide_timeout_id = 0
            
        if timeout_ms > 0:
            self._hide_timeout_id = GLib.timeout_add(timeout_ms, self._on_timeout)

    def _on_timeout(self):
        self.set_visible(False)
        self._hide_timeout_id = 0
        return False
        
class OSDManager:
    def __init__(self):
        self.app = Gtk.Application(application_id="org.omega13.osd", flags=gi.repository.Gio.ApplicationFlags.FLAGS_NONE)
        self.app.connect("activate", self._on_activate)
        self.window: Optional[Omega13OSD] = None
        self._started = False

    def _on_activate(self, app):
        self.window = Omega13OSD()
        self.window.set_application(app)

    def run_in_background(self):
        if not self._started:
            self._started = True
            import threading
            self.thread = threading.Thread(target=self.app.run, args=(None,), daemon=True)
            self.thread.start()

    def update(self, text: str, recording: bool = False, timeout_ms: int = 0):
        def _do_update():
            if self.window:
                self.window.show_status(text, recording, timeout_ms)
            return False
        if self._started:
            GLib.idle_add(_do_update)
            
    def quit(self):
        if self._started:
            GLib.idle_add(lambda: self.app.quit() or False)

osd_manager = OSDManager()

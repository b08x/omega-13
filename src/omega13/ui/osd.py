import gi
import cairo
import sys
import os
from typing import Optional
import ctypes

try:
    ctypes.CDLL("libgtk4-layer-shell.so", mode=ctypes.RTLD_GLOBAL)
except Exception:
    pass

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
        self._state_type = "normal"  # "normal", "recording", "success", "processing"
        
        # Animation state
        self._anim_tick = 0
        self._anim_timer_id = 0
        
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

    def _start_animation(self):
        if not self._anim_timer_id:
            self._anim_timer_id = GLib.timeout_add(500, self._on_anim_tick)
            
    def _stop_animation(self):
        if self._anim_timer_id:
            GLib.source_remove(self._anim_timer_id)
            self._anim_timer_id = 0
            
    def _on_anim_tick(self):
        self._anim_tick += 1
        self.drawing_area.queue_draw()
        return True

    def _on_draw(self, drawing_area, cr, width, height):
        # Allow drawing transparent background
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        # Draw background pill
        cr.set_source_rgba(0.12, 0.12, 0.14, 0.90)
        radius = min(width, height) / 2
        cr.arc(radius, radius, radius, 3.14159/2, 3.14159*3/2)
        cr.arc(width - radius, radius, radius, -3.14159/2, 3.14159/2)
        cr.fill()
        
        # Draw border
        cr.set_source_rgba(0.35, 0.35, 0.4, 1.0)
        cr.set_line_width(1.5)
        cr.arc(radius, radius, radius, 3.14159/2, 3.14159*3/2)
        cr.arc(width - radius, radius, radius, -3.14159/2, 3.14159/2)
        cr.close_path()
        cr.stroke()
        
        # Setup font
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(15)
        
        # Calculate indicator and text layout
        indicator_radius = 6
        text_padding = 12
        
        if self._state_type == "recording":
            # Blinking red dot
            if self._anim_tick % 2 == 0:
                cr.set_source_rgb(1.0, 0.3, 0.3)
            else:
                cr.set_source_rgb(0.6, 0.1, 0.1)
            cr.arc(radius, height / 2, indicator_radius, 0, 2 * 3.14159)
            cr.fill()
            text_x = radius + indicator_radius + text_padding
        elif self._state_type == "processing":
            # Pulsing yellow dot
            cr.set_source_rgba(0.9, 0.8, 0.2, 0.5 + (0.5 * (self._anim_tick % 2)))
            cr.arc(radius, height / 2, indicator_radius, 0, 2 * 3.14159)
            cr.fill()
            text_x = radius + indicator_radius + text_padding
        elif self._state_type == "success":
            # Solid green dot
            cr.set_source_rgb(0.2, 0.9, 0.4)
            cr.arc(radius, height / 2, indicator_radius, 0, 2 * 3.14159)
            cr.fill()
            text_x = radius + indicator_radius + text_padding
        else:
            text_x = radius

        # Draw text
        cr.set_source_rgb(0.95, 0.95, 0.95)
        te = cr.text_extents(self._status_text)
        cr.move_to(text_x, height/2 + te.height/2 - 1)
        cr.show_text(self._status_text)

    def show_status(self, text: str, state_type: str = "normal", timeout_ms: int = 0):
        self._status_text = text
        self._state_type = state_type
        
        if state_type in ("recording", "processing"):
            self._start_animation()
        else:
            self._stop_animation()
        
        # Exact width calculation using Cairo (dummy surface)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
        cr = cairo.Context(surface)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(15)
        te = cr.text_extents(text)
        
        # base_width = radius (left) + indicator + padding + text_width + radius (right)
        radius = 25  # half of 50px height
        extra = (radius + 6 + 12) if state_type != "normal" else radius
        exact_width = extra + te.width + radius + 15
        
        self.set_size_request(int(exact_width), 50)
        
        self.drawing_area.queue_draw()
        
        if not self.get_visible():
            self.set_visible(True)
        self.present()
            
        if self._hide_timeout_id:
            GLib.source_remove(self._hide_timeout_id)
            self._hide_timeout_id = 0
            
        if timeout_ms > 0:
            self._hide_timeout_id = GLib.timeout_add(timeout_ms, self._on_timeout)

    def _on_timeout(self):
        self.set_visible(False)
        self._hide_timeout_id = 0
        self._stop_animation()
        return False
        
import logging
logger = logging.getLogger(__name__)

from ..notifications import DesktopNotifier

class OSDManager:
    def __init__(self):
        self.app = Gtk.Application(application_id="org.omega13.osd", flags=gi.repository.Gio.ApplicationFlags.FLAGS_NONE)
        self.app.connect("activate", self._on_activate)
        self.window: Optional[Omega13OSD] = None
        self._started = False
        self._notifier = DesktopNotifier()
        self._layer_shell_active = False

    def _on_activate(self, app):
        logger.info("OSD GTK Application activated!")
        try:
            self.window = Omega13OSD()
            self.window.set_application(app)
            # Try to see if it bound as a layer surface successfully
            if LAYER_SHELL_AVAILABLE and hasattr(Gtk4LayerShell, 'is_layer_window'):
                self._layer_shell_active = Gtk4LayerShell.is_layer_window(self.window)
            else:
                self._layer_shell_active = LAYER_SHELL_AVAILABLE
            logger.info(f"OSD Window created. Layer shell active: {self._layer_shell_active}")
        except Exception as e:
            logger.error(f"Failed to create OSD Window: {e}")
            self.window = None

    def run_in_background(self):
        if not self._started:
            self._started = True
            logger.info("Starting OSD GTK thread...")
            import threading
            def run_app():
                logger.info("GTK loop starting")
                try:
                    self.app.run(None)
                except Exception as e:
                    logger.error(f"GTK app run error: {e}")
                logger.info("GTK loop exited")
            self.thread = threading.Thread(target=run_app, daemon=True)
            self.thread.start()

    def update(self, text: str, state_type: str = "normal", timeout_ms: int = 0):
        logger.debug(f"OSD Update requested: {text} ({state_type})")
        
        # Play auditory feedback
        if state_type == "recording":
            self._notifier.play_sound("device-added")
        elif state_type == "processing":
            self._notifier.play_sound("device-removed")
        elif state_type == "success":
            self._notifier.play_sound("complete")
            
        # Determine fallback behavior based on GNOME/compositor
        is_gnome = "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "")
        
        def _do_update():
            # If we are on GNOME or window creation failed, fallback to notify-send
            if is_gnome or not self.window:
                urgency = "normal" if state_type == "recording" else "low"
                self._notifier.notify(f"Omega-13: {state_type.title()}", text, urgency=urgency, timeout=max(2000, timeout_ms))
            else:
                self.window.show_status(text, state_type, timeout_ms)
            return False
            
        if self._started:
            GLib.idle_add(_do_update)
            
    def quit(self):
        if self._started:
            GLib.idle_add(lambda: self.app.quit() or False)

osd_manager = OSDManager()

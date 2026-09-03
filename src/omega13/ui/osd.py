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
            self._anim_timer_id = GLib.timeout_add(100, self._on_anim_tick)
            
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

        # Check for audio engine
        audio_engine = None
        if hasattr(self, 'osd_manager') and hasattr(self.osd_manager, 'audio_engine'):
            audio_engine = self.osd_manager.audio_engine

        # Layout metrics
        radius = min(width, height) / 2
        indicator_radius = 6
        text_padding = 12
        num_bars = 8
        bar_width = 3
        bar_gap = 2
        meter_width = (num_bars * bar_width) + ((num_bars - 1) * bar_gap) if audio_engine else 0
        meter_padding = 15 if meter_width > 0 else 0
        
        # Pill bounds (shrink slightly to fit meter if needed)
        pill_width = width - meter_width - meter_padding

        # Draw background pill
        cr.set_source_rgba(0.12, 0.12, 0.14, 0.90)
        cr.arc(radius, radius, radius, 3.14159/2, 3.14159*3/2)
        cr.arc(pill_width - radius, radius, radius, -3.14159/2, 3.14159/2)
        cr.fill()
        
        # Draw border
        cr.set_source_rgba(0.35, 0.35, 0.4, 1.0)
        cr.set_line_width(1.5)
        cr.arc(radius, radius, radius, 3.14159/2, 3.14159*3/2)
        cr.arc(pill_width - radius, radius, radius, -3.14159/2, 3.14159/2)
        cr.close_path()
        cr.stroke()
        
        # Setup font
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(15)
        
        display_text = self._status_text
        
        if self._state_type == "recording":
            # Blinking red dot
            if (self._anim_tick // 5) % 2 == 0:  # divide by 5 since tick is 100ms
                cr.set_source_rgb(1.0, 0.3, 0.3)
            else:
                cr.set_source_rgb(0.6, 0.1, 0.1)
            cr.arc(radius, height / 2, indicator_radius, 0, 2 * 3.14159)
            cr.fill()
            text_x = radius + indicator_radius + text_padding
            
            # Add duration
            if hasattr(self, '_state_start_time'):
                import time
                duration = time.time() - self._state_start_time
                display_text = f"{display_text} [{duration:.1f}s]"
        elif self._state_type == "processing":
            # Pulsing yellow dot
            pulse = 0.5 + (0.5 * abs((self._anim_tick % 10) - 5) / 5.0)
            cr.set_source_rgba(0.9, 0.8, 0.2, pulse)
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
        te = cr.text_extents(display_text)
        cr.move_to(text_x, height/2 + te.height/2 - 1)
        cr.show_text(display_text)
        
        # Draw Audio Waveform Meter
        if audio_engine:
            meter_x = pill_width + meter_padding / 2
            meter_h = 20
            meter_y = (height - meter_h) / 2
            
            # Get max RMS from channels
            try:
                import numpy as np
                rms_levels = audio_engine.signal_detector.rms_levels
                val = float(np.max(rms_levels)) if len(rms_levels) > 0 else 0.0
            except Exception:
                val = 0.0
                
            # Cap value between 0.0 and 1.0
            display_val = min(1.0, val * 4.0)
            
            import math
            for i in range(num_bars):
                # Pseudo-random multiplier for this bar to simulate frequency bands
                phase = self._anim_tick * 0.5 + i * 1.3
                bar_level = display_val * (0.3 + 0.7 * abs(math.sin(phase)))
                
                bar_h = 2 + (bar_level * 18) # Min 2px, Max 20px
                
                if display_val > 0.8:
                    cr.set_source_rgb(1.0, 0.2, 0.2) # Red
                elif display_val > 0.5:
                    cr.set_source_rgb(1.0, 0.8, 0.2) # Yellow
                else:
                    cr.set_source_rgb(0.2, 0.9, 0.4) # Green
                    
                bx = meter_x + i * (bar_width + bar_gap)
                by = meter_y + (meter_h - bar_h) / 2 # Center vertically
                
                # Draw rounded rectangle for bar
                cr.rectangle(bx, by, bar_width, bar_h)
                cr.fill()

    def show_status(self, text: str, state_type: str = "normal", timeout_ms: int = 0):
        if not hasattr(self, '_state_type') or self._state_type != state_type:
            import time
            self._state_start_time = time.time()
            
        self._status_text = text
        self._state_type = state_type
        
        if state_type in ("recording", "processing"):
            self._start_animation()
        else:
            self._start_animation() # Need animation for audio meters even if not recording
        
        # Exact width calculation using Cairo (dummy surface)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
        cr = cairo.Context(surface)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(15)
        
        # Calculate base text width
        te = cr.text_extents(text)
        
        # Add space for duration if it's a state that might show it
        extra_text_width = 0
        if state_type == "recording":
            te_duration = cr.text_extents(" [88.8s]")
            extra_text_width = te_duration.width
            
        # Add space for waveform meter
        meter_space = 55 # 38 width + 17 padding
        
        # base_width = radius (left) + indicator + padding + text_width + extra + radius (right)
        radius = 25  # half of 50px height
        extra = (radius + 6 + 12) if state_type != "normal" else radius
        exact_width = extra + te.width + extra_text_width + radius + meter_space + 15
        
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

    def set_audio_engine(self, engine):
        self.audio_engine = engine

    def _on_activate(self, app):
        logger.info("OSD GTK Application activated!")
        try:
            self.window = Omega13OSD()
            self.window.set_application(app)
            self.window.osd_manager = self  # Give window access to audio_engine
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
            
            # Check if a display is available before starting GTK
            import gi
            gi.require_version('Gtk', '4.0')
            from gi.repository import Gtk, Gdk
            Gtk.init_check()
            if not Gdk.Display.get_default():
                logger.warning("No display found. OSD will be disabled (fallback to notify-send).")
                return
                
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
        
        # Determine fallback behavior based on GNOME/compositor
        is_gnome = "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "")
        
        from ..config import ConfigManager
        config = ConfigManager()
        force_osd = config.get_force_osd()
        
        def _do_update():
            # If we are on GNOME or window creation failed, fallback to notify-send
            if (is_gnome and not force_osd) or not self.window:
                urgency = "normal" if state_type == "recording" else "low"
                self._notifier.notify(f"Omega-13: {state_type.title()}", text, urgency=urgency, timeout=max(2000, timeout_ms))
                
                # Play auditory feedback ONLY when OSD is disabled/fallback
                if state_type == "recording":
                    self._notifier.play_sound("device-added")
                elif state_type == "processing":
                    self._notifier.play_sound("device-removed")
                elif state_type == "success":
                    self._notifier.play_sound("complete")
            else:
                self.window.show_status(text, state_type, timeout_ms)
            return False
            
        if self._started:
            GLib.idle_add(_do_update)
            
    def quit(self):
        if self._started:
            GLib.idle_add(lambda: self.app.quit() or False)

osd_manager = OSDManager()

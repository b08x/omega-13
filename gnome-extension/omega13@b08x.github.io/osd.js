import Clutter from 'gi://Clutter';
import St from 'gi://St';
import Cairo from 'gi://cairo';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export class Omega13OSD {
    constructor() {
        this._actor = new St.DrawingArea({
            width: 400,
            height: 100,
            style_class: 'omega13-osd-container'
        });
        
        this._actor.set_position(
            (global.stage.width / 2) - 200,
            global.stage.height - 150
        );
        
        this._actor.connect('repaint', this._onRepaint.bind(this));
        
        this._data = [];
        this._visible = false;
        
        // State tracking
        this._stateType = "idle";
        this._stateText = "";
        this._animTick = 0;
        this._animTimerId = null;
        this._hideTimerId = null;
    }

    show() {
        if (!this._visible) {
            Main.layoutManager.addTopChrome(this._actor, {
                affectsInputRegion: false,
                trackFullscreen: true
            });
            this._visible = true;
        }
    }

    hide() {
        if (this._visible) {
            Main.layoutManager.removeChrome(this._actor);
            this._visible = false;
        }
        if (this._animTimerId) {
            GLib.source_remove(this._animTimerId);
            this._animTimerId = null;
        }
        if (this._hideTimerId) {
            GLib.source_remove(this._hideTimerId);
            this._hideTimerId = null;
        }
    }

    showState(stateType, text, timeoutMs) {
        this._stateType = stateType;
        this._stateText = text;
        this.show();
        
        if (!this._animTimerId) {
            this._animTimerId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
                this._animTick++;
                this._actor.queue_repaint();
                return GLib.SOURCE_CONTINUE;
            });
        }
        
        if (this._hideTimerId) {
            GLib.source_remove(this._hideTimerId);
            this._hideTimerId = null;
        }
        
        if (timeoutMs > 0) {
            this._hideTimerId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, timeoutMs, () => {
                this.hide();
                return GLib.SOURCE_REMOVE;
            });
        }
        this._actor.queue_repaint();
    }

    update(data) {
        this._data = data || [];
        if (this._visible) {
            this._actor.queue_repaint();
        }
    }

    destroy() {
        this.hide();
        this._actor.destroy();
    }

    _onRepaint(area) {
        let cr = area.get_context();
        let [width, height] = area.get_surface_size();

        // Draw background with rounded corners
        let radius = 10;
        cr.setSourceRGBA(0.1, 0.1, 0.1, 0.8);
        cr.arc(radius, radius, radius, Math.PI, 1.5 * Math.PI);
        cr.arc(width - radius, radius, radius, 1.5 * Math.PI, 2 * Math.PI);
        cr.arc(width - radius, height - radius, radius, 0, 0.5 * Math.PI);
        cr.arc(radius, height - radius, radius, 0.5 * Math.PI, Math.PI);
        cr.closePath();
        cr.fill();

        // Indicator
        let indicatorX = 30;
        let indicatorY = height / 2;
        let indicatorRadius = 8;
        
        if (this._stateType === "recording") {
            if ((this._animTick % 10) < 5) {
                cr.setSourceRGB(1.0, 0.3, 0.3); // Bright red
            } else {
                cr.setSourceRGB(0.5, 0.1, 0.1); // Dim red
            }
        } else if (this._stateType === "processing") {
            let alpha = 0.5 + 0.5 * (Math.abs((this._animTick % 20) - 10) / 10);
            cr.setSourceRGBA(0.9, 0.8, 0.2, alpha); // Pulsing amber
        } else if (this._stateType === "success") {
            cr.setSourceRGB(0.2, 0.9, 0.4); // Solid green
        } else if (this._stateType === "error") {
            cr.setSourceRGB(0.9, 0.2, 0.2); // Steady red
        } else {
            cr.setSourceRGBA(0.2, 0.9, 0.4, 0.3); // Dim green/blue
        }
        
        cr.arc(indicatorX, indicatorY, indicatorRadius, 0, 2 * Math.PI);
        cr.fill();
        
        // Text
        cr.setSourceRGB(1.0, 1.0, 1.0);
        cr.selectFontFace("Sans", Cairo.FontSlant.NORMAL, Cairo.FontWeight.BOLD);
        cr.setFontSize(14);
        cr.moveTo(indicatorX + 20, indicatorY + 5);
        cr.showText(this._stateText);

        if (!this._data || this._data.length === 0) return;

        // Draw waveform
        cr.setSourceRGBA(0.0, 0.9, 0.4, 1.0); // Vibrant green
        cr.setLineWidth(2.0);
        cr.setLineJoin(Cairo.LineJoin.ROUND);

        let centerY = height / 2;
        let meterWidth = 100; // right side
        let startX = width - meterWidth - 20;
        let step = meterWidth / (this._data.length > 1 ? this._data.length - 1 : 1);

        cr.moveTo(startX, centerY);
        for (let i = 0; i < this._data.length; i++) {
            let val = Math.min(this._data[i] * height * 1.5, (height / 2) - 10);
            let x = startX + (i * step);
            cr.moveTo(x, centerY - val);
            cr.lineTo(x, centerY + val);
        }
        cr.stroke();
    }
}

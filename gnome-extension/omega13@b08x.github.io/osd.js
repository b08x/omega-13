import Clutter from 'gi://Clutter';
import St from 'gi://St';
import Cairo from 'gi://cairo';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export class Omega13OSD {
    constructor() {
        this._actor = new St.DrawingArea({
            width: 400,
            height: 100,
            style_class: 'omega13-osd-container'
        });
        
        // Position it at the bottom center or bottom right.
        // Let's do bottom center for now.
        this._actor.set_position(
            (global.stage.width / 2) - 200,
            global.stage.height - 150
        );
        
        this._actor.connect('repaint', this._onRepaint.bind(this));
        
        this._data = [];
        this._visible = false;
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

        if (!this._data || this._data.length === 0) return;

        // Draw waveform
        cr.setSourceRGBA(0.0, 0.9, 0.4, 1.0); // Vibrant green
        cr.setLineWidth(2.0);
        cr.setLineJoin(Cairo.LineJoin.ROUND);

        let centerY = height / 2;
        let step = width / (this._data.length > 1 ? this._data.length - 1 : 1);

        cr.moveTo(0, centerY);
        for (let i = 0; i < this._data.length; i++) {
            // Assume rms values are reasonably small, e.g. 0 to 0.5
            // Multiply by a factor to make it visible
            let val = Math.min(this._data[i] * height * 1.5, (height / 2) - 10);
            
            // Draw a bar or continuous line. Let's do a continuous line for the upper half,
            // or just vertical bars for each point to look like a waveform.
            // Let's do a symmetric waveform around the center.
            let x = i * step;
            cr.moveTo(x, centerY - val);
            cr.lineTo(x, centerY + val);
        }
        cr.stroke();
    }
}

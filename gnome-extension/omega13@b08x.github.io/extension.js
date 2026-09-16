import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as Slider from 'resource:///org/gnome/shell/ui/slider.js';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import { Omega13DBusService } from './dbus.js';

export default class Omega13Extension extends Extension {
    enable() {
        console.log(`[Omega-13] Enabling extension ${this.uuid}`);
        this._dbusService = new Omega13DBusService();
        this._dbusService.export();

        this._indicator = new PanelMenu.Button(0.0, 'Omega-13', false);
        
        let icon = new St.Icon({
            icon_name: 'media-record-symbolic',
            style_class: 'system-status-icon'
        });
        this._indicator.add_child(icon);

        // OSD Toggle
        this._osdToggle = new PopupMenu.PopupSwitchMenuItem('OSD Display', true);
        this._osdToggle.connect('toggled', (item, state) => {
            this._callMethod('SetOSDEnabled', new GLib.Variant('(b)', [state]));
        });
        this._indicator.menu.addMenuItem(this._osdToggle);

        // Auto-Record Toggle
        this._autoRecordToggle = new PopupMenu.PopupSwitchMenuItem('Auto-Record', false);
        this._autoRecordToggle.connect('toggled', (item, state) => {
            this._callMethod('SetAutoRecordEnabled', new GLib.Variant('(b)', [state]));
        });
        this._indicator.menu.addMenuItem(this._autoRecordToggle);

        // Auto-Record Threshold Slider
        this._sliderItem = new PopupMenu.PopupBaseMenuItem({ activate: false });
        let sliderLabel = new St.Label({ text: 'Auto-Record Threshold', x_expand: true });
        this._thresholdSlider = new Slider.Slider(0.5); // Maps 0..1 to -60..0 dB
        this._thresholdSlider.x_expand = true;
        this._thresholdSlider.connect('notify::value', (slider) => {
            let threshold = -60.0 + (slider.value * 60.0);
            this._callMethod('SetAutoRecordThreshold', new GLib.Variant('(d)', [threshold]));
        });
        this._sliderItem.add_child(sliderLabel);
        this._sliderItem.add_child(this._thresholdSlider);
        this._indicator.menu.addMenuItem(this._sliderItem);

        // Transcription Menu
        this._transcriptionItem = new PopupMenu.PopupSubMenuMenuItem('Transcription');
        this._retryItem = new PopupMenu.PopupMenuItem('Retry failed transcription (0)');
        this._retryItem.connect('activate', () => {
            this._callMethod('RetryFailedTranscriptions', null);
        });
        
        this._transcriptionItem.menu.addMenuItem(this._retryItem);
        this._indicator.menu.addMenuItem(this._transcriptionItem);

        Main.panel.addToStatusArea('omega13-indicator', this._indicator);

        // Poll for failed transcriptions
        this._pollId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 2000, () => {
            this._pollFailures();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _callMethod(methodName, params, callback) {
        const bus = Gio.DBus.session;
        bus.call(
            'org.omega13.Recorder',
            '/org/omega13/Recorder',
            'org.omega13.Recorder',
            methodName,
            params,
            null,
            Gio.DBusCallFlags.NONE,
            -1,
            null,
            (connection, res) => {
                try {
                    let result = connection.call_finish(res);
                    if (callback) callback(result);
                } catch (e) {
                    // Ignore errors when daemon is not running
                }
            }
        );
    }

    _pollFailures() {
        this._callMethod('GetFailedTranscriptionCount', null, (result) => {
            if (result) {
                let count = result.unpack()[0];
                this._retryItem.label.text = `Retry failed transcription (${count})`;
                if (count > 0) {
                    this._retryItem.label.set_style('color: #ff5555; font-weight: bold;');
                } else {
                    this._retryItem.label.set_style('');
                }
            }
        });
    }

    disable() {
        console.log(`[Omega-13] Disabling extension ${this.uuid}`);
        if (this._pollId) {
            GLib.source_remove(this._pollId);
            this._pollId = null;
        }
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
        if (this._dbusService) {
            this._dbusService.unexport();
            this._dbusService = null;
        }
    }
}

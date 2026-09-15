import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import St from 'gi://St';
import Gio from 'gi://Gio';
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

        this._transcriptionItem = new PopupMenu.PopupSubMenuMenuItem('Transcription');
        
        this._retryItem = new PopupMenu.PopupMenuItem('Retry failed transcription');
        this._retryItem.connect('activate', () => {
            this._callRetryTranscription();
        });
        
        this._transcriptionItem.menu.addMenuItem(this._retryItem);
        this._indicator.menu.addMenuItem(this._transcriptionItem);

        Main.panel.addToStatusArea('omega13-indicator', this._indicator);
    }

    _callRetryTranscription() {
        const bus = Gio.DBus.session;
        bus.call(
            'org.omega13.Recorder',
            '/org/omega13/Recorder',
            'org.omega13.Recorder',
            'RetryTranscription',
            null,
            null,
            Gio.DBusCallFlags.NONE,
            -1,
            null,
            (connection, res) => {
                try {
                    connection.call_finish(res);
                } catch (e) {
                    console.error(`[Omega-13] Retry failed: ${e.message}`);
                }
            }
        );
    }

    disable() {
        console.log(`[Omega-13] Disabling extension ${this.uuid}`);
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

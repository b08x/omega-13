import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import { Omega13DBusService } from './dbus.js';

export default class Omega13Extension extends Extension {
    enable() {
        console.log(`[Omega-13] Enabling extension ${this.uuid}`);
        this._dbusService = new Omega13DBusService();
        this._dbusService.export();
    }

    disable() {
        console.log(`[Omega-13] Disabling extension ${this.uuid}`);
        if (this._dbusService) {
            this._dbusService.unexport();
            this._dbusService = null;
        }
    }
}

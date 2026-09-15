import Gio from 'gi://Gio';
import { Omega13OSD } from './osd.js';

const DBUS_INTERFACE = `
<node>
  <interface name="org.gnome.Shell.Extensions.Omega13">
    <method name="FocusWindow">
      <arg type="s" name="title" direction="in"/>
      <arg type="b" name="success" direction="out"/>
    </method>
    <method name="ShowOSD" />
    <method name="HideOSD" />
    <method name="UpdateWaveform">
      <arg type="ad" name="rms_data" direction="in"/>
    </method>
  </interface>
</node>`;

export class Omega13DBusService {
    constructor() {
        this._dbusImpl = Gio.DBusExportedObject.wrapJSObject(DBUS_INTERFACE, this);
        this._osd = new Omega13OSD();
    }

    export() {
        this._dbusImpl.export(Gio.DBus.session, '/org/gnome/Shell/Extensions/Omega13');
    }

    unexport() {
        this._dbusImpl.unexport();
        this._osd.destroy();
    }

    FocusWindow(title) {
        let success = false;
        const windowActors = global.get_window_actors();
        
        for (let actor of windowActors) {
            let win = actor.meta_window;
            if (win && win.get_title() === title) {
                win.activate(global.get_current_time());
                success = true;
                break;
            }
        }
        
        return success;
    }

    ShowOSD() {
        this._osd.show();
    }

    HideOSD() {
        this._osd.hide();
    }

    UpdateWaveform(rms_data) {
        let data = rms_data;
        if (rms_data) {
            if (typeof rms_data.deepUnpack === 'function') {
                data = rms_data.deepUnpack();
            } else if (typeof rms_data.unpack === 'function') {
                data = rms_data.unpack();
            }
        }
        this._osd.update(data);
    }
}

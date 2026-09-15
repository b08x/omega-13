# Omega-13 GNOME Shell Extension Plan

## Goal
Develop a native GNOME Shell Extension (for GNOME 49.9+) named `omega13-integration` that provides native text injection into specific windows (bypassing Wayland security restrictions) and renders an on-screen display (OSD) waveform using Clutter, solving the limitations of `gtk4-layer-shell` on GNOME.

## Architecture

The extension will be an ESM-based GNOME Shell Extension exposing a custom D-Bus interface `org.gnome.Shell.Extensions.Omega13`.

### 1. Extension Skeleton
*   **Directory:** `gnome-extension/omega13@b08x.github.io/`
*   `metadata.json`: Define UUID, name, description, shell versions (`"45"`, `"46"`, `"47"`, `"48"`, `"49"`, `"50"`).
*   `extension.js`: The main entry point. Will extend `Extension` from `resource:///org/gnome/shell/extensions/extension.js`.

### 2. D-Bus Interface (`dbus.js`)
*   Define `org.gnome.Shell.Extensions.Omega13` with methods:
    *   `FocusWindow(in s title, out b success)`: Iterates `global.get_window_actors()` to find the window by title and calls `.activate(global.get_current_time())`.
    *   `ShowOSD()`: Initializes and displays the Clutter/St OSD actor.
    *   `HideOSD()`: Destroys or hides the OSD actor.
    *   `UpdateWaveform(in ad rms_data)`: Updates the waveform drawing.

### 3. Native OSD (`osd.js`)
*   Create a `St.Widget` or `St.DrawingArea` (via Cairo) to render the waveform.
*   Add it to `Main.layoutManager.uiGroup` to ensure it floats above all windows globally without window borders.
*   Update the drawing based on the `rms_data` passed via D-Bus.

### 4. Integration with Omega-13 Daemon
*   **`src/omega13/injection.py`**: Update `_focus_whisp_window()` to first attempt calling our new `org.gnome.Shell.Extensions.Omega13.FocusWindow` method.
*   **`src/omega13/ui/osd.py`**: Replace or augment the GTK4 Layer Shell implementation. When running on GNOME Wayland, it should delegate OSD rendering to the GNOME extension via D-Bus (`ShowOSD`, `UpdateWaveform`, `HideOSD`).

## Steps for Execution
1. Scaffold the extension files (`metadata.json`, `extension.js`, `dbus.js`, `osd.js`).
2. Implement the D-Bus service export and window focus logic.
3. Test window focusing independently via `busctl`.
4. Implement the Clutter-based OSD rendering.
5. Update the Omega-13 Python daemon to consume the new D-Bus API.
6. Add extension installation instructions to `install.sh`.

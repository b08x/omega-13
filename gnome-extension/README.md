# Omega13 GNOME Extension

This module provides the GNOME Shell extension component for Omega13. Its primary purpose is to enable native Cairo On-Screen Display (OSD) waveform drawing and reliable window activation on GNOME Wayland sessions.

## Compatibility

This extension supports GNOME versions **45 through 50**.

## Build and Installation

To manually package and install the extension:

1. **Package the extension:**
   ```bash
   gnome-extensions pack omega13@b08x.github.io
   ```

2. **Install to your local extensions directory:**
   Ensure the extension is extracted or installed to the following path:
   `~/.local/share/gnome-shell/extensions/omega13@b08x.github.io`

3. **Activate the extension:**
   ```bash
   gnome-extensions enable omega13@b08x.github.io
   ```
   *(Note: On Wayland, you may need to log out and log back in before the extension becomes visible and can be enabled.)*

## D-Bus Public Interface

The extension exposes a public D-Bus interface for interacting with the OSD and window management.

- **Bus Name:** `org.gnome.Shell`
- **Object Path:** `/org/gnome/Shell/Extensions/Omega13`
- **Interface:** `org.gnome.Shell.Extensions.Omega13`

### Methods

- **`FocusWindow(s title) -> b`**
  Attempts to focus a window matching the given `title`. Returns a boolean indicating success (`true`) or failure (`false`).

- **`ShowOSD() -> void`**
  Displays the Omega13 On-Screen Display (OSD).

- **`HideOSD() -> void`**
  Hides the Omega13 On-Screen Display (OSD).

- **`UpdateWaveform(ad rms_data) -> void`**
  Updates the OSD waveform drawing with an array of double values (`ad`) representing RMS audio data.

## Troubleshooting and CLI Inspection

You can interact with and inspect the extension's D-Bus interface from the command line using `busctl`. This is useful for debugging and manual testing.

### Example `busctl` Recipes

**Show the OSD:**
```bash
busctl --user call org.gnome.Shell \
  /org/gnome/Shell/Extensions/Omega13 \
  org.gnome.Shell.Extensions.Omega13 \
  ShowOSD
```

**Hide the OSD:**
```bash
busctl --user call org.gnome.Shell \
  /org/gnome/Shell/Extensions/Omega13 \
  org.gnome.Shell.Extensions.Omega13 \
  HideOSD
```

**Focus a Specific Window:**
```bash
busctl --user call org.gnome.Shell \
  /org/gnome/Shell/Extensions/Omega13 \
  org.gnome.Shell.Extensions.Omega13 \
  FocusWindow s "Mozilla Firefox"
```

**Update Waveform Data:**
```bash
busctl --user call org.gnome.Shell \
  /org/gnome/Shell/Extensions/Omega13 \
  org.gnome.Shell.Extensions.Omega13 \
  UpdateWaveform ad 3 0.1 0.5 0.3
```

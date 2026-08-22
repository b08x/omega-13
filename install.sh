#!/bin/bash
# Omega-13 Local User Installer (XDG compliant, powered by Gum)

set -e

# Verify gum is installed
command -v gum >/dev/null || { echo 'gum is required for this installer; please install it (e.g. pacman -S gum, apt install gum) or use bootstrap.sh' >&2; exit 1; }

# Prevent running as root
if [ "$EUID" -eq 0 ]; then
    gum style --foreground 196 "❌ This is a local user installer. Please DO NOT run as root (no sudo)."
    exit 1
fi

gum style --border double --margin "1" --padding "1 2" --border-foreground 212 --foreground 212 "Omega-13 Local Installer"

# Respect XDG Base Directory specification
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

DEST_DIR="$XDG_DATA_HOME/omega13"
BIN_LINK="$XDG_BIN_HOME/omega13"
SYSTEMD_USER_DIR="$XDG_CONFIG_HOME/systemd/user"
SERVICE_FILE="$SYSTEMD_USER_DIR/omega13.service"

if ! gum confirm "Install Omega-13 to $DEST_DIR ?"; then
    gum style --foreground 240 "Installation cancelled."
    exit 0
fi

# Step 1: Copy files
mkdir -p "$DEST_DIR"
gum spin --title "Copying files to $DEST_DIR..." -- rsync -a --exclude='.git' --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='logs' --exclude='tests' ./ "$DEST_DIR/"

gum style --foreground 76 "✅ Files copied to $DEST_DIR"

# Step 2: Setup Python environment
cd "$DEST_DIR"

if command -v uv >/dev/null; then
    gum spin --title "Setting up Python virtual environment (uv)..." -- bash -c "uv venv >/dev/null && uv sync >/dev/null"
else
    gum spin --title "Setting up Python virtual environment (pip)..." -- bash -c "python3 -m venv .venv && .venv/bin/pip install -e . >/dev/null"
fi

gum style --foreground 76 "✅ Virtual environment prepared"

# Step 3: Symlink
mkdir -p "$XDG_BIN_HOME"
ln -sf "$DEST_DIR/.venv/bin/omega13" "$BIN_LINK"
gum style --foreground 76 "✅ Created symlink at $BIN_LINK"

# Step 4: Systemd user service
mkdir -p "$SYSTEMD_USER_DIR"
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Omega-13 Retroactive Audio Recorder
After=sound.target pipewire.service jack.service
Wants=sound.target

[Service]
Type=simple
ExecStart=$DEST_DIR/.venv/bin/omega13 --no-daemon
WorkingDirectory=$DEST_DIR
Restart=on-failure
RestartSec=5
Environment="DISPLAY=:0"
Environment="WAYLAND_DISPLAY=wayland-0"

[Install]
WantedBy=default.target
EOF

gum spin --title "Reloading systemd user daemon..." -- systemctl --user daemon-reload
gum style --foreground 76 "✅ Systemd service installed at $SERVICE_FILE"

# Step 5: Final instructions
gum style --border normal --margin "1" --padding "1 2" --border-foreground 76 --foreground 76 "🎉 Installation Complete!"

echo ""
echo "To start the daemon, run:"
echo "  systemctl --user enable --now omega13"
echo ""
echo "Ensure $XDG_BIN_HOME is in your PATH to use the 'omega13' command from anywhere."
echo ""

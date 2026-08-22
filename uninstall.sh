#!/bin/bash
# Omega-13 Local User Uninstaller (XDG compliant)

set -e

# Verify gum is installed
command -v gum >/dev/null || { echo 'gum is required; please install it first.' >&2; exit 1; }

# Prevent running as root
if [ "$EUID" -eq 0 ]; then
    gum style --foreground 196 "❌ This is a local user uninstaller. Please DO NOT run as root (no sudo)."
    exit 1
fi

gum style --border double --margin "1" --padding "1 2" --border-foreground 196 --foreground 196 "Omega-13 Local Uninstaller"

# Respect XDG Base Directory specification
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

DEST_DIR="$XDG_DATA_HOME/omega13"
BIN_LINK="$XDG_BIN_HOME/omega13"
SYSTEMD_USER_DIR="$XDG_CONFIG_HOME/systemd/user"
SERVICE_FILE="$SYSTEMD_USER_DIR/omega13.service"

if ! gum confirm "Are you sure you want to completely remove Omega-13 and its systemd service?"; then
    gum style --foreground 240 "Uninstallation cancelled."
    exit 0
fi

# Step 1: Stop and disable systemd service
if systemctl --user is-active --quiet omega13 2>/dev/null || systemctl --user is-enabled --quiet omega13 2>/dev/null; then
    gum spin --title "Stopping and disabling systemd service..." -- bash -c "systemctl --user disable --now omega13 2>/dev/null || true"
    gum style --foreground 76 "✅ Systemd service stopped and disabled"
fi

# Step 2: Remove systemd service file
if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    gum spin --title "Reloading systemd user daemon..." -- systemctl --user daemon-reload
    gum style --foreground 76 "✅ Removed service file: $SERVICE_FILE"
fi

# Step 3: Remove symlink
if [ -L "$BIN_LINK" ]; then
    rm -f "$BIN_LINK"
    gum style --foreground 76 "✅ Removed symlink: $BIN_LINK"
fi

# Step 4: Remove application directory
if [ -d "$DEST_DIR" ]; then
    gum spin --title "Removing application files in $DEST_DIR..." -- rm -rf "$DEST_DIR"
    gum style --foreground 76 "✅ Removed application directory: $DEST_DIR"
fi

# Final instructions
gum style --border normal --margin "1" --padding "1 2" --border-foreground 76 --foreground 76 "👋 Uninstallation Complete!"
echo "Omega-13 has been completely removed from your local environment."
echo ""

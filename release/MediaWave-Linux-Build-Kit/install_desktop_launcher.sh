#!/usr/bin/env bash
# install_desktop_launcher.sh — Install MediaWave desktop launcher for current user
#
# Copies MediaWave.desktop to ~/.local/share/applications/ and patches
# the Exec= and Icon= paths to point to this folder.
#
# Usage: bash install_desktop_launcher.sh
# No sudo required — installs for current user only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_SRC="$SCRIPT_DIR/MediaWave.desktop"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_DST="$DESKTOP_DIR/MediaWave.desktop"
LAUNCHER="$SCRIPT_DIR/run_mediawave.sh"
ICON="$SCRIPT_DIR/logos/MW2K_appicon.png"

echo ""
echo "MediaWave — Desktop Launcher Installer"
echo "======================================="
echo ""

if [[ ! -f "$DESKTOP_SRC" ]]; then
    echo "ERROR: MediaWave.desktop not found at $DESKTOP_SRC"
    exit 1
fi

if [[ ! -f "$LAUNCHER" ]]; then
    echo "ERROR: run_mediawave.sh not found at $LAUNCHER"
    exit 1
fi

echo "Install location : $DESKTOP_DST"
echo "Launcher path    : $LAUNCHER"
echo "Icon path        : $ICON"
echo ""

mkdir -p "$DESKTOP_DIR"

# Patch the template paths
sed \
    -e "s|Exec=/REPLACE_WITH_INSTALL_PATH/run_mediawave.sh|Exec=$LAUNCHER|g" \
    -e "s|Icon=/REPLACE_WITH_INSTALL_PATH/logos/MW2K_appicon.png|Icon=$ICON|g" \
    "$DESKTOP_SRC" > "$DESKTOP_DST"

chmod 644 "$DESKTOP_DST"

# Refresh desktop database if available
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo "Done. MediaWave should now appear in your application launcher."
echo ""
echo "To remove the launcher:"
echo "  rm \"$DESKTOP_DST\""
echo ""

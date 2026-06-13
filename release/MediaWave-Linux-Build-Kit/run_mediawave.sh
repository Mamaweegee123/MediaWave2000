#!/usr/bin/env bash
# run_mediawave.sh — MediaWave Linux launcher
#
# Usage: ./run_mediawave.sh
#
# Finds and launches the MediaWave2000 executable from the same folder.
# Falls back to a helpful error message if the executable is missing.

set -euo pipefail

# Resolve the directory this script lives in, handling symlinks and spaces.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

EXE="$SCRIPT_DIR/MediaWave2000/MediaWave2000"

# ── Qt / display environment ─────────────────────────────────────────────────
# Prefer native Wayland when available; fall back to xcb (X11) otherwise.
# Uncomment the line below to force X11 if you hit Wayland rendering issues:
# export QT_QPA_PLATFORM=xcb

# Suppress Qt scaling warnings on mixed-DPI setups (cosmetic only).
export QT_LOGGING_RULES="${QT_LOGGING_RULES:-*.debug=false;qt.qpa.fonts.warning=false}"

# Keep Qt from choosing a platform plugin that needs root or is unavailable.
export QT_QPA_PLATFORMTHEME="${QT_QPA_PLATFORMTHEME:-}"

# ── GStreamer — point at bundled plugins if present ──────────────────────────
GST_PLUGIN_DIR="$SCRIPT_DIR/MediaWave2000/_internal/gst-plugins"
if [[ -d "$GST_PLUGIN_DIR" ]]; then
    export GST_PLUGIN_PATH="$GST_PLUGIN_DIR${GST_PLUGIN_PATH:+:$GST_PLUGIN_PATH}"
fi

# ── Sanity checks ────────────────────────────────────────────────────────────
if [[ ! -f "$EXE" ]]; then
    echo ""
    echo "ERROR: MediaWave2000 executable not found at:"
    echo "  $EXE"
    echo ""
    echo "The portable release must be built with PyInstaller on a Linux machine first."
    echo "See README-LINUX.md for build instructions."
    echo ""
    echo "To check all dependencies first, run:"
    echo "  bash \"$SCRIPT_DIR/check_linux_deps.sh\""
    echo ""
    exit 1
fi

if [[ ! -x "$EXE" ]]; then
    echo "Making MediaWave2000 executable..."
    chmod +x "$EXE"
fi

# ── Display check ────────────────────────────────────────────────────────────
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo ""
    echo "ERROR: No display found (DISPLAY and WAYLAND_DISPLAY are both unset)."
    echo "MediaWave requires a graphical desktop session."
    echo ""
    exit 1
fi

# ── Launch ───────────────────────────────────────────────────────────────────
cd "$SCRIPT_DIR"
exec "$EXE" "$@"

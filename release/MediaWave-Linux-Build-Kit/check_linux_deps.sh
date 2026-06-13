#!/usr/bin/env bash
# check_linux_deps.sh — MediaWave Linux dependency checker
#
# MediaWave uses Qt Multimedia (GStreamer backend on Linux) for all
# video/audio playback — NOT mpv or libmpv.
# Required: GStreamer + codec plugins. See README-LINUX.md.
#
# Usage: bash check_linux_deps.sh

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
RESET='\033[0m'

PASS=0
WARN=0
FAIL=0

ok()   { echo -e "  ${GREEN}[OK]${RESET}      $*"; ((PASS++)); }
warn() { echo -e "  ${YELLOW}[WARN]${RESET}    $*"; ((WARN++)); }
fail() { echo -e "  ${RED}[MISSING]${RESET} $*"; ((FAIL++)); }
info() { echo -e "  ${CYAN}[INFO]${RESET}    $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${BOLD}MediaWave Linux Dependency Check${RESET}"
echo "=================================="
echo ""
echo "Playback engine: Qt Multimedia via GStreamer (NOT mpv)"
echo ""

# ── Executable / Python ──────────────────────────────────────────────────────
echo -e "${BOLD}MediaWave executable${RESET}"

HAVE_EXE=false
if [[ -f "$SCRIPT_DIR/MediaWave2000/MediaWave2000" ]]; then
    if [[ -x "$SCRIPT_DIR/MediaWave2000/MediaWave2000" ]]; then
        ok "MediaWave2000 executable found and is executable"
        HAVE_EXE=true
    else
        warn "MediaWave2000 found but not executable — run: chmod +x \"$SCRIPT_DIR/MediaWave2000/MediaWave2000\""
        HAVE_EXE=true
    fi
else
    warn "MediaWave2000 executable not found (build with PyInstaller first)"
    info "See README-LINUX.md for build instructions"
fi

if [[ "$HAVE_EXE" == "false" ]]; then
    echo ""
    echo -e "${BOLD}Python (source-run fallback)${RESET}"
    if command -v python3 &>/dev/null; then
        PY_VER=$(python3 --version 2>&1)
        ok "python3 found: $PY_VER"
    else
        fail "python3 not found"
        info "Ubuntu/Debian/Mint: sudo apt install python3 python3-venv python3-pip"
        info "Fedora:             sudo dnf install python3"
        info "Arch/Manjaro:       sudo pacman -S python"
    fi
fi

# ── GStreamer — required for all video/audio playback ───────────────────────
# Qt Multimedia on Linux uses GStreamer as its media backend.
# No GStreamer = no video, no audio, no channel playback.
echo ""
echo -e "${BOLD}GStreamer (required for playback)${RESET}"
echo -e "  ${CYAN}[NOTE]${RESET}    MediaWave uses Qt Multimedia → GStreamer, not mpv or libmpv."
echo -e "  ${CYAN}[NOTE]${RESET}    Both the core library and codec plugins are required."

GST_OK=false
if command -v gst-launch-1.0 &>/dev/null; then
    GST_VER=$(gst-launch-1.0 --version 2>&1 | head -1)
    ok "gst-launch-1.0 found: $GST_VER"
    GST_OK=true
else
    fail "gst-launch-1.0 not found — GStreamer is not installed or not on PATH"
fi

if command -v gst-inspect-1.0 &>/dev/null; then
    ok "gst-inspect-1.0 found"
else
    warn "gst-inspect-1.0 not found (included with GStreamer core)"
fi

# Check for required GStreamer plugins by probing with gst-inspect-1.0
if command -v gst-inspect-1.0 &>/dev/null; then
    echo ""
    echo -e "  ${BOLD}GStreamer plugin check:${RESET}"

    # Core plugins — almost always present if GStreamer is installed at all
    check_gst_plugin() {
        local plugin="$1"
        local label="${2:-$plugin}"
        if gst-inspect-1.0 "$plugin" &>/dev/null 2>&1; then
            ok "GStreamer plugin: $label"
        else
            fail "GStreamer plugin missing: $label"
        fi
    }

    # Playbin — the high-level playback element Qt Multimedia uses
    check_gst_plugin "playbin"  "playbin (core playback pipeline)"

    # Video output
    check_gst_plugin "videoconvert" "videoconvert"
    check_gst_plugin "autovideosink" "autovideosink"

    # Audio output
    check_gst_plugin "autoaudiosink" "autoaudiosink"
    check_gst_plugin "volume"        "volume"

    # Demuxers and containers (gst-plugins-good)
    check_gst_plugin "qtdemux"   "qtdemux (MP4/MOV — gst-plugins-good)"
    check_gst_plugin "matroskademux" "matroskademux (MKV — gst-plugins-good)"

    # Video decoders — H.264 is essential for most local media
    if gst-inspect-1.0 avdec_h264 &>/dev/null 2>&1; then
        ok "GStreamer plugin: avdec_h264 (H.264 decoder — gst-libav)"
    elif gst-inspect-1.0 openh264dec &>/dev/null 2>&1; then
        ok "GStreamer plugin: openh264dec (H.264 decoder — alternative)"
    else
        fail "No H.264 decoder found — install gst-libav (Ubuntu: gstreamer1.0-libav)"
        info "Ubuntu/Debian/Mint: sudo apt install gstreamer1.0-libav"
        info "Fedora:             sudo dnf install gstreamer1-libav  (RPM Fusion required)"
        info "Arch/Manjaro:       sudo pacman -S gst-libav"
    fi

    # H.265 / HEVC — common on modern files, gst-plugins-bad or gst-libav
    if gst-inspect-1.0 avdec_hevc &>/dev/null 2>&1 || gst-inspect-1.0 libde265dec &>/dev/null 2>&1; then
        ok "GStreamer plugin: H.265/HEVC decoder found"
    else
        warn "No H.265/HEVC decoder found — newer files may not play"
        info "Ubuntu/Debian/Mint: sudo apt install gstreamer1.0-libav gstreamer1.0-plugins-bad"
        info "Arch/Manjaro:       sudo pacman -S gst-libav gst-plugins-bad"
    fi

    # AAC audio — very common
    if gst-inspect-1.0 avdec_aac &>/dev/null 2>&1 || gst-inspect-1.0 faad &>/dev/null 2>&1; then
        ok "GStreamer plugin: AAC audio decoder found"
    else
        warn "No AAC audio decoder found — some MP4 files may have no audio"
        info "Ubuntu/Debian/Mint: sudo apt install gstreamer1.0-libav"
        info "Arch/Manjaro:       sudo pacman -S gst-libav"
    fi

    # HLS — needed for NetTV live streams
    if gst-inspect-1.0 hlsdemux &>/dev/null 2>&1; then
        ok "GStreamer plugin: hlsdemux (HLS live streams — gst-plugins-bad)"
    else
        warn "hlsdemux not found — HLS/live streams in NetTV may not play"
        info "Ubuntu/Debian/Mint: sudo apt install gstreamer1.0-plugins-bad"
        info "Fedora:             sudo dnf install gstreamer1-plugins-bad-free"
        info "Arch/Manjaro:       sudo pacman -S gst-plugins-bad"
    fi

else
    if [[ "$GST_OK" == "false" ]]; then
        info "Install GStreamer first, then re-run this check for plugin details."
        info "Ubuntu/Debian/Mint: sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav"
        info "Fedora:             sudo dnf install gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-bad-free gstreamer1-plugins-ugly gstreamer1-libav  (RPM Fusion needed)"
        info "Arch/Manjaro:       sudo pacman -S gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly gst-libav"
    fi
fi

# ── ffmpeg / ffprobe ─────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}FFmpeg (conversion + media probing)${RESET}"

if command -v ffmpeg &>/dev/null; then
    FF_VER=$(ffmpeg -version 2>&1 | head -1)
    ok "ffmpeg found: $FF_VER"
else
    fail "ffmpeg not found — MediaWave Converter and media probing will not work"
    info "Ubuntu/Debian/Mint: sudo apt install ffmpeg"
    info "Fedora:             sudo dnf install ffmpeg  (RPM Fusion required)"
    info "Arch/Manjaro:       sudo pacman -S ffmpeg"
fi

if command -v ffprobe &>/dev/null; then
    ok "ffprobe found"
else
    fail "ffprobe not found — install ffmpeg (ffprobe is included)"
fi

# ── yt-dlp ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}yt-dlp (optional — NetTV only)${RESET}"

if command -v yt-dlp &>/dev/null; then
    YTDLP_VER=$(yt-dlp --version 2>&1 | head -1)
    ok "yt-dlp found: $YTDLP_VER"
elif python3 -c "import yt_dlp" &>/dev/null 2>&1; then
    ok "yt-dlp found as Python module"
else
    warn "yt-dlp not found — NetTV streaming channels will not work"
    info "Recommended:        pipx install yt-dlp"
    info "Ubuntu/Debian/Mint: sudo apt install yt-dlp  (may be outdated — pipx preferred)"
    info "Fedora:             sudo dnf install yt-dlp"
    info "Arch/Manjaro:       sudo pacman -S yt-dlp"
fi

# ── Qt platform / display ────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Display server${RESET}"

if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    ok "Wayland session detected (WAYLAND_DISPLAY=$WAYLAND_DISPLAY)"
    info "Qt will use the Wayland backend. If you see rendering issues, try:"
    info "  QT_QPA_PLATFORM=xcb ./run_mediawave.sh"
elif [[ -n "${DISPLAY:-}" ]]; then
    ok "X11 session detected (DISPLAY=$DISPLAY)"
else
    warn "No DISPLAY or WAYLAND_DISPLAY set — MediaWave requires a graphical session"
fi

# Check for the xcb platform plugin dependencies (needed even on Wayland fallback)
echo ""
echo -e "${BOLD}Qt xcb platform libraries${RESET}"
XCB_OK=true
for lib in libxcb.so.1 libxcb-icccm.so.4 libxcb-xinerama.so.0; do
    if ldconfig -p 2>/dev/null | grep -q "$lib"; then
        ok "$lib"
    else
        # Don't hard-fail — library names vary; just note it
        warn "$lib not found in ldconfig (may be under a different name or not needed on Wayland-only)"
        XCB_OK=false
    fi
done
if [[ "$XCB_OK" == "false" ]]; then
    info "If MediaWave fails to start with 'cannot load xcb platform plugin', install:"
    info "  Ubuntu/Debian/Mint: sudo apt install libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0"
fi

# ── Config/cache writability ─────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Config / cache directory${RESET}"

XDG_DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
MW_DATA="$XDG_DATA/MediaWave2000"

if mkdir -p "$MW_DATA" 2>/dev/null; then
    ok "Data directory writable: $MW_DATA"
else
    fail "Cannot write to $MW_DATA — check permissions"
fi

# ── PySide6 (only relevant for source-run) ───────────────────────────────────
if [[ "$HAVE_EXE" == "false" ]]; then
    echo ""
    echo -e "${BOLD}PySide6 (source-run only — not needed with packaged exe)${RESET}"
    if python3 -c "import PySide6" &>/dev/null 2>&1; then
        PS6_VER=$(python3 -c "import PySide6; print(PySide6.__version__)" 2>/dev/null || echo "unknown")
        ok "PySide6 found: $PS6_VER"
    else
        fail "PySide6 not found"
        info "Install in a virtualenv:"
        info "  python3 -m venv venv && source venv/bin/activate && pip install PySide6"
    fi
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=================================="
echo -e "${BOLD}Summary${RESET}"
echo -e "  ${GREEN}OK:${RESET}      $PASS"
echo -e "  ${YELLOW}Warnings:${RESET} $WARN"
echo -e "  ${RED}Missing:${RESET}  $FAIL"
echo ""

if [[ $FAIL -gt 0 ]]; then
    echo -e "${RED}Some required dependencies are missing. Install them before launching MediaWave.${RESET}"
    echo -e "Run ${BOLD}bash install_linux_deps.sh${RESET} to see distro-specific install commands."
    exit 1
elif [[ $WARN -gt 0 ]]; then
    echo -e "${YELLOW}Some optional dependencies are missing. MediaWave will run but some features may not work.${RESET}"
    exit 0
else
    echo -e "${GREEN}All checks passed. MediaWave should be ready to launch.${RESET}"
    echo -e "Run: ${BOLD}./run_mediawave.sh${RESET}"
    exit 0
fi

#!/usr/bin/env bash
# install_linux_deps.sh — MediaWave Linux dependency installer
#
# MediaWave uses Qt Multimedia → GStreamer for playback. NOT mpv.
# This script detects your distro and prints the install commands.
# It does NOT run them automatically — copy and paste to install.
#
# Usage: bash install_linux_deps.sh

set -euo pipefail

BOLD='\033[1m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RESET='\033[0m'

echo ""
echo -e "${BOLD}MediaWave Linux — Dependency Install Helper${RESET}"
echo "============================================"
echo ""
echo "Playback engine: Qt Multimedia via GStreamer (NOT mpv)"
echo ""
echo "This script detects your Linux distribution and shows"
echo "the install commands. It does NOT run them automatically."
echo ""

# ── Distro detection ─────────────────────────────────────────────────────────
DISTRO=""
DISTRO_LIKE=""
PRETTY_NAME=""

if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    DISTRO="${ID:-unknown}"
    DISTRO_LIKE="${ID_LIKE:-}"
    PRETTY_NAME="${PRETTY_NAME:-$DISTRO}"
fi

is_debian_like() {
    [[ "$DISTRO" == "ubuntu" || "$DISTRO" == "debian" || "$DISTRO" == "linuxmint" \
       || "$DISTRO" == "pop" || "$DISTRO" == "elementary" || "$DISTRO" == "zorin" ]] \
        || echo "$DISTRO_LIKE" | grep -qE "debian|ubuntu"
}

is_fedora_like() {
    [[ "$DISTRO" == "fedora" || "$DISTRO" == "rhel" || "$DISTRO" == "centos" \
       || "$DISTRO" == "rocky" || "$DISTRO" == "alma" ]] \
        || echo "$DISTRO_LIKE" | grep -qE "fedora|rhel"
}

is_arch_like() {
    [[ "$DISTRO" == "arch" || "$DISTRO" == "manjaro" || "$DISTRO" == "endeavouros" \
       || "$DISTRO" == "garuda" ]] \
        || echo "$DISTRO_LIKE" | grep -q "arch"
}

echo -e "${CYAN}Detected distro:${RESET} $PRETTY_NAME"
echo ""

# ── Show install commands ────────────────────────────────────────────────────

show_ubuntu() {
    echo -e "${BOLD}Ubuntu / Debian / Linux Mint — install commands:${RESET}"
    echo ""
    echo -e "${YELLOW}  # 1. System packages${RESET}"
    echo "  sudo apt update"
    echo "  sudo apt install \\"
    echo "    python3 python3-venv python3-pip \\"
    echo "    ffmpeg \\"
    echo "    gstreamer1.0-tools \\"
    echo "    gstreamer1.0-plugins-base \\"
    echo "    gstreamer1.0-plugins-good \\"
    echo "    gstreamer1.0-plugins-bad \\"
    echo "    gstreamer1.0-plugins-ugly \\"
    echo "    gstreamer1.0-libav \\"
    echo "    libgstreamer1.0-dev \\"
    echo "    libgstreamer-plugins-base1.0-dev \\"
    echo "    libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \\"
    echo "    libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \\"
    echo "    libgl1 libegl1 libdbus-1-3"
    echo ""
    echo -e "${YELLOW}  # 2. yt-dlp — pipx recommended for latest version (NetTV only)${RESET}"
    echo "  sudo apt install pipx"
    echo "  pipx install yt-dlp"
    echo "  # OR (may be an older version): sudo apt install yt-dlp"
    echo ""
    echo -e "${YELLOW}  # 3. PySide6 (only needed for source-run; skip if using packaged exe)${RESET}"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install --upgrade pip"
    echo "  pip install -r requirements.txt"
}

show_fedora() {
    echo -e "${BOLD}Fedora / RHEL / Rocky / AlmaLinux — install commands:${RESET}"
    echo ""
    echo -e "${YELLOW}  # 1. Enable RPM Fusion (required for ffmpeg and most GStreamer codec plugins)${RESET}"
    echo "  sudo dnf install \\"
    echo "    https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-\$(rpm -E %fedora).noarch.rpm \\"
    echo "    https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-\$(rpm -E %fedora).noarch.rpm"
    echo ""
    echo -e "${YELLOW}  # 2. System packages${RESET}"
    echo "  sudo dnf install \\"
    echo "    python3 python3-virtualenv \\"
    echo "    ffmpeg \\"
    echo "    gstreamer1-plugins-base \\"
    echo "    gstreamer1-plugins-good \\"
    echo "    gstreamer1-plugins-bad-free \\"
    echo "    gstreamer1-plugins-bad-nonfree \\"
    echo "    gstreamer1-plugins-ugly \\"
    echo "    gstreamer1-libav \\"
    echo "    mesa-libGL mesa-libEGL \\"
    echo "    xcb-util xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil"
    echo ""
    echo -e "${YELLOW}  # 3. yt-dlp (NetTV only)${RESET}"
    echo "  sudo dnf install yt-dlp"
    echo "  # OR: pipx install yt-dlp"
    echo ""
    echo -e "${YELLOW}  # 4. PySide6 (only needed for source-run; skip if using packaged exe)${RESET}"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install --upgrade pip"
    echo "  pip install -r requirements.txt"
}

show_arch() {
    echo -e "${BOLD}Arch Linux / Manjaro / EndeavourOS — install commands:${RESET}"
    echo ""
    echo -e "${YELLOW}  # 1. System packages${RESET}"
    echo "  sudo pacman -S \\"
    echo "    python python-virtualenv python-pip \\"
    echo "    ffmpeg \\"
    echo "    gstreamer \\"
    echo "    gst-plugins-base \\"
    echo "    gst-plugins-good \\"
    echo "    gst-plugins-bad \\"
    echo "    gst-plugins-ugly \\"
    echo "    gst-libav \\"
    echo "    mesa libgl"
    echo ""
    echo -e "${YELLOW}  # 2. yt-dlp (NetTV only)${RESET}"
    echo "  sudo pacman -S yt-dlp"
    echo "  # OR: pipx install yt-dlp"
    echo ""
    echo -e "${YELLOW}  # 3. PySide6 (only needed for source-run; skip if using packaged exe)${RESET}"
    echo "  python -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install --upgrade pip"
    echo "  pip install -r requirements.txt"
}

show_generic() {
    echo -e "${BOLD}Generic Linux — what to install:${RESET}"
    echo ""
    echo "  Use your package manager to install:"
    echo "    - python3 (3.11 or newer) + venv + pip"
    echo "    - ffmpeg and ffprobe"
    echo "    - GStreamer 1.x core"
    echo "    - GStreamer plugins: base, good, bad, ugly"
    echo "    - GStreamer libav bridge (gst-libav / gstreamer1.0-libav)"
    echo "      This provides the H.264/H.265/AAC decoders."
    echo "    - Qt xcb platform plugin dependencies"
    echo "    - yt-dlp (optional, for NetTV)"
    echo ""
    echo "  After installing GStreamer, verify with:"
    echo "    gst-inspect-1.0 playbin"
    echo "    gst-inspect-1.0 avdec_h264"
}

if is_debian_like; then
    show_ubuntu
elif is_fedora_like; then
    show_fedora
elif is_arch_like; then
    show_arch
else
    show_generic
    echo ""
    echo "Distro-specific install blocks for reference:"
    echo ""
    show_ubuntu
    echo ""
    show_fedora
    echo ""
    show_arch
fi

echo ""
echo -e "${BOLD}After installing, verify with:${RESET}"
echo "  bash check_linux_deps.sh"
echo ""
echo -e "${BOLD}Why GStreamer and not mpv?${RESET}"
echo "  MediaWave uses Qt Multimedia (PySide6.QtMultimedia) for playback."
echo "  Qt Multimedia uses GStreamer as its media backend on Linux."
echo "  mpv is not used anywhere in the MediaWave codebase."
echo ""

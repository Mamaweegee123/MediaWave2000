# MediaWave — Linux Portable Build Kit

This folder is a **source/build kit** for creating a Linux-compatible MediaWave portable release.
It is not a pre-built finished release. You build the executable here, then the assembly script
packages it into a portable folder you can copy to any Linux machine.

---

## What is in this folder

| Item | Purpose |
|---|---|
| `channelsurfer2000.py` | MediaWave source (synced from repo root) |
| `mediawave_converter.py` | MediaWave Converter source (synced from repo root) |
| `MediaWaveLinux.spec` | PyInstaller build spec for MediaWave |
| `MediaWaveConverterLinux.spec` | PyInstaller build spec for Converter |
| `requirements.txt` | Python dependencies including PySide6 and PyInstaller |
| `assets/` | Sound effects and other runtime assets |
| `logos/` | Application icons |
| `docs/` | User guide documents |
| `ds_digital/` | Font for WeatherStar display |
| `Fonts/` | Bundled UI fonts |
| `hooks/` | PyInstaller runtime hooks |
| `icons/` | App icon files (PNG for Linux) |
| `scripts/assemble_linux_portable.py` | Assembly script (run after build) |
| `run_mediawave.sh` | Launcher script for the portable release |
| `check_linux_deps.sh` | Dependency checker |
| `install_linux_deps.sh` | Install guide (prints commands, does not run them) |
| `MediaWave.desktop` | Desktop entry template |
| `install_desktop_launcher.sh` | Installs desktop launcher for current user |

---

## Quick start — build and run on Linux

### Step 1: Install system dependencies

```bash
bash install_linux_deps.sh
```

This prints the install commands for your distro. Review and run them.

### Step 2: Create a Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Build with PyInstaller

```bash
python -m PyInstaller --noconfirm MediaWaveLinux.spec
python -m PyInstaller --noconfirm MediaWaveConverterLinux.spec
```

Expected output:

```
dist/MediaWave2000/
  MediaWave2000          ← executable
  _internal/

dist/MediaWaveConverter/
  MediaWaveConverter
  _internal/
```

### Step 4: Assemble the portable release

```bash
python scripts/assemble_linux_portable.py
```

This creates:

```
../../release/MediaWave-Linux-Portable/
  MediaWave2000/
  MediaWave Converter/
  User Content/
  docs/
  logos/
  run_mediawave.sh
  check_linux_deps.sh
  install_linux_deps.sh
  install_desktop_launcher.sh
  MediaWave.desktop
  README-LINUX.md
  START HERE.txt
```

### Step 5: Launch

```bash
cd ../../release/MediaWave-Linux-Portable
bash check_linux_deps.sh
bash run_mediawave.sh
```

---

## Playback engine: Qt Multimedia → GStreamer

**MediaWave does NOT use mpv or libmpv.** It uses `PySide6.QtMultimedia` (`QMediaPlayer` / `QVideoSink`) for all video and audio playback — local channels, NetTV, and RadioWave music. On Linux, Qt Multimedia uses GStreamer as its media backend.

This means:
- **GStreamer core + codec plugins are required for any playback to work.**
- mpv/libmpv are not needed and should not be listed as a requirement.
- The H.264/H.265/AAC decoders come from the `gst-libav` package (the ffmpeg bridge).

You can verify your GStreamer setup after installing with:
```bash
gst-inspect-1.0 playbin      # must exist
gst-inspect-1.0 avdec_h264   # must exist for H.264 video
```

## Required system dependencies

| Dependency | Purpose | Required? |
|---|---|---|
| Python 3.11+ | Build-time only (not needed after PyInstaller build) | Build: yes |
| ffmpeg + ffprobe | MediaWave Converter, media probing | Runtime: strongly recommended |
| GStreamer core | Qt Multimedia media backend | Runtime: required |
| gst-plugins-base | Core demuxers, audio/video converters | Runtime: required |
| gst-plugins-good | MP4/MKV containers, common codecs | Runtime: required |
| gst-plugins-bad | HLS/live streams, HEVC, extras | Runtime: required for NetTV |
| gst-plugins-ugly | MP3, some H.264 profiles | Runtime: required for full codec coverage |
| gst-libav | H.264, H.265, AAC via ffmpeg bridge | Runtime: required for most video files |
| yt-dlp | NetTV live/streaming channels | Optional: NetTV only |
| Qt xcb libs | Qt platform plugin on X11 | Runtime: required on X11 |

### Ubuntu / Debian / Linux Mint

```bash
sudo apt update
sudo apt install \
  python3 python3-venv python3-pip \
  ffmpeg \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav \
  libgstreamer1.0-dev \
  libgstreamer-plugins-base1.0-dev \
  libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
  libgl1 libegl1 libdbus-1-3

# yt-dlp (latest version via pipx recommended — apt version may be outdated)
sudo apt install pipx && pipx install yt-dlp
```

### Fedora

Fedora requires RPM Fusion for ffmpeg and most GStreamer codec plugins (H.264, AAC, MP3, etc.):

```bash
# Enable RPM Fusion (required for codec plugins)
sudo dnf install \
  https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
  https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm

sudo dnf install \
  python3 python3-virtualenv \
  ffmpeg \
  gstreamer1-plugins-base \
  gstreamer1-plugins-good \
  gstreamer1-plugins-bad-free \
  gstreamer1-plugins-bad-nonfree \
  gstreamer1-plugins-ugly \
  gstreamer1-libav \
  mesa-libGL mesa-libEGL \
  xcb-util xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil

# yt-dlp (NetTV only)
sudo dnf install yt-dlp
# OR: pipx install yt-dlp
```

### Arch / Manjaro

```bash
sudo pacman -S \
  python python-virtualenv python-pip \
  ffmpeg \
  gstreamer \
  gst-plugins-base \
  gst-plugins-good \
  gst-plugins-bad \
  gst-plugins-ugly \
  gst-libav \
  mesa libgl

# yt-dlp (NetTV only)
sudo pacman -S yt-dlp
# OR: pipx install yt-dlp
```

---

## Choosing a catalog folder

On first launch, MediaWave will ask you to choose a **catalog folder**.

- A catalog folder is any folder that contains channel subfolders.
- Each subfolder becomes one TV channel. The folder name becomes the channel name.
- The catalog can live anywhere: internal disk, external drive, USB flash drive, NAS.
- The `User Content/Channels/` folder included here is a convenient starter but is not required.

Example catalog layout:
```
My Channels/
  HBO Classic/
    show01.mp4
    show02.mp4
  Comedy Central/
    special.mp4
```

---

## NetTV (streaming channels)

NetTV uses yt-dlp to play live streams and video URLs. Install yt-dlp separately:

```bash
pipx install yt-dlp
```

NetTV requires a valid internet connection. Some sources may require a cookie file for authentication — see the in-app settings.

---

## X11 vs Wayland

MediaWave uses Qt, which works on both X11 and Wayland.

- On most modern desktops (GNOME, KDE Plasma 6, etc.) Qt will automatically choose the right backend.
- If you see rendering issues on Wayland, force X11 by editing `run_mediawave.sh` and uncommenting the `QT_QPA_PLATFORM=xcb` line.
- If you are running in a headless or SSH session, MediaWave requires a forwarded X11 display or Wayland socket.

---

## Desktop launcher

To add MediaWave to your application menu:

```bash
bash install_desktop_launcher.sh
```

This installs a `MediaWave.desktop` file for your current user only (no sudo needed).
It patches the `Exec=` and `Icon=` paths to point to wherever you installed the portable folder.

To remove the launcher:
```bash
rm ~/.local/share/applications/MediaWave.desktop
```

---

## Config and cache locations

When running from the built executable, MediaWave stores data at:

```
~/.local/share/MediaWave2000/
  settings.json
  thumbnails/
  youtube_video_cache/
  metadata_artwork/
  ...
```

This respects the XDG Base Directory spec. Set `XDG_DATA_HOME` to override.

Media files and catalogs are never stored inside this folder — they live wherever you choose.

---

## Troubleshooting

**MediaWave launches but video is black / no audio**

GStreamer plugins are missing. Verify with:
```bash
gst-inspect-1.0 playbin       # must exist
gst-inspect-1.0 avdec_h264    # must exist for H.264 video
gst-inspect-1.0 autoaudiosink # must exist for audio
```
Install the full plugin set including `gst-plugins-ugly` and `gst-libav`. On Ubuntu:
```bash
sudo apt install gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav
```
On Fedora, RPM Fusion must be enabled first (see install commands above).

Note: MediaWave does NOT use mpv. If you are searching for a fix involving mpv, that is not relevant here.

**Error: could not load the Qt platform plugin "xcb"**

Missing xcb library dependencies. On Ubuntu/Debian:
```bash
sudo apt install libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb1 libx11-xcb1
```

**App crashes or shows black screen on Wayland**

Try forcing X11:
```bash
QT_QPA_PLATFORM=xcb bash run_mediawave.sh
```

**yt-dlp errors in NetTV**

yt-dlp may need updating:
```bash
pipx upgrade yt-dlp
# or if installed directly:
yt-dlp -U
```

**Permissions error on executable**

```bash
chmod +x MediaWave2000/MediaWave2000
chmod +x run_mediawave.sh
```

---

## Important notes

- **PyInstaller builds are OS-specific.** A Linux build must be created on Linux. A macOS build created on macOS will not run on Linux, and vice versa.
- **The build kit folder is not the portable release.** After building and assembling, distribute `release/MediaWave-Linux-Portable/`, not this build kit folder.
- **Keep user media outside the application folder.** Catalogs, channels, and converted files should live in a folder you control, not inside the app bundle.
- **No mpv required.** MediaWave uses Qt Multimedia (`QMediaPlayer`/`QVideoSink`) for all playback — not mpv or libmpv. The GStreamer backend is the playback requirement; mpv is irrelevant.
- **After any code change,** sync the source file using from the repo root: `python scripts/sync_release_targets.py`, then rebuild.

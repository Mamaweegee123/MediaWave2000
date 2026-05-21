# MediaWave2000

MediaWave2000 is a PySide6 desktop app that turns a local media library into a retro cable-TV style experience, with scheduled channels, a guide overlay, on-demand browsing, resume points, companion music/weather/playlist channels, and optional metadata matching.

This repository is being prepared for a future public release. Runtime cache files, local library scans, built app bundles, virtual environments, thumbnails, and personal media paths are intentionally excluded from git.

## Apps

- `channelsurfer2000.py` runs the main MediaWaveTV app.
- `mediawave_converter.py` runs the MediaWave Converter helper for batch-preparing videos with FFmpeg.

## Local Development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python channelsurfer2000.py
```

Optional external tools:

- FFmpeg / FFprobe for probing media, generating thumbnails, and converter workflows.
- yt-dlp for NetTV / YouTube playlist channels.

## Packaging

The PyInstaller specs are included:

```bash
pyinstaller MediaWaveTV.spec
pyinstaller MediaWaveConverter.spec
```

Built `.app` bundles belong in GitHub Releases, not in the source tree.

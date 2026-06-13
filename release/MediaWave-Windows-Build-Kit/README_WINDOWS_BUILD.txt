MEDIAWAVE WINDOWS BUILD KIT
===========================

This folder is a source/build kit for creating a Windows-compatible MediaWave
beta. It is not a finished Windows release.


AFTER CODE CHANGES
------------------

After any edit to channelsurfer2000.py (or mediawave_converter.py), run from
the repo root on the Mac:

    python scripts/sync_release_targets.py

This copies the updated source into this Windows Build Kit folder AND rebuilds
the macOS .app staging folder in one step, so all release targets stay in sync.
Use --no-mac to skip the macOS rebuild (Windows sync only).
Use --no-zip to skip zip creation during the macOS rebuild.

MediaWave keeps flexible catalog behavior. Users may choose any catalog folder,
including folders on external drives, USB flash drives, or network shares.
Media does not need to be stored inside the application folder.


BUILD ON WINDOWS
----------------

1. Copy this entire folder to a Windows PC.

2. Install Python 3.12 or newer from https://www.python.org/ if needed.
   During installation, enable the option to add Python to PATH.

3. Open PowerShell in this folder.

4. Create a virtual environment:

   py -m venv venv

5. Activate it:

   .\venv\Scripts\Activate.ps1

   If PowerShell blocks activation, run this once in the same window:

   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

6. Upgrade pip:

   python -m pip install --upgrade pip

7. Install requirements:

   pip install -r requirements.txt

8. Build both applications:

   python -m PyInstaller --noconfirm MediaWave2000.spec
   python -m PyInstaller --noconfirm MediaWaveConverter.spec


EXPECTED PYINSTALLER OUTPUT
---------------------------

The current specs use one-folder mode. Expected output:

  dist\MediaWave2000\
    MediaWave2000.exe
    _internal\

  dist\MediaWaveConverter\
    MediaWaveConverter.exe
    _internal\

Keep each executable with all files in its matching output folder.


ASSEMBLE A PORTABLE BETA
------------------------

After both builds finish, run:

  python scripts\assemble_windows_portable.py

Expected assembled output:

  release\MediaWave-Windows-Portable\
    MediaWave.exe
    _internal\
    MediaWave Converter\
      MediaWave Converter.exe
      _internal\
    User Content\
      Channels\
      Commercials\
      Music\
      Fonts\
      Themes\
      Converted\
      Settings\
      Cache\
    docs\
    START HERE.txt

MediaWave.exe must stay beside the root _internal folder. The converter remains
in its own folder because it has a separate one-folder dependency set. Do not
move either executable away from its matching _internal folder.

The assembly script only replaces:

  release\MediaWave-Windows-Portable\

It does not delete anything outside that folder.


FFMPEG, FFPROBE, MPV, AND YT-DLP
--------------------------------

No bundled ffmpeg, ffprobe, mpv, or other Windows runtime binaries were found
in the source repo when this kit was created.

- FFmpeg and FFprobe are needed for conversion and some media probing.
- For the converter, ffmpeg.exe and ffprobe.exe may be placed in bin\ before
  building, or installed on Windows and added to PATH.
- MediaWave currently discovers FFmpeg and FFprobe from PATH on Windows.
- The current playback setup uses PySide6 QtMultimedia. No bundled mpv runtime
  is currently present.
- yt-dlp is installed by requirements.txt for NetTV build/testing. Before a
  portable public release, verify yt-dlp availability when running outside the
  build virtual environment.

If a Windows bin\ folder is added to this build kit later, rebuild the converter
so its spec can include that folder.


WINDOWS RELEASE NOTES
---------------------

- Windows Defender or SmartScreen may warn about unsigned beta builds.
- Code signing can be added later.
- Test both applications on a Windows PC that does not have Python installed.
- Test local playback, external-drive catalogs, conversion, Guide, Vault,
  WeatherStar, and NetTV before distribution.
- Test with the catalog on a removable drive and confirm it can be reselected
  after its Windows drive letter changes.
- Keep user media and catalogs outside the application folder unless the user
  deliberately chooses the included starter folders.


BUILD KIT CONTENTS
------------------

- channelsurfer2000.py
- mediawave_converter.py
- MediaWave2000.spec
- MediaWaveConverter.spec
- requirements.txt
- assets\
- docs\
- ds_digital\
- Fonts\
- hooks\
- icons\ (Windows .ico files)
- logos\
- scripts\assemble_windows_portable.py

Development caches, local settings/catalog data, media caches, screenshots,
macOS app bundles, prior releases, build output, virtual environments, and
generated icon sources are intentionally excluded.

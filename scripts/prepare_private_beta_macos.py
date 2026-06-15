#!/usr/bin/env python3
"""Prepare the macOS private beta ZIP for MediaWave v0.1.0-beta.

Layout matches the Windows private beta exactly:

  MediaWave-v0.1.0-beta-macOS/
    MediaWave.app
    MediaWave Converter.app
    START HERE.txt
    BUILD_INFO.json
    User Content/
      Channels/         Put Channel Folders Here.txt
      Commercials/      Put Commercials Here.txt
      Converted/        Converted Files Go Here.txt
      Fonts/            Put Custom Fonts Here.txt
      Music/            Put Music Here.txt
      Themes/           Put Custom Themes Here.txt
      Settings/         Runtime Settings Go Here.txt
      Cache/            Runtime Cache Goes Here.txt
    Supplemental Reading/
      Channel Setup Guide.txt
      Commercial Setup Guide.txt
      Converter Guide.txt
      Troubleshooting.txt
    docs/
      CHANGELOG.md
      KNOWN_ISSUES.md
      QUICKSTART.md
      THIRD_PARTY_NOTICES.md
      PACKAGE_MANIFEST.txt   (generated)

Usage:
    python3 scripts/prepare_private_beta_macos.py [--no-zip] [--skip-staleness]

Outputs:
    release/MediaWave-v0.1.0-beta-macOS/   (staging folder)
    release/MediaWave-v0.1.0-beta-macOS.zip
    release/PACKAGE_REPORT.txt
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

BETA_VERSION = "0.1.0-beta"
STAGING_NAME = f"MediaWave-v{BETA_VERSION}-macOS"
ZIP_NAME = f"{STAGING_NAME}.zip"

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"
RELEASE_ROOT = REPO / "release"
STAGING = RELEASE_ROOT / STAGING_NAME
DOCS_SRC = REPO / "docs"
SOURCE_PY = REPO / "channelsurfer2000.py"
SOURCE_CONV_PY = REPO / "mediawave_converter.py"

APP_MAIN_SRC = DIST / "MediaWave2000.app"
APP_CONV_SRC = DIST / "MediaWaveConverter.app"

APP_MAIN_DST = STAGING / "MediaWave.app"
APP_CONV_DST = STAGING / "MediaWave Converter.app"

# ── Text content (matching Windows exactly) ───────────────────────────────────

START_HERE = """\
===============================================================================
+-----------------------------------------------------------------------------+
|                                                                             |
|        __  __          _ _        __        __                              |
|       |  \\/  | ___  __| (_) __ _  \\ \\      / /_ ___   _____                 |
|       | |\\/| |/ _ \\/ _` | |/ _` |  \\ \\ /\\ / / _` \\ \\ / / _ \\                |
|       | |  | |  __/ (_| | | (_| |   \\ V  V / (_| |\\ V /  __/                |
|       |_|  |_|\\___|\\__,_|_|\\__,_|    \\_/\\_/ \\__,_| \\_/ \\___|                |
|                                                                             |
|                        WELCOME TO MEDIAWAVE 2000!                           |
|                 Your Friendly Neighborhood Cable Box!                       |
|                                                                             |
|              Tune in. Sit back. There is always something on.               |
|                                                                             |
+-----------------------------------------------------------------------------+
===============================================================================

WHAT IS MEDIAWAVE?
------------------
MediaWave turns your own video collection into a browsable cable TV experience.
Point it at a folder of videos, and it builds a full channel lineup — complete
with a scrolling guide, commercial breaks, and channel watermark logos.

It is not a streaming service. There are no subscriptions. No accounts.
Your media, your channels, your TV.

-------------------------------------------------------------------------------

GETTING STARTED
---------------
1. Open MediaWave.app.

2. Press "Choose Catalog..." to select your catalog folder.

   A catalog is just the folder that CONTAINS your channel subfolders.
   It can live anywhere:

     - An external hard drive
     - A USB flash drive
     - A NAS / network share
     - Your Documents folder
     - Anywhere you want

   The User Content/Channels folder included here is a convenient starter,
   but you do not have to use it. No need to move your whole media library.

3. Press "Watch TV >" to start watching.

-------------------------------------------------------------------------------

CHANNEL SETUP
-------------
Each subfolder inside your catalog becomes one TV channel.
The folder name becomes the channel name.

  Channels/
    HBO/           <-- becomes channel "HBO"
      show01.mp4
    Comedy Central/        <-- becomes channel "Comedy Central"
      special.mp4

Channel logos (optional):
  Drop a logo image in a Logos/ subfolder inside the channel folder:

    Channel Name/Logos/logo.png

  Enable the channel bug (watermark) in Advanced Config.
  If no logo is found, MediaWave shows a text fallback instead.

See: Supplemental Reading/Channel Setup Guide.txt

-------------------------------------------------------------------------------

COMMERCIALS (OPTIONAL)
-----------------------
Put commercial clips, bumpers, promos, or station IDs in a folder anywhere,
then point Advanced Config to it and enable commercials.

The User Content/Commercials folder is ready to use as a starting point,
but any folder works fine.

See: Supplemental Reading/Commercial Setup Guide.txt

-------------------------------------------------------------------------------

MEDIAWAVE CONVERTER (OPTIONAL)
-------------------------------
Open MediaWave Converter.app if a video file gives MediaWave trouble.
It re-encodes videos to a clean H.264 MP4 format with consistent framing.

You do not need to convert everything. Most modern MP4s play fine as-is.

Converted files default to User Content/Converted/ when that folder exists.

See: Supplemental Reading/Converter Guide.txt

-------------------------------------------------------------------------------

USER CONTENT FOLDER
-------------------
The User Content folder included in this release is a convenient starter
for keeping your catalog close to the app. It is entirely optional.

  User Content/
    Channels/     <-- starter catalog folder
    Commercials/  <-- starter commercials folder
    Converted/    <-- where Converter puts finished files
    Fonts/        <-- custom fonts (optional)
    Music/        <-- music for RadioWaveTV (optional)
    Themes/       <-- custom themes (optional, future)
    Settings/     <-- app settings are stored here (do not delete)
    Cache/        <-- thumbnails and metadata (safe to clear)

You can ignore any subfolder you do not need.

-------------------------------------------------------------------------------

SUPPLEMENTAL READING
--------------------
Guides are in the Supplemental Reading/ folder:

  Channel Setup Guide.txt     - folder structure, logos, catalogs
  Commercial Setup Guide.txt  - setting up ad breaks
  Converter Guide.txt         - converting video files
  Troubleshooting.txt         - when something goes sideways

-------------------------------------------------------------------------------

IF SOMETHING LOOKS WRONG
-------------------------
Check Troubleshooting.txt first. Common fixes are in there.

If the app opens but nothing plays, the most common cause is selecting
the wrong catalog folder — make sure you select the PARENT folder that
contains your channel subfolders, not a channel folder itself.

===============================================================================
"""

PLACEHOLDERS = {
    "User Content/Channels/Put Channel Folders Here.txt":
        "Put channel folders here, or choose another catalog folder in MediaWave.\n",
    "User Content/Commercials/Put Commercials Here.txt":
        "Put optional commercial clips here.\n",
    "User Content/Converted/Converted Files Go Here.txt":
        "MediaWave Converter can use this folder for converted files.\n",
    "User Content/Fonts/Put Custom Fonts Here.txt":
        "Put optional custom fonts here.\n",
    "User Content/Music/Put Music Here.txt":
        "Put optional RadioWave music here.\n",
    "User Content/Themes/Put Custom Themes Here.txt":
        "Put optional custom themes here.\n",
    "User Content/Settings/Runtime Settings Go Here.txt":
        "MediaWave creates private runtime settings in this folder. Do not share them.\n",
    "User Content/Cache/Runtime Cache Goes Here.txt":
        "MediaWave creates disposable runtime cache files in this folder.\n",
}

SUPPLEMENTAL_GUIDES = (
    "Channel Setup Guide.txt",
    "Commercial Setup Guide.txt",
    "Converter Guide.txt",
    "Troubleshooting.txt",
)

BETA_DOCS = (
    "CHANGELOG.md",
    "KNOWN_ISSUES.md",
    "QUICKSTART.md",
    "THIRD_PARTY_NOTICES.md",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(msg)


def fail(msg: str) -> None:
    print(f"\n✗ PACKAGING ABORTED: {msg}\n", file=sys.stderr)
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"  ⚠  WARNING: {msg}")


# ── Guards ────────────────────────────────────────────────────────────────────

def check_app_version(app_path: Path) -> None:
    plist = app_path / "Contents" / "Info.plist"
    if not plist.exists():
        fail(f"Info.plist not found: {plist}")
    result = subprocess.run(
        ["defaults", "read", str(plist), "CFBundleShortVersionString"],
        capture_output=True, text=True, timeout=5,
    )
    version = result.stdout.strip()
    if version != BETA_VERSION:
        fail(
            f"App version mismatch in {app_path.name}: "
            f"expected '{BETA_VERSION}', got '{version}'. Rebuild first."
        )


TOOL_SEARCH_PATHS = [
    "Contents/Frameworks/bin",
    "Contents/MacOS",
    "Contents/Resources/bin",
    "Contents/Resources",
]


def find_bundled_tool(app_path: Path, name: str) -> Path | None:
    for rel in TOOL_SEARCH_PATHS:
        candidate = app_path / rel / name
        if candidate.is_file():
            return candidate
    return None


def check_bundled_tools_main(app_path: Path) -> dict[str, str]:
    found = {}
    for tool in ("ffmpeg", "ffprobe"):
        p = find_bundled_tool(app_path, tool)
        if p is None:
            fail(f"Bundled '{tool}' not found inside {app_path.name}. Add to bin/ and rebuild.")
        found[tool] = str(p.relative_to(app_path))
    # yt-dlp: confirmed in PYZ archive
    toc = REPO / "build" / "MediaWave2000" / "PYZ-00.toc"
    if toc.exists() and ("'yt_dlp'" in toc.read_text(errors="ignore") or '"yt_dlp"' in toc.read_text(errors="ignore")):
        found["yt-dlp"] = "frozen in PYZ archive"
    elif find_bundled_tool(app_path, "yt-dlp"):
        found["yt-dlp"] = str(find_bundled_tool(app_path, "yt-dlp").relative_to(app_path))
    else:
        fail("yt-dlp not bundled. Add 'yt_dlp' to hiddenimports in dev/MediaWave2000.spec and rebuild.")
    return found


def check_bundled_tools_converter(app_path: Path) -> dict[str, str]:
    found = {}
    for tool in ("ffmpeg", "ffprobe"):
        p = find_bundled_tool(app_path, tool)
        if p is None:
            fail(f"Bundled '{tool}' not found inside {app_path.name}. Add to bin/ and rebuild.")
        found[tool] = str(p.relative_to(app_path))
    return found


def check_staleness(app_path: Path, src: Path) -> None:
    if not src.exists():
        return
    if app_path.stat().st_mtime < src.stat().st_mtime:
        fail(
            f"{app_path.name} is older than {src.name} "
            f"(app: {time.ctime(app_path.stat().st_mtime)}, "
            f"src: {time.ctime(src.stat().st_mtime)}). "
            "Rebuild or pass --skip-staleness."
        )


def check_no_personal_paths(staging: Path) -> None:
    personal = ("mamaweegee123",)
    hits = []
    for item in staging.rglob("*"):
        if not item.is_file():
            continue
        if any(item.suffix == ext for ext in (".txt", ".md", ".json", ".cfg")):
            try:
                text = item.read_text(encoding="utf-8", errors="ignore")
                for p in personal:
                    if p in text:
                        hits.append(str(item.relative_to(staging)))
                        break
            except OSError:
                pass
    if hits:
        fail("Personal paths detected:\n  " + "\n  ".join(hits[:5]))


def check_no_forbidden_files(staging: Path) -> None:
    FORBIDDEN = {".git", "__pycache__", ".venv", "venv", "build", "dist"}
    FORBIDDEN_EXT = (".spec", ".patch", ".log", ".pyc")
    FORBIDDEN_SRC = {"channelsurfer2000.py", "mediawave_converter.py"}
    hits = []
    for item in staging.rglob("*"):
        name = item.name
        if name in FORBIDDEN or name in FORBIDDEN_SRC:
            hits.append(str(item.relative_to(staging)))
        elif any(name.endswith(e) for e in FORBIDDEN_EXT):
            hits.append(str(item.relative_to(staging)))
    if hits:
        fail("Forbidden dev files in staging:\n  " + "\n  ".join(hits[:10]))


# ── Staging ───────────────────────────────────────────────────────────────────

def safe_remove_staging() -> None:
    if STAGING.exists():
        assert str(STAGING).startswith(str(RELEASE_ROOT))
        log(f"  Removing: {STAGING}")
        # Use Python's own recursive delete; ignore errors from locked .app internals.
        shutil.rmtree(STAGING, ignore_errors=True)
        if STAGING.exists():
            # Second pass with chmod to unlock anything still left.
            subprocess.run(["chmod", "-R", "u+w", str(STAGING)], check=False)
            shutil.rmtree(STAGING, ignore_errors=True)


def copy_app(src: Path, dst: Path, label: str) -> None:
    if not src.exists():
        fail(f"Not found: {src}")
    log(f"  {label}: {src.name} → {dst.name}")
    shutil.copytree(src, dst, symlinks=True)


def generate_package_manifest() -> str:
    lines = [f"MediaWave {BETA_VERSION} private beta", "Generated for manual review. Not published.", ""]
    for item in sorted(STAGING.rglob("*")):
        if item.is_file() or item.is_symlink():
            lines.append(str(item.relative_to(STAGING)))
    return "\n".join(lines) + "\n"


def generate_build_info() -> dict:
    src = SOURCE_PY
    sha = ""
    if src.exists():
        h = hashlib.sha256(src.read_bytes())
        sha = h.hexdigest()
    exe = APP_MAIN_DST / "Contents" / "MacOS" / "MediaWave2000"
    exe_sha = ""
    if exe.exists():
        exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    return {
        "component": "MediaWave2000",
        "version": BETA_VERSION,
        "platform": "macOS",
        "built_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_file": "channelsurfer2000.py",
        "source_sha256": sha,
        "source_modified_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(src.stat().st_mtime)
        ) if src.exists() else "",
        "executable": "MediaWave.app/Contents/MacOS/MediaWave2000",
        "executable_sha256": exe_sha,
    }


def create_staging(skip_staleness: bool) -> tuple[dict, dict]:
    log("\n=== Step 1: Verify app versions ===")
    check_app_version(APP_MAIN_SRC)
    check_app_version(APP_CONV_SRC)
    log(f"  ✓ Both apps: {BETA_VERSION}")

    log("\n=== Step 2: Verify bundled tools ===")
    main_tools = check_bundled_tools_main(APP_MAIN_SRC)
    conv_tools = check_bundled_tools_converter(APP_CONV_SRC)
    for k, v in main_tools.items():
        log(f"  MediaWave.app    {k}: {v}")
    for k, v in conv_tools.items():
        log(f"  Converter.app    {k}: {v}")

    if not skip_staleness:
        log("\n=== Step 3: Staleness check ===")
        check_staleness(APP_MAIN_SRC, SOURCE_PY)
        check_staleness(APP_CONV_SRC, SOURCE_CONV_PY)
        log("  ✓ Apps are current")

    log("\n=== Step 4: Clear staging ===")
    safe_remove_staging()
    STAGING.mkdir(parents=True, exist_ok=True)

    log("\n=== Step 5: Copy .app bundles ===")
    copy_app(APP_MAIN_SRC, APP_MAIN_DST, "MediaWave")
    copy_app(APP_CONV_SRC, APP_CONV_DST, "MediaWave Converter")

    log("\n=== Step 6: START HERE.txt ===")
    (STAGING / "START HERE.txt").write_text(START_HERE, encoding="utf-8")

    log("\n=== Step 7: User Content folders ===")
    for rel, content in PLACEHOLDERS.items():
        p = STAGING / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    log("\n=== Step 8: Supplemental Reading (text guides) ===")
    sup = STAGING / "Supplemental Reading"
    sup.mkdir(exist_ok=True)
    for guide in SUPPLEMENTAL_GUIDES:
        src_guide = DOCS_SRC / guide
        if src_guide.exists():
            shutil.copy2(src_guide, sup / guide)
            log(f"  {guide}")
        else:
            warn(f"Missing guide: {guide}")

    log("\n=== Step 9: docs/ (beta documents) ===")
    docs_dst = STAGING / "docs"
    docs_dst.mkdir(exist_ok=True)
    for doc in BETA_DOCS:
        src_doc = DOCS_SRC / doc
        if src_doc.exists():
            shutil.copy2(src_doc, docs_dst / doc)
            log(f"  {doc}")
        else:
            warn(f"Missing: docs/{doc} — create it in the repo docs/ folder")

    log("\n=== Step 10: PACKAGE_MANIFEST.txt ===")
    manifest = generate_package_manifest()
    (docs_dst / "PACKAGE_MANIFEST.txt").write_text(manifest, encoding="utf-8")

    log("\n=== Step 11: BUILD_INFO.json ===")
    build_info = generate_build_info()
    (STAGING / "BUILD_INFO.json").write_text(
        json.dumps(build_info, indent=4), encoding="utf-8"
    )
    log(f"  Built at: {build_info['built_at_utc']}")

    log("\n=== Step 12: Guard — no forbidden files ===")
    check_no_forbidden_files(STAGING)
    log("  ✓ Clean")

    log("\n=== Step 13: Guard — no personal paths ===")
    check_no_personal_paths(STAGING)
    log("  ✓ Clean")

    return main_tools, conv_tools


# ── ZIP ───────────────────────────────────────────────────────────────────────

def make_zip(no_zip: bool) -> Path | None:
    if no_zip:
        return None
    zip_path = RELEASE_ROOT / ZIP_NAME
    log(f"\n=== Step 14: Creating ZIP: {ZIP_NAME} ===")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for item in STAGING.rglob("*"):
            arcname = item.relative_to(RELEASE_ROOT)
            if item.is_symlink():
                info = zipfile.ZipInfo(str(arcname))
                info.create_system = 3
                info.external_attr = 0xA1ED0000
                zf.writestr(info, str(item.readlink()))
            elif item.is_file():
                zf.write(item, arcname)
    log(f"  ✓ {zip_path}")
    return zip_path


# ── Report ────────────────────────────────────────────────────────────────────

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def write_report(zip_path: Path | None, main_tools: dict, conv_tools: dict, ts: str) -> Path:
    report = RELEASE_ROOT / "PACKAGE_REPORT.txt"
    lines = [
        "=" * 64,
        "  MEDIAWAVE PRIVATE BETA — PACKAGE REPORT",
        f"  Version  : {BETA_VERSION}",
        f"  Platform : macOS (arm64)",
        f"  Built    : {ts}",
        "=" * 64,
        "",
        "APPS",
        "----",
        f"  MediaWave.app         : {APP_MAIN_DST}",
        f"  MediaWave Converter   : {APP_CONV_DST}",
        "",
        "BUNDLED TOOLS — MediaWave.app",
        "------------------------------",
    ]
    for k, v in main_tools.items():
        lines.append(f"  {k:10s}: {v}")
    lines += ["", "BUNDLED TOOLS — MediaWave Converter.app", "----------------------------------------"]
    for k, v in conv_tools.items():
        lines.append(f"  {k:10s}: {v}")
    lines += [""]
    if zip_path and zip_path.exists():
        size = zip_path.stat().st_size
        digest = sha256(zip_path)
        lines += [
            "ZIP", "---",
            f"  Path   : {zip_path}",
            f"  Size   : {human_size(size)} ({size:,} bytes)",
            f"  SHA-256: {digest}",
            "",
        ]
    lines += ["LAYOUT", "------"]
    for item in sorted(STAGING.rglob("*")):
        if item.is_file() or item.is_symlink():
            rel = item.relative_to(STAGING)
            parts = rel.parts
            if len(parts) > 3 and parts[0].endswith(".app"):
                continue
            size_str = human_size(item.stat().st_size) if item.is_file() else "[symlink]"
            lines.append(f"  {rel}  ({size_str})")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    no_zip = "--no-zip" in sys.argv
    skip_staleness = "--skip-staleness" in sys.argv
    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    log(f"\nMediaWave Private Beta Packager — macOS")
    log(f"Version  : {BETA_VERSION}")
    log(f"ZIP name : {ZIP_NAME}")
    log(f"Staging  : {STAGING}")
    log(f"Time     : {ts}\n")

    if not APP_MAIN_SRC.exists():
        fail(f"MediaWave2000.app not found in dist/. Run PyInstaller first.")
    if not APP_CONV_SRC.exists():
        fail(f"MediaWaveConverter.app not found in dist/. Run PyInstaller first.")

    main_tools, conv_tools = create_staging(skip_staleness)
    zip_path = make_zip(no_zip)
    report = write_report(zip_path, main_tools, conv_tools, ts)

    log("\n" + "=" * 64)
    log("  PACKAGING COMPLETE")
    log("=" * 64)
    log(f"  Staging  : {STAGING}")
    if zip_path and zip_path.exists():
        size = zip_path.stat().st_size
        log(f"  ZIP      : {zip_path}")
        log(f"  Size     : {human_size(size)}")
        log(f"  SHA-256  : {sha256(zip_path)}")
    log(f"  Report   : {report}")
    log("")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Assemble Linux PyInstaller outputs into a clean portable release folder.

This is the repo-root version of the assembly script.
It mirrors scripts/assemble_windows_portable.py for Linux.

Run on a Linux machine from the repo root after building with PyInstaller:
    python scripts/assemble_linux_portable.py

Expected PyInstaller input (one-folder mode):
    dist/MediaWave2000/
    dist/MediaWaveConverter/

Expected output:
    release/MediaWave-Linux-Portable/
      MediaWave2000/
        MediaWave2000
        _internal/
      MediaWave Converter/
        MediaWaveConverter
        _internal/
      User Content/
        Channels/ Commercials/ Music/ Fonts/ Themes/ Converted/ Settings/ Cache/
      docs/
      logos/
      run_mediawave.sh
      check_linux_deps.sh
      install_linux_deps.sh
      install_desktop_launcher.sh
      MediaWave.desktop
      README-LINUX.md
      START HERE.txt
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
RELEASE_ROOT = ROOT / "release"
OUTPUT = RELEASE_ROOT / "MediaWave-Linux-Portable"
LINUX_KIT = RELEASE_ROOT / "MediaWave-Linux-Build-Kit"
DOCS_SRC = ROOT / "docs"
LOGOS_SRC = ROOT / "logos"

APPS = (
    ("MediaWave2000", "MediaWave2000"),
    ("MediaWaveConverter", "MediaWave Converter"),
)

USER_FOLDERS = (
    "Channels",
    "Commercials",
    "Music",
    "Fonts",
    "Themes",
    "Converted",
    "Settings",
    "Cache",
)

PLACEHOLDERS = {
    "Channels/Put Channel Folders Here.txt": (
        "Put channel folders here, or choose any other catalog folder in MediaWave.\n"
        "Catalogs may be on internal disks, external drives, flash drives, or network shares.\n"
    ),
    "Commercials/Put Commercials Here.txt": (
        "Put optional commercial clips here, or select another folder in MediaWave.\n"
    ),
    "Music/Put Music Here.txt": (
        "Put optional RadioWave music here, or select another folder in MediaWave.\n"
    ),
    "Fonts/Put Custom Fonts Here.txt": "Put optional custom fonts here.\n",
    "Themes/Put Custom Themes Here.txt": "Put optional custom themes here.\n",
    "Converted/Converted Files Go Here.txt": (
        "MediaWave Converter can use this folder for converted files.\n"
    ),
}

SCRIPTS_TO_COPY = (
    "run_mediawave.sh",
    "check_linux_deps.sh",
    "install_linux_deps.sh",
    "install_desktop_launcher.sh",
    "MediaWave.desktop",
    "README-LINUX.md",
)


def log(msg: str) -> None:
    print(msg)


def remove_output() -> None:
    if not OUTPUT.exists():
        return
    if OUTPUT.parent != RELEASE_ROOT or OUTPUT.name != "MediaWave-Linux-Portable":
        raise RuntimeError(f"Refusing to remove unexpected path: {OUTPUT}")
    log(f"  Removing existing output: {OUTPUT}")
    shutil.rmtree(OUTPUT)


def validate_builds() -> None:
    for dist_name, _ in APPS:
        exe = DIST / dist_name / dist_name
        if not exe.is_file():
            raise FileNotFoundError(
                f"Missing Linux PyInstaller output: {exe}\n"
                f"Build first with PyInstaller on a Linux machine:\n"
                f"  python -m PyInstaller --noconfirm release/MediaWave-Linux-Build-Kit/MediaWaveLinux.spec"
            )


def copy_build(dist_name: str, dest_folder: str) -> None:
    source_dir = DIST / dist_name
    destination = OUTPUT / dest_folder
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Missing PyInstaller output folder: {source_dir}")
    log(f"  Copying {source_dir.name} -> {dest_folder}/")
    shutil.copytree(source_dir, destination, dirs_exist_ok=True)


def create_user_content() -> None:
    user_content = OUTPUT / "User Content"
    for folder in USER_FOLDERS:
        (user_content / folder).mkdir(parents=True, exist_ok=True)
    for relative_path, text in PLACEHOLDERS.items():
        target = user_content / relative_path
        target.write_text(text, encoding="utf-8")
    log(f"  Created User Content/ with {len(USER_FOLDERS)} folders")


def copy_docs() -> None:
    destination = OUTPUT / "docs"
    if DOCS_SRC.is_dir():
        log("  Copying docs/")
        shutil.copytree(DOCS_SRC, destination, dirs_exist_ok=True)
    else:
        log("  WARNING: docs/ not found — creating empty docs/")
        destination.mkdir(parents=True, exist_ok=True)


def copy_logos() -> None:
    if LOGOS_SRC.is_dir():
        log("  Copying logos/")
        shutil.copytree(LOGOS_SRC, OUTPUT / "logos", dirs_exist_ok=True)


def copy_scripts() -> None:
    for name in SCRIPTS_TO_COPY:
        src = LINUX_KIT / name
        if src.exists():
            dst = OUTPUT / name
            shutil.copy2(src, dst)
            log(f"  Copied {name}")
        else:
            log(f"  WARNING: {name} not found in Linux Build Kit — skipping")

    for name in SCRIPTS_TO_COPY:
        if name.endswith(".sh"):
            target = OUTPUT / name
            if target.exists():
                target.chmod(target.stat().st_mode | 0o111)


def write_start_here() -> None:
    (OUTPUT / "START HERE.txt").write_text(
        "MEDIAWAVE LINUX PORTABLE\n"
        "========================\n\n"
        "1. Run: bash check_linux_deps.sh\n"
        "   to verify all required system dependencies.\n\n"
        "2. Run: bash run_mediawave.sh\n"
        "   to launch MediaWave.\n\n"
        "3. On first launch, choose a catalog folder containing your channel subfolders.\n"
        "   The included User Content/Channels/ folder is a convenient starter,\n"
        "   but you may use any folder on any drive.\n\n"
        "See README-LINUX.md for full instructions and troubleshooting.\n",
        encoding="utf-8",
    )


def validate() -> None:
    log("\n" + "=" * 60)
    log("VALIDATION")
    log("=" * 60)
    log(f"  Output folder:       {OUTPUT}")
    log(f"  MediaWave2000:       {'OK' if (OUTPUT / 'MediaWave2000' / 'MediaWave2000').exists() else 'MISSING'}")
    log(f"  MediaWave Converter: {'OK' if (OUTPUT / 'MediaWave Converter' / 'MediaWaveConverter').exists() else 'MISSING'}")
    log(f"  run_mediawave.sh:    {'OK' if (OUTPUT / 'run_mediawave.sh').exists() else 'MISSING'}")
    log(f"  check_linux_deps:    {'OK' if (OUTPUT / 'check_linux_deps.sh').exists() else 'MISSING'}")
    log(f"  README-LINUX.md:     {'OK' if (OUTPUT / 'README-LINUX.md').exists() else 'MISSING'}")
    log(f"  User Content/:       {'OK' if (OUTPUT / 'User Content').is_dir() else 'MISSING'}")
    log(f"  docs/:               {'OK' if (OUTPUT / 'docs').is_dir() else 'MISSING'}")


def main() -> None:
    log("\nAssembling MediaWave Linux Portable release...")
    log(f"  Repo root : {ROOT}")
    log(f"  Output    : {OUTPUT}\n")

    validate_builds()
    remove_output()
    OUTPUT.mkdir(parents=True)

    for dist_name, dest_folder in APPS:
        copy_build(dist_name, dest_folder)

    create_user_content()
    copy_docs()
    copy_logos()
    copy_scripts()
    write_start_here()
    validate()

    log(f"\nPortable release assembled at: {OUTPUT}")
    log("Copy the entire MediaWave-Linux-Portable/ folder to any Linux machine and run:")
    log("  bash run_mediawave.sh\n")


if __name__ == "__main__":
    main()

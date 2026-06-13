#!/usr/bin/env python3
"""Assemble Windows PyInstaller outputs into a clean portable release folder."""

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
RELEASE_ROOT = ROOT / "release"
OUTPUT = RELEASE_ROOT / "MediaWave-Windows-Portable"
DOCS = ROOT / "docs"

APPS = (
    ("MediaWave2000", ".", "MediaWave2000.exe", "MediaWave.exe"),
    (
        "MediaWaveConverter",
        "MediaWave Converter",
        "MediaWaveConverter.exe",
        "MediaWave Converter.exe",
    ),
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


def remove_output() -> None:
    if not OUTPUT.exists():
        return
    if OUTPUT.parent != RELEASE_ROOT or OUTPUT.name != "MediaWave-Windows-Portable":
        raise RuntimeError(f"Refusing to remove unexpected path: {OUTPUT}")
    shutil.rmtree(OUTPUT)


def validate_builds() -> None:
    for dist_name, _, old_exe, _ in APPS:
        one_folder_exe = DIST / dist_name / old_exe
        one_file_exe = DIST / old_exe
        if not one_folder_exe.is_file() and not one_file_exe.is_file():
            raise FileNotFoundError(
                f"Missing Windows PyInstaller output: {one_folder_exe} or {one_file_exe}"
            )


def copy_build(dist_name: str, destination_name: str, old_exe: str, new_exe: str) -> None:
    source_dir = DIST / dist_name
    source_exe = DIST / old_exe
    destination = OUTPUT if destination_name == "." else OUTPUT / destination_name

    if source_dir.is_dir():
        built_exe = source_dir / old_exe
        if not built_exe.is_file():
            raise FileNotFoundError(f"Missing Windows executable: {built_exe}")
        shutil.copytree(source_dir, destination, dirs_exist_ok=True)
        built_exe = destination / old_exe
        if built_exe.exists() and old_exe != new_exe:
            built_exe.rename(destination / new_exe)
        return

    if source_exe.is_file():
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_exe, destination / new_exe)
        return

    raise FileNotFoundError(
        f"Missing PyInstaller output for {dist_name}. Expected {source_dir} or {source_exe}."
    )


def create_user_content() -> None:
    user_content = OUTPUT / "User Content"
    for folder in USER_FOLDERS:
        (user_content / folder).mkdir(parents=True, exist_ok=True)
    for relative_path, text in PLACEHOLDERS.items():
        target = user_content / relative_path
        target.write_text(text, encoding="utf-8")


def copy_docs() -> None:
    destination = OUTPUT / "docs"
    if DOCS.is_dir():
        shutil.copytree(DOCS, destination)
    else:
        destination.mkdir(parents=True, exist_ok=True)


def write_start_here() -> None:
    (OUTPUT / "START HERE.txt").write_text(
        "MEDIAWAVE WINDOWS PORTABLE BETA\n"
        "===============================\n\n"
        "Launch MediaWave.exe.\n"
        "Launch MediaWave Converter\\MediaWave Converter.exe for conversion.\n\n"
        "You may choose any catalog folder in MediaWave. The included User Content folder\n"
        "is only a starter and is not required. External drives and flash drives are supported.\n\n"
        "FFmpeg and FFprobe must be on PATH or bundled where the applications can find them.\n"
        "Test this release on a Windows PC without Python installed before distribution.\n",
        encoding="utf-8",
    )


def main() -> None:
    validate_builds()
    remove_output()
    OUTPUT.mkdir(parents=True)

    for app in APPS:
        copy_build(*app)

    create_user_content()
    copy_docs()
    write_start_here()
    print(f"Portable release assembled at: {OUTPUT}")


if __name__ == "__main__":
    main()

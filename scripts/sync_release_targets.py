#!/usr/bin/env python3
"""Sync the root source files and assets to all release targets.

After any code change to the root channelsurfer2000.py, run:

    python scripts/sync_release_targets.py

What this does (quick sync — default):
  1. Copies root channelsurfer2000.py  →  Windows Build Kit
  2. Copies root channelsurfer2000.py  →  Linux Build Kit
  3. Copies root mediawave_converter.py to both build kits
  4. Copies root requirements.txt to both build kits
  5. Copies dev/ PyInstaller specs to the Windows Build Kit
  6. Runs scripts/assemble_mac_release.py to rebuild the macOS .app staging folder

What --assets adds (full sync):
  Syncs the static asset folders to both build kits so they never silently lag
  behind the main app:
    assets/   logos/   docs/   hooks/   Fonts/   icons/

  Asset sync uses a recursive file-by-file comparison and only copies changed
  files, so it is fast if nothing changed.  Use it whenever you change art,
  fonts, docs, or hooks.

Options:
  --assets      Also sync static asset folders (see above)
  --full        Alias for --assets
  --no-mac      Skip the macOS .app rebuild
  --no-zip      Pass --no-zip to the mac release script (skip zip creation)
  --skip-mac    Alias for --no-mac

Safe to run repeatedly. Fails loudly on any error — never silently continues.
"""

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "channelsurfer2000.py"
CONVERTER_SOURCE = REPO / "mediawave_converter.py"
REQUIREMENTS_SOURCE = REPO / "requirements.txt"
DEV_DIR = REPO / "dev"

WIN_KIT_DIR = REPO / "release" / "MediaWave-Windows-Build-Kit"
WIN_KIT_TARGET = WIN_KIT_DIR / "channelsurfer2000.py"

LINUX_KIT_DIR = REPO / "release" / "MediaWave-Linux-Build-Kit"
LINUX_KIT_TARGET = LINUX_KIT_DIR / "channelsurfer2000.py"

MAC_SCRIPT = REPO / "scripts" / "assemble_mac_release.py"

# Static asset folders that both build kits mirror from the repo root.
# These change rarely (art, fonts, docs, hooks) but MUST stay in sync when
# they do, otherwise a Linux/Windows build will use stale assets.
ASSET_DIRS = (
    "assets",
    "logos",
    "docs",
    "hooks",
    "Fonts",
    "icons",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def fail(msg: str) -> None:
    print(f"\n✗ ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def separator(title: str = "") -> None:
    width = 60
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'─' * pad} {title} {'─' * (width - pad - len(title) - 2)}")
    else:
        print(f"\n{'─' * width}")


# ── File sync helpers ─────────────────────────────────────────────────────────

def _sync_file(src: Path, dst: Path, label: str) -> None:
    src_hash = sha256(src)
    if dst.exists() and sha256(dst) == src_hash:
        print(f"  ✓ {label} already in sync — no copy needed")
        return
    shutil.copy2(src, dst)
    post_hash = sha256(dst)
    if post_hash != src_hash:
        fail(f"Post-copy checksum mismatch for {label}!")
    print(f"  ✓ {label} synced  ({dst.stat().st_size:,} bytes)")


def _sync_dir(src_dir: Path, dst_dir: Path, label: str) -> None:
    """Sync src_dir into dst_dir file-by-file, copying only changed files.

    Files that exist in dst_dir but not in src_dir are left alone — this
    avoids destroying kit-specific additions (e.g. extra .ico files in icons/).
    """
    if not src_dir.is_dir():
        print(f"  — {label} skipped (source not present: {src_dir.name}/)")
        return

    dst_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped = 0

    for src_file in src_dir.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_dir)
        dst_file = dst_dir / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        src_hash = sha256(src_file)
        if dst_file.exists() and sha256(dst_file) == src_hash:
            skipped += 1
            continue
        shutil.copy2(src_file, dst_file)
        copied += 1

    status = f"{copied} updated, {skipped} unchanged"
    print(f"  ✓ {label}  ({status})")


# ── Steps ─────────────────────────────────────────────────────────────────────

def preflight_checks(sync_assets: bool) -> None:
    separator("Pre-flight checks")
    if not SOURCE.exists():
        fail(f"Source file not found: {SOURCE}")
    print(f"  Source : {SOURCE}")
    print(f"  Size   : {SOURCE.stat().st_size:,} bytes")
    print(f"  SHA256 : {sha256(SOURCE)}")

    if not WIN_KIT_DIR.is_dir():
        fail(f"Windows Build Kit folder not found: {WIN_KIT_DIR}")
    print(f"\n  Windows Build Kit : {WIN_KIT_DIR}")

    if not LINUX_KIT_DIR.is_dir():
        print(f"\n  Linux Build Kit   : {LINUX_KIT_DIR} (not present — Linux sync will be skipped)")
    else:
        print(f"\n  Linux Build Kit   : {LINUX_KIT_DIR}")

    if not MAC_SCRIPT.exists():
        fail(f"Mac release script not found: {MAC_SCRIPT}")
    print(f"  Mac script        : {MAC_SCRIPT}")

    if sync_assets:
        missing = [d for d in ASSET_DIRS if not (REPO / d).is_dir()]
        if missing:
            print(f"\n  Asset dirs absent (will skip): {', '.join(missing)}")
        present = [d for d in ASSET_DIRS if (REPO / d).is_dir()]
        if present:
            print(f"\n  Asset dirs to sync: {', '.join(present)}")

    print("\n  ✓ Paths checked")


def sync_windows_build_kit() -> None:
    separator("Step 1 — Windows Build Kit (source files)")
    _sync_file(SOURCE, WIN_KIT_TARGET, "channelsurfer2000.py → Windows")
    if CONVERTER_SOURCE.exists():
        _sync_file(CONVERTER_SOURCE, WIN_KIT_DIR / "mediawave_converter.py", "mediawave_converter.py → Windows")
    if REQUIREMENTS_SOURCE.exists():
        _sync_file(REQUIREMENTS_SOURCE, WIN_KIT_DIR / "requirements.txt", "requirements.txt → Windows")
    for spec_name in ("MediaWave2000.spec", "MediaWaveConverter.spec"):
        spec_source = DEV_DIR / spec_name
        if spec_source.exists():
            spec_target = WIN_KIT_DIR / "dev" / spec_name
            spec_target.parent.mkdir(parents=True, exist_ok=True)
            _sync_file(spec_source, spec_target, f"dev/{spec_name} → Windows")


def sync_linux_build_kit() -> None:
    separator("Step 2 — Linux Build Kit (source files)")
    if not LINUX_KIT_DIR.is_dir():
        print(f"  Skipped — Linux Build Kit folder not present: {LINUX_KIT_DIR}")
        return
    _sync_file(SOURCE, LINUX_KIT_TARGET, "channelsurfer2000.py → Linux")
    if CONVERTER_SOURCE.exists():
        _sync_file(CONVERTER_SOURCE, LINUX_KIT_DIR / "mediawave_converter.py", "mediawave_converter.py → Linux")
    if REQUIREMENTS_SOURCE.exists():
        _sync_file(REQUIREMENTS_SOURCE, LINUX_KIT_DIR / "requirements.txt", "requirements.txt → Linux")


def sync_asset_dirs() -> None:
    separator("Step 2b — Asset folders (--assets)")
    print("  Syncing static asset folders to both build kits...")
    print("  (Only changed files are copied. Kit-specific files are not deleted.)\n")

    for dir_name in ASSET_DIRS:
        src = REPO / dir_name
        _sync_dir(src, WIN_KIT_DIR / dir_name, f"{dir_name}/ → Windows")

    print()

    if not LINUX_KIT_DIR.is_dir():
        print(f"  Linux Build Kit not present — skipping Linux asset sync")
        return

    for dir_name in ASSET_DIRS:
        src = REPO / dir_name
        _sync_dir(src, LINUX_KIT_DIR / dir_name, f"{dir_name}/ → Linux")

    # Re-copy the Linux-specific PNG icons into icons/ (they are not in the repo
    # icons/ dir — they are derived from logos/).
    _reseed_linux_png_icons()


def _reseed_linux_png_icons() -> None:
    """Ensure icons/mediawave2000.png and icons/mediawave_converter.png exist in Linux kit."""
    icon_dir = LINUX_KIT_DIR / "icons"
    mappings = (
        (REPO / "logos" / "MW2K_appicon.png",       icon_dir / "mediawave2000.png"),
        (REPO / "logos" / "MWConverter_appicon.png", icon_dir / "mediawave_converter.png"),
    )
    for src, dst in mappings:
        if src.exists():
            _sync_file(src, dst, f"{dst.name} → Linux icons/")


def rebuild_mac_app(no_zip: bool) -> None:
    separator("Step 3 — macOS .app rebuild")
    print(f"  Script : {MAC_SCRIPT}")

    cmd = [sys.executable, str(MAC_SCRIPT)]
    if no_zip:
        cmd.append("--no-zip")
        print(f"  Mode   : --no-zip (skipping zip creation)")
    else:
        print(f"  Mode   : full (includes zip)")

    print()
    result = subprocess.run(cmd, cwd=str(REPO))

    if result.returncode != 0:
        fail(f"Mac release script exited with code {result.returncode}")

    print(f"\n  ✓ macOS .app rebuild succeeded")


def summary(skipped_mac: bool, sync_assets: bool) -> None:
    separator("Summary")
    src_hash = sha256(SOURCE)

    win_hash = sha256(WIN_KIT_TARGET) if WIN_KIT_TARGET.exists() else "missing"
    win_match = "✓ match" if win_hash == src_hash else "✗ MISMATCH"
    print(f"  channelsurfer2000.py checksum")
    print(f"    root SHA256        : {src_hash}")
    print(f"    Windows kit SHA256 : {win_hash}  {win_match}")

    if LINUX_KIT_DIR.is_dir() and LINUX_KIT_TARGET.exists():
        linux_hash = sha256(LINUX_KIT_TARGET)
        linux_match = "✓ match" if linux_hash == src_hash else "✗ MISMATCH"
        print(f"    Linux kit SHA256   : {linux_hash}  {linux_match}")
    else:
        print(f"    Linux kit SHA256   : skipped (kit not present)")

    if sync_assets:
        print(f"\n  Asset folders synced: {', '.join(ASSET_DIRS)}")
    else:
        print(f"\n  Asset folders: not synced (run with --assets to sync)")

    if skipped_mac:
        print(f"\n  macOS .app : skipped (--no-mac)")
    else:
        mac_staging = REPO / "release" / "MediaWave" / "MediaWave.app"
        mac_zip = REPO / "release" / "MediaWave-macOS-beta.zip"
        print(f"\n  macOS .app : {'✓ present' if mac_staging.exists() else '✗ missing'}")
        print(f"  macOS .zip : {'✓ present' if mac_zip.exists() else 'skipped / missing'}")

    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    skip_mac = "--no-mac" in args or "--skip-mac" in args
    no_zip = "--no-zip" in args
    sync_assets = "--assets" in args or "--full" in args

    print("=" * 60)
    print("  MediaWave — sync_release_targets")
    print("=" * 60)
    print(f"  Repo       : {REPO}")
    print(f"  Asset sync : {'yes (--assets)' if sync_assets else 'no  (add --assets or --full to enable)'}")

    preflight_checks(sync_assets)
    sync_windows_build_kit()
    sync_linux_build_kit()

    if sync_assets:
        sync_asset_dirs()

    if skip_mac:
        separator("Step 3 — macOS .app rebuild")
        print("  Skipped (--no-mac)")
    else:
        rebuild_mac_app(no_zip=no_zip)

    summary(skipped_mac=skip_mac, sync_assets=sync_assets)
    print("✓ All release targets in sync.\n")


if __name__ == "__main__":
    main()

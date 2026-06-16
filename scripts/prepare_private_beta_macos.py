#!/usr/bin/env python3
"""Prepare the macOS private beta ZIP for MediaWave v0.1.0-beta.

All user-facing docs (START HERE.txt, the Supplemental Reading guides, and
the docs/ beta documents) are copied byte-for-byte from the canonical
sources in docs/. This script never rewrites or regenerates their content —
if a canonical doc is missing, packaging fails instead of substituting a
generic placeholder.

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
import plistlib
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

BETA_VERSION = "0.1.0-beta"
CONVERTER_VERSION = "0.1.0"
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

# ── Canonical doc sources ───────────────────────────────────────────────────
# These files are never generated or rewritten by this script. They are
# copied verbatim from docs/ and packaging fails loudly if one is missing.

ROOT_DOCS = (
    "START HERE.txt",
)

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


# ── Guards ────────────────────────────────────────────────────────────────────

def check_app_version(app_path: Path, expected_version: str = BETA_VERSION) -> None:
    plist = app_path / "Contents" / "Info.plist"
    if not plist.exists():
        fail(f"Info.plist not found: {plist}")
    try:
        with plist.open("rb") as handle:
            version = str(plistlib.load(handle).get("CFBundleShortVersionString", "")).strip()
    except (OSError, plistlib.InvalidFileException) as exc:
        fail(f"Could not read Info.plist from {app_path.name}: {exc}")
    if version != expected_version:
        fail(
            f"App version mismatch in {app_path.name}: "
            f"expected '{expected_version}', got '{version}'. Rebuild first."
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
    for tool in ("ffmpeg", "ffprobe", "yt-dlp"):
        p = find_bundled_tool(app_path, tool)
        if p is None:
            fail(f"Bundled '{tool}' not found inside {app_path.name}. Add to bin/ and rebuild.")
        found[tool] = str(p.relative_to(app_path))
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


def verify_staged_docs(copied_docs: list[tuple[Path, Path]]) -> None:
    mismatches = []
    for src, dst in copied_docs:
        if not dst.exists():
            mismatches.append(f"{dst.relative_to(STAGING)}: missing in staging")
            continue
        if sha256(src) != sha256(dst):
            mismatches.append(f"{dst.relative_to(STAGING)}: content differs from canonical {src.relative_to(REPO)}")
    if mismatches:
        fail("Staged docs do not match canonical sources:\n  " + "\n  ".join(mismatches))


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
        "converter_version": CONVERTER_VERSION,
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
    check_app_version(APP_CONV_SRC, CONVERTER_VERSION)
    log(f"  ✓ MediaWave: {BETA_VERSION}; Converter: {CONVERTER_VERSION}")

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

    log("\n=== Step 6: START HERE.txt (canonical, verbatim from docs/) ===")
    copied_docs: list[tuple[Path, Path]] = []
    for doc in ROOT_DOCS:
        src_doc = DOCS_SRC / doc
        if not src_doc.exists():
            fail(f"Required canonical doc missing: {src_doc}. Create it in docs/ — packaging will not generate a substitute.")
        dst_doc = STAGING / doc
        shutil.copy2(src_doc, dst_doc)
        copied_docs.append((src_doc, dst_doc))
        log(f"  {doc}  <-  {src_doc.relative_to(REPO)}")

    log("\n=== Step 7: User Content folders ===")
    for rel, content in PLACEHOLDERS.items():
        p = STAGING / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    log("\n=== Step 8: Supplemental Reading (canonical, verbatim from docs/) ===")
    sup = STAGING / "Supplemental Reading"
    sup.mkdir(exist_ok=True)
    for guide in SUPPLEMENTAL_GUIDES:
        src_guide = DOCS_SRC / guide
        if not src_guide.exists():
            fail(f"Required canonical doc missing: {src_guide}. Create it in docs/ — packaging will not generate a substitute.")
        dst_guide = sup / guide
        shutil.copy2(src_guide, dst_guide)
        copied_docs.append((src_guide, dst_guide))
        log(f"  {guide}  <-  {src_guide.relative_to(REPO)}")

    log("\n=== Step 9: docs/ (canonical beta documents, verbatim) ===")
    docs_dst = STAGING / "docs"
    docs_dst.mkdir(exist_ok=True)
    for doc in BETA_DOCS:
        src_doc = DOCS_SRC / doc
        if not src_doc.exists():
            fail(f"Required canonical doc missing: {src_doc}. Create it in docs/ — packaging will not generate a substitute.")
        dst_doc = docs_dst / doc
        shutil.copy2(src_doc, dst_doc)
        copied_docs.append((src_doc, dst_doc))
        log(f"  {doc}  <-  {src_doc.relative_to(REPO)}")

    log("\n=== Step 10: Verify staged docs match canonical sources exactly ===")
    verify_staged_docs(copied_docs)
    log("  ✓ All staged docs are byte-for-byte identical to their canonical source")

    log("\n=== Step 11: PACKAGE_MANIFEST.txt (generated) ===")
    manifest = generate_package_manifest()
    (docs_dst / "PACKAGE_MANIFEST.txt").write_text(manifest, encoding="utf-8")

    log("\n=== Step 12: BUILD_INFO.json (generated) ===")
    build_info = generate_build_info()
    (STAGING / "BUILD_INFO.json").write_text(
        json.dumps(build_info, indent=4), encoding="utf-8"
    )
    log(f"  Built at: {build_info['built_at_utc']}")

    log("\n=== Step 13: Guard — no forbidden files ===")
    check_no_forbidden_files(STAGING)
    log("  ✓ Clean")

    log("\n=== Step 14: Guard — no personal paths ===")
    check_no_personal_paths(STAGING)
    log("  ✓ Clean")

    return main_tools, conv_tools


# ── ZIP ───────────────────────────────────────────────────────────────────────

def make_zip(no_zip: bool) -> Path | None:
    if no_zip:
        return None
    zip_path = RELEASE_ROOT / ZIP_NAME
    log(f"\n=== Step 15: Creating ZIP: {ZIP_NAME} ===")
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

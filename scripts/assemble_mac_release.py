#!/usr/bin/env python3
"""Assemble a clean macOS release staging folder for MediaWave.

Usage:
    python3 scripts/assemble_mac_release.py [--no-zip]

Outputs:
    release/MediaWave/
    release/MediaWave-macOS-beta.zip  (unless --no-zip)

Safe:
    Only ever deletes / replaces release/MediaWave/.
    Never touches anything outside the release/ directory.

Docs:
    START HERE.txt and the Supplemental Reading guides are copied
    byte-for-byte from the canonical sources in docs/. This script never
    rewrites or regenerates their content — if a canonical doc is missing,
    assembly fails instead of substituting a generic placeholder.
"""

import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"
RELEASE_ROOT = REPO / "release"
STAGING = RELEASE_ROOT / "MediaWave"
DOCS_SRC = REPO / "docs"

# ── Canonical doc sources ────────────────────────────────────────────────────
# Never rewritten or regenerated — copied verbatim from docs/. Assembly fails
# loudly if one of these is missing.
ROOT_DOCS = (
    "START HERE.txt",
)

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

# ── Placeholder text files ────────────────────────────────────────────────────
PLACEHOLDERS = {
    "User Content/Channels/Put Channel Folders Here.txt": (
        "CHANNELS\n"
        "--------\n"
        "Put your channel folders here.\n"
        "\n"
        "Each subfolder becomes one TV channel in MediaWave.\n"
        "The folder name becomes the channel name.\n"
        "\n"
        "Example:\n"
        "  Channels/\n"
        "    HBO Classic/\n"
        "      show01.mp4\n"
        "      show02.mp4\n"
        "    Comedy Central/\n"
        "      special.mp4\n"
        "\n"
        "You can also choose any folder on any drive as your\n"
        "catalog — this folder is just a convenient starter.\n"
        "\n"
        "See docs/Channel Setup Guide.txt for more details.\n"
    ),
    "User Content/Commercials/Put Commercials Here.txt": (
        "COMMERCIALS\n"
        "-----------\n"
        "Put your commercial video clips here.\n"
        "\n"
        "MediaWave plays these between episodes, just like\n"
        "broadcast TV. Short clips (15–60 seconds) work best.\n"
        "\n"
        "Enable commercials and set this folder path in\n"
        "Advanced Config inside MediaWave.\n"
        "\n"
        "See docs/Commercial Setup Guide.txt for more details.\n"
    ),
    "User Content/Music/Put Music Here.txt": (
        "MUSIC (RadioWaveTV)\n"
        "--------------------\n"
        "Put music files here for the RadioWaveTV channel.\n"
        "\n"
        "Supported: .mp3  .m4a  .aac  .flac  .wav  .ogg\n"
        "\n"
        "Enable RadioWaveTV in Advanced Config and point it\n"
        "to this folder.\n"
    ),
    "User Content/Fonts/Put Custom Fonts Here.txt": (
        "CUSTOM FONTS\n"
        "------------\n"
        "Place any custom .ttf or .otf font files here.\n"
        "\n"
        "MediaWave will load fonts from this folder when\n"
        "custom theme configurations reference them.\n"
    ),
    "User Content/Themes/Put Custom Themes Here.txt": (
        "CUSTOM THEMES\n"
        "-------------\n"
        "Place custom theme JSON files here.\n"
        "\n"
        "Custom themes override the built-in guide themes\n"
        "inside MediaWave.\n"
    ),
}

def log(msg: str) -> None:
    print(msg)


def fail(msg: str) -> None:
    print(f"\n✗ ASSEMBLY ABORTED: {msg}\n", file=sys.stderr)
    sys.exit(1)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_remove_staging() -> None:
    """Remove only the staging folder — never anything above release/."""
    if STAGING.exists():
        # Safety: confirm we are not about to delete something above release/
        assert str(STAGING).startswith(str(RELEASE_ROOT)), (
            f"Safety check failed: {STAGING} is not inside {RELEASE_ROOT}"
        )
        log(f"Removing existing staging folder: {STAGING}")
        shutil.rmtree(STAGING)


def copy_app(src_name: str, dst_name: str) -> bool:
    src = DIST / src_name
    dst = STAGING / dst_name
    if not src.exists():
        log(f"  WARNING: {src} not found — skipping")
        return False
    log(f"  Copying {src.name} -> {dst.name} ...")
    shutil.copytree(src, dst, symlinks=True)
    log(f"  Done.")
    return True


def create_user_content() -> None:
    for subdir in ("Channels", "Commercials", "Music", "Fonts", "Themes", "Converted"):
        (STAGING / "User Content" / subdir).mkdir(parents=True, exist_ok=True)
    for rel_path, content in PLACEHOLDERS.items():
        target = STAGING / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        log(f"  Created {rel_path}")


def copy_canonical_docs() -> list[tuple[Path, Path]]:
    """Copy START HERE.txt, the Supplemental Reading guides, and the docs/
    beta documents byte-for-byte from docs/. Never rewrites their content;
    fails loudly if a required canonical doc is missing."""
    copied: list[tuple[Path, Path]] = []

    log("  START HERE.txt (main folder, canonical, verbatim) ...")
    for doc in ROOT_DOCS:
        src = DOCS_SRC / doc
        if not src.exists():
            fail(f"Required canonical doc missing: {src}. Create it in docs/ — assembly will not generate a substitute.")
        dst = STAGING / doc
        shutil.copy2(src, dst)
        copied.append((src, dst))
        log(f"    {doc}  <-  {src.relative_to(REPO)}")

    log("  Supplemental Reading/ (canonical, verbatim) ...")
    sup = STAGING / "Supplemental Reading"
    sup.mkdir(exist_ok=True)
    for guide in SUPPLEMENTAL_GUIDES:
        src = DOCS_SRC / guide
        if not src.exists():
            fail(f"Required canonical doc missing: {src}. Create it in docs/ — assembly will not generate a substitute.")
        dst = sup / guide
        shutil.copy2(src, dst)
        copied.append((src, dst))
        log(f"    {guide}  <-  {src.relative_to(REPO)}")

    log("  docs/ (canonical beta documents, verbatim) ...")
    docs_dst = STAGING / "docs"
    docs_dst.mkdir(exist_ok=True)
    for doc in BETA_DOCS:
        src = DOCS_SRC / doc
        if not src.exists():
            fail(f"Required canonical doc missing: {src}. Create it in docs/ — assembly will not generate a substitute.")
        dst = docs_dst / doc
        shutil.copy2(src, dst)
        copied.append((src, dst))
        log(f"    {doc}  <-  {src.relative_to(REPO)}")

    return copied


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


def make_zip(no_zip: bool) -> Path | None:
    if no_zip:
        return None
    zip_path = RELEASE_ROOT / "MediaWave-macOS-beta.zip"
    log(f"\nCreating zip: {zip_path.name} ...")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for item in STAGING.rglob("*"):
            arcname = item.relative_to(RELEASE_ROOT)
            if item.is_symlink():
                # Preserve symlinks inside .app bundles
                zip_info = zipfile.ZipInfo(str(arcname))
                zip_info.create_system = 3  # Unix
                zip_info.external_attr = 0xA1ED0000  # symlink flag
                zf.writestr(zip_info, str(item.readlink()))
            elif item.is_file():
                zf.write(item, arcname)
    log(f"  Zip created: {zip_path}")
    return zip_path


def validate(zip_path: Path | None) -> None:
    log("\n" + "=" * 60)
    log("VALIDATION")
    log("=" * 60)
    log(f"  Release folder:  {STAGING}")
    log(f"  MediaWave.app:   {'✓' if (STAGING / 'MediaWave.app').exists() else '✗ MISSING'}")
    log(f"  Converter.app:   {'✓' if (STAGING / 'MediaWave Converter.app').exists() else '✗ MISSING'}")
    log(f"  START HERE.txt:  {'✓' if (STAGING / 'START HERE.txt').exists() else '✗ MISSING'}")
    log(f"  docs/:           {'✓' if (STAGING / 'docs').is_dir() else '✗ MISSING'}")
    log(f"  User Content/:   {'✓' if (STAGING / 'User Content').is_dir() else '✗ MISSING'}")
    if zip_path:
        log(f"  Zip:             {'✓' if zip_path.exists() else '✗ MISSING'} {zip_path.name}")
    else:
        log("  Zip:             skipped")

    # Dev clutter check
    clutter_patterns = [".git", "venv", "__pycache__", "build", "dist", "*.spec",
                        "*.py", "*.patch", "*.log"]
    found_clutter = []
    for item in STAGING.rglob("*"):
        name = item.name
        if (name.startswith(".git") or name == "venv" or name == "__pycache__"
                or name == "build" or name == "dist"
                or name.endswith(".spec") or name.endswith(".patch")
                or (name.endswith(".py") and not name.endswith("Guide.txt"))):
            found_clutter.append(str(item.relative_to(STAGING)))
    if found_clutter:
        log(f"\n  WARNING — dev clutter found:")
        for c in found_clutter[:10]:
            log(f"    {c}")
    else:
        log("  Dev clutter:     ✓ none found")

    log("\nFolder tree (3 levels):")
    _print_tree(STAGING, max_depth=3)
    log("")


def _print_tree(root: Path, max_depth: int, _prefix: str = "", _depth: int = 0) -> None:
    if _depth > max_depth:
        return
    entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    for i, entry in enumerate(entries):
        connector = "└── " if i == len(entries) - 1 else "├── "
        print(_prefix + connector + entry.name)
        if entry.is_dir() and _depth < max_depth:
            extension = "    " if i == len(entries) - 1 else "│   "
            _print_tree(entry, max_depth, _prefix + extension, _depth + 1)


def main() -> None:
    no_zip = "--no-zip" in sys.argv

    log(f"\nRepo:    {REPO}")
    log(f"Staging: {STAGING}")
    log("")

    log("Step 1: Clearing existing staging folder ...")
    safe_remove_staging()
    STAGING.mkdir(parents=True, exist_ok=True)

    log("\nStep 2: Copying .app bundles ...")
    copy_app("MediaWave2000.app", "MediaWave.app")
    copy_app("MediaWaveConverter.app", "MediaWave Converter.app")

    log("\nStep 3: Creating User Content folders ...")
    create_user_content()

    log("\nStep 4: Copying canonical docs ...")
    copied_docs = copy_canonical_docs()

    log("\nStep 5: Verifying staged docs match canonical sources ...")
    verify_staged_docs(copied_docs)
    log("  ✓ All staged docs are byte-for-byte identical to their canonical source")

    log("\nStep 6: Creating zip ...")
    zip_path = make_zip(no_zip)

    validate(zip_path)
    log(f"\n✓ Release folder ready: {STAGING}\n")


if __name__ == "__main__":
    main()

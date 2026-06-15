#!/usr/bin/env python3
"""Build app icons for MediaWave 2000 and MediaWave Converter.

Reads source logos from logos/ and produces:
  icons/source/mediawave2000_icon.png       (2048x2048 master)
  icons/source/mediawave_converter_icon.png  (2048x2048 master)
  icons/mediawave2000.icns
  icons/mediawave2000.ico
  icons/mediawave_converter.icns
  icons/mediawave_converter.ico
  icons/generated/<name>/<size>.png          (intermediate PNGs)

Requirements:
  pip install Pillow        (already in venv)
  iconutil                  (built into macOS — for .icns)

Usage:
  python3 tools/build_icons.py
  python3 tools/build_icons.py --no-icns    (skip if not on macOS)
"""

import argparse
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from math import sqrt

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parent.parent
LOGOS = REPO / "logos"
ICONS = REPO / "icons"
ICONS_SRC = ICONS / "source"
ICONS_GEN = ICONS / "generated"

SOURCE_LOGOS = {
    "mediawave2000": LOGOS / "MW2K.png",
    "mediawave_converter": LOGOS / "MWConverter.png",
}

# App background colour — matches the startup screen deep-space navy in the app
# (_SW_BG = QColor(13, 16, 38))
BG_COLOR = (13, 16, 38, 255)

# macOS standard icon corner radius as a fraction of icon size (~22.4%)
# Apple HIG: 1024px icon → ~229px corner radius
CORNER_RADIUS_FRAC = 0.2237

# Padding as fraction of the larger logo dimension (applied on all four sides)
PADDING_FRAC = 0.12

# Extra right-side padding fraction for MW2K (its "2K" badge clips the source edge)
MW2K_EXTRA_RIGHT_FRAC = 0.08

# Master icon canvas size — largest iconutil / ico size we'll use
MASTER_SIZE = 2048

# macOS iconset sizes: (filename_suffix, pixel_size)
ICNS_SIZES = [
    ("icon_16x16",       16),
    ("icon_16x16@2x",    32),
    ("icon_32x32",       32),
    ("icon_32x32@2x",    64),
    ("icon_128x128",    128),
    ("icon_128x128@2x", 256),
    ("icon_256x256",    256),
    ("icon_256x256@2x", 512),
    ("icon_512x512",    512),
    ("icon_512x512@2x",1024),
]

# Windows .ico sizes to embed
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(msg)


def load_pil():
    try:
        from PIL import Image, ImageFilter
        return Image, ImageFilter
    except ImportError:
        print("ERROR: Pillow not installed. Run: pip install Pillow")
        sys.exit(1)


def content_bbox(img):
    """Return (left, upper, right, lower) of non-transparent content."""
    Image, _ = load_pil()
    alpha = img.split()[3]
    bbox = alpha.getbbox()
    return bbox  # None if fully transparent


def make_rounded_mask(size: int, radius: int) -> "Image":
    """Return an RGBA mask image: white inside the rounded rect, transparent outside.
    Uses a high-res intermediate for smooth anti-aliased corners.
    """
    Image, ImageFilter = load_pil()
    from PIL import ImageDraw

    # Draw at 4× for anti-aliased corners, then scale down
    scale = 4
    big = size * scale
    r = radius * scale

    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, big - 1, big - 1], radius=r, fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)

    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(Image.new("RGB", (size, size), (255, 255, 255)), mask=mask)
    return mask


def make_master(logo_name: str, source_path: Path, master_size: int) -> "Image":
    """Load source logo, centre on a macOS-style rounded-rect dark background."""
    Image, ImageFilter = load_pil()

    src = Image.open(source_path).convert("RGBA")
    bbox = content_bbox(src)
    if bbox is None:
        raise ValueError(f"No visible content found in {source_path}")

    left, upper, right, lower = bbox

    # MW2K: the "2K" badge clips the right image edge — extend bbox rightward
    if logo_name == "mediawave2000":
        extra_right = int(src.width * MW2K_EXTRA_RIGHT_FRAC)
        right = min(right + extra_right, src.width)

    logo_crop = src.crop((left, upper, right, lower))
    lw, lh = logo_crop.size

    # Compute canvas size: fit logo inside (master_size * (1 - 2*padding))^2
    usable = int(master_size * (1.0 - 2.0 * PADDING_FRAC))
    scale = min(usable / lw, usable / lh)
    new_w = int(lw * scale)
    new_h = int(lh * scale)

    logo_scaled = logo_crop.resize((new_w, new_h), Image.LANCZOS)

    # Build canvas: transparent background + macOS rounded-rect background shape
    canvas = Image.new("RGBA", (master_size, master_size), (0, 0, 0, 0))

    # Paint the rounded-rect background (dark navy, matching Apple's icon grid)
    radius = int(master_size * CORNER_RADIUS_FRAC)
    bg_layer = Image.new("RGBA", (master_size, master_size), BG_COLOR)
    rounded_mask = make_rounded_mask(master_size, radius)
    canvas.paste(bg_layer, mask=rounded_mask)

    # Paste logo centred on the rounded background
    x = (master_size - new_w) // 2
    y = (master_size - new_h) // 2
    canvas.paste(logo_scaled, (x, y), logo_scaled)

    return canvas


def save_png(img, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), "PNG", optimize=False)
    log(f"  Saved {path.relative_to(REPO)}")


def resize_to(master, size: int) -> "Image":
    Image, _ = load_pil()
    return master.resize((size, size), Image.LANCZOS)


def build_ico(master, output_path: Path) -> None:
    """Build a proper multi-resolution Windows .ico from the master image.

    PIL's ICO plugin uses the `sizes` kwarg to resize the *master* image to
    each requested size and embed all frames in one file.  The `append_images`
    kwarg is ignored by the ICO plugin — do not use it here.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image, _ = load_pil()
    # PIL requires the base image to be in RGBA for transparent icons
    src = master.convert("RGBA")
    src.save(
        str(output_path),
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
    )
    # Verify
    check = Image.open(str(output_path))
    actual = check.info.get("sizes", {(check.size[0], check.size[1])})
    log(f"  Saved {output_path.relative_to(REPO)}  ({len(actual)} sizes: {sorted(actual)})")


def build_icns(master, name: str, output_path: Path, skip: bool) -> None:
    """Build an .icns using iconutil (macOS only)."""
    if skip:
        log(f"  Skipping .icns for {name} (--no-icns)")
        return
    if sys.platform != "darwin":
        log(f"  Skipping .icns for {name} (not on macOS — iconutil not available)")
        return
    if not shutil.which("iconutil"):
        log(f"  Skipping .icns for {name} (iconutil not found)")
        return

    iconset_dir = ICONS_GEN / f"{name}.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)

    for suffix, size in ICNS_SIZES:
        frame = resize_to(master, size)
        frame_path = iconset_dir / f"{suffix}.png"
        frame.save(str(frame_path), "PNG")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log(f"  ERROR building {output_path.name}: {result.stderr.strip()}")
    else:
        log(f"  Saved {output_path.relative_to(REPO)}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Build MediaWave app icons")
    parser.add_argument("--no-icns", action="store_true", help="Skip .icns generation")
    parser.add_argument("--size", type=int, default=MASTER_SIZE, help=f"Master canvas size (default {MASTER_SIZE})")
    args = parser.parse_args()

    ICONS_SRC.mkdir(parents=True, exist_ok=True)
    ICONS_GEN.mkdir(parents=True, exist_ok=True)

    for name, source_path in SOURCE_LOGOS.items():
        log(f"\n── {name} ──────────────────────────────────────────")
        if not source_path.exists():
            log(f"  ERROR: source logo not found: {source_path}")
            continue

        log(f"  Building master from {source_path.relative_to(REPO)} ...")
        master = make_master(name, source_path, args.size)

        # Master PNG (2048x2048)
        master_path = ICONS_SRC / f"{name}_icon.png"
        save_png(master, master_path)

        # Also save a 1024x1024 copy for reference / smaller machines
        save_png(resize_to(master, 1024), ICONS_SRC / f"{name}_icon_1024.png")

        # Individual generated sizes for reference
        for size in [16, 32, 48, 64, 128, 256, 512, 1024]:
            save_png(resize_to(master, size), ICONS_GEN / name / f"{size}.png")

        # .ico (Windows)
        ico_path = ICONS / f"{name}.ico"
        log(f"  Building {ico_path.name} ...")
        build_ico(master, ico_path)

        # .icns (macOS)
        icns_path = ICONS / f"{name}.icns"
        log(f"  Building {icns_path.name} ...")
        build_icns(master, name, icns_path, args.no_icns)

    log("\n\nDone. Summary of output files:")
    log(f"  {ICONS_SRC.relative_to(REPO)}/  — master PNGs (source of truth)")
    log(f"  {ICONS_GEN.relative_to(REPO)}/  — individual size PNGs per app")
    for name in SOURCE_LOGOS:
        log(f"  icons/{name}.icns")
        log(f"  icons/{name}.ico")
    log("")


if __name__ == "__main__":
    main()

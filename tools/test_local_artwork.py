"""
Smoke tests for local artwork discovery and cache refresh.
Run from the repo root:  venv/bin/python3 tools/test_local_artwork.py
No GUI launch required.
"""
import os
import sys
import tempfile
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.local_artwork import (
    clear_local_artwork_caches,
    discover_local_media_assets,
    local_asset_directories,
    local_asset_signature,
)
from mediawave.local_media import parse_local_media

PASS = []
FAIL = []


def check(name, expr, detail=""):
    if expr:
        PASS.append(name)
        print(f"  OK  {name}")
    else:
        FAIL.append(name)
        print(f"FAIL  {name}" + (f"  ({detail})" if detail else ""))


def section(title):
    print(f"\n--- {title} ---")


with tempfile.TemporaryDirectory() as tmpdir:
    show_dir = os.path.join(tmpdir, "Example Show")
    season_dir = os.path.join(show_dir, "Season 1")
    os.makedirs(season_dir)
    episode_path = os.path.join(season_dir, "Example.Show.S01E01.Pilot.mkv")
    poster_path = os.path.join(show_dir, "poster.jpg")
    description_path = os.path.join(show_dir, "description.txt")
    with open(episode_path, "wb") as handle:
        handle.write(b"video-one")
    with open(poster_path, "wb") as handle:
        handle.write(b"poster-one")
    with open(description_path, "w", encoding="utf-8") as handle:
        handle.write("A local show description.")

    local = parse_local_media(episode_path)

    section("discovery")
    dirs = local_asset_directories(episode_path, local)
    assets = discover_local_media_assets(episode_path, local)
    check("tv season artwork searches show folder", show_dir in dirs, dirs)
    check("poster found in show folder", assets["poster_path"] == poster_path, assets)
    check("description loaded", assets["description"] == "A local show description.", assets)

    section("signature refresh")
    first_signature = local_asset_signature(episode_path, local)
    time.sleep(1.05)
    with open(poster_path, "wb") as handle:
        handle.write(b"poster-two")
    clear_local_artwork_caches()
    second_signature = local_asset_signature(episode_path, local)
    check("poster content change updates signature", first_signature != second_signature, (first_signature, second_signature))


print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All local artwork smoke tests passed.")

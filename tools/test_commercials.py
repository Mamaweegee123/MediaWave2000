"""Smoke tests for commercial library restore and schedule cache helpers."""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.commercials import (
    COMMERCIAL_TIMING_VERSION,
    cached_commercial_assets_for_root,
    commercial_schedule_needs_rebuild,
    schedule_has_commercial_entries,
    staggered_timed_breakpoints,
)


PASS = []
FAIL = []


def check(name, expression):
    (PASS if expression else FAIL).append(name)
    print(f"{'  OK  ' if expression else 'FAIL  '}{name}")


root = "/Media/Commercials"
asset_path = "/Media/Commercials/ad.mp4"
cache = {"root_folder": root, "assets": [{"path": asset_path, "duration": 30.0}]}

check(
    "matching cached root restores available assets",
    len(cached_commercial_assets_for_root(cache, root, path_exists=lambda path: path == asset_path)) == 1,
)
check(
    "different root does not restore stale assets",
    cached_commercial_assets_for_root(cache, "/Other/Commercials", path_exists=lambda _path: True) == [],
)
check(
    "missing cached files are skipped",
    cached_commercial_assets_for_root(cache, root, path_exists=lambda _path: False) == [],
)

content_only = {"entries": [{"kind": "content", "path": "/Media/show.mp4"}]}
with_ads = {"entries": [{"kind": "content"}, {"kind": "commercial", "is_commercial": True}]}
check("content-only schedule has no commercials", not schedule_has_commercial_entries(content_only))
check("commercial entry is detected", schedule_has_commercial_entries(with_ads))
check("enabled commercial schedule rebuilds when ads are absent", commercial_schedule_needs_rebuild(content_only, True))
check("enabled commercial schedule reuses cache when ads are present", not commercial_schedule_needs_rebuild(with_ads, True))
check("disabled commercials do not force a rebuild", not commercial_schedule_needs_rebuild(content_only, False))
check("commercial timing cache version includes staggered breaks", COMMERCIAL_TIMING_VERSION >= 2)

moomin_breaks = staggered_timed_breakpoints("Moomin", "/Media/Moomin/S01E01.mkv", 3600, 900)
moomin_repeat = staggered_timed_breakpoints("Moomin", "/Media/Moomin/S01E01.mkv", 3600, 900)
other_channel_breaks = staggered_timed_breakpoints("Retro TV", "/Media/Moomin/S01E01.mkv", 3600, 900)
other_program_breaks = staggered_timed_breakpoints("Moomin", "/Media/Moomin/S01E02.mkv", 3600, 900)
check("timed breaks are stable for the same channel and program", moomin_breaks == moomin_repeat)
check("timed breaks differ across channels", moomin_breaks != other_channel_breaks)
check("timed breaks differ across programs", moomin_breaks != other_program_breaks)
check("timed breaks stay inside safe program bounds", all(300 <= point <= 3300 for point in moomin_breaks))
check("short programs still have no timed break", staggered_timed_breakpoints("Shorts", "/Media/short.mp4", 1199, 900) == [])

print(f"\nResults: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)

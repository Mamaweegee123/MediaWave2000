"""Smoke tests for commercial library restore and schedule cache helpers."""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.commercials import (
    COMMERCIAL_TIMING_VERSION,
    cached_commercial_assets_for_root,
    commercial_parent_path,
    commercial_parent_title,
    commercial_parent_window,
    commercial_duration_status,
    commercial_schedule_needs_rebuild,
    filter_commercial_assets_by_duration,
    is_commercial_entry,
    normalize_commercial_max_duration_seconds,
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
long_asset = {"path": "/Media/Commercials/full-episode.mp4", "duration": 1800.0}
accepted, ignored = filter_commercial_assets_by_duration([cache["assets"][0], long_asset], 300)
check("normal commercials pass duration filter", len(accepted) == 1 and accepted[0]["path"] == asset_path)
check("long suspicious commercials are ignored", len(ignored) == 1 and ignored[0]["path"] == long_asset["path"])
check("disabled max duration accepts long commercials", commercial_duration_status(1800, 0) == "ok")
check("invalid max duration falls back to five minutes", normalize_commercial_max_duration_seconds("bad") == 300)
check(
    "cached long commercials do not restore by default",
    cached_commercial_assets_for_root(
        {"root_folder": root, "assets": [long_asset]},
        root,
        path_exists=lambda path: path == long_asset["path"],
        max_duration_seconds=300,
    ) == [],
)

content_only = {"entries": [{"kind": "content", "path": "/Media/show.mp4"}]}
with_ads = {"entries": [{"kind": "content"}, {"kind": "commercial", "is_commercial": True}]}
check("content-only schedule has no commercials", not schedule_has_commercial_entries(content_only))
check("commercial entry is detected", schedule_has_commercial_entries(with_ads))
check("enabled commercial schedule rebuilds when ads are absent", commercial_schedule_needs_rebuild(content_only, True))
check("enabled commercial schedule reuses cache when ads are present", not commercial_schedule_needs_rebuild(with_ads, True))
check("disabled commercials do not force a rebuild", not commercial_schedule_needs_rebuild(content_only, False))
program_entry = {"kind": "content", "path": "/Media/show.mp4", "title": "Real Show", "duration": 1200}
ad_entry = {
    "kind": "commercial",
    "is_commercial": True,
    "path": "/Media/Commercials/ad.mp4",
    "title": "Ad File",
    "duration": 30,
    "parent_path": "/Media/show.mp4",
    "parent_title": "Real Show",
}
after_entry = {"kind": "content", "path": "/Media/next.mp4", "title": "Next Show", "duration": 1200}
check("commercial helper detects ad entries", is_commercial_entry(ad_entry))
check("commercial parent path hides ad path", commercial_parent_path(ad_entry) == "/Media/show.mp4")
check("commercial parent title hides ad title", commercial_parent_title(ad_entry) == "Real Show")
window_start, window_end = commercial_parent_window([program_entry, ad_entry, after_entry], 1, 1200, 1230)
check("commercial parent window includes parent program duration", window_start == 0 and window_end == 1230)
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

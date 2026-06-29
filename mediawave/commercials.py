"""Pure helpers for restoring and validating the shared commercial library."""

import hashlib
import os
import random


COMMERCIAL_ENTRY_KINDS = {"commercial", "promo", "bumper", "station_id"}
COMMERCIAL_TIMING_VERSION = 2
DEFAULT_COMMERCIAL_MAX_DURATION_SECONDS = 5 * 60


def normalize_commercial_max_duration_seconds(value, default=DEFAULT_COMMERCIAL_MAX_DURATION_SECONDS):
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        seconds = int(default)
    if seconds <= 0:
        return 0
    return max(30, min(6 * 60 * 60, seconds))


def commercial_duration_status(duration, max_duration_seconds=DEFAULT_COMMERCIAL_MAX_DURATION_SECONDS):
    try:
        seconds = float(duration or 0)
    except (TypeError, ValueError):
        seconds = 0.0
    max_seconds = normalize_commercial_max_duration_seconds(max_duration_seconds)
    if seconds <= 0:
        return "unreadable"
    if max_seconds and seconds > max_seconds:
        return "too_long"
    return "ok"


def filter_commercial_assets_by_duration(assets, max_duration_seconds=DEFAULT_COMMERCIAL_MAX_DURATION_SECONDS):
    accepted = []
    ignored = []
    for asset in assets or []:
        if not isinstance(asset, dict):
            continue
        if commercial_duration_status(asset.get("duration", 0), max_duration_seconds) == "too_long":
            ignored.append(dict(asset))
        else:
            accepted.append(dict(asset))
    return accepted, ignored


def cached_commercial_assets_for_root(
    cache_state,
    root_folder,
    path_exists=os.path.isfile,
    max_duration_seconds=DEFAULT_COMMERCIAL_MAX_DURATION_SECONDS,
):
    if not isinstance(cache_state, dict) or not root_folder:
        return []
    cached_root = str(cache_state.get("root_folder") or "").strip()
    if not cached_root or os.path.abspath(cached_root) != os.path.abspath(root_folder):
        return []
    assets = cache_state.get("assets")
    if not isinstance(assets, list):
        return []
    restored = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        path = str(asset.get("path") or "").strip()
        if (
            path
            and path_exists(path)
            and commercial_duration_status(asset.get("duration", 0), max_duration_seconds) != "too_long"
        ):
            restored.append(dict(asset))
    return restored


def schedule_has_commercial_entries(state):
    entries = state.get("entries") if isinstance(state, dict) else []
    return any(
        isinstance(entry, dict)
        and (entry.get("is_commercial") or entry.get("kind") in COMMERCIAL_ENTRY_KINDS)
        for entry in (entries or [])
    )


def commercial_schedule_needs_rebuild(state, commercials_expected):
    return bool(commercials_expected) and not schedule_has_commercial_entries(state)


def staggered_timed_breakpoints(channel_name, program_path, duration, interval):
    duration = float(duration or 0)
    interval = max(6 * 60, int(interval or 0))
    if duration < 20 * 60:
        return []

    first_allowed = 5 * 60
    last_allowed = max(first_allowed, duration - (5 * 60))
    seed_text = f"{channel_name}|{program_path}|{duration:.3f}|{interval}"
    seed = int(hashlib.sha1(seed_text.encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed)
    jitter_limit = min(2 * 60, interval * 0.12)
    breakpoints = []
    target = float(interval)
    while target < last_allowed:
        chosen = max(first_allowed, min(last_allowed, target + rng.uniform(-jitter_limit, jitter_limit)))
        if chosen >= last_allowed:
            break
        if not breakpoints or chosen - breakpoints[-1] >= interval * 0.70:
            breakpoints.append(round(float(chosen), 3))
        target += interval
    return breakpoints

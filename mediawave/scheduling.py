"""Schedule lineup helpers for MediaWave."""

import random
import time

from .local_media import media_lineup_sort_key, stable_hash


CATALOG_PLAYBACK_ORDER_RANDOM = "random"
CATALOG_PLAYBACK_ORDER_SEQUENTIAL = "sequential"
CATALOG_PLAYBACK_ORDER_LABELS = {
    CATALOG_PLAYBACK_ORDER_RANDOM: "Random",
    CATALOG_PLAYBACK_ORDER_SEQUENTIAL: "Sequential episodes",
}


def normalize_playback_order(value):
    playback_order = str(value or CATALOG_PLAYBACK_ORDER_RANDOM).lower()
    if playback_order not in {CATALOG_PLAYBACK_ORDER_RANDOM, CATALOG_PLAYBACK_ORDER_SEQUENTIAL}:
        return CATALOG_PLAYBACK_ORDER_RANDOM
    return playback_order


def auto_schedule_anchor():
    now = int(time.time())
    half_hour = 30 * 60
    return now - (now % half_hour)


def ordered_channel_lineup(root_path, channel_name, file_paths, playback_order=CATALOG_PLAYBACK_ORDER_RANDOM, shuffle_seed=None):
    ordered = list(file_paths)
    if normalize_playback_order(playback_order) == CATALOG_PLAYBACK_ORDER_SEQUENTIAL:
        ordered.sort(key=media_lineup_sort_key)
        return ordered
    seed_value = shuffle_seed if shuffle_seed is not None else stable_hash(f"{root_path}|{channel_name}")
    seeded = random.Random(seed_value)
    seeded.shuffle(ordered)
    return ordered


def generate_auto_schedule(root_path, channel_name, file_paths, playback_order=CATALOG_PLAYBACK_ORDER_RANDOM, shuffle_seed=None):
    normalized_order = normalize_playback_order(playback_order)
    return {
        "mode": "auto",
        "anchor_time": auto_schedule_anchor(),
        "playback_order": normalized_order,
        "shuffle_seed": shuffle_seed,
        "lineup": ordered_channel_lineup(root_path, channel_name, file_paths, normalized_order, shuffle_seed),
    }


def lineup_diagnostics(file_paths, lineup, limit=25):
    eligible = list(file_paths or [])
    chosen = list(lineup or [])
    visible = chosen[:max(1, int(limit or 1))]
    return {
        "eligible_pool_size": len(eligible),
        "lineup_size": len(chosen),
        "lineup_ids": [stable_hash(path)[:12] for path in visible],
        "lineup_paths": visible,
        "truncated_count": max(0, len(chosen) - len(visible)),
    }


def remove_path_from_schedule(schedule, path):
    """Remove one media path from every lineup collection in a schedule."""
    if not isinstance(schedule, dict) or not path:
        return False
    removed = False
    for key in ("lineup", "schedule_paths"):
        values = schedule.get(key)
        if isinstance(values, list):
            kept = [value for value in values if value != path]
            removed = removed or len(kept) != len(values)
            schedule[key] = kept
    entries = schedule.get("entries")
    if isinstance(entries, list):
        kept = [entry for entry in entries if not isinstance(entry, dict) or entry.get("path") != path]
        removed = removed or len(kept) != len(entries)
        schedule["entries"] = kept
    return removed

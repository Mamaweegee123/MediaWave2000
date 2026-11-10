"""Schedule lineup helpers for MediaWave."""

import random
import time

from .local_media import media_lineup_sort_key, metadata_lookup_key, parse_local_media, stable_hash


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


def legacy_random_channel_lineup(file_paths, seed_value):
    """The original flat-pool shuffle: every episode is an equally-likely draw
    regardless of which show it belongs to. Kept as the fallback for pools
    that show_balanced_random_order can't safely group (movies, mixed
    TV/movie content, unparseable items), and for regression comparison."""
    ordered = list(file_paths)
    seeded = random.Random(seed_value)
    seeded.shuffle(ordered)
    return ordered


def show_balanced_random_order(paths, seed, parser=None):
    """Group paths by show, then rotate shows fairly before choosing an
    episode -- a 4-episode show and a 400-episode show each get one turn per
    cycle. Returns None if the pool can't be safely grouped as all-TV (the
    caller should fall back to legacy_random_channel_lineup in that case).
    Pure and deterministic: same seed + same paths -> same order. Does not
    mutate its input.
    """
    parser = parser or parse_local_media
    paths = list(paths)
    if not paths:
        return []

    show_order = []
    buckets = {}
    for path in paths:
        try:
            local = parser(path) or {}
        except Exception:
            return None
        if local.get("media_type") != "tv":
            return None
        key = metadata_lookup_key(path, local)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = []
            buckets[key] = bucket
            show_order.append(key)
        bucket.append(path)

    show_order = [key for key in show_order if buckets.get(key)]
    show_count = len(show_order)
    if show_count == 0:
        return None

    cycle_rng = random.Random(seed)

    per_show_queue = {}
    for key in show_order:
        episodes = list(buckets[key])
        random.Random(stable_hash(f"{seed}::{key}")).shuffle(episodes)
        per_show_queue[key] = episodes

    per_show_position = {key: 0 for key in show_order}
    per_show_last_episode = {key: None for key in show_order}

    def _swap_away_from(items, avoid_value):
        if len(items) < 2 or items[0] != avoid_value:
            return
        for i in range(1, len(items)):
            if items[i] != avoid_value:
                items[0], items[i] = items[i], items[0]
                return

    result = []
    total = len(paths)
    last_show_of_previous_cycle = None
    wrap_counters = {key: 0 for key in show_order}

    while len(result) < total:
        cycle_shows = list(show_order)
        cycle_rng.shuffle(cycle_shows)
        if show_count > 1:
            _swap_away_from(cycle_shows, last_show_of_previous_cycle)

        for key in cycle_shows:
            if len(result) >= total:
                break
            queue = per_show_queue[key]
            position = per_show_position[key]
            if position >= len(queue):
                wrap_counters[key] += 1
                reshuffled = list(buckets[key])
                random.Random(stable_hash(f"{seed}::{key}::wrap::{wrap_counters[key]}")).shuffle(reshuffled)
                _swap_away_from(reshuffled, per_show_last_episode[key])
                per_show_queue[key] = reshuffled
                queue = reshuffled
                position = 0
            episode = queue[position]
            per_show_position[key] = position + 1
            per_show_last_episode[key] = episode
            result.append(episode)

        last_show_of_previous_cycle = cycle_shows[-1] if cycle_shows else last_show_of_previous_cycle

    return result


def ordered_channel_lineup(root_path, channel_name, file_paths, playback_order=CATALOG_PLAYBACK_ORDER_RANDOM, shuffle_seed=None):
    ordered = list(file_paths)
    if normalize_playback_order(playback_order) == CATALOG_PLAYBACK_ORDER_SEQUENTIAL:
        ordered.sort(key=media_lineup_sort_key)
        return ordered
    seed_value = shuffle_seed if shuffle_seed is not None else stable_hash(f"{root_path}|{channel_name}")
    balanced = show_balanced_random_order(ordered, seed_value)
    if balanced is not None:
        return balanced
    return legacy_random_channel_lineup(ordered, seed_value)


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

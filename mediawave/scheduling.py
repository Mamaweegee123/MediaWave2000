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


def ordered_channel_lineup(root_path, channel_name, file_paths, playback_order=CATALOG_PLAYBACK_ORDER_RANDOM):
    ordered = list(file_paths)
    if normalize_playback_order(playback_order) == CATALOG_PLAYBACK_ORDER_SEQUENTIAL:
        ordered.sort(key=media_lineup_sort_key)
        return ordered
    seeded = random.Random(stable_hash(f"{root_path}|{channel_name}"))
    seeded.shuffle(ordered)
    return ordered


def generate_auto_schedule(root_path, channel_name, file_paths, playback_order=CATALOG_PLAYBACK_ORDER_RANDOM):
    normalized_order = normalize_playback_order(playback_order)
    return {
        "mode": "auto",
        "anchor_time": auto_schedule_anchor(),
        "playback_order": normalized_order,
        "lineup": ordered_channel_lineup(root_path, channel_name, file_paths, normalized_order),
    }

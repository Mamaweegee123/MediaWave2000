"""Pure helpers for restoring and validating the shared commercial library."""

import os


COMMERCIAL_ENTRY_KINDS = {"commercial", "promo", "bumper", "station_id"}


def cached_commercial_assets_for_root(cache_state, root_folder, path_exists=os.path.isfile):
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
        if path and path_exists(path):
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

"""Local artwork and description discovery helpers for MediaWave."""

import os
import re
import time

from .local_media import stable_hash


LOCAL_POSTER_NAMES = ("poster.jpg", "poster.jpeg", "poster.png", "folder.jpg", "folder.jpeg", "folder.png", "cover.jpg", "cover.jpeg", "cover.png")
LOCAL_FANART_NAMES = ("fanart.jpg", "fanart.jpeg", "fanart.png", "background.jpg", "background.jpeg", "background.png", "backdrop.jpg", "backdrop.jpeg", "backdrop.png")
LOCAL_CLEARLOGO_NAMES = ("clearlogo.png", "clearlogo.jpg", "clearlogo.jpeg", "logo.png", "logo.jpg", "logo.jpeg", "clearlogo-white.png")
LOCAL_DESCRIPTION_NAMES = ("show.txt", "description.txt", "plot.txt", "summary.txt", "desc.txt", "about.txt")

_LOCAL_MEDIA_ASSET_CACHE = {}
_LOCAL_ASSET_SIGNATURE_CACHE = {}


def clear_local_artwork_caches():
    _LOCAL_MEDIA_ASSET_CACHE.clear()
    _LOCAL_ASSET_SIGNATURE_CACHE.clear()


def unique_existing_dirs(paths):
    seen = set()
    results = []
    for path in paths:
        resolved = os.path.abspath(path or "")
        if not resolved or resolved in seen or not os.path.isdir(resolved):
            continue
        seen.add(resolved)
        results.append(resolved)
    return results


def local_asset_directories(path, local):
    parent_dir = os.path.dirname(path)
    grandparent_dir = os.path.dirname(parent_dir)
    parent_name = os.path.basename(parent_dir)
    if local.get("media_type") == "tv":
        if (
            re.search(r"\bseason\s*\d{1,2}\b", parent_name, re.IGNORECASE)
            or re.search(r"\b(specials?|extras?|bonus|ova|movies?)\b", parent_name, re.IGNORECASE)
        ):
            return unique_existing_dirs([grandparent_dir, parent_dir])
        return unique_existing_dirs([parent_dir, grandparent_dir])
    return unique_existing_dirs([parent_dir])


def find_named_asset(directories, names):
    wanted = {name.casefold(): name for name in names}
    for directory in directories:
        for name in names:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
        try:
            entries = os.listdir(directory)
        except OSError:
            continue
        by_name = {entry.casefold(): entry for entry in entries}
        for wanted_name in wanted:
            entry = by_name.get(wanted_name)
            if not entry:
                continue
            candidate = os.path.join(directory, entry)
            if os.path.isfile(candidate):
                return candidate
    return ""


def load_local_description_file(path):
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def discover_local_media_assets(path, local):
    cached = _LOCAL_MEDIA_ASSET_CACHE.get(path)
    now = time.monotonic()
    if isinstance(cached, tuple) and len(cached) == 2 and now - float(cached[0]) < 5.0:
        return dict(cached[1])
    directories = local_asset_directories(path, local)
    poster_path = find_named_asset(directories, LOCAL_POSTER_NAMES)
    fanart_path = find_named_asset(directories, LOCAL_FANART_NAMES)
    clearlogo_path = find_named_asset(directories, LOCAL_CLEARLOGO_NAMES)
    description_path = find_named_asset(directories, LOCAL_DESCRIPTION_NAMES)
    assets = {
        "directories": directories,
        "poster_path": poster_path,
        "fanart_path": fanart_path,
        "clearlogo_path": clearlogo_path,
        "description_path": description_path,
        "description": load_local_description_file(description_path),
    }
    if len(_LOCAL_MEDIA_ASSET_CACHE) > 12000:
        _LOCAL_MEDIA_ASSET_CACHE.clear()
    _LOCAL_MEDIA_ASSET_CACHE[path] = (now, dict(assets))
    return assets


def _fresh_file_signature(path):
    try:
        stat = os.stat(path)
        return stable_hash(f"{path}|{int(stat.st_mtime)}|{stat.st_size}")
    except OSError:
        return stable_hash(path)


def local_asset_signature(path, local):
    cached = _LOCAL_ASSET_SIGNATURE_CACHE.get(path)
    now = time.monotonic()
    if isinstance(cached, tuple) and len(cached) == 2 and now - float(cached[0]) < 5.0:
        return cached[1]
    assets = discover_local_media_assets(path, local)
    parts = [_fresh_file_signature(path)]
    for directory in assets.get("directories", []):
        try:
            stat = os.stat(directory)
            parts.append(f"dir:{directory}:{int(stat.st_mtime)}")
        except OSError:
            continue
    for key in ("poster_path", "fanart_path", "clearlogo_path", "description_path"):
        candidate = assets.get(key, "")
        if candidate:
            parts.append(_fresh_file_signature(candidate))
    signature = stable_hash("|".join(parts))
    if len(_LOCAL_ASSET_SIGNATURE_CACHE) > 12000:
        _LOCAL_ASSET_SIGNATURE_CACHE.clear()
    _LOCAL_ASSET_SIGNATURE_CACHE[path] = (now, signature)
    return signature

"""Recently Scheduled: a small, schema-versioned, persisted history of
media the Schedule Editor has actually placed into a lineup -- Put On
Air, Duplicate Here…, Copy to Another Day…, or Fill Open Time.

Deliberately NOT playback/watch history (channelsurfer2000.py has no such
concept today, and this module doesn't invent one it needs to merge
with) -- this is "what have I recently SCHEDULED", tracked purely by
stable media identity (`path`), never a live Channel/widget reference,
so it stays valid across catalog reloads and app restarts.

No Qt, no imports from channelsurfer2000 -- mirrors
mediawave/schedule_overrides.py's shape (schema version, normalize,
atomic tempfile+os.replace write) so this is one more small file in the
same family, not a new persistence pattern.
"""

import json
import os
import tempfile

RECENT_MEDIA_VERSION = 1
MAX_RECENT_ITEMS = 30


def empty_recent_data():
    return {"version": RECENT_MEDIA_VERSION, "items": []}


def normalize_recent_item(item):
    """Validated plain-dict copy of one recent-media record, or None if
    it's structurally unusable (no path -- there is nothing stable to key
    on without one). Unknown extra keys are dropped.
    """
    if not isinstance(item, dict):
        return None
    path = str(item.get("path", "") or "")
    if not path:
        return None
    try:
        duration = float(item.get("duration", 0) or 0)
    except (TypeError, ValueError):
        duration = 0.0
    try:
        last_scheduled_at = float(item.get("last_scheduled_at", 0) or 0)
    except (TypeError, ValueError):
        last_scheduled_at = 0.0
    return {
        "path": path,
        "title": str(item.get("title", "") or ""),
        "media_type": str(item.get("media_type", "") or "tv"),
        "duration": duration,
        "channel_name": str(item.get("channel_name", "") or ""),
        "last_context": str(item.get("last_context", "") or ""),
        "last_scheduled_at": last_scheduled_at,
    }


def normalize_recent_data(data):
    """(normalized_data, ok) -- same contract as
    schedule_overrides.normalize_overrides_data: ok is False when the
    payload was malformed at the top level, so callers can keep the
    previous in-memory state rather than silently truncating it.
    """
    if not isinstance(data, dict):
        return empty_recent_data(), False
    try:
        version = int(data.get("version", 0) or 0)
    except (TypeError, ValueError):
        return empty_recent_data(), False
    if version < 1 or version > RECENT_MEDIA_VERSION:
        return empty_recent_data(), False
    raw = data.get("items")
    if not isinstance(raw, list):
        return empty_recent_data(), False
    items = []
    for entry in raw:
        normalized = normalize_recent_item(entry)
        if normalized is not None:
            items.append(normalized)
    return {"version": RECENT_MEDIA_VERSION, "items": items[:MAX_RECENT_ITEMS]}, True


def load_recent_media(path):
    """Load and validate the recent-media file. Malformed or missing
    files yield an empty structure -- the file itself is never rewritten
    or deleted here.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return empty_recent_data()
    normalized, _ok = normalize_recent_data(data)
    return normalized


def save_recent_media(path, data):
    """Atomically persist recent-media history. Returns (ok, error). A
    structurally bad payload is refused outright, leaving the existing
    file untouched -- same contract as
    schedule_overrides.save_schedule_overrides.
    """
    normalized, ok = normalize_recent_data(data)
    if not ok:
        return False, "The recent-media data was not in a valid format, so the existing file was left unchanged."
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".schedule_recent_media_", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(normalized, handle, indent=2)
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    except OSError as error:
        return False, f"The recent-media file could not be written ({error.strerror or error})."
    return True, ""


def record_recent_media(data, item, now=None):
    """The new recent-media data after recording one successful
    placement: `item` moves to the front (newest first), any existing
    entry for the same `path` is removed first (so re-scheduling
    something already-recent re-promotes it rather than duplicating it),
    and the list is capped at MAX_RECENT_ITEMS. Returns a fresh dict;
    does not mutate `data`.
    """
    normalized_item = normalize_recent_item(item)
    if normalized_item is None:
        return data if isinstance(data, dict) else empty_recent_data()
    normalized_item["last_scheduled_at"] = float(now) if now is not None else normalized_item["last_scheduled_at"]

    current, _ok = normalize_recent_data(data if isinstance(data, dict) else empty_recent_data())
    items = [entry for entry in current["items"] if entry["path"] != normalized_item["path"]]
    items.insert(0, normalized_item)
    return {"version": RECENT_MEDIA_VERSION, "items": items[:MAX_RECENT_ITEMS]}


def recent_items_resolved(items, exists_fn):
    """Recent items whose media file still exists, in the same (newest-
    first) order -- missing media is dropped rather than shown as a dead
    entry (spec: "missing recent media is handled gracefully").
    `exists_fn` is injected (real callers pass os.path.isfile) so this
    stays testable without touching a filesystem.
    """
    return [item for item in (items or []) if exists_fn(item.get("path", ""))]

"""Pure companion-channel logic for Channel Studio.

Companion channels (WeatherStar, RadioWaveTV, NetTV) are built-in,
non-folder channels configured in Advanced Configuration's Companion
Channels tab (see `AdvancedConfigDialog.build_companion_tab` in
channelsurfer2000.py). Each type has its own dedicated
`<type>_enabled` / `<type>_channel_number` setting -- there's no shared
companion registry in the app today, so this module defines one
normalized "snapshot" shape so Channel Studio can treat all three
uniformly.

No Qt, no live channel objects, no filesystem -- just dicts and numbers,
so this stays testable without a QApplication (same pattern as
reorder.py). `channel_actions.py` does the Qt-side work of reading a
snapshot off the real dialog widgets and applying one back.
"""

COMPANION_TYPES = ("weatherstar", "radiowave", "youtube")

COMPANION_CHANNEL_IDS = {
    "weatherstar": "special:weatherstar",
    "radiowave": "special:radiowave",
    "youtube": "special:youtube",
}

COMPANION_NAMES = {
    "weatherstar": "WeatherStar 4000+",
    "radiowave": "RadioWaveTV",
    "youtube": "NetTV",
}

COMPANION_INFO_LABELS = {
    "weatherstar": "Location",
    "radiowave": "Music Folder",
    "youtube": "Playlist",
}


def empty_snapshot():
    """The all-disabled starting point every read_companion_snapshot()
    result is built on top of. `name` is blank here -- blank means "use
    the built-in COMPANION_NAMES default", same convention
    read_companion_snapshot and companion_summaries use.
    """
    return {
        companion_type: {"enabled": False, "number": 1, "detail": "", "name": ""}
        for companion_type in COMPANION_TYPES
    }


def read_companion_snapshot(raw):
    """Normalize a raw settings-like dict (the same key names
    AdvancedConfigDialog.values()/app_settings use: weatherstar_enabled,
    weatherstar_channel_number, weatherstar_location,
    weatherstar_display_name, radiowave_enabled, radiowave_channel_number,
    radiowave_folder, radiowave_display_name, youtube_enabled,
    youtube_channel_number, youtube_playlist_url, youtube_display_name)
    into this module's snapshot shape. Never raises -- malformed or
    missing fields just fall back to disabled defaults.

    `name` is blank when the user hasn't renamed a companion yet --
    companion_summaries falls back to the built-in COMPANION_NAMES in
    that case, same as the type's hardcoded default before this field
    existed.
    """
    raw = raw if isinstance(raw, dict) else {}

    def _int(value, default=1):
        try:
            return int(value or default)
        except (TypeError, ValueError):
            return default

    return {
        "weatherstar": {
            "enabled": bool(raw.get("weatherstar_enabled", False)),
            "number": _int(raw.get("weatherstar_channel_number", 1)),
            "detail": str(raw.get("weatherstar_location", "") or "").strip(),
            "name": str(raw.get("weatherstar_display_name", "") or "").strip(),
        },
        "radiowave": {
            "enabled": bool(raw.get("radiowave_enabled", False)),
            "number": _int(raw.get("radiowave_channel_number", 1)),
            "detail": str(raw.get("radiowave_folder", "") or "").strip(),
            "name": str(raw.get("radiowave_display_name", "") or "").strip(),
        },
        "youtube": {
            "enabled": bool(raw.get("youtube_enabled", False)),
            "number": _int(raw.get("youtube_channel_number", 1)),
            "detail": str(raw.get("youtube_playlist_url", "") or "").strip(),
            "name": str(raw.get("youtube_display_name", "") or "").strip(),
        },
    }


def companion_summaries(snapshot, status_by_type=None):
    """Enabled companions only, as plain summary dicts (keys match
    ChannelStudioSummary's constructor kwargs), sorted by real channel
    number. Disabled companions are simply absent from the result --
    that mirrors how the live app already drops disabled companions
    from the real lineup (inject_special_channels / apply_catalog_
    channel_customizations in channelsurfer2000.py never even
    considers them channel_type == "media" filtering), so hiding
    disabled companions needs no extra logic here.

    `status_by_type`, if given, is an optional dict of richer live
    status strings (e.g. "12 tracks found") keyed by companion type
    that override the configured `detail` when the channel is actually
    loaded and running; falls back to the configured detail (location/
    folder/playlist) otherwise, so the card always has something to
    show even before the app has built a live object for it.
    """
    status_by_type = status_by_type if isinstance(status_by_type, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    results = []
    for companion_type in COMPANION_TYPES:
        entry = snapshot.get(companion_type) or {}
        if not entry.get("enabled"):
            continue
        detail = status_by_type.get(companion_type) or entry.get("detail") or "Not configured yet"
        results.append(
            {
                "channel_id": COMPANION_CHANNEL_IDS[companion_type],
                "name": str(entry.get("name") or "").strip() or COMPANION_NAMES[companion_type],
                "number": int(entry.get("number", 1) or 1),
                "channel_type": companion_type,
                "companion_info_label": COMPANION_INFO_LABELS[companion_type],
                "companion_info_value": detail,
            }
        )
    results.sort(key=lambda item: (item["number"], item["name"]))
    return results


def set_companion_enabled(snapshot, companion_type, enabled):
    """Pure update: a new snapshot with one companion's enabled flag
    flipped. Unknown companion_type is a safe no-op (returns a copy of
    the input unchanged).
    """
    snapshot = dict(snapshot or {})
    if companion_type not in COMPANION_TYPES:
        return snapshot
    entry = dict(snapshot.get(companion_type) or {})
    entry["enabled"] = bool(enabled)
    snapshot[companion_type] = entry
    return snapshot

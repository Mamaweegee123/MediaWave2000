"""Channel logo settings helpers for MediaWave."""


CHANNEL_BUG_SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
CHANNEL_BUG_PREFERRED_NAMES = ("logo.png", "channel.png", "bug.png")
CHANNEL_BUG_CORNER_OPTIONS = ("top-left", "top-right", "bottom-left", "bottom-right")
CHANNEL_BUG_OVERRIDE_MODES = ("global", "custom", "off")

_TIMING_DEFAULTS = {
    "always_visible": False,
    "on_channel_tune": True,
    "on_program_start": False,
    "periodic": False,
    "duration_seconds": 5,
    "periodic_interval_minutes": 10,
}

CHANNEL_BUG_DURATION_OPTIONS = [
    ("5 seconds", 5),
    ("10 seconds", 10),
    ("15 seconds", 15),
    ("30 seconds", 30),
    ("1 minute", 60),
]

CHANNEL_BUG_INTERVAL_OPTIONS = [
    ("1 minute", 1),
    ("5 minutes", 5),
    ("10 minutes", 10),
    ("15 minutes", 15),
    ("30 minutes", 30),
]

CHANNEL_BUG_PLACEMENT_AREAS = ("overlay", "video_content")
CHANNEL_BUG_PLACEMENT_LABELS = {
    "overlay": "Screen area",
    "video_content": "Video content area",
}


def normalize_timing(t):
    if not isinstance(t, dict):
        t = {}
    result = dict(_TIMING_DEFAULTS)
    for key in ("always_visible", "on_channel_tune", "on_program_start", "periodic"):
        if key in t:
            result[key] = bool(t[key])
    if "duration_seconds" in t:
        result["duration_seconds"] = max(1, min(3600, int(t["duration_seconds"] or 5)))
    if "periodic_interval_minutes" in t:
        result["periodic_interval_minutes"] = max(1, min(120, int(t["periodic_interval_minutes"] or 10)))
    if result["always_visible"]:
        result["on_channel_tune"] = False
        result["on_program_start"] = False
        result["periodic"] = False
    elif result["on_program_start"]:
        result["on_channel_tune"] = False
    elif not any([result["on_channel_tune"], result["on_program_start"], result["periodic"]]):
        result["on_channel_tune"] = True
    return result


def migrate_old_timing_fields(settings_dict, fallback_timing=None):
    existing = settings_dict.get("timing")
    if isinstance(existing, dict):
        return normalize_timing(existing)

    old_mode = settings_dict.get("timing_mode", "")
    old_dur = settings_dict.get("timing_duration") or settings_dict.get("duration_seconds") or 5
    old_interval = settings_dict.get("periodic_interval") or settings_dict.get("periodic_interval_minutes") or 10

    try:
        old_dur = int(old_dur)
    except (TypeError, ValueError):
        old_dur = 5
    try:
        old_interval = int(old_interval)
    except (TypeError, ValueError):
        old_interval = 10

    t = {"duration_seconds": old_dur, "periodic_interval_minutes": old_interval}
    if old_mode in ("always", "always_visible"):
        t["always_visible"] = True
    elif old_mode in ("on_tune", "channel_tune"):
        t["on_channel_tune"] = True
    elif old_mode == "on_program_start":
        t["on_program_start"] = True
    elif old_mode == "periodic":
        t["on_channel_tune"] = True
        t["periodic"] = True
    else:
        if isinstance(fallback_timing, dict):
            return dict(fallback_timing)
        t["always_visible"] = True
    return normalize_timing(t)


def channel_bug_settings_defaults():
    return {
        "enabled": False,
        "corner": "bottom-right",
        "opacity": 0.75,
        "size": 80,
        "margin": 18,
        "horizontal_offset": 0,
        "vertical_offset": 0,
        "placement_area": "overlay",
        "grayscale_on_video": False,
        "fade": True,
        "timing": dict(_TIMING_DEFAULTS),
        "channel_overrides": {},
    }


def channel_bug_channel_defaults():
    return {
        "mode": "global",
    }


def normalize_channel_bug_override(override, global_settings):
    if not isinstance(override, dict):
        return {"mode": "global"}
    mode = str(override.get("mode", "global") or "global")
    if mode not in CHANNEL_BUG_OVERRIDE_MODES:
        if "enabled" in override and not override.get("enabled", True):
            mode = "off"
        else:
            mode = "global"
    result = {"mode": mode}
    if mode == "custom":
        gs = global_settings or {}
        result["corner"] = str(override.get("corner") or gs.get("corner", "bottom-right"))
        if result["corner"] not in CHANNEL_BUG_CORNER_OPTIONS:
            result["corner"] = gs.get("corner", "bottom-right")
        result["opacity"] = max(0.1, min(1.0, float(override.get("opacity") or gs.get("opacity", 0.75))))
        result["size"] = max(32, min(256, int(override.get("size") or gs.get("size", 80))))
        result["margin"] = max(0, min(120, int(override.get("margin") if override.get("margin") is not None else gs.get("margin", 18))))
        result["horizontal_offset"] = max(-240, min(240, int(override.get("horizontal_offset") if override.get("horizontal_offset") is not None else gs.get("horizontal_offset", 0))))
        result["vertical_offset"] = max(-240, min(240, int(override.get("vertical_offset") if override.get("vertical_offset") is not None else gs.get("vertical_offset", 0))))
        result["placement_area"] = str(override.get("placement_area") or gs.get("placement_area", "overlay"))
        if result["placement_area"] not in CHANNEL_BUG_PLACEMENT_AREAS:
            result["placement_area"] = gs.get("placement_area", "overlay")
        result["grayscale_on_video"] = bool(override.get("grayscale_on_video") if "grayscale_on_video" in override else gs.get("grayscale_on_video", False))
        result["fade"] = bool(override.get("fade") if override.get("fade") is not None else gs.get("fade", True))
        result["timing"] = migrate_old_timing_fields(override, fallback_timing=gs.get("timing") or {})
    return result


def normalize_channel_bug_settings(settings):
    defaults = channel_bug_settings_defaults()
    source = settings if isinstance(settings, dict) else {}
    merged = dict(defaults)
    for k in ("enabled", "corner", "opacity", "size", "margin", "horizontal_offset", "vertical_offset", "placement_area", "grayscale_on_video", "fade"):
        if k in source:
            merged[k] = source[k]
    merged["enabled"] = bool(merged.get("enabled", False))
    merged["corner"] = str(merged.get("corner", "bottom-right"))
    if merged["corner"] not in CHANNEL_BUG_CORNER_OPTIONS:
        merged["corner"] = "bottom-right"
    merged["opacity"] = max(0.1, min(1.0, float(merged.get("opacity", 0.75) or 0.75)))
    merged["size"] = max(32, min(256, int(merged.get("size", 80) or 80)))
    merged["margin"] = max(0, min(120, int(merged.get("margin", 18) or 18)))
    merged["horizontal_offset"] = max(-240, min(240, int(merged.get("horizontal_offset", 0) or 0)))
    merged["vertical_offset"] = max(-240, min(240, int(merged.get("vertical_offset", 0) or 0)))
    merged["placement_area"] = str(merged.get("placement_area", "overlay") or "overlay")
    if merged["placement_area"] not in CHANNEL_BUG_PLACEMENT_AREAS:
        merged["placement_area"] = "overlay"
    merged["grayscale_on_video"] = bool(merged.get("grayscale_on_video", False))
    merged["fade"] = bool(merged.get("fade", True))
    merged["timing"] = migrate_old_timing_fields(source)
    overrides_raw = source.get("channel_overrides") or {}
    normalized_overrides = {}
    for ch_name, override in overrides_raw.items():
        if not isinstance(ch_name, str) or not isinstance(override, dict):
            continue
        normalized_overrides[str(ch_name)] = normalize_channel_bug_override(override, merged)
    merged["channel_overrides"] = normalized_overrides
    return merged


def get_effective_channel_logo_settings(channel_name, global_settings):
    gs = global_settings if isinstance(global_settings, dict) else channel_bug_settings_defaults()
    if not gs.get("enabled", False):
        result = dict(gs)
        result["enabled"] = False
        return result
    overrides = gs.get("channel_overrides") or {}
    ch_override = overrides.get(channel_name) if channel_name else None
    if not isinstance(ch_override, dict):
        return dict(gs)
    mode = ch_override.get("mode", "global")
    if mode == "off":
        result = dict(gs)
        result["enabled"] = False
        return result
    if mode == "custom":
        result = dict(gs)
        result["corner"] = ch_override.get("corner", gs.get("corner", "bottom-right"))
        result["opacity"] = ch_override.get("opacity", gs.get("opacity", 0.75))
        result["size"] = ch_override.get("size", gs.get("size", 80))
        result["margin"] = ch_override.get("margin", gs.get("margin", 18))
        result["horizontal_offset"] = ch_override.get("horizontal_offset", gs.get("horizontal_offset", 0))
        result["vertical_offset"] = ch_override.get("vertical_offset", gs.get("vertical_offset", 0))
        result["placement_area"] = ch_override.get("placement_area", gs.get("placement_area", "overlay"))
        result["grayscale_on_video"] = ch_override.get("grayscale_on_video", gs.get("grayscale_on_video", False))
        result["fade"] = ch_override.get("fade", gs.get("fade", True))
        result["timing"] = normalize_timing(ch_override.get("timing") or gs.get("timing") or {})
        return result
    return dict(gs)

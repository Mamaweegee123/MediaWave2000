"""Channel logo settings helpers for MediaWave."""

import os
import re


CHANNEL_BUG_SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
CHANNEL_BUG_PREFERRED_NAMES = ("logo.png", "channel.png", "bug.png")
CHANNEL_BUG_CORNER_OPTIONS = ("top-left", "top-right", "bottom-left", "bottom-right")
CHANNEL_BUG_OVERRIDE_MODES = ("global", "custom", "off")
COMPANION_LOGO_ALIASES = {
    "weatherstar": ("WeatherStar 4000+", "WeatherStar 4000", "WeatherStar", "weatherstar"),
    "radiowave": ("RadioWaveTV", "RadioWave", "radiowave"),
    "youtube": ("NetTV", "nettv", "youtube"),
}
COMPANION_LOGO_FOLDER_NAMES = {
    "weatherstar": "WeatherStar",
    "radiowave": "RadioWave",
    "youtube": "NetTV",
}
COMPANION_ID_TYPES = {
    "special:weatherstar": "weatherstar",
    "special:radiowave": "radiowave",
    "special:youtube": "youtube",
}


def _append_unique(values, value):
    value = str(value or "").strip()
    if value and value not in values:
        values.append(value)


def companion_logo_type(channel_name="", channel_id=None, channel_type=None, display_name=None):
    """Best-effort companion classifier for shared logo aliases."""
    raw_type = str(channel_type or "").strip().lower()
    if raw_type in COMPANION_LOGO_ALIASES:
        return raw_type
    raw_id = str(channel_id or "").strip().lower()
    if raw_id in COMPANION_ID_TYPES:
        return COMPANION_ID_TYPES[raw_id]
    names = [channel_name, display_name]
    for name in names:
        folded = re.sub(r"[^a-z0-9]+", "", str(name or "").lower())
        if not folded:
            continue
        if folded.startswith("weatherstar"):
            return "weatherstar"
        if folded.startswith("radiowave"):
            return "radiowave"
        if folded in {"nettv", "youtube"} or folded.startswith("nettv"):
            return "youtube"
    return ""


def channel_bug_logo_candidate_names(channel_name, channel_id=None, channel_type=None, display_name=None):
    """Ordered names to check for a channel logo file.

    Companions check their canonical names first, then the current display
    name/stable name/id aliases. That keeps a renamed WeatherStar channel able
    to find WeatherStar.png while still allowing a user to name a file after
    the renamed channel if there is no canonical logo.
    """
    candidates = []
    ctype = companion_logo_type(channel_name, channel_id=channel_id, channel_type=channel_type, display_name=display_name)
    if ctype:
        for alias in COMPANION_LOGO_ALIASES.get(ctype, ()):
            _append_unique(candidates, alias)
    _append_unique(candidates, display_name)
    _append_unique(candidates, channel_name)
    raw_id = str(channel_id or "").strip()
    if raw_id:
        _append_unique(candidates, raw_id)
        if ":" in raw_id:
            _append_unique(candidates, raw_id.split(":", 1)[1])
    return candidates


def companion_logo_folder(shared_logos_dir, channel_name="", channel_id=None, channel_type=None, display_name=None):
    """Stable companion artwork folder, independent of display name."""
    if not shared_logos_dir:
        return ""
    ctype = companion_logo_type(channel_name, channel_id=channel_id, channel_type=channel_type, display_name=display_name)
    folder = COMPANION_LOGO_FOLDER_NAMES.get(ctype, "")
    return os.path.join(shared_logos_dir, folder) if folder else ""


def _scan_logo_dir(logos_dir, channel_names, allow_any_image_fallback):
    """Look for a channel's logo inside an already-resolved directory.

    `allow_any_image_fallback` gates two things that only make sense for
    a folder scoped to ONE channel (a local channel's own <root>/Logos/):
    the bare preferred names (logo.png/channel.png/bug.png), and the
    last-resort "just take whatever image is in here" fallback. Neither
    is safe for the shared, multi-channel User Content/Logos/ folder --
    grabbing an arbitrary file there could just as easily return a
    completely different channel's logo, so a shared-folder lookup only
    ever matches a real <channel_name>.<ext> file.
    """
    if not os.path.isdir(logos_dir):
        return ""
    try:
        entries = os.listdir(logos_dir)
    except OSError:
        return ""
    lower_entries = {e.lower(): e for e in entries}

    def candidate(name):
        actual = lower_entries.get(name.lower())
        if actual:
            p = os.path.join(logos_dir, actual)
            if os.path.isfile(p):
                return p
        return ""

    if allow_any_image_fallback:
        # Exact preferred names -- only meaningful in a single-channel folder.
        for name in CHANNEL_BUG_PREFERRED_NAMES:
            c = candidate(name)
            if c:
                return c

    # <channel_name>.png variants -- safe in either kind of folder.
    # Allow "+" -- COMPANION_NAMES["weatherstar"] is literally
    # "WeatherStar 4000+" (see companion_adapter.py), and a filename built
    # from that real name needs to round-trip through this sanitizer.
    for channel_name in channel_names or []:
        safe_name = re.sub(r"[^\w\-.+ ]", "", channel_name or "").strip()
        if not safe_name:
            continue
        for ext in CHANNEL_BUG_SUPPORTED_EXTS:
            c = candidate(f"{safe_name}{ext}")
            if c:
                return c

    if not allow_any_image_fallback:
        return ""

    # Any supported image in the folder, prefer PNG first.
    png_hits = []
    other_hits = []
    for entry in sorted(entries):
        ext = os.path.splitext(entry)[1].lower()
        if ext in CHANNEL_BUG_SUPPORTED_EXTS:
            full = os.path.join(logos_dir, entry)
            if os.path.isfile(full):
                if ext == ".png":
                    png_hits.append(full)
                else:
                    other_hits.append(full)
    if png_hits:
        return png_hits[0]
    if other_hits:
        return other_hits[0]
    return ""


def _scan_companion_logo_dir(logos_dir):
    """Preferred companion-folder lookup: logo.* first, then one image."""
    if not os.path.isdir(logos_dir):
        return ""
    try:
        entries = os.listdir(logos_dir)
    except OSError:
        return ""
    lower_entries = {e.lower(): e for e in entries}

    def candidate(name):
        actual = lower_entries.get(name.lower())
        if actual:
            p = os.path.join(logos_dir, actual)
            if os.path.isfile(p):
                return p
        return ""

    for name in ("logo.png", "logo.webp", "logo.jpg", "logo.jpeg"):
        found = candidate(name)
        if found:
            return found
    for name in CHANNEL_BUG_PREFERRED_NAMES:
        found = candidate(name)
        if found:
            return found

    image_hits = []
    for entry in sorted(entries, key=str.casefold):
        ext = os.path.splitext(entry)[1].lower()
        full = os.path.join(logos_dir, entry)
        if ext in CHANNEL_BUG_SUPPORTED_EXTS and os.path.isfile(full):
            image_hits.append(full)
    return image_hits[0] if len(image_hits) == 1 else ""


def channel_bug_logo_lookup_details(root_path, channel_name, shared_logos_dir=None, channel_id=None, channel_type=None, display_name=None):
    """Discover the best logo image for a channel.

    The single source of truth for channel logo discovery -- real
    playback (ChannelBugOverlay.configure in channelsurfer2000.py) and
    every UI that shows a logo preview (Channel Studio cards, Logo
    Studio) all call this same function, so "logos work during
    playback but Channel Studio can't find them" can't happen from a
    second, weaker lookup drifting out of sync with this one.

    Looks first in <root_path>/Logos/ (unchanged from before -- existing
    local-channel setups keep working exactly as they did, and never even
    reach the fallback below). If nothing is found there (including when
    `root_path` is empty, as for every companion channel -- WeatherStar,
    RadioWaveTV, NetTV -- which have no folder of their own), falls back
    to `shared_logos_dir` (the portable User Content/Logos/ folder every
    channel can use, keyed by channel name -- e.g. "MTV.png",
    "WeatherStar.png"). This is what finally gives companion channels a
    real logo path.

    Returns a dict with path, source, and the ordered candidate names checked.
    """
    candidates = channel_bug_logo_candidate_names(
        channel_name,
        channel_id=channel_id,
        channel_type=channel_type,
        display_name=display_name,
    )
    if root_path:
        found = _scan_logo_dir(os.path.join(root_path, "Logos"), [channel_name], allow_any_image_fallback=True)
        if found:
            return {"path": found, "source": "local", "candidates": candidates}
    if shared_logos_dir:
        folder = companion_logo_folder(
            shared_logos_dir,
            channel_name,
            channel_id=channel_id,
            channel_type=channel_type,
            display_name=display_name,
        )
        found = _scan_companion_logo_dir(folder)
        if found:
            return {"path": found, "source": "companion-folder", "candidates": candidates}
        found = _scan_logo_dir(shared_logos_dir, candidates, allow_any_image_fallback=False)
        if found:
            return {"path": found, "source": "shared", "candidates": candidates}
    return {"path": "", "source": "", "candidates": candidates}


def find_channel_bug_logo(root_path, channel_name, shared_logos_dir=None, channel_id=None, channel_type=None, display_name=None):
    """Discover the best logo image for a channel.

    The single source of truth for channel logo discovery -- real
    playback (ChannelBugOverlay.configure in channelsurfer2000.py) and
    every UI that shows a logo preview (Channel Studio cards, Logo
    Studio) all call this same function, so "logos work during
    playback but Channel Studio can't find them" can't happen from a
    second, weaker lookup drifting out of sync with this one.

    Looks first in <root_path>/Logos/ (unchanged from before -- existing
    local-channel setups keep working exactly as they did, and never even
    reach the fallback below). If nothing is found there (including when
    `root_path` is empty, as for every companion channel -- WeatherStar,
    RadioWaveTV, NetTV -- which have no folder of their own), falls back
    to `shared_logos_dir` (the portable User Content/Logos/ folder every
    channel can use, keyed by channel name or companion alias -- e.g.
    "MTV.png", "WeatherStar 4000+.png", "WeatherStar.png").

    Returns an absolute path string or "" if none found.
    """
    return channel_bug_logo_lookup_details(
        root_path,
        channel_name,
        shared_logos_dir=shared_logos_dir,
        channel_id=channel_id,
        channel_type=channel_type,
        display_name=display_name,
    ).get("path", "")


_TIMING_DEFAULTS = {
    "always_visible": False,
    "on_channel_tune": True,
    "on_program_start": False,
    "periodic": False,
    "duration_seconds": 5,
    "periodic_interval_minutes": 10,
    # Random-interval periodic mode: when set, each periodic cycle picks a
    # fresh interval within [interval_min_minutes, interval_max_minutes]
    # instead of firing on a fixed clock. Chosen once per cycle (a handful
    # of minutes apart at minimum), never per-frame, so it can't flicker.
    "random_interval": False,
    "interval_min_minutes": 5,
    "interval_max_minutes": 20,
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

# Logo Studio's simulated-screen shape -- a per-channel setting (like
# excluded_shows) independent of Default/Custom/Off mode, so switching
# modes never resets which shape the user picked for this channel.
# Purely a Channel Studio preview concept -- real playback happens inside
# whatever window/aspect the video itself already has, so this never
# flows into ChannelBugOverlay.
CHANNEL_BUG_SCREEN_ASPECT_OPTIONS = ("16:9", "4:3")
CHANNEL_BUG_SCREEN_ASPECT_DEFAULT = "16:9"
_SCREEN_ASPECT_DIMENSIONS = {"16:9": (16, 9), "4:3": (4, 3)}


def normalize_screen_aspect(value):
    v = str(value or CHANNEL_BUG_SCREEN_ASPECT_DEFAULT)
    return v if v in CHANNEL_BUG_SCREEN_ASPECT_OPTIONS else CHANNEL_BUG_SCREEN_ASPECT_DEFAULT


def screen_aspect_dimensions(aspect):
    """(w, h) ratio ints for a screen_aspect value, e.g. "4:3" -> (4, 3)."""
    return _SCREEN_ASPECT_DIMENSIONS.get(normalize_screen_aspect(aspect), (16, 9))


def compute_active_screen_rect(width, height, aspect_w, aspect_h):
    """(x, y, w, h) of the centered "active" placement rectangle inside a
    width x height box, matching a target aspect_w:aspect_h shape.

    Pillarboxed (narrower than the box, centered horizontally, full
    height) when the target aspect is narrower than the box's own --
    e.g. a 4:3 active area inside a 16:9 Logo Studio preview widget.
    Letterboxed (shorter, centered vertically, full width) in the
    opposite case. Equals the full box when the aspects already match.

    Pure geometry, no Qt dependency, so it's testable without a
    QApplication -- Logo Studio's preview widget (see
    logo_studio.LogoPreviewScreen.active_rect) wraps this in a QRect,
    and it's also the single source of truth both the widget's drag
    clamp and its paintEvent use, so they can't drift apart.
    """
    width = max(1, int(width))
    height = max(1, int(height))
    aspect_w = max(1, int(aspect_w or 1))
    aspect_h = max(1, int(aspect_h or 1))
    target_w = height * aspect_w / aspect_h
    if target_w <= width:
        x = round((width - target_w) / 2.0)
        return (x, 0, max(1, round(target_w)), height)
    target_h = width * aspect_h / aspect_w
    y = round((height - target_h) / 2.0)
    return (0, y, width, max(1, round(target_h)))


def resolve_channel_bug_canvas_rect(canvas_width, canvas_height, screen_aspect):
    """(x, y, w, h) of the centered, screen_aspect-shaped placement canvas
    inside a canvas_width x canvas_height box -- the ONE shared resolver for
    "what rectangle should a channel's logo be positioned within", used by
    both the Logo Studio editor preview and real playback
    (ChannelBugOverlay.paintEvent in channelsurfer2000.py), so a channel's
    4:3/16:9 choice means the same physical placement canvas in both places
    instead of only ever affecting the editor's own preview widget.

    Just screen_aspect_dimensions(screen_aspect) fed into
    compute_active_screen_rect -- a thin, named combination of two already-
    existing pure functions so callers don't each have to remember to chain
    them themselves.
    """
    aspect_w, aspect_h = screen_aspect_dimensions(screen_aspect)
    return compute_active_screen_rect(canvas_width, canvas_height, aspect_w, aspect_h)


def normalize_timing(t):
    if not isinstance(t, dict):
        t = {}
    result = dict(_TIMING_DEFAULTS)
    for key in ("always_visible", "on_channel_tune", "on_program_start", "periodic", "random_interval"):
        if key in t:
            result[key] = bool(t[key])
    if "duration_seconds" in t:
        result["duration_seconds"] = max(1, min(3600, int(t["duration_seconds"] or 5)))
    if "periodic_interval_minutes" in t:
        result["periodic_interval_minutes"] = max(1, min(120, int(t["periodic_interval_minutes"] or 10)))
    if "interval_min_minutes" in t:
        result["interval_min_minutes"] = max(1, min(120, int(t["interval_min_minutes"] or 5)))
    if "interval_max_minutes" in t:
        result["interval_max_minutes"] = max(1, min(120, int(t["interval_max_minutes"] or 20)))
    if result["interval_max_minutes"] < result["interval_min_minutes"]:
        result["interval_max_minutes"] = result["interval_min_minutes"]
    if not result["periodic"]:
        result["random_interval"] = False
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


def normalize_show_exclusions(raw):
    """A deduped, order-preserving list of non-empty show-key strings."""
    if not isinstance(raw, (list, tuple)):
        return []
    seen = set()
    result = []
    for item in raw:
        key = str(item or "").strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


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
    # Show exclusions are independent of mode -- a channel can be in
    # Default (global) logo mode and still hide the bug for specific
    # shows that already have a network logo baked in (see
    # channel_logo_excluded_shows / is_show_excluded below).
    excluded_shows = normalize_show_exclusions(override.get("excluded_shows"))
    if excluded_shows:
        result["excluded_shows"] = excluded_shows
    # Screen shape is a real per-channel Logo Studio setting, but like
    # excluded_shows it's independent of mode -- picking 4:3 for a
    # channel shouldn't be undone by switching Default/Custom/Off.
    # Only stored when it differs from the default, same rationale as
    # excluded_shows: it keeps untouched channels' saved settings
    # unchanged.
    if "screen_aspect" in override:
        screen_aspect = normalize_screen_aspect(override.get("screen_aspect"))
        if screen_aspect != CHANNEL_BUG_SCREEN_ASPECT_DEFAULT:
            result["screen_aspect"] = screen_aspect
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
        # Freeform drag position -- normalized [0.0, 1.0] coordinates (see
        # resolve_freeform_position). Only meaningful once both axes are
        # set (a real drag always writes both together); a channel that
        # has never been dragged in the new editor has neither, and
        # falls back to corner + margin + offset (resolve_effective_logo_position).
        pos_x = override.get("pos_x")
        pos_y = override.get("pos_y")
        if pos_x is not None and pos_y is not None:
            try:
                result["pos_x"] = max(0.0, min(1.0, float(pos_x)))
                result["pos_y"] = max(0.0, min(1.0, float(pos_y)))
            except (TypeError, ValueError):
                pass
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
        result["pos_x"] = ch_override.get("pos_x")
        result["pos_y"] = ch_override.get("pos_y")
        return result
    return dict(gs)


def pick_periodic_interval_minutes(timing, rng=None):
    """The number of minutes until the next periodic show.

    Fixed `periodic_interval_minutes` unless `random_interval` is set, in
    which case a fresh value is drawn from
    [interval_min_minutes, interval_max_minutes] -- callers are expected to
    call this once per cycle (when a periodic timer (re)starts), not per
    frame, so the result only changes a handful of times per hour at most.

    `rng` takes any object with a `.uniform(a, b)` method (e.g. `random`,
    or a `random.Random(seed)` for deterministic tests); defaults to the
    stdlib `random` module.
    """
    t = timing if isinstance(timing, dict) else {}
    if not t.get("random_interval"):
        return max(1, int(t.get("periodic_interval_minutes", 10) or 10))
    lo = max(1, int(t.get("interval_min_minutes", 5) or 5))
    hi = max(lo, int(t.get("interval_max_minutes", 20) or 20))
    if rng is None:
        import random as rng
    return rng.uniform(lo, hi)


# ── Logo Studio v1: simulated-screen position math ──────────────────────────
#
# The overlay positions the logo by corner + margin + horizontal/vertical
# offset (see ChannelBugOverlay.paintEvent in channelsurfer2000.py) -- never
# raw x/y. These two functions are the exact same math, factored out so the
# Logo Studio preview widget can convert a drag position to real settings
# (and back) without duplicating or drifting from the real overlay's layout.
#
# Both operate in one consistent unit space (e.g. real screen pixels, or a
# scaled-down preview-canvas pixel space -- callers pick the space and stay
# consistent within a single call).

LOGO_OFFSET_RANGE = (-240, 240)
LOGO_MARGIN_RANGE = (0, 120)
LOGO_SIZE_RANGE = (32, 256)


def resolve_logo_position(corner, horizontal_offset, vertical_offset, screen_w, screen_h, logo_w, logo_h, margin):
    """(x, y) top-left position of the logo, clamped inside the screen --
    identical formula to ChannelBugOverlay.paintEvent.
    """
    if "right" in corner:
        x = screen_w - logo_w - margin
    else:
        x = margin
    if "bottom" in corner:
        y = screen_h - logo_h - margin
    else:
        y = margin
    x += horizontal_offset
    y += vertical_offset
    x = max(0, min(x, screen_w - logo_w))
    y = max(0, min(y, screen_h - logo_h))
    return x, y


def scale_logo_dimensions(natural_w, natural_h, size):
    """(w, h) for a logo bounded inside a size x size box, aspect preserved --
    the exact same "fit inside a square, keep proportions" rule
    load_channel_bug_pixmap uses (QPixmap.scaled(size, size, Qt.KeepAspectRatio))
    for real playback, factored out here so any preview that wants to show
    the logo at the same effective size computes the identical box instead
    of stretching the source image to fill a forced square.
    """
    size = max(1, int(size or 1))
    natural_w = max(1, int(natural_w or 1))
    natural_h = max(1, int(natural_h or 1))
    scale = min(size / natural_w, size / natural_h)
    return max(1, round(natural_w * scale)), max(1, round(natural_h * scale))


def resolve_freeform_position(pos_x, pos_y, screen_w, screen_h, logo_w, logo_h):
    """(x, y) top-left position from normalized [0.0, 1.0] coordinates --
    0.0 means the logo's edge is flush with the screen's left/top edge,
    1.0 means flush with the right/bottom edge. Because the fraction is
    applied to the *available room* (screen size minus logo size), the
    result is always inside the screen by construction -- no separate
    clamp needed, unlike the corner+offset scheme this supplements.
    """
    room_w = max(0, screen_w - logo_w)
    room_h = max(0, screen_h - logo_h)
    px = max(0.0, min(1.0, float(pos_x if pos_x is not None else 0.5)))
    py = max(0.0, min(1.0, float(pos_y if pos_y is not None else 0.5)))
    return room_w * px, room_h * py


def position_to_normalized(x, y, screen_w, screen_h, logo_w, logo_h):
    """Inverse of resolve_freeform_position -- a dropped top-left pixel
    position to normalized [0.0, 1.0] coordinates. A screen with no room
    to move in either axis (logo fills the screen) reports the midpoint
    (0.5) rather than dividing by zero.
    """
    room_w = screen_w - logo_w
    room_h = screen_h - logo_h
    pos_x = (x / room_w) if room_w > 0 else 0.5
    pos_y = (y / room_h) if room_h > 0 else 0.5
    return max(0.0, min(1.0, pos_x)), max(0.0, min(1.0, pos_y))


def resolve_effective_logo_position(eff, screen_w, screen_h, logo_w, logo_h):
    """The single position resolver for both the Logo Studio preview and
    real playback (ChannelBugOverlay.paintEvent): freeform normalized
    pos_x/pos_y when a channel has been dragged in the new editor, else
    the legacy corner + margin + offset math (resolve_logo_position) for
    channels that have never been touched by the freeform editor, or
    whose settings predate it -- so old saved settings keep working
    unchanged.
    """
    pos_x = eff.get("pos_x") if isinstance(eff, dict) else None
    pos_y = eff.get("pos_y") if isinstance(eff, dict) else None
    if pos_x is not None and pos_y is not None:
        return resolve_freeform_position(pos_x, pos_y, screen_w, screen_h, logo_w, logo_h)
    return resolve_logo_position(
        eff.get("corner", "bottom-right"),
        int(eff.get("horizontal_offset", 0) or 0),
        int(eff.get("vertical_offset", 0) or 0),
        screen_w, screen_h, logo_w, logo_h,
        int(eff.get("margin", 18) or 18),
    )


def position_to_corner_offsets(x, y, screen_w, screen_h, logo_w, logo_h, margin):
    """Inverse of resolve_logo_position: given a dropped top-left position,
    pick the nearest corner (by which quadrant the logo's center falls in)
    and the horizontal/vertical offset that reproduces that exact position
    from that corner + margin, clamped to the supported offset range.
    """
    cx = x + logo_w / 2.0
    cy = y + logo_h / 2.0
    corner = ("bottom" if cy >= screen_h / 2.0 else "top") + "-" + ("right" if cx >= screen_w / 2.0 else "left")

    lo, hi = LOGO_OFFSET_RANGE
    if "right" in corner:
        h_offset = x - (screen_w - logo_w - margin)
    else:
        h_offset = x - margin
    if "bottom" in corner:
        v_offset = y - (screen_h - logo_h - margin)
    else:
        v_offset = y - margin
    h_offset = int(max(lo, min(hi, round(h_offset))))
    v_offset = int(max(lo, min(hi, round(v_offset))))
    return corner, h_offset, v_offset


def logo_size_to_percent(size):
    """Map a real size in px (LOGO_SIZE_RANGE) to a 0-100 display percent."""
    lo, hi = LOGO_SIZE_RANGE
    size = max(lo, min(hi, int(size or lo)))
    return round((size - lo) / (hi - lo) * 100)


def logo_percent_to_size(percent):
    """Inverse of logo_size_to_percent -- 0-100 display percent to real px."""
    lo, hi = LOGO_SIZE_RANGE
    percent = max(0, min(100, int(percent or 0)))
    return int(round(lo + (hi - lo) * (percent / 100.0)))


def logo_opacity_to_percent(opacity):
    return round(max(0.0, min(1.0, float(opacity or 0.0))) * 100)


def logo_percent_to_opacity(percent):
    percent = max(10, min(100, int(percent or 10)))
    return round(percent / 100.0, 2)


# ── Logo Studio v1: timing presets ───────────────────────────────────────────
#
# Every preset maps to the exact real `timing` sub-dict shape the overlay
# already reads (see ChannelBugOverlay / normalize_timing above) plus,
# for a couple of presets, the sibling top-level `fade` field. Nothing here
# invents a setting the overlay doesn't understand -- "random_interval" is
# the one real extension this pass adds (see pick_periodic_interval_minutes
# and ChannelBugOverlay's periodic-timer handling), and every preset that
# uses it is exercised by tools/test_channel_logos.py.


def _timing_preset(**overrides):
    base = dict(_TIMING_DEFAULTS)
    base.update({
        "always_visible": False,
        "on_channel_tune": False,
        "on_program_start": False,
        "periodic": False,
        "random_interval": False,
    })
    base.update(overrides)
    return normalize_timing(base)


LOGO_TIMING_PRESETS = (
    {
        "id": "always",
        "label": "Always On",
        "description": "The logo stays on screen the whole time, fading in gently when you tune in.",
        "timing": _timing_preset(always_visible=True),
        "fade": True,
    },
    {
        "id": "show_start",
        "label": "Show Start Only",
        "description": "Appears briefly when you tune to this channel, then fades away.",
        "timing": _timing_preset(on_channel_tune=True, duration_seconds=5),
        "fade": None,
    },
    {
        "id": "interval",
        "label": "Fade In Every Few Minutes",
        "description": "Fades in on a fixed schedule, every few minutes.",
        "timing": _timing_preset(on_channel_tune=True, periodic=True, duration_seconds=5, periodic_interval_minutes=10),
        "fade": None,
    },
    {
        "id": "random_pop_in",
        "label": "Random Pop-Ins",
        "description": "Pops in unpredictably every few minutes -- never on a fixed clock.",
        "timing": _timing_preset(
            on_channel_tune=True, periodic=True, random_interval=True,
            duration_seconds=5, interval_min_minutes=3, interval_max_minutes=12,
        ),
        "fade": None,
    },
    {
        "id": "random_short_bumps",
        "label": "Random Short Bumps",
        "description": "Quick, frequent flashes of the logo at randomized short intervals.",
        "timing": _timing_preset(
            on_channel_tune=True, periodic=True, random_interval=True,
            duration_seconds=3, interval_min_minutes=2, interval_max_minutes=6,
        ),
        "fade": None,
    },
    {
        "id": "mostly_hidden",
        "label": "Mostly Hidden",
        "description": "Rarely appears, and only for a moment when it does.",
        "timing": _timing_preset(
            periodic=True, random_interval=True,
            duration_seconds=3, interval_min_minutes=20, interval_max_minutes=45,
        ),
        "fade": None,
    },
    {
        "id": "classic_cable_bug",
        "label": "Classic Cable Bug",
        "description": "Always on, snaps in with no fade -- like an old cable channel bug.",
        "timing": _timing_preset(always_visible=True),
        "fade": False,
    },
    {
        "id": "network_promo",
        "label": "Network Promo Style",
        "description": "Shows at the start of every program, plus periodic reminders.",
        "timing": _timing_preset(on_program_start=True, periodic=True, duration_seconds=4, periodic_interval_minutes=15),
        "fade": None,
    },
    {
        "id": "show_start_plus_random",
        "label": "Per-Show Start + Random Returns",
        "description": "Appears at the start of every show, then returns at random moments in between.",
        "timing": _timing_preset(
            on_program_start=True, periodic=True, random_interval=True,
            duration_seconds=4, interval_min_minutes=8, interval_max_minutes=20,
        ),
        "fade": None,
    },
)

_LOGO_TIMING_PRESETS_BY_ID = {p["id"]: p for p in LOGO_TIMING_PRESETS}

# The Timing dropdown's own, smaller public list -- everything else in
# LOGO_TIMING_PRESETS stays real and stays in the lookup table (so a
# channel already using one of the trimmed presets, or one loaded from
# an older saved settings file, still resolves correctly), it's just
# not offered as a fresh choice. logo_timing_preset_for_settings still
# recognizes a trimmed preset's exact settings -- the dropdown is the
# only thing that treats it as "no dropdown match", which the UI shows
# as "Custom" (an honest description: the trimmed presets are still
# real, specific settings, just not surfaced as a one-click choice).
LOGO_TIMING_PRESETS_DROPDOWN_IDS = ("always", "show_start", "interval", "random_pop_in", "random_short_bumps")


def logo_timing_preset_by_id(preset_id):
    return _LOGO_TIMING_PRESETS_BY_ID.get(preset_id)


def channel_logo_excluded_shows(global_settings, channel_name):
    """The list of show keys this channel's logo is hidden for, regardless
    of its mode (Default/Custom/Off don't affect this list -- Off already
    hides the logo for everything, so exclusions are moot there, but
    Default and Custom both respect it).
    """
    gs = global_settings if isinstance(global_settings, dict) else {}
    overrides = gs.get("channel_overrides") or {}
    override = overrides.get(channel_name) or {}
    return normalize_show_exclusions(override.get("excluded_shows"))


def channel_logo_screen_aspect(global_settings, channel_name):
    """This channel's Logo Studio simulated-screen shape ("16:9"/"4:3") --
    independent of Default/Custom/Off mode, same as excluded_shows above.
    """
    gs = global_settings if isinstance(global_settings, dict) else {}
    overrides = gs.get("channel_overrides") or {}
    override = overrides.get(channel_name) or {}
    return normalize_screen_aspect(override.get("screen_aspect"))


def is_show_excluded(excluded_shows, show_key):
    """False (not excluded) whenever show_key can't be determined -- an
    unresolved show should never accidentally suppress the logo for
    everything else on the channel.
    """
    show_key = str(show_key or "").strip()
    if not show_key:
        return False
    return show_key in (excluded_shows or [])


def logo_should_be_visible(enabled, is_commercial, is_vault, is_excluded_show):
    """The single source of truth for whether the channel bug is even
    ELIGIBLE to show right now -- independent of which timing mode is
    active. A timing mode (always/interval/random/...) only controls
    whether the bug WOULD show when eligible; this gate can only turn
    eligibility OFF, never force it on.
    """
    if not enabled:
        return False
    if is_commercial or is_vault or is_excluded_show:
        return False
    return True


def logo_timing_preset_for_settings(timing, fade):
    """Best-effort reverse lookup: which preset (if any) exactly matches
    the given timing dict + fade flag. Returns None for a hand-tuned
    combination that doesn't match a preset (that's fine -- the UI just
    shows no preset highlighted in that case).
    """
    normalized = normalize_timing(timing)
    for preset in LOGO_TIMING_PRESETS:
        if preset["timing"] != normalized:
            continue
        if preset["fade"] is not None and bool(fade) != preset["fade"]:
            continue
        return preset["id"]
    return None

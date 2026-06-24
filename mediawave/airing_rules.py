"""Airing Rules data model, storage helpers, validation, and diagnostics."""

import hashlib
import json
import os
import re


AIRING_RULES_VERSION = 1
AIRING_RULES_FILE = os.path.join(os.getcwd(), "airing_rules.json")

AIRING_RULE_LEVELS = ("channel", "show", "genre")

AIRING_RULE_BASIC_TYPES = (
    "always_allowed",
    "prefer_daytime",
    "prefer_late_night",
    "prefer_weekends",
    "prefer_weekdays",
    "prefer_movie_block",
    "block_from_channel",
)
AIRING_SEASONAL_PRESETS = (
    "christmas_season",
    "spooky_season",
    "summer",
    "winter",
    "custom_date_range",
)
AIRING_RULE_STRICT_TYPES = (
    "prefer_between_times",
    "only_between_times",
    "blocked_between_times",
    "only_on_dates",
    "blocked_on_dates",
    "only_between_dates",
    "blocked_between_dates",
)
AIRING_RULE_TYPES = AIRING_RULE_BASIC_TYPES + AIRING_SEASONAL_PRESETS + AIRING_RULE_STRICT_TYPES

AIRING_RULE_STRENGTHS = ("hint", "strong_preference", "strict")

AIRING_DAYS_OF_WEEK = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def configure_airing_rules_file(path):
    """Point load/save helpers at the app's writable airing_rules.json path."""
    global AIRING_RULES_FILE
    AIRING_RULES_FILE = path


def load_json_file(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def save_json_file(path, data):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
    except OSError:
        pass


def merge_dict_defaults(data, defaults):
    if not isinstance(defaults, dict):
        return data
    merged = {}
    source = data if isinstance(data, dict) else {}
    for key, default_value in defaults.items():
        current_value = source.get(key)
        if isinstance(default_value, dict):
            merged[key] = merge_dict_defaults(current_value, default_value)
        else:
            merged[key] = current_value if current_value is not None else default_value
    for key, value in source.items():
        if key not in merged:
            merged[key] = value
    return merged


def stable_hash(value):
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def normalize_title(value):
    cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def normalize_airing_rule_strength(value):
    text = str(value or "hint").strip().lower()
    if text not in AIRING_RULE_STRENGTHS:
        return "hint"
    return text


def normalize_airing_rule_type(value):
    text = str(value or "").strip().lower()
    if text not in AIRING_RULE_TYPES:
        return ""
    return text


def normalize_seasonal_preset(value):
    text = str(value or "").strip().lower()
    if text not in AIRING_SEASONAL_PRESETS:
        return ""
    return text


def normalize_days_of_week(value):
    if isinstance(value, str):
        candidates = re.split(r"[,\s]+", value.strip().lower())
    elif isinstance(value, (list, tuple, set)):
        candidates = [str(item).strip().lower() for item in value]
    else:
        candidates = []
    return [day for day in AIRING_DAYS_OF_WEEK if day in candidates]


def normalize_airing_time(value):
    text = str(value or "").strip()
    match = re.match(r"^([0-2]?\d):([0-5]\d)$", text)
    if not match:
        return ""
    hour = int(match.group(1))
    if hour > 23:
        return ""
    return f"{hour:02d}:{match.group(2)}"


def normalize_airing_date(value):
    text = str(value or "").strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if not match:
        return ""
    month, day = int(match.group(2)), int(match.group(3))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return ""
    return text


def airing_rule_target_defaults():
    return {
        "channel_id": "",
        "title": "",
        "title_key": "",
        "genre": "",
        "catalog_item_id": "",
    }


def normalize_airing_rule_target(value):
    merged = merge_dict_defaults(value if isinstance(value, dict) else {}, airing_rule_target_defaults())
    title = str(merged.get("title", "") or "").strip()
    title_key = str(merged.get("title_key", "") or "").strip()
    merged["title"] = title
    merged["title_key"] = title_key or (normalize_title(title) if title else "")
    merged["channel_id"] = str(merged.get("channel_id", "") or "").strip()
    merged["genre"] = str(merged.get("genre", "") or "").strip()
    merged["catalog_item_id"] = str(merged.get("catalog_item_id", "") or "").strip()
    return merged


def airing_rule_defaults():
    return {
        "id": "",
        "level": "channel",
        "enabled": True,
        "rule_type": "always_allowed",
        "rule_strength": "hint",
        "target": airing_rule_target_defaults(),
        "start_time": "",
        "end_time": "",
        "only_on_dates": [],
        "blocked_on_dates": [],
        "start_date": "",
        "end_date": "",
        "seasonal_preset": "",
        "notes": "",
    }


def normalize_airing_rule(value):
    merged = merge_dict_defaults(value if isinstance(value, dict) else {}, airing_rule_defaults())
    level = str(merged.get("level", "channel") or "channel").strip().lower()
    merged["level"] = level if level in AIRING_RULE_LEVELS else "channel"
    merged["enabled"] = bool(merged.get("enabled", True))
    # Preserve unknown rule_type values as-is for forward compatibility with future versions.
    # Only fall back to "always_allowed" if the field is empty or missing.
    raw_rule_type = str(merged.get("rule_type", "") or "").strip().lower()
    known_type = normalize_airing_rule_type(raw_rule_type)
    merged["rule_type"] = known_type if known_type else (raw_rule_type or "always_allowed")
    merged["rule_strength"] = normalize_airing_rule_strength(merged.get("rule_strength"))
    merged["target"] = normalize_airing_rule_target(merged.get("target"))
    merged["start_time"] = normalize_airing_time(merged.get("start_time"))
    merged["end_time"] = normalize_airing_time(merged.get("end_time"))
    merged["start_date"] = normalize_airing_date(merged.get("start_date"))
    merged["end_date"] = normalize_airing_date(merged.get("end_date"))
    merged["seasonal_preset"] = normalize_seasonal_preset(merged.get("seasonal_preset"))
    only_dates = merged.get("only_on_dates")
    blocked_dates = merged.get("blocked_on_dates")
    merged["only_on_dates"] = [d for d in (normalize_airing_date(x) for x in (only_dates if isinstance(only_dates, list) else [])) if d]
    merged["blocked_on_dates"] = [d for d in (normalize_airing_date(x) for x in (blocked_dates if isinstance(blocked_dates, list) else [])) if d]
    merged["notes"] = str(merged.get("notes", "") or "").strip()
    if not merged.get("id"):
        merged["id"] = stable_hash(json.dumps(merged, sort_keys=True, default=str))
    return merged


def channel_takeover_defaults():
    return {
        "id": "",
        "enabled": False,
        "takeover_name": "",
        "source_channel_id": "",
        "display_channel_name": "",
        "display_logo_path": "",
        "display_channel_bug_path": "",
        "start_time": "",
        "end_time": "",
        "days_of_week": [],
        "start_date": "",
        "end_date": "",
        "seasonal_preset": "",
        "optional_bumper_path": "",
        "optional_station_id_path": "",
        "rule_strength": "hint",
        "notes": "",
    }


def normalize_channel_takeover(value):
    merged = merge_dict_defaults(value if isinstance(value, dict) else {}, channel_takeover_defaults())
    merged["enabled"] = bool(merged.get("enabled", False))
    merged["takeover_name"] = str(merged.get("takeover_name", "") or "").strip()
    merged["source_channel_id"] = str(merged.get("source_channel_id", "") or "").strip()
    merged["display_channel_name"] = str(merged.get("display_channel_name", "") or "").strip()
    merged["display_logo_path"] = str(merged.get("display_logo_path", "") or "").strip()
    merged["display_channel_bug_path"] = str(merged.get("display_channel_bug_path", "") or "").strip()
    merged["start_time"] = normalize_airing_time(merged.get("start_time"))
    merged["end_time"] = normalize_airing_time(merged.get("end_time"))
    merged["days_of_week"] = normalize_days_of_week(merged.get("days_of_week"))
    merged["start_date"] = normalize_airing_date(merged.get("start_date"))
    merged["end_date"] = normalize_airing_date(merged.get("end_date"))
    merged["seasonal_preset"] = normalize_seasonal_preset(merged.get("seasonal_preset"))
    merged["optional_bumper_path"] = str(merged.get("optional_bumper_path", "") or "").strip()
    merged["optional_station_id_path"] = str(merged.get("optional_station_id_path", "") or "").strip()
    merged["rule_strength"] = normalize_airing_rule_strength(merged.get("rule_strength"))
    merged["notes"] = str(merged.get("notes", "") or "").strip()
    if not merged.get("id"):
        merged["id"] = stable_hash(json.dumps(merged, sort_keys=True, default=str))
    return merged


def airing_rules_config_defaults():
    return {
        "airing_rules_version": AIRING_RULES_VERSION,
        "channel_rules": [],
        "show_rules": [],
        "genre_rules": [],
        "channel_takeovers": [],
    }


def _normalize_airing_rule_list(raw, level):
    items = raw if isinstance(raw, list) else []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rule = normalize_airing_rule(item)
        rule["level"] = level
        result.append(rule)
    return result


def normalize_airing_rules_config(data):
    merged = merge_dict_defaults(data if isinstance(data, dict) else {}, airing_rules_config_defaults())
    merged["airing_rules_version"] = AIRING_RULES_VERSION
    merged["channel_rules"] = _normalize_airing_rule_list(merged.get("channel_rules"), "channel")
    merged["show_rules"] = _normalize_airing_rule_list(merged.get("show_rules"), "show")
    merged["genre_rules"] = _normalize_airing_rule_list(merged.get("genre_rules"), "genre")
    takeovers = merged.get("channel_takeovers")
    merged["channel_takeovers"] = [
        normalize_channel_takeover(item)
        for item in (takeovers if isinstance(takeovers, list) else [])
        if isinstance(item, dict)
    ]
    return merged


def load_airing_rules_config():
    return normalize_airing_rules_config(load_json_file(AIRING_RULES_FILE, airing_rules_config_defaults()))


def save_airing_rules_config(config):
    save_json_file(AIRING_RULES_FILE, config)


def validate_airing_rules_config(config, known_channel_ids=None, known_title_keys=None):
    """Returns a list of human-readable warning strings. Never raises."""
    warnings = []
    if not isinstance(config, dict):
        return ["airing rules config is not a dict; defaults will be used"]
    known_channel_ids = set(known_channel_ids) if known_channel_ids is not None else None
    known_title_keys = set(known_title_keys) if known_title_keys is not None else None

    def check_time_range(label, start, end):
        if start and end and start == end:
            warnings.append(f"{label}: start_time and end_time are identical ({start})")

    def check_date_range(label, start, end):
        if start and end and start > end:
            warnings.append(f"{label}: start_date {start} is after end_date {end}")

    def check_target(label, target):
        target = target if isinstance(target, dict) else {}
        channel_id = target.get("channel_id")
        if channel_id and known_channel_ids is not None and channel_id not in known_channel_ids:
            warnings.append(f"{label}: references unknown channel_id '{channel_id}'")
        title_key = target.get("title_key")
        if title_key and known_title_keys is not None and title_key not in known_title_keys:
            warnings.append(f"{label}: references missing/stale show title_key '{title_key}'")

    strict_channel_blocks = {}
    for level_key in ("channel_rules", "show_rules", "genre_rules"):
        for rule in config.get(level_key, []) or []:
            if not isinstance(rule, dict):
                continue
            label = f"{level_key}[{rule.get('id', '?')}]"
            rule_type = rule.get("rule_type")
            check_target(label, rule.get("target"))
            check_time_range(label, rule.get("start_time"), rule.get("end_time"))
            check_date_range(label, rule.get("start_date"), rule.get("end_date"))
            if rule_type == "custom_date_range" and not (rule.get("start_date") and rule.get("end_date")):
                warnings.append(f"{label}: custom_date_range rule is missing start_date/end_date")
            if rule_type in ("prefer_between_times", "only_between_times", "blocked_between_times") and not (rule.get("start_time") and rule.get("end_time")):
                warnings.append(f"{label}: {rule_type} rule is missing start_time/end_time")
            if rule_type in ("only_between_dates", "blocked_between_dates") and not (rule.get("start_date") and rule.get("end_date")):
                warnings.append(f"{label}: {rule_type} rule is missing start_date/end_date")
            if rule_type == "only_on_dates" and not rule.get("only_on_dates"):
                warnings.append(f"{label}: only_on_dates rule has no dates configured")
            if rule_type == "blocked_on_dates" and not rule.get("blocked_on_dates"):
                warnings.append(f"{label}: blocked_on_dates rule has no dates configured")
            if rule.get("enabled") and rule.get("rule_strength") == "strict" and rule_type == "block_from_channel":
                channel_id = (rule.get("target") or {}).get("channel_id")
                strict_channel_blocks.setdefault(channel_id, []).append(label)

    for channel_id, labels in strict_channel_blocks.items():
        if len(labels) > 1:
            warnings.append(f"conflicting strict block_from_channel rules for channel '{channel_id}': {', '.join(labels)}")

    strict_takeovers_by_channel = {}
    for takeover in config.get("channel_takeovers", []) or []:
        if not isinstance(takeover, dict):
            continue
        label = f"channel_takeover[{takeover.get('takeover_name') or takeover.get('id', '?')}]"
        source_channel_id = takeover.get("source_channel_id")
        if not source_channel_id:
            warnings.append(f"{label}: missing source_channel_id")
        elif known_channel_ids is not None and source_channel_id not in known_channel_ids:
            warnings.append(f"{label}: references unknown source_channel_id '{source_channel_id}'")
        for path_field in ("display_logo_path", "display_channel_bug_path", "optional_bumper_path", "optional_station_id_path"):
            path_value = takeover.get(path_field)
            if path_value and not os.path.exists(path_value):
                warnings.append(f"{label}: {path_field} not found: {path_value}")
        check_time_range(label, takeover.get("start_time"), takeover.get("end_time"))
        check_date_range(label, takeover.get("start_date"), takeover.get("end_date"))
        seasonal_preset = takeover.get("seasonal_preset")
        if seasonal_preset and seasonal_preset not in AIRING_SEASONAL_PRESETS:
            warnings.append(f"{label}: unknown seasonal_preset '{seasonal_preset}'")
        if takeover.get("enabled") and takeover.get("rule_strength") == "strict" and source_channel_id:
            strict_takeovers_by_channel.setdefault(source_channel_id, []).append(takeover.get("takeover_name") or takeover.get("id"))

    for channel_id, names in strict_takeovers_by_channel.items():
        if len(names) > 1:
            warnings.append(f"conflicting strict Channel Takeovers on channel '{channel_id}': {', '.join(str(n) for n in names)}")

    return warnings


def airing_rules_diagnostics(config, known_channel_ids=None, known_title_keys=None, log=True):
    """Developer-facing summary of the Airing Rules config. Never raises."""
    config = config if isinstance(config, dict) else airing_rules_config_defaults()
    warnings = validate_airing_rules_config(config, known_channel_ids, known_title_keys)
    summary = {
        "airing_rules_version": config.get("airing_rules_version", AIRING_RULES_VERSION),
        "channel_rule_count": len(config.get("channel_rules", []) or []),
        "show_rule_count": len(config.get("show_rules", []) or []),
        "genre_rule_count": len(config.get("genre_rules", []) or []),
        "channel_takeover_count": len(config.get("channel_takeovers", []) or []),
        "warnings": warnings,
    }
    if log:
        print(
            "[AiringRules] v{v} | channel_rules={cr} show_rules={sr} genre_rules={gr} "
            "channel_takeovers={ct} warnings={wc}".format(
                v=summary["airing_rules_version"],
                cr=summary["channel_rule_count"],
                sr=summary["show_rule_count"],
                gr=summary["genre_rule_count"],
                ct=summary["channel_takeover_count"],
                wc=len(warnings),
            ),
            flush=True,
        )
        for warning in warnings:
            print(f"[AiringRules][warn] {warning}", flush=True)
    return summary


CHANNEL_RULE_PRESETS = [
    ("Late Night Block", "prefer_late_night"),
    ("Weekend Block", "prefer_weekends"),
    ("Christmas Season", "christmas_season"),
    ("Spooky Season", "spooky_season"),
    ("Summer Season", "summer"),
    ("Winter Season", "winter"),
    ("Movie Night", "prefer_movie_block"),
    ("Block From Channel", "block_from_channel"),
]

SHOW_AIRING_PRESETS = [
    ("Normal", ""),
    ("Prefer Daytime", "prefer_daytime"),
    ("Prefer Late Night", "prefer_late_night"),
    ("Christmas Season", "christmas_season"),
    ("Spooky Season", "spooky_season"),
    ("Weekends Only", "prefer_weekends"),
    ("Block From This Channel", "block_from_channel"),
]

GENRE_AIRING_PRESETS = [
    ("Normal", ""),
    ("Prefer Daytime", "prefer_daytime"),
    ("Prefer Late Night", "prefer_late_night"),
    ("Weekends", "prefer_weekends"),
    ("Christmas Season", "christmas_season"),
    ("Spooky Season", "spooky_season"),
]


def _fmt_time_ampm(hhmm):
    """Convert '22:30' to '10:30 PM', or return hhmm unchanged."""
    if not hhmm:
        return hhmm
    try:
        hour, minute = int(hhmm[:2]), int(hhmm[3:5])
        suffix = "AM" if hour < 12 else "PM"
        display_hour = hour % 12 or 12
        return f"{display_hour}:{minute:02d} {suffix}"
    except (ValueError, IndexError):
        return hhmm


def airing_rule_summary(rule, channel_name=""):
    """Return a plain-English one-line description of a rule dict."""
    if not isinstance(rule, dict):
        return "Unknown rule"
    rule_type = rule.get("rule_type", "always_allowed")
    enabled = rule.get("enabled", True)
    prefix = "" if enabled else "[disabled] "
    t_start = _fmt_time_ampm(rule.get("start_time") or "")
    t_end = _fmt_time_ampm(rule.get("end_time") or "")
    d_start = rule.get("start_date") or ""
    d_end = rule.get("end_date") or ""
    _type_map = {
        "always_allowed": "Always allowed to air",
        "prefer_daytime": "Prefer daytime scheduling",
        "prefer_late_night": "Prefer late night scheduling",
        "prefer_weekends": "Prefer weekends",
        "prefer_weekdays": "Prefer weekdays",
        "prefer_movie_block": "Prefer movie block scheduling",
        "block_from_channel": f"Blocked from {channel_name or 'this channel'}",
        "christmas_season": "Christmas season only",
        "spooky_season": "Spooky season only (Oct–Nov)",
        "summer": "Summer only",
        "winter": "Winter only",
        "custom_date_range": f"Date range {d_start} – {d_end}" if d_start or d_end else "Custom date range",
        "prefer_between_times": f"Prefer airing between {t_start} – {t_end}" if t_start or t_end else "Prefer a time window",
        "only_between_times": f"Only between {t_start} – {t_end}" if t_start or t_end else "Only between set times",
        "blocked_between_times": f"Blocked between {t_start} – {t_end}" if t_start or t_end else "Blocked between set times",
        "only_on_dates": "Only on specific dates",
        "blocked_on_dates": "Blocked on specific dates",
        "only_between_dates": f"Only between {d_start} – {d_end}" if d_start or d_end else "Only between set dates",
        "blocked_between_dates": f"Blocked between {d_start} – {d_end}" if d_start or d_end else "Blocked between set dates",
    }
    base = _type_map.get(rule_type, f"Rule: {rule_type}")
    strength = rule.get("rule_strength", "hint")
    if strength == "strict":
        base += " (strict)"
    elif strength == "strong_preference":
        base += " (strong)"
    return prefix + base


def channel_takeover_summary(takeover):
    """Return a plain-English one-line description of a Channel Takeover dict."""
    if not isinstance(takeover, dict):
        return "Unknown takeover"
    name = takeover.get("takeover_name") or takeover.get("display_channel_name") or "Unnamed Takeover"
    start = _fmt_time_ampm(takeover.get("start_time") or "")
    end = _fmt_time_ampm(takeover.get("end_time") or "")
    enabled = takeover.get("enabled", False)
    prefix = "" if enabled else "[disabled] "
    time_part = f" from {start} to {end}" if start or end else ""
    days = takeover.get("days_of_week") or []
    days_part = f" on {', '.join(d.capitalize() for d in days)}" if days else ""
    seasonal = takeover.get("seasonal_preset") or ""
    seasonal_part = f" ({seasonal.replace('_', ' ')})" if seasonal else ""
    return f"{prefix}{name}{time_part}{days_part}{seasonal_part}"

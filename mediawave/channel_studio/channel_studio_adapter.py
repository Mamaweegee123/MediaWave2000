"""Read-only adapter: turns existing app data into Channel Studio summaries.

This module never touches the filesystem and never writes settings. It
takes data the main app has already gathered — catalog channel infos,
per-channel show lists (from the existing `gather_channel_shows` helper),
commercial config, airing rules config, and optionally the live `Channel`
objects for schedule preview — and shapes it into the small, friendly
dataclasses in `channel_studio_model.py`.

Extraction note: channel-list building, folder scanning, logo lookup, and
commercial-profile resolution all live in channelsurfer2000.py today.
Importing them directly here would create a circular import (that module
lazily imports this package), so callers pass the already-computed
values in. TODO: once channelsurfer2000.py is split into smaller
modules, move those helpers under mediawave/ and import them directly
instead of threading the values through call sites.
"""

import time

from mediawave.scheduling import CATALOG_PLAYBACK_ORDER_LABELS, CATALOG_PLAYBACK_ORDER_RANDOM

from .channel_studio_model import ChannelStudioSummary, ScheduleSlot, TonightSchedule


def _content_counts(shows):
    if not shows:
        return 0, 0, False
    show_count = 0
    movie_count = 0
    for item in shows:
        media_type = (item or {}).get("media_type", "tv") if isinstance(item, dict) else "tv"
        if media_type == "movie":
            movie_count += 1
        else:
            show_count += 1
    return show_count, movie_count, True


def _resolve_commercial_status(channel_name, commercials_config):
    config = commercials_config if isinstance(commercials_config, dict) else {}
    global_enabled = bool(config.get("enabled", False))
    global_mode = str(config.get("mode", "off") or "off")
    overrides = config.get("channel_overrides", {})
    override = overrides.get(channel_name, {}) if isinstance(overrides, dict) else {}
    override = override if isinstance(override, dict) else {}
    enabled_mode = str(override.get("enabled_mode", "inherit") or "inherit")
    if enabled_mode == "on":
        enabled = True
    elif enabled_mode == "off":
        enabled = False
    else:
        enabled = global_enabled
    mode = str(override.get("mode", global_mode) or global_mode) if enabled else "off"
    return enabled, mode


def _count_airing_rules(channel_id, airing_rules_config):
    config = airing_rules_config if isinstance(airing_rules_config, dict) else {}
    channel_rules = config.get("channel_rules", []) or []
    return sum(
        1
        for rule in channel_rules
        if isinstance(rule, dict) and (rule.get("target") or {}).get("channel_id") == channel_id
    )


def _count_seasonal_rules(channel_id, airing_rules_config):
    config = airing_rules_config if isinstance(airing_rules_config, dict) else {}
    takeovers = config.get("channel_takeovers", []) or []
    return sum(
        1
        for takeover in takeovers
        if isinstance(takeover, dict)
        and takeover.get("source_channel_id") == channel_id
        and takeover.get("seasonal_preset")
    )


def build_channel_studio_summary(
    info,
    shows=None,
    catalog_channel_settings=None,
    commercials_config=None,
    airing_rules_config=None,
    logo_path="",
):
    """Build a single read-only ChannelStudioSummary. Never raises."""
    info = info if isinstance(info, dict) else {}
    channel_id = str(info.get("id", "") or "")
    name = str(info.get("name", "Channel") or "Channel")
    channel_type = str(info.get("channel_type", "media") or "media")
    root_path = str(info.get("root_path", "") or "")
    number = info.get("default_number", 0)
    try:
        number = int(number or 0)
    except (TypeError, ValueError):
        number = 0

    show_count, movie_count, content_known = _content_counts(shows)

    settings_row = {}
    if isinstance(catalog_channel_settings, dict):
        settings_row = catalog_channel_settings.get(channel_id, {}) or {}
    playback_order = str(settings_row.get("playback_order", CATALOG_PLAYBACK_ORDER_RANDOM) or CATALOG_PLAYBACK_ORDER_RANDOM)
    playback_order_label = CATALOG_PLAYBACK_ORDER_LABELS.get(playback_order, "Random")

    commercials_enabled, commercial_mode = _resolve_commercial_status(name, commercials_config)
    commercials_label = "Commercials on" if commercials_enabled else "Commercials off"

    return ChannelStudioSummary(
        channel_id=channel_id,
        name=name,
        number=number,
        channel_type=channel_type,
        root_path=root_path,
        logo_path=str(logo_path or ""),
        show_count=show_count,
        movie_count=movie_count,
        content_known=content_known,
        playback_order_label=playback_order_label,
        commercials_enabled=commercials_enabled,
        commercials_label=commercials_label,
        airing_rule_count=_count_airing_rules(channel_id, airing_rules_config),
        seasonal_rule_count=_count_seasonal_rules(channel_id, airing_rules_config),
    )


def build_channel_studio_summaries(
    channel_infos,
    shows_lookup=None,
    catalog_channel_settings=None,
    commercials_config=None,
    airing_rules_config=None,
    logo_lookup=None,
):
    """Build one summary per channel info, preserving input order. Never raises."""
    shows_lookup = shows_lookup if isinstance(shows_lookup, dict) else {}
    logo_lookup = logo_lookup if isinstance(logo_lookup, dict) else {}
    summaries = []
    for info in channel_infos or []:
        channel_id = (info or {}).get("id", "")
        summaries.append(
            build_channel_studio_summary(
                info,
                shows=shows_lookup.get(channel_id),
                catalog_channel_settings=catalog_channel_settings,
                commercials_config=commercials_config,
                airing_rules_config=airing_rules_config,
                logo_path=logo_lookup.get(channel_id, ""),
            )
        )
    return summaries


def _tonight_start_epoch(start_hour=18):
    now = time.localtime()
    tonight = time.struct_time(
        (now.tm_year, now.tm_mon, now.tm_mday, start_hour, 0, 0, now.tm_wday, now.tm_yday, now.tm_isdst)
    )
    return time.mktime(tonight)


def _format_slot_time(epoch_seconds):
    try:
        return time.strftime("%-I:%M %p", time.localtime(epoch_seconds))
    except Exception:
        return time.strftime("%I:%M %p", time.localtime(epoch_seconds)).lstrip("0")


def build_tonight_schedule(channel_info, channel=None, slot_count=6, start_hour=18):
    """Build a read-only tonight's-lineup preview for one channel.

    Uses the channel's existing schedule engine (`get_programs_for_window`)
    when a live Channel object is available. No new scheduling engine —
    this simply reads whatever the channel is already set to play tonight.
    Returns a TonightSchedule with has_data=False (never raises) when no
    live schedule can be read, so the UI can show a friendly empty state.
    """
    info = channel_info if isinstance(channel_info, dict) else {}
    channel_id = str(info.get("id", "") or "")
    name = str(info.get("name", "Channel") or "Channel")

    if channel is None or not hasattr(channel, "get_programs_for_window"):
        return TonightSchedule(channel_id=channel_id, channel_name=name, slots=[], has_data=False)

    try:
        window_start = _tonight_start_epoch(start_hour)
        programs = channel.get_programs_for_window(window_start, count=slot_count)
    except Exception:
        programs = []

    if not programs:
        return TonightSchedule(channel_id=channel_id, channel_name=name, slots=[], has_data=False)

    slots = []
    for program in programs:
        try:
            time_label = _format_slot_time(program.get("start"))
            title = program.get("title") or "Untitled"
        except Exception:
            continue
        slots.append(ScheduleSlot(time_label=time_label, title=title))

    if not slots:
        return TonightSchedule(channel_id=channel_id, channel_name=name, slots=[], has_data=False)

    return TonightSchedule(channel_id=channel_id, channel_name=name, slots=slots, has_data=True)


def build_tonight_schedules(channel_infos, channels_by_id=None, slot_count=6, start_hour=18):
    """Build tonight's-lineup previews for every channel info. Never raises."""
    channels_by_id = channels_by_id if isinstance(channels_by_id, dict) else {}
    schedules = []
    for info in channel_infos or []:
        channel_id = (info or {}).get("id", "")
        schedules.append(
            build_tonight_schedule(
                info,
                channel=channels_by_id.get(channel_id),
                slot_count=slot_count,
                start_hour=start_hour,
            )
        )
    return schedules

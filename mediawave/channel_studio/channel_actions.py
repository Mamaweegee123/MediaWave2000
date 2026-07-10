"""Bridge between Channel Studio and the real settings widgets that live
on `AdvancedConfigDialog` (channelsurfer2000.py).

Channel Studio is one more tab inside the same `AdvancedConfigDialog`
instance as the Companion Channels and My Catalog tabs -- so the
widgets those tabs read/write (`dialog.weatherstar_enabled`,
`dialog.catalog_rows`, `dialog.channel_commercial_overrides`, ...) are
the SAME objects Channel Studio can reach through `dialog`. Reading or
writing them here changes what those other tabs show too, live, in
the same dialog session -- no separate "sync" step is needed for that
part. What this module does NOT do is trigger the dialog's real
Save/persist/rebuild pipeline (`open_advanced_configuration` in
channelsurfer2000.py): that pipeline does expensive, one-shot-per-Save
work (stopping/restarting the RadioWave background thread, refetching
the NetTV playlist cache, preloading weather, rebuilding the on-demand
catalog, ...) that would be wrong to fire on every checkbox click.
Real disk persistence and the live channel-lineup rebuild still only
happen when the user clicks the dialog's own Save button, same as
today for every other tab -- Channel Studio just needs to be honest
about that (see channel_studio_pages.py's unsaved-changes note).

Every function here takes `dialog` (or a channel_id) as a plain
argument rather than being a method on the dialog class itself, so it
stays out of the already enormous AdvancedConfigDialog and is testable
against a lightweight stand-in object (see tools/test_channel_studio.py)
that only needs to duck-type the handful of attributes actually used.
"""

from .companion_adapter import (
    COMPANION_TYPES,
    read_companion_snapshot,
    resequence_companion_numbers,
)

_COMPANION_ENABLED_ATTR = {
    "weatherstar": "weatherstar_enabled",
    "radiowave": "radiowave_enabled",
    "youtube": "youtube_enabled",
}
_COMPANION_NUMBER_ATTR = {
    "weatherstar": "weatherstar_channel_input",
    "radiowave": "radiowave_channel_input",
    "youtube": "youtube_channel_input",
}
_COMPANION_DETAIL_ATTR = {
    "weatherstar": "weatherstar_location_input",
    "radiowave": "radiowave_input",
    "youtube": "youtube_playlist_input",
}


def _widget(dialog, attr_name):
    return getattr(dialog, attr_name, None)


def companion_snapshot_from_dialog(dialog):
    """Read the three companion widgets' current live state off `dialog`
    into the raw settings-shaped dict `companion_adapter.
    read_companion_snapshot` expects. Missing widgets (dialog not fully
    built yet) are treated as "disabled" rather than raising.
    """
    raw = {}
    for companion_type in COMPANION_TYPES:
        enabled_box = _widget(dialog, _COMPANION_ENABLED_ATTR[companion_type])
        number_spin = _widget(dialog, _COMPANION_NUMBER_ATTR[companion_type])
        detail_input = _widget(dialog, _COMPANION_DETAIL_ATTR[companion_type])
        raw[f"{companion_type}_enabled"] = bool(enabled_box.isChecked()) if enabled_box is not None else False
        raw[f"{companion_type}_channel_number"] = number_spin.value() if number_spin is not None else 1
        raw[f"{companion_type}_detail_field"] = detail_input.text().strip() if detail_input is not None else ""
    # read_companion_snapshot reads type-specific field names (weatherstar_location,
    # radiowave_folder, youtube_playlist_url) -- map the generic one above onto them.
    raw["weatherstar_location"] = raw.pop("weatherstar_detail_field", "")
    raw["radiowave_folder"] = raw.pop("radiowave_detail_field", "")
    raw["youtube_playlist_url"] = raw.pop("youtube_detail_field", "")
    return read_companion_snapshot(raw)


def apply_companion_entry_to_dialog(dialog, companion_type, entry):
    """Write one companion's `enabled`/`number` back onto the live
    Companion Channels tab widgets. Never touches the detail field
    (location/folder/playlist URL) -- editing those stays in the
    Companion Channels tab, out of scope for this pass. Safe no-op if
    the widgets aren't present or `companion_type` is unknown.
    """
    if companion_type not in COMPANION_TYPES or not isinstance(entry, dict):
        return False
    enabled_box = _widget(dialog, _COMPANION_ENABLED_ATTR[companion_type])
    number_spin = _widget(dialog, _COMPANION_NUMBER_ATTR[companion_type])
    if enabled_box is None or number_spin is None:
        return False
    if "enabled" in entry:
        enabled_box.setChecked(bool(entry["enabled"]))
    if "number" in entry:
        number_spin.setValue(int(entry["number"] or 1))
    return True


def set_companion_enabled_on_dialog(dialog, companion_type, enabled):
    """Real enable/disable for a companion channel: flips the live
    checkbox that the Companion Channels tab itself uses (the primary
    gate that decides whether the channel is injected into the live
    lineup at all -- see inject_special_channels in channelsurfer2000.py).
    Returns True if a matching widget was found and updated.
    """
    return apply_companion_entry_to_dialog(dialog, companion_type, {"enabled": enabled})


def resequence_companions_on_dialog(dialog, ordered_types):
    """After a Channel Studio drag-drop reorder among companion cards,
    recompute and write back each affected companion's real channel
    number. Local folder channel numbering is never touched by this --
    see companion_adapter.resequence_companion_numbers.
    """
    snapshot = companion_snapshot_from_dialog(dialog)
    resequenced = resequence_companion_numbers(snapshot, ordered_types)
    for companion_type in ordered_types or []:
        if companion_type in COMPANION_TYPES:
            apply_companion_entry_to_dialog(dialog, companion_type, resequenced.get(companion_type, {}))
    return resequenced


def companion_status_from_dialog(dialog):
    """Best-effort live status strings for enabled companions, read from
    whatever real Channel objects the dialog already has on hand
    (`dialog._studio_channels_by_id`, populated in
    channelsurfer2000.py's open_advanced_configuration -- see
    companion_adapter.companion_summaries for how these fall back to
    the configured location/folder/playlist when a channel hasn't been
    built yet this session). Never raises; missing data just means an
    absent entry for that type, so callers fall back to the configured
    detail instead of showing an error.
    """
    channels_by_id = getattr(dialog, "_studio_channels_by_id", None)
    if not isinstance(channels_by_id, dict):
        return {}
    status = {}
    weatherstar = channels_by_id.get("special:weatherstar")
    if weatherstar is not None:
        location = getattr(weatherstar, "location", "") or ""
        status["weatherstar"] = f"Live forecast for {location}" if location else "Live forecast ready"
    radiowave = channels_by_id.get("special:radiowave")
    if radiowave is not None:
        if getattr(radiowave, "empty_state", False):
            status["radiowave"] = getattr(radiowave, "empty_reason", "") or "No playable tracks found"
        else:
            track_count = len(getattr(radiowave, "shows", []) or [])
            status["radiowave"] = f"{track_count} track" + ("s" if track_count != 1 else "") + " loaded"
    youtube = channels_by_id.get("special:youtube")
    if youtube is not None:
        entries = [e for e in (getattr(youtube, "entries", None) or []) if not e.get("placeholder")]
        status["youtube"] = f"{len(entries)} video" + ("s" if len(entries) != 1 else "") + " loaded" if entries else "Loading playlist..."
    return status


def local_channel_row(dialog, channel_id):
    """The My Catalog row dict for `channel_id`, or None. Rows carry the
    real, persisted `enabled`/`number` widgets (see
    AdvancedConfigDialog.add_catalog_row/collect_catalog_channel_settings
    in channelsurfer2000.py) -- the same ones My Catalog itself edits.
    """
    for row in getattr(dialog, "catalog_rows", None) or []:
        if row.get("id") == channel_id:
            return row
    return None


def local_channel_enabled_from_dialog(dialog, channel_id):
    """Current live enabled state for a local folder channel, or None
    if no matching My Catalog row exists (shouldn't normally happen --
    every catalog_channel_infos entry gets a row -- but stays a safe
    lookup rather than raising).
    """
    row = local_channel_row(dialog, channel_id)
    if row is None:
        return None
    return bool(row["enabled"].isChecked())


def set_local_channel_enabled(dialog, channel_id, enabled):
    """Real enable/disable for a local folder channel: flips the same
    checkbox My Catalog's own row uses. Returns True if a row was found
    and updated, False otherwise (safe no-op -- never raises).
    """
    row = local_channel_row(dialog, channel_id)
    if row is None:
        return False
    row["enabled"].setChecked(bool(enabled))
    return True


def open_commercial_overrides_for_channel(dialog, channel_name):
    """Open the existing Channel Commercial Overrides dialog, preselected
    to `channel_name` -- reused as-is, not reimplemented (see the
    `initial_channel_name` param added to
    AdvancedConfigDialog.open_channel_overrides_dialog).
    """
    opener = getattr(dialog, "open_channel_overrides_dialog", None)
    if opener is not None:
        opener(initial_channel_name=channel_name)


def open_logo_overrides_for_channel(dialog, channel_name):
    """Open the existing per-channel logo display-override dialog,
    preselected to `channel_name`. This customizes corner/opacity/size/
    timing for the channel's bug -- not the logo image file itself,
    which is always auto-discovered from the channel's own Logos folder
    (see channel_card._find_channel_logo_path).
    """
    opener = getattr(dialog, "_open_channel_logo_overrides", None)
    if opener is not None:
        opener(initial_channel_name=channel_name)


def channel_commercial_override_mode(dialog, channel_name):
    """The current enabled_mode ("inherit"/"on"/"off") for one channel's
    commercial override, or "inherit" if no override has been set yet.
    """
    overrides = getattr(dialog, "channel_commercial_overrides", None) or {}
    override = overrides.get(channel_name) or {}
    return str(override.get("enabled_mode", "inherit") or "inherit")


def set_channel_commercial_override_mode(dialog, channel_name, enabled_mode):
    """Set just the enabled_mode field of one channel's commercial
    override in place, leaving every other override field (era,
    category, density, ad counts, ...) untouched -- creates a bare
    override entry if the channel didn't have one yet. Mirrors exactly
    what `channel_commercial_overrides` already holds after using the
    existing Channel Commercial Overrides dialog (see
    CommercialOverridesDialog.save_current_override in
    channelsurfer2000.py) -- picked up by the real save the same way,
    at the dialog's final values()/Save.
    """
    if enabled_mode not in ("inherit", "on", "off"):
        return
    overrides = getattr(dialog, "channel_commercial_overrides", None)
    if overrides is None:
        return
    override = dict(overrides.get(channel_name) or {})
    override["enabled_mode"] = enabled_mode
    overrides[channel_name] = override


def commercials_summary_label(dialog, channel_name):
    """A short "Default" / "Off" / "Custom" label for Setup's Overview
    section -- Default when the channel has no override (or an
    inherit-mode override with nothing else customized), Off when
    enabled_mode is explicitly "off", Custom for anything else
    (enabled_mode "on", or an inherit override that also customizes
    other fields like era/density).
    """
    overrides = getattr(dialog, "channel_commercial_overrides", None) or {}
    override = overrides.get(channel_name) or {}
    if not override:
        return "Default"
    mode = str(override.get("enabled_mode", "inherit") or "inherit")
    if mode == "off":
        return "Off"
    if mode == "on":
        return "Custom"
    extra_keys = set(override.keys()) - {"enabled_mode"}
    truthy_extra = any(override.get(key) for key in extra_keys)
    return "Custom" if truthy_extra else "Default"


def card_commercials_status(dialog, channel_name):
    """The short, lowercase line a Channel Studio card shows for
    commercial status -- same three states as commercials_summary_label,
    just card-length phrasing ("shared commercials" instead of
    "Default", to match the card's existing "N shows · commercials off"
    style headline text).
    """
    label = commercials_summary_label(dialog, channel_name)
    return {"Default": "shared commercials", "Off": "commercials off", "Custom": "custom commercials"}.get(
        label, "shared commercials"
    )


def commercial_library_status(dialog):
    """Best-effort description of the shared commercial library's real
    state. A live clip count when reachable -- load_or_refresh_
    commercial_library (channelsurfer2000.py) populates
    `commercial_library` on the MAIN app object, not on this dialog,
    and there's no dedicated accessor for it, so this reaches through
    `dialog.parent()` (the main app -- see how AdvancedConfigDialog is
    always constructed with `self` as its Qt parent in
    open_advanced_configuration). Falls back to calm, still-accurate
    text (off / no folder set / configured) when the count isn't
    reachable, rather than guessing a number.
    """
    commercials_settings = getattr(dialog, "commercials_settings", None) or {}
    if not commercials_settings.get("enabled"):
        return "Shared library: commercials are off"
    if not str(commercials_settings.get("root_folder", "") or "").strip():
        return "Shared library: no folder configured yet"
    parent = getattr(dialog, "parent", None)
    main_app = parent() if callable(parent) else None
    library = getattr(main_app, "commercial_library", None)
    if isinstance(library, list):
        count = len(library)
        return f"Shared library: {count} clip" + ("s" if count != 1 else "")
    return "Shared library: configured"


def channel_timed_breaks_label(dialog, channel_name):
    """"On"/"Off" for whether this channel's EFFECTIVE commercial mode
    is timed mid-episode breaks (mode == "timed_midroll" -- a real
    existing value in COMMERCIAL_MODES, channelsurfer2000.py, not an
    invented proxy). Uses the channel's own override mode when Custom
    is active and it sets one, otherwise the shared global mode --
    mirrors exactly what resolve_channel_commercial_profile does when
    building this channel's real schedule.
    """
    commercials_settings = getattr(dialog, "commercials_settings", None) or {}
    overrides = getattr(dialog, "channel_commercial_overrides", None) or {}
    override = overrides.get(channel_name) or {}
    enabled_mode = str(override.get("enabled_mode", "inherit") or "inherit")
    if enabled_mode == "on" and override.get("mode"):
        effective_mode = override["mode"]
    else:
        effective_mode = commercials_settings.get("mode", "between_episodes")
    return "On" if effective_mode == "timed_midroll" else "Off"


def channel_override_summary(dialog, channel_name):
    """A short description of what's actually stored in this channel's
    commercial override entry, or "None" if there isn't one yet --
    what the "Channel override:" status line shows.
    """
    overrides = getattr(dialog, "channel_commercial_overrides", None) or {}
    override = overrides.get(channel_name) or {}
    if not override:
        return "None"
    mode = str(override.get("enabled_mode", "inherit") or "inherit")
    if mode == "off":
        return "Commercials off"
    if mode == "on":
        return "Custom commercial settings"
    extra_keys = set(override.keys()) - {"enabled_mode"}
    if any(override.get(key) for key in extra_keys):
        return "Custom preferences"
    return "None"

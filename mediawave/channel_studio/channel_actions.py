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

from ..channel_logos import (
    channel_logo_excluded_shows as _channel_logo_excluded_shows,
    channel_logo_screen_aspect as _channel_logo_screen_aspect,
    get_effective_channel_logo_settings,
    logo_timing_preset_by_id,
    logo_timing_preset_for_settings,
    normalize_channel_bug_override,
    normalize_channel_bug_settings,
    normalize_screen_aspect,
    normalize_show_exclusions,
    position_to_normalized,
    resolve_effective_logo_position,
)
from . import channel_identity
from .companion_adapter import (
    COMPANION_NAMES,
    COMPANION_TYPES,
    read_companion_snapshot,
    resequence_companion_numbers,
)

_LOGO_MODE_LABELS = {"global": "Default", "custom": "Custom", "off": "Off"}

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
        # No live widget holds a companion's display name today (see
        # _companion_name_from_dialog) -- it lives directly on the main
        # app's real app_settings, read through dialog.parent().
        raw[f"{companion_type}_display_name"] = _companion_name_from_dialog(dialog, companion_type)
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


def local_channel_number_from_dialog(dialog, channel_id):
    """Current live channel number for a local folder channel, or None
    if no matching My Catalog row exists.
    """
    row = local_channel_row(dialog, channel_id)
    if row is None:
        return None
    return int(row["number"].value())


def set_local_channel_number(dialog, channel_id, number):
    """Real channel-number write for a local folder channel: sets the
    same spinbox My Catalog's own row uses. Returns True if a row was
    found and updated, False otherwise (safe no-op -- never raises).
    """
    row = local_channel_row(dialog, channel_id)
    if row is None:
        return False
    row["number"].setValue(int(number))
    return True


_COMPANION_NAME_SETTING_KEY = {
    "weatherstar": "weatherstar_display_name",
    "radiowave": "radiowave_display_name",
    "youtube": "youtube_display_name",
}


def local_channel_name_from_dialog(dialog, channel_id):
    """Current live name for a local folder channel -- My Catalog has no
    editable name widget (just a static label), so this is the row's own
    name string, already reflecting any earlier rename this session.
    None if no matching row exists.
    """
    row = local_channel_row(dialog, channel_id)
    return row.get("name", "") if row is not None else None


def set_local_channel_name(dialog, channel_id, name):
    """Real channel-name write for a local folder channel: updates the My
    Catalog row's own name string (so a later Save's
    collect_catalog_channel_settings() persists the new name, not the
    old one -- see channelsurfer2000.py). Returns True if a row was found
    and updated, False otherwise (safe no-op -- never raises).
    """
    row = local_channel_row(dialog, channel_id)
    if row is None:
        return False
    row["name"] = str(name or "").strip()
    return True


def _companion_name_from_dialog(dialog, companion_type):
    """Companions have no live name widget today (the Companion Channels
    tab only edits enabled/number/location-or-folder-or-playlist) -- the
    current name lives directly on the main app's real app_settings, read
    through dialog.parent() the same way _write_channel_setting_field
    writes it. Blank (not yet renamed) is a valid, common result.
    """
    parent = getattr(dialog, "parent", None)
    main_app = parent() if callable(parent) else None
    if main_app is None or not hasattr(main_app, "app_settings"):
        return ""
    return str(main_app.app_settings.get(_COMPANION_NAME_SETTING_KEY[companion_type], "") or "").strip()


def _set_companion_name_on_dialog(dialog, companion_type, name):
    """Writes a companion's display name straight onto the main app's real
    app_settings (through dialog.parent()) -- there's no live widget to
    mirror it onto, unlike enabled/number. Returns True if a real app
    object was reachable, False otherwise (safe no-op).
    """
    parent = getattr(dialog, "parent", None)
    main_app = parent() if callable(parent) else None
    if main_app is None or not hasattr(main_app, "app_settings"):
        return False
    main_app.app_settings[_COMPANION_NAME_SETTING_KEY[companion_type]] = str(name or "").strip()
    return True


def resequence_local_channels_on_dialog(dialog, ordered_channel_ids):
    """Reassign real channel numbers among the local folder channels
    named in `ordered_channel_ids` (desired left-to-right order) by
    redistributing the SAME pool of numbers they already occupy --
    mirrors companion_adapter.resequence_companion_numbers exactly, so
    this can never collide with a companion channel's number or invent
    a new one; a local channel's number always stays within the set of
    numbers local channels already held. Channel ids with no matching
    My Catalog row are safely skipped. Returns the list of channel ids
    actually updated, in order. A single (or empty) channel is a safe
    no-op -- there's nothing to redistribute.
    """
    rows = []
    for channel_id in ordered_channel_ids or []:
        row = local_channel_row(dialog, channel_id)
        if row is not None:
            rows.append((channel_id, row))
    if len(rows) < 2:
        return [channel_id for channel_id, _ in rows]
    pool = sorted(int(row["number"].value()) for _, row in rows)
    updated = []
    for (channel_id, row), number in zip(rows, pool):
        row["number"].setValue(number)
        updated.append(channel_id)
    return updated


def card_display_number(dialog, summary):
    """The channel number to show on `summary`'s card right now -- live
    from the same widget My Catalog / Companion Channels tabs edit
    (and a just-finished reorder already wrote to), falling back to the
    summary's own snapshot number when no live widget exists yet. Lets
    a reorder's renumbering show up immediately without rebuilding the
    whole summaries list.
    """
    if summary.channel_type in _COMPANION_NUMBER_ATTR:
        widget = _widget(dialog, _COMPANION_NUMBER_ATTR[summary.channel_type])
        if widget is not None:
            return int(widget.value())
        return summary.number
    live = local_channel_number_from_dialog(dialog, summary.channel_id)
    return summary.number if live is None else live


def _companion_type_from_id(channel_id):
    """"special:weatherstar" -> "weatherstar", or None for a local channel
    id / anything unrecognized. The `special:` ids are literally built as
    that prefix + the type name everywhere else in the app (see
    companion_adapter.COMPANION_CHANNEL_IDS), so this is a safe, cheap
    string check rather than a lookup table.
    """
    channel_id = str(channel_id or "")
    if not channel_id.startswith("special:"):
        return None
    companion_type = channel_id.split(":", 1)[1]
    return companion_type if companion_type in COMPANION_TYPES else None


def _local_rows_snapshot(dialog):
    """channel_identity.unified_entries()'s local-side input, built from
    every live My Catalog row -- id/name/number/enabled, straight off the
    real widgets (not a stale settings snapshot).
    """
    rows = []
    for row in getattr(dialog, "catalog_rows", None) or []:
        rows.append(
            {
                "id": row.get("id", ""),
                "name": row.get("name", ""),
                "number": row["number"].value(),
                "enabled": row["enabled"].isChecked(),
            }
        )
    return rows


def unified_entries_from_dialog(dialog):
    """channel_identity.unified_entries() built from the dialog's LIVE
    widget state -- local rows via dialog.catalog_rows, companions via
    companion_snapshot_from_dialog(dialog) -- so number/name validation
    and reorder renumbering always operate on exactly what's on screen
    right now, matching card_display_number's existing "read live
    widgets" convention.
    """
    return channel_identity.unified_entries(_local_rows_snapshot(dialog), companion_snapshot_from_dialog(dialog))


def channel_number_from_dialog(dialog, channel_id):
    """Current live channel number for ANY channel -- local or companion,
    dispatched by id prefix, same pattern card_display_number already
    uses. None if no matching widget exists yet.
    """
    companion_type = _companion_type_from_id(channel_id)
    if companion_type is not None:
        widget = _widget(dialog, _COMPANION_NUMBER_ATTR[companion_type])
        return widget.value() if widget is not None else None
    return local_channel_number_from_dialog(dialog, channel_id)


def channel_name_from_dialog(dialog, channel_id):
    """Current live channel name for ANY channel -- local or companion.
    Local channels read the My Catalog row's name string; companions
    fall back to their built-in COMPANION_NAMES default until renamed.
    """
    companion_type = _companion_type_from_id(channel_id)
    if companion_type is not None:
        return _companion_name_from_dialog(dialog, companion_type) or COMPANION_NAMES[companion_type]
    return local_channel_name_from_dialog(dialog, channel_id)


def set_channel_name_on_dialog(dialog, channel_id, name):
    """Real channel-name write for ANY channel -- local or companion.

    Local channels: updates the My Catalog row's name string (so a later
    Save's collect_catalog_channel_settings() persists the new name, not
    the stale one -- see channelsurfer2000.py) and pushes the same value
    straight into the main app's real app_settings (see
    _write_channel_setting_field) for immediate, no-restart effect.
    Companions: writes the new weatherstar_display_name/etc setting
    directly, since no live widget exists for it yet. Returns True if
    the channel was found and updated, False otherwise (safe no-op --
    never raises; a blank name is rejected here too).
    """
    name = str(name or "").strip()
    if not name:
        return False
    companion_type = _companion_type_from_id(channel_id)
    if companion_type is not None:
        return _set_companion_name_on_dialog(dialog, companion_type, name)
    if not set_local_channel_name(dialog, channel_id, name):
        return False
    _write_channel_setting_field(dialog, channel_id, "display_name", name)
    return True


def validate_channel_name_on_dialog(dialog, channel_id, candidate_name):
    """Thin bridge from the Overview inline name editor to
    channel_identity's pure validator -- see
    validate_channel_number_on_dialog for the equivalent number bridge.
    """
    entries = unified_entries_from_dialog(dialog)
    outcome, detail = channel_identity.validate_new_name(entries, channel_id, candidate_name)
    if outcome == "ok":
        return ("ok", "Looks good")
    return ("invalid", detail or "Enter a valid channel name.")


def _write_channel_setting_field(dialog, channel_id, field, value):
    """Write one field of `channel_id`'s catalog_channel_settings entry
    directly onto the REAL running app's app_settings (reached through
    `dialog.parent()` -- see commercial_library_status for the same
    reach-through-parent pattern) rather than only the dialog's own live
    widgets. Channel Studio identity edits (number, name) are meant to
    take effect immediately, without waiting for the dialog's Save button
    (see refresh_live_lineup below) -- so the setting the main app's
    apply_catalog_channel_customizations() actually reads needs updating
    right away, not just at Save. Any other field this row is missing
    gets filled in by the main app's own normalize_catalog_channel_settings
    the next time it runs, so this never needs its own copy of the schema
    defaults. Safe no-op (returns False) if dialog.parent() isn't a real
    app object with app_settings -- e.g. a test double.
    """
    parent = getattr(dialog, "parent", None)
    main_app = parent() if callable(parent) else None
    if main_app is None or not hasattr(main_app, "app_settings"):
        return False
    settings = main_app.app_settings.get("catalog_channel_settings")
    if not isinstance(settings, dict):
        settings = {}
    row = dict(settings.get(channel_id) or {})
    row[field] = value
    settings[channel_id] = row
    main_app.app_settings["catalog_channel_settings"] = settings
    return True


def set_channel_number_on_dialog(dialog, channel_id, number):
    """Real channel-number write for ANY channel -- local or companion.
    Updates the live widget (so My Catalog/Companion Channels tabs and
    Channel Studio's own card_display_number stay consistent within this
    dialog session) AND writes straight into the main app's real
    app_settings (see _write_channel_setting_field) so a subsequent
    refresh_live_lineup() picks it up without needing Save first. Returns
    True if a matching widget was found and updated.
    """
    number = int(number)
    companion_type = _companion_type_from_id(channel_id)
    if companion_type is not None:
        widget = _widget(dialog, _COMPANION_NUMBER_ATTR[companion_type])
        if widget is None:
            return False
        widget.setValue(number)
    else:
        if not set_local_channel_number(dialog, channel_id, number):
            return False
    _write_channel_setting_field(dialog, channel_id, "channel_number", number)
    return True


def validate_channel_number_on_dialog(dialog, channel_id, candidate_number):
    """Thin bridge from the Overview inline number editor to
    channel_identity's pure validator -- builds a fresh unified snapshot
    off the dialog's live widgets on every call (cheap: at most a few
    dozen entries) so the check always reflects exactly what's on screen
    right now. Returns ("ok"|"duplicate"|"invalid", human_message) --
    unlike channel_identity.validate_new_number, the detail here is
    always a ready-to-show message, not a raw conflicting id.
    """
    entries = unified_entries_from_dialog(dialog)
    outcome, detail = channel_identity.validate_new_number(entries, channel_id, candidate_number)
    if outcome == "ok":
        return ("ok", "Available")
    if outcome == "duplicate":
        return ("duplicate", "Channel number already exists.")
    return ("invalid", detail or "Enter a valid channel number.")


def refresh_live_lineup(dialog):
    """Immediately propagate a Channel Studio identity edit (number, name,
    enabled, reorder) to the rest of the app -- Guide, My Catalog,
    playback metadata -- without waiting for the dialog's Save button.

    Calls the exact same recompute sequence Save already triggers
    (see open_advanced_configuration, channelsurfer2000.py) -- just
    eagerly. Every screen already re-reads self.channels/app_settings
    fresh on render, so calling these is sufficient; no separate
    observer/pub-sub system is needed. This is a deliberate, narrow
    exception to "only Save persists" for identity fields specifically --
    every other My Catalog/Companion Channels setting still waits for
    Save, same as always.

    Safe no-op if dialog.parent() isn't the real running app (e.g. a test
    double, or Channel Studio opened standalone) -- never raises.
    """
    parent = getattr(dialog, "parent", None)
    main_app = parent() if callable(parent) else None
    if main_app is None:
        return
    inject = getattr(main_app, "inject_special_channels", None)
    if callable(inject):
        inject()
    apply_customizations = getattr(main_app, "apply_catalog_channel_customizations", None)
    if callable(apply_customizations):
        apply_customizations()
    try:
        if main_app.video_window.guide_overlay.isVisible():
            main_app.refresh_guide()
    except Exception:
        pass


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
    (see channel_logos.find_channel_bug_logo).
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


# ── Logo Studio v1 ────────────────────────────────────────────────────────
#
# Same live-widget-sharing pattern as the commercials helpers above:
# `dialog.channel_bug_settings` is the SAME dict My Catalog / Companion
# Channels tabs would see, normalized on this dialog's construction (see
# `self.channel_bug_settings = normalize_channel_bug_settings(...)` in
# AdvancedConfigDialog.__init__). Its "channel_overrides" sub-dict is
# exactly what ChannelLogoOverridesDialog itself reads and writes -- these
# helpers write to the same place, so the two stay interchangeable.


def channel_logo_global_settings(dialog):
    """The live global channel-bug settings for this dialog session."""
    return normalize_channel_bug_settings(getattr(dialog, "channel_bug_settings", None) or {})


def channel_logo_effective_settings(dialog, channel_name):
    """What would actually apply to this channel right now -- global
    settings merged with its override, if any. Mirrors exactly what
    ChannelBugOverlay.configure() computes for real playback.
    """
    return get_effective_channel_logo_settings(channel_name, channel_logo_global_settings(dialog))


def channel_logo_override_mode(dialog, channel_name):
    """"global" / "custom" / "off" -- "global" if no override exists yet."""
    settings = getattr(dialog, "channel_bug_settings", None) or {}
    overrides = settings.get("channel_overrides") or {}
    override = overrides.get(channel_name) or {}
    return str(override.get("mode", "global") or "global")


def channel_logo_mode_label(dialog, channel_name):
    """"Default" / "Custom" / "Off" -- what the Logo Studio status card
    shows for this channel's current mode.
    """
    return _LOGO_MODE_LABELS.get(channel_logo_override_mode(dialog, channel_name), "Default")


def set_channel_logo_override_mode(dialog, channel_name, mode):
    """Set just the mode ("global"/"custom"/"off"). Switching to "custom"
    seeds the override from the channel's current effective settings so
    controls start from where the logo already visually is, not from
    the global defaults.

    Mode-independent fields (excluded_shows, screen_aspect) are carried
    over from whatever override already existed regardless of which way
    the mode is changing -- neither is part of "effective settings", so
    without this a mode switch would otherwise silently drop them (they
    used to only survive by accident, when a caller happened not to
    replace the whole override dict).
    """
    settings = getattr(dialog, "channel_bug_settings", None)
    if not isinstance(settings, dict):
        return
    overrides = settings.setdefault("channel_overrides", {})
    existing = overrides.get(channel_name) or {}
    if mode == "custom":
        seed = dict(channel_logo_effective_settings(dialog, channel_name))
        seed["mode"] = "custom"
    else:
        seed = {"mode": mode}
    for mode_independent_key in ("excluded_shows", "screen_aspect"):
        if mode_independent_key in existing:
            seed[mode_independent_key] = existing[mode_independent_key]
    overrides[channel_name] = normalize_channel_bug_override(seed, channel_logo_global_settings(dialog))


def set_channel_logo_override_fields(dialog, channel_name, **fields):
    """Merge `fields` (corner/opacity/size/margin/horizontal_offset/
    vertical_offset/placement_area/grayscale_on_video/fade/timing) into
    this channel's override, switching it to "custom" first if it wasn't
    already -- dragging, resizing, or adjusting opacity implies the user
    wants a custom setting for this channel. Unknown keys are silently
    dropped by normalize_channel_bug_override, same as the old dialog.
    """
    settings = getattr(dialog, "channel_bug_settings", None)
    if not isinstance(settings, dict):
        return
    overrides = settings.setdefault("channel_overrides", {})
    current = overrides.get(channel_name) or {}
    if current.get("mode") != "custom":
        current = dict(channel_logo_effective_settings(dialog, channel_name))
    else:
        current = dict(current)
    current["mode"] = "custom"
    current.update(fields)
    overrides[channel_name] = normalize_channel_bug_override(current, channel_logo_global_settings(dialog))


def reset_channel_logo_override(dialog, channel_name):
    """Remove this channel's override entirely -- back to "Use Default"."""
    settings = getattr(dialog, "channel_bug_settings", None)
    if not isinstance(settings, dict):
        return
    overrides = settings.get("channel_overrides")
    if isinstance(overrides, dict):
        overrides.pop(channel_name, None)


def apply_channel_logo_timing_preset(dialog, channel_name, preset_id):
    """Apply one of LOGO_TIMING_PRESETS's real timing (+ fade) settings to
    this channel's override, switching it to "custom" if needed.
    """
    preset = logo_timing_preset_by_id(preset_id)
    if preset is None:
        return
    fields = {"timing": dict(preset["timing"])}
    if preset["fade"] is not None:
        fields["fade"] = preset["fade"]
    set_channel_logo_override_fields(dialog, channel_name, **fields)


def channel_logo_current_preset_id(dialog, channel_name):
    """Which LOGO_TIMING_PRESETS entry (if any) matches this channel's
    current effective timing + fade -- None for a hand-tuned combo that
    doesn't match a preset (the UI just shows nothing highlighted then).
    """
    eff = channel_logo_effective_settings(dialog, channel_name)
    return logo_timing_preset_for_settings(eff.get("timing") or {}, eff.get("fade", True))


def channel_logo_preview_position(dialog, channel_name, screen_w, screen_h, logo_w, logo_h):
    """(x, y) top-left position for the preview, in whatever pixel unit
    screen_w/screen_h/logo_w/logo_h are given in -- callers pass a scaled
    preview-canvas size, not the real video window size. Uses the exact
    same resolver (resolve_effective_logo_position) real playback does,
    so a channel that's been dragged in the freeform editor previews at
    the same normalized position it'll actually play back at.
    """
    eff = channel_logo_effective_settings(dialog, channel_name)
    return resolve_effective_logo_position(eff, screen_w, screen_h, logo_w, logo_h)


def set_channel_logo_position_from_drop(dialog, channel_name, x, y, screen_w, screen_h, logo_w, logo_h):
    """Convert a dropped preview position to normalized [0.0, 1.0]
    coordinates (see position_to_normalized) and write it to the
    channel's override -- true freeform placement, not snapped to the
    nearest of 4 corners the old position_to_corner_offsets scheme used.
    """
    pos_x, pos_y = position_to_normalized(x, y, screen_w, screen_h, logo_w, logo_h)
    set_channel_logo_override_fields(dialog, channel_name, pos_x=pos_x, pos_y=pos_y)


def channel_logo_screen_aspect(dialog, channel_name):
    """This channel's Logo Studio simulated-screen shape ("16:9"/"4:3")."""
    settings = getattr(dialog, "channel_bug_settings", None) or {}
    return _channel_logo_screen_aspect(settings, channel_name)


def set_channel_logo_screen_aspect(dialog, channel_name, aspect):
    """Write this channel's screen shape without disturbing its mode --
    like set_channel_logo_excluded_shows, this is orthogonal to
    Default/Custom/Off.
    """
    settings = getattr(dialog, "channel_bug_settings", None)
    if not isinstance(settings, dict):
        return
    overrides = settings.setdefault("channel_overrides", {})
    current = dict(overrides.get(channel_name) or {"mode": "global"})
    current["screen_aspect"] = normalize_screen_aspect(aspect)
    overrides[channel_name] = normalize_channel_bug_override(current, channel_logo_global_settings(dialog))


def channel_logo_available_shows(dialog, channel_id):
    """The shows Airing Rules already knows about for this channel --
    [{"title", "title_key", "media_type"}, ...] -- reused as-is for Show
    Exclusions so it doesn't need its own discovery pass. Empty if the
    catalog hasn't loaded shows for this channel yet.
    """
    lookup = getattr(dialog, "_channel_shows_lookup", None) or {}
    return list(lookup.get(channel_id, None) or [])


def channel_logo_excluded_shows(dialog, channel_name):
    """The show keys this channel's logo is hidden for, regardless of
    its Default/Custom/Off mode (see channel_logos.channel_logo_excluded_shows).
    """
    settings = getattr(dialog, "channel_bug_settings", None) or {}
    return _channel_logo_excluded_shows(settings, channel_name)


def set_channel_logo_excluded_shows(dialog, channel_name, show_keys):
    """Write this channel's excluded-show list without disturbing its
    mode (Default/Custom/Off) -- exclusions are orthogonal to those,
    unlike opacity/size/timing which imply "Custom" (see
    set_channel_logo_override_fields).
    """
    settings = getattr(dialog, "channel_bug_settings", None)
    if not isinstance(settings, dict):
        return
    overrides = settings.setdefault("channel_overrides", {})
    current = dict(overrides.get(channel_name) or {"mode": "global"})
    current["excluded_shows"] = normalize_show_exclusions(show_keys)
    overrides[channel_name] = normalize_channel_bug_override(current, channel_logo_global_settings(dialog))

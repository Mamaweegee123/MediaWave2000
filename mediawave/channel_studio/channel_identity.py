"""Unified channel identity: one pool, one number space, local and
companion channels together.

Local channels (`catalog_channel_settings`, keyed by `media:...`/`missing:...`
ids) and companion channels (WeatherStar/RadioWaveTV/NetTV, keyed by
`special:...` ids -- see companion_adapter.py) have always lived in two
separate settings pools. That split is why a local channel and a companion
channel could silently share the same channel number: nothing ever checked
the two pools against each other. This module is the seam that fixes that --
`unified_entries()` merges both pools into one flat list of plain dicts, and
every dedup/validate/renumber function below operates on that single list, so
"channel 7" can only ever mean one channel, period, regardless of which pool
it actually lives in on disk.

No Qt, no filesystem, no live channel objects -- just dicts and numbers, same
testable-without-a-QApplication pattern as companion_adapter.py.
channel_actions.py does the Qt-side work of building a unified_entries() list
off the real dialog widgets and applying results back.
"""


def unified_entries(local_rows, companion_snapshot):
    """Merge local channel rows and the companion snapshot into one flat
    list of `{"id", "name", "number", "enabled", "is_companion"}` dicts.

    `local_rows`: `[{"id": str, "name": str, "number": int, "enabled": bool}, ...]`.
    `companion_snapshot`: companion_adapter.read_companion_snapshot()'s shape
    -- always has an entry for every COMPANION_TYPES member (enabled or not),
    so this always contributes exactly 3 companion entries, matching that
    module's "every type always has a slot" convention.

    Disabled channels of either kind are INCLUDED, not filtered out --
    dedup/validation need to see them too (a disabled channel's number should
    never collide with an enabled one it might later be re-enabled next to).
    Never raises on malformed input; missing fields fall back to safe
    defaults.
    """
    from .companion_adapter import COMPANION_CHANNEL_IDS, COMPANION_NAMES, COMPANION_TYPES

    entries = []
    for row in local_rows or []:
        if not isinstance(row, dict):
            continue
        try:
            number = int(row.get("number", 0) or 0)
        except (TypeError, ValueError):
            number = 0
        entries.append(
            {
                "id": str(row.get("id", "") or ""),
                "name": str(row.get("name", "") or "Channel"),
                "number": number,
                "enabled": bool(row.get("enabled", True)),
                "is_companion": False,
            }
        )

    snapshot = companion_snapshot if isinstance(companion_snapshot, dict) else {}
    for companion_type in COMPANION_TYPES:
        entry = snapshot.get(companion_type) or {}
        try:
            number = int(entry.get("number", 1) or 1)
        except (TypeError, ValueError):
            number = 1
        entries.append(
            {
                "id": COMPANION_CHANNEL_IDS[companion_type],
                "name": str(entry.get("name") or COMPANION_NAMES[companion_type]),
                "number": number,
                "enabled": bool(entry.get("enabled", False)),
                "is_companion": True,
            }
        )
    return entries


def find_duplicate_numbers(entries):
    """Read-only report: `{number: [ids...]}` for every number held by 2+
    ENABLED entries. Disabled entries never count -- they're not part of the
    real, visible lineup, so two disabled channels quietly sharing a
    leftover/default number (every companion type defaults to number 1
    before it's ever configured) is not a collision worth reporting. Empty
    dict means no duplicates. Never mutates `entries`.
    """
    by_number = {}
    for entry in entries or []:
        if not entry.get("enabled", True):
            continue
        number = int(entry.get("number", 0) or 0)
        by_number.setdefault(number, []).append(entry.get("id"))
    return {number: ids for number, ids in by_number.items() if len(ids) > 1}


def repair_duplicate_numbers(entries):
    """Deterministic, gap-preserving duplicate repair for startup/load-time
    use. Only ever touches ENABLED entries -- same reasoning as
    find_duplicate_numbers, so a fresh install (all three companion slots
    disabled, all defaulting to number 1) never gets "repaired" into churn
    nobody asked for.

    Strategy (must stay literally this -- it's what makes the result
    deterministic and testable):
      1. Stable-sort enabled entries by (number, name.casefold(), id)
         ascending -- the same tie-break tuple apply_catalog_channel_
         customizations already uses for its own sort, so already-valid
         configs see no behavior change.
      2. Walk the sorted order, tracking which numbers are already claimed.
      3. A number > 0 that isn't claimed yet is left exactly as-is and
         claimed -- this is what preserves user-created gaps like 2/5/8: a
         number is only ever touched if it collides (or was never set).
      4. A number that's 0 (never assigned) or already claimed by an
         earlier entry gets the smallest unclaimed integer >= 1 --
         "smallest free slot", not "next after the max", so repaired
         numbers stay compact and reproducible regardless of how large
         existing numbers are.

    Returns `(repaired_entries, changes)`: `repaired_entries` is a new list,
    same length and order as the input, with only the `number` field
    possibly changed on affected entries; `changes` is
    `[{"id":..., "old_number":..., "new_number":...}, ...]`, empty if
    nothing needed fixing. Disabled entries are copied through untouched.
    Never raises; never drops an entry.
    """
    repaired = [dict(entry) for entry in (entries or [])]
    enabled_positions = [i for i, entry in enumerate(repaired) if entry.get("enabled", True)]
    ordered_positions = sorted(
        enabled_positions,
        key=lambda i: (
            int(repaired[i].get("number", 0) or 0),
            str(repaired[i].get("name", "")).casefold(),
            str(repaired[i].get("id", "")),
        ),
    )

    used = set()
    changes = []
    for i in ordered_positions:
        entry = repaired[i]
        number = int(entry.get("number", 0) or 0)
        if number > 0 and number not in used:
            used.add(number)
            continue
        new_number = 1
        while new_number in used:
            new_number += 1
        changes.append({"id": entry.get("id"), "old_number": number, "new_number": new_number})
        entry["number"] = new_number
        used.add(new_number)

    return repaired, changes


def validate_new_number(entries, channel_id, candidate_number):
    """Pure availability check for the inline Overview number editor.

    `entries` is the CURRENT unified pool, including `channel_id`'s own
    current row (it must not flag itself as a duplicate of itself).
    Returns one of:
      ("ok", None)               -- candidate is free to use
      ("duplicate", other_id)    -- another enabled channel already holds it
      ("invalid", reason)        -- not a usable integer, or out of range

    Range is 1-9999, matching catalog_channel_settings' existing clamp in
    normalize_catalog_channel_settings -- 0 is deliberately excluded here
    (0 means "unset" internally; a manual edit should never re-enter that
    state). Never raises.
    """
    try:
        number = int(candidate_number)
    except (TypeError, ValueError):
        return ("invalid", "Enter a whole number.")
    if number < 1 or number > 9999:
        return ("invalid", "Channel number must be between 1 and 9999.")
    channel_id = str(channel_id)
    for entry in entries or []:
        if str(entry.get("id")) == channel_id:
            continue
        if not entry.get("enabled", True):
            continue
        if int(entry.get("number", 0) or 0) == number:
            return ("duplicate", entry.get("id"))
    return ("ok", None)


def validate_new_name(entries, channel_id, candidate_name):
    """Pure check for the inline Overview name editor. Names aren't required
    to be unique -- only rejects blank/whitespace-only or excessively long
    names. `entries`/`channel_id` are accepted for signature symmetry with
    validate_new_number even though this check doesn't need to look at
    other entries today. Never raises.
    """
    name = str(candidate_name or "").strip()
    if not name:
        return ("invalid", "Channel name can't be empty.")
    if len(name) > 64:
        return ("invalid", "Channel name is too long.")
    return ("ok", None)


def sort_unified_entries(entries):
    """Channel Studio's one and only lineup order: real channel number
    ascending, local and companion channels interleaved together (no
    separate per-type ordering), name then id as a stable, deterministic
    tie-break for equal numbers.

    This only orders -- it never rewrites a number, so manual gaps (e.g.
    2/5/8/36) are always preserved exactly, and renumbering one channel
    (e.g. to 36) can only ever change that channel's position, never
    another entry's number. Disabled entries are included, same as
    elsewhere in this module; filtering, if any, is the caller's job.
    Never mutates `entries`; never raises.
    """
    return sorted(
        entries or [],
        key=lambda entry: (
            int(entry.get("number", 0) or 0),
            str(entry.get("name", "")).casefold(),
            str(entry.get("id", "")),
        ),
    )

"""Saved schedule overrides: the durable representation of Schedule Editor
edits, and the pure splice logic that layers them onto the generated lineup.

No Qt, no imports from channelsurfer2000. This module is the third
schedule-state layer (see docs/SCHEDULE_EDITOR_ARCHITECTURE.md):

  generated lineup   -> schedule_state.json, the auto-built looping entry
                        list each live Channel resolves wall-clock time
                        against (unchanged by this module)
  draft lineup       -> mediawave/schedule_editor/draft_model.py, editor-only
  saved overrides    -> THIS module: schedule_overrides.json
  live playback      -> Channel.get_current(); consults overrides only
                        through the splice/resolve helpers here

An override is a small per-date record anchored to an absolute wall-clock
interval on one channel -- never a recurring rule, and never a rewrite of
the generated entry list. Two actions exist in this phase:

  remove -- "nothing from the generated lineup airs in this interval";
            consumers see an explicit synthetic "Open Time" item (an
            explicit item rather than a hole, because the TV Guide's slot
            builder assumes contiguous window items)
  add    -- "this media airs in this interval"; it masks whatever the
            generated lineup had there, and a generated program partially
            covered by it is joined in progress afterward (real-broadcast
            semantics, and it keeps playback's untouched modular time math
            consistent with what the guide shows)

Interval semantics: half-open [start, end). Overrides apply sequentially,
in file order (Save Schedule always appends in edit order) -- each record
masks whatever the layers below it put in its interval, so an add placed
inside a pulled program's gap covers part of that gap, and a later pull of
a previously saved added program masks the add. "Last edit wins" is the
one precedence rule everywhere: the splice, override_at, and playback
resolution all walk the list in order.

Overrides are time-slot anchored, not content anchored: generated entries
have no stable per-entry IDs, but the wall-clock slot IS deterministic
(schedule anchor + persisted shuffle seed survive restarts), so "override
what airs at 11:30 PM on this date" is the honest identity. If the
generated schedule is later rebuilt (catalog or commercial settings
changed), the override still claims the same wall-clock slot on the same
date -- that is the documented, intentional behavior.
"""

import json
import os
import tempfile


SCHEDULE_OVERRIDES_VERSION = 1

OVERRIDE_ACTION_ADD = "add"
OVERRIDE_ACTION_REMOVE = "remove"
OVERRIDE_ACTIONS = (OVERRIDE_ACTION_ADD, OVERRIDE_ACTION_REMOVE)

# Overrides whose interval ended more than this long ago are dropped on
# save -- per-date edits have no meaning once their date has passed, and
# pruning on save (never on load) means a malformed-load fallback can
# never silently shrink a file it failed to read.
PRUNE_AFTER_SECONDS = 48 * 3600

OPEN_TIME_TITLE = "Open Time"
OPEN_TIME_KIND = "open_time"


def empty_overrides_data():
    return {"version": SCHEDULE_OVERRIDES_VERSION, "overrides": []}


def normalize_override(record):
    """Validated plain-dict copy of one override record, or None if the
    record is structurally unusable. Unknown extra keys are dropped --
    what's persisted is exactly what's documented.
    """
    if not isinstance(record, dict):
        return None
    action = str(record.get("action", "") or "")
    if action not in OVERRIDE_ACTIONS:
        return None
    channel_id = str(record.get("channel_id", "") or "")
    if not channel_id:
        return None
    try:
        start = float(record.get("start", 0) or 0)
        end = float(record.get("end", 0) or 0)
    except (TypeError, ValueError):
        return None
    if end <= start:
        return None
    normalized = {
        "action": action,
        "channel_id": channel_id,
        "date": str(record.get("date", "") or ""),
        "start": start,
        "end": end,
        "title": str(record.get("title", "") or ""),
        "path": str(record.get("path", "") or ""),
        "media_type": str(record.get("media_type", "") or ""),
    }
    if action == OVERRIDE_ACTION_ADD and not normalized["path"]:
        return None
    return normalized


def normalize_overrides_data(data):
    """(normalized_data, ok). ok is False when the payload was malformed
    at the top level -- callers keep the previous in-memory state and
    surface the problem instead of silently replacing the file.
    """
    if not isinstance(data, dict):
        return empty_overrides_data(), False
    try:
        version = int(data.get("version", 0) or 0)
    except (TypeError, ValueError):
        return empty_overrides_data(), False
    if version < 1 or version > SCHEDULE_OVERRIDES_VERSION:
        return empty_overrides_data(), False
    raw = data.get("overrides")
    if not isinstance(raw, list):
        return empty_overrides_data(), False
    overrides = []
    for record in raw:
        normalized = normalize_override(record)
        if normalized is not None:
            overrides.append(normalized)
    return {"version": SCHEDULE_OVERRIDES_VERSION, "overrides": overrides}, True


def load_schedule_overrides(path):
    """Load and validate the overrides file. Malformed or missing files
    yield an empty structure -- the file itself is never rewritten or
    deleted here, so nothing is lost to a transient read problem.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return empty_overrides_data()
    normalized, _ok = normalize_overrides_data(data)
    return normalized


def save_schedule_overrides(path, data, now=None):
    """Atomically persist overrides. Returns (ok, error_message).

    Validates first (a structurally bad payload is refused outright,
    leaving the existing file untouched), prunes long-past intervals, then
    writes via tempfile + os.replace so a crash mid-write can never leave
    a truncated overrides file behind.
    """
    normalized, ok = normalize_overrides_data(data)
    if not ok:
        return False, "The override data was not in a valid format, so the existing file was left unchanged."
    if now is not None:
        cutoff = float(now) - PRUNE_AFTER_SECONDS
        normalized["overrides"] = [
            record for record in normalized["overrides"] if record["end"] >= cutoff
        ]
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".schedule_overrides_", suffix=".tmp", dir=directory)
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
        return False, f"The schedule override file could not be written ({error.strerror or error})."
    return True, ""


def overrides_for_channel(data, channel_id):
    """The channel's override records, in file order -- creation order is
    the precedence order (see module docstring), so no re-sorting.
    """
    records = (data or {}).get("overrides") or []
    return [record for record in records if record.get("channel_id") == channel_id]


def override_at(overrides, when):
    """The single override governing instant `when`, or None. Walks the
    list in order; the last (most recently created) match wins.
    """
    active = None
    for record in overrides or []:
        if record["start"] <= when < record["end"]:
            active = record
    return active


def subtract_interval(start, end, mask_start, mask_end):
    """The sub-intervals of [start, end) NOT covered by [mask_start,
    mask_end). Zero, one, or two pieces. Shared with the Schedule
    Editor's draft presentation (draft_model.py), which mirrors this
    module's sequential-mask semantics on unsaved edits.
    """
    pieces = []
    if mask_start > start:
        pieces.append((start, min(mask_start, end)))
    if mask_end < end:
        pieces.append((max(mask_end, start), end))
    return [(s, e) for s, e in pieces if e > s]


def open_time_item(start, end):
    """The synthetic window item consumers see for a removed interval with
    nothing put on air in it. An explicit item, not a hole (see module
    docstring); `kind: "open_time"` is how the board model and guide
    recognize it.
    """
    return {
        "path": "",
        "title": OPEN_TIME_TITLE,
        "start": float(start),
        "end": float(end),
        "entry": {
            "kind": OPEN_TIME_KIND,
            "path": "",
            "title": OPEN_TIME_TITLE,
            "duration": float(end) - float(start),
            "source": "override",
        },
    }


def added_program_item(record, clip_start=None, clip_end=None):
    """The synthetic window item for an add override (optionally clipped
    for consumers that requested a narrower window).
    """
    start = float(record["start"]) if clip_start is None else max(float(record["start"]), clip_start)
    end = float(record["end"]) if clip_end is None else min(float(record["end"]), clip_end)
    duration = float(record["end"]) - float(record["start"])
    return {
        "path": record["path"],
        "title": record.get("title") or record["path"],
        "start": start,
        "end": end,
        "entry": {
            "kind": "content",
            "path": record["path"],
            "title": record.get("title") or record["path"],
            "duration": duration,
            "start_offset": 0.0,
            "end_offset": duration,
            "source": "override",
            "media_type": record.get("media_type", ""),
        },
    }


def splice_overrides_into_window(items, overrides):
    """Layer override records onto a channel's raw window items.

    `items` is the untouched get_programs_for_window output (contiguous,
    sorted). Overrides apply sequentially in list order: each record masks
    its interval out of everything accumulated so far (base items AND
    earlier overrides' items), then contributes its own item -- an add
    contributes a real program item, a remove contributes an explicit Open
    Time item. A base program partially masked keeps real wall-clock times
    on its surviving piece (joined in progress -- playback's untouched
    modular math and this display agree). Result is sorted and contiguous
    across the original span.
    """
    if not overrides or not items:
        return list(items or [])

    window_start = min(item["start"] for item in items)
    window_end = max(item["end"] for item in items)

    result = list(items)
    changed = False
    for record in overrides:
        mask_start = max(float(record["start"]), window_start)
        mask_end = min(float(record["end"]), window_end)
        if mask_end <= mask_start:
            continue
        changed = True
        survivors = []
        for item in result:
            for piece_start, piece_end in subtract_interval(item["start"], item["end"], mask_start, mask_end):
                if piece_start == item["start"] and piece_end == item["end"]:
                    survivors.append(item)
                else:
                    trimmed = dict(item)
                    trimmed["start"] = piece_start
                    trimmed["end"] = piece_end
                    survivors.append(trimmed)
        if record["action"] == OVERRIDE_ACTION_ADD:
            survivors.append(added_program_item(record, clip_start=window_start, clip_end=window_end))
        else:
            survivors.append(open_time_item(mask_start, mask_end))
        result = survivors

    if not changed:
        return list(items)
    result.sort(key=lambda item: (item["start"], item["end"]))
    return result


def resolve_current_with_overrides(overrides, now):
    """What the override layer says about instant `now`:

      None                          -- no override active; use the
                                       generated lineup as always
      ("add", record, media_offset) -- the added media is on air,
                                       media_offset seconds in (an added
                                       program whose start has already
                                       passed is joined in progress)
      ("open", record, 0.0)         -- a pulled interval with nothing put
                                       on air; nothing plays
    """
    record = override_at(overrides or [], now)
    if record is None:
        return None
    if record["action"] == OVERRIDE_ACTION_ADD:
        return ("add", record, max(0.0, float(now) - record["start"]))
    return ("open", record, 0.0)

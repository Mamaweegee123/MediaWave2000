"""Auto-Fill Block's "Continue Sequentially" cursor (Phase 4).

A small, schema-versioned, persisted record of the last episode PLACED
by a sequential Auto-Fill Block action, per (channel, show) -- keyed by
a stable show identity (mediawave.local_media.metadata_lookup_key, the
same key scheduling.py's own lineup ordering already trusts), never by
display title, since two shows can share a title and one show's title
can change without its key changing.

Deliberately NOT playback history, and its name says so on purpose:
this only ever advances at the moment Save Schedule successfully
persists a sequential Auto-Fill placement (dialog.py's _perform_save is
the one caller of advance semantics) -- it records "the last episode
this feature scheduled here", not "the last episode that actually
aired". Saved overrides can't answer the latter reliably either (they
only capture explicit edits, not automatically generated programming),
which is why this module exists instead of trying to reconstruct
history from them. If a real play-log is ever built, it can outrank or
replace this cursor as plan_continue_sequentially's `last_aired_path`
source without changing the planner's API or this module's storage
format -- the planner only ever receives a plain path, never where it
came from.

Mirrors recent_media.py's shape exactly (schema version, normalize-with-
ok, atomic tempfile+os.replace write) -- one more file in the same
persistence family, not a new pattern.

Phase 5.5.2 step 4 -- legacy raw-key compatibility: a cursor row is
persisted under whatever show_key was canonical AT THE TIME it was
written. If a user later corrects that show's identity (rename/merge),
old rows stay under their original (now-legacy) raw key forever -- this
module never rewrites or deletes them; only a fresh successful sequential
placement ever writes a new row, always under today's canonical key (see
last_aired_path_for below for the read-side compatibility this implies).

Cursor conflict rule, when a merged canonical show has cursor rows under
more than one of its legacy aliases (last_aired_path_for's alias-search
path): the fields persisted per row are `path`, `title`, `season_number`,
`episode_number`, and `updated_at`. `updated_at` is only as reliable as
whatever the caller passed as `now` -- a row advanced without one
defaults to 0.0, which is NOT a real timestamp, so it can't be trusted to
outrank a row that does have one. The winner rule, in order:

  1. Among rows with `updated_at > 0` (a real timestamp), the highest
     `updated_at` wins -- the most recently PLACED (never "aired", see
     above) episode is the best signal of "where this show currently is".
  2. If no row has a reliable timestamp, the row with the furthest
     parseable `(season_number, episode_number)` wins -- a reasonable
     proxy for progress when timing information doesn't exist.
  3. If neither comparison is possible (no timestamps AND no season/
     episode numbers on any candidate), the first alias in the registry's
     own deterministic alias order wins -- arbitrary but STABLE, so the
     same merge always resolves the same way rather than depending on
     dict/scan order.

Every losing row is left exactly as it was; this rule only affects what
last_aired_path_for returns, never what's on disk.
"""

import json
import os
import tempfile

from mediawave.show_identity import aliases_for_show_key

AUTOFILL_CURSOR_VERSION = 1

# A key sequence that can never collide with a real channel_id or
# show_key -- both are always non-empty strings from real identifiers
# (channel ids, metadata_lookup_key's own "tv::"/"movie::" prefixes),
# never containing this separator.
_KEY_SEP = "␟"


def empty_cursor_data():
    return {"version": AUTOFILL_CURSOR_VERSION, "cursors": {}}


def cursor_key(channel_id, show_key):
    return f"{channel_id}{_KEY_SEP}{show_key}"


def normalize_cursor_entry(entry):
    """A validated plain-dict copy of one cursor record, or None if it's
    structurally unusable -- channel_id/show_key/path are all required;
    there's nothing stable to key or resume from without them. Unknown
    extra keys are dropped, same contract as recent_media's normalizer.
    """
    if not isinstance(entry, dict):
        return None
    channel_id = str(entry.get("channel_id", "") or "")
    show_key = str(entry.get("show_key", "") or "")
    path = str(entry.get("path", "") or "")
    if not channel_id or not show_key or not path:
        return None

    def _optional_int(value):
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    try:
        updated_at = float(entry.get("updated_at", 0) or 0)
    except (TypeError, ValueError):
        updated_at = 0.0

    return {
        "channel_id": channel_id,
        "show_key": show_key,
        "path": path,
        "title": str(entry.get("title", "") or ""),
        "season_number": _optional_int(entry.get("season_number")),
        "episode_number": _optional_int(entry.get("episode_number")),
        "updated_at": updated_at,
    }


def normalize_cursor_data(data):
    """(normalized_data, ok) -- ok is False when the payload was
    malformed at the top level (not a dict, bad/future version, or
    "cursors" isn't a dict), so callers can keep the previous in-memory
    state rather than silently discarding it. Individual malformed
    entries within an otherwise-valid file are simply dropped, not
    treated as a whole-file failure -- one corrupt cursor shouldn't cost
    every other show's sequencing state.
    """
    if not isinstance(data, dict):
        return empty_cursor_data(), False
    try:
        version = int(data.get("version", 0) or 0)
    except (TypeError, ValueError):
        return empty_cursor_data(), False
    if version < 1 or version > AUTOFILL_CURSOR_VERSION:
        return empty_cursor_data(), False
    raw = data.get("cursors")
    if not isinstance(raw, dict):
        return empty_cursor_data(), False
    cursors = {}
    for entry in raw.values():
        normalized = normalize_cursor_entry(entry)
        if normalized is not None:
            cursors[cursor_key(normalized["channel_id"], normalized["show_key"])] = normalized
    return {"version": AUTOFILL_CURSOR_VERSION, "cursors": cursors}, True


def load_autofill_cursors(path):
    """Load and validate the cursor file. Missing or malformed files
    yield an empty structure -- the file itself is never rewritten or
    deleted here, and a bad load is never a fatal error for the caller.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return empty_cursor_data()
    normalized, _ok = normalize_cursor_data(data)
    return normalized


def save_autofill_cursors(path, data):
    """Atomically persist cursor data (tempfile write + os.replace, same
    as schedule_overrides.py/recent_media.py). Returns (ok, error). A
    structurally invalid payload is refused outright, leaving the
    existing file on disk untouched -- callers must never end up with a
    half-written or corrupted cursor file.
    """
    normalized, ok = normalize_cursor_data(data)
    if not ok:
        return False, "The Auto-Fill sequencing data was not in a valid format, so the existing file was left unchanged."
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".schedule_autofill_cursor_", suffix=".tmp", dir=directory)
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
        return False, f"The Auto-Fill sequencing file could not be written ({error.strerror or error})."
    return True, ""


def advance_cursor(data, channel_id, show_key, path, title="", season_number=None, episode_number=None, now=None):
    """The new cursor data after recording one successfully-SAVED
    sequential Auto-Fill placement. Returns a fresh dict; never mutates
    `data`. Callers (dialog.py, via cursors_to_advance_from_saved_changes
    below) are expected to pass only the chronologically LAST episode of
    a (channel, show) among everything that just saved together.
    """
    current, _ok = normalize_cursor_data(data if isinstance(data, dict) else empty_cursor_data())
    entry = normalize_cursor_entry({
        "channel_id": channel_id,
        "show_key": show_key,
        "path": path,
        "title": title,
        "season_number": season_number,
        "episode_number": episode_number,
        "updated_at": float(now) if now is not None else 0.0,
    })
    if entry is None:
        return current
    cursors = dict(current["cursors"])
    cursors[cursor_key(channel_id, show_key)] = entry
    return {"version": AUTOFILL_CURSOR_VERSION, "cursors": cursors}


def _reliable_updated_at(entry):
    updated_at = entry.get("updated_at", 0.0)
    return updated_at if updated_at and updated_at > 0 else None


def _season_episode_progress(entry):
    def _optional_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    season = _optional_int(entry.get("season_number"))
    episode = _optional_int(entry.get("episode_number"))
    if season is None and episode is None:
        return None
    return (season if season is not None else -1, episode if episode is not None else -1)


def pick_winning_cursor_entry(entries):
    """The one cursor entry `last_aired_path_for` should trust when a
    merged show has more than one candidate (one per legacy alias) --
    see the module docstring for the exact rule and why. `entries` is
    assumed already in the registry's deterministic alias order, which
    is what makes rule 3's fallback deterministic. Never mutates
    `entries`; returns None for an empty list.
    """
    entries = list(entries or [])
    if not entries:
        return None
    if len(entries) == 1:
        return entries[0]

    timestamped = [(entry, _reliable_updated_at(entry)) for entry in entries]
    timestamped = [(entry, value) for entry, value in timestamped if value is not None]
    if timestamped:
        return max(timestamped, key=lambda pair: pair[1])[0]

    with_progress = [(entry, _season_episode_progress(entry)) for entry in entries]
    with_progress = [(entry, value) for entry, value in with_progress if value is not None]
    if with_progress:
        return max(with_progress, key=lambda pair: pair[1])[0]

    return entries[0]


def last_aired_path_for(data, channel_id, show_key, show_identity_registry=None):
    """The path plan_continue_sequentially should resume after for this
    (channel, show), or None if there's no cursor yet -- exactly the "no
    history" case the planner already falls back on by starting at the
    first episode. Despite the name (kept for readability against the
    planner's own `last_aired_path` parameter), this is never a claim
    about actual playback -- see the module docstring.

    `show_key` is expected to already be canonical (every caller resolves
    it from a catalog item, which has carried canonical show_key since
    Phase 5.5.2 step 2). The canonical row is tried FIRST and, if found,
    returned immediately -- no alias search needed. Only when there's no
    row under the canonical key does this fall back to searching every
    legacy alias `show_identity_registry` knows for that show (Phase
    5.5.2 step 4), applying pick_winning_cursor_entry's rule if more than
    one alias has a row. `show_identity_registry=None` (or a registry
    with no aliases for this show) preserves today's exact behavior: a
    canonical-only lookup, returning None if it misses.
    """
    current, _ok = normalize_cursor_data(data if isinstance(data, dict) else empty_cursor_data())
    entry = current["cursors"].get(cursor_key(channel_id, show_key))
    if entry is not None:
        return entry["path"]
    if not show_identity_registry:
        return None
    candidates = []
    for alias in aliases_for_show_key(show_key, show_identity_registry):
        alias_entry = current["cursors"].get(cursor_key(channel_id, alias))
        if alias_entry is not None:
            candidates.append(alias_entry)
    winner = pick_winning_cursor_entry(candidates)
    return winner["path"] if winner is not None else None


def cursors_to_advance_from_saved_changes(autofill_entries):
    """`autofill_entries`: one {channel_id, show_key, path, title,
    season_number, episode_number, start} dict per sequential Auto-Fill
    placement that just successfully SAVED. Collapses them to at most one
    advance per (channel_id, show_key) -- the entry with the latest
    `start` -- so several sequential Auto-Fill Block groups saved
    together in one Save Schedule action advance to the FINAL episode in
    chronological order, never an earlier one depending on incoming list
    order. The only caller is dialog.py's _perform_save, and only after
    its own save() call has already returned success.
    """
    latest = {}
    for entry in autofill_entries or []:
        channel_id = entry.get("channel_id", "")
        show_key = entry.get("show_key", "")
        if not channel_id or not show_key or not entry.get("path"):
            continue
        key = (channel_id, show_key)
        current = latest.get(key)
        if current is None or float(entry.get("start", 0) or 0) > float(current.get("start", 0) or 0):
            latest[key] = entry
    return list(latest.values())

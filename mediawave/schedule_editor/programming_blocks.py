"""Programming Blocks (Phase 5.4): a small, user-named group of shows that
Auto-Fill can rotate through fairly when filling an Open Time range --
"Adult Swim", "Halloween TV", "Comfort Shows", etc. Strict MVP: a block
is only {id, name, show_keys, behavior}. `behavior` is always
"rotate_shows" today; it's kept as a stored field rather than an implicit
constant so a second behavior could be added later without a migration,
not because this phase offers a choice.

Mirrors autofill_cursor.py's persistence shape exactly (schema version,
normalize-with-ok, atomic tempfile+os.replace write) -- one more file in
the same persistence family, not a new pattern.

Identity: blocks are keyed on `id` (a random token, assigned once at
creation), never on `name` or on the show_keys they contain -- renaming a
block or changing its show list is an edit to the same id, not a new
block. `show_keys` stores whatever show_key was canonical at save time --
for an uncorrected show that's still exactly mediawave.local_media.
metadata_lookup_key's own output. A show_key the current catalog doesn't
have -- deleted media, a renamed folder, or simply not scanned yet -- is
left in the block untouched; resolve_programming_block below just skips
it when resolving, the same "list it, don't invent it" treatment the
rest of the Schedule Editor gives missing catalog data.

Phase 5.5.2 step 4 -- legacy raw-key compatibility: a block saved before
a show was corrected (renamed/merged) may still list its old raw key(s).
resolve_programming_block/`_block_stats`'s caller passes an already-
loaded mediawave.show_identity registry snapshot; `show_keys` is
canonicalized THROUGH that registry before matching against `items`
(whose own show_key has been canonical since Phase 5.5.2 step 2), so
several old raw aliases of one merged show collapse to a single rotation
slot instead of either going stale (no longer matching anything) or
counting as separate shows. The stored block JSON is never rewritten by
resolving it -- only a normal explicit Save Block from the editor writes
canonical keys back out (programming_block_dialog.py).
"""

import hashlib
import json
import os
import tempfile
import uuid

from mediawave.show_identity import canonicalize_show_keys, empty_registry, show_behavior_for

from .autofill_cursor import last_aired_path_for
from .autofill_planner import plan_rotate_shows

PROGRAMMING_BLOCKS_VERSION = 1
BEHAVIOR_ROTATE_SHOWS = "rotate_shows"

# Deterministic library-card identity plates (Phase 5.4 redesign): each
# block gets a stable gradient pair chosen from `block.id` alone, never
# from `name` -- renaming a block must never change its plate. A small
# fixed palette (not a full hue wheel) keeps the library feeling like one
# coherent set of packages rather than a random-color grab bag.
PLATE_PALETTE = [
    ("#ff8a4c", "#d13e6e"),
    ("#ffcf4c", "#ff8a3d"),
    ("#5b3df0", "#8b7bff"),
    ("#2fbf9f", "#1e8ed6"),
    ("#e94f9c", "#7c3aed"),
    ("#22a06b", "#8bc34a"),
    ("#3c6ff0", "#22c1e0"),
    ("#f0473c", "#ff9147"),
]


def plate_colors_for_block(block_id):
    """(start_hex, end_hex) for this block's identity plate -- a pure
    function of `block_id` alone (a stable md5 digest, not Python's
    randomized-per-process hash()), so the same block always gets the
    same plate across saves, reloads, and renames.
    """
    digest = hashlib.md5(str(block_id or "").encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(PLATE_PALETTE)
    return PLATE_PALETTE[index]


class ProgrammingBlock:
    """One saved Programming Block. Deliberately has no methods beyond
    to_dict -- all real logic (grouping shows, resolving a lineup) lives
    in module-level pure functions here and in autofill_planner.py, so
    tests never need a live instance to exercise the actual behavior.
    """

    __slots__ = ("id", "name", "description", "show_keys", "behavior")

    def __init__(self, id, name, show_keys, behavior=BEHAVIOR_ROTATE_SHOWS, description=""):
        self.id = id
        self.name = name
        self.description = description or ""
        self.show_keys = list(show_keys or [])
        self.behavior = behavior

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "show_keys": list(self.show_keys),
            "behavior": self.behavior,
        }

    def __eq__(self, other):
        return isinstance(other, ProgrammingBlock) and self.to_dict() == other.to_dict()

    def __repr__(self):
        return f"ProgrammingBlock(id={self.id!r}, name={self.name!r}, show_keys={self.show_keys!r})"


def new_block_id():
    return uuid.uuid4().hex


def empty_programming_blocks_data():
    return {"version": PROGRAMMING_BLOCKS_VERSION, "blocks": []}


def normalize_block_entry(entry):
    """A validated ProgrammingBlock, or None if it's structurally unusable
    (no id, no non-empty name). An empty show_keys list is kept as valid
    structure -- it simply resolves to nothing (see resolve_programming_
    block) rather than being treated as a malformed record; the UI layer
    is what actually requires "at least one show" before letting a user
    save one. `description` is optional and backward-compatible: entries
    saved before it existed simply have no "description" key and load as
    an empty string, no version bump required.
    """
    if isinstance(entry, ProgrammingBlock):
        entry = entry.to_dict()
    if not isinstance(entry, dict):
        return None
    block_id = str(entry.get("id", "") or "").strip()
    name = str(entry.get("name", "") or "").strip()
    if not block_id or not name:
        return None
    description = str(entry.get("description", "") or "").strip()
    raw_keys = entry.get("show_keys")
    show_keys = []
    if isinstance(raw_keys, list):
        seen = set()
        for key in raw_keys:
            key = str(key or "").strip()
            if key and key not in seen:
                seen.add(key)
                show_keys.append(key)
    behavior = entry.get("behavior")
    if behavior != BEHAVIOR_ROTATE_SHOWS:
        behavior = BEHAVIOR_ROTATE_SHOWS
    return ProgrammingBlock(block_id, name, show_keys, behavior, description=description)


def normalize_programming_blocks_data(data):
    """(normalized_data, ok) -- ok is False only when the payload is
    malformed at the top level (not a dict, bad/future version, or
    "blocks" isn't a list), so a caller can keep its previous in-memory
    state rather than silently discarding every saved block. An
    individual malformed block entry is simply dropped, not treated as a
    whole-file failure. Duplicate ids keep only the first occurrence.
    """
    if not isinstance(data, dict):
        return empty_programming_blocks_data(), False
    try:
        version = int(data.get("version", 0) or 0)
    except (TypeError, ValueError):
        return empty_programming_blocks_data(), False
    if version < 1 or version > PROGRAMMING_BLOCKS_VERSION:
        return empty_programming_blocks_data(), False
    raw = data.get("blocks")
    if not isinstance(raw, list):
        return empty_programming_blocks_data(), False
    blocks = []
    seen_ids = set()
    for entry in raw:
        block = normalize_block_entry(entry)
        if block is None or block.id in seen_ids:
            continue
        seen_ids.add(block.id)
        blocks.append(block)
    return {"version": PROGRAMMING_BLOCKS_VERSION, "blocks": blocks}, True


def load_programming_blocks(path):
    """Load and validate the Programming Blocks file. Missing or malformed
    files yield an empty structure -- the file itself is never rewritten
    or deleted here, matching autofill_cursor.py's load contract.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return empty_programming_blocks_data()
    normalized, _ok = normalize_programming_blocks_data(data)
    return normalized


def save_programming_blocks(path, data):
    """Atomically persist Programming Blocks data (tempfile write +
    os.replace, same as autofill_cursor.py/schedule_overrides.py).
    Returns (ok, error). A structurally invalid payload is refused
    outright, leaving the existing file on disk untouched.
    """
    normalized, ok = normalize_programming_blocks_data(data)
    if not ok:
        return False, "The Programming Blocks data was not in a valid format, so the existing file was left unchanged."
    payload = {
        "version": normalized["version"],
        "blocks": [block.to_dict() for block in normalized["blocks"]],
    }
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".schedule_programming_blocks_", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    except OSError as error:
        return False, f"The Programming Blocks file could not be written ({error.strerror or error})."
    return True, ""


def upsert_block(data, block):
    """A fresh data dict with `block` added, or replacing an existing
    block of the same id -- editing a block's name/show_keys keeps its
    id (an edit, not a delete-and-recreate). Never mutates `data`.
    """
    normalized, _ok = normalize_programming_blocks_data(data if isinstance(data, dict) else empty_programming_blocks_data())
    blocks = [existing for existing in normalized["blocks"] if existing.id != block.id]
    blocks.append(block)
    return {"version": PROGRAMMING_BLOCKS_VERSION, "blocks": blocks}


def remove_block(data, block_id):
    """A fresh data dict with the block matching `block_id` removed (a
    no-op if it doesn't exist). Never mutates `data`. Removing a block
    never touches any catalog media -- deleting a block deletes only the
    block.
    """
    normalized, _ok = normalize_programming_blocks_data(data if isinstance(data, dict) else empty_programming_blocks_data())
    blocks = [existing for existing in normalized["blocks"] if existing.id != block_id]
    return {"version": PROGRAMMING_BLOCKS_VERSION, "blocks": blocks}


def resolve_programming_block(block, items, gap_start, gap_duration, seed=None, show_identity_registry=None, channel_id=None, cursor_data=None):
    """One resolved concrete lineup for `block` filling [gap_start,
    gap_start + gap_duration) -- the same plan_* result shape
    (autofill_planner.py) every other Auto-Fill strategy returns, so it
    reaches AutoFillBlockCommand through the exact existing "planner
    proposes, command applies" pipeline with no new consumer needed.
    Show_keys the current catalog doesn't have are silently skipped (see
    module docstring); the block's own stored data is never touched by
    resolving it. `block.show_keys` is canonicalized through
    `show_identity_registry` first (Phase 5.5.2 step 4) -- several old
    raw aliases of one merged show collapse to that show's single
    canonical key, so plan_rotate_shows sees it once, not several times.
    `show_identity_registry=None` preserves today's exact behavior
    (canonicalize_show_keys against an empty registry is a no-op).

    Phase 5.6: also resolves each included show's persistent Episode
    Behavior (show_behavior_for) and, for any show explicitly saved as
    "sequential", its next episode via the SAME shared cursor lookup
    (autofill_cursor.last_aired_path_for) Schedule Show/sequential
    Auto-Fill already use -- both forwarded into plan_rotate_shows, which
    does the actual episode selection. `channel_id`/`cursor_data=None`
    preserve today's exact behavior (no sequential show can resolve a
    "next episode" without a channel/cursor context, so every show falls
    back to plan_rotate_shows' existing default queue exactly as before
    this phase).

    Delegates entirely to autofill_planner.plan_rotate_shows so there is
    exactly one show-rotation-for-a-gap implementation.
    """
    registry = show_identity_registry if isinstance(show_identity_registry, dict) else empty_registry()
    canonical_show_keys = canonicalize_show_keys(block.show_keys, registry)
    show_behaviors = {key: show_behavior_for(key, registry) for key in canonical_show_keys}
    last_aired_path_by_show = {}
    if channel_id is not None and cursor_data is not None:
        for key, behavior in show_behaviors.items():
            if behavior == "sequential":
                last_aired_path_by_show[key] = last_aired_path_for(cursor_data, channel_id, key, show_identity_registry=registry)
    return plan_rotate_shows(
        items,
        canonical_show_keys,
        gap_start,
        gap_duration,
        seed=seed,
        show_behaviors=show_behaviors,
        last_aired_path_by_show=last_aired_path_by_show,
    )

"""Canonical show identity registry: persistence, resolution, and the
correction mutators (Rename Show as of Phase 5.5.3; Merge Shows and
Folder Rule creation are still not implemented). This module is the
single owner of "what show does this file actually belong to" once a
user has corrected it; for every show nobody has touched, it still
behaves exactly like mediawave.local_media.metadata_lookup_key.

Identity model: `show_key` keeps its existing name and meaning as "the
canonical identity of a show" -- for an untouched show it is still
exactly local_media.metadata_lookup_key()'s output (`tv::...`/
`movie::...`); for a corrected show it is a registry-minted
`show_<uuid4 hex>` token instead. Consumers are never meant to tell the
two forms apart -- both are just opaque strings. The two forms can never
collide: metadata_lookup_key never produces anything starting with
"show_", and mint_show_key never produces anything starting with "tv::"
or "movie::".

`raw_key_to_show_key` is the alias table: any raw metadata_lookup_key
string that has been folded into a corrected show maps here to that
show's `show_key`. A raw key with no entry here has not been corrected,
and resolve_show_identity falls back to using it as its own show_key --
this is what makes an untouched library behave identically to today,
with zero migration required.

Mirrors autofill_cursor.py's and programming_blocks.py's persistence
shape exactly (schema version, normalize-with-ok, atomic tempfile+
os.replace write) -- one more file in the same persistence family, not a
new pattern. Suggested sidecar filename: schedule_show_identity.json,
alongside schedule_programming_blocks.json and schedule_autofill_cursor.
json -- this module takes `path` as a parameter rather than hardcoding
one, same as its siblings.

`external_ids`, `behavior`, and `correction_source` are reserved fields
on a show record: accepted and round-tripped by normalize_registry if
present, but nothing in this step reads or writes them. They exist now so
a future TMDB/TVmaze match, a show-level Auto-Fill behavior override, or
a "how was this show corrected" audit trail don't require a schema
version bump later.
"""

import json
import os
import tempfile
import uuid

from .local_media import metadata_lookup_key

SHOW_IDENTITY_VERSION = 1


def empty_registry():
    return {
        "version": SHOW_IDENTITY_VERSION,
        "shows": {},
        "raw_key_to_show_key": {},
        "folder_rules": {},
    }


def mint_show_key():
    """A fresh opaque canonical show_key for a newly-corrected show.
    Never produced by local_media.metadata_lookup_key, so it can never
    collide with a provisional (uncorrected) show_key.
    """
    return f"show_{uuid.uuid4().hex}"


def create_registry_record(display_name, aliases=None, folder_rule_ids=None, now=None):
    """A single, not-yet-inserted show record -- pure factory, no registry
    mutation. Callers (rename/merge, in a later step) are responsible for
    picking the show_key (via mint_show_key, or an existing one when
    absorbing more aliases into an already-corrected show) and inserting
    the record into a registry dict themselves.
    """
    timestamp = float(now) if now is not None else 0.0
    seen = set()
    clean_aliases = []
    for alias in aliases or []:
        alias = str(alias or "").strip()
        if alias and alias not in seen:
            seen.add(alias)
            clean_aliases.append(alias)
    return {
        "display_name": str(display_name or "").strip(),
        "aliases": clean_aliases,
        "folder_rules": [str(rule_id) for rule_id in (folder_rule_ids or []) if str(rule_id or "").strip()],
        "external_ids": {},
        "behavior": None,
        "correction_source": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _normalize_show_entry(entry):
    if not isinstance(entry, dict):
        return None
    display_name = str(entry.get("display_name", "") or "").strip()

    seen = set()
    aliases = []
    for alias in entry.get("aliases") or []:
        alias = str(alias or "").strip()
        if alias and alias not in seen:
            seen.add(alias)
            aliases.append(alias)

    seen_rules = set()
    folder_rules = []
    for rule_id in entry.get("folder_rules") or []:
        rule_id = str(rule_id or "").strip()
        if rule_id and rule_id not in seen_rules:
            seen_rules.add(rule_id)
            folder_rules.append(rule_id)

    external_ids = entry.get("external_ids")
    external_ids = dict(external_ids) if isinstance(external_ids, dict) else {}

    def _optional_float(value):
        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    return {
        "display_name": display_name,
        "aliases": aliases,
        "folder_rules": folder_rules,
        "external_ids": external_ids,
        "behavior": entry.get("behavior"),
        "correction_source": entry.get("correction_source"),
        "created_at": _optional_float(entry.get("created_at")),
        "updated_at": _optional_float(entry.get("updated_at")),
    }


def _normalize_folder_rule_entry(rule_id, entry, known_show_keys):
    if not isinstance(entry, dict):
        return None
    show_key = str(entry.get("show_key", "") or "").strip()
    root_relative_path = str(entry.get("root_relative_path", "") or "").strip()
    if not show_key or show_key not in known_show_keys or not root_relative_path:
        return None
    try:
        created_at = float(entry.get("created_at", 0) or 0)
    except (TypeError, ValueError):
        created_at = 0.0
    return {
        "show_key": show_key,
        "root_relative_path": root_relative_path,
        "channel_id": str(entry.get("channel_id", "") or ""),
        "created_at": created_at,
    }


def normalize_registry(data):
    """(normalized_data, ok) -- ok is False only when the payload is
    malformed at the top level (not a dict, bad/future version, or one of
    "shows"/"raw_key_to_show_key"/"folder_rules" isn't the right container
    type), so a caller can keep its previous in-memory state rather than
    silently discarding every saved correction. Individual malformed
    entries within an otherwise-valid file are dropped, not treated as a
    whole-file failure -- one corrupt show record shouldn't cost every
    other correction. Referential integrity is enforced: alias entries and
    folder rules pointing at a show_key that doesn't exist in "shows" are
    dropped, since they can never resolve to anything.
    """
    if not isinstance(data, dict):
        return empty_registry(), False
    try:
        version = int(data.get("version", 0) or 0)
    except (TypeError, ValueError):
        return empty_registry(), False
    if version < 1 or version > SHOW_IDENTITY_VERSION:
        return empty_registry(), False

    raw_shows = data.get("shows")
    if not isinstance(raw_shows, dict):
        return empty_registry(), False
    shows = {}
    for show_key, entry in raw_shows.items():
        show_key = str(show_key or "").strip()
        normalized = _normalize_show_entry(entry)
        if not show_key or normalized is None:
            continue
        shows[show_key] = normalized

    raw_aliases = data.get("raw_key_to_show_key")
    if not isinstance(raw_aliases, dict):
        return empty_registry(), False
    raw_key_to_show_key = {}
    for raw_key, show_key in raw_aliases.items():
        raw_key = str(raw_key or "").strip()
        show_key = str(show_key or "").strip()
        if raw_key and show_key and show_key in shows:
            raw_key_to_show_key[raw_key] = show_key

    raw_folder_rules = data.get("folder_rules")
    if not isinstance(raw_folder_rules, dict):
        return empty_registry(), False
    folder_rules = {}
    for rule_id, entry in raw_folder_rules.items():
        rule_id = str(rule_id or "").strip()
        normalized_rule = _normalize_folder_rule_entry(rule_id, entry, shows)
        if rule_id and normalized_rule is not None:
            folder_rules[rule_id] = normalized_rule

    return {
        "version": SHOW_IDENTITY_VERSION,
        "shows": shows,
        "raw_key_to_show_key": raw_key_to_show_key,
        "folder_rules": folder_rules,
    }, True


def load_show_identity_registry(path):
    """Load and validate the show identity registry file. Missing or
    malformed files yield an empty registry -- the file itself is never
    rewritten or deleted here, matching autofill_cursor.py's/
    programming_blocks.py's load contract. A malformed file means "no
    corrections known", not a crash: every show simply resolves as
    provisional, which is identical to today's behavior.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return empty_registry()
    normalized, _ok = normalize_registry(data)
    return normalized


def save_show_identity_registry(path, data):
    """Atomically persist the registry (tempfile write + os.replace, same
    as autofill_cursor.py/programming_blocks.py). Returns (ok, error). A
    structurally invalid payload is refused outright, leaving the existing
    file on disk untouched.
    """
    normalized, ok = normalize_registry(data)
    if not ok:
        return False, "The show identity data was not in a valid format, so the existing file was left unchanged."
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".schedule_show_identity_", suffix=".tmp", dir=directory)
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
        return False, f"The show identity file could not be written ({error.strerror or error})."
    return True, ""


def _normalized_path_segments(path):
    normalized = os.path.normpath(str(path or "")).replace("\\", "/")
    return [segment for segment in normalized.split("/") if segment]


def _matching_folder_rule(path, folder_rules, channel_id=None):
    """The folder rule (if any) whose root_relative_path appears as a
    contiguous, segment-bounded run within `path`, matching by segment-
    bounded substring so a rule never accidentally matches a sibling
    folder that merely shares a prefix (e.g. "Moral Orel" does not match
    "Moral Orel Extras") and nested season folders still match (a rule's
    segments only need to appear as a contiguous run SOMEWHERE in the
    path, not be the whole thing). Longest root_relative_path wins when
    more than one rule matches.

    `channel_id`: when given (real callers -- build_picker_catalog --
    always have one), a rule is only eligible if its own stored
    `channel_id` is empty/unset OR matches exactly -- a rule never leaks
    into another channel's files that happen to share a relative path.
    When `channel_id` is None (the default, used by callers/tests that
    don't have channel context), channel scoping is skipped entirely --
    permissive, matching this function's original pre-Phase-5.5.5
    behavior, so existing callers/tests that never passed a channel_id
    are unaffected.
    """
    if not folder_rules:
        return None
    path_segments = _normalized_path_segments(path)
    best = None
    best_len = -1
    for rule in folder_rules.values():
        if channel_id is not None:
            rule_channel = rule.get("channel_id")
            if rule_channel and rule_channel != channel_id:
                continue
        rule_segments = _normalized_path_segments(rule.get("root_relative_path", ""))
        if not rule_segments:
            continue
        span = len(rule_segments)
        for start in range(0, len(path_segments) - span + 1):
            if path_segments[start:start + span] == rule_segments:
                if span > best_len:
                    best = rule
                    best_len = span
                break
    return best


def canonical_show_key(value, registry):
    """`value` (a raw provisional key, e.g. `tv::moral orel`, OR an
    already-canonical `show_<uuid>` key) resolved to its CURRENT canonical
    show_key via `registry["raw_key_to_show_key"]`. A key with no alias
    entry is returned unchanged -- either it's already canonical, or it's
    an uncorrected provisional key, which is its own canonical identity
    (Phase 5.5.2 step 1's core rule). Never mutates `registry`.

    `raw_key_to_show_key` entries always point directly at a real show's
    own show_key (normalize_registry enforces this), so one hop is all a
    well-formed registry ever needs. The loop below is defense-in-depth
    for a registry that was NOT produced by normalize_registry (e.g. a
    hand-built dict in a test, or a future bug) -- it caps iterations and
    stops on a repeated value so a malformed multi-hop chain can never
    spin forever.
    """
    value = str(value or "")
    if not value:
        return value
    raw_key_to_show_key = registry.get("raw_key_to_show_key") if isinstance(registry, dict) else None
    if not isinstance(raw_key_to_show_key, dict):
        return value
    seen = {value}
    current = value
    for _ in range(len(raw_key_to_show_key) + 1):
        next_key = raw_key_to_show_key.get(current)
        if not next_key or next_key in seen:
            break
        current = next_key
        seen.add(current)
    return current


def canonicalize_show_keys(values, registry):
    """`values` (e.g. a Programming Block's stored show_keys) resolved
    through canonical_show_key, deduplicated while preserving FIRST
    occurrence order -- so three raw aliases of one merged show collapse
    to that show's canonical key appearing once, at the position its
    first alias held. Never mutates `values` or `registry`.
    """
    result = []
    seen = set()
    for value in values or []:
        key = canonical_show_key(value, registry)
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def aliases_for_show_key(show_key, registry):
    """The raw legacy keys registered as aliases of `show_key` (an
    already-canonical show_<uuid> key), in the registry's own stored
    order -- deterministic, since normalize_registry/create_registry_
    record both already dedupe and preserve insertion order. Empty for an
    unknown or provisional show_key (nothing to alias-search for an
    uncorrected show). Never mutates `registry`.
    """
    shows = registry.get("shows") if isinstance(registry, dict) else None
    if not isinstance(shows, dict):
        return []
    record = shows.get(show_key)
    if not isinstance(record, dict):
        return []
    aliases = record.get("aliases")
    return list(aliases) if isinstance(aliases, list) else []


def group_catalog_by_show(items):
    """{show_key: {show_key, title, episodes, episode_count, season_count,
    raw_aliases_present, source}} for every TV catalog item that carries a
    `show_key` -- one entry per distinct canonical show. Movies and
    anything without a `show_key` aren't shows and never appear here.

    Replaces put_on_air_picker.group_shows_for_picker and autofill_dialog.
    group_shows, which duplicated this exact grouping independently; both
    are now thin callers of this one pure helper. `episodes` is unordered
    (same as the functions it replaces); callers sort with
    episode_sort_key. Pure and Qt/filesystem-free so it can be tested and
    reused without either.

    `title` prefers the item's `show_display_name` (a registry correction)
    when non-empty, else falls back to the item's own `title` -- so an
    uncorrected show groups exactly as group_shows_for_picker/group_shows
    always did, and only a real correction changes the group's title.
    `source` is "override" if any item in the group resolved via the
    registry (an alias or folder rule), else "parsed". `raw_aliases_present`
    collects every distinct pre-correction key represented in the group,
    for a future "this show combines N sources" UI affordance.

    Never mutates `items`. Output order matches first-seen order in
    `items`, same as the dict-insertion order the two functions this
    replaces already produced.
    """
    groups = {}
    order = []
    for item in items or []:
        if item.get("media_type") != "tv":
            continue
        show_key = item.get("show_key")
        if not show_key:
            continue
        if show_key not in groups:
            groups[show_key] = {
                "show_key": show_key,
                "title": item.get("show_display_name") or item.get("title", ""),
                "episodes": [],
                "raw_aliases_present": set(),
                "source": "parsed",
            }
            order.append(show_key)
        group = groups[show_key]
        group["episodes"].append(item)
        raw_show_key = item.get("raw_show_key")
        if raw_show_key:
            group["raw_aliases_present"].add(raw_show_key)
        if item.get("show_identity_source") == "override":
            group["source"] = "override"

    result = {}
    for show_key in order:
        group = groups[show_key]
        seasons = {ep.get("season_number") for ep in group["episodes"] if ep.get("season_number") is not None}
        group["episode_count"] = len(group["episodes"])
        group["season_count"] = len(seasons) if seasons else None
        result[show_key] = group
    return result


def resolve_show_identity(path, parsed_media, registry, channel_id=None):
    """The canonical identity for one media file, given its already-
    parsed local_media.parse_local_media() result and the loaded show
    identity registry. Never mutates `registry`. Returns:

        show_key      -- opaque identity; provisional (a raw
                          metadata_lookup_key) if uncorrected, or a
                          registry-minted show_<uuid> if corrected
        display_name  -- the show's display name (parsed show_name if
                          uncorrected, the registry's display_name if
                          corrected)
        raw_show_key  -- always local_media.metadata_lookup_key()'s
                          output for this file, regardless of correction
                          state -- callers doing alias bookkeeping need
                          this even when a folder rule or existing alias
                          already resolved a different show_key
        source        -- "override" if a folder rule or alias resolved
                          this, else "parsed"
        media_type    -- "tv" or "movie". From `parsed_media` UNLESS a
                          folder rule matched (Phase 5.5.5, Treat Folder
                          as Show): folder-as-show is TV-only by design
                          (an episode with no season/episode numbers is
                          still an episode), so a folder-rule match
                          always reports "tv" here regardless of what
                          parse_local_media guessed for this individual
                          file (often "movie", since that's exactly the
                          misclassification this feature corrects). This
                          NEVER touches parse_local_media's own output or
                          the file on disk -- it's scheduling/catalog
                          metadata only, read by whichever caller trusts
                          this return value (see build_picker_catalog).

    `channel_id`: forwarded to _matching_folder_rule's channel scoping --
    see its own docstring. Optional/None preserves this function's
    original permissive behavior for callers with no channel context.

    For an uncorrected show this is bit-for-bit equivalent to calling
    metadata_lookup_key() directly today -- that equivalence is what
    keeps every existing library's behavior unchanged.
    """
    parsed_media = parsed_media or {}
    media_type = parsed_media.get("media_type", "tv")
    raw_show_key = metadata_lookup_key(path, parsed_media)
    shows = registry.get("shows", {}) if isinstance(registry, dict) else {}
    folder_rules = registry.get("folder_rules", {}) if isinstance(registry, dict) else {}
    raw_key_to_show_key = registry.get("raw_key_to_show_key", {}) if isinstance(registry, dict) else {}

    matched_rule = _matching_folder_rule(path, folder_rules, channel_id=channel_id)
    if matched_rule is not None:
        show_key = matched_rule["show_key"]
        show_record = shows.get(show_key)
        if show_record is not None:
            return {
                "show_key": show_key,
                "display_name": show_record["display_name"] or parsed_media.get("show_name", ""),
                "raw_show_key": raw_show_key,
                "source": "override",
                "media_type": "tv",
            }

    aliased_show_key = raw_key_to_show_key.get(raw_show_key)
    if aliased_show_key is not None:
        show_record = shows.get(aliased_show_key)
        if show_record is not None:
            return {
                "show_key": aliased_show_key,
                "display_name": show_record["display_name"] or parsed_media.get("show_name", ""),
                "raw_show_key": raw_show_key,
                "source": "override",
                "media_type": media_type,
            }

    return {
        "show_key": raw_show_key,
        "display_name": parsed_media.get("show_name", ""),
        "raw_show_key": raw_show_key,
        "source": "parsed",
        "media_type": media_type,
    }


def rename_show(registry, show_key, new_display_name, now=None):
    """(new_registry, canonical_show_key) -- Rename Show (Phase 5.5.3):
    the user-declared correction of one show's display name. Never
    mutates `registry`; always returns a freshly normalized registry
    value, so callers can pass the result straight to
    save_show_identity_registry.

    `show_key` may be either a still-provisional raw key (e.g.
    `tv::moral orel 1`) or an already-canonical `show_<uuid>` key -- both
    forms resolve through canonical_show_key first, so renaming via any
    known alias of an already-corrected show reaches the SAME record
    rather than minting a duplicate.

    Provisional show_key (first correction): mints one new opaque
    show_<uuid> canonical key, creates its registry record with
    `show_key` as its sole alias, sets the corrected display_name, and
    sets correction_source="renamed".

    Already-canonical show_key (renaming a show that was already
    corrected, whether by a prior rename or -- once it exists -- a merge
    or folder rule): the canonical key, aliases, folder_rules,
    external_ids, behavior, and created_at are all preserved untouched;
    only display_name and updated_at change. correction_source is
    DELIBERATELY left as whatever it already was, not overwritten to
    "renamed" -- a show whose canonical identity came from a merge or
    folder rule is still fundamentally a merged/folder show even after
    someone also renames it, and overwriting that would lose real
    provenance for no benefit (nothing currently reads correction_source
    to change behavior; it exists purely as a future-facing audit trail,
    so misattributing it would be a pure loss).

    Raises ValueError for an empty/whitespace-only `new_display_name` --
    a defensive backstop; the Rename Show dialog is expected to validate
    (and trim) before ever calling this.
    """
    display_name = str(new_display_name or "").strip()
    if not display_name:
        raise ValueError("new_display_name must not be empty")
    if not show_key:
        # Defense-in-depth: a falsy show_key (empty string, None, or a
        # bool -- exactly what a caller-side signal/argument mismatch
        # produces, see programming_block_dialog.py's overflow-menu
        # wiring history) must never silently mint a garbage show record
        # aliased to "False"/"None"/"". Fail loudly instead.
        raise ValueError("show_key must not be empty")

    normalized, _ok = normalize_registry(registry if isinstance(registry, dict) else empty_registry())
    timestamp = float(now) if now is not None else 0.0

    resolved_key = canonical_show_key(show_key, normalized)
    shows = dict(normalized["shows"])
    raw_key_to_show_key = dict(normalized["raw_key_to_show_key"])

    if resolved_key in shows:
        record = dict(shows[resolved_key])
        record["display_name"] = display_name
        record["updated_at"] = timestamp
        shows[resolved_key] = record
        canonical_key = resolved_key
    else:
        canonical_key = mint_show_key()
        record = create_registry_record(display_name, aliases=[str(show_key)], now=timestamp)
        record["correction_source"] = "renamed"
        shows[canonical_key] = record
        raw_key_to_show_key[str(show_key)] = canonical_key

    new_registry = {
        "version": SHOW_IDENTITY_VERSION,
        "shows": shows,
        "raw_key_to_show_key": raw_key_to_show_key,
        "folder_rules": dict(normalized["folder_rules"]),
    }
    normalized_result, _ok = normalize_registry(new_registry)
    return normalized_result, canonical_key


SHOW_BEHAVIOR_SEQUENTIAL = "sequential"
SHOW_BEHAVIOR_RANDOM = "random"
_VALID_SHOW_BEHAVIORS = {SHOW_BEHAVIOR_SEQUENTIAL, SHOW_BEHAVIOR_RANDOM}


def set_show_behavior(registry, show_key, behavior, *, display_name=None, now=None):
    """(new_registry, canonical_show_key) -- persist a show's Episode
    Behavior override. Never mutates `registry`.

    `behavior` must be None (Use Channel Default -- clears any existing
    override rather than storing a sentinel for it), "sequential", or
    "random"; anything else raises ValueError. Channel Default is
    represented by the ABSENCE of a value, not a stored "channel_default"
    string, so every scheduling context's own current default behavior
    naturally applies wherever nothing overrides it.

    `show_key` may be a still-provisional raw key or an already-canonical
    show_<uuid> key, exactly like rename_show -- both resolve through
    canonical_show_key first.

    Provisional show_key (first correction of any kind on this show):
    mints one new canonical show_<uuid> key, creates its registry record
    with `show_key` as its sole alias, sets `behavior`, and uses
    `display_name` if given (falling back to the raw key itself, since a
    provisional show has no other name on record yet).

    Already-canonical show_key: canonical key, aliases, folder_rules,
    external_ids, display_name, and correction_source are all preserved
    untouched (display_name is NOT overwritten by the `display_name`
    param here -- unlike rename_show, this is not a rename; `display_name`
    only seeds a brand-new record's name); only `behavior` and
    `updated_at` change. `correction_source` is left as whatever it
    already was, same reasoning as rename_show -- setting a behavior is
    not itself a naming/grouping correction.
    """
    if behavior is not None and behavior not in _VALID_SHOW_BEHAVIORS:
        raise ValueError(f"invalid behavior: {behavior!r}")
    if not show_key:
        raise ValueError("show_key must not be empty")

    normalized, _ok = normalize_registry(registry if isinstance(registry, dict) else empty_registry())
    timestamp = float(now) if now is not None else 0.0

    resolved_key = canonical_show_key(show_key, normalized)
    shows = dict(normalized["shows"])

    if resolved_key in shows:
        record = dict(shows[resolved_key])
        record["behavior"] = behavior
        record["updated_at"] = timestamp
        shows[resolved_key] = record
        canonical_key = resolved_key
    else:
        canonical_key = mint_show_key()
        name = str(display_name or "").strip() or str(show_key)
        record = create_registry_record(name, aliases=[str(show_key)], now=timestamp)
        record["behavior"] = behavior
        shows[canonical_key] = record
        raw_key_to_show_key = dict(normalized["raw_key_to_show_key"])
        raw_key_to_show_key[str(show_key)] = canonical_key
        new_registry = {
            "version": SHOW_IDENTITY_VERSION,
            "shows": shows,
            "raw_key_to_show_key": raw_key_to_show_key,
            "folder_rules": dict(normalized["folder_rules"]),
        }
        normalized_result, _ok = normalize_registry(new_registry)
        return normalized_result, canonical_key

    new_registry = {
        "version": SHOW_IDENTITY_VERSION,
        "shows": shows,
        "raw_key_to_show_key": dict(normalized["raw_key_to_show_key"]),
        "folder_rules": dict(normalized["folder_rules"]),
    }
    normalized_result, _ok = normalize_registry(new_registry)
    return normalized_result, canonical_key


def show_behavior_for(show_key, registry):
    """The persisted Episode Behavior for `show_key` -- None (Use Channel
    Default) unless an explicit "sequential"/"random" override is on
    record. Resolves aliases/canonical redirects first via
    canonical_show_key, so this works for a raw legacy key, an absorbed
    merged-away canonical key, or the show's current canonical key alike.

    Fails open (returns None) on any malformed/dangling state -- an
    unknown show_key, a non-dict registry, or a registry whose resolved
    show_key has no record -- so a corrupted or stale registry can never
    make scheduling do something other than fall back to Channel Default.
    """
    if not show_key or not isinstance(registry, dict):
        return None
    resolved_key = canonical_show_key(show_key, registry)
    shows = registry.get("shows")
    if not isinstance(shows, dict):
        return None
    record = shows.get(resolved_key)
    if not isinstance(record, dict):
        return None
    behavior = record.get("behavior")
    return behavior if behavior in _VALID_SHOW_BEHAVIORS else None


def merge_shows(registry, show_keys, display_name=None, now=None):
    """(new_registry, survivor_show_key, redirect_map, conflicts) -- Merge
    Shows (Phase 5.5.4): combines several incorrectly-split show groups
    into one canonical show. Never mutates `registry`; always returns a
    freshly normalized registry value.

    `show_keys` may mix provisional raw keys and already-canonical
    show_<uuid> keys in any combination. Each is resolved through
    canonical_show_key and deduplicated first -- fewer than two DISTINCT
    resolved canonical identities raises ValueError (nothing to merge).

    SURVIVOR SELECTION (deterministic): the first of the resolved,
    deduplicated keys (in the order `show_keys` was given) that already
    has a persisted registry record wins. If none of the resolved keys
    has a persisted record (every input is still provisional), one new
    show_<uuid> key is minted.

    ABSORBED CANONICAL KEYS -- REDIRECT COMPATIBILITY: when one of the
    OTHER resolved keys already has its own persisted record (e.g. the
    user is merging two shows that were each already renamed
    separately), that record is absorbed and then REMOVED from `shows`
    -- but the absorbed key itself is added to the survivor's `aliases`
    list AND repointed in `raw_key_to_show_key` to the survivor. This
    reuses the exact same alias-redirect mechanism raw legacy keys
    already rely on (`raw_key_to_show_key` doesn't care whether a key
    looks like `tv::...` or `show_<uuid>...` -- it's just a string key
    pointing at a real show record), so canonical_show_key/aliases_for_
    show_key/last_aired_path_for all keep working for an absorbed
    canonical key with ZERO new resolution logic. An absorbed key can
    never become permanently unresolvable: it either still exists as a
    real show record (untouched, if it wasn't selected for this merge)
    or redirects to the survivor. Any raw key that used to point AT an
    absorbed record is also repointed straight to the survivor, so a
    Programming Block/cursor row saved under any prior generation of
    alias -- legacy raw key, first-merge survivor, second-merge input --
    all still resolve correctly after however many merges have happened.

    DISPLAY METADATA: `aliases` and `folder_rules` are unioned and
    deduplicated across every absorbed record (plus each raw provisional
    input key, which becomes a plain alias). `external_ids`: the
    survivor's own value for a given provider always wins on conflict;
    a conflicting absorbed value is recorded in the returned `conflicts`
    dict rather than silently dropped. `behavior`: same rule -- survivor
    wins, conflicts are reported, nothing is silently combined (Show
    Behavior UI doesn't exist yet, so this is future-facing only).
    `created_at` is the survivor's own (or the merge time, if the
    survivor was just minted); `updated_at` becomes the merge time.
    `correction_source`: preserved if the survivor already has one
    (e.g. "renamed" or a future "folder_rule"), else set to "merged" --
    a survivor's own prior meaningful origin is never overwritten just
    because it later absorbs other shows.

    `display_name`: the caller-supplied final name (trimmed; raises
    ValueError if given but empty after trimming). If omitted entirely
    (None), falls back to the survivor's current display_name, or the
    first alias, or the survivor key itself -- callers that only care
    about the merge mechanics (most pure-helper tests) don't need to
    supply one.

    `redirect_map`: {old_key: survivor_show_key} for every literal input
    in `show_keys` PLUS every absorbed canonical key discovered -- a
    caller (the Programming Block dialog) uses this to remap its own
    in-memory catalog items/`_included` selections in one pass without
    needing to re-derive what got absorbed.

    `conflicts`: {"external_ids": [...], "behavior": [...]} -- non-empty
    only when a genuine value conflict was discarded in the survivor's
    favor; empty lists otherwise. Nothing currently reads this; it exists
    so a future correction UI can surface it.
    """
    normalized, _ok = normalize_registry(registry if isinstance(registry, dict) else empty_registry())
    timestamp = float(now) if now is not None else 0.0

    inputs = [str(key) for key in (show_keys or []) if str(key or "").strip()]

    shows = dict(normalized["shows"])
    raw_key_to_show_key = dict(normalized["raw_key_to_show_key"])
    folder_rules_table = dict(normalized["folder_rules"])

    resolved = []
    seen_resolved = set()
    for key in inputs:
        canonical = canonical_show_key(key, normalized)
        if canonical not in seen_resolved:
            seen_resolved.add(canonical)
            resolved.append(canonical)

    if len(resolved) < 2:
        raise ValueError("merge_shows requires at least two distinct canonical shows")

    survivor_key = next((key for key in resolved if key in shows), None)
    if survivor_key is None:
        survivor_key = mint_show_key()

    survivor_record = dict(shows[survivor_key]) if survivor_key in shows else create_registry_record("", now=timestamp)
    union_aliases = list(survivor_record.get("aliases") or [])
    union_folder_rule_ids = list(survivor_record.get("folder_rules") or [])
    external_ids = dict(survivor_record.get("external_ids") or {})
    behavior = survivor_record.get("behavior")
    conflicts = {"external_ids": [], "behavior": []}

    def _absorb_metadata(record):
        nonlocal behavior
        for alias in record.get("aliases") or []:
            if alias not in union_aliases:
                union_aliases.append(alias)
        for rule_id in record.get("folder_rules") or []:
            if rule_id not in union_folder_rule_ids:
                union_folder_rule_ids.append(rule_id)
        for provider, value in (record.get("external_ids") or {}).items():
            if provider in external_ids:
                if external_ids[provider] != value:
                    conflicts["external_ids"].append({"provider": provider, "kept": external_ids[provider], "discarded": value})
            else:
                external_ids[provider] = value
        record_behavior = record.get("behavior")
        if record_behavior is not None:
            if behavior is None:
                behavior = record_behavior
            elif behavior != record_behavior:
                conflicts["behavior"].append(record_behavior)

    redirect_map = {key: survivor_key for key in inputs}
    absorbed_keys = [key for key in resolved if key != survivor_key]
    for absorbed_key in absorbed_keys:
        if absorbed_key in shows:
            _absorb_metadata(shows[absorbed_key])
            del shows[absorbed_key]
        if absorbed_key not in union_aliases:
            union_aliases.append(absorbed_key)
        redirect_map[absorbed_key] = survivor_key
        for raw_key, target in list(raw_key_to_show_key.items()):
            if target == absorbed_key:
                raw_key_to_show_key[raw_key] = survivor_key

    if display_name is not None:
        final_name = str(display_name).strip()
        if not final_name:
            raise ValueError("display_name must not be empty")
    else:
        final_name = survivor_record.get("display_name") or (union_aliases[0] if union_aliases else survivor_key)

    merged_record = {
        "display_name": final_name,
        "aliases": union_aliases,
        "folder_rules": union_folder_rule_ids,
        "external_ids": external_ids,
        "behavior": behavior,
        "correction_source": survivor_record.get("correction_source") or "merged",
        "created_at": survivor_record.get("created_at", timestamp),
        "updated_at": timestamp,
    }
    shows[survivor_key] = merged_record

    for alias in union_aliases:
        raw_key_to_show_key[alias] = survivor_key

    for rule_id, rule in list(folder_rules_table.items()):
        if rule.get("show_key") in absorbed_keys:
            folder_rules_table[rule_id] = dict(rule, show_key=survivor_key)

    new_registry = {
        "version": SHOW_IDENTITY_VERSION,
        "shows": shows,
        "raw_key_to_show_key": raw_key_to_show_key,
        "folder_rules": folder_rules_table,
    }
    normalized_result, _ok = normalize_registry(new_registry)
    return normalized_result, survivor_key, redirect_map, conflicts


def _catalog_relative_folder_path(catalog_root, folder_path):
    """`folder_path` expressed relative to `catalog_root`, POSIX-
    normalized (forward slashes, no leading slash, no drive letter) --
    the same identifier shape _matching_folder_rule already understands.
    Pure string math, no filesystem access (no realpath/exists/os.stat)
    -- this is deliberate: it's what makes the rule survive a NAS/
    external-drive remount that changes the absolute mount point but
    keeps the relative layout the same, and it's what keeps this
    testable without real folders on disk.

    Returns None when `folder_path` is not under `catalog_root` (a
    catalog-relative path can't be derived -- e.g. the folder is outside
    the configured channel root), or when `folder_path` equals
    `catalog_root` itself (there is no relative subfolder to name a rule
    after). Windows backslashes are normalized to forward slashes before
    comparison, so this handles Windows/macOS/Linux path separators
    consistently.
    """
    root_norm = str(catalog_root or "").replace("\\", "/").rstrip("/")
    path_norm = str(folder_path or "").replace("\\", "/").rstrip("/")
    if not root_norm or not path_norm:
        return None
    if path_norm == root_norm:
        return None
    prefix = root_norm + "/"
    if not path_norm.startswith(prefix):
        return None
    relative = path_norm[len(prefix):].strip("/")
    return relative or None


def add_folder_show_rule(registry, *, channel_id, catalog_root, folder_path, display_name, target_show_key=None, provisional_raw_keys=None, now=None):
    """(new_registry, canonical_show_key, folder_rule_id, redirect_map)
    -- Treat Folder as Show (Phase 5.5.5): declares that every compatible
    video under `folder_path` belongs to one show, without touching
    parse_local_media's per-file inference or any file/folder on disk.
    Never mutates `registry`.

    `folder_path`/`catalog_root` are converted to the catalog-root-
    relative, POSIX-normalized identifier resolve_show_identity's folder-
    rule matching already understands (_catalog_relative_folder_path) --
    raises ValueError if that can't be derived (folder outside the
    catalog root, or equal to the root itself), or if `display_name` is
    empty after trimming, or if a folder rule already exists for this
    exact (channel_id, relative path) -- creating a second rule at the
    same location is never correct; the caller should rename the
    existing show or pick a different folder instead.

    `target_show_key`: pass an ALREADY-CANONICAL show_key to attach this
    rule to an existing corrected show -- the "this folder's compatible
    items already resolve to exactly one already-corrected show" case.
    Same semantics as rename_show's already-canonical branch: aliases,
    other folder_rules, external_ids, behavior, and created_at are all
    preserved; only display_name/updated_at change, and correction_
    source is set to "folder_rule" ONLY if the record didn't already
    have one (a show's real prior origin -- "renamed", "merged" -- is
    never overwritten just because a folder rule later also applies to
    it). Omit (None) to mint a brand-new canonical show instead
    (correction_source="folder_rule" unconditionally, since there's
    nothing to preserve).

    AMBIGUITY IS NOT DECIDED HERE: this helper only ever attaches ONE
    rule to ONE show. If a folder's current catalog items already
    resolve to MORE THAN ONE distinct already-corrected show, the CALLER
    (the Treat Folder as Show dialog) must detect that itself -- by
    resolving the folder's items through resolve_show_identity first --
    and refuse to proceed (a calm warning, "use Merge Shows first")
    rather than ever passing an ambiguous target_show_key here. This
    keeps Treat Folder as Show from ever silently performing a merge.

    `provisional_raw_keys`: raw metadata_lookup_key strings the caller
    found among the folder's current, still-uncorrected items -- each
    becomes an alias of the resulting canonical show (mirroring every
    other correction path's "the corrected raw key becomes an alias"
    rule), so a Programming Block/cursor row already saved under one of
    them keeps resolving. `redirect_map` reports {raw_key: canonical_
    show_key} for each of these, for a caller to remap its own in-memory
    catalog/selection state in one pass, same shape merge_shows returns.
    """
    display = str(display_name or "").strip()
    if not display:
        raise ValueError("display_name must not be empty")

    relative_path = _catalog_relative_folder_path(catalog_root, folder_path)
    if not relative_path:
        raise ValueError("folder_path must be a subfolder of catalog_root")

    channel = str(channel_id or "")
    normalized, _ok = normalize_registry(registry if isinstance(registry, dict) else empty_registry())
    timestamp = float(now) if now is not None else 0.0

    shows = dict(normalized["shows"])
    raw_key_to_show_key = dict(normalized["raw_key_to_show_key"])
    folder_rules_table = dict(normalized["folder_rules"])

    for existing_rule in folder_rules_table.values():
        if existing_rule.get("channel_id") == channel and existing_rule.get("root_relative_path") == relative_path:
            raise ValueError("A folder rule already exists for this folder")

    provisional_keys = [str(key) for key in (provisional_raw_keys or []) if str(key or "").strip()]
    redirect_map = {}

    if target_show_key and target_show_key in shows:
        canonical_key = target_show_key
        record = dict(shows[canonical_key])
        record["display_name"] = display
        record["updated_at"] = timestamp
        if not record.get("correction_source"):
            record["correction_source"] = "folder_rule"
        aliases = list(record.get("aliases") or [])
        for key in provisional_keys:
            if key not in aliases:
                aliases.append(key)
            redirect_map[key] = canonical_key
        record["aliases"] = aliases
    else:
        canonical_key = mint_show_key()
        aliases = list(dict.fromkeys(provisional_keys))
        record = create_registry_record(display, aliases=aliases, now=timestamp)
        record["correction_source"] = "folder_rule"
        for key in provisional_keys:
            redirect_map[key] = canonical_key

    for alias in aliases:
        raw_key_to_show_key[alias] = canonical_key

    rule_id = f"rule_{uuid.uuid4().hex}"
    folder_rules_table[rule_id] = {
        "show_key": canonical_key,
        "root_relative_path": relative_path,
        "channel_id": channel,
        "created_at": timestamp,
    }
    rule_ids = list(record.get("folder_rules") or [])
    if rule_id not in rule_ids:
        rule_ids.append(rule_id)
    record["folder_rules"] = rule_ids
    shows[canonical_key] = record

    new_registry = {
        "version": SHOW_IDENTITY_VERSION,
        "shows": shows,
        "raw_key_to_show_key": raw_key_to_show_key,
        "folder_rules": folder_rules_table,
    }
    normalized_result, _ok = normalize_registry(new_registry)
    return normalized_result, canonical_key, rule_id, redirect_map

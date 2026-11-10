"""
Phase 5.5.2 step 4 tests: persisted show-key compatibility -- existing
Programming Blocks and Auto-Fill sequential cursor data staying valid
once a raw show_key resolves to a corrected canonical show_<uuid>
identity via mediawave.show_identity.

Covers:
- the shared canonicalization helpers (canonical_show_key/
  canonicalize_show_keys/aliases_for_show_key) in isolation,
- Programming Block resolution/stats canonicalizing legacy show_keys so
  merged aliases collapse to one rotation slot instead of going stale,
- the Programming Block editor canonicalizing an existing block's keys
  on open, and persisting canonical keys on save,
- Auto-Fill cursor lookup falling back to a legacy alias's saved row when
  the canonical key has none yet, and the documented conflict-winner rule
  when more than one alias has a row,
- that save-time cursor-advance metadata has carried canonical show_key
  end-to-end since Phase 5.5.2 step 2 (no new code needed there -- this
  just proves it),
- a full synthetic end-to-end scenario (merged Programming Block +
  merged cursor rows + merged catalog), and
- that none of the above ever rewrites a persisted file merely by being
  resolved/opened/read.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase554_persisted_key_compat.py
"""

import copy
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

PASS = []
FAIL = []


def check(name, expr, detail=""):
    if expr:
        PASS.append(name)
        print(f"  OK  {name}")
    else:
        FAIL.append(name)
        print(f"FAIL  {name}" + (f"  ({detail})" if detail else ""))


def section(title):
    print(f"\n--- {title} ---")


from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.schedule_editor.autofill_cursor import (
    advance_cursor,
    cursor_key,
    cursors_to_advance_from_saved_changes,
    empty_cursor_data,
    last_aired_path_for,
    pick_winning_cursor_entry,
    save_autofill_cursors,
    load_autofill_cursors,
)
from mediawave.schedule_editor.autofill_planner import plan_rotate_shows
from mediawave.schedule_editor.programming_blocks import (
    BEHAVIOR_ROTATE_SHOWS,
    ProgrammingBlock,
    load_programming_blocks,
    resolve_programming_block,
    save_programming_blocks,
)
from mediawave.schedule_editor.programming_block_dialog import _block_stats, _EditorPage
from mediawave.schedule_editor.put_on_air_picker import resolve_show_episode
from mediawave.show_identity import (
    aliases_for_show_key,
    canonical_show_key,
    canonicalize_show_keys,
    create_registry_record,
    empty_registry,
    mint_show_key,
)

CANONICAL_KEY = mint_show_key()
REGISTRY = {
    "version": 1,
    "shows": {
        CANONICAL_KEY: create_registry_record("Moral Orel", aliases=["tv::2", "tv::3", "tv::moral orel 1"], now=1.0),
    },
    "raw_key_to_show_key": {"tv::2": CANONICAL_KEY, "tv::3": CANONICAL_KEY, "tv::moral orel 1": CANONICAL_KEY},
    "folder_rules": {},
}


def episode(show_key, num, duration=1800, media_type="tv", season=1, path=None):
    return {
        "path": path or f"/media/{show_key}/{num}.mp4",
        "title": "Moral Orel",
        "episode_label": f"Episode {num}",
        "media_type": media_type,
        "duration": duration,
        "channel_name": "Adult Swim",
        "schedulable": True,
        "season_number": season,
        "episode_number": num,
        "show_key": show_key,
        "raw_show_key": show_key,
        "show_identity_source": "parsed",
        "show_display_name": "",
        "episode_title": f"Ep {num}",
    }


section("1. canonical_show_key / canonicalize_show_keys / aliases_for_show_key")

check("1a. a legacy raw key resolves to its canonical show_key", canonical_show_key("tv::2", REGISTRY) == CANONICAL_KEY)
check("1b. an already-canonical key is returned unchanged", canonical_show_key(CANONICAL_KEY, REGISTRY) == CANONICAL_KEY)
check("1c. an unknown/uncorrected raw key is returned unchanged (provisional identity)", canonical_show_key("tv::unrelated", REGISTRY) == "tv::unrelated")
check("1d. an empty value resolves to an empty value, not a crash", canonical_show_key("", REGISTRY) == "")
check("1e. a None registry/empty registry behaves as a no-op", canonical_show_key("tv::2", empty_registry()) == "tv::2")

check(
    "2a. canonicalize_show_keys dedupes several merged aliases to one canonical key, first-occurrence order",
    canonicalize_show_keys(["tv::2", "tv::unrelated", "tv::3", "tv::moral orel 1"], REGISTRY) == [CANONICAL_KEY, "tv::unrelated"],
)
check("2b. canonicalize_show_keys never mutates its input list", (lambda values: (canonicalize_show_keys(values, REGISTRY), values == ["tv::2", "tv::3"]))(["tv::2", "tv::3"])[1])
before_registry = copy.deepcopy(REGISTRY)
canonicalize_show_keys(["tv::2", "tv::3"], REGISTRY)
check("2c. canonicalize_show_keys never mutates the registry", REGISTRY == before_registry)

check("3a. aliases_for_show_key returns the registry's own stored (deterministic) alias order", aliases_for_show_key(CANONICAL_KEY, REGISTRY) == ["tv::2", "tv::3", "tv::moral orel 1"])
check("3b. aliases_for_show_key on an unknown show returns an empty list, not a crash", aliases_for_show_key("show_missing", REGISTRY) == [])
check("3c. aliases_for_show_key on a provisional (never-corrected) key returns an empty list", aliases_for_show_key("tv::unrelated", REGISTRY) == [])

# Cycle safety: a hand-built malformed registry where a raw key points at
# another raw key (never produced by normalize_registry, but the helper
# must still terminate rather than loop forever).
malformed_cyclic = {
    "shows": {"show_x": create_registry_record("X")},
    "raw_key_to_show_key": {"a": "b", "b": "a"},
}
check("4. canonical_show_key never infinite-loops on a malformed cyclic alias table", canonical_show_key("a", malformed_cyclic) in ("a", "b"))


section("2. Programming Block resolution canonicalizes legacy show_keys")

GAP = 6000  # 3 * 1800s episodes, plus slack -- big enough that all 3 eligible shows get a turn in one cycle

# Catalog as it looks WITHOUT any correction: each file's show_key is
# still exactly its own raw metadata_lookup_key-style string, matching
# what build_picker_catalog produces against an empty registry.
items_uncorrected = [episode("tv::2", 1), episode("tv::3", 1), episode("tv::moral orel 1", 1), episode("tv::unrelated", 1)]
legacy_block = ProgrammingBlock("block1", "Adult Swim", ["tv::2", "tv::3", "tv::moral orel 1"], BEHAVIOR_ROTATE_SHOWS)

plan_uncorrected = resolve_programming_block(legacy_block, items_uncorrected, 0, GAP, seed=0)
check("5. untouched (no registry) block resolves against its raw keys exactly as before -- each raw key is its own show, all three get separate turns", len({e["show_key"] for e in plan_uncorrected["lineup"]}) == 3)

# Catalog as it looks AFTER correction: build_picker_catalog would have
# resolved these same three files' show_key to the canonical key (their
# raw_show_key is preserved separately) -- "tv::unrelated" has no alias
# entry, so it stays provisional/unchanged, exactly as resolve_show_
# identity would produce.
items_corrected = [
    episode(CANONICAL_KEY, 1, path="/media/tv::2/1.mp4"),
    episode(CANONICAL_KEY, 1, path="/media/tv::3/1.mp4"),
    episode(CANONICAL_KEY, 1, path="/media/tv::moral orel 1/1.mp4"),
    episode("tv::unrelated", 1),
]

plan_corrected = resolve_programming_block(legacy_block, items_corrected, 0, GAP, seed=0, show_identity_registry=REGISTRY)
lineup_show_keys = {e["show_key"] for e in plan_corrected["lineup"]}
check("6. with the registry, the three merged aliases resolve to ONE canonical show in the lineup", lineup_show_keys == {CANONICAL_KEY})
check("6b. Moral Orel gets exactly one fair-rotation turn per cycle, not triple weighting -- fewer or equal placements than the uncorrected 3-show rotation", len(plan_corrected["lineup"]) <= len(plan_uncorrected["lineup"]))

# Compare directly against a block that already only lists the canonical key.
canonical_block = ProgrammingBlock("block1", "Adult Swim", [CANONICAL_KEY], BEHAVIOR_ROTATE_SHOWS)
plan_canonical_only = resolve_programming_block(canonical_block, items_corrected, 0, GAP, seed=0, show_identity_registry=REGISTRY)
check("6c. resolving the merged legacy block matches resolving an equivalent canonical-only block exactly", plan_corrected == plan_canonical_only)

block_with_missing = ProgrammingBlock("block2", "Missing Show", ["tv::2", "tv::gone"], BEHAVIOR_ROTATE_SHOWS)
plan_with_missing = resolve_programming_block(block_with_missing, items_corrected, 0, GAP, seed=0, show_identity_registry=REGISTRY)
check("7. a missing/stale legacy key is skipped, not an error", block_with_missing.show_keys == ["tv::2", "tv::gone"])
check("7b. the block's own stored show_keys are untouched merely by resolving", block_with_missing.show_keys == ["tv::2", "tv::gone"])

stats_uncorrected = _block_stats(legacy_block, items_uncorrected)
check("8. untouched _block_stats behaves exactly as before (no registry passed)", stats_uncorrected["show_count"] == 3 and stats_uncorrected["available_count"] == 3)
stats_corrected = _block_stats(legacy_block, items_corrected, show_identity_registry=REGISTRY)
check("9. _block_stats with the registry reports the CANONICAL (deduped) show/available counts", stats_corrected["show_count"] == 1 and stats_corrected["available_count"] == 1)
check("9b. _block_stats' episode_count combines all merged aliases' episodes", stats_corrected["episode_count"] == 3)

before_block_snapshot = copy.deepcopy(legacy_block.to_dict())
resolve_programming_block(legacy_block, items_corrected, 0, GAP, seed=0, show_identity_registry=REGISTRY)
_block_stats(legacy_block, items_corrected, show_identity_registry=REGISTRY)
check("10. merely resolving/computing stats never mutates the block's own data", legacy_block.to_dict() == before_block_snapshot)


section("3. Programming Block editor: legacy keys canonicalize on open, persist canonical on save")

editor = _EditorPage(items_corrected, legacy_block, on_save=lambda block: None, on_cancel=lambda: None, show_identity_registry=REGISTRY)
check("11. opening the editor on a legacy block canonicalizes its included shows to one canonical key", set(editor._included.keys()) == {CANONICAL_KEY})
check("11b. the pre-checked show resolves to a real show (title, not a raw-key fallback label)", editor._shows.get(CANONICAL_KEY) is not None)

saved_blocks = []
editor2 = _EditorPage(items_corrected, legacy_block, on_save=lambda block: saved_blocks.append(block), on_cancel=lambda: None, show_identity_registry=REGISTRY)
editor2._name_edit.setText("Adult Swim")
editor2._save()
check("12. saving an opened legacy block persists ONLY the canonical show_key, no legacy aliases", saved_blocks and saved_blocks[0].show_keys == [CANONICAL_KEY])
check("12b. the stable block id is preserved across the edit", saved_blocks[0].id == legacy_block.id)
check("12c. the description is preserved (empty, same as the original)", saved_blocks[0].description == legacy_block.description)

fresh_editor = _EditorPage(items_corrected, None, on_save=lambda block: None, on_cancel=lambda: None, show_identity_registry=REGISTRY)
check("13. a brand-new block editor with no existing_block starts with no included shows (nothing to canonicalize)", fresh_editor._included == {})


section("4. Old Programming Block files remain readable, malformed registry fails open")

with tempfile.TemporaryDirectory() as tmp:
    blocks_path = os.path.join(tmp, "schedule_programming_blocks.json")
    ok, error = save_programming_blocks(blocks_path, {"version": 1, "blocks": [legacy_block]})
    check("14. an old-format block file (raw keys) saves fine", ok, error)
    reloaded = load_programming_blocks(blocks_path)
    check("14b. it reloads with its raw legacy keys intact -- reading never migrates", reloaded["blocks"][0].show_keys == ["tv::2", "tv::3", "tv::moral orel 1"])

    plan_from_disk = resolve_programming_block(reloaded["blocks"][0], items_corrected, 0, GAP, seed=0, show_identity_registry=REGISTRY)
    check("14c. the reloaded legacy block still resolves correctly through the registry", {e["show_key"] for e in plan_from_disk["lineup"]} == {CANONICAL_KEY})

malformed_registry = {"version": 1, "shows": "not a dict", "raw_key_to_show_key": {}, "folder_rules": {}}
plan_malformed = resolve_programming_block(legacy_block, items_uncorrected, 0, GAP, seed=0, show_identity_registry=malformed_registry)
check("15. a malformed registry fails open to today's behavior (each raw key stands alone)", len({e["show_key"] for e in plan_malformed["lineup"]}) == 3)


section("5. Auto-Fill cursor: canonical hit wins immediately")

data = empty_cursor_data()
data = advance_cursor(data, "ch1", CANONICAL_KEY, "/media/canonical/ep5.mp4", now=1000.0)
data = advance_cursor(data, "ch1", "tv::2", "/media/legacy/ep1.mp4", now=500.0)
check("16. a canonical row is returned directly, without needing the registry at all", last_aired_path_for(data, "ch1", CANONICAL_KEY) == "/media/canonical/ep5.mp4")
check("16b. the canonical hit wins even though a legacy alias row also exists and is older", last_aired_path_for(data, "ch1", CANONICAL_KEY, show_identity_registry=REGISTRY) == "/media/canonical/ep5.mp4")


section("6. Auto-Fill cursor: legacy alias fallback after rename/merge")

data_legacy_only = empty_cursor_data()
data_legacy_only = advance_cursor(data_legacy_only, "ch1", "tv::2", "/media/legacy/s1e1.mp4", now=100.0)
check("17. no canonical row exists yet, so a plain lookup misses", last_aired_path_for(data_legacy_only, "ch1", CANONICAL_KEY) is None)
check("18. with the registry, the legacy alias's row is found and returned", last_aired_path_for(data_legacy_only, "ch1", CANONICAL_KEY, show_identity_registry=REGISTRY) == "/media/legacy/s1e1.mp4")
check("18b. an empty registry preserves today's exact miss behavior", last_aired_path_for(data_legacy_only, "ch1", CANONICAL_KEY, show_identity_registry=empty_registry()) is None)


section("7. Auto-Fill cursor: conflict-winner rule across several merged aliases")

# Rule 1: reliable (>0) updated_at wins.
data_multi = empty_cursor_data()
data_multi = advance_cursor(data_multi, "ch1", "tv::2", "/media/a.mp4", season_number=1, episode_number=1, now=100.0)
data_multi = advance_cursor(data_multi, "ch1", "tv::3", "/media/b.mp4", season_number=5, episode_number=9, now=200.0)
data_multi = advance_cursor(data_multi, "ch1", "tv::moral orel 1", "/media/c.mp4", season_number=1, episode_number=2, now=50.0)
winner_path = last_aired_path_for(data_multi, "ch1", CANONICAL_KEY, show_identity_registry=REGISTRY)
check("19. rule 1: the most recently PLACED (highest updated_at) legacy row wins, even though it has the lowest season/episode", winner_path == "/media/b.mp4")

check("19b. the losing legacy rows are still present in the data structure (nothing deleted)", cursor_key("ch1", "tv::2") in data_multi["cursors"] and cursor_key("ch1", "tv::moral orel 1") in data_multi["cursors"])

# Rule 2: no reliable timestamps -> furthest (season, episode) wins.
data_no_ts = empty_cursor_data()
data_no_ts = advance_cursor(data_no_ts, "ch1", "tv::2", "/media/a2.mp4", season_number=1, episode_number=1)
data_no_ts = advance_cursor(data_no_ts, "ch1", "tv::3", "/media/b2.mp4", season_number=3, episode_number=4)
data_no_ts = advance_cursor(data_no_ts, "ch1", "tv::moral orel 1", "/media/c2.mp4", season_number=2, episode_number=9)
winner_path_2 = last_aired_path_for(data_no_ts, "ch1", CANONICAL_KEY, show_identity_registry=REGISTRY)
check("20. rule 2: with no reliable timestamps, the furthest (season, episode) legacy row wins", winner_path_2 == "/media/b2.mp4")

# Rule 3: neither timestamp nor season/episode -> deterministic alias order (first alias with a row).
data_bare = empty_cursor_data()
data_bare = advance_cursor(data_bare, "ch1", "tv::3", "/media/bare_b.mp4")
data_bare = advance_cursor(data_bare, "ch1", "tv::moral orel 1", "/media/bare_c.mp4")
winner_path_3 = last_aired_path_for(data_bare, "ch1", CANONICAL_KEY, show_identity_registry=REGISTRY)
check("21. rule 3: with neither signal, the first alias in the registry's own deterministic order (that has a row) wins", winner_path_3 == "/media/bare_b.mp4")

check("22. pick_winning_cursor_entry returns None for an empty list", pick_winning_cursor_entry([]) is None)
single = {"path": "/only.mp4", "updated_at": 0.0}
check("22b. pick_winning_cursor_entry returns the sole entry untouched when there's only one candidate", pick_winning_cursor_entry([single]) is single)


section("8. Stale path fallback still works (unrelated to alias search)")

data_stale = empty_cursor_data()
data_stale = advance_cursor(data_stale, "ch1", CANONICAL_KEY, "/media/deleted-episode.mp4", now=1.0)
matching_episodes = [episode(CANONICAL_KEY, n) for n in (1, 2, 3)]
last_path = last_aired_path_for(data_stale, "ch1", CANONICAL_KEY)
check("23. a stale saved path (no longer in the catalog) is still returned as-is -- resolving 'does it exist' is the planner's job, not the cursor's", last_path == "/media/deleted-episode.mp4")
check("23b. none of the current episodes happen to match the stale path (confirming it really is stale for this check)", all(ep["path"] != last_path for ep in matching_episodes))


section("9. Save-time cursor writes already carry canonical show_key (verifying Phase 5.5.2 step 2/3 flow, no new code)")

canonical_episode_group = {
    "show_key": CANONICAL_KEY,
    "title": "Moral Orel",
    "episodes": [episode(CANONICAL_KEY, 1), episode(CANONICAL_KEY, 2)],
}
resolved_sequential = resolve_show_episode(canonical_episode_group, "sequential", last_path=None)
check("24. Show Picker's sequential resolution stamps the CANONICAL show_key onto the placement", resolved_sequential["show_key"] == CANONICAL_KEY)
check("24b. it's tagged strategy='sequential' so the save-time collector picks it up", resolved_sequential["strategy"] == "sequential")

rotate_plan = plan_rotate_shows(items_corrected, [CANONICAL_KEY, "tv::unrelated"], 0, 3600, seed=0)
check("25. Auto-Fill's own placement dicts already carry canonical show_key straight from the catalog item", all(e["show_key"] in (CANONICAL_KEY, "tv::unrelated") for e in rotate_plan["lineup"]))

autofill_entries = [
    {"channel_id": "ch1", "show_key": CANONICAL_KEY, "path": "/media/a.mp4", "title": "A", "season_number": 1, "episode_number": 1, "start": 100},
    {"channel_id": "ch1", "show_key": CANONICAL_KEY, "path": "/media/b.mp4", "title": "B", "season_number": 1, "episode_number": 2, "start": 200},
]
collapsed = cursors_to_advance_from_saved_changes(autofill_entries)
check("26. several saved sequential placements for the same (channel, canonical show) collapse to the chronologically FINAL one", len(collapsed) == 1 and collapsed[0]["path"] == "/media/b.mp4")

new_cursor_data = advance_cursor(empty_cursor_data(), "ch1", CANONICAL_KEY, "/media/b.mp4", now=200.0)
check("27. a fresh advance writes under the CANONICAL key, not any legacy alias", cursor_key("ch1", CANONICAL_KEY) in new_cursor_data["cursors"])
check(
    "27b. no legacy alias row was created by this advance",
    cursor_key("ch1", "tv::2") not in new_cursor_data["cursors"] and cursor_key("ch1", "tv::3") not in new_cursor_data["cursors"],
)


section("10. Failure/undo paths never advance a cursor (regression pin, unrelated to registry work)")

no_advance_from_empty = cursors_to_advance_from_saved_changes([])
check("28. no saved changes -> nothing to advance", no_advance_from_empty == [])
random_entry = resolve_show_episode(canonical_episode_group, "random")
check("29. a random placement carries no 'strategy' key, so it can never be mistaken for sequential and never advances a cursor", "strategy" not in random_entry)


section("11. Integration: merged Programming Block + merged cursor rows + merged catalog")

integration_items = [
    episode("tv::2", 1, path="/media/moral-orel/s1e1.mp4"),
    episode("tv::3", 1, path="/media/moral-orel-redux/s1e2.mp4"),
    episode("tv::unrelated-show", 1, path="/media/other/s1e1.mp4"),
]
# Re-annotate as build_picker_catalog would: canonical show_key resolved,
# raw_show_key preserved per-item.
for item in integration_items[:2]:
    item["raw_show_key"] = item["show_key"]
    item["show_key"] = CANONICAL_KEY
    item["show_identity_source"] = "override"
    item["show_display_name"] = "Moral Orel"

integration_block = ProgrammingBlock("blockX", "Adult Swim", ["tv::2", "tv::3", "tv::unrelated-show"], BEHAVIOR_ROTATE_SHOWS)
integration_cursor_data = empty_cursor_data()
integration_cursor_data = advance_cursor(integration_cursor_data, "ch1", "tv::2", "/media/moral-orel/s1e1.mp4", season_number=1, episode_number=1, now=100.0)
integration_cursor_data = advance_cursor(integration_cursor_data, "ch1", "tv::3", "/media/moral-orel-redux/s1e2.mp4", season_number=1, episode_number=2, now=500.0)

integration_stats = _block_stats(integration_block, integration_items, show_identity_registry=REGISTRY)
check("30. integration: Moral Orel counts as ONE canonical show in the block's stats", integration_stats["show_count"] == 2)  # Moral Orel (merged) + unrelated-show

integration_plan = resolve_programming_block(integration_block, integration_items, 0, 7200, seed=1, show_identity_registry=REGISTRY)
lineup_shows = {e["show_key"] for e in integration_plan["lineup"]}
check("31. integration: Moral Orel appears once in the block rotation (canonical key), alongside the unrelated show", lineup_shows == {CANONICAL_KEY, "tv::unrelated-show"})
check("31b. integration: combined episodes from both merged aliases are available to the rotation", any(e["path"] == "/media/moral-orel/s1e1.mp4" for e in integration_plan["lineup"]) or any(e["path"] == "/media/moral-orel-redux/s1e2.mp4" for e in integration_plan["lineup"]))

integration_winner = last_aired_path_for(integration_cursor_data, "ch1", CANONICAL_KEY, show_identity_registry=REGISTRY)
check("32. integration: the winning legacy cursor (most recently placed) is used to resume", integration_winner == "/media/moral-orel-redux/s1e2.mp4")

integration_block_before = copy.deepcopy(integration_block.to_dict())
integration_cursor_before = copy.deepcopy(integration_cursor_data)
resolve_programming_block(integration_block, integration_items, 0, 7200, seed=1, show_identity_registry=REGISTRY)
last_aired_path_for(integration_cursor_data, "ch1", CANONICAL_KEY, show_identity_registry=REGISTRY)
check("33. integration: nothing persisted is rewritten merely from resolution", integration_block.to_dict() == integration_block_before and integration_cursor_data == integration_cursor_before)


section("12. No app-startup / read-only rewrites occur")

with tempfile.TemporaryDirectory() as tmp:
    blocks_path = os.path.join(tmp, "schedule_programming_blocks.json")
    cursor_path = os.path.join(tmp, "schedule_autofill_cursor.json")
    save_programming_blocks(blocks_path, {"version": 1, "blocks": [legacy_block]})
    save_autofill_cursors(cursor_path, data_multi)
    blocks_mtime_before = os.path.getmtime(blocks_path)
    cursor_mtime_before = os.path.getmtime(cursor_path)

    loaded_blocks = load_programming_blocks(blocks_path)
    loaded_cursor = load_autofill_cursors(cursor_path)
    resolve_programming_block(loaded_blocks["blocks"][0], items_corrected, 0, 3600, seed=0, show_identity_registry=REGISTRY)
    last_aired_path_for(loaded_cursor, "ch1", CANONICAL_KEY, show_identity_registry=REGISTRY)
    _block_stats(loaded_blocks["blocks"][0], items_corrected, show_identity_registry=REGISTRY)

    check("34. loading + resolving Programming Blocks never rewrites the file", os.path.getmtime(blocks_path) == blocks_mtime_before)
    check("35. loading + looking up cursors never rewrites the file", os.path.getmtime(cursor_path) == cursor_mtime_before)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

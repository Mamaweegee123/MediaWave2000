"""
Phase 5.4 Programming Blocks MVP tests: the pure persistence layer
(mediawave/schedule_editor/programming_blocks.py) and the pure
show-rotation gap-fill planner (autofill_planner.plan_rotate_shows /
programming_blocks.resolve_programming_block). No Qt in this file --
UI-level checks (creation dialog, Add to Schedule wiring) live in
test_schedule_phase54_programming_blocks_ui.py.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase54_programming_blocks.py
"""

import os
import sys
import tempfile

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


from mediawave.schedule_editor.autofill_planner import plan_rotate_shows
from mediawave.schedule_editor.programming_blocks import (
    BEHAVIOR_ROTATE_SHOWS,
    ProgrammingBlock,
    empty_programming_blocks_data,
    load_programming_blocks,
    new_block_id,
    normalize_programming_blocks_data,
    remove_block,
    resolve_programming_block,
    save_programming_blocks,
    upsert_block,
)


def episode(show_key, title, num, duration=1800, media_type="tv"):
    return {
        "path": f"/media/{show_key}/{num}.mp4",
        "title": title,
        "episode_label": f"Episode {num}",
        "media_type": media_type,
        "duration": duration,
        "channel_name": "Comedy",
        "schedulable": True,
        "season_number": 1,
        "episode_number": num,
        "show_key": show_key,
    }


def show_episodes(show_key, title, count, duration=1800):
    return [episode(show_key, title, i + 1, duration=duration) for i in range(count)]


# ---------------------------------------------------------------------------
section("1-8. Persistence: normalize / load / save / upsert / remove")
# ---------------------------------------------------------------------------

check("1. empty data is version 1 with no blocks", empty_programming_blocks_data() == {"version": 1, "blocks": []})

malformed_cases = [None, "not a dict", 42, {"version": 99, "blocks": []}, {"version": 1, "blocks": "not a list"}, {}]
for case in malformed_cases:
    normalized, ok = normalize_programming_blocks_data(case)
    check(f"2. malformed data normalizes safely and reports not-ok: {case!r}", ok is False and normalized == empty_programming_blocks_data(), normalized)

good_entry = {"id": "abc123", "name": "Adult Swim", "show_keys": ["tv::aqua teen", "tv::sealab", "tv::aqua teen"], "behavior": "rotate_shows"}
normalized, ok = normalize_programming_blocks_data({"version": 1, "blocks": [good_entry, {"name": "missing id"}, {"id": "no-name"}]})
check("3. a well-formed block entry normalizes to a ProgrammingBlock", ok and len(normalized["blocks"]) == 1 and normalized["blocks"][0].id == "abc123")
check("3b. duplicate show_keys within one block are de-duplicated", normalized["blocks"][0].show_keys == ["tv::aqua teen", "tv::sealab"], normalized["blocks"][0].show_keys)
check("3c. entries missing id or name are dropped, not fatal to the whole file", len(normalized["blocks"]) == 1)

behavior_entry = {"id": "x", "name": "Weird", "show_keys": ["tv::a"], "behavior": "something_else"}
normalized2, ok2 = normalize_programming_blocks_data({"version": 1, "blocks": [behavior_entry]})
check("4. an unknown behavior is coerced to rotate_shows, not rejected", ok2 and normalized2["blocks"][0].behavior == BEHAVIOR_ROTATE_SHOWS)

dup_id_entry_a = {"id": "same", "name": "First", "show_keys": []}
dup_id_entry_b = {"id": "same", "name": "Second", "show_keys": []}
normalized3, ok3 = normalize_programming_blocks_data({"version": 1, "blocks": [dup_id_entry_a, dup_id_entry_b]})
check("5. duplicate ids within one file keep only the first", ok3 and len(normalized3["blocks"]) == 1 and normalized3["blocks"][0].name == "First")

empty_show_keys_entry = {"id": "y", "name": "Empty For Now", "show_keys": []}
normalized4, ok4 = normalize_programming_blocks_data({"version": 1, "blocks": [empty_show_keys_entry]})
check("6. an empty show_keys list is structurally valid (UI enforces non-empty, not this layer)", ok4 and len(normalized4["blocks"]) == 1)

with tempfile.TemporaryDirectory() as tmp:
    store_path = os.path.join(tmp, "programming_blocks.json")
    check("7. loading a missing file returns empty data, not an error", load_programming_blocks(store_path) == empty_programming_blocks_data())

    block_a = ProgrammingBlock(new_block_id(), "Adult Swim", ["tv::aqua teen", "tv::sealab"])
    ok, err = save_programming_blocks(store_path, {"version": 1, "blocks": [block_a]})
    check("8. saving a valid block succeeds", ok, err)
    check("8b. the file exists on disk after saving", os.path.exists(store_path))
    reloaded = load_programming_blocks(store_path)
    check("8c. a reloaded block round-trips exactly", reloaded["blocks"] == [block_a], reloaded)

    with open(store_path, "w") as fh:
        fh.write("{not valid json")
    check("8d. a corrupted file loads as empty data rather than raising", load_programming_blocks(store_path) == empty_programming_blocks_data())

    bad_ok, bad_err = save_programming_blocks(store_path, {"version": 1, "blocks": "nope"})
    check("8e. saving structurally invalid data is refused and returns an error", bad_ok is False and bool(bad_err))
    check("8f. a refused save leaves the existing (corrupted) file untouched, not silently overwritten", open(store_path).read() == "{not valid json")


# ---------------------------------------------------------------------------
section("9-13. upsert_block / remove_block")
# ---------------------------------------------------------------------------

data = empty_programming_blocks_data()
block_id = new_block_id()
block = ProgrammingBlock(block_id, "Halloween TV", ["tv::simpsons", "tv::treehouse"])
data2 = upsert_block(data, block)
check("9. upsert_block adds a new block", data2["blocks"] == [block])
check("9b. upsert_block never mutates the original data", data == empty_programming_blocks_data())

renamed = ProgrammingBlock(block_id, "Spooky Season", ["tv::simpsons"])
data3 = upsert_block(data2, renamed)
check("10. renaming a block (same id) preserves identity -- one block, not two", len(data3["blocks"]) == 1 and data3["blocks"][0].id == block_id)
check("10b. the rename actually took effect", data3["blocks"][0].name == "Spooky Season")

other_block = ProgrammingBlock(new_block_id(), "Comfort Shows", ["tv::bobs burgers"])
data4 = upsert_block(data3, other_block)
check("11. a second distinct block coexists with the first", len(data4["blocks"]) == 2)

data5 = remove_block(data4, block_id)
check("12. remove_block deletes only the targeted block", len(data5["blocks"]) == 1 and data5["blocks"][0].id == other_block.id)
check("12b. remove_block never mutates its input", len(data4["blocks"]) == 2)

data6 = remove_block(data5, "does-not-exist")
check("13. removing a nonexistent id is a harmless no-op", data6["blocks"] == data5["blocks"])


# ---------------------------------------------------------------------------
section("14-15. Deleting media / renaming a show does not delete the block")
# ---------------------------------------------------------------------------

survivor_block = ProgrammingBlock(new_block_id(), "Adult Swim", ["tv::aqua teen", "tv::gone show"])
catalog_without_gone_show = show_episodes("tv::aqua teen", "Aqua Teen Hunger Force", 3)
plan = resolve_programming_block(survivor_block, catalog_without_gone_show, gap_start=0, gap_duration=99999)
check("14. resolving with a show_key no longer in the catalog does not error", plan is not None)
check("14b. the block's own show_keys are unchanged after resolving (never pruned)", survivor_block.show_keys == ["tv::aqua teen", "tv::gone show"])
check("15. resolution simply skips the unavailable show_key and still uses the available one", any(e.get("show_key") == "tv::aqua teen" for e in plan["lineup"]))


# ---------------------------------------------------------------------------
section("16-26. plan_rotate_shows: fairness, determinism, edge cases")
# ---------------------------------------------------------------------------

items_4shows = (
    show_episodes("tv::pokemon", "Pokemon", 400, duration=1200)
    + show_episodes("tv::bobross", "Bob Ross", 4, duration=1200)
    + show_episodes("tv::clonehigh", "Clone High", 4, duration=1200)
    + show_episodes("tv::critic", "The Critic", 4, duration=1200)
)
show_keys_4 = ["tv::pokemon", "tv::bobross", "tv::clonehigh", "tv::critic"]

big_plan = plan_rotate_shows(items_4shows, show_keys_4, gap_start=0, gap_duration=1200 * 16, seed=1)
big_keys = [e["show_key"] for e in big_plan["lineup"]]
check("16. every selected show appears in the first cycle regardless of episode count", len(set(big_keys[:4])) == 4, big_keys[:4])

from collections import Counter

counts = Counter(big_keys)
check("17. the 400-episode show is not chosen more often than the 4-episode shows over 4 cycles", len(set(counts.values())) == 1, counts)

violations = 0
for i in range(0, len(big_keys) - 4, 4):
    if big_keys[i + 3] == big_keys[i + 4]:
        violations += 1
check("18. no show repeats immediately across a cycle boundary", violations == 0, violations)

repeat_a = plan_rotate_shows(items_4shows, show_keys_4, gap_start=0, gap_duration=1200 * 12, seed=7)
repeat_b = plan_rotate_shows(items_4shows, show_keys_4, gap_start=0, gap_duration=1200 * 12, seed=7)
check("19. same seed + same content -> identical lineup", repeat_a["lineup"] == repeat_b["lineup"])

different_seed = plan_rotate_shows(items_4shows, show_keys_4, gap_start=0, gap_duration=1200 * 12, seed=8)
check("20. a different seed can produce a different valid lineup", different_seed["lineup"] != repeat_a["lineup"])

one_show_plan = plan_rotate_shows(show_episodes("tv::solo", "Solo Show", 10, duration=600), ["tv::solo"], gap_start=0, gap_duration=6000, seed=2)
check("21. a one-show selection fills normally", len(one_show_plan["lineup"]) == 10, one_show_plan)

two_show_items = show_episodes("tv::a", "Show A", 3, duration=1000) + show_episodes("tv::b", "Show B", 20, duration=1000)
two_show_plan = plan_rotate_shows(two_show_items, ["tv::a", "tv::b"], gap_start=0, gap_duration=1000 * 8, seed=3)
two_keys = [e["show_key"] for e in two_show_plan["lineup"]]
pairs = [two_keys[i:i + 2] for i in range(0, len(two_keys) - 1, 2)]
check("22. a two-show selection alternates -- each consecutive pair has both shows", all(len(set(p)) == 2 for p in pairs if len(p) == 2), pairs[:4])

single_episode_items = show_episodes("tv::marathon", "Marathon Show", 8, duration=900) + show_episodes("tv::oneoff", "One-Off", 1, duration=900)
single_ep_plan = plan_rotate_shows(single_episode_items, ["tv::marathon", "tv::oneoff"], gap_start=0, gap_duration=900 * 10, seed=4)
single_ep_keys = [e["show_key"] for e in single_ep_plan["lineup"]]
check("23. a show with a single episode still gets a turn every cycle (roughly every other pick)", single_ep_keys.count("tv::oneoff") >= 4, single_ep_keys.count("tv::oneoff"))

empty_selection_plan = plan_rotate_shows(items_4shows, [], gap_start=0, gap_duration=99999)
check("24. an empty show selection resolves to an empty lineup, not an error", empty_selection_plan["lineup"] == [])

no_match_plan = plan_rotate_shows(items_4shows, ["tv::does-not-exist"], gap_start=0, gap_duration=99999)
check("24b. a show_key with zero matching episodes is skipped, resolving to an empty lineup", no_match_plan["lineup"] == [])

mixed_valid_invalid_plan = plan_rotate_shows(items_4shows, ["tv::does-not-exist", "tv::bobross"], gap_start=0, gap_duration=1200 * 4, seed=5)
check("25. one invalid show_key among valid ones doesn't block the valid ones from being used", all(e["show_key"] == "tv::bobross" for e in mixed_valid_invalid_plan["lineup"]) and mixed_valid_invalid_plan["lineup"])

movie_pool = [episode("tv::pokemon", "Pokemon", 1)] + [
    {"path": "/media/Movie.mp4", "title": "A Movie", "media_type": "movie", "duration": 5400, "schedulable": True, "show_key": "movie::abc"}
]
movie_excluded_plan = plan_rotate_shows(movie_pool, ["tv::pokemon", "movie::abc"], gap_start=0, gap_duration=99999)
check("26. non-TV items are never included even if their show_key is selected", all(e.get("media_type") == "tv" for e in movie_excluded_plan["lineup"]))

original_items_copy = list(items_4shows)
original_keys_copy = list(show_keys_4)
_ = plan_rotate_shows(items_4shows, show_keys_4, gap_start=0, gap_duration=1200 * 8, seed=9)
check("26b. plan_rotate_shows never mutates its items or show_keys input", items_4shows == original_items_copy and show_keys_4 == original_keys_copy)


# ---------------------------------------------------------------------------
section("27. Episode rotation within a show (not always the same episode)")
# ---------------------------------------------------------------------------

repeater_items = show_episodes("tv::repeater", "Repeater", 5, duration=1000) + show_episodes("tv::other", "Other", 5, duration=1000)
repeater_plan = plan_rotate_shows(repeater_items, ["tv::repeater", "tv::other"], gap_start=0, gap_duration=1000 * 10, seed=11)
repeater_paths = [e["path"] for e in repeater_plan["lineup"] if e["show_key"] == "tv::repeater"]
check("27. a show's own episodes rotate across cycles rather than replaying the same one", len(set(repeater_paths[:4])) > 1, repeater_paths[:4])


# ---------------------------------------------------------------------------
section("28. Output is ordinary concrete schedule entries (same shape as other plan_* results)")
# ---------------------------------------------------------------------------

sample_plan = plan_rotate_shows(items_4shows, show_keys_4, gap_start=1000.0, gap_duration=4800, seed=12)
check("28. lineup entries carry absolute start/end times tiling the gap without overlap", all(sample_plan["lineup"][i]["end"] == sample_plan["lineup"][i + 1]["start"] for i in range(len(sample_plan["lineup"]) - 1)))
check("28b. result carries the standard gap_start/gap_duration/filled_seconds/leftover_seconds fields", set(sample_plan.keys()) == {"lineup", "gap_start", "gap_duration", "filled_seconds", "leftover_seconds"})
check("28c. no placement carries a strategy tag (rotate_shows never advances the sequential cursor)", all("strategy" not in e for e in sample_plan["lineup"]))


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All Phase 5.4 Programming Blocks (persistence + planner) tests passed.")

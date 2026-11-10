"""
Phase 5.6 Programming Block resolver tests: plan_rotate_shows/
resolve_programming_block consulting each show's persistent Episode
Behavior to choose WHICH EPISODE a show contributes, while fair show-turn
rotation (WHICH SHOW gets a turn) stays completely unchanged.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase56_programming_block_behavior.py
"""

import os
import sys
import time

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


from mediawave.schedule_editor.autofill_cursor import advance_cursor, empty_cursor_data
from mediawave.schedule_editor.autofill_planner import plan_rotate_shows
from mediawave.schedule_editor.programming_blocks import ProgrammingBlock, resolve_programming_block
from mediawave.show_identity import empty_registry, set_show_behavior

CH = "media:/catalog/Comedy"


def episode(show_key, title, num, duration=1800):
    return {
        "path": f"/media/{show_key}/{num}.mp4",
        "title": title, "episode_label": f"Episode {num}",
        "media_type": "tv", "duration": duration, "channel_name": "Comedy",
        "schedulable": True, "season_number": 1, "episode_number": num,
        "show_key": show_key,
    }


def show_episodes(show_key, title, count, duration=1800):
    return [episode(show_key, title, i + 1, duration=duration) for i in range(count)]


section("1. Fair show rotation remains unchanged regardless of per-show behavior")
items = show_episodes("A", "A", 20) + show_episodes("B", "B", 20) + show_episodes("C", "C", 20)
show_behaviors = {"A": "sequential", "B": "random", "C": None}
plan = plan_rotate_shows(items, ["A", "B", "C"], gap_start=0, gap_duration=1800 * 9, seed=1, show_behaviors=show_behaviors)
turn_order = [entry["show_key"] for entry in plan["lineup"]]
check("1. every show gets exactly one turn before any repeat, across all 3 cycles", all(set(turn_order[i:i + 3]) == {"A", "B", "C"} for i in range(0, 9, 3)))

section("2. Sequential show resolves next cursor episode")
cursor_data = advance_cursor(empty_cursor_data(), CH, "A", "/media/A/1.mp4", now=time.time())
plan2 = plan_rotate_shows(items, ["A", "B", "C"], gap_start=0, gap_duration=1800 * 3, seed=2, show_behaviors={"A": "sequential"}, last_aired_path_by_show={"A": "/media/A/1.mp4"})
first_a_entry = next(entry for entry in plan2["lineup"] if entry["show_key"] == "A")
check("2. sequential show continues from episode 2 (after the cursor's episode 1)", first_a_entry["path"] == "/media/A/2.mp4")

section("3. Random show resolves a valid random episode")
plan3 = plan_rotate_shows(items, ["A", "B", "C"], gap_start=0, gap_duration=1800 * 3, seed=3, show_behaviors={"B": "random"})
b_entry = next(entry for entry in plan3["lineup"] if entry["show_key"] == "B")
check("3. random show's placement is one of its own real episodes", b_entry["path"].startswith("/media/B/"))

section("4. Default show preserves existing block episode behavior")
plan4a = plan_rotate_shows(items, ["C"], gap_start=0, gap_duration=1800 * 3, seed=4, show_behaviors={})
plan4b = plan_rotate_shows(items, ["C"], gap_start=0, gap_duration=1800 * 3, seed=4, show_behaviors={"C": None})
check("4. an unset behavior and an explicit None behavior resolve identically", [e["path"] for e in plan4a["lineup"]] == [e["path"] for e in plan4b["lineup"]])
check("4b. default-behavior placements carry no strategy tag (same as pre-5.6)", all("strategy" not in e for e in plan4a["lineup"]))

section("5. Mixed behaviors within one block: A sequential, B random, C default")
plan5 = plan_rotate_shows(
    items, ["A", "B", "C"], gap_start=0, gap_duration=1800 * 9, seed=5,
    show_behaviors={"A": "sequential", "B": "random", "C": None},
    last_aired_path_by_show={"A": "/media/A/3.mp4"},
)
a_entries = [e for e in plan5["lineup"] if e["show_key"] == "A"]
check("5. sequential show A plays in strict order starting after its cursor", [e["path"] for e in a_entries] == ["/media/A/4.mp4", "/media/A/5.mp4", "/media/A/6.mp4"])
check("5b. all three shows appear", {e["show_key"] for e in plan5["lineup"]} == {"A", "B", "C"})

section("6. Show count does not influence turn frequency")
items_uneven = show_episodes("BigShow", "BigShow", 50) + show_episodes("SmallShow", "SmallShow", 2)
plan6 = plan_rotate_shows(items_uneven, ["BigShow", "SmallShow"], gap_start=0, gap_duration=1800 * 10, seed=6, show_behaviors={"SmallShow": "sequential"})
counts = {}
for entry in plan6["lineup"]:
    counts[entry["show_key"]] = counts.get(entry["show_key"], 0) + 1
check("6. both shows get an equal number of turns (5 each of 10 slots)", counts.get("BigShow") == counts.get("SmallShow") == 5)

section("7. Sequential placement carries cursor metadata (strategy tag)")
plan7 = plan_rotate_shows(items, ["A"], gap_start=0, gap_duration=1800 * 3, seed=7, show_behaviors={"A": "sequential"})
check("7. every sequential-behavior placement is tagged strategy=sequential", all(e.get("strategy") == "sequential" for e in plan7["lineup"]))
check("7b. season_number/episode_number are present (needed by _sequential_cursor_meta)", all(e.get("episode_number") is not None for e in plan7["lineup"]))

section("8. Random placement carries no sequential cursor metadata")
plan8 = plan_rotate_shows(items, ["B"], gap_start=0, gap_duration=1800 * 3, seed=8, show_behaviors={"B": "random"})
check("8. no random-behavior placement is tagged strategy=sequential", all("strategy" not in e for e in plan8["lineup"]))

section("9. Sequential show wraps back to the FIRST episode in order (not reshuffled) once exhausted")
short_items = show_episodes("D", "D", 3)
plan9 = plan_rotate_shows(short_items, ["D"], gap_start=0, gap_duration=1800 * 7, seed=9, show_behaviors={"D": "sequential"})
paths9 = [e["path"] for e in plan9["lineup"]]
check("9. wraps in strict repeating order 1,2,3,1,2,3,1", paths9 == ["/media/D/1.mp4", "/media/D/2.mp4", "/media/D/3.mp4", "/media/D/1.mp4", "/media/D/2.mp4", "/media/D/3.mp4", "/media/D/1.mp4"])

section("10. resolve_programming_block end-to-end: registry-driven behavior resolution")
registry = empty_registry()
registry, seq_key = set_show_behavior(registry, "raw::A", "sequential", display_name="A")
registry, rand_key = set_show_behavior(registry, "raw::B", "random", display_name="B")
# resolve_show_identity (build_picker_catalog) is what normally remaps a
# catalog item's show_key to its canonical identity before this dialog
# ever sees it -- here that remap is done by hand, the same way
# _apply_identity_registry_update's item_predicate remap works in
# production, so this test can exercise resolve_programming_block's own
# registry-driven behavior resolution without needing a live catalog.
items10 = show_episodes(seq_key, "A", 20) + show_episodes(rand_key, "B", 20) + show_episodes("C", "C", 20)
block = ProgrammingBlock("blk1", "Mixed Block", [seq_key, rand_key, "C"], "rotate_shows")
cursor_data10 = advance_cursor(empty_cursor_data(), CH, seq_key, f"/media/{seq_key}/5.mp4", now=time.time())
plan10 = resolve_programming_block(block, items10, gap_start=0, gap_duration=1800 * 6, seed=10, show_identity_registry=registry, channel_id=CH, cursor_data=cursor_data10)
seq_entries10 = [e for e in plan10["lineup"] if e["show_key"] == seq_key]
check("10. resolve_programming_block resolves the registry-saved sequential show's next episode via the shared cursor", all(e["path"] == f"/media/{seq_key}/6.mp4" for e in seq_entries10[:1]))
check("10b. resolve_programming_block resolves all three canonical show keys, not the raw pre-correction keys", {e["show_key"] for e in plan10["lineup"]} == {seq_key, rand_key, "C"})

section("11. resolve_programming_block with no channel/cursor context preserves prior (unchanged) behavior")
plan11 = resolve_programming_block(block, items10, gap_start=0, gap_duration=1800 * 6, seed=11, show_identity_registry=registry)
check("11. no crash and a full lineup resolves even with no channel_id/cursor_data", len(plan11["lineup"]) > 0)
check("11b. without cursor context, the sequential show still falls back to its first episode (no cursor to resume from)", any(e["show_key"] == seq_key and e["path"] == f"/media/{seq_key}/1.mp4" for e in plan11["lineup"]))

section("12. Full suite sanity: plan_rotate_shows with show_behaviors=None matches pre-5.6 default call shape")
plan12a = plan_rotate_shows(items, ["A", "B", "C"], gap_start=0, gap_duration=1800 * 9, seed=12)
plan12b = plan_rotate_shows(items, ["A", "B", "C"], gap_start=0, gap_duration=1800 * 9, seed=12, show_behaviors=None, last_aired_path_by_show=None)
check("12. omitting the new params entirely matches passing None explicitly", [e["path"] for e in plan12a["lineup"]] == [e["path"] for e in plan12b["lineup"]])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

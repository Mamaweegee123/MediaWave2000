"""
Phase 4 Schedule Editor tests: the Auto-Fill Block planner
(autofill_planner.py). Pure-function tests only -- no Qt, no draft
model -- since the planner never touches either.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase4_planner.py
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.schedule_editor.autofill_planner import (
    episode_sort_key,
    plan_best_fit_mix,
    plan_continue_sequentially,
    plan_random_mix,
    plan_show_marathon,
)

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


def item(path, title, duration, media_type="movie", season=None, episode=None, schedulable=True):
    return {
        "path": path,
        "title": title,
        "episode_label": f"Episode {episode}" if episode else "",
        "media_type": media_type,
        "duration": duration,
        "channel_name": "Test Channel",
        "schedulable": schedulable,
        "season_number": season,
        "episode_number": episode,
    }


def lineup_is_contiguous(result):
    lineup = result["lineup"]
    cursor = result["gap_start"]
    for entry in lineup:
        if abs(entry["start"] - cursor) > 0.01:
            return False
        cursor = entry["end"]
    return True


def lineup_within_gap(result):
    end = result["gap_start"] + result["gap_duration"]
    return all(entry["end"] <= end + 0.01 for entry in result["lineup"])


# ---------------------------------------------------------------------------
section("Best Fit Mix")

pool = [
    item("a.mp4", "Half Hour Show", 30 * 60),
    item("b.mp4", "Hour Movie", 60 * 60),
    item("c.mp4", "Quarter Short", 15 * 60),
]
result = plan_best_fit_mix(pool, gap_start=1000, gap_duration=90 * 60)
check("1. best-fit fills contiguously with no gaps between placements", lineup_is_contiguous(result))
check("2. best-fit never proposes a placement past the gap", lineup_within_gap(result))
check(
    "3. best-fit minimizes leftover open time (fully fills a 90-min gap from 30/60/15-min items)",
    result["leftover_seconds"] < 1.0,
    result,
)

empty = plan_best_fit_mix([], gap_start=0, gap_duration=3600)
check("4. best-fit with an empty catalog leaves the whole gap as leftover", empty["leftover_seconds"] == 3600)

too_long = plan_best_fit_mix([item("x.mp4", "Too Long", 7200)], gap_start=0, gap_duration=1800)
check("5. best-fit never picks an item longer than the gap", too_long["lineup"] == [])

# ---------------------------------------------------------------------------
section("Random Mix")

pool = [
    item("a.mp4", "Show A", 20 * 60),
    item("b.mp4", "Show B", 20 * 60),
    item("c.mp4", "Show C", 20 * 60),
]
result = plan_random_mix(pool, gap_start=0, gap_duration=60 * 60, seed=42)
check("6. random mix fills contiguously with no gaps", lineup_is_contiguous(result))
check("7. random mix never proposes a placement past the gap", lineup_within_gap(result))
no_immediate_repeat = all(
    result["lineup"][i]["path"] != result["lineup"][i + 1]["path"]
    for i in range(len(result["lineup"]) - 1)
)
check("8. random mix avoids immediate repeats when other options exist", no_immediate_repeat, result["lineup"])

deterministic_a = plan_random_mix(pool, gap_start=0, gap_duration=3600, seed=7)
deterministic_b = plan_random_mix(pool, gap_start=0, gap_duration=3600, seed=7)
check(
    "9. random mix is deterministic for a given seed (previewable without surprises on Apply)",
    [e["path"] for e in deterministic_a["lineup"]] == [e["path"] for e in deterministic_b["lineup"]],
)

# ---------------------------------------------------------------------------
section("Show Marathon")

episodes = [
    item("s1e2.mp4", "Marathon Show", 22 * 60, media_type="tv", season=1, episode=2),
    item("s1e1.mp4", "Marathon Show", 22 * 60, media_type="tv", season=1, episode=1),
    item("s2e1.mp4", "Marathon Show", 22 * 60, media_type="tv", season=2, episode=1),
]
ordered = sorted(episodes, key=episode_sort_key)
check(
    "10. episode_sort_key orders by season then episode",
    [e["path"] for e in ordered] == ["s1e1.mp4", "s1e2.mp4", "s2e1.mp4"],
    ordered,
)

result = plan_show_marathon(ordered, gap_start=0, gap_duration=44 * 60)
check(
    "11. marathon plays episodes in season/episode order",
    [e["path"] for e in result["lineup"]] == ["s1e1.mp4", "s1e2.mp4"],
    result["lineup"],
)

long_gap = plan_show_marathon(ordered, gap_start=0, gap_duration=4 * 22 * 60)
check(
    "12. marathon loops back to episode 1 once the whole series has played and time remains",
    [e["path"] for e in long_gap["lineup"]] == ["s1e1.mp4", "s1e2.mp4", "s2e1.mp4", "s1e1.mp4"],
    long_gap["lineup"],
)

# ---------------------------------------------------------------------------
section("Continue Sequentially")

result = plan_continue_sequentially(ordered, gap_start=0, gap_duration=44 * 60, last_aired_path="s1e1.mp4")
check(
    "13. continues with the episode after the last-aired one",
    [e["path"] for e in result["lineup"]] == ["s1e2.mp4", "s2e1.mp4"],
    result["lineup"],
)

wraps = plan_continue_sequentially(ordered, gap_start=0, gap_duration=22 * 60, last_aired_path="s2e1.mp4")
check(
    "14. continuing after the last episode wraps back to episode 1",
    [e["path"] for e in wraps["lineup"]] == ["s1e1.mp4"],
    wraps["lineup"],
)

no_history = plan_continue_sequentially(ordered, gap_start=0, gap_duration=22 * 60, last_aired_path=None)
check(
    "15. with no last-aired match, continues from the first episode",
    [e["path"] for e in no_history["lineup"]] == ["s1e1.mp4"],
    no_history["lineup"],
)

unknown_path = plan_continue_sequentially(ordered, gap_start=0, gap_duration=22 * 60, last_aired_path="not_in_catalog.mp4")
check(
    "16. an unresolved last-aired path (e.g. file since removed) falls back to episode 1 instead of erroring",
    [e["path"] for e in unknown_path["lineup"]] == ["s1e1.mp4"],
    unknown_path["lineup"],
)

# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 4 planner tests passed.")

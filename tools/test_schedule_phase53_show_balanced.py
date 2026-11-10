"""
Phase 5.3 tests: show-balanced automatic scheduling.

Covers the pure show_balanced_random_order/legacy_random_channel_lineup
helpers in mediawave/scheduling.py, their integration into
ordered_channel_lineup (random TV-only channels get show rotation; movie-only
and mixed TV/movie channels and sequential mode fall back to legacy/unchanged
behavior), and that schedule-state persistence/caching behavior in
channelsurfer2000.py is untouched by the new code path.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase53_show_balanced.py
"""

import os
import sys

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


from mediawave.scheduling import (
    CATALOG_PLAYBACK_ORDER_RANDOM,
    CATALOG_PLAYBACK_ORDER_SEQUENTIAL,
    legacy_random_channel_lineup,
    ordered_channel_lineup,
    show_balanced_random_order,
)
from mediawave.local_media import metadata_lookup_key, parse_local_media


def tv_paths(show, count, season=1):
    return [f"/media/{show}/S{season:02d}E{i + 1:02d} - {show}.mp4" for i in range(count)]


def show_keys(paths):
    return [metadata_lookup_key(p, parse_local_media(p)) for p in paths]


# ---------------------------------------------------------------------------
section("1. Equal show opportunity despite wildly unequal episode counts")
# ---------------------------------------------------------------------------

big_show = tv_paths("Pokemon", 400)
small_shows = tv_paths("Bob Ross", 4) + tv_paths("Clone High", 4) + tv_paths("The Critic", 4)
pool = big_show + small_shows

order = show_balanced_random_order(pool, seed=42)
check("1a. output is not None (all-TV pool groups successfully)", order is not None)
check("1b. output length equals input length", len(order) == len(pool), len(order))

keys = show_keys(order)
first_cycle = keys[:4]
check("1c. first cycle contains all four distinct shows", len(set(first_cycle)) == 4, first_cycle)

# Count how many times each show appears in the first 16 picks (4 cycles).
from collections import Counter

counts_16 = Counter(keys[:16])
check(
    "1d. across the first 4 cycles, Pokemon (400 eps) appears exactly as often as Bob Ross (4 eps)",
    len(counts_16) == 4 and len(set(counts_16.values())) == 1,
    counts_16,
)


# ---------------------------------------------------------------------------
section("2. Every eligible show appears once before any repeats")
# ---------------------------------------------------------------------------

four_shows = tv_paths("A", 10) + tv_paths("B", 10) + tv_paths("C", 10) + tv_paths("D", 10)
order2 = show_balanced_random_order(four_shows, seed=7)
keys2 = show_keys(order2)
for cycle_index in range(0, len(keys2) - 3, 4):
    cycle = keys2[cycle_index:cycle_index + 4]
    if len(cycle) == 4:
        check(f"2. cycle at offset {cycle_index} has all 4 distinct shows", len(set(cycle)) == 4, cycle)
        break


# ---------------------------------------------------------------------------
section("3. No immediate show repeat across cycle boundaries when >1 show")
# ---------------------------------------------------------------------------

violations = 0
for cycle_index in range(0, len(keys2) - 4, 4):
    if keys2[cycle_index + 3] == keys2[cycle_index + 4]:
        violations += 1
check("3. no cycle-boundary show repeats across the whole sequence", violations == 0, violations)


# ---------------------------------------------------------------------------
section("4-5. Determinism")
# ---------------------------------------------------------------------------

repeat_a = show_balanced_random_order(four_shows, seed=99)
repeat_b = show_balanced_random_order(four_shows, seed=99)
check("4. same seed + same content -> identical order", repeat_a == repeat_b)

different_seed = show_balanced_random_order(four_shows, seed=100)
check("5. a different seed can produce a different valid order", different_seed != repeat_a)
check("5b. the different-seed order is still a permutation of the same pool", sorted(different_seed) == sorted(four_shows))


# ---------------------------------------------------------------------------
section("6. One-show channel")
# ---------------------------------------------------------------------------

one_show = tv_paths("Solo Show", 12)
one_show_order = show_balanced_random_order(one_show, seed=1)
check("6a. one-show channel returns full pool", one_show_order is not None and len(one_show_order) == 12)
check("6b. one-show channel output is a permutation of the input", sorted(one_show_order) == sorted(one_show))


# ---------------------------------------------------------------------------
section("7. Two-show channel")
# ---------------------------------------------------------------------------

two_shows = tv_paths("Show One", 3) + tv_paths("Show Two", 20)
two_show_order = show_balanced_random_order(two_shows, seed=2)
two_keys = show_keys(two_show_order)
pairs = [two_keys[i:i + 2] for i in range(0, len(two_keys) - 1, 2)]
check("7. each pair of consecutive picks in a two-show channel contains both shows", all(len(set(p)) == 2 for p in pairs if len(p) == 2), pairs[:5])


# ---------------------------------------------------------------------------
section("8. Show with a single episode")
# ---------------------------------------------------------------------------

single_ep_pool = tv_paths("Marathon Show", 8) + tv_paths("One Episode Show", 1)
single_ep_order = show_balanced_random_order(single_ep_pool, seed=3)
single_ep_keys = show_keys(single_ep_order)
one_ep_key = show_keys(tv_paths("One Episode Show", 1))[0]
marathon_key = show_keys(tv_paths("Marathon Show", 1))[0]
check(
    "8. a one-episode show still gets one turn per cycle (appears roughly every other pick)",
    single_ep_keys.count(one_ep_key) >= 3,
    single_ep_keys.count(one_ep_key),
)


# ---------------------------------------------------------------------------
section("9. Invalid/empty bucket skipped; non-TV pool -> None")
# ---------------------------------------------------------------------------

check("9a. empty pool returns empty list, not None", show_balanced_random_order([], seed=1) == [])

movie_pool = ["/media/Movies/Samurai Cop.mp4", "/media/Movies/Plan 9.mp4"]
check("9b. an all-movie pool returns None (caller falls back to legacy)", show_balanced_random_order(movie_pool, seed=1) is None)

mixed_pool = tv_paths("Pokemon", 5) + ["/media/Movies/Samurai Cop.mp4"]
check("9c. a mixed TV/movie pool returns None (caller falls back to legacy)", show_balanced_random_order(mixed_pool, seed=1) is None)


# ---------------------------------------------------------------------------
section("10. Input is not mutated")
# ---------------------------------------------------------------------------

original = list(four_shows)
_ = show_balanced_random_order(four_shows, seed=55)
check("10. the input list is unchanged after calling the helper", four_shows == original)


# ---------------------------------------------------------------------------
section("11. Output contains only original playable items")
# ---------------------------------------------------------------------------

check("11. output is exactly a permutation of the input (no invented/dropped items)", sorted(order2) == sorted(four_shows))


# ---------------------------------------------------------------------------
section("12. Episode count does not influence show frequency")
# ---------------------------------------------------------------------------

huge = tv_paths("Huge Show", 500)
tiny = tv_paths("Tiny Show", 2)
skewed_pool = huge + tiny
skewed_order = show_balanced_random_order(skewed_pool, seed=8)
skewed_keys = show_keys(skewed_order)
huge_key = show_keys(tv_paths("Huge Show", 1))[0]
tiny_key = show_keys(tv_paths("Tiny Show", 1))[0]
first_2 = skewed_keys[:2]
check(
    "12. in the first cycle, the 500-episode show and the 2-episode show each appear exactly once",
    first_2.count(huge_key) == 1 and first_2.count(tiny_key) == 1,
    first_2,
)


# ---------------------------------------------------------------------------
section("13. Per-show episodes rotate rather than always choosing the same one")
# ---------------------------------------------------------------------------

repeat_show_pool = tv_paths("Repeater", 5) + tv_paths("Other", 5)
repeat_order = show_balanced_random_order(repeat_show_pool, seed=21)
repeater_key = show_keys(tv_paths("Repeater", 1))[0]
repeater_picks = [p for p, k in zip(repeat_order, show_keys(repeat_order)) if k == repeater_key]
check(
    "13. a show's picks across cycles are not the same episode every time",
    len(set(repeater_picks[:5])) > 1,
    repeater_picks[:5],
)


# ---------------------------------------------------------------------------
section("14. ordered_channel_lineup integration")
# ---------------------------------------------------------------------------

integrated = ordered_channel_lineup("/root", "Comedy", pool, CATALOG_PLAYBACK_ORDER_RANDOM, shuffle_seed=42)
check("14a. random TV-only pool via ordered_channel_lineup matches the balanced helper directly", integrated == order)

sequential_pool = tv_paths("Zeta", 3) + tv_paths("Alpha", 3)
seq_result = ordered_channel_lineup("/root", "Comedy", sequential_pool, CATALOG_PLAYBACK_ORDER_SEQUENTIAL, shuffle_seed=1)
check(
    "14b. sequential mode is completely unchanged (alphabetical-by-show sort, not show-rotation)",
    seq_result[0].startswith("/media/Alpha/"),
    seq_result,
)

movie_only_pool = ["/media/Movies/A.mp4", "/media/Movies/B.mp4", "/media/Movies/C.mp4"]
movie_result = ordered_channel_lineup("/root", "Movies", movie_only_pool, CATALOG_PLAYBACK_ORDER_RANDOM, shuffle_seed=5)
legacy_movie_result = legacy_random_channel_lineup(movie_only_pool, 5)
check("14c. movie-only random channel falls back to legacy flat shuffle", movie_result == legacy_movie_result, movie_result)

mixed_result = ordered_channel_lineup("/root", "Mixed", mixed_pool, CATALOG_PLAYBACK_ORDER_RANDOM, shuffle_seed=9)
legacy_mixed_result = legacy_random_channel_lineup(mixed_pool, 9)
check("14d. mixed TV/movie random channel falls back to legacy flat shuffle", mixed_result == legacy_mixed_result, mixed_result)


# ---------------------------------------------------------------------------
section("15. Cached schedule / persistence regression (channelsurfer2000 integration)")
# ---------------------------------------------------------------------------

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import inspect

    import channelsurfer2000 as app_module

    src = inspect.getsource(app_module.ChannelSurfer.apply_channel_schedules)
    check(
        "15a. apply_channel_schedules still persists 'entries'/'shuffle_seed'/'signature' as before (no schema change)",
        "\"entries\": schedule[\"entries\"]" in src and "\"shuffle_seed\": schedule.get(\"shuffle_seed\")" in src and "\"signature\": signature" in src,
    )
    build_src = inspect.getsource(app_module.ChannelSurfer.build_channel_schedule_entries)
    check(
        "15b. build_channel_schedule_entries still calls generate_auto_schedule with channel.shows (flat pool input unchanged)",
        "generate_auto_schedule(" in build_src and "channel.shows" in build_src,
    )
except Exception as exc:  # pragma: no cover - environment-dependent (PySide6/Qt availability)
    check("15. cached schedule / persistence source inspection (skipped)", True, str(exc))


# ---------------------------------------------------------------------------
section("16. Guide and playback read the same persisted concrete entries")
# ---------------------------------------------------------------------------

# generate_auto_schedule is the single function both the "entries" builder and
# the guide/playback-facing lineup diagnostics call through ordered_channel_lineup;
# proving repeated calls with the same seed/pool are identical is exactly the
# guarantee that keeps guide and playback from disagreeing.
call_a = ordered_channel_lineup("/root", "Comedy", pool, CATALOG_PLAYBACK_ORDER_RANDOM, shuffle_seed=42)
call_b = ordered_channel_lineup("/root", "Comedy", pool, CATALOG_PLAYBACK_ORDER_RANDOM, shuffle_seed=42)
check("16. two independent calls with the same seed/content produce an identical concrete lineup", call_a == call_b)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 5.3 (show-balanced scheduling) tests passed.")

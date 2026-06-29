"""
Smoke tests for MediaWave schedule lineup helpers.
Run from the repo root:  venv/bin/python3 tools/test_scheduling.py
No GUI launch required.
"""
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import channelsurfer2000 as app
from mediawave import scheduling as scheduling_mod

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


lineup = [
    "/Media/Toons/Example/Season 1/Example.S01E03.Third.mkv",
    "/Media/Toons/Example/Season 1/Example.S01E01.First.mkv",
    "/Media/Toons/Example/Season 1/Example.S01E02.Second.mkv",
]


section("lineup modes")
sequential = app.ordered_channel_lineup(
    "/Media/Toons",
    "Example",
    lineup,
    app.CATALOG_PLAYBACK_ORDER_SEQUENTIAL,
)
check(
    "sequential lineup follows episode order",
    [app.parse_local_media(path)["episode_number"] for path in sequential] == [1, 2, 3],
    sequential,
)

random_a = app.ordered_channel_lineup("/Media/Toons", "Example", lineup, app.CATALOG_PLAYBACK_ORDER_RANDOM)
random_b = app.ordered_channel_lineup("/Media/Toons", "Example", lineup, app.CATALOG_PLAYBACK_ORDER_RANDOM)
check("random lineup is deterministic", random_a == random_b, (random_a, random_b))
check("random lineup keeps all paths", sorted(random_a) == sorted(lineup), random_a)
check("module helper matches app import", scheduling_mod.ordered_channel_lineup("/Media/Toons", "Example", lineup, app.CATALOG_PLAYBACK_ORDER_SEQUENTIAL) == sequential)

boot_pool = [f"/Media/Toons/Example/Example.S01E{index:02d}.mkv" for index in range(1, 21)]
boot_a = scheduling_mod.ordered_channel_lineup("/Media/Toons", "Example", boot_pool, shuffle_seed=1001)
boot_a_again = scheduling_mod.ordered_channel_lineup("/Media/Toons", "Example", boot_pool, shuffle_seed=1001)
boot_b = scheduling_mod.ordered_channel_lineup("/Media/Toons", "Example", boot_pool, shuffle_seed=2002)
check("same persisted shuffle seed keeps schedule stable", boot_a == boot_a_again, boot_a)
check("different rebuild seeds produce a different lineup", boot_a != boot_b, (boot_a, boot_b))
check("random rebuild keeps the full eligible pool", sorted(boot_a) == sorted(boot_pool) and sorted(boot_b) == sorted(boot_pool))
check(
    "sequential mode ignores rebuild seed",
    scheduling_mod.ordered_channel_lineup(
        "/Media/Toons",
        "Example",
        lineup,
        app.CATALOG_PLAYBACK_ORDER_SEQUENTIAL,
        shuffle_seed=999,
    ) == sequential,
)
diagnostics = scheduling_mod.lineup_diagnostics(boot_pool, boot_a, limit=5)
check("lineup diagnostics report full eligible pool", diagnostics["eligible_pool_size"] == len(boot_pool), diagnostics)
check("lineup diagnostics cap displayed paths", len(diagnostics["lineup_paths"]) == 5, diagnostics)
check("lineup diagnostics report truncated paths", diagnostics["truncated_count"] == 15, diagnostics)


section("catalog settings")
settings = app.normalize_catalog_channel_settings({
    "media:/Media/Toons": {"playback_order": app.CATALOG_PLAYBACK_ORDER_SEQUENTIAL},
    "media:/Media/Movies": {"playback_order": "surprise"},
})
check("sequential setting persists", settings["media:/Media/Toons"]["playback_order"] == app.CATALOG_PLAYBACK_ORDER_SEQUENTIAL, settings)
check("invalid setting falls back to random", settings["media:/Media/Movies"]["playback_order"] == app.CATALOG_PLAYBACK_ORDER_RANDOM, settings)
check("module normalizes invalid setting", scheduling_mod.normalize_playback_order("surprise") == app.CATALOG_PLAYBACK_ORDER_RANDOM)


section("failed path cleanup")
failed_path = lineup[1]
schedule = {
    "lineup": list(lineup),
    "schedule_paths": list(lineup),
    "entries": [{"path": path, "duration": 10} for path in lineup],
}
check("failed path is removed", scheduling_mod.remove_path_from_schedule(schedule, failed_path), schedule)
check("failed path leaves lineup", failed_path not in schedule["lineup"], schedule)
check("failed path leaves schedule paths", failed_path not in schedule["schedule_paths"], schedule)
check("failed path leaves entries", all(entry["path"] != failed_path for entry in schedule["entries"]), schedule)


print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All scheduling smoke tests passed.")

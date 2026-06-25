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


section("catalog settings")
settings = app.normalize_catalog_channel_settings({
    "media:/Media/Toons": {"playback_order": app.CATALOG_PLAYBACK_ORDER_SEQUENTIAL},
    "media:/Media/Movies": {"playback_order": "surprise"},
})
check("sequential setting persists", settings["media:/Media/Toons"]["playback_order"] == app.CATALOG_PLAYBACK_ORDER_SEQUENTIAL, settings)
check("invalid setting falls back to random", settings["media:/Media/Movies"]["playback_order"] == app.CATALOG_PLAYBACK_ORDER_RANDOM, settings)


print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All scheduling smoke tests passed.")

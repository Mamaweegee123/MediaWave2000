"""
Smoke tests for guide slot building and program coalescing.
Run from the repo root:  venv/bin/python3 tools/test_guide_schedule.py
No GUI launch required.
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


# ---------------------------------------------------------------------------
# Minimal channel / program stubs for exercising the guide slot logic
# without a real media catalog.
# ---------------------------------------------------------------------------

MOVIE_PATH = "/Media/Movies/Samurai Cop (1991).mkv"
MOVIE2_PATH = "/Media/Movies/The Living Planet (1984).mkv"
EPISODE_A = "/Media/Shows/Seinfeld/Season 1/Seinfeld.S01E01.mkv"
EPISODE_B = "/Media/Shows/Seinfeld/Season 1/Seinfeld.S01E02.mkv"
COMMERCIAL_PATH = "/Commercials/cola_ad_1985.mkv"

MOVIE_DURATION = 5400.0   # 90-minute movie
EPISODE_DURATION = 1380.0  # 23-minute episode
COMMERCIAL_DURATION = 30.0


def make_content(path, start_offset, end_offset):
    """Return a fake 'programs' item for a content segment."""
    return {
        "path": path,
        "title": os.path.basename(path),
        "entry": {
            "kind": "content",
            "path": path,
            "start_offset": start_offset,
            "end_offset": end_offset,
            "duration": end_offset - start_offset,
        },
    }


def make_commercial(path):
    """Return a fake 'programs' item for a commercial break."""
    return {
        "path": path,
        "title": "Commercial",
        "entry": {
            "kind": "commercial",
            "is_commercial": True,
            "path": path,
            "start_offset": 0.0,
            "end_offset": COMMERCIAL_DURATION,
            "duration": COMMERCIAL_DURATION,
        },
    }


def assign_times(raw_programs, window_start):
    """Attach wall-clock start/end to a list of raw program stubs."""
    programs = []
    t = window_start
    for p in raw_programs:
        d = p["entry"].get("duration", COMMERCIAL_DURATION)
        programs.append({**p, "start": t, "end": t + d})
        t += d
    return programs


def run_slot_builder(programs, window_start):
    """
    Re-implement the slot-building loop from build_guide_rows in isolation so
    this test can run without Qt / a live ChannelSurfer instance.
    """
    slot_data = []
    pending_start = None
    for program in programs:
        entry = program.get("entry") or {}
        is_break = entry.get("is_commercial") or entry.get("kind") in {
            "commercial", "promo", "bumper", "station_id",
        }
        if is_break:
            if slot_data:
                slot_data[-1]["end"] = program["end"]
            else:
                if pending_start is None:
                    pending_start = program["start"]
        else:
            slot_start = pending_start if pending_start is not None else program["start"]
            pending_start = None
            slot_data.append({
                "title": program["title"],
                "time": "",
                "start": slot_start,
                "end": program["end"],
                "path": program["path"],
                "_seg_start": float(entry.get("start_offset", 0) or 0),
                "_seg_end": float(entry.get("end_offset", 0) or 0),
            })

    # Coalesce — must match the logic in channelsurfer2000.py build_guide_rows.
    if len(slot_data) > 1:
        coalesced = [slot_data[0]]
        for slot in slot_data[1:]:
            prev = coalesced[-1]
            if (
                slot["path"]
                and slot["path"] == prev["path"]
                and abs(slot.get("_seg_start", -1.0) - prev.get("_seg_end", -2.0)) < 0.5
            ):
                prev["end"] = slot["end"]
                prev["_seg_end"] = slot.get("_seg_end", prev.get("_seg_end", 0.0))
            else:
                coalesced.append(slot)
        slot_data = coalesced
    for slot in slot_data:
        slot.pop("_seg_start", None)
        slot.pop("_seg_end", None)

    return slot_data


# ---------------------------------------------------------------------------

NOW = int(time.time()) - 1800  # pretend guide window started 30 min ago

section("movie with midroll commercial breaks → one guide cell")

# Samurai Cop split at two commercial breakpoints (1800s and 3600s).
raw = [
    make_content(MOVIE_PATH, 0.0, 1800.0),
    make_commercial(COMMERCIAL_PATH),
    make_commercial(COMMERCIAL_PATH),
    make_content(MOVIE_PATH, 1800.0, 3600.0),
    make_commercial(COMMERCIAL_PATH),
    make_content(MOVIE_PATH, 3600.0, MOVIE_DURATION),
]
programs = assign_times(raw, NOW)
slots = run_slot_builder(programs, NOW)

check("movie with midrolls → exactly 1 guide slot", len(slots) == 1, [s["path"] for s in slots])
check("movie slot uses movie path", slots[0]["path"] == MOVIE_PATH)
check("movie slot spans full wall-clock window", slots[0]["end"] >= slots[0]["start"] + MOVIE_DURATION)
check("no internal _seg fields leaked", "_seg_start" not in slots[0] and "_seg_end" not in slots[0])


section("movie with no commercial breaks → one guide cell")

raw_clean = [make_content(MOVIE_PATH, 0.0, MOVIE_DURATION)]
programs_clean = assign_times(raw_clean, NOW)
slots_clean = run_slot_builder(programs_clean, NOW)
check("clean movie → 1 guide slot", len(slots_clean) == 1)
check("clean movie path correct", slots_clean[0]["path"] == MOVIE_PATH)


section("two separate airings of same movie → two guide cells")

raw_two = [
    make_content(MOVIE_PATH, 0.0, MOVIE_DURATION),
    make_commercial(COMMERCIAL_PATH),
    make_content(MOVIE_PATH, 0.0, MOVIE_DURATION),  # second airing, offset resets to 0
]
programs_two = assign_times(raw_two, NOW)
slots_two = run_slot_builder(programs_two, NOW)
check("two airings → exactly 2 guide slots", len(slots_two) == 2, [s["path"] for s in slots_two])
check("both cells have same movie path", all(s["path"] == MOVIE_PATH for s in slots_two))


section("sequential episodes with same series title → separate cells")

raw_eps = [
    make_content(EPISODE_A, 0.0, EPISODE_DURATION),
    make_commercial(COMMERCIAL_PATH),
    make_content(EPISODE_B, 0.0, EPISODE_DURATION),
]
programs_eps = assign_times(raw_eps, NOW)
slots_eps = run_slot_builder(programs_eps, NOW)
check("two episodes → exactly 2 guide slots", len(slots_eps) == 2, [s["path"] for s in slots_eps])
check("episode A slot has correct path", slots_eps[0]["path"] == EPISODE_A)
check("episode B slot has correct path", slots_eps[1]["path"] == EPISODE_B)


section("commercial filler never appears as a guide slot")

raw_filler = [
    make_commercial(COMMERCIAL_PATH),
    make_commercial(COMMERCIAL_PATH),
    make_content(MOVIE_PATH, 0.0, MOVIE_DURATION),
    make_commercial(COMMERCIAL_PATH),
]
programs_filler = assign_times(raw_filler, NOW)
slots_filler = run_slot_builder(programs_filler, NOW)
check("commercial filler → no standalone commercial slot", all(s["path"] != COMMERCIAL_PATH for s in slots_filler))
check("filler before movie → only 1 content slot", len(slots_filler) == 1)
check("filler absorbed into movie slot", slots_filler[0]["path"] == MOVIE_PATH)


section("two different movies back-to-back (between-episodes commercial) → two cells")

raw_two_movies = [
    make_content(MOVIE_PATH, 0.0, MOVIE_DURATION),
    make_commercial(COMMERCIAL_PATH),
    make_content(MOVIE2_PATH, 0.0, MOVIE_DURATION),
]
programs_two_movies = assign_times(raw_two_movies, NOW)
slots_two_movies = run_slot_builder(programs_two_movies, NOW)
check("two different movies → 2 guide slots", len(slots_two_movies) == 2)
check("first slot is movie 1", slots_two_movies[0]["path"] == MOVIE_PATH)
check("second slot is movie 2", slots_two_movies[1]["path"] == MOVIE2_PATH)


section("episode with internal breaks → one guide cell")

raw_ep_breaks = [
    make_content(EPISODE_A, 0.0, 600.0),
    make_commercial(COMMERCIAL_PATH),
    make_content(EPISODE_A, 600.0, EPISODE_DURATION),
]
programs_ep_breaks = assign_times(raw_ep_breaks, NOW)
slots_ep_breaks = run_slot_builder(programs_ep_breaks, NOW)
check("episode with internal break → 1 guide slot", len(slots_ep_breaks) == 1)
check("episode slot has correct path", slots_ep_breaks[0]["path"] == EPISODE_A)


# ---------------------------------------------------------------------------

print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All guide schedule smoke tests passed.")

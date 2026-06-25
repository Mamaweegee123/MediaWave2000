"""
Smoke tests for local media filename parsing.
Run from the repo root:  venv/bin/python3 tools/test_local_media.py
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.local_media import parse_local_media

PASS = []
FAIL = []


def check(name, expr, detail=""):
    if expr:
        PASS.append(name)
        print(f"  OK  {name}")
    else:
        FAIL.append(name)
        print(f"FAIL  {name}" + (f"  ({detail})" if detail else ""))


def parsed(path):
    return parse_local_media(path)


def section(title):
    print(f"\n--- {title} ---")


section("episode filename parsing")
episode = parsed("/Media/Cartoons/Example.Show.S01E02.The.Big.Day.mkv")
check("dotted SxxEyy is tv", episode["media_type"] == "tv", episode)
check("dotted SxxEyy show name", episode["show_name"] == "Example Show", episode)
check("dotted SxxEyy title", episode["episode_title"] == "The Big Day", episode)
check("dotted SxxEyy numbers", episode["season_number"] == 1 and episode["episode_number"] == 2, episode)

episode = parsed("/Media/Cartoons/Example Show/Season 2/S02E04 - Picnic Problems.mp4")
check("season folder SxxEyy is tv", episode["media_type"] == "tv", episode)
check("season folder show name", episode["show_name"] == "Example Show", episode)
check("season folder numbers", episode["season_number"] == 2 and episode["episode_number"] == 4, episode)

episode = parsed("/Media/Cartoons/Example Show/Season 3/3x07 The Finale.mp4")
check("season folder 3x07 is tv", episode["media_type"] == "tv", episode)
check("season folder 3x07 numbers", episode["season_number"] == 3 and episode["episode_number"] == 7, episode)


section("movie fallback")
movie = parsed("/Media/Movies/Action/The Big Movie.mkv")
check("plain file remains movie", movie["media_type"] == "movie", movie)
check("genre folder does not become title", movie["show_name"] == "The Big Movie", movie)


print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All local media smoke tests passed.")

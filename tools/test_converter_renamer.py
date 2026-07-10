"""Focused tests for MediaWave Converter rename parsing and previews."""

import os
import sys
from pathlib import Path

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave_converter import MediaWaveConverterWindow, parse_rename_file


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, value: str) -> None:
        self.text = value


class _FakeRenamePreview:
    def __init__(self, files) -> None:
        self._rename_files = files
        self.rename_search_note = _FakeLabel()
        self.refreshed = False

    def refresh_rename_table(self) -> None:
        self.refreshed = True


def parsed(name: str, folder: str = "Example Show"):
    return parse_rename_file(Path("/Media") / folder / name)


def assert_episode(name: str, season: int | None, episode: int, folder: str = "Example Show") -> None:
    info = parsed(name, folder)
    assert info.season == season, (name, info)
    assert info.episode == episode, (name, info)


assert_episode("1-01.mp4", 1, 1)
assert_episode("1-01 Charity.mp4", 1, 1)
assert_episode("01-01 - The Lord's Greatest Gift.mp4", 1, 1)
assert_episode("2-04.whatever.mkv", 2, 4)
assert_episode("02-04_whatever.mkv", 2, 4)

assert_episode("204.mp4", 2, 4)
assert_episode("204 - Beat the Clock.mp4", 2, 4)
assert_episode("101.mp4", 1, 1)
assert_episode("112.mp4", 1, 12)
assert_episode("0204.mp4", 2, 4)
assert_episode("1004.mp4", 10, 4)

date_like = parsed("2004 Special.mp4")
assert date_like.season is None
assert date_like.episode is None

embedded_year = parsed("Show 2004 Special.mp4")
assert (embedded_year.season, embedded_year.episode) != (20, 4)

sxxexx = parsed("Example.Show.S01E01.Pilot.mp4")
assert sxxexx.season == 1
assert sxxexx.episode == 1
assert sxxexx.existing_episode_title == "Pilot"

title_match = parsed("Example Show Episode 03 - Picnic Problems.mp4")
assert title_match.season is None
assert title_match.episode == 3
assert title_match.existing_episode_title == "Picnic Problems"

selected = parsed("1-01 blah blah.mp4", "moral orel")
preview = _FakeRenamePreview([selected])
MediaWaveConverterWindow.apply_metadata_preview(
    preview,
    {"title": "Moral Orel"},
    {"1:1": "The Lord's Greatest Gift"},
    "TVmaze",
)
assert preview.refreshed
assert selected.status == "Ready to rename"
assert selected.proposed_name == "Moral Orel S01E01 - The Lord's Greatest Gift.mp4"

fallback_selected = parsed("204.mp4", "mxc")
fallback_preview = _FakeRenamePreview([fallback_selected])
MediaWaveConverterWindow.apply_metadata_preview(
    fallback_preview,
    {"title": "MXC"},
    {},
    "AniList",
)
assert fallback_selected.status == "Ready to rename"
assert fallback_selected.proposed_name == "MXC S02E04 - Episode 4.mp4"

print("Converter renamer tests passed.")

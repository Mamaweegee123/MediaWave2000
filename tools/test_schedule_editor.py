"""
Smoke tests for the Phase 1 Schedule Editor (mediawave/schedule_editor/).
Run from the repo root:
  venv/bin/python3 tools/test_schedule_editor.py
The pure schedule_model.py checks need no QApplication; the widget-geometry
checks below construct real Qt widgets, so this file forces an offscreen
platform (safe to run headless even without QT_QPA_PLATFORM set explicitly).
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.schedule_editor.schedule_model import (
    PX_PER_MINUTE,
    block_width_px,
    build_board_model,
    build_channel_lane,
    sort_channel_rows,
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


class FakeChannel:
    """A minimal stand-in for the real Channel (channelsurfer2000.py) --
    scripted to return a fixed list of window items regardless of the
    requested window_start/count, which is all build_channel_lane needs.
    """

    def __init__(self, items):
        self._items = items

    def get_programs_for_window(self, window_start, count=8):
        return list(self._items)


class RaisingChannel:
    def get_programs_for_window(self, window_start, count=8):
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
section("block_width_px: exact duration-proportional geometry")
# ---------------------------------------------------------------------------

thirty_min = block_width_px(30 * 60)
sixty_min = block_width_px(60 * 60)
check("a 30-minute block is exactly half a 60-minute block's width", thirty_min == sixty_min / 2, (thirty_min, sixty_min))

two_hour_movie = block_width_px(120 * 60)
check("a 2-hour movie is exactly 4x a 30-minute block's width", two_hour_movie == thirty_min * 4, (two_hour_movie, thirty_min))
check("width scales linearly with PX_PER_MINUTE", block_width_px(60 * 60, px_per_minute=2.0) == 120.0, block_width_px(60 * 60, px_per_minute=2.0))

check("zero duration yields zero width, not negative", block_width_px(0) == 0.0, block_width_px(0))
check("negative/garbage duration never yields negative width", block_width_px(-50) == 0.0, block_width_px(-50))


# ---------------------------------------------------------------------------
section("build_channel_lane: real start/end positioning")
# ---------------------------------------------------------------------------

T0 = 1_700_000_000.0  # arbitrary fixed epoch, irrelevant to the math being tested

two_show_items = [
    {"path": "/Media/A.mkv", "title": "Show A", "entry": {"path": "/Media/A.mkv", "kind": "content"}, "start": T0, "end": T0 + 1800},
    {"path": "/Media/B.mkv", "title": "Show B", "entry": {"path": "/Media/B.mkv", "kind": "content"}, "start": T0 + 1800, "end": T0 + 1800 + 3600},
]
lane = build_channel_lane("ch1", "Channel One", 4, "media", "", FakeChannel(two_show_items), T0, T0 + 5400)
check("two distinct programs produce two blocks", len(lane.blocks) == 2, lane.blocks)
check("first block starts at the real start time", lane.blocks[0].start == T0, lane.blocks[0])
check("first block duration is 30 minutes", lane.blocks[0].duration == 1800, lane.blocks[0])
check("second block duration is 60 minutes", lane.blocks[1].duration == 3600, lane.blocks[1])
check("second block starts where the first ends (no gap)", lane.blocks[1].start == lane.blocks[0].end, lane.blocks)


# ---------------------------------------------------------------------------
section("build_channel_lane: movie with internal commercial breaks stays one block")
# ---------------------------------------------------------------------------

movie_path = "/Media/Movies/Jackass The Movie.mkv"
movie_items = [
    {
        "path": movie_path,
        "title": "Jackass The Movie",
        "entry": {"path": movie_path, "kind": "content"},
        "start": T0,
        "end": T0 + 3600,
    },
    {
        "path": movie_path,
        "title": "Jackass The Movie",
        "entry": {"kind": "commercial", "is_commercial": True, "parent_path": movie_path, "parent_title": "Jackass The Movie"},
        "start": T0 + 3600,
        "end": T0 + 3600 + 180,
    },
    {
        "path": movie_path,
        "title": "Jackass The Movie",
        "entry": {"path": movie_path, "kind": "content"},
        "start": T0 + 3780,
        "end": T0 + 3780 + 3600,
    },
]
movie_lane = build_channel_lane("ch2", "Movie Channel", 7, "media", "", FakeChannel(movie_items), T0, T0 + 7380)
check("a movie split into segments + a commercial pod collapses to one logical block", len(movie_lane.blocks) == 1, movie_lane.blocks)
if movie_lane.blocks:
    block = movie_lane.blocks[0]
    check("the collapsed block spans the full true duration (2 segments + break)", block.duration == 7380, block)
    check("the collapsed block is not itself flagged as a commercial", block.is_commercial is False, block)
    check("the collapsed block's media_type resolves from the movie's path", block.media_type == "movie", block)
    check("the collapsed block keeps every underlying raw entry for the details strip", len(block.raw_entries) == 3, block.raw_entries)

# A standalone commercial pod with no adjoining content segment in the
# window (e.g. the window opens mid-break) still forms a valid, all-commercial block.
standalone_break = [
    {
        "path": "",
        "title": "Jackass The Movie",
        "entry": {"kind": "commercial", "is_commercial": True, "parent_path": movie_path, "parent_title": "Jackass The Movie"},
        "start": T0,
        "end": T0 + 60,
    },
]
break_lane = build_channel_lane("ch3", "Movie Channel", 7, "media", "", FakeChannel(standalone_break), T0, T0 + 60)
check("a commercial-only window still produces a block, flagged as commercial", len(break_lane.blocks) == 1 and break_lane.blocks[0].is_commercial, break_lane.blocks)


# ---------------------------------------------------------------------------
section("build_channel_lane: window clipping keeps true start/end for the details strip")
# ---------------------------------------------------------------------------

spanning_items = [
    {"path": "/Media/C.mkv", "title": "Show C", "entry": {"path": "/Media/C.mkv", "kind": "content"}, "start": T0 - 900, "end": T0 + 1800},
]
clipped_lane = build_channel_lane("ch4", "Channel Four", 9, "media", "", FakeChannel(spanning_items), T0, T0 + 1800)
check("a block starting before the window is clipped to the window edge for rendering", clipped_lane.blocks and clipped_lane.blocks[0].start == T0, clipped_lane.blocks)
check("the clipped block's true_start keeps the real, unclipped start", clipped_lane.blocks and clipped_lane.blocks[0].true_start == T0 - 900, clipped_lane.blocks)


# ---------------------------------------------------------------------------
section("build_channel_lane: graceful degradation, never raises")
# ---------------------------------------------------------------------------

no_channel_lane = build_channel_lane("ch5", "No Channel", 1, "weatherstar", "", None, T0, T0 + 3600)
check("channel=None yields has_data=False with no blocks", no_channel_lane.has_data is False and no_channel_lane.blocks == [], no_channel_lane)

class NoWindowQuery:
    pass

no_window_lane = build_channel_lane("ch6", "WeatherStar", 2, "weatherstar", "", NoWindowQuery(), T0, T0 + 3600)
check("a channel-like object without get_programs_for_window degrades gracefully", no_window_lane.has_data is False, no_window_lane)

raising_lane = build_channel_lane("ch7", "Broken", 3, "media", "", RaisingChannel(), T0, T0 + 3600)
check("a channel whose query raises never propagates the exception", raising_lane.has_data is False and raising_lane.blocks == [], raising_lane)

empty_board = build_board_model([], {}, T0, T0 + 3600)
check("an empty channel list produces an empty board, not an error", empty_board == [], empty_board)

board_with_bad_row = build_board_model(
    [{"channel_id": "ch7", "name": "Broken", "number": 3, "channel_type": "media", "logo_path": ""}],
    {"ch7": RaisingChannel()},
    T0,
    T0 + 3600,
)
check("build_board_model never aborts the whole board over one bad channel", len(board_with_bad_row) == 1 and board_with_bad_row[0].has_data is False, board_with_bad_row)


# ---------------------------------------------------------------------------
section("sort_channel_rows: real channel number order")
# ---------------------------------------------------------------------------

rows = [
    {"channel_id": "b", "name": "Bravo", "number": 12},
    {"channel_id": "a", "name": "Alpha", "number": 2},
    {"channel_id": "c", "name": "Charlie", "number": 2},
]
ordered = sort_channel_rows(rows)
check(
    "channels sort by real number ascending, name as a stable tie-break",
    [row["channel_id"] for row in ordered] == ["a", "c", "b"],
    ordered,
)


# ---------------------------------------------------------------------------
section("widget geometry: real ProgramBlockWidget instances")
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.schedule_editor.program_block import ProgramBlockWidget
from mediawave.schedule_editor.schedule_model import ProgramBlock

thirty_block = ProgramBlock(channel_id="x", title="Thirty", media_type="tv", start=T0, end=T0 + 1800, duration=1800, true_start=T0, true_end=T0 + 1800)
sixty_block = ProgramBlock(channel_id="x", title="Sixty", media_type="tv", start=T0, end=T0 + 3600, duration=3600, true_start=T0, true_end=T0 + 3600)
movie_block = ProgramBlock(channel_id="x", title="Movie", media_type="movie", start=T0, end=T0 + 7200, duration=7200, true_start=T0, true_end=T0 + 7200)

thirty_widget = ProgramBlockWidget(thirty_block)
sixty_widget = ProgramBlockWidget(sixty_block)
movie_widget = ProgramBlockWidget(movie_block)

check("a real 30-minute block widget is exactly half a 60-minute widget's width", thirty_widget.width() == sixty_widget.width() / 2, (thirty_widget.width(), sixty_widget.width()))
check("a real 2-hour movie widget is exactly 4x the 30-minute widget's width", movie_widget.width() == thirty_widget.width() * 4, (movie_widget.width(), thirty_widget.width()))

from mediawave.schedule_editor.layout_constants import MIN_BLOCK_WIDTH_PX

tiny_block = ProgramBlock(channel_id="x", title="Ad", media_type="commercial", start=T0, end=T0 + 5, duration=5, is_commercial=True, true_start=T0, true_end=T0 + 5)
tiny_widget = ProgramBlockWidget(tiny_block)
check("a very short (5-second) block never collapses to zero/negative geometry", tiny_widget.width() >= MIN_BLOCK_WIDTH_PX and tiny_widget.height() > 0, (tiny_widget.width(), tiny_widget.height()))

long_title = "A" * 300
long_block = ProgramBlock(channel_id="x", title=long_title, media_type="tv", start=T0, end=T0 + 1800, duration=1800, true_start=T0, true_end=T0 + 1800)
long_widget = ProgramBlockWidget(long_block)
check("a very long title still builds a valid widget without raising", long_widget.width() > 0, long_widget.width())
check("the tooltip keeps the full, un-elided title for on-demand detail", long_title in long_widget.toolTip(), long_widget.toolTip()[:40])


# ---------------------------------------------------------------------------
section("widget behavior: selection, current-time line, no stale widgets on rebuild")
# ---------------------------------------------------------------------------

from mediawave.schedule_editor.board import ProgrammingBoard
from mediawave.schedule_editor.schedule_model import ChannelLane

lane_a = build_channel_lane("ch1", "Channel One", 4, "media", "", FakeChannel(two_show_items), T0, T0 + 5400)
lane_b = ChannelLane(channel_id="ch5", name="No Data Channel", number=1, channel_type="weatherstar", logo_path="", blocks=[], has_data=False)

board = ProgrammingBoard()

selected_blocks = []
selected_channels = []
board.program_selected.connect(lambda b: selected_blocks.append(b))
board.channel_selected.connect(lambda cid: selected_channels.append(cid))

board.set_lanes([lane_a, lane_b], T0, T0 + 5400)
check("set_lanes builds one identity cell per lane", len(board.identity_cells) == 2, board.identity_cells)
check("set_lanes builds one row strip per lane", len(board._grid_content.row_strips) == 2, board._grid_content.row_strips)

first_row_widgets = board._grid_content.row_strips[0].block_widgets
check("the first channel's row has one widget per logical block", len(first_row_widgets) == len(lane_a.blocks), first_row_widgets)

if first_row_widgets:
    first_row_widgets[0].selected.emit(first_row_widgets[0].block)
    check("clicking a block emits program_selected with that block", selected_blocks and selected_blocks[-1] is first_row_widgets[0].block, selected_blocks)
    check("the clicked widget becomes visually selected", first_row_widgets[0]._is_selected is True, first_row_widgets[0]._is_selected)

board.identity_cells[1].selected.emit(board.identity_cells[1].channel_id)
check("clicking a channel identity cell emits channel_selected with its id", selected_channels == ["ch5"], selected_channels)

# Rebuild -- must not leave the old widgets behind as stale siblings.
board.set_lanes([lane_a, lane_b], T0, T0 + 5400)
check("rebuilding the board still has exactly one identity cell per lane (no duplicates)", len(board.identity_cells) == 2, board.identity_cells)
check("rebuilding the board still has exactly one row strip per lane (no duplicates)", len(board._grid_content.row_strips) == 2, board._grid_content.row_strips)

check("the identity column and time header are separate widgets from the scrolling grid", board._identity_viewport is not board._grid_scroll and board._ruler_viewport is not board._grid_scroll, None)

import time as _time
from mediawave.schedule_editor.board import _GridContent

real_now = _time.time()
grid_with_now = _GridContent([lane_a], real_now - 1800, real_now + 1800, PX_PER_MINUTE)
check("the current-time line appears when the window actually contains now", grid_with_now.now_line is not None, grid_with_now.now_line)

grid_without_now = _GridContent([lane_a], T0, T0 + 3600, PX_PER_MINUTE)
check("the current-time line is absent for a window that doesn't contain now (e.g. a past/future day)", grid_without_now.now_line is None, grid_without_now.now_line)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
else:
    print("All smoke tests passed.")

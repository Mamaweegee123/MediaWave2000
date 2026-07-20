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

from mediawave.schedule_editor.companion_display import group_for_display
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

from mediawave.schedule_editor.layout_constants import WIDE_CONTENT_MIN_PX

check(
    "an ordinary 30-minute show meets the 'wide' readability floor at the default scale "
    "(full title + time + type visible, not squeezed to fit any particular viewport)",
    block_width_px(30 * 60) >= WIDE_CONTENT_MIN_PX,
    (block_width_px(30 * 60), WIDE_CONTENT_MIN_PX),
)


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
section("companion_display.group_for_display: broad blocks, real timing preserved")
# ---------------------------------------------------------------------------

from mediawave.schedule_editor.schedule_model import ProgramBlock as _PB


def _synthetic_segments(count, seg_seconds, channel_id="weatherstar-1", title_prefix="Segment"):
    segments = []
    t = T0
    for i in range(count):
        end = t + seg_seconds
        segments.append(
            _PB(
                channel_id=channel_id,
                title=f"{title_prefix} {i}",
                media_type="tv",
                start=t,
                end=end,
                duration=seg_seconds,
                true_start=t,
                true_end=end,
                raw_entries=[{"kind": "content", "title": f"{title_prefix} {i}"}],
            )
        )
        t = end
    return segments


weatherstar_segments = _synthetic_segments(40, 300)  # 40 x 5 min = ~3.3 hours of real segments
weatherstar_grouped = group_for_display("weatherstar", weatherstar_segments)
check(
    "WeatherStar's many 5-minute segments collapse into materially fewer display blocks",
    0 < len(weatherstar_grouped) < len(weatherstar_segments) / 4,
    (len(weatherstar_segments), len(weatherstar_grouped)),
)
check(
    "the grouped WeatherStar span starts at the first real segment's start",
    weatherstar_grouped[0].start == weatherstar_segments[0].start,
    weatherstar_grouped[0] if weatherstar_grouped else None,
)
check(
    "the grouped WeatherStar span ends at the last real segment's end",
    weatherstar_grouped[-1].end == weatherstar_segments[-1].end,
    weatherstar_grouped[-1] if weatherstar_grouped else None,
)
check(
    "WeatherStar display blocks use the real-channel_type-backed 'weather' category",
    all(b.media_type == "weather" for b in weatherstar_grouped),
    [b.media_type for b in weatherstar_grouped],
)
check(
    "WeatherStar's merged title is one honest, stable label -- not a rotating list implying "
    "editorial variety (Local/Regional/National) the real segment data doesn't support",
    all(b.title == "WeatherStar Forecast" for b in weatherstar_grouped),
    [b.title for b in weatherstar_grouped],
)
check(
    "WeatherStar's real distinct segment titles survive in source_titles, even though the "
    "display title is generic -- honesty is one click away, not lost",
    all(len(set(b.source_titles)) > 1 for b in weatherstar_grouped),
    [b.source_titles for b in weatherstar_grouped],
)

radiowave_segments = _synthetic_segments(50, 210, channel_id="radiowave-1", title_prefix="Track")  # 50 tracks, ~3.5 min each
radiowave_grouped = group_for_display("radiowave", radiowave_segments)
check(
    "RadioWaveTV's many small track blocks collapse into materially fewer display blocks",
    0 < len(radiowave_grouped) < len(radiowave_segments) / 4,
    (len(radiowave_segments), len(radiowave_grouped)),
)
check(
    "RadioWaveTV display blocks use the 'music' category",
    all(b.media_type == "music" for b in radiowave_grouped),
    [b.media_type for b in radiowave_grouped],
)

youtube_segments = _synthetic_segments(12, 600, channel_id="youtube-1", title_prefix="Cool Real Video")  # 12 x 10-minute real videos
youtube_grouped = group_for_display("youtube", youtube_segments)
check(
    "NetTV still gets grouped when there are genuinely many entries",
    0 < len(youtube_grouped) < len(youtube_segments),
    (len(youtube_segments), len(youtube_grouped)),
)
check(
    "NetTV's merged title is built from a real absorbed video's title, not a fabricated "
    "curated-sounding name (no 'Late Night Laughs'/'Chill Streams'/'Classic Clips'/'YouTube Mix')",
    all(b.title.startswith("Cool Real Video") for b in youtube_grouped),
    [b.title for b in youtube_grouped],
)
check(
    "NetTV renders as the same real 'Show' category regular content uses, not a fabricated Companion bucket",
    all(b.media_type == "tv" for b in youtube_grouped),
    [b.media_type for b in youtube_grouped],
)
check(
    "NetTV should feel more literal than RadioWaveTV -- fewer entries get absorbed into each "
    "merged block on average",
    (len(youtube_segments) / max(1, len(youtube_grouped))) < (len(radiowave_segments) / max(1, len(radiowave_grouped))),
    (len(youtube_segments) / len(youtube_grouped), len(radiowave_segments) / len(radiowave_grouped)),
)

local_media_segments = _synthetic_segments(10, 1800, channel_id="movies-1")  # 10 x 30-minute shows
local_media_grouped = group_for_display("media", local_media_segments)
check(
    "a local 'media' channel_type is returned completely unchanged by group_for_display",
    local_media_grouped == local_media_segments,
    (len(local_media_grouped), len(local_media_segments)),
)

total_raw_entries = sum(len(b.raw_entries) for b in weatherstar_segments)
grouped_raw_entries = sum(len(b.raw_entries) for b in weatherstar_grouped)
check(
    "a grouped block's raw_entries is the concatenation of every absorbed block's raw_entries (real data survives)",
    grouped_raw_entries == total_raw_entries,
    (grouped_raw_entries, total_raw_entries),
)

repeat_grouped = group_for_display("weatherstar", weatherstar_segments)
check(
    "calling group_for_display twice on the same input produces the same result (no duplication/drift)",
    [b.title for b in repeat_grouped] == [b.title for b in weatherstar_grouped]
    and [(b.start, b.end) for b in repeat_grouped] == [(b.start, b.end) for b in weatherstar_grouped],
    None,
)

check(
    "an empty block list passes through as an empty list",
    group_for_display("weatherstar", []) == [],
    None,
)


# ---------------------------------------------------------------------------
section("build_channel_lane: companion grouping runs end-to-end through the real pipeline")
# ---------------------------------------------------------------------------


class FakeCompanionChannel:
    """Mimics WeatherChannel.get_programs_for_window's shape (no "entry"
    key on each item -- see program_block._resolve_media_type's docstring
    on synthetic weatherstar:// paths) to prove the full build_channel_lane
    pipeline (not just group_for_display in isolation) groups companion
    output correctly.
    """

    def get_programs_for_window(self, window_start, count=8):
        items = []
        t = window_start
        for i in range(count):
            end = t + 300
            items.append({"path": f"weatherstar://segment-{i}", "title": f"Forecast Segment {i}", "start": t, "end": end})
            t = end
        return items


companion_lane = build_channel_lane(
    "special:weatherstar", "WeatherStar 4000+", 4, "weatherstar", "", FakeCompanionChannel(), T0, T0 + 3 * 3600
)
check(
    "a real companion lane (via build_channel_lane, not just group_for_display) renders far fewer blocks than raw segments",
    companion_lane.has_data and 0 < len(companion_lane.blocks) < 10,
    companion_lane.blocks,
)

local_lane_for_grouping_check = build_channel_lane(
    "ch-local", "Movies", 1, "media", "", FakeChannel(two_show_items), T0, T0 + 5400
)
check(
    "a regular local channel's real blocks are untouched by the companion grouping pass",
    len(local_lane_for_grouping_check.blocks) == 2,
    local_lane_for_grouping_check.blocks,
)


# ---------------------------------------------------------------------------
section("widget geometry: new companion media-type accents render without error")
# ---------------------------------------------------------------------------

from mediawave.schedule_editor.program_block import MEDIA_TYPE_ACCENTS, MEDIA_TYPE_LABELS, ProgramBlockWidget, build_category_legend

check(
    "'companion' is not a category -- nothing produces it anymore (NetTV renders as real 'tv'/Show content)",
    "companion" not in MEDIA_TYPE_ACCENTS and "companion" not in MEDIA_TYPE_LABELS,
    (list(MEDIA_TYPE_ACCENTS.keys()), list(MEDIA_TYPE_LABELS.keys())),
)

for companion_media_type in ("weather", "music"):
    check(f"'{companion_media_type}' has a real accent entry", companion_media_type in MEDIA_TYPE_ACCENTS, MEDIA_TYPE_ACCENTS.keys())
    check(f"'{companion_media_type}' has a real label entry", companion_media_type in MEDIA_TYPE_LABELS, MEDIA_TYPE_LABELS.keys())
    block = _PB(
        channel_id="x",
        title="Local Forecast",
        media_type=companion_media_type,
        start=T0,
        end=T0 + 7200,
        duration=7200,
        true_start=T0,
        true_end=T0 + 7200,
    )
    widget = ProgramBlockWidget(block)
    check(f"a '{companion_media_type}' ProgramBlockWidget builds without error", widget.width() > 0, widget.width())

legend = build_category_legend()
check("build_category_legend() builds without error", legend is not None, legend)


# ---------------------------------------------------------------------------
section("ProgrammingBoard: horizontal scrolling restored, app shell stays fixed")
# ---------------------------------------------------------------------------

from PySide6.QtCore import Qt

scroll_board = ProgrammingBoard()
scroll_board.resize(400, 500)  # deliberately narrower than a 90-minute window at the new scale
scroll_board.show()
scroll_lanes = [lane_a, lane_b]
scroll_board.set_lanes(scroll_lanes, T0, T0 + 5400)

check(
    "the grid's horizontal scrollbar is available again (not permanently off)",
    scroll_board._grid_scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded,
    scroll_board._grid_scroll.horizontalScrollBarPolicy(),
)
check(
    "guide content is allowed to be wider than the viewport -- that's what makes it scrollable "
    "instead of being squeezed to fit",
    scroll_board._grid_content.width() > scroll_board._grid_scroll.viewport().width(),
    (scroll_board._grid_content.width(), scroll_board._grid_scroll.viewport().width()),
)
check(
    "the ruler's width still matches the grid content's total width (tracks real content, not the viewport)",
    abs(scroll_board._ruler_content.width() - scroll_board._grid_content.width()) <= 1,
    (scroll_board._ruler_content.width(), scroll_board._grid_content.width()),
)
check(
    "the board's own footprint never grows to fit its wider-than-viewport content -- the "
    "surrounding application shell never needs to scroll horizontally",
    scroll_board.width() <= 401,
    scroll_board.width(),
)

scroll_board._grid_scroll.horizontalScrollBar().setValue(37)
check(
    "scrolling the grid horizontally keeps the ruler in sync, mirroring the existing vertical sync",
    scroll_board._ruler_content.x() == -37,
    scroll_board._ruler_content.x(),
)


# ---------------------------------------------------------------------------
section("Editing Tools: six real actions, deferred tools as one dim line")
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QLabel, QPushButton
from mediawave.schedule_editor.utility_panels import _COMING_LATER_TOOL_NAMES, build_editing_tools_card

editing_tools_card, editing_tools_controls = build_editing_tools_card()
editing_tools_buttons = editing_tools_card.findChildren(QPushButton)
check(
    "exactly the six real actions exist as buttons (no wall of deferred inert controls)",
    sorted(b.text() for b in editing_tools_buttons) == [
        "Copy to Another Day…", "Duplicate Here…", "Fill Open Time", "Move To…", "Pull", "Put On Air",
    ],
    [b.text() for b in editing_tools_buttons],
)
check(
    "all three action buttons start disabled until a selection makes them meaningful",
    all(b.isEnabled() is False for b in editing_tools_buttons),
    [(b.text(), b.isEnabled()) for b in editing_tools_buttons],
)

editing_tools_text = " ".join(label.text() for label in editing_tools_card.findChildren(QLabel))
check(
    "every deferred bulk tool is still named, as a dim 'Coming later' line",
    all(name in editing_tools_text for name in _COMING_LATER_TOOL_NAMES) and "Coming later" in editing_tools_text,
    editing_tools_text,
)
editing_tools_controls["set_hint"]("A test hint.")
check(
    "the tools card exposes a working hint line for explaining the selection state",
    "A test hint." in " ".join(label.text() for label in editing_tools_card.findChildren(QLabel)),
)


# ---------------------------------------------------------------------------
section("ScheduleEditorWorkspace: top toolbar (no title, no legend, Back relocated)")
# ---------------------------------------------------------------------------

from mediawave.schedule_editor.dialog import ScheduleEditorWorkspace, _compact_date, build_schedule_editor_tab


class _FakeStudioDialog:
    """Deliberately bare -- every attribute `_build_channel_rows` and
    `channel_actions.companion_snapshot_from_dialog`/`companion_status_from_dialog`
    read off a studio_dialog is `getattr(..., default)`-guarded (confirmed
    in dialog.py and channel_actions.py), so this resolves to zero
    channels and hits ScheduleEditorWorkspace's cheap empty-state path --
    which still builds the top bar and footer inspector first, before
    returning, so both are testable without a real Channel Studio dialog.
    """


back_calls = []
workspace = ScheduleEditorWorkspace(_FakeStudioDialog(), on_back=lambda: back_calls.append(1))

top_bar_texts = [lbl.text() for lbl in workspace._top_bar.findChildren(QLabel)]
check(
    "no 'Tonight's Lineup' (or any) page title remains in the top toolbar",
    all("Tonight" not in text for text in top_bar_texts),
    top_bar_texts,
)
check(
    "the category legend no longer rides the top toolbar (it's a guide key under the board now)",
    all(name not in top_bar_texts for name in ("Show", "Movie", "Weather")),
    top_bar_texts,
)

back_buttons = [b for b in workspace._top_bar.findChildren(QPushButton) if b.text() == "←  Back"]
check("a Back button lives in the top toolbar", len(back_buttons) == 1, len(back_buttons))
if back_buttons:
    back_buttons[0].click()
    check("clicking the top-toolbar Back button invokes the on_back callback", back_calls == [1], back_calls)

history_buttons = [b for b in workspace._top_bar.findChildren(QPushButton) if b.text() in ("Undo", "Redo", "Save Schedule")]
check("Undo/Redo/Save are all present", len(history_buttons) == 3, [b.text() for b in history_buttons])
check(
    "Undo/Redo/Save all start disabled for a clean, empty draft",
    all(b.isEnabled() is False for b in history_buttons),
    [(b.text(), b.isEnabled()) for b in history_buttons],
)
check(
    "each disabled history control explains itself via tooltip",
    all(b.toolTip() for b in history_buttons),
    [b.toolTip() for b in history_buttons],
)
check(
    "no unsaved-changes badge shows for a clean draft (and the READ-ONLY badge is gone)",
    "READ-ONLY PREVIEW" not in top_bar_texts and workspace._status_badge.text() == "",
    (top_bar_texts, workspace._status_badge.text()),
)
revert_buttons = [b for b in workspace._top_bar.findChildren(QPushButton) if b.text() == "Revert Draft"]
check(
    "Revert Draft exists but stays hidden while the draft is clean",
    len(revert_buttons) == 1 and revert_buttons[0].isVisible() is False,
    [(b.text(), b.isVisible()) for b in revert_buttons],
)
nav_buttons = [b for b in workspace._top_bar.findChildren(QPushButton) if b.text() in ("←  Back", "‹", "Today", "›")]
check(
    "Back/prev/Today/next use the quiet nav style, not the app-wide 110px filled button box",
    all("min-width: 0px" in b.styleSheet() for b in nav_buttons),
    [(b.text(), b.styleSheet()) for b in nav_buttons],
)


# ---------------------------------------------------------------------------
section("compact corner date: format, board placement, day navigation")
# ---------------------------------------------------------------------------

import re as _re

compact = _compact_date(T0)
check(
    "the compact date matches the 'Thu 7-16-26' shape (no big page-heading date, no time range)",
    bool(_re.match(r"^[A-Z][a-z]{2} \d{1,2}-\d{1,2}-\d{2}$", compact)),
    compact,
)
check(
    "the compact date changes when the viewed day changes",
    _compact_date(T0 + 24 * 3600) != compact,
    (_compact_date(T0 + 24 * 3600), compact),
)

corner_board = ProgrammingBoard()
corner_board.set_corner_text("Thu 7-16-26")
check(
    "the board's frozen corner cell (beside the time row) carries the compact date",
    corner_board._corner_label.text() == "Thu 7-16-26",
    corner_board._corner_label.text(),
)

from mediawave.schedule_editor.layout_constants import TIME_HEADER_HEIGHT

check("the time header is tall enough to read as a proper guide ruler", TIME_HEADER_HEIGHT >= 40, TIME_HEADER_HEIGHT)

from mediawave.schedule_editor.board import _TimeRulerContent

ruler = _TimeRulerContent(T0, T0 + 5400, PX_PER_MINUTE)
ruler_labels = [lbl for lbl in ruler.findChildren(QLabel) if ":" in lbl.text()]
check("the ruler renders time labels", len(ruler_labels) >= 2, len(ruler_labels))
check(
    "ruler time labels span the full header height, vertically centered (not small top-anchored text)",
    all(lbl.height() == TIME_HEADER_HEIGHT and (lbl.alignment() & Qt.AlignVCenter) for lbl in ruler_labels),
    [(lbl.height(), int(lbl.alignment())) for lbl in ruler_labels],
)
check(
    "ruler time labels use the larger 12px font",
    all(lbl.font().pixelSize() == 12 for lbl in ruler_labels),
    [lbl.font().pixelSize() for lbl in ruler_labels],
)


# ---------------------------------------------------------------------------
section("channel identity: true ink-centered channel numbers (not advance-box AlignCenter)")
# ---------------------------------------------------------------------------

from PySide6.QtGui import QFont, QFontMetrics
from mediawave.channel_studio.studio_styles import channel_number_font_family
from mediawave.schedule_editor.channel_row import (
    ChannelIdentityCell,
    _ChannelNumberBadge,
    _ink_centered_origin,
    _NUMBER_LANE_WIDTH,
)
from mediawave.schedule_editor.layout_constants import ROW_HEIGHT

# The actual bug (verified against the real loaded font, not asserted):
# Qt.AlignHCenter centers a string's *advance* box, but this pixel-styled
# OSD font has uneven left/right glyph bearing that differs per digit --
# "1" and "6" don't even share the same bearing as each other, let alone
# with a two-digit number -- so advance-box centering necessarily lands
# each string at a different visual position. This section proves the fix
# (centering the measured ink rect instead) puts every one of them on the
# exact same true center, for real one- and two-digit numbers.
badge_font = QFont(channel_number_font_family(), QFont().pointSize() + 5, QFont.Bold)
badge_fm = QFontMetrics(badge_font)
box_w, box_h = _NUMBER_LANE_WIDTH, ROW_HEIGHT

ink_centers = {}
for number_text in ("1", "6", "10", "12", "16"):
    pen_x, pen_y = _ink_centered_origin(badge_fm, number_text, box_w, box_h)
    ink = badge_fm.boundingRect(number_text)
    center = (pen_x + ink.x() + ink.width() / 2.0, pen_y + ink.y() + ink.height() / 2.0)
    ink_centers[number_text] = center
    check(
        f"'{number_text}' ink lands on the lane's true geometric center (not just 'AlignCenter is set')",
        abs(center[0] - box_w / 2.0) < 0.6 and abs(center[1] - box_h / 2.0) < 0.6,
        (number_text, center, (box_w / 2.0, box_h / 2.0)),
    )

check(
    "one-digit and two-digit numbers all land on the exact same visual center as each other",
    len({(round(x, 1), round(y, 1)) for x, y in ink_centers.values()}) == 1,
    ink_centers,
)

for identity_number in (1, 6, 10, 12, 16):
    badge = _ChannelNumberBadge(identity_number)
    check(
        f"a real _ChannelNumberBadge({identity_number}) builds at the fixed lane size and paints without error",
        badge.width() == _NUMBER_LANE_WIDTH and badge.height() == ROW_HEIGHT,
        (badge.width(), badge.height()),
    )
    badge.repaint()  # exercises paintEvent for real -- would raise on a broken drawText call

identity_lane = ChannelLane(channel_id="ch1", name="Movies", number=16, channel_type="media", logo_path="", blocks=[], has_data=True)
identity_cell = ChannelIdentityCell(identity_lane)
number_badges = [w for w in identity_cell.findChildren(_ChannelNumberBadge)]
check("the identity cell renders exactly one channel-number badge", len(number_badges) == 1, len(number_badges))
if number_badges:
    check(
        "the channel number uses the shared Channel Studio digital-font path",
        number_badges[0]._font.family() == channel_number_font_family(),
        (number_badges[0]._font.family(), channel_number_font_family()),
    )
    check("the badge renders the real channel number text", number_badges[0]._text == "16", number_badges[0]._text)

# Selection state: subtle for a bare channel click, distinct from a
# program's own strong yellow border (see program_block.ProgramBlockWidget).
check("a fresh identity cell starts unselected", identity_cell._is_selected is False, identity_cell._is_selected)
identity_cell.set_selected(True)
check(
    "set_selected(True) applies a distinctly different (subtle) style than the default",
    "rgba(96, 144, 255, 30)" in identity_cell.styleSheet(),
    identity_cell.styleSheet(),
)
from mediawave.schedule_editor.program_block import ProgramBlockWidget as _PBW

selected_program_style = ""
_sel_block = ProgramBlock(channel_id="ch1", title="X", media_type="tv", start=T0, end=T0 + 1800, duration=1800, true_start=T0, true_end=T0 + 1800)
_sel_widget = _PBW(_sel_block)
_sel_widget.set_selected(True)
check(
    "a selected program's own strong-state style is visually distinct from a selected channel row's subtle style",
    identity_cell.styleSheet() != _sel_widget._card.styleSheet(),
    None,
)
identity_cell.set_selected(False)
check("set_selected(False) reverts to the unselected style", identity_cell._is_selected is False, identity_cell._is_selected)


# ---------------------------------------------------------------------------
section("Selected Program footer inspector: occupies the footer band, updates on selection")
# ---------------------------------------------------------------------------

_, footer = build_schedule_editor_tab(_FakeStudioDialog())
check("the footer page is the inspector, styled with the shared advFooter chrome", footer.objectName() == "advFooter", footer.objectName())
check("the inspector has real presence (fixed footer-band height, not a zero/skinny strip)", footer.height() >= 80, footer.height())

footer_texts = [lbl.text() for lbl in footer.findChildren(QLabel)]
check(
    "with nothing selected, the inspector shows the calm full-details prompt",
    any("Select a program to see its full details." in text for text in footer_texts),
    footer_texts,
)

from mediawave.schedule_editor.utility_panels import build_selected_program_footer

inspector, update_inspector = build_selected_program_footer()
inspected_block = ProgramBlock(
    channel_id="ch1", title="Most Extreme Elimination Challenge", media_type="tv",
    start=T0, end=T0 + 480, duration=480, true_start=T0, true_end=T0 + 480,
)
inspected_lane = ChannelLane(channel_id="ch1", name="SpikeTV", number=14, channel_type="media", logo_path="", blocks=[inspected_block], has_data=True)
update_inspector(inspected_block, inspected_lane)
populated_texts = " | ".join(lbl.text() for lbl in inspector.findChildren(QLabel))
check(
    "selecting a program populates title, channel, time/duration/type, and origin",
    all(part in populated_texts for part in ("Most Extreme Elimination Challenge", "Ch 14 · SpikeTV", "8 min", "Show", "Auto-generated schedule")),
    populated_texts,
)

update_inspector(None, None)
update_inspector(None, None)
prompt_labels = [lbl for lbl in inspector.findChildren(QLabel) if "Select a program" in lbl.text() and lbl.isVisibleTo(inspector)]
check(
    "clearing the selection restores exactly one prompt (no duplicated widgets after repeated updates)",
    len(prompt_labels) == 1,
    [lbl.text() for lbl in inspector.findChildren(QLabel)],
)


# ---------------------------------------------------------------------------
section("workspace integration: corner date wired to day navigation")
# ---------------------------------------------------------------------------


class _DynamicFakeChannel:
    """Unlike FakeChannel (fixed T0-anchored items, clipped away entirely
    once `window_start` drifts to "now"), this anchors its two shows to
    whatever window_start is actually requested -- needed here since
    ScheduleEditorWorkspace always opens on the real current time.
    """

    def get_programs_for_window(self, window_start, count=8):
        return [
            {"path": "/Media/A.mkv", "title": "Show A", "entry": {"path": "/Media/A.mkv", "kind": "content"}, "start": window_start, "end": window_start + 1800},
            {"path": "/Media/B.mkv", "title": "Show B", "entry": {"path": "/Media/B.mkv", "kind": "content"}, "start": window_start + 1800, "end": window_start + 1800 + 3600},
        ]


class _FakeStudioDialogWithChannel:
    def __init__(self):
        self.catalog_channel_infos = [
            {"id": "ch1", "name": "Channel One", "channel_type": "media", "default_number": 4},
            {"id": "ch2", "name": "Channel Two", "channel_type": "media", "default_number": 5},
        ]
        self.catalog_channel_settings = {}
        self._studio_channels_by_id = {"ch1": _DynamicFakeChannel(), "ch2": _DynamicFakeChannel()}


live_workspace = ScheduleEditorWorkspace(_FakeStudioDialogWithChannel())
if hasattr(live_workspace, "board"):
    check(
        "the workspace's board corner shows the compact date for the viewed day",
        live_workspace.board._corner_label.text() == _compact_date(live_workspace._window_start),
        (live_workspace.board._corner_label.text(), _compact_date(live_workspace._window_start)),
    )
    before_shift = live_workspace.board._corner_label.text()
    live_workspace._shift_day(1)
    check(
        "navigating to the next day updates the corner date immediately",
        live_workspace.board._corner_label.text() == _compact_date(live_workspace._window_start)
        and live_workspace.board._corner_label.text() != before_shift,
        (before_shift, live_workspace.board._corner_label.text()),
    )
    right_column_widget = live_workspace._editing_tools_card.parentWidget()
    right_layout = right_column_widget.layout()
    card_indices = [right_layout.indexOf(w) for w in (live_workspace._editing_tools_card, live_workspace._next_up_card, live_workspace._channel_defaults_card)]
    check(
        "Editing Tools/Next Up/Channel Defaults all get their natural content height (stretch=0), "
        "not equal-stretch that crowds Channel Defaults out",
        all(right_layout.stretch(i) == 0 for i in card_indices),
        [right_layout.stretch(i) for i in card_indices],
    )

    from PySide6.QtWidgets import QFrame as _QFrame

    if live_workspace.board.identity_cells and live_workspace.board._grid_content.row_strips[0].block_widgets:
        first_cell = live_workspace.board.identity_cells[0]
        first_widget = live_workspace.board._grid_content.row_strips[0].block_widgets[0]
        first_widget.selected.emit(first_widget.block)
        check(
            "selecting a program also marks its own channel row as the (subtle) selection context",
            first_cell._is_selected is True,
            first_cell._is_selected,
        )
        _, expected_accent = MEDIA_TYPE_ACCENTS.get(first_widget.block.media_type, MEDIA_TYPE_ACCENTS["tv"])
        check(
            "the Selected Program footer's accent bar matches the selected block's real category color",
            expected_accent in live_workspace._details_footer.findChild(_QFrame, "selectedProgramAccentBar").styleSheet(),
            live_workspace._details_footer.findChild(_QFrame, "selectedProgramAccentBar").styleSheet(),
        )

        if len(live_workspace.board.identity_cells) > 1:
            second_cell = live_workspace.board.identity_cells[1]
            second_cell.selected.emit(second_cell.channel_id)
            check(
                "selecting a different channel row clears the previous row's subtle state",
                first_cell._is_selected is False and second_cell._is_selected is True,
                (first_cell._is_selected, second_cell._is_selected),
            )
else:
    check("workspace with one real channel builds a board", False, "empty-state path hit unexpectedly")


# ---------------------------------------------------------------------------
section("visual cleanup: legend under the guide, no corner/accent artifacts")
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QFrame as _QFrame, QScrollArea as _QScrollArea

if hasattr(live_workspace, "_guide_column"):
    guide_layout = live_workspace._guide_column.layout()
    check(
        "the guide column stacks the board first, then the legend row below it",
        guide_layout.itemAt(0).widget() is live_workspace.board,
        guide_layout.itemAt(0).widget(),
    )
    legend_item = guide_layout.itemAt(1)
    legend_widget = legend_item.layout().itemAt(0).widget() if legend_item.layout() is not None else None
    legend_texts = [lbl.text() for lbl in legend_widget.findChildren(QLabel)] if legend_widget is not None else []
    check(
        "the legend sits under the guide, as the first (left-aligned) item of its row",
        all(name in legend_texts for name in ("Show", "Movie", "Commercial", "Weather", "Music")),
        legend_texts,
    )
else:
    check("workspace exposes the guide column holding board + legend", False, "no _guide_column")

check(
    "the board's scroll corner is styled transparent (no white bracket artifact where scrollbars meet)",
    "::corner" in live_workspace.board._grid_scroll.styleSheet(),
    live_workspace.board._grid_scroll.styleSheet(),
)

right_scrolls = [s for s in live_workspace.findChildren(_QScrollArea) if s is not live_workspace.board._grid_scroll]
check(
    "the right utility panel can never grow a horizontal scrollbar (the stray blue bar under the cards)",
    right_scrolls and all(s.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff for s in right_scrolls),
    [s.horizontalScrollBarPolicy() for s in right_scrolls],
)

for card_name, card in (("Editing Tools", live_workspace._editing_tools_card), ("Channel Defaults", live_workspace._channel_defaults_card), ("Next Up", live_workspace._next_up_card)):
    accent_strips = [f for f in card.findChildren(_QFrame) if f.maximumWidth() == 4]
    check(
        f"the {card_name} card renders no stray accent-strip fragment",
        len(accent_strips) == 0,
        accent_strips,
    )


# ---------------------------------------------------------------------------
section("Channel Studio: Schedule Editor entry removed")
# ---------------------------------------------------------------------------

import mediawave.channel_studio.channel_studio_pages as _cs_pages

check(
    "channel_studio_pages no longer defines the Schedule Editor launch card",
    not hasattr(_cs_pages, "_build_schedule_editor_card"),
    dir(_cs_pages),
)
with open(_cs_pages.__file__, "r") as _f:
    _cs_source = _f.read()
check(
    "the Channel Studio page source contains no 'Open Schedule Editor' entry",
    "Open Schedule Editor" not in _cs_source and "schedule_editor" not in _cs_source,
    None,
)


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

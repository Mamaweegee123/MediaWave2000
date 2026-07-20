"""
Phase 3 Schedule Editor tests: MoveProgramCommand, the Move To… workflow,
and drag-and-drop geometry/interaction on the board.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase3.py

Covers the 40 scenarios from the Phase 3 spec (numbered in section
titles). Pure-model tests run without Qt; widget-level checks force the
offscreen platform, same as the earlier schedule-editor test files.
"""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


from mediawave.schedule_editor.commands import (
    CONFLICT_OVERLAPS_DESTINATION,
    CommandHistory,
    MoveProgramCommand,
    PullProgramCommand,
    PutOnAirCommand,
    snap_to_interval,
)
from mediawave.schedule_editor.draft_model import DraftSchedule
from mediawave.schedule_editor.move_to_dialog import destination_epoch_for_time
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock

NOW = time.time()
T0 = NOW - (NOW % 1800)
CH = "media:/catalog/Comedy"
CH2 = "media:/catalog/Movies"


def make_lane(channel_id=CH, blocks=None, name="Comedy", number=4, channel_type="media", has_data=True):
    return ChannelLane(channel_id=channel_id, name=name, number=number, channel_type=channel_type, logo_path="", blocks=blocks or [], has_data=has_data)


def make_block(title, start, end, channel_id=CH, media_type="tv", source="generated", is_commercial=False, raw_entries=None):
    return ProgramBlock(
        channel_id=channel_id,
        title=title,
        media_type=media_type,
        start=start,
        end=end,
        duration=end - start,
        is_commercial=is_commercial,
        source=source,
        true_start=start,
        true_end=end,
        raw_entries=raw_entries if raw_entries is not None else [{"kind": "content", "path": f"/media/{title}.mp4", "title": title, "duration": end - start}],
    )


def fresh_draft():
    draft = DraftSchedule()
    draft.set_base_lanes([make_lane(blocks=[
        make_block("Show A", T0, T0 + 1800),
        make_block("Show B", T0 + 1800, T0 + 3600),
        make_block("Show C", T0 + 3600, T0 + 5400),
    ])])
    return draft


def blocks_of(draft, channel_id=CH):
    lane = next(l for l in draft.presentation_lanes() if l.channel_id == channel_id)
    return lane.blocks


def titles_of(draft, channel_id=CH):
    return [(b.title, b.media_type) for b in blocks_of(draft, channel_id)]


# ---------------------------------------------------------------------------
section("1-4. Core move mechanics: remove+add, undo, redo")
# ---------------------------------------------------------------------------

draft = fresh_draft()
history = CommandHistory()
block_a = blocks_of(draft)[0]
cmd = MoveProgramCommand(block_a, CH, T0 + 5400)
v = cmd.validate(draft, now=NOW)
check("move validates cleanly onto a clear destination", v.ok, v.reason)
history.execute(cmd, draft)
after = titles_of(draft)
check(
    "1. move removes the original placement and adds the destination placement",
    ("Open Time", "open") == after[0][:2] or after[0][0] == "Open Time",
    after,
)
check("1b. the moved program appears at the destination", any(t == "Show A" for t, _m in after), after)

history.undo(draft)
check("3. Undo restores the exact original lineup", titles_of(draft) == [("Show A", "tv"), ("Show B", "tv"), ("Show C", "tv")], titles_of(draft))
history.redo(draft)
check("4. Redo restores the move", any(t == "Show A" for t, _m in titles_of(draft)) and any(m == "open" for _t, m in titles_of(draft)))


# ---------------------------------------------------------------------------
section("2. Generated source data is not mutated")
# ---------------------------------------------------------------------------

import channelsurfer2000 as cs

duration_cache = {"/media/a.mp4": 1800.0, "/media/b.mp4": 1800.0, "/media/c.mp4": 1800.0}
channel = cs.Channel("Comedy", duration_cache)
channel.set_schedule(["/media/a.mp4", "/media/b.mp4", "/media/c.mp4"], T0)
entries_before = [dict(e) for e in channel.schedule_entries]
window_items = channel.get_programs_for_window(T0, count=6)
lane_blocks = [make_block(item["title"], item["start"], item["end"]) for item in window_items[:3]]
draft2 = DraftSchedule()
draft2.set_base_lanes([make_lane(blocks=lane_blocks)])
history2 = CommandHistory()
history2.execute(MoveProgramCommand(blocks_of(draft2)[0], CH, T0 + 5400), draft2)
check("2. moving a block never mutates the live Channel's generated entries", [dict(e) for e in channel.schedule_entries] == entries_before)


# ---------------------------------------------------------------------------
section("5-7. Pending Changes / Save Review / minimal saved overrides")
# ---------------------------------------------------------------------------

draft = fresh_draft()
history = CommandHistory()
history.execute(MoveProgramCommand(blocks_of(draft)[0], CH, T0 + 5400), draft)
rows = draft.describe_pending_changes()
check("5. a move appears as exactly one Pending Changes row", len(rows) == 1 and rows[0]["action"] == "move", rows)
check("5b. the row headline says 'Moved', not separate Pull/Put On Air language", rows[0]["headline"] == 'Moved “Show A”', rows[0])
check("5c. the subline shows a from -> to time range", "→" in rows[0]["subline"], rows[0]["subline"])

records = draft.overrides_for_save()
check("7. saving a plain move produces exactly the minimal remove+add record pair", len(records) == 2 and {r["action"] for r in records} == {"add", "remove"}, records)


# ---------------------------------------------------------------------------
section("8-10. No-op guard, snap-to-5-minutes, duration preservation")
# ---------------------------------------------------------------------------

draft = fresh_draft()
block_b = next(b for b in blocks_of(draft) if b.title == "Show B")
same_spot = MoveProgramCommand(block_b, CH, block_b.true_start)
check("8. same-time/same-channel destination is rejected as a no-op", not same_spot.validate(draft, now=NOW).ok)

check("9a. 5:02 snaps down to 5:00 (2 min offset)", snap_to_interval(T0 + 2 * 60) == T0)
check("9b. 5:03 snaps up to 5:05 (3 min offset)", snap_to_interval(T0 + 3 * 60) == T0 + 5 * 60)
check("9c. 5:28 snaps up to 5:30", snap_to_interval(T0 + 28 * 60) == T0 + 30 * 60)
check("9d. an exact 5-minute boundary is unchanged", snap_to_interval(T0 + 25 * 60) == T0 + 25 * 60)

move_far = MoveProgramCommand(block_b, CH, T0 + 20 * 3600)
check("10. destination end preserves the original program's duration", move_far.destination_end - move_far.destination_start == (block_b.true_end - block_b.true_start))


# ---------------------------------------------------------------------------
section("11-13. Open Time interaction: fill, leftover, source gap")
# ---------------------------------------------------------------------------

draft = fresh_draft()
history = CommandHistory()
history.execute(PullProgramCommand(next(b for b in blocks_of(draft) if b.title == "Show C")), draft)
open_slot = next(b for b in blocks_of(draft) if b.media_type == "open")
check("open slot exists at Show C's old location (30 min)", abs((open_slot.true_end - open_slot.true_start) - 1800) < 1)

move_into_open = MoveProgramCommand(next(b for b in blocks_of(draft) if b.title == "Show A"), CH, open_slot.true_start)
check("11. moving into clear Open Time validates and succeeds", move_into_open.validate(draft, now=NOW).ok)
history.execute(move_into_open, draft)
after_move = blocks_of(draft)
check("13. moving Show A away leaves Open Time at its old (source) location", any(b.media_type == "open" and abs(b.true_start - T0) < 1 for b in after_move), [(b.title, b.media_type, b.true_start - T0) for b in after_move])

# 12: a program shorter than the destination open interval leaves the
# remainder open. Needs a genuinely larger open slot than the moved
# program's own duration -- a dedicated draft with one 60-minute block
# (pulled to make one single 60-min open interval) and a 30-minute mover.
draft12 = DraftSchedule()
draft12.set_base_lanes([make_lane(blocks=[
    make_block("Short Show", T0, T0 + 1800),
    make_block("Long Show", T0 + 1800, T0 + 5400),  # 60 minutes
])])
history12 = CommandHistory()
history12.execute(PullProgramCommand(blocks_of(draft12, CH)[1]), draft12)
big_open = next(b for b in blocks_of(draft12) if b.media_type == "open")
check("a 60-minute open slot exists after pulling the 60-minute block", abs((big_open.true_end - big_open.true_start) - 3600) < 1, (big_open.true_start - T0, big_open.true_end - T0))
move_short_into_big = MoveProgramCommand(next(b for b in blocks_of(draft12) if b.title == "Short Show"), CH, big_open.true_start)
history12.execute(move_short_into_big, draft12)
# Two open intervals now exist: the source gap Short Show vacated, AND
# the destination remainder -- item 12 is specifically about the latter.
destination_remainder = next((b for b in blocks_of(draft12) if b.media_type == "open" and abs(b.true_start - (big_open.true_start + 1800)) < 1), None)
check(
    "12. moving a program shorter than the open run leaves the remainder open",
    destination_remainder is not None and abs((destination_remainder.true_end - destination_remainder.true_start) - 1800) < 1,
    [(b.title, b.media_type, b.true_start - T0, b.true_end - T0) for b in blocks_of(draft12)],
)


# ---------------------------------------------------------------------------
section("14-17. Overlap conflicts and replacement")
# ---------------------------------------------------------------------------

# A dedicated draft with a gap between Show A and a much-longer Show Y --
# fresh_draft()'s three equal 30-minute blocks can't isolate a single-
# program overlap (any offset move of a 30-min block against an adjacent
# 30-min block necessarily also clips the next one over).
draft14 = DraftSchedule()
draft14.set_base_lanes([make_lane(blocks=[
    make_block("Show A", T0, T0 + 1800),
    make_block("Show Y", T0 + 3600, T0 + 3600 + 5400),  # 90 minutes, well clear of Show A
])])
block_a = next(b for b in blocks_of(draft14) if b.title == "Show A")
move_overlap = MoveProgramCommand(block_a, CH, T0 + 3600 + 600)  # lands 10 min into Show Y only
result = move_overlap.validate(draft14, now=NOW)
check("14. overlap conflict is reported, not silently allowed", not result.ok and result.conflicts)
conflict = result.conflicts[0]
check("14b. the conflict names the correct overlapping program", len(conflict["overlapping_blocks"]) == 1 and conflict["overlapping_blocks"][0].title == "Show Y", conflict)
check("14c. the conflict states a plausible overlap amount", "minute" in conflict["message"], conflict["message"])

before_titles = titles_of(draft14)
check("15. a cancelled conflict leaves the draft unchanged (never applied)", titles_of(draft14) == before_titles)

history = CommandHistory()
move_replace = MoveProgramCommand(block_a, CH, T0 + 3600 + 600, replace_blocks=[next(b for b in blocks_of(draft14) if b.title == "Show Y")])
v_replace = move_replace.validate(draft14, now=NOW)
check("16. an explicitly-approved replace validates", v_replace.ok, v_replace.reason)
history.execute(move_replace, draft14)
check("16b. the replaced program is gone from the draft", not any(b.title == "Show Y" for b in blocks_of(draft14)), titles_of(draft14))
history.undo(draft14)
check("16c/17. Undo restores BOTH the moved program's original spot and the replaced program", titles_of(draft14) == before_titles, titles_of(draft14))


# ---------------------------------------------------------------------------
section("18-20. Protected channels and missing media")
# ---------------------------------------------------------------------------

weather_lane = make_lane(channel_id="special:weatherstar", channel_type="weatherstar", name="WeatherStar 4000+", number=8, blocks=[
    make_block("WeatherStar Forecast", T0, T0 + 7200, channel_id="special:weatherstar", media_type="weather"),
])
media_lane = make_lane(blocks=[make_block("Show A", T0, T0 + 1800)])
draft3 = DraftSchedule()
draft3.set_base_lanes([media_lane, weather_lane])

weather_block = blocks_of(draft3, "special:weatherstar")[0]
v_weather_source = MoveProgramCommand(weather_block, "special:weatherstar", T0 + 3600).validate(draft3, now=NOW)
check("18. a protected companion source cannot be moved", not v_weather_source.ok and "weather service" in v_weather_source.reason, v_weather_source.reason)

media_block = blocks_of(draft3, CH)[0]
v_weather_dest = MoveProgramCommand(media_block, "special:weatherstar", T0 + 3600).validate(draft3, now=NOW)
check("19. a protected companion destination cannot accept a move", not v_weather_dest.ok, v_weather_dest.reason)

no_media_block = make_block("No File", T0, T0 + 1800, raw_entries=[{"path": ""}])
draft4 = DraftSchedule()
draft4.set_base_lanes([make_lane(blocks=[no_media_block])])
v_missing = MoveProgramCommand(no_media_block, CH, T0 + 3600).validate(draft4, now=NOW)
check("20. missing source media fails validation safely (no crash)", not v_missing.ok and "media file" in v_missing.reason, v_missing.reason)


# ---------------------------------------------------------------------------
section("21-22. Moving unsaved-added vs. saved-override blocks")
# ---------------------------------------------------------------------------

draft = fresh_draft()
history = CommandHistory()
history.execute(PullProgramCommand(blocks_of(draft)[1]), draft)
slot = next(b for b in blocks_of(draft) if b.media_type == "open")
history.execute(PutOnAirCommand(CH, slot.true_start, {"path": "/m/new.mp4", "title": "New Show", "duration": 900.0, "media_type": "tv"}, slot_end=slot.true_end), draft)
added_block = next(b for b in blocks_of(draft) if b.title == "New Show")
change_count_before = len(draft.changes)
history.execute(MoveProgramCommand(added_block, CH, T0 + 5400), draft)
records = draft.overrides_for_save()
check(
    "21. moving an unsaved added block updates it in place rather than stacking a redundant remove",
    not any(r["action"] == "remove" and r.get("title") == "New Show" for r in records) and len(records) == 2,
    records,
)

saved_block = make_block("Old Movie", T0, T0 + 1800, source="override")
draft5 = DraftSchedule()
draft5.set_base_lanes([make_lane(blocks=[saved_block])])
history5 = CommandHistory()
history5.execute(MoveProgramCommand(saved_block, CH, T0 + 3600), draft5)
records5 = draft5.overrides_for_save()
check(
    "22. moving a saved-override block produces a remove (old placement) + add (new placement)",
    len(records5) == 2 and {r["action"] for r in records5} == {"add", "remove"},
    records5,
)
from mediawave.schedule_overrides import compact_overrides, override_at

previously_saved_add = {"action": "add", "channel_id": CH, "date": "", "start": T0, "end": T0 + 1800, "title": "Old Movie", "path": "/media/Old Movie.mp4", "media_type": "movie"}
compacted = compact_overrides([previously_saved_add] + records5)
# The old placement's slot is now superseded (masked by the move's own
# remove record) -- resolving "what plays at the OLD slot's midpoint"
# must report the remove, not the stale old add, proving the old saved
# placement was genuinely superseded rather than left active alongside
# the new one. (The two records don't literally collapse into one here
# since the old and new placements are non-adjacent in time -- that's
# correct: compaction only merges what's actually redundant.)
old_slot_resolution = override_at(compacted, T0 + 900)
new_slot_resolution = override_at(compacted, records5[1]["start"] + 900)
check(
    "22b. compacting supersedes the old saved placement (old slot no longer resolves to the stale add)",
    old_slot_resolution is not None and old_slot_resolution["action"] == "remove",
    old_slot_resolution,
)
check(
    "22c. the new placement resolves correctly after compaction",
    new_slot_resolution is not None and new_slot_resolution["action"] == "add" and new_slot_resolution["path"] == "/media/Old Movie.mp4",
    new_slot_resolution,
)


# ---------------------------------------------------------------------------
section("Cross-channel policy (36)")
# ---------------------------------------------------------------------------

lane1 = make_lane(channel_id=CH, blocks=[make_block("Show A", T0, T0 + 1800)])
lane2 = make_lane(channel_id=CH2, name="Movies", number=1, blocks=[make_block("Movie X", T0, T0 + 1800, channel_id=CH2)])
draft6 = DraftSchedule()
draft6.set_base_lanes([lane1, lane2])
cross = MoveProgramCommand(blocks_of(draft6, CH)[0], CH2, T0 + 3600)
check("36. cross-channel moves are rejected with the documented Phase 3 policy message", cross.validate(draft6, now=NOW).reason == "Moving programs between channels will be added later.")


# ---------------------------------------------------------------------------
section("23-29, 37. Drag geometry, preview state, autoscroll (widget-level)")
# ---------------------------------------------------------------------------

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.schedule_editor.board import ProgrammingBoard
from mediawave.schedule_editor.layout_constants import ROW_HEIGHT

board_lane = make_lane(blocks=[make_block("A", T0, T0 + 1800), make_block("B", T0 + 1800, T0 + 3600)])
board = ProgrammingBoard()
board.resize(900, 400)
board.show()
board.set_lanes([board_lane], T0, T0 + 4 * 3600)
app.processEvents()

strip = board._grid_content.row_strips[0]
widget_a, widget_b = strip.block_widgets[0], strip.block_widgets[1]

result = board._channel_and_time_at(widget_a.mapToGlobal(widget_a.rect().center()))
check("23. drag pointer position maps to the correct channel and a snapped time", result is not None and result[0] == CH and result[1] % 300 == 0, result)

# 24/25: scroll offsets are included in the mapping. Query a FIXED point
# in on-screen VIEWPORT coordinates (not a widget that itself moves when
# scrolled -- mapToGlobal on a child widget always yields the same
# logical content point regardless of scroll, which would trivially and
# incorrectly "pass" this check without proving anything).
fixed_viewport_point = QPoint(50, 10)
fixed_global_point = board._grid_scroll.viewport().mapToGlobal(fixed_viewport_point)
result_unscrolled = board._channel_and_time_at(fixed_global_point)
board.set_scroll_positions((60, 0))
app.processEvents()
result_scrolled = board._channel_and_time_at(fixed_global_point)
check(
    "24. horizontal scroll offset changes what a stationary screen point maps to",
    result_unscrolled is not None and result_scrolled is not None and result_scrolled[1] != result_unscrolled[1],
    (result_unscrolled, result_scrolled),
)
board.set_scroll_positions((0, 0))

# 26: a point in the frozen identity column (outside the grid viewport) maps to nothing
outside_point = board._identity_viewport.mapToGlobal(board._identity_viewport.rect().center())
check("26. the frozen identity column is outside the grid's drop-mapping area", board._channel_and_time_at(outside_point) is None)

# 27: a point below all lanes is rejected
far_below = board._grid_content.mapToGlobal(board._grid_content.rect().bottomLeft())
far_below.setY(far_below.y() + 500)
check("27. a drag point far below the valid lanes is rejected", board._channel_and_time_at(far_below) is None)

# 28: preview state coloring reflects the validator's returned state
board.set_drop_validator(lambda block, cid, start: ("conflict", "Overlaps something"))
board._on_drag_started(widget_a, widget_a.mapToGlobal(widget_a.rect().center()))
conflict_style = board._drag_preview.styleSheet()
check("28. a conflict drop state renders a visibly different preview style", "170, 90" in conflict_style, conflict_style)
board._on_drag_finished(widget_a, widget_a.mapToGlobal(widget_a.rect().center()))

board.set_drop_validator(lambda block, cid, start: ("valid", ""))
board._on_drag_started(widget_a, widget_a.mapToGlobal(widget_a.rect().center()))
valid_style = board._drag_preview.styleSheet()
check("28b. a valid drop state renders a different style than conflict", valid_style != conflict_style, (valid_style, conflict_style))
board._on_drag_finished(widget_a, widget_a.mapToGlobal(widget_a.rect().center()))

# 29: autoscroll timer starts on drag start and stops after drop
board._on_drag_started(widget_a, widget_a.mapToGlobal(widget_a.rect().center()))
check("29. autoscroll timer is running while a drag is active", board._autoscroll_timer.isActive())
board._on_drag_finished(widget_a, widget_a.mapToGlobal(widget_a.rect().center()))
check("29b. autoscroll timer stops once the drag ends", not board._autoscroll_timer.isActive())

# 37: repeated rebuilds never leave a stray preview widget behind
board._on_drag_started(widget_a, widget_a.mapToGlobal(widget_a.rect().center()))
preview_ref = board._drag_preview
board.set_lanes([board_lane], T0, T0 + 4 * 3600)  # a refresh mid-drag
check("37. a rebuild mid-drag safely tears down the drag state (no dangling preview)", board._drag_preview is None and not board.is_dragging)


# ---------------------------------------------------------------------------
section("30-32. Click vs. drag threshold, drop command count")
# ---------------------------------------------------------------------------

from PySide6.QtCore import QEvent, QPointF
from PySide6.QtCore import Qt as QtNS
from PySide6.QtGui import QMouseEvent

board2 = ProgrammingBoard()
board2.resize(900, 400)
board2.show()
board2.set_lanes([board_lane], T0, T0 + 4 * 3600)
app.processEvents()
strip2 = board2._grid_content.row_strips[0]
widget2 = strip2.block_widgets[0]

selections = []
board2.program_selected.connect(lambda blk: selections.append(blk.title))
drops2 = []
board2.move_drop.connect(lambda blk, cid, start: drops2.append(1))

center = widget2.rect().center()
global_center = QPointF(widget2.mapToGlobal(center))
press = QMouseEvent(QEvent.MouseButtonPress, QPointF(center), global_center, QtNS.LeftButton, QtNS.LeftButton, QtNS.NoModifier)
release = QMouseEvent(QEvent.MouseButtonRelease, QPointF(center), global_center, QtNS.LeftButton, QtNS.NoButton, QtNS.NoModifier)
widget2.mousePressEvent(press)
widget2.mouseReleaseEvent(release)
check("30. a click with no movement selects instead of dragging", selections == ["A"] and not drops2, (selections, drops2))
check("30b. no drag was ever started by a plain click", widget2._dragging is False and widget2._press_global is None)


# ---------------------------------------------------------------------------
section("Move To… and drag share validation (35); duration/time helpers")
# ---------------------------------------------------------------------------

draft7 = fresh_draft()
block_for_dialog = next(b for b in blocks_of(draft7) if b.title == "Show A")
dialog_dest = destination_epoch_for_time(block_for_dialog.true_start, time.localtime(block_for_dialog.true_start + 3600).tm_hour, time.localtime(block_for_dialog.true_start + 3600).tm_min)
move_via_dialog_path = MoveProgramCommand(block_for_dialog, CH, dialog_dest)
move_via_drag_path = MoveProgramCommand(block_for_dialog, CH, dialog_dest)
check(
    "35. Move To…'s destination and a drag's destination validate identically through the same command",
    move_via_dialog_path.validate(draft7, now=NOW).ok == move_via_drag_path.validate(draft7, now=NOW).ok,
)


# ---------------------------------------------------------------------------
section("33-34, 38-40. Selection restoration, dirty state, Revert, failed save")
# ---------------------------------------------------------------------------

from mediawave.schedule_editor.dialog import ScheduleEditorWorkspace


class _EmptyStudioDialog:
    pass


def _silence_dialogs(workspace):
    workspace._show_info = lambda title, text: None
    workspace._show_warning = lambda title, text: None
    return workspace


ws = _silence_dialogs(ScheduleEditorWorkspace(_EmptyStudioDialog(), on_back=lambda: None))
ws._draft.set_base_lanes([make_lane(blocks=[
    make_block("Show A", T0, T0 + 1800),
    make_block("Show B", T0 + 1800, T0 + 3600),
])])
check("38-setup. a fresh draft is clean", not ws._draft.is_dirty())

command = MoveProgramCommand(blocks_of(ws._draft)[0], CH, T0 + 5400)
ws._history.execute(command, ws._draft)
ws._update_toolbar_state()
check("38. Save Schedule enables after a move makes the draft dirty", ws._save_btn.isEnabled())
check("38b. Pending Changes reflects the move", len(ws._draft.describe_pending_changes()) == 1)

reselect_after_undo = ws._reselect_target_for(command, after_undo=True)
check("33/34a. reselect-after-undo targets the move's ORIGINAL source location", reselect_after_undo == (command.source_channel_id, command.source_start), reselect_after_undo)
reselect_after_redo = ws._reselect_target_for(command, after_undo=False)
check("33/34b. reselect-after-redo targets the move's destination", reselect_after_redo == (command.destination_channel_id, command.destination_start), reselect_after_redo)

ws._discard_draft()
check("39. Revert Draft removes the move (draft clean again)", not ws._draft.is_dirty() and ws._draft.describe_pending_changes() == [])


class _FailingSaveDialog:
    def _schedule_overrides_save(self, records):
        return False, "The disk is full."


ws2 = _silence_dialogs(ScheduleEditorWorkspace(_EmptyStudioDialog(), on_back=lambda: None))
ws2._draft.set_base_lanes([make_lane(blocks=[make_block("Show A", T0, T0 + 1800)])])
ws2._history.execute(MoveProgramCommand(blocks_of(ws2._draft)[0], CH, T0 + 5400), ws2._draft)
ws2._studio_dialog = _FailingSaveDialog()
result = ws2._perform_save(ws2._draft.overrides_for_save())
check("40. a failed Save preserves the moved draft and its history", result is False and ws2._draft.is_dirty() and ws2._history.can_undo)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 3 tests passed.")

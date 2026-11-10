"""
Phase 4.5.2 Schedule Editor tests: Clear Day (ClearChannelDayCommand),
local_day_bounds, draft wording, Quick Actions wiring, and persistence.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase452_clear_day.py
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
    CONFLICT_PROTECTED_BLOCK,
    ClearChannelDayCommand,
    CommandHistory,
    local_day_bounds,
)
from mediawave.schedule_editor.draft_model import DraftSchedule
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock

NOW = time.time()
CH = "media:/catalog/Comedy"


def make_lane(channel_id=CH, blocks=None, name="Comedy", number=4, channel_type="media", has_data=True):
    return ChannelLane(channel_id=channel_id, name=name, number=number, channel_type=channel_type, logo_path="", blocks=blocks or [], has_data=has_data)


def make_block(title, start, end, channel_id=CH, media_type="tv"):
    return ProgramBlock(
        channel_id=channel_id, title=title, media_type=media_type, start=start, end=end,
        duration=end - start, is_commercial=False, source="generated",
        true_start=start, true_end=end,
        raw_entries=[{"kind": "content", "path": f"/media/{title}.mp4", "title": title, "duration": end - start}],
    )


# ---------------------------------------------------------------------------
section("local_day_bounds")
# ---------------------------------------------------------------------------

anchor_local = time.localtime(NOW)
# A time deliberately in the middle of the day, so start/end aren't
# accidentally correct because the input was already midnight-aligned.
mid_afternoon = time.mktime((anchor_local.tm_year, anchor_local.tm_mon, anchor_local.tm_mday, 15, 30, 0, 0, 0, -1))

day_start, day_end = local_day_bounds(mid_afternoon)
check("1. day_start is local midnight of the containing day", time.localtime(day_start)[3:6] == (0, 0, 0), time.localtime(day_start))
check("2. day_end is local midnight of the NEXT day", time.localtime(day_end)[3:6] == (0, 0, 0), time.localtime(day_end))
check("3. day_start is strictly before the input instant", day_start <= mid_afternoon < day_end)
check("4. day_start/day_end are on consecutive calendar days", time.localtime(day_end).tm_yday == time.localtime(day_start).tm_yday + 1 or time.localtime(day_end).tm_year != time.localtime(day_start).tm_year, (time.localtime(day_start), time.localtime(day_end)))

exact_midnight = day_start
check("5. an input that's already midnight resolves to itself as day_start", local_day_bounds(exact_midnight)[0] == day_start, local_day_bounds(exact_midnight))

next_day_start, next_day_end = local_day_bounds(day_end)
check("6. calling local_day_bounds on the previous day's end gives the next day's own bounds", next_day_start == day_end, (day_end, next_day_start))
check("7. a day's own span is between 23 and 25 hours (never a hardcoded 86400)", 23 * 3600 <= (day_end - day_start) <= 25 * 3600, day_end - day_start)


# ---------------------------------------------------------------------------
section("ClearChannelDayCommand: validation, apply, undo, redo")
# ---------------------------------------------------------------------------

T0 = mid_afternoon
draft = DraftSchedule()
draft.set_base_lanes([make_lane(blocks=[
    make_block("Show A", T0 - 3600, T0),
    make_block("Show B", T0, T0 + 3600),
    make_block("Show C", T0 + 3600, T0 + 7200),
])])
history = CommandHistory()

day_start, day_end = local_day_bounds(T0)
cmd = ClearChannelDayCommand(CH, day_start, day_end)
v = cmd.validate(draft, now=NOW)
check("8. clearing today's (future-inclusive) day validates cleanly", v.ok, v.reason)

history.execute(cmd, draft)
lane = next(l for l in draft.presentation_lanes(day_start, day_end) if l.channel_id == CH)
check(
    "9. after apply, the ENTIRE requested span presents as one Open Time block",
    len(lane.blocks) == 1 and lane.blocks[0].media_type == "open" and lane.blocks[0].true_start == day_start and lane.blocks[0].true_end == day_end,
    [(b.title, b.media_type, b.true_start, b.true_end) for b in lane.blocks],
)

rows = draft.describe_pending_changes()
check("10. Clear Day collapses to exactly ONE Pending Changes row", len(rows) == 1, rows)
check("10b. the row uses friendly wording, not internal terms", "Cleared" in rows[0]["headline"] and "lineup" in rows[0]["headline"], rows[0])
check("10c. the row names the channel and says 'Full day'", "Comedy" in rows[0]["subline"] and "Full day" in rows[0]["subline"], rows[0])
check("10d. the row headline/subline never say 'override', 'command', 'tombstone', or 'suppression'", not any(word in (rows[0]["headline"] + rows[0]["subline"]).lower() for word in ("override", "command", "tombstone", "suppression")), rows[0])

check("11. exactly one command-history entry was added", len(history._undo_stack) == 1, len(history._undo_stack))

history.undo(draft)
lane = next(l for l in draft.presentation_lanes(day_start, day_end) if l.channel_id == CH)
check(
    "12. undo restores the exact prior state (three original blocks)",
    [(b.title, b.true_start, b.true_end) for b in lane.blocks] == [("Show A", T0 - 3600, T0), ("Show B", T0, T0 + 3600), ("Show C", T0 + 3600, T0 + 7200)],
    [(b.title, b.true_start, b.true_end) for b in lane.blocks],
)

history.redo(draft)
lane = next(l for l in draft.presentation_lanes(day_start, day_end) if l.channel_id == CH)
check("13. redo clears the day again", len(lane.blocks) == 1 and lane.blocks[0].media_type == "open", [(b.title, b.media_type) for b in lane.blocks])


# ---------------------------------------------------------------------------
section("Protected lane / invalid span")
# ---------------------------------------------------------------------------

locked_draft = DraftSchedule()
locked_draft.set_base_lanes([make_lane(channel_id="weatherstar:1", channel_type="weatherstar", blocks=[
    make_block("Weather", day_start, day_end, channel_id="weatherstar:1"),
])])
locked_cmd = ClearChannelDayCommand("weatherstar:1", day_start, day_end)
v2 = locked_cmd.validate(locked_draft, now=NOW)
check(
    "14. a protected/companion channel rejects Clear Day with the existing locked-lane reason",
    not v2.ok and v2.conflicts and v2.conflicts[0]["type"] == CONFLICT_PROTECTED_BLOCK,
    v2,
)

bad_span_cmd = ClearChannelDayCommand(CH, day_end, day_start)  # end before start
v3 = bad_span_cmd.validate(draft, now=NOW)
check("15. an invalid (end <= start) span is rejected", not v3.ok, v3)


# ---------------------------------------------------------------------------
section("Interval spans the FULL local day, not just a narrow viewport window")
# ---------------------------------------------------------------------------

viewport_draft = DraftSchedule()
viewport_draft.set_base_lanes([make_lane(blocks=[make_block("All-day rerun", day_start, day_end)])])
viewport_cmd = ClearChannelDayCommand(CH, day_start, day_end)
viewport_cmd.apply(viewport_draft)

# A narrow 4.5-hour "board viewport" window somewhere in the middle of
# the day should ALSO show Open Time -- the change itself is anchored to
# the full day, independent of whatever window presentation_lanes() is
# asked to render.
narrow_start = day_start + 10 * 3600
narrow_end = narrow_start + 4.5 * 3600
narrow_lane = next(l for l in viewport_draft.presentation_lanes(narrow_start, narrow_end) if l.channel_id == CH)
check(
    "16. a narrow mid-day viewport also shows Open Time -- the clear isn't limited to whatever window it was created from",
    all(b.media_type == "open" for b in narrow_lane.blocks),
    [(b.title, b.media_type) for b in narrow_lane.blocks],
)
# And the very end of the day (near the next midnight) too.
late_lane = next(l for l in viewport_draft.presentation_lanes(day_end - 1800, day_end) if l.channel_id == CH)
check("16b. the last half hour of the day is also Open Time", all(b.media_type == "open" for b in late_lane.blocks), late_lane.blocks)


# ---------------------------------------------------------------------------
section("Quick Actions: selection wiring, enablement, protected lane")
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

import mediawave.schedule_editor.dialog as dialog_module
from mediawave.schedule_editor.dialog import ScheduleEditorWorkspace
from mediawave.schedule_overrides import (
    load_schedule_overrides,
    save_schedule_overrides,
    splice_overrides_into_window,
)

UI_CH = "ch1"
# Anchored 2 days out (not just "today at 3 PM"), same reason
# test_schedule_phase31.py's T0 is: "NOW + a few hours" wanders into the
# past whenever the suite happens to run late in the day, which would
# spuriously fail every "already aired" validate() check below.
_anchor_local = time.localtime(NOW)
UI_T0 = time.mktime((_anchor_local.tm_year, _anchor_local.tm_mon, _anchor_local.tm_mday, 15, 0, 0, 0, 0, -1)) + 2 * 24 * 3600


def ui_make_lane(channel_id=UI_CH, blocks=None, name="Comedy", number=4, channel_type="media", has_data=True):
    return ChannelLane(channel_id=channel_id, name=name, number=number, channel_type=channel_type, logo_path="", blocks=blocks or [], has_data=has_data)


def ui_make_block(title, start, end, channel_id=UI_CH, media_type="tv"):
    return ProgramBlock(
        channel_id=channel_id, title=title, media_type=media_type, start=start, end=end,
        duration=end - start, is_commercial=False, source="generated",
        true_start=start, true_end=end,
        raw_entries=[{"kind": "content", "path": f"/media/{title}.mp4", "title": title, "duration": end - start}],
    )


class _UIFakeStudioDialog:
    def __init__(self, save_ok=True, save_error=""):
        self.catalog_channel_infos = [{"id": UI_CH, "name": "Comedy", "channel_type": "media", "default_number": 4}]
        self.catalog_channel_settings = {}
        self._studio_channels_by_id = {}
        self.info_calls = []
        self.warning_calls = []
        self.saved_records = []
        self.save_calls = 0
        self._save_ok = save_ok
        self._save_error = save_error

    def _schedule_overrides_save(self, records):
        self.save_calls += 1
        if not self._save_ok:
            return False, self._save_error
        self.saved_records.append(list(records))
        return True, ""


def make_ui_workspace(**kwargs):
    studio = _UIFakeStudioDialog(**kwargs)
    ws = ScheduleEditorWorkspace(studio)
    ws._window_start = UI_T0
    ws._show_info = lambda title, text: studio.info_calls.append((title, text))
    ws._show_warning = lambda title, text: studio.warning_calls.append((title, text))
    return ws, studio


def ui_lane(ws, channel_id=UI_CH):
    return next(l for l in ws._draft.presentation_lanes() if l.channel_id == channel_id)


ui_ws, ui_studio = make_ui_workspace()
if ui_ws.board is not None:
    ui_ws._draft.set_base_lanes([ui_make_lane(blocks=[ui_make_block("Show A", UI_T0, UI_T0 + 3600)])])
    ui_ws._render_draft()

    check("17a. Clear Day… lives inside Editing Tools' own controls, not a separate card", "clear_day_btn" in ui_ws._tools)
    check("17b. the standalone Quick Actions card no longer exists", not hasattr(ui_ws, "_quick_actions_card") and not hasattr(ui_ws, "_quick_actions"))
    check("17. Clear Day… is disabled with no selection at all", not ui_ws._tools["clear_day_btn"].isEnabled())

    ui_ws._on_channel_selected(UI_CH)
    check(
        "18. Clear Day… is enabled from a channel-ROW selection alone (no block selected)",
        ui_ws._tools["clear_day_btn"].isEnabled() and ui_ws._selected_block is None,
    )
    check(
        "18b. block-level Editing Tools buttons stay disabled in that channel-only state",
        not ui_ws._tools["pull_btn"].isEnabled() and not ui_ws._tools["move_btn"].isEnabled()
        and not ui_ws._tools["put_btn"].isEnabled() and not ui_ws._tools["fill_btn"].isEnabled()
        and not ui_ws._tools["auto_fill_btn"].isEnabled(),
        {k: v.isEnabled() for k, v in ui_ws._tools.items() if hasattr(v, "isEnabled")},
    )
    check(
        "18c. Programming Blocks… is the one exception -- always enabled, even with only a channel selected",
        ui_ws._tools["programming_blocks_btn"].isEnabled(),
    )

    real_block = ui_lane(ui_ws).blocks[0]
    ui_ws._on_program_selected(real_block)
    check("19. Clear Day… is also enabled from a PROGRAM selection on that channel", ui_ws._tools["clear_day_btn"].isEnabled())

    locked_ws2, _ = make_ui_workspace()
    locked_ws2._draft.set_base_lanes([ui_make_lane(channel_type="weatherstar", blocks=[ui_make_block("Weather", UI_T0, UI_T0 + 1800)])])
    locked_ws2._render_draft()
    locked_ws2._on_channel_selected(UI_CH)
    clear_btn = locked_ws2._tools["clear_day_btn"]
    check(
        "20. a protected/companion channel replaces the WHOLE Editing Tools grid (Clear Day… included) with the locked message",
        clear_btn.parentWidget() is not None and clear_btn.parentWidget().isHidden() and not clear_btn.isEnabled(),
    )
else:
    check("17-20. Clear Day in Editing Tools wiring (skipped — no live board in this environment)", True)


# ---------------------------------------------------------------------------
section("Confirmation dialog: Cancel changes nothing")
# ---------------------------------------------------------------------------


def make_fake_conflict_dialog(forced_result):
    class _Fake:
        def __init__(self, *args, **kwargs):
            self.result = forced_result

        def exec(self):
            return None
    return _Fake


if ui_ws.board is not None:
    cancel_ws, cancel_studio = make_ui_workspace()
    cancel_ws._draft.set_base_lanes([ui_make_lane(blocks=[ui_make_block("Show A", UI_T0, UI_T0 + 3600)])])
    cancel_ws._render_draft()
    cancel_ws._on_channel_selected(UI_CH)
    before_changes = len(cancel_ws._draft.changes)
    before_history = len(cancel_ws._history._undo_stack)

    original_dialog_cls = dialog_module.ConflictDialog
    dialog_module.ConflictDialog = make_fake_conflict_dialog("cancel")
    try:
        cancel_ws._clear_day_clicked()
    finally:
        dialog_module.ConflictDialog = original_dialog_cls
    check("21. clicking Cancel in the confirmation makes no draft changes", len(cancel_ws._draft.changes) == before_changes)
    check("21b. clicking Cancel adds nothing to command history", len(cancel_ws._history._undo_stack) == before_history)
else:
    check("21-21b. Cancel confirmation (skipped — no live board in this environment)", True)


# ---------------------------------------------------------------------------
section("Apply flow: full local-day span, one history entry, one Pending Changes row")
# ---------------------------------------------------------------------------

if ui_ws.board is not None:
    apply2_ws, apply2_studio = make_ui_workspace()
    apply2_ws._draft.set_base_lanes([ui_make_lane(blocks=[
        ui_make_block("Show A", UI_T0, UI_T0 + 1800),
        ui_make_block("Show B", UI_T0 + 1800, UI_T0 + 3600),
    ])])
    apply2_ws._render_draft()
    apply2_ws._on_channel_selected(UI_CH)

    dialog_module.ConflictDialog = make_fake_conflict_dialog("clear")
    try:
        apply2_ws._clear_day_clicked()
    finally:
        dialog_module.ConflictDialog = original_dialog_cls

    check("22. apply adds exactly one DraftChange", len(apply2_ws._draft.changes) == 1, apply2_ws._draft.changes)
    added = apply2_ws._draft.changes[0]
    expected_start, expected_end = local_day_bounds(UI_T0)
    check(
        "23. the change spans the full LOCAL day, not just the ~4.5-hour board viewport",
        added.start == expected_start and added.end == expected_end and (added.end - added.start) > 20 * 3600,
        (added.start, added.end, expected_start, expected_end),
    )
    check("24. exactly one command-history entry was created", len(apply2_ws._history._undo_stack) == 1, len(apply2_ws._history._undo_stack))
    rows = apply2_ws._draft.describe_pending_changes()
    check("25. exactly one grouped Pending Changes row exists", len(rows) == 1, rows)
    check("25b. the selected channel stays active after apply", apply2_ws._selected_channel_id == UI_CH)
else:
    check("22-25b. apply flow (skipped — no live board in this environment)", True)


# ---------------------------------------------------------------------------
section("Earlier unsaved edits are masked, not deleted -- Undo/Redo ordering")
# ---------------------------------------------------------------------------

if ui_ws.board is not None:
    from mediawave.schedule_editor.commands import PutOnAirCommand, AutoFillBlockCommand

    order_ws, order_studio = make_ui_workspace()
    order_ws._draft.set_base_lanes([ui_make_lane(blocks=[ui_make_block("Open Time", UI_T0, UI_T0 + 5400, media_type="open")])])
    order_ws._render_draft()

    # 1. Manual placement.
    manual_media = {"path": "/media/Manual.mp4", "title": "Manual", "duration": 1800, "media_type": "tv"}
    manual_cmd = PutOnAirCommand(UI_CH, UI_T0, manual_media)
    order_ws._history.execute(manual_cmd, order_ws._draft)
    check("26. the manual placement is present before Clear Day", any(c.title == "Manual" for c in order_ws._draft.changes))

    # 2. Clear Day.
    day_start2, day_end2 = local_day_bounds(UI_T0)
    clear_cmd = ClearChannelDayCommand(UI_CH, day_start2, day_end2)
    order_ws._history.execute(clear_cmd, order_ws._draft)
    check(
        "27. Clear Day MASKS the manual placement (day presents as Open Time) without deleting its change",
        all(b.media_type == "open" for b in ui_lane(order_ws).blocks) and any(c.title == "Manual" for c in order_ws._draft.changes),
        [(b.title, b.media_type) for b in ui_lane(order_ws).blocks],
    )

    # 3. Auto-Fill part of the day.
    autofill_lineup = [{"path": "/media/AF.mp4", "title": "AF Show", "episode_label": "", "media_type": "tv", "duration": 1800, "channel_name": "Comedy", "start": UI_T0, "end": UI_T0 + 1800}]
    autofill_cmd = AutoFillBlockCommand(UI_CH, UI_T0, UI_T0 + 1800, autofill_lineup)
    order_ws._history.execute(autofill_cmd, order_ws._draft)
    check("28. Auto-Fill placed its own program over the cleared span", any(b.title == "AF Show" for b in ui_lane(order_ws).blocks), ui_lane(order_ws).blocks)

    # 4. Undo once -- expect ONLY the Auto-Fill to be removed.
    order_ws._history.undo(order_ws._draft)
    check(
        "29. one Undo removes ONLY the Auto-Fill (day is fully Open Time again, manual placement still masked-not-deleted)",
        all(b.media_type == "open" for b in ui_lane(order_ws).blocks) and any(c.title == "Manual" for c in order_ws._draft.changes),
        [(b.title, b.media_type) for b in ui_lane(order_ws).blocks],
    )

    # Another Undo -- expect the state before Clear Day (the manual placement, unmasked).
    order_ws._history.undo(order_ws._draft)
    check(
        "30. a second Undo restores the state before Clear Day (the manual placement reappears)",
        any(b.title == "Manual" for b in ui_lane(order_ws).blocks),
        ui_lane(order_ws).blocks,
    )

    # Redo -- Clear Day re-applies.
    order_ws._history.redo(order_ws._draft)
    check("31. Redo clears the day again", all(b.media_type == "open" for b in ui_lane(order_ws).blocks), ui_lane(order_ws).blocks)
else:
    check("26-31. masking/undo-ordering (skipped — no live board in this environment)", True)


# ---------------------------------------------------------------------------
section("Auto-Fill works over the resulting Open Time")
# ---------------------------------------------------------------------------

af_ws, af_studio = make_ui_workspace()
af_ws._draft.set_base_lanes([ui_make_lane(blocks=[ui_make_block("Show A", UI_T0, UI_T0 + 3600)])])
af_ws._render_draft()
af_ws._on_channel_selected(UI_CH)
day_start3, day_end3 = local_day_bounds(UI_T0)
af_ws._try_clear_day(UI_CH, day_start3, day_end3)

from mediawave.schedule_editor.commands import AutoFillBlockCommand as _AFCommand

af_lineup = [{"path": "/media/Fresh.mp4", "title": "Fresh Program", "episode_label": "", "media_type": "tv", "duration": 1800, "channel_name": "Comedy", "start": UI_T0, "end": UI_T0 + 1800}]
af_cmd = _AFCommand(UI_CH, UI_T0, UI_T0 + 1800, af_lineup)
af_validation = af_cmd.validate(af_ws._draft)
check("32. AutoFillBlockCommand validates cleanly over the cleared day's Open Time", af_validation.ok, af_validation.reason)
af_ws._history.execute(af_cmd, af_ws._draft)
check("33. the new placement appears normally after Clear Day", any(b.title == "Fresh Program" for b in ui_lane(af_ws).blocks), ui_lane(af_ws).blocks)


# ---------------------------------------------------------------------------
section("Other channels and other dates are unchanged")
# ---------------------------------------------------------------------------

multi_ws, multi_studio = make_ui_workspace()
OTHER_CH = "ch2"
multi_ws._draft.set_base_lanes([
    ui_make_lane(channel_id=UI_CH, blocks=[ui_make_block("Ch1 Show", UI_T0, UI_T0 + 3600)]),
    ui_make_lane(channel_id=OTHER_CH, name="Cartoons", number=5, blocks=[ui_make_block("Ch2 Show", UI_T0, UI_T0 + 3600, channel_id=OTHER_CH)]),
])
multi_ws._render_draft()
multi_ws._on_channel_selected(UI_CH)
day_start4, day_end4 = local_day_bounds(UI_T0)
multi_ws._try_clear_day(UI_CH, day_start4, day_end4)

check("34. the CLEARED channel's day is Open Time", all(b.media_type == "open" for b in ui_lane(multi_ws, UI_CH).blocks))
check("35. the OTHER channel is completely unaffected", [b.title for b in ui_lane(multi_ws, OTHER_CH).blocks] == ["Ch2 Show"], ui_lane(multi_ws, OTHER_CH).blocks)

next_day_start = day_start4 + 25 * 3600
next_day_probe_lane = next(
    l for l in multi_ws._draft.presentation_lanes(next_day_start, next_day_start + 3600) if l.channel_id == UI_CH
)
check(
    "36. a different date on the SAME channel is unaffected (the change's interval doesn't leak past its own day)",
    not any(b.media_type == "open" and b.true_start < day_end4 for b in next_day_probe_lane.blocks),
    next_day_probe_lane.blocks,
)


# ---------------------------------------------------------------------------
section("Persistence: save/reload, and regeneration doesn't repopulate the cleared day")
# ---------------------------------------------------------------------------

persist_ws, persist_studio = make_ui_workspace()
persist_ws._draft.set_base_lanes([ui_make_lane(blocks=[ui_make_block("Show A", UI_T0, UI_T0 + 3600)])])
persist_ws._render_draft()
persist_ws._on_channel_selected(UI_CH)
day_start5, day_end5 = local_day_bounds(UI_T0)
persist_ws._try_clear_day(UI_CH, day_start5, day_end5)

ok = persist_ws._save_clicked()
check("37. Save Schedule succeeds for a Clear Day change", ok)
check("37b. the save pipeline received exactly one override record for the whole day", len(persist_studio.saved_records[0]) == 1 and persist_studio.saved_records[0][0]["action"] == "remove", persist_studio.saved_records)

import tempfile

with tempfile.TemporaryDirectory() as tmp_dir:
    overrides_path = os.path.join(tmp_dir, "schedule_overrides.json")
    saved_ok, save_err = save_schedule_overrides(overrides_path, {"version": 1, "overrides": persist_studio.saved_records[0]}, now=NOW)
    check("38. the override file itself saves successfully", saved_ok, save_err)

    reloaded = load_schedule_overrides(overrides_path)  # simulates an app restart
    check("39. after 'restart', the override still exists and still covers the whole day", len(reloaded["overrides"]) == 1 and reloaded["overrides"][0]["start"] == day_start5 and reloaded["overrides"][0]["end"] == day_end5, reloaded)

    # Simulate the generated schedule coming back DIFFERENTLY after
    # restart (new catalog contents, different shuffle, etc.) -- the
    # override must still blank out the whole day regardless.
    differently_generated_items = [
        {"path": "/media/NewShowA.mp4", "title": "New Show A", "start": day_start5, "end": day_start5 + 7200},
        {"path": "/media/NewShowB.mp4", "title": "New Show B", "start": day_start5 + 7200, "end": day_end5},
    ]
    spliced = splice_overrides_into_window(differently_generated_items, reloaded["overrides"])
    check(
        "40. regeneration with entirely different content still produces an all-Open-Time day (the override doesn't depend on the old blocks)",
        all(item["entry"]["kind"] == "open_time" for item in spliced) and spliced[0]["start"] == day_start5 and spliced[-1]["end"] == day_end5,
        spliced,
    )


# ---------------------------------------------------------------------------
section("Save failure leaves the draft dirty")
# ---------------------------------------------------------------------------

fail_ws, fail_studio = make_ui_workspace(save_ok=False, save_error="Disk is full.")
fail_ws._draft.set_base_lanes([ui_make_lane(blocks=[ui_make_block("Show A", UI_T0, UI_T0 + 3600)])])
fail_ws._render_draft()
fail_ws._on_channel_selected(UI_CH)
day_start6, day_end6 = local_day_bounds(UI_T0)
fail_ws._try_clear_day(UI_CH, day_start6, day_end6)
ok2 = fail_ws._save_clicked()
check("41. a failed save reports failure", not ok2)
check("42. the draft remains dirty after a failed save (nothing lost)", fail_ws._draft.is_dirty())


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All Phase 4.5.2 Clear Day tests passed.")

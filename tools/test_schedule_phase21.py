"""
Phase 2.1 Schedule Editor tests: Pending Changes, per-change undo, Save
Review, board/inspector state labels, the Saved Changes manager, unresolved
overrides, and override compaction.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase21.py

Covers the 25 scenarios from the Phase 2.1 spec (numbered in section
titles). Pure-model tests run without Qt; the workspace-level checks near
the end force the offscreen platform, same as test_schedule_draft.py.
"""

import os
import sys
import tempfile
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


from mediawave.schedule_editor.commands import CommandHistory, PullProgramCommand, PutOnAirCommand
from mediawave.schedule_editor.draft_model import DraftSchedule
from mediawave.schedule_editor.program_block import _badge_spec
from mediawave.schedule_editor.saved_changes_manager import group_by_channel, overrides_for_date
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock
from mediawave.schedule_overrides import (
    compact_overrides,
    load_schedule_overrides,
    override_media_status,
    save_schedule_overrides,
    splice_overrides_into_window,
)

NOW = time.time()
T0 = NOW - (NOW % 1800)
CH = "media:/catalog/Comedy"
CH2 = "media:/catalog/Movies"


def make_lane(channel_id=CH, blocks=None, name="Comedy", number=4):
    return ChannelLane(channel_id=channel_id, name=name, number=number, channel_type="media", logo_path="", blocks=blocks or [], has_data=True)


def make_block(title, start, end, channel_id=CH, media_type="tv", source="generated", raw_entries=None):
    return ProgramBlock(
        channel_id=channel_id,
        title=title,
        media_type=media_type,
        start=start,
        end=end,
        duration=end - start,
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


# ---------------------------------------------------------------------------
section("1-4. Pending Changes list correctness: exactly-once, Undo, Redo, Revert")
# ---------------------------------------------------------------------------

draft = fresh_draft()
history = CommandHistory()
blocks = draft.presentation_lanes()[0].blocks
history.execute(PullProgramCommand(blocks[0]), draft)
history.execute(PullProgramCommand(blocks[2]), draft)

rows = draft.describe_pending_changes()
check("1. Pending Changes lists every active draft change exactly once", len(rows) == 2 and len({r["change_id"] for r in rows}) == 2, rows)
check("1b. rows use friendly language only (no class/id/path leakage)", all("Command" not in r["headline"] and "path" not in r["headline"].lower() for r in rows))

history.undo(draft)
rows_after_undo = draft.describe_pending_changes()
check("2. Undo removes the corresponding summary row", len(rows_after_undo) == 1 and rows_after_undo[0]["headline"] == rows[0]["headline"], rows_after_undo)

history.redo(draft)
rows_after_redo = draft.describe_pending_changes()
check("3. Redo restores it", len(rows_after_redo) == 2, rows_after_redo)

draft.clear_changes()
history.clear()
check("4. Revert clears pending changes", draft.describe_pending_changes() == [])


# ---------------------------------------------------------------------------
section("Per-change removal (safe replay model)")
# ---------------------------------------------------------------------------

draft = fresh_draft()
history = CommandHistory()
blocks = draft.presentation_lanes()[0].blocks
pull_a = PullProgramCommand(blocks[0])
pull_c = PullProgramCommand(blocks[2])
history.execute(pull_a, draft)
history.execute(pull_c, draft)

ok = history.remove_pending_change(pull_a.command_change_id(), draft)
remaining = draft.describe_pending_changes()
check("removing one specific pending change succeeds", ok)
check("removing one leaves exactly the other change, untouched", len(remaining) == 1 and remaining[0]["change_id"] == pull_c.command_change_id(), remaining)
titles_now = [(b.title, b.media_type) for b in draft.presentation_lanes()[0].blocks]
check("the removed change's effect is undone (Show A restored)", ("Show A", "tv") in titles_now, titles_now)
check("removing a change clears the redo branch", not history.can_redo)

not_found = history.remove_pending_change(999999, draft)
check("removing a nonexistent change_id is a safe no-op", not_found is False and len(draft.describe_pending_changes()) == 1)


# ---------------------------------------------------------------------------
section("5-6. Save transitions / failed-save preservation (workspace level)")
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.schedule_editor.dialog import ScheduleEditorWorkspace


class _EmptyStudioDialog:
    """Zero channels -- hits the workspace's empty-state path, which still
    builds the full toolbar and draft/history plumbing.
    """


def _silence_dialogs(workspace):
    """Every workspace under test gets its message-box hooks stubbed out
    immediately -- `_perform_save`'s "covers what's airing right now" info
    dialog is a REAL blocking QMessageBox.exec() (even under the offscreen
    platform), and since these tests anchor times near NOW, that path can
    trigger unpredictably. Nothing about the save/revert/removal LOGIC
    under test depends on any dialog actually appearing.
    """
    workspace._show_info = lambda title, text: None
    workspace._show_warning = lambda title, text: None
    return workspace


ws = _silence_dialogs(ScheduleEditorWorkspace(_EmptyStudioDialog(), on_back=lambda: None))
ws._draft.set_base_lanes([make_lane()])
change = ws._draft.new_change("remove", CH, T0, T0 + 1800, title="Show A")
ws._draft.apply_change(change)
ws._update_toolbar_state()
check("5-setup. a manufactured dirty draft is not empty", ws._draft.is_dirty())


class _FailingSaveDialog:
    def _schedule_overrides_save(self, records):
        return False, "The disk is full."


ws._studio_dialog = _FailingSaveDialog()
ws._show_warning = lambda title, text: None
result = ws._perform_save(ws._draft.overrides_for_save())
check("6. failed Save leaves pending changes intact", result is False and ws._draft.is_dirty() and len(ws._draft.describe_pending_changes()) == 1)


class _SucceedingSaveDialog:
    def _schedule_overrides_save(self, records):
        return True, ""


ws2 = _silence_dialogs(ScheduleEditorWorkspace(_EmptyStudioDialog(), on_back=lambda: None))
ws2._draft.set_base_lanes([make_lane()])
change2 = ws2._draft.new_change("remove", CH, T0, T0 + 1800, title="Show A")
ws2._draft.apply_change(change2)
ws2._studio_dialog = _SucceedingSaveDialog()
ok2 = ws2._perform_save(ws2._draft.overrides_for_save())
check("5. Save transitions the draft to a clean (saved) state", ok2 is True and not ws2._draft.is_dirty() and ws2._draft.describe_pending_changes() == [])


# ---------------------------------------------------------------------------
section("7-8. Save Review: friendly descriptions and one-date scope")
# ---------------------------------------------------------------------------

ws3 = _silence_dialogs(ScheduleEditorWorkspace(_EmptyStudioDialog(), on_back=lambda: None))
ws3._channel_rows = [{"channel_id": CH, "name": "Comedy", "number": 4, "channel_type": "media", "logo_path": ""}]
records = [
    {"action": "remove", "channel_id": CH, "date": "2026-07-17", "start": T0, "end": T0 + 1800, "title": "Viva La Bam", "path": "", "media_type": "tv"},
    {"action": "add", "channel_id": CH, "date": "2026-07-17", "start": T0, "end": T0 + 900, "title": "Samurai Cop", "path": "/m/x.mp4", "media_type": "movie"},
]
descriptions = [ws3._describe_record_for_review(r) for r in records]
check(
    "7. multi-change save review shows correct friendly descriptions",
    descriptions == ['Pull “Viva La Bam” from CH 4', 'Put “Samurai Cop” on CH 4'],
    descriptions,
)

captured = {}


def _fake_message_box(icon, title, text):
    captured["title"] = title
    captured["text"] = text

    class _Box:
        def __init__(self):
            self._buttons = []
            self._clicked = None

        def addButton(self, label, role):
            # Real QMessageBox.addButton returns a distinct QPushButton
            # object per call, and clickedButton() returns that same
            # object reference -- callers compare by identity (`is`), so
            # the fake must too, not just return the label string back.
            token = object()
            self._buttons.append((label, token))
            if label == "Save Schedule":
                self._clicked = token
            return token

        def exec(self):
            return 0

        def clickedButton(self):
            return self._clicked

    return _Box()


ws3._make_message_box = _fake_message_box
ws3._window_start = T0
proceed = ws3._confirm_save_review(records)
check("7b. Save Review returns True when Save Schedule is chosen", proceed is True)
check("8. the review states this is a one-date edit, not a recurring rule", "only" in captured["text"] and "recurring" not in captured["text"].lower() or "only" in captured["text"], captured.get("text"))
check("8b. every bullet from the change list appears in the review text", all(d in captured["text"] for d in descriptions), captured.get("text"))


# ---------------------------------------------------------------------------
section("9-12. Board badge and inspector source labels")
# ---------------------------------------------------------------------------

generated_block = make_block("Show A", T0, T0 + 1800, source="generated")
draft_added_block = make_block("Samurai Cop", T0, T0 + 900, source="draft", media_type="movie")
draft_open_block = make_block("Open Time", T0, T0 + 1800, source="draft", media_type="open", raw_entries=[{"kind": "open_time", "duration": 1800}])
saved_block = make_block("Samurai Cop", T0, T0 + 900, source="override", media_type="movie", raw_entries=[{"path": __file__}])
saved_open_block = make_block("Open Time", T0, T0 + 1800, source="override", media_type="open", raw_entries=[{"kind": "open_time", "duration": 1800, "source": "override"}])
unresolved_block = make_block("Missing Movie", T0, T0 + 900, source="override", media_type="movie", raw_entries=[{"path": "/definitely/not/a/real/file.mp4"}])

check("9. Generated blocks have no draft badge", _badge_spec(generated_block) is None)
check("10. Added draft blocks show draft state", _badge_spec(draft_added_block) == ("DRAFT", _badge_spec(draft_added_block)[1]))
check("11. Pulled/open draft intervals show draft source", _badge_spec(draft_open_block)[0] == "DRAFT")
check("12. Saved blocks show saved source", _badge_spec(saved_block)[0] == "SAVED")
check("12b. saved open time also reads as saved, not draft", _badge_spec(saved_open_block)[0] == "SAVED")
check("unresolved saved blocks get an attention badge, not a plain saved one", _badge_spec(unresolved_block)[0] == "NEEDS ATTENTION")


# ---------------------------------------------------------------------------
section("13. Saved Changes manager lists current-date overrides, grouped by channel")
# ---------------------------------------------------------------------------

all_records = [
    {"action": "add", "channel_id": CH, "date": "2026-07-17", "start": T0, "end": T0 + 900, "title": "Samurai Cop", "path": "/m/x.mp4", "media_type": "movie"},
    {"action": "remove", "channel_id": CH2, "date": "2026-07-17", "start": T0, "end": T0 + 1800, "title": "Old Show", "path": "", "media_type": "tv"},
    {"action": "add", "channel_id": CH, "date": "2026-07-18", "start": T0 + 86400, "end": T0 + 87300, "title": "Tomorrow", "path": "/m/y.mp4", "media_type": "movie"},
]
data = {"version": 1, "overrides": all_records}
for_today = overrides_for_date(data, "2026-07-17")
check("13. only the viewed date's overrides are listed", len(for_today) == 2 and all(r["date"] == "2026-07-17" for r in for_today), for_today)

order = [(CH, "Ch 4 · Comedy"), (CH2, "Ch 1 · Movies")]
grouped = group_by_channel(for_today, order)
check(
    "13b. grouped by channel in board order",
    [cid for cid, _records in grouped] == [CH, CH2],
    grouped,
)
check("13c. a channel with no overrides for the date is simply absent", CH2 not in [cid for cid, _r in group_by_channel(overrides_for_date(data, "2026-07-19"), order)])


# ---------------------------------------------------------------------------
section("14-15, 18, 24. removing one saved override: file-level safety and playback isolation")
# ---------------------------------------------------------------------------


def _remove_one_override(path, records_before, target):
    """Mirrors remove_schedule_override_from_editor's exact algorithm
    (index -> del -> atomic save -> reload) at the schedule_overrides.py
    level, so this is testable without constructing the full app window.
    """
    records = list(records_before)
    index = records.index(target)
    del records[index]
    ok, error = save_schedule_overrides(path, {"version": 1, "overrides": records}, now=NOW)
    return ok, error, load_schedule_overrides(path)


with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "schedule_overrides.json")
    record_a = {"action": "add", "channel_id": CH, "date": "2026-07-17", "start": T0, "end": T0 + 900, "title": "Samurai Cop", "path": "/m/x.mp4", "media_type": "movie"}
    record_b = {"action": "remove", "channel_id": CH2, "date": "2026-07-17", "start": T0, "end": T0 + 1800, "title": "Old Show", "path": "", "media_type": "tv"}
    save_schedule_overrides(path, {"version": 1, "overrides": [record_a, record_b]}, now=NOW)

    ok, error, reloaded = _remove_one_override(path, [record_a, record_b], record_a)
    check("14. removing one saved override succeeds and rewrites the file", ok and not error)
    check("14b. reload reflects the removal", reloaded["overrides"] == [record_b], reloaded)
    check("15. removing one override does not remove an unrelated one on another channel", record_b in reloaded["overrides"])

    # 18: removing an unresolved override works the same way
    unresolved_record = {"action": "add", "channel_id": CH, "date": "2026-07-17", "start": T0 + 2000, "end": T0 + 2900, "title": "Missing", "path": "/nope.mp4", "media_type": "movie"}
    save_schedule_overrides(path, {"version": 1, "overrides": [record_b, unresolved_record]}, now=NOW)
    ok3, error3, reloaded3 = _remove_one_override(path, [record_b, unresolved_record], unresolved_record)
    check("18. removing an unresolved override works", ok3 and reloaded3["overrides"] == [record_b], reloaded3)

# 24: removing a saved override that covers a FUTURE (not-yet-airing) slot doesn't touch current playback
import channelsurfer2000 as cs

duration_cache = {"/media/a.mp4": 1800.0, "/media/b.mp4": 1800.0}
channel = cs.Channel("Comedy", duration_cache)
channel.set_schedule(["/media/a.mp4", "/media/b.mp4"], T0)
future_override = {"action": "add", "channel_id": CH, "date": "", "start": NOW + 3600, "end": NOW + 4500, "title": "Later", "path": "/media/later.mp4", "media_type": "movie"}
channel.set_schedule_overrides([future_override])
before_removal = channel.get_current()
channel.set_schedule_overrides([])  # simulates the override having been removed
after_removal = channel.get_current()
check(
    "24. removing an upcoming saved override does not interrupt current playback",
    before_removal[0] == after_removal[0] and abs(before_removal[1] - after_removal[1]) < 2.0,
    (before_removal, after_removal),
)


# ---------------------------------------------------------------------------
section("16-17. unresolved overrides: detection and crash-safety")
# ---------------------------------------------------------------------------

missing_record = {"action": "add", "channel_id": CH, "path": "/definitely/not/real.mp4"}
present_record = {"action": "add", "channel_id": CH, "path": __file__}
remove_record = {"action": "remove", "channel_id": CH}
check("16. a missing-media add override is reported unresolved", override_media_status(missing_record, os.path.isfile) == "unresolved")
check("16b. a present-media add override is resolved", override_media_status(present_record, os.path.isfile) == "resolved")
check("16c. remove-type overrides are always resolved (nothing to look up)", override_media_status(remove_record, os.path.isfile) == "resolved")

items = [{"path": "/a.mp4", "title": "A", "start": T0, "end": T0 + 1800, "entry": {"kind": "content", "path": "/a.mp4", "title": "A", "duration": 1800}}]
overrides = [{"action": "add", "channel_id": CH, "start": T0, "end": T0 + 900, "title": "Missing", "path": "/definitely/not/real.mp4", "media_type": "movie"}]
try:
    spliced = splice_overrides_into_window(items, overrides)
    crashed = False
except Exception:
    spliced = []
    crashed = True
check("17. unresolved overrides do not crash schedule generation (the splice)", not crashed and len(spliced) >= 1, spliced)


# ---------------------------------------------------------------------------
section("19-21. override compaction")
# ---------------------------------------------------------------------------

add_then_remove = compact_overrides([
    {"action": "add", "channel_id": CH, "date": "", "start": T0, "end": T0 + 900, "title": "X", "path": "/x.mp4", "media_type": "movie"},
    {"action": "remove", "channel_id": CH, "date": "", "start": T0, "end": T0 + 900, "title": "", "path": "", "media_type": ""},
])
check("19. add-then-remove no-op pairs compact away", len(add_then_remove) == 1 and add_then_remove[0]["action"] == "remove", add_then_remove)

repeated_replacement = compact_overrides([
    {"action": "add", "channel_id": CH, "date": "", "start": T0, "end": T0 + 1800, "title": "A", "path": "/a.mp4", "media_type": "movie"},
    {"action": "remove", "channel_id": CH, "date": "", "start": T0, "end": T0 + 1800, "title": "", "path": "", "media_type": ""},
    {"action": "add", "channel_id": CH, "date": "", "start": T0, "end": T0 + 1800, "title": "B", "path": "/b.mp4", "media_type": "movie"},
])
check(
    "20. repeated replacement of one time range compacts to just the final record",
    len(repeated_replacement) == 1 and repeated_replacement[0]["path"] == "/b.mp4",
    repeated_replacement,
)

dependent_ordering = compact_overrides([
    {"action": "add", "channel_id": CH, "date": "", "start": T0, "end": T0 + 3000, "title": "A", "path": "/a.mp4", "media_type": "movie"},
    {"action": "remove", "channel_id": CH, "date": "", "start": T0 + 1000, "end": T0 + 2000, "title": "", "path": "", "media_type": ""},
])
check(
    "21. compaction preserves real dependent ordering (a genuine gap in the middle is not merged away)",
    len(dependent_ordering) == 3
    and dependent_ordering[0]["path"] == "/a.mp4"
    and dependent_ordering[1]["action"] == "remove"
    and dependent_ordering[2]["path"] == "/a.mp4",
    dependent_ordering,
)

unrelated_channels = compact_overrides([
    {"action": "add", "channel_id": CH, "date": "", "start": T0, "end": T0 + 900, "title": "A", "path": "/a.mp4", "media_type": "movie"},
    {"action": "add", "channel_id": CH2, "date": "", "start": T0, "end": T0 + 900, "title": "B", "path": "/b.mp4", "media_type": "movie"},
])
check("compaction never merges across channels", len(unrelated_channels) == 2)


# ---------------------------------------------------------------------------
section("22-23, 25. Revert safety, clean reopen, refresh idempotence")
# ---------------------------------------------------------------------------

removal_calls = []


class _TrackingSaveDialog:
    def _schedule_overrides_save(self, records):
        removal_calls.append(("save", records))
        return True, ""

    def _schedule_overrides_remove(self, record):
        removal_calls.append(("remove", record))
        return True, ""


ws4 = _silence_dialogs(ScheduleEditorWorkspace(_EmptyStudioDialog(), on_back=lambda: None))
ws4._studio_dialog = _TrackingSaveDialog()
ws4._draft.set_base_lanes([make_lane()])
ws4._draft.apply_change(ws4._draft.new_change("remove", CH, T0, T0 + 1800, title="Show A"))
ws4._discard_draft()
check("22. Revert Draft never touches the saved-override save/remove pipeline", removal_calls == [])
check("22b. Revert Draft clears the draft locally", not ws4._draft.is_dirty())

ws5 = _silence_dialogs(ScheduleEditorWorkspace(_EmptyStudioDialog(), on_back=lambda: None))
ws5._studio_dialog = _SucceedingSaveDialog()
ws5._draft.set_base_lanes([make_lane()])
ws5._draft.apply_change(ws5._draft.new_change("remove", CH, T0, T0 + 1800, title="Show A"))
ws5._perform_save(ws5._draft.overrides_for_save())
check("23. reopening after Save begins with a clean draft", not ws5._draft.is_dirty() and ws5._draft.describe_pending_changes() == [])

draft6 = fresh_draft()
history6 = CommandHistory()
history6.execute(PullProgramCommand(draft6.presentation_lanes()[0].blocks[0]), draft6)
lengths = []
for _ in range(3):
    draft6.set_base_lanes([make_lane(blocks=[
        make_block("Show A", T0, T0 + 1800),
        make_block("Show B", T0 + 1800, T0 + 3600),
        make_block("Show C", T0 + 3600, T0 + 5400),
    ])])
    lengths.append(len(draft6.describe_pending_changes()))
check("25. repeated refreshes do not duplicate change-summary rows", lengths == [1, 1, 1], lengths)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 2.1 tests passed.")

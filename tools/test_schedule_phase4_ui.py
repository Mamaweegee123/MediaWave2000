"""
Phase 4 Schedule Editor tests: the Auto-Fill Block… button's
enablement/locking in the Editing Tools card, and dialog.py's
_auto_fill_block_clicked / _try_auto_fill_block wiring -- apply/undo/
redo, validation drift, recent-media recording, cancel, and empty
states, exercised against a real (offscreen) ScheduleEditorWorkspace.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase4_ui.py
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


from PySide6.QtWidgets import QApplication, QDialog

app = QApplication.instance() or QApplication(sys.argv)

import mediawave.schedule_editor.dialog as dialog_module
from mediawave.schedule_editor.dialog import ScheduleEditorWorkspace
from mediawave.schedule_editor.draft_model import DraftSchedule
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock

NOW = time.time()
T0 = NOW - (NOW % 1800) + 3600  # comfortably in the future
CH = "ch1"


def make_lane(channel_id=CH, blocks=None, name="Comedy", number=4, channel_type="media", has_data=True):
    return ChannelLane(channel_id=channel_id, name=name, number=number, channel_type=channel_type, logo_path="", blocks=blocks or [], has_data=has_data)


def make_block(title, start, end, channel_id=CH, media_type="tv"):
    return ProgramBlock(
        channel_id=channel_id, title=title, media_type=media_type, start=start, end=end,
        duration=end - start, is_commercial=False, source="generated",
        true_start=start, true_end=end,
        raw_entries=[{"kind": "content", "path": f"/media/{title}.mp4", "title": title, "duration": end - start}],
    )


def entry(title, start, end, path=None):
    return {
        "path": path or f"/media/{title}.mp4", "title": title, "episode_label": "", "media_type": "tv",
        "duration": end - start, "channel_name": "Comedy", "start": start, "end": end,
    }


class _NoShowsChannel:
    """A live media channel with no catalog media at all -- exercises the
    "Nothing to schedule yet" empty state (build_picker_catalog(...) is
    empty), separately from AutoFillBlockDialog's own internal empty
    states (already covered in test_schedule_phase4_dialog.py).
    """
    channel_type = "media"
    shows = []
    duration_cache = {}


class _FakeStudioDialog:
    def __init__(self):
        self.catalog_channel_infos = [{"id": CH, "name": "Comedy", "channel_type": "media", "default_number": 4}]
        self.catalog_channel_settings = {}
        self._studio_channels_by_id = {CH: _NoShowsChannel()}
        self.recent_records = []
        self.info_calls = []
        self.warning_calls = []

    def _schedule_recent_media_record(self, item):
        self.recent_records.append(item)


def make_workspace():
    studio = _FakeStudioDialog()
    ws = ScheduleEditorWorkspace(studio)
    ws._show_info = lambda title, text: studio.info_calls.append((title, text))
    ws._show_warning = lambda title, text: studio.warning_calls.append((title, text))
    return ws, studio


def select_open_block(ws, open_start, open_end):
    ws._draft.set_base_lanes([make_lane(blocks=[
        make_block("Show Before", open_start - 1800, open_start),
        make_block("Open Time", open_start, open_end, media_type="open"),
        make_block("Show After", open_end, open_end + 1800),
    ])])
    ws._render_draft()
    lane = next(l for l in ws._draft.presentation_lanes() if l.channel_id == CH)
    open_block = next(b for b in lane.blocks if b.media_type == "open")
    ws._on_program_selected(open_block)
    return open_block


# ---------------------------------------------------------------------------
section("1-2. Auto-Fill Block… button enablement")
# ---------------------------------------------------------------------------

ws, studio = make_workspace()
if ws.board is not None:
    open_start, open_end = T0, T0 + 5400
    open_block = select_open_block(ws, open_start, open_end)
    check("1. Auto-Fill Block… is enabled for a selected Open Time block", ws._tools["auto_fill_btn"].isEnabled())

    lane = next(l for l in ws._draft.presentation_lanes() if l.channel_id == CH)
    real_block = next(b for b in lane.blocks if b.media_type != "open")
    ws._on_program_selected(real_block)
    check("2. Auto-Fill Block… is disabled for a scheduled program", not ws._tools["auto_fill_btn"].isEnabled())
else:
    check("1-2. button enablement (skipped — no live board in this environment)", True)


# ---------------------------------------------------------------------------
section("3. Protected lane uses the existing locked state")
# ---------------------------------------------------------------------------

locked_ws, _ = make_workspace()
if locked_ws.board is not None:
    locked_ws._draft.set_base_lanes([make_lane(channel_type="weatherstar", blocks=[
        make_block("Weather", T0, T0 + 1800),
    ])])
    locked_ws._render_draft()
    lane = next(l for l in locked_ws._draft.presentation_lanes() if l.channel_id == CH)
    locked_ws._on_program_selected(lane.blocks[0])
    # set_locked hides the WHOLE buttons_container (Put On Air through
    # Auto-Fill Block…) rather than disabling each button individually --
    # .isHidden() reflects the explicit hide() call regardless of the
    # dialog's own top-level shown state (unlike isVisible(), which would
    # read False for everything here since this test never calls show()).
    auto_fill_btn = locked_ws._tools["auto_fill_btn"]
    check(
        "3. a protected lane hides the Auto-Fill Block… button along with the rest of the tools grid",
        auto_fill_btn.parentWidget() is not None and auto_fill_btn.parentWidget().isHidden(),
    )
else:
    check("3. protected lane (skipped — no live board in this environment)", True)


# ---------------------------------------------------------------------------
section("4-6. Apply creates exactly one history entry; undo/redo restore the whole lineup")
# ---------------------------------------------------------------------------

apply_ws, apply_studio = make_workspace()
open_start, open_end = T0, T0 + 3600
open_block = select_open_block(apply_ws, open_start, open_end)
lineup = [entry("Ep A", open_start, open_start + 1800), entry("Ep B", open_start + 1800, open_end)]

before_undo_depth = len(apply_ws._history._undo_stack)
apply_ws._try_auto_fill_block(open_block, lineup)
check("4. apply() adds exactly ONE entry to command history for the whole lineup", len(apply_ws._history._undo_stack) == before_undo_depth + 1, len(apply_ws._history._undo_stack))

lane = next(l for l in apply_ws._draft.presentation_lanes() if l.channel_id == CH)
titles = [b.title for b in lane.blocks]
check("4b. every lineup item was placed", titles == ["Show Before", "Ep A", "Ep B", "Show After"], titles)

apply_ws._undo_clicked()
lane = next(l for l in apply_ws._draft.presentation_lanes() if l.channel_id == CH)
check("5. undo removes the WHOLE lineup, restoring the single Open Time block", [b.title for b in lane.blocks] == ["Show Before", "Open Time", "Show After"], [b.title for b in lane.blocks])

apply_ws._redo_clicked()
lane = next(l for l in apply_ws._draft.presentation_lanes() if l.channel_id == CH)
check("6. redo restores the entire lineup again", [b.title for b in lane.blocks] == ["Show Before", "Ep A", "Ep B", "Show After"], [b.title for b in lane.blocks])


# ---------------------------------------------------------------------------
section("7. Recent-media recording happens only after successful execution")
# ---------------------------------------------------------------------------

recent_ws, recent_studio = make_workspace()
open_start, open_end = T0, T0 + 3600
open_block = select_open_block(recent_ws, open_start, open_end)

# First: a lineup that will fail validation (drifted draft) -- inject a
# real block into the middle of the open span AFTER "preview" was
# conceptually generated, simulating the draft changing underneath it.
recent_ws._draft.set_base_lanes([make_lane(blocks=[
    make_block("Show Before", open_start - 1800, open_start),
    make_block("Surprise", open_start + 500, open_start + 1000),
    make_block("Show After", open_end, open_end + 1800),
])])
drifted_lineup = [entry("Ep A", open_start, open_start + 1800), entry("Ep B", open_start + 1800, open_end)]
recent_ws._try_auto_fill_block(open_block, drifted_lineup)
check("8. a validation-drift failure records ZERO recent-media entries", recent_studio.recent_records == [])
check("8b. a validation-drift failure produces a clear warning message", len(recent_studio.warning_calls) == 1, recent_studio.warning_calls)

lane = next(l for l in recent_ws._draft.presentation_lanes() if l.channel_id == CH)
check(
    "9. validation drift causes ZERO draft changes (nothing partially applied)",
    [b.title for b in lane.blocks] == ["Show Before", "Surprise", "Show After"],
    [b.title for b in lane.blocks],
)

# Now a clean lineup against the ACTUAL current draft state (past the
# Surprise block) succeeds and records recent media for every item.
clean_lineup = [entry("Ep C", open_start + 1000, open_end)]
recent_ws._try_auto_fill_block(open_block, clean_lineup)
check("10. after a successful apply, recent media is recorded for every placed item", [r["path"] for r in recent_studio.recent_records] == ["/media/Ep C.mp4"], recent_studio.recent_records)


# ---------------------------------------------------------------------------
section("11. Cancel makes no changes")
# ---------------------------------------------------------------------------


class _CancelledDialog:
    Accepted = QDialog.Accepted
    Rejected = QDialog.Rejected

    def __init__(self, *args, **kwargs):
        pass

    def exec(self):
        return QDialog.Rejected


cancel_ws, cancel_studio = make_workspace()
open_start, open_end = T0, T0 + 3600
open_block = select_open_block(cancel_ws, open_start, open_end)
# Give the fake channel real catalog media so the dialog would actually
# open (otherwise "no media" short-circuits before the dialog at all).
cancel_ws._studio_channels_by_id[CH].shows = ["/media/Cancel Test.mp4"]
cancel_ws._studio_channels_by_id[CH].duration_cache = {"/media/Cancel Test.mp4": 1800}

before_changes = len(cancel_ws._draft.changes)
before_undo_depth = len(cancel_ws._history._undo_stack)
original_dialog_cls = dialog_module.AutoFillBlockDialog
dialog_module.AutoFillBlockDialog = _CancelledDialog
try:
    cancel_ws._auto_fill_block_clicked()
finally:
    dialog_module.AutoFillBlockDialog = original_dialog_cls
check("11. cancelling the dialog leaves the draft completely untouched", len(cancel_ws._draft.changes) == before_changes)
check("11b. cancelling adds nothing to command history", len(cancel_ws._history._undo_stack) == before_undo_depth)
check("11c. cancelling records no recent media", cancel_studio.recent_records == [])


# ---------------------------------------------------------------------------
section("12. No-media state is handled cleanly")
# ---------------------------------------------------------------------------

no_media_ws, no_media_studio = make_workspace()
open_start, open_end = T0, T0 + 3600
select_open_block(no_media_ws, open_start, open_end)
no_media_ws._auto_fill_block_clicked()  # the fixture channel has no shows/duration_cache at all
check("12. an empty catalog shows an informational message instead of opening a dialog or crashing", len(no_media_studio.info_calls) == 1, no_media_studio.info_calls)
check("12b. no draft changes result from the no-media state", not no_media_ws._draft.is_dirty())


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 4 UI tests passed.")

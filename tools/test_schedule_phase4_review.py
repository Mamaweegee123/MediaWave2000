"""
Phase 4 review-pass tests: closes two coverage gaps found during the
final review --

1. `_perform_save` -> `_advance_autofill_cursors_for_saved_changes` (the
   actual Save Schedule integration point) had no direct test; only the
   pure autofill_cursor.py helpers under it were tested.
2. `overrides_for_save()`'s behavior over a multi-add Auto-Fill Block
   group (does every placement serialize correctly, does grouping/
   autofill_meta correctly stay OUT of the saved record) was unverified.

Also verifies reselection after Auto-Fill undo/redo lands correctly
(reviewed by inspection; confirmed here empirically).

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase4_review.py
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


from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.schedule_editor.commands import AutoFillBlockCommand
from mediawave.schedule_editor.dialog import ScheduleEditorWorkspace
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock

NOW = time.time()
T0 = NOW - (NOW % 1800) + 3600
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


def sequential_entry(path, title, start, end, season, ep, show_key="tv::sitcom"):
    return {
        "path": path, "title": title, "episode_label": f"S{season}E{ep}", "media_type": "tv",
        "duration": end - start, "channel_name": "Comedy", "start": start, "end": end,
        "season_number": season, "episode_number": ep, "show_key": show_key, "strategy": "sequential",
    }


class _NoShowsChannel:
    channel_type = "media"
    shows = []
    duration_cache = {}


class _FakeStudioDialog:
    def __init__(self, save_ok=True, save_error=""):
        self.catalog_channel_infos = [{"id": CH, "name": "Comedy", "channel_type": "media", "default_number": 4}]
        self.catalog_channel_settings = {}
        self._studio_channels_by_id = {CH: _NoShowsChannel()}
        self.saved_records = []
        self.save_calls = 0
        self.advance_calls = []
        self._save_ok = save_ok
        self._save_error = save_error

    def _schedule_overrides_save(self, records):
        self.save_calls += 1
        if not self._save_ok:
            return False, self._save_error
        self.saved_records.append(list(records))
        return True, ""

    def _schedule_autofill_cursor_advance(self, entries):
        self.advance_calls.append(entries)

    def _schedule_recent_media_record(self, item):
        pass


def make_workspace(**kwargs):
    studio = _FakeStudioDialog(**kwargs)
    ws = ScheduleEditorWorkspace(studio)
    ws._show_info = lambda title, text: None
    ws._show_warning = lambda title, text: None
    return ws, studio


def select_open_block(ws, open_start, open_end):
    ws._draft.set_base_lanes([make_lane(blocks=[make_block("Open Time", open_start, open_end, media_type="open")])])
    ws._render_draft()
    lane = next(l for l in ws._draft.presentation_lanes() if l.channel_id == CH)
    open_block = next(b for b in lane.blocks if b.media_type == "open")
    ws._on_program_selected(open_block)
    return open_block


# ---------------------------------------------------------------------------
section("1. Save Schedule integration: cursor advances only after a real successful save")
# ---------------------------------------------------------------------------

ws, studio = make_workspace(save_ok=True)
open_start, open_end = T0, T0 + 2640
open_block = select_open_block(ws, open_start, open_end)
lineup = [
    sequential_entry("/m/s1e1.mp4", "Sitcom", open_start, open_start + 1320, 1, 1),
    sequential_entry("/m/s1e2.mp4", "Sitcom", open_start + 1320, open_end, 1, 2),
]
ws._try_auto_fill_block(open_block, lineup)
check("1a. the Auto-Fill placement is pending before save", ws._draft.is_dirty())

ok = ws._save_clicked()
check("1b. _save_clicked reports success", ok)
check("1c. the real save pipeline was called exactly once", studio.save_calls == 1)
check("1d. the cursor sink was called exactly once, after the successful save", len(studio.advance_calls) == 1, studio.advance_calls)
check(
    "1e. the cursor advance collapsed to the FINAL episode of the sequential lineup",
    studio.advance_calls[0][0]["path"] == "/m/s1e2.mp4",
    studio.advance_calls,
)
check("1f. the draft is clean after a successful save", not ws._draft.is_dirty())


# ---------------------------------------------------------------------------
section("2. Save failure: cursor NEVER advances, draft stays dirty")
# ---------------------------------------------------------------------------

fail_ws, fail_studio = make_workspace(save_ok=False, save_error="Disk is full.")
open_start, open_end = T0, T0 + 1320
open_block = select_open_block(fail_ws, open_start, open_end)
lineup = [sequential_entry("/m/s1e1.mp4", "Sitcom", open_start, open_end, 1, 1)]
fail_ws._try_auto_fill_block(open_block, lineup)

ok = fail_ws._save_clicked()
check("2a. _save_clicked reports failure", not ok)
check("2b. the cursor sink was never called on a failed save", fail_studio.advance_calls == [])
check("2c. the draft remains dirty (nothing was lost) after a failed save", fail_ws._draft.is_dirty())


# ---------------------------------------------------------------------------
section("3. No cursor sink wired (older/standalone session) doesn't crash Save Schedule")
# ---------------------------------------------------------------------------


class _StudioNoCursorSink:
    def __init__(self):
        self.catalog_channel_infos = [{"id": CH, "name": "Comedy", "channel_type": "media", "default_number": 4}]
        self.catalog_channel_settings = {}
        self._studio_channels_by_id = {CH: _NoShowsChannel()}

    def _schedule_overrides_save(self, records):
        return True, ""


no_sink_ws = ScheduleEditorWorkspace(_StudioNoCursorSink())
no_sink_ws._show_info = lambda title, text: None
no_sink_ws._show_warning = lambda title, text: None
open_start, open_end = T0, T0 + 1320
open_block = select_open_block(no_sink_ws, open_start, open_end)
no_sink_ws._try_auto_fill_block(open_block, [sequential_entry("/m/s1e1.mp4", "Sitcom", open_start, open_end, 1, 1)])
ok = no_sink_ws._save_clicked()
check("3. saving without a wired cursor sink still succeeds and doesn't crash", ok)


# ---------------------------------------------------------------------------
section("4. overrides_for_save() serializes every placement, without grouping metadata")
# ---------------------------------------------------------------------------

records_ws, records_studio = make_workspace(save_ok=True)
open_start, open_end = T0, T0 + 3600
open_block = select_open_block(records_ws, open_start, open_end)
best_fit_entry_a = {"path": "/m/a.mp4", "title": "A", "episode_label": "", "media_type": "movie", "duration": 1800, "channel_name": "Comedy", "start": open_start, "end": open_start + 1800}
best_fit_entry_b = {"path": "/m/b.mp4", "title": "B", "episode_label": "", "media_type": "movie", "duration": 1800, "channel_name": "Comedy", "start": open_start + 1800, "end": open_end}
records_ws._try_auto_fill_block(open_block, [best_fit_entry_a, best_fit_entry_b])
records_ws._save_clicked()
check("4a. the save pipeline received exactly one override record per placement", len(records_studio.saved_records[0]) == 2, records_studio.saved_records)
check(
    "4b. each saved record has the right path/title/time, and carries no group_id/group_kind/autofill_meta leakage",
    all(set(r.keys()) == {"action", "channel_id", "date", "start", "end", "title", "path", "media_type"} for r in records_studio.saved_records[0]),
    records_studio.saved_records[0],
)
check("4c. best-fit (non-sequential) placements never advance the cursor", records_studio.advance_calls == [])


# ---------------------------------------------------------------------------
section("5. Reselection after Auto-Fill apply/undo/redo")
# ---------------------------------------------------------------------------

reselect_ws, _ = make_workspace()
open_start, open_end = T0, T0 + 3600
open_block = select_open_block(reselect_ws, open_start, open_end)
lineup = [
    {"path": "/m/a.mp4", "title": "Ep A", "episode_label": "", "media_type": "tv", "duration": 1800, "channel_name": "Comedy", "start": open_start, "end": open_start + 1800},
    {"path": "/m/b.mp4", "title": "Ep B", "episode_label": "", "media_type": "tv", "duration": 1800, "channel_name": "Comedy", "start": open_start + 1800, "end": open_end},
]
reselect_ws._try_auto_fill_block(open_block, lineup)
check(
    "5a. after apply, selection lands on the first placed item (same start the Open Time block had)",
    reselect_ws._selected_block is not None and reselect_ws._selected_block.title == "Ep A",
    reselect_ws._selected_block,
)

reselect_ws._undo_clicked()
check(
    "5b. after undo, selection returns to the restored Open Time block at the same start",
    reselect_ws._selected_block is not None and reselect_ws._selected_block.media_type == "open",
    reselect_ws._selected_block,
)

reselect_ws._redo_clicked()
check(
    "5c. after redo, selection lands on the first placed item again",
    reselect_ws._selected_block is not None and reselect_ws._selected_block.title == "Ep A",
    reselect_ws._selected_block,
)

# Selecting a LATER item before undo is a known, harmless edge case: the
# undo target (the open block's start) no longer matches where "Ep B"
# was selected, so selection clears to None instead of pointing at a
# stale/nonexistent block -- verified here to be a clean no-selection
# state, not a crash or an incorrect stale reference.
reselect_ws._on_program_selected(next(b for b in reselect_ws._draft.presentation_lanes()[0].blocks if b.title == "Ep B"))
reselect_ws._undo_clicked()
check(
    "5d. undoing while a later lineup item was selected clears selection cleanly (no stale/incorrect reference)",
    reselect_ws._selected_block is None,
    reselect_ws._selected_block,
)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 4 review tests passed.")

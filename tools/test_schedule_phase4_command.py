"""
Phase 4 Schedule Editor tests: AutoFillBlockCommand -- validation,
execute/undo/redo, overlap rejection, protected lanes, and atomic
all-or-nothing application.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase4_command.py
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
    CONFLICT_OVERLAPS_EXISTING,
    CONFLICT_PROTECTED_BLOCK,
    AutoFillBlockCommand,
    CommandHistory,
)
from mediawave.schedule_editor.draft_model import DraftSchedule
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock

NOW = time.time()
T0 = NOW - (NOW % 1800) + 3600  # comfortably in the future, avoids "already aired" checks
CH = "media:/catalog/Comedy"


def make_lane(channel_id=CH, blocks=None, name="Comedy", number=4, channel_type="media", has_data=True):
    return ChannelLane(channel_id=channel_id, name=name, number=number, channel_type=channel_type, logo_path="", blocks=blocks or [], has_data=has_data)


def make_block(title, start, end, channel_id=CH, media_type="tv", source="generated", raw_entries=None):
    return ProgramBlock(
        channel_id=channel_id,
        title=title,
        media_type=media_type,
        start=start,
        end=end,
        duration=end - start,
        is_commercial=False,
        source=source,
        true_start=start,
        true_end=end,
        raw_entries=raw_entries if raw_entries is not None else [{"kind": "content", "path": f"/media/{title}.mp4", "title": title, "duration": end - start}],
    )


def fresh_draft_with_open_block(open_start, open_end):
    draft = DraftSchedule()
    draft.set_base_lanes([make_lane(blocks=[
        make_block("Show Before", open_start - 1800, open_start),
        make_block("Open Time", open_start, open_end, media_type="open"),
        make_block("Show After", open_end, open_end + 1800),
    ])])
    return draft


def blocks_of(draft, channel_id=CH):
    lane = next(l for l in draft.presentation_lanes() if l.channel_id == channel_id)
    return lane.blocks


def entry(title, start, end, path=None):
    return {
        "path": path or f"/media/{title}.mp4",
        "title": title,
        "episode_label": "",
        "media_type": "tv",
        "duration": end - start,
        "channel_name": "Comedy",
        "start": start,
        "end": end,
    }


# ---------------------------------------------------------------------------
section("1-4. Validation, execute, undo, redo")
# ---------------------------------------------------------------------------

open_start, open_end = T0, T0 + 5400
draft = fresh_draft_with_open_block(open_start, open_end)
history = CommandHistory()

lineup = [
    entry("Ep A", open_start, open_start + 1800),
    entry("Ep B", open_start + 1800, open_start + 3600),
    entry("Ep C", open_start + 3600, open_start + 5400),
]
cmd = AutoFillBlockCommand(CH, open_start, open_end, lineup)

v = cmd.validate(draft, now=NOW)
check("1. a fully-fitting lineup validates cleanly", v.ok, v.reason)

history.execute(cmd, draft)
titles = [b.title for b in blocks_of(draft)]
check(
    "2. execute() places every lineup item, replacing the Open Time block",
    titles == ["Show Before", "Ep A", "Ep B", "Ep C", "Show After"],
    titles,
)

rows = draft.describe_pending_changes()
check("3. the whole lineup collapses into ONE Pending Changes row", len(rows) == 1, rows)
check("3b. the row's headline names the program count", "3 program" in rows[0]["headline"], rows[0])

history.undo(draft)
titles_after_undo = [b.title for b in blocks_of(draft)]
check(
    "4. undo restores the single Open Time block exactly",
    titles_after_undo == ["Show Before", "Open Time", "Show After"],
    titles_after_undo,
)

history.redo(draft)
titles_after_redo = [b.title for b in blocks_of(draft)]
check("5. redo re-applies the entire lineup", titles_after_redo == ["Show Before", "Ep A", "Ep B", "Ep C", "Show After"], titles_after_redo)


# ---------------------------------------------------------------------------
section("6-7. Overlap rejection")
# ---------------------------------------------------------------------------

draft2 = fresh_draft_with_open_block(open_start, open_end)
# A lineup item that runs past the Open Time block into "Show After".
overrunning_lineup = [
    entry("Ep A", open_start, open_start + 1800),
    entry("Ep B", open_start + 1800, open_end + 900),  # overruns into Show After
]
cmd2 = AutoFillBlockCommand(CH, open_start, open_end, overrunning_lineup)
v2 = cmd2.validate(draft2, now=NOW)
check("6. a lineup item extending past the block's own end is rejected", not v2.ok, v2.reason)

draft3 = fresh_draft_with_open_block(open_start, open_end)
# Insert an ad-hoc real block INSIDE the open span (simulating draft drift
# between preview and Apply Lineup) that a lineup item would overlap.
draft3.set_base_lanes([make_lane(blocks=[
    make_block("Show Before", open_start - 1800, open_start),
    make_block("Surprise Special", open_start + 1000, open_start + 2000),
    make_block("Show After", open_end, open_end + 1800),
])])
drifted_lineup = [entry("Ep A", open_start, open_start + 1800)]
cmd3 = AutoFillBlockCommand(CH, open_start, open_end, drifted_lineup)
v3 = cmd3.validate(draft3, now=NOW)
check(
    "7. a lineup item overlapping a block that appeared after preview is rejected",
    not v3.ok and v3.conflicts and v3.conflicts[0]["type"] == CONFLICT_OVERLAPS_EXISTING,
    v3,
)


# ---------------------------------------------------------------------------
section("8. Protected lane")
# ---------------------------------------------------------------------------

locked_draft = DraftSchedule()
locked_draft.set_base_lanes([make_lane(channel_id="weatherstar:1", channel_type="weatherstar", blocks=[
    make_block("Weather", open_start, open_end, channel_id="weatherstar:1"),
])])
locked_cmd = AutoFillBlockCommand("weatherstar:1", open_start, open_end, [entry("Ep A", open_start, open_end)])
v4 = locked_cmd.validate(locked_draft, now=NOW)
check(
    "8. a protected/locked lane rejects Auto-Fill Block with a plain-language reason",
    not v4.ok and v4.conflicts and v4.conflicts[0]["type"] == CONFLICT_PROTECTED_BLOCK,
    v4,
)


# ---------------------------------------------------------------------------
section("9-10. Atomic all-or-nothing application")
# ---------------------------------------------------------------------------

draft4 = fresh_draft_with_open_block(open_start, open_end)
draft4.set_base_lanes([make_lane(blocks=[
    make_block("Show Before", open_start - 1800, open_start),
    make_block("Surprise Special", open_start + 1000, open_start + 2000),
    make_block("Show After", open_end, open_end + 1800),
])])
before_changes = len(draft4.changes)
# A realistic lineup: first item is perfectly fine, second collides with
# the "Surprise Special" block that appeared after preview -- apply()
# must not leave the first item's change behind.
partial_lineup = [
    entry("Ep A", open_start, open_start + 1000),
    entry("Ep B", open_start + 1000, open_start + 2500),  # collides with Surprise Special
]
cmd5 = AutoFillBlockCommand(CH, open_start, open_end, partial_lineup)
raised = False
try:
    cmd5.apply(draft4)
except ValueError:
    raised = True
check("9. apply() on a since-invalidated lineup raises instead of writing", raised)
check("10. no partial changes were left behind after the failed apply()", len(draft4.changes) == before_changes, draft4.changes)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 4 command tests passed.")

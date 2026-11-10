"""
Phase 4 Schedule Editor tests: the Auto-Fill Block "Continue
Sequentially" cursor (autofill_cursor.py) -- persistence across
restarts, channel/show-specific keying, save-success-only advancement,
atomic writes, and graceful handling of malformed/stale data.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase4_cursor.py
"""

import os
import shutil
import sys
import tempfile
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.schedule_editor.autofill_cursor import (
    advance_cursor,
    cursors_to_advance_from_saved_changes,
    empty_cursor_data,
    last_aired_path_for,
    load_autofill_cursors,
    normalize_cursor_data,
    save_autofill_cursors,
)
from mediawave.schedule_editor.autofill_planner import plan_continue_sequentially
from mediawave.schedule_editor.commands import AutoFillBlockCommand, CommandHistory
from mediawave.schedule_editor.draft_model import DraftSchedule
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock

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


TMP_DIR = tempfile.mkdtemp(prefix="mediawave_autofill_cursor_test_")


def cursor_path(name):
    return os.path.join(TMP_DIR, name)


# ---------------------------------------------------------------------------
section("1. Persistence across restarts")
# ---------------------------------------------------------------------------

path = cursor_path("restart.json")
data = empty_cursor_data()
data = advance_cursor(data, "ch1", "tv::sitcom", "/media/sitcom_s1e3.mp4", title="Sitcom", season_number=1, episode_number=3, now=1000)
ok, error = save_autofill_cursors(path, data)
check("1a. save reports success", ok, error)

reloaded = load_autofill_cursors(path)  # simulates a fresh process reading the same file
check(
    "1b. a freshly loaded cursor (simulated restart) resolves the same last-aired path",
    last_aired_path_for(reloaded, "ch1", "tv::sitcom") == "/media/sitcom_s1e3.mp4",
    reloaded,
)


# ---------------------------------------------------------------------------
section("2. Channel-specific cursors")
# ---------------------------------------------------------------------------

data = empty_cursor_data()
data = advance_cursor(data, "ch1", "tv::sitcom", "/media/sitcom_s1e1.mp4", now=1000)
data = advance_cursor(data, "ch2", "tv::sitcom", "/media/sitcom_s2e5.mp4", now=1000)
check(
    "2. the same show on two different channels tracks two independent cursors",
    last_aired_path_for(data, "ch1", "tv::sitcom") == "/media/sitcom_s1e1.mp4"
    and last_aired_path_for(data, "ch2", "tv::sitcom") == "/media/sitcom_s2e5.mp4",
    data,
)


# ---------------------------------------------------------------------------
section("3. Separate cursors for separate shows")
# ---------------------------------------------------------------------------

data = empty_cursor_data()
data = advance_cursor(data, "ch1", "tv::sitcom", "/media/sitcom_s1e1.mp4", now=1000)
data = advance_cursor(data, "ch1", "tv::cartoon", "/media/cartoon_s1e1.mp4", now=1000)
check(
    "3. two different shows on the same channel don't clobber each other",
    last_aired_path_for(data, "ch1", "tv::sitcom") == "/media/sitcom_s1e1.mp4"
    and last_aired_path_for(data, "ch1", "tv::cartoon") == "/media/cartoon_s1e1.mp4",
    data,
)


# ---------------------------------------------------------------------------
section("4-6. Cursor only advances after Save Schedule succeeds")
# ---------------------------------------------------------------------------

CH = "media:/catalog/Comedy"


def make_lane(channel_id=CH, blocks=None):
    return ChannelLane(channel_id=channel_id, name="Comedy", number=4, channel_type="media", logo_path="", blocks=blocks or [], has_data=True)


def make_block(title, start, end, channel_id=CH, media_type="tv"):
    return ProgramBlock(
        channel_id=channel_id, title=title, media_type=media_type, start=start, end=end,
        duration=end - start, is_commercial=False, source="generated",
        true_start=start, true_end=end,
        raw_entries=[{"kind": "content", "path": f"/media/{title}.mp4", "title": title, "duration": end - start}],
    )


def episode(path, title, start, end, season, ep, show_key="tv::sitcom"):
    return {
        "path": path, "title": title, "episode_label": "", "media_type": "tv",
        "duration": end - start, "channel_name": "Comedy", "start": start, "end": end,
        "season_number": season, "episode_number": ep, "show_key": show_key, "strategy": "sequential",
    }


T0 = time.time() + 3600  # comfortably in the future, avoids "already aired" checks
draft = DraftSchedule()
draft.set_base_lanes([make_lane(blocks=[make_block("Open Time", T0, T0 + 3600, media_type="open")])])
history = CommandHistory()

lineup = [episode("/media/s1e1.mp4", "Sitcom", T0, T0 + 1800, 1, 1), episode("/media/s1e2.mp4", "Sitcom", T0 + 1800, T0 + 3600, 1, 2)]
cmd = AutoFillBlockCommand(CH, T0, T0 + 3600, lineup)
history.execute(cmd, draft)


def autofill_entries_from_draft(draft):
    return [
        {
            "channel_id": c.channel_id, "show_key": c.autofill_meta["show_key"], "path": c.path,
            "title": c.title, "season_number": c.autofill_meta.get("season_number"),
            "episode_number": c.autofill_meta.get("episode_number"), "start": c.start,
        }
        for c in draft.changes
        if c.group_kind == "autofill" and c.autofill_meta and c.autofill_meta.get("strategy") == "sequential"
    ]


check("4a. AutoFillBlockCommand's DraftChanges carry sequential autofill_meta", len(autofill_entries_from_draft(draft)) == 2)

cursor_data = empty_cursor_data()
check("4. before any save, the cursor is untouched by mere execute()", last_aired_path_for(cursor_data, CH, "tv::sitcom") is None)

history.undo(draft)
check("5a. undo doesn't touch the cursor (nothing ever called advance_cursor)", last_aired_path_for(cursor_data, CH, "tv::sitcom") is None)
history.redo(draft)
check("5b. redo doesn't touch the cursor either", last_aired_path_for(cursor_data, CH, "tv::sitcom") is None)

draft.clear_changes()  # simulates discarding the draft
check(
    "5c. a discarded draft loses its pending autofill changes, so a save-time scan afterward finds nothing to advance",
    autofill_entries_from_draft(draft) == [],
)

# Now the real "Save Schedule succeeded" path: re-apply, then advance.
draft2 = DraftSchedule()
draft2.set_base_lanes([make_lane(blocks=[make_block("Open Time", T0, T0 + 3600, media_type="open")])])
history2 = CommandHistory()
history2.execute(AutoFillBlockCommand(CH, T0, T0 + 3600, lineup), draft2)
entries = autofill_entries_from_draft(draft2)
saved_path = cursor_path("save_success.json")
saved_data = empty_cursor_data()
for advance_entry in cursors_to_advance_from_saved_changes(entries):
    saved_data = advance_cursor(
        saved_data, advance_entry["channel_id"], advance_entry["show_key"], advance_entry["path"],
        title=advance_entry["title"], season_number=advance_entry["season_number"],
        episode_number=advance_entry["episode_number"], now=2000,
    )
ok, _ = save_autofill_cursors(saved_path, saved_data)
check("6. after a successful save, the cursor advances to the LAST episode of the saved lineup", ok and last_aired_path_for(saved_data, CH, "tv::sitcom") == "/media/s1e2.mp4", saved_data)


# ---------------------------------------------------------------------------
section("7. Multiple saved Auto-Fill groups for the same show/channel")
# ---------------------------------------------------------------------------

group_a = [episode("/media/s1e1.mp4", "Sitcom", T0, T0 + 1800, 1, 1)]
group_b = [episode("/media/s1e3.mp4", "Sitcom", T0 + 1800, T0 + 3600, 1, 3), episode("/media/s1e4.mp4", "Sitcom", T0 + 3600, T0 + 5400, 1, 4)]
draft3 = DraftSchedule()
draft3.set_base_lanes([make_lane(blocks=[make_block("Open Time", T0, T0 + 5400, media_type="open")])])
history3 = CommandHistory()
history3.execute(AutoFillBlockCommand(CH, T0, T0 + 1800, group_a), draft3)
history3.execute(AutoFillBlockCommand(CH, T0 + 1800, T0 + 5400, group_b), draft3)
all_entries = autofill_entries_from_draft(draft3)
check("7a. two separate Auto-Fill groups both stay pending together", len(all_entries) == 3)
to_advance = cursors_to_advance_from_saved_changes(all_entries)
check(
    "7b. saving both groups together collapses to ONE advance, to the chronologically FINAL episode",
    len(to_advance) == 1 and to_advance[0]["path"] == "/media/s1e4.mp4",
    to_advance,
)


# ---------------------------------------------------------------------------
section("8-9. Missing catalog episodes (stale cursor) fall back safely")
# ---------------------------------------------------------------------------

catalog_now = [
    {"path": "/media/s1e1.mp4", "title": "Sitcom", "season_number": 1, "episode_number": 1, "duration": 1800, "schedulable": True},
    {"path": "/media/s1e2.mp4", "title": "Sitcom", "season_number": 1, "episode_number": 2, "duration": 1800, "schedulable": True},
]
stale_cursor_data = advance_cursor(empty_cursor_data(), CH, "tv::sitcom", "/media/s1e_deleted.mp4", now=1000)
resume_from = last_aired_path_for(stale_cursor_data, CH, "tv::sitcom")
result = plan_continue_sequentially(catalog_now, gap_start=0, gap_duration=1800, last_aired_path=resume_from)
check(
    "8. a cursor pointing at a since-removed file resolves to a path the planner tries",
    resume_from == "/media/s1e_deleted.mp4",
)
check(
    "9. plan_continue_sequentially falls back to the first available episode instead of erroring",
    [e["path"] for e in result["lineup"]] == ["/media/s1e1.mp4"],
    result,
)


# ---------------------------------------------------------------------------
section("10. Malformed cursor data")
# ---------------------------------------------------------------------------

check("10a. a non-dict payload normalizes to empty, ok=False", normalize_cursor_data([1, 2, 3]) == (empty_cursor_data(), False))
check("10b. a future/unknown schema version is rejected, not guessed at", normalize_cursor_data({"version": 999, "cursors": {}})[1] is False)
check("10c. 'cursors' not being a dict is rejected", normalize_cursor_data({"version": 1, "cursors": "nope"})[1] is False)

mixed, ok = normalize_cursor_data({
    "version": 1,
    "cursors": {
        "good": {"channel_id": "ch1", "show_key": "tv::x", "path": "/media/x.mp4"},
        "bad_missing_path": {"channel_id": "ch1", "show_key": "tv::y"},
        "bad_not_a_dict": "garbage",
    },
})
check("10d. one malformed entry among valid ones doesn't invalidate the whole file", ok and len(mixed["cursors"]) == 1, mixed)

malformed_file = cursor_path("malformed.json")
with open(malformed_file, "w", encoding="utf-8") as handle:
    handle.write("{not valid json")
loaded = load_autofill_cursors(malformed_file)
check("10e. loading a corrupt JSON file yields an empty structure, not a crash", loaded == empty_cursor_data())

missing_file = cursor_path("does_not_exist.json")
check("10f. loading a missing file yields an empty structure", load_autofill_cursors(missing_file) == empty_cursor_data())


# ---------------------------------------------------------------------------
section("11. Save failure leaves cursor state unchanged")
# ---------------------------------------------------------------------------

good_path = cursor_path("save_failure.json")
good_data = advance_cursor(empty_cursor_data(), "ch1", "tv::sitcom", "/media/s1e1.mp4", now=1000)
save_autofill_cursors(good_path, good_data)
before_bad_save = load_autofill_cursors(good_path)

bad_ok, bad_error = save_autofill_cursors(good_path, {"version": 1, "cursors": "not-a-dict"})
check("11a. saving a structurally invalid payload reports failure", not bad_ok, bad_error)
after_bad_save = load_autofill_cursors(good_path)
check("11b. the on-disk file is untouched after a rejected save", after_bad_save == before_bad_save, (before_bad_save, after_bad_save))


# ---------------------------------------------------------------------------
section("12. Atomic writes")
# ---------------------------------------------------------------------------

atomic_path = cursor_path("atomic.json")
save_autofill_cursors(atomic_path, advance_cursor(empty_cursor_data(), "ch1", "tv::sitcom", "/media/s1e1.mp4", now=1000))
before_files = set(os.listdir(TMP_DIR))
save_autofill_cursors(atomic_path, advance_cursor(load_autofill_cursors(atomic_path), "ch1", "tv::sitcom", "/media/s1e2.mp4", now=2000))
after_files = set(os.listdir(TMP_DIR))
check(
    "12. no leftover .tmp file survives a successful save (tempfile was renamed, not left behind)",
    not any(name.startswith(".schedule_autofill_cursor_") for name in after_files),
    after_files - before_files,
)
check(
    "12b. the save used a rename, not an in-place truncate (final content is fully the new value)",
    last_aired_path_for(load_autofill_cursors(atomic_path), "ch1", "tv::sitcom") == "/media/s1e2.mp4",
)


# ---------------------------------------------------------------------------
shutil.rmtree(TMP_DIR, ignore_errors=True)

print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 4 cursor tests passed.")

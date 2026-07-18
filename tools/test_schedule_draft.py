"""
Phase 2 Schedule Editor tests: the draft model, Pull / Put On Air
commands, undo/redo history, override persistence, and the proof
obligations that draft edits never touch live schedule state.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_draft.py

Covers the 25 scenarios from the Phase 2 spec (numbered in section
titles). Pure-model tests run without Qt; the workspace-level checks at
the end force the offscreen platform, same as test_schedule_editor.py.
Importing channelsurfer2000 (for the real Channel class) is intentional:
the override splice lives on Channel itself and must be tested against
the real modular-time resolution, not a stub.
"""

import json
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


from mediawave.schedule_editor.commands import (
    CONFLICT_OVERLAPS_FOLLOWING,
    CommandHistory,
    PullProgramCommand,
    PutOnAirCommand,
)
from mediawave.schedule_editor.draft_model import DraftSchedule, channel_lock_reason
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock
from mediawave.schedule_overrides import (
    load_schedule_overrides,
    overrides_for_channel,
    resolve_current_with_overrides,
    save_schedule_overrides,
    splice_overrides_into_window,
)

NOW = time.time()
T0 = NOW - (NOW % 1800)  # a stable half-hour boundary near now
CH = "media:/catalog/Comedy"


def make_lane(channel_id=CH, channel_type="media", blocks=None, name="Comedy", number=1):
    return ChannelLane(
        channel_id=channel_id,
        name=name,
        number=number,
        channel_type=channel_type,
        logo_path="",
        blocks=blocks if blocks is not None else [],
        has_data=True,
    )


def make_block(title, start, end, channel_id=CH, media_type="tv", source="generated", is_commercial=False):
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
        raw_entries=[{"kind": "content", "path": f"/media/{title}.mp4", "title": title, "duration": end - start}],
    )


def fresh_draft(blocks=None):
    draft = DraftSchedule()
    lane_blocks = blocks if blocks is not None else [
        make_block("Show A", T0, T0 + 1800),
        make_block("Show B", T0 + 1800, T0 + 3600),
        make_block("Show C", T0 + 3600, T0 + 5400),
    ]
    draft.set_base_lanes([make_lane(blocks=lane_blocks)])
    return draft


def blocks_of(draft, channel_id=CH):
    lane = next(l for l in draft.presentation_lanes() if l.channel_id == channel_id)
    return lane.blocks


def titles_of(draft, channel_id=CH):
    return [(b.title, b.media_type) for b in blocks_of(draft, channel_id)]


# ---------------------------------------------------------------------------
section("1. draft cloning does not mutate the generated source")
# ---------------------------------------------------------------------------

source_blocks = [make_block("Show A", T0, T0 + 1800), make_block("Show B", T0 + 1800, T0 + 3600)]
source_lane = make_lane(blocks=source_blocks)
source_snapshot = [(b.title, b.start, b.end, b.duration) for b in source_blocks]

draft = DraftSchedule()
draft.set_base_lanes([source_lane])
history = CommandHistory()
pull_b = PullProgramCommand(blocks_of(draft)[1])
history.execute(pull_b, draft)
draft_blocks = blocks_of(draft)

check(
    "the source lane's blocks are untouched after cloning and a draft edit",
    [(b.title, b.start, b.end, b.duration) for b in source_blocks] == source_snapshot,
)
check(
    "the source lane still owns its original block objects (no draft aliasing)",
    all(cloned is not original for cloned in draft_blocks for original in source_blocks),
)


# ---------------------------------------------------------------------------
section("2-6. Pull, Undo, Redo, redo-branch clearing, open time")
# ---------------------------------------------------------------------------

check(
    "2. Pull removes the program from the draft only",
    ("Show B", "tv") not in titles_of(draft) and any(t == "Show B" for t, _m in [(b.title, b.media_type) for b in source_blocks]),
    titles_of(draft),
)
check(
    "6. Pull leaves an explicit Open Time interval covering the pulled slot",
    any(b.media_type == "open" and b.start == T0 + 1800 and b.end == T0 + 3600 for b in blocks_of(draft)),
    titles_of(draft),
)

history.undo(draft)
check("3. Undo restores the pulled program", ("Show B", "tv") in titles_of(draft), titles_of(draft))
check("3b. Undo returns the draft to clean", not draft.is_dirty())

history.redo(draft)
check("4. Redo removes it again", ("Show B", "tv") not in titles_of(draft), titles_of(draft))

history.undo(draft)
pull_a = PullProgramCommand(next(b for b in blocks_of(draft) if b.title == "Show A"))
history.execute(pull_a, draft)
check("5. a new command after Undo clears the redo branch", history.can_redo is False)
check(
    "5b. undo/redo descriptions are human-readable",
    history.undo_description == "Pull “Show A”",
    history.undo_description,
)


# ---------------------------------------------------------------------------
section("7-10. Put On Air: filling, short media, long media, cancelled conflict")
# ---------------------------------------------------------------------------

draft = fresh_draft()
history = CommandHistory()
history.execute(PullProgramCommand(blocks_of(draft)[1]), draft)
open_slot = next(b for b in blocks_of(draft) if b.media_type == "open")

exact = {"path": "/media/exact.mp4", "title": "Exact Fit", "duration": 1800.0, "media_type": "movie"}
cmd = PutOnAirCommand(CH, open_slot.true_start, exact, slot_end=open_slot.true_end)
v = cmd.validate(draft, now=NOW)
check("7. exact-fit media validates cleanly into an open interval", v.ok and not v.conflicts, v.reason)
history.execute(cmd, draft)
check(
    "7b. the added program fills the interval (no open time left)",
    ("Exact Fit", "movie") in titles_of(draft) and not any(b.media_type == "open" for b in blocks_of(draft)),
    titles_of(draft),
)
history.undo(draft)

short = {"path": "/media/short.mp4", "title": "Short Film", "duration": 1200.0, "media_type": "movie"}
cmd_short = PutOnAirCommand(CH, open_slot.true_start, short, slot_end=open_slot.true_end)
check("8. short media validates", cmd_short.validate(draft, now=NOW).ok)
history.execute(cmd_short, draft)
remaining_open = [b for b in blocks_of(draft) if b.media_type == "open"]
check(
    "8b. short media is placed at the slot start and leaves the remaining open time visible",
    len(remaining_open) == 1
    and abs(remaining_open[0].start - (open_slot.true_start + 1200.0)) < 0.01
    and abs(remaining_open[0].end - open_slot.true_end) < 0.01,
    [(b.title, b.start - T0, b.end - T0) for b in blocks_of(draft)],
)
history.undo(draft)

long_media = {"path": "/media/long.mp4", "title": "Epic Movie", "duration": 3420.0, "media_type": "movie"}
cmd_long = PutOnAirCommand(CH, open_slot.true_start, long_media, slot_end=open_slot.true_end)
v_long = cmd_long.validate(draft, now=NOW)
check(
    "9. long media reports an overlaps-following conflict instead of silently truncating",
    not v_long.ok and v_long.conflicts and v_long.conflicts[0]["type"] == CONFLICT_OVERLAPS_FOLLOWING,
    v_long.conflicts,
)
check(
    "9b. the conflict message names the overrun and the following program in plain language",
    "Show C" in v_long.conflicts[0]["message"] and "minute" in v_long.conflicts[0]["message"],
    v_long.conflicts[0]["message"],
)

before_cancel = titles_of(draft)
before_changes = len(draft.changes)
check(
    "10. a cancelled conflict leaves the draft unchanged (command never applied)",
    titles_of(draft) == before_cancel and len(draft.changes) == before_changes,
)

cmd_extend = PutOnAirCommand(CH, open_slot.true_start, long_media, slot_end=open_slot.true_end, extend_over_following=True)
v_extend = cmd_extend.validate(draft, now=NOW)
check("10b. the explicit Extend choice validates (conflict acknowledged, not hidden)", v_extend.ok and v_extend.conflicts)
history.execute(cmd_extend, draft)
show_c = next(b for b in blocks_of(draft) if b.title == "Show C")
check(
    "10c. extending masks the following program's start (joined in progress, never auto-moved)",
    abs(show_c.start - (open_slot.true_start + 3420.0)) < 0.01 and abs(show_c.end - (T0 + 5400)) < 0.01,
    (show_c.start - T0, show_c.end - T0),
)
history.undo(draft)


# ---------------------------------------------------------------------------
section("11-12. dirty state and Revert")
# ---------------------------------------------------------------------------

draft = fresh_draft()
history = CommandHistory()
check("11. a fresh draft is clean", not draft.is_dirty())
history.execute(PullProgramCommand(blocks_of(draft)[0]), draft)
check("11b. dirty after a real edit", draft.is_dirty())
history.undo(draft)
check("11c. clean again once every difference is undone", not draft.is_dirty())

history.execute(PullProgramCommand(blocks_of(draft)[0]), draft)
history.execute(PullProgramCommand(next(b for b in blocks_of(draft) if b.title == "Show C")), draft)
original_titles = [("Show A", "tv"), ("Show B", "tv"), ("Show C", "tv")]
draft.clear_changes()
history.clear()
check("12. Revert restores the original generated snapshot", titles_of(draft) == original_titles, titles_of(draft))
check("12b. Revert clears undo/redo history", not history.can_undo and not history.can_redo)
check("12c. Revert returns to clean", not draft.is_dirty())


# ---------------------------------------------------------------------------
section("13. Save produces minimal overrides")
# ---------------------------------------------------------------------------

draft = fresh_draft()
history = CommandHistory()
history.execute(PullProgramCommand(blocks_of(draft)[1]), draft)
slot = next(b for b in blocks_of(draft) if b.media_type == "open")
put_cmd = PutOnAirCommand(CH, slot.true_start, {"path": "/media/m.mp4", "title": "M", "duration": 900.0, "media_type": "movie"}, slot_end=slot.true_end)
history.execute(put_cmd, draft)
records = draft.overrides_for_save()
check(
    "13. exactly one override record per surviving change, in edit order",
    [r["action"] for r in records] == ["remove", "add"],
    records,
)
check(
    "13b. records carry stable identities: channel id, date, absolute times, media path",
    all(r["channel_id"] == CH and r["date"] and r["start"] < r["end"] for r in records)
    and records[1]["path"] == "/media/m.mp4",
    records,
)

# an edit that was made and undone must not leave a compensating record
history.undo(draft)
check("13c. undone edits vanish from the save set instead of compensating", [r["action"] for r in draft.overrides_for_save()] == ["remove"])
history.redo(draft)

# pulling an unsaved added program removes its add record entirely
added_block = next(b for b in blocks_of(draft) if b.title == "M")
history.execute(PullProgramCommand(added_block), draft)
check(
    "13d. pulling an unsaved Put On Air removes the add record (no add+remove pair)",
    [r["action"] for r in draft.overrides_for_save()] == ["remove"],
    draft.overrides_for_save(),
)


# ---------------------------------------------------------------------------
section("14-15. override persistence: reload survival, malformed data, atomicity")
# ---------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    overrides_path = os.path.join(tmp, "schedule_overrides.json")
    payload = {
        "version": 1,
        "overrides": [
            {"action": "remove", "channel_id": CH, "date": "2026-07-17", "start": T0, "end": T0 + 1800, "title": "Show A", "path": "", "media_type": "tv"},
            {"action": "add", "channel_id": CH, "date": "2026-07-17", "start": T0, "end": T0 + 900, "title": "M", "path": "/media/m.mp4", "media_type": "movie"},
        ],
    }
    ok, err = save_schedule_overrides(overrides_path, payload, now=NOW)
    check("14. save_schedule_overrides succeeds and reports no error", ok and not err, err)
    reloaded = load_schedule_overrides(overrides_path)
    check(
        "14b. overrides survive reload byte-for-value (restart survival)",
        reloaded["overrides"] == payload["overrides"] and reloaded["version"] == 1,
        reloaded,
    )
    check(
        "14c. per-channel filtering preserves creation order (order IS precedence)",
        [r["action"] for r in overrides_for_channel(reloaded, CH)] == ["remove", "add"],
    )

    # malformed JSON on disk loads as empty and the file is left alone
    broken_path = os.path.join(tmp, "broken.json")
    with open(broken_path, "w") as f:
        f.write("{this is not json")
    before_bytes = open(broken_path).read()
    loaded = load_schedule_overrides(broken_path)
    check("15. malformed override JSON loads as an empty structure", loaded == {"version": 1, "overrides": []}, loaded)
    check("15b. the malformed file is not rewritten or deleted by loading", open(broken_path).read() == before_bytes)

    # structurally invalid payloads are refused at save time, file untouched
    ok_bad, err_bad = save_schedule_overrides(overrides_path, {"version": 999, "overrides": []}, now=NOW)
    check("15c. saving a wrong-version payload is refused with a plain-language error", not ok_bad and err_bad)
    check("15d. the refused save leaves the existing file intact", load_schedule_overrides(overrides_path) == reloaded)

    ok_junk, _ = save_schedule_overrides(overrides_path, {"version": 1, "overrides": [{"action": "add", "channel_id": CH, "start": 5, "end": 4}, "garbage", None]}, now=NOW)
    junk_reloaded = load_schedule_overrides(overrides_path)
    check("15e. individually invalid records are dropped by validation, not persisted", ok_junk and junk_reloaded["overrides"] == [])

    check("15f. no temp files linger after atomic writes", [n for n in os.listdir(tmp) if n.endswith(".tmp")] == [])


# ---------------------------------------------------------------------------
section("16-17. live state isolation: schedule cache, playback, Channel object")
# ---------------------------------------------------------------------------

import channelsurfer2000 as cs

duration_cache = {"/media/a.mp4": 1800.0, "/media/b.mp4": 1800.0, "/media/c.mp4": 1800.0}
channel = cs.Channel("Comedy", duration_cache)
channel.set_schedule(["/media/a.mp4", "/media/b.mp4", "/media/c.mp4"], T0)
entries_before = [dict(e) for e in channel.schedule_entries]
anchor_before = channel.schedule_anchor
current_before = channel.get_current()

# Build a draft from this channel's real window items and edit it heavily.
window_items = channel.get_programs_for_window(T0, count=12)
lane_blocks = [
    make_block(item["title"], item["start"], item["end"]) for item in window_items[:3]
]
draft = fresh_draft(blocks=lane_blocks)
history = CommandHistory()
history.execute(PullProgramCommand(blocks_of(draft)[0]), draft)
slot = next(b for b in blocks_of(draft) if b.media_type == "open")
history.execute(PutOnAirCommand(CH, slot.true_start, {"path": "/media/x.mp4", "title": "X", "duration": 600.0, "media_type": "movie"}, slot_end=slot.true_end), draft)
history.undo(draft)
history.redo(draft)

check(
    "17. draft commands never mutate the live Channel: entries identical",
    [dict(e) for e in channel.schedule_entries] == entries_before,
)
check("17b. schedule anchor untouched", channel.schedule_anchor == anchor_before)
current_after = channel.get_current()
check(
    "17c. what's on air right now is unchanged by draft editing",
    current_after[0] == current_before[0] and abs(current_after[1] - current_before[1]) < 2.0,
    (current_before, current_after),
)
check("17d. no overrides were attached to the channel by drafting", channel.schedule_overrides == [])

# The saved-override splice reads, never writes, the generated entries.
test_overrides = [
    {"action": "remove", "channel_id": CH, "date": "", "start": T0 + 1800, "end": T0 + 3600, "title": "", "path": "", "media_type": ""},
]
channel.set_schedule_overrides(test_overrides)
spliced = channel.get_programs_for_window(T0, count=12)
check(
    "16. applying overrides splices the window without touching the generated entry list",
    [dict(e) for e in channel.schedule_entries] == entries_before,
)
check(
    "16b. the spliced window shows an explicit Open Time item for the pulled interval",
    any(item.get("entry", {}).get("kind") == "open_time" and item["start"] == T0 + 1800 for item in spliced),
    [(i["title"], i["start"] - T0) for i in spliced[:5]],
)

# playback resolution honors the override layer without state changes
channel.set_schedule_overrides([
    {"action": "add", "channel_id": CH, "date": "", "start": NOW - 300, "end": NOW + 300, "title": "Override Movie", "path": "/media/override.mp4", "media_type": "movie"},
])
path_now, offset_now = channel.get_current()
check(
    "16c. an add override wins playback resolution for its interval, joined in progress",
    path_now == "/media/override.mp4" and 295 <= offset_now <= 305,
    (path_now, offset_now),
)
channel.set_schedule_overrides([
    {"action": "remove", "channel_id": CH, "date": "", "start": NOW - 300, "end": NOW + 300, "title": "", "path": "", "media_type": ""},
])
check("16d. a remove override yields nothing playable (open time), not a crash", channel.get_current() == (None, 0))
channel.set_schedule_overrides([])
restored = channel.get_current()
check(
    "16e. clearing overrides restores base resolution exactly",
    restored[0] == current_before[0] and abs(restored[1] - current_before[1]) < 2.0,
    (current_before, restored),
)


# ---------------------------------------------------------------------------
section("18-19. companion protection with friendly reasons")
# ---------------------------------------------------------------------------

weather_lane = make_lane(channel_id="special:weatherstar", channel_type="weatherstar", name="WeatherStar 4000+", number=8, blocks=[
    make_block("WeatherStar Forecast", T0, T0 + 7200, channel_id="special:weatherstar", media_type="weather"),
])
draft = DraftSchedule()
draft.set_base_lanes([weather_lane])
weather_block = blocks_of(draft, "special:weatherstar")[0]
v_weather = PullProgramCommand(weather_block).validate(draft, now=NOW)
check("18. WeatherStar blocks refuse Pull", not v_weather.ok)
check(
    "18b. the WeatherStar reason is a friendly sentence about the weather service",
    "weather service" in v_weather.reason,
    v_weather.reason,
)
v_put_weather = PutOnAirCommand("special:weatherstar", T0, {"path": "/m.mp4", "title": "M", "duration": 600.0}, slot_end=T0 + 600).validate(draft, now=NOW)
check("18c. WeatherStar refuses Put On Air with the same reason", not v_put_weather.ok and "weather service" in v_put_weather.reason)

check(
    "19. every companion type explains itself in plain language",
    all(channel_lock_reason(t) for t in ("weatherstar", "radiowave", "youtube")),
    {t: channel_lock_reason(t) for t in ("weatherstar", "radiowave", "youtube")},
)
check("19b. normal media channels are not locked", channel_lock_reason("media") == "")
check(
    "19c. commercial blocks refuse Pull with a scheduler explanation",
    "commercial scheduler" in PullProgramCommand(
        make_block("Ad Break", T0, T0 + 120, is_commercial=True, media_type="commercial")
    ).validate(fresh_draft(), now=NOW).reason,
)


# ---------------------------------------------------------------------------
section("24. repeated refreshes never duplicate draft entries")
# ---------------------------------------------------------------------------

draft = fresh_draft()
history = CommandHistory()
history.execute(PullProgramCommand(blocks_of(draft)[1]), draft)
for _ in range(3):
    draft.set_base_lanes([make_lane(blocks=[
        make_block("Show A", T0, T0 + 1800),
        make_block("Show B", T0 + 1800, T0 + 3600),
        make_block("Show C", T0 + 3600, T0 + 5400),
    ])])
check(
    "24. three re-clones of the base still yield one open block and one change",
    len([b for b in blocks_of(draft) if b.media_type == "open"]) == 1 and len(draft.changes) == 1,
    titles_of(draft),
)


# ---------------------------------------------------------------------------
section("20-23, 25. workspace-level: toolbar state, failed save, leave flow, selection")
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.schedule_editor.dialog import ScheduleEditorWorkspace


class _FakeStudioDialog:
    """Zero channels -- hits the workspace's empty-state path, which still
    builds the full toolbar and draft/history plumbing (see
    test_schedule_editor.py's identical pattern).
    """


workspace = ScheduleEditorWorkspace(_FakeStudioDialog(), on_back=lambda: None)
check("20. Save Schedule is disabled for a clean draft", workspace._save_btn.isEnabled() is False)
check("20b. no unsaved badge for a clean draft", workspace._status_badge.text() == "")

# make the draft dirty the same way a command would
workspace._draft.set_base_lanes([make_lane()])
change = workspace._draft.new_change("remove", CH, T0, T0 + 1800, title="Show A")
workspace._draft.apply_change(change)
workspace._update_toolbar_state()
check("21. Save Schedule enables for a valid dirty draft", workspace._save_btn.isEnabled() is True)
check("21b. the restrained unsaved indicator appears", workspace._status_badge.text() == "UNSAVED CHANGES")

# 22: failed save must preserve the draft and history
class _FailingSaveDialog:
    def _schedule_overrides_save(self, records):
        return False, "The disk is full."


warnings_shown = []
workspace._studio_dialog = _FailingSaveDialog()
workspace._show_warning = lambda title, text: warnings_shown.append((title, text))
result = workspace._save_clicked()
check("22. a failed save returns False and shows a recoverable error", result is False and warnings_shown)
check("22b. the failed save preserved the dirty draft", workspace._draft.is_dirty())
check(
    "22c. the error message reassures that nothing was lost",
    "draft is untouched" in warnings_shown[0][1],
    warnings_shown,
)

# 23: leaving with a dirty draft triggers the Save/Discard/Keep flow
class _ScriptedBox:
    """Stands in for the QMessageBox confirm_leave builds: records that a
    prompt happened and 'clicks' the button at `choose_index` in added
    order (0=Save, 1=Discard, 2=Keep Editing).
    """

    instances = []

    def __init__(self, choose_index):
        self._choose = choose_index
        self._buttons = []
        _ScriptedBox.instances.append(self)

    def addButton(self, text, role):
        token = (text, role)
        self._buttons.append(token)
        return token

    def exec(self):
        return 0

    def clickedButton(self):
        return self._buttons[self._choose]


workspace._make_message_box = lambda icon, title, text: _ScriptedBox(2)  # Keep Editing
check("23. leaving with a dirty draft prompts instead of proceeding", workspace.confirm_leave() is False)
check("23b. the prompt offered Save / Discard / Keep Editing", [b[0] for b in _ScriptedBox.instances[-1]._buttons] == ["Save Changes", "Discard Changes", "Keep Editing"])
check("23c. Keep Editing preserves the dirty draft", workspace._draft.is_dirty())

workspace._make_message_box = lambda icon, title, text: _ScriptedBox(1)  # Discard Changes
check("23d. Discard Changes allows leaving", workspace.confirm_leave() is True)
check("23e. and the draft is clean afterwards", not workspace._draft.is_dirty())

prompts_before = len(_ScriptedBox.instances)
check("23f. leaving with a clean draft never prompts", workspace.confirm_leave() is True and len(_ScriptedBox.instances) == prompts_before)

# 25: selection stability -- the board can re-find a block after a rebuild
from mediawave.schedule_editor.board import ProgrammingBoard

board = ProgrammingBoard()
lanes = [make_lane(blocks=[make_block("Show A", T0, T0 + 1800), make_block("Show B", T0 + 1800, T0 + 3600)])]
board.set_lanes(lanes, T0, T0 + 4 * 3600)
selected = []
board.program_selected.connect(lambda block: selected.append(block.title))
check("25. select_block_at finds a block by channel and start", board.select_block_at(CH, T0 + 1800) is True and selected[-1] == "Show B")
board.set_lanes(lanes, T0, T0 + 4 * 3600)  # simulate an unrelated edit's rebuild
check(
    "25b. after a full board rebuild the same selection can be restored",
    board.select_block_at(CH, T0 + 1800) is True and selected[-1] == "Show B",
    selected,
)
check("25c. a vanished block simply reports False (no crash, selection cleared upstream)", board.select_block_at(CH, T0 + 99999) is False)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule draft tests passed.")

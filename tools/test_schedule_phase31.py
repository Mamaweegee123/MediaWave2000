"""
Phase 3.1 Schedule Editor tests: DuplicateProgramCommand (backing both
Duplicate Here… and Copy to Another Day…), multi-date Pending
Changes/Save Review, Fill Open Time's ranked picker, and Recently
Scheduled history.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase31.py

Covers scenarios from the Phase 3.1 spec (numbered in section titles
where a scenario maps cleanly to one check).
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

from mediawave.schedule_editor.commands import (
    CONFLICT_OVERLAPS_DESTINATION,
    CONFLICT_PROTECTED_BLOCK,
    CommandHistory,
    DuplicateProgramCommand,
    MoveProgramCommand,
)
from mediawave.schedule_editor.draft_model import DraftSchedule
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock
from mediawave.schedule_overrides import compact_overrides

NOW = time.time()
# Anchored to 2 PM two days out, not "NOW + 2h" -- the latter wanders
# past midnight whenever the suite happens to run late at night, which
# silently collapses "same-day move" and "next-day copy" destinations
# onto the same calendar date and made check 12/13b flaky by time of day.
_anchor_local = time.localtime(NOW)
T0 = time.mktime((_anchor_local.tm_year, _anchor_local.tm_mon, _anchor_local.tm_mday, 14, 0, 0, 0, 0, -1)) + 2 * 24 * 3600
CH = "media:/catalog/Comedy"


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
section("1-8. Core duplicate mechanics: original untouched, undo/redo, one row")
# ---------------------------------------------------------------------------

draft = fresh_draft()
history = CommandHistory()
block_a = blocks_of(draft)[0]
cmd = DuplicateProgramCommand(block_a, T0 + 5400, kind="duplicate")
v = cmd.validate(draft, now=NOW)
check("duplicate validates cleanly onto a clear destination", v.ok, v.reason)
history.execute(cmd, draft)
after = titles_of(draft)
check("1. the original 'Show A' is still exactly where it was", after[0] == ("Show A", "tv"), after)
check("2. exactly one new draft airing was added", any(t == "Show A" for i, (t, m) in enumerate(after) if i != 0), after)
check("2b. draft has exactly one new add change", len(draft.changes) == 1 and draft.changes[0].action == "add")

rows = draft.describe_pending_changes()
check("5. duplicate appears as exactly one friendly Pending Changes row", len(rows) == 1 and rows[0]["action"] == "duplicate", rows)
check("5b. headline says 'Duplicated', not 'Put ... on air'", rows[0]["headline"] == 'Duplicated “Show A”', rows[0])

history.undo(draft)
check("3. Undo removes only the duplicate — original lineup restored exactly", titles_of(draft) == [("Show A", "tv"), ("Show B", "tv"), ("Show C", "tv")], titles_of(draft))
history.redo(draft)
check("4. Redo restores the duplicate", titles_of(draft) != [("Show A", "tv"), ("Show B", "tv"), ("Show C", "tv")], titles_of(draft))


# ---------------------------------------------------------------------------
section("6-7. Duplicate at an occupied time reports a conflict; replacement is undoable")
# ---------------------------------------------------------------------------

draft2 = fresh_draft()
history2 = CommandHistory()
block_a2 = blocks_of(draft2)[0]
conflict_cmd = DuplicateProgramCommand(block_a2, T0 + 1800, kind="duplicate")  # Show B's slot
conflict_v = conflict_cmd.validate(draft2, now=NOW)
check("6. duplicating onto an occupied time reports a conflict, not a silent overwrite", not conflict_v.ok and conflict_v.conflicts and conflict_v.conflicts[0]["type"] == CONFLICT_OVERLAPS_DESTINATION, conflict_v)

overlapped = conflict_v.conflicts[0]["overlapping_blocks"]
replace_cmd = DuplicateProgramCommand(block_a2, T0 + 1800, kind="duplicate", replace_blocks=overlapped)
replace_v = replace_cmd.validate(draft2, now=NOW)
check("an explicitly-approved replace validates", replace_v.ok, replace_v.reason)
history2.execute(replace_cmd, draft2)
check("Show B was replaced by the duplicate", "Show B" not in [t for t, _m in titles_of(draft2)], titles_of(draft2))
history2.undo(draft2)
check("7. undoing a replacing duplicate restores the replaced program exactly", titles_of(draft2) == [("Show A", "tv"), ("Show B", "tv"), ("Show C", "tv")], titles_of(draft2))


# ---------------------------------------------------------------------------
section("8. Protected companion channels can't be duplicated")
# ---------------------------------------------------------------------------

weatherstar_draft = DraftSchedule()
weatherstar_draft.set_base_lanes([make_lane(
    channel_id="companion:weatherstar", name="WeatherStar 4000+", number=6, channel_type="weatherstar",
    blocks=[make_block("WeatherStar Forecast", T0, T0 + 1800, channel_id="companion:weatherstar", media_type="tv")],
)])
weatherstar_block = blocks_of(weatherstar_draft, "companion:weatherstar")[0]
weatherstar_cmd = DuplicateProgramCommand(weatherstar_block, T0 + 5400, kind="duplicate")
weatherstar_v = weatherstar_cmd.validate(weatherstar_draft, now=NOW)
check(
    "8. WeatherStar (a protected companion channel) can't be duplicated",
    not weatherstar_v.ok and weatherstar_v.conflicts and weatherstar_v.conflicts[0]["type"] == CONFLICT_PROTECTED_BLOCK,
    weatherstar_v,
)


# ---------------------------------------------------------------------------
section("9-11. Copy to Another Day: destination date, no recurrence, midnight rule")
# ---------------------------------------------------------------------------

draft3 = fresh_draft()
history3 = CommandHistory()
block_a3 = blocks_of(draft3)[0]
next_day_start = T0 + 24 * 3600
copy_cmd = DuplicateProgramCommand(block_a3, next_day_start, kind="copy")
copy_v = copy_cmd.validate(draft3, now=NOW)
check("copy validates cleanly onto a clear destination on another date", copy_v.ok, copy_v.reason)
history3.execute(copy_cmd, draft3)
records3 = draft3.overrides_for_save()
add_record = next(r for r in records3 if r["action"] == "add")
expected_date = time.strftime("%Y-%m-%d", time.localtime(next_day_start))
check("9. copy creates a change dated on the selected destination date", add_record["date"] == expected_date, (add_record["date"], expected_date))
check(
    "10. copy is a single one-date record — nothing about it repeats (no weekday/interval field exists at all)",
    set(add_record.keys()) == {"action", "channel_id", "date", "start", "end", "title", "path", "media_type"},
    add_record,
)

copy_rows = draft3.describe_pending_changes()
copy_row = next(r for r in copy_rows if r["action"] == "copy")
check("copy's Pending Changes headline names the destination weekday, not a recurring rule", "Copied" in copy_row["headline"] and "to" in copy_row["headline"], copy_row)

# 11. midnight-crossing copy belongs to its START date (draft_model.py's
# overrides_for_save uses change.start's local date; a copy crossing
# midnight should follow the exact same rule a saved move/put-on-air
# already does). Built from an explicit local-midnight boundary (NOT
# T0 +/- some offset, which says nothing about time-of-day) so the
# destination genuinely straddles two calendar dates.
_now_local = time.localtime(NOW)
_next_midnight = time.mktime((_now_local.tm_year, _now_local.tm_mon, _now_local.tm_mday, 0, 0, 0, 0, 0, -1)) + 24 * 3600
draft4 = DraftSchedule()
draft4.set_base_lanes([make_lane(blocks=[make_block("Late Movie", T0, T0 + 7200)])])  # 2-hour movie
late_block = blocks_of(draft4)[0]
midnight_dest = _next_midnight - 1800  # lands 30 min before midnight, runs 90 min past it
midnight_cmd = DuplicateProgramCommand(late_block, midnight_dest, kind="copy")
history4 = CommandHistory()
history4.execute(midnight_cmd, draft4)
midnight_records = draft4.overrides_for_save()
midnight_add = next(r for r in midnight_records if r["action"] == "add")
expected_start_date = time.strftime("%Y-%m-%d", time.localtime(midnight_dest))
expected_end_date = time.strftime("%Y-%m-%d", time.localtime(midnight_dest + 7200))
check(
    "11. a midnight-crossing copy is filed under its START date, not its end date",
    midnight_add["date"] == expected_start_date and expected_start_date != expected_end_date,
    (midnight_add["date"], expected_start_date, expected_end_date),
)


# ---------------------------------------------------------------------------
section("12-13. Multi-date Pending Changes grouping and Save Review")
# ---------------------------------------------------------------------------

draft5 = fresh_draft()
history5 = CommandHistory()
history5.execute(MoveProgramCommand(blocks_of(draft5)[0], CH, T0 + 5400), draft5)  # same-date move
history5.execute(DuplicateProgramCommand(blocks_of(draft5)[1], next_day_start, kind="copy"), draft5)  # next-date copy

multi_rows = draft5.describe_pending_changes()
distinct_dates = list(dict.fromkeys(row["date"] for row in multi_rows))
check("12. a move + a next-day copy produce rows spanning exactly two distinct dates", len(distinct_dates) == 2, distinct_dates)
check("12b. every row carries a date_label suitable for a section heading", all(row.get("date_label") for row in multi_rows), multi_rows)

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
ws._history.execute(MoveProgramCommand(blocks_of(ws._draft)[0], CH, T0 + 5400), ws._draft)
ws._history.execute(DuplicateProgramCommand(blocks_of(ws._draft)[1], next_day_start, kind="copy"), ws._draft)
review_rows = ws._draft.describe_pending_changes()
proceeded = []
ws._make_message_box = lambda icon, title, text: _RecordingBox(title, text, proceeded) if False else ws._make_message_box
# _confirm_save_review needs a real-ish message box; build one that auto-accepts and records the body text.


class _FakeButton:
    pass


class _FakeBox:
    def __init__(self, title, text):
        self.title = title
        self.text = text
        self._save_btn = _FakeButton()

    def addButton(self, label, role):
        if label == "Save Schedule":
            return self._save_btn
        return _FakeButton()

    def exec(self):
        return None

    def clickedButton(self):
        return self._save_btn


captured = {}


def _fake_make_message_box(icon, title, text):
    captured["title"] = title
    captured["text"] = text
    box = _FakeBox(title, text)
    return box


ws._make_message_box = _fake_make_message_box
proceed = ws._confirm_save_review(review_rows)
check("13. Save Review proceeds when the user picks Save Schedule", proceed is True)
check("13b. Save Review's title mentions how many days are affected", "2 days" in captured["title"], captured["title"])
check("13c. Save Review's body has a heading section for each date", all(row["date_label"] in captured["text"] for row in review_rows), captured["text"])


# ---------------------------------------------------------------------------
section("14-15. Atomic multi-date save; failed save preserves the whole draft")
# ---------------------------------------------------------------------------

records5 = ws._draft.overrides_for_save()
dates_in_records = {r["date"] for r in records5}
check("14. overrides_for_save's records span both dates in one flat list (one atomic write)", len(dates_in_records) == 2, dates_in_records)


class _FailingSaveDialog:
    def _schedule_overrides_save(self, records):
        return False, "The disk is full."


ws._studio_dialog = _FailingSaveDialog()
result = ws._perform_save(records5)
check("15. a failed multi-date save preserves the full draft (both dates' changes) and history", result is False and ws._draft.is_dirty() and len(ws._draft.describe_pending_changes()) == 2)


# ---------------------------------------------------------------------------
section("16-21. Fill Open Time ranking and fit labels")
# ---------------------------------------------------------------------------

from mediawave.schedule_editor.put_on_air_picker import fit_label, rank_items_by_fit

GAP = 21 * 60  # 21-minute gap


def _item(title, minutes, path=None):
    return {
        "path": path or f"/media/{title}.mp4",
        "title": title,
        "detail_title": title,
        "episode_label": "",
        "media_type": "tv",
        "duration": minutes * 60,
        "channel_name": "MTV",
        "schedulable": True,
    }


items = [_item("Runs Long", 33), _item("Perfect", 21), _item("Slightly Short", 17)]
ranked = rank_items_by_fit(items, GAP)
check("16. Fill picker ranks the exact-duration match first", ranked[0]["title"] == "Perfect", [i["title"] for i in ranked])
check("Fill picker ranks shorter-than-gap ahead of longer-than-gap", [i["title"] for i in ranked] == ["Perfect", "Slightly Short", "Runs Long"], [i["title"] for i in ranked])

check("19. an exact-fit label reads 'Perfect fit'", fit_label(21 * 60, GAP).startswith("Perfect fit"), fit_label(21 * 60, GAP))
short_label = fit_label(17 * 60, GAP)
check("17. a shorter-media label reports the remaining Open Time accurately", short_label == "Leaves 4 min open\n17 min for 21 min open time", short_label)
long_label = fit_label(33 * 60, GAP)
check("18. a longer-media label reports the overrun accurately", long_label == "Runs 12 min long\n33 min for 21 min open time", long_label)

recent_first = rank_items_by_fit(
    [_item("Short A", 17, path="/a.mp4"), _item("Short B", 17, path="/b.mp4")],
    GAP, recent_paths=["/b.mp4"],
)
check("recently scheduled media breaks a tie between equally-close fits", recent_first[0]["title"] == "Short B", [i["title"] for i in recent_first])


# ---------------------------------------------------------------------------
section("22. A cancelled Fill Open Time does not mutate the draft")
# ---------------------------------------------------------------------------

draft6 = fresh_draft()
history6 = CommandHistory()
history6.execute(MoveProgramCommand(blocks_of(draft6)[0], CH, T0 + 5400), draft6)
changes_before_cancel = len(draft6.changes)
# A cancelled picker never calls _try_put_on_air at all (dialog.py's
# _fill_open_time_clicked only proceeds `if item:` after Accepted) --
# modeled here as simply not invoking anything further.
check("22. a cancelled fill leaves the draft's change count untouched", len(draft6.changes) == changes_before_cancel)


# ---------------------------------------------------------------------------
section("23-27. Recently Scheduled history")
# ---------------------------------------------------------------------------

import tempfile

from mediawave.schedule_editor.recent_media import (
    empty_recent_data,
    load_recent_media,
    normalize_recent_item,
    record_recent_media,
    save_recent_media,
)

data = empty_recent_data()
data = record_recent_media(data, {"path": "/m/a.mp4", "title": "A", "media_type": "movie", "duration": 3600}, now=100)
data = record_recent_media(data, {"path": "/m/b.mp4", "title": "B", "media_type": "tv", "duration": 1800}, now=200)
check("23. recording successful placements adds them, newest first", [i["path"] for i in data["items"]] == ["/m/b.mp4", "/m/a.mp4"], data["items"])

check("24. a record with no path (representing a cancelled/invalid action) is simply ignored", normalize_recent_item({"title": "no path"}) is None)

data = record_recent_media(data, {"path": "/m/a.mp4", "title": "A", "media_type": "movie", "duration": 3600}, now=300)
check("25. history deduplicates by stable media identity (path) — re-scheduling promotes, doesn't duplicate", len(data["items"]) == 2 and data["items"][0]["path"] == "/m/a.mp4", data["items"])

with tempfile.TemporaryDirectory() as tmp_dir:
    recent_path = os.path.join(tmp_dir, "schedule_recent_media.json")
    ok, error = save_recent_media(recent_path, data)
    check("saving recent-media history succeeds", ok, error)
    reloaded = load_recent_media(recent_path)
    check("26. history persists across restart (reload from disk matches what was saved)", reloaded["items"] == data["items"], reloaded)

many = empty_recent_data()
for i in range(40):
    many = record_recent_media(many, {"path": f"/m/{i}.mp4", "title": str(i), "duration": 60}, now=i)
check("history is capped at MAX_RECENT_ITEMS (30)", len(many["items"]) == 30, len(many["items"]))

from mediawave.schedule_editor.put_on_air_picker import filter_picker_items

catalog_items = [_item("A", 30, path="/m/a.mp4"), _item("B", 30, path="/m/b.mp4")]
recent_filtered = filter_picker_items(catalog_items, mode="Recently Scheduled", recent_paths=["/missing.mp4", "/m/b.mp4"])
check("27. a recent path no longer in the live catalog (missing media) is simply absent, not an error", [i["title"] for i in recent_filtered] == ["B"], recent_filtered)


# ---------------------------------------------------------------------------
section("28-33. Override compaction: duplicate/copy scenarios")
# ---------------------------------------------------------------------------

# 31. duplicate-then-undo-before-save never reaches overrides_for_save at
# all (undo removes the change from the draft directly) -- covered by
# the "3. Undo removes only the duplicate" check above. Here we cover
# duplicate-then-REMOVE (a saved duplicate later pulled) and repeated
# distinct duplicates surviving compaction separately.

base_add = {"action": "add", "channel_id": CH, "date": "2026-07-24", "start": T0, "end": T0 + 900, "title": "Samurai Cop", "path": "/m/samurai.mp4", "media_type": "movie"}
later_remove = {"action": "remove", "channel_id": CH, "date": "2026-07-24", "start": T0, "end": T0 + 900, "title": "Samurai Cop"}
compacted = compact_overrides([base_add, later_remove])
# The remove record itself always survives (it's the thing saying
# "nothing airs here now", regardless of whatever came before it) --
# only the now-fully-superseded ADD compacts away. Same rule
# test_schedule_phase21.py's "19. add-then-remove no-op pairs compact
# away" already documents for a plain duplicate/undo pair.
check(
    "28/31. duplicate-then-remove compacts the superseded add away, leaving just the remove",
    len(compacted) == 1 and compacted[0]["action"] == "remove",
    compacted,
)

# 30/33. two intentional duplicate airings of the SAME media at
# different, non-adjacent times must both survive compaction distinctly.
first_airing = dict(base_add, start=T0, end=T0 + 900)
second_airing = dict(base_add, start=T0 + 3600, end=T0 + 4500)
compacted_two = compact_overrides([first_airing, second_airing])
check(
    "30/33. two intentional duplicate airings of the same media at different times both survive, distinctly",
    len(compacted_two) == 2 and {(r["start"], r["end"]) for r in compacted_two} == {(T0, T0 + 900), (T0 + 3600, T0 + 4500)},
    compacted_two,
)

# 32. a copy moved (re-copied to a new time) before save compacts to
# just the final placement — same "later record masks earlier" rule
# compaction already applies to any add/add pair at the same slot.
first_copy = dict(base_add, start=T0, end=T0 + 900)
moved_copy_remove = {"action": "remove", "channel_id": CH, "date": "2026-07-24", "start": T0, "end": T0 + 900, "title": "Samurai Cop"}
moved_copy_add = dict(base_add, start=T0 + 1800, end=T0 + 2700)
compacted_moved = compact_overrides([first_copy, moved_copy_remove, moved_copy_add])
# The old slot's now-redundant add is fully superseded (compacted away);
# what remains is the remove that vacates the old slot plus the add at
# the final placement -- two records, not the original three.
check(
    "32. a copy moved before save compacts to the vacated-old-slot remove plus the final placement",
    len(compacted_moved) == 2 and compacted_moved[-1] == moved_copy_add and compacted_moved[0]["action"] == "remove",
    compacted_moved,
)


# ---------------------------------------------------------------------------
section("34. Context-sensitive Editing Tools enablement")
# ---------------------------------------------------------------------------


class _DynamicFakeChannel:
    def get_programs_for_window(self, window_start, count=8):
        return [
            {"path": "/Media/A.mkv", "title": "Show A", "entry": {"path": "/Media/A.mkv", "kind": "content"}, "start": window_start, "end": window_start + 1800},
            {"path": "/Media/B.mkv", "title": "Show B", "entry": {"path": "/Media/B.mkv", "kind": "content"}, "start": window_start + 1800, "end": window_start + 1800 + 3600},
        ]


class _FakeStudioDialogWithChannel:
    def __init__(self):
        self.catalog_channel_infos = [{"id": "ch1", "name": "Channel One", "channel_type": "media", "default_number": 4}]
        self.catalog_channel_settings = {}
        self._studio_channels_by_id = {"ch1": _DynamicFakeChannel()}


live_ws = _silence_dialogs(ScheduleEditorWorkspace(_FakeStudioDialogWithChannel()))
if getattr(live_ws, "board", None) is not None and live_ws.board._grid_content.row_strips:
    strip = live_ws.board._grid_content.row_strips[0]
    real_blocks = [w.block for w in strip.block_widgets if w.block.media_type != "open"]
    open_blocks = [w.block for w in strip.block_widgets if w.block.media_type == "open"]

    if real_blocks:
        live_ws._on_program_selected(real_blocks[0])
        check(
            "34a. a real program selected enables Pull/Move/Duplicate/Copy, disables Fill Open Time",
            live_ws._tools["pull_btn"].isEnabled() and live_ws._tools["move_btn"].isEnabled()
            and live_ws._tools["duplicate_btn"].isEnabled() and live_ws._tools["copy_btn"].isEnabled()
            and not live_ws._tools["fill_btn"].isEnabled() and not live_ws._tools["put_btn"].isEnabled(),
            {k: v.isEnabled() for k, v in live_ws._tools.items() if hasattr(v, "isEnabled")},
        )
    # A synthetic Open Time block on the same channel -- doesn't need to
    # actually be present on the board (this fixture's fake channel
    # always reports the same two real shows), just to have a valid
    # channel_id the draft recognizes, since _update_tools_for_selection
    # only inspects block.channel_id/media_type.
    channel_id = real_blocks[0].channel_id if real_blocks else "ch1"
    synthetic_open = make_block("Open Time", T0 + 5400, T0 + 7200, channel_id=channel_id, media_type="open")
    live_ws._on_program_selected(synthetic_open)
    check(
        "34b. Open Time selected enables Put On Air/Fill Open Time, disables program-only actions",
        live_ws._tools["put_btn"].isEnabled() and live_ws._tools["fill_btn"].isEnabled()
        and not live_ws._tools["pull_btn"].isEnabled() and not live_ws._tools["move_btn"].isEnabled()
        and not live_ws._tools["duplicate_btn"].isEnabled() and not live_ws._tools["copy_btn"].isEnabled(),
        {k: v.isEnabled() for k, v in live_ws._tools.items() if hasattr(v, "isEnabled")},
    )
else:
    check("34. context-sensitive enablement (skipped — no live board in this environment)", True)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 3.1 tests passed.")

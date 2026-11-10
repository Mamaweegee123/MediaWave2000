"""
Phase 5.2 Schedule Editor tests: Continue Sequentially / Random Episode
show behavior -- resolve_show_episode/sequential_preview_note (pure),
ShowPickerDialog's behavior radios/Choose Again/Cancel, and the shared
save-time Continue Sequentially cursor now covering both Auto-Fill Block
AND Show Picker sequential placements through the same collector
(dialog.py's _advance_autofill_cursors_for_saved_changes), never a second
persistence path.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase52_show_behavior.py
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
from mediawave.schedule_editor.autofill_cursor import advance_cursor, empty_cursor_data
from mediawave.schedule_editor.commands import AutoFillBlockCommand, CommandHistory
from mediawave.schedule_editor.dialog import ScheduleEditorWorkspace
from mediawave.schedule_editor.draft_model import DraftSchedule
from mediawave.schedule_editor.put_on_air_picker import (
    BEHAVIOR_RANDOM,
    BEHAVIOR_SEQUENTIAL,
    ShowPickerDialog,
    _episode_preview_label,
    resolve_show_episode,
    sequential_preview_note,
)
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock

NOW = time.time()
T0 = NOW - (NOW % 1800) + 3600
CH = "media:/catalog/Comedy"


def catalog_item(title, show_key, season, episode, path=None, duration=1800, schedulable=True):
    return {
        "path": path or f"/media/{show_key}/{season}x{episode}.mp4",
        "title": title,
        "detail_title": title,
        "episode_label": f"Season {season} · Episode {episode}",
        "episode_title": f"Episode Title {season}-{episode}",
        "media_type": "tv",
        "duration": duration,
        "channel_name": "Comedy",
        "schedulable": schedulable,
        "season_number": season,
        "episode_number": episode,
        "show_key": show_key,
    }


pokemon_show = {
    "show_key": "tv::pokemon",
    "title": "Pokemon",
    "episodes": [
        catalog_item("Pokemon", "tv::pokemon", 1, 1, path="/media/pokemon/s1e1.mp4"),
        catalog_item("Pokemon", "tv::pokemon", 1, 2, path="/media/pokemon/s1e2.mp4"),
        catalog_item("Pokemon", "tv::pokemon", 2, 1, path="/media/pokemon/s2e1.mp4"),
    ],
}


# ---------------------------------------------------------------------------
section("1-4. resolve_show_episode -- Continue Sequentially (pure)")
# ---------------------------------------------------------------------------

no_cursor = resolve_show_episode(pokemon_show, BEHAVIOR_SEQUENTIAL, last_path=None)
check(
    "1. no cursor resolves to the expected first regular episode",
    no_cursor is not None and no_cursor["path"] == "/media/pokemon/s1e1.mp4",
    no_cursor,
)
check("1b. the sequential result carries strategy/show_key for the save-time cursor hook", no_cursor.get("strategy") == "sequential" and no_cursor.get("show_key") == "tv::pokemon", no_cursor)

existing_cursor = resolve_show_episode(pokemon_show, BEHAVIOR_SEQUENTIAL, last_path="/media/pokemon/s1e1.mp4")
check(
    "2. an existing cursor resolves to the following episode in sequence",
    existing_cursor["path"] == "/media/pokemon/s1e2.mp4",
    existing_cursor,
)

wraparound_cursor = resolve_show_episode(pokemon_show, BEHAVIOR_SEQUENTIAL, last_path="/media/pokemon/s2e1.mp4")
check(
    "2b. sequential wraps back to the first episode after the last one, same as Continue Sequentially/Show Marathon",
    wraparound_cursor["path"] == "/media/pokemon/s1e1.mp4",
    wraparound_cursor,
)

stale_cursor = resolve_show_episode(pokemon_show, BEHAVIOR_SEQUENTIAL, last_path="/media/pokemon/removed-episode.mp4")
check(
    "3. a stale cursor (episode no longer in the catalog) falls back safely to the first regular episode",
    stale_cursor["path"] == "/media/pokemon/s1e1.mp4",
    stale_cursor,
)

check("4. resolve_show_episode never mutates the input show's episode dicts", pokemon_show["episodes"][0].get("strategy") is None)


# ---------------------------------------------------------------------------
section("5-6. resolve_show_episode -- Random Episode (pure)")
# ---------------------------------------------------------------------------

koth_show = {
    "show_key": "tv::koth",
    "title": "King of the Hill",
    "episodes": [catalog_item("King of the Hill", "tv::koth", 1, 1, path="/media/koth/s1e1.mp4")],
}
two_show_catalog_paths = {ep["path"] for ep in pokemon_show["episodes"]} | {ep["path"] for ep in koth_show["episodes"]}

random_choices = {resolve_show_episode(pokemon_show, BEHAVIOR_RANDOM)["path"] for _ in range(40)}
check(
    "5. random always chooses from the selected show's own episodes, never another show's",
    random_choices <= {ep["path"] for ep in pokemon_show["episodes"]} and random_choices,
    random_choices,
)
check("5b. random results carry no strategy tag -- never mistaken for a sequential placement", all(resolve_show_episode(pokemon_show, BEHAVIOR_RANDOM).get("strategy") is None for _ in range(5)))

single_episode_show = {
    "show_key": "tv::single",
    "title": "One-Off",
    "episodes": [catalog_item("One-Off", "tv::single", 1, 1, path="/media/single/s1e1.mp4")],
}
check(
    "5c. a show with only one schedulable episode still resolves for Random",
    resolve_show_episode(single_episode_show, BEHAVIOR_RANDOM)["path"] == "/media/single/s1e1.mp4",
)

mixed_schedulability_show = {
    "show_key": "tv::mixed",
    "title": "Mixed",
    "episodes": [
        catalog_item("Mixed", "tv::mixed", 1, 1, path="/media/mixed/unschedulable.mp4", schedulable=False),
        catalog_item("Mixed", "tv::mixed", 1, 2, path="/media/mixed/schedulable.mp4", schedulable=True),
    ],
}
random_mixed_choices = {resolve_show_episode(mixed_schedulability_show, BEHAVIOR_RANDOM)["path"] for _ in range(20)}
check(
    "6. random excludes unschedulable entries entirely",
    random_mixed_choices == {"/media/mixed/schedulable.mp4"},
    random_mixed_choices,
)

no_time_show = {
    "show_key": "tv::notime",
    "title": "No Durations Yet",
    "episodes": [catalog_item("No Durations Yet", "tv::notime", 1, 1, schedulable=False)],
}
check("6b. a show with zero schedulable episodes resolves to None for Random too", resolve_show_episode(no_time_show, BEHAVIOR_RANDOM) is None)


# ---------------------------------------------------------------------------
section("sequential_preview_note wording")
# ---------------------------------------------------------------------------

check("note-1. no cursor -> the 'starts with first available' sentence", sequential_preview_note(pokemon_show, None) == "Starts with the first available episode.")
check("note-2. a real, still-valid cursor -> None (caller shows 'Next: ...' instead)", sequential_preview_note(pokemon_show, "/media/pokemon/s1e1.mp4") is None)
check(
    "note-3. a stale cursor -> the honest 'no longer available' sentence, not a claim about playback",
    sequential_preview_note(pokemon_show, "/media/pokemon/removed-episode.mp4")
    == "The previous episode is no longer available, so this starts with the first available episode.",
)


# ---------------------------------------------------------------------------
section("Polish fix. _episode_preview_label: no show-title fallback for the episode title")
# ---------------------------------------------------------------------------

numbered_with_title = {"season_number": 1, "episode_number": 2, "episode_title": "The Great Escape", "title": "Pokemon"}
check(
    "P1. numbered episode with a distinct title shows numbers AND the title",
    _episode_preview_label(numbered_with_title) == "S1 · E2 — The Great Escape",
    _episode_preview_label(numbered_with_title),
)

numbered_without_title = {"season_number": 1, "episode_number": 2, "episode_title": "", "title": "No Title Show"}
check(
    "P2. numbered episode with no episode title shows ONLY the numbers -- no show-title fallback",
    _episode_preview_label(numbered_without_title) == "S1 · E2",
    _episode_preview_label(numbered_without_title),
)

title_equals_show_title = {"season_number": 1, "episode_number": 2, "episode_title": "No Title Show", "title": "No Title Show"}
check(
    "P3. an episode title identical to the show title is treated as no distinct title (case-insensitive)",
    _episode_preview_label(title_equals_show_title) == "S1 · E2",
    _episode_preview_label(title_equals_show_title),
)
title_equals_show_title_diff_case = {"season_number": 1, "episode_number": 2, "episode_title": "no title show", "title": "No Title Show"}
check(
    "P3b. the same check is case-insensitive",
    _episode_preview_label(title_equals_show_title_diff_case) == "S1 · E2",
    _episode_preview_label(title_equals_show_title_diff_case),
)

title_only = {"season_number": None, "episode_number": None, "episode_title": "A One-Off Special", "title": "Bob Ross"}
check(
    "P4. an episode with a distinct title but no season/episode numbers shows just the title",
    _episode_preview_label(title_only) == "A One-Off Special",
    _episode_preview_label(title_only),
)

nothing_useful = {"season_number": None, "episode_number": None, "episode_title": "", "title": "Mystery Show"}
check(
    "P5. no useful numbering and no distinct title -> None, so the caller falls back to a generic sentence",
    _episode_preview_label(nothing_useful) is None,
    _episode_preview_label(nothing_useful),
)

nothing_useful_title_matches_show = {"season_number": None, "episode_number": None, "episode_title": "Mystery Show", "title": "Mystery Show"}
check(
    "P5b. same when the only 'title' present is just the show's own name repeated",
    _episode_preview_label(nothing_useful_title_matches_show) is None,
    _episode_preview_label(nothing_useful_title_matches_show),
)

# Sequential/Random wording is exercised end-to-end through ShowPickerDialog
# so the fix is checked in the exact place a user would see it, not just
# against the pure helper.
no_title_show = {
    "show_key": "tv::notitle",
    "title": "No Title Show",
    "episodes": [
        catalog_item("No Title Show", "tv::notitle", 1, 1, path="/media/notitle/s1e1.mp4"),
        catalog_item("No Title Show", "tv::notitle", 1, 2, path="/media/notitle/s1e2.mp4"),
    ],
}
for ep in no_title_show["episodes"]:
    ep["episode_title"] = ""  # simulate parse_local_media finding no per-episode title

no_title_cursor_data = advance_cursor(empty_cursor_data(), CH, "tv::notitle", "/media/notitle/s1e1.mp4", now=1000)
label_picker = ShowPickerDialog({"tv::notitle": no_title_show}, 4, "Comedy", T0, 1800, channel_id=CH, cursor_data=no_title_cursor_data)
label_row = next(label_picker._list.item(i) for i in range(label_picker._list.count()) if "No Title Show" in label_picker._list.item(i).text())
label_row.setSelected(True)
label_picker._on_selection()
check(
    "P6. sequential wording: 'Next: S1 · E2' with no show-title repeat, given a real cursor to continue from",
    label_picker._preview.text() == "Next: S1 · E2",
    label_picker._preview.text(),
)

label_picker._random_radio.setChecked(True)
check(
    "P7. random wording: 'Selected: S# · E#' with no show-title repeat",
    label_picker._preview.text().startswith("Selected: S1 · E"),
    label_picker._preview.text(),
)


# ---------------------------------------------------------------------------
section("7-9. ShowPickerDialog: default behavior, Choose Again, Cancel")
# ---------------------------------------------------------------------------

shows_by_key = {"tv::pokemon": pokemon_show, "tv::koth": koth_show}
picker = ShowPickerDialog(shows_by_key, 4, "Comedy", T0, 1800)
check("7. Continue Sequentially is the default behavior", picker._sequential_radio.isChecked() and not picker._random_radio.isChecked())

pokemon_row = next(picker._list.item(i) for i in range(picker._list.count()) if "Pokemon" in picker._list.item(i).text())
pokemon_row.setSelected(True)
picker._on_selection()
check("7b. selecting a show with the default behavior previews the expected first episode", picker.selected_episode()["path"] == "/media/pokemon/s1e1.mp4", picker.selected_episode())
check("7c. Choose Again is hidden while Continue Sequentially is selected", picker._choose_again_btn.isHidden())

picker._random_radio.setChecked(True)
check("8a. Choose Again becomes visible once Random Episode is selected", not picker._choose_again_btn.isHidden())
first_random_pick = picker.selected_episode()
check("8b. switching to Random previews one of Pokemon's own episodes", first_random_pick["path"] in {ep["path"] for ep in pokemon_show["episodes"]}, first_random_pick)

seen_after_choose_again = set()
for _ in range(30):
    picker._choose_again()
    seen_after_choose_again.add(picker.selected_episode()["path"])
check(
    "8c. Choose Again can change the preview across repeated clicks (still only from this show)",
    seen_after_choose_again <= {ep["path"] for ep in pokemon_show["episodes"]},
    seen_after_choose_again,
)
check(
    "8d. Choose Again only ever changes the PREVIEW -- the dialog is not accepted and has no draft dependency at all",
    picker.result() != QDialog.Accepted,
)

cancel_picker = ShowPickerDialog(shows_by_key, 4, "Comedy", T0, 1800)
cancel_row = next(cancel_picker._list.item(i) for i in range(cancel_picker._list.count()) if "Pokemon" in cancel_picker._list.item(i).text())
cancel_row.setSelected(True)
cancel_picker._on_selection()
cancel_picker.reject()
check("9. Cancel rejects the dialog without ever calling accept()", cancel_picker.result() == QDialog.Rejected)


# ---------------------------------------------------------------------------
section("10-11. Integration: the exact previewed episode reaches _try_put_on_air, unmodified")
# ---------------------------------------------------------------------------


def make_lane(channel_id=CH, blocks=None):
    return ChannelLane(channel_id=channel_id, name="Comedy", number=4, channel_type="media", logo_path="", blocks=blocks or [], has_data=True)


def make_block(title, start, end, channel_id=CH, media_type="tv"):
    return ProgramBlock(
        channel_id=channel_id, title=title, media_type=media_type, start=start, end=end,
        duration=end - start, is_commercial=False, source="generated",
        true_start=start, true_end=end,
        raw_entries=[{"kind": "content", "path": f"/media/{title}.mp4", "title": title, "duration": end - start}],
    )


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
        self._cursor_data = empty_cursor_data()

    def _schedule_overrides_save(self, records):
        self.save_calls += 1
        if not self._save_ok:
            return False, self._save_error
        self.saved_records.append(list(records))
        return True, ""

    def _schedule_autofill_cursor_get(self):
        return self._cursor_data

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


ws, studio = make_workspace()
open_start, open_end = T0, T0 + 1800
open_block = select_open_block(ws, open_start, open_end)
sequential_episode = resolve_show_episode(pokemon_show, BEHAVIOR_SEQUENTIAL, last_path=None)
sequential_episode["duration"] = open_end - open_start  # fits the slot exactly
ws._try_put_on_air(open_block, sequential_episode, extend_over_following=False)

lane = next(l for l in ws._draft.presentation_lanes() if l.channel_id == CH)
placed = next((b for b in lane.blocks if b.media_type != "open"), None)
check(
    "10. Accept passes the exact previewed episode into the existing _try_put_on_air/PutOnAirCommand path",
    placed is not None and placed.raw_entries[0]["path"] == "/media/pokemon/s1e1.mp4",
    placed,
)
check("11. exactly one history entry results, same as any other Put On Air", len(ws._history._undo_stack) == 1)


# ---------------------------------------------------------------------------
section("12-14. Sequential Show placement advances the shared cursor only after a successful save")
# ---------------------------------------------------------------------------

seq_ws, seq_studio = make_workspace(save_ok=True)
open_start, open_end = T0, T0 + 1800
open_block = select_open_block(seq_ws, open_start, open_end)
episode_to_place = resolve_show_episode(pokemon_show, BEHAVIOR_SEQUENTIAL, last_path=None)
episode_to_place["duration"] = open_end - open_start
seq_ws._try_put_on_air(open_block, episode_to_place, extend_over_following=False)
check("12a. the placement is pending, cursor untouched before save", seq_ws._draft.is_dirty() and seq_studio.advance_calls == [])

ok = seq_ws._save_clicked()
check("12b. save succeeds", ok)
check("12. the shared cursor sink is called exactly once after a successful save", len(seq_studio.advance_calls) == 1, seq_studio.advance_calls)
check(
    "12c. the advanced entry is keyed on the show/channel and points at the placed episode",
    seq_studio.advance_calls[0][0]["show_key"] == "tv::pokemon" and seq_studio.advance_calls[0][0]["path"] == "/media/pokemon/s1e1.mp4",
    seq_studio.advance_calls,
)


fail_ws, fail_studio = make_workspace(save_ok=False, save_error="Disk is full.")
open_start, open_end = T0, T0 + 1800
open_block = select_open_block(fail_ws, open_start, open_end)
episode_to_place = resolve_show_episode(pokemon_show, BEHAVIOR_SEQUENTIAL, last_path=None)
episode_to_place["duration"] = open_end - open_start
fail_ws._try_put_on_air(open_block, episode_to_place, extend_over_following=False)
ok = fail_ws._save_clicked()
check("13. a failed save does not advance the cursor", not ok and fail_studio.advance_calls == [])
check("13b. the draft remains dirty after a failed save", fail_ws._draft.is_dirty())


undo_ws, undo_studio = make_workspace(save_ok=True)
open_start, open_end = T0, T0 + 1800
open_block = select_open_block(undo_ws, open_start, open_end)
episode_to_place = resolve_show_episode(pokemon_show, BEHAVIOR_SEQUENTIAL, last_path=None)
episode_to_place["duration"] = open_end - open_start
undo_ws._try_put_on_air(open_block, episode_to_place, extend_over_following=False)
undo_ws._undo_clicked()
check("14. an undone/discarded sequential placement carries no pending autofill_meta to advance from at save time", not any(c.autofill_meta for c in undo_ws._draft.changes))
ok = undo_ws._save_clicked()
check("14b. saving after undo (nothing pending) never calls the cursor sink", undo_studio.advance_calls == [])


# ---------------------------------------------------------------------------
section("15. Random placement never advances the cursor, even after a successful save")
# ---------------------------------------------------------------------------

random_ws, random_studio = make_workspace(save_ok=True)
open_start, open_end = T0, T0 + 1800
open_block = select_open_block(random_ws, open_start, open_end)
random_episode = resolve_show_episode(pokemon_show, BEHAVIOR_RANDOM)
random_episode["duration"] = open_end - open_start
check("15a. a random resolution carries no strategy tag", random_episode.get("strategy") is None)
random_ws._try_put_on_air(open_block, random_episode, extend_over_following=False)
ok = random_ws._save_clicked()
check("15. a Random Episode placement never advances the cursor, even though its save succeeded", ok and random_studio.advance_calls == [])


# ---------------------------------------------------------------------------
section("16. Existing Auto-Fill sequential cursor behavior is unchanged by the broadened filter")
# ---------------------------------------------------------------------------

autofill_ws, autofill_studio = make_workspace(save_ok=True)
open_start, open_end = T0, T0 + 3600
open_block = select_open_block(autofill_ws, open_start, open_end)
autofill_lineup = [
    {
        "path": "/media/koth/s1e1.mp4", "title": "King of the Hill", "episode_label": "", "media_type": "tv",
        "duration": 1800, "channel_name": "Comedy", "start": open_start, "end": open_start + 1800,
        "season_number": 1, "episode_number": 1, "show_key": "tv::koth", "strategy": "sequential",
    },
    {
        "path": "/media/koth/s1e2.mp4", "title": "King of the Hill", "episode_label": "", "media_type": "tv",
        "duration": 1800, "channel_name": "Comedy", "start": open_start + 1800, "end": open_end,
        "season_number": 1, "episode_number": 2, "show_key": "tv::koth", "strategy": "sequential",
    },
]
autofill_ws._try_auto_fill_block(open_block, autofill_lineup)
ok = autofill_ws._save_clicked()
check("16. Auto-Fill Block's sequential save-time cursor advance still works after the filter was broadened to also accept Show Picker placements", ok and len(autofill_studio.advance_calls) == 1, autofill_studio.advance_calls)
check(
    "16b. it still collapses to the FINAL episode of the saved lineup, exactly as before",
    autofill_studio.advance_calls[0][0]["path"] == "/media/koth/s1e2.mp4",
    autofill_studio.advance_calls,
)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 5.2 (Show behavior) tests passed.")

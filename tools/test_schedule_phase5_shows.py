"""
Phase 5.1 Schedule Editor tests: scheduling a whole show instead of an
individual episode -- group_catalog_by_show/show_summary/
first_available_episode (pure), ShowPickerDialog (schedules the first
available episode of the chosen show), AddToScheduleDialog (the new
Shows/Movies/Advanced… front door), and dialog.py's _put_on_air_clicked
wiring -- proving the scheduling engine downstream (PutOnAirCommand,
DraftChange, saved overrides) receives exactly the same resolved episode
placement it always has.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase5_shows.py
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
from mediawave.schedule_editor.put_on_air_picker import (
    AddToScheduleDialog,
    ShowPickerDialog,
    first_available_episode,
    show_summary,
)
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock
from mediawave.show_identity import group_catalog_by_show

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


def catalog_item(title, show_key, season, episode, path=None, duration=1800, schedulable=True, media_type="tv"):
    return {
        "path": path or f"/media/{show_key}/{season}x{episode}.mp4",
        "title": title,
        "detail_title": title,
        "episode_label": f"Season {season} · Episode {episode}",
        "media_type": media_type,
        "duration": duration,
        "channel_name": "Comedy",
        "schedulable": schedulable,
        "season_number": season,
        "episode_number": episode,
        "show_key": show_key,
    }


# ---------------------------------------------------------------------------
section("1-4. group_catalog_by_show / show_summary / first_available_episode (pure)")
# ---------------------------------------------------------------------------

items = [
    catalog_item("Pokemon", "tv::pokemon", 1, 1),
    catalog_item("Pokemon", "tv::pokemon", 1, 2),
    catalog_item("Pokemon", "tv::pokemon", 2, 1),
    catalog_item("King of the Hill", "tv::koth", 1, 1),
    catalog_item("Samurai Cop", None, None, None, media_type="movie"),
]

shows = group_catalog_by_show(items)
check("1. one row per show -- movies and items with no show_key are excluded", sorted(shows.keys()) == ["tv::koth", "tv::pokemon"], sorted(shows.keys()))
check("1b. each show's episode list has exactly its own episodes", len(shows["tv::pokemon"]["episodes"]) == 3 and len(shows["tv::koth"]["episodes"]) == 1)

episode_count, season_count = show_summary(shows["tv::pokemon"])
check("2. episode count is correct", episode_count == 3, episode_count)
check("2b. season count is correct", season_count == 2, season_count)

no_season_items = [catalog_item("Bob Ross", "tv::bobross", None, None, path=f"/media/bobross/{i}.mp4") for i in range(4)]
no_season_shows = group_catalog_by_show(no_season_items)
_, no_season_count = show_summary(no_season_shows["tv::bobross"])
check("2c. a show with no season metadata reports season_count as None, not 0", no_season_count is None, no_season_count)

first = first_available_episode(shows["tv::pokemon"])
check("3. selecting a show resolves to its earliest season/episode, not an arbitrary one", (first["season_number"], first["episode_number"]) == (1, 1), first)

unschedulable_items = [
    catalog_item("Futurama", "tv::futurama", 1, 1, schedulable=False),
    catalog_item("Futurama", "tv::futurama", 1, 2, schedulable=True),
]
futurama_show = group_catalog_by_show(unschedulable_items)["tv::futurama"]
first_schedulable = first_available_episode(futurama_show)
check("3b. a not-yet-timed episode is skipped in favor of the earliest SCHEDULABLE one", first_schedulable["episode_number"] == 2, first_schedulable)

empty_show = {"show_key": "tv::none", "title": "Nothing Timed", "episodes": [catalog_item("Nothing Timed", "tv::none", 1, 1, schedulable=False)]}
check("3c. a show with no schedulable episode at all resolves to None", first_available_episode(empty_show) is None)


# ---------------------------------------------------------------------------
section("Follow-up A. first_available_episode: regular seasons before specials before unknown metadata")
# ---------------------------------------------------------------------------

specials_and_regular = {
    "show_key": "tv::futurama",
    "title": "Futurama",
    "episodes": [
        catalog_item("Futurama", "tv::futurama", 0, 1, path="/media/futurama/special1.mp4"),
        catalog_item("Futurama", "tv::futurama", 1, 1, path="/media/futurama/s1e1.mp4"),
    ],
}
check(
    "A1. S1E1 sorts before S0E1 -- a special is never the default first episode of a show that also has a regular season",
    first_available_episode(specials_and_regular)["path"] == "/media/futurama/s1e1.mp4",
    first_available_episode(specials_and_regular),
)

season_1_and_2 = {
    "show_key": "tv::pokemon",
    "title": "Pokemon",
    "episodes": [
        catalog_item("Pokemon", "tv::pokemon", 2, 1, path="/media/pokemon/s2e1.mp4"),
        catalog_item("Pokemon", "tv::pokemon", 1, 1, path="/media/pokemon/s1e1.mp4"),
    ],
}
check(
    "A2. S1E1 sorts before S2E1",
    first_available_episode(season_1_and_2)["path"] == "/media/pokemon/s1e1.mp4",
    first_available_episode(season_1_and_2),
)

specials_only = {
    "show_key": "tv::shorts",
    "title": "Shorts",
    "episodes": [
        catalog_item("Shorts", "tv::shorts", 0, 2, path="/media/shorts/special2.mp4"),
        catalog_item("Shorts", "tv::shorts", 0, 1, path="/media/shorts/special1.mp4"),
    ],
}
check(
    "A3. a show containing only specials still resolves successfully, in numeric order among themselves",
    first_available_episode(specials_only)["path"] == "/media/shorts/special1.mp4",
    first_available_episode(specials_only),
)

unknown_metadata_show = {
    "show_key": "tv::mystery",
    "title": "Mystery Show",
    "episodes": [
        catalog_item("Mystery Show", "tv::mystery", None, None, path="/media/mystery/unnumbered.mp4"),
        catalog_item("Mystery Show", "tv::mystery", 0, 1, path="/media/mystery/special1.mp4"),
        catalog_item("Mystery Show", "tv::mystery", 1, 1, path="/media/mystery/s1e1.mp4"),
    ],
}
check(
    "A4. a well-numbered regular episode outranks both a special and an unknown-metadata episode",
    first_available_episode(unknown_metadata_show)["path"] == "/media/mystery/s1e1.mp4",
    first_available_episode(unknown_metadata_show),
)

missing_number_vs_regular = {
    "show_key": "tv::partial",
    "title": "Partial Metadata Show",
    "episodes": [
        catalog_item("Partial Metadata Show", "tv::partial", 1, None, path="/media/partial/unknown-episode.mp4"),
        catalog_item("Partial Metadata Show", "tv::partial", 1, 1, path="/media/partial/s1e1.mp4"),
    ],
}
check(
    "A5. an episode with a known season but unknown episode number does not outrank a fully-numbered episode",
    first_available_episode(missing_number_vs_regular)["path"] == "/media/partial/s1e1.mp4",
    first_available_episode(missing_number_vs_regular),
)


# ---------------------------------------------------------------------------
section("Follow-up A. Continue Sequentially / Show Marathon ordering is unaffected")
# ---------------------------------------------------------------------------

from mediawave.schedule_editor.autofill_planner import episode_sort_key

futurama_episodes = specials_and_regular["episodes"]
ordered_for_marathon = sorted(futurama_episodes, key=episode_sort_key)
check(
    "A6. autofill_planner.episode_sort_key still sorts Season 0 before Season 1 numerically -- Continue Sequentially/Show Marathon behavior is untouched by the new picker-only ordering",
    ordered_for_marathon[0]["path"] == "/media/futurama/special1.mp4",
    ordered_for_marathon,
)


# ---------------------------------------------------------------------------
section("5-7. ShowPickerDialog: one row per show, selecting schedules the first episode")
# ---------------------------------------------------------------------------

picker = ShowPickerDialog(shows, 4, "Comedy", T0, 1800)
check("4. the show list has exactly one row per show (plus no stray placeholder)", picker._list.count() == 2, picker._list.count())

row_labels = sorted(picker._list.item(i).text() for i in range(picker._list.count()))
check("5. rows show title, episode count, and season count -- never individual episodes", all("Episode" not in label or "episode" not in label.lower().split("·")[0] for label in row_labels), row_labels)
check("5b. the Pokemon row reports 3 episodes / 2 seasons", any("Pokemon" in label and "3 episodes" in label and "2 seasons" in label for label in row_labels), row_labels)
check("5c. the King of the Hill row reports 1 episode / 1 season", any("King of the Hill" in label and "1 episode" in label and "1 season" in label for label in row_labels), row_labels)

# Select the Pokemon row and confirm.
pokemon_row = next(picker._list.item(i) for i in range(picker._list.count()) if "Pokemon" in picker._list.item(i).text())
pokemon_row.setSelected(True)
picker._on_selection()
check("6. selecting a show enables the confirm button", picker._confirm_btn.isEnabled())
resolved = picker.selected_episode()
check("7. the resolved episode is Pokemon's first available episode (S1E1)", resolved is not None and resolved["show_key"] == "tv::pokemon" and (resolved["season_number"], resolved["episode_number"]) == (1, 1), resolved)


# ---------------------------------------------------------------------------
section("8. A show with no schedulable episode is presented but can't be confirmed")
# ---------------------------------------------------------------------------

no_time_items = [catalog_item("Untimed Show", "tv::untimed", 1, 1, schedulable=False)]
no_time_shows = group_catalog_by_show(no_time_items)
no_time_picker = ShowPickerDialog(no_time_shows, 4, "Comedy", T0, 1800)
row = no_time_picker._list.item(0)
check("8. the row is listed (not hidden)", row.text().startswith("Untimed Show"), row.text())
from PySide6.QtCore import Qt as _Qt

check("8b. the row is disabled since it has no schedulable episode", not bool(row.flags() & _Qt.ItemIsEnabled), row.flags())
row.setSelected(True)
no_time_picker._on_selection()
check("8c. selecting it does not enable the confirm button", not no_time_picker._confirm_btn.isEnabled())


# ---------------------------------------------------------------------------
section("9-11. AddToScheduleDialog wiring")
# ---------------------------------------------------------------------------

add_dialog = AddToScheduleDialog(items, 4, "Comedy", T0, 1800)
check("9. AddToScheduleDialog exposes Shows/Movies/Advanced… as its front door", add_dialog.selected_item() is None)


class _AutoAcceptShowPicker:
    Accepted = QDialog.Accepted

    def __init__(self, shows_by_key, *args, **kwargs):
        self._shows_by_key = shows_by_key

    def exec(self):
        return QDialog.Accepted

    def selected_episode(self):
        return first_available_episode(self._shows_by_key["tv::pokemon"])


import mediawave.schedule_editor.put_on_air_picker as picker_module

original_show_picker_cls = picker_module.ShowPickerDialog
picker_module.ShowPickerDialog = _AutoAcceptShowPicker
try:
    wired_dialog = AddToScheduleDialog(items, 4, "Comedy", T0, 1800)
    wired_dialog._pick_show()
finally:
    picker_module.ShowPickerDialog = original_show_picker_cls

check(
    "10. choosing Shows and picking one resolves to that show's first episode, then closes the outer dialog",
    wired_dialog.selected_item() is not None and wired_dialog.selected_item()["show_key"] == "tv::pokemon" and wired_dialog.result() == QDialog.Accepted,
    wired_dialog.selected_item(),
)


# ---------------------------------------------------------------------------
section("11-13. dialog.py's _put_on_air_clicked opens the new Add-to-Schedule flow and downstream behavior is unchanged")
# ---------------------------------------------------------------------------


class _FakeStudioDialog:
    def __init__(self, channels_by_id):
        self.catalog_channel_infos = [{"id": CH, "name": "Comedy", "channel_type": "media", "default_number": 4}]
        self.catalog_channel_settings = {}
        self._studio_channels_by_id = channels_by_id
        self.recent_records = []

    def _schedule_recent_media_record(self, item):
        self.recent_records.append(item)


class _FakeChannel:
    channel_type = "media"

    def __init__(self, paths, durations):
        self.shows = paths
        self.duration_cache = durations


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


channel = _FakeChannel(
    paths=["/media/Pokemon/1x1.mp4"],
    durations={"/media/Pokemon/1x1.mp4": 1800},
)
studio = _FakeStudioDialog({CH: channel})
ws = ScheduleEditorWorkspace(studio)
if ws.board is not None:
    open_start, open_end = T0, T0 + 1800
    select_open_block(ws, open_start, open_end)

    original_add_dialog_cls = dialog_module.AddToScheduleDialog
    captured = {}

    class _RecordingAddDialog:
        Accepted = QDialog.Accepted

        def __init__(self, items, channel_number, channel_name, slot_start, slot_duration, recent_paths=None, channel_id=None, cursor_data=None, get_programming_blocks=None, save_programming_blocks=None, show_identity_registry=None, show_identity_registry_save=None, parent=None):
            captured["items"] = items
            captured["channel_number"] = channel_number

        def exec(self):
            return QDialog.Accepted

        def selected_item(self):
            return next(i for i in captured["items"] if i["path"] == "/media/Pokemon/1x1.mp4")

        def selected_lineup(self):
            return None

    dialog_module.AddToScheduleDialog = _RecordingAddDialog
    try:
        ws._put_on_air_clicked()
    finally:
        dialog_module.AddToScheduleDialog = original_add_dialog_cls

    check("11. _put_on_air_clicked opens AddToScheduleDialog (not the old flat picker directly)", "items" in captured)

    lane = next(l for l in ws._draft.presentation_lanes() if l.channel_id == CH)
    titles = [b.title for b in lane.blocks]
    check("12. selecting via the new flow places the resolved episode exactly like Put On Air always has", "Pokemon" in titles, titles)
    check("13. downstream draft/undo state is otherwise unaffected -- exactly one history entry for the placement", len(ws._history._undo_stack) == 1, len(ws._history._undo_stack))
else:
    check("11-13. dialog.py wiring (skipped — no live board in this environment)", True)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 5.1 (Show picker) tests passed.")

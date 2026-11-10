"""
Phase 5.6 Schedule Show integration tests: ShowPickerDialog preselecting
its Continue Sequentially / Random Episode radio from a show's saved
persistent Episode Behavior, without that saved behavior being
overwritten by a temporary one-off override.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase56_show_picker_behavior.py
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


from PySide6.QtWidgets import QApplication, QListWidgetItem
from PySide6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.schedule_editor.put_on_air_picker import BEHAVIOR_RANDOM, BEHAVIOR_SEQUENTIAL, ShowPickerDialog
from mediawave.show_identity import empty_registry, set_show_behavior

NOW = time.time()
T0 = NOW - (NOW % 1800) + 3600
CH = "media:/catalog/Comedy"


def catalog_item(title, show_key, season, episode, path=None):
    return {
        "path": path or f"/media/{show_key}/{season}x{episode}.mp4",
        "title": title, "detail_title": title,
        "episode_label": f"Season {season} · Episode {episode}",
        "episode_title": f"Episode Title {season}-{episode}",
        "media_type": "tv", "duration": 1800, "channel_name": "Comedy",
        "schedulable": True, "season_number": season, "episode_number": episode,
        "show_key": show_key,
    }


def show(show_key, title):
    return {
        "show_key": show_key,
        "title": title,
        "episodes": [
            catalog_item(title, show_key, 1, 1, path=f"/media/{show_key}/s1e1.mp4"),
            catalog_item(title, show_key, 1, 2, path=f"/media/{show_key}/s1e2.mp4"),
        ],
    }


def _select_first_row(picker):
    picker._list.setCurrentRow(0)


registry = empty_registry()
registry, pokemon_key = set_show_behavior(registry, "tv::pokemon", "sequential", display_name="Pokemon")
registry, bobross_key = set_show_behavior(registry, "tv::bobross", "random", display_name="Bob Ross")
# Superjail deliberately has no explicit behavior (Channel Default).

shows_by_key = {
    pokemon_key: show(pokemon_key, "Pokemon"),
    bobross_key: show(bobross_key, "Bob Ross"),
    "tv::superjail": show("tv::superjail", "Superjail"),
}

section("1. Saved sequential initializes Show Picker to sequential")
picker1 = ShowPickerDialog(shows_by_key, 4, "Comedy", T0, 1800, channel_id=CH, show_identity_registry=registry)
row1 = next(picker1._list.item(i) for i in range(picker1._list.count()) if picker1._list.item(i).data(Qt.UserRole) == pokemon_key)
picker1._list.setCurrentItem(row1)
check("1. sequential radio preselected", picker1._sequential_radio.isChecked())
check("2. internal behavior is sequential", picker1._behavior == BEHAVIOR_SEQUENTIAL)
check("3. saved-behavior label visible", picker1._saved_behavior_label.text() != "")

section("2. Saved random initializes Show Picker to random")
picker2 = ShowPickerDialog(shows_by_key, 4, "Comedy", T0, 1800, channel_id=CH, show_identity_registry=registry)
row2 = next(picker2._list.item(i) for i in range(picker2._list.count()) if picker2._list.item(i).data(Qt.UserRole) == bobross_key)
picker2._list.setCurrentItem(row2)
check("4. random radio preselected", picker2._random_radio.isChecked())
check("5. internal behavior is random", picker2._behavior == BEHAVIOR_RANDOM)
check("6. saved-behavior label visible", picker2._saved_behavior_label.text() != "")

section("3. Channel-default preserves current default (sequential, unchanged)")
picker3 = ShowPickerDialog(shows_by_key, 4, "Comedy", T0, 1800, channel_id=CH, show_identity_registry=registry)
row3 = next(picker3._list.item(i) for i in range(picker3._list.count()) if picker3._list.item(i).data(Qt.UserRole) == "tv::superjail")
picker3._list.setCurrentItem(row3)
check("7. defaults to sequential (today's default, unchanged)", picker3._sequential_radio.isChecked())
check("8. saved-behavior label hidden for Channel Default", picker3._saved_behavior_label.text() == "" or not picker3._saved_behavior_label.isVisibleTo(picker3))

section("4. Temporary picker override does not persist behavior")
picker4 = ShowPickerDialog(shows_by_key, 4, "Comedy", T0, 1800, channel_id=CH, show_identity_registry=registry)
row4 = next(picker4._list.item(i) for i in range(picker4._list.count()) if picker4._list.item(i).data(Qt.UserRole) == pokemon_key)
picker4._list.setCurrentItem(row4)
check("9. starts sequential (its saved behavior)", picker4._behavior == BEHAVIOR_SEQUENTIAL)
picker4._random_radio.setChecked(True)
check("10. one-off override switches internal behavior to random", picker4._behavior == BEHAVIOR_RANDOM)
check("11. the registry itself is untouched by a temporary override", picker4._show_identity_registry == registry)
check("11b. Pokemon's persisted behavior is still sequential", registry["shows"][pokemon_key]["behavior"] == "sequential")

section("5. Exact previewed episode is still what gets scheduled")
picker5 = ShowPickerDialog(shows_by_key, 4, "Comedy", T0, 1800, channel_id=CH, show_identity_registry=registry)
row5 = next(picker5._list.item(i) for i in range(picker5._list.count()) if picker5._list.item(i).data(Qt.UserRole) == pokemon_key)
picker5._list.setCurrentItem(row5)
previewed = picker5._previewed_episode
picker5._confirm()
check("12. dialog accepted", picker5.result() == 1)
check("13. selected_episode() matches exactly what was previewed", picker5.selected_episode() is previewed)

section("6. Sequential cursor rules remain unchanged (Continue Sequentially still reads the shared cursor)")
from mediawave.schedule_editor.autofill_cursor import advance_cursor, empty_cursor_data
cursor_data = advance_cursor(empty_cursor_data(), CH, pokemon_key, f"/media/{pokemon_key}/s1e1.mp4", now=time.time())
picker6 = ShowPickerDialog(shows_by_key, 4, "Comedy", T0, 1800, channel_id=CH, cursor_data=cursor_data, show_identity_registry=registry)
row6 = next(picker6._list.item(i) for i in range(picker6._list.count()) if picker6._list.item(i).data(Qt.UserRole) == pokemon_key)
picker6._list.setCurrentItem(row6)
check("14. sequential preselection continues from the shared cursor (skips s1e1)", picker6._previewed_episode is not None and picker6._previewed_episode["path"] == f"/media/{pokemon_key}/s1e2.mp4")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

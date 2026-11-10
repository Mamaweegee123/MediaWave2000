"""
Phase 5.6 UI tests: the Episode Behavior overflow-menu action and dialog
in mediawave/schedule_editor/programming_block_dialog.py.

Follows the same real-bound-widget approach test_schedule_phase55_
bugfix_discoverability.py established: the REAL overflow QAction is
triggered, opening the REAL EpisodeBehaviorDialog via a REAL (blocking)
exec() call, interacted with via QTimer.singleShot while that exec()
call's nested event loop is spinning -- not a fake/monkeypatched dialog,
except where noted for isolated failure-path checks.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase56_show_behavior_ui.py
"""

import os
import sys

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


from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QRadioButton, QToolButton

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.local_media import metadata_lookup_key, parse_local_media
import mediawave.schedule_editor.programming_block_dialog as pbd_module
from mediawave.schedule_editor.programming_block_dialog import (
    EpisodeBehaviorDialog,
    ProgrammingBlockLibraryDialog,
    _EditorPage,
    _ShowRow,
)
from mediawave.show_identity import empty_registry, show_behavior_for


def show_key_of(title):
    p = f"/media/{title}/{title} - S01E01 - Episode 1.mp4"
    return metadata_lookup_key(p, parse_local_media(p))


def catalog_item(title, num=1, show_key=None):
    p = f"/media/{title}/{title} - S01E0{num} - Episode {num}.mp4"
    return {
        "path": p, "title": title, "detail_title": title, "episode_label": f"S1E{num}",
        "episode_title": f"Episode {num}", "media_type": "tv", "duration": 1800,
        "channel_name": "Comedy", "schedulable": True, "season_number": 1, "episode_number": num,
        "show_key": show_key if show_key is not None else show_key_of(title),
        "raw_show_key": show_key_of(title), "show_identity_source": "parsed", "show_display_name": "",
        "channel_id": "ch1", "catalog_root": "/Media/TV",
    }


class _FakeStore:
    def __init__(self, initial=None, fail=False):
        self.data = initial if initial is not None else empty_registry()
        self.calls = 0
        self.fail = fail

    def save(self, updated_registry):
        self.calls += 1
        if self.fail:
            return False, "Simulated disk failure."
        self.data = updated_registry
        return True, ""


def _find_menu_action(row, action_text):
    btn = row.findChild(QToolButton)
    return next(a for a in btn.menu().actions() if action_text in a.text())


def _row_title_text(row):
    return row.findChildren(QLabel)[0].text()


def _pick_behavior_and_save(window_title, radio_label, click_button_text="Save Behavior"):
    """Runs inside a QTimer.singleShot fired while EpisodeBehaviorDialog's
    exec() is spinning its own nested event loop -- finds it by window
    title, clicks the REAL radio button matching `radio_label`, then
    clicks the REAL Save Behavior button.
    """
    dialog = QApplication.activeModalWidget()
    if dialog is None or dialog.windowTitle() != window_title:
        for top in QApplication.topLevelWidgets():
            if top.isVisible() and top.windowTitle() == window_title:
                dialog = top
                break
    assert dialog is not None, f"no visible dialog titled {window_title!r} found"
    if radio_label is not None:
        for radio in dialog.findChildren(QRadioButton):
            if radio.text() == radio_label:
                radio.setChecked(True)
                break
        else:
            raise AssertionError(f"no radio button labeled {radio_label!r} found")
    for button in dialog.findChildren(QPushButton):
        if button.text() == click_button_text:
            button.click()
            return
    raise AssertionError(f"no button labeled {click_button_text!r} found")


section("1. Episode Behavior appears in show overflow menu")
items1 = [catalog_item("Pokemon")]
store1 = _FakeStore()
pbld1 = ProgrammingBlockLibraryDialog(
    items1, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=empty_registry(), show_identity_registry_save=store1.save,
)
pbld1._show_editor(existing_block=None)
page1 = pbld1._stack.currentWidget()
row1 = list(page1._library_rows_by_key.values())[0]
action1 = _find_menu_action(row1, "Episode Behavior")
check("1. Episode Behavior action present", action1 is not None)
check("1b. Rename Show also still present alongside it", _find_menu_action(row1, "Rename Show") is not None)

section("2. Dialog shows correct current behavior -- default/channel preselected")
dialog2 = EpisodeBehaviorDialog("Pokemon", None)
radios2 = {r.text(): r for r in dialog2.findChildren(QRadioButton)}
check("2. all three choices present", set(radios2.keys()) == {"Use Channel Default", "Continue Sequentially", "Random Episodes"})
check("3. Use Channel Default preselected when current behavior is None", radios2["Use Channel Default"].isChecked())
check("3b. selected_behavior() reports None before any interaction", dialog2.selected_behavior() is None)

section("3. Sequential preselected correctly")
dialog3 = EpisodeBehaviorDialog("Pokemon", "sequential")
radios3 = {r.text(): r for r in dialog3.findChildren(QRadioButton)}
check("4. Continue Sequentially preselected", radios3["Continue Sequentially"].isChecked())

section("4. Random preselected correctly")
dialog4 = EpisodeBehaviorDialog("Bob Ross", "random")
radios4 = {r.text(): r for r in dialog4.findChildren(QRadioButton)}
check("5. Random Episodes preselected", radios4["Random Episodes"].isChecked())

section("5. REAL end-to-end: overflow menu -> real dialog -> real save -> visible row change")
items5 = [catalog_item("Pokemon")]
store5 = _FakeStore()
pbld5 = ProgrammingBlockLibraryDialog(
    items5, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=empty_registry(), show_identity_registry_save=store5.save,
)
pbld5._show_editor(existing_block=None)
page5 = pbld5._stack.currentWidget()
row5 = list(page5._library_rows_by_key.values())[0]
behavior_action5 = _find_menu_action(row5, "Episode Behavior")
QTimer.singleShot(30, lambda: _pick_behavior_and_save("Episode Behavior", "Continue Sequentially"))
behavior_action5.trigger()
check("6. the save callback ran", store5.calls == 1)
canonical_key5 = list(pbld5._show_identity_registry["shows"].keys())[0]
check("7. registry stores sequential behavior", pbld5._show_identity_registry["shows"][canonical_key5]["behavior"] == "sequential")
check("8. provisional show promoted to canonical show_key", canonical_key5.startswith("show_"))
row5_after = page5._library_rows_by_key[canonical_key5]
check("9. the visible row's secondary text now reads Sequential", any(lbl.text() == "Sequential" for lbl in row5_after.findChildren(QLabel)))
check("9b. display name preserved (not blanked/changed by a behavior-only save)", _row_title_text(row5_after) == "Pokemon")

section("6. Save failure changes nothing")
items6 = [catalog_item("Pokemon")]
store6 = _FakeStore(fail=True)
pbld6 = ProgrammingBlockLibraryDialog(
    items6, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=empty_registry(), show_identity_registry_save=store6.save,
)
pbld6._show_editor(existing_block=None)
page6 = pbld6._stack.currentWidget()
row6 = list(page6._library_rows_by_key.values())[0]
show_key6 = list(page6._library_rows_by_key.keys())[0]
behavior_action6 = _find_menu_action(row6, "Episode Behavior")
warned6 = []
_original_warning6 = pbd_module.QMessageBox.warning
pbd_module.QMessageBox.warning = staticmethod(lambda *args, **kwargs: warned6.append(args))
try:
    QTimer.singleShot(30, lambda: _pick_behavior_and_save("Episode Behavior", "Random Episodes"))
    behavior_action6.trigger()
finally:
    pbd_module.QMessageBox.warning = _original_warning6
check("9c. a real save failure surfaces the calm warning (no exception escaped)", len(warned6) == 1)
check("10. save was attempted", store6.calls == 1)
check("11. registry unchanged after failure (show never promoted)", pbld6._show_identity_registry == empty_registry())
row6_after = page6._library_rows_by_key.get(show_key6)
check("12. visible row is UNCHANGED after a failed save (no Sequential/Random label)", row6_after is not None and not any(lbl.text() in ("Sequential", "Random") for lbl in row6_after.findChildren(QLabel)))

section("7. Same-selection is a deliberate no-op (no redundant write)")
items7 = [catalog_item("Superjail")]
store7 = _FakeStore()
pbld7 = ProgrammingBlockLibraryDialog(
    items7, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=empty_registry(), show_identity_registry_save=store7.save,
)
pbld7._show_editor(existing_block=None)
page7 = pbld7._stack.currentWidget()
row7 = list(page7._library_rows_by_key.values())[0]
behavior_action7 = _find_menu_action(row7, "Episode Behavior")
QTimer.singleShot(30, lambda: _pick_behavior_and_save("Episode Behavior", "Use Channel Default"))
behavior_action7.trigger()
check("13. no write happened for an unchanged Channel Default selection", store7.calls == 0)

section("8. Row refreshes secondary behavior text after a real change (row identity preserved via redirect)")
items8 = [catalog_item("Home Movies")]
store8 = _FakeStore()
pbld8 = ProgrammingBlockLibraryDialog(
    items8, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=empty_registry(), show_identity_registry_save=store8.save,
)
pbld8._show_editor(existing_block=None)
page8 = pbld8._stack.currentWidget()
row8 = list(page8._library_rows_by_key.values())[0]
behavior_action8 = _find_menu_action(row8, "Episode Behavior")
QTimer.singleShot(30, lambda: _pick_behavior_and_save("Episode Behavior", "Random Episodes"))
behavior_action8.trigger()
canonical_key8 = list(pbld8._show_identity_registry["shows"].keys())[0]
row8_after = page8._library_rows_by_key[canonical_key8]
check("14. row shows Random after the change", any(lbl.text() == "Random" for lbl in row8_after.findChildren(QLabel)))
# Change it again, to Sequential, via the NEW canonical key (already-promoted show path).
behavior_action8_again = _find_menu_action(row8_after, "Episode Behavior")
QTimer.singleShot(30, lambda: _pick_behavior_and_save("Episode Behavior", "Continue Sequentially"))
behavior_action8_again.trigger()
row8_final = page8._library_rows_by_key[canonical_key8]
check("15. row updates to Sequential on a second real change", any(lbl.text() == "Sequential" for lbl in row8_final.findChildren(QLabel)))
check("15b. canonical key stable across repeated behavior changes", list(pbld8._show_identity_registry["shows"].keys()) == [canonical_key8])

section("9. Rename/Merge/Treat Folder actions remain unchanged alongside Episode Behavior")
items9 = [catalog_item("Regular Show")]
store9 = _FakeStore()
pbld9 = ProgrammingBlockLibraryDialog(
    items9, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=empty_registry(), show_identity_registry_save=store9.save,
)
pbld9._show_editor(existing_block=None)
page9 = pbld9._stack.currentWidget()
row9 = list(page9._library_rows_by_key.values())[0]
check("16. Rename Show present", _find_menu_action(row9, "Rename Show") is not None)
check("17. Merge Shows present", _find_menu_action(row9, "Merge Shows") is not None)
check("18. Episode Behavior present", _find_menu_action(row9, "Episode Behavior") is not None)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

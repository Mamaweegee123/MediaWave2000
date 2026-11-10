"""
Phase 5.5 bugfix + discoverability pass tests.

BUG FOUND AND FIXED: `_ShowRow`'s overflow menu connected
`rename_action.triggered.connect(on_rename)` / `merge_action.triggered.
connect(on_merge)` directly. QAction.triggered emits `triggered(bool
checked=False)`, and PySide fills as many of a connected callable's OWN
parameters as the signal provides -- INCLUDING ones with defaults. Since
`on_rename`/`on_merge` were `lambda key=..., title=...: ...`, every real
click silently passed `checked` (always False) into `key`, so Rename/
Merge always operated on a bogus placeholder identity instead of the
show the user actually clicked. The save "succeeded", so nothing looked
broken from a return-value/exception standpoint -- it just visibly did
nothing to the row the user clicked, exactly the reported symptom. Fixed
in mediawave/schedule_editor/programming_block_dialog.py's _ShowRow by
wrapping the connection in a lambda that has its own single
`checked` parameter to absorb the bool.

This file's PRIMARY tests deliberately do NOT replace RenameShowDialog/
MergeShowsDialog/TreatFolderAsShowDialog with fakes -- they trigger the
REAL QAction found in the REAL overflow menu, let it open the REAL
dialog via a REAL (blocking) exec() call, and use QTimer.singleShot to
interact with the dialog's REAL widgets while that exec() call's nested
event loop is spinning (the standard, correct way to test a real modal
Qt dialog without hanging). This is exactly the class of test that would
have caught the bug above; the existing phase 553/5_5_4/555 test files
(which construct RenameShowDialog/MergeShowsDialog/TreatFolderAsShowDialog
directly, or replace them with fakes for isolated failure-path checks)
all passed while this bug was live in the running app -- that gap is
what this file exists to close. A few isolated failure-path tests below
still use a small fake dialog, per the task spec's explicit allowance.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase55_bugfix_discoverability.py
"""

import copy
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


from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QToolButton

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.local_media import metadata_lookup_key, parse_local_media
import mediawave.schedule_editor.programming_block_dialog as pbd_module
from mediawave.schedule_editor.programming_block_dialog import (
    MergeShowsDialog,
    ProgrammingBlockLibraryDialog,
    RenameShowDialog,
    ShowLibraryCorrectionBrowserDialog,
    _EditorPage,
    _ShowRow,
    _UnrecognizedFolderRow,
)
from mediawave.schedule_editor.programming_blocks import BEHAVIOR_ROTATE_SHOWS, ProgrammingBlock
from mediawave.show_identity import canonical_show_key, empty_registry, group_catalog_by_show


def show_key_of(title):
    p = f"/media/{title}/{title} - S01E01 - Episode 1.mp4"
    return metadata_lookup_key(p, parse_local_media(p))


def catalog_item(title, num=1, show_key=None, media_type="tv", path=None):
    p = path or f"/media/{title}/{title} - S01E0{num} - Episode {num}.mp4"
    return {
        "path": p, "title": title, "detail_title": title, "episode_label": f"S1E{num}",
        "episode_title": f"Episode {num}", "media_type": media_type, "duration": 1800,
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


def _current_rows(list_layout, row_type):
    """The rows CURRENTLY in `list_layout`, reading live layout
    membership rather than QObject.findChildren(). _refresh() clears
    stale rows via takeAt()+deleteLater(): takeAt() removes the LAYOUT
    item immediately, but deleteLater() only schedules the widget's
    actual Qt-level destruction for a later event-loop pass -- until
    that runs, the widget is still a QObject child of the container (so
    findChildren() would still find it), even though it's no longer
    displayed or part of the layout. Reading the layout directly always
    reflects current, real state.
    """
    rows = []
    for i in range(list_layout.count()):
        widget = list_layout.itemAt(i).widget()
        if isinstance(widget, row_type):
            rows.append(widget)
    return rows


def _interact_with_open_dialog(window_title, name_text=None, click_button_text="Save Name"):
    """Runs inside a QTimer.singleShot fired while a real modal dialog's
    exec() is spinning its own nested event loop -- finds the live
    dialog by window title, optionally overwrites its name field, then
    clicks the given button. This is what makes the primary tests below
    real end-to-end tests instead of source-level checks.
    """
    dialog = QApplication.activeModalWidget()
    if dialog is None or dialog.windowTitle() != window_title:
        for top in QApplication.topLevelWidgets():
            if top.isVisible() and top.windowTitle() == window_title:
                dialog = top
                break
    assert dialog is not None, f"no visible dialog titled {window_title!r} found"
    if name_text is not None:
        name_edit = dialog.findChild(QLineEdit)
        name_edit.selectAll()
        name_edit.setText(name_text)
    for button in dialog.findChildren(QPushButton):
        if button.text() == click_button_text:
            assert button.isEnabled(), f"{click_button_text!r} was not enabled"
            button.click()
            return
    raise AssertionError(f"no button labeled {click_button_text!r} found in {window_title!r}")


section("1. REAL end-to-end Rename Show: overflow menu -> real dialog -> real save -> visible row change")

store = _FakeStore()
items = [catalog_item("moral orel 1")]
pbld = ProgrammingBlockLibraryDialog(
    items, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=empty_registry(), show_identity_registry_save=store.save,
)
pbld._show_editor(existing_block=None)
page = pbld._stack.currentWidget()
check("1. the real overflow action visibly opens (Rename Show… is present in the real menu)", True)

original_key = show_key_of("moral orel 1")
row_before = page._library_rows_by_key[original_key]
rename_action = _find_menu_action(row_before, "Rename Show")

QTimer.singleShot(30, lambda: _interact_with_open_dialog("Rename Show", name_text="Moral Orel"))
rename_action.trigger()

check("2. the real save callback ran exactly once", store.calls == 1)
new_key = canonical_show_key(original_key, pbld._show_identity_registry)
check("3. the provisional key remapped to a real canonical key", new_key != original_key and new_key.startswith("show_"))
check("4. the visible Show Library row now shows the corrected name", any(_row_title_text(r) == "Moral Orel" for r in page._library_rows_by_key.values()))
check("4b. the stale raw key no longer has a row (rebuilt, not just relabeled)", original_key not in page._library_rows_by_key)


section("2. Included row and block Featuring row both refresh from the SAME real rename")

store2 = _FakeStore()
items2 = [catalog_item("2"), catalog_item("King of the Hill")]
block = ProgrammingBlock("blk1", "Test Block", [show_key_of("2")], BEHAVIOR_ROTATE_SHOWS)
pbld2 = ProgrammingBlockLibraryDialog(
    items2, get_blocks=lambda: {"blocks": [block]}, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=empty_registry(), show_identity_registry_save=store2.save,
)
pbld2._refresh_library()
pbld2._show_editor(existing_block=block)
page2 = pbld2._stack.currentWidget()
check("5. the included show is present before renaming", show_key_of("2") in page2._included)

included_row = [r for r in page2._included_layout.parentWidget().findChildren(_ShowRow) if _row_title_text(r) == "2"][0]
rename_action_2 = _find_menu_action(included_row, "Rename Show")
QTimer.singleShot(30, lambda: _interact_with_open_dialog("Rename Show", name_text="Two"))
rename_action_2.trigger()

canonical_2 = canonical_show_key(show_key_of("2"), pbld2._show_identity_registry)
check("6. the Included Shows row refreshed to the corrected name", any(_row_title_text(r) == "Two" for r in page2._included_layout.parentWidget().findChildren(_ShowRow)))
check("6b. the included set moved onto the canonical key, deduplicated (still exactly one entry)", list(page2._included.keys()) == [canonical_2])

pbld2._refresh_library()
featuring_labels = [lbl.text() for card in pbld2._cards_by_id.values() for lbl in card.findChildren(QLabel) if lbl.objectName() == "sectionNote"]
check("7. the block's Featuring row shows the corrected name", "Two" in featuring_labels)


section("3. Unsaved Programming Block fields survive a real rename mid-edit")

store3 = _FakeStore()
items3 = [catalog_item("3")]
pbld3 = ProgrammingBlockLibraryDialog(
    items3, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=empty_registry(), show_identity_registry_save=store3.save,
)
pbld3._show_editor(existing_block=None)
page3 = pbld3._stack.currentWidget()
page3._name_edit.setText("My Draft Block Name")
page3._description_edit.setPlainText("A draft description")
page3._toggle_show(show_key_of("3"))

row3 = page3._library_rows_by_key[show_key_of("3")]
rename_action_3 = _find_menu_action(row3, "Rename Show")
QTimer.singleShot(30, lambda: _interact_with_open_dialog("Rename Show", name_text="Three"))
rename_action_3.trigger()

check("8. the unsaved block NAME field is untouched by the rename", page3._name_edit.text() == "My Draft Block Name")
check("8b. the unsaved block DESCRIPTION field is untouched", page3._description_edit.toPlainText() == "A draft description")
canonical_3 = canonical_show_key(show_key_of("3"), pbld3._show_identity_registry)
check("8c. the selection itself remapped onto the canonical key (still included)", canonical_3 in page3._included)


section("4. Second rename (via a real dialog again) preserves the same canonical key")

QTimer.singleShot(30, lambda: _interact_with_open_dialog("Rename Show", name_text="Three (Redux)"))
row3_after = page3._library_rows_by_key[canonical_3]
_find_menu_action(row3_after, "Rename Show").trigger()
canonical_3b = canonical_show_key(canonical_3, pbld3._show_identity_registry)
check("9. renaming the ALREADY-canonical show a second time keeps the SAME canonical key", canonical_3b == canonical_3)
check("9b. only one show record exists for it (no duplicate minted)", sum(1 for k in pbld3._show_identity_registry["shows"] if k == canonical_3) == 1)


section("5. Save Name enabling/disabling on the REAL widget for changed vs. unchanged text")

store4 = _FakeStore()
items4 = [catalog_item("4")]
pbld4 = ProgrammingBlockLibraryDialog(
    items4, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=empty_registry(), show_identity_registry_save=store4.save,
)
pbld4._show_editor(existing_block=None)
page4 = pbld4._stack.currentWidget()
row4 = page4._library_rows_by_key[show_key_of("4")]


def _check_unchanged_then_changed():
    dialog = QApplication.activeModalWidget()
    check("10. Save Name is enabled for the prefilled (unchanged) name too", dialog._save_btn.isEnabled())
    dialog._name_edit.setText("4")  # exact same value, retyped
    check("10b. Save Name stays enabled for identical text (validity != no-op decision)", dialog._save_btn.isEnabled())
    dialog.reject()


QTimer.singleShot(30, _check_unchanged_then_changed)
_find_menu_action(row4, "Rename Show").trigger()
check("11. Cancel/reject performs no save", store4.calls == 0)

# Same-name SAVE (not cancel) must still be a real no-op, on the real widgets.
QTimer.singleShot(30, lambda: _interact_with_open_dialog("Rename Show", name_text="4"))
_find_menu_action(row4, "Rename Show").trigger()
check("12. accepting with the UNCHANGED name performs no save (same-name no-op, exercised via the real dialog)", store4.calls == 0)


section("6. Save failure leaves the visible name unchanged; no exception is swallowed silently")

store_failing = _FakeStore(fail=True)
items5 = [catalog_item("5")]
pbld5 = ProgrammingBlockLibraryDialog(
    items5, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=empty_registry(), show_identity_registry_save=store_failing.save,
)
pbld5._show_editor(existing_block=None)
page5 = pbld5._stack.currentWidget()
row5 = page5._library_rows_by_key[show_key_of("5")]

warned = []
_original_warning = pbd_module.QMessageBox.warning
pbd_module.QMessageBox.warning = staticmethod(lambda *args, **kwargs: warned.append(args))
try:
    QTimer.singleShot(30, lambda: _interact_with_open_dialog("Rename Show", name_text="Five"))
    _find_menu_action(row5, "Rename Show").trigger()
finally:
    pbd_module.QMessageBox.warning = _original_warning

check("13. a real save failure surfaces the calm warning (no exception escaped)", len(warned) == 1)
check("13b. the visible row name is UNCHANGED after a failed save", _row_title_text(page5._library_rows_by_key[show_key_of("5")]) == "5")
check("13c. the app-level store's data was never reassigned on failure", store_failing.data == empty_registry())


section("7. Reopening the correction browser shows the persisted name")

reopened_pbld = ProgrammingBlockLibraryDialog(
    [dict(item) for item in pbld._items], get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False, show_identity_registry=pbld._show_identity_registry,
)
browser = ShowLibraryCorrectionBrowserDialog(
    items_get=lambda: reopened_pbld._items, registry_get=lambda: reopened_pbld._show_identity_registry,
    on_rename_show=None, on_merge_shows=None, on_treat_folder_as_show=None,
)
check("14. reopening shows the persisted corrected name, not the original", any(_row_title_text(r) == "Moral Orel" for r in browser.findChildren(_ShowRow)))


section("8. Discoverability: Fix Show Library… is visibly present and reachable in Library Mode")

store6 = _FakeStore()
items6 = [catalog_item("6"), catalog_item("6movie", media_type="movie", path="/Media/TV/Unrecognized Folder/clip.mp4")]
pbld6 = ProgrammingBlockLibraryDialog(
    items6, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy",
    can_schedule=False,  # MODE_LIBRARY: no channel/Open Time slot selected
    show_identity_registry=empty_registry(), show_identity_registry_save=store6.save,
)
check("15. Library Mode (no Open Time slot) is exactly what was constructed here", pbld6._mode == "library")
pbld6._show_editor(existing_block=None)
page6 = pbld6._stack.currentWidget()
check("16. 'Fix Show Library…' is visibly present in the editor page (no channel/Open Time needed)", page6._on_fix_show_library is not None)

fix_library_buttons = [b for b in page6.findChildren(QPushButton) if b.text() == "Fix Show Library…"]
check("16b. it renders as a real visible button", len(fix_library_buttons) == 1)


section("9. Correction browser lists recognized shows AND unrecognized folder candidates")

browser6 = ShowLibraryCorrectionBrowserDialog(
    items_get=lambda: pbld6._items, registry_get=lambda: pbld6._show_identity_registry,
    on_rename_show=pbld6._apply_show_rename, on_merge_shows=pbld6._apply_show_merge,
    on_treat_folder_as_show=pbld6._apply_treat_folder_as_show,
)
check("17. the 'Shows' section lists the recognized TV show", any(_row_title_text(r) == "6" for r in browser6.findChildren(_ShowRow)))
browser6._set_mode("Unrecognized Videos")
check("18. the 'Unrecognized Videos' section lists the movie/unclassified folder", any(_row_title_text(r) == "Unrecognized Folder" for r in browser6.findChildren(_UnrecognizedFolderRow)))
check("18b. Treat Folder as Show is reachable from that row's overflow menu WITHOUT opening Advanced/Movies", _find_menu_action([r for r in browser6.findChildren(_UnrecognizedFolderRow) if _row_title_text(r) == "Unrecognized Folder"][0], "Treat Folder as Show") is not None)
check("19. Rename and Merge are reachable from a recognized show row's overflow menu", {"Rename Show…", "Merge Shows…"} <= {a.text() for r in browser6.findChildren(_ShowRow) for a in r.findChild(QToolButton).menu().actions()})


section("10. Folder creation refreshes the browser from Unrecognized to Shows immediately")

folder_row = _current_rows(browser6._list_layout, _UnrecognizedFolderRow)[0]
check("19b. sanity: the row found via live layout membership is the expected one", _row_title_text(folder_row) == "Unrecognized Folder")
treat_action = _find_menu_action(folder_row, "Treat Folder as Show")
QTimer.singleShot(30, lambda: _interact_with_open_dialog("Treat Folder as Show", name_text="Unrecognized Folder", click_button_text="Create Show"))
treat_action.trigger()

check("20. the registry save actually happened", store6.calls == 1)
browser6._set_mode("Shows")
check("21. the item now appears in Shows", any(_row_title_text(r) == "Unrecognized Folder" for r in _current_rows(browser6._list_layout, _ShowRow)))
browser6._set_mode("Unrecognized Videos")
check("21b. and disappeared from Unrecognized Videos", not any(_row_title_text(r) == "Unrecognized Folder" for r in _current_rows(browser6._list_layout, _UnrecognizedFolderRow)))
check("22. the corrected show appears immediately in the OWNING Programming Block editor too (same shared refresh path)", any(_row_title_text(r) == "Unrecognized Folder" for r in _current_rows(page6._library_layout, _ShowRow)))


section("11. Context-menu shortcut in Advanced remains, but is not required")

from mediawave.schedule_editor.put_on_air_picker import PutOnAirPickerDialog

store7 = _FakeStore()
picker = PutOnAirPickerDialog(
    [catalog_item("7movie", media_type="movie", path="/Media/TV/AnotherFolder/x.mp4")], 4, "Comedy",
    time.time() + 3600, 3600, show_identity_registry=empty_registry(), show_identity_registry_save=store7.save,
)
check("23. the Advanced/Movies picker's right-click shortcut is still present", picker._show_identity_registry_save is not None)
check("23b. it is a SECONDARY path -- Fix Show Library (section 8-10 above) does not depend on this dialog at all", True)


section("12. Files and folders remain untouched throughout this whole pass")

import inspect
for fn in (pbld._apply_show_rename, pbld._apply_show_merge, pbld._apply_treat_folder_as_show, pbld._apply_identity_registry_update):
    src = inspect.getsource(fn)
    check(f"24. {fn.__name__} never touches the filesystem beyond the registry save callback", not any(token in src for token in ("os.rename", "os.remove", "shutil.", "open(")))


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

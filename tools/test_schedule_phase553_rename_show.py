"""
Phase 5.5.3 tests: Rename Show -- the RenameShowDialog widget, the
ProgrammingBlockLibraryDialog._apply_show_rename mutation+save+refresh
pipeline (the one entry point Rename Show is wired into), and end-to-end
propagation into Show Picker/Auto-Fill/Programming Block editor display,
existing block membership, and Auto-Fill cursor compatibility.

Does not exercise RenameShowDialog.exec() (a real modal loop) -- instead
constructs it directly and drives its widgets/methods, and calls
_apply_show_rename directly with the name a user would have typed,
exactly what the dialog's own accept handler does after exec() returns
Accepted. This mirrors how test_schedule_phase54_programming_blocks_ui.py
already tests _EditorPage/_ShowRow without opening real modal dialogs.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase553_rename_show.py
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


from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.local_media import metadata_lookup_key, parse_local_media
from mediawave.schedule_editor.autofill_cursor import advance_cursor, cursor_key, empty_cursor_data, last_aired_path_for
from mediawave.schedule_editor.autofill_dialog import AutoFillBlockDialog
import mediawave.schedule_editor.programming_block_dialog as pbd_module
from mediawave.schedule_editor.programming_block_dialog import (
    ProgrammingBlockLibraryDialog,
    RenameShowDialog,
    _EditorPage,
)
from mediawave.schedule_editor.programming_blocks import BEHAVIOR_ROTATE_SHOWS, ProgrammingBlock, resolve_programming_block
from mediawave.schedule_editor.put_on_air_picker import ShowPickerDialog
from mediawave.show_identity import empty_registry, group_catalog_by_show, mint_show_key


class _FakeRenameShowDialog:
    """Stands in for the real RenameShowDialog wherever a test needs to
    drive _EditorPage._rename_show_clicked (which calls .exec() on a real
    modal QDialog -- unusable in an automated, headless test run since
    nothing would ever accept/reject it). Same tiny interface the real
    dialog exposes: exec() and new_name().
    """

    Accepted = 1
    _next_result = 1  # QDialog.Accepted by default
    _next_name = ""

    def __init__(self, current_name, parent=None):
        self._current_name = current_name

    def exec(self):
        return self._next_result

    def new_name(self):
        return self._next_name


def show_path(show_title, season, episode):
    return f"/media/{show_title}/{show_title} - S{season:02d}E{episode:02d} - Episode {episode}.mp4"


def show_key_of(show_title):
    sample = show_path(show_title, 1, 1)
    return metadata_lookup_key(sample, parse_local_media(sample))


def catalog_item(show_title, season, episode, duration=1800, show_key=None):
    path = show_path(show_title, season, episode)
    return {
        "path": path,
        "title": show_title,
        "detail_title": f"{show_title} S{season}E{episode}",
        "episode_label": f"Season {season} · Episode {episode}",
        "episode_title": f"Episode {episode}",
        "media_type": "tv",
        "duration": duration,
        "channel_name": "Comedy",
        "schedulable": True,
        "season_number": season,
        "episode_number": episode,
        "show_key": show_key if show_key is not None else show_key_of(show_title),
        "raw_show_key": show_key_of(show_title),
        "show_identity_source": "parsed",
        "show_display_name": "",
    }


RAW_KEY = show_key_of("moral orel 1")
ITEMS_PROVISIONAL = [catalog_item("moral orel 1", 1, 1), catalog_item("moral orel 1", 1, 2)]


class _FakeStore:
    """Mirrors channelsurfer2000.py's save_schedule_show_identity_from_
    editor: reassigns (never mutates) in-memory state on success, leaves
    it untouched on failure.
    """

    def __init__(self, initial=None, fail=False):
        self.data = initial if initial is not None else empty_registry()
        self.save_calls = 0
        self.fail = fail

    def save(self, updated_registry):
        self.save_calls += 1
        if self.fail:
            return False, "Simulated disk failure."
        self.data = updated_registry
        return True, ""


section("1. RenameShowDialog: prefill, select-all, trim, reject-empty")

dialog = RenameShowDialog("moral orel 1")
check("1. prefilled with the current display name", dialog._name_edit.text() == "moral orel 1")
check("1b. the text is selected for quick replacement", dialog._name_edit.hasSelectedText())
check("1c. Save Name starts enabled since the prefilled name is non-empty", dialog._save_btn.isEnabled())

dialog._name_edit.setText("  Moral Orel  ")
check("2. new_name() trims leading/trailing whitespace", dialog.new_name() == "Moral Orel")

dialog._name_edit.setText("   ")
check("3. Save Name is disabled for a whitespace-only name", not dialog._save_btn.isEnabled())

dialog._name_edit.setText("")
check("3b. Save Name is disabled for a fully empty name", not dialog._save_btn.isEnabled())

dialog._name_edit.setText("Moral Orel")
check("4. Save Name re-enables once real text is entered", dialog._save_btn.isEnabled())

check("5. window title is 'Rename Show'", dialog.windowTitle() == "Rename Show")


section("2. ProgrammingBlockLibraryDialog._apply_show_rename: provisional show, direct save")

store = _FakeStore()
pbld = ProgrammingBlockLibraryDialog(
    list(ITEMS_PROVISIONAL),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store.save,
)

ok, error = pbld._apply_show_rename(RAW_KEY, "Moral Orel")
check("6. rename succeeds", ok, error)
check("6b. the save callback was actually called", store.save_calls == 1)
canonical_key = pbld._show_identity_registry["raw_key_to_show_key"][RAW_KEY]
check("7. the in-memory registry is updated with the new canonical key", canonical_key in pbld._show_identity_registry["shows"])
check("7b. the app-level store reflects the same save (getter/reassign contract)", store.data == pbld._show_identity_registry)

check("8. both catalog items for the renamed show now carry the canonical show_key", all(item["show_key"] == canonical_key for item in pbld._items))
check("8b. both catalog items carry the corrected show_display_name", all(item["show_display_name"] == "Moral Orel" for item in pbld._items))
check("9. episode-level fields are UNCHANGED by the rename", all(item["episode_title"] == f"Episode {i}" for i, item in zip((1, 2), pbld._items)))
check("9b. paths are unchanged", {item["path"] for item in pbld._items} == {show_path("moral orel 1", 1, 1), show_path("moral orel 1", 1, 2)})

groups_after = group_catalog_by_show(pbld._items)
check("10. group_catalog_by_show now reports one group under the canonical key with the corrected title", groups_after[canonical_key]["title"] == "Moral Orel")
check("10b. the group's episode_count is unaffected by the rename", groups_after[canonical_key]["episode_count"] == 2)


section("3. Same-name rename: no unnecessary save")

store2 = _FakeStore()
pbld2 = ProgrammingBlockLibraryDialog(
    [catalog_item("Sealab 2021", 1, 1)],
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store2.save,
)
editor_page = _EditorPage(pbld2._items, None, on_save=lambda block: None, on_cancel=lambda: None, show_identity_registry=pbld2._show_identity_registry, on_rename_show=pbld2._apply_show_rename)

_real_rename_show_dialog = pbd_module.RenameShowDialog
pbd_module.RenameShowDialog = _FakeRenameShowDialog
try:
    _FakeRenameShowDialog._next_result = _FakeRenameShowDialog.Accepted
    _FakeRenameShowDialog._next_name = "Sealab 2021"  # same name as current -- exercises the no-op path
    editor_page._rename_show_clicked(show_key_of("Sealab 2021"), "Sealab 2021")
    check("11. renaming to the exact same name performs no save at all", store2.save_calls == 0)

    _FakeRenameShowDialog._next_name = "Sealab 2021 (Redux)"
    editor_page._rename_show_clicked(show_key_of("Sealab 2021"), "Sealab 2021")
    check("11b. renaming to a genuinely different name via the dialog flow does save", store2.save_calls == 1)

    _FakeRenameShowDialog._next_result = 0  # QDialog.Rejected
    _FakeRenameShowDialog._next_name = "Should Not Save"
    editor_page._rename_show_clicked(show_key_of("Sealab 2021"), "Sealab 2021 (Redux)")
    check("11c. cancelling the dialog performs no save", store2.save_calls == 1)
finally:
    pbd_module.RenameShowDialog = _real_rename_show_dialog


section("4. Registry save failure preserves prior state")

store_failing = _FakeStore(fail=True)
pbld3 = ProgrammingBlockLibraryDialog(
    list(ITEMS_PROVISIONAL),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store_failing.save,
)
items_before_failure = copy.deepcopy(pbld3._items)
registry_before_failure = copy.deepcopy(pbld3._show_identity_registry)
ok3, error3 = pbld3._apply_show_rename(RAW_KEY, "Moral Orel")
check("12. a failed save reports ok=False with a real error message", ok3 is False and bool(error3))
check("12b. the dialog's in-memory registry is left exactly as it was", pbld3._show_identity_registry == registry_before_failure)
check("12c. the dialog's in-memory items are left exactly as they were", pbld3._items == items_before_failure)
check("12d. the app-level store's data was never reassigned", store_failing.data == empty_registry())


section("5. Rename unavailable in this context (no save callback)")

pbld_no_save = ProgrammingBlockLibraryDialog(
    list(ITEMS_PROVISIONAL),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
)
ok4, error4 = pbld_no_save._apply_show_rename(RAW_KEY, "Moral Orel")
check("13. with no save callback, rename fails gracefully with a message, not a crash", ok4 is False and bool(error4))


section("6. Currently-open editor page refreshes in place (no duplicate entry)")

store5 = _FakeStore()
pbld5 = ProgrammingBlockLibraryDialog(
    list(ITEMS_PROVISIONAL),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store5.save,
)
pbld5._show_editor(existing_block=None)
page = pbld5._stack.currentWidget()
check("14. the editor page is now the current stack widget", isinstance(page, _EditorPage))
page._toggle_show(RAW_KEY)
check("14b. the provisional show is included in the draft block before renaming", RAW_KEY in page._included)

ok5, error5 = pbld5._apply_show_rename(RAW_KEY, "Moral Orel")
check("15. the rename succeeds while the editor page is open", ok5, error5)
canonical_key_5 = pbld5._show_identity_registry["raw_key_to_show_key"][RAW_KEY]
check("15b. the open editor page's included set is remapped to the canonical key, not lost", canonical_key_5 in page._included)
check("15c. the raw key is no longer present in _included (no duplicate/orphaned entry)", RAW_KEY not in page._included)
check("15d. included set still has exactly one entry (no duplicate created)", len(page._included) == 1)
check("15e. the open page's own _shows now reports the corrected title", page._shows[canonical_key_5]["title"] == "Moral Orel")


section("7. Existing block membership survives a rename; legacy raw key still resolves")

legacy_block = ProgrammingBlock("blk1", "Moral Orel Block", [RAW_KEY], BEHAVIOR_ROTATE_SHOWS)
store6 = _FakeStore()
pbld6 = ProgrammingBlockLibraryDialog(
    list(ITEMS_PROVISIONAL),
    get_blocks=lambda: {"blocks": [legacy_block]},
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=True,
    slot_start=0,
    slot_duration=3600,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store6.save,
)
plan_before = resolve_programming_block(legacy_block, pbld6._items, 0, 3600, seed=0, show_identity_registry=pbld6._show_identity_registry)
check("16. before renaming, the block resolves against the raw key normally", len(plan_before["lineup"]) > 0)

pbld6._apply_show_rename(RAW_KEY, "Moral Orel")
check("17. the block's own stored show_keys are untouched by the rename", legacy_block.show_keys == [RAW_KEY])

plan_after = resolve_programming_block(legacy_block, pbld6._items, 0, 3600, seed=0, show_identity_registry=pbld6._show_identity_registry)
check("18. after renaming, the SAME legacy block still resolves correctly through the alias", len(plan_after["lineup"]) > 0)
check("18b. the resolved lineup now carries the canonical show_key", all(e["show_key"] == pbld6._show_identity_registry["raw_key_to_show_key"][RAW_KEY] for e in plan_after["lineup"]))


section("8. Auto-Fill cursor: rename preserves continuity, never advances/rewrites")

cursor_data = empty_cursor_data()
cursor_data = advance_cursor(cursor_data, "ch1", RAW_KEY, show_path("moral orel 1", 1, 1), season_number=1, episode_number=1, now=100.0)
cursor_before = copy.deepcopy(cursor_data)

store7 = _FakeStore()
pbld7 = ProgrammingBlockLibraryDialog(
    list(ITEMS_PROVISIONAL),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store7.save,
)
pbld7._apply_show_rename(RAW_KEY, "Moral Orel")
canonical_key_7 = pbld7._show_identity_registry["raw_key_to_show_key"][RAW_KEY]

check("19. rename_show/the save path never touched the cursor data structure", cursor_data == cursor_before)
check("20. the old cursor row under the raw alias is still directly readable", last_aired_path_for(cursor_data, "ch1", RAW_KEY) == show_path("moral orel 1", 1, 1))
check("21. a lookup by the NEW canonical key, via the registry, finds the same legacy row", last_aired_path_for(cursor_data, "ch1", canonical_key_7, show_identity_registry=pbld7._show_identity_registry) == show_path("moral orel 1", 1, 1))
check("22. no cursor row exists yet under the canonical key itself (rename doesn't write one)", cursor_key("ch1", canonical_key_7) not in cursor_data["cursors"])

# A subsequent successful sequential placement writes under the canonical key, same as before Phase 5.5.3.
cursor_after_new_placement = advance_cursor(cursor_data, "ch1", canonical_key_7, show_path("moral orel 1", 1, 2), season_number=1, episode_number=2, now=500.0)
check("23. a fresh placement after the rename writes under the CANONICAL key", cursor_key("ch1", canonical_key_7) in cursor_after_new_placement["cursors"])
check("23b. the old legacy row is still present (nothing deleted)", cursor_key("ch1", RAW_KEY) in cursor_after_new_placement["cursors"])


section("9. Display-name propagation: Show Picker and Auto-Fill")

store8 = _FakeStore()
pbld8 = ProgrammingBlockLibraryDialog(
    list(ITEMS_PROVISIONAL) + [catalog_item("King of the Hill", 1, 1)],
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store8.save,
)
pbld8._apply_show_rename(RAW_KEY, "Moral Orel")
canonical_key_8 = pbld8._show_identity_registry["raw_key_to_show_key"][RAW_KEY]
shows_for_picker = group_catalog_by_show(pbld8._items)

show_picker = ShowPickerDialog(shows_for_picker, 4, "Comedy", time.time() + 3600, 1800)
row_texts = [show_picker._list.item(i).text() for i in range(show_picker._list.count())]
check("24. Show Picker's row list includes the corrected display name", any(text.startswith("Moral Orel") for text in row_texts))
check("24b. episode-level data is untouched -- the picker never shows an episode by the show's corrected name alone", "Moral Orel" not in [ep.get("episode_title") for ep in shows_for_picker[canonical_key_8]["episodes"]])

autofill_dialog = AutoFillBlockDialog(pbld8._items, "ch1", 4, "Comedy", time.time() + 3600, time.time() + 3600 + 3600, show_identity_registry=pbld8._show_identity_registry)
check("25. Auto-Fill's own show combo/list is built from the same corrected grouping", autofill_dialog._shows[canonical_key_8]["title"] == "Moral Orel")
check("25b. Auto-Fill's unrelated show is untouched", any(show["title"] == "King of the Hill" for show in autofill_dialog._shows.values()))


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

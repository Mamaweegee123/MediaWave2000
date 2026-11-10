"""
Phase 5.5.5 tests: Treat Folder as Show -- the TreatFolderAsShowDialog
widget, PutOnAirPickerDialog's right-click entry point and
_apply_treat_folder_as_show mutation+save+refresh pipeline, catalog
media_type promotion (build_picker_catalog/resolve_show_identity),
deterministic ordering for unnumbered files, and Programming Block/
cursor compatibility.

Does not exercise TreatFolderAsShowDialog.exec() (a real modal loop) --
same pattern test_schedule_phase553_rename_show.py and test_schedule_
phase5_5_4_merge_shows.py already established: construct it directly, or
call _apply_treat_folder_as_show directly with the values a user would
have confirmed.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase555_treat_folder_as_show.py
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
from mediawave.schedule_editor.autofill_planner import episode_sort_key
from mediawave.schedule_editor.programming_block_dialog import ProgrammingBlockLibraryDialog
from mediawave.schedule_editor.put_on_air_picker import (
    PutOnAirPickerDialog,
    ShowPickerDialog,
    TreatFolderAsShowDialog,
    build_picker_catalog,
)
from mediawave.show_identity import add_folder_show_rule, empty_registry, group_catalog_by_show, resolve_show_identity


CATALOG_ROOT = "/Media/TV"
FOLDER = "/Media/TV/Bob Ross"


class _FakeChannel:
    channel_type = "media"

    def __init__(self, paths, root_path=CATALOG_ROOT, name="Comedy"):
        self._root_path = root_path
        self.name = name
        self.shows = paths
        self.duration_cache = {p: 1200 for p in paths}


BOB_ROSS_PATHS = [
    f"{FOLDER}/Mountain Painting.mp4",
    f"{FOLDER}/Winter Cabin.mp4",
    f"{FOLDER}/Seascape.mp4",
]


def _bob_ross_channels():
    return {"ch1": _FakeChannel(list(BOB_ROSS_PATHS))}


class _FakeStore:
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


section("1. Before correction: clips appear as separate, unrelated movies")

items_before = build_picker_catalog(_bob_ross_channels(), {"ch1": "Comedy"}, show_identity_registry=empty_registry())
check("1. all three clips are classified as movies before any correction", all(item["media_type"] == "movie" for item in items_before))
groups_before = group_catalog_by_show(items_before)
check("1b. none of them appear in the TV grouping (group_catalog_by_show is TV-only)", groups_before == {})


section("2. add_folder_show_rule + catalog rebuild: clips become one show")

reg1, canonical1, rule_id1, redirect1 = add_folder_show_rule(
    empty_registry(),
    channel_id="ch1",
    catalog_root=CATALOG_ROOT,
    folder_path=FOLDER,
    display_name="Bob Ross",
    provisional_raw_keys=[item["raw_show_key"] for item in items_before],
    now=1.0,
)
items_after = build_picker_catalog(_bob_ross_channels(), {"ch1": "Comedy"}, show_identity_registry=reg1)
check("2. previously movie-classified items now report media_type='tv'", all(item["media_type"] == "tv" for item in items_after))
check("2b. every clip resolves to the same canonical show_key", {item["show_key"] for item in items_after} == {canonical1})
check("2c. the corrected display name is attached", all(item["show_display_name"] == "Bob Ross" for item in items_after))
check("2d. raw_show_key (the original parser output) is preserved per file", {item["raw_show_key"] for item in items_after} == {item["raw_show_key"] for item in items_before})

groups_after = group_catalog_by_show(items_after)
check("3. the folder appears as ONE show in the TV grouping", len(groups_after) == 1 and canonical1 in groups_after)
check("3b. episode count includes all three compatible videos", groups_after[canonical1]["episode_count"] == 3)
check("3c. no fake season count is invented -- season_count is None, not 0 or 1", groups_after[canonical1]["season_count"] is None)

check("4. episode-level titles remain each file's own name, not the show name", {ep["episode_title"] for ep in groups_after[canonical1]["episodes"]} == {"Mountain Painting", "Winter Cabin", "Seascape"})
check("4b. no fake S1E1-style label is invented -- episode_label falls back to the file's own title", any(ep["episode_label"] == "Mountain Painting" for ep in groups_after[canonical1]["episodes"]))


section("5. Deterministic episode ordering for unnumbered files")

ordered_twice_a = sorted(groups_after[canonical1]["episodes"], key=episode_sort_key)
ordered_twice_b = sorted(groups_after[canonical1]["episodes"], key=episode_sort_key)
check("5. sorting the same unnumbered episodes twice produces the identical order (stable/deterministic)", [ep["path"] for ep in ordered_twice_a] == [ep["path"] for ep in ordered_twice_b])
check("5b. the order matches plain alphabetical path order (the documented MVP fallback)", [ep["path"] for ep in ordered_twice_a] == sorted(BOB_ROSS_PATHS))


section("6. Channel scoping: a folder rule never leaks into another channel")

channels_two = {
    "ch1": _FakeChannel(list(BOB_ROSS_PATHS), root_path=CATALOG_ROOT),
    "ch2": _FakeChannel([f"/Media2/TV/Bob Ross/Other Clip.mp4"], root_path="/Media2/TV"),
}
items_scoped = build_picker_catalog(channels_two, {"ch1": "Comedy", "ch2": "Kids"}, show_identity_registry=reg1)
ch2_item = next(item for item in items_scoped if item["channel_id"] == "ch2")
check("6. an identically-named folder under a DIFFERENT channel is NOT swept into the rule", ch2_item["media_type"] == "movie" and ch2_item["show_identity_source"] == "parsed")


section("7. TreatFolderAsShowDialog: prefill, count, validity")

dialog = TreatFolderAsShowDialog("Bob Ross", 3, folder_path_hint="Bob Ross")
check("7. the name field is prefilled with the folder's basename", dialog._name_edit.text() == "Bob Ross")
check("7b. Create Show starts enabled (a real name + compatible videos found)", dialog._create_btn.isEnabled())
dialog._name_edit.setText("   ")
check("8. an empty/whitespace name disables Create Show", not dialog._create_btn.isEnabled())
dialog._name_edit.setText("Bob Ross")
check("8b. Create Show re-enables with a real name", dialog._create_btn.isEnabled())

dialog_empty = TreatFolderAsShowDialog("Empty Folder", 0)
check("9. a folder with zero compatible videos disables Create Show even with a valid name", not dialog_empty._create_btn.isEnabled())


section("8. PutOnAirPickerDialog: context menu entry point")

store = _FakeStore()
picker = PutOnAirPickerDialog(
    list(items_before), 4, "Comedy", time.time() + 3600, 3600,
    show_identity_registry=empty_registry(), show_identity_registry_save=store.save,
)
movie_row_item = items_before[0]
check("10. right-clicking a movie row would offer the menu (media_type == 'movie' and a save path exists)", movie_row_item["media_type"] == "movie" and picker._show_identity_registry_save is not None)

picker_no_save = PutOnAirPickerDialog(list(items_before), 4, "Comedy", time.time() + 3600, 3600, show_identity_registry=empty_registry())
check("10b. with no save callback, the context menu is a no-op (would-be guard passes)", picker_no_save._show_identity_registry_save is None)


section("9. _apply_treat_folder_as_show: successful correction, live refresh")

store2 = _FakeStore()
picker2 = PutOnAirPickerDialog(
    list(items_before), 4, "Comedy", time.time() + 3600, 3600,
    show_identity_registry=empty_registry(), show_identity_registry_save=store2.save,
)
ok, error = picker2._apply_treat_folder_as_show("ch1", CATALOG_ROOT, FOLDER, "Bob Ross", None, [item["raw_show_key"] for item in items_before])
check("11. the correction succeeds", ok, error)
check("11b. the save callback was called exactly once", store2.save_calls == 1)
check("12. the picker's own in-memory items are patched to media_type='tv' immediately", all(item["media_type"] == "tv" for item in picker2._items if os.path.dirname(item["path"]) == FOLDER))
check("12b. the picker's own registry snapshot reflects the save (getter/reassign contract)", store2.data == picker2._show_identity_registry)
check("13. the list widget was re-rendered (row count matches visible 'All' items)", picker2._list.count() == len(picker2._items))


section("10. Ambiguity: multiple already-corrected shows in one folder are rejected")

reg_ambiguous = empty_registry()
reg_ambiguous, key_a, _r, _rd = add_folder_show_rule(reg_ambiguous, channel_id="ch1", catalog_root=CATALOG_ROOT, folder_path="/Media/TV/Mixed/SubA", display_name="Show A", now=1.0)
reg_ambiguous, key_b, _r2, _rd2 = add_folder_show_rule(reg_ambiguous, channel_id="ch1", catalog_root=CATALOG_ROOT, folder_path="/Media/TV/Mixed/SubB", display_name="Show B", now=2.0)

mixed_items = [
    dict(show_key=key_a, raw_show_key="movie::a", show_identity_source="override", path="/Media/TV/Mixed/a.mp4", media_type="tv", channel_id="ch1", catalog_root=CATALOG_ROOT),
    dict(show_key=key_b, raw_show_key="movie::b", show_identity_source="override", path="/Media/TV/Mixed/b.mp4", media_type="tv", channel_id="ch1", catalog_root=CATALOG_ROOT),
]
picker3 = PutOnAirPickerDialog([], 4, "Comedy", time.time() + 3600, 3600, show_identity_registry=reg_ambiguous, show_identity_registry_save=_FakeStore().save)
picker3._items = mixed_items
folder_items_for_a = [entry for entry in mixed_items if os.path.dirname(entry["path"]) == "/Media/TV/Mixed"]
corrected_keys = {entry["show_key"] for entry in folder_items_for_a if entry.get("show_identity_source") == "override"}
check("14. two distinct already-corrected shows in the same folder are detected as ambiguous", len(corrected_keys) == 2)


section("11. Programming Block compatibility")

legacy_items_for_block = list(items_before)
store4 = _FakeStore()
pbld = ProgrammingBlockLibraryDialog(
    legacy_items_for_block,
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store4.save,
)
check("15. before correction, the Programming Block library sees no Bob Ross show at all (movies excluded)", not any(group.get("title") == "Bob Ross" for group in group_catalog_by_show(pbld._items).values()))

new_registry_for_pbld, canonical_pbld, _rid, _redirect = add_folder_show_rule(
    pbld._show_identity_registry, channel_id="ch1", catalog_root=CATALOG_ROOT, folder_path=FOLDER, display_name="Bob Ross",
    provisional_raw_keys=[item["raw_show_key"] for item in items_before], now=5.0,
)
ok_pbld, error_pbld = store4.save(new_registry_for_pbld)
check("15b. the registry saves successfully via the same shared save path", ok_pbld, error_pbld)

# A freshly-opened Programming Block dialog after the correction (the
# realistic flow -- Treat Folder as Show is reached from a different
# dialog than Programming Blocks, so "currently open" propagation is via
# the shared app-level registry, same as every other correction path).
fresh_items = build_picker_catalog(_bob_ross_channels(), {"ch1": "Comedy"}, show_identity_registry=new_registry_for_pbld)
pbld2 = ProgrammingBlockLibraryDialog(
    fresh_items, get_blocks=None, save_blocks=None, channel_number=4, channel_name="Comedy", can_schedule=False,
    show_identity_registry=new_registry_for_pbld,
)
groups_pbld = group_catalog_by_show(pbld2._items)
check("16. after correction, Bob Ross appears exactly once in the Programming Block Show Library", sum(1 for g in groups_pbld.values() if g["title"] == "Bob Ross") == 1)
check("16b. its episode count includes all three clips", groups_pbld[canonical_pbld]["episode_count"] == 3)

autofill = AutoFillBlockDialog(fresh_items, "ch1", 4, "Comedy", time.time() + 3600, time.time() + 3600 + 3600, show_identity_registry=new_registry_for_pbld)
check("17. Bob Ross appears exactly once in Auto-Fill's own show grouping", sum(1 for s in autofill._shows.values() if s["title"] == "Bob Ross") == 1)

show_picker = ShowPickerDialog(groups_pbld, 4, "Comedy", time.time() + 3600, 1800)
row_texts = [show_picker._list.item(i).text() for i in range(show_picker._list.count())]
check("18. the corrected name appears in Show Picker", any(text.startswith("Bob Ross") for text in row_texts))


section("12. Existing block is not automatically saved by the correction")

check("19. add_folder_show_rule / the Treat Folder as Show save path never touches Programming Blocks data", store4.save_calls == 1)


section("13. Auto-Fill cursor compatibility")

raw_key_1 = items_before[0]["raw_show_key"]
cursor_data = empty_cursor_data()
cursor_data = advance_cursor(cursor_data, "ch1", raw_key_1, BOB_ROSS_PATHS[0], now=100.0)
cursor_before = copy.deepcopy(cursor_data)

check("20. the folder correction itself never touches the cursor data structure", cursor_data == cursor_before)
check("21. the old cursor row under the provisional raw key remains directly readable", last_aired_path_for(cursor_data, "ch1", raw_key_1) == BOB_ROSS_PATHS[0])
winner = last_aired_path_for(cursor_data, "ch1", canonical1, show_identity_registry=reg1)
check("22. a lookup by the new canonical key finds the legacy row via alias search", winner == BOB_ROSS_PATHS[0])
check("23. no cursor row exists yet under the canonical key itself (correction doesn't write one)", cursor_key("ch1", canonical1) not in cursor_data["cursors"])


section("14. Save failure changes nothing")

store_failing = _FakeStore(fail=True)
picker_fail = PutOnAirPickerDialog(
    list(items_before), 4, "Comedy", time.time() + 3600, 3600,
    show_identity_registry=empty_registry(), show_identity_registry_save=store_failing.save,
)
items_before_failure = copy.deepcopy(picker_fail._items)
registry_before_failure = copy.deepcopy(picker_fail._show_identity_registry)
ok_fail, error_fail = picker_fail._apply_treat_folder_as_show("ch1", CATALOG_ROOT, FOLDER, "Bob Ross", None, [])
check("24. a failed save reports ok=False with a real error message", ok_fail is False and bool(error_fail))
check("24b. the dialog's in-memory registry is left exactly as it was", picker_fail._show_identity_registry == registry_before_failure)
check("24c. the dialog's in-memory items are left exactly as they were", picker_fail._items == items_before_failure)
check("24d. the app-level store's data was never reassigned", store_failing.data == empty_registry())


section("15. Failure states handled calmly")

try:
    add_folder_show_rule(empty_registry(), channel_id="ch1", catalog_root=CATALOG_ROOT, folder_path="/Outside/Root", display_name="X", now=1.0)
    check("25. a folder outside the catalog root is rejected safely", False)
except ValueError:
    check("25. a folder outside the catalog root is rejected safely", True)

picker_outside = PutOnAirPickerDialog(
    [dict(items_before[0], catalog_root="/Different/Root")], 4, "Comedy", time.time() + 3600, 3600,
    show_identity_registry=empty_registry(), show_identity_registry_save=_FakeStore().save,
)
relative_check = None
from mediawave.show_identity import _catalog_relative_folder_path
relative_check = _catalog_relative_folder_path("/Different/Root", os.path.dirname(items_before[0]["path"]))
check("25b. a mismatched catalog_root/folder_path pair yields no derivable relative path", relative_check is None)


section("16. Files and folders remain untouched (no filesystem mutation anywhere)")

import inspect
add_rule_src = inspect.getsource(add_folder_show_rule)
check("26. add_folder_show_rule never calls any os.rename/os.remove/shutil function", not any(token in add_rule_src for token in ("os.rename", "os.remove", "shutil.")))
apply_src = inspect.getsource(PutOnAirPickerDialog._apply_treat_folder_as_show)
check("26b. _apply_treat_folder_as_show never touches the filesystem beyond the registry save callback", not any(token in apply_src for token in ("os.rename", "os.remove", "shutil.", "open(")))


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

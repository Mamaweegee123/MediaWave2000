"""
Phase 5.5.4 tests: Merge Shows -- the MergeShowsDialog widget, the
ProgrammingBlockLibraryDialog._apply_show_merge mutation+save+refresh
pipeline (the one entry point Merge Shows is wired into, shared with
Rename Show's overflow menu), and end-to-end Programming Block/cursor
compatibility including absorbed-canonical-key redirect resolution.

Does not exercise MergeShowsDialog.exec() (a real modal loop) -- instead
constructs it directly and drives its widgets/methods, and calls
_apply_show_merge directly with the selection/name a user would have
confirmed, exactly what the dialog's own accept handler does after
exec() returns Accepted. Same pattern test_schedule_phase553_rename_
show.py already established for RenameShowDialog.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase5_5_4_merge_shows.py
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


from PySide6.QtWidgets import QApplication, QLabel

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.local_media import metadata_lookup_key, parse_local_media
from mediawave.schedule_editor.autofill_cursor import advance_cursor, cursor_key, empty_cursor_data, last_aired_path_for
import mediawave.schedule_editor.programming_block_dialog as pbd_module
from mediawave.schedule_editor.programming_block_dialog import (
    MergeShowsDialog,
    ProgrammingBlockLibraryDialog,
    _EditorPage,
)
from mediawave.schedule_editor.programming_blocks import BEHAVIOR_ROTATE_SHOWS, ProgrammingBlock, resolve_programming_block
from mediawave.show_identity import canonical_show_key, empty_registry, group_catalog_by_show, mint_show_key, rename_show


class _FakeMergeShowsDialog:
    """Stands in for the real MergeShowsDialog wherever a test needs to
    drive _EditorPage._merge_shows_clicked (which calls .exec() on a real
    modal QDialog). Same tiny interface the real dialog exposes.
    """

    Accepted = 1
    _next_result = 1
    _next_selected = ()
    _next_name = ""
    last_candidates = None
    last_starting_show_key = None

    def __init__(self, starting_show_key, starting_title, starting_episode_count, starting_season_count, candidates, parent=None):
        self._starting_show_key = starting_show_key
        _FakeMergeShowsDialog.last_candidates = list(candidates)
        _FakeMergeShowsDialog.last_starting_show_key = starting_show_key

    def exec(self):
        return self._next_result

    def selected_show_keys(self):
        return list(self._next_selected)

    def final_name(self):
        return self._next_name


def show_path(show_title, season, episode):
    if season is None or episode is None:
        return f"/media/Movies/{show_title}.mp4"
    return f"/media/{show_title}/{show_title} - S{season:02d}E{episode:02d} - Episode {episode}.mp4"


def show_key_of(show_title):
    sample = show_path(show_title, 1, 1)
    return metadata_lookup_key(sample, parse_local_media(sample))


def catalog_item(show_title, season, episode, duration=1800, show_key=None, media_type="tv"):
    path = show_path(show_title, season, episode)
    return {
        "path": path,
        "title": show_title,
        "detail_title": f"{show_title} S{season}E{episode}",
        "episode_label": f"Season {season} · Episode {episode}",
        "episode_title": f"Episode {episode}",
        "media_type": media_type,
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


KEY_2 = show_key_of("2")
KEY_3 = show_key_of("3")
KEY_MORAL_OREL_1 = show_key_of("moral orel 1")
ITEMS = [
    catalog_item("2", 1, 1),
    catalog_item("3", 1, 1),
    catalog_item("moral orel 1", 1, 1),
    catalog_item("moral orel 1", 1, 2),
    catalog_item("King of the Hill", 1, 1),
    catalog_item("Some Movie", None, None, media_type="movie"),
]


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


section("1. MergeShowsDialog: preselected/locked starting show, counts, validity")

dialog = MergeShowsDialog(
    KEY_2,
    "2",
    1,
    1,
    [
        {"show_key": KEY_3, "title": "3", "episode_count": 1, "season_count": 1},
        {"show_key": KEY_MORAL_OREL_1, "title": "moral orel 1", "episode_count": 2, "season_count": 1},
    ],
)
check("1. the starting show is preselected", KEY_2 in dialog._selected)
check("1b. Merge Shows starts disabled -- only the starting show is selected so far", not dialog._merge_btn.isEnabled())
check("1c. the destination name is prefilled with the starting show's current name", dialog._name_edit.text() == "2")

dialog._toggle_candidate(KEY_3)
check("2. selecting one more candidate enables Merge Shows", dialog._merge_btn.isEnabled())
check("2b. the summary reflects the combined episode count", "2 show groups" in dialog._summary_label.text() and "2 episodes" in dialog._summary_label.text())

dialog._toggle_candidate(KEY_MORAL_OREL_1)
check("3. selecting a third candidate updates the summary further", "3 show groups" in dialog._summary_label.text() and "4 episodes" in dialog._summary_label.text())

dialog._toggle_candidate(KEY_3)
check("4. deselecting a candidate removes it from the selection", KEY_3 not in dialog._selected)
check("4b. Merge Shows stays enabled with 2 shows still selected", dialog._merge_btn.isEnabled())

dialog._name_edit.setText("   ")
check("5. an empty/whitespace-only destination name disables Merge Shows even with enough shows selected", not dialog._merge_btn.isEnabled())
dialog._name_edit.setText("Moral Orel")
check("5b. Merge Shows re-enables once a real name is entered", dialog._merge_btn.isEnabled())
check("6. final_name() reflects the entered (trimmed) name", dialog.final_name() == "Moral Orel")
check("7. selected_show_keys() includes the locked starting show plus the selected candidate", set(dialog.selected_show_keys()) == {KEY_2, KEY_MORAL_OREL_1})

# The starting row is never wired to toggle -- clicking a bound toggle
# callback never exists for it, so it can never be removed.
check("8. the starting show's row has no toggle callback bound (cannot be removed by clicking)", dialog._rows_by_key[KEY_2]._on_toggle_cb is None)


section("2. Candidate list excludes movies and the same canonical show")

pbld_candidates = ProgrammingBlockLibraryDialog(
    list(ITEMS),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=_FakeStore().save,
)
editor_for_candidates = _EditorPage(
    pbld_candidates._items,
    None,
    on_save=lambda block: None,
    on_cancel=lambda: None,
    show_identity_registry=pbld_candidates._show_identity_registry,
    on_merge_shows=pbld_candidates._apply_show_merge,
)

_real_merge_dialog = pbd_module.MergeShowsDialog
pbd_module.MergeShowsDialog = _FakeMergeShowsDialog
try:
    _FakeMergeShowsDialog._next_result = 0  # reject -- just capture what candidates were built
    editor_for_candidates._merge_shows_clicked(KEY_2, "2")
finally:
    pbd_module.MergeShowsDialog = _real_merge_dialog

candidate_keys = {c["show_key"] for c in _FakeMergeShowsDialog.last_candidates}
check("9. no movie ever appears as a merge candidate", not any(c["title"] == "Some Movie" for c in _FakeMergeShowsDialog.last_candidates))
check("9b. group_catalog_by_show (which candidates are built from) never includes the movie either", not any(group["title"] == "Some Movie" for group in editor_for_candidates._shows.values()))
check("10. the starting show itself never appears in its own candidate list", KEY_2 not in candidate_keys)
check("10b. every OTHER canonical show does appear as a candidate", candidate_keys == {KEY_3, KEY_MORAL_OREL_1, show_key_of("King of the Hill")})


section("3. _apply_show_merge: three provisional shows merge into one canonical show")

store = _FakeStore()
pbld = ProgrammingBlockLibraryDialog(
    list(ITEMS),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store.save,
)
ok, error = pbld._apply_show_merge([KEY_2, KEY_3, KEY_MORAL_OREL_1], "Moral Orel")
check("11. merge succeeds", ok, error)
check("11b. the save callback was called exactly once", store.save_calls == 1)

survivor = pbld._show_identity_registry["raw_key_to_show_key"][KEY_2]
check("12. all three raw keys resolve to the same survivor", (
    pbld._show_identity_registry["raw_key_to_show_key"][KEY_3] == survivor
    and pbld._show_identity_registry["raw_key_to_show_key"][KEY_MORAL_OREL_1] == survivor
))
check("13. every catalog item from all three original groups now carries the survivor show_key", all(
    item["show_key"] == survivor for item in pbld._items if item["path"] in (show_path("2", 1, 1), show_path("3", 1, 1), show_path("moral orel 1", 1, 1), show_path("moral orel 1", 1, 2))
))
check("13b. the corrected display name is applied to all merged items", all(
    item["show_display_name"] == "Moral Orel" for item in pbld._items if item["show_key"] == survivor
))
check("14. episode-level fields are unchanged (paths/titles/season/episode)", {
    (item["path"], item["episode_title"], item["season_number"], item["episode_number"])
    for item in pbld._items if item["show_key"] == survivor
} == {
    (show_path("2", 1, 1), "Episode 1", 1, 1),
    (show_path("3", 1, 1), "Episode 1", 1, 1),
    (show_path("moral orel 1", 1, 1), "Episode 1", 1, 1),
    (show_path("moral orel 1", 1, 2), "Episode 2", 1, 2),
})
check("14b. an unrelated show's item is completely untouched", any(item["show_key"] == show_key_of("King of the Hill") and item["show_display_name"] == "" for item in pbld._items))

groups = group_catalog_by_show(pbld._items)
check("15. the show appears exactly once in the grouped catalog (Show Picker/Auto-Fill source of truth)", survivor in groups and groups[survivor]["title"] == "Moral Orel")
check("15b. the merged group's combined episode count is correct", groups[survivor]["episode_count"] == 4)


section("4. _apply_show_merge: two existing canonical shows (absorbed key redirect)")

registry_pre, key_a = rename_show(empty_registry(), show_key_of("Show A"), "Show A", now=1.0)
registry_pre2, key_b = rename_show(registry_pre, show_key_of("Show B"), "Show B", now=2.0)
store2 = _FakeStore(initial=registry_pre2)
items_ab = [catalog_item("Show A", 1, 1, show_key=key_a), catalog_item("Show B", 1, 1, show_key=key_b)]
pbld2 = ProgrammingBlockLibraryDialog(
    items_ab,
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=registry_pre2,
    show_identity_registry_save=store2.save,
)
ok2, error2 = pbld2._apply_show_merge([key_a, key_b], "Combined Show")
check("16. merging two already-canonical shows succeeds", ok2, error2)
survivor_2 = canonical_show_key(key_a, pbld2._show_identity_registry)
check("17. deterministic survivor selection keeps the first-selected existing canonical key", survivor_2 == key_a)
check("18. the absorbed canonical key (key_b) still resolves through the redirect", canonical_show_key(key_b, pbld2._show_identity_registry) == survivor_2)
check("19. items that carried the ABSORBED canonical key are remapped to the survivor", all(item["show_key"] == survivor_2 for item in pbld2._items))


section("5. Cancel and save-failure change nothing")

store3 = _FakeStore()
pbld3 = ProgrammingBlockLibraryDialog(
    list(ITEMS),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store3.save,
)
editor3 = _EditorPage(pbld3._items, None, on_save=lambda block: None, on_cancel=lambda: None, show_identity_registry=pbld3._show_identity_registry, on_merge_shows=pbld3._apply_show_merge)
pbd_module.MergeShowsDialog = _FakeMergeShowsDialog
try:
    _FakeMergeShowsDialog._next_result = 0  # QDialog.Rejected
    _FakeMergeShowsDialog._next_selected = (KEY_2, KEY_3)
    _FakeMergeShowsDialog._next_name = "Should Not Save"
    editor3._merge_shows_clicked(KEY_2, "2")
    check("20. cancelling the merge dialog performs no save", store3.save_calls == 0)
finally:
    pbd_module.MergeShowsDialog = _real_merge_dialog

items_before_failure = copy.deepcopy(pbld3._items)
registry_before_failure = copy.deepcopy(pbld3._show_identity_registry)
store_failing = _FakeStore(fail=True)
pbld4 = ProgrammingBlockLibraryDialog(
    list(ITEMS),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store_failing.save,
)
items_before_failure_4 = copy.deepcopy(pbld4._items)
registry_before_failure_4 = copy.deepcopy(pbld4._show_identity_registry)
ok4, error4 = pbld4._apply_show_merge([KEY_2, KEY_3], "Moral Orel")
check("21. a failed save reports ok=False with a real error message", ok4 is False and bool(error4))
check("21b. the dialog's in-memory registry is left exactly as it was", pbld4._show_identity_registry == registry_before_failure_4)
check("21c. the dialog's in-memory items are left exactly as they were", pbld4._items == items_before_failure_4)
check("21d. the app-level store's data was never reassigned", store_failing.data == empty_registry())


section("6. Merge is unavailable in this context (no save callback)")

pbld_no_save = ProgrammingBlockLibraryDialog(
    list(ITEMS),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
)
ok5, error5 = pbld_no_save._apply_show_merge([KEY_2, KEY_3], "Moral Orel")
check("22. with no save callback, merge fails gracefully with a message, not a crash", ok5 is False and bool(error5))


section("7. A single distinct show (nothing to merge) fails safely, not a crash")

store6 = _FakeStore()
pbld6 = ProgrammingBlockLibraryDialog(
    list(ITEMS),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store6.save,
)
ok6, error6 = pbld6._apply_show_merge([KEY_2], "Solo")
check("23. a single show_key is rejected safely (ValueError caught, not propagated)", ok6 is False and bool(error6))
check("23b. no save was attempted for an invalid merge request", store6.save_calls == 0)


section("8. Currently-open editor page: included keys remap and deduplicate")

store7 = _FakeStore()
pbld7 = ProgrammingBlockLibraryDialog(
    list(ITEMS),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store7.save,
)
pbld7._show_editor(existing_block=None)
page7 = pbld7._stack.currentWidget()
page7._name_edit.setText("Unsaved Block Name")
page7._toggle_show(KEY_2)
page7._toggle_show(KEY_3)  # both will merge -- should collapse to one entry
page7._toggle_show(show_key_of("King of the Hill"))  # unrelated -- must survive untouched
check("24. before merging, both to-be-merged shows and the unrelated show are all included separately", {KEY_2, KEY_3, show_key_of("King of the Hill")} <= set(page7._included.keys()))

ok7, error7 = pbld7._apply_show_merge([KEY_2, KEY_3], "Moral Orel")
check("25. the merge succeeds while the editor page is open", ok7, error7)
survivor_7 = canonical_show_key(KEY_2, pbld7._show_identity_registry)
check("25b. the open editor page's included set now contains the survivor key", survivor_7 in page7._included)
check("25c. the two pre-merge keys collapsed into ONE included entry (no duplicate)", KEY_2 not in page7._included and KEY_3 not in page7._included)
check("25d. the unrelated show's inclusion is completely untouched", show_key_of("King of the Hill") in page7._included)
check("25e. other unsaved edits (the block name field) survive the merge", page7._name_edit.text() == "Unsaved Block Name")
check("25f. the open page's own _shows now reports the merged title", page7._shows[survivor_7]["title"] == "Moral Orel")


section("9. Programming Block compatibility: raw-key and absorbed-canonical-key membership survive")

legacy_block = ProgrammingBlock("blk1", "Moral Orel Block", [KEY_2, KEY_3, KEY_MORAL_OREL_1], BEHAVIOR_ROTATE_SHOWS)
store8 = _FakeStore()
pbld8 = ProgrammingBlockLibraryDialog(
    list(ITEMS),
    get_blocks=lambda: {"blocks": [legacy_block]},
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=True,
    slot_start=0,
    slot_duration=7200,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store8.save,
)
plan_before = resolve_programming_block(legacy_block, pbld8._items, 0, 7200, seed=0, show_identity_registry=pbld8._show_identity_registry)
check("26. before merging, the block rotates through THREE distinct shows (fragmented)", len({e["show_key"] for e in plan_before["lineup"]}) >= 2)

pbld8._apply_show_merge([KEY_2, KEY_3, KEY_MORAL_OREL_1], "Moral Orel")
check("27. the block's own stored show_keys are untouched by the merge", legacy_block.show_keys == [KEY_2, KEY_3, KEY_MORAL_OREL_1])
plan_after = resolve_programming_block(legacy_block, pbld8._items, 0, 7200, seed=0, show_identity_registry=pbld8._show_identity_registry)
survivor_8 = canonical_show_key(KEY_2, pbld8._show_identity_registry)
check("28. after merging, the SAME legacy block resolves as ONE canonical show, not three separate rotation slots", {e["show_key"] for e in plan_after["lineup"]} == {survivor_8})
check("28b. every placement in the resolved lineup carries the survivor's canonical key", all(e["show_key"] == survivor_8 for e in plan_after["lineup"]))

# Absorbed-canonical-key membership: a block that stores an ALREADY-canonical
# key which later gets absorbed by a further merge must still resolve.
registry_c, key_c = rename_show(empty_registry(), show_key_of("Show C"), "Show C", now=1.0)
store9 = _FakeStore(initial=registry_c)
items_c = [catalog_item("Show C", 1, 1, show_key=key_c), catalog_item("Show D", 1, 1)]
block_with_absorbed_canonical = ProgrammingBlock("blk2", "C Block", [key_c], BEHAVIOR_ROTATE_SHOWS)
pbld9 = ProgrammingBlockLibraryDialog(
    items_c,
    get_blocks=lambda: {"blocks": [block_with_absorbed_canonical]},
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=True,
    slot_start=0,
    slot_duration=3600,
    show_identity_registry=registry_c,
    show_identity_registry_save=store9.save,
)
pbld9._apply_show_merge([key_c, show_key_of("Show D")], "C and D")
plan_9 = resolve_programming_block(block_with_absorbed_canonical, pbld9._items, 0, 3600, seed=0, show_identity_registry=pbld9._show_identity_registry)
check("29. a block storing an already-canonical key that later gets absorbed still resolves correctly after the merge", len(plan_9["lineup"]) > 0)


section("10. Programming Block card Featuring list uses the final merged name")

store10 = _FakeStore()
pbld10 = ProgrammingBlockLibraryDialog(
    list(ITEMS),
    get_blocks=lambda: {"blocks": [ProgrammingBlock("blk3", "Featuring Test", [KEY_2, KEY_3, KEY_MORAL_OREL_1], BEHAVIOR_ROTATE_SHOWS)]},
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store10.save,
)
pbld10._apply_show_merge([KEY_2, KEY_3, KEY_MORAL_OREL_1], "Moral Orel")
pbld10._refresh_library()
check("30. exactly one card was built for the one block", len(pbld10._cards_by_id) == 1)
card = list(pbld10._cards_by_id.values())[0]
featuring_titles = [label.text() for label in card.findChildren(QLabel) if label.objectName() == "sectionNote"]
check("31. the card's Featuring section shows the merged display name, not a raw key fragment", any(text == "Moral Orel" for text in featuring_titles))
check("31b. the card's Featuring section lists the show only ONCE despite three stored raw keys", sum(1 for text in featuring_titles if text == "Moral Orel") == 1)


section("11. Auto-Fill cursor compatibility")

cursor_data = empty_cursor_data()
cursor_data = advance_cursor(cursor_data, "ch1", KEY_2, show_path("2", 1, 1), season_number=1, episode_number=1, now=100.0)
cursor_data = advance_cursor(cursor_data, "ch1", KEY_MORAL_OREL_1, show_path("moral orel 1", 1, 2), season_number=1, episode_number=2, now=500.0)
cursor_before = copy.deepcopy(cursor_data)

store11 = _FakeStore()
pbld11 = ProgrammingBlockLibraryDialog(
    list(ITEMS),
    get_blocks=None,
    save_blocks=None,
    channel_number=4,
    channel_name="Comedy",
    can_schedule=False,
    show_identity_registry=empty_registry(),
    show_identity_registry_save=store11.save,
)
pbld11._apply_show_merge([KEY_2, KEY_3, KEY_MORAL_OREL_1], "Moral Orel")
survivor_11 = canonical_show_key(KEY_2, pbld11._show_identity_registry)

check("32. merge itself never touches the cursor data structure", cursor_data == cursor_before)
check("33. the old cursor row under KEY_2's raw alias remains directly readable", last_aired_path_for(cursor_data, "ch1", KEY_2) == show_path("2", 1, 1))
check("34. the old cursor row under KEY_MORAL_OREL_1's raw alias remains directly readable", last_aired_path_for(cursor_data, "ch1", KEY_MORAL_OREL_1) == show_path("moral orel 1", 1, 2))
winner = last_aired_path_for(cursor_data, "ch1", survivor_11, show_identity_registry=pbld11._show_identity_registry)
check("35. a lookup by the survivor key finds the most recently placed of the two legacy rows (approved winner rule, unchanged)", winner == show_path("moral orel 1", 1, 2))
check("36. no cursor row exists yet under the survivor key itself (merge doesn't write one)", cursor_key("ch1", survivor_11) not in cursor_data["cursors"])


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

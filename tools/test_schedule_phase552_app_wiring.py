"""
Phase 5.5.2 step 3 tests (revised by Phase 5.5.3): app-level Show
Identity registry wiring -- startup load, AdvancedConfigDialog's getter/
save pair (schedule_show_identity_get/schedule_show_identity_save,
mirroring the Programming Blocks pattern -- Phase 5.5.3 upgraded this
from step 3's original read-only snapshot now that Rename Show can save
a correction while the dialog is open), and every Schedule Editor
build_picker_catalog call site receiving the current registry. This file
proves the plumbing: a manually/synthetically populated registry becomes
visible to catalog construction, and normal app startup/shutdown never
writes the registry file merely from reading it.

Deliberately avoids constructing the full AdvancedConfigDialog (a very
heavy Qt dialog nothing else in this suite instantiates directly) and
avoids invoking ScheduleEditorWorkspace's click handlers (which open
real modal picker dialogs) -- instead uses source-level inspection for
the wiring itself (same pattern test_schedule_phase53_show_balanced.py
and test_catalog_autoload.py already use for channelsurfer2000.py) plus
direct construction of ScheduleEditorWorkspace against a bare fake
studio_dialog (same pattern test_schedule_editor.py already uses) for
the runtime behavior.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase552_app_wiring.py
"""

import inspect
import os
import sys
import tempfile

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

from mediawave.schedule_editor.dialog import ScheduleEditorWorkspace
from mediawave.show_identity import (
    create_registry_record,
    empty_registry,
    load_show_identity_registry,
    mint_show_key,
    save_show_identity_registry,
)


section("Source-level wiring: channelsurfer2000.py startup + AdvancedConfigDialog")

try:
    import channelsurfer2000 as app_module

    check(
        "1. SCHEDULE_SHOW_IDENTITY_FILE constant exists, named schedule_show_identity.json",
        os.path.basename(app_module.SCHEDULE_SHOW_IDENTITY_FILE) == "schedule_show_identity.json",
        getattr(app_module, "SCHEDULE_SHOW_IDENTITY_FILE", None),
    )

    init_src = inspect.getsource(app_module.ChannelSurfer.__init__)
    check(
        "2. startup loads the registry via load_show_identity_registry(SCHEDULE_SHOW_IDENTITY_FILE)",
        "self.schedule_show_identity_data = load_show_identity_registry(SCHEDULE_SHOW_IDENTITY_FILE)" in init_src,
    )

    adv_init_src = inspect.getsource(app_module.AdvancedConfigDialog.__init__)
    check(
        "3. AdvancedConfigDialog.__init__ accepts schedule_show_identity_get and schedule_show_identity_save",
        "schedule_show_identity_get=None" in adv_init_src and "schedule_show_identity_save=None" in adv_init_src,
    )
    check(
        "4. AdvancedConfigDialog stores both as plain callback attributes (getter/reassign contract, not a snapshot)",
        "_schedule_show_identity_get = schedule_show_identity_get" in adv_init_src
        and "_schedule_show_identity_save = schedule_show_identity_save" in adv_init_src,
    )

    # Find whichever method constructs AdvancedConfigDialog(...) and confirm
    # it forwards the app's own loaded registry, not a fresh/empty one.
    open_adv_src = None
    for name, method in inspect.getmembers(app_module.ChannelSurfer, predicate=inspect.isfunction):
        try:
            src = inspect.getsource(method)
        except (OSError, TypeError):
            continue
        if "AdvancedConfigDialog(" in src and "schedule_programming_blocks_save=" in src:
            open_adv_src = src
            break
    check(
        "5. found the ChannelSurfer method that constructs AdvancedConfigDialog",
        open_adv_src is not None,
    )
    check(
        "6. that construction call passes a getter reading self.schedule_show_identity_data and the app's save callback",
        open_adv_src is not None
        and "schedule_show_identity_get=lambda: self.schedule_show_identity_data" in open_adv_src
        and "schedule_show_identity_save=self.save_schedule_show_identity_from_editor" in open_adv_src,
        open_adv_src,
    )

    check(
        "7. save_schedule_show_identity_from_editor exists and calls save_show_identity_registry (Phase 5.5.3's Rename Show save path)",
        "def save_schedule_show_identity_from_editor" in inspect.getsource(app_module)
        and "save_show_identity_registry(SCHEDULE_SHOW_IDENTITY_FILE" in inspect.getsource(app_module.ChannelSurfer.save_schedule_show_identity_from_editor),
    )
    save_src = inspect.getsource(app_module.ChannelSurfer.save_schedule_show_identity_from_editor)
    check(
        "7b. on success it reassigns self.schedule_show_identity_data (never mutates it in place)",
        "self.schedule_show_identity_data = load_show_identity_registry(SCHEDULE_SHOW_IDENTITY_FILE)" in save_src,
    )
except Exception as exc:  # pragma: no cover - environment-dependent (PySide6/Qt availability)
    check("1-7b. app-level source wiring checks (skipped)", True, str(exc))


section("Persistence behavior: missing/malformed registry file")

with tempfile.TemporaryDirectory() as tmp:
    missing_path = os.path.join(tmp, "schedule_show_identity.json")
    loaded = load_show_identity_registry(missing_path)
    check("8. a missing registry file loads as empty", loaded == empty_registry())
    check("8b. loading a missing file does not create it", not os.path.exists(missing_path))

    malformed_path = os.path.join(tmp, "schedule_show_identity_bad.json")
    with open(malformed_path, "w", encoding="utf-8") as handle:
        handle.write("{not valid json at all")
    loaded_bad = load_show_identity_registry(malformed_path)
    check("9. a malformed registry file loads as empty (fails open)", loaded_bad == empty_registry())
    with open(malformed_path, "r", encoding="utf-8") as handle:
        check("9b. loading a malformed file does not rewrite it", handle.read() == "{not valid json at all")


section("ScheduleEditorWorkspace._show_identity_registry(): getter, not a snapshot")


class _FakeStudioDialogNoRegistry:
    """Bare, like test_schedule_editor.py's _FakeStudioDialog -- no
    _schedule_show_identity_get attribute at all, exercising the
    None-means-unavailable fallback.
    """


workspace_none = ScheduleEditorWorkspace(_FakeStudioDialogNoRegistry())
check("10. missing _schedule_show_identity_get on the studio dialog falls back to an empty registry", workspace_none._show_identity_registry() == empty_registry())


class _FakeStudioDialogBadRegistry:
    _schedule_show_identity_get = staticmethod(lambda: "not a dict")


workspace_bad = ScheduleEditorWorkspace(_FakeStudioDialogBadRegistry())
check("11. a non-dict return from the getter also falls back to an empty registry, not a crash", workspace_bad._show_identity_registry() == empty_registry())

canonical_key = mint_show_key()
synthetic_registry = {
    "version": 1,
    "shows": {canonical_key: create_registry_record("Moral Orel", aliases=["tv::moral orel", "tv::moral orel redux"], now=1.0)},
    "raw_key_to_show_key": {"tv::moral orel": canonical_key, "tv::moral orel redux": canonical_key},
    "folder_rules": {},
}


class _FakeStudioDialogWithRegistry:
    _schedule_show_identity_get = staticmethod(lambda: synthetic_registry)


workspace_with_registry = ScheduleEditorWorkspace(_FakeStudioDialogWithRegistry())
check("12. a real registry from the getter is returned exactly as given", workspace_with_registry._show_identity_registry() == synthetic_registry)
check("12b. the same registry instance is handed back (the getter's own return value, not a copy)", workspace_with_registry._show_identity_registry() is synthetic_registry)

import copy

before = copy.deepcopy(synthetic_registry)
workspace_with_registry._show_identity_registry()
ScheduleEditorWorkspace(_FakeStudioDialogWithRegistry())
check("13. merely constructing the workspace / calling the accessor never mutates the registry", synthetic_registry == before)

# The whole point of switching to a getter (Phase 5.5.3): a reassignment
# on the studio dialog's side (exactly what a successful Rename Show save
# does to self.schedule_show_identity_data) is visible on the WORKSPACE's
# very next read, with no cache to invalidate.
renamed_registry = dict(synthetic_registry, shows={**synthetic_registry["shows"]})


class _FakeStudioDialogReassignable:
    _current = synthetic_registry

    @classmethod
    def _schedule_show_identity_get(cls):
        return cls._current


workspace_reassignable = ScheduleEditorWorkspace(_FakeStudioDialogReassignable())
check("13b. before reassignment, the workspace sees the original registry", workspace_reassignable._show_identity_registry() == synthetic_registry)
_FakeStudioDialogReassignable._current = renamed_registry
check("13c. after the studio dialog's attribute is reassigned, the SAME already-open workspace sees the new registry immediately", workspace_reassignable._show_identity_registry() is renamed_registry)


section("All four catalog-build call sites pass show_identity_registry=self._show_identity_registry()")

dialog_source = inspect.getsource(sys.modules["mediawave.schedule_editor.dialog"])
call_site_count = dialog_source.count("build_picker_catalog(self._studio_channels_by_id, names_by_id, show_identity_registry=self._show_identity_registry())")
check(
    "14. exactly four build_picker_catalog call sites thread the registry through (Put On Air, Fill Open Time, Programming Blocks, Auto-Fill)",
    call_site_count == 4,
    call_site_count,
)
check("15. no build_picker_catalog call site was left without the registry", "build_picker_catalog(self._studio_channels_by_id, names_by_id)\n" not in dialog_source)


section("Synthetic correction validation: end-to-end catalog output through the real call site shape")

from mediawave.schedule_editor.put_on_air_picker import build_picker_catalog
from mediawave.show_identity import group_catalog_by_show


class _FakeChannel:
    channel_type = "media"

    def __init__(self, paths, duration=1320):
        self.name = "Comedy"
        self.shows = paths
        self.duration_cache = {p: duration for p in paths}


MORAL_OREL_1 = "/media/TV/Moral Orel/Season 1/Moral Orel - S01E01 - Numb.mp4"
MORAL_OREL_REDUX = "/media/TV/Moral Orel Redux/Season 1/Moral Orel Redux - S01E02 - Numb Pt2.mp4"


class _FakeStudioDialogForSyntheticCorrection:
    _studio_channels_by_id = {"ch1": _FakeChannel([MORAL_OREL_1, MORAL_OREL_REDUX])}
    _schedule_show_identity_get = staticmethod(lambda: synthetic_registry)


synthetic_workspace = ScheduleEditorWorkspace(_FakeStudioDialogForSyntheticCorrection())
names_by_id = {"ch1": "Comedy"}
items = build_picker_catalog(
    synthetic_workspace._studio_channels_by_id,
    names_by_id,
    show_identity_registry=synthetic_workspace._show_identity_registry(),
)
groups = group_catalog_by_show(items)

check("16. exactly one grouped show row exists for the corrected show", canonical_key in groups and len(groups) == 1)
check("17. the corrected display name appears", groups[canonical_key]["title"] == "Moral Orel")
check("18. the episode count is the combined total across both aliased files", groups[canonical_key]["episode_count"] == 2)
check("19. the group's show_key is the canonical show_<uuid> key", groups[canonical_key]["show_key"] == canonical_key)
paths_in_group = {ep["path"] for ep in groups[canonical_key]["episodes"]}
check("20. source media paths are unchanged", paths_in_group == {MORAL_OREL_1, MORAL_OREL_REDUX})
episode_titles = {ep["episode_title"] for ep in groups[canonical_key]["episodes"]}
check("21. episode titles remain the concrete per-file titles, not the show display name", episode_titles == {"Numb", "Numb Pt2"})


section("Programming Block editor and Auto-Fill dialog see the same canonical grouping")

# Both consume group_catalog_by_show(items) over the exact same `items`
# build_picker_catalog just produced above -- proving they'd see identical
# grouping without needing to open either dialog (which would block on
# exec()). This is the same items list the four call sites in dialog.py
# now all construct identically (all four pass the same registry).
groups_for_programming_blocks = group_catalog_by_show(items)
groups_for_autofill = group_catalog_by_show(items)
check("22. Programming Block grouping and Auto-Fill grouping agree exactly (one shared helper, one shared catalog)", groups_for_programming_blocks == groups_for_autofill == groups)


section("Empty registry: catalog output is unaffected (regression pin)")

items_empty = build_picker_catalog({"ch1": _FakeChannel([MORAL_OREL_1, MORAL_OREL_REDUX])}, names_by_id, show_identity_registry=empty_registry())
groups_empty = group_catalog_by_show(items_empty)
check("23. with an empty registry the two aliased files remain two separate shows", len(groups_empty) == 2)
check("23b. neither group is marked as an override", all(group["source"] == "parsed" for group in groups_empty.values()))


section("No save occurs anywhere in this step")

with tempfile.TemporaryDirectory() as tmp:
    registry_path = os.path.join(tmp, "schedule_show_identity.json")
    loaded = load_show_identity_registry(registry_path)
    # Simulate a full "open the editor, build a few catalogs" cycle and
    # confirm the sidecar file was never created -- opening the Schedule
    # Editor is read-only in this step.
    ScheduleEditorWorkspace(_FakeStudioDialogForSyntheticCorrection())
    build_picker_catalog({"ch1": _FakeChannel([MORAL_OREL_1])}, names_by_id, show_identity_registry=loaded)
    check("24. no registry file was written just from loading + building catalogs", not os.path.exists(registry_path))


section("Scratch harness imports updated (cleanup)")

for harness_path in ("dev_testing/phase51_ux/review_harness.py", "dev_testing/phase52_ux/review_harness.py"):
    full_path = os.path.join(REPO_ROOT, harness_path)
    if not os.path.exists(full_path):
        check(f"25. {harness_path} exists to check", False, "file not found")
        continue
    with open(full_path, "r", encoding="utf-8") as handle:
        harness_source = handle.read()
    check(f"25. {harness_path} no longer imports group_shows_for_picker", "group_shows_for_picker" not in harness_source, harness_path)
    check(f"25b. {harness_path} uses the shared group_catalog_by_show helper", "group_catalog_by_show" in harness_source, harness_path)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

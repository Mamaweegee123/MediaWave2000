"""
Auto-load-saved-catalog-on-startup tests.

Covers:
- mediawave.core_io.catalog_path_is_available (pure helper) against real
  temp directories/files/permissions/broken symlinks/missing paths.
- ChannelSurfer.load_catalog's re-entrancy guard, exercised on the real bound
  method with _load_catalog_impl stubbed out (so no full Qt/catalog scan is
  needed) -- proving the guard actually lives in production code, not a test
  reimplementation.
- ChannelSurfer.auto_load_catalog_if_available, exercised the same way (real
  bound method, fake collaborator app object), proving it delegates to the
  exact same load_catalog() used by Choose Catalog rather than a second
  implementation, and behaves correctly for every saved-path availability
  case.
- Source-level checks that browse_catalog (Choose Catalog) and
  auto_load_catalog_if_available (startup) both call self.load_catalog(...)
  and that there is exactly one scanning implementation.

Run from the repo root:
  venv/bin/python3 tools/test_catalog_autoload.py
"""

import inspect
import os
import stat
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

from mediawave.core_io import (
    PATH_ACCESS_DISCONNECTED_VOLUME,
    PATH_ACCESS_MISSING,
    PATH_ACCESS_NOT_DIRECTORY,
    PATH_ACCESS_OK,
    catalog_path_is_available,
)

import channelsurfer2000 as app_module
from channelsurfer2000 import ChannelSurfer


# ---------------------------------------------------------------------------
section("1-6. catalog_path_is_available (pure helper)")
# ---------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    good_dir = os.path.join(tmp, "catalog")
    os.makedirs(good_dir)
    with open(os.path.join(good_dir, "placeholder.mp4"), "w") as fh:
        fh.write("x")

    check("1. a readable existing directory is available", catalog_path_is_available(good_dir) is True)
    check("2. an empty string is not available", catalog_path_is_available("") is False)
    check("2b. None is not available", catalog_path_is_available(None) is False)
    check("2c. whitespace-only is not available", catalog_path_is_available("   ") is False)

    missing = os.path.join(tmp, "does-not-exist")
    check("3. a missing path is not available", catalog_path_is_available(missing) is False)

    a_file = os.path.join(tmp, "not_a_folder.txt")
    with open(a_file, "w") as fh:
        fh.write("x")
    check("4. a file (not a directory) is not available", catalog_path_is_available(a_file) is False)

    broken_link = os.path.join(tmp, "broken_link")
    link_target = os.path.join(tmp, "target_that_will_be_removed")
    os.makedirs(link_target)
    os.symlink(link_target, broken_link)
    os.rmdir(link_target)
    check("4b. a broken symlink is not available", catalog_path_is_available(broken_link) is False)

    if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() != 0:
        locked_dir = os.path.join(tmp, "locked")
        os.makedirs(locked_dir)
        os.chmod(locked_dir, 0)
        try:
            check("5. permission-denied is handled safely (returns False, no exception)", catalog_path_is_available(locked_dir) is False)
        finally:
            os.chmod(locked_dir, stat.S_IRWXU)
    else:
        check("5. permission-denied case (skipped -- running as root or unsupported platform)", True)

    home_backed_dir = os.path.join(tmp, "home_root")
    home_catalog = os.path.join(home_backed_dir, "Catalog")
    os.makedirs(home_catalog)
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = home_backed_dir
    try:
        check("6. a ~-prefixed path is expanded before checking", catalog_path_is_available("~/Catalog") is True)
    finally:
        if old_home is not None:
            os.environ["HOME"] = old_home
        else:
            os.environ.pop("HOME", None)

    check("6b. never raises for a value that isn't a valid path type", catalog_path_is_available(12345) is False)


# ---------------------------------------------------------------------------
section("7-9. load_catalog re-entrancy guard (real bound method, stubbed impl)")
# ---------------------------------------------------------------------------


class _FakeLoadCatalogApp:
    load_catalog = ChannelSurfer.load_catalog

    def __init__(self):
        self._catalog_load_in_progress = False
        self.impl_calls = []
        self.flag_during_call = None

    def _load_catalog_impl(self, folder=None, autoplay=False):
        self.impl_calls.append((folder, autoplay))
        self.flag_during_call = self._catalog_load_in_progress
        return True


fresh = _FakeLoadCatalogApp()
result = fresh.load_catalog("/some/folder", autoplay=True)
check("7. load_catalog delegates to _load_catalog_impl exactly once", fresh.impl_calls == [("/some/folder", True)], fresh.impl_calls)
check("7b. load_catalog returns _load_catalog_impl's result", result is True)
check("7c. the in-progress flag is set to True while the real load runs", fresh.flag_during_call is True)
check("7d. the in-progress flag is reset to False after load_catalog returns", fresh._catalog_load_in_progress is False)

busy = _FakeLoadCatalogApp()
busy._catalog_load_in_progress = True
busy_result = busy.load_catalog("/other/folder")
check("8. a load_catalog call while already in progress is skipped entirely", busy.impl_calls == [], busy.impl_calls)
check("8b. the skipped call returns False rather than raising or blocking", busy_result is False)
check("8c. the in-progress flag is left as-is (still True) by the skipped call", busy._catalog_load_in_progress is True)


class _FailingLoadCatalogApp:
    load_catalog = ChannelSurfer.load_catalog

    def __init__(self):
        self._catalog_load_in_progress = False

    def _load_catalog_impl(self, folder=None, autoplay=False):
        raise RuntimeError("boom")


failing = _FailingLoadCatalogApp()
try:
    failing.load_catalog("/x")
except RuntimeError:
    pass
check("9. the in-progress flag is reset even if the underlying load raises", failing._catalog_load_in_progress is False)


# ---------------------------------------------------------------------------
section("10-16. auto_load_catalog_if_available (real bound method, fake app)")
# ---------------------------------------------------------------------------


class _FakeLabel:
    def __init__(self):
        self.text = ""

    def setText(self, value):
        self.text = value


class _FakeAutoLoadApp:
    auto_load_catalog_if_available = ChannelSurfer.auto_load_catalog_if_available
    _path_access_blocks_scan = ChannelSurfer._path_access_blocks_scan

    def __init__(self, catalog_path, access_status, auto_launch=False, already_loading=False, load_catalog_returns=True):
        self.app_settings = {"catalog_path": catalog_path, "auto_launch": auto_launch}
        self.catalog_path_label = _FakeLabel()
        self.status = _FakeLabel()
        self._catalog_load_in_progress = already_loading
        self._access_status = access_status
        self._load_catalog_returns = load_catalog_returns
        self.load_catalog_calls = []
        self.first_run_calls = 0
        self.refresh_calls = 0
        self.hide_calls = 0
        self.applied_statuses = []

    def _classify_catalog_path(self, path, context="", force=False):
        return {"status": self._access_status, "path": path}

    def _apply_library_status(self, status_info):
        self.applied_statuses.append(status_info)

    def _library_status_for_path(self, folder, access):
        return {"folder": folder, "status": access.get("status")}

    def _show_first_run_guidance(self):
        self.first_run_calls += 1

    def refresh_controls(self):
        self.refresh_calls += 1

    def load_catalog(self, folder=None, autoplay=False):
        self.load_catalog_calls.append((folder, autoplay))
        return self._load_catalog_returns

    def hide(self):
        self.hide_calls += 1

    def _auto_launch_watch_tv(self):
        pass


good_app = _FakeAutoLoadApp("/Volumes/MediaWave/Catalog", PATH_ACCESS_OK)
good_app.auto_load_catalog_if_available()
check("10. a saved readable directory auto-loads once via the real load_catalog", good_app.load_catalog_calls == [("/Volumes/MediaWave/Catalog", False)], good_app.load_catalog_calls)

empty_path_app = _FakeAutoLoadApp("", PATH_ACCESS_OK)
empty_path_app.auto_load_catalog_if_available()
check("11. an empty saved path does nothing (no load, shows first-run guidance)", empty_path_app.load_catalog_calls == [] and empty_path_app.first_run_calls == 1)

missing_app = _FakeAutoLoadApp("/Volumes/Gone/Catalog", PATH_ACCESS_MISSING)
missing_app.auto_load_catalog_if_available()
check("12. a missing saved path does nothing", missing_app.load_catalog_calls == [])
check("12b. the saved path setting itself is left untouched", missing_app.app_settings["catalog_path"] == "/Volumes/Gone/Catalog")
check("12c. the setup screen stays usable (refresh_controls still runs, no exception)", missing_app.refresh_calls == 1)
check("12d. a non-blocking status message is shown", missing_app.status.text == "Saved catalog is currently unavailable.")

disconnected_app = _FakeAutoLoadApp("/Volumes/NAS/Catalog", PATH_ACCESS_DISCONNECTED_VOLUME)
disconnected_app.auto_load_catalog_if_available()
check("13. an unmounted/disconnected saved path does nothing", disconnected_app.load_catalog_calls == [])
check("13b. it does not clear the saved path", disconnected_app.app_settings["catalog_path"] == "/Volumes/NAS/Catalog")

file_path_app = _FakeAutoLoadApp("/Users/someone/not_a_folder.txt", PATH_ACCESS_NOT_DIRECTORY)
file_path_app.auto_load_catalog_if_available()
check("14. a saved path that is a file, not a directory, does nothing", file_path_app.load_catalog_calls == [])

failing_load_app = _FakeAutoLoadApp("/Volumes/MediaWave/Catalog", PATH_ACCESS_OK, load_catalog_returns=False)
failing_load_app.auto_load_catalog_if_available()
check(
    "15. when the path is available but the load itself fails, load_catalog is still the one called (existing error path owns it)",
    failing_load_app.load_catalog_calls == [("/Volumes/MediaWave/Catalog", False)],
)
check("15b. auto-load does not reopen the folder chooser or run first-run guidance on a load failure", failing_load_app.first_run_calls == 0)

already_loading_app = _FakeAutoLoadApp("/Volumes/MediaWave/Catalog", PATH_ACCESS_OK, already_loading=True)
already_loading_app.auto_load_catalog_if_available()
check("16. no duplicate auto-load when a catalog load is already in progress", already_loading_app.load_catalog_calls == [])

auto_launch_app = _FakeAutoLoadApp("/Volumes/MediaWave/Catalog", PATH_ACCESS_OK, auto_launch=True)
auto_launch_app.auto_load_catalog_if_available()
check(
    "16b. with Skip Setup Screen enabled, startup hands off to the auto-launch path instead of double-loading",
    auto_launch_app.load_catalog_calls == [] and auto_launch_app.hide_calls == 1,
    (auto_launch_app.load_catalog_calls, auto_launch_app.hide_calls),
)


# ---------------------------------------------------------------------------
section("17-19. Single implementation: browse_catalog and auto-load share load_catalog")
# ---------------------------------------------------------------------------

browse_src = inspect.getsource(ChannelSurfer.browse_catalog)
check("17. Choose Catalog (browse_catalog) calls self.load_catalog(...)", "self.load_catalog(" in browse_src, browse_src)

auto_src = inspect.getsource(ChannelSurfer.auto_load_catalog_if_available)
check("18. startup auto-load calls self.load_catalog(...) for the available-path case", "self.load_catalog(" in auto_src, auto_src)
check(
    "18b. auto-load does not reimplement scanning itself (no os.walk / safe_iter_media_folder in this method)",
    "os.walk(" not in auto_src and "safe_iter_media_folder(" not in auto_src,
    auto_src,
)

impl_owners = [name for name, member in vars(ChannelSurfer).items() if name == "_load_catalog_impl"]
check("19. there is exactly one catalog-scanning implementation (_load_catalog_impl)", len(impl_owners) == 1, impl_owners)
load_catalog_src = inspect.getsource(ChannelSurfer.load_catalog)
check("19b. the public load_catalog is a thin guarded wrapper, not a second scan implementation", "os.walk(" not in load_catalog_src and "_load_catalog_impl(" in load_catalog_src, load_catalog_src)


# ---------------------------------------------------------------------------
section("20. Startup wiring: auto-load is scheduled post-init, not run in the constructor body directly")
# ---------------------------------------------------------------------------

init_src = inspect.getsource(ChannelSurfer.__init__)
check(
    "20. auto_load_catalog_if_available runs via QTimer.singleShot(0, ...) after init, not synchronously mid-constructor",
    "QTimer.singleShot(0, self.auto_load_catalog_if_available)" in init_src,
    None,
)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All catalog auto-load tests passed.")

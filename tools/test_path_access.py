"""
Smoke tests for core path access helpers.
Run from the repo root:  venv/bin/python3 tools/test_path_access.py
"""
import os
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave import core_io as mod

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


section("classification")
missing = mod.classify_path_access("/no/such/mediawave/path")
check("missing path", missing["status"] == mod.PATH_ACCESS_MISSING, missing)

with tempfile.TemporaryDirectory() as tmpdir:
    folder = os.path.join(tmpdir, "folder")
    os.mkdir(folder)
    empty = mod.classify_path_access(folder)
    check("empty folder", empty["status"] == mod.PATH_ACCESS_EMPTY, empty)

    media = os.path.join(folder, "clip.mp4")
    with open(media, "w", encoding="utf-8") as handle:
        handle.write("not real media")
    ok = mod.classify_path_access(folder)
    check("normal local folder", ok["status"] == mod.PATH_ACCESS_OK, ok)

    file_result = mod.classify_path_access(media)
    check("file instead of folder", file_result["status"] == mod.PATH_ACCESS_NOT_DIRECTORY, file_result)

    if os.name != "nt":
        unreadable = os.path.join(tmpdir, "unreadable")
        os.mkdir(unreadable)
        try:
            os.chmod(unreadable, 0)
            unreadable_result = mod.classify_path_access(unreadable)
            check(
                "unreadable folder",
                unreadable_result["status"] in {mod.PATH_ACCESS_PERMISSION_DENIED, mod.PATH_ACCESS_UNREADABLE},
                unreadable_result,
            )
        finally:
            os.chmod(unreadable, 0o700)


section("network-like paths")
check("UNC path classification", mod.is_network_like_path(r"\\server\share"))
check("smb URL classification", mod.is_network_like_path("smb://server/share"))
check("macOS external volume is not network warning", not mod.is_network_like_path("/Volumes/cable/Catalog"))

valid_external = mod.format_library_path_status(
    "/Volumes/cable/Catalog",
    {
        "status": mod.PATH_ACCESS_OK,
        "path": "/Volumes/cable/Catalog",
        "location": mod.PATH_LOCATION_EXTERNAL,
        "network_like": False,
    },
)
check("valid external path is calm", valid_external["title"] == "Library ready", valid_external)
check("valid external path avoids NAS wording", "NAS" not in (valid_external["message"] + valid_external["detail"]), valid_external)

vol = mod.classify_path_access("/Volumes/MediaWaveDefinitelyMissing/Shows")
if sys.platform == "darwin":
    check("stale macOS /Volumes path", vol["status"] == mod.PATH_ACCESS_DISCONNECTED_VOLUME, vol)
else:
    check("stale /Volumes path outside macOS is missing", vol["status"] == mod.PATH_ACCESS_MISSING, vol)
drive_status = mod.format_library_path_status("/Volumes/MediaWaveDefinitelyMissing/Shows", vol)
if sys.platform == "darwin":
    check("missing /Volumes status title", drive_status["title"] == "Drive not found", drive_status)

unc = mod.classify_path_access(r"\\server\share")
unc_status = mod.format_library_path_status(r"\\server\share", unc)
check("UNC unavailable title", unc_status["title"] == "Network library unavailable", unc_status)


section("descriptions")
onboarding = mod.no_catalog_selected_status()
check("no catalog onboarding copy", onboarding["message"] == "Choose a folder containing your shows and movies to get started.", onboarding)
local_ready = mod.format_library_path_status(
    "/tmp/mediawave-local",
    {"status": mod.PATH_ACCESS_OK, "path": "/tmp/mediawave-local", "location": mod.PATH_LOCATION_LOCAL, "network_like": False},
)
check("valid local path ready", local_ready["title"] == "Library ready", local_ready)
empty_message = mod.format_no_playable_media_message("/tmp/mediawave-empty", network_like=False)
check("empty no-media message friendly", empty_message == "No playable media found in this folder. Try choosing the folder that contains your show or movie files.", empty_message)
network_empty_message = mod.format_no_playable_media_message(r"\\server\share", network_like=True)
check("network no-media message adds one line", "network library" in network_empty_message and "NAS" not in network_empty_message, network_empty_message)
permission_status = mod.format_library_path_status(
    "/tmp/mediawave-denied",
    {"status": mod.PATH_ACCESS_PERMISSION_DENIED, "path": "/tmp/mediawave-denied", "location": mod.PATH_LOCATION_LOCAL, "network_like": False},
)
check("permission message friendly", permission_status["message"] == "MediaWave can't read this folder. Check permissions or choose a different folder.", permission_status)


print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All path access smoke tests passed.")

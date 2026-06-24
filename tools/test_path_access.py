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
check("macOS volume classification", mod.is_network_like_path("/Volumes/NAS/Shows"))

vol = mod.classify_path_access("/Volumes/MediaWaveDefinitelyMissing/Shows")
if sys.platform == "darwin":
    check("stale macOS /Volumes path", vol["status"] == mod.PATH_ACCESS_DISCONNECTED_VOLUME, vol)
else:
    check("stale /Volumes path outside macOS is missing", vol["status"] == mod.PATH_ACCESS_MISSING, vol)


section("descriptions")
check("missing description is friendly", "NAS" in mod.describe_path_access_issue("/no/such/mediawave/path", mod.PATH_ACCESS_MISSING))
check("permission description exists", bool(mod.describe_path_access_issue("", mod.PATH_ACCESS_PERMISSION_DENIED)))


print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All path access smoke tests passed.")

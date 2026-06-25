"""
Smoke tests for channel logo settings helpers.
Run from the repo root:  venv/bin/python3 tools/test_channel_logos.py
No GUI launch required.
"""
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import channelsurfer2000 as app

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


section("defaults")
defaults = app.normalize_channel_bug_settings({})
check("horizontal offset default", defaults["horizontal_offset"] == 0, defaults)
check("vertical offset default", defaults["vertical_offset"] == 0, defaults)
check("placement area default", defaults["placement_area"] == "overlay", defaults)


section("normalization")
normalized = app.normalize_channel_bug_settings({
    "horizontal_offset": 999,
    "vertical_offset": -999,
    "placement_area": "video_content",
})
check("horizontal offset clamps high", normalized["horizontal_offset"] == 240, normalized)
check("vertical offset clamps low", normalized["vertical_offset"] == -240, normalized)
check("video content placement accepted", normalized["placement_area"] == "video_content", normalized)

invalid = app.normalize_channel_bug_settings({"placement_area": "somewhere-else"})
check("invalid placement falls back", invalid["placement_area"] == "overlay", invalid)


section("per-channel overrides")
settings = app.normalize_channel_bug_settings({
    "enabled": True,
    "horizontal_offset": 12,
    "vertical_offset": -8,
    "placement_area": "video_content",
    "channel_overrides": {
        "Ch 1": {
            "mode": "custom",
            "horizontal_offset": -24,
            "vertical_offset": 16,
            "placement_area": "overlay",
        }
    },
})
global_effective = app.get_effective_channel_logo_settings("Ch 2", settings)
custom_effective = app.get_effective_channel_logo_settings("Ch 1", settings)
check("global channel inherits horizontal offset", global_effective["horizontal_offset"] == 12, global_effective)
check("global channel inherits placement", global_effective["placement_area"] == "video_content", global_effective)
check("custom channel overrides horizontal offset", custom_effective["horizontal_offset"] == -24, custom_effective)
check("custom channel overrides vertical offset", custom_effective["vertical_offset"] == 16, custom_effective)
check("custom channel overrides placement", custom_effective["placement_area"] == "overlay", custom_effective)


print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All channel logo smoke tests passed.")

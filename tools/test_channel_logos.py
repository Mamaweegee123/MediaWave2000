"""
Smoke tests for channel logo settings helpers.
Run from the repo root:  venv/bin/python3 tools/test_channel_logos.py
No GUI launch required.
"""
import inspect
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import channelsurfer2000 as app
from mediawave import channel_logos as logo_mod

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
check("module defaults match app import", logo_mod.channel_bug_settings_defaults()["placement_area"] == defaults["placement_area"])


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
check("module effective settings match app import", logo_mod.get_effective_channel_logo_settings("Ch 1", settings) == custom_effective)


section("Logo Studio v1: position <-> corner/offset math")
# resolve_logo_position mirrors ChannelBugOverlay.paintEvent's corner formula exactly.
check(
    "bottom-right at zero offset sits margin px from the bottom-right edge",
    logo_mod.resolve_logo_position("bottom-right", 0, 0, 1280, 720, 80, 80, 18) == (1182, 622),
)
check(
    "top-left at zero offset sits margin px from the top-left edge",
    logo_mod.resolve_logo_position("top-left", 0, 0, 1280, 720, 80, 80, 18) == (18, 18),
)
check(
    "an offset that would push the logo off-screen is clamped inside the screen",
    logo_mod.resolve_logo_position("top-left", 9999, 9999, 1280, 720, 80, 80, 18) == (1200, 640),
)

for corner in logo_mod.CHANNEL_BUG_CORNER_OPTIONS:
    x, y = logo_mod.resolve_logo_position(corner, 5, -5, 1280, 720, 80, 80, 18)
    round_trip_corner, h, v = logo_mod.position_to_corner_offsets(x, y, 1280, 720, 80, 80, 18)
    check(
        f"position_to_corner_offsets recovers the same corner for {corner}",
        round_trip_corner == corner,
        (corner, round_trip_corner),
    )
    check(
        f"position_to_corner_offsets recovers the same offsets for {corner}",
        (h, v) == (5, -5),
        (corner, h, v),
    )

dropped_corner, dropped_h, dropped_v = logo_mod.position_to_corner_offsets(0, 0, 1280, 720, 80, 80, 18)
check("dropping at the top-left of the screen resolves to the top-left corner", dropped_corner == "top-left", dropped_corner)
check(
    "an out-of-range dropped offset is clamped to the supported range",
    logo_mod.position_to_corner_offsets(-9999, -9999, 1280, 720, 80, 80, 18) == ("top-left", -240, -240),
)


section("Logo Studio v1: size/opacity percent mapping")
check("minimum size maps to 0%", logo_mod.logo_size_to_percent(32) == 0)
check("maximum size maps to 100%", logo_mod.logo_size_to_percent(256) == 100)
check("0% maps back to the minimum size", logo_mod.logo_percent_to_size(0) == 32)
check("100% maps back to the maximum size", logo_mod.logo_percent_to_size(100) == 256)
check("opacity 0.75 maps to 75%", logo_mod.logo_opacity_to_percent(0.75) == 75)
check("75% maps back to opacity 0.75", logo_mod.logo_percent_to_opacity(75) == 0.75)


section("Logo Studio v1: timing presets are real settings, not invented ones")
check("there are at least the 3 core + 6 new presets the spec asked for", len(logo_mod.LOGO_TIMING_PRESETS) == 9)
for preset in logo_mod.LOGO_TIMING_PRESETS:
    fade = preset["fade"] if preset["fade"] is not None else True
    round_trip = logo_mod.logo_timing_preset_for_settings(preset["timing"], fade)
    check(f"preset '{preset['id']}' round-trips through its own timing+fade", round_trip == preset["id"], round_trip)
    # Every field a preset sets is one normalize_timing already understands --
    # nothing here invents a setting the overlay doesn't read.
    check(
        f"preset '{preset['id']}' timing normalizes to itself (no unknown/invalid fields)",
        logo_mod.normalize_timing(preset["timing"]) == preset["timing"],
    )
check("an unknown preset id returns None, not a crash", logo_mod.logo_timing_preset_by_id("not-a-real-preset") is None)
check(
    "a hand-tuned timing combo that matches no preset returns None",
    logo_mod.logo_timing_preset_for_settings({"on_channel_tune": True, "periodic": True, "duration_seconds": 47}, True) is None,
)


section("Logo Studio v1: randomized periodic interval (real playback extension)")
check(
    "normalize_timing turns off random_interval when periodic itself is off",
    logo_mod.normalize_timing({"periodic": False, "random_interval": True})["random_interval"] is False,
)
check(
    "normalize_timing clamps interval_max below interval_min up to interval_min",
    logo_mod.normalize_timing({"interval_min_minutes": 20, "interval_max_minutes": 5})["interval_max_minutes"] == 20,
)


class _FixedRng:
    """Deterministic stand-in for the `random` module in pick_periodic_interval_minutes."""

    def __init__(self, value):
        self.value = value

    def uniform(self, lo, hi):
        return self.value


fixed_timing = {"random_interval": False, "periodic_interval_minutes": 12}
check(
    "fixed (non-random) mode always returns the configured interval",
    logo_mod.pick_periodic_interval_minutes(fixed_timing) == 12,
)
random_timing = {"random_interval": True, "interval_min_minutes": 3, "interval_max_minutes": 12}
check(
    "random mode draws from the injected rng, not the real random module",
    logo_mod.pick_periodic_interval_minutes(random_timing, rng=_FixedRng(7)) == 7,
)
check(
    "random mode without an injected rng still returns a value in range (uses real random)",
    3 <= logo_mod.pick_periodic_interval_minutes(random_timing) <= 12,
)


section("show exclusions: storage helpers")
check("empty/invalid input normalizes to an empty list", logo_mod.normalize_show_exclusions(None) == [])
check("blanks and duplicates are dropped, order preserved", logo_mod.normalize_show_exclusions(["a", "", "b", "a", "  "]) == ["a", "b"])

exclusion_settings = app.normalize_channel_bug_settings({
    "channel_overrides": {
        "Movies": {"mode": "global", "excluded_shows": ["show-a", "show-a"]},
        "News": {"mode": "off"},
    },
})
check(
    "excluded shows are readable even when the channel's mode is Default (global)",
    logo_mod.channel_logo_excluded_shows(exclusion_settings, "Movies") == ["show-a"],
)
check("a channel with no override has no exclusions", logo_mod.channel_logo_excluded_shows(exclusion_settings, "News") == [])
check("a channel that was never mentioned at all has no exclusions", logo_mod.channel_logo_excluded_shows(exclusion_settings, "Nowhere") == [])


section("show exclusions: is_show_excluded")
check("an excluded key is excluded", logo_mod.is_show_excluded(["a", "b"], "b") is True)
check("a non-excluded key is not excluded", logo_mod.is_show_excluded(["a", "b"], "c") is False)
check("a missing/blank show key fails safe -- never excluded", logo_mod.is_show_excluded(["a", "b"], "") is False)
check("a missing/blank show key fails safe even with no exclusion list at all", logo_mod.is_show_excluded([], "") is False)


section("commercial/Vault visibility gate: logo_should_be_visible")
check("content, logo enabled -> eligible", logo_mod.logo_should_be_visible(True, False, False, False) is True)
check("logo disabled entirely -> never eligible", logo_mod.logo_should_be_visible(False, False, False, False) is False)
check("commercial segment -> not eligible, regardless of timing mode", logo_mod.logo_should_be_visible(True, True, False, False) is False)
check("Vault (on-demand) playback -> not eligible", logo_mod.logo_should_be_visible(True, False, True, False) is False)
check("an excluded show -> not eligible", logo_mod.logo_should_be_visible(True, False, False, True) is False)
check("commercial AND Vault at once -> still not eligible (not exclusive states)", logo_mod.logo_should_be_visible(True, True, True, False) is False)
check("returning to normal content -> eligible again", logo_mod.logo_should_be_visible(True, False, False, False) is True)


section("ChannelBugOverlay: suppression wiring (source-level -- no QApplication needed)")
overlay_source = inspect.getsource(app.ChannelBugOverlay)
check("the overlay has a real set_suppressed method", "def set_suppressed(self, suppressed):" in overlay_source)
check(
    "suppression is enforced at the single show/hide choke point, not duplicated per trigger",
    "if self._suppressed:\n            show = False" in overlay_source,
)
check("suppressing hard-hides immediately, no fade (can't be caught mid-fade over a commercial)", overlay_source.count("self._fade_timer.stop()") >= 2)

check("configure_channel_bug syncs suppression right after a channel tune", "self._sync_channel_bug_suppression()" in inspect.getsource(app.ChannelSurfer.configure_channel_bug))
check(
    "a lightweight periodic timer catches a commercial/Vault transition mid-viewing, not just at tune",
    "_channel_bug_suppression_timer" in inspect.getsource(app.ChannelSurfer),
)

suppression_source = inspect.getsource(app.ChannelSurfer._sync_channel_bug_suppression)
check("suppression checks the real commercial-playback flag", "_is_currently_commercial" in suppression_source)
check("suppression checks Vault (on-demand) playback mode", 'playback_mode == "ondemand"' in suppression_source)
check("suppression checks per-channel show exclusions", "channel_logo_excluded_shows" in suppression_source and "is_show_excluded" in suppression_source)


section("Timing dropdown: trimmed public preset list")
_REMOVED_DROPDOWN_IDS = ("mostly_hidden", "classic_cable_bug", "network_promo", "show_start_plus_random")
check(
    "the trimmed dropdown list is exactly the 5 simple presets the spec asked for",
    logo_mod.LOGO_TIMING_PRESETS_DROPDOWN_IDS == ("always", "show_start", "interval", "random_pop_in", "random_short_bumps"),
    logo_mod.LOGO_TIMING_PRESETS_DROPDOWN_IDS,
)
for removed_id in _REMOVED_DROPDOWN_IDS:
    check(f"'{removed_id}' is not in the trimmed dropdown list", removed_id not in logo_mod.LOGO_TIMING_PRESETS_DROPDOWN_IDS)
    check(f"'{removed_id}' still exists in the real preset table (old saved settings still resolve)", logo_mod.logo_timing_preset_by_id(removed_id) is not None)
for kept_id in logo_mod.LOGO_TIMING_PRESETS_DROPDOWN_IDS:
    check(f"'{kept_id}' still resolves to a real preset", logo_mod.logo_timing_preset_by_id(kept_id) is not None)
check(
    "every LOGO_TIMING_PRESETS entry still exists (the dropdown filter doesn't shrink the real table)",
    len(logo_mod.LOGO_TIMING_PRESETS) == 9,
    len(logo_mod.LOGO_TIMING_PRESETS),
)
# A channel using a removed preset should still resolve to that preset id from the
# real lookup (so its status text stays honest) -- only the dropdown hides it.
removed_preset = logo_mod.logo_timing_preset_by_id("classic_cable_bug")
fade_value = removed_preset["fade"] if removed_preset["fade"] is not None else True
check(
    "a channel using a removed preset still round-trips to its real id outside the dropdown",
    logo_mod.logo_timing_preset_for_settings(removed_preset["timing"], fade_value) == "classic_cable_bug",
)


print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All channel logo smoke tests passed.")

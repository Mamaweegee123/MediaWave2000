"""
Smoke tests for channel logo settings helpers.
Run from the repo root:  venv/bin/python3 tools/test_channel_logos.py
No GUI launch required.
"""
import inspect
import os
import sys
import tempfile

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


section("Logo Studio v2: freeform normalized position (replaces corner-snap for the editor)")
check(
    "pos_x/pos_y 0.5/0.5 centers the logo in the available room",
    logo_mod.resolve_freeform_position(0.5, 0.5, 1280, 720, 80, 80) == (600.0, 320.0),
)
check(
    "pos_x/pos_y 0.0/0.0 sits flush at the top-left, no margin",
    logo_mod.resolve_freeform_position(0.0, 0.0, 1280, 720, 80, 80) == (0.0, 0.0),
)
check(
    "pos_x/pos_y 1.0/1.0 sits flush at the bottom-right, no margin",
    logo_mod.resolve_freeform_position(1.0, 1.0, 1280, 720, 80, 80) == (1200.0, 640.0),
)
check(
    "out-of-range normalized coordinates are clamped to [0.0, 1.0]",
    logo_mod.resolve_freeform_position(-5, 5, 1280, 720, 80, 80) == (0.0, 640.0),
)
check(
    "a screen with no room to move (logo fills it) still resolves without dividing by zero",
    logo_mod.resolve_freeform_position(0.5, 0.5, 80, 80, 80, 80) == (0.0, 0.0),
)

for px, py in ((0.0, 0.0), (0.25, 0.75), (1.0, 1.0), (0.5, 0.5)):
    x, y = logo_mod.resolve_freeform_position(px, py, 1280, 720, 80, 80)
    round_trip = logo_mod.position_to_normalized(x, y, 1280, 720, 80, 80)
    check(
        f"position_to_normalized round-trips pos_x/pos_y ({px}, {py})",
        round_trip == (px, py),
        round_trip,
    )
check(
    "position_to_normalized reports the midpoint when there's no room to move",
    logo_mod.position_to_normalized(0, 0, 80, 80, 80, 80) == (0.5, 0.5),
)

freeform_eff = {"pos_x": 0.25, "pos_y": 0.75, "corner": "bottom-right", "margin": 18}
check(
    "resolve_effective_logo_position prefers freeform pos_x/pos_y when present",
    logo_mod.resolve_effective_logo_position(freeform_eff, 1280, 720, 80, 80)
    == logo_mod.resolve_freeform_position(0.25, 0.75, 1280, 720, 80, 80),
)
legacy_eff = {"corner": "bottom-right", "horizontal_offset": 0, "vertical_offset": 0, "margin": 18}
check(
    "resolve_effective_logo_position falls back to corner/margin/offset when no freeform position is stored",
    logo_mod.resolve_effective_logo_position(legacy_eff, 1280, 720, 80, 80)
    == logo_mod.resolve_logo_position("bottom-right", 0, 0, 1280, 720, 80, 80, 18),
)
partial_eff = {"pos_x": 0.5, "corner": "top-left", "horizontal_offset": 0, "vertical_offset": 0, "margin": 18}
check(
    "a half-set freeform position (only pos_x, no pos_y) doesn't take effect -- falls back to corner math",
    logo_mod.resolve_effective_logo_position(partial_eff, 1280, 720, 80, 80)
    == logo_mod.resolve_logo_position("top-left", 0, 0, 1280, 720, 80, 80, 18),
)


section("Logo Studio v2: aspect-preserving logo sizing (no more stretching to a forced square)")
check("a square source logo stays square", logo_mod.scale_logo_dimensions(200, 200, 80) == (80, 80))
check("a wide source logo is bounded by width, height shrinks proportionally", logo_mod.scale_logo_dimensions(400, 200, 80) == (80, 40))
check("a tall source logo is bounded by height, width shrinks proportionally", logo_mod.scale_logo_dimensions(200, 400, 80) == (40, 80))
check("a zero/invalid natural size fails safe, never crashes", logo_mod.scale_logo_dimensions(0, 0, 80) == (80, 80))


section("Logo Studio v2: 4:3 / 16:9 screen shape -- a real per-channel setting")
check("an unset aspect normalizes to 16:9", logo_mod.normalize_screen_aspect(None) == "16:9")
check("an invalid aspect value falls back to 16:9", logo_mod.normalize_screen_aspect("21:9") == "16:9")
check("4:3 is accepted as-is", logo_mod.normalize_screen_aspect("4:3") == "4:3")
check("16:9 dimensions are (16, 9)", logo_mod.screen_aspect_dimensions("16:9") == (16, 9))
check("4:3 dimensions are (4, 3)", logo_mod.screen_aspect_dimensions("4:3") == (4, 3))

aspect_settings = app.normalize_channel_bug_settings({
    "channel_overrides": {
        "Movies": {"mode": "global", "screen_aspect": "4:3"},
        "News": {"mode": "custom"},
    },
})
check(
    "screen_aspect is readable even when the channel's logo mode is Default (global)",
    logo_mod.channel_logo_screen_aspect(aspect_settings, "Movies") == "4:3",
)
check("a channel with no screen_aspect set defaults to 16:9", logo_mod.channel_logo_screen_aspect(aspect_settings, "News") == "16:9")
check("a channel never mentioned at all defaults to 16:9", logo_mod.channel_logo_screen_aspect(aspect_settings, "Nowhere") == "16:9")

default_aspect_settings = app.normalize_channel_bug_settings({
    "channel_overrides": {"Sports": {"mode": "global", "screen_aspect": "16:9"}},
})
check(
    "setting screen_aspect back to the default (16:9) isn't stored as override noise",
    "screen_aspect" not in default_aspect_settings["channel_overrides"].get("Sports", {}),
)


section("Logo Studio v2: active placement rectangle (4:3/16:9 shape inside a fixed-size preview)")
check(
    "16:9 active rect fills the full wide preview area (matches the widget's own natural shape)",
    logo_mod.compute_active_screen_rect(1280, 720, 16, 9) == (0, 0, 1280, 720),
)
check(
    "4:3 active rect is centered and narrower than the 16:9 widget it sits inside",
    logo_mod.compute_active_screen_rect(1280, 720, 4, 3) == (160, 0, 960, 720),
)
_active_16x9 = logo_mod.compute_active_screen_rect(1280, 720, 16, 9)
_active_4x3 = logo_mod.compute_active_screen_rect(1280, 720, 4, 3)
check("the 4:3 active rect is narrower than the 16:9 active rect", _active_4x3[2] < _active_16x9[2])
check("the 4:3 active rect keeps the full widget height (pillarboxed, not letterboxed)", _active_4x3[3] == 720)
check(
    "the 4:3 active rect is horizontally centered inside the widget",
    _active_4x3[0] == (1280 - _active_4x3[2]) / 2,
)
check(
    "an aspect wider than the box letterboxes instead (shorter, centered vertically, full width)",
    logo_mod.compute_active_screen_rect(800, 600, 21, 9) == (0, 129, 800, 343),
)
check("a zero/invalid size fails safe, never crashes", logo_mod.compute_active_screen_rect(0, 0, 16, 9) == (0, 0, 1, 1))


section("resolve_channel_bug_canvas_rect: the ONE shared canvas resolver for editor + live playback")
check(
    "16:9 canvas matches compute_active_screen_rect(..., 16, 9) directly",
    logo_mod.resolve_channel_bug_canvas_rect(1280, 720, "16:9") == logo_mod.compute_active_screen_rect(1280, 720, 16, 9),
)
check(
    "4:3 canvas matches compute_active_screen_rect(..., 4, 3) directly",
    logo_mod.resolve_channel_bug_canvas_rect(1280, 720, "4:3") == logo_mod.compute_active_screen_rect(1280, 720, 4, 3),
)
check(
    "an unset/None screen_aspect defaults to 16:9, same as normalize_screen_aspect",
    logo_mod.resolve_channel_bug_canvas_rect(1280, 720, None) == logo_mod.compute_active_screen_rect(1280, 720, 16, 9),
)
_bug_canvas_4x3 = logo_mod.resolve_channel_bug_canvas_rect(1920, 1080, "4:3")
check("a 4:3 canvas inside a wider real-world 1920x1080 target is still centered and pillarboxed", _bug_canvas_4x3 == logo_mod.compute_active_screen_rect(1920, 1080, 4, 3))
check("that 4:3 canvas is narrower than the full 1920 width (genuinely constrained, not the whole widget)", _bug_canvas_4x3[2] < 1920)


section("ChannelBugOverlay: screen_aspect actually constrains live playback (source-level -- no QApplication needed)")
overlay_paint_source = inspect.getsource(app.ChannelBugOverlay.paintEvent)
check(
    "paintEvent narrows the target rect using the channel's own screen_aspect before positioning the logo -- "
    "this is the actual fix: previously screen_aspect was read only by the Logo Studio editor, never live playback",
    "channel_logo_screen_aspect(" in overlay_paint_source and "resolve_channel_bug_canvas_rect(" in overlay_paint_source,
    overlay_paint_source,
)
check(
    "the narrowed canvas rect (not the raw video/display rect) is what gets handed to resolve_effective_logo_position",
    "resolve_effective_logo_position(self._eff, target.width(), target.height()" in overlay_paint_source,
    overlay_paint_source,
)


section("Logo Studio v2: freeform clamping + normalization respect the ACTIVE rect, not the full widget")
_ax, _ay, _aw, _ah = logo_mod.compute_active_screen_rect(1280, 720, 4, 3)  # (160, 0, 960, 720)
check(
    "dragging to the bottom-right in the 4:3 active area stays inside that area's own room, not the wider 16:9 widget",
    logo_mod.resolve_freeform_position(1.0, 1.0, _aw, _ah, 80, 80) == (880.0, 640.0),
)
for px, py in ((0.0, 0.0), (0.25, 0.75), (0.5, 0.5), (1.0, 1.0)):
    x, y = logo_mod.resolve_freeform_position(px, py, _aw, _ah, 80, 80)
    check(f"a freeform position ({px}, {py}) resolved against the 4:3 active area never leaves that area's own bounds", 0 <= x <= _aw - 80 and 0 <= y <= _ah - 80, (x, y))

check(
    "the same normalized position (0.75, 0.25) maps to a proportionally equivalent spot in both 16:9 and 4:3 active areas",
    logo_mod.resolve_freeform_position(0.75, 0.25, 1280, 720, 80, 80) == (900.0, 160.0)
    and logo_mod.resolve_freeform_position(0.75, 0.25, _aw, _ah, 80, 80) == (660.0, 160.0),
)

check(
    "center (0.5, 0.5) stays the center of whichever active area is current",
    logo_mod.resolve_freeform_position(0.5, 0.5, 1280, 720, 80, 80) == (600.0, 320.0)
    and logo_mod.resolve_freeform_position(0.5, 0.5, _aw, _ah, 80, 80) == (440.0, 320.0),
)

# Switching 16:9 <-> 4:3 for the SAME stored normalized position: the pixel
# position changes (the active area itself moved/narrowed), but it's always
# contained within whichever active area is now current -- never drifts
# outside it, and switching back to 16:9 returns to the original spot.
_stored_pos = (0.9, 0.1)
_pos_16x9 = logo_mod.resolve_freeform_position(*_stored_pos, 1280, 720, 80, 80)
_pos_4x3 = logo_mod.resolve_freeform_position(*_stored_pos, _aw, _ah, 80, 80)
check("switching to 4:3 keeps the stored position inside the 4:3 active area", 0 <= _pos_4x3[0] <= _aw - 80 and 0 <= _pos_4x3[1] <= _ah - 80)
check("switching back to 16:9 keeps the stored position inside the 16:9 active area", 0 <= _pos_16x9[0] <= 1280 - 80 and 0 <= _pos_16x9[1] <= 720 - 80)
check(
    "round-tripping 16:9 -> 4:3 -> 16:9 recovers the exact original normalized position (no drift)",
    logo_mod.position_to_normalized(*logo_mod.resolve_freeform_position(*_stored_pos, _aw, _ah, 80, 80), _aw, _ah, 80, 80) == _stored_pos,
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


section("find_channel_bug_logo: shared User Content/Logos fallback (unified logo lookup)")

with tempfile.TemporaryDirectory() as tmpdir:
    user_content = os.path.join(tmpdir, "User Content")
    app.ensure_user_content_structure(user_content)
    shared_dir = os.path.join(user_content, "Logos")
    weatherstar_dir = os.path.join(shared_dir, "WeatherStar")
    radiowave_dir = os.path.join(shared_dir, "RadioWave")
    nettv_dir = os.path.join(shared_dir, "NetTV")
    check("companion logo folders are created idempotently", all(os.path.isdir(p) for p in (weatherstar_dir, radiowave_dir, nettv_dir)))
    app.ensure_user_content_structure(user_content)
    check("running User Content structure initialization twice keeps companion folders", all(os.path.isdir(p) for p in (weatherstar_dir, radiowave_dir, nettv_dir)))

    local_root = os.path.join(tmpdir, "MTV")
    local_logos = os.path.join(local_root, "Logos")
    os.makedirs(local_logos)
    local_logo_file = os.path.join(local_logos, "MTV.png")
    with open(local_logo_file, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")

    weatherstar_folder_logo = os.path.join(weatherstar_dir, "logo.png")
    with open(weatherstar_folder_logo, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    radiowave_folder_logo = os.path.join(radiowave_dir, "logo.webp")
    with open(radiowave_folder_logo, "wb") as f:
        f.write(b"RIFFxxxxWEBP")
    nettv_folder_logo = os.path.join(nettv_dir, "only-image.bmp")
    with open(nettv_folder_logo, "wb") as f:
        f.write(b"BM")
    shared_logo_file = os.path.join(shared_dir, "WeatherStar 4000+.png")
    with open(shared_logo_file, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    weatherstar_alias_file = os.path.join(shared_dir, "WeatherStar.png")
    with open(weatherstar_alias_file, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    radiowave_alias_file = os.path.join(shared_dir, "RadioWave.png")
    with open(radiowave_alias_file, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    nettv_logo_file = os.path.join(shared_dir, "NetTV.png")
    with open(nettv_logo_file, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    # A decoy for a DIFFERENT channel, to prove the shared-folder lookup
    # never falls back to "just grab whatever's in here" the way a
    # single-channel folder does.
    with open(os.path.join(shared_dir, "RadioWaveTV.png"), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")

    check(
        "a local channel's own root_path/Logos/ still wins when present -- no behavior change",
        logo_mod.find_channel_bug_logo(local_root, "MTV", shared_logos_dir=shared_dir) == local_logo_file,
    )
    check(
        "WeatherStar playback resolves the new stable companion folder logo.png first",
        logo_mod.find_channel_bug_logo(
            "",
            "WeatherStar 4000+",
            shared_logos_dir=shared_dir,
            channel_id="special:weatherstar",
            channel_type="weatherstar",
            display_name="WeatherStar 4000+",
        ) == weatherstar_folder_logo,
    )
    check(
        "companion folder source is reported before legacy shared-root aliases",
        logo_mod.channel_bug_logo_lookup_details(
            "",
            "WeatherStar 4000+",
            shared_logos_dir=shared_dir,
            channel_id="special:weatherstar",
            channel_type="weatherstar",
        )["source"] == "companion-folder",
    )
    check(
        "renamed WeatherStar still uses the stable WeatherStar logo folder",
        logo_mod.find_channel_bug_logo(
            "",
            "Local Weather",
            shared_logos_dir=shared_dir,
            channel_id="special:weatherstar",
            channel_type="weatherstar",
            display_name="Local Weather",
        ) == weatherstar_folder_logo,
    )
    check(
        "RadioWave resolves its own stable companion logo folder",
        logo_mod.find_channel_bug_logo(
            "",
            "Studio Jukebox",
            shared_logos_dir=shared_dir,
            channel_id="special:radiowave",
            channel_type="radiowave",
            display_name="Studio Jukebox",
        ) == radiowave_folder_logo,
    )
    check(
        "NetTV resolves exactly one supported image in its stable companion logo folder",
        logo_mod.find_channel_bug_logo(
            "",
            "Playlist Channel",
            shared_logos_dir=shared_dir,
            channel_id="special:youtube",
            channel_type="youtube",
            display_name="Playlist Channel",
        ) == nettv_folder_logo,
    )
    os.remove(weatherstar_folder_logo)
    check(
        "removing the companion-folder logo falls back to the legacy shared-root alias",
        logo_mod.find_channel_bug_logo(
            "",
            "WeatherStar 4000+",
            shared_logos_dir=shared_dir,
            channel_id="special:weatherstar",
            channel_type="weatherstar",
        ) == shared_logo_file,
    )
    with open(weatherstar_folder_logo, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\nreplacement")
    check(
        "a companion channel (no root_path) resolves from its stable folder by name",
        logo_mod.find_channel_bug_logo("", "WeatherStar 4000+", shared_logos_dir=shared_dir) == weatherstar_folder_logo,
    )
    check(
        "WeatherStar shared logo resolves in the live playback identity path",
        logo_mod.find_channel_bug_logo(
            "",
            "WeatherStar 4000+",
            shared_logos_dir=shared_dir,
            channel_id="special:weatherstar",
            channel_type="weatherstar",
            display_name="WeatherStar 4000+",
        ) == weatherstar_folder_logo,
    )
    check(
        "WeatherStar user logo wins before rendered fallback would be needed",
        logo_mod.channel_bug_logo_lookup_details(
            "",
            "WeatherStar 4000+",
            shared_logos_dir=shared_dir,
            channel_id="special:weatherstar",
            channel_type="weatherstar",
        )["source"] == "companion-folder",
    )
    check(
        "renamed WeatherStar still finds the canonical shared logo alias",
        logo_mod.find_channel_bug_logo(
            "",
            "WeatherStar 4000+",
            shared_logos_dir=shared_dir,
            channel_id="special:weatherstar",
            channel_type="weatherstar",
            display_name="Local Forecast",
        ) == weatherstar_folder_logo,
    )
    check(
        "WeatherStar alias lookup can fall back from 4000+ to WeatherStar.png",
        logo_mod.find_channel_bug_logo(
            "",
            "Local Forecast",
            shared_logos_dir=shared_dir,
            channel_id="special:weatherstar",
            channel_type="weatherstar",
            display_name="Local Forecast",
        ) == weatherstar_folder_logo,
    )
    os.remove(shared_logo_file)
    check(
        "WeatherStar companion folder still takes precedence when 4000+ is absent",
        logo_mod.find_channel_bug_logo(
            "",
            "Local Forecast",
            shared_logos_dir=shared_dir,
            channel_id="special:weatherstar",
            channel_type="weatherstar",
            display_name="Local Forecast",
        ) == weatherstar_folder_logo,
    )
    os.remove(weatherstar_folder_logo)
    check(
        "WeatherStar shared alias WeatherStar.png resolves when the companion folder has no logo",
        logo_mod.find_channel_bug_logo(
            "",
            "Local Forecast",
            shared_logos_dir=shared_dir,
            channel_id="special:weatherstar",
            channel_type="weatherstar",
            display_name="Local Forecast",
        ) == weatherstar_alias_file,
    )
    with open(shared_logo_file, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    check(
        "RadioWave shared logo resolves by companion alias",
        logo_mod.find_channel_bug_logo(
            "",
            "Studio Jukebox",
            shared_logos_dir=shared_dir,
            channel_id="special:radiowave",
            channel_type="radiowave",
            display_name="Studio Jukebox",
        ) == radiowave_folder_logo,
    )
    os.remove(radiowave_folder_logo)
    os.remove(os.path.join(shared_dir, "RadioWaveTV.png"))
    check(
        "RadioWave.png shared alias resolves when RadioWaveTV.png is absent",
        logo_mod.find_channel_bug_logo(
            "",
            "Studio Jukebox",
            shared_logos_dir=shared_dir,
            channel_id="special:radiowave",
            channel_type="radiowave",
            display_name="Studio Jukebox",
        ) == radiowave_alias_file,
    )
    check(
        "NetTV shared logo resolves by companion alias",
        logo_mod.find_channel_bug_logo(
            "",
            "Playlist Channel",
            shared_logos_dir=shared_dir,
            channel_id="special:youtube",
            channel_type="youtube",
            display_name="Playlist Channel",
        ) == nettv_folder_logo,
    )
    os.remove(nettv_folder_logo)
    check(
        "NetTV shared root alias resolves after the stable folder image is removed",
        logo_mod.find_channel_bug_logo(
            "",
            "Playlist Channel",
            shared_logos_dir=shared_dir,
            channel_id="special:youtube",
            channel_type="youtube",
            display_name="Playlist Channel",
        ) == nettv_logo_file,
    )
    check(
        "omitting shared_logos_dir entirely still works exactly as before (backward compatible signature)",
        logo_mod.find_channel_bug_logo(local_root, "MTV") == local_logo_file,
    )
    check(
        "a shared-folder miss (no matching name) fails safe -- empty string, no crash, and does NOT grab an unrelated channel's logo",
        logo_mod.find_channel_bug_logo("", "Unknown Channel", shared_logos_dir=shared_dir) == "",
    )
    check(
        "a channel with neither a local Logos/ folder nor a shared-folder match fails safe",
        logo_mod.find_channel_bug_logo("", "", shared_logos_dir=shared_dir) == "",
    )
    check(
        "a nonexistent shared_logos_dir fails safe, no crash",
        logo_mod.find_channel_bug_logo("", "WeatherStar 4000+", shared_logos_dir=os.path.join(tmpdir, "does-not-exist")) == "",
    )

check(
    "ensure_user_content_structure creates the shared Logos/ folder",
    "Logos" in inspect.getsource(app.ensure_user_content_structure),
)
check(
    "app startup creates the shared Logos folder unconditionally, not just on first run",
    "ensure_user_content_structure(default_mediawave_user_dir())" in inspect.getsource(app.ChannelSurfer.__init__),
)
check(
    "real playback's channel bug lookup uses the channel's stable folder_name, not the live (possibly renamed) name",
    "folder_name" in inspect.getsource(app.ChannelSurfer.configure_channel_bug),
)
configure_source = inspect.getsource(app.ChannelSurfer.configure_channel_bug)
check(
    "real playback passes stable companion id/type/display name into the shared logo lookup",
    "channel_id=channel_id" in configure_source and "channel_type=channel_type" in configure_source and "display_name=display_name" in configure_source,
)
cache_source = inspect.getsource(app.load_channel_bug_pixmap)
check(
    "playback logo cache no longer stores misses forever",
    "_CHANNEL_BUG_CACHE[cache_key] = None" not in cache_source,
)
check(
    "playback logo cache keys include the resolved file signature for retune refresh",
    "st_mtime_ns" in cache_source and "st_size" in cache_source,
)

print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All channel logo smoke tests passed.")

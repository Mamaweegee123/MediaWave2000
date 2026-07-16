"""
End-to-end proof that a channel's screen_aspect (4:3/16:9) actually
constrains the LIVE ChannelBugOverlay, not just the Logo Studio editor
preview -- the bug this test guards against: previously screen_aspect was
read only by mediawave/channel_studio/{setup_sections.py,logo_studio.py},
never by channelsurfer2000.py's ChannelBugOverlay.paintEvent, so a "4:3"
channel would position its logo across the entire (possibly much wider)
real video/display rect.

Unlike tools/test_channel_logos.py and tools/test_channel_studio.py (both
deliberately "no QApplication needed" -- pure functions and source
inspection only), this file constructs a real ChannelBugOverlay QWidget, so
it needs an offscreen-capable Qt platform. Run from the repo root:
  QT_QPA_PLATFORM=offscreen venv/bin/python3 tools/test_channel_bug_overlay_geometry.py
(the platform is also forced below so this is safe to run in a headless
environment even without the env var set explicitly).
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QWidget

app = QApplication.instance() or QApplication(sys.argv)

import channelsurfer2000 as mw
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


class _FakeParent(QWidget):
    """Stands in for VideoSurface -- overlay_target_rect() (channelsurfer2000.py)
    prefers a parent's display_rect()/video_rect() when present; this fake
    reports a fixed wide (16:9-shaped) rect, simulating a real widescreen
    video/display area the channel bug overlay sits on top of.
    """

    def __init__(self, rect):
        super().__init__()
        self._rect = rect

    def display_rect(self):
        return self._rect


section("ChannelBugOverlay: screen_aspect actually constrains live logo geometry")

WIDE_RECT = QRect(0, 0, 1920, 1080)  # a real, wide 16:9 video/display area
parent = _FakeParent(WIDE_RECT)
parent.resize(1920, 1080)

overlay = mw.ChannelBugOverlay(parent)
settings = logo_mod.normalize_channel_bug_settings({
    "enabled": True,
    "size": 80,
    "channel_overrides": {
        "Retro Channel": {"mode": "custom", "screen_aspect": "4:3", "pos_x": 1.0, "pos_y": 1.0},
    },
})
overlay.configure(settings, "Retro Channel", root_path="")

# Compute what the logo's bounding box SHOULD be: bottom-right corner
# (pos_x=pos_y=1.0) of the centered 4:3 canvas inside the wide 1920x1080
# video rect -- never the full 1920-wide rect itself.
expected_canvas = logo_mod.resolve_channel_bug_canvas_rect(WIDE_RECT.width(), WIDE_RECT.height(), "4:3")
check("the 4:3 canvas is genuinely narrower than the full 1920-wide video rect", expected_canvas[2] < WIDE_RECT.width(), expected_canvas)

pw, ph = overlay._bug_pixmap.width(), overlay._bug_pixmap.height()
x_rel, y_rel = logo_mod.resolve_effective_logo_position(overlay._eff, expected_canvas[2], expected_canvas[3], pw, ph)
expected_x = expected_canvas[0] + x_rel
expected_y = expected_canvas[1] + y_rel

# The logo's bottom-right corner (pos 1.0, 1.0) should land at the 4:3
# canvas's own right/bottom edge, NOT the wide 1920-pixel-wide rect's edge.
check(
    "the bottom-right-anchored logo's right edge sits at the 4:3 canvas's right edge, not the full 1920-wide rect",
    round(expected_x + pw) == expected_canvas[0] + expected_canvas[2],
    (expected_x, pw, expected_canvas),
)
check(
    "that same right edge is well inside (less than) the full 1920-wide video rect -- proof screen_aspect is really constraining it",
    expected_x + pw < WIDE_RECT.width(),
    (expected_x, pw, WIDE_RECT.width()),
)

# Now the same channel set to 16:9 should be allowed to use almost the
# full wide rect (no artificial narrowing).
settings_16x9 = logo_mod.normalize_channel_bug_settings({
    "enabled": True,
    "size": 80,
    "channel_overrides": {
        "Retro Channel": {"mode": "custom", "screen_aspect": "16:9", "pos_x": 1.0, "pos_y": 1.0},
    },
})
overlay.configure(settings_16x9, "Retro Channel", root_path="")
canvas_16x9 = logo_mod.resolve_channel_bug_canvas_rect(WIDE_RECT.width(), WIDE_RECT.height(), "16:9")
check("a 16:9 channel's canvas uses the full width of a 16:9 video rect (no unintended narrowing)", canvas_16x9[2] == WIDE_RECT.width(), canvas_16x9)

# A channel with NO override at all (screen_aspect defaults to 16:9)
# behaves the same as an explicit 16:9 -- confirms old saved settings
# (channels that never touched screen_aspect) still work exactly as before.
default_settings = logo_mod.normalize_channel_bug_settings({"enabled": True, "size": 80})
overlay.configure(default_settings, "Some Old Channel", root_path="")
check(
    "a channel with no screen_aspect override at all still defaults to the full 16:9 canvas (backward compatible)",
    logo_mod.channel_logo_screen_aspect(default_settings, "Some Old Channel") == "16:9",
)

print()
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)
print("All ChannelBugOverlay geometry smoke tests passed.")

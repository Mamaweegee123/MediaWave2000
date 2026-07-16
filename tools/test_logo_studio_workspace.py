"""
End-to-end proof that Logo Studio's workspace layout pass (widened window,
hero preview, clickable logo source card, 16:9/4:3 beneath the preview,
grouped/de-duplicated controls) actually holds together as real Qt widgets
-- not just as source text. Companion to tools/test_channel_studio.py's
source-level checks for the same change.

Unlike tools/test_channel_studio.py and tools/test_channel_logos.py
(deliberately "no QApplication needed"), this file constructs real
LogoStudioDialog/build_logo_section widgets, so it needs an
offscreen-capable Qt platform. Run from the repo root:
  QT_QPA_PLATFORM=offscreen venv/bin/python3 tools/test_logo_studio_workspace.py
(the platform is also forced below so this is safe to run headless even
without the env var set explicitly).
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from PySide6.QtCore import QEventLoop, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.channel_studio.logo_studio_dialog import LogoStudioDialog
from mediawave.channel_studio.setup_sections import _LogoSourceCard, build_logo_section
from mediawave.channel_studio.logo_studio import LogoPreviewScreen

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


def _pump():
    for _ in range(3):
        app.processEvents(QEventLoop.AllEvents)


class _FakeDialog:
    pass


def _build_page(channel_info=None):
    channel_info = channel_info or {"id": "local:movies", "name": "Movies", "default_number": 1, "root_path": "/tmp"}
    page = build_logo_section(_FakeDialog(), channel_info, None)
    page.resize(1360, 780)
    page.show()
    _pump()
    return page


section("LogoStudioDialog: default and minimum window size fit the widened workspace")

dlg = LogoStudioDialog(_FakeDialog(), {"id": "local:movies", "name": "Movies", "default_number": 1, "root_path": "/tmp"}, None, parent=None)
check("default window width is wide enough for a hero preview + grouped controls", dlg.width() >= 1300, dlg.width())
check("minimum window size is set (a floor below which scrolling, not clipping, takes over)", dlg.minimumWidth() >= 1000, dlg.minimumWidth())

section("build_logo_section: exactly one no-logo source card, no leftover duplicate messaging")

page = _build_page()
source_cards = page.findChildren(_LogoSourceCard)
check("exactly one logo source card exists", len(source_cards) == 1, len(source_cards))
check("the no-logo source card invites the user to add a logo", source_cards[0]._title_lbl.text() == "No channel logo yet")

all_texts = [lbl.text() for lbl in page.findChildren(QLabel) if lbl.text()]
check(
    "the old duplicate 'No logo image found' status card text is gone (now owned solely by the source card)",
    not any("No logo image found" in t for t in all_texts),
)
check(
    "the preview's own empty-state text is restrained, not a second copy of the detailed instructions",
    not any("Place a PNG in your Logos folder" in t for t in all_texts),
)

section("build_logo_section: 16:9/4:3 controls are parented in the preview column, not the controls panel")

scroll_areas = page.findChildren(QScrollArea)
check("the controls panel has exactly one scroll-area fallback wrapper", len(scroll_areas) == 1, len(scroll_areas))
controls_scroll = scroll_areas[0]
shape_buttons = [b for b in page.findChildren(QPushButton) if b.text() in ("16:9", "4:3")]
check("both screen-shape buttons exist", len(shape_buttons) == 2, len(shape_buttons))
check(
    "neither screen-shape button is inside the controls scroll area -- they belong under the preview",
    all(not controls_scroll.isAncestorOf(b) for b in shape_buttons),
)

section("build_logo_section: clicking 16:9/4:3 actually resizes the preview's active aspect")

preview = page.findChildren(LogoPreviewScreen)[0]
initial_aspect = (preview._active_aspect_w, preview._active_aspect_h)
for btn in shape_buttons:
    if btn.text() == "4:3":
        QTest.mouseClick(btn, Qt.LeftButton)
_pump()
check("selecting 4:3 changes the preview's active aspect", (preview._active_aspect_w, preview._active_aspect_h) == (4, 3), (preview._active_aspect_w, preview._active_aspect_h))
for btn in shape_buttons:
    if btn.text() == "16:9":
        QTest.mouseClick(btn, Qt.LeftButton)
_pump()
check("selecting 16:9 changes it back", (preview._active_aspect_w, preview._active_aspect_h) == (16, 9))

section("build_logo_section: the source card is genuinely clickable (whole card, not just a button)")

card = page.findChildren(_LogoSourceCard)[0]
clicked = []
card._on_activated = lambda: clicked.append(True)
QTest.mouseClick(card, Qt.LeftButton, pos=card.rect().center())
_pump()
check("clicking anywhere on the source card invokes its activation callback", clicked == [True])

section("build_logo_section: an existing logo shows current-logo state, not the no-logo state")

pixmap = QPixmap(64, 64)
pixmap.fill(Qt.red)

import mediawave.channel_studio.setup_sections as setup_sections_module
original_resolver = setup_sections_module.resolve_channel_logo_pixmap
original_path_resolver = setup_sections_module.resolve_channel_logo_path
setup_sections_module.resolve_channel_logo_pixmap = lambda dialog, channel_info, summary: pixmap
setup_sections_module.resolve_channel_logo_path = lambda dialog, channel_info, summary: "/tmp/Logos/CineMax logo.png"
try:
    page_with_logo = _build_page()
finally:
    setup_sections_module.resolve_channel_logo_pixmap = original_resolver
    setup_sections_module.resolve_channel_logo_path = original_path_resolver

card_with_logo = page_with_logo.findChildren(_LogoSourceCard)[0]
check("the source card switches to the current-logo state", card_with_logo._title_lbl.text() == "Channel Logo")
check("the current-logo subtitle names the actual file", "CineMax logo.png" in card_with_logo._subtitle_lbl.text())

section("LogoPreviewScreen: 16:9 and 4:3 pillarbox to the same height instead of the canvas growing taller")


def _select(text):
    for b in shape_buttons:
        if b.text() == text:
            QTest.mouseClick(b, Qt.LeftButton)
    _pump()


def _shape_row_top():
    # Any one of the shape buttons' own top edge, mapped into `page`'s
    # coordinate space -- used below to confirm the row beneath the
    # preview doesn't shift when the preview's internal pillarboxing
    # changes width.
    btn = shape_buttons[0]
    return btn.mapTo(page, btn.rect().topLeft()).y()


_select("16:9")
h_169 = preview.height()
w_169 = preview.width()
active_169 = preview.active_rect()
selector_top_169 = _shape_row_top()

_select("4:3")
h_43 = preview.height()
w_43 = preview.width()
active_43 = preview.active_rect()
selector_top_43 = _shape_row_top()

check("16:9 and 4:3 preview widgets report the same overall height", h_169 == h_43, (h_169, h_43))
check("16:9 and 4:3 active-area canvases have the same height", active_169.height() == active_43.height(), (active_169.height(), active_43.height()))
check("the 4:3 active canvas is narrower than the 16:9 active canvas", active_43.width() < active_169.width(), (active_43.width(), active_169.width()))

ratio_169 = active_169.width() / active_169.height()
ratio_43 = active_43.width() / active_43.height()
check("the 16:9 canvas keeps approximately a 16:9 ratio", abs(ratio_169 - (16 / 9)) < 0.05, ratio_169)
check("the 4:3 canvas keeps approximately a 4:3 ratio", abs(ratio_43 - (4 / 3)) < 0.05, ratio_43)

center_169 = active_169.left() + active_169.width() / 2.0
center_43 = active_43.left() + active_43.width() / 2.0
check("both canvases share the same horizontal center within the preview host", abs(center_169 - center_43) <= 1, (center_169, center_43))
check("the 4:3 canvas is horizontally centered within the preview widget", abs(center_43 - w_43 / 2.0) <= 1, (center_43, w_43 / 2.0))
check("both canvases start at the same top edge (y=0)", active_169.top() == 0 and active_43.top() == 0)

check("the aspect selector row doesn't move vertically when switching aspect ratios", selector_top_169 == selector_top_43, (selector_top_169, selector_top_43))

_select("16:9")  # leave shared page/preview state as the other sections expect

section("LogoStudioDialog: switching aspect repeatedly never changes the dialog's own height")

dlg.show()
_pump()
dlg_initial_height = dlg.height()
dlg_shape_buttons = [b for b in dlg.findChildren(QPushButton) if b.text() in ("16:9", "4:3")]
dlg_preview = dlg.findChildren(LogoPreviewScreen)[0]


def _dlg_select(text):
    for b in dlg_shape_buttons:
        if b.text() == text:
            QTest.mouseClick(b, Qt.LeftButton)
    _pump()


for _ in range(3):
    _dlg_select("4:3")
    _dlg_select("16:9")
check("repeated aspect switching never changes the dialog's overall height", dlg.height() == dlg_initial_height, (dlg.height(), dlg_initial_height))

dlg.resize(dlg.width() + 120, dlg.height() + 40)
_pump()
_dlg_select("16:9")
h_169_resized = dlg_preview.height()
_dlg_select("4:3")
h_43_resized = dlg_preview.height()
check("after resizing the window, 16:9 and 4:3 still report the same preview height", h_169_resized == h_43_resized, (h_169_resized, h_43_resized))

section("LogoPreviewScreen: switching aspect never touches the logo's own box (no stretching)")

from mediawave.channel_logos import scale_logo_dimensions

standalone_preview = LogoPreviewScreen()
rect_pixmap = QPixmap(200, 80)  # a clearly non-square source logo
rect_pixmap.fill(Qt.blue)
standalone_preview.resize(600, standalone_preview.heightForWidth(600))
standalone_preview.set_logo(rect_pixmap)
logo_w, logo_h = scale_logo_dimensions(rect_pixmap.width(), rect_pixmap.height(), 80)
standalone_preview.set_geometry_state(10, 10, logo_w, logo_h, 1.0)
logo_box_before = standalone_preview.logo_rect()
standalone_preview.set_aspect(4, 3)
logo_box_43 = standalone_preview.logo_rect()
standalone_preview.set_aspect(16, 9)
logo_box_169 = standalone_preview.logo_rect()
check(
    "the logo's own box size is untouched by an aspect switch",
    (logo_box_before.width(), logo_box_before.height())
    == (logo_box_43.width(), logo_box_43.height())
    == (logo_box_169.width(), logo_box_169.height()),
)
source_ratio = rect_pixmap.width() / rect_pixmap.height()
logo_box_ratio = logo_box_before.width() / logo_box_before.height()
check(
    "the logo box keeps the source image's own aspect ratio, not a stretched one",
    abs(logo_box_ratio - source_ratio) < 0.05,
    (logo_box_ratio, source_ratio),
)

print()
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)
print("All Logo Studio workspace layout smoke tests passed.")

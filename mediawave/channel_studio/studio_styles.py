"""Shared visual helpers for Channel Studio (Preview).

Small, self-contained fixes/helpers reused across the grid, cards, and
channel detail dialog — kept in one place so Channel Studio's look
stays consistent without duplicating the same fix in every file.
"""

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QFrame, QMessageBox, QScrollArea, QStackedWidget

from .channel_studio_dialogs import show_preview_dialog

CHANNEL_NUMBER_COLOR = "#5aff6e"

NOW_COLOR = "#6dffa0"
NEXT_COLOR = "#6fd6ff"
LATER_COLOR = "#c79bff"

SETUP_BUTTON_COLOR = "#6090ff"
REMOVE_BUTTON_COLOR = "#ff5a6e"

_CHANNEL_NUMBER_FONT_CANDIDATES = (
    "Helvetica Neue Condensed Bold",
    "HelveticaNeue-CondensedBold",
    "Arial Narrow",
    "Nimbus Sans Narrow",
    "Liberation Sans Narrow",
)

_channel_number_font_family_cache = None


def _project_root_dir():
    """A safe, project-relative base dir — never a user-specific
    absolute path. Mirrors channelsurfer2000.py's own resource_base_dir()
    (frozen app vs. running from source) without importing that module,
    which would pull in its whole top-level startup path just to load a
    font.
    """
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(sys.executable))
    # mediawave/channel_studio/studio_styles.py -> mediawave -> project root
    this_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(this_dir))


def _find_vhs_osd_font_path():
    """Best-effort, read-only lookup for the app's own VHS/VCR/OSD font
    — the same file used for the classic channel-switching HUD (see
    channelsurfer2000.py's ChannelOverlay/crt_font_family). Never raises.
    """
    root = _project_root_dir()
    for relative in ("Fonts/vhs-vcr-osd.ttf", "fonts/vhs-vcr-osd.ttf"):
        candidate = os.path.join(root, relative)
        if os.path.isfile(candidate):
            return candidate
    return ""


def channel_number_font_family():
    """The channel-switching HUD's own VHS/VCR/OSD font when it can be
    loaded from the project's Fonts folder; otherwise the same
    condensed-bold system-font fallback tier the rest of Channel Studio
    already used, ending in Arial.
    """
    global _channel_number_font_family_cache
    if _channel_number_font_family_cache:
        return _channel_number_font_family_cache

    font_path = _find_vhs_osd_font_path()
    if font_path:
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                _channel_number_font_family_cache = families[0]
                return _channel_number_font_family_cache

    available = set(QFontDatabase.families())
    for family in _CHANNEL_NUMBER_FONT_CANDIDATES:
        if family in available:
            _channel_number_font_family_cache = family
            return family
    _channel_number_font_family_cache = "Arial"
    return _channel_number_font_family_cache


def style_setup_button(button):
    """Blue fill — Channel Studio's consistent "go do something" action."""
    button.setStyleSheet(
        f"""
        QPushButton {{
            background: rgba(96, 144, 255, 220);
            border: 1px solid rgba(140, 175, 255, 230);
            border-radius: 6px;
            color: white;
            font-weight: 600;
            padding: 5px 14px;
        }}
        QPushButton:hover {{
            background: rgba(120, 165, 255, 235);
        }}
        """
    )
    return button


def style_remove_button(button):
    """Red outline — visually distinct from Setup, but not a solid
    alarm-red fill; Remove itself stays a safe, confirmation-gated
    preview action (see confirm_remove_channel).
    """
    button.setStyleSheet(
        f"""
        QPushButton {{
            background: rgba(60, 18, 22, 200);
            border: 1.5px solid rgba(255, 90, 110, 200);
            border-radius: 6px;
            color: {REMOVE_BUTTON_COLOR};
            font-weight: 600;
            padding: 5px 14px;
        }}
        QPushButton:hover {{
            background: rgba(90, 24, 30, 220);
        }}
        """
    )
    return button


def style_choice_button(button, active):
    """One of a row of mutually-exclusive choice buttons (e.g. Commercials
    Setup v2's Default/Off/Custom) — filled and bordered like
    style_setup_button when it's the currently-active choice, a quieter
    outline otherwise, so the user can tell which one is in effect
    without reading the status text above it.
    """
    if active:
        return style_setup_button(button)
    button.setStyleSheet(
        """
        QPushButton {
            background: rgba(255, 255, 255, 12);
            border: 1px solid rgba(255, 255, 255, 60);
            border-radius: 6px;
            color: rgba(230, 235, 250, 220);
            font-weight: 600;
            padding: 5px 14px;
        }
        QPushButton:hover {
            background: rgba(255, 255, 255, 24);
        }
        """
    )
    return button


def schedule_row_badge_style(kind):
    """Inline stylesheet for a colored NOW/NEXT/LATER pill label.
    `kind` is one of "now", "next", "later".
    """
    color = {"now": NOW_COLOR, "next": NEXT_COLOR, "later": LATER_COLOR}.get(kind, NOW_COLOR)
    return (
        f"color: {color};"
        f" background: transparent;"
        f" border: 1px solid {color};"
        " border-radius: 4px;"
        " font-size: 10px;"
        " font-weight: 700;"
        " padding: 1px 6px;"
    )


def build_scroll_area(widget):
    """A QScrollArea whose viewport shows the app's own dark background
    instead of the platform-default gray/white fill.

    Two separate Qt gotchas stack up here: (1) `QScrollArea { background:
    transparent }` in the app-wide QSS never reaches the scroll area's
    internal viewport widget on its own — `setAutoFillBackground(False)`
    is needed too, the same trick the main app's FocusScrollArea uses.
    (2) a plain QWidget (like the page `widget` being scrolled) doesn't
    paint QSS `background` at all unless it opts in via
    `WA_StyledBackground` — the app already has a QSS rule for exactly
    this (`QWidget#advPageContent`), so reusing that object name here
    paints the same dark background instead of adding a new rule.
    """
    widget.setObjectName("advPageContent")
    widget.setAttribute(Qt.WA_StyledBackground, True)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.viewport().setAutoFillBackground(False)
    scroll.setWidget(widget)
    return scroll


class SinglePageStackedWidget(QStackedWidget):
    """A QStackedWidget sized to whichever page is showing, not the
    tallest one. Plain QStackedWidget reports the largest child's
    sizeHint regardless of which page is current, which leaves short
    tabs (Commercials, Identity, Preview) with a lot of dead space
    under the tallest tab (Tonight). Call `updateGeometry()` (done in
    setCurrentIndex here) after switching so layouts re-measure.
    """

    def sizeHint(self):
        current = self.currentWidget()
        return current.sizeHint() if current is not None else super().sizeHint()

    def minimumSizeHint(self):
        current = self.currentWidget()
        return current.minimumSizeHint() if current is not None else super().minimumSizeHint()

    def setCurrentIndex(self, index):
        super().setCurrentIndex(index)
        self.updateGeometry()


def confirm_remove_channel(parent, channel_name):
    """Shared safe "Remove" confirmation. Never deletes anything —
    only ever asks, then reports that removal isn't wired up yet.
    """
    box = QMessageBox(parent)
    box.setWindowTitle(f"Remove {channel_name}?")
    box.setText(
        "This will eventually remove the channel from Channel Studio, not delete your media."
    )
    box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
    box.setDefaultButton(QMessageBox.Cancel)
    if box.exec() == QMessageBox.Yes:
        show_preview_dialog(
            parent,
            "Remove Channel",
            "Removing channels from Channel Studio isn't wired up yet — nothing changed.",
        )


def confirm_disable_companion_channel(parent, channel_name, on_confirm):
    """"Remove" for a companion channel is real, but only ever a real
    Disable — never a delete. Nothing about the channel's configuration
    (location, music folder, playlist URL, ...) is touched, so turning
    it back on later picks up right where it left off.
    """
    box = QMessageBox(parent)
    box.setWindowTitle(f"Disable {channel_name}?")
    box.setText("Disable this companion channel? Your settings will be kept.")
    box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
    box.setDefaultButton(QMessageBox.Cancel)
    if box.exec() == QMessageBox.Yes:
        on_confirm()

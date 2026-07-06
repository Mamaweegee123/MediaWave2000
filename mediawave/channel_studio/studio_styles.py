"""Shared visual helpers for Channel Studio (Preview).

Small, self-contained fixes/helpers reused across the grid, cards, and
channel detail dialog — kept in one place so Channel Studio's look
stays consistent without duplicating the same fix in every file.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QFrame, QMessageBox, QScrollArea, QStackedWidget

from .channel_studio_dialogs import show_preview_dialog

CHANNEL_NUMBER_COLOR = "#c9e26b"

_CHANNEL_NUMBER_FONT_CANDIDATES = (
    "Helvetica Neue Condensed Bold",
    "HelveticaNeue-CondensedBold",
    "Arial Narrow",
    "Nimbus Sans Narrow",
    "Liberation Sans Narrow",
)

_channel_number_font_family_cache = None


def channel_number_font_family():
    """A condensed, bold family for CH-number badges.

    Mirrors the app's own guide-font fallback tier (never touches the
    app's custom-loaded guide font directly, to avoid Channel Studio
    importing from channelsurfer2000.py) — checks already-installed
    system families and falls back to Arial, same as the rest of the
    app does when its own preferred fonts aren't available.
    """
    global _channel_number_font_family_cache
    if _channel_number_font_family_cache:
        return _channel_number_font_family_cache
    available = set(QFontDatabase.families())
    for family in _CHANNEL_NUMBER_FONT_CANDIDATES:
        if family in available:
            _channel_number_font_family_cache = family
            return family
    _channel_number_font_family_cache = "Arial"
    return _channel_number_font_family_cache


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

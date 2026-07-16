"""Generic style helpers shared by every Studio tool.

Extracted from mediawave/channel_studio/studio_styles.py, where these lived
alongside genuinely channel-specific helpers (VHS/OSD font loading, the
NOW/NEXT/LATER schedule badge, the two channel/companion confirm dialogs).
Those stay in channel_studio/studio_styles.py, which re-exports the names
below so existing `from .studio_styles import ...` call sites there don't
need to change.

Nothing here knows about channels, logos, or any other MediaWave concept.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QScrollArea, QStackedWidget

REMOVE_BUTTON_COLOR = "#ff5a6e"


def apply_card_shadow(widget, blur_radius=20, alpha=150):
    """A soft drop shadow so a card reads as a raised, tactile tile instead
    of a flat text block. Shared by the dashboard channel cards
    (channel_card.py) and StudioSection (studio/section.py) so both use the
    same "glow" rather than each hardcoding their own shadow -- StudioSection
    passes smaller values for a more restrained glow, since a workspace's own
    cards shouldn't compete for attention as strongly as a dashboard's tiles
    do.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setOffset(0, 3)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


def style_setup_button(button):
    """Blue fill -- a Studio tool's consistent "go do something" action."""
    button.setStyleSheet(
        """
        QPushButton {
            background: rgba(96, 144, 255, 220);
            border: 1px solid rgba(140, 175, 255, 230);
            border-radius: 6px;
            color: white;
            font-weight: 600;
            padding: 5px 14px;
        }
        QPushButton:hover {
            background: rgba(120, 165, 255, 235);
        }
        """
    )
    return button


def style_remove_button(button):
    """Red outline -- visually distinct from Setup, but not a solid
    alarm-red fill; destructive actions built on this should stay a safe,
    confirmation-gated preview action.
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
    Setup v2's Default/Off/Custom) -- filled and bordered like
    style_setup_button when it's the currently-active choice, a quieter
    outline otherwise, so the user can tell which one is in effect without
    reading the status text above it.
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


def style_nav_item(widget, active):
    """One row in a StudioNavRail (studio/nav_rail.py) -- matches Advanced
    Configuration's own `advNavItem` treatment exactly (a flat list item,
    not a card): a 3px left accent strip + a translucent accent tint when
    selected, a fainter tint-only on hover, transparent otherwise. Same
    accent/border tones Advanced Configuration's own sidebar QSS uses
    (channelsurfer2000.py's `QPushButton#advNavItem` rule), reused here
    rather than invented, so the sidebar reads as the same navigation
    language, not a different one.
    """
    if active:
        widget.setStyleSheet(
            "QFrame#studioNavItem {"
            " border: none;"
            " border-left: 3px solid rgba(96, 144, 255, 255);"
            " border-radius: 0px;"
            " background: rgba(68, 108, 235, 38);"
            "}"
        )
        return widget
    widget.setStyleSheet(
        "QFrame#studioNavItem {"
        " border: none;"
        " border-left: 3px solid transparent;"
        " border-radius: 0px;"
        " background: transparent;"
        "}"
        "QFrame#studioNavItem:hover {"
        " background: rgba(68, 108, 235, 18);"
        "}"
    )
    return widget


def style_slider(slider):
    """A themed QSlider matching a Studio tool's dark panels -- used by
    Logo Studio's opacity/size sliders. No app-wide QSlider styling exists
    yet, so this is scoped to the slider instance, not global QSS.
    """
    slider.setStyleSheet(
        """
        QSlider::groove:horizontal {
            background: rgba(255, 255, 255, 30);
            height: 4px;
            border-radius: 2px;
        }
        QSlider::sub-page:horizontal {
            background: rgba(96, 144, 255, 220);
            height: 4px;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: rgba(230, 235, 250, 240);
            border: 1px solid rgba(140, 175, 255, 230);
            width: 14px;
            height: 14px;
            margin: -6px 0;
            border-radius: 7px;
        }
        QSlider::handle:horizontal:hover {
            background: rgba(255, 255, 255, 255);
        }
        """
    )
    return slider


def build_scroll_area(widget):
    """A QScrollArea whose viewport shows the app's own dark background
    instead of the platform-default gray/white fill.

    Two separate Qt gotchas stack up here: (1) `QScrollArea { background:
    transparent }` in the app-wide QSS never reaches the scroll area's
    internal viewport widget on its own -- `setAutoFillBackground(False)`
    is needed too, the same trick the main app's FocusScrollArea uses.
    (2) a plain QWidget (like the page `widget` being scrolled) doesn't
    paint QSS `background` at all unless it opts in via
    `WA_StyledBackground` -- the app already has a QSS rule for exactly
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
    pages with a lot of dead space under the tallest one. Call
    `updateGeometry()` (done in setCurrentIndex here) after switching so
    layouts re-measure.
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

"""StudioSidebar: a branded left sidebar matching Advanced Configuration's
own nav panel (`_AdvNavPanel` in channelsurfer2000.py) -- a star-painted
dark gradient background, a right-edge glow, and a 1px border -- hosting
whatever identity block and nav rail a caller builds, rather than a plain
floating strip of nav items. Generic composition: this widget doesn't know
anything about channels/logos/pages, it just arranges and frames two child
widgets the same way Advanced Configuration's sidebar frames its own
branding header + nav button column.

Deliberately does NOT import channelsurfer2000.py (see mediawave/
theme_tokens.py's own docstring for why the Studio package stays
independent of the app's full startup path) -- the star field here is a
fresh, self-contained implementation using the same shared color tokens
(mediawave/theme_tokens.py, a general app-wide module, not Studio-specific),
not the app's actual `_STARTUP_STARS` list.
"""

import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from ..theme_tokens import SW_BG, SW_CARD_BORDER, SW_STAR_COOL, SW_STAR_DIM, SW_STAR_WARM

SIDEBAR_WIDTH = 230

# The exact border tone Advanced Configuration's own sidebar
# (_AdvNavPanel.paintEvent in channelsurfer2000.py) uses for its 1px right
# edge -- a distinct darker blue with no named _SW_* token of its own,
# reused here as a literal for an exact visual match rather than derived
# via QColor.darker(), which lands close but not identical.
_SIDEBAR_BORDER_COLOR = QColor(40, 56, 150)
# Advanced Configuration's sidebar gradient starts slightly darker than
# SW_BG itself (8,10,26 vs. SW_BG's 13,16,38) -- reused as-is for the same
# subtle top-to-bottom depth.
_SIDEBAR_GRADIENT_TOP = QColor(8, 10, 26)

# Fixed seed -- the star field looks the same every run rather than
# reshuffling, same spirit as a real starfield being a fixed piece of art,
# not something that should visibly jump around between sessions.
_STAR_SEED = 1997
_STAR_COUNT = 26
_STAR_TIERS = (
    (SW_STAR_WARM, 60, 130, 1.1, 1.8),
    (SW_STAR_COOL, 50, 110, 0.9, 1.6),
    (SW_STAR_DIM, 30, 80, 0.7, 1.3),
)


def _generate_stars():
    rng = random.Random(_STAR_SEED)
    stars = []
    for i in range(_STAR_COUNT):
        color, alpha_lo, alpha_hi, r_lo, r_hi = _STAR_TIERS[i % len(_STAR_TIERS)]
        stars.append(
            (
                rng.random(),
                rng.random(),
                rng.uniform(r_lo, r_hi),
                rng.randint(alpha_lo, alpha_hi),
                color,
            )
        )
    return stars


class StudioSidebar(QWidget):
    """Fixed-width branded sidebar: `identity_widget` at top, a separator,
    then `nav_rail` filling the rest. Both are supplied fully-built by the
    caller (see channel_setup.py) -- this widget only owns the frame/
    background chrome around them.
    """

    def __init__(self, identity_widget, nav_rail, parent=None):
        super().__init__(parent)
        self.setFixedWidth(SIDEBAR_WIDTH)
        self._stars = _generate_stars()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(identity_widget)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background: rgba({SW_CARD_BORDER.red()}, {SW_CARD_BORDER.green()}, {SW_CARD_BORDER.blue()}, 90); border: none;")
        layout.addWidget(separator)

        nav_wrap = QWidget()
        nav_wrap.setStyleSheet("background: transparent;")
        nav_wrap_layout = QVBoxLayout(nav_wrap)
        nav_wrap_layout.setContentsMargins(0, 12, 0, 0)
        nav_wrap_layout.setSpacing(0)
        nav_wrap_layout.addWidget(nav_rail)
        layout.addWidget(nav_wrap, 1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()

        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0.0, _SIDEBAR_GRADIENT_TOP)
        gradient.setColorAt(1.0, SW_BG)
        painter.fillRect(rect, gradient)

        painter.setPen(Qt.NoPen)
        for fx, fy, radius, alpha, color in self._stars:
            star_color = color.__class__(color)
            star_color.setAlpha(alpha)
            painter.setBrush(star_color)
            painter.drawEllipse(QPointF(fx * rect.width(), fy * rect.height()), radius, radius)

        glow_width = 30
        glow = QLinearGradient(rect.width() - glow_width, 0, rect.width(), 0)
        glow.setColorAt(0.0, _with_alpha(SW_CARD_BORDER, 0))
        glow.setColorAt(1.0, _with_alpha(SW_CARD_BORDER, 32))
        painter.fillRect(QRectF(rect.width() - glow_width, 0, glow_width, rect.height()), glow)

        painter.setPen(QPen(_with_alpha(_SIDEBAR_BORDER_COLOR, 180), 1))
        painter.drawLine(rect.width() - 1, 0, rect.width() - 1, rect.height())
        painter.end()


def _with_alpha(color, alpha):
    out = color.__class__(color)
    out.setAlpha(alpha)
    return out

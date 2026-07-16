"""StudioSection: a reusable card for Channel Studio setup pages (Phase 1
introduced it; Phase 2 polished it -- softer corners, refined spacing, a
slightly larger title, an optional colored accent strip, and a smoother
expand/collapse). Phase 3's cleanup pass added a real `collapsible=False`
mode: when the left nav rail already owns which page is visible (the main
Channel Studio workspace pages), there's nothing left for a per-page
collapse arrow to do -- so in that mode no toggle button is created, no
space is reserved for one, the content is always visible, and none of the
expand/collapse animation machinery runs. `collapsible=True` (the default) keeps the original toggle-arrow behavior
for any future caller that wants it; Logo Studio's own card already opts
out via `collapsible=False`, and the main Channel Studio workspace pages
(channel_setup.py) do the same as of this cleanup pass.

Generic on purpose -- this widget knows nothing about commercials,
scheduling, or any other Channel Studio concept. It just hosts arbitrary
child content inside a themed card with a title/subtitle header and an
optional expand/collapse toggle, so future setup pages (Artwork, Playback,
Audio, Signal, Companion Settings, ...) can reuse it without touching this
file.
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .spacing import CARD_PADDING, CONTROL_SPACING, SECTION_SPACING
from .styles import apply_card_shadow
from .typography import SECTION_TITLE_SIZE, SECTION_TITLE_WEIGHT

_ANIMATION_MS = 200

# Same theme tokens the rest of Channel Studio already reuses
# (channel_card.py's dashboard tile, studio_nav_rail.py's cards) --
# channelsurfer2000.py's _SW_CARD_BG / _SW_CARD_BORDER / _SW_HEADER /
# _SW_ACCENT -- kept here as one literal set rather than re-derived, since
# this module can't import the app's private theme constants directly.
_CARD_BG = "rgba(22, 26, 58, 232)"
_CARD_BORDER = "rgba(68, 108, 235, 100)"
_TITLE_COLOR = "rgba(118, 162, 255, 255)"
_ACCENT_COLOR = "rgba(96, 144, 255, 220)"

_CARD_STYLE = (
    "QFrame#studioSectionCard {"
    f" background: {_CARD_BG};"
    f" border: 1px solid {_CARD_BORDER};"
    " border-radius: 14px;"
    "}"
)
_TITLE_STYLE = (
    "QLabel#studioSectionTitle {"
    f" color: {_TITLE_COLOR};"
    " background: transparent;"
    f" font-size: {SECTION_TITLE_SIZE}px;"
    f" font-weight: {SECTION_TITLE_WEIGHT};"
    "}"
)


class StudioSection(QFrame):
    """One collapsible card: header (icon + title + subtitle + toggle) and
    a body that hosts a single content widget.

    Collapsing only hides the body -- the header stays fully visible so a
    collapsed card still shows what it is, per the "collapsed cards should
    preserve enough height that the title and description remain visible"
    requirement.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        title,
        subtitle=None,
        icon=None,
        content=None,
        footer=None,
        expanded=True,
        collapsible=True,
        accent=False,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("studioSectionCard")
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(_CARD_STYLE)
        # A more restrained glow than the dashboard cards' default (Phase
        # 3: "restrained use of glow effects" in the main workspace).
        apply_card_shadow(self, blur_radius=14, alpha=110)

        self._collapsible = collapsible
        self._expanded = expanded
        self._animation = None

        card_row = QHBoxLayout(self)
        card_row.setContentsMargins(0, 0, 0, 0)
        card_row.setSpacing(0)

        if accent:
            accent_strip = QFrame()
            accent_strip.setFixedWidth(4)
            accent_strip.setStyleSheet(f"background: {_ACCENT_COLOR}; border-radius: 2px;")
            card_row.addWidget(accent_strip)

        inner = QWidget()
        card_row.addWidget(inner, 1)
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(*CARD_PADDING)
        outer.setSpacing(SECTION_SPACING)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        outer.addLayout(header_row)

        if icon:
            icon_lbl = QLabel(icon)
            icon_font = icon_lbl.font()
            icon_font.setPointSize(icon_font.pointSize() + 4)
            icon_lbl.setFont(icon_font)
            header_row.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("studioSectionTitle")
        self._title_lbl.setStyleSheet(_TITLE_STYLE)
        title_col.addWidget(self._title_lbl)
        if subtitle:
            self._subtitle_lbl = QLabel(subtitle)
            self._subtitle_lbl.setObjectName("sectionNote")
            self._subtitle_lbl.setWordWrap(True)
            title_col.addWidget(self._subtitle_lbl)
        else:
            self._subtitle_lbl = None
        header_row.addLayout(title_col, 1)

        # No toggle button is created at all in non-collapsible mode --
        # not just hidden -- since a channel-studio-style workspace page
        # that's always open (nav rail owns which page is visible) has no
        # use for collapse affordance, reserved space, or the animation/
        # state-persistence machinery collapsing implies.
        self._toggle_btn = None
        if collapsible:
            self._toggle_btn = QPushButton()
            self._toggle_btn.setFlat(True)
            self._toggle_btn.setCursor(Qt.PointingHandCursor)
            self._toggle_btn.setFixedWidth(28)
            self._toggle_btn.clicked.connect(self._on_toggle_clicked)
            header_row.addWidget(self._toggle_btn)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 4, 0, 0)
        self._body_layout.setSpacing(CONTROL_SPACING)
        outer.addWidget(self._body)

        self._content = None
        self.set_content(content)

        self._footer_wrap = None
        if footer is not None:
            self.set_footer(footer)

        self._outer_layout = outer
        if collapsible:
            self._sync_toggle_label()
            self._apply_expanded_state(animate=False)

    def set_content(self, widget):
        """Swap the card's body content in place, keeping the header and
        current expand/collapse state untouched. Used by callers that
        refresh a section's content without rebuilding the whole card
        (e.g. picking up a logo dropped onto disk after the page opened).

        The old widget is hidden immediately, before `removeWidget`/
        `deleteLater` -- `QLayout.removeWidget` only detaches the widget
        from layout management, it doesn't hide it, and `deleteLater`'s
        actual deletion is deferred to the next event-loop pass. Without
        the explicit `hide()`, the outgoing widget stays a fully visible,
        unmanaged sibling of the new content -- at whatever geometry it
        last had (or Qt's raw default size if it was swapped out before
        ever being laid out) -- until deletion is processed, producing
        exactly the doubled/overlapping content this call is meant to
        prevent.
        """
        if self._content is not None:
            self._content.hide()
            self._body_layout.removeWidget(self._content)
            self._content.deleteLater()
        self._content = widget
        if widget is not None:
            self._body_layout.addWidget(widget)
        if self._expanded:
            self._body.setMaximumHeight(16777215)

    def set_footer(self, widget):
        if self._footer_wrap is not None:
            self._footer_wrap.hide()
            self._outer_layout.removeWidget(self._footer_wrap)
            self._footer_wrap.deleteLater()
            self._footer_wrap = None
        if widget is not None:
            self._footer_wrap = widget
            self._outer_layout.addWidget(widget)

    @property
    def is_expanded(self):
        return self._expanded

    def set_expanded(self, expanded, animate=True):
        if not self._collapsible:
            return
        expanded = bool(expanded)
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self._sync_toggle_label()
        self._apply_expanded_state(animate=animate)
        self.toggled.emit(self._expanded)

    def _on_toggle_clicked(self):
        if self._collapsible:
            self.set_expanded(not self._expanded)

    def _sync_toggle_label(self):
        self._toggle_btn.setText("▾" if self._expanded else "▸")
        self._toggle_btn.setToolTip("Collapse" if self._expanded else "Expand")

    def _apply_expanded_state(self, animate):
        # Deliberately height-only, no accompanying opacity fade: a
        # QGraphicsOpacityEffect on the body -- nested inside this frame's
        # own QGraphicsDropShadowEffect (apply_card_shadow above) -- turned
        # out to silently break painting of some of the body's children in
        # testing (a real, if obscure, Qt effect-compositing interaction,
        # not a layout bug -- geometry was always correct, content just
        # didn't paint). Not worth the risk for a "nice to have" fade on
        # top of an animation that already reads as smooth on its own.
        if self._animation is not None:
            self._animation.stop()
            self._animation = None

        if not animate:
            self._body.setMaximumHeight(16777215 if self._expanded else 0)
            return

        start_height = self._body.height()
        target_height = self._body.sizeHint().height() if self._expanded else 0

        height_anim = QPropertyAnimation(self._body, b"maximumHeight", self)
        height_anim.setDuration(_ANIMATION_MS)
        height_anim.setEasingCurve(QEasingCurve.InOutCubic)
        height_anim.setStartValue(start_height)
        height_anim.setEndValue(target_height)
        if self._expanded:
            height_anim.finished.connect(lambda: self._body.setMaximumHeight(16777215))
        self._animation = height_anim
        height_anim.start()

"""The channel identity block for a single channel's real Setup screen --
not to be confused with channel_studio_header.py, which builds the
unrelated "Your Channels" dashboard toolbar on the Choose Channel grid page.

Phase 1.5 made the logo preview a clickable entry point into Logo Studio.
Phase 2 added status badges + a hover-fade "Edit Logo" overlay, laid out as
a full-width header row above the rest of the page. Phase 3 moves this
content into the top of the left sidebar (studio_sidebar.py), matching
Advanced Configuration's own branding-block-above-nav-items shape -- so
build_identity_block lays the same information out vertically (logo, name,
number, then short status lines) instead of as a wide horizontal row.
"""

from PySide6.QtCore import QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

_LOGO_SIZE = 84
_OVERLAY_MS = 140

_LOGO_HAS_IMAGE_STYLE = (
    "QFrame#logoControl {"
    " background: rgba(255, 255, 255, 10);"
    " border: 1px solid rgba(140, 175, 255, 140);"
    " border-radius: 10px;"
    "}"
)
_LOGO_PLACEHOLDER_STYLE = (
    "QFrame#logoControl {"
    " background: rgba(255, 255, 255, 10);"
    " border: 1.5px dashed rgba(140, 175, 255, 140);"
    " border-radius: 10px;"
    "}"
)


class _LogoControl(QFrame):
    """The header's clickable logo: a pixmap (or "Add Logo" placeholder)
    with a semi-transparent "Edit Logo" label that fades in on hover --
    the hover cue the spec asks for "without requiring another visible
    button". A QFrame rather than a QPushButton so a QStackedLayout can
    overlay the two children in the same rect (StackAll mode); click and
    Enter/Space are implemented directly.
    """

    def __init__(self, pixmap, on_activated, parent=None):
        super().__init__(parent)
        self.setObjectName("logoControl")
        self.setFixedSize(_LOGO_SIZE, _LOGO_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setToolTip("Click to edit in Logo Studio")
        self._on_activated = on_activated

        stack = QStackedLayout(self)
        stack.setStackingMode(QStackedLayout.StackAll)
        stack.setContentsMargins(0, 0, 0, 0)

        self._image_lbl = QLabel()
        self._image_lbl.setAlignment(Qt.AlignCenter)
        self._image_lbl.setWordWrap(True)
        # Both stacked labels sit on top of this frame in z-order (StackAll
        # keeps every layer present, not just the current one) -- without
        # this, Qt delivers mouse events to whichever label is under the
        # cursor instead of this QFrame's own mousePressEvent below, and
        # the logo silently stops being clickable.
        self._image_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        image_font = self._image_lbl.font()
        image_font.setPointSize(max(8, image_font.pointSize() - 2))
        self._image_lbl.setFont(image_font)
        stack.addWidget(self._image_lbl)

        self._overlay_lbl = QLabel("Edit Logo")
        self._overlay_lbl.setAlignment(Qt.AlignCenter)
        self._overlay_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._overlay_lbl.setStyleSheet(
            "background: rgba(10, 14, 30, 210); color: white; font-weight: 600; font-size: 11px;"
        )
        self._overlay_opacity = QGraphicsOpacityEffect(self._overlay_lbl)
        self._overlay_opacity.setOpacity(0.0)
        self._overlay_lbl.setGraphicsEffect(self._overlay_opacity)
        stack.addWidget(self._overlay_lbl)

        self._overlay_anim = QPropertyAnimation(self._overlay_opacity, b"opacity", self)
        self._overlay_anim.setDuration(_OVERLAY_MS)

        self.set_pixmap(pixmap)

    def set_pixmap(self, pixmap):
        if pixmap is not None and not pixmap.isNull():
            scaled = pixmap.scaled(
                _LOGO_SIZE - 12, _LOGO_SIZE - 12, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._image_lbl.setPixmap(scaled)
            self._image_lbl.setText("")
            self.setStyleSheet(_LOGO_HAS_IMAGE_STYLE)
        else:
            self._image_lbl.clear()
            self._image_lbl.setText("Add\nLogo")
            self.setStyleSheet(_LOGO_PLACEHOLDER_STYLE)

    def _animate_overlay(self, target):
        self._overlay_anim.stop()
        self._overlay_anim.setStartValue(self._overlay_opacity.opacity())
        self._overlay_anim.setEndValue(target)
        self._overlay_anim.start()

    def enterEvent(self, event):
        self._animate_overlay(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_overlay(0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._on_activated is not None:
            self._on_activated()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if self._on_activated is not None:
                self._on_activated()
            return
        super().keyPressEvent(event)


class ChannelIdentityApi:
    """Returned alongside the identity block widget (same tuple convention
    as build_inline_value_editor in channel_studio_widgets.py) so a caller
    can refresh the logo thumbnail or the status lines in place -- e.g.
    after returning from Logo Studio (logo may have changed), or after
    navigating to a page whose edits could affect the commercials-mode/
    enabled lines (same "refresh on navigate" pattern ChannelSetupDialog
    already uses for Overview's own preview card).
    """

    def __init__(self, logo_control, status_layout):
        self._logo_control = logo_control
        self._status_layout = status_layout

    def set_logo_pixmap(self, pixmap):
        if self._logo_control is not None:
            self._logo_control.set_pixmap(pixmap)

    def set_status_lines(self, lines):
        # hide() before takeAt()/deleteLater(): QLayout.takeAt() only
        # detaches the item from layout management, it doesn't hide the
        # widget, and deleteLater()'s actual deletion is deferred to the
        # next event-loop pass. A widget swapped out this way stays a
        # fully visible, unmanaged sibling -- at whatever geometry it last
        # had, or Qt's raw default size if it was swapped out before ever
        # being laid out -- until deletion runs. That's exactly how a
        # stale status label ended up covering this whole identity block
        # (and everything behind it, including the clickable logo) after
        # the very first refresh: this same call is made once at
        # construction and again immediately on the initial page-select,
        # both before the dialog's first paint, so the outgoing label
        # never got a real layout-assigned geometry to fall back to.
        while self._status_layout.count():
            item = self._status_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        for line in lines or []:
            lbl = QLabel(line)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: rgba(148, 196, 255, 200); background: transparent; font-size: 11px;")
            self._status_layout.addWidget(lbl)


def build_identity_block(
    channel_name,
    channel_number,
    subtitle_text,
    logo_pixmap=None,
    on_logo_activated=None,
    status_lines=None,
):
    """Build the sidebar's top identity area: logo, `"{channel_name} ·
    Channel {channel_number}"`, `subtitle_text` (the identity/summary note),
    and short status lines (`status_lines` -- plain strings, e.g. commercials
    mode / enabled state; show/movie count is already folded into
    `subtitle_text` via ChannelStudioSummary.headline) -- all stacked
    vertically for a narrow sidebar column, not a wide horizontal row. When
    `on_logo_activated` is given, the logo is a clickable entry point into
    Logo Studio (or an "Add Logo" placeholder), with a hover overlay
    suggesting "Edit Logo".

    Returns `(block_widget, api)`; `api.set_logo_pixmap(pixmap)` /
    `api.set_status_lines(lines)` update those pieces in place without
    rebuilding the rest of the block.
    """
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(20, 22, 16, 16)
    layout.setSpacing(8)

    logo_control = None
    if on_logo_activated is not None:
        logo_control = _LogoControl(logo_pixmap, on_logo_activated)
        layout.addWidget(logo_control, 0, Qt.AlignLeft)

    heading = QLabel(f"{channel_name} · Channel {channel_number}")
    heading.setObjectName("sectionHeader")
    heading.setWordWrap(True)
    layout.addWidget(heading)

    subtitle = QLabel(subtitle_text)
    subtitle.setObjectName("sectionNote")
    subtitle.setWordWrap(True)
    layout.addWidget(subtitle)

    status_layout = QVBoxLayout()
    status_layout.setSpacing(2)
    layout.addLayout(status_layout)

    api = ChannelIdentityApi(logo_control, status_layout)
    api.set_status_lines(status_lines)
    return container, api

"""ProgramBlockWidget: one physical card on the programming board.

Purpose-built rather than a StudioSection -- the spec is explicit that the
timeline board shouldn't be forced into the generic card abstraction. Reuses
the same rounded-corner/glow language StudioSection already established
(mediawave/studio/section.py's `_CARD_STYLE`) so the board still reads as
"the same building", just not literally the same widget class.
"""

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from .layout_constants import (
    MEDIUM_CONTENT_MIN_PX,
    MIN_BLOCK_WIDTH_PX,
    NARROW_CONTENT_MIN_PX,
    ROW_HEIGHT,
    ROW_VERTICAL_MARGIN,
    WIDE_CONTENT_MIN_PX,
)
from .schedule_model import PX_PER_MINUTE, block_width_px

_MEDIA_TYPE_LABELS = {"tv": "Series", "movie": "Movie", "commercial": "Commercial"}

_MEDIA_TYPE_ACCENTS = {
    # Reuses the app's existing "deep space" palette tones
    # (mediawave/theme_tokens.py) rather than inventing new hues -- Series
    # rides the same electric-blue every other Studio card already uses,
    # Movie borrows the CTA amber (a deliberate "this one's an event" cue),
    # Commercial stays dim/neutral so it doesn't compete for attention.
    "tv": ("rgba(22, 26, 58, 232)", "rgba(68, 108, 235, 130)"),
    "movie": ("rgba(58, 42, 16, 232)", "rgba(255, 188, 10, 150)"),
    "commercial": ("rgba(24, 26, 34, 210)", "rgba(120, 130, 160, 90)"),
}

_TEXT_COLOR = "rgba(210, 222, 252, 235)"
_TEXT_DIM = "rgba(158, 172, 210, 220)"
_SELECTED_BORDER = "rgba(255, 218, 96, 235)"


def _format_time_range(start_epoch, end_epoch):
    try:
        start_label = time.strftime("%-I:%M", time.localtime(start_epoch))
        end_label = time.strftime("%-I:%M %p", time.localtime(end_epoch))
    except Exception:
        return ""
    return f"{start_label}–{end_label}"


def _content_level(width_px):
    if width_px >= WIDE_CONTENT_MIN_PX:
        return "wide"
    if width_px >= MEDIUM_CONTENT_MIN_PX:
        return "medium"
    if width_px >= NARROW_CONTENT_MIN_PX:
        return "narrow"
    return "marker"


class ProgramBlockWidget(QFrame):
    """One logical program (or commercial break) rendered at a width
    proportional to its real duration. Read-only: no drag cursor, no resize
    handles, click only toggles selection.
    """

    selected = Signal(object)  # emits the underlying ProgramBlock

    def __init__(self, block, px_per_minute=PX_PER_MINUTE, parent=None):
        super().__init__(parent)
        self.block = block
        self._is_selected = False
        self.setObjectName("scheduleProgramBlock")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        width = max(MIN_BLOCK_WIDTH_PX, round(block_width_px(block.duration, px_per_minute)))
        self.setFixedWidth(width)
        self.setFixedHeight(ROW_HEIGHT - ROW_VERTICAL_MARGIN * 2)

        self._level = _content_level(width)
        self._build_content()
        self._apply_style()

        time_label = _format_time_range(block.true_start, block.true_end)
        minutes = max(1, round(block.duration / 60))
        tooltip = block.title
        if time_label:
            tooltip += f"\n{time_label}"
        tooltip += f"\n{minutes} min"
        self.setToolTip(tooltip)

    def _build_content(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        if self._level == "marker":
            # Too narrow for any text -- a plain colored tile; full detail
            # lives in the tooltip and the details strip on selection.
            return

        title_text = self.block.title or "Untitled"
        title_lbl = QLabel(title_text)
        title_lbl.setWordWrap(False)
        title_lbl.setStyleSheet(f"color: {_TEXT_COLOR}; font-weight: 600; font-size: 12px; background: transparent;")
        fm = title_lbl.fontMetrics()
        available = self.width() - 16 if self.width() else 400
        title_lbl.setText(fm.elidedText(title_text, Qt.ElideRight, max(20, available)))
        layout.addWidget(title_lbl)

        if self._level == "narrow":
            return

        time_label = _format_time_range(self.block.true_start, self.block.true_end)
        if time_label:
            time_lbl = QLabel(time_label)
            time_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 10px; background: transparent;")
            layout.addWidget(time_lbl)

        if self._level == "wide" and self.block.media_type in ("movie",):
            minutes = max(1, round(self.block.duration / 60))
            type_lbl = QLabel(f"{_MEDIA_TYPE_LABELS.get(self.block.media_type, '')} · {minutes} min")
            type_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 10px; background: transparent;")
            layout.addWidget(type_lbl)

        layout.addStretch(1)

    def _apply_style(self):
        bg, border = _MEDIA_TYPE_ACCENTS.get(self.block.media_type, _MEDIA_TYPE_ACCENTS["tv"])
        border_color = _SELECTED_BORDER if self._is_selected else border
        border_width = 2 if self._is_selected else 1
        self.setStyleSheet(
            "QFrame#scheduleProgramBlock {"
            f" background: {bg};"
            f" border: {border_width}px solid {border_color};"
            " border-radius: 8px;"
            "}"
        )

    def set_selected(self, is_selected):
        self._is_selected = bool(is_selected)
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.block)
        super().mousePressEvent(event)

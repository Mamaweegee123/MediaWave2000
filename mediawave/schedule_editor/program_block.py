"""ProgramBlockWidget: one physical card on the programming board.

Purpose-built rather than a StudioSection -- the spec is explicit that the
timeline board shouldn't be forced into the generic card abstraction. Reuses
the same rounded-corner/glow language StudioSection already established
(mediawave/studio/section.py's `_CARD_STYLE`) so the board still reads as
"the same building", just not literally the same widget class.
"""

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from .layout_constants import (
    BLOCK_GAP_PX,
    MEDIUM_CONTENT_MIN_PX,
    MIN_BLOCK_WIDTH_PX,
    NARROW_CONTENT_MIN_PX,
    ROW_HEIGHT,
    ROW_VERTICAL_MARGIN,
    WIDE_CONTENT_MIN_PX,
)
from .schedule_model import PX_PER_MINUTE, block_width_px

# The canonical media-type -> (label, accent) map. Deliberately the one
# place this exists -- utility_panels.py imports MEDIA_TYPE_LABELS from
# here instead of keeping its own copy, so a category can never show one
# name on the board and a different one in Next Up/the details strip.
# "weather"/"music" are real, channel_type-backed categories
# companion_display.group_for_display() produces for WeatherStar/RadioWaveTV
# -- not invented per-program content categories (see that module's
# docstring). NetTV deliberately has no category of its own: its real
# per-video titles render as plain "tv"/Show cards, the same as any other
# literal content -- a separate "Companion" bucket with nothing real behind
# it would itself be a small dishonesty in the legend.
MEDIA_TYPE_LABELS = {
    "tv": "Show",
    "movie": "Movie",
    "commercial": "Commercial",
    "weather": "Weather",
    "music": "Music",
}

MEDIA_TYPE_ACCENTS = {
    # Reuses the app's existing "deep space" palette tones
    # (mediawave/theme_tokens.py) rather than inventing new hues -- Show
    # rides the same electric-blue every other Studio card already uses,
    # Movie borrows the CTA amber (a deliberate "this one's an event" cue),
    # Commercial stays dim/neutral so it doesn't compete for attention.
    # Weather/Music follow the identical (bg, border) alpha pattern with
    # new hues (teal/purple).
    "tv": ("rgba(22, 26, 58, 232)", "rgba(68, 108, 235, 130)"),
    "movie": ("rgba(58, 42, 16, 232)", "rgba(255, 188, 10, 150)"),
    "commercial": ("rgba(24, 26, 34, 210)", "rgba(120, 130, 160, 90)"),
    "weather": ("rgba(16, 48, 46, 232)", "rgba(90, 200, 170, 150)"),
    "music": ("rgba(42, 24, 58, 232)", "rgba(180, 120, 235, 150)"),
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

    The widget's own outer box stays exactly `block_width_px()`-proportional
    (a 30-minute block is still always exactly half a 60-minute block's
    *slot* width) -- the visible, styled card is a smaller inner QFrame
    inset by `BLOCK_GAP_PX`, so adjacent cards read as separate tiles with
    real breathing room between them without touching the duration-exact
    geometry the board's slot math and tests depend on.
    """

    selected = Signal(object)  # emits the underlying ProgramBlock

    def __init__(self, block, px_per_minute=PX_PER_MINUTE, parent=None):
        super().__init__(parent)
        self.block = block
        self._is_selected = False
        self.setObjectName("scheduleProgramBlockSlot")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setStyleSheet("QFrame#scheduleProgramBlockSlot { background: transparent; border: none; }")

        width = max(MIN_BLOCK_WIDTH_PX, round(block_width_px(block.duration, px_per_minute)))
        self.setFixedWidth(width)
        self.setFixedHeight(ROW_HEIGHT - ROW_VERTICAL_MARGIN * 2)

        slot_layout = QHBoxLayout(self)
        slot_layout.setContentsMargins(0, 0, BLOCK_GAP_PX, 0)
        slot_layout.setSpacing(0)
        self._card = QFrame(self)
        self._card.setObjectName("scheduleProgramBlock")
        slot_layout.addWidget(self._card)

        card_width = max(1, width - BLOCK_GAP_PX)
        self._level = _content_level(card_width)
        self._build_content(card_width)
        self._apply_style()

        time_label = _format_time_range(block.true_start, block.true_end)
        minutes = max(1, round(block.duration / 60))
        tooltip = block.title
        if time_label:
            tooltip += f"\n{time_label}"
        tooltip += f"\n{minutes} min"
        self.setToolTip(tooltip)

    def _build_content(self, card_width):
        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        if self._level == "marker":
            # Too narrow for any text -- a plain colored tile; full detail
            # lives in the tooltip and the details strip on selection.
            return

        title_text = self.block.title or "Untitled"
        title_lbl = QLabel(title_text)
        title_lbl.setWordWrap(False)
        title_lbl.setStyleSheet(f"color: {_TEXT_COLOR}; font-weight: 600; font-size: 12px; background: transparent;")
        fm = title_lbl.fontMetrics()
        available = card_width - 20 if card_width else 400
        title_lbl.setText(fm.elidedText(title_text, Qt.ElideRight, max(20, available)))
        layout.addWidget(title_lbl)

        if self._level == "narrow":
            return

        time_label = _format_time_range(self.block.true_start, self.block.true_end)
        if time_label:
            time_lbl = QLabel(time_label)
            time_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 10px; background: transparent;")
            layout.addWidget(time_lbl)

        if self._level == "wide" and self.block.media_type != "tv":
            minutes = max(1, round(self.block.duration / 60))
            type_lbl = QLabel(f"{MEDIA_TYPE_LABELS.get(self.block.media_type, '')} · {minutes} min")
            type_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 10px; background: transparent;")
            layout.addWidget(type_lbl)

        layout.addStretch(1)

    def _apply_style(self):
        bg, border = MEDIA_TYPE_ACCENTS.get(self.block.media_type, MEDIA_TYPE_ACCENTS["tv"])
        border_color = _SELECTED_BORDER if self._is_selected else border
        border_width = 2 if self._is_selected else 1
        self._card.setStyleSheet(
            "QFrame#scheduleProgramBlock {"
            f" background: {bg};"
            f" border: {border_width}px solid {border_color};"
            " border-radius: 11px;"
            "}"
        )

    def set_selected(self, is_selected):
        self._is_selected = bool(is_selected)
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.block)
        super().mousePressEvent(event)


def build_category_legend():
    """A small swatch+label row for every real category the board can
    render -- co-located with MEDIA_TYPE_ACCENTS so the legend can never
    drift out of sync with what a block actually looks like.
    """
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(18)

    for media_type, label in MEDIA_TYPE_LABELS.items():
        item = QWidget()
        item_layout = QHBoxLayout(item)
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(6)

        _, border = MEDIA_TYPE_ACCENTS.get(media_type, MEDIA_TYPE_ACCENTS["tv"])
        swatch = QFrame()
        swatch.setFixedSize(10, 10)
        swatch.setStyleSheet(f"background: {border}; border-radius: 3px;")
        item_layout.addWidget(swatch)

        text = QLabel(label)
        text.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;")
        item_layout.addWidget(text)

        layout.addWidget(item)

    layout.addStretch(1)
    return row

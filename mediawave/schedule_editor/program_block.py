"""ProgramBlockWidget: one physical card on the programming board.

Purpose-built rather than a StudioSection -- the spec is explicit that the
timeline board shouldn't be forced into the generic card abstraction. Reuses
the same rounded-corner/glow language StudioSection already established
(mediawave/studio/section.py's `_CARD_STYLE`) so the board still reads as
"the same building", just not literally the same widget class.
"""

import os
import time

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

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
    # An intentionally empty interval (a pulled program's gap) -- part of
    # the draft/override presentation, not a fake persisted program. Its
    # calm dashed treatment (see _apply_style) is deliberate: open time
    # is an invitation to Put On Air, not an error state.
    "open": "Open Time",
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
    # Near-transparent face + soft neutral outline -- quieter than every
    # real program category on purpose.
    "open": ("rgba(16, 19, 44, 90)", "rgba(158, 172, 210, 80)"),
}

_TEXT_COLOR = "rgba(210, 222, 252, 235)"
_TEXT_DIM = "rgba(158, 172, 210, 220)"
_SELECTED_BORDER = "rgba(255, 218, 96, 235)"

# Small corner pills distinguishing generated / unsaved-draft / saved-
# override state (Phase 2.1 spec section 4) -- a corner badge, never a
# title-covering banner, and only rendered at the "wide" content tier
# where there's real room beside the title. Selection stays the strongest
# visual cue (the yellow border, unaffected by any of this); these badges
# are deliberately quieter than that.
_DRAFT_BADGE_STYLE = (
    "background: rgba(255, 188, 10, 215); color: rgba(40, 28, 4, 255);"
    " font-size: 8px; font-weight: 700; letter-spacing: 0.5px;"
    " border-radius: 5px; padding: 1px 5px;"
)
_SAVED_BADGE_STYLE = (
    "background: rgba(130, 200, 170, 130); color: rgba(8, 26, 18, 255);"
    " font-size: 8px; font-weight: 700; letter-spacing: 0.5px;"
    " border-radius: 5px; padding: 1px 5px;"
)
_ATTENTION_BADGE_STYLE = (
    "background: rgba(255, 130, 120, 215); color: rgba(40, 8, 6, 255);"
    " font-size: 8px; font-weight: 700; letter-spacing: 0.5px;"
    " border-radius: 5px; padding: 1px 5px;"
)


def _badge_spec(block):
    """(text, stylesheet) for this block's corner badge, or None. Purely a
    function of `block.source`/`media_type`/`raw_entries` -- no new state,
    so it can never drift from what the inspector says about the same
    block (utility_panels.py's build_selected_program_footer mirrors this
    same source/path logic for its text-only equivalent).
    """
    if block.source == "draft":
        return ("DRAFT", _DRAFT_BADGE_STYLE)
    if block.source == "override":
        if block.media_type != "open":
            path = (block.raw_entries[0] or {}).get("path", "") if block.raw_entries else ""
            if path and not os.path.isfile(path):
                return ("NEEDS ATTENTION", _ATTENTION_BADGE_STYLE)
        return ("SAVED", _SAVED_BADGE_STYLE)
    return None


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
    # Phase 3 direct manipulation -- mechanical mouse tracking only; every
    # interpretation (destination channel/time, validity, conflicts) is
    # owned by ProgrammingBoard/the workspace, not this widget. Each
    # signal carries (self, global_pos) so the receiver can read
    # `widget.block` and map the position itself.
    drag_started = Signal(object, QPoint)
    drag_moved = Signal(object, QPoint)
    drag_finished = Signal(object, QPoint)

    def __init__(self, block, px_per_minute=PX_PER_MINUTE, parent=None, draggable=True):
        super().__init__(parent)
        self.block = block
        self._is_selected = False
        # A click must always still select (spec section 7: "A simple
        # click must continue selecting the program") -- dragging is an
        # ADDITIONAL behavior layered on the same press, gated by the
        # platform's real drag-start distance so an ordinary click never
        # misfires as a drag. Never draggable for open time (nothing to
        # move), a commercial pod (protected, same as Pull), or a
        # companion/no-data lane (draggable=False, set by the caller from
        # lane.channel_type/has_data).
        self._draggable = bool(draggable) and block.media_type != "open" and not block.is_commercial
        self._press_global = None
        self._dragging = False
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

        if self._level == "wide":
            badge_spec = _badge_spec(block)
            if badge_spec is not None:
                badge_text, badge_style = badge_spec
                badge = QLabel(badge_text, self._card)
                badge.setStyleSheet(badge_style)
                badge.adjustSize()
                badge.move(max(0, card_width - badge.width() - 6), 6)
                badge.show()
                badge.raise_()

        time_label = _format_time_range(block.true_start, block.true_end)
        # true_end - true_start, not block.duration -- duration is clipped
        # to the visible window (a program landing near the window's edge
        # would otherwise show its full, uncropped time range next to a
        # truncated-looking minute count).
        minutes = max(1, round((block.true_end - block.true_start) / 60))
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

        is_open = self.block.media_type == "open"
        title_text = self.block.title or "Untitled"
        title_lbl = QLabel(title_text)
        title_lbl.setWordWrap(False)
        # Open Time reads as quiet availability, not a program: dim title,
        # same layout.
        title_color = _TEXT_DIM if is_open else _TEXT_COLOR
        title_lbl.setStyleSheet(f"color: {title_color}; font-weight: 600; font-size: 12px; background: transparent;")
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
            # true_end - true_start, matching the time_lbl range above --
            # see the tooltip's identical fix earlier in __init__.
            minutes = max(1, round((self.block.true_end - self.block.true_start) / 60))
            detail = f"Available · {minutes} min" if is_open else f"{MEDIA_TYPE_LABELS.get(self.block.media_type, '')} · {minutes} min"
            type_lbl = QLabel(detail)
            type_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 10px; background: transparent;")
            layout.addWidget(type_lbl)

        layout.addStretch(1)

    def _apply_style(self):
        bg, border = MEDIA_TYPE_ACCENTS.get(self.block.media_type, MEDIA_TYPE_ACCENTS["tv"])
        border_color = _SELECTED_BORDER if self._is_selected else border
        border_width = 2 if self._is_selected else 1
        # Open time gets a dashed outline (unless selected -- the solid
        # yellow selection border stays the one selection language for
        # every block type).
        border_style = "dashed" if self.block.media_type == "open" and not self._is_selected else "solid"
        self._card.setStyleSheet(
            "QFrame#scheduleProgramBlock {"
            f" background: {bg};"
            f" border: {border_width}px {border_style} {border_color};"
            " border-radius: 11px;"
            "}"
        )

    def set_selected(self, is_selected):
        self._is_selected = bool(is_selected)
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.block)
            self._press_global = event.globalPosition().toPoint()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_global is not None and event.buttons() & Qt.LeftButton:
            current = event.globalPosition().toPoint()
            if not self._dragging:
                if self._draggable and (current - self._press_global).manhattanLength() >= QApplication.startDragDistance():
                    self._dragging = True
                    self.drag_started.emit(self, current)
            if self._dragging:
                self.drag_moved.emit(self, current)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._dragging:
                self.drag_finished.emit(self, event.globalPosition().toPoint())
            self._press_global = None
            self._dragging = False
        super().mouseReleaseEvent(event)


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

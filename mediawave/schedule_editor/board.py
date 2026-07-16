"""ProgrammingBoard: the hero widget of the Schedule Editor -- a time-ruler
header (frozen vertically, scrolls horizontally with the grid), a channel
identity column (frozen horizontally, scrolls vertically with the grid), and
the scrolling grid of channel rows in between.

Built from one real QScrollArea (the grid) plus two "frozen" sibling
widgets whose inner content is manually offset to match the grid's
scrollbars -- the standard Qt frozen-row/frozen-column technique, chosen
over nested QScrollAreas specifically because nested scroll areas fight each
other for wheel/trackpad events (the spec's own explicit requirement).
"""

import time

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QWidget,
)

from .channel_row import ChannelIdentityCell, ChannelRowStrip
from .layout_constants import IDENTITY_COLUMN_WIDTH, ROW_HEIGHT, TIME_HEADER_HEIGHT
from .schedule_model import PX_PER_MINUTE

_BOARD_BG = "rgba(9, 11, 27, 255)"
_RULER_BG = "rgba(16, 19, 44, 245)"
_RULER_BORDER = "rgba(255, 255, 255, 24)"
_RULER_TEXT = "rgba(158, 172, 210, 230)"
_CORNER_BG = "rgba(13, 16, 38, 255)"
_NOW_LINE_COLOR = "rgba(255, 218, 96, 210)"

_TICK_INTERVAL_SECONDS = 30 * 60


class _TimeRulerContent(QWidget):
    def __init__(self, window_start, window_end, px_per_minute, parent=None):
        super().__init__(parent)
        total_minutes = max(0.0, (window_end - window_start) / 60.0)
        self.setFixedSize(round(total_minutes * px_per_minute), TIME_HEADER_HEIGHT)
        self.setStyleSheet(f"background: {_RULER_BG};")

        tick = window_start - (window_start % _TICK_INTERVAL_SECONDS)
        if tick < window_start:
            tick += _TICK_INTERVAL_SECONDS
        while tick < window_end:
            x = round((tick - window_start) / 60.0 * px_per_minute)
            mark = QFrame(self)
            mark.setGeometry(x, TIME_HEADER_HEIGHT - 8, 1, 8)
            mark.setStyleSheet(f"background: {_RULER_BORDER};")
            mark.show()

            label = QLabel(time.strftime("%-I:%M %p", time.localtime(tick)), self)
            label.setStyleSheet(f"color: {_RULER_TEXT}; font-size: 10px; background: transparent;")
            label.move(x + 4, 4)
            label.show()
            tick += _TICK_INTERVAL_SECONDS


class _GridContent(QWidget):
    def __init__(self, lanes, window_start, window_end, px_per_minute, parent=None):
        super().__init__(parent)
        total_minutes = max(0.0, (window_end - window_start) / 60.0)
        width = round(total_minutes * px_per_minute)
        height = len(lanes) * ROW_HEIGHT
        self.setFixedSize(width, max(height, 1))
        self.setStyleSheet(f"background: {_BOARD_BG};")

        self.row_strips = []
        for index, lane in enumerate(lanes):
            strip = ChannelRowStrip(lane, window_start, window_end, px_per_minute=px_per_minute, parent=self)
            strip.move(0, index * ROW_HEIGHT)
            strip.show()
            self.row_strips.append(strip)

        now = time.time()
        if window_start <= now < window_end:
            line = QFrame(self)
            x = round((now - window_start) / 60.0 * px_per_minute)
            line.setGeometry(x, 0, 2, max(height, 1))
            line.setStyleSheet(f"background: {_NOW_LINE_COLOR};")
            line.show()
            self.now_line = line
            self.now_line_x = x
        else:
            self.now_line = None
            self.now_line_x = 0


class ProgrammingBoard(QWidget):
    """The full board: corner + ruler + identity column + scrolling grid."""

    program_selected = Signal(object)  # ProgramBlock
    channel_selected = Signal(str)  # channel_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_widget = None
        self._px_per_minute = PX_PER_MINUTE

        outer = QGridLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        corner = QFrame()
        corner.setFixedSize(IDENTITY_COLUMN_WIDTH, TIME_HEADER_HEIGHT)
        corner.setStyleSheet(f"background: {_CORNER_BG}; border-bottom: 1px solid {_RULER_BORDER};")
        outer.addWidget(corner, 0, 0)

        self._ruler_viewport = QWidget()
        self._ruler_viewport.setFixedHeight(TIME_HEADER_HEIGHT)
        self._ruler_viewport.setStyleSheet(f"background: {_RULER_BG}; border-bottom: 1px solid {_RULER_BORDER};")
        self._ruler_content = None
        outer.addWidget(self._ruler_viewport, 0, 1)

        self._identity_viewport = QWidget()
        self._identity_viewport.setFixedWidth(IDENTITY_COLUMN_WIDTH)
        self._identity_content = None
        outer.addWidget(self._identity_viewport, 1, 0)

        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(False)
        self._grid_scroll.setFrameShape(QFrame.NoFrame)
        self._grid_scroll.viewport().setAutoFillBackground(False)
        self._grid_scroll.horizontalScrollBar().valueChanged.connect(self._on_h_scroll)
        self._grid_scroll.verticalScrollBar().valueChanged.connect(self._on_v_scroll)
        outer.addWidget(self._grid_scroll, 1, 1)

        outer.setColumnStretch(1, 1)
        outer.setRowStretch(1, 1)

        self._grid_content = None
        self.identity_cells = []

    def _on_h_scroll(self, value):
        if self._ruler_content is not None:
            self._ruler_content.move(-value, 0)

    def _on_v_scroll(self, value):
        if self._identity_content is not None:
            self._identity_content.move(0, -value)

    def set_lanes(self, lanes, window_start, window_end):
        """Rebuilds the whole board for a new set of channel lanes/window.
        Hides and schedules deletion of every previous row/identity widget
        first (Qt's removeWidget-doesn't-hide gotcha -- see
        StudioSection.set_content's docstring for why the explicit hide()
        matters) so repeated refreshes never leave stale, overlapping
        widgets behind.
        """
        self._selected_widget = None

        if self._ruler_content is not None:
            self._ruler_content.hide()
            self._ruler_content.deleteLater()
        if self._grid_content is not None:
            self._grid_content.hide()
            self._grid_content.deleteLater()
        if self._identity_content is not None:
            self._identity_content.hide()
            self._identity_content.deleteLater()
        self.identity_cells = []

        self._ruler_content = _TimeRulerContent(
            window_start, window_end, self._px_per_minute, parent=self._ruler_viewport
        )
        self._ruler_content.move(0, 0)
        self._ruler_content.show()

        self._grid_content = _GridContent(lanes, window_start, window_end, self._px_per_minute, parent=None)
        self._grid_scroll.setWidget(self._grid_content)
        for strip in self._grid_content.row_strips:
            strip.block_widget_selected.connect(self._on_block_selected)

        self._identity_content = QWidget(self._identity_viewport)
        self._identity_content.setFixedSize(IDENTITY_COLUMN_WIDTH, max(len(lanes) * ROW_HEIGHT, 1))
        for index, lane in enumerate(lanes):
            cell = ChannelIdentityCell(lane, parent=self._identity_content)
            cell.selected.connect(self.channel_selected.emit)
            cell.move(0, index * ROW_HEIGHT)
            cell.show()
            self.identity_cells.append(cell)
        self._identity_content.move(0, 0)
        self._identity_content.show()

        self._window_start = window_start
        self._window_end = window_end

    def _on_block_selected(self, widget):
        if self._selected_widget is not None and self._selected_widget is not widget:
            self._selected_widget.set_selected(False)
        widget.set_selected(True)
        self._selected_widget = widget
        self.program_selected.emit(widget.block)

    def scroll_to_now(self):
        """Home/Today action: centers the current-time line in the visible
        viewport when it's within the current window; otherwise scrolls to
        the window's start.
        """
        if self._grid_content is None:
            return
        now_line = getattr(self._grid_content, "now_line", None)
        target_x = self._grid_content.now_line_x if now_line is not None else 0
        viewport_width = self._grid_scroll.viewport().width()
        self._grid_scroll.horizontalScrollBar().setValue(max(0, target_x - viewport_width // 2))

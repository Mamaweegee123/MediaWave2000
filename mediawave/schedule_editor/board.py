"""ProgrammingBoard: the hero widget of the Schedule Editor -- a time-ruler
header (frozen, spans the board's full width), a channel identity column
(frozen horizontally, scrolls vertically with the grid), and the grid of
channel rows in between.

The guide scrolls both ways: real QScrollArea, real scrollbars, native
trackpad gestures. `px_per_minute` (schedule_model.PX_PER_MINUTE) is a
fixed scale, not fit to the viewport -- a 30-minute block stays a
comfortably readable size regardless of how much of the visible window
happens to fit on screen at once; the surrounding application shell never
needs to grow to accommodate it; the guide's own QScrollArea clips and
scrolls the excess instead. The ruler and the identity column are each
kept in sync with the grid's scroll position via `_on_h_scroll`/
`_on_v_scroll`, the same "frozen sibling" pattern on both axes.
"""

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QWidget,
)

from .board_ticks import tick_times
from .channel_row import ChannelIdentityCell, ChannelRowStrip
from .layout_constants import IDENTITY_COLUMN_WIDTH, ROW_HEIGHT, TIME_HEADER_HEIGHT
from .schedule_model import PX_PER_MINUTE

_BOARD_BG = "rgba(9, 11, 27, 255)"
_RULER_BG = "rgba(16, 19, 44, 245)"
_RULER_BORDER = "rgba(255, 255, 255, 24)"
_RULER_TEXT = "rgba(158, 172, 210, 230)"
_CORNER_DATE_TEXT = "rgba(138, 152, 190, 190)"
_CORNER_BG = "rgba(13, 16, 38, 255)"
_NOW_LINE_COLOR = "rgba(255, 218, 96, 210)"
_NOW_BADGE_BG = "rgba(255, 218, 96, 235)"
_NOW_BADGE_TEXT = "rgba(20, 16, 4, 255)"


class _TimeRulerContent(QWidget):
    def __init__(self, window_start, window_end, px_per_minute, parent=None):
        super().__init__(parent)
        total_minutes = max(0.0, (window_end - window_start) / 60.0)
        self.setFixedSize(round(total_minutes * px_per_minute), TIME_HEADER_HEIGHT)
        self.setStyleSheet(f"background: {_RULER_BG};")

        for tick in tick_times(window_start, window_end):
            x = round((tick - window_start) / 60.0 * px_per_minute)
            mark = QFrame(self)
            mark.setGeometry(x, TIME_HEADER_HEIGHT - 10, 1, 10)
            mark.setStyleSheet(f"background: {_RULER_BORDER};")
            mark.show()

            label = QLabel(time.strftime("%-I:%M %p", time.localtime(tick)), self)
            # Font set via QFont (not stylesheet font-size) so sizeHint's
            # width is measured with the real rendering font.
            label_font = label.font()
            label_font.setPixelSize(12)
            label_font.setWeight(QFont.DemiBold)
            label.setFont(label_font)
            label.setStyleSheet(f"color: {_RULER_TEXT}; background: transparent;")
            label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            label.setFixedSize(label.sizeHint().width() + 2, TIME_HEADER_HEIGHT)
            label.move(x + 6, 0)
            label.show()

        now = time.time()
        if window_start <= now < window_end:
            now_x = round((now - window_start) / 60.0 * px_per_minute)
            badge = QLabel(time.strftime("%-I:%M %p", time.localtime(now)), self)
            badge.setStyleSheet(
                f"background: {_NOW_BADGE_BG}; color: {_NOW_BADGE_TEXT};"
                " font-size: 10px; font-weight: 700; border-radius: 8px; padding: 2px 8px;"
            )
            badge.adjustSize()
            badge.move(max(0, now_x - badge.width() // 2), (TIME_HEADER_HEIGHT - badge.height()) // 2)
            badge.show()
            badge.raise_()


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
            x = round((now - window_start) / 60.0 * px_per_minute)
            line = QFrame(self)
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
        self._selected_identity_cell = None
        self._px_per_minute = PX_PER_MINUTE
        self._lanes = None
        self._window_start = 0
        self._window_end = 0

        outer = QGridLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # The corner cell (above the identity column, beside the ruler)
        # carries the compact viewed-day label -- "Thu 7-16-26" -- so the
        # date reads as part of the guide's frozen header, not a page
        # heading. Text set via set_corner_text (the workspace's
        # _refresh_board keeps it in sync with day navigation).
        self._corner_label = QLabel()
        self._corner_label.setObjectName("scheduleCornerDate")
        self._corner_label.setFixedSize(IDENTITY_COLUMN_WIDTH, TIME_HEADER_HEIGHT)
        # Right-aligned and tucked against the ruler's edge, with a
        # smaller/dimmer weight than the ruler's own 12px DemiBold time
        # labels -- reads as the first (secondary) cell of the guide
        # ruler row, not a detached, equal-weight label floating in the
        # corner's dead space.
        self._corner_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._corner_label.setContentsMargins(0, 0, 10, 0)
        corner_font = self._corner_label.font()
        corner_font.setPixelSize(11)
        corner_font.setWeight(QFont.Normal)
        self._corner_label.setFont(corner_font)
        self._corner_label.setStyleSheet(
            f"QLabel#scheduleCornerDate {{ background: {_CORNER_BG};"
            f" border-bottom: 1px solid {_RULER_BORDER}; color: {_CORNER_DATE_TEXT}; }}"
        )
        outer.addWidget(self._corner_label, 0, 0)

        self._ruler_viewport = QWidget()
        self._ruler_viewport.setFixedHeight(TIME_HEADER_HEIGHT)
        self._ruler_viewport.setStyleSheet(f"background: {_RULER_BG}; border-bottom: 1px solid {_RULER_BORDER};")
        self._ruler_content = None
        outer.addWidget(self._ruler_viewport, 0, 1)

        self._identity_viewport = QWidget()
        self._identity_viewport.setFixedWidth(IDENTITY_COLUMN_WIDTH)
        self._identity_content = None
        outer.addWidget(self._identity_viewport, 1, 0)

        # A real QScrollArea on both axes -- its own footprint is governed
        # by the surrounding layout (outer's column/row stretch below), not
        # by its content, so wider-than-viewport guide content never grows
        # the dialog itself; it just becomes scrollable, same as the
        # vertical axis always has been.
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(False)
        self._grid_scroll.setFrameShape(QFrame.NoFrame)
        self._grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # The square where the two scrollbars meet is otherwise painted
        # with the platform default (white) -- against the dark board it
        # read as a stray bracket-shaped artifact peeking around the
        # rounded scrollbar ends.
        self._grid_scroll.setStyleSheet("QScrollArea::corner { background: transparent; }")
        self._grid_scroll.viewport().setAutoFillBackground(False)
        self._grid_scroll.verticalScrollBar().valueChanged.connect(self._on_v_scroll)
        self._grid_scroll.horizontalScrollBar().valueChanged.connect(self._on_h_scroll)
        outer.addWidget(self._grid_scroll, 1, 1)

        outer.setColumnStretch(1, 1)
        outer.setRowStretch(1, 1)

        self._grid_content = None
        self.identity_cells = []

    def _on_v_scroll(self, value):
        if self._identity_content is not None:
            self._identity_content.move(0, -value)

    def _on_h_scroll(self, value):
        if self._ruler_content is not None:
            self._ruler_content.move(-value, 0)

    def set_corner_text(self, text):
        """The compact date label in the frozen corner cell."""
        self._corner_label.setText(text)

    def set_lanes(self, lanes, window_start, window_end):
        """Records the lanes/window to render and (re)builds the board."""
        self._lanes = lanes
        self._window_start = window_start
        self._window_end = window_end
        self._rebuild()

    def _rebuild(self):
        """Tears down and reconstructs every board widget at the fixed
        `PX_PER_MINUTE` scale. Hides and schedules deletion of every
        previous row/identity widget first (Qt's removeWidget-doesn't-hide
        gotcha -- see StudioSection.set_content's docstring for why the
        explicit hide() matters) so a repeated rebuild (a data refresh)
        never leaves stale, overlapping widgets behind.
        """
        if self._lanes is None:
            return
        lanes, window_start, window_end = self._lanes, self._window_start, self._window_end

        self._selected_widget = None
        self._selected_identity_cell = None

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
            cell.selected.connect(self._on_channel_row_clicked)
            cell.move(0, index * ROW_HEIGHT)
            cell.show()
            self.identity_cells.append(cell)
        self._identity_content.move(0, 0)
        self._identity_content.show()

    def _select_identity_cell(self, channel_id):
        """The subtle "current selection context" state on the identity
        column -- set both when a channel row is clicked directly and when
        a program is selected (its channel is the selection context
        either way, which is why Next Up/Channel Defaults update in both
        cases). Distinct from `_selected_widget`'s strong per-program
        state.
        """
        if self._selected_identity_cell is not None:
            self._selected_identity_cell.set_selected(False)
        self._selected_identity_cell = next(
            (cell for cell in self.identity_cells if cell.channel_id == channel_id), None
        )
        if self._selected_identity_cell is not None:
            self._selected_identity_cell.set_selected(True)

    def _on_channel_row_clicked(self, channel_id):
        self._select_identity_cell(channel_id)
        self.channel_selected.emit(channel_id)

    def scroll_positions(self):
        """(horizontal, vertical) scrollbar values -- captured before a
        draft-triggered set_lanes rebuild so an edit doesn't yank the
        board back to the window's left edge.
        """
        return (
            self._grid_scroll.horizontalScrollBar().value(),
            self._grid_scroll.verticalScrollBar().value(),
        )

    def set_scroll_positions(self, positions):
        horizontal, vertical = positions
        self._grid_scroll.horizontalScrollBar().setValue(horizontal)
        self._grid_scroll.verticalScrollBar().setValue(vertical)

    def select_block_at(self, channel_id, start, tolerance=1.5):
        """Programmatically select the block starting at (about) `start`
        on the given channel -- the after-rebuild half of keeping
        selection stable across draft edits. Runs the exact same
        selection path a click does (so the same signals fire and the
        side panels refresh). Returns True if a block was found.
        """
        if self._grid_content is None:
            return False
        for strip in self._grid_content.row_strips:
            if strip.channel_id != channel_id:
                continue
            for widget in strip.block_widgets:
                if abs(widget.block.start - start) <= tolerance:
                    self._on_block_selected(widget)
                    return True
        return False

    def _on_block_selected(self, widget):
        if self._selected_widget is not None and self._selected_widget is not widget:
            self._selected_widget.set_selected(False)
        widget.set_selected(True)
        self._selected_widget = widget
        self._select_identity_cell(widget.block.channel_id)
        self.program_selected.emit(widget.block)

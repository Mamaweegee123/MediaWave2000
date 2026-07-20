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

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
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
from .commands import snap_to_interval
from .layout_constants import IDENTITY_COLUMN_WIDTH, ROW_HEIGHT, TIME_HEADER_HEIGHT
from .schedule_model import PX_PER_MINUTE

# Drag placement preview colors (Phase 3 spec section 7) -- valid/conflict/
# invalid are distinguished by color AND by the label text set alongside
# them (never color alone, per that section's own instruction).
_PREVIEW_VALID_BORDER = "rgba(120, 220, 160, 235)"
_PREVIEW_VALID_BG = "rgba(120, 220, 160, 60)"
_PREVIEW_CONFLICT_BORDER = "rgba(255, 170, 90, 235)"
_PREVIEW_CONFLICT_BG = "rgba(255, 170, 90, 60)"
_PREVIEW_INVALID_BORDER = "rgba(158, 172, 210, 160)"
_PREVIEW_INVALID_BG = "rgba(158, 172, 210, 40)"

# How close the pointer must get to a viewport edge to trigger autoscroll,
# and how far each tick nudges the scrollbar -- a small zone/step so
# autoscroll assists reaching off-screen destinations without making
# precise placement near an edge unreachable (spec section 8).
_AUTOSCROLL_EDGE_PX = 36
_AUTOSCROLL_STEP_PX = 14
_AUTOSCROLL_INTERVAL_MS = 30

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
    # Phase 3: emitted once, on a valid drop -- (source_block,
    # destination_channel_id, destination_start). The board never applies
    # a move itself; the workspace owns validation/execution, reusing the
    # exact same path Move To… uses (see dialog.py's _try_move).
    move_drop = Signal(object, str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_widget = None
        self._selected_identity_cell = None
        self._px_per_minute = PX_PER_MINUTE
        self._lanes = None
        self._window_start = 0
        self._window_end = 0

        # Phase 3 drag state -- one drag at a time, no persisted list of
        # its own beyond what's needed to render the current preview and
        # answer autoscroll ticks.
        self._drag_block = None
        self._drag_preview = None
        self._drop_validator = None  # callback(block, channel_id, start) -> (state, label)
        self._last_pointer_viewport_pos = None
        self._autoscroll_timer = QTimer(self)
        self._autoscroll_timer.setInterval(_AUTOSCROLL_INTERVAL_MS)
        self._autoscroll_timer.timeout.connect(self._autoscroll_tick)

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
        # A rebuild mid-drag would destroy the preview's parent (the old
        # _grid_content) out from under it -- nothing in this single-
        # threaded UI normally mutates the draft while a drag is active,
        # but this guard keeps that combination safe rather than crashing
        # on a dangling preview reference if it ever happens.
        self._cancel_drag_state()

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
            strip.block_drag_started.connect(self._on_drag_started)
            strip.block_drag_moved.connect(self._on_drag_moved)
            strip.block_drag_finished.connect(self._on_drag_finished)

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

    # ── Phase 3: drag-and-drop ─────────────────────────────────────────

    def set_drop_validator(self, callback):
        """`callback(block, channel_id, start) -> (state, label)` where
        state is "valid" | "conflict" | "invalid" -- consulted on every
        pointer move during a drag so the preview can be colored/labeled
        without the board itself knowing anything about drafts, channels,
        or commands.
        """
        self._drop_validator = callback

    @property
    def is_dragging(self):
        return self._drag_block is not None

    def cancel_drag(self):
        """Escape cancels an active drag (spec section 15) -- restores
        the original visual state with no draft mutation, since no
        `move_drop` is ever emitted for a cancelled drag.
        """
        self._cancel_drag_state()

    def _cancel_drag_state(self):
        self._autoscroll_timer.stop()
        self._clear_preview()
        self._drag_block = None
        self._last_pointer_viewport_pos = None

    def _on_drag_started(self, widget, global_pos):
        self._drag_block = widget.block
        self._ensure_preview()
        self._autoscroll_timer.start()
        self._update_drag_preview(global_pos)

    def _on_drag_moved(self, widget, global_pos):
        if self._drag_block is None:
            return
        self._update_drag_preview(global_pos)

    def _on_drag_finished(self, widget, global_pos):
        if self._drag_block is None:
            return
        source_block = self._drag_block
        result = self._channel_and_time_at(global_pos)
        self._cancel_drag_state()
        if result is not None:
            channel_id, start = result
            self.move_drop.emit(source_block, channel_id, start)

    def _viewport_pos_from_global(self, global_pos):
        return self._grid_scroll.viewport().mapFromGlobal(global_pos)

    def _channel_and_time_at(self, global_pos):
        """(channel_id, snapped_start) for a global pointer position, or
        None if it isn't over any channel lane. Accounts for the grid's
        own scroll offset (mapFrom already resolves this via the actual
        widget geometry) -- the frozen identity column lives in a
        completely separate viewport, so it needs no separate correction
        here at all.
        """
        if self._grid_content is None or self._lanes is None:
            return None
        viewport_pos = self._viewport_pos_from_global(global_pos)
        if not self._grid_scroll.viewport().rect().contains(viewport_pos):
            return None
        content_pos = self._grid_content.mapFromGlobal(global_pos)
        if content_pos.x() < 0 or content_pos.y() < 0:
            return None
        row_index = int(content_pos.y() // ROW_HEIGHT)
        if row_index < 0 or row_index >= len(self._lanes):
            return None
        channel_id = self._lanes[row_index].channel_id
        minutes = content_pos.x() / self._px_per_minute
        raw_start = self._window_start + minutes * 60.0
        return channel_id, snap_to_interval(raw_start)

    def _ensure_preview(self):
        if self._drag_preview is not None or self._grid_content is None:
            return
        preview = QFrame(self._grid_content)
        preview.setObjectName("scheduleDragPreview")
        preview.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        label = QLabel(preview)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: white; font-size: 11px; font-weight: 700; background: transparent;")
        preview.hide()
        self._drag_preview = preview
        self._drag_preview_label = label

    def _clear_preview(self):
        if self._drag_preview is not None:
            self._drag_preview.hide()
            self._drag_preview.deleteLater()
        self._drag_preview = None
        self._drag_preview_label = None

    def _update_drag_preview(self, global_pos):
        self._last_pointer_viewport_pos = self._viewport_pos_from_global(global_pos)
        result = self._channel_and_time_at(global_pos)
        if result is None or self._drag_block is None or self._drag_preview is None:
            if self._drag_preview is not None:
                self._drag_preview.hide()
            return

        channel_id, start = result
        duration = max(0.0, self._drag_block.true_end - self._drag_block.true_start)
        end = start + duration
        state, label_text = "valid", ""
        if self._drop_validator is not None:
            state, label_text = self._drop_validator(self._drag_block, channel_id, start)

        if state == "conflict":
            border, bg = _PREVIEW_CONFLICT_BORDER, _PREVIEW_CONFLICT_BG
        elif state == "invalid":
            border, bg = _PREVIEW_INVALID_BORDER, _PREVIEW_INVALID_BG
        else:
            border, bg = _PREVIEW_VALID_BORDER, _PREVIEW_VALID_BG
        self._drag_preview.setStyleSheet(
            f"QFrame#scheduleDragPreview {{ background: {bg}; border: 2px dashed {border}; border-radius: 10px; }}"
        )

        row_index = next((i for i, lane in enumerate(self._lanes) if lane.channel_id == channel_id), None)
        if row_index is None:
            self._drag_preview.hide()
            return
        x = round((start - self._window_start) / 60.0 * self._px_per_minute)
        width = max(1, round(duration / 60.0 * self._px_per_minute))
        y = row_index * ROW_HEIGHT + 4
        self._drag_preview.setGeometry(max(0, x), y, width, ROW_HEIGHT - 8)
        self._drag_preview_label.setGeometry(0, 0, width, ROW_HEIGHT - 8)
        self._drag_preview_label.setText(label_text or self._format_preview_time(start, end))
        self._drag_preview.show()
        self._drag_preview.raise_()

    def _format_preview_time(self, start, end):
        start_label = time.strftime("%-I:%M", time.localtime(start))
        end_label = time.strftime("%-I:%M %p", time.localtime(end))
        return f"{start_label}–{end_label}"

    def _autoscroll_tick(self):
        if self._drag_block is None or self._last_pointer_viewport_pos is None:
            self._autoscroll_timer.stop()
            return
        viewport = self._grid_scroll.viewport()
        rect = viewport.rect()
        pos = self._last_pointer_viewport_pos
        h_bar = self._grid_scroll.horizontalScrollBar()
        v_bar = self._grid_scroll.verticalScrollBar()
        moved = False
        if pos.x() < rect.left() + _AUTOSCROLL_EDGE_PX and h_bar.value() > h_bar.minimum():
            h_bar.setValue(max(h_bar.minimum(), h_bar.value() - _AUTOSCROLL_STEP_PX))
            moved = True
        elif pos.x() > rect.right() - _AUTOSCROLL_EDGE_PX and h_bar.value() < h_bar.maximum():
            h_bar.setValue(min(h_bar.maximum(), h_bar.value() + _AUTOSCROLL_STEP_PX))
            moved = True
        if pos.y() < rect.top() + _AUTOSCROLL_EDGE_PX and v_bar.value() > v_bar.minimum():
            v_bar.setValue(max(v_bar.minimum(), v_bar.value() - _AUTOSCROLL_STEP_PX))
            moved = True
        elif pos.y() > rect.bottom() - _AUTOSCROLL_EDGE_PX and v_bar.value() < v_bar.maximum():
            v_bar.setValue(min(v_bar.maximum(), v_bar.value() + _AUTOSCROLL_STEP_PX))
            moved = True
        if moved:
            # Autoscroll moves content under a STATIONARY pointer -- the
            # preview must be recomputed against the new scroll position,
            # using the same (unchanged) global pointer location.
            global_pos = viewport.mapToGlobal(pos)
            self._update_drag_preview(global_pos)

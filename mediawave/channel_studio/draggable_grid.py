"""Channel Studio's drag-and-drop channel grid — iPhone-icon-style
reorder: dragging a card does not shove other cards around on every
pixel of motion. The dragged card lifts and follows the cursor while
its own slot dims in place; the grid only reflows once the cursor has
held over a *different* card for HOVER_DELAY_MS, and it reflows once
(a clean snap) rather than live-shuffling as the cursor crosses cards.

Kept separate from channel_card.py (card *rendering*) and reorder.py
(pure order-list logic) — this module only owns mouse tracking, the
floating drag copy, and hover timing. Card widgets are built entirely
by the caller; `set_reorder_mode` disables them (via QWidget.setEnabled,
which also disables every child button/checkbox for free) rather than
this module knowing anything about Setup/Remove/Enabled.
"""

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget

from .channel_studio_widgets import FlowLayout
from .reorder import move_item, overlay_top_left

_DRAG_THRESHOLD_PX = 6
_HOVER_DELAY_MS = 380
_DRAGGED_SLOT_OPACITY = 0.35
_OVERLAY_OPACITY = 0.92
_HANDLE_TEXT = "⠿"
_HANDLE_MARGIN = 8


def _event_pos(event):
    # Qt6 (PySide6) prefers position(); older bindings only have pos().
    return event.position().toPoint() if hasattr(event, "position") else event.pos()


class _Slot(QFrame):
    """One card's draggable wrapper. Drag mechanics live here; the card
    inside is never modified by this class beyond enable/disable and a
    dim opacity effect while it's the one being dragged.
    """

    def __init__(self, channel_id, card_widget, grid):
        super().__init__()
        self.channel_id = channel_id
        self.card_widget = card_widget
        self._grid = grid
        self._press_pos = None
        self._dragging = False
        self._reorder_active = False
        self.setFocusPolicy(Qt.StrongFocus)
        # A scoped object name, not a bare "QFrame" selector: Qt stylesheet
        # rules cascade to matching *descendants* too, and card_widget has
        # its own nested QFrames (schedule panel, channel info panel) — a
        # bare "QFrame { border: ... }" rule set here would paint a border
        # on all of those as well, not just this wrapper.
        self.setObjectName("reorderSlot")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card_widget)

        # No QGraphicsEffect at rest, on purpose: attaching one (even at
        # opacity 1.0) forces Qt to composite the card via an offscreen
        # buffer, which can escape the enclosing QScrollArea's clip rect
        # near its edges. Only the card actually being dragged gets one,
        # lazily, in _dim()/_undim() below.
        self.dim_effect = None

        # A small corner badge — not part of the layout (it's an absolutely
        # positioned child, repositioned in resizeEvent), so showing it
        # can't change the card's sizeHint the way adding a layout row or a
        # QSS `border` would. Hidden outside reorder mode.
        self._handle = QLabel(_HANDLE_TEXT, self)
        self._handle.setObjectName("reorderHandle")
        self._handle.setStyleSheet(
            "QLabel#reorderHandle {"
            " color: rgba(210, 224, 255, 245);"
            " background: rgba(68, 108, 235, 130);"
            " border: 1px solid rgba(150, 180, 255, 220);"
            " border-radius: 9px;"
            " font-size: 13px;"
            " font-weight: 700;"
            " padding: 1px 7px;"
            "}"
        )
        self._handle.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._handle.adjustSize()
        self._handle.hide()

    def set_reorder_mode(self, active):
        self.card_widget.setEnabled(not active)
        self.setCursor(Qt.OpenHandCursor if active else Qt.ArrowCursor)
        # `outline` (not `border`): Qt, like CSS, draws outlines outside the
        # box without reserving layout space for them, so this can't change
        # the frame's sizeHint/minimumSizeHint — a `border` here would, and
        # was exactly what shifted the grid from 2 columns to 1 in reorder
        # mode (a couple of extra pixels per card was enough to tip a
        # borderline-fitting row over into wrapping).
        self.setStyleSheet(
            "QFrame#reorderSlot {"
            " outline: 1.5px solid rgba(140, 175, 255, 170);"
            " outline-offset: -1px;"
            "}"
            if active
            else ""
        )
        self._reorder_active = active
        self._handle.setVisible(active)
        if active:
            self._position_handle()

    def _position_handle(self):
        self._handle.adjustSize()
        x = max(0, self.width() - self._handle.width() - _HANDLE_MARGIN)
        self._handle.move(x, _HANDLE_MARGIN)
        self._handle.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Guarded on our own _reorder_active flag, not self._handle.isVisible():
        # set_reorder_mode(True) can run before this slot has its real,
        # laid-out size (Qt still reports its unsized 640x480 default at
        # that point), and isVisible() is unreliable in that same early
        # window — it can still report False right after setVisible(True)
        # if the widget isn't fully mapped to screen yet. That combination
        # left the handle positioned against the wrong (640-wide) box and
        # never corrected once the slot resized down to its real ~430px
        # width. Reacting to every resize while reorder mode is on fixes
        # that regardless of isVisible()'s timing quirks.
        if self._reorder_active:
            self._position_handle()

    def mousePressEvent(self, event):
        if self._grid.reorder_mode and event.button() == Qt.LeftButton:
            self._press_pos = _event_pos(event)
            self._dragging = False
            self.setFocus()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._grid.reorder_mode and (event.buttons() & Qt.LeftButton) and self._press_pos is not None:
            pos = _event_pos(event)
            delta = pos - self._press_pos
            if not self._dragging and delta.manhattanLength() >= _DRAG_THRESHOLD_PX:
                self._dragging = True
                self._grid.begin_drag(self, self._press_pos)
            if self._dragging:
                self._grid.update_drag(QCursor.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._grid.end_drag()
        self._dragging = False
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self._dragging and event.key() == Qt.Key_Escape:
            self._grid.cancel_drag()
            self._dragging = False
        else:
            super().keyPressEvent(event)

    def dim(self):
        """Applied only to the card actually being dragged, only for the
        duration of that drag — see the comment in __init__.
        """
        if self.dim_effect is None:
            self.dim_effect = QGraphicsOpacityEffect(self.card_widget)
            self.card_widget.setGraphicsEffect(self.dim_effect)
        self.dim_effect.setOpacity(_DRAGGED_SLOT_OPACITY)

    def undim(self):
        if self.dim_effect is not None:
            self.card_widget.setGraphicsEffect(None)
            self.dim_effect = None


class DraggableGrid(QWidget):
    """A FlowLayout grid of channel cards that supports iPhone-icon-style
    drag reordering when `reorder_mode` is on. Starts in normal
    (non-draggable, fully interactive) mode.
    """

    def __init__(self, entries, on_order_changed=None, parent=None):
        """`entries` is a list of (channel_id, card_widget) tuples in
        initial display order. `on_order_changed(order)` — if given —
        is called once per drop with the full new id order (not on
        every pixel of motion); callers decide whether/when to persist
        it (see channel_studio_pages.py, which only persists on
        "Done Reordering").
        """
        super().__init__(parent)
        self.reorder_mode = False
        self._on_order_changed = on_order_changed
        self._order = [cid for cid, _ in entries]
        self._slots_by_id = {cid: _Slot(cid, widget, self) for cid, widget in entries}

        self._layout = FlowLayout(self, margin=0, h_spacing=16, v_spacing=16)
        self._relayout()

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._commit_hover)

        self._dragging_id = None
        self._hover_target_id = None
        self._pre_drag_order = None
        self._press_offset = QPoint(0, 0)
        self._overlay = None

    def _relayout(self):
        # Updates suspended for the whole batch: re-adding every slot to
        # the layout one at a time, mid-drag, while the dragged slot's
        # card still has a live QGraphicsOpacityEffect from dim() and a
        # floating overlay is being moved by the same mouse event, was
        # observed to trip Qt's "paint device painted by one painter at a
        # time" warning (harmless — no visual artifact in any of these
        # cards ever showed up — but avoidable) when a reflow landed the
        # same tick as an in-flight effect repaint. Batching into one
        # paint pass at the end removes that overlap instead of chasing
        # the specific interleaving.
        self.setUpdatesEnabled(False)
        try:
            while self._layout.count():
                self._layout.takeAt(0)
            for channel_id in self._order:
                slot = self._slots_by_id.get(channel_id)
                if slot is not None:
                    self._layout.addWidget(slot)
            # FlowLayout's addItem/takeAt (see channel_studio_widgets.py) are
            # minimal QLayout overrides that don't call invalidate() — fine
            # for a layout only ever built once, but this grid mutates an
            # already-visible one, so without an explicit invalidate() Qt
            # never learns the item order changed and never re-runs
            # setGeometry, leaving cards drawn at their old positions.
            self._layout.invalidate()
            self.updateGeometry()
        finally:
            self.setUpdatesEnabled(True)

    def set_reorder_mode(self, active):
        self.reorder_mode = bool(active)
        for slot in self._slots_by_id.values():
            slot.set_reorder_mode(self.reorder_mode)
        if not self.reorder_mode:
            self.cancel_drag()

    def current_order(self):
        return list(self._order)

    # ---- drag lifecycle --------------------------------------------------

    def begin_drag(self, slot, press_pos):
        self._dragging_id = slot.channel_id
        self._pre_drag_order = list(self._order)
        self._press_offset = press_pos
        self._hover_target_id = None

        window = self.window()
        pixmap = slot.card_widget.grab()
        overlay = QLabel(window)
        overlay.setPixmap(pixmap)
        # slot.card_widget.size(), NOT pixmap.size(): grab() returns a
        # pixmap sized in *device* pixels (e.g. 2x on a Retina display),
        # while QWidget sizes are logical/device-independent. Fixing the
        # overlay to the raw pixmap size made it render far larger than
        # the real card, throwing off the cursor-hotspot math below even
        # though that math itself was correct — the ghost visibly drifted
        # away from the click point as a result.
        overlay.setFixedSize(slot.card_widget.size())
        overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        overlay_effect = QGraphicsOpacityEffect(overlay)
        overlay_effect.setOpacity(_OVERLAY_OPACITY)
        overlay.setGraphicsEffect(overlay_effect)
        overlay.move(window.mapFromGlobal(slot.card_widget.mapToGlobal(QPoint(0, 0))))
        overlay.show()
        overlay.raise_()
        self._overlay = overlay

        slot.dim()

    def update_drag(self, global_cursor_pos):
        if self._overlay is None or self._dragging_id is None:
            return
        window = self.window()
        top_left_x, top_left_y = overlay_top_left(
            (global_cursor_pos.x(), global_cursor_pos.y()),
            (self._press_offset.x(), self._press_offset.y()),
        )
        self._overlay.move(window.mapFromGlobal(QPoint(top_left_x, top_left_y)))

        local_point = self.mapFromGlobal(global_cursor_pos)
        target = self._slot_at(local_point, exclude_id=self._dragging_id)
        target_id = target.channel_id if target is not None else None
        if target_id != self._hover_target_id:
            self._hover_target_id = target_id
            self._hover_timer.stop()
            if target_id is not None:
                self._hover_timer.start(_HOVER_DELAY_MS)

    def end_drag(self):
        self._hover_timer.stop()
        changed = self._order != self._pre_drag_order if self._pre_drag_order is not None else False
        self._cleanup_drag_visuals()
        if changed and self._on_order_changed is not None:
            self._on_order_changed(list(self._order))
        self._dragging_id = None
        self._hover_target_id = None
        self._pre_drag_order = None

    def cancel_drag(self):
        self._hover_timer.stop()
        if self._pre_drag_order is not None and self._order != self._pre_drag_order:
            self._order = list(self._pre_drag_order)
            self._relayout()
        self._cleanup_drag_visuals()
        self._dragging_id = None
        self._hover_target_id = None
        self._pre_drag_order = None

    def _commit_hover(self):
        if self._dragging_id is None or self._hover_target_id is None:
            return
        if self._hover_target_id == self._dragging_id:
            return
        try:
            from_index = self._order.index(self._dragging_id)
            to_index = self._order.index(self._hover_target_id)
        except ValueError:
            return
        self._order = move_item(self._order, from_index, to_index)
        self._relayout()

    def _slot_at(self, local_point, exclude_id=None):
        for channel_id in self._order:
            if channel_id == exclude_id:
                continue
            slot = self._slots_by_id.get(channel_id)
            if slot is not None and slot.geometry().contains(local_point):
                return slot
        return None

    def _cleanup_drag_visuals(self):
        if self._overlay is not None:
            self._overlay.deleteLater()
            self._overlay = None
        if self._dragging_id is not None:
            slot = self._slots_by_id.get(self._dragging_id)
            if slot is not None:
                slot.undim()

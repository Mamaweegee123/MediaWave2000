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
from .reorder import move_item

_DRAG_THRESHOLD_PX = 6
_HOVER_DELAY_MS = 380
_DRAGGED_SLOT_OPACITY = 0.35
_OVERLAY_OPACITY = 0.92


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
        self.setFocusPolicy(Qt.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card_widget)

        # No QGraphicsEffect at rest, on purpose: attaching one (even at
        # opacity 1.0) forces Qt to composite the card via an offscreen
        # buffer, which can escape the enclosing QScrollArea's clip rect
        # near its edges. Only the card actually being dragged gets one,
        # lazily, in _dim()/_undim() below.
        self.dim_effect = None

    def set_reorder_mode(self, active):
        self.card_widget.setEnabled(not active)
        self.setCursor(Qt.OpenHandCursor if active else Qt.ArrowCursor)
        self.setStyleSheet(
            "QFrame {"
            " border: 1.5px dashed rgba(140, 175, 255, 150);"
            " border-radius: 12px;"
            "}"
            if active
            else ""
        )

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
        overlay.setFixedSize(pixmap.size())
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
        top_left_global = global_cursor_pos - self._press_offset
        self._overlay.move(window.mapFromGlobal(top_left_global))

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

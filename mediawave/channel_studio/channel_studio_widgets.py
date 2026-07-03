"""Shared low-level widgets for Channel Studio (Preview).

Everything here reuses the Advanced Configuration dialog's existing
themed object names (sectionCard, sectionHeader, statusBadge, ...) so
Channel Studio inherits the same look without any new QSS.
"""

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FlowLayout(QLayout):
    """A left-to-right, top-to-bottom layout that wraps onto new lines.

    Used for action-button rows so buttons wrap instead of clipping
    when a card or dialog is narrower than the row's natural width —
    no horizontal scrolling, no cut-off buttons at the default window
    size.
    """

    def __init__(self, parent=None, margin=0, h_spacing=8, v_spacing=8):
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._items:
            item_size = item.sizeHint()
            next_x = x + item_size.width() + self._h_spacing
            if next_x - self._h_spacing > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y += line_height + self._v_spacing
                next_x = x + item_size.width() + self._h_spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y() + bottom


def build_placeholder_note(text="This section is under construction."):
    label = QLabel(text)
    label.setObjectName("fieldHelp")
    label.setWordWrap(True)
    return label


def build_empty_state(text, icon="🗂️"):
    """A friendly, non-scary "nothing here yet" block."""
    box = QFrame()
    box.setObjectName("sectionCard")
    box.setFrameShape(QFrame.NoFrame)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(20, 24, 20, 24)
    layout.setSpacing(6)

    icon_lbl = QLabel(icon)
    icon_lbl.setAlignment(Qt.AlignCenter)
    icon_font = icon_lbl.font()
    icon_font.setPointSize(icon_font.pointSize() + 12)
    icon_lbl.setFont(icon_font)
    layout.addWidget(icon_lbl)

    text_lbl = QLabel(text)
    text_lbl.setObjectName("sectionNote")
    text_lbl.setWordWrap(True)
    text_lbl.setAlignment(Qt.AlignCenter)
    layout.addWidget(text_lbl)
    return box


def build_info_card(title_text, subtitle_text=None, meta_lines=None, buttons=None, badge_text=None):
    """A friendly card: title (+ optional badge), subtitle, meta lines, action buttons.

    `buttons` is a list of (label, callback) tuples. Every card built
    this way is display/mock only unless the caller's callback does
    something real.
    """
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)

    title_row = QHBoxLayout()
    title_row.setSpacing(8)
    title = QLabel(title_text)
    title.setObjectName("sectionHeader")
    title_row.addWidget(title)
    if badge_text:
        badge = QLabel(badge_text)
        badge.setObjectName("statusBadge")
        title_row.addWidget(badge)
    title_row.addStretch(1)
    layout.addLayout(title_row)

    if subtitle_text:
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("sectionNote")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

    if meta_lines:
        for line in meta_lines:
            meta_lbl = QLabel(line)
            meta_lbl.setObjectName("fieldHelp")
            layout.addWidget(meta_lbl)

    if buttons:
        btn_row = FlowLayout(h_spacing=8, v_spacing=6)
        for label, callback in buttons:
            btn = QPushButton(label)
            if callback is not None:
                btn.clicked.connect(callback)
            else:
                btn.setEnabled(False)
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

    return card


def build_schedule_timeline(channel_name, slots):
    """A vertical "tonight on <channel>" timeline, arrows between slots.

    `slots` is a list of objects with `.time_label` and `.title` (see
    `ScheduleSlot` in channel_studio_model.py). Display only — nothing
    here reads or writes real schedule data.
    """
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(4)

    heading = QLabel(f"Tonight on {channel_name}")
    heading.setObjectName("sectionHeader")
    layout.addWidget(heading)

    for index, slot in enumerate(slots):
        row = QHBoxLayout()
        row.setSpacing(10)
        time_lbl = QLabel(slot.time_label)
        time_lbl.setObjectName("statusBadge")
        time_lbl.setFixedWidth(84)
        time_lbl.setAlignment(Qt.AlignCenter)
        row.addWidget(time_lbl)
        title_lbl = QLabel(slot.title)
        title_lbl.setObjectName("sectionNote")
        row.addWidget(title_lbl, 1)
        layout.addLayout(row)

        if index < len(slots) - 1:
            arrow = QLabel("↓")
            arrow.setObjectName("fieldHelp")
            arrow.setAlignment(Qt.AlignCenter)
            arrow.setFixedWidth(84)
            layout.addWidget(arrow, 0, Qt.AlignLeft)

    return card


def build_card_grid(cards, columns=3):
    """Lay out already-built card widgets in a grid."""
    grid_widget = QWidget()
    grid = QGridLayout(grid_widget)
    grid.setSpacing(12)
    for index, card in enumerate(cards):
        row, col = divmod(index, columns)
        grid.addWidget(card, row, col)
    return grid_widget


def build_mock_card_grid(items, columns=3):
    """Convenience: items are str titles or (title, subtitle) tuples."""
    cards = []
    for item in items:
        title_text, subtitle_text = item if isinstance(item, tuple) else (item, None)
        cards.append(build_info_card(title_text, subtitle_text))
    return build_card_grid(cards, columns=columns)


def build_action_button_row(items, fallback=None):
    """Build a row of action buttons.

    `items` is a list of str labels or (label, callback) tuples. If an
    item has no callback and `fallback` is given, `fallback(label)` is
    called on click (used to pop a generic "Preview only" dialog).
    """
    row = QWidget()
    layout = FlowLayout(row, margin=0, h_spacing=10, v_spacing=8)
    buttons = []
    for item in items:
        label, callback = item if isinstance(item, tuple) else (item, None)
        btn = QPushButton(label)
        if callback is None and fallback is not None:
            callback = (lambda checked=False, l=label: fallback(l))
        if callback is not None:
            btn.clicked.connect(callback)
        else:
            btn.setEnabled(False)
            btn.setToolTip("Channel Studio preview — not yet implemented")
        layout.addWidget(btn)
        buttons.append(btn)
    return row, buttons

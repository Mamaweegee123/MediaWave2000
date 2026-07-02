"""Shared low-level widgets for Channel Studio (Preview).

Everything here reuses the Advanced Configuration dialog's existing
themed object names (sectionCard, sectionHeader, statusBadge, ...) so
Channel Studio inherits the same look without any new QSS.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for label, callback in buttons:
            btn = QPushButton(label)
            if callback is not None:
                btn.clicked.connect(callback)
            else:
                btn.setEnabled(False)
            btn_row.addWidget(btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

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
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
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
    layout.addStretch(1)
    return row, buttons

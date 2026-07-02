"""Shared low-level placeholder widgets for Channel Studio (Preview).

Everything here reuses the Advanced Configuration dialog's existing
themed object names (sectionCard, sectionHeader, statusBadge, ...) so
Channel Studio inherits the same look without any new QSS.
"""

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


def build_mock_card(title_text, subtitle_text=None):
    """A non-functional placeholder card — preview only, no real data."""
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)
    title = QLabel(title_text)
    title.setObjectName("sectionHeader")
    layout.addWidget(title)
    if subtitle_text:
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("sectionNote")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
    return card


def build_mock_card_grid(items, columns=3):
    """items: list of str titles, or (title, subtitle) tuples."""
    grid_widget = QWidget()
    grid = QGridLayout(grid_widget)
    grid.setSpacing(12)
    for index, item in enumerate(items):
        title_text, subtitle_text = item if isinstance(item, tuple) else (item, None)
        row, col = divmod(index, columns)
        grid.addWidget(build_mock_card(title_text, subtitle_text), row, col)
    return grid_widget


def build_action_button_row(labels):
    """Disabled placeholder buttons — establishes layout only, no functionality."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    buttons = []
    for label in labels:
        btn = QPushButton(label)
        btn.setEnabled(False)
        btn.setToolTip("Channel Studio preview — not yet implemented")
        layout.addWidget(btn)
        buttons.append(btn)
    layout.addStretch(1)
    return row, buttons

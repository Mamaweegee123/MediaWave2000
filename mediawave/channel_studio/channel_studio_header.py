"""The "Your Channels" dashboard header for Channel Studio's Choose
Channel page: icon + heading + subtitle on the left, search, a filter
placeholder, and Create Channel on the right.

Kept separate from channel_studio_pages.py so that module stays a page
builder, not a page builder plus a hand-rolled toolbar.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

_ICON_SIZE = 44


def _build_heading_block():
    row = QHBoxLayout()
    row.setSpacing(12)

    icon = QLabel("📺")
    icon.setFixedSize(_ICON_SIZE, _ICON_SIZE)
    icon.setAlignment(Qt.AlignCenter)
    icon_font = icon.font()
    icon_font.setPointSize(18)
    icon.setFont(icon_font)
    icon.setStyleSheet(
        "background: rgba(68,108,235,40);"
        " border: 1px solid rgba(68,108,235,90);"
        " border-radius: 10px;"
    )
    row.addWidget(icon)

    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    heading = QLabel("Your Channels")
    heading.setObjectName("dialogTitle")
    text_col.addWidget(heading)
    subtitle = QLabel("Manage and customize your lineup.")
    subtitle.setObjectName("sectionNote")
    text_col.addWidget(subtitle)
    row.addLayout(text_col)
    return row


def build_channel_studio_header(on_create, on_filter, on_search_changed=None):
    """Build the header row. `on_search_changed(text)` (if given) is called
    live as the search field changes; `on_filter` and `on_create` are
    plain no-arg callbacks — both preview-only actions for now.
    """
    container = QWidget()
    outer = QHBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(16)

    outer.addLayout(_build_heading_block())
    outer.addStretch(1)

    search = QLineEdit()
    search.setPlaceholderText("Search channels…")
    search.setMinimumWidth(160)
    search.setMaximumWidth(260)
    if on_search_changed is not None:
        search.textChanged.connect(on_search_changed)
    outer.addWidget(search)

    filter_btn = QPushButton("☰")
    filter_btn.setFixedWidth(40)
    filter_btn.setToolTip("Filters (coming soon)")
    filter_btn.setCursor(Qt.PointingHandCursor)
    filter_btn.clicked.connect(on_filter)
    outer.addWidget(filter_btn)

    create_btn = QPushButton("+  Create Channel")
    create_btn.setObjectName("saveButton")
    create_btn.setCursor(Qt.PointingHandCursor)
    create_btn.clicked.connect(on_create)
    outer.addWidget(create_btn)

    return container

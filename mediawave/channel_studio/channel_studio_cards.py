"""Channel list card + placeholder channel editor for Channel Studio (Preview).

Reads existing channel info (number, name) for display only. No
scheduling, logo, or settings data is written from here.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .channel_studio_widgets import build_placeholder_note


def build_channel_card(channel_info, on_open):
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    layout = QHBoxLayout(card)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(14)

    number_lbl = QLabel(str(channel_info.get("default_number", "")))
    number_lbl.setObjectName("statusBadge")
    number_lbl.setFixedWidth(36)
    number_lbl.setAlignment(Qt.AlignCenter)
    layout.addWidget(number_lbl)

    logo_lbl = QLabel((channel_info.get("name") or "?")[:1].upper())
    logo_lbl.setObjectName("statusBadge")
    logo_lbl.setFixedSize(32, 32)
    logo_lbl.setAlignment(Qt.AlignCenter)
    layout.addWidget(logo_lbl)

    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    name_lbl = QLabel(channel_info.get("name", "Channel"))
    name_lbl.setObjectName("sectionHeader")
    text_col.addWidget(name_lbl)
    summary_lbl = QLabel("Programming summary coming soon.")
    summary_lbl.setObjectName("sectionNote")
    text_col.addWidget(summary_lbl)
    layout.addLayout(text_col, 1)

    open_btn = QPushButton("Open")
    open_btn.clicked.connect(lambda: on_open(channel_info))
    layout.addWidget(open_btn)

    return card


class ChannelEditorPreviewDialog(QDialog):
    """Skeleton-only channel editor. Mock settings — nothing is read or written."""

    SECTIONS = ["Overview", "Programming", "Commercials", "Branding", "Advanced"]

    def __init__(self, channel_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            f"Channel Studio (Preview) — {channel_info.get('name', 'Channel')}"
        )
        self.resize(560, 420)

        outer = QVBoxLayout(self)
        header = QLabel(
            f"{channel_info.get('name', 'Channel')} · "
            f"Channel {channel_info.get('default_number', '')}"
        )
        header.setObjectName("sectionHeader")
        outer.addWidget(header)

        tabs = QTabWidget()
        for section in self.SECTIONS:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.addWidget(
                build_placeholder_note(
                    f"{section} settings are a preview mock — nothing here is "
                    "connected to your real channel yet."
                )
            )
            page_layout.addStretch(1)
            tabs.addTab(page, section)
        outer.addWidget(tabs, 1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        outer.addWidget(close_btn, 0, Qt.AlignRight)

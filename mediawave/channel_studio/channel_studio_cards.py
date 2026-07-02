"""Channel list card + friendly channel editor for Channel Studio (Preview).

Reads existing channel info (number, name, root path) for display
only, plus a best-effort read-only logo lookup. No scheduling, logo,
or settings data is written from here.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
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

from .channel_studio_dialogs import show_preview_dialog
from .channel_studio_widgets import build_info_card

_LOGO_CANDIDATE_NAMES = ("logo.png", "logo.jpg", "logo.jpeg", "bug.png", "channel.png")


def _find_channel_logo_path(root_path):
    """Best-effort, read-only lookup of a channel logo image. Never raises."""
    if not root_path:
        return ""
    logos_dir = os.path.join(root_path, "Logos")
    if not os.path.isdir(logos_dir):
        return ""
    try:
        entries = {name.lower(): name for name in os.listdir(logos_dir)}
    except OSError:
        return ""
    for candidate in _LOGO_CANDIDATE_NAMES:
        actual = entries.get(candidate)
        if actual:
            return os.path.join(logos_dir, actual)
    return ""


def _build_channel_logo_widget(channel_info):
    logo_path = _find_channel_logo_path(channel_info.get("root_path", ""))
    if logo_path:
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            logo_lbl = QLabel()
            logo_lbl.setPixmap(
                pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            logo_lbl.setFixedSize(36, 36)
            logo_lbl.setAlignment(Qt.AlignCenter)
            return logo_lbl
    monogram = QLabel((channel_info.get("name") or "?")[:1].upper())
    monogram.setObjectName("statusBadge")
    monogram.setFixedSize(36, 36)
    monogram.setAlignment(Qt.AlignCenter)
    return monogram


def build_channel_card(channel_info, on_open_studio, on_preview, on_edit_basics):
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    layout = QHBoxLayout(card)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(14)

    number_lbl = QLabel(str(channel_info.get("default_number", "")))
    number_lbl.setObjectName("statusBadge")
    number_lbl.setFixedWidth(32)
    number_lbl.setAlignment(Qt.AlignCenter)
    layout.addWidget(number_lbl)

    layout.addWidget(_build_channel_logo_widget(channel_info))

    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    name_lbl = QLabel(channel_info.get("name", "Channel"))
    name_lbl.setObjectName("sectionHeader")
    text_col.addWidget(name_lbl)
    summary_lbl = QLabel("No programming planned yet — this channel is ready when you are.")
    summary_lbl.setObjectName("sectionNote")
    summary_lbl.setWordWrap(True)
    text_col.addWidget(summary_lbl)
    layout.addLayout(text_col, 1)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(6)
    open_btn = QPushButton("Open Studio")
    open_btn.clicked.connect(lambda: on_open_studio(channel_info))
    btn_row.addWidget(open_btn)
    preview_btn = QPushButton("Preview")
    preview_btn.clicked.connect(lambda: on_preview(channel_info))
    btn_row.addWidget(preview_btn)
    edit_btn = QPushButton("Edit Basics")
    edit_btn.clicked.connect(lambda: on_edit_basics(channel_info))
    btn_row.addWidget(edit_btn)
    layout.addLayout(btn_row)

    return card


# (section title, friendly blurb, [(mock item title, mock item note), ...])
_EDITOR_SECTIONS = [
    (
        "Overview",
        "The at-a-glance basics for this channel.",
        [
            ("Channel Name & Number", "Rename this channel or move it to a new number."),
            ("Description", "A short blurb viewers might see in a future guide."),
        ],
    ),
    (
        "Programming",
        "What shows up on this channel, and when.",
        [
            ("Shows & Movies", "Pick what plays on this channel."),
            ("Programming Blocks", "Group shows into recurring blocks like Nick at Nite."),
        ],
    ),
    (
        "Schedule",
        "The day-by-day lineup for this channel.",
        [
            ("Weekly Grid", "See a full week of programming at a glance."),
            ("Marathons & Events", "Plan one-off marathons or seasonal takeovers."),
        ],
    ),
    (
        "Commercials & Promos",
        "The breaks that play between programs.",
        [
            ("Commercial Profile", "Choose which commercial mix plays on this channel."),
            ("Promos", "Cross-promote your other channels."),
        ],
    ),
    (
        "Branding",
        "How this channel looks and feels.",
        [
            ("Logo & Bug", "Set the on-screen channel logo."),
            ("Station IDs", "Short idents that play between programs."),
        ],
    ),
    (
        "Advanced",
        "Reserved for power-user options.",
        [
            ("Channel Inheritance", "Coming later."),
            ("Raw Overrides", "Coming later."),
        ],
    ),
]


class ChannelEditorPreviewDialog(QDialog):
    """Friendly, card-based channel editor skeleton.

    Everything here is a mock — nothing is read from or written to the
    real channel yet.
    """

    def __init__(self, channel_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            f"Channel Studio (Preview) — {channel_info.get('name', 'Channel')}"
        )
        self.resize(620, 480)

        outer = QVBoxLayout(self)
        header = QLabel(
            f"{channel_info.get('name', 'Channel')} · "
            f"Channel {channel_info.get('default_number', '')}"
        )
        header.setObjectName("sectionHeader")
        outer.addWidget(header)

        badge = QLabel("Preview only — nothing here saves yet")
        badge.setObjectName("fieldHelp")
        outer.addWidget(badge)

        tabs = QTabWidget()
        for section_title, section_note, mock_items in _EDITOR_SECTIONS:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setSpacing(10)
            note = QLabel(section_note)
            note.setObjectName("sectionNote")
            note.setWordWrap(True)
            page_layout.addWidget(note)
            for item_title, item_note in mock_items:
                page_layout.addWidget(
                    build_info_card(
                        item_title,
                        item_note,
                        buttons=[
                            (
                                "Preview",
                                (
                                    lambda checked=False, t=item_title, n=item_note: show_preview_dialog(
                                        self, t, n
                                    )
                                ),
                            )
                        ],
                    )
                )
            page_layout.addStretch(1)
            tabs.addTab(page, section_title)
        outer.addWidget(tabs, 1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        outer.addWidget(close_btn, 0, Qt.AlignRight)


def build_block_card(block, on_edit, on_preview):
    """block: dict with keys name, time_range, content_type, commercials_profile, bumper_set."""
    meta_lines = [
        f"⏰ {block.get('time_range', '')}",
        f"🎞 {block.get('content_type', '')}",
        f"📢 Commercials: {block.get('commercials_profile', '')}",
        f"🎬 Bumpers: {block.get('bumper_set', '')}",
    ]
    return build_info_card(
        block.get("name", "Block"),
        meta_lines=meta_lines,
        buttons=[
            ("Edit Block", lambda: on_edit(block)),
            ("Preview Night", lambda: on_preview(block)),
        ],
    )

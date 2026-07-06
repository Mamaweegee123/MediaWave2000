"""The channel dashboard card — Channel Studio's main "choose a channel" tile.

Read-only aside from the safe, confirmation-gated Remove action (see
studio_styles.confirm_remove_channel). Now/Next/Later comes from the
same TonightSchedule data the Tonight tab already uses; nothing here
reads or writes real schedule, library, or settings data.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .channel_studio_widgets import FlowLayout
from .studio_styles import CHANNEL_NUMBER_COLOR, channel_number_font_family, confirm_remove_channel

_LOGO_CANDIDATE_NAMES = ("logo.png", "logo.jpg", "logo.jpeg", "bug.png", "channel.png")

CARD_WIDTH = 390


def _find_channel_logo_path(root_path):
    """Best-effort, read-only fallback logo lookup. Never raises."""
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


def _build_logo_widget(summary, on_set_logo):
    logo_path = summary.logo_path or _find_channel_logo_path(summary.root_path)
    if logo_path:
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            logo_lbl = QLabel()
            logo_lbl.setPixmap(
                pixmap.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            logo_lbl.setFixedSize(72, 72)
            logo_lbl.setAlignment(Qt.AlignCenter)
            return logo_lbl

    placeholder = QPushButton("Set\nLogo")
    placeholder.setObjectName("channelLogoPlaceholder")
    placeholder.setFixedSize(72, 72)
    placeholder.setCursor(Qt.PointingHandCursor)
    placeholder.setFlat(True)
    placeholder_font = placeholder.font()
    placeholder_font.setPointSize(max(8, placeholder_font.pointSize() - 2))
    placeholder.setFont(placeholder_font)
    if on_set_logo is not None:
        placeholder.clicked.connect(on_set_logo)
    return placeholder


def _build_channel_number_label(number):
    label = QLabel(f"CH {int(number or 0):02d}")
    label.setFont(QFont(channel_number_font_family(), 18, QFont.Bold))
    label.setStyleSheet(f"color: {CHANNEL_NUMBER_COLOR};")
    return label


def _build_now_next_later(schedule):
    box = QVBoxLayout()
    box.setSpacing(2)
    slots = list(schedule.slots) if (schedule is not None and schedule.has_data) else []
    rows = list(zip(("Now", "Next", "Later"), slots))
    if not rows:
        note = QLabel("Lineup will appear when this channel is playing.")
        note.setObjectName("fieldHelp")
        note.setWordWrap(True)
        box.addWidget(note)
        return box
    for prefix, slot in rows:
        line = QLabel(f"{prefix}: {slot.title}")
        line.setObjectName("fieldHelp" if prefix != "Now" else "sectionNote")
        line.setWordWrap(True)
        box.addWidget(line)
    return box


def build_dashboard_channel_card(summary, schedule, on_open, on_commercials, on_set_logo=None):
    """Build one channel's dashboard tile for the Choose Channel grid.

    Remove is handled internally via `studio_styles.confirm_remove_channel`
    (safe, confirmation-only) — callers don't need to wire it.
    """
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    card.setFixedWidth(CARD_WIDTH)
    outer = QVBoxLayout(card)
    outer.setContentsMargins(18, 16, 18, 16)
    outer.setSpacing(10)

    header_row = QHBoxLayout()
    header_row.setSpacing(10)
    header_row.addWidget(_build_channel_number_label(summary.number))

    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    name_lbl = QLabel(summary.name)
    name_lbl.setObjectName("sectionHeader")
    title_col.addWidget(name_lbl)
    headline_lbl = QLabel(summary.headline)
    headline_lbl.setObjectName("sectionNote")
    headline_lbl.setWordWrap(True)
    title_col.addWidget(headline_lbl)
    header_row.addLayout(title_col, 1)

    header_row.addWidget(_build_logo_widget(summary, on_set_logo))
    outer.addLayout(header_row)

    outer.addLayout(_build_now_next_later(schedule))

    commercials_lbl = QLabel(f"Commercials: {'On' if summary.commercials_enabled else 'Off'}")
    commercials_lbl.setObjectName("fieldHelp")
    outer.addWidget(commercials_lbl)

    outer.addStretch(1)

    channel_info = {"id": summary.channel_id, "name": summary.name, "default_number": summary.number}

    btn_row = FlowLayout(h_spacing=8, v_spacing=8)
    open_btn = QPushButton("Open")
    open_btn.clicked.connect(lambda: on_open(channel_info))
    btn_row.addWidget(open_btn)
    commercials_btn = QPushButton("Commercials")
    commercials_btn.clicked.connect(lambda: on_commercials(channel_info))
    btn_row.addWidget(commercials_btn)
    remove_btn = QPushButton("Remove")
    remove_btn.clicked.connect(lambda: confirm_remove_channel(card, summary.name))
    btn_row.addWidget(remove_btn)
    outer.addLayout(btn_row)

    return card

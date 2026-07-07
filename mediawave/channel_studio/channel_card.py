"""Channel dashboard cards — Channel Studio's main "choose a channel" tiles.

Two builders live here: `build_dashboard_channel_card` (the compact tile
used for every normal channel) and `build_hero_channel_card` (the larger
featured tile used for the first channel). Both are read-only aside from
the safe, confirmation-gated Remove action (see
studio_styles.confirm_remove_channel). Now/Next/Later comes from the same
TonightSchedule data the Tonight tab already uses; nothing here reads or
writes real schedule, library, or settings data.

Every label in the normal card is single-line and elided rather than
word-wrapped, and the schedule area always reserves the same three rows
(or their empty-state equivalent) — that's what keeps every normal card
the same height regardless of how long a channel's name or lineup titles
are, without resorting to a hard-clipping fixed size.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .channel_studio_widgets import FlowLayout
from .studio_styles import CHANNEL_NUMBER_COLOR, channel_number_font_family, confirm_remove_channel

_LOGO_CANDIDATE_NAMES = ("logo.png", "logo.jpg", "logo.jpeg", "bug.png", "channel.png")

CARD_WIDTH = 390
HERO_CARD_WIDTH = CARD_WIDTH * 2 + 16  # visually spans two normal cards, same gutter

_SCHEDULE_LABELS = ("NOW", "NEXT", "LATER")


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


def _elide(label, text, max_width):
    """Set `label`'s text to a single-line elided version of `text`,
    keeping the full text as a tooltip so nothing is silently lost.
    """
    text = text or ""
    metrics = QFontMetrics(label.font())
    label.setText(metrics.elidedText(text, Qt.ElideRight, max_width))
    label.setToolTip(text)


def _build_logo_widget(summary, on_set_logo, size=72):
    """The channel's logo/bug — shown once per card, never duplicated.

    Falls back to an "Add Channel Logo" button (not blank space) when no
    logo is set, which routes to the channel's Identity tab.
    """
    logo_path = summary.logo_path or _find_channel_logo_path(summary.root_path)
    if logo_path:
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            logo_lbl = QLabel()
            logo_lbl.setPixmap(
                pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            logo_lbl.setFixedSize(size, size)
            logo_lbl.setAlignment(Qt.AlignCenter)
            return logo_lbl

    placeholder = QPushButton("Add\nLogo")
    placeholder.setObjectName("channelLogoPlaceholder")
    placeholder.setToolTip("Add Channel Logo")
    placeholder.setFixedSize(size, size)
    placeholder.setCursor(Qt.PointingHandCursor)
    placeholder.setFlat(True)
    placeholder_font = placeholder.font()
    placeholder_font.setPointSize(max(8, placeholder_font.pointSize() - 2))
    placeholder.setFont(placeholder_font)
    if on_set_logo is not None:
        placeholder.clicked.connect(on_set_logo)
    return placeholder


def _build_channel_number_label(number, point_size=18, glow=False):
    label = QLabel(f"CH {int(number or 0):02d}")
    label.setFont(QFont(channel_number_font_family(), point_size, QFont.Bold))
    label.setStyleSheet(f"color: {CHANNEL_NUMBER_COLOR}; background: transparent;")
    if glow:
        effect = QGraphicsDropShadowEffect(label)
        effect.setColor(QColor(CHANNEL_NUMBER_COLOR))
        effect.setBlurRadius(28)
        effect.setOffset(0, 0)
        label.setGraphicsEffect(effect)
    return label


def _schedule_slots_or_none(schedule):
    if schedule is not None and schedule.has_data and schedule.slots:
        return list(schedule.slots)
    return None


def _build_now_next_later_compact(schedule, text_width):
    """A fixed-height, always-three-row Now/Next/Later preview.

    Reserving the same three rows (or an empty-state message in the same
    space) regardless of data is what keeps every normal card's schedule
    area the same height.
    """
    container = QWidget()
    container.setFixedHeight(64)
    box = QVBoxLayout(container)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(3)

    slots = _schedule_slots_or_none(schedule)
    if slots is None:
        note = QLabel("Lineup appears once this channel is playing.")
        note.setObjectName("fieldHelp")
        note.setWordWrap(True)
        box.addWidget(note)
        box.addStretch(1)
        return container

    for prefix in _SCHEDULE_LABELS:
        row = QHBoxLayout()
        row.setSpacing(6)
        prefix_lbl = QLabel(prefix)
        prefix_lbl.setObjectName("statusBadge" if prefix == "NOW" else "fieldHelp")
        prefix_lbl.setFixedWidth(42)
        row.addWidget(prefix_lbl)

        slot = slots.pop(0) if slots else None
        title_lbl = QLabel()
        title_lbl.setObjectName("sectionNote" if prefix == "NOW" else "fieldHelp")
        text = f"{slot.time_label}  {slot.title}" if slot and slot.time_label else (slot.title if slot else "—")
        _elide(title_lbl, text, text_width)
        row.addWidget(title_lbl, 1)
        box.addLayout(row)

    return container


def build_dashboard_channel_card(summary, schedule, on_open, on_set_logo=None):
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
    name_lbl = QLabel()
    name_lbl.setObjectName("sectionHeader")
    _elide(name_lbl, summary.name, CARD_WIDTH - 190)
    title_col.addWidget(name_lbl)
    headline_lbl = QLabel()
    headline_lbl.setObjectName("sectionNote")
    _elide(headline_lbl, summary.headline, CARD_WIDTH - 190)
    title_col.addWidget(headline_lbl)
    header_row.addLayout(title_col, 1)

    header_row.addWidget(_build_logo_widget(summary, on_set_logo))
    outer.addLayout(header_row)

    outer.addWidget(_build_now_next_later_compact(schedule, CARD_WIDTH - 90))

    channel_info = {"id": summary.channel_id, "name": summary.name, "default_number": summary.number}

    btn_row = FlowLayout(h_spacing=8, v_spacing=8)
    setup_btn = QPushButton("Setup")
    setup_btn.clicked.connect(lambda: on_open(channel_info))
    btn_row.addWidget(setup_btn)
    remove_btn = QPushButton("Remove")
    remove_btn.clicked.connect(lambda: confirm_remove_channel(card, summary.name))
    btn_row.addWidget(remove_btn)
    outer.addLayout(btn_row)

    return card


def _build_schedule_panel(schedule):
    """The hero card's single Now/Next/Later panel — shown once, never
    repeated in the channel info panel below it.
    """
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)

    slots = _schedule_slots_or_none(schedule)
    if slots is None:
        note = QLabel("Lineup will appear here once this channel is playing.")
        note.setObjectName("fieldHelp")
        note.setWordWrap(True)
        layout.addWidget(note)
        return card

    for prefix in _SCHEDULE_LABELS:
        slot = slots.pop(0) if slots else None
        row = QHBoxLayout()
        row.setSpacing(12)
        prefix_lbl = QLabel(prefix)
        prefix_lbl.setObjectName("statusBadge")
        prefix_lbl.setFixedWidth(56)
        prefix_lbl.setAlignment(Qt.AlignCenter)
        row.addWidget(prefix_lbl)

        if slot is not None:
            time_lbl = QLabel(slot.time_label)
            time_lbl.setObjectName("fieldHelp")
            time_lbl.setFixedWidth(90)
            row.addWidget(time_lbl)
            title_lbl = QLabel()
            title_lbl.setObjectName("sectionNote")
            _elide(title_lbl, slot.title, HERO_CARD_WIDTH - 260)
        else:
            title_lbl = QLabel("—")
            title_lbl.setObjectName("fieldHelp")
        row.addWidget(title_lbl, 1)
        layout.addLayout(row)

    return card


def _channel_info_rows(summary):
    """Only real, already-known values — calm fallback text otherwise.
    Never repeats the Now/Next/Later schedule shown above it.
    """
    is_special = summary.channel_type != "media"
    rows = [
        ("Type", "Special channel" if is_special else "Folder channel"),
        ("Source", "Built in" if is_special else "Local folder"),
    ]
    if not is_special:
        rows.append(("Playback", f"{summary.playback_order_label} order"))
    rows.append(("Commercials", summary.commercials_label))
    if summary.content_known:
        counts = []
        if summary.show_count:
            counts.append(f"{summary.show_count} show" + ("s" if summary.show_count != 1 else ""))
        if summary.movie_count:
            counts.append(f"{summary.movie_count} movie" + ("s" if summary.movie_count != 1 else ""))
        if counts:
            rows.append(("Library", " · ".join(counts)))
    return rows


def _build_channel_info_panel(summary):
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)

    heading = QLabel("Channel Info")
    heading.setObjectName("sectionHeader")
    layout.addWidget(heading)

    for label_text, value_text in _channel_info_rows(summary):
        row = QHBoxLayout()
        row.setSpacing(10)
        label_lbl = QLabel(label_text)
        label_lbl.setObjectName("fieldHelp")
        label_lbl.setFixedWidth(90)
        row.addWidget(label_lbl)
        value_lbl = QLabel()
        value_lbl.setObjectName("sectionNote")
        _elide(value_lbl, value_text, HERO_CARD_WIDTH - 380)
        row.addWidget(value_lbl, 1)
        layout.addLayout(row)

    return card


def build_hero_channel_card(summary, schedule, on_open, on_set_logo=None):
    """Build the larger featured tile for the Choose Channel grid's first
    channel: big channel number, name, logo (once), a single Now/Next/Later
    panel, and a channel-info panel — never a repeated schedule.
    """
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    card.setFixedWidth(HERO_CARD_WIDTH)
    card.setStyleSheet(
        "QFrame#sectionCard { border: 2px solid rgba(255, 209, 102, 130); border-radius: 12px; }"
    )
    outer = QVBoxLayout(card)
    outer.setContentsMargins(22, 18, 22, 18)
    outer.setSpacing(12)

    badge_row = QHBoxLayout()
    badge_row.addStretch(1)
    featured_badge = QLabel("★ Featured")
    featured_badge.setObjectName("statusBadge")
    badge_row.addWidget(featured_badge)
    outer.addLayout(badge_row)

    header_row = QHBoxLayout()
    header_row.setSpacing(16)
    header_row.addWidget(_build_channel_number_label(summary.number, point_size=34, glow=True), 0, Qt.AlignTop)

    title_col = QVBoxLayout()
    title_col.setSpacing(4)
    name_lbl = QLabel()
    name_lbl.setObjectName("dialogTitle")
    _elide(name_lbl, summary.name, HERO_CARD_WIDTH - 300)
    title_col.addWidget(name_lbl)
    title_col.addStretch(1)
    header_row.addLayout(title_col, 1)

    header_row.addWidget(_build_logo_widget(summary, on_set_logo, size=84))
    outer.addLayout(header_row)

    outer.addWidget(_build_schedule_panel(schedule))
    outer.addWidget(_build_channel_info_panel(summary))

    channel_info = {"id": summary.channel_id, "name": summary.name, "default_number": summary.number}

    btn_row = FlowLayout(h_spacing=10, v_spacing=8)
    setup_btn = QPushButton("Setup")
    setup_btn.clicked.connect(lambda: on_open(channel_info))
    btn_row.addWidget(setup_btn)
    remove_btn = QPushButton("Remove")
    remove_btn.clicked.connect(lambda: confirm_remove_channel(card, summary.name))
    btn_row.addWidget(remove_btn)
    outer.addLayout(btn_row)

    return card

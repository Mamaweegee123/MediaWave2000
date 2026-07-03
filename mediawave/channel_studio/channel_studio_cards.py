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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .channel_studio_dialogs import show_preview_dialog
from .channel_studio_widgets import (
    FlowLayout,
    build_card_grid,
    build_info_card,
    build_schedule_timeline,
)
from .programming_blocks import DEFAULT_PROGRAMMING_BLOCKS

_LOGO_CANDIDATE_NAMES = ("logo.png", "logo.jpg", "logo.jpeg", "bug.png", "channel.png")


def _find_channel_logo_path(root_path):
    """Best-effort, read-only fallback logo lookup. Never raises.

    Only used when the caller couldn't supply a pre-resolved logo path
    (e.g. `ChannelStudioSummary.logo_path` from the adapter).
    """
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


def _build_channel_logo_widget(summary):
    logo_path = summary.logo_path or _find_channel_logo_path(summary.root_path)
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
    monogram = QLabel((summary.name or "?")[:1].upper())
    monogram.setObjectName("statusBadge")
    monogram.setFixedSize(36, 36)
    monogram.setAlignment(Qt.AlignCenter)
    return monogram


def build_channel_card(summary, on_open_studio, on_preview, on_edit_basics):
    """Build a channel card from a `ChannelStudioSummary` (read-only).

    Buttons sit in their own wrapping row below the name/logo, so at
    narrow widths they stack onto a new line instead of clipping off
    the right edge.
    """
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    outer = QVBoxLayout(card)
    outer.setContentsMargins(14, 10, 14, 10)
    outer.setSpacing(8)

    top_row = QHBoxLayout()
    top_row.setSpacing(14)

    number_lbl = QLabel(str(summary.number or ""))
    number_lbl.setObjectName("statusBadge")
    number_lbl.setFixedWidth(32)
    number_lbl.setAlignment(Qt.AlignCenter)
    top_row.addWidget(number_lbl)

    top_row.addWidget(_build_channel_logo_widget(summary))

    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    name_lbl = QLabel(summary.name)
    name_lbl.setObjectName("sectionHeader")
    text_col.addWidget(name_lbl)
    summary_lbl = QLabel(summary.headline)
    summary_lbl.setObjectName("sectionNote")
    summary_lbl.setWordWrap(True)
    text_col.addWidget(summary_lbl)
    if summary.has_hints:
        hint_bits = []
        if summary.airing_rule_count:
            hint_bits.append(f"{summary.airing_rule_count} airing rule" + ("s" if summary.airing_rule_count != 1 else ""))
        if summary.seasonal_rule_count:
            hint_bits.append(f"{summary.seasonal_rule_count} seasonal event" + ("s" if summary.seasonal_rule_count != 1 else ""))
        hint_lbl = QLabel(" · ".join(hint_bits))
        hint_lbl.setObjectName("fieldHelp")
        text_col.addWidget(hint_lbl)
    top_row.addLayout(text_col, 1)
    outer.addLayout(top_row)

    channel_info = {"id": summary.channel_id, "name": summary.name, "default_number": summary.number}

    btn_row = FlowLayout(h_spacing=6, v_spacing=6)
    open_btn = QPushButton("Open Studio")
    open_btn.clicked.connect(lambda: on_open_studio(channel_info))
    btn_row.addWidget(open_btn)
    preview_btn = QPushButton("Preview")
    preview_btn.clicked.connect(lambda: on_preview(channel_info))
    btn_row.addWidget(preview_btn)
    edit_btn = QPushButton("Edit Basics")
    edit_btn.clicked.connect(lambda: on_edit_basics(channel_info))
    btn_row.addWidget(edit_btn)
    outer.addLayout(btn_row)

    return card


# (card title, icon, one-line blurb shown on the landing hub,
#  friendly section note, [(mock item title, mock item note), ...])
_EDITOR_CARDS = [
    (
        "Watching Tonight",
        "🌙",
        "See what's playing on this channel right now.",
        "Here's what this channel feels like tonight.",
        None,  # rendered specially — see _build_watching_tonight_page
    ),
    (
        "Programming",
        "🕒",
        "What plays on this channel, and when.",
        "What plays on this channel, and when?",
        [
            ("Shows & Movies", "Pick what plays on this channel."),
            ("Programming Blocks", "Group shows into recurring blocks like Nick at Nite."),
            ("Weekly Grid", "See a full week of programming at a glance."),
            ("Marathons & Events", "Plan one-off marathons or seasonal takeovers."),
        ],
    ),
    (
        "Commercials",
        "📢",
        "What kind of commercials belong here?",
        "What kind of commercials belong here?",
        [
            ("Commercial Profile", "Choose which commercial mix plays on this channel."),
            ("Promos", "Cross-promote your other channels."),
        ],
    ),
    (
        "Branding",
        "⭐",
        "How should this channel look and feel?",
        "How should this channel look and feel?",
        [
            ("Logo & Bug", "Set the on-screen channel logo."),
            ("Station IDs", "Short idents that play between programs."),
        ],
    ),
    (
        "Blocks",
        "🎬",
        "When should this channel come alive?",
        "When should this channel come alive?",
        None,  # rendered specially — see _build_blocks_hub_page
    ),
    (
        "Preview",
        "📺",
        "Watch this channel like a viewer would.",
        "Watch this channel like a viewer would.",
        [("Live Channel Preview", "See what's currently playing, as a viewer would see it.")],
    ),
]


def _build_mock_items_page(dialog, items):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setSpacing(10)
    for item_title, item_note in items:
        layout.addWidget(
            build_info_card(
                item_title,
                item_note,
                buttons=[
                    (
                        "Preview",
                        (
                            lambda checked=False, t=item_title, n=item_note: show_preview_dialog(
                                dialog, t, n
                            )
                        ),
                    )
                ],
            )
        )
    layout.addStretch(1)
    return page


def _build_watching_tonight_page(dialog, schedule):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setSpacing(10)
    if schedule is not None and schedule.has_data:
        layout.addWidget(build_schedule_timeline(schedule.channel_name, schedule.slots))
    else:
        layout.addWidget(
            build_info_card(
                "No lineup yet",
                "Once this channel is playing, tonight's lineup will show up here.",
            )
        )
    layout.addStretch(1)
    return page


def _build_blocks_hub_page(dialog):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setSpacing(10)
    cards = [
        build_block_card(
            block,
            on_edit=lambda b: show_preview_dialog(
                dialog, f"Edit {b.title}", "Block editing isn't wired up yet — this is a preview."
            ),
            on_preview=lambda b: show_preview_dialog(
                dialog, f"Preview {b.title}", "This will eventually simulate a night of this block."
            ),
        )
        for block in DEFAULT_PROGRAMMING_BLOCKS
    ]
    layout.addWidget(build_card_grid(cards, columns=2))
    layout.addStretch(1)
    return page


def _build_identity_text(summary):
    """A friendly one-line identity blurb, not a stats dump."""
    if summary is None:
        return "A folder channel, ready to play."
    bits = [summary.headline]
    if summary.playback_order_label:
        bits.append(f"{summary.playback_order_label} order")
    return " · ".join(bits)


class ChannelEditorPreviewDialog(QDialog):
    """A friendly, card-based television-station hub for one channel.

    Opening a channel feels like walking into its studio: a handful of
    big cards (Watching Tonight, Programming, Commercials, Branding,
    Blocks, Preview) rather than a wall of settings tabs. Everything
    here is a mock — nothing is read from or written to the real
    channel yet, aside from the optional read-only `summary` and
    `schedule` used to make Watching Tonight and the identity line
    feel real when the data is available.
    """

    def __init__(self, channel_info, summary=None, schedule=None, parent=None):
        super().__init__(parent)
        channel_name = channel_info.get("name", "Channel")
        self.setWindowTitle(f"Channel Studio (Preview) — {channel_name}")
        self.resize(680, 520)

        outer = QVBoxLayout(self)
        header = QLabel(f"{channel_name} · Channel {channel_info.get('default_number', '')}")
        header.setObjectName("sectionHeader")
        outer.addWidget(header)

        identity = QLabel(_build_identity_text(summary))
        identity.setObjectName("sectionNote")
        identity.setWordWrap(True)
        outer.addWidget(identity)

        badge = QLabel("Preview only — nothing here saves yet")
        badge.setObjectName("fieldHelp")
        outer.addWidget(badge)

        self._stack = QStackedWidget()

        landing = QWidget()
        landing_layout = QVBoxLayout(landing)
        landing_layout.setSpacing(10)
        prompt = QLabel("What do you want to work on?")
        prompt.setObjectName("sectionNote")
        landing_layout.addWidget(prompt)

        hub_cards = []
        for title, icon, blurb, section_note, items in _EDITOR_CARDS:
            hub_cards.append(
                build_info_card(
                    f"{icon} {title}",
                    blurb,
                    buttons=[
                        (
                            "Open",
                            (
                                lambda checked=False, t=title: self._open_section(t)
                            ),
                        )
                    ],
                )
            )
        landing_layout.addWidget(build_card_grid(hub_cards, columns=2))
        landing_layout.addStretch(1)
        self._stack.addWidget(landing)

        self._section_index_by_title = {}
        for title, icon, blurb, section_note, items in _EDITOR_CARDS:
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setSpacing(10)

            back_btn = QPushButton(f"←  Back to {channel_name}")
            back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
            section_layout.addWidget(back_btn, 0, Qt.AlignLeft)

            note = QLabel(section_note)
            note.setObjectName("sectionNote")
            note.setWordWrap(True)
            section_layout.addWidget(note)

            if title == "Watching Tonight":
                section_layout.addWidget(_build_watching_tonight_page(self, schedule))
            elif title == "Blocks":
                section_layout.addWidget(_build_blocks_hub_page(self))
            else:
                section_layout.addWidget(_build_mock_items_page(self, items))

            self._section_index_by_title[title] = self._stack.addWidget(section)

        outer.addWidget(self._stack, 1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        outer.addWidget(close_btn, 0, Qt.AlignRight)

    def _open_section(self, title):
        index = self._section_index_by_title.get(title)
        if index is not None:
            self._stack.setCurrentIndex(index)


def build_block_card(block, on_edit, on_preview):
    """block: a `ProgrammingBlock` — a named identity, not a raw time range."""
    meta_lines = [
        f"⏰ Typically airs {block.typical_airtime}",
        f"📢 Commercials: {block.commercial_profile}",
        f"🎬 Bumpers: {block.bumper_set}",
        f"⭐ Branding: {block.branding_style}",
    ]
    return build_info_card(
        block.title,
        block.description,
        meta_lines=meta_lines,
        buttons=[
            ("Edit Block", lambda: on_edit(block)),
            ("Preview", lambda: on_preview(block)),
        ],
    )

"""The Schedule Editor's right-side utility panels (Quick Actions, Next Up,
Channel Defaults) and bottom selection details strip -- all built from the
existing mediawave/studio/cards.py constructors, per the Studio Design
System's "same cards, same spacing" philosophy. None of this writes
settings; Quick Actions' buttons stay permanently disabled this phase.
"""

import time

from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from mediawave.commercials import is_commercial_entry
from mediawave.studio.cards import build_action_card, build_property_card, build_status_card
from mediawave.studio.spacing import CONTROL_SPACING

_NOTE_COLOR = "rgba(138, 158, 212, 220)"
_VALUE_COLOR = "rgba(210, 222, 252, 235)"

_QUICK_ACTIONS = [
    ("📡", "Put On Air"),
    ("⏏", "Pull"),
    ("🧩", "Auto-Fill Block"),
    ("🌆", "Build Prime Time"),
    ("📺", "Drop In Commercials"),
    ("🕒", "Clone Daypart"),
]

_MEDIA_TYPE_LABELS = {"tv": "Series", "movie": "Movie", "commercial": "Commercial Break"}


def _note_label(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {_NOTE_COLOR}; font-size: 11px; background: transparent;")
    return label


def build_quick_actions_card():
    """All six future editing actions, visibly present but disabled -- "the
    controls exist, editing arrives next phase" rather than looking broken.
    """
    content = QWidget()
    layout = QGridLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(CONTROL_SPACING)

    for index, (icon, label) in enumerate(_QUICK_ACTIONS):
        btn = QPushButton(f"{icon}  {label}")
        btn.setEnabled(False)
        btn.setToolTip("Schedule editing will be enabled in the next phase.")
        layout.addWidget(btn, index // 2, index % 2)

    note = _note_label("Schedule editing will be enabled in the next phase.")
    layout.addWidget(note, (len(_QUICK_ACTIONS) + 1) // 2, 0, 1, 2)

    return build_action_card("Quick Actions", content, subtitle="Tonight's control-room moves — coming soon.")


def build_next_up_card():
    """Returns (card, update_fn). `update_fn(lane)` refreshes the list from
    a ChannelLane's already-fetched blocks -- no extra schedule query.
    """
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    placeholder = _note_label("Select a channel to see what's up next.")
    layout.addWidget(placeholder)

    card = build_status_card("Next Up", content, subtitle="Real upcoming programming for the selected channel.")

    def update(lane, limit=6):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        if lane is None:
            layout.addWidget(_note_label("Select a channel to see what's up next."))
            return
        if not lane.has_data or not lane.blocks:
            layout.addWidget(_note_label("No scheduled breakdown available for this channel."))
            return

        for block in lane.blocks[:limit]:
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 4)
            row_layout.setSpacing(0)
            time_label = time.strftime("%-I:%M %p", time.localtime(block.true_start))
            minutes = max(1, round(block.duration / 60))
            headline = QLabel(f"{time_label} · {block.title}")
            headline.setWordWrap(True)
            headline.setStyleSheet(f"color: {_VALUE_COLOR}; font-size: 12px; font-weight: 600; background: transparent;")
            row_layout.addWidget(headline)
            detail = QLabel(f"{_MEDIA_TYPE_LABELS.get(block.media_type, 'Program')} · {minutes} min")
            detail.setStyleSheet(f"color: {_NOTE_COLOR}; font-size: 10px; background: transparent;")
            row_layout.addWidget(detail)
            layout.addWidget(row)

    return card, update


def build_channel_defaults_card():
    """Returns (card, update_fn). `update_fn(summary)` takes a
    ChannelStudioSummary (see mediawave/channel_studio/channel_studio_model.py)
    or None -- only ever shows fields that dataclass actually carries, never
    invented settings.
    """
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(_note_label("Select a channel to see its defaults."))

    card = build_property_card("Channel Defaults", content, subtitle="Real configuration for the selected channel.")

    def _row(text):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {_VALUE_COLOR}; font-size: 12px; background: transparent;")
        return label

    def update(summary):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        if summary is None:
            layout.addWidget(_note_label("Select a channel to see its defaults."))
            return

        if summary.is_companion:
            layout.addWidget(_row("Companion channel"))
            if summary.companion_info_label:
                layout.addWidget(_row(f"{summary.companion_info_label}: {summary.companion_info_value}"))
        else:
            layout.addWidget(_row(f"Playback: {summary.playback_order_label}"))
            layout.addWidget(_row(summary.commercials_label))
            if summary.content_known:
                layout.addWidget(_row(summary.headline))

        if summary.airing_rule_count:
            layout.addWidget(_row(f"{summary.airing_rule_count} airing rule(s)"))
        if summary.seasonal_rule_count:
            layout.addWidget(_row(f"{summary.seasonal_rule_count} seasonal takeover(s)"))

    return card, update


def build_details_strip():
    """The persistent bottom bar bound to the currently selected program
    block (or, absent a block selection, just the selected channel). Returns
    (widget, update_fn). `update_fn(block, lane)` -- both may be None.
    """
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    placeholder = _note_label("Select a program to see its details.")
    layout.addWidget(placeholder)

    card = build_status_card("Selected Program", content)

    def update(block, lane):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        if block is None:
            if lane is not None:
                layout.addWidget(_note_label(f"Ch {lane.number} · {lane.name} selected — choose a program for full details."))
            else:
                layout.addWidget(_note_label("Select a program to see its details."))
            return

        channel_label = f"Ch {lane.number} · {lane.name}" if lane is not None else ""
        title_lbl = QLabel(f"{block.title}" + (f"  —  {channel_label}" if channel_label else ""))
        title_lbl.setStyleSheet(f"color: {_VALUE_COLOR}; font-size: 14px; font-weight: 700; background: transparent;")
        layout.addWidget(title_lbl)

        start_label = time.strftime("%-I:%M %p", time.localtime(block.true_start))
        end_label = time.strftime("%-I:%M %p", time.localtime(block.true_end))
        minutes = max(1, round(block.duration / 60))
        media_label = _MEDIA_TYPE_LABELS.get(block.media_type, "Program")
        detail_parts = [media_label, f"{start_label} – {end_label}", f"{minutes} min", "Auto-generated schedule"]

        has_internal_break = not block.is_commercial and any(
            is_commercial_entry(entry) for entry in block.raw_entries
        )
        if has_internal_break:
            detail_parts.append("Includes a commercial break")

        detail_lbl = QLabel("  ·  ".join(detail_parts))
        detail_lbl.setStyleSheet(f"color: {_NOTE_COLOR}; font-size: 11px; background: transparent;")
        layout.addWidget(detail_lbl)

    return card, update

"""The Schedule Editor's right-side utility panels (Editing Tools, Next Up,
Channel Defaults) and the bottom Selected Program footer inspector -- the
cards built from the existing mediawave/studio/cards.py constructors, per
the Studio Design System's "same cards, same spacing" philosophy; the
inspector as a flat advFooter-chromed panel (it IS the mode's footer-stack
page, see build_selected_program_footer). None of this writes settings.
"""

import time

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from mediawave.commercials import is_commercial_entry
from mediawave.studio.cards import build_status_card
from mediawave.studio.section import StudioSection

from .program_block import MEDIA_TYPE_LABELS

_NOTE_COLOR = "rgba(138, 158, 212, 220)"
_VALUE_COLOR = "rgba(210, 222, 252, 235)"

_EDITING_TOOL_NAMES = [
    "Put On Air",
    "Pull",
    "Auto-Fill Block",
    "Build Prime Time",
    "Drop In Commercials",
    "Clone Daypart",
]

_READ_ONLY_NOTE = "Schedule editing will be enabled in the next phase."


def _note_label(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {_NOTE_COLOR}; font-size: 11px; background: transparent;")
    return label


def build_editing_tools_card():
    """A compact preview of the six future editing actions -- names only,
    no disabled button wall. A dense grid or list of six inert controls
    reads as broken; one word-wrapped line naming what's coming
    communicates the same thing without dominating a read-only screen.
    The single read-only-status message lives here, in the card's
    subtitle, and nowhere else in the workspace.
    """
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    names_lbl = QLabel("  ·  ".join(_EDITING_TOOL_NAMES))
    names_lbl.setWordWrap(True)
    names_lbl.setStyleSheet(f"color: {_VALUE_COLOR}; font-size: 12px; background: transparent;")
    layout.addWidget(names_lbl)

    # accent=False on purpose: nothing here is actionable this phase, so
    # the blue accent strip read as a stray line fragment beside the card
    # rather than meaningful "this does something" structure. Built via
    # StudioSection directly (cards.py's docstring sanctions this when
    # the intent-named defaults don't fit).
    return StudioSection("Editing Tools", subtitle=_READ_ONLY_NOTE, content=content, collapsible=False, accent=False)


def build_next_up_card():
    """Returns (card, update_fn). `update_fn(lane)` refreshes the list from
    a ChannelLane's already-fetched blocks -- no extra schedule query.
    """
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
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
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)
            time_label = time.strftime("%-I:%M %p", time.localtime(block.true_start))
            minutes = max(1, round(block.duration / 60))
            headline = QLabel(f"{time_label} · {block.title}")
            headline.setWordWrap(True)
            headline.setStyleSheet(f"color: {_VALUE_COLOR}; font-size: 12px; font-weight: 600; background: transparent;")
            row_layout.addWidget(headline)
            detail = QLabel(f"{MEDIA_TYPE_LABELS.get(block.media_type, 'Program')} · {minutes} min")
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
    layout.setSpacing(8)
    layout.addWidget(_note_label("Select a channel to see its defaults."))

    # accent=False for the same reason as the Editing Tools card: this is
    # a read-only summary, and its accent strip read as stray clutter
    # beside the otherwise accent-less right column.
    card = StudioSection(
        "Channel Defaults", subtitle="Real configuration for the selected channel.", content=content, collapsible=False, accent=False
    )

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


def build_selected_program_footer():
    """The Selected Program inspector: the Schedule Editor's footer-stack
    page (see dialog.build_schedule_editor_tab), occupying the
    constant-height footer band every Advanced Configuration mode reserves
    at the bottom of the dialog -- selection details live there instead of
    leaving the band dead. Returns (footer_widget, update_fn);
    `update_fn(block, lane)` -- both may be None.

    Fixed-height on purpose: the footer stack sizes itself to its tallest
    page, so a selection-dependent height here would make the whole
    dialog's footer band jump around as programs are clicked.
    """
    footer = QWidget()
    footer.setObjectName("advFooter")
    footer.setFixedHeight(96)

    outer = QHBoxLayout(footer)
    outer.setContentsMargins(24, 10, 24, 12)
    outer.setSpacing(10)

    column = QVBoxLayout()
    column.setSpacing(2)
    outer.addLayout(column, 1)

    eyebrow = QLabel("SELECTED PROGRAM")
    eyebrow.setStyleSheet(
        f"color: {_NOTE_COLOR}; font-size: 10px; font-weight: 700; letter-spacing: 1px; background: transparent;"
    )
    column.addWidget(eyebrow)

    layout = QVBoxLayout()
    layout.setSpacing(2)
    column.addLayout(layout)
    column.addStretch(1)

    def _prompt_label(text):
        label = QLabel(text)
        label.setStyleSheet(f"color: {_NOTE_COLOR}; font-size: 13px; background: transparent;")
        return label

    def _dim_line(text):
        label = QLabel(text)
        label.setStyleSheet(f"color: {_NOTE_COLOR}; font-size: 11px; background: transparent;")
        return label

    layout.addWidget(_prompt_label("Select a program to see its full details."))

    def update(block, lane):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        if block is None:
            if lane is not None:
                layout.addWidget(_prompt_label(f"Ch {lane.number} · {lane.name} selected — choose a program for full details."))
            else:
                layout.addWidget(_prompt_label("Select a program to see its full details."))
            return

        title_lbl = QLabel(block.title)
        title_lbl.setStyleSheet(f"color: {_VALUE_COLOR}; font-size: 15px; font-weight: 700; background: transparent;")
        layout.addWidget(title_lbl)

        start_label = time.strftime("%-I:%M %p", time.localtime(block.true_start))
        end_label = time.strftime("%-I:%M %p", time.localtime(block.true_end))
        minutes = max(1, round(block.duration / 60))
        media_label = MEDIA_TYPE_LABELS.get(block.media_type, "Program")
        detail_parts = []
        if lane is not None:
            detail_parts.append(f"Ch {lane.number} · {lane.name}")
        detail_parts.append(f"{start_label}–{end_label} · {minutes} min · {media_label}")
        layout.addWidget(_dim_line("   ·   ".join(detail_parts)))

        origin_parts = ["Auto-generated schedule"]
        has_internal_break = not block.is_commercial and any(
            is_commercial_entry(entry) for entry in block.raw_entries
        )
        if has_internal_break:
            origin_parts.append("Includes a commercial break")
        # A generic display label (e.g. "WeatherStar Forecast") stays
        # honest specifically because the real, distinct things it stands
        # in for are still visible right here -- see
        # ProgramBlock.source_titles' docstring in schedule_model.py.
        distinct_sources = list(dict.fromkeys(block.source_titles))
        if len(distinct_sources) > 1:
            shown = distinct_sources[:5]
            suffix = f", and {len(distinct_sources) - len(shown)} more" if len(distinct_sources) > len(shown) else ""
            origin_parts.append(f"Includes: {', '.join(shown)}{suffix}")
        origin_lbl = _dim_line("   ·   ".join(origin_parts))
        # One line, elided by clipping rather than wrapping -- the footer
        # band is fixed-height, and the full source list is still in the
        # block's tooltip/Next Up context.
        origin_lbl.setWordWrap(False)
        layout.addWidget(origin_lbl)

    return footer, update

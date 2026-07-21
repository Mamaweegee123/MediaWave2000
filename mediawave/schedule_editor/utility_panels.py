"""The Schedule Editor's right-side utility panels (Editing Tools, Next Up,
Channel Defaults) and the bottom Selected Program footer inspector -- the
cards built from the existing mediawave/studio/cards.py constructors, per
the Studio Design System's "same cards, same spacing" philosophy; the
inspector as a flat advFooter-chromed panel (it IS the mode's footer-stack
page, see build_selected_program_footer). None of this writes settings.
"""

import os
import time

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from mediawave.commercials import is_commercial_entry
from mediawave.studio.cards import build_status_card
from mediawave.studio.section import StudioSection

from .program_block import MEDIA_TYPE_ACCENTS, MEDIA_TYPE_LABELS

_NOTE_COLOR = "rgba(138, 158, 212, 220)"
_VALUE_COLOR = "rgba(210, 222, 252, 235)"
_ACCENT_NEUTRAL = "rgba(255, 255, 255, 24)"

# Compact real-action buttons for the Editing Tools card's primary row --
# the same quiet geometry as the top bar's nav buttons (the app-wide
# filled-blue QPushButton default is too heavy stacked inside a side
# card), with a clearly-lower-contrast :disabled state.
_TOOL_BUTTON_STYLE = """
    QPushButton {
        min-width: 0px;
        min-height: 28px;
        padding: 5px 12px;
        border-radius: 6px;
        border: 1px solid rgba(96, 144, 255, 150);
        background: rgba(50, 70, 160, 110);
        color: rgba(222, 232, 255, 240);
        font-size: 12px;
        font-weight: 600;
    }
    QPushButton:hover:enabled {
        border: 1px solid rgba(120, 165, 255, 210);
        background: rgba(60, 84, 190, 150);
        color: white;
    }
    QPushButton:disabled {
        border: 1px solid rgba(90, 100, 140, 60);
        background: transparent;
        color: rgba(120, 132, 168, 150);
        font-weight: 400;
    }
"""

# The secondary row (Duplicate Here…/Copy to Another Day…/Fill Open
# Time) is deliberately quieter than the primary row -- no fill, thinner
# text -- so six real actions don't all compete at the same visual
# weight. These are the lower-frequency lineup-building shortcuts, not
# the core editing verbs.
_SECONDARY_BUTTON_STYLE = """
    QPushButton {
        min-width: 0px;
        min-height: 26px;
        padding: 4px 10px;
        border-radius: 6px;
        border: 1px solid rgba(96, 144, 255, 90);
        background: transparent;
        color: rgba(200, 214, 245, 215);
        font-size: 11px;
        font-weight: 500;
    }
    QPushButton:hover:enabled {
        border: 1px solid rgba(120, 165, 255, 170);
        background: rgba(60, 84, 190, 80);
        color: white;
    }
    QPushButton:disabled {
        border: 1px solid rgba(90, 100, 140, 50);
        background: transparent;
        color: rgba(120, 132, 168, 120);
    }
"""

_LOCKED_MESSAGE_STYLE = (
    f"color: {_NOTE_COLOR}; font-size: 12px; background: transparent;"
)


def _note_label(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {_NOTE_COLOR}; font-size: 11px; background: transparent;")
    return label


def build_editing_tools_card(
    on_put_on_air=None,
    on_pull=None,
    on_move_to=None,
    on_duplicate_here=None,
    on_copy_to_day=None,
    on_fill_open_time=None,
):
    """Two tiers, not six equal-weight buttons: Put On Air / Pull / Move
    To… are the primary row; Duplicate Here… / Copy to Another Day… /
    Fill Open Time sit below in a quieter, unfilled style -- real, but
    visibly secondary. A protected companion selection replaces the
    whole grid with one calm locked line via `set_locked(reason)`.

    Returns (card, controls): one `*_btn` per action, `set_hint(text)`
    for a short constraint explanation (empty string clears it), and
    `set_locked(reason_or_none)`.
    """
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    def _tool_button(label, handler, style=_TOOL_BUTTON_STYLE):
        btn = QPushButton(label)
        btn.setStyleSheet(style)
        btn.setEnabled(False)
        if handler is not None:
            btn.clicked.connect(handler)
        return btn

    buttons_container = QWidget()
    buttons_layout = QVBoxLayout(buttons_container)
    buttons_layout.setContentsMargins(0, 0, 0, 0)
    buttons_layout.setSpacing(8)

    primary_row = QHBoxLayout()
    primary_row.setSpacing(8)
    put_btn = _tool_button("Put On Air", on_put_on_air)
    primary_row.addWidget(put_btn)
    pull_btn = _tool_button("Pull", on_pull)
    primary_row.addWidget(pull_btn)
    move_btn = _tool_button("Move To…", on_move_to)
    primary_row.addWidget(move_btn)
    primary_row.addStretch(1)
    buttons_layout.addLayout(primary_row)

    # Full-width, one per line -- three across clipped "Copy to Another
    # Day…" at this card's width, and stacking also reads as visibly
    # lower-priority than the primary row's horizontal group.
    secondary_col = QVBoxLayout()
    secondary_col.setSpacing(4)
    duplicate_btn = _tool_button("Duplicate Here…", on_duplicate_here, _SECONDARY_BUTTON_STYLE)
    secondary_col.addWidget(duplicate_btn)
    copy_btn = _tool_button("Copy to Another Day…", on_copy_to_day, _SECONDARY_BUTTON_STYLE)
    secondary_col.addWidget(copy_btn)
    fill_btn = _tool_button("Fill Open Time", on_fill_open_time, _SECONDARY_BUTTON_STYLE)
    secondary_col.addWidget(fill_btn)
    buttons_layout.addLayout(secondary_col)

    hint_lbl = _note_label("")
    buttons_layout.addWidget(hint_lbl)
    hint_lbl.hide()

    layout.addWidget(buttons_container)

    locked_lbl = QLabel("")
    locked_lbl.setWordWrap(True)
    locked_lbl.setStyleSheet(_LOCKED_MESSAGE_STYLE)
    locked_lbl.hide()
    layout.addWidget(locked_lbl)

    def set_hint(text):
        hint_lbl.setText(text or "")
        hint_lbl.setVisible(bool(text))

    def set_locked(reason):
        is_locked = bool(reason)
        buttons_container.setVisible(not is_locked)
        locked_lbl.setText(reason or "")
        locked_lbl.setVisible(is_locked)

    card = StudioSection(
        "Editing Tools",
        content=content,
        collapsible=False,
        accent=False,
    )
    controls = {
        "put_btn": put_btn,
        "pull_btn": pull_btn,
        "move_btn": move_btn,
        "duplicate_btn": duplicate_btn,
        "copy_btn": copy_btn,
        "fill_btn": fill_btn,
        "set_hint": set_hint,
        "set_locked": set_locked,
    }
    return card, controls


_PENDING_ROW_BG = "rgba(50, 70, 160, 60)"
_PENDING_UNDO_BUTTON_STYLE = """
    QPushButton {
        min-width: 0px;
        min-height: 22px;
        padding: 2px 8px;
        border-radius: 5px;
        border: 1px solid rgba(96, 144, 255, 130);
        background: transparent;
        color: rgba(210, 222, 252, 220);
        font-size: 10px;
    }
    QPushButton:hover {
        border: 1px solid rgba(130, 170, 255, 200);
        background: rgba(60, 84, 190, 120);
        color: white;
    }
"""


def build_pending_changes_card():
    """Returns (card, update_fn). `update_fn(rows, on_undo_change)` renders
    the draft's current change-set -- `rows` is exactly
    DraftSchedule.describe_pending_changes()'s output, so this card is a
    pure view over the real change model, never a second list that could
    drift out of sync (Phase 2.1 spec section 10). `on_undo_change(change_id)`
    is called when a row's "Undo This Change" button is clicked.

    Internal command/class names, change ids, and raw paths never appear
    here -- only the friendly headline/subline text draft_model.py already
    produced.
    """
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(_note_label("No unsaved changes"))

    card = StudioSection(
        "Pending Changes",
        content=content,
        collapsible=False,
        accent=False,
    )

    def _build_row_widget(row, on_undo_change):
        row_widget = QWidget()
        row_widget.setStyleSheet(f"background: {_PENDING_ROW_BG}; border-radius: 8px;")
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(10, 8, 8, 8)
        row_layout.setSpacing(8)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        headline = QLabel(row["headline"])
        headline.setWordWrap(True)
        headline.setStyleSheet(f"color: {_VALUE_COLOR}; font-size: 12px; font-weight: 600; background: transparent;")
        text_col.addWidget(headline)
        subline = QLabel(row["subline"])
        subline.setWordWrap(True)
        subline.setStyleSheet(f"color: {_NOTE_COLOR}; font-size: 10px; background: transparent;")
        text_col.addWidget(subline)
        row_layout.addLayout(text_col, 1)

        if on_undo_change is not None:
            undo_btn = QPushButton("Undo This Change")
            undo_btn.setStyleSheet(_PENDING_UNDO_BUTTON_STYLE)
            undo_btn.clicked.connect(lambda _checked=False, cid=row["change_id"]: on_undo_change(cid))
            row_layout.addWidget(undo_btn)

        return row_widget

    def update(rows, on_undo_change=None):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        if not rows:
            layout.addWidget(_note_label("No unsaved changes"))
            return

        count_label = f"{len(rows)} unsaved change" + ("" if len(rows) == 1 else "s") + " in this draft."
        layout.addWidget(_note_label(count_label))

        distinct_dates = list(dict.fromkeys(row.get("date", "") for row in rows))
        # Only show date headers once a session actually spans more than
        # one date (Copy to Another Day) -- the common single-date case
        # stays exactly as calm as it was before Phase 3.1 (spec section
        # 18: don't make this overwhelming for a single simple action).
        if len(distinct_dates) <= 1:
            for row in rows:
                layout.addWidget(_build_row_widget(row, on_undo_change))
            return

        for date_key in distinct_dates:
            date_rows = [row for row in rows if row.get("date", "") == date_key]
            header = QLabel(date_rows[0].get("date_label", date_key))
            header.setStyleSheet(
                "color: rgba(150, 190, 255, 235); font-size: 11px; font-weight: 700; background: transparent;"
            )
            layout.addWidget(header)
            for row in date_rows:
                layout.addWidget(_build_row_widget(row, on_undo_change))

    return card, update


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

    card = build_status_card("Next Up", content)

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
            # true_end - true_start, not block.duration -- duration is
            # clipped to the visible window (schedule_model._clip_to_window /
            # draft_model._build_change_block), so a program landing near
            # the window's edge would otherwise show its real, uncropped
            # time range next to a truncated-looking minute count.
            minutes = max(1, round((block.true_end - block.true_start) / 60))
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
    card = StudioSection("Channel Defaults", content=content, collapsible=False, accent=False)

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

    # A thin category-colored accent, restrained on purpose -- reuses
    # program_block.MEDIA_TYPE_ACCENTS (the exact palette the board's own
    # blocks and the legend already use) so the inspector's accent can
    # never drift from what the board shows. Neutral/transparent when
    # nothing is selected.
    accent_bar = QFrame()
    accent_bar.setObjectName("selectedProgramAccentBar")
    accent_bar.setFixedWidth(3)
    accent_bar.setStyleSheet(f"background: {_ACCENT_NEUTRAL}; border-radius: 1px;")
    outer.addWidget(accent_bar)

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

    layout.addWidget(_prompt_label("No program selected."))

    def update(block, lane):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        if block is None:
            accent_bar.setStyleSheet(f"background: {_ACCENT_NEUTRAL}; border-radius: 1px;")
            if lane is not None:
                layout.addWidget(_prompt_label(f"Ch {lane.number} · {lane.name}"))
            else:
                layout.addWidget(_prompt_label("No program selected."))
            return

        _, accent_color = MEDIA_TYPE_ACCENTS.get(block.media_type, MEDIA_TYPE_ACCENTS["tv"])
        accent_bar.setStyleSheet(f"background: {accent_color}; border-radius: 1px;")

        title_lbl = QLabel(block.title)
        title_lbl.setStyleSheet(f"color: {_VALUE_COLOR}; font-size: 15px; font-weight: 700; background: transparent;")
        layout.addWidget(title_lbl)

        start_label = time.strftime("%-I:%M %p", time.localtime(block.true_start))
        end_label = time.strftime("%-I:%M %p", time.localtime(block.true_end))
        # true_end - true_start, not block.duration -- see build_next_up_card's
        # identical fix for why (block.duration is clipped to the visible
        # window, true_start/true_end are not).
        minutes = max(1, round((block.true_end - block.true_start) / 60))
        media_label = MEDIA_TYPE_LABELS.get(block.media_type, "Program")
        detail_parts = []
        if lane is not None:
            detail_parts.append(f"Ch {lane.number} · {lane.name}")
        detail_parts.append(f"{start_label}–{end_label} · {minutes} min · {media_label}")
        layout.addWidget(_dim_line("   ·   ".join(detail_parts)))

        if block.media_type == "open":
            origin_label = "Unsaved open time" if block.source == "draft" else "Open time"
            layout.addWidget(_dim_line(origin_label))
            return

        if block.source == "draft":
            origin_parts = ["Your unsaved schedule edit"]
        elif block.source == "override":
            override_path = (block.raw_entries[0] or {}).get("path", "") if block.raw_entries else ""
            if override_path and not os.path.isfile(override_path):
                origin_parts = ["Saved change needs attention"]
            else:
                origin_parts = ["Scheduled by you"]
        else:
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

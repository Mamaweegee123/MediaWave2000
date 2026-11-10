"""AutoFillBlockDialog: Phase 4's Auto-Fill Block UI.

A guided workflow over the existing autofill_planner.py functions --
this module never generates a lineup itself, only calls plan_best_fit_mix/
plan_continue_sequentially/plan_show_marathon/plan_random_mix and
displays whatever they return. Nothing here touches the draft: the
workspace (dialog.py's _auto_fill_block_clicked) builds ONE
AutoFillBlockCommand from this dialog's previewed lineup and runs it
through the exact same validate/execute path every other command uses.
Same division of labor FillOpenTimePickerDialog already has for Put On
Air, just for a whole generated lineup instead of one item.

Grouping shows for the picker combo box is handled by mediawave.
show_identity.group_catalog_by_show (Phase 5.5.2) -- a plain grouping of
build_picker_catalog's existing items by the show_key they already
carry, shared with put_on_air_picker.py and programming_block_dialog.py
rather than reimplemented here.
"""

import random
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mediawave.commercials import is_commercial_entry

from ..show_identity import group_catalog_by_show
from .autofill_cursor import last_aired_path_for
from .autofill_planner import (
    STRATEGY_BEST_FIT,
    STRATEGY_LABELS,
    STRATEGY_MARATHON,
    STRATEGY_RANDOM,
    STRATEGY_SEQUENTIAL,
    episode_sort_key,
    plan_best_fit_mix,
    plan_continue_sequentially,
    plan_random_mix,
    plan_show_marathon,
)
from .program_block import MEDIA_TYPE_ACCENTS
from .put_on_air_picker import format_duration_minutes

_TEXT_COLOR = "rgba(210, 222, 252, 235)"
_DIM_COLOR = "rgba(138, 158, 212, 220)"
_PANEL_BG = "rgba(13, 16, 38, 255)"
_ROW_BG = "rgba(22, 26, 58, 200)"
# A touch dimmer than a program row's _ROW_BG -- "slightly quieter than
# program rows while retaining their media-type accent" (a real
# commercial's own MEDIA_TYPE_ACCENTS entry is used for the accent bar
# itself; this only dims the card face behind it).
_ROW_BG_COMMERCIAL = "rgba(18, 20, 46, 165)"
_ACCENT = "rgba(96, 144, 255, 170)"

_CHIP_STYLE = """
    QPushButton {
        min-width: 0px; min-height: 26px; padding: 4px 12px;
        border-radius: 13px; border: 1px solid rgba(68, 108, 235, 90);
        background: transparent; color: rgba(210, 222, 252, 220); font-size: 11px;
    }
    QPushButton:checked {
        background: rgba(50, 70, 160, 160); border: 1px solid rgba(96, 144, 255, 200);
        color: white;
    }
"""

_COMBO_STYLE = (
    f"QComboBox {{ background: rgba(22, 26, 58, 232); color: {_TEXT_COLOR};"
    f" border: 1px solid rgba(68, 108, 235, 90); border-radius: 6px; padding: 5px 10px; }}"
)

STRATEGY_ORDER = [STRATEGY_BEST_FIT, STRATEGY_SEQUENTIAL, STRATEGY_MARATHON, STRATEGY_RANDOM]

# Strategies whose preview depends on a chosen show, not just the catalog.
_SHOW_STRATEGIES = {STRATEGY_SEQUENTIAL, STRATEGY_MARATHON}


def _format_clock(epoch_seconds):
    try:
        return time.strftime("%-I:%M %p", time.localtime(epoch_seconds))
    except (OSError, OverflowError, ValueError):
        return ""


def _format_duration_long(seconds):
    """'2 hr 58 min' / '3 hr' / '45 min' -- the summary area's duration
    format, distinct from format_duration_minutes' plain 'N min' (used on
    each compact row, where an hours/minutes split would be more text
    than a single placement's length needs).
    """
    total_minutes = max(1, round(float(seconds or 0) / 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours} hr {minutes} min"
    if hours:
        return f"{hours} hr"
    return f"{minutes} min"


def build_preview_plan(strategy, items, block_start, block_duration, show=None, cursor_data=None, channel_id=None, seed=None, show_identity_registry=None):
    """The one place strategy -> planner call is decided, so the dialog
    and its tests agree exactly on what each strategy means. Returns
    (plan, notes) -- `plan` is a planner result dict (or None if this
    strategy needs a show that isn't chosen yet), `notes` is a list of
    short, honest, user-facing sentences for the preview's "Programming
    notes" area (0 or 1 items today; a list so a future strategy could
    add a second without changing this contract). Every sentence here is
    about PLACEMENT history (what this feature has scheduled before),
    never a claim about actual airing/playback -- see autofill_cursor.py.

    `show_identity_registry` (Phase 5.5.2 step 4) is forwarded to
    last_aired_path_for's legacy-alias search below -- None preserves
    today's exact canonical-only cursor lookup.
    """
    if strategy == STRATEGY_BEST_FIT:
        plan = plan_best_fit_mix(items, block_start, block_duration)
        notes = ["Prioritized using as much of the available block as possible."] if plan["lineup"] else []
        return plan, notes
    if strategy == STRATEGY_RANDOM:
        plan = plan_random_mix(items, block_start, block_duration, seed=seed)
        notes = ["Immediate title repeats were avoided."] if len(plan["lineup"]) > 1 else []
        return plan, notes
    if strategy in _SHOW_STRATEGIES:
        if show is None:
            return None, []
        ordered = sorted(show["episodes"], key=episode_sort_key)
        if strategy == STRATEGY_MARATHON:
            plan = plan_show_marathon(ordered, block_start, block_duration)
            notes = ["Built from one show in episode order."] if plan["lineup"] else []
            return plan, notes
        # Continue Sequentially.
        last_path = None
        if cursor_data is not None and channel_id is not None:
            last_path = last_aired_path_for(cursor_data, channel_id, show["show_key"], show_identity_registry=show_identity_registry)
        plan = plan_continue_sequentially(ordered, block_start, block_duration, last_aired_path=last_path)
        if not plan["lineup"]:
            return plan, []
        matched = next((episode for episode in ordered if episode["path"] == last_path), None) if last_path else None
        if last_path is None:
            note = "No prior sequential Auto-Fill placement was found, so this begins with the first available episode."
        elif matched is None:
            note = "The previously saved episode is no longer available, so this begins with the first available episode."
        else:
            season, episode = matched.get("season_number"), matched.get("episode_number")
            if season is not None and episode is not None:
                note = f"Continues after S{season} · E{episode} from the last saved sequential Auto-Fill placement."
            else:
                note = "Continues after the last saved sequential Auto-Fill placement."
        return plan, [note]
    return None, []


def distinct_show_count(lineup):
    """Number of distinct program identities in a lineup -- each entry's
    `show_key` when present (groups a show's episodes together; every
    catalog-derived entry has one, see put_on_air_picker.build_picker_
    catalog), falling back to `path` for anything that somehow doesn't
    (defensive only -- real planner output always carries show_key).
    """
    return len({entry.get("show_key") or entry.get("path", "") for entry in lineup})


def build_summary_lines(plan):
    """The "compact lineup summary" text (a plain list of lines, not yet
    joined, so widget code and tests can each decide how to render/
    inspect it) -- derived entirely from one planner result dict's
    existing fields (`lineup`, `filled_seconds`, `gap_duration`,
    `leftover_seconds`); no planner or draft state is touched to produce
    it. Returns [] for an empty/missing plan -- callers hide the summary
    entirely in that case.

    "programs" deliberately EXCLUDES real commercial breaks (identified
    only via is_commercial_entry -- never by title/filename text, see
    _build_placement_row's docstring for why): a commercial pod isn't a
    program the user picked or the planner chose for its content, so
    counting it as one of "N programs" would overstate how much actual
    programming is in the block. Commercials get their own explicit
    "Includes N commercial breaks" line instead, only when at least one
    is present. As of this pass no real Auto-Fill catalog entry is ever
    commercial-flagged (see the module docstring's investigation note),
    so in practice this line never renders yet -- it's here so the
    summary is already correct the day that changes.
    """
    lineup = (plan or {}).get("lineup") or []
    if not lineup:
        return []
    programs = [entry for entry in lineup if not is_commercial_entry(entry)]
    commercials = [entry for entry in lineup if is_commercial_entry(entry)]
    filled = plan["filled_seconds"]
    gap = plan["gap_duration"]
    leftover = plan["leftover_seconds"]

    lines = []
    if programs:
        count = len(programs)
        shows = distinct_show_count(programs)
        lines.append(
            f"{count} program{'' if count == 1 else 's'} · "
            f"{shows} show{'' if shows == 1 else 's'} · "
            f"{_format_duration_long(filled)} scheduled"
        )
    else:
        # Defensive only (see docstring): a lineup that's ALL commercial
        # breaks with no ordinary programs at all.
        lines.append(f"{_format_duration_long(filled)} scheduled")
    if commercials:
        count = len(commercials)
        lines.append(f"Includes {count} commercial break{'' if count == 1 else 's'}")
    if leftover < 30:
        lines.append("Uses the full block")
    else:
        fill_pct = round((filled / gap) * 100) if gap > 0 else 100
        lines.append(f"{fill_pct}% filled · {_format_duration_long(leftover)} Open Time")
    return lines


def commercial_source_label(entry):
    """A real, already-existing break-source label for a commercial
    placement, or "" if none is available -- reads the same `category`
    field the live commercial-scheduling engine already attaches to a
    real commercial pod entry (channelsurfer2000.py's commercial-break
    builder), NEVER inferred from a path or filename. This module can't
    import that field's formatter (channelsurfer2000.py sits above
    mediawave/schedule_editor in the dependency direction), so the raw
    category text is shown as-is rather than re-deriving a lookup table
    here -- acceptable since, per this pass's investigation, no current
    Auto-Fill data path ever populates `category` anyway; this only
    matters the day a future feature feeds real commercial entries in.
    """
    if not is_commercial_entry(entry):
        return ""
    return str(entry.get("category") or "").strip()


def _build_placement_row(entry):
    """One compact "card" row for the preview list: a thin left accent
    bar in the placement's media-type color (program_block.py's existing
    MEDIA_TYPE_ACCENTS -- the same colors the real board uses, so a
    preview row and its board block always agree), a time/duration line,
    the title as the strongest text, and the episode line when present.
    A dedicated QWidget (via QListWidget.setItemWidget) rather than a
    joined plain-text QListWidgetItem string -- the only way to get a
    right-aligned duration and a distinct title/episode type scale
    cleanly. Purely a display transform of one already-generated
    placement dict; never reads or writes anything beyond `entry`.

    A real commercial placement (is_commercial_entry(entry) -- NEVER
    guessed from title/filename text) never shows its own filename/title
    as the heading: it reads "Commercial Break", with the break's real
    source label (commercial_source_label) as a quiet subtitle when one
    exists, and a dimmer card face than an ordinary program row.
    """
    is_commercial = is_commercial_entry(entry)
    widget = QWidget()
    widget.setObjectName("autofillRow")
    accent_key = "commercial" if is_commercial else entry.get("media_type", "tv")
    _, border = MEDIA_TYPE_ACCENTS.get(accent_key, MEDIA_TYPE_ACCENTS["tv"])
    row_bg = _ROW_BG_COMMERCIAL if is_commercial else _ROW_BG
    widget.setStyleSheet(
        f"QWidget#autofillRow {{ background: {row_bg}; border-radius: 8px; }}"
    )

    outer = QHBoxLayout(widget)
    outer.setContentsMargins(0, 0, 10, 0)
    outer.setSpacing(10)

    accent = QFrame()
    accent.setFixedWidth(4)
    accent.setStyleSheet(f"background: {border}; border-top-left-radius: 8px; border-bottom-left-radius: 8px;")
    outer.addWidget(accent)

    content = QVBoxLayout()
    content.setContentsMargins(0, 6, 0, 6)
    content.setSpacing(1)

    top_row = QHBoxLayout()
    top_row.setSpacing(6)
    time_lbl = QLabel(f"{_format_clock(entry['start'])}–{_format_clock(entry['end'])}")
    time_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
    top_row.addWidget(time_lbl)
    top_row.addStretch(1)
    duration_lbl = QLabel(format_duration_minutes(entry.get("duration", 0)))
    duration_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
    duration_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    top_row.addWidget(duration_lbl)
    content.addLayout(top_row)

    title_lbl = QLabel("Commercial Break" if is_commercial else (entry.get("title") or "Untitled"))
    title_style = f"color: {_DIM_COLOR}; font-size: 13px; font-weight: 700;" if is_commercial else f"color: {_TEXT_COLOR}; font-size: 13px; font-weight: 700;"
    title_lbl.setStyleSheet(title_style)
    title_lbl.setWordWrap(True)
    content.addWidget(title_lbl)

    if is_commercial:
        source_label = commercial_source_label(entry)
        if source_label:
            subtitle_lbl = QLabel(f"[{source_label}]")
            subtitle_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
            content.addWidget(subtitle_lbl)
    elif entry.get("episode_label"):
        episode_lbl = QLabel(entry["episode_label"])
        episode_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
        content.addWidget(episode_lbl)

    outer.addLayout(content, 1)
    return widget


class AutoFillBlockDialog(QDialog):
    """Choose a fill strategy, preview the generated lineup, and confirm.
    `previewed_lineup()` returns the planner's lineup (the same shape
    AutoFillBlockCommand expects) after exec() == Accepted; this dialog
    never applies it itself.
    """

    def __init__(self, items, channel_id, channel_number, channel_name, block_start, block_end, cursor_data=None, show_identity_registry=None, parent=None):
        super().__init__(parent)
        self._items = items
        self._channel_id = channel_id
        self._block_start = block_start
        self._block_end = block_end
        self._block_duration = max(0.0, block_end - block_start)
        self._cursor_data = cursor_data
        # Phase 5.5.2 step 4: forwarded to build_preview_plan's cursor
        # lookup above.
        self._show_identity_registry = show_identity_registry
        self._shows = group_catalog_by_show(items)
        self._strategy = STRATEGY_BEST_FIT
        self._plan = None
        self._random_seed = 0

        self.setWindowTitle("Auto-Fill Block")
        self.setModal(True)
        self.resize(560, 620)
        self.setStyleSheet(
            f"QDialog {{ background: {_PANEL_BG}; }}"
            f"QLabel {{ color: {_TEXT_COLOR}; }}"
            f"QListWidget {{ background: transparent; border: none; outline: none; }}"
            # Each row is its own widget (see _build_placement_row) that
            # draws its own card background/radius -- the list item itself
            # only contributes the margin between cards, not a second
            # nested background/padding.
            f"QListWidget::item {{ background: transparent; margin: 3px 0px; padding: 0px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        heading = QLabel("Auto-Fill Block")
        heading.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(heading)

        context = QLabel(
            f"Ch {channel_number} · {channel_name}\n"
            f"{_format_clock(block_start)}–{_format_clock(block_end)} · {format_duration_minutes(self._block_duration)} open"
        )
        context.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px;")
        layout.addWidget(context)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(6)
        self._chips = {}
        for strategy in STRATEGY_ORDER:
            chip = QPushButton(STRATEGY_LABELS[strategy])
            chip.setCheckable(True)
            chip.setChecked(strategy == self._strategy)
            chip.setStyleSheet(_CHIP_STYLE)
            if strategy in _SHOW_STRATEGIES and not self._shows:
                chip.setEnabled(False)
            chip.clicked.connect(lambda _checked, s=strategy: self._set_strategy(s))
            chip_row.addWidget(chip)
            self._chips[strategy] = chip
        chip_row.addStretch(1)
        layout.addLayout(chip_row)

        self._show_combo = QComboBox()
        self._show_combo.setStyleSheet(_COMBO_STYLE)
        for show in sorted(self._shows.values(), key=lambda s: s["title"].lower()):
            self._show_combo.addItem(show["title"], show["show_key"])
        self._show_combo.currentIndexChanged.connect(lambda _index: self._regenerate())
        layout.addWidget(self._show_combo)
        self._show_combo.setVisible(self._strategy in _SHOW_STRATEGIES)

        # "GENERATED LINEUP" header, directly above the preview list --
        # same eyebrow-label visual language as the Selected Program
        # footer's "SELECTED PROGRAM" (utility_panels.py), with
        # Regenerate right-aligned in the same compact row rather than
        # floating in its own row above the list.
        list_header = QHBoxLayout()
        list_header.setSpacing(6)
        list_eyebrow = QLabel("GENERATED LINEUP")
        list_eyebrow.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        list_header.addWidget(list_eyebrow)
        list_header.addStretch(1)
        self._regen_btn = QPushButton("Regenerate")
        self._regen_btn.setStyleSheet(_CHIP_STYLE)
        self._regen_btn.clicked.connect(self._regenerate_randomly)
        list_header.addWidget(self._regen_btn)
        layout.addLayout(list_header)
        self._regen_btn.setVisible(self._strategy == STRATEGY_RANDOM)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.NoSelection)
        self._list.setFocusPolicy(Qt.NoFocus)
        self._list.setSpacing(0)
        self._list.setUniformItemSizes(False)
        self._list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        # Bottom padding inside the list's own viewport (not a fake
        # trailing row) so the last card has breathing room before the
        # summary/scrollbar -- the smallest clean Qt way to get spacing
        # without inventing a placement-shaped list item.
        self._list.setViewportMargins(0, 0, 0, 6)
        layout.addWidget(self._list, 1)

        # Compact lineup summary: program/show counts, scheduled
        # duration, and either "Uses the full block" or a fill
        # percentage + remaining Open Time -- see build_summary_lines().
        self._summary = QLabel("")
        self._summary.setStyleSheet(f"color: {_TEXT_COLOR}; font-size: 12px; font-weight: 600;")
        layout.addWidget(self._summary)

        # "Programming notes": one short, honest sentence about how this
        # lineup was built (see build_preview_plan) -- only ever shown
        # when there's something genuinely useful to say, never on every
        # generation.
        self._notes = QLabel("")
        self._notes.setWordWrap(True)
        self._notes.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
        layout.addWidget(self._notes)
        self._notes.hide()

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self._confirm_btn = QPushButton("Place Lineup")
        self._confirm_btn.clicked.connect(self.accept)
        button_row.addWidget(self._confirm_btn)
        layout.addLayout(button_row)

        self._regenerate()

    # ── strategy / preview ───────────────────────────────────────────

    def _set_strategy(self, strategy):
        self._strategy = strategy
        for name, chip in self._chips.items():
            chip.setChecked(name == strategy)
        self._show_combo.setVisible(strategy in _SHOW_STRATEGIES)
        self._regen_btn.setVisible(strategy == STRATEGY_RANDOM)
        self._regenerate()

    def _selected_show(self):
        if self._strategy not in _SHOW_STRATEGIES or self._show_combo.count() == 0:
            return None
        show_key = self._show_combo.currentData()
        return self._shows.get(show_key)

    def _regenerate_randomly(self):
        self._random_seed += 1
        self._regenerate()

    def _regenerate(self):
        """Rebuilds the preview from the planner -- pure read: never
        creates a DraftChange, never touches the autofill cursor, never
        records recent media. Safe to call as often as the UI likes.
        """
        show = self._selected_show()
        plan, notes = build_preview_plan(
            self._strategy,
            self._items,
            self._block_start,
            self._block_duration,
            show=show,
            cursor_data=self._cursor_data,
            channel_id=self._channel_id,
            seed=self._random_seed,
            show_identity_registry=self._show_identity_registry,
        )
        self._plan = plan

        self._notes.setText("\n".join(notes))
        self._notes.setVisible(bool(notes))

        self._list.clear()
        lineup = (plan or {}).get("lineup") or []
        for entry in lineup:
            row_widget = _build_placement_row(entry)
            item = QListWidgetItem()
            item.setFlags(Qt.NoItemFlags)
            self._list.addItem(item)
            item.setSizeHint(row_widget.sizeHint())
            self._list.setItemWidget(item, row_widget)

        if not lineup:
            placeholder = QListWidgetItem(self._empty_state_text(show))
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsEnabled)
            self._list.addItem(placeholder)

        summary_lines = build_summary_lines(plan)
        self._summary.setText("\n".join(summary_lines))

        self._confirm_btn.setEnabled(bool(lineup))

    def _empty_state_text(self, show):
        if self._strategy in _SHOW_STRATEGIES and not self._shows:
            return "No shows found in the catalog yet — Auto-Fill Block needs at least one TV show with episodes."
        if self._strategy in _SHOW_STRATEGIES and show is None:
            return "Choose a show above to preview a lineup."
        if self._strategy in _SHOW_STRATEGIES:
            return "This show doesn't have any playable episodes yet."
        return "Nothing in the catalog fits this open time yet."

    # ── result ────────────────────────────────────────────────────────

    def previewed_lineup(self):
        return list((self._plan or {}).get("lineup") or [])

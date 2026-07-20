"""ScheduleEditorWorkspace: the programming board with draft editing.

A first-class Advanced Configuration workspace (its own left-sidebar nav
item, `AdvancedConfigDialog`'s `_enter_schedule_editor_mode` /
`build_schedule_editor_tab`, channelsurfer2000.py) rather than something
buried inside Channel Studio -- `build_schedule_editor_tab(studio_dialog,
on_back=...)` returns `(workspace, footer)` the exact same shape
`channel_studio.build_channel_studio_tab` does, so `AdvancedConfigDialog`
can add it to its mode/footer stacks identically.

Phase 2 editing model -- every edit is draft-isolated:

  base lanes (schedule_model.build_board_model, read from live channels)
      -> DraftSchedule (draft_model.py): cloned snapshot + change records
      -> Pull / Put On Air commands (commands.py) through CommandHistory
      -> Save Schedule serializes the changes to per-date override records
         and hands them to the app's save pipeline
         (`studio_dialog._schedule_overrides_save`, which is
         save_schedule_overrides_from_editor in channelsurfer2000.py)

Nothing in this workspace mutates live channels, playback, schedule
caches, or settings; the ONLY write path is that save callback, and it
runs solely from the explicit Save Schedule flow. Closing or navigating
away with unsaved changes routes through `confirm_leave()` (Save /
Discard / Keep Editing) -- also invoked by `AdvancedConfigDialog.reject`
so closing the whole dialog can't silently drop a dirty draft.
"""

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mediawave.channel_studio import channel_actions
from mediawave.channel_studio import companion_adapter
from mediawave.channel_studio.channel_studio_adapter import build_channel_studio_summaries
from mediawave.channel_studio.channel_studio_model import ChannelStudioSummary
from mediawave.studio.cards import build_empty_state_card
from mediawave.studio.spacing import OUTER_MARGIN
from mediawave.studio.styles import build_scroll_area

from .board import ProgrammingBoard
from .commands import (
    CONFLICT_OVERLAPS_DESTINATION,
    CONFLICT_OVERLAPS_FOLLOWING,
    CommandHistory,
    DuplicateProgramCommand,
    MoveProgramCommand,
    PullProgramCommand,
    PutOnAirCommand,
)
from .copy_to_day_dialog import CopyToAnotherDayDialog
from .draft_model import DraftSchedule
from .duplicate_dialog import DuplicateHereDialog
from .fill_open_time_picker import FillOpenTimePickerDialog
from .move_to_dialog import MoveToDialog
from .program_block import build_category_legend
from .put_on_air_picker import PutOnAirPickerDialog, build_picker_catalog
from .saved_changes_manager import SavedChangesManagerDialog
from .schedule_model import build_board_model, sort_channel_rows
from .utility_panels import (
    build_channel_defaults_card,
    build_editing_tools_card,
    build_next_up_card,
    build_pending_changes_card,
    build_selected_program_footer,
)

_WINDOW_HOURS = 4.5
# ~26% of the ~1400px default Schedule Editor width (_enter_schedule_editor_mode,
# channelsurfer2000.py) -- inside the target 24-28% band at the default
# window size. Fixed, not resize-responsive: the guide column already
# takes all the *remaining* width and scrolls horizontally on its own (see
# board.py), so this panel never needs to shrink to make room for it.
_RIGHT_COLUMN_WIDTH = 360

_TOP_BAR_BG = "rgba(9, 11, 27, 255)"
_TOP_BAR_BORDER = "rgba(42, 54, 128, 255)"
_SUBTITLE_COLOR = "rgba(138, 158, 212, 220)"

# A quiet, flat look for Back/prev/Today/next -- the app-wide QPushButton
# rule (channelsurfer2000.py) gives every plain button a filled-blue
# ~110x32px box, which made the whole toolbar read as a row of
# similarly-weighted controls competing with the board for attention.
# No min-width override, smaller padding -- these are navigation, not
# primary actions.
_NAV_BUTTON_STYLE = """
    QPushButton {
        min-width: 0px;
        min-height: 26px;
        padding: 4px 10px;
        border-radius: 5px;
        border: 1px solid rgba(68, 108, 235, 90);
        background: transparent;
        color: rgba(210, 222, 252, 230);
        font-size: 12px;
    }
    QPushButton:hover:enabled, QPushButton:focus {
        border: 1px solid rgba(96, 144, 255, 170);
        background: rgba(50, 70, 160, 90);
        color: white;
    }
    QPushButton:disabled {
        border: 1px solid rgba(90, 100, 140, 60);
        background: transparent;
        color: rgba(120, 132, 168, 150);
    }
"""

# Save Schedule: the toolbar's one primary action -- filled when armed,
# clearly inert when the draft is clean.
_SAVE_BUTTON_STYLE = """
    QPushButton {
        min-width: 0px;
        min-height: 26px;
        padding: 4px 14px;
        border-radius: 5px;
        border: 1px solid rgba(96, 144, 255, 190);
        background: rgba(56, 84, 200, 190);
        color: white;
        font-size: 12px;
        font-weight: 600;
    }
    QPushButton:hover:enabled {
        border: 1px solid rgba(130, 170, 255, 230);
        background: rgba(70, 100, 224, 220);
    }
    QPushButton:disabled {
        border: 1px solid rgba(90, 100, 140, 60);
        background: transparent;
        color: rgba(120, 132, 168, 150);
        font-weight: 400;
    }
"""

# The restrained unsaved-changes indicator -- same corner the READ-ONLY
# badge occupied in Phase 1, amber instead of alarming red, hidden
# entirely when the draft is clean.
_DIRTY_BADGE_STYLE = (
    "color: rgba(255, 214, 120, 225); font-size: 10px; font-weight: 700;"
    " letter-spacing: 1px; background: transparent;"
)
_SAVED_BADGE_STYLE = (
    "color: rgba(130, 220, 160, 220); font-size: 10px; font-weight: 700;"
    " letter-spacing: 1px; background: transparent;"
)


def _channel_enabled(channel_id, catalog_channel_settings):
    settings = catalog_channel_settings if isinstance(catalog_channel_settings, dict) else {}
    row = settings.get(channel_id, {})
    if not isinstance(row, dict):
        return True
    return bool(row.get("enabled", True))


def _build_channel_rows(studio_dialog):
    """Enabled channels only (local + companion), each a plain dict with
    the fields schedule_model.build_board_model needs, plus a parallel
    ChannelStudioSummary lookup for the Channel Defaults panel. Mirrors
    channel_studio_pages.py's own local/companion assembly so this reuses
    the exact same read-only data Channel Studio already shows.
    """
    infos = list(getattr(studio_dialog, "catalog_channel_infos", None) or [])
    catalog_channel_settings = getattr(studio_dialog, "catalog_channel_settings", None)
    logo_lookup = getattr(studio_dialog, "_channel_logo_lookup", None) or {}

    local_infos = [
        info
        for info in infos
        if info.get("channel_type", "media") not in companion_adapter.COMPANION_TYPES
        and _channel_enabled(info.get("id", ""), catalog_channel_settings)
    ]
    local_summaries = build_channel_studio_summaries(
        local_infos,
        shows_lookup=getattr(studio_dialog, "_channel_shows_lookup", None),
        catalog_channel_settings=catalog_channel_settings,
        commercials_config=getattr(studio_dialog, "commercials_settings", None),
        airing_rules_config=getattr(studio_dialog, "_airing_rules_config", None),
        logo_lookup=logo_lookup,
    )

    companion_snapshot = channel_actions.companion_snapshot_from_dialog(studio_dialog)
    companion_status = channel_actions.companion_status_from_dialog(studio_dialog)
    companion_summaries = [
        ChannelStudioSummary(**fields)
        for fields in companion_adapter.companion_summaries(companion_snapshot, companion_status)
    ]

    summaries = list(local_summaries) + companion_summaries
    summaries_by_id = {summary.channel_id: summary for summary in summaries}

    rows = [
        {
            "channel_id": summary.channel_id,
            "name": summary.name,
            "number": summary.number,
            "channel_type": summary.channel_type,
            "logo_path": logo_lookup.get(summary.channel_id, summary.logo_path or ""),
        }
        for summary in summaries
    ]
    return sort_channel_rows(rows), summaries_by_id


def _floor_to_half_hour(epoch_seconds):
    return epoch_seconds - (epoch_seconds % (30 * 60))


def _compact_date(epoch_seconds):
    """The guide-corner date label: "Thu 7-16-26" -- a compact guide
    label beside the time ruler, not a page heading (the board itself is
    what says which day you're looking at).
    """
    return time.strftime("%a %-m-%-d-%y", time.localtime(epoch_seconds))


class ScheduleEditorWorkspace(QWidget):
    def __init__(self, studio_dialog, on_back=None, parent=None):
        super().__init__(parent)
        self._studio_dialog = studio_dialog
        self._on_back = on_back

        self._channel_rows, self._summaries_by_id = _build_channel_rows(studio_dialog)
        self._studio_channels_by_id = getattr(studio_dialog, "_studio_channels_by_id", None) or {}
        self._lanes_by_channel_id = {}
        self._window_start = _floor_to_half_hour(time.time())
        # None until the non-empty-state branch below builds it -- every
        # render/refresh path guards on this, so the empty-channels
        # workspace (which still owns a live draft + toolbar) never
        # crashes on a board it doesn't have.
        self.board = None

        # The draft layer: cloned base lanes + change records + command
        # history. Everything the editing UI touches lives here until
        # Save Schedule.
        self._draft = DraftSchedule()
        self._history = CommandHistory()
        self._selected_block = None
        self._saved_badge_timer = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._top_bar = self._build_top_bar()
        outer.addWidget(self._top_bar)

        # The Selected Program inspector is this workspace's footer page
        # (see build_schedule_editor_tab) -- built unconditionally, before
        # the empty-channels early return, so the footer contract holds
        # even when there's no board to select anything on.
        self._details_footer, self._update_details = build_selected_program_footer()

        if not self._channel_rows:
            empty = build_empty_state_card(
                "No channels are ready yet",
                _empty_state_label("Create or enable a channel in Channel Studio to build a lineup."),
            )
            wrap = QWidget()
            wrap_layout = QVBoxLayout(wrap)
            wrap_layout.setContentsMargins(*OUTER_MARGIN)
            wrap_layout.addWidget(empty)
            wrap_layout.addStretch(1)
            outer.addWidget(wrap, 1)
            return

        self.board = ProgrammingBoard()
        self.board.program_selected.connect(self._on_program_selected)
        self.board.channel_selected.connect(self._on_channel_selected)
        self.board.move_drop.connect(self._on_move_drop)
        self.board.set_drop_validator(self._validate_drop_preview)

        self._editing_tools_card, self._tools = build_editing_tools_card(
            on_put_on_air=self._put_on_air_clicked,
            on_pull=self._pull_clicked,
            on_move_to=self._move_to_clicked,
            on_duplicate_here=self._duplicate_here_clicked,
            on_copy_to_day=self._copy_to_day_clicked,
            on_fill_open_time=self._fill_open_time_clicked,
        )
        self._pending_changes_card, self._update_pending_changes = build_pending_changes_card()
        self._next_up_card, self._update_next_up = build_next_up_card()
        self._channel_defaults_card, self._update_channel_defaults = build_channel_defaults_card()

        # The column is NOT fixed-width -- build_scroll_area's
        # widgetResizable sizes it to the scroll viewport, which shrinks
        # by the vertical scrollbar's width when one appears. A fixed
        # 360px column inside that narrower viewport forced a spurious
        # horizontal scrollbar under the cards (the stray blue bar), plus
        # a white unstyled scroll-corner artifact where the two bars met.
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 4, 0, 4)
        right_layout.setSpacing(18)
        right_layout.addWidget(self._editing_tools_card)
        right_layout.addWidget(self._pending_changes_card)
        right_layout.addWidget(self._next_up_card)
        right_layout.addWidget(self._channel_defaults_card)
        right_layout.addStretch(1)
        right_scroll = build_scroll_area(right_column)
        right_scroll.setFixedWidth(_RIGHT_COLUMN_WIDTH + 4)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # The legend sits directly under the guide board, left-aligned --
        # a guide key grounded to the board it describes, not a toolbar
        # element. Scoped to the board column's width, so it never drifts
        # under the right utility panel.
        self._guide_column = QWidget()
        guide_layout = QVBoxLayout(self._guide_column)
        guide_layout.setContentsMargins(0, 0, 0, 0)
        guide_layout.setSpacing(8)
        guide_layout.addWidget(self.board, 1)

        legend_row = QHBoxLayout()
        legend_row.setContentsMargins(0, 0, 0, 0)
        legend_row.setSpacing(10)
        legend_row.addWidget(build_category_legend())
        legend_row.addStretch(1)
        guide_layout.addLayout(legend_row)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(16)
        content_row.addWidget(self._guide_column, 1)
        content_row.addWidget(right_scroll)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(*OUTER_MARGIN)
        content_layout.setSpacing(16)
        content_layout.addLayout(content_row, 1)

        outer.addWidget(content, 1)

        self._refresh_board()

    # ── top bar ──────────────────────────────────────────────────────

    def _build_top_bar(self):
        """One compact row: Back on the far left, day navigation next to
        it, the unsaved-changes badge and Undo/Redo/Revert/Save
        right-aligned. The category legend lives under the guide board
        (see __init__'s guide column), not up here.
        """
        bar = QWidget()
        bar.setObjectName("scheduleTopBar")
        bar.setStyleSheet(
            f"QWidget#scheduleTopBar {{ background: {_TOP_BAR_BG}; border-bottom: 1px solid {_TOP_BAR_BORDER}; }}"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(20, 10, 20, 10)
        row.setSpacing(10)

        back_btn = QPushButton("←  Back")
        back_btn.setStyleSheet(_NAV_BUTTON_STYLE)
        back_btn.clicked.connect(self._back)
        row.addWidget(back_btn)

        row.addSpacing(10)

        prev_btn = QPushButton("‹")
        prev_btn.setFixedWidth(30)
        prev_btn.setStyleSheet(_NAV_BUTTON_STYLE)
        prev_btn.clicked.connect(lambda: self._shift_day(-1))
        row.addWidget(prev_btn)

        today_btn = QPushButton("Today")
        today_btn.setStyleSheet(_NAV_BUTTON_STYLE)
        today_btn.clicked.connect(self._go_to_today)
        row.addWidget(today_btn)

        next_btn = QPushButton("›")
        next_btn.setFixedWidth(30)
        next_btn.setStyleSheet(_NAV_BUTTON_STYLE)
        next_btn.clicked.connect(lambda: self._shift_day(1))
        row.addWidget(next_btn)

        row.addStretch(1)

        self._status_badge = QLabel("")
        self._status_badge.setStyleSheet(_DIRTY_BADGE_STYLE)
        row.addWidget(self._status_badge)
        row.addSpacing(6)

        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setStyleSheet(_NAV_BUTTON_STYLE)
        self._undo_btn.clicked.connect(self._undo_clicked)
        row.addWidget(self._undo_btn)

        self._redo_btn = QPushButton("Redo")
        self._redo_btn.setStyleSheet(_NAV_BUTTON_STYLE)
        self._redo_btn.clicked.connect(self._redo_clicked)
        row.addWidget(self._redo_btn)

        self._revert_btn = QPushButton("Revert Draft")
        self._revert_btn.setStyleSheet(_NAV_BUTTON_STYLE)
        self._revert_btn.clicked.connect(self._revert_clicked)
        row.addWidget(self._revert_btn)

        self._saved_changes_btn = QPushButton("Saved Changes")
        self._saved_changes_btn.setStyleSheet(_NAV_BUTTON_STYLE)
        self._saved_changes_btn.clicked.connect(self._open_saved_changes_manager)
        self._saved_changes_btn.setToolTip("Review or remove schedule changes you've already saved for this date.")
        row.addWidget(self._saved_changes_btn)

        self._save_btn = QPushButton("Save Schedule")
        self._save_btn.setStyleSheet(_SAVE_BUTTON_STYLE)
        self._save_btn.clicked.connect(self._save_clicked)
        row.addWidget(self._save_btn)

        self._update_toolbar_state()
        return bar

    def _update_toolbar_state(self):
        dirty = self._draft.is_dirty()

        self._undo_btn.setEnabled(self._history.can_undo)
        self._undo_btn.setToolTip(
            f"Undo {self._history.undo_description}" if self._history.can_undo else "Nothing to undo yet."
        )
        self._redo_btn.setEnabled(self._history.can_redo)
        self._redo_btn.setToolTip(
            f"Redo {self._history.redo_description}" if self._history.can_redo else "Nothing to redo."
        )

        self._save_btn.setEnabled(dirty)
        self._save_btn.setToolTip(
            "Save your schedule changes." if dirty else "No unsaved changes."
        )
        self._revert_btn.setEnabled(dirty)
        self._revert_btn.setVisible(dirty)
        self._revert_btn.setToolTip("Discard all unsaved schedule changes for this editing session.")

        if dirty:
            self._status_badge.setStyleSheet(_DIRTY_BADGE_STYLE)
            self._status_badge.setText("UNSAVED CHANGES")

        elif self._status_badge.text() != "SAVED ✓":
            self._status_badge.setText("")

    def _flash_saved_badge(self):
        self._status_badge.setStyleSheet(_SAVED_BADGE_STYLE)
        self._status_badge.setText("SAVED ✓")

        def _clear():
            if self._status_badge.text() == "SAVED ✓":
                self._status_badge.setText("")

        QTimer.singleShot(4000, _clear)

    # ── navigation ───────────────────────────────────────────────────

    def _back(self):
        if not self.confirm_leave():
            return
        if self._on_back is not None:
            self._on_back()

    def _shift_day(self, delta_days):
        # Draft changes are absolute-time anchored, so day navigation
        # with a dirty draft is safe: edits on other days stay in the
        # change list and reappear when navigating back.
        self._window_start += delta_days * 24 * 3600
        self._refresh_board()

    def _go_to_today(self):
        self._window_start = _floor_to_half_hour(time.time())
        self._refresh_board()

    # ── board rendering ──────────────────────────────────────────────

    def _refresh_board(self):
        """Rebuild the base snapshot from the live channels for the
        current window, then render the draft over it. Repeated calls are
        idempotent (set_base_lanes replaces the clone wholesale; changes
        are keyed by absolute time, never duplicated by a refresh).
        """
        if self.board is None:
            return
        window_end = self._window_start + _WINDOW_HOURS * 3600
        lanes = build_board_model(self._channel_rows, self._studio_channels_by_id, self._window_start, window_end)
        self._draft.set_base_lanes(lanes)
        self._render_draft(preserve_scroll=False)

    def _render_draft(self, preserve_scroll=True, reselect=None):
        """Render the draft's presentation lanes onto the board. Keeps
        scroll position by default (an edit shouldn't yank the board
        around) and optionally restores selection to `(channel_id, start)`
        -- or to the previously selected block when it still exists.
        """
        if self.board is None:
            self._update_toolbar_state()
            return
        window_end = self._window_start + _WINDOW_HOURS * 3600
        scroll = self.board.scroll_positions() if preserve_scroll else None

        lanes = self._draft.presentation_lanes(self._window_start, window_end)
        self._lanes_by_channel_id = {lane.channel_id: lane for lane in lanes}
        self.board.set_lanes(lanes, self._window_start, window_end)
        self.board.set_corner_text(_compact_date(self._window_start))

        if scroll is not None:
            self.board.set_scroll_positions(scroll)

        target = reselect
        if target is None and self._selected_block is not None:
            target = (self._selected_block.channel_id, self._selected_block.start)
        reselected = False
        if target is not None:
            reselected = self.board.select_block_at(target[0], target[1])
        if not reselected:
            self._selected_block = None
            self._update_next_up(None)
            self._update_channel_defaults(None)
            self._update_details(None, None)
            self._update_tools_for_selection()
        self._update_pending_changes(self._draft.describe_pending_changes(), self._undo_pending_change)
        self._update_toolbar_state()

    # ── selection ────────────────────────────────────────────────────

    def _on_program_selected(self, block):
        self._selected_block = block
        lane = self._lanes_by_channel_id.get(block.channel_id)
        self._update_details(block, lane)
        if lane is not None:
            self._update_next_up(lane)
            self._update_channel_defaults(self._summaries_by_id.get(block.channel_id))
        self._update_tools_for_selection()

    def _on_channel_selected(self, channel_id):
        self._selected_block = None
        lane = self._lanes_by_channel_id.get(channel_id)
        self._update_next_up(lane)
        self._update_channel_defaults(self._summaries_by_id.get(channel_id))
        self._update_details(None, lane)
        self._update_tools_for_selection()

    def _update_tools_for_selection(self):
        """Enable exactly the actions the current selection supports and
        explain the state in the tools card's hint line -- a disabled
        button always has its reason one line below it.
        """
        block = self._selected_block
        put_btn = self._tools["put_btn"]
        pull_btn = self._tools["pull_btn"]
        move_btn = self._tools["move_btn"]
        duplicate_btn = self._tools["duplicate_btn"]
        copy_btn = self._tools["copy_btn"]
        fill_btn = self._tools["fill_btn"]
        set_hint = self._tools["set_hint"]

        def _disable_all():
            put_btn.setEnabled(False)
            pull_btn.setEnabled(False)
            move_btn.setEnabled(False)
            duplicate_btn.setEnabled(False)
            copy_btn.setEnabled(False)
            fill_btn.setEnabled(False)

        if block is None:
            _disable_all()
            set_hint("Select a program to pull, move, duplicate, or copy it, or select open time to fill it.")
            return

        lock_reason = self._draft.lane_lock_reason(block.channel_id)
        if lock_reason:
            _disable_all()
            set_hint(lock_reason)
            return

        if block.media_type == "open":
            _disable_all()
            put_btn.setEnabled(True)
            fill_btn.setEnabled(True)
            set_hint(
                "Open time is selected — Put On Air lets you choose anything; "
                "Fill Open Time ranks media by how well it fits this gap."
            )
            return

        put_btn.setEnabled(False)
        fill_btn.setEnabled(False)
        validation = PullProgramCommand(block).validate(self._draft)
        pull_btn.setEnabled(validation.ok)
        # Move To…/Duplicate Here…/Copy to Another Day… each use a
        # placeholder same-time-ish destination purely to ask "can this
        # block be acted on at all" (protected/commercial/already-aired/
        # missing-media) -- the real destination time is only known once
        # the relevant dialog is open, so its own overlap check happens
        # later. All three share the exact same underlying validate()
        # shape (Move via MoveProgramCommand, Duplicate/Copy via
        # DuplicateProgramCommand), so a destination-overlap-only failure
        # means "still possible, just needs a different time" for all of
        # them alike.
        move_probe = MoveProgramCommand(block, block.channel_id, block.true_start + 60)
        move_probe_result = move_probe.validate(self._draft)
        move_ok = move_probe_result.ok or any(
            c["type"] == CONFLICT_OVERLAPS_DESTINATION for c in move_probe_result.conflicts
        )
        move_btn.setEnabled(move_ok)

        duplicate_probe = DuplicateProgramCommand(block, block.true_start + 60, kind="duplicate")
        duplicate_probe_result = duplicate_probe.validate(self._draft)
        duplicate_ok = duplicate_probe_result.ok or any(
            c["type"] == CONFLICT_OVERLAPS_DESTINATION for c in duplicate_probe_result.conflicts
        )
        duplicate_btn.setEnabled(duplicate_ok)
        # Copy to Another Day shares Duplicate's validate() shape exactly
        # (same-channel, different-date destinations aren't checked by
        # validate() at all -- only the dialog constrains which date is
        # offered), so the same probe result governs both buttons.
        copy_btn.setEnabled(duplicate_ok)

        if validation.ok:
            set_hint(f"Pull removes “{block.title}” from the draft lineup and leaves open time.")
        elif move_ok:
            set_hint(validation.reason + " You can still move, duplicate, or copy it to a different time.")
        else:
            set_hint(validation.reason)

    # ── drag-and-drop (Phase 3) ──────────────────────────────────────

    def _validate_drop_preview(self, block, channel_id, start):
        """The board's drop-preview callback (set via
        `self.board.set_drop_validator`) -- reuses MoveProgramCommand's
        own validate() so a drag preview can never disagree with what an
        actual drop would do. Returns (state, label) where state is
        "valid" | "conflict" | "invalid"; an empty label lets the board
        fall back to its own plain time-range text for a clean valid
        placement.
        """
        command = MoveProgramCommand(block, channel_id, start)
        result = command.validate(self._draft)
        if result.ok:
            return "valid", ""
        conflict = next((c for c in result.conflicts if c["type"] == CONFLICT_OVERLAPS_DESTINATION), None)
        if conflict is not None:
            return "conflict", conflict["message"]
        return "invalid", result.reason

    def _on_move_drop(self, source_block, destination_channel_id, destination_start):
        """A confirmed drop (board.py's move_drop signal) -- funnels
        through the exact same `_try_move` Move To… uses, so a drag and a
        dialog-driven move share one execution/conflict-resolution path.
        """
        self._try_move(source_block, destination_channel_id, destination_start)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.board is not None and self.board.is_dragging:
            self.board.cancel_drag()
            event.accept()
            return
        super().keyPressEvent(event)

    # ── commands ─────────────────────────────────────────────────────

    def _pull_clicked(self):
        block = self._selected_block
        if block is None:
            return
        command = PullProgramCommand(block)
        validation = command.validate(self._draft)
        if not validation.ok:
            self._show_info("Can't pull this program", validation.reason)
            return
        self._history.execute(command, self._draft)
        self._render_draft(reselect=(block.channel_id, block.start))

    def _put_on_air_clicked(self):
        block = self._selected_block
        if block is None or block.media_type != "open":
            return
        lane = self._lanes_by_channel_id.get(block.channel_id)
        if lane is None:
            return
        names_by_id = {cid: summary.name for cid, summary in self._summaries_by_id.items()}
        items = build_picker_catalog(self._studio_channels_by_id, names_by_id)
        if not items:
            self._show_info(
                "Nothing to schedule yet",
                "No catalog media is available to put on air. Load a catalog with playable files first.",
            )
            return
        picker = PutOnAirPickerDialog(
            items,
            lane.number,
            lane.name,
            block.true_start,
            max(0.0, block.true_end - block.true_start),
            recent_paths=self._recent_paths(),
            parent=self,
        )
        if picker.exec() != PutOnAirPickerDialog.Accepted:
            return
        item = picker.selected_item()
        if item:
            self._try_put_on_air(block, item, extend_over_following=False)

    def _try_put_on_air(self, slot_block, item, extend_over_following=False):
        media = {
            "path": item["path"],
            "title": item["title"],
            "duration": item["duration"],
            "media_type": item.get("media_type", "tv"),
        }
        command = PutOnAirCommand(
            slot_block.channel_id,
            slot_block.true_start,
            media,
            slot_end=slot_block.true_end,
            extend_over_following=extend_over_following,
        )
        validation = command.validate(self._draft)
        overlap = next((c for c in validation.conflicts if c["type"] == CONFLICT_OVERLAPS_FOLLOWING), None)
        if not validation.ok and overlap is not None:
            choice = self._ask_extend_conflict(overlap)
            if choice == "extend":
                self._try_put_on_air(slot_block, item, extend_over_following=True)
            elif choice == "choose":
                self._put_on_air_clicked()
            return
        if not validation.ok:
            self._show_info("Can't schedule this here", validation.reason)
            return
        self._history.execute(command, self._draft)
        lane = self._lanes_by_channel_id.get(slot_block.channel_id)
        self._record_recent_placement(
            item["path"], item["title"], item.get("media_type", "tv"), item["duration"],
            channel_name=lane.name if lane is not None else "",
        )
        self._render_draft(reselect=(slot_block.channel_id, slot_block.start))

    # ── recently scheduled (Phase 3.1) ────────────────────────────────

    def _recent_paths(self):
        """Paths of media recently placed into a lineup, newest first --
        the persisted history (recent_media.py) IS the session's own
        recency too, since every successful placement write-throughs
        immediately (see _record_recent_placement); there is no separate
        session-only list to keep in sync.
        """
        getter = getattr(self._studio_dialog, "_schedule_recent_media_get", None)
        if getter is None:
            return []
        data = getter() or {}
        return [item.get("path", "") for item in (data.get("items") or []) if item.get("path")]

    def _record_recent_placement(self, path, title, media_type, duration, channel_name=""):
        """Records one successful placement (Put On Air / Duplicate
        Here… / Copy to Another Day… / Fill Open Time) -- called only
        from the success path of each action, right after
        `self._history.execute(...)`, so a cancelled picker or a failed
        validation never reaches this. Silently a no-op when this
        workspace wasn't opened from a running MediaWave session (tests,
        or `_schedule_recent_media_record` otherwise unavailable) --
        recent history is a convenience, never schedule state.
        """
        recorder = getattr(self._studio_dialog, "_schedule_recent_media_record", None)
        if recorder is None or not path:
            return
        recorder(
            {
                "path": path,
                "title": title,
                "media_type": media_type,
                "duration": duration,
                "channel_name": channel_name,
            }
        )

    def _move_to_clicked(self):
        """The guided, non-drag reference workflow (Phase 3 spec section
        3) -- also the accessible alternative dragging must never be the
        only way to reach (section 15).
        """
        block = self._selected_block
        if block is None:
            return
        lane = self._lanes_by_channel_id.get(block.channel_id)
        if lane is None:
            return
        dialog = MoveToDialog(block, lane, parent=self)
        if dialog.exec() != MoveToDialog.Accepted:
            return
        self._try_move(block, block.channel_id, dialog.destination_start(), on_choose_another=self._move_to_clicked)

    def _try_move(self, source_block, destination_channel_id, destination_start, replace_blocks=None, on_choose_another=None):
        """The one path both Move To… and drag-and-drop funnel through --
        neither interaction mutates the draft directly; both end up here,
        which validates via the exact same MoveProgramCommand.validate()
        and, on a destination conflict, offers the exact same Choose
        Another Time / Replace Overlapping Program / Cancel resolution
        (Phase 3 spec section 9: "Move To… and drag use the same
        validation path").

        `on_choose_another`, if given, is called when the user picks
        "Choose Another Time" -- Move To… reopens its dialog; a drag drop
        passes None, since "try again" there just means dragging again,
        not popping a dialog after the gesture already ended.
        """
        command = MoveProgramCommand(source_block, destination_channel_id, destination_start, replace_blocks=replace_blocks)
        validation = command.validate(self._draft)
        overlap = next((c for c in validation.conflicts if c["type"] == CONFLICT_OVERLAPS_DESTINATION), None)
        if not validation.ok and overlap is not None:
            choice = self._ask_move_conflict(source_block, overlap)
            if choice == "replace":
                self._try_move(
                    source_block,
                    destination_channel_id,
                    destination_start,
                    replace_blocks=overlap["overlapping_blocks"],
                    on_choose_another=on_choose_another,
                )
            elif choice == "choose" and on_choose_another is not None:
                on_choose_another()
            return
        if not validation.ok:
            self._show_info("Can't move this program", validation.reason)
            return
        self._history.execute(command, self._draft)
        self._render_draft(reselect=(destination_channel_id, destination_start))

    def _ask_move_conflict(self, source_block, conflict):
        """The move-destination-overlap flow (Phase 3 spec section 5-6):
        explain exactly what would be overlapped/replaced in plain
        language, and offer only the supported resolutions. Replacing
        removes the overlapped block(s) from the draft -- fully undoable
        as part of the same one move command (commands.py). Returns
        "replace" | "choose" | "cancel".
        """
        overlapping = conflict.get("overlapping_blocks") or []
        if len(overlapping) == 1:
            detail = f"Replacing will pull “{overlapping[0].title}” from the lineup."
        else:
            names = ", ".join(f"“{block.title}”" for block in overlapping)
            detail = f"Replacing will pull {names} from the lineup."
        box = self._make_message_box(
            QMessageBox.Question,
            "This time is already scheduled",
            f"{conflict['message']}\n\nWhat should MediaWave do?\n\n{detail}",
        )
        choose_btn = box.addButton("Choose Another Time", QMessageBox.ActionRole)
        replace_btn = box.addButton("Replace Overlapping Program", QMessageBox.DestructiveRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is replace_btn:
            return "replace"
        if clicked is choose_btn:
            return "choose"
        return "cancel"

    # ── duplicate / copy to another day (Phase 3.1) ───────────────────

    def _duplicate_here_clicked(self):
        """Duplicate Here…: another airing of the selected program on the
        same channel and date -- the source program is never touched.
        """
        block = self._selected_block
        if block is None:
            return
        lane = self._lanes_by_channel_id.get(block.channel_id)
        if lane is None:
            return
        dialog = DuplicateHereDialog(block, lane, parent=self)
        if dialog.exec() != DuplicateHereDialog.Accepted:
            return
        self._try_duplicate(
            block, block.channel_id, dialog.destination_start(),
            kind="duplicate", on_choose_another=self._duplicate_here_clicked,
        )

    def _copy_to_day_clicked(self):
        """Copy to Another Day…: one airing on a different calendar date
        -- explicitly NOT a recurring rule (spec section 4). The
        underlying command is identical to Duplicate Here…'s; only the
        destination date (and the wording) differ.
        """
        block = self._selected_block
        if block is None:
            return
        lane = self._lanes_by_channel_id.get(block.channel_id)
        if lane is None:
            return
        dialog = CopyToAnotherDayDialog(block, lane, default_date_epoch=self._window_start + 24 * 3600, parent=self)
        if dialog.exec() != CopyToAnotherDayDialog.Accepted:
            return
        self._try_duplicate(
            block, block.channel_id, dialog.destination_start(),
            kind="copy", on_choose_another=self._copy_to_day_clicked,
        )

    def _try_duplicate(self, source_block, destination_channel_id, destination_start, replace_blocks=None, kind="duplicate", on_choose_another=None):
        """The one path both Duplicate Here… and Copy to Another Day…
        funnel through -- mirrors `_try_move`'s shape exactly (same
        validate/conflict-resolution/execute flow, same shared conflict
        dialog), since DuplicateProgramCommand backs both workflows and
        never removes the source.
        """
        command = DuplicateProgramCommand(
            source_block, destination_start, destination_channel_id, replace_blocks=replace_blocks, kind=kind,
        )
        validation = command.validate(self._draft)
        overlap = next((c for c in validation.conflicts if c["type"] == CONFLICT_OVERLAPS_DESTINATION), None)
        if not validation.ok and overlap is not None:
            choice = self._ask_move_conflict(source_block, overlap)
            if choice == "replace":
                self._try_duplicate(
                    source_block,
                    destination_channel_id,
                    destination_start,
                    replace_blocks=overlap["overlapping_blocks"],
                    kind=kind,
                    on_choose_another=on_choose_another,
                )
            elif choice == "choose" and on_choose_another is not None:
                on_choose_another()
            return
        if not validation.ok:
            verb_label = "duplicate" if kind == "duplicate" else "copy"
            self._show_info(f"Can't {verb_label} this program", validation.reason)
            return
        self._history.execute(command, self._draft)
        path = (source_block.raw_entries[0] or {}).get("path", "") if source_block.raw_entries else ""
        self._record_recent_placement(
            path, source_block.title, source_block.media_type or "tv",
            max(0.0, source_block.true_end - source_block.true_start),
            channel_name=self._lanes_by_channel_id.get(destination_channel_id).name
            if self._lanes_by_channel_id.get(destination_channel_id) is not None else "",
        )
        self._render_draft(reselect=(destination_channel_id, destination_start))

    # ── fill open time (Phase 3.1) ────────────────────────────────────

    def _fill_open_time_clicked(self):
        """A guided UI workflow over the existing Put On Air command
        (spec section 7) -- the ranked picker just chooses WHAT fills the
        gap; placement, conflict handling (including the longer-than-gap
        Extend/Choose Something Else/Cancel flow), and Open Time bookkeeping
        all go through the exact same `_try_put_on_air` Put On Air itself
        uses, so there is no second fill mutation path.
        """
        block = self._selected_block
        if block is None or block.media_type != "open":
            return
        lane = self._lanes_by_channel_id.get(block.channel_id)
        if lane is None:
            return
        names_by_id = {cid: summary.name for cid, summary in self._summaries_by_id.items()}
        items = build_picker_catalog(self._studio_channels_by_id, names_by_id)
        if not items:
            self._show_info(
                "Nothing to schedule yet",
                "No catalog media is available to put on air. Load a catalog with playable files first.",
            )
            return
        picker = FillOpenTimePickerDialog(
            items,
            lane.number,
            lane.name,
            block.true_start,
            max(0.0, block.true_end - block.true_start),
            recent_paths=self._recent_paths(),
            parent=self,
        )
        if picker.exec() != FillOpenTimePickerDialog.Accepted:
            return
        item = picker.selected_item()
        if item:
            self._try_put_on_air(block, item, extend_over_following=False)

    def _undo_clicked(self):
        command = self._history.undo(self._draft)
        if command is not None:
            self._render_draft(reselect=self._reselect_target_for(command, after_undo=True))

    def _undo_pending_change(self, change_id):
        """One Pending Changes row's "Undo This Change" action -- removes
        just that change via CommandHistory's safe replay-based rebuild
        (commands.py), leaving every other pending change untouched.
        """
        removed = self._history.remove_pending_change(change_id, self._draft)
        if removed is not None:
            self._render_draft(reselect=self._reselect_target_for(removed, after_undo=True))

    def _redo_clicked(self):
        command = self._history.redo(self._draft)
        if command is not None:
            self._render_draft(reselect=self._reselect_target_for(command, after_undo=False))

    def _reselect_target_for(self, command, after_undo):
        """Where selection should land after Undo/Redo of `command` --
        explicit for MoveProgramCommand/DuplicateProgramCommand, since a
        plain fallback to the stale `self._selected_block`'s (channel,
        start) would try to reselect at a location the action just
        vacated (Phase 3 spec section 13: selection follows the restored/
        moved block; Phase 3.1 extends the same idea to duplicate/copy --
        undo returns to the original, redo returns to the new airing).
        Every other command already reselects correctly via
        `_render_draft`'s own fallback (the block's location didn't
        change), so returning None there is deliberate, not an oversight.
        """
        if isinstance(command, (MoveProgramCommand, DuplicateProgramCommand)):
            if after_undo:
                return (command.source_channel_id, command.source_start)
            return (command.destination_channel_id, command.destination_start)
        return None

    # ── saved changes manager ────────────────────────────────────────

    def _open_saved_changes_manager(self):
        """Opens the Saved Changes manager for the currently viewed date
        (Phase 2.1 spec section 5) -- lets the user remove a previously
        SAVED override without touching schedule_overrides.json. Distinct
        from Pending Changes/Revert, which only ever act on the unsaved
        draft.
        """
        data_get = getattr(self._studio_dialog, "_schedule_overrides_data_get", None)
        remove_fn = getattr(self._studio_dialog, "_schedule_overrides_remove", None)
        if data_get is None or remove_fn is None:
            self._show_info(
                "Saved Changes isn't available",
                "This window wasn't opened from a running MediaWave session, so saved changes can't be reviewed here.",
            )
            return
        date_str = time.strftime("%Y-%m-%d", time.localtime(self._window_start))
        date_label = time.strftime("%A, %B %-d", time.localtime(self._window_start))
        channel_order = [
            (row.get("channel_id", ""), f"Ch {row.get('number', 0)} · {row.get('name', 'Channel')}")
            for row in self._channel_rows
        ]
        manager = SavedChangesManagerDialog(
            date_str,
            date_label,
            channel_order,
            data_get,
            remove_fn,
            on_changed=self._on_saved_changes_updated,
            parent=self,
        )
        manager.exec()

    def _on_saved_changes_updated(self):
        """A saved override was removed from another dialog -- refresh
        the board (and the guide cache upstream, already handled by
        remove_schedule_override_from_editor) so this workspace shows the
        restored/automatic programming immediately, without disturbing
        scroll position or requiring the user to close and reopen.
        """
        if self.board is None:
            return
        scroll = self.board.scroll_positions()
        self._refresh_board()
        self.board.set_scroll_positions(scroll)

    # ── revert / save ────────────────────────────────────────────────

    def _revert_clicked(self):
        if not self._draft.is_dirty():
            return
        box = self._make_message_box(
            QMessageBox.Question,
            "Revert draft?",
            "This discards every unsaved schedule change and restores the generated lineup.",
        )
        discard_btn = box.addButton("Discard Changes", QMessageBox.DestructiveRole)
        box.addButton("Keep Editing", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not discard_btn:
            return
        self._discard_draft()

    def _discard_draft(self):
        self._draft.clear_changes()
        self._history.clear()
        self._render_draft()

    def _save_clicked(self):
        """Serialize the draft, ask for a Save Review when there's more
        than one meaningful change (Phase 2.1 spec section 3 -- a single
        simple change stays a plain one-click save), then perform the
        save. Returns True when the save completed.

        "Meaningful change" is counted by Pending Changes ROWS, not raw
        override records -- a single Move produces two records (a pull +
        an add) but is exactly one user action, and should stay a
        one-click save like any other single edit (Phase 3).
        """
        if not self._draft.is_dirty():
            return True
        pending_rows = self._draft.describe_pending_changes()
        records = self._draft.overrides_for_save()
        if len(pending_rows) > 1 and not self._confirm_save_review(pending_rows):
            return False
        return self._perform_save(records)

    def _confirm_save_review(self, pending_rows):
        """The multi-change confirmation: a friendly bullet per pending
        row (the exact same rows Pending Changes already shows -- a move
        is one bullet, never separate pull/add lines). When every pending
        row lands on the same date, this stays exactly the single-date
        summary Phase 2.1 shipped; when Copy to Another Day has put
        changes on more than one date, the bullets are grouped under a
        date heading per date instead (Phase 3.1 spec section 13), and
        the title says how many days are affected. Either way, every
        bullet's own change is still explicitly one-date (a copy's own
        subline never implies recurrence). Returns True if the user chose
        to proceed.
        """
        distinct_dates = list(dict.fromkeys(row.get("date", "") for row in pending_rows))
        if len(distinct_dates) <= 1:
            date_label = pending_rows[0].get("date_label") or time.strftime("%A, %B %-d", time.localtime(self._window_start))
            bullets = "\n".join(f"•  {row['headline']} ({row['subline']})" for row in pending_rows)
            body = f"{bullets}\n\nThese changes apply to {date_label} only."
            title = f"Save {len(pending_rows)} lineup changes?"
        else:
            sections = []
            for date_key in distinct_dates:
                date_rows = [row for row in pending_rows if row.get("date", "") == date_key]
                heading = date_rows[0].get("date_label", date_key)
                bullets = "\n".join(f"•  {row['headline']} ({row['subline']})" for row in date_rows)
                sections.append(f"{heading}\n{bullets}")
            body = "\n\n".join(sections)
            title = f"Save {len(pending_rows)} lineup changes across {len(distinct_dates)} days?"
        box = self._make_message_box(QMessageBox.Question, title, body)
        save_btn = box.addButton("Save Schedule", QMessageBox.AcceptRole)
        box.addButton("Keep Editing", QMessageBox.RejectRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is save_btn

    def _perform_save(self, records):
        """Validate -> hand to the app's save pipeline -> mark clean. On
        failure the draft and Undo history are untouched.
        """
        save = getattr(self._studio_dialog, "_schedule_overrides_save", None)
        if save is None:
            self._show_info(
                "Saving isn't available",
                "This window wasn't opened from a running MediaWave session, so schedule changes can't be saved here.",
            )
            return False
        ok, error = save(records)
        if not ok:
            self._show_warning(
                "The schedule couldn't be saved",
                (error or "Something went wrong while writing the schedule file.")
                + "\n\nYour draft is untouched — nothing was lost, and you can try saving again.",
            )
            return False

        now = time.time()
        covers_now = any(record["start"] <= now < record["end"] for record in records)

        self._draft.clear_changes()
        self._history.clear()
        # Rebuild the base snapshot from the live channels: the saved
        # overrides are now part of the effective lineup, so the board
        # shows the same programming -- just no longer as draft edits.
        if self.board is not None:
            scroll = self.board.scroll_positions()
            self._refresh_board()
            self.board.set_scroll_positions(scroll)
        else:
            self._update_toolbar_state()

        self._flash_saved_badge()
        if covers_now:
            self._show_info(
                "Schedule saved",
                "A change affects what's airing right now. The current program keeps playing — "
                "your change takes effect after it ends.",
            )
        return True

    # ── leave / close ────────────────────────────────────────────────

    def has_unsaved_changes(self):
        return self._draft.is_dirty()

    def confirm_leave(self):
        """The unsaved-changes flow for Back and for closing the whole
        dialog: Save Changes / Discard Changes / Keep Editing. Returns
        True when leaving may proceed.
        """
        if not self._draft.is_dirty():
            return True
        box = self._make_message_box(
            QMessageBox.Question,
            "Unsaved schedule changes",
            "You have schedule edits that haven't been saved yet.",
        )
        save_btn = box.addButton("Save Changes", QMessageBox.AcceptRole)
        discard_btn = box.addButton("Discard Changes", QMessageBox.DestructiveRole)
        box.addButton("Keep Editing", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_btn:
            return self._save_clicked()
        if clicked is discard_btn:
            self._discard_draft()
            return True
        return False

    # ── message helpers ──────────────────────────────────────────────

    def _make_message_box(self, icon, title, text):
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        return box

    def _show_info(self, title, text):
        self._make_message_box(QMessageBox.Information, title, text).exec()

    def _show_warning(self, title, text):
        self._make_message_box(QMessageBox.Warning, title, text).exec()

    def _ask_extend_conflict(self, conflict):
        """The longer-than-slot flow (spec sections 10-11): explain the
        overrun in plain language and offer exactly the supported
        choices. Extending masks the overlapped part of the following
        program (it's joined in progress afterward) -- nothing is
        silently truncated or auto-moved.
        Returns "extend" | "choose" | "cancel".
        """
        box = self._make_message_box(
            QMessageBox.Question,
            "It runs longer than the open time",
            conflict["message"]
            + f"\n\nExtend into it, and “{conflict['following_title']}” will already be in progress "
            "when it's joined afterward.",
        )
        extend_btn = box.addButton("Extend Into Following Time", QMessageBox.AcceptRole)
        choose_btn = box.addButton("Choose Something Else", QMessageBox.ActionRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is extend_btn:
            return "extend"
        if clicked is choose_btn:
            return "choose"
        return "cancel"


def _empty_state_label(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {_SUBTITLE_COLOR}; font-size: 12px; background: transparent;")
    return label


def build_schedule_editor_tab(studio_dialog, on_back=None):
    """Builds the Schedule Editor as an embeddable Advanced Configuration
    workspace. Returns `(workspace, footer)` -- the same shape
    `channel_studio.build_channel_studio_tab` returns, so
    `AdvancedConfigDialog` can add both to its mode/footer stacks the
    identical way it already does for Channel Studio. `on_back`, if given,
    is called when the workspace's own top-toolbar "Back" button is
    clicked (after the unsaved-changes flow allows it).

    The footer is the workspace's own Selected Program inspector
    (utility_panels.build_selected_program_footer): the footer stack
    reserves a constant-height band at the bottom of the dialog either way
    (see the plain-QStackedWidget comment where `_footer_stack` is built in
    channelsurfer2000.py), so this mode fills that band with the selection
    details instead of leaving it dead.
    """
    workspace = ScheduleEditorWorkspace(studio_dialog, on_back=on_back)
    return workspace, workspace._details_footer

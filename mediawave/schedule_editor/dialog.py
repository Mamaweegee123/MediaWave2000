"""ScheduleEditorDialog: Phase 1's read-only programming board.

Opened from Channel Studio's "Open Schedule Editor" action card
(mediawave/channel_studio/channel_studio_pages.py), constructed from the
same `AdvancedConfigDialog` instance (`studio_dialog`) Channel Studio itself
already holds a reference to -- exactly like `ChannelSetupDialog` already
is. Reads `studio_dialog._studio_channels_by_id`, `.catalog_channel_infos`,
`.catalog_channel_settings`, `._channel_logo_lookup`, `.commercials_settings`
the same way `_open_channel` in channel_studio_pages.py does. Never writes
to any of them, `schedule_state.json`, or `app_settings` -- there is no
mutation path anywhere in this dialog this phase.
"""

import time

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mediawave.channel_studio import channel_actions
from mediawave.channel_studio import companion_adapter
from mediawave.channel_studio.channel_studio_adapter import build_channel_studio_summaries
from mediawave.channel_studio.channel_studio_model import ChannelStudioSummary
from mediawave.studio.action_bar import build_action_bar
from mediawave.studio.cards import build_empty_state_card
from mediawave.studio.spacing import OUTER_MARGIN
from mediawave.studio.styles import build_scroll_area
from mediawave.studio.workspace import build_workspace

from .board import ProgrammingBoard
from .schedule_model import build_board_model, sort_channel_rows
from .utility_panels import build_channel_defaults_card, build_details_strip, build_next_up_card, build_quick_actions_card

_WINDOW_HOURS = 4
_RIGHT_COLUMN_WIDTH = 300

_TOP_BAR_BG = "rgba(9, 11, 27, 255)"
_TOP_BAR_BORDER = "rgba(42, 54, 128, 255)"
_TITLE_COLOR = "rgba(210, 222, 252, 255)"
_SUBTITLE_COLOR = "rgba(138, 158, 212, 220)"

_DISABLED_TOOLTIP = "Editing arrives in the next phase."


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
    the exact same read-only data channel Studio already shows.
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


class ScheduleEditorDialog(QDialog):
    def __init__(self, studio_dialog, parent=None):
        super().__init__(parent)
        self._studio_dialog = studio_dialog
        self.setWindowTitle("Schedule Editor")
        self.resize(1440, 780)
        self.setMinimumSize(1080, 620)

        self._channel_rows, self._summaries_by_id = _build_channel_rows(studio_dialog)
        self._studio_channels_by_id = getattr(studio_dialog, "_studio_channels_by_id", None) or {}
        self._lanes_by_channel_id = {}
        self._window_start = _floor_to_half_hour(time.time())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._top_bar = self._build_top_bar()
        outer.addWidget(self._top_bar)

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
            action_bar, action_buttons = build_action_bar(["back"])
            action_buttons["back"].clicked.connect(self.accept)
            workspace = build_workspace(wrap, action_bar, sidebar=None)
            outer.addWidget(workspace, 1)
            return

        self.board = ProgrammingBoard()
        self.board.program_selected.connect(self._on_program_selected)
        self.board.channel_selected.connect(self._on_channel_selected)

        self._quick_actions_card = build_quick_actions_card()
        self._next_up_card, self._update_next_up = build_next_up_card()
        self._channel_defaults_card, self._update_channel_defaults = build_channel_defaults_card()
        self._details_strip, self._update_details = build_details_strip()

        right_column = QWidget()
        right_column.setFixedWidth(_RIGHT_COLUMN_WIDTH)
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(self._quick_actions_card)
        right_layout.addWidget(self._next_up_card, 1)
        right_layout.addWidget(self._channel_defaults_card, 1)
        right_scroll = build_scroll_area(right_column)
        right_scroll.setFixedWidth(_RIGHT_COLUMN_WIDTH + 4)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(12)
        content_row.addWidget(self.board, 1)
        content_row.addWidget(right_scroll)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(*OUTER_MARGIN)
        content_layout.setSpacing(12)
        content_layout.addLayout(content_row, 1)
        content_layout.addWidget(self._details_strip)

        action_bar, action_buttons = build_action_bar(["back"])
        action_buttons["back"].clicked.connect(self.accept)
        workspace = build_workspace(content, action_bar, sidebar=None)
        outer.addWidget(workspace, 1)

        self._refresh_board()

    def _build_top_bar(self):
        bar = QWidget()
        bar.setObjectName("scheduleTopBar")
        bar.setStyleSheet(
            f"QWidget#scheduleTopBar {{ background: {_TOP_BAR_BG}; border-bottom: 1px solid {_TOP_BAR_BORDER}; }}"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(10)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("📅  Schedule Editor")
        title_lbl.setStyleSheet(f"color: {_TITLE_COLOR}; font-size: 18px; font-weight: 700; background: transparent;")
        title_col.addWidget(title_lbl)
        self._date_lbl = QLabel()
        self._date_lbl.setStyleSheet(f"color: {_SUBTITLE_COLOR}; font-size: 11px; background: transparent;")
        title_col.addWidget(self._date_lbl)
        layout.addLayout(title_col)

        layout.addStretch(1)

        prev_btn = QPushButton("‹")
        prev_btn.setFixedWidth(32)
        prev_btn.clicked.connect(lambda: self._shift_day(-1))
        layout.addWidget(prev_btn)

        today_btn = QPushButton("Today")
        today_btn.clicked.connect(self._go_to_today)
        layout.addWidget(today_btn)

        next_btn = QPushButton("›")
        next_btn.setFixedWidth(32)
        next_btn.clicked.connect(lambda: self._shift_day(1))
        layout.addWidget(next_btn)

        layout.addSpacing(20)

        for label in ("Undo", "Redo", "Save Schedule"):
            btn = QPushButton(label)
            btn.setEnabled(False)
            btn.setToolTip(_DISABLED_TOOLTIP)
            layout.addWidget(btn)

        self._update_date_label()
        return bar

    def _update_date_label(self):
        window_end = self._window_start + _WINDOW_HOURS * 3600
        day_label = time.strftime("%A, %B %-d", time.localtime(self._window_start))
        start_label = time.strftime("%-I:%M %p", time.localtime(self._window_start))
        end_label = time.strftime("%-I:%M %p", time.localtime(window_end))
        self._date_lbl.setText(f"{day_label}  ·  {start_label} – {end_label}")

    def _shift_day(self, delta_days):
        self._window_start += delta_days * 24 * 3600
        self._update_date_label()
        self._refresh_board()

    def _go_to_today(self):
        self._window_start = _floor_to_half_hour(time.time())
        self._update_date_label()
        self._refresh_board()
        if hasattr(self, "board"):
            self.board.scroll_to_now()

    def _refresh_board(self):
        window_end = self._window_start + _WINDOW_HOURS * 3600
        lanes = build_board_model(self._channel_rows, self._studio_channels_by_id, self._window_start, window_end)
        self._lanes_by_channel_id = {lane.channel_id: lane for lane in lanes}
        self.board.set_lanes(lanes, self._window_start, window_end)
        self._update_next_up(None)
        self._update_channel_defaults(None)
        self._update_details(None, None)

    def _on_program_selected(self, block):
        lane = self._lanes_by_channel_id.get(block.channel_id)
        self._update_details(block, lane)
        if lane is not None:
            self._update_next_up(lane)
            self._update_channel_defaults(self._summaries_by_id.get(block.channel_id))

    def _on_channel_selected(self, channel_id):
        lane = self._lanes_by_channel_id.get(channel_id)
        self._update_next_up(lane)
        self._update_channel_defaults(self._summaries_by_id.get(channel_id))
        self._update_details(None, lane)


def _empty_state_label(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {_SUBTITLE_COLOR}; font-size: 12px; background: transparent;")
    return label

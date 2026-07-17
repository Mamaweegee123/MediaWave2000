"""ScheduleEditorWorkspace: the read-only programming board.

A first-class Advanced Configuration workspace (its own left-sidebar nav
item, `AdvancedConfigDialog`'s `_enter_schedule_editor_mode` /
`build_schedule_editor_tab`, channelsurfer2000.py) rather than something
buried inside Channel Studio -- `build_schedule_editor_tab(studio_dialog,
on_back=...)` returns `(workspace, footer)` the exact same shape
`channel_studio.build_channel_studio_tab` does, so `AdvancedConfigDialog`
can add it to its mode/footer stacks identically. Channel Studio's own
"Open Schedule Editor" action card still exists as a contextual shortcut
into this same workspace (`dialog._enter_schedule_editor_mode()`), not a
separate implementation.

Constructed from the same `AdvancedConfigDialog` instance (`studio_dialog`)
Channel Studio itself already holds a reference to -- exactly like
`ChannelSetupDialog` already is. Reads `studio_dialog._studio_channels_by_id`,
`.catalog_channel_infos`, `.catalog_channel_settings`, `._channel_logo_lookup`,
`.commercials_settings` the same way `_open_channel` in
channel_studio_pages.py does. Never writes to any of them,
`schedule_state.json`, or `app_settings` -- there is no mutation path
anywhere in this workspace this phase.
"""

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
from mediawave.studio.cards import build_empty_state_card
from mediawave.studio.spacing import OUTER_MARGIN
from mediawave.studio.styles import build_scroll_area

from .board import ProgrammingBoard
from .program_block import build_category_legend
from .schedule_model import build_board_model, sort_channel_rows
from .utility_panels import (
    build_channel_defaults_card,
    build_editing_tools_card,
    build_next_up_card,
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

        self._editing_tools_card = build_editing_tools_card()
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
        right_layout.addWidget(self._next_up_card, 1)
        right_layout.addWidget(self._channel_defaults_card, 1)
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

    def _back(self):
        if self._on_back is not None:
            self._on_back()

    def _build_top_bar(self):
        """One compact row: Back on the far left, day navigation next to
        it, Undo/Redo/Save right-aligned -- no page title, the guide
        itself (and the window title, one level up) already say what this
        is. The category legend lives under the guide board (see
        __init__'s guide column), not up here.
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
        back_btn.clicked.connect(self._back)
        row.addWidget(back_btn)

        row.addSpacing(10)

        prev_btn = QPushButton("‹")
        prev_btn.setFixedWidth(32)
        prev_btn.clicked.connect(lambda: self._shift_day(-1))
        row.addWidget(prev_btn)

        today_btn = QPushButton("Today")
        today_btn.clicked.connect(self._go_to_today)
        row.addWidget(today_btn)

        next_btn = QPushButton("›")
        next_btn.setFixedWidth(32)
        next_btn.clicked.connect(lambda: self._shift_day(1))
        row.addWidget(next_btn)

        row.addStretch(1)

        for label in ("Undo", "Redo", "Save Schedule"):
            btn = QPushButton(label)
            btn.setEnabled(False)
            row.addWidget(btn)

        return bar

    def _shift_day(self, delta_days):
        self._window_start += delta_days * 24 * 3600
        self._refresh_board()

    def _go_to_today(self):
        self._window_start = _floor_to_half_hour(time.time())
        self._refresh_board()

    def _refresh_board(self):
        window_end = self._window_start + _WINDOW_HOURS * 3600
        lanes = build_board_model(self._channel_rows, self._studio_channels_by_id, self._window_start, window_end)
        self._lanes_by_channel_id = {lane.channel_id: lane for lane in lanes}
        self.board.set_lanes(lanes, self._window_start, window_end)
        self.board.set_corner_text(_compact_date(self._window_start))
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


def build_schedule_editor_tab(studio_dialog, on_back=None):
    """Builds the Schedule Editor as an embeddable Advanced Configuration
    workspace. Returns `(workspace, footer)` -- the same shape
    `channel_studio.build_channel_studio_tab` returns, so
    `AdvancedConfigDialog` can add both to its mode/footer stacks the
    identical way it already does for Channel Studio. `on_back`, if given,
    is called when the workspace's own top-toolbar "Back" button is
    clicked.

    The footer is the workspace's own Selected Program inspector
    (utility_panels.build_selected_program_footer): the footer stack
    reserves a constant-height band at the bottom of the dialog either way
    (see the plain-QStackedWidget comment where `_footer_stack` is built in
    channelsurfer2000.py), so this mode fills that band with the selection
    details instead of leaving it dead.
    """
    workspace = ScheduleEditorWorkspace(studio_dialog, on_back=on_back)
    return workspace, workspace._details_footer

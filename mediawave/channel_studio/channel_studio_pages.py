"""Channel Studio (Preview): Choose Channel.

The only top-level page in Channel Studio. Picking a channel opens its
own five-tab view (see channel_studio_cards.py) — there is nothing else
to navigate to from here. Aside from a read-only list of existing
channel names/numbers/logos and the small preview state in
studio_state.py (grid display order), no scheduling, library, or
settings data is read or written from this page.

No hero/featured card: every channel gets exactly one tile, in the
regular grid. studio_state.py's last-edited-channel helpers still exist
for backward compatibility with any state file written by an older
build, but nothing here calls them anymore.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from . import channel_actions
from . import companion_adapter
from .channel_setup import ChannelSetupDialog
from .channel_studio_adapter import build_channel_studio_summaries, build_tonight_schedules
from .channel_studio_dialogs import show_preview_dialog
from .channel_studio_header import build_channel_studio_header
from .channel_studio_model import ChannelStudioSummary
from .channel_studio_widgets import build_channel_studio_footer, build_empty_state
from .channel_card import build_dashboard_channel_card
from .draggable_grid import DraggableGrid
from .reorder import apply_saved_order
from .studio_state import load_channel_order, save_channel_order
from .studio_styles import style_setup_button

_COMPANION_TYPE_BY_ID = {cid: ctype for ctype, cid in companion_adapter.COMPANION_CHANNEL_IDS.items()}

# Matches channel_setup.ChannelSetupDialog's own section order
# (Overview, Logo, Commercials, Programming, Advanced) -- "Add Channel
# Logo" should land on Logo, not wherever the *old* five-tab mock
# dialog's Identity tab used to be.
_LOGO_TAB_INDEX = 1

_REORDER_HINT_TEXT = "Drag channels to rearrange them."
_REORDER_BUTTON_IDLE = "⇅  Reorder Channels"
_REORDER_BUTTON_ACTIVE = "✓  Done Reordering"


def _preview(dialog, title, description):
    show_preview_dialog(dialog, title, description)


def _drafts_path(dialog):
    return getattr(dialog, "_channel_studio_drafts_file", None)


def _state_path(dialog):
    return getattr(dialog, "_channel_studio_state_file", None)


def _channel_enabled(channel_id, catalog_channel_settings):
    """Read-only lookup of the channel's real enabled state (the same
    setting My Catalog's Enable/Disable All controls) so the dashboard's
    preview-only checkbox at least starts in the right position.
    """
    settings = catalog_channel_settings if isinstance(catalog_channel_settings, dict) else {}
    row = settings.get(channel_id, {})
    if not isinstance(row, dict):
        return True
    return bool(row.get("enabled", True))


def _build_reorder_hint():
    label = QLabel(_REORDER_HINT_TEXT)
    label.setObjectName("sectionNote")
    return label


def _channel_info_for(summary, number=None):
    return {
        "id": summary.channel_id,
        "name": summary.name,
        "default_number": summary.number if number is None else number,
    }


class _RefreshOnShowWidget(QWidget):
    """Channel Studio's own settings edits already trigger a rebuild (see
    _toggle_local_enabled/_toggle_companion_enabled/_toggle_reorder in
    build_channel_studio_content), but an edit made in a SIBLING tab —
    the Companion Channels tab's own channel-number spinbox, or a My
    Catalog row — has no way to reach into an already-built Channel
    Studio grid to tell it to refresh. Rebuilding on every showEvent
    (i.e. every time the user switches into Channel Studio's mode, not
    just the first time) closes that gap without Channel Studio needing
    to know anything about which other tab might have changed
    something, and without any changes to channelsurfer2000.py's own
    navigation code. `on_show` is set by the caller once its rebuild
    functions exist; a callable is expected but a missing/None one is a
    safe no-op (relevant only during this widget's own construction,
    before the caller has anything to assign yet).
    """

    def __init__(self):
        super().__init__()
        self.on_show = None

    def showEvent(self, event):
        super().showEvent(event)
        if self.on_show is not None:
            self.on_show()


def build_channel_studio_content(dialog):
    """Build the Choose Channel page: the scrollable content (header,
    grid) and its persistent footer, together — not as two
    independent builds — so the footer's Reorder Channels button can
    share reorder-mode state with the grid it toggles. Returns
    `(content, footer)`; see channel_studio.py for how callers place
    `footer` outside the scrollable area.
    """
    content = _RefreshOnShowWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(16)

    infos = list(getattr(dialog, "catalog_channel_infos", None) or [])
    # Companion channels (weatherstar/radiowave/youtube) get their own
    # dedicated pipeline below (companion_adapter + channel_actions,
    # reading live Companion Channels tab widgets) so their cards show
    # real type-specific status instead of generic folder-channel
    # labels -- excluded here so they don't also render as a second,
    # wrong-looking tile through the local/folder pipeline. Excluding
    # by companion type name (not by keeping only "media") matters: a
    # local channel can legitimately show up as channel_type "missing"
    # here too -- e.g. before self.channels has been populated yet this
    # session, current_catalog_channel_infos() falls back to building
    # entries from catalog_channel_settings alone -- and those still
    # belong in the local/folder pipeline, not dropped.
    local_infos = [
        info for info in infos if info.get("channel_type", "media") not in companion_adapter.COMPANION_TYPES
    ]
    state_path = _state_path(dialog)
    catalog_channel_settings = getattr(dialog, "catalog_channel_settings", None)

    reorder_hint_container = QWidget()
    reorder_hint_layout = QVBoxLayout(reorder_hint_container)
    reorder_hint_layout.setContentsMargins(0, 0, 0, 0)
    reorder_hint_layout.setSpacing(0)

    grid_container = QWidget()
    grid_layout = QVBoxLayout(grid_container)
    grid_layout.setContentsMargins(0, 0, 0, 0)
    grid_layout.setSpacing(0)

    summaries_by_id = {}
    schedules_by_id = {}

    if local_infos:
        summaries = build_channel_studio_summaries(
            local_infos,
            shows_lookup=getattr(dialog, "_channel_shows_lookup", None),
            catalog_channel_settings=catalog_channel_settings,
            commercials_config=getattr(dialog, "commercials_settings", None),
            airing_rules_config=getattr(dialog, "_airing_rules_config", None),
            logo_lookup=getattr(dialog, "_channel_logo_lookup", None),
        )
        summaries_by_id = {summary.channel_id: summary for summary in summaries}
        channels_by_id = getattr(dialog, "_studio_channels_by_id", None) or {}
        schedules = build_tonight_schedules(local_infos, channels_by_id=channels_by_id)
        schedules_by_id = {schedule.channel_id: schedule for schedule in schedules}
        number_sorted = sorted(summaries, key=lambda s: s.number)
    else:
        number_sorted = []

    current_filter = {"text": ""}
    reorder_state = {"active": False}
    grid_ref = {"widget": None}

    def _clear(layout_obj):
        while layout_obj.count():
            item = layout_obj.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _display_order():
        """Channel-number order, reshuffled by any saved Channel Studio
        display order (see reorder.apply_saved_order) — this never
        touches real channel numbers, scheduling, or playback order.
        """
        ids = [s.channel_id for s in number_sorted]
        ordered_ids = apply_saved_order(ids, load_channel_order(state_path))
        by_id = {s.channel_id: s for s in number_sorted}
        return [by_id[cid] for cid in ordered_ids if cid in by_id]

    def _local_enabled(channel_id):
        """Real enabled state for a local folder channel: prefers the
        live My Catalog row (so an edit made either here or in My
        Catalog itself, earlier in this same dialog session, is always
        reflected), falling back to the settings snapshot the dialog
        was opened with when no row exists yet.
        """
        live = channel_actions.local_channel_enabled_from_dialog(dialog, channel_id)
        if live is not None:
            return live
        return _channel_enabled(channel_id, catalog_channel_settings)

    def _companion_summary_objects():
        """Enabled companions only, read live off the Companion Channels
        tab's own widgets every time this is called so enable/disable
        and reorder changes made in Channel Studio (or in the Companion
        Channels tab itself) show up immediately.
        """
        snapshot = channel_actions.companion_snapshot_from_dialog(dialog)
        status = channel_actions.companion_status_from_dialog(dialog)
        return [
            ChannelStudioSummary(**fields)
            for fields in companion_adapter.companion_summaries(snapshot, status)
        ]

    def _toggle_local_enabled(channel_id, checked):
        channel_actions.set_local_channel_enabled(dialog, channel_id, checked)
        _rebuild_grid(current_filter["text"])

    def _toggle_companion_enabled(companion_type, checked):
        channel_actions.set_companion_enabled_on_dialog(dialog, companion_type, checked)
        _rebuild_grid(current_filter["text"])

    def _summary_for(channel_id):
        """Local summaries are already indexed; a companion summary is
        built fresh (live) only when actually needed, since it's not
        worth rebuilding all three companions' live status on every
        grid refresh just so Setup could open on one of them.
        """
        if channel_id in summaries_by_id:
            return summaries_by_id[channel_id]
        if channel_id in _COMPANION_TYPE_BY_ID:
            for summary in _companion_summary_objects():
                if summary.channel_id == channel_id:
                    return summary
        return None

    def _open_channel(channel_info, initial_tab=0):
        channel_id = channel_info.get("id", "")
        summary = _summary_for(channel_id)
        schedule = schedules_by_id.get(channel_id)
        ChannelSetupDialog(
            channel_info,
            summary=summary,
            schedule=schedule,
            parent=dialog,
            studio_dialog=dialog,
            drafts_path=_drafts_path(dialog),
            initial_tab=initial_tab,
        ).exec()

    def _open_logo(channel_info):
        _open_channel(channel_info, initial_tab=_LOGO_TAB_INDEX)

    def _open_from_setup(channel_info):
        """The Setup button's handler: opens the channel's detail
        screen, then refreshes the grid once it closes (a Setup edit
        can change what a card shows -- logo, commercial status,
        enabled state, ...).
        """
        _open_channel(channel_info, initial_tab=0)
        _rebuild_grid(current_filter["text"])

    def _rebuild_grid(filter_text=""):
        current_filter["text"] = filter_text or ""
        if grid_ref["widget"] is not None:
            # Defensive: if a drag was somehow still active when the grid
            # is being torn down, cancel it first so its floating overlay
            # (parented to the window, not to the grid, so it can float
            # above the QScrollArea without being clipped) doesn't leak.
            grid_ref["widget"].cancel_drag()
        _clear(grid_layout)
        grid_ref["widget"] = None

        ordered = _display_order()
        companions = _companion_summary_objects()

        if not ordered and not companions:
            grid_layout.addWidget(
                build_empty_state(
                    "No channels yet. Once you create or import one, it'll show up here "
                    "as a card you can open."
                )
            )
            return

        if reorder_state["active"]:
            # Reorder mode always shows every channel, unfiltered — dragging
            # a partially-filtered view would make "where did the rest go"
            # confusing.
            visible_local = ordered
            visible_companions = companions
        else:
            needle = current_filter["text"].strip().lower()
            visible_local = [s for s in ordered if needle in s.name.lower()] if needle else ordered
            visible_companions = [c for c in companions if needle in c.name.lower()] if needle else companions
            if not visible_local and not visible_companions:
                grid_layout.addWidget(build_empty_state(f'No channels match "{filter_text}".'))
                return

        entries = []
        for summary in visible_local:
            number = channel_actions.card_display_number(dialog, summary)
            channel_info = _channel_info_for(summary, number)
            card = build_dashboard_channel_card(
                summary,
                schedules_by_id.get(summary.channel_id),
                on_open=_open_from_setup,
                on_set_logo=lambda checked=False, info=channel_info: _open_logo(info),
                enabled=_local_enabled(summary.channel_id),
                on_toggle_enabled=lambda checked, cid=summary.channel_id: _toggle_local_enabled(cid, checked),
                commercials_status=channel_actions.card_commercials_status(dialog, summary.name),
                display_number=number,
            )
            entries.append((summary.channel_id, card))
        for summary in visible_companions:
            number = channel_actions.card_display_number(dialog, summary)
            channel_info = _channel_info_for(summary, number)
            card = build_dashboard_channel_card(
                summary,
                None,
                on_open=_open_from_setup,
                on_set_logo=lambda checked=False, info=channel_info: _open_logo(info),
                enabled=True,
                on_toggle_enabled=lambda checked, ct=summary.channel_type: _toggle_companion_enabled(ct, checked),
                on_remove=lambda ct=summary.channel_type: _toggle_companion_enabled(ct, False),
                display_number=number,
            )
            entries.append((summary.channel_id, card))

        grid = DraggableGrid(entries)
        grid.set_reorder_mode(reorder_state["active"])
        grid_ref["widget"] = grid
        grid_layout.addWidget(grid)

    def _toggle_reorder(checked=False):
        if reorder_state["active"]:
            # Exiting reorder mode: persist wherever the grid ended up,
            # and finalize real channel numbers to match -- both pools
            # redistribute only the numbers they already occupy (see
            # channel_actions.resequence_local_channels_on_dialog /
            # companion_adapter.resequence_companion_numbers), so a
            # local channel can never collide with or renumber a
            # companion, or vice versa. While dragging, numbers are left
            # alone -- only Done Reordering commits them.
            if grid_ref["widget"] is not None:
                final_order = grid_ref["widget"].current_order()
                save_channel_order(state_path, final_order)
                companion_order = [
                    _COMPANION_TYPE_BY_ID[cid] for cid in final_order if cid in _COMPANION_TYPE_BY_ID
                ]
                if len(companion_order) >= 2:
                    channel_actions.resequence_companions_on_dialog(dialog, companion_order)
                local_order = [cid for cid in final_order if cid in summaries_by_id]
                if len(local_order) >= 2:
                    channel_actions.resequence_local_channels_on_dialog(dialog, local_order)
            reorder_state["active"] = False
        else:
            reorder_state["active"] = True

        if reorder_state["active"]:
            reorder_btn.setText(_REORDER_BUTTON_ACTIVE)
            style_setup_button(reorder_btn)
        else:
            reorder_btn.setText(_REORDER_BUTTON_IDLE)
            reorder_btn.setStyleSheet("")

        _clear(reorder_hint_layout)
        if reorder_state["active"]:
            reorder_hint_layout.addWidget(_build_reorder_hint())

        _rebuild_grid(current_filter["text"])

    header = build_channel_studio_header(
        on_create=lambda: _preview(dialog, "Create Channel", "Creating a new channel isn't wired up yet — this is a preview."),
        on_filter=lambda: _preview(dialog, "Filters", "Filtering your channel list isn't wired up yet — this is a preview."),
        on_search_changed=_rebuild_grid,
    )
    layout.addWidget(header)
    layout.addWidget(reorder_hint_container)
    layout.addWidget(grid_container)

    _rebuild_grid()
    layout.addStretch(1)

    footer, reorder_btn = build_channel_studio_footer(
        total_count=len(infos),
        on_reorder=_toggle_reorder,
    )

    content.on_show = lambda: _rebuild_grid(current_filter["text"])

    return content, footer

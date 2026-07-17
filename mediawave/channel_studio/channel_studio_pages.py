"""Channel Studio (Preview): Choose Channel.

The only top-level page in Channel Studio. Picking a channel opens its
own five-tab view (see channel_studio_cards.py) — there is nothing else
to navigate to from here. Aside from a read-only list of existing
channel names/numbers/logos, no scheduling, library, or settings data
is read or written from this page.

No hero/featured card: every channel gets exactly one tile, in the
regular grid. studio_state.py's last-edited-channel helpers still exist
for backward compatibility with any state file written by an older
build, but nothing here calls them anymore.

The grid has exactly one ordering rule: real channel number, ascending,
local and companion channels together (see _sorted_summaries below).
There is no separate display-order state and no drag-and-drop —
channel number IS the lineup order, and manual renumbering (Overview's
inline number editor) is the only way to move a channel's position.
"""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from . import channel_actions
from . import companion_adapter
from .channel_setup import ChannelSetupDialog
from .channel_studio_adapter import build_channel_studio_summaries, build_tonight_schedules
from .channel_studio_dialogs import show_preview_dialog
from .channel_studio_header import build_channel_studio_header
from .channel_studio_model import ChannelStudioSummary
from .channel_studio_widgets import build_channel_studio_footer, build_empty_state
from .channel_card import build_dashboard_channel_card
from .channel_grid import build_channel_grid

_COMPANION_TYPE_BY_ID = {cid: ctype for ctype, cid in companion_adapter.COMPANION_CHANNEL_IDS.items()}


def _preview(dialog, title, description):
    show_preview_dialog(dialog, title, description)


def _drafts_path(dialog):
    return getattr(dialog, "_channel_studio_drafts_file", None)


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


def _channel_info_for(summary, number=None):
    return {
        "id": summary.channel_id,
        "name": summary.name,
        "default_number": summary.number if number is None else number,
    }


class _RefreshOnShowWidget(QWidget):
    """Channel Studio's own settings edits already trigger a rebuild (see
    _toggle_local_enabled/_toggle_companion_enabled in
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
    grid) and its persistent footer, together. Returns `(content,
    footer)`; see channel_studio.py for how callers place `footer`
    outside the scrollable area.
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
    catalog_channel_settings = getattr(dialog, "catalog_channel_settings", None)

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

    current_filter = {"text": ""}

    def _clear(layout_obj):
        while layout_obj.count():
            item = layout_obj.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

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
        tab's own widgets every time this is called so an enable/disable
        change made in Channel Studio (or in the Companion Channels tab
        itself) shows up immediately.
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

    def _open_channel(channel_info, initial_page=None, open_logo_studio=False):
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
            initial_page=initial_page,
            open_logo_studio_on_show=open_logo_studio,
        ).exec()

    def _open_logo(channel_info):
        # Logo Studio isn't a Setup page anymore (see logo_studio_dialog.py)
        # -- opens Setup and immediately opens Logo Studio on top of it, so
        # this still lands the user straight in logo editing, same intent
        # as the old Logo-tab shortcut.
        _open_channel(channel_info, open_logo_studio=True)

    def _open_from_setup(channel_info):
        """The Setup button's handler: opens the channel's detail
        screen, then refreshes the grid once it closes (a Setup edit
        can change what a card shows -- logo, commercial status,
        enabled state, ...).
        """
        _open_channel(channel_info)
        _rebuild_grid(current_filter["text"])

    def _sorted_summaries():
        """Every channel -- local and companion together -- in Channel
        Studio's one and only lineup order: real channel number
        ascending, name/id as a stable tie-break (see this module's
        docstring). Reads each channel's LIVE number (card_display_
        number), not the summary's own snapshot, so a manual Overview
        number edit resorts the grid the moment Channel Studio is shown
        again -- no separate display-order state to keep in sync.
        """
        combined = list(summaries_by_id.values()) + _companion_summary_objects()
        return sorted(
            combined,
            key=lambda s: (channel_actions.card_display_number(dialog, s), s.name.casefold(), s.channel_id),
        )

    def _build_card(summary):
        number = channel_actions.card_display_number(dialog, summary)
        channel_info = _channel_info_for(summary, number)
        if summary.channel_id in _COMPANION_TYPE_BY_ID:
            return build_dashboard_channel_card(
                summary,
                None,
                on_open=_open_from_setup,
                on_set_logo=lambda checked=False, info=channel_info: _open_logo(info),
                enabled=True,
                on_toggle_enabled=lambda checked, ct=summary.channel_type: _toggle_companion_enabled(ct, checked),
                on_remove=lambda ct=summary.channel_type: _toggle_companion_enabled(ct, False),
                display_number=number,
                shared_logos_dir=getattr(dialog, "_shared_logos_dir", ""),
            )
        return build_dashboard_channel_card(
            summary,
            schedules_by_id.get(summary.channel_id),
            on_open=_open_from_setup,
            on_set_logo=lambda checked=False, info=channel_info: _open_logo(info),
            enabled=_local_enabled(summary.channel_id),
            on_toggle_enabled=lambda checked, cid=summary.channel_id: _toggle_local_enabled(cid, checked),
            commercials_status=channel_actions.card_commercials_status(dialog, summary.name),
            display_number=number,
            shared_logos_dir=getattr(dialog, "_shared_logos_dir", ""),
        )

    def _rebuild_grid(filter_text=""):
        current_filter["text"] = filter_text or ""
        _clear(grid_layout)

        ordered = _sorted_summaries()
        if not ordered:
            grid_layout.addWidget(
                build_empty_state(
                    "No channels yet. Once you create or import one, it'll show up here "
                    "as a card you can open."
                )
            )
            return

        needle = current_filter["text"].strip().lower()
        visible = [s for s in ordered if needle in s.name.lower()] if needle else ordered
        if not visible:
            grid_layout.addWidget(build_empty_state(f'No channels match "{filter_text}".'))
            return

        grid_layout.addWidget(build_channel_grid([_build_card(summary) for summary in visible]))

    header = build_channel_studio_header(
        on_create=lambda: _preview(dialog, "Create Channel", "Creating a new channel isn't wired up yet — this is a preview."),
        on_filter=lambda: _preview(dialog, "Filters", "Filtering your channel list isn't wired up yet — this is a preview."),
        on_search_changed=_rebuild_grid,
    )
    layout.addWidget(header)
    layout.addWidget(grid_container)

    _rebuild_grid()
    layout.addStretch(1)

    footer = build_channel_studio_footer(total_count=len(infos))

    content.on_show = lambda: _rebuild_grid(current_filter["text"])

    return content, footer

"""Channel Studio (Preview): Choose Channel.

The only top-level page in Channel Studio. Picking a channel opens its
own five-tab view (see channel_studio_cards.py) — there is nothing else
to navigate to from here. Aside from a read-only list of existing
channel names/numbers/logos, no scheduling, library, or settings data
is read or written from this page.
"""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from .channel_studio_adapter import build_channel_studio_summaries, build_tonight_schedules
from .channel_studio_cards import ChannelEditorPreviewDialog
from .channel_studio_dialogs import show_preview_dialog
from .channel_studio_header import build_channel_studio_header
from .channel_studio_widgets import build_channel_studio_footer, build_empty_state
from .channel_card import build_dashboard_channel_card, build_hero_channel_card
from .channel_grid import build_channel_grid

_IDENTITY_TAB_INDEX = 3


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


def build_channels_page(dialog):
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(16)

    infos = list(getattr(dialog, "catalog_channel_infos", None) or [])

    grid_container = QWidget()
    grid_layout = QVBoxLayout(grid_container)
    grid_layout.setContentsMargins(0, 0, 0, 0)
    grid_layout.setSpacing(0)

    def _open_channel(channel_info, initial_tab=0):
        channel_id = channel_info.get("id", "")
        summary = summaries_by_id.get(channel_id)
        schedule = schedules_by_id.get(channel_id)
        ChannelEditorPreviewDialog(
            channel_info,
            summary=summary,
            schedule=schedule,
            parent=dialog,
            studio_dialog=dialog,
            drafts_path=_drafts_path(dialog),
            initial_tab=initial_tab,
        ).exec()

    def _open_identity(channel_info):
        _open_channel(channel_info, initial_tab=_IDENTITY_TAB_INDEX)

    def _clear_grid():
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    summaries_by_id = {}
    schedules_by_id = {}
    catalog_channel_settings = getattr(dialog, "catalog_channel_settings", None)

    if infos:
        summaries = build_channel_studio_summaries(
            infos,
            shows_lookup=getattr(dialog, "_channel_shows_lookup", None),
            catalog_channel_settings=catalog_channel_settings,
            commercials_config=getattr(dialog, "commercials_settings", None),
            airing_rules_config=getattr(dialog, "_airing_rules_config", None),
            logo_lookup=getattr(dialog, "_channel_logo_lookup", None),
        )
        summaries_by_id = {summary.channel_id: summary for summary in summaries}
        channels_by_id = getattr(dialog, "_studio_channels_by_id", None) or {}
        schedules = build_tonight_schedules(infos, channels_by_id=channels_by_id)
        schedules_by_id = {schedule.channel_id: schedule for schedule in schedules}
        ordered_summaries = sorted(summaries, key=lambda s: s.number)
    else:
        ordered_summaries = []

    def _rebuild(filter_text=""):
        _clear_grid()

        if not ordered_summaries:
            grid_layout.addWidget(
                build_empty_state(
                    "No channels yet. Once you create or import one, it'll show up here "
                    "as a card you can open."
                )
            )
            return

        needle = (filter_text or "").strip().lower()
        visible = [s for s in ordered_summaries if needle in s.name.lower()] if needle else ordered_summaries
        if not visible:
            grid_layout.addWidget(build_empty_state(f'No channels match "{filter_text}".'))
            return

        cards = []
        for index, summary in enumerate(visible):
            channel_info = {
                "id": summary.channel_id,
                "name": summary.name,
                "default_number": summary.number,
            }
            # TODO: once Channel Studio tracks per-channel edit timestamps,
            # feature the most-recently-edited channel here instead of
            # always the first — see build_hero_channel_card's docstring.
            builder = build_hero_channel_card if index == 0 else build_dashboard_channel_card
            cards.append(
                builder(
                    summary,
                    schedules_by_id.get(summary.channel_id),
                    on_open=_open_channel,
                    on_set_logo=lambda checked=False, info=channel_info: _open_identity(info),
                    enabled=_channel_enabled(summary.channel_id, catalog_channel_settings),
                )
            )
        grid_layout.addWidget(build_channel_grid(cards))

    header = build_channel_studio_header(
        on_create=lambda: _preview(dialog, "Create Channel", "Creating a new channel isn't wired up yet — this is a preview."),
        on_filter=lambda: _preview(dialog, "Filters", "Filtering your channel list isn't wired up yet — this is a preview."),
        on_search_changed=_rebuild,
    )
    layout.addWidget(header)
    layout.addWidget(grid_container)
    layout.addWidget(
        build_channel_studio_footer(
            total_count=len(infos),
            on_reorder=lambda: _preview(
                dialog, "Reorder Channels", "Reordering channels isn't wired up yet — this is a preview."
            ),
        )
    )

    _rebuild()
    layout.addStretch(1)
    return content

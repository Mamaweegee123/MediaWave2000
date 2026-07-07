"""Channel Studio (Preview): Choose Channel.

The only top-level page in Channel Studio. Picking a channel opens its
own five-tab view (see channel_studio_cards.py) — there is nothing else
to navigate to from here. Aside from a read-only list of existing
channel names/numbers/logos and the small last-edited-channel state in
studio_state.py, no scheduling, library, or settings data is read or
written from this page.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .channel_studio_adapter import build_channel_studio_summaries, build_tonight_schedules
from .channel_studio_cards import ChannelEditorPreviewDialog
from .channel_studio_dialogs import show_preview_dialog
from .channel_studio_header import build_channel_studio_header
from .channel_studio_widgets import build_channel_studio_footer, build_empty_state
from .channel_card import build_dashboard_channel_card, build_hero_channel_card
from .channel_grid import build_channel_grid
from .studio_state import load_last_edited_channel_id, save_last_edited_channel_id

_IDENTITY_TAB_INDEX = 3


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


def _build_choose_hint():
    """Shown above the grid instead of a hero card until the user has
    opened Setup on at least one channel — no empty hero placeholder,
    no blank gap.
    """
    label = QLabel("Choose a channel to start customizing.")
    label.setObjectName("sectionNote")
    return label


def _channel_info_for(summary):
    return {"id": summary.channel_id, "name": summary.name, "default_number": summary.number}


def build_channels_page(dialog):
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(16)

    infos = list(getattr(dialog, "catalog_channel_infos", None) or [])
    state_path = _state_path(dialog)
    catalog_channel_settings = getattr(dialog, "catalog_channel_settings", None)

    # Hero (last-edited channel, contextual only) and grid (every channel,
    # including whichever one the hero is showing) rebuild independently:
    # the grid reacts to search text, the hero reacts to Setup being used.
    hero_container = QWidget()
    hero_layout = QVBoxLayout(hero_container)
    hero_layout.setContentsMargins(0, 0, 0, 0)
    hero_layout.setSpacing(0)

    grid_container = QWidget()
    grid_layout = QVBoxLayout(grid_container)
    grid_layout.setContentsMargins(0, 0, 0, 0)
    grid_layout.setSpacing(0)

    summaries_by_id = {}
    schedules_by_id = {}

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

    current_filter = {"text": ""}

    def _clear(layout_obj):
        while layout_obj.count():
            item = layout_obj.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

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

    def _open_from_setup(channel_info):
        """The Setup button's handler, from either the hero card or a
        grid card: marks this channel as most-recently-customized (so
        it becomes/stays the hero), opens its detail screen, then
        refreshes both the hero and the grid once it closes.
        """
        save_last_edited_channel_id(state_path, channel_info.get("id", ""))
        _open_channel(channel_info, initial_tab=0)
        _rebuild_hero()
        _rebuild_grid(current_filter["text"])

    def _rebuild_hero():
        _clear(hero_layout)
        if not ordered_summaries:
            return

        last_edited_id = load_last_edited_channel_id(state_path)
        hero_summary = summaries_by_id.get(last_edited_id) if last_edited_id else None
        if hero_summary is None:
            hero_layout.addWidget(_build_choose_hint())
            return

        hero_layout.addWidget(
            build_hero_channel_card(
                hero_summary,
                schedules_by_id.get(hero_summary.channel_id),
                on_open=_open_from_setup,
                on_set_logo=lambda checked=False, info=_channel_info_for(hero_summary): _open_identity(info),
                enabled=_channel_enabled(hero_summary.channel_id, catalog_channel_settings),
            )
        )

    def _rebuild_grid(filter_text=""):
        current_filter["text"] = filter_text or ""
        _clear(grid_layout)

        if not ordered_summaries:
            grid_layout.addWidget(
                build_empty_state(
                    "No channels yet. Once you create or import one, it'll show up here "
                    "as a card you can open."
                )
            )
            return

        needle = current_filter["text"].strip().lower()
        visible = [s for s in ordered_summaries if needle in s.name.lower()] if needle else ordered_summaries
        if not visible:
            grid_layout.addWidget(build_empty_state(f'No channels match "{filter_text}".'))
            return

        # The grid always shows every channel — including whichever one the
        # hero card is currently featuring; the hero is a duplicate,
        # contextual preview, not a replacement for its grid card.
        cards = []
        for summary in visible:
            channel_info = _channel_info_for(summary)
            cards.append(
                build_dashboard_channel_card(
                    summary,
                    schedules_by_id.get(summary.channel_id),
                    on_open=_open_from_setup,
                    on_set_logo=lambda checked=False, info=channel_info: _open_identity(info),
                    enabled=_channel_enabled(summary.channel_id, catalog_channel_settings),
                )
            )
        grid_layout.addWidget(build_channel_grid(cards))

    header = build_channel_studio_header(
        on_create=lambda: _preview(dialog, "Create Channel", "Creating a new channel isn't wired up yet — this is a preview."),
        on_filter=lambda: _preview(dialog, "Filters", "Filtering your channel list isn't wired up yet — this is a preview."),
        on_search_changed=_rebuild_grid,
    )
    layout.addWidget(header)
    layout.addWidget(hero_container)
    layout.addWidget(grid_container)

    _rebuild_hero()
    _rebuild_grid()
    layout.addStretch(1)
    return content


def build_channels_footer(dialog):
    """Channel Studio's own persistent footer — built separately from
    `build_channels_page` so the caller can place it *outside* the
    scrollable content, in the same fixed spot the main Advanced
    Configuration dialog's Close/Save footer occupies (see
    channel_studio.py and _animate_mode_switch in channelsurfer2000.py).
    """
    infos = list(getattr(dialog, "catalog_channel_infos", None) or [])
    return build_channel_studio_footer(
        total_count=len(infos),
        on_reorder=lambda: _preview(
            dialog,
            "Reorder Channels",
            "Drag-and-drop channel order is coming soon. Nothing changes until then.",
        ),
    )

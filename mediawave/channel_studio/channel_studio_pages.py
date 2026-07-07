"""Channel Studio (Preview): Choose Channel.

The only top-level page in Channel Studio. Picking a channel opens its
own five-tab view (see channel_studio_cards.py) — there is nothing else
to navigate to from here. Aside from a read-only list of existing
channel names/numbers/logos and the small preview state in
studio_state.py (last-edited channel, grid display order), no
scheduling, library, or settings data is read or written from this page.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .channel_studio_adapter import build_channel_studio_summaries, build_tonight_schedules
from .channel_studio_cards import ChannelEditorPreviewDialog
from .channel_studio_dialogs import show_preview_dialog
from .channel_studio_header import build_channel_studio_header
from .channel_studio_widgets import build_channel_studio_footer, build_empty_state
from .channel_card import build_dashboard_channel_card, build_hero_channel_card
from .draggable_grid import DraggableGrid
from .reorder import apply_saved_order
from .studio_state import (
    load_channel_order,
    load_last_edited_channel_id,
    save_channel_order,
    save_last_edited_channel_id,
)
from .studio_styles import style_setup_button

_IDENTITY_TAB_INDEX = 3

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


def _build_choose_hint():
    """Shown above the grid instead of a hero card until the user has
    opened Setup on at least one channel — no empty hero placeholder,
    no blank gap.
    """
    label = QLabel("Choose a channel to start customizing.")
    label.setObjectName("sectionNote")
    return label


def _build_reorder_hint():
    label = QLabel(_REORDER_HINT_TEXT)
    label.setObjectName("sectionNote")
    return label


def _channel_info_for(summary):
    return {"id": summary.channel_id, "name": summary.name, "default_number": summary.number}


def build_channel_studio_content(dialog):
    """Build the Choose Channel page: the scrollable content (header,
    hero, grid) and its persistent footer, together — not as two
    independent builds — so the footer's Reorder Channels button can
    share reorder-mode state with the grid it toggles. Returns
    `(content, footer)`; see channel_studio.py for how callers place
    `footer` outside the scrollable area.
    """
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(16)

    infos = list(getattr(dialog, "catalog_channel_infos", None) or [])
    state_path = _state_path(dialog)
    catalog_channel_settings = getattr(dialog, "catalog_channel_settings", None)

    hero_container = QWidget()
    hero_layout = QVBoxLayout(hero_container)
    hero_layout.setContentsMargins(0, 0, 0, 0)
    hero_layout.setSpacing(0)

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
        if not number_sorted:
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
        if grid_ref["widget"] is not None:
            # Defensive: if a drag was somehow still active when the grid
            # is being torn down, cancel it first so its floating overlay
            # (parented to the window, not to the grid, so it can float
            # above the QScrollArea without being clipped) doesn't leak.
            grid_ref["widget"].cancel_drag()
        _clear(grid_layout)
        grid_ref["widget"] = None

        if not number_sorted:
            grid_layout.addWidget(
                build_empty_state(
                    "No channels yet. Once you create or import one, it'll show up here "
                    "as a card you can open."
                )
            )
            return

        ordered = _display_order()
        if reorder_state["active"]:
            # Reorder mode always shows every channel, unfiltered — dragging
            # a partially-filtered view would make "where did the rest go"
            # confusing. The grid always includes every channel, including
            # whichever one the hero card is featuring — the hero is a
            # duplicate contextual preview, not a replacement.
            visible = ordered
        else:
            needle = current_filter["text"].strip().lower()
            visible = [s for s in ordered if needle in s.name.lower()] if needle else ordered
            if not visible:
                grid_layout.addWidget(build_empty_state(f'No channels match "{filter_text}".'))
                return

        entries = []
        for summary in visible:
            channel_info = _channel_info_for(summary)
            card = build_dashboard_channel_card(
                summary,
                schedules_by_id.get(summary.channel_id),
                on_open=_open_from_setup,
                on_set_logo=lambda checked=False, info=channel_info: _open_identity(info),
                enabled=_channel_enabled(summary.channel_id, catalog_channel_settings),
            )
            entries.append((summary.channel_id, card))

        grid = DraggableGrid(entries)
        grid.set_reorder_mode(reorder_state["active"])
        grid_ref["widget"] = grid
        grid_layout.addWidget(grid)

    def _toggle_reorder(checked=False):
        if reorder_state["active"]:
            # Exiting reorder mode: persist wherever the grid ended up.
            # Display order only — channel numbers, scheduling, and
            # playback order are all untouched.
            if grid_ref["widget"] is not None:
                save_channel_order(state_path, grid_ref["widget"].current_order())
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
    layout.addWidget(hero_container)
    layout.addWidget(reorder_hint_container)
    layout.addWidget(grid_container)

    _rebuild_hero()
    _rebuild_grid()
    layout.addStretch(1)

    footer, reorder_btn = build_channel_studio_footer(
        total_count=len(infos),
        on_reorder=_toggle_reorder,
    )

    return content, footer

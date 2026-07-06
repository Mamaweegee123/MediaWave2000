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
from .channel_studio_widgets import build_action_button_row, build_empty_state
from .channel_card import build_dashboard_channel_card
from .channel_grid import build_channel_grid

_COMMERCIALS_TAB_INDEX = 2
_IDENTITY_TAB_INDEX = 3


def _page(dialog, title_text, note_text=None):
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(14)
    card, card_layout = dialog.build_section_card(title_text, note_text)
    layout.addWidget(card)
    return content, layout, card_layout


def _preview(dialog, title, description):
    show_preview_dialog(dialog, title, description)


def _drafts_path(dialog):
    return getattr(dialog, "_channel_studio_drafts_file", None)


def build_channels_page(dialog):
    content, layout, hero_layout = _page(
        dialog,
        "Get Started",
        "Choose a channel to start running it.",
    )
    action_row, _buttons = build_action_button_row(
        ["Create Channel", "Import Existing Channel"],
        fallback=lambda label: _preview(
            dialog, label, f"{label} will walk you through this step by step. Not wired up yet."
        ),
    )
    hero_layout.addWidget(action_row)

    list_card, list_layout = dialog.build_section_card("📺 Your Channels")
    infos = list(getattr(dialog, "catalog_channel_infos", None) or [])
    if not infos:
        list_layout.addWidget(
            build_empty_state(
                "No channels yet. Once you create or import one, it'll show up here "
                "as a card you can open."
            )
        )
    else:
        summaries = build_channel_studio_summaries(
            infos,
            shows_lookup=getattr(dialog, "_channel_shows_lookup", None),
            catalog_channel_settings=getattr(dialog, "catalog_channel_settings", None),
            commercials_config=getattr(dialog, "commercials_settings", None),
            airing_rules_config=getattr(dialog, "_airing_rules_config", None),
            logo_lookup=getattr(dialog, "_channel_logo_lookup", None),
        )
        summaries_by_id = {summary.channel_id: summary for summary in summaries}
        channels_by_id = getattr(dialog, "_studio_channels_by_id", None) or {}
        schedules = build_tonight_schedules(infos, channels_by_id=channels_by_id)
        schedules_by_id = {schedule.channel_id: schedule for schedule in schedules}

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

        def _open_commercials(channel_info):
            _open_channel(channel_info, initial_tab=_COMMERCIALS_TAB_INDEX)

        def _open_identity(channel_info):
            _open_channel(channel_info, initial_tab=_IDENTITY_TAB_INDEX)

        cards = []
        for summary in sorted(summaries, key=lambda s: s.number):
            channel_info = {
                "id": summary.channel_id,
                "name": summary.name,
                "default_number": summary.number,
            }
            cards.append(
                build_dashboard_channel_card(
                    summary,
                    schedules_by_id.get(summary.channel_id),
                    on_open=_open_channel,
                    on_commercials=_open_commercials,
                    on_set_logo=lambda checked=False, info=channel_info: _open_identity(info),
                )
            )
        list_layout.addWidget(build_channel_grid(cards))
    layout.addWidget(list_card)

    layout.addStretch(1)
    return content

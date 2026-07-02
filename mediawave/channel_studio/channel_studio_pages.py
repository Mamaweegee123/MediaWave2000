"""Page content builders for Channel Studio (Preview).

Every page here is a placeholder — no scheduling, library, or settings
data is read or written, aside from a read-only list of existing
channel names/numbers on the Channels page. See channel_studio.py for
the shell that wires these into the sidebar navigation.
"""

from .channel_studio_cards import ChannelEditorPreviewDialog, build_channel_card
from .channel_studio_widgets import (
    build_action_button_row,
    build_mock_card_grid,
    build_placeholder_note,
)

from PySide6.QtWidgets import QVBoxLayout, QWidget


def _page(dialog, title_text, note_text=None):
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(14)
    card, card_layout = dialog.build_section_card(title_text, note_text)
    layout.addWidget(card)
    return content, layout, card_layout


def build_channels_page(dialog):
    content, layout, hero_layout = _page(
        dialog,
        "CHANNEL STUDIO",
        "Design your television lineup. This preview only displays your "
        "existing channels — nothing here changes real schedules yet.",
    )
    action_row, _buttons = build_action_button_row(
        ["Select a Channel", "Create a New Channel", "Import an Existing Channel"]
    )
    hero_layout.addWidget(action_row)

    list_card, list_layout = dialog.build_section_card("Your Channels")
    infos = list(getattr(dialog, "catalog_channel_infos", None) or [])
    if not infos:
        list_layout.addWidget(build_placeholder_note("No channels found yet."))
    else:
        def _open_editor(channel_info):
            ChannelEditorPreviewDialog(channel_info, parent=dialog).exec()

        for info in sorted(infos, key=lambda i: i.get("default_number", 0)):
            list_layout.addWidget(build_channel_card(info, _open_editor))
    layout.addWidget(list_card)

    layout.addStretch(1)
    return content


def build_library_page(dialog):
    content, layout, card_layout = _page(
        dialog,
        "Library",
        "Your media stays exactly where it already is. MediaWave creates "
        "virtual collections instead of requiring folders or symlinks.",
    )
    action_row, _buttons = build_action_button_row(
        ["Add Library", "Create Collection", "Scan Libraries"]
    )
    card_layout.addWidget(action_row)
    layout.addStretch(1)
    return content


def build_programming_page(dialog):
    content, layout, card_layout = _page(
        dialog, "Programming", "Prototype of a television-style programming workflow."
    )
    card_layout.addWidget(
        build_mock_card_grid(
            [
                ("Programming Blocks", "Recurring lineup segments"),
                ("Marathons", "Back-to-back runs"),
                ("Movies", "Feature presentations"),
                ("Seasonal Events", "Holiday & special programming"),
                ("Schedules", "Day-by-day lineups"),
            ]
        )
    )
    layout.addStretch(1)
    return content


def build_blocks_page(dialog):
    content, layout, card_layout = _page(dialog, "Blocks", "This section is under construction.")
    card_layout.addWidget(
        build_mock_card_grid(
            ["Nickelodeon Day", "Nick at Nite", "Adult Swim", "Friday Night Movies", "Holiday Marathon"]
        )
    )
    layout.addStretch(1)
    return content


def build_commercials_page(dialog):
    content, layout, card_layout = _page(dialog, "Commercials", "This section is under construction.")
    card_layout.addWidget(
        build_mock_card_grid(["Daytime", "Night", "Holiday", "Infomercials", "Kids", "Adult"])
    )
    layout.addStretch(1)
    return content


def build_bumpers_page(dialog):
    content, layout, card_layout = _page(dialog, "Bumpers", "This section is under construction.")
    card_layout.addWidget(
        build_mock_card_grid(["Day", "Night", "Seasonal", "Network IDs", "Transitions"])
    )
    layout.addStretch(1)
    return content


def build_branding_page(dialog):
    content, layout, card_layout = _page(dialog, "Branding", "This section is under construction.")
    card_layout.addWidget(
        build_mock_card_grid(["Logo", "Station IDs", "Theme", "Colors", "Future Era Mode"])
    )
    layout.addStretch(1)
    return content


def build_appearance_page(dialog):
    content, layout, card_layout = _page(dialog, "Appearance", "This section is under construction.")
    layout.addStretch(1)
    return content


def build_advanced_page(dialog):
    content, layout, card_layout = _page(
        dialog, "Advanced", "Reserved for future advanced configuration."
    )
    layout.addStretch(1)
    return content

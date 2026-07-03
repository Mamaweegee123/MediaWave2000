"""Page content builders for Channel Studio (Preview).

Every page here is a friendly, card-based mock. Aside from a read-only
list of existing channel names/numbers/logos on the Channels page, no
scheduling, library, or settings data is read or written. Buttons open
"Preview only" dialogs explaining what the feature will eventually do.
See channel_studio.py for the shell that wires these into the sidebar.
"""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from .channel_studio_adapter import build_channel_studio_summaries, build_tonight_schedules
from .channel_studio_cards import ChannelEditorPreviewDialog, build_block_card, build_channel_card
from .channel_studio_dialogs import show_preview_dialog
from .channel_studio_widgets import (
    build_action_button_row,
    build_card_grid,
    build_empty_state,
    build_info_card,
)


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


# ── Tonight's Schedule ───────────────────────────────────────────────────

def _build_tonight_schedule_card(schedule):
    if not schedule.has_data:
        return build_info_card(
            schedule.channel_name,
            "No lineup detected yet for tonight — once this channel is playing, "
            "its lineup will show up here.",
        )
    meta_lines = [f"{slot.time_label} — {slot.title}" for slot in schedule.slots]
    return build_info_card(schedule.channel_name, meta_lines=meta_lines)


def build_tonight_schedule_page(dialog):
    content, layout, hero_layout = _page(
        dialog,
        "Tonight's Schedule",
        "Here's what your channel feels like tonight. This is a read-only "
        "preview, built from your channel's current lineup — nothing here "
        "changes what plays.",
    )
    infos = list(getattr(dialog, "catalog_channel_infos", None) or [])
    list_card, list_layout = dialog.build_section_card("Tonight's Lineup")
    if not infos:
        list_layout.addWidget(
            build_empty_state(
                "No channels yet, so there's no lineup to preview. Once you have a "
                "channel, tonight's schedule will show up here.",
                icon="🌙",
            )
        )
    else:
        schedules = build_tonight_schedules(
            infos,
            channels_by_id=getattr(dialog, "_studio_channels_by_id", None),
        )
        cards = [_build_tonight_schedule_card(schedule) for schedule in schedules]
        list_layout.addWidget(build_card_grid(cards, columns=1))
    layout.addWidget(list_card)
    layout.addStretch(1)
    return content


# ── Channels ─────────────────────────────────────────────────────────────

def build_channels_page(dialog):
    content, layout, hero_layout = _page(
        dialog,
        "CHANNEL STUDIO",
        "Design your television lineup. This preview only displays your "
        "existing channels — nothing here changes real schedules yet.",
    )
    action_row, _buttons = build_action_button_row(
        ["Create Channel", "Import Existing Channel", "Build from Library"],
        fallback=lambda label: _preview(
            dialog, label, f"{label} will walk you through this step by step. Not wired up yet."
        ),
    )
    hero_layout.addWidget(action_row)

    list_card, list_layout = dialog.build_section_card("Your Channels")
    infos = list(getattr(dialog, "catalog_channel_infos", None) or [])
    if not infos:
        list_layout.addWidget(
            build_empty_state(
                "No channels yet. Once you create or import one, it'll show up here "
                "as a card you can open in the Studio.",
                icon="📺",
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

        def _open_studio(channel_info):
            ChannelEditorPreviewDialog(channel_info, parent=dialog).exec()

        def _open_preview(channel_info):
            _preview(
                dialog,
                f"Preview {channel_info.get('name', 'Channel')}",
                "This will eventually show a live preview of what's currently "
                "playing on this channel.",
            )

        def _open_edit_basics(channel_info):
            _preview(
                dialog,
                f"Edit Basics — {channel_info.get('name', 'Channel')}",
                "Quick renaming and channel-number changes will live here, "
                "without opening the full Studio editor.",
            )

        for summary in sorted(summaries, key=lambda s: s.number):
            list_layout.addWidget(build_channel_card(summary, _open_studio, _open_preview, _open_edit_basics))
    layout.addWidget(list_card)

    layout.addStretch(1)
    return content


# ── Library ──────────────────────────────────────────────────────────────

def build_library_page(dialog):
    content, layout, card_layout = _page(
        dialog,
        "Library",
        "Your files stay where they are. MediaWave builds channels from "
        "references — no folders to reorganize, no symlinks to manage.",
    )
    card_layout.addWidget(
        build_info_card(
            "Folder channels still work automatically",
            "Nothing is moved or reorganized. Drop a folder in and it plays as a "
            "channel — Channel Studio can customize it later, but it never has to.",
        )
    )
    action_row, _buttons = build_action_button_row(
        ["Add Library Location", "Create Collection", "Scan Library", "Explain How This Works"],
        fallback=lambda label: _preview(
            dialog,
            label,
            "MediaWave creates virtual collections that point at your existing "
            "files instead of copying or moving anything. This step isn't wired "
            "up yet, but that's the plan."
            if label == "Explain How This Works"
            else f"{label} is a preview placeholder — no library changes happen yet.",
        ),
    )
    card_layout.addWidget(action_row)
    card_layout.addWidget(
        build_empty_state(
            "No collections yet. Add a library location to get started — "
            "MediaWave will never move or rename your files.",
            icon="📁",
        )
    )
    layout.addStretch(1)
    return content


# ── Programming ──────────────────────────────────────────────────────────

_PROGRAMMING_ACTIONS = [
    ("Add Show", "Pick a show from your library to add to a channel."),
    ("Add Movie Folder", "Point at a folder of movies to program from."),
    ("Create Programming Block", "Group content into a recurring block, like Nick at Nite."),
    ("Add Seasonal Event", "Plan holiday or seasonal takeovers ahead of time."),
    ("Create Marathon", "Queue up a back-to-back run of episodes or movies."),
    ("Add Night Block", "Build a themed overnight lineup."),
]


def build_programming_page(dialog):
    content, layout, card_layout = _page(
        dialog,
        "Programming",
        "Plan your lineup like a television network. Nothing here is "
        "connected to real scheduling yet.",
    )
    cards = [
        build_info_card(
            title,
            note,
            buttons=[("Start", lambda checked=False, t=title, n=note: _preview(dialog, t, n))],
        )
        for title, note in _PROGRAMMING_ACTIONS
    ]
    card_layout.addWidget(build_card_grid(cards))
    layout.addStretch(1)
    return content


# ── Blocks ───────────────────────────────────────────────────────────────

_MOCK_BLOCKS = [
    {
        "name": "Daytime",
        "time_range": "6:00 AM – 3:00 PM",
        "content_type": "Sitcoms & Cartoons",
        "commercials_profile": "Kids Daytime",
        "bumper_set": "Channel IDs",
    },
    {
        "name": "Nick at Nite",
        "time_range": "8:00 PM – 12:00 AM",
        "content_type": "Classic Sitcoms",
        "commercials_profile": "Night",
        "bumper_set": "Block Starts",
    },
    {
        "name": "Adult Swim",
        "time_range": "12:00 AM – 6:00 AM",
        "content_type": "Adult Animation",
        "commercials_profile": "Night",
        "bumper_set": "Adult Swim Style",
    },
    {
        "name": "Friday Night Movies",
        "time_range": "8:00 PM – 11:00 PM",
        "content_type": "Feature Films",
        "commercials_profile": "Movies",
        "bumper_set": "Block Starts",
    },
    {
        "name": "Holiday Marathon",
        "time_range": "All Day",
        "content_type": "Seasonal Specials",
        "commercials_profile": "Holiday",
        "bumper_set": "Holiday",
    },
]


def build_blocks_page(dialog):
    content, layout, card_layout = _page(
        dialog,
        "Blocks",
        "Blocks are recurring chunks of programming, like a network would air. "
        "These are example blocks — building your own comes later.",
    )
    cards = [
        build_block_card(
            block,
            on_edit=lambda b: _preview(
                dialog, f"Edit {b['name']}", "Block editing isn't wired up yet — this is a preview."
            ),
            on_preview=lambda b: _preview(
                dialog, f"Preview {b['name']}", "This will eventually simulate a night of this block."
            ),
        )
        for block in _MOCK_BLOCKS
    ]
    card_layout.addWidget(build_card_grid(cards, columns=2))
    layout.addStretch(1)
    return content


# ── Commercials ──────────────────────────────────────────────────────────

_COMMERCIAL_PROFILES = [
    ("Kids Daytime", "Cereal, toys, and Saturday-morning energy."),
    ("Night", "Slower-paced spots for late-night viewing."),
    ("Holiday", "Seasonal ads for the time of year."),
    ("Infomercials", "Long-form spots for overnight blocks."),
    ("Movies", "Trailer-style breaks for feature presentations."),
]


def build_commercials_page(dialog):
    content, layout, card_layout = _page(
        dialog,
        "Commercials",
        "Commercial profiles decide what kind of breaks play on a channel or block.",
    )
    action_row, _buttons = build_action_button_row(
        ["Create Profile", "Assign to Block", "Scan Commercials"],
        fallback=lambda label: _preview(
            dialog, label, f"{label} is a preview placeholder — no commercial settings change yet."
        ),
    )
    card_layout.addWidget(action_row)
    cards = [
        build_info_card(
            title,
            note,
            buttons=[("Preview", lambda checked=False, t=title, n=note: _preview(dialog, t, n))],
        )
        for title, note in _COMMERCIAL_PROFILES
    ]
    card_layout.addWidget(build_card_grid(cards))
    layout.addStretch(1)
    return content


# ── Bumpers ──────────────────────────────────────────────────────────────

_BUMPER_SETS = [
    ("Channel IDs", "Short idents that remind viewers what channel they're on."),
    ("Block Starts", "Plays right before a programming block begins."),
    ("Block Ends", "Plays right after a programming block wraps up."),
    ("Holiday", "Seasonal bumpers for the time of year."),
    ("Adult Swim Style", "Moody, late-night transition bumpers."),
]


def build_bumpers_page(dialog):
    content, layout, card_layout = _page(
        dialog,
        "Bumpers",
        "Bumpers are the short transitions between shows, blocks, and breaks.",
    )
    action_row, _buttons = build_action_button_row(
        ["Add Bumper Folder", "Assign to Block"],
        fallback=lambda label: _preview(
            dialog, label, f"{label} is a preview placeholder — no bumper settings change yet."
        ),
    )
    card_layout.addWidget(action_row)
    cards = [
        build_info_card(
            title,
            note,
            buttons=[("Preview", lambda checked=False, t=title, n=note: _preview(dialog, t, n))],
        )
        for title, note in _BUMPER_SETS
    ]
    card_layout.addWidget(build_card_grid(cards))
    layout.addStretch(1)
    return content


# ── Branding ─────────────────────────────────────────────────────────────

def build_branding_page(dialog):
    content, layout, card_layout = _page(
        dialog,
        "Branding",
        "How your channels look and feel — logos, colors, and station idents.",
    )
    branding_items = [
        ("Channel Logo", "The bug shown on screen for this channel.", None),
        ("Station IDs", "Short idents that play between programs.", None),
        ("Colors", "Pick an accent color for guide and overlays.", None),
        ("Theme", "Choose a visual theme for this channel's on-screen look.", None),
        ("Future Era Mode", "Style channels like a specific decade of television.", "Later"),
    ]
    cards = [
        build_info_card(
            title,
            note,
            badge_text=badge,
            buttons=[("Preview", lambda checked=False, t=title, n=note: _preview(dialog, t, n))],
        )
        for title, note, badge in branding_items
    ]
    card_layout.addWidget(build_card_grid(cards))
    layout.addStretch(1)
    return content


# ── Appearance / Advanced ────────────────────────────────────────────────

def build_appearance_page(dialog):
    content, layout, card_layout = _page(
        dialog,
        "Appearance",
        "Fine-tune how Channel Studio itself looks. Nothing to configure yet.",
    )
    card_layout.addWidget(
        build_empty_state("This is reserved for future look-and-feel options.", icon="🎨")
    )
    layout.addStretch(1)
    return content


def build_advanced_page(dialog):
    content, layout, card_layout = _page(
        dialog,
        "Advanced",
        "Power-user options will live here once the basics are solid.",
    )
    card_layout.addWidget(
        build_empty_state("Nothing to configure yet — check back in a future update.", icon="⚙")
    )
    layout.addStretch(1)
    return content

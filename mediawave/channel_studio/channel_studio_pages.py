"""Page content builders for Channel Studio (Preview).

Every page here is a friendly, card-based mock. Aside from a read-only
list of existing channel names/numbers/logos on the Channels page, no
scheduling, library, or settings data is read or written. Buttons open
"Preview only" dialogs explaining what the feature will eventually do.
See channel_studio.py for the shell that wires these into the sidebar.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .channel_studio_adapter import build_channel_studio_summaries, build_tonight_schedules
from .channel_studio_cards import ChannelEditorPreviewDialog, build_block_card, build_channel_card
from .channel_studio_dialogs import show_preview_dialog
from .channel_studio_widgets import (
    build_action_button_row,
    build_card_grid,
    build_empty_state,
    build_info_card,
    build_schedule_timeline,
)
from .drafts import delete_draft, load_drafts
from .programming_block_wizard import open_programming_block_wizard
from .programming_blocks import DEFAULT_PROGRAMMING_BLOCKS, QUICK_ACTION_SUGGESTIONS

_CREATE_PROGRAMMING_BLOCK = "Create Programming Block"


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


def _start_create_block(dialog, on_saved=None):
    open_programming_block_wizard(dialog, _drafts_path(dialog), on_saved=on_saved)


def _trigger(dialog, title, description, on_saved=None):
    """Route a Channel Studio action button: the real wizard for "Create
    Programming Block", a "Preview only" dialog for everything else.
    """
    if title == _CREATE_PROGRAMMING_BLOCK:
        _start_create_block(dialog, on_saved=on_saved)
    else:
        _preview(dialog, title, description)


# ── Tonight's Schedule ───────────────────────────────────────────────────

def _build_tonight_schedule_card(schedule):
    if not schedule.has_data:
        return build_info_card(
            schedule.channel_name,
            "No lineup detected yet for tonight — once this channel is playing, "
            "its lineup will show up here.",
        )
    return build_schedule_timeline(schedule.channel_name, schedule.slots)


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

    actions_card, actions_layout = dialog.build_section_card(
        "Quick Actions", "A few fun ways to shake up tonight's lineup."
    )
    action_cards = [
        build_info_card(
            f"{suggestion.icon} {suggestion.title}",
            suggestion.description,
            buttons=[
                (
                    "Try It",
                    lambda checked=False, s=suggestion: _trigger(dialog, s.title, s.description),
                )
            ],
        )
        for suggestion in QUICK_ACTION_SUGGESTIONS
    ]
    actions_layout.addWidget(build_card_grid(action_cards))
    layout.addWidget(actions_card)

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
        summaries_by_id = {summary.channel_id: summary for summary in summaries}
        channels_by_id = getattr(dialog, "_studio_channels_by_id", None) or {}

        def _open_studio(channel_info):
            channel_id = channel_info.get("id", "")
            summary = summaries_by_id.get(channel_id)
            schedule = build_tonight_schedules([channel_info], channels_by_id=channels_by_id)[0]
            ChannelEditorPreviewDialog(
                channel_info, summary=summary, schedule=schedule, parent=dialog
            ).exec()

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
            buttons=[("Start", lambda checked=False, t=title, n=note: _trigger(dialog, t, n))],
        )
        for title, note in _PROGRAMMING_ACTIONS
    ]
    card_layout.addWidget(build_card_grid(cards))
    layout.addStretch(1)
    return content


# ── Blocks ───────────────────────────────────────────────────────────────

def _preview_draft_dialog(parent, draft):
    from PySide6.QtWidgets import QDialog, QPushButton

    from .schedule_preview import build_draft_preview_slots

    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Preview — {draft.title}")
    dlg.resize(420, 420)
    layout = QVBoxLayout(dlg)
    layout.setSpacing(10)
    note = QLabel("A made-up preview of this draft — nothing here is scheduled yet.")
    note.setObjectName("sectionNote")
    note.setWordWrap(True)
    layout.addWidget(note)
    layout.addWidget(build_schedule_timeline(draft.title, build_draft_preview_slots(draft.media_selections)))
    layout.addStretch(1)
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dlg.accept)
    layout.addWidget(close_btn, 0, Qt.AlignRight)
    dlg.exec()


def _build_draft_card(dialog, draft, refresh):
    def _preview_draft(checked=False):
        _preview_draft_dialog(dialog, draft)

    def _edit_draft(checked=False):
        open_programming_block_wizard(dialog, _drafts_path(dialog), existing_draft=draft, on_saved=refresh)

    def _delete_draft(checked=False):
        delete_draft(_drafts_path(dialog), draft.key)
        refresh()

    meta_lines = [f"🗓 {draft.time_preset_label}"] if draft.time_preset_label else []
    if draft.playback_style_label:
        meta_lines.append(f"🎛 {draft.playback_style_label}")
    return build_info_card(
        draft.title,
        f"{len(draft.media_selections)} item(s) selected" if draft.media_selections else "No content selected yet",
        meta_lines=meta_lines,
        badge_text="Draft",
        buttons=[
            ("Preview", _preview_draft),
            ("Edit", _edit_draft),
            ("Delete", _delete_draft),
        ],
    )


def _build_drafts_section(dialog):
    section = QWidget()
    section_layout = QVBoxLayout(section)
    section_layout.setContentsMargins(0, 0, 0, 0)
    section_layout.setSpacing(10)

    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(10)
    section_layout.addWidget(body)

    def refresh():
        while body_layout.count():
            item = body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        action_row, _buttons = build_action_button_row(
            [(_CREATE_PROGRAMMING_BLOCK, lambda checked=False: _start_create_block(dialog, on_saved=refresh))]
        )
        body_layout.addWidget(action_row)

        drafts = load_drafts(_drafts_path(dialog))
        if not drafts:
            body_layout.addWidget(
                build_empty_state(
                    "No draft blocks yet. Create one to design a recurring lineup like Nick at Nite.",
                    icon="🧩",
                )
            )
        else:
            cards = [_build_draft_card(dialog, draft, refresh) for draft in drafts]
            body_layout.addWidget(build_card_grid(cards, columns=2))

    refresh()
    return section


def build_blocks_page(dialog):
    content, layout, card_layout = _page(
        dialog,
        "Blocks",
        "When should this channel come alive? Blocks are the identities "
        "that make up a broadcast day — like a network's own dayparts. "
        "These are example blocks — building your own comes later.",
    )

    drafts_card, drafts_card_layout = dialog.build_section_card(
        "Your Draft Blocks", "Blocks you've created with the wizard — draft only, nothing plays yet."
    )
    drafts_card_layout.addWidget(_build_drafts_section(dialog))
    layout.addWidget(drafts_card)

    cards = [
        build_block_card(
            block,
            on_edit=lambda b: _preview(
                dialog, f"Edit {b.title}", "Block editing isn't wired up yet — this is a preview."
            ),
            on_preview=lambda b: _preview(
                dialog, f"Preview {b.title}", "This will eventually simulate a night of this block."
            ),
        )
        for block in DEFAULT_PROGRAMMING_BLOCKS
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
        "What kind of commercials belong here? Commercial profiles decide "
        "what kind of breaks play on a channel or block.",
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
        "How your channels look and feel — logos, station idents, and "
        "on-screen identity. Your app's own theme stays put; these are "
        "just for how a channel presents itself on screen.",
    )
    branding_items = [
        ("Channel Logo", "The bug shown on screen for this channel.", None),
        ("Station IDs", "Short idents that play between programs.", None),
        (
            "Channel Colors",
            "A future accent color for this channel's own guide entries and "
            "overlays — separate from your app's theme, not a replacement for it.",
            "Later",
        ),
        (
            "Channel Look",
            "A future on-screen style for this channel, layered on top of "
            "your app's look rather than changing it.",
            "Later",
        ),
        (
            "On-Air Popups",
            "Future support for fun on-screen extras during a show — think "
            "an 'Up next' character popup or a lower-third, styled to match "
            "the channel.",
            "Later",
        ),
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

"""Step content for the Draft Programming Block wizard.

Every step here is a friendly, card-based question — no forms, no raw
property grids, no filesystem/folder pickers. Selections only ever
populate a `ProgrammingBlockDraft` in memory (see `drafts.py`); nothing
here reads or writes real schedule, library, or settings data.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .channel_studio_widgets import build_card_grid, build_empty_state, build_info_card
from .programming_blocks import WIZARD_BLOCK_TYPES, WIZARD_PLAYBACK_STYLES, WIZARD_TIME_PRESETS
from .schedule_preview import build_draft_preview_slots
from .channel_studio_widgets import build_schedule_timeline


# ── Step 1: block type ───────────────────────────────────────────────────

def build_step1_block_type(on_select):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setSpacing(10)

    cards = []
    for option in WIZARD_BLOCK_TYPES:
        cards.append(
            build_info_card(
                f"{option.icon} {option.title}",
                option.description,
                meta_lines=[
                    f"⏰ Typically airs {option.typical_airtime}",
                    f"🎞 Example: {option.example_content}",
                ],
                buttons=[("Choose", lambda checked=False, o=option: on_select(o))],
            )
        )
    layout.addWidget(build_card_grid(cards, columns=2))
    layout.addStretch(1)
    return page


# ── Step 2: time preset ──────────────────────────────────────────────────

def build_step2_time_preset(on_select, on_custom):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setSpacing(10)

    cards = []
    for option in WIZARD_TIME_PRESETS:
        if option.key == "custom":
            cards.append(
                build_info_card(
                    option.label,
                    option.description,
                    buttons=[("Choose", lambda checked=False: on_custom())],
                )
            )
        else:
            cards.append(
                build_info_card(
                    option.label,
                    option.description,
                    buttons=[("Choose", lambda checked=False, o=option: on_select(o))],
                )
            )
    layout.addWidget(build_card_grid(cards, columns=2))
    layout.addStretch(1)
    return page


# ── Step 3: content ───────────────────────────────────────────────────────

def _build_checkable_list(labels, empty_text):
    list_widget = QListWidget()
    list_widget.setObjectName("sectionCard")
    if not labels:
        list_widget.setEnabled(False)
        placeholder = QListWidgetItem(empty_text)
        placeholder.setFlags(Qt.NoItemFlags)
        list_widget.addItem(placeholder)
        return list_widget
    for label in labels:
        item = QListWidgetItem(label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Unchecked)
        list_widget.addItem(item)
    return list_widget


def build_step3_content(dialog, on_continue, initial_selections=None):
    """`dialog` is only used read-only, to list already-detected shows,
    movies, and channels the user can pick from — no folders, no filesystem.
    """
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setSpacing(10)

    shows_lookup = getattr(dialog, "_channel_shows_lookup", None) or {}
    all_titles = []
    seen = set()
    for entries in shows_lookup.values():
        for entry in entries or []:
            title = (entry or {}).get("title") if isinstance(entry, dict) else None
            media_type = (entry or {}).get("media_type", "tv") if isinstance(entry, dict) else "tv"
            if title and title not in seen:
                seen.add(title)
                all_titles.append((title, media_type))

    show_titles = [title for title, media_type in all_titles if media_type != "movie"]
    movie_titles = [title for title, media_type in all_titles if media_type == "movie"]
    channel_names = [
        info.get("name", "Channel") for info in (getattr(dialog, "catalog_channel_infos", None) or [])
    ]

    switch_row, switch_buttons = QHBoxLayout(), []
    stack = QStackedWidget()

    shows_list = _build_checkable_list(show_titles, "No shows detected yet.")
    movies_list = _build_checkable_list(movie_titles, "No movies detected yet.")
    collections_panel = build_empty_state(
        "No collections yet. Once you create one from the Library page, "
        "it'll show up here to add to a block.",
        icon="📁",
    )
    channels_list = _build_checkable_list(channel_names, "No channels yet.")

    for widget in (shows_list, movies_list, collections_panel, channels_list):
        stack.addWidget(widget)

    button_group = QButtonGroup(page)
    button_group.setExclusive(True)
    for index, label in enumerate(["Add Shows", "Add Movies", "Choose Existing Collection", "Choose Existing Channel"]):
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setChecked(index == 0)
        switch_row.addWidget(btn)
        button_group.addButton(btn, index)
        switch_buttons.append(btn)
    switch_row.addStretch(1)
    button_group.idClicked.connect(stack.setCurrentIndex)

    prompt = QLabel("Pick from what's already been detected — nothing here touches your files.")
    prompt.setObjectName("sectionNote")
    prompt.setWordWrap(True)
    layout.addWidget(prompt)
    layout.addLayout(switch_row)
    layout.addWidget(stack, 1)

    if initial_selections:
        wanted = set(initial_selections)
        for list_widget in (shows_list, movies_list, channels_list):
            for row in range(list_widget.count()):
                item = list_widget.item(row)
                if item.text() in wanted:
                    item.setCheckState(Qt.Checked)

    def _collect_selected():
        selected = []
        for list_widget in (shows_list, movies_list, channels_list):
            for row in range(list_widget.count()):
                item = list_widget.item(row)
                if item.flags() & Qt.ItemIsUserCheckable and item.checkState() == Qt.Checked:
                    selected.append(item.text())
        return selected

    continue_row = QHBoxLayout()
    continue_row.addStretch(1)
    continue_btn = QPushButton("Continue")
    continue_btn.clicked.connect(lambda: on_continue(_collect_selected()))
    continue_row.addWidget(continue_btn)
    layout.addLayout(continue_row)

    return page


# ── Step 4: playback style ───────────────────────────────────────────────

def build_step4_playback_style(on_select):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setSpacing(10)

    cards = []
    for option in WIZARD_PLAYBACK_STYLES:
        cards.append(
            build_info_card(
                f"{option.icon} {option.title}",
                option.description,
                buttons=[("Choose", lambda checked=False, o=option: on_select(o))],
            )
        )
    layout.addWidget(build_card_grid(cards, columns=2))
    layout.addStretch(1)
    return page


# ── Step 5: preview ──────────────────────────────────────────────────────

def build_step5_preview(draft_title, media_selections, example_content, on_save, on_discard):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setSpacing(14)

    heading = QLabel(draft_title)
    heading.setObjectName("sectionHeader")
    layout.addWidget(heading)

    items = media_selections or ([example_content] if example_content else [])
    slots = build_draft_preview_slots(items)
    layout.addWidget(build_schedule_timeline(draft_title, slots))

    note = QLabel("This is a made-up preview to give you a feel for the block — nothing here is scheduled yet.")
    note.setObjectName("fieldHelp")
    note.setWordWrap(True)
    layout.addWidget(note)

    layout.addStretch(1)

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    discard_btn = QPushButton("Discard")
    discard_btn.clicked.connect(on_discard)
    btn_row.addWidget(discard_btn)
    save_btn = QPushButton("Save Draft")
    save_btn.clicked.connect(on_save)
    btn_row.addWidget(save_btn)
    layout.addLayout(btn_row)

    return page

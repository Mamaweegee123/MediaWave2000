"""Channel editor dialog for Channel Studio (Preview).

The Choose Channel grid/card themselves live in channel_grid.py and
channel_card.py — this module is the per-channel detail view they
open into. No scheduling, library, or settings data is written from
here, aside from the isolated Programming Block drafts file.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .channel_studio_dialogs import show_preview_dialog
from .channel_studio_widgets import (
    build_action_button_row,
    build_card_grid,
    build_empty_state,
    build_info_card,
    build_schedule_timeline,
    build_tab_row,
)
from .drafts import delete_draft, load_drafts
from .programming_block_wizard import open_programming_block_wizard
from .programming_blocks import QUICK_ACTION_SUGGESTIONS
from .schedule_preview import build_draft_preview_slots
from .studio_styles import SinglePageStackedWidget, build_scroll_area

_CREATE_PROGRAMMING_BLOCK = "Create Programming Block"

# Five tabs, five questions. No drill-down, no landing hub of cards —
# picking a tab shows its answer immediately. Icons are small markers
# next to each label, not decoration — labels stay short and plain.
_TAB_TITLES = ["🌙 Tonight", "🕒 Programming", "📢 Commercials", "⭐ Identity", "▶ Preview"]


def _build_tonight_tab(dialog, schedule):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 4, 2, 4)
    layout.setSpacing(10)

    if schedule is not None and schedule.has_data:
        layout.addWidget(build_schedule_timeline(schedule.channel_name, schedule.slots))
    else:
        layout.addWidget(
            build_info_card(
                "No lineup yet",
                "Once this channel is playing, tonight's lineup will show up here.",
            )
        )

    quick_row = QLabel("Quick Actions")
    quick_row.setObjectName("sectionHeader")
    layout.addWidget(quick_row)
    action_cards = [
        build_info_card(
            suggestion.title,
            suggestion.description,
            buttons=[
                (
                    "Try It",
                    lambda checked=False, s=suggestion: show_preview_dialog(
                        dialog, s.title, s.description
                    ),
                )
            ],
        )
        for suggestion in QUICK_ACTION_SUGGESTIONS
    ]
    layout.addWidget(build_card_grid(action_cards))

    layout.addStretch(1)
    return page


def _build_commercials_tab(dialog, summary):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 4, 2, 4)
    layout.setSpacing(10)

    is_on = bool(summary and summary.commercials_enabled)
    status_label = summary.commercials_label if summary else "Commercials off"
    toggle_label = "Turn Off" if is_on else "Turn On"

    layout.addWidget(
        build_info_card(
            status_label,
            "Commercials play between programs on this channel when they're on."
            if is_on
            else "This channel plays straight through, with no commercial breaks.",
            buttons=[
                (
                    toggle_label,
                    lambda checked=False: show_preview_dialog(
                        dialog,
                        "Commercials",
                        "Turning commercials on or off for this channel isn't wired up yet — "
                        "this is a preview.",
                    ),
                ),
                (
                    "Change Mix",
                    lambda checked=False: show_preview_dialog(
                        dialog,
                        "Commercial Mix",
                        "Choosing which commercials play here isn't wired up yet — this is a preview.",
                    ),
                ),
            ],
        )
    )

    layout.addStretch(1)
    return page


_IDENTITY_ITEMS = [
    ("Channel Logo", "The on-screen bug for this channel.", None),
    ("Station IDs", "Short idents between programs.", None),
    ("Channel Look", "Colors, style, and on-air extras.", "Later"),
]


def _build_identity_tab(dialog):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 4, 2, 4)
    layout.setSpacing(10)
    cards = [
        build_info_card(
            title,
            note,
            badge_text=badge,
            buttons=[
                (
                    "Preview",
                    lambda checked=False, t=title, n=note: show_preview_dialog(dialog, t, n),
                )
            ],
        )
        for title, note, badge in _IDENTITY_ITEMS
    ]
    layout.addWidget(build_card_grid(cards))
    layout.addStretch(1)
    return page


def _build_preview_tab(dialog, channel_name):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 4, 2, 4)
    layout.setSpacing(10)
    layout.addWidget(
        build_info_card(
            "Live Channel Preview",
            f"See what's currently playing on {channel_name}, as a viewer would see it.",
            buttons=[
                (
                    "Preview",
                    lambda checked=False: show_preview_dialog(
                        dialog,
                        "Live Channel Preview",
                        "This will eventually show a live preview of what's currently "
                        "playing on this channel.",
                    ),
                )
            ],
        )
    )
    layout.addStretch(1)
    return page


def _preview_draft_dialog(parent, draft):
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


def _build_draft_card(parent, studio_dialog, drafts_path, draft, refresh):
    def _preview_draft(checked=False):
        _preview_draft_dialog(parent, draft)

    def _edit_draft(checked=False):
        open_programming_block_wizard(studio_dialog, drafts_path, existing_draft=draft, on_saved=refresh)

    def _delete_draft(checked=False):
        delete_draft(drafts_path, draft.key)
        refresh()

    meta_lines = [f"Airs {draft.time_preset_label}"] if draft.time_preset_label else []
    if draft.playback_style_label:
        meta_lines.append(f"Style: {draft.playback_style_label}")
    return build_info_card(
        draft.title,
        f"{len(draft.media_selections)} item(s) selected" if draft.media_selections else "No content selected yet",
        meta_lines=meta_lines,
        badge_text="Not On Air Yet",
        buttons=[
            ("Preview", _preview_draft),
            ("Edit", _edit_draft),
            ("Delete", _delete_draft),
        ],
    )


def build_drafts_section(parent, studio_dialog, drafts_path):
    """Draft Programming Block cards, reusable from both the Blocks page
    and a single channel's Blocks hub. `studio_dialog` is the main Channel
    Studio dialog (used read-only by the wizard's content step);
    `drafts_path` is where drafts are stored. Reads/writes only the
    isolated drafts file — never the real schedule.
    """
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
            [
                (
                    _CREATE_PROGRAMMING_BLOCK,
                    lambda checked=False: open_programming_block_wizard(
                        studio_dialog, drafts_path, on_saved=refresh
                    ),
                )
            ]
        )
        body_layout.addWidget(action_row)

        drafts = load_drafts(drafts_path)
        if not drafts:
            body_layout.addWidget(
                build_empty_state(
                    "No draft blocks yet. Create one to design a recurring lineup like Nick at Nite."
                )
            )
        else:
            cards = [
                _build_draft_card(parent, studio_dialog, drafts_path, draft, refresh) for draft in drafts
            ]
            body_layout.addWidget(build_card_grid(cards, columns=2))

    refresh()
    return section


def _build_identity_text(summary):
    """A friendly one-line identity blurb, not a stats dump."""
    if summary is None:
        return "A folder channel, ready to play."
    bits = [summary.headline]
    if summary.playback_order_label:
        bits.append(f"{summary.playback_order_label} order")
    return " · ".join(bits)


class ChannelEditorPreviewDialog(QDialog):
    """Running one channel: five flat tabs, no drill-down.

    Tonight, Programming, Commercials, Identity, and Preview each answer
    one question about this channel. Everything here is a mock aside
    from Programming's draft blocks, which read and write Channel
    Studio's own isolated drafts file — never the real schedule.
    """

    def __init__(
        self,
        channel_info,
        summary=None,
        schedule=None,
        parent=None,
        studio_dialog=None,
        drafts_path=None,
        initial_tab=0,
    ):
        super().__init__(parent)
        self._studio_dialog = studio_dialog
        self._drafts_path = drafts_path
        channel_name = channel_info.get("name", "Channel")
        self.setWindowTitle(channel_name)
        self.resize(820, 500)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)

        header = QLabel(f"{channel_name} · Channel {channel_info.get('default_number', '')}")
        header.setObjectName("sectionHeader")
        outer.addWidget(header)

        identity = QLabel(_build_identity_text(summary))
        identity.setObjectName("sectionNote")
        identity.setWordWrap(True)
        outer.addWidget(identity)

        tab_row, _group = build_tab_row(_TAB_TITLES, self._show_tab, initial_index=initial_tab)
        outer.addWidget(tab_row)

        self._stack = SinglePageStackedWidget()
        self._stack.addWidget(_build_tonight_tab(self, schedule))
        self._stack.addWidget(build_drafts_section(self, self._studio_dialog, self._drafts_path))
        self._stack.addWidget(_build_commercials_tab(self, summary))
        self._stack.addWidget(_build_identity_tab(self))
        self._stack.addWidget(_build_preview_tab(self, channel_name))
        self._stack.setCurrentIndex(initial_tab)

        outer.addWidget(build_scroll_area(self._stack), 1)

        back_btn = QPushButton("←  Back")
        back_btn.clicked.connect(self.accept)
        outer.addWidget(back_btn, 0, Qt.AlignLeft)

    def _show_tab(self, index):
        self._stack.setCurrentIndex(index)

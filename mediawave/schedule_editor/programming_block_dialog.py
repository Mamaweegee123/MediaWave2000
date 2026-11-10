"""Programming Blocks UI: a Channel Studio screen, not a separate
application with its own layout language.

This dialog deliberately does NOT define its own visual system. It
reuses Channel Studio's actual, already-shipped components:

- `mediawave.channel_studio.channel_studio_widgets`: FlowLayout (the
  same responsive-grid mechanism the Choose Channel dashboard uses --
  channel_grid.py), build_page_header (the "dialogTitle" + "sectionNote"
  page heading every Channel Studio page uses).
- `mediawave.studio.styles`: apply_card_shadow (the same drop shadow
  channel_card.py's own dashboard tiles use), style_setup_button/
  style_choice_button (Channel Studio's actual button treatments),
  build_scroll_area (a QScrollArea whose viewport paints the app's own
  dark background instead of the platform-default gray -- this is what
  removes the old "card floating over a gray rectangle" problem).
- `mediawave.studio.action_bar`: build_action_bar, the same persistent
  footer chrome (`studioActionBar`) other Studio workspaces use.
- `mediawave.studio.spacing`: OUTER_MARGIN/CONTROL_SPACING, the same
  page-level margins Channel Studio's own setup pages use.
- `mediawave.theme_tokens`: the literal SW_* palette every Channel
  Studio screen is themed from.

`_channel_studio_stylesheet()` below mirrors channelsurfer2000.py's
`build_themed_dialog_stylesheet()` for exactly the object-name selectors
this dialog needs ("sectionCard", "dialogTitle", "sectionHeader",
"sectionNote"/"fieldHelp", "statusBadge", QListWidget, QScrollBar). It
can't import that function directly: mediawave/schedule_editor, like
mediawave/studio (see action_bar.py's own `_BAR_STYLE` docstring),
deliberately never imports channelsurfer2000.py, the app's top-level
entry script (mediawave/studio/sidebar.py documents why that boundary
exists). The values below come from `mediawave.theme_tokens`, the same
tokens that function itself is built from -- not new, invented numbers.

Two EXPLICIT modes, both rendered by the SAME browser (no second page):

- MODE_LIBRARY: opened with no valid Open Time target. Browse, create,
  edit, duplicate, and delete blocks. No Fill action exists at all --
  not disabled, not hidden, simply not built. A card click opens the
  editor.
- MODE_FILL: opened with a real, editable Open Time gap selected
  (dialog.py's _programming_blocks_fill_target is the single source of
  truth for what qualifies). A card click SELECTS a block using the
  exact treatment Channel Studio's own nav-rail selection already uses
  (a 3px accent-colored left border + translucent tint -- see
  style_nav_item in mediawave/studio/styles.py) -- no navigation, no
  draft mutation. The bottom bar gains one primary action, "Fill Open
  Time", which resolves the selected block against the full catalog and
  hands the complete lineup to previewed_lineup() for dialog.py to run
  through the existing single AutoFillBlockCommand path. There is no
  separate Schedule Review/confirmation page -- the browser itself is
  the selection screen, in both modes.

Per-show accent bars (editor's Included Shows tray) still use the
guide's own MEDIA_TYPE_ACCENTS (program_block.py) for "tv" -- unrelated
to this pass, unchanged from the prior color-source-of-truth fix.
"""

import os
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..channel_studio.channel_studio_widgets import FlowLayout, build_page_header
from ..studio.action_bar import build_action_bar
from ..studio.spacing import CONTROL_SPACING, OUTER_MARGIN
from ..studio.styles import apply_card_shadow, build_scroll_area, style_choice_button, style_setup_button
from ..theme_tokens import (
    SW_ACCENT,
    SW_BG,
    SW_CARD_BG,
    SW_CARD_BORDER,
    SW_HEADER,
    SW_INPUT_BG,
    SW_INPUT_TEXT,
    SW_TEXT,
    SW_TEXT_DIM,
)
from .autofill_dialog import _build_placement_row, _format_duration_long
from .draft_model import format_time_range
from .program_block import MEDIA_TYPE_ACCENTS
from .programming_blocks import (
    BEHAVIOR_ROTATE_SHOWS,
    ProgrammingBlock,
    empty_programming_blocks_data,
    new_block_id,
    resolve_programming_block,
)
from ..show_identity import (
    SHOW_BEHAVIOR_RANDOM,
    SHOW_BEHAVIOR_SEQUENTIAL,
    add_folder_show_rule,
    canonicalize_show_keys,
    empty_registry,
    group_catalog_by_show,
    merge_shows,
    rename_show,
    set_show_behavior,
    show_behavior_for,
)
from .put_on_air_picker import format_duration_minutes, show_summary

MODE_LIBRARY = "library"
MODE_FILL = "fill"

# A rotation type label, matching the detail strip's own "Fair rotation"
# wording -- BEHAVIOR_ROTATE_SHOWS is the only rotation behavior that
# exists today, so this is a constant, not a per-block lookup.
_ROTATION_LABEL = "Fair Rotation"


def _rgba(color, alpha=255):
    return f"rgba({color.red()},{color.green()},{color.blue()},{alpha})"


def _channel_studio_stylesheet():
    """See module docstring -- a literal reduction of channelsurfer2000.py's
    build_themed_dialog_stylesheet(), built from mediawave.theme_tokens,
    covering only the selectors this dialog's own widgets use.
    """
    bg = _rgba(SW_BG)
    card = _rgba(SW_CARD_BG)
    card_border = _rgba(SW_CARD_BORDER, 110)
    card_border_strong = _rgba(SW_CARD_BORDER, 160)
    text = _rgba(SW_TEXT)
    dim = _rgba(SW_TEXT_DIM)
    header = _rgba(SW_HEADER)
    input_bg = _rgba(SW_INPUT_BG)
    input_text = _rgba(SW_INPUT_TEXT)
    return f"""
        QDialog {{ background: {bg}; }}
        QWidget#advScrollContainer, QWidget#advPageContent, QWidget#dialogScrollContent {{
            background: {bg};
        }}
        QWidget#dialogCard, QWidget#sectionCard {{
            background: {card};
            border: 1px solid {card_border};
            border-radius: 10px;
        }}
        QLabel#dialogTitle {{
            color: {header}; font-size: 20px; font-weight: 700; background: transparent;
        }}
        QLabel#sectionHeader, QLabel#sectionTitle {{
            color: {header}; font-size: 14px; font-weight: 700; background: transparent;
        }}
        QLabel#dialogNote, QLabel#sectionNote, QLabel#fieldHelp, QLabel#metaLabel {{
            color: {dim}; font-size: 12px; background: transparent;
        }}
        QLabel#statusBadge {{
            color: rgba(148, 196, 255, 200);
            background: rgba(68, 108, 235, 40);
            border: 1px solid rgba(68, 108, 235, 80);
            border-radius: 8px;
            font-size: 10px;
            font-weight: 600;
            padding: 1px 7px;
        }}
        QLabel {{ color: {text}; background: transparent; }}
        QLineEdit, QTextEdit {{
            min-height: 30px;
            padding: 4px 9px;
            border-radius: 6px;
            border: 1px solid {card_border_strong};
            background: {input_bg};
            color: {input_text};
        }}
        QPushButton {{
            min-height: 32px;
            padding: 5px 16px;
            border-radius: 7px;
            border: 1px solid {card_border_strong};
            color: {text};
            background: rgba(30, 38, 90, 220);
            font-size: 12px;
        }}
        QPushButton:hover, QPushButton:focus {{
            border: 1px solid {_rgba(SW_CARD_BORDER, 220)};
            background: rgba(50, 70, 160, 240);
            color: white;
        }}
        QScrollArea {{ border: none; background: transparent; }}
        QScrollBar:vertical {{
            background: rgba(22, 26, 58, 120); width: 10px; margin: 2px; border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(96, 144, 255, 160); min-height: 24px; border-radius: 5px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar:horizontal {{
            background: rgba(22, 26, 58, 120); height: 8px; margin: 2px; border-radius: 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: rgba(96, 144, 255, 160); min-width: 24px; border-radius: 4px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
    """


# No existing Channel Studio icon-button pattern to reuse yet (overflow
# menus/remove-row glyphs aren't a solved case elsewhere) -- this is the
# one bit of genuinely new, minimal chrome in this module, derived from
# the same tokens rather than arbitrary numbers.
_ICON_BUTTON_STYLE = (
    f"QToolButton {{ color: {_rgba(SW_TEXT)}; background: rgba(255,255,255,10);"
    f" border: 1px solid {_rgba(SW_CARD_BORDER, 55)}; border-radius: 8px; font-size: 13px; padding: 5px; min-width: 26px; }}"
    f"QToolButton::menu-indicator {{ image: none; width: 0px; }}"
    f"QToolButton:hover {{ border-color: {_rgba(SW_ACCENT)}; background: rgba(96, 144, 255, 45); }}"
)

# The card's selected state -- a literal copy of style_nav_item's own
# "active" treatment (mediawave/studio/styles.py): a 3px accent-colored
# left border plus a translucent accent tint. Reused verbatim rather than
# inventing a new selection language for cards.
_SELECTED_CARD_STYLE = (
    "QFrame#sectionCard {"
    " background: rgba(68, 108, 235, 38);"
    " border: 1px solid rgba(96, 144, 255, 255);"
    " border-left: 3px solid rgba(96, 144, 255, 255);"
    " border-radius: 10px;"
    "}"
)

# A show row's "included" state -- the same style_nav_item-derived accent
# treatment _SELECTED_CARD_STYLE uses, applied to a plain row instead of a
# card, so a toggled-in show in the editor's Show Library reads with the
# same visual language as a selected block card.
_INCLUDED_ROW_STYLE = (
    "QFrame#showRow {"
    " background: rgba(68, 108, 235, 38);"
    " border: 1px solid rgba(96, 144, 255, 160);"
    " border-left: 3px solid rgba(96, 144, 255, 255);"
    " border-radius: 8px;"
    "}"
)
# A plain row gets no box of its own -- just a hairline bottom divider,
# the same "list of rows" language broadcast scheduling tools use. The
# accent tint above is reserved for the one state that's actually
# information (included/selected), not decoration on every row.
_ROW_STYLE = f"QFrame#showRow {{ background: transparent; border: none; border-bottom: 1px solid {_rgba(SW_CARD_BORDER, 60)}; border-radius: 0px; }}"

# No boxes for statistics: a broadcast-scheduling-style stat readout is
# a large number over a small caption, groups separated by a hairline
# divider -- not a bordered tile. Bordered panels are reserved for
# actual interactive controls and major content cards (sectionCard),
# per the "don't draw a rectangle for every fact" direction.
def _vertical_divider():
    line = QFrame()
    line.setFixedWidth(1)
    line.setStyleSheet(f"background: {_rgba(SW_CARD_BORDER, 90)};")
    return line


def _horizontal_divider():
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {_rgba(SW_CARD_BORDER, 70)};")
    return line


def _build_stat_group(value_text, label_text):
    """One metric ("5" over "Shows") as plain typography -- size and
    weight carry the hierarchy, not a border.
    """
    group = QVBoxLayout()
    group.setSpacing(1)
    value_lbl = QLabel(value_text)
    value_lbl.setStyleSheet(f"color: {_rgba(SW_TEXT)}; font-size: 19px; font-weight: 700; background: transparent;")
    group.addWidget(value_lbl)
    label_lbl = QLabel(label_text)
    label_lbl.setStyleSheet(
        f"color: {_rgba(SW_TEXT_DIM)}; font-size: 10px; font-weight: 600; letter-spacing: 0.5px; background: transparent;"
    )
    group.addWidget(label_lbl)
    return group


def _build_stats_row(pairs):
    """A row of stat groups (value/caption) separated by hairline
    vertical dividers -- the classic scheduling-software metrics strip,
    not a grid of boxed tiles.
    """
    row = QHBoxLayout()
    row.setSpacing(16)
    for index, (value_text, label_text) in enumerate(pairs):
        if index > 0:
            row.addWidget(_vertical_divider())
        row.addLayout(_build_stat_group(value_text, label_text))
    row.addStretch(1)
    return row


def _block_stats(block, items, show_identity_registry=None):
    """What a Programming Block actually IS, in numbers: how many of its
    shows are available in today's catalog, how many total episodes they
    carry, and the approximate combined runtime -- the same real
    ingredients resolve_programming_block draws from, computed directly
    here so a library card can show "what is this / how big is it"
    without resolving a full lineup just to answer that.

    `block.show_keys` is canonicalized through `show_identity_registry`
    first (Phase 5.5.2 step 4), same as resolve_programming_block --
    `items`' own show_key has been canonical since Phase 5.5.2 step 2, so
    an un-canonicalized legacy raw key would never match `shows` at all
    and silently read as "unavailable". `show_count`/`available_count`
    are the CANONICAL (deduplicated) counts -- several old raw aliases of
    one merged show count as one show here, matching resolve_programming_
    block's rotation (one turn per cycle, not one per alias).
    """
    registry = show_identity_registry if isinstance(show_identity_registry, dict) else empty_registry()
    canonical_show_keys = canonicalize_show_keys(block.show_keys, registry)
    shows = group_catalog_by_show(items)
    available_keys = [key for key in canonical_show_keys if key in shows]
    episode_count = 0
    total_seconds = 0
    for key in available_keys:
        episodes = shows[key].get("episodes") or []
        episode_count += len(episodes)
        total_seconds += sum(ep.get("duration", 0) or 0 for ep in episodes)
    return {
        "show_count": len(canonical_show_keys),
        "available_count": len(available_keys),
        "episode_count": episode_count,
        "total_seconds": total_seconds,
    }


class RenameShowDialog(QDialog):
    """Phase 5.5.3: a tiny, friendly correction moment -- "MediaWave got
    the name wrong; I fixed it." -- not a settings/metadata screen.
    Deliberately shows nothing but the show's current name and one input:
    no canonical ID, no raw key, no alias list, no filename/path, no
    registry language anywhere in the UI. `new_name()` is only meaningful
    after exec() == Accepted; it is always already trimmed.
    """

    def __init__(self, current_name, parent=None):
        super().__init__(parent)
        self._current_name = current_name or ""
        self.setWindowTitle("Rename Show")
        self.setModal(True)
        self.resize(380, 200)
        self.setStyleSheet(_channel_studio_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*OUTER_MARGIN)
        layout.setSpacing(CONTROL_SPACING)

        heading = QLabel("Rename Show")
        heading.setObjectName("dialogTitle")
        layout.addWidget(heading)

        context_lbl = QLabel(f"Currently “{self._current_name}”")
        context_lbl.setObjectName("sectionNote")
        context_lbl.setWordWrap(True)
        layout.addWidget(context_lbl)

        field_label = QLabel("Show name")
        field_label.setObjectName("fieldHelp")
        layout.addWidget(field_label)
        self._name_edit = QLineEdit(self._current_name)
        self._name_edit.selectAll()
        self._name_edit.textChanged.connect(self._refresh_validity)
        layout.addWidget(self._name_edit)

        helper = QLabel("This changes how the show appears in MediaWave. Your media files and folders will not be changed.")
        helper.setObjectName("fieldHelp")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        layout.addStretch(1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        style_choice_button(cancel_btn, False)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self._save_btn = QPushButton("Save Name")
        style_setup_button(self._save_btn)
        self._save_btn.clicked.connect(self.accept)
        button_row.addWidget(self._save_btn)
        layout.addLayout(button_row)

        self._refresh_validity()
        self._name_edit.setFocus()

    def _refresh_validity(self, *_args):
        self._save_btn.setEnabled(bool(self._name_edit.text().strip()))

    def new_name(self):
        return self._name_edit.text().strip()


class MergeShowsDialog(QDialog):
    """Phase 5.5.4: "MediaWave split this show incorrectly; I put it back
    together." Same tiny, friendly correction language as RenameShowDialog
    -- no canonical IDs, no raw keys, no paths, no "alias"/"registry"
    words anywhere. The starting show (whichever row's overflow menu
    opened this) is shown first, always included, and not wired to
    toggle -- it can never be removed from the merge. Each OTHER
    candidate is an ordinary toggleable show row (same _ShowRow class,
    same visual language, no episode-level detail). `candidates` is a
    list of {show_key, title, episode_count, season_count} dicts, already
    excluding movies and the starting show itself -- since each entry
    comes from one group_catalog_by_show() row, two aliases of the SAME
    canonical show can never appear as separate candidates.
    """

    def __init__(self, starting_show_key, starting_title, starting_episode_count, starting_season_count, candidates, parent=None):
        super().__init__(parent)
        self._starting_show_key = starting_show_key
        self._selected = {starting_show_key}
        self._rows_by_key = {}
        self._candidates_by_key = {candidate["show_key"]: candidate for candidate in candidates}
        self._starting_episode_count = starting_episode_count

        self.setWindowTitle("Merge Shows")
        self.setModal(True)
        self.resize(440, 560)
        self.setStyleSheet(_channel_studio_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*OUTER_MARGIN)
        layout.setSpacing(CONTROL_SPACING)

        heading = QLabel("Merge Shows")
        heading.setObjectName("dialogTitle")
        layout.addWidget(heading)

        context_lbl = QLabel("Combine show groups that MediaWave split apart.")
        context_lbl.setObjectName("sectionNote")
        context_lbl.setWordWrap(True)
        layout.addWidget(context_lbl)

        name_label = QLabel("Destination name")
        name_label.setObjectName("fieldHelp")
        layout.addWidget(name_label)
        self._name_edit = QLineEdit(starting_title)
        self._name_edit.selectAll()
        self._name_edit.textChanged.connect(self._refresh_validity)
        layout.addWidget(self._name_edit)

        groups_label = QLabel("Show groups")
        groups_label.setObjectName("fieldHelp")
        layout.addWidget(groups_label)

        list_container = QWidget()
        self._list_layout = QVBoxLayout(list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        list_scroll = build_scroll_area(list_container)
        list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(list_scroll, 1)

        starting_row = _ShowRow(starting_title, starting_episode_count, starting_season_count, _show_accent_color(), removable=False)
        starting_row.set_included(True)
        self._list_layout.addWidget(starting_row)
        self._rows_by_key[starting_show_key] = starting_row

        for candidate in candidates:
            row = _ShowRow(candidate["title"], candidate["episode_count"], candidate["season_count"], _show_accent_color(), removable=False)
            row.bind_toggle(lambda key=candidate["show_key"]: self._toggle_candidate(key))
            self._list_layout.addWidget(row)
            self._rows_by_key[candidate["show_key"]] = row

        self._summary_label = QLabel("")
        self._summary_label.setObjectName("fieldHelp")
        layout.addWidget(self._summary_label)

        helper = QLabel("These groups will appear as one show in MediaWave. Your files and folders will not be changed.")
        helper.setObjectName("fieldHelp")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        style_choice_button(cancel_btn, False)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self._merge_btn = QPushButton("Merge Shows")
        style_setup_button(self._merge_btn)
        self._merge_btn.clicked.connect(self.accept)
        button_row.addWidget(self._merge_btn)
        layout.addLayout(button_row)

        self._refresh_summary()
        self._refresh_validity()
        self._name_edit.setFocus()

    def _toggle_candidate(self, key):
        if key in self._selected:
            self._selected.discard(key)
        else:
            self._selected.add(key)
        row = self._rows_by_key.get(key)
        if row is not None:
            row.set_included(key in self._selected)
        self._refresh_summary()
        self._refresh_validity()

    def _refresh_summary(self):
        episode_total = self._starting_episode_count + sum(
            self._candidates_by_key[key]["episode_count"] for key in self._selected if key != self._starting_show_key
        )
        count = len(self._selected)
        episode_word = "episode" if episode_total == 1 else "episodes"
        group_word = "show group" if count == 1 else "show groups"
        self._summary_label.setText(f"{count} {group_word} · {episode_total} {episode_word}")

    def _refresh_validity(self, *_args):
        name_ok = bool(self._name_edit.text().strip())
        self._merge_btn.setEnabled(name_ok and len(self._selected) >= 2)

    def selected_show_keys(self):
        return list(self._selected)

    def final_name(self):
        return self._name_edit.text().strip()


_BEHAVIOR_CHOICES = [
    (None, "Use Channel Default", "Follow this channel's normal episode order."),
    (SHOW_BEHAVIOR_SEQUENTIAL, "Continue Sequentially", "Continue from the last episode placed sequentially for this show."),
    (SHOW_BEHAVIOR_RANDOM, "Random Episodes", "Choose a random episode whenever this show is scheduled."),
]

_BEHAVIOR_ROW_LABEL = {
    SHOW_BEHAVIOR_SEQUENTIAL: "Sequential",
    SHOW_BEHAVIOR_RANDOM: "Random",
}


class EpisodeBehaviorDialog(QDialog):
    """Phase 5.6: "how MediaWave should choose this show's episodes" as
    one property of the show, not a settings dashboard -- three radio
    choices, short helper copy, no mention of cursors/registry/aliases/
    canonical identity anywhere in the visible text. `current_behavior`
    is None/"sequential"/"random" (show_behavior_for's own return shape);
    `selected_behavior()` is only meaningful after exec() == Accepted.
    """

    def __init__(self, show_title, current_behavior, parent=None):
        super().__init__(parent)
        self._selected = current_behavior if current_behavior in (SHOW_BEHAVIOR_SEQUENTIAL, SHOW_BEHAVIOR_RANDOM) else None
        self.setWindowTitle("Episode Behavior")
        self.setModal(True)
        self.resize(400, 320)
        self.setStyleSheet(_channel_studio_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*OUTER_MARGIN)
        layout.setSpacing(CONTROL_SPACING)

        heading = QLabel("Episode Behavior")
        heading.setObjectName("dialogTitle")
        layout.addWidget(heading)

        context_lbl = QLabel(show_title)
        context_lbl.setObjectName("sectionNote")
        context_lbl.setWordWrap(True)
        layout.addWidget(context_lbl)

        self._group = QButtonGroup(self)
        for value, label, helper_text in _BEHAVIOR_CHOICES:
            radio = QRadioButton(label)
            radio.setChecked(value == self._selected)
            radio.toggled.connect(lambda checked, v=value: self._on_toggled(checked, v))
            layout.addWidget(radio)
            self._group.addButton(radio)
            helper = QLabel(helper_text)
            helper.setObjectName("fieldHelp")
            helper.setWordWrap(True)
            helper.setContentsMargins(20, 0, 0, 0)
            layout.addWidget(helper)

        layout.addStretch(1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        style_choice_button(cancel_btn, False)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save Behavior")
        style_setup_button(save_btn)
        save_btn.clicked.connect(self.accept)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

    def _on_toggled(self, checked, value):
        if checked:
            self._selected = value

    def selected_behavior(self):
        return self._selected


class _ShowRow(QFrame):
    """One show row -- the SAME visual language autofill_dialog.py's
    _build_placement_row already established for a Generated Lineup row
    (thin media-type accent bar, bold title, dim caption line), reused
    here for both of the editor's two lists instead of a checkbox
    checklist on one side and a bespoke "cart" row on the other:

    - Show Library (toggle mode): the ENTIRE row is clickable, toggling
      inclusion -- tinted with the same accent treatment a selected
      block card uses (_INCLUDED_ROW_STYLE) when included, instead of a
      native QCheckBox.
    - This Block (removable mode): a small remove (x) button instead of
      click-to-toggle -- removing a show here is a distinct, deliberate
      action from browsing the library.

    Phase 5.5.3/5.5.4: an optional small overflow (⋯) button exposes
    "Rename Show…" and/or "Merge Shows…" -- the entry points into show-
    identity correction, shared by both modes since they're the same
    widget class. The button itself, and each action within it, is
    absent entirely when its callback isn't bound (e.g. a context with
    no save path available), rather than shown disabled -- an action
    that can never work has no reason to be visible.
    """

    def __init__(self, title, episode_count, season_count, accent_color, removable=False, on_rename=None, on_merge=None, on_episode_behavior=None, behavior_label=None, parent=None):
        super().__init__(parent)
        self.setObjectName("showRow")
        self._included = False
        self._removable = removable
        self._on_toggle_cb = None
        if not removable:
            self.setCursor(Qt.PointingHandCursor)
        self._apply_style()

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 10, 0)
        outer.setSpacing(10)
        outer.addWidget(_accent_bar(accent_color))

        content = QVBoxLayout()
        content.setContentsMargins(0, 8, 0, 8)
        content.setSpacing(1)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {_rgba(SW_TEXT)}; font-size: 13px; font-weight: 700; background: transparent;")
        title_lbl.setWordWrap(True)
        content.addWidget(title_lbl)

        episode_word = "episode" if episode_count == 1 else "episodes"
        caption_bits = [f"{episode_count} {episode_word}"]
        if season_count:
            season_word = "season" if season_count == 1 else "seasons"
            caption_bits.append(f"{season_count} {season_word}")
        caption_lbl = QLabel("   ·   ".join(caption_bits))
        caption_lbl.setObjectName("fieldHelp")
        content.addWidget(caption_lbl)
        if behavior_label:
            behavior_lbl = QLabel(behavior_label)
            behavior_lbl.setObjectName("fieldHelp")
            behavior_lbl.setStyleSheet(f"color: {_rgba(SW_TEXT_DIM, 200)}; font-size: 11px; background: transparent;")
            content.addWidget(behavior_lbl)
        outer.addLayout(content, 1)

        if on_rename is not None or on_merge is not None or on_episode_behavior is not None:
            overflow_btn = QToolButton()
            overflow_btn.setText("⋯")
            overflow_btn.setToolTip("More")
            overflow_btn.setPopupMode(QToolButton.InstantPopup)
            overflow_btn.setStyleSheet(_ICON_BUTTON_STYLE)
            menu = QMenu(overflow_btn)
            if on_rename is not None:
                rename_action = menu.addAction("Rename Show…")
                # QAction.triggered emits triggered(bool checked=False).
                # on_rename is `lambda key=..., title=...: ...` -- PySide
                # fills as many of a connected callable's OWN parameters
                # as the signal provides, INCLUDING ones with defaults, so
                # connecting on_rename directly silently passed `checked`
                # (always False) as `key`, overwriting the real show_key
                # on every real click. This was the actual cause of
                # "Rename Show does nothing" -- the save ran, just against
                # a bogus key, so nothing visible ever changed. The
                # wrapper here has its OWN single (checked) parameter to
                # absorb that argument, then calls on_rename() with
                # truly zero args so on_rename's own defaults apply.
                rename_action.triggered.connect(lambda checked=False, cb=on_rename: cb())
            if on_merge is not None:
                merge_action = menu.addAction("Merge Shows…")
                merge_action.triggered.connect(lambda checked=False, cb=on_merge: cb())
            if on_episode_behavior is not None:
                behavior_action = menu.addAction("Episode Behavior…")
                behavior_action.triggered.connect(lambda checked=False, cb=on_episode_behavior: cb())
            overflow_btn.setMenu(menu)
            outer.addWidget(overflow_btn)

        self._remove_btn = None
        if removable:
            remove_btn = QPushButton("×")
            remove_btn.setFixedSize(22, 22)
            remove_btn.setStyleSheet(
                "QPushButton { color: rgba(138, 158, 212, 220); background: transparent; border: none; font-size: 15px; }"
                "QPushButton:hover { color: white; }"
            )
            outer.addWidget(remove_btn)
            self._remove_btn = remove_btn

    def bind_remove(self, callback):
        if self._remove_btn is not None:
            self._remove_btn.clicked.connect(callback)

    def bind_toggle(self, callback):
        self._on_toggle_cb = callback

    def set_included(self, included):
        if included == self._included:
            return
        self._included = included
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(_INCLUDED_ROW_STYLE if self._included else _ROW_STYLE)

    def mousePressEvent(self, event):
        if not self._removable and event.button() == Qt.LeftButton and self._on_toggle_cb:
            self._on_toggle_cb()
        super().mousePressEvent(event)


class _UnrecognizedFolderRow(QFrame):
    """One row in Fix Show Library's "Unrecognized Videos" section
    (Phase 5.5 discoverability pass) -- same visual language as _ShowRow
    (accent bar, bold title, dim caption), but for a FOLDER of movie/
    unclassified items rather than a recognized show: "N videos found"
    instead of an episode/season count, and its only overflow action is
    "Treat Folder as Show…". Never shows the folder's absolute path --
    just its basename, the same "no paths as primary content" rule every
    other correction dialog in this module follows.
    """

    def __init__(self, folder_display_name, video_count, on_treat_as_show=None, parent=None):
        super().__init__(parent)
        self.setObjectName("showRow")
        self.setStyleSheet(_ROW_STYLE)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 10, 0)
        outer.setSpacing(10)
        outer.addWidget(_accent_bar(_show_accent_color()))

        content = QVBoxLayout()
        content.setContentsMargins(0, 8, 0, 8)
        content.setSpacing(1)
        title_lbl = QLabel(folder_display_name)
        title_lbl.setStyleSheet(f"color: {_rgba(SW_TEXT)}; font-size: 13px; font-weight: 700; background: transparent;")
        title_lbl.setWordWrap(True)
        content.addWidget(title_lbl)

        video_word = "video" if video_count == 1 else "videos"
        caption_lbl = QLabel(f"{video_count} {video_word} found")
        caption_lbl.setObjectName("fieldHelp")
        content.addWidget(caption_lbl)
        outer.addLayout(content, 1)

        if on_treat_as_show is not None:
            overflow_btn = QToolButton()
            overflow_btn.setText("⋯")
            overflow_btn.setToolTip("More")
            overflow_btn.setPopupMode(QToolButton.InstantPopup)
            overflow_btn.setStyleSheet(_ICON_BUTTON_STYLE)
            menu = QMenu(overflow_btn)
            action = menu.addAction("Treat Folder as Show…")
            action.triggered.connect(lambda checked=False, cb=on_treat_as_show: cb())
            overflow_btn.setMenu(menu)
            outer.addWidget(overflow_btn)


class ShowLibraryCorrectionBrowserDialog(QDialog):
    """"Fix Show Library…" (Phase 5.5 discoverability pass): one compact
    screen that is the home for all three identity corrections -- Rename
    Show, Merge Shows, Treat Folder as Show -- reached from one visible
    button next to the Show Library heading, instead of requiring a user
    to already know an item was misparsed as a movie and that the flat
    Advanced… picker hides a right-click menu. Two minimal sections
    behind a chip filter: "Shows" (group_catalog_by_show's own TV
    grouping, the same _ShowRow treatment/overflow menu the editor's own
    Show Library uses) and "Unrecognized Videos" (movie/unclassified
    items grouped by containing folder, each a _UnrecognizedFolderRow).
    Not a metadata-management dashboard: no absolute paths as primary
    content, no episode file lists, no raw keys or registry language
    anywhere in the visible text.

    Every correction here saves through the EXACT SAME callbacks
    (`on_rename_show`/`on_merge_shows`/`on_treat_folder_as_show`) the
    owning ProgrammingBlockLibraryDialog's row overflow menus already
    use -- there is no second mutation path. Those callbacks already
    update the parent's own `_items`/`_show_identity_registry` and
    refresh its library cards and currently-open editor page as a side
    effect of succeeding; this browser just re-reads the parent's
    current state (via `items_get`/`registry_get`) after each success to
    refresh its own two lists.
    """

    def __init__(self, items_get, registry_get, on_rename_show, on_merge_shows, on_treat_folder_as_show, on_episode_behavior=None, parent=None):
        super().__init__(parent)
        self._items_get = items_get
        self._registry_get = registry_get
        self._on_rename_show = on_rename_show
        self._on_merge_shows = on_merge_shows
        self._on_treat_folder_as_show = on_treat_folder_as_show
        self._on_episode_behavior = on_episode_behavior
        self._items = items_get()
        self._shows = group_catalog_by_show(self._items)
        self._mode = "Shows"

        self.setWindowTitle("Fix Show Library")
        self.setModal(True)
        self.resize(520, 640)
        self.setStyleSheet(_channel_studio_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*OUTER_MARGIN)
        layout.setSpacing(CONTROL_SPACING)

        heading = QLabel("Fix Show Library")
        heading.setObjectName("dialogTitle")
        layout.addWidget(heading)

        subtitle = QLabel("Correct names and grouping without changing your media files.")
        subtitle.setObjectName("sectionNote")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(6)
        self._chips = {}
        for mode in ("Shows", "Unrecognized Videos"):
            chip = QPushButton(mode)
            chip.setCheckable(True)
            chip.setChecked(mode == self._mode)
            chip.clicked.connect(lambda checked=False, m=mode: self._set_mode(m))
            chip_row.addWidget(chip)
            self._chips[mode] = chip
        chip_row.addStretch(1)
        layout.addLayout(chip_row)

        list_container = QWidget()
        self._list_layout = QVBoxLayout(list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)
        list_scroll = build_scroll_area(list_container)
        list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(list_scroll, 1)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton("Close")
        style_choice_button(close_btn, False)
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

        self._refresh()

    def _set_mode(self, mode):
        self._mode = mode
        for name, chip in self._chips.items():
            chip.setChecked(name == mode)
        self._refresh()

    def _unrecognized_groups(self):
        """{(channel_id, folder_path): {...}} for every movie/
        unclassified item, grouped by its containing folder -- the same
        grouping PutOnAirPickerDialog's context-menu entry point uses
        (one row per distinct folder, not per file).
        """
        groups = {}
        for item in self._items:
            if item.get("media_type") == "tv":
                continue
            folder_path = os.path.dirname(item.get("path", ""))
            channel_id = item.get("channel_id") or ""
            key = (channel_id, folder_path)
            if key not in groups:
                groups[key] = {
                    "channel_id": channel_id,
                    "catalog_root": item.get("catalog_root") or "",
                    "folder_path": folder_path,
                    "title": os.path.basename(folder_path) or folder_path,
                    "items": [],
                }
            groups[key]["items"].append(item)
        return groups

    def _refresh(self):
        while self._list_layout.count() > 1:
            entry = self._list_layout.takeAt(0)
            if entry.widget():
                entry.widget().deleteLater()

        if self._mode == "Shows":
            shows = sorted(self._shows.values(), key=lambda show: show["title"].lower())
            if not shows:
                placeholder = QLabel("No shows in the catalog yet.")
                placeholder.setObjectName("fieldHelp")
                self._list_layout.insertWidget(0, placeholder)
                return
            registry = self._registry_get()
            for show in shows:
                on_rename = (lambda key=show["show_key"], title=show["title"]: self._rename_clicked(key, title)) if self._on_rename_show is not None else None
                on_merge = (lambda key=show["show_key"], title=show["title"]: self._merge_clicked(key, title)) if self._on_merge_shows is not None else None
                on_behavior = (lambda key=show["show_key"], title=show["title"]: self._episode_behavior_clicked(key, title)) if self._on_episode_behavior is not None else None
                behavior_label = _BEHAVIOR_ROW_LABEL.get(show_behavior_for(show["show_key"], registry))
                row = _ShowRow(show["title"], show["episode_count"], show["season_count"], _show_accent_color(), removable=False, on_rename=on_rename, on_merge=on_merge, on_episode_behavior=on_behavior, behavior_label=behavior_label)
                self._list_layout.insertWidget(self._list_layout.count() - 1, row)
        else:
            groups = sorted(self._unrecognized_groups().values(), key=lambda group: group["title"].lower())
            if not groups:
                placeholder = QLabel("No unrecognized videos found.")
                placeholder.setObjectName("fieldHelp")
                self._list_layout.insertWidget(0, placeholder)
                return
            for group in groups:
                on_treat = (lambda g=group: self._treat_folder_clicked(g)) if self._on_treat_folder_as_show is not None else None
                row = _UnrecognizedFolderRow(group["title"], len(group["items"]), on_treat_as_show=on_treat)
                self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _rename_clicked(self, show_key, current_title):
        dialog = RenameShowDialog(current_title, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        new_name = dialog.new_name()
        if not new_name or new_name == current_title:
            return
        ok, error = self._on_rename_show(show_key, new_name)
        if ok:
            self._sync_after_correction()
        else:
            QMessageBox.warning(self, "Couldn't rename this show", error or "An unknown error occurred.")

    def _merge_clicked(self, show_key, current_title):
        show = self._shows.get(show_key)
        starting_episode_count = show["episode_count"] if show else 0
        starting_season_count = show["season_count"] if show else None
        candidates = [
            {"show_key": key, "title": candidate["title"], "episode_count": candidate["episode_count"], "season_count": candidate["season_count"]}
            for key, candidate in sorted(self._shows.items(), key=lambda pair: pair[1]["title"].lower())
            if key != show_key
        ]
        dialog = MergeShowsDialog(show_key, current_title, starting_episode_count, starting_season_count, candidates, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        selected_keys = dialog.selected_show_keys()
        final_name = dialog.final_name()
        if len(set(selected_keys)) < 2 or not final_name:
            return
        ok, error = self._on_merge_shows(selected_keys, final_name)
        if ok:
            self._sync_after_correction()
        else:
            QMessageBox.warning(self, "Couldn't merge these shows", error or "An unknown error occurred.")

    def _episode_behavior_clicked(self, show_key, current_title):
        current_behavior = show_behavior_for(show_key, self._registry_get())
        dialog = EpisodeBehaviorDialog(current_title, current_behavior, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        new_behavior = dialog.selected_behavior()
        if new_behavior == current_behavior:
            return
        ok, error = self._on_episode_behavior(show_key, new_behavior, current_title)
        if ok:
            self._sync_after_correction()
        else:
            QMessageBox.warning(self, "Couldn't save episode behavior", error or "An unknown error occurred.")

    def _treat_folder_clicked(self, group):
        # Local import: put_on_air_picker imports from this module
        # (ProgrammingBlockLibraryDialog), so importing TreatFolderAsShowDialog
        # at module scope here would be circular. Same deferred-import
        # pattern put_on_air_picker._pick_programming_block already uses.
        from .put_on_air_picker import TreatFolderAsShowDialog

        folder_items = group["items"]
        corrected_keys = {entry["show_key"] for entry in folder_items if entry.get("show_identity_source") == "override"}
        if len(corrected_keys) > 1:
            QMessageBox.warning(
                self,
                "Multiple shows found in this folder",
                "This folder already contains more than one corrected show. Use Merge Shows to combine them first, then try again.",
            )
            return
        target_show_key = next(iter(corrected_keys), None)
        provisional_keys = sorted({entry["raw_show_key"] for entry in folder_items if entry.get("show_identity_source") != "override"})
        dialog = TreatFolderAsShowDialog(group["title"], len(folder_items), folder_path_hint=group["title"], parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        final_name = dialog.new_show_name()
        if not final_name:
            return
        ok, error = self._on_treat_folder_as_show(group["channel_id"], group["catalog_root"], group["folder_path"], final_name, target_show_key, provisional_keys)
        if ok:
            self._sync_after_correction()
        else:
            QMessageBox.warning(self, "Couldn't create this show", error or "An unknown error occurred.")

    def _sync_after_correction(self):
        self._items = self._items_get()
        self._shows = group_catalog_by_show(self._items)
        self._refresh()


def _accent_bar(color, width=4):
    """A thin colored bar -- the exact visual pattern autofill_dialog.py's
    _build_placement_row already uses for a program's media-type accent
    (program_block.py's MEDIA_TYPE_ACCENTS), reused here as the identity
    cue for an included show row in the editor. No plates, no icons, no
    generated artwork.
    """
    bar = QFrame()
    bar.setFixedWidth(width)
    bar.setStyleSheet(f"background: {color}; border-top-left-radius: 4px; border-bottom-left-radius: 4px;")
    return bar


def _show_accent_color():
    """The SAME accent the main guide/grid uses for a "tv" program
    (program_block.py's MEDIA_TYPE_ACCENTS, the identical lookup
    autofill_dialog.py's _build_placement_row uses) -- every show reachable
    here is media_type == "tv" (group_catalog_by_show filters to exactly
    that), so this is a constant, not a per-show color.
    """
    return MEDIA_TYPE_ACCENTS["tv"][1]


class _BlockCard(QFrame):
    """A large Programming Block content card -- a miniature television
    station's own identity card, not a checklist summary: name,
    description, a 2x2 row of real metric tiles (Shows/Episodes/Runtime/
    Rotation, the same "this is substantial" idea Channel Studio's own
    dashboard cards lean on), and a short "Featuring" preview of what's
    actually programmed on it. Built to the same visual weight as
    Channel Studio's own dashboard channel cards (channel_card.py):
    fixed width, "sectionCard" chrome + drop shadow (apply_card_shadow),
    generous padding, room left for metadata that doesn't exist yet
    (artwork, tags, favorites, last-edited...) without another redesign.
    The ENTIRE card is clickable (mousePressEvent below); the only
    button is the overflow (...) menu for Duplicate/Delete. Qt already
    routes a click on that QToolButton to itself before this frame ever
    sees it, so no manual hit-testing is needed to keep the two from
    conflicting.
    """

    CARD_WIDTH = 320

    clicked = Signal()

    def __init__(self, block, stats, shows, canonical_show_keys=None, parent=None):
        super().__init__(parent)
        self._block = block
        self._selected = False
        self.setObjectName("sectionCard")
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(self.CARD_WIDTH)
        apply_card_shadow(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        name_lbl = QLabel(block.name)
        name_lbl.setObjectName("sectionHeader")
        name_lbl.setWordWrap(True)
        title_row.addWidget(name_lbl, 1)

        overflow_btn = QToolButton()
        overflow_btn.setText("⋮")
        overflow_btn.setToolTip("More")
        overflow_btn.setPopupMode(QToolButton.InstantPopup)
        overflow_btn.setStyleSheet(_ICON_BUTTON_STYLE)
        menu = QMenu(overflow_btn)
        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(self._on_duplicate)
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self._on_delete)
        overflow_btn.setMenu(menu)
        title_row.addWidget(overflow_btn, 0, Qt.AlignTop)
        layout.addLayout(title_row)

        if block.description:
            desc_lbl = QLabel(block.description)
            desc_lbl.setObjectName("sectionNote")
            desc_lbl.setWordWrap(True)
            layout.addWidget(desc_lbl)

        if stats["available_count"] < stats["show_count"]:
            missing = stats["show_count"] - stats["available_count"]
            warning_lbl = QLabel(f"{missing} show{'' if missing == 1 else 's'} unavailable in today's catalog")
            warning_lbl.setObjectName("fieldHelp")
            warning_lbl.setWordWrap(True)
            layout.addWidget(warning_lbl)

        layout.addWidget(_horizontal_divider())

        # A single metrics strip -- what this block actually IS and how
        # big it is -- as plain typography over a hairline divider, not
        # a grid of boxed tiles.
        layout.addLayout(
            _build_stats_row(
                [
                    (str(stats["show_count"]), "Shows"),
                    (str(stats["episode_count"]), "Episodes"),
                    (_format_duration_long(stats["total_seconds"]), "Runtime"),
                    (_ROTATION_LABEL.split(" ")[0], "Rotation"),
                ]
            )
        )

        layout.addWidget(_horizontal_divider())

        # "Featuring": what's actually programmed on this station -- the
        # PRIMARY preview of a block's identity, not a row of tiny chips.
        # `canonical_show_keys` (Phase 5.5.2 step 4/5.5.3) is `block.
        # show_keys` already resolved through the show identity registry
        # -- `shows` (group_catalog_by_show's output) is canonical-keyed,
        # so looking a legacy raw key up in it directly would always miss
        # and fall back to an ugly raw-key fragment for any corrected
        # show. None (no registry available) falls back to the raw keys
        # unchanged, same as before this fix.
        featuring_label = QLabel("Featuring")
        featuring_label.setObjectName("fieldHelp")
        layout.addWidget(featuring_label)
        shown_keys = (canonical_show_keys if canonical_show_keys is not None else block.show_keys)[:3]
        for key in shown_keys:
            show_title = shows.get(key, {}).get("title") or key.split("::", 1)[-1][:40]
            line = QHBoxLayout()
            line.setSpacing(8)
            line.addWidget(_accent_bar(_show_accent_color(), width=3))
            name_only = QLabel(show_title)
            name_only.setObjectName("sectionNote")
            line.addWidget(name_only, 1)
            layout.addLayout(line)
        if stats["show_count"] > len(shown_keys):
            more = QLabel(f"+{stats['show_count'] - len(shown_keys)} more")
            more.setObjectName("fieldHelp")
            layout.addWidget(more)

        # Deliberate breathing room -- today's card doesn't need this
        # space, but a future one (artwork, tags, favorites, statistics)
        # will, without redesigning the card again.
        layout.addStretch(1)

        self._on_activate_cb = None
        self._on_duplicate_cb = None
        self._on_delete_cb = None

    def bind(self, on_activate, on_duplicate, on_delete):
        self._on_activate_cb = on_activate
        self._on_duplicate_cb = on_duplicate
        self._on_delete_cb = on_delete

    def set_selected(self, selected):
        if selected == self._selected:
            return
        self._selected = selected
        # An empty local stylesheet falls back to the dialog's own
        # inherited "QWidget#sectionCard" rule -- the card's own
        # stylesheet always wins over an ancestor's for this widget, so
        # this cleanly toggles between the two without fighting QSS
        # specificity.
        self.setStyleSheet(_SELECTED_CARD_STYLE if selected else "")

    def _on_duplicate(self):
        if self._on_duplicate_cb:
            self._on_duplicate_cb(self._block)

    def _on_delete(self):
        if self._on_delete_cb:
            self._on_delete_cb(self._block)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            if self._on_activate_cb:
                self._on_activate_cb(self._block)
        super().mousePressEvent(event)


class _EditorPage(QWidget):
    """Building a lineup, not filling out a form: a searchable Show
    Library on the left where clicking a row toggles it into the block
    (the whole row is the control, tinted when included -- no
    QCheckBox), and a live "This Block" lineup on the right showing
    exactly what's been assembled so far. Both sides use the SAME show
    row (_ShowRow) that already matches autofill_dialog.py's own
    Generated Lineup row style, so this reads as scheduling, not a
    checklist-into-shopping-cart flow. `on_save(block)` / `on_cancel()`
    are plain callbacks the owning dialog wires to its own navigation,
    since this is a QWidget page, not a QDialog.
    """

    def __init__(self, items, existing_block, on_save, on_cancel, show_identity_registry=None, on_rename_show=None, on_merge_shows=None, on_treat_folder_as_show=None, on_episode_behavior=None, parent=None):
        super().__init__(parent)
        self._items = items
        self._shows = group_catalog_by_show(items)
        self._existing_block = existing_block
        self._on_save = on_save
        self._on_cancel = on_cancel
        # Phase 5.5.3: the owning ProgrammingBlockLibraryDialog's
        # `on_rename_show(show_key, new_name) -> (ok, error)` -- this
        # page only ever collects the new name (RenameShowDialog) and
        # asks the parent to actually mutate/save the registry, since the
        # parent owns the canonical `_items`/registry state shared with
        # the library grid's cards. On success the parent calls back into
        # `apply_identity_update` below to refresh THIS page in place.
        self._on_rename_show = on_rename_show
        # Phase 5.5.4: same delegation shape as on_rename_show above --
        # `on_merge_shows(show_keys, display_name) -> (ok, error)`. This
        # page only collects the selection/name (MergeShowsDialog); the
        # parent mutates/saves and calls back into `apply_identity_update`
        # below to refresh THIS page in place.
        self._on_merge_shows = on_merge_shows
        # Phase 5.5 discoverability pass: `on_treat_folder_as_show(
        # channel_id, catalog_root, folder_path, display_name,
        # target_show_key, provisional_keys) -> (ok, error)` -- forwarded
        # straight to Fix Show Library's correction browser (this page
        # never opens Treat Folder as Show directly itself, since
        # unrecognized movie/unclassified items don't appear in the Show
        # Library list at all).
        self._on_treat_folder_as_show = on_treat_folder_as_show
        # Phase 5.6: same delegation shape -- `on_episode_behavior(
        # show_key, behavior, display_name) -> (ok, error)`.
        self._on_episode_behavior = on_episode_behavior
        # None means Fix Show Library… is unavailable in this context
        # (e.g. no save path) -- same None-means-unavailable contract as
        # on_rename_show/on_merge_shows.
        self._on_fix_show_library = None
        if on_rename_show is not None or on_merge_shows is not None or on_treat_folder_as_show is not None or on_episode_behavior is not None:
            self._on_fix_show_library = self._open_fix_show_library
        # Phase 5.5.2 step 4: canonicalize an existing block's stored
        # show_keys BEFORE seeding _included, so a block saved before its
        # show(s) were corrected still shows as included/matched against
        # `self._shows` (canonical-keyed since Phase 5.5.2 step 2) rather
        # than silently falling out of the "This Block" list. `_save`
        # below always persists whatever's in `_included`, so a plain
        # open-and-save of an old block naturally rewrites it to
        # canonical keys -- no separate migration step needed.
        registry = show_identity_registry if isinstance(show_identity_registry, dict) else empty_registry()
        self._show_identity_registry = registry
        self._included = dict.fromkeys(canonicalize_show_keys(existing_block.show_keys, registry)) if existing_block else {}
        self._library_rows_by_key = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*OUTER_MARGIN)
        layout.setSpacing(CONTROL_SPACING + 6)

        header = QHBoxLayout()
        back_btn = QPushButton("← Back")
        style_choice_button(back_btn, False)
        back_btn.clicked.connect(lambda: self._on_cancel())
        header.addWidget(back_btn)
        heading = QLabel("Edit Programming Block" if existing_block else "New Programming Block")
        heading.setObjectName("dialogTitle")
        header.addWidget(heading)
        header.addStretch(1)
        layout.addLayout(header)

        panes = QHBoxLayout()
        panes.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(9)
        left_header = QHBoxLayout()
        left_header.setSpacing(8)
        left_label = QLabel("Show Library")
        left_label.setObjectName("sectionHeader")
        left_header.addWidget(left_label)
        left_header.addStretch(1)
        # Phase 5.5 discoverability pass: a single visible destination for
        # all three identity corrections (Rename/Merge/Treat Folder as
        # Show), so a user never needs to already know a video was
        # misparsed as a movie or that Advanced… hides a right-click
        # menu. Absent when no save path exists, same "an action that
        # can never work has no reason to be visible" rule every other
        # correction entry point in this module follows.
        if self._on_fix_show_library is not None:
            fix_library_btn = QPushButton("Fix Show Library…")
            style_choice_button(fix_library_btn, False)
            fix_library_btn.clicked.connect(self._open_fix_show_library)
            left_header.addWidget(fix_library_btn)
        left.addLayout(left_header)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search shows…")
        self._search.textChanged.connect(self._populate_library)
        left.addWidget(self._search)

        library_scroll = QScrollArea()
        library_scroll.setWidgetResizable(True)
        library_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        library_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._library_container = QWidget()
        self._library_container.setStyleSheet("background: transparent;")
        self._library_layout = QVBoxLayout(self._library_container)
        self._library_layout.setContentsMargins(0, 0, 0, 0)
        self._library_layout.setSpacing(6)
        self._library_layout.addStretch(1)
        library_scroll.setWidget(self._library_container)
        left.addWidget(library_scroll, 1)
        panes.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(9)
        right_label = QLabel("This Block")
        right_label.setObjectName("sectionHeader")
        right.addWidget(right_label)
        self._name_edit = QLineEdit(existing_block.name if existing_block else "")
        self._name_edit.setPlaceholderText("Block name")
        self._name_edit.textChanged.connect(self._refresh_validity)
        right.addWidget(self._name_edit)
        self._description_edit = QTextEdit(existing_block.description if existing_block else "")
        self._description_edit.setPlaceholderText("Short description (optional)")
        self._description_edit.setFixedHeight(48)
        right.addWidget(self._description_edit)

        self._count_label = QLabel("")
        self._count_label.setObjectName("fieldHelp")
        right.addWidget(self._count_label)

        # A plain QScrollArea + persistent row widgets added directly to a
        # layout, NOT a QListWidget with setItemWidget: a QListWidgetItem's
        # sizeHint is queried before its embedded widget is ever shown/
        # laid out, which can silently collapse a row to near-zero height.
        # A real widget in a real layout lays itself out correctly with no
        # separate sizeHint bookkeeping to get wrong.
        included_scroll = QScrollArea()
        included_scroll.setWidgetResizable(True)
        included_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        included_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._included_container = QWidget()
        self._included_container.setStyleSheet("background: transparent;")
        self._included_layout = QVBoxLayout(self._included_container)
        self._included_layout.setContentsMargins(0, 0, 0, 0)
        self._included_layout.setSpacing(6)
        self._included_layout.addStretch(1)
        included_scroll.setWidget(self._included_container)
        right.addWidget(included_scroll, 1)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: rgba(255, 140, 140, 230); font-size: 11px;")
        self._error_label.setWordWrap(True)
        right.addWidget(self._error_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        style_choice_button(cancel_btn, False)
        cancel_btn.clicked.connect(lambda: self._on_cancel())
        button_row.addWidget(cancel_btn)
        self._save_btn = QPushButton("Save Block")
        style_setup_button(self._save_btn)
        self._save_btn.clicked.connect(self._save)
        button_row.addWidget(self._save_btn)
        right.addLayout(button_row)

        panes.addLayout(right, 2)
        layout.addLayout(panes, 1)

        self._populate_library()
        self._refresh_included()
        self._refresh_validity()

    def _populate_library(self):
        query = self._search.text().strip().lower()
        while self._library_layout.count() > 1:
            item = self._library_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._library_rows_by_key = {}

        shows = sorted(self._shows.values(), key=lambda show: show["title"].lower())
        matches = [show for show in shows if not query or query in show["title"].lower()]
        if not matches:
            placeholder = QLabel("No shows match your search." if query else "No shows in the catalog yet.")
            placeholder.setObjectName("fieldHelp")
            self._library_layout.insertWidget(0, placeholder)
            return

        for show in matches:
            episode_count, season_count = show_summary(show)
            on_rename = (lambda key=show["show_key"], title=show["title"]: self._rename_show_clicked(key, title)) if self._on_rename_show is not None else None
            on_merge = (lambda key=show["show_key"], title=show["title"]: self._merge_shows_clicked(key, title)) if self._on_merge_shows is not None else None
            on_behavior = (lambda key=show["show_key"], title=show["title"]: self._episode_behavior_clicked(key, title)) if self._on_episode_behavior is not None else None
            behavior_label = _BEHAVIOR_ROW_LABEL.get(show_behavior_for(show["show_key"], self._show_identity_registry))
            row = _ShowRow(show["title"], episode_count, season_count, _show_accent_color(), removable=False, on_rename=on_rename, on_merge=on_merge, on_episode_behavior=on_behavior, behavior_label=behavior_label)
            row.set_included(show["show_key"] in self._included)
            row.bind_toggle(lambda key=show["show_key"]: self._toggle_show(key))
            self._library_rows_by_key[show["show_key"]] = row
            self._library_layout.insertWidget(self._library_layout.count() - 1, row)

    def _toggle_show(self, key):
        if key in self._included:
            self._included.pop(key, None)
        else:
            self._included[key] = None
        row = self._library_rows_by_key.get(key)
        if row is not None:
            row.set_included(key in self._included)
        self._refresh_included()
        self._refresh_validity()

    def _remove_included(self, key):
        self._included.pop(key, None)
        row = self._library_rows_by_key.get(key)
        if row is not None:
            row.set_included(False)
        self._refresh_included()
        self._refresh_validity()

    def _refresh_included(self):
        # Clear every row widget except the trailing stretch item (index
        # 0 is that stretch, added once in __init__ and never removed).
        while self._included_layout.count() > 1:
            item = self._included_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for key in self._included:
            show = self._shows.get(key)
            title = show["title"] if show else key.split("::", 1)[-1]
            episode_count, season_count = show_summary(show) if show else (0, None)
            on_rename = (lambda k=key, t=title: self._rename_show_clicked(k, t)) if self._on_rename_show is not None else None
            on_merge = (lambda k=key, t=title: self._merge_shows_clicked(k, t)) if self._on_merge_shows is not None else None
            on_behavior = (lambda k=key, t=title: self._episode_behavior_clicked(k, t)) if self._on_episode_behavior is not None else None
            behavior_label = _BEHAVIOR_ROW_LABEL.get(show_behavior_for(key, self._show_identity_registry))
            row = _ShowRow(title, episode_count, season_count, _show_accent_color(), removable=True, on_rename=on_rename, on_merge=on_merge, on_episode_behavior=on_behavior, behavior_label=behavior_label)
            row.bind_remove(lambda _checked=False, k=key: self._remove_included(k))
            self._included_layout.insertWidget(self._included_layout.count() - 1, row)

        count = len(self._included)
        episode_total = sum((show_summary(self._shows[k])[0] if k in self._shows else 0) for k in self._included)
        total_seconds = sum(
            sum(ep.get("duration", 0) or 0 for ep in self._shows[k].get("episodes") or [])
            for k in self._included
            if k in self._shows
        )
        bits = [f"{count} show{'' if count == 1 else 's'}", f"{episode_total} episode{'' if episode_total == 1 else 's'}"]
        if total_seconds:
            bits.append(f"≈{_format_duration_long(total_seconds)}")
        if count:
            bits.append(_ROTATION_LABEL)
        self._count_label.setText("   ·   ".join(bits))

    def _rename_show_clicked(self, show_key, current_title):
        """RenameShowDialog collects the new name; this page never
        mutates/saves the registry itself -- it asks the owning
        ProgrammingBlockLibraryDialog (`_on_rename_show`) to, since the
        parent is what owns the canonical `_items`/registry state shared
        with the library grid's cards. Same-name (after trimming) is a
        deliberate no-op -- closing the dialog without writing a
        redundant registry update, per Phase 5.5.3's same-name rule.
        """
        if self._on_rename_show is None:
            return
        dialog = RenameShowDialog(current_title, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        new_name = dialog.new_name()
        if not new_name or new_name == current_title:
            return
        ok, error = self._on_rename_show(show_key, new_name)
        if not ok:
            QMessageBox.warning(self, "Couldn't rename this show", error or "An unknown error occurred.")

    def _open_fix_show_library(self):
        """Phase 5.5 discoverability pass: the one visible destination
        for all three corrections. Every correction made inside the
        browser saves through the SAME `_on_rename_show`/`_on_merge_
        shows`/`_on_treat_folder_as_show` callbacks a row's own overflow
        menu uses, which already call `apply_identity_update` on THIS
        page as a side effect of succeeding -- so by the time the browser
        closes (or even while it's still open), this page's own Show
        Library/Included Shows are already live-updated with no extra
        wiring needed here.
        """
        dialog = ShowLibraryCorrectionBrowserDialog(
            items_get=lambda: self._items,
            registry_get=lambda: self._show_identity_registry,
            on_rename_show=self._on_rename_show,
            on_merge_shows=self._on_merge_shows,
            on_treat_folder_as_show=self._on_treat_folder_as_show,
            on_episode_behavior=self._on_episode_behavior,
            parent=self,
        )
        dialog.exec()

    def _episode_behavior_clicked(self, show_key, current_title):
        """EpisodeBehaviorDialog collects the new behavior; this page
        never mutates/saves the registry itself -- same delegation shape
        as _rename_show_clicked. An unchanged selection is a deliberate
        no-op, same as Rename's same-name rule.
        """
        if self._on_episode_behavior is None:
            return
        current_behavior = show_behavior_for(show_key, self._show_identity_registry)
        dialog = EpisodeBehaviorDialog(current_title, current_behavior, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        new_behavior = dialog.selected_behavior()
        if new_behavior == current_behavior:
            return
        ok, error = self._on_episode_behavior(show_key, new_behavior, current_title)
        if not ok:
            QMessageBox.warning(self, "Couldn't save episode behavior", error or "An unknown error occurred.")

    def apply_identity_update(self, redirect_map, items, show_identity_registry):
        """Called by the owning ProgrammingBlockLibraryDialog right after
        ANY successful identity correction save -- Rename, Merge, or
        Treat Folder as Show all funnel through this ONE method (Phase
        5.5 consistency pass), so THIS already-open page reflects the
        correction immediately, no close/reopen needed. `items` is the
        freshly re-annotated catalog the parent computed. `redirect_map`
        is {old_show_key: new_canonical_show_key} for every show_key
        string that changed -- a rename's single old key, a merge's
        several absorbed keys, or a folder correction's provisional raw
        keys, all in the same shape -- so `_included`'s membership can be
        remapped and deduplicated through one shared code path regardless
        of which correction produced it. A show that was already included
        stays included under its new identity; two included shows that
        just merged collapse to one entry instead of duplicating or one
        silently vanishing.
        """
        self._items = items
        self._show_identity_registry = show_identity_registry if isinstance(show_identity_registry, dict) else empty_registry()
        self._shows = group_catalog_by_show(items)
        if any(key in redirect_map for key in self._included):
            remapped = {}
            for key, value in self._included.items():
                remapped[redirect_map.get(key, key)] = value
            self._included = remapped
        self._populate_library()
        self._refresh_included()
        self._refresh_validity()

    def _merge_shows_clicked(self, show_key, current_title):
        """MergeShowsDialog collects the additional show groups and the
        final name; this page never mutates/saves the registry itself --
        same delegation shape as _rename_show_clicked. Candidates are
        every OTHER row in `self._shows` (already canonical-keyed and
        movie-excluded by group_catalog_by_show, so two aliases of the
        SAME canonical show can never appear as separate candidates).
        """
        if self._on_merge_shows is None:
            return
        show = self._shows.get(show_key)
        starting_episode_count, starting_season_count = show_summary(show) if show else (0, None)
        candidates = [
            {
                "show_key": key,
                "title": candidate["title"],
                "episode_count": candidate["episode_count"],
                "season_count": candidate["season_count"],
            }
            for key, candidate in sorted(self._shows.items(), key=lambda pair: pair[1]["title"].lower())
            if key != show_key
        ]
        dialog = MergeShowsDialog(show_key, current_title, starting_episode_count, starting_season_count, candidates, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        selected_keys = dialog.selected_show_keys()
        final_name = dialog.final_name()
        if len(set(selected_keys)) < 2 or not final_name:
            return
        ok, error = self._on_merge_shows(selected_keys, final_name)
        if not ok:
            QMessageBox.warning(self, "Couldn't merge these shows", error or "An unknown error occurred.")

    def _refresh_validity(self, *_args):
        name = self._name_edit.text().strip()
        if not name:
            self._error_label.setText("Name is required.")
            self._save_btn.setEnabled(False)
        elif not self._included:
            self._error_label.setText("Choose at least one show.")
            self._save_btn.setEnabled(False)
        else:
            self._error_label.setText("")
            self._save_btn.setEnabled(True)

    def _save(self):
        name = self._name_edit.text().strip()
        if not name or not self._included:
            self._refresh_validity()
            return
        block_id = self._existing_block.id if self._existing_block else new_block_id()
        description = self._description_edit.toPlainText().strip()
        block = ProgrammingBlock(block_id, name, list(self._included.keys()), BEHAVIOR_ROTATE_SHOWS, description=description)
        self._on_save(block)


class ProgrammingBlockLibraryDialog(QDialog):
    """The single entry point for Programming Blocks: one Channel-Studio-
    styled browser, operating in one of two EXPLICIT modes (see module
    docstring) -- never a blend of management and scheduling controls in
    the same layout, and never a second page for Fill Mode.
    previewed_lineup() returns the complete resolved lineup once the
    user actually clicks Fill Open Time (exec() == Accepted); until then
    it's None, exactly the contract dialog.py's _programming_blocks_
    clicked already expects from AutoFillBlockDialog -- dialog.py itself
    still runs the ONE AutoFillBlockCommand via _try_auto_fill_block, so
    Undo/Redo, draft validation, and recent-media recording are untouched
    by this dialog.
    """

    def __init__(self, items, get_blocks, save_blocks, channel_number, channel_name, can_schedule, slot_start=None, slot_duration=None, show_identity_registry=None, show_identity_registry_save=None, channel_id=None, cursor_data=None, parent=None):
        super().__init__(parent)
        self._items = items
        self._get_blocks = get_blocks
        self._save_blocks = save_blocks
        self._channel_number = channel_number
        self._channel_name = channel_name
        self._mode = MODE_FILL if can_schedule else MODE_LIBRARY
        self._slot_start = slot_start
        self._slot_duration = slot_duration
        # Phase 5.6: forwarded into every resolve_programming_block call
        # below so a show saved as "sequential" can resolve its next
        # episode via the SAME shared cursor Schedule Show/sequential
        # Auto-Fill already read. None/None (a context with no channel
        # selected, e.g. pure Library Mode with no Open Time chosen)
        # preserves today's exact behavior -- see resolve_programming_
        # block's own docstring.
        self._channel_id = channel_id
        self._cursor_data = cursor_data
        # Phase 5.5.2 step 4 (now also Phase 5.5.3's live copy): threaded
        # into every resolution/stats call below so legacy raw show_keys
        # already-corrected blocks were saved with keep resolving
        # correctly. None/invalid normalizes to an empty registry, which
        # makes canonicalize_show_keys a no-op -- unchanged prior
        # behavior. Unlike step 4 (read-only), this is now REASSIGNED (
        # never mutated) by _apply_show_rename below after a successful
        # Rename Show save, so every subsequent resolution/stats call in
        # THIS dialog sees the correction immediately without needing to
        # reopen it -- the getter on the workspace side still owns the
        # source of truth for the NEXT time this dialog is opened.
        self._show_identity_registry = show_identity_registry if isinstance(show_identity_registry, dict) else empty_registry()
        # Phase 5.5.3: Rename Show's save path -- None means renaming
        # isn't available in this context (e.g. a test constructing this
        # dialog standalone), same None-means-unavailable contract as
        # every other callback here.
        self._show_identity_registry_save = show_identity_registry_save
        self._result_lineup = None
        self._selected_block_id = None
        self._cards_by_id = {}
        self._fill_btn = None
        self._detail_label = None
        self._preview_layout = None

        self.setWindowTitle("Fill Open Time" if self._mode == MODE_FILL else "Programming Blocks")
        self.setModal(True)
        # Wide enough that the default size already shows 3 columns of
        # CARD_WIDTH-320 cards (3*320 + 2*16 gaps + OUTER_MARGIN sides +
        # scrollbar) -- the window should never look mostly empty when
        # there are a few blocks to show.
        self.resize(1120, 720)
        self.setStyleSheet(_channel_studio_stylesheet())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)

        self._library_page = self._build_library_page()
        self._stack.addWidget(self._library_page)

    # ── persistence ──────────────────────────────────────────────────

    def _blocks(self):
        data = self._get_blocks() if self._get_blocks is not None else None
        return list((data or empty_programming_blocks_data()).get("blocks") or [])

    def _persist(self, blocks):
        if self._save_blocks is None:
            return True
        ok, error = self._save_blocks({"version": 1, "blocks": blocks})
        if not ok:
            QMessageBox.warning(self, "Couldn't save this block", error or "An unknown error occurred.")
        return ok

    # ── library page (the browser -- shared by both modes) ────────────

    def _build_library_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        header_wrap = QWidget()
        header_layout = QHBoxLayout(header_wrap)
        header_layout.setContentsMargins(OUTER_MARGIN[0], OUTER_MARGIN[1], OUTER_MARGIN[2], 0)
        header_layout.setSpacing(CONTROL_SPACING)
        header_layout.addWidget(self._build_header_block(), 1)
        new_btn = QPushButton("+ New Block")
        style_choice_button(new_btn, False)
        new_btn.clicked.connect(self._open_new_block)
        header_layout.addWidget(new_btn, 0, Qt.AlignTop)
        page_layout.addWidget(header_wrap)

        # The large content area IS the browser -- a responsive FlowLayout
        # grid (same mechanism channel_grid.py uses for the Choose Channel
        # dashboard: fixed-width cards wrap 3/2/1-per-row as space allows,
        # no manual column-count math) inside build_scroll_area(), which
        # paints the app's own dark layered background in the viewport
        # instead of Qt's default gray -- no more empty canvas behind one
        # small card.
        grid_content = QWidget()
        grid_layout = QVBoxLayout(grid_content)
        grid_layout.setContentsMargins(OUTER_MARGIN[0], 0, OUTER_MARGIN[2], OUTER_MARGIN[3])
        self._card_container = QWidget()
        self._card_layout = FlowLayout(self._card_container, margin=0, h_spacing=16, v_spacing=16)
        grid_layout.addWidget(self._card_container)

        # Fill Mode's richer "what happens if I use this" preview -- the
        # SAME browser, not a second page: appears below the grid once a
        # block is selected, built from _build_placement_row (the exact
        # Generated Lineup row style autofill_dialog.py already uses) so
        # "Next Up" reads like real scheduling, not a re-invented list.
        preview_container = QWidget()
        self._preview_layout = QVBoxLayout(preview_container)
        self._preview_layout.setContentsMargins(0, 16, 0, 0)
        self._preview_layout.setSpacing(0)
        grid_layout.addWidget(preview_container)

        grid_layout.addStretch(1)
        page_layout.addWidget(build_scroll_area(grid_content), 1)

        # Persistent bottom action bar (mediawave.studio.action_bar's own
        # "studioActionBar" chrome, the same footer other Studio
        # workspaces use) -- NEVER inside the scrollable content, always
        # visible regardless of card count/scroll depth.
        bar, buttons_by_key = build_action_bar(["back", "save"] if self._mode == MODE_FILL else ["back"])
        buttons_by_key["back"].clicked.connect(self.reject)
        if self._mode == MODE_FILL:
            self._fill_btn = buttons_by_key["save"]
            self._fill_btn.setText("Fill Open Time")
            self._fill_btn.clicked.connect(self._fill_open_time)
            self._detail_label = QLabel("")
            self._detail_label.setObjectName("fieldHelp")
            bar.layout().insertWidget(bar.layout().count() - 1, self._detail_label)
        page_layout.addWidget(bar)

        self._refresh_library()
        return page

    def _build_header_block(self):
        if self._mode == MODE_FILL:
            title = "Fill Open Time"
            subtitle = (
                f"Ch {self._channel_number} · {self._channel_name}\n"
                f"{format_time_range(self._slot_start, self._slot_start + self._slot_duration)} · {format_duration_minutes(self._slot_duration)} open\n"
                "Choose a Programming Block for this Open Time."
            )
        else:
            title = "Programming Blocks"
            subtitle = "Create reusable groups of shows for your channels. Each block rotates fairly through its included shows."
        return build_page_header(None, title, subtitle)

    def _refresh_library(self):
        while self._card_layout.count():
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards_by_id = {}

        blocks = sorted(self._blocks(), key=lambda b: b.name.lower())
        if not blocks:
            self._card_layout.addWidget(self._build_empty_state())
            self._update_bottom_bar()
            return

        # A deleted/renamed-away selection shouldn't silently linger.
        if self._selected_block_id not in {block.id for block in blocks}:
            self._selected_block_id = None

        shows = group_catalog_by_show(self._items)
        for block in blocks:
            stats = _block_stats(block, self._items, show_identity_registry=self._show_identity_registry)
            canonical_show_keys = canonicalize_show_keys(block.show_keys, self._show_identity_registry)
            card = _BlockCard(block, stats, shows, canonical_show_keys=canonical_show_keys)
            card.set_selected(block.id == self._selected_block_id)
            # Context-sensitive, explicit in code rather than inferred:
            # Fill Mode selects (no navigation, no draft mutation);
            # Library Mode opens the editor. Same browser either way.
            on_activate = self._select_block if self._mode == MODE_FILL else self._open_edit_block
            card.bind(on_activate, self._duplicate_block, self._confirm_delete_block)
            self._cards_by_id[block.id] = card
            self._card_layout.addWidget(card)
        self._update_bottom_bar()

    def _select_block(self, block):
        if self._mode != MODE_FILL:
            return
        self._selected_block_id = block.id
        for block_id, card in self._cards_by_id.items():
            card.set_selected(block_id == block.id)
        self._update_bottom_bar()

    def _update_bottom_bar(self):
        if self._fill_btn is None:
            return
        selected_block = next((b for b in self._blocks() if b.id == self._selected_block_id), None)
        self._fill_btn.setEnabled(selected_block is not None)
        self._fill_btn.setToolTip("" if selected_block is not None else "Select a Programming Block first.")
        self._detail_label.setText(self._selection_detail_text(selected_block) if selected_block is not None else "")
        self._refresh_preview_panel(selected_block)

    def _selection_detail_text(self, block):
        """A compact, secondary reassurance strip in the bottom bar
        itself (stays visible even once the fuller preview panel below
        the grid has scrolled out of view). Resolving on selection
        (rather than only on Fill Open Time) is cheap enough here since
        it's the same bounded lineup resolve_programming_block always
        computes, and it lets the strip reflect reality (e.g. "nothing
        schedulable right now") before the user commits.
        """
        plan = resolve_programming_block(block, self._items, self._slot_start, self._slot_duration, seed=0, show_identity_registry=self._show_identity_registry, channel_id=self._channel_id, cursor_data=self._cursor_data)
        canonical_show_count = len(canonicalize_show_keys(block.show_keys, self._show_identity_registry))
        lineup = plan.get("lineup") or []
        if not lineup:
            return f"{canonical_show_count} shows · nothing schedulable right now"
        filled = plan.get("filled_seconds", 0)
        leftover = plan.get("leftover_seconds", 0)
        bits = [f"{canonical_show_count} shows", "Fair rotation", f"Fills {format_duration_minutes(filled)}"]
        if leftover >= 30:
            bits.append(f"{format_duration_minutes(leftover)} remains open")
        return "   ·   ".join(bits)

    def _refresh_preview_panel(self, block):
        """Answers "what happens if I use this?" -- not a separate page,
        just a richer section of the same browser that appears below the
        grid once a block is selected: name/description, real metric
        tiles (Programs/Runtime/Shows/Rotation), and a Next Up preview
        built from the SAME _build_placement_row autofill_dialog.py's own
        Generated Lineup preview already uses. Resolving here is the same
        bounded computation _selection_detail_text already does for the
        bottom-bar strip -- cheap, and it means the panel never lies
        about what's actually schedulable.
        """
        if self._preview_layout is None:
            return
        while self._preview_layout.count():
            item = self._preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if block is None:
            return

        panel = QFrame()
        panel.setObjectName("sectionCard")
        panel.setFrameShape(QFrame.NoFrame)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(10)

        title_lbl = QLabel(block.name)
        title_lbl.setObjectName("sectionHeader")
        panel_layout.addWidget(title_lbl)
        if block.description:
            desc_lbl = QLabel(block.description)
            desc_lbl.setObjectName("sectionNote")
            desc_lbl.setWordWrap(True)
            panel_layout.addWidget(desc_lbl)

        plan = resolve_programming_block(block, self._items, self._slot_start, self._slot_duration, seed=0, show_identity_registry=self._show_identity_registry, channel_id=self._channel_id, cursor_data=self._cursor_data)
        lineup = plan.get("lineup") or []
        stats = _block_stats(block, self._items, show_identity_registry=self._show_identity_registry)

        panel_layout.addWidget(_horizontal_divider())
        panel_layout.addLayout(
            _build_stats_row(
                [
                    (str(len(lineup)), "Programs"),
                    (_format_duration_long(plan.get("filled_seconds", 0)), "Runtime"),
                    (str(stats["available_count"]), "Shows"),
                    (_ROTATION_LABEL.split(" ")[0], "Rotation"),
                ]
            )
        )
        panel_layout.addWidget(_horizontal_divider())

        if lineup:
            next_up_label = QLabel("Next Up")
            next_up_label.setObjectName("fieldHelp")
            panel_layout.addWidget(next_up_label)
            for entry in lineup[:3]:
                panel_layout.addWidget(_build_placement_row(entry))
            if len(lineup) > 3:
                more = QLabel(f"+{len(lineup) - 3} more programs")
                more.setObjectName("fieldHelp")
                panel_layout.addWidget(more)
        else:
            empty_lbl = QLabel("Nothing schedulable right now.")
            empty_lbl.setObjectName("fieldHelp")
            panel_layout.addWidget(empty_lbl)

        self._preview_layout.addWidget(panel)

    def _build_empty_state(self):
        # Same structural DNA as channel_studio_widgets.build_empty_state
        # (sectionCard chrome, centered sectionNote copy) with a bold
        # headline added on top and a CTA below, since that helper is
        # single-line-only and this needs both.
        box = QFrame()
        box.setObjectName("sectionCard")
        box.setFrameShape(QFrame.NoFrame)
        box.setFixedWidth(420)
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(20, 24, 20, 24)
        box_layout.setSpacing(8)
        box_layout.setAlignment(Qt.AlignCenter)

        title = QLabel("No Programming Blocks yet")
        title.setObjectName("sectionHeader")
        title.setAlignment(Qt.AlignCenter)
        box_layout.addWidget(title)

        if self._mode == MODE_FILL:
            body_text = "Create your first Programming Block, then use it to fill this Open Time."
        else:
            body_text = "Create a reusable group of shows, such as Saturday Morning or Adult Swim."
        body = QLabel(body_text)
        body.setObjectName("sectionNote")
        body.setAlignment(Qt.AlignCenter)
        body.setWordWrap(True)
        box_layout.addWidget(body)

        cta = QPushButton("Create Your First Block")
        style_setup_button(cta)
        cta.clicked.connect(self._open_new_block)
        cta_row = QHBoxLayout()
        cta_row.addStretch(1)
        cta_row.addWidget(cta)
        cta_row.addStretch(1)
        box_layout.addLayout(cta_row)
        return box

    # ── navigation ───────────────────────────────────────────────────

    def _back_to_library(self, select_block_id=None):
        if select_block_id is not None and self._mode == MODE_FILL:
            self._selected_block_id = select_block_id
        self._refresh_library()
        self._stack.setCurrentWidget(self._library_page)

    def _open_new_block(self):
        self._show_editor(existing_block=None)

    def _open_edit_block(self, block):
        self._show_editor(existing_block=block)

    def _show_editor(self, existing_block):
        page = _EditorPage(
            self._items,
            existing_block,
            on_save=self._save_from_editor,
            on_cancel=self._discard_editor,
            show_identity_registry=self._show_identity_registry,
            on_rename_show=self._apply_show_rename,
            on_merge_shows=self._apply_show_merge,
            on_treat_folder_as_show=self._apply_treat_folder_as_show,
            on_episode_behavior=self._apply_show_behavior,
            parent=self,
        )
        self._stack.addWidget(page)
        self._stack.setCurrentWidget(page)

    def _apply_identity_registry_update(self, mutate_fn, display_name):
        """The ONE shared save+refresh path for every show-identity
        correction (Phase 5.5 consistency pass) -- Rename, Merge, and
        Treat Folder as Show all funnel through this single method
        instead of maintaining three subtly different refresh
        implementations. `mutate_fn(current_registry)` performs the pure
        registry mutation (rename_show/merge_shows/add_folder_show_rule)
        and returns `(new_registry, canonical_key, item_predicate,
        redirect_map)`:

            new_registry     -- the pure helper's own return value
            canonical_key    -- the surviving/new canonical show_key
            item_predicate   -- callable(item) -> bool, decides which of
                                 this dialog's `_items` just changed
                                 identity (equality-by-show_key for
                                 Rename/Merge; folder+channel match for
                                 Treat Folder as Show, since a folder
                                 correction can pull in items that never
                                 shared a single old show_key)
            redirect_map     -- {old_show_key_string: canonical_key} for
                                 every STRING key that changed -- used to
                                 remap/dedupe `_included` (a dict of bare
                                 show_key strings, not full items) the
                                 same way regardless of which correction
                                 produced it

        `mutate_fn` may raise ValueError (e.g. Merge Shows given fewer
        than two distinct shows) -- caught and reported like any other
        save failure. Returns (ok, error). On success, refreshes the
        library cards, the currently-open editor page (if any), and
        leaves every unsaved Programming Block field (name, description,
        other included shows) untouched -- only the corrected show's own
        rows change.
        """
        if self._show_identity_registry_save is None:
            return False, "This correction isn't available in this context."
        try:
            new_registry, canonical_key, item_predicate, redirect_map = mutate_fn(self._show_identity_registry)
        except ValueError as error:
            return False, str(error)
        ok, error = self._show_identity_registry_save(new_registry)
        if not ok:
            return ok, error
        self._show_identity_registry = new_registry
        # Match on whatever PRE-correction identity each item still
        # carries -- nothing has re-resolved the catalog against the new
        # registry yet.
        self._items = [
            dict(item, show_key=canonical_key, show_display_name=display_name, show_identity_source="override", media_type="tv")
            if item_predicate(item)
            else item
            for item in self._items
        ]
        self._refresh_library()
        page = self._stack.currentWidget()
        if isinstance(page, _EditorPage):
            page.apply_identity_update(redirect_map, self._items, self._show_identity_registry)
        return True, ""

    def _apply_show_rename(self, show_key, new_name):
        """Rename Show's mutation, expressed as one _apply_identity_
        registry_update call (Phase 5.5 consistency pass)."""

        def mutate(registry):
            new_registry, canonical_key = rename_show(registry, show_key, new_name, now=time.time())
            predicate = lambda item, sk=show_key: item.get("show_key") == sk
            redirect_map = {show_key: canonical_key}
            return new_registry, canonical_key, predicate, redirect_map

        return self._apply_identity_registry_update(mutate, new_name)

    def _apply_show_merge(self, show_keys, display_name):
        """Merge Shows' mutation, expressed as one _apply_identity_
        registry_update call (Phase 5.5 consistency pass)."""

        def mutate(registry):
            new_registry, survivor_key, redirect_map, _conflicts = merge_shows(registry, show_keys, display_name, now=time.time())
            predicate = lambda item, rm=redirect_map: item.get("show_key") in rm
            return new_registry, survivor_key, predicate, redirect_map

        return self._apply_identity_registry_update(mutate, display_name)

    def _apply_treat_folder_as_show(self, channel_id, catalog_root, folder_path, display_name, target_show_key, provisional_keys):
        """Treat Folder as Show's mutation, expressed as one
        _apply_identity_registry_update call (Phase 5.5 consistency
        pass) -- the SAME save/refresh path Rename and Merge use, even
        though this correction identifies affected items by (channel,
        containing folder) rather than by an existing show_key."""

        def mutate(registry):
            new_registry, canonical_key, _rule_id, redirect_map = add_folder_show_rule(
                registry,
                channel_id=channel_id,
                catalog_root=catalog_root,
                folder_path=folder_path,
                display_name=display_name,
                target_show_key=target_show_key,
                provisional_raw_keys=provisional_keys,
                now=time.time(),
            )
            predicate = lambda item, cid=channel_id, fp=folder_path: item.get("channel_id") == cid and os.path.dirname(item["path"]) == fp
            return new_registry, canonical_key, predicate, redirect_map

        return self._apply_identity_registry_update(mutate, display_name)

    def _apply_show_behavior(self, show_key, behavior, display_name):
        """Episode Behavior's mutation, expressed as one
        _apply_identity_registry_update call (Phase 5.6) -- the same
        shared save+refresh path Rename/Merge/Treat Folder as Show use.
        `display_name` is always the show's OWN current title (never a
        rename) -- passing it through _apply_identity_registry_update's
        item remap is a no-op for an already-corrected show and correctly
        seeds the name for a provisional show being promoted for the
        first time, exactly like set_show_behavior's own contract.
        """

        def mutate(registry):
            new_registry, canonical_key = set_show_behavior(registry, show_key, behavior, display_name=display_name, now=time.time())
            predicate = lambda item, sk=show_key: item.get("show_key") == sk
            redirect_map = {show_key: canonical_key}
            return new_registry, canonical_key, predicate, redirect_map

        return self._apply_identity_registry_update(mutate, display_name)

    def _save_from_editor(self, block):
        blocks = [existing for existing in self._blocks() if existing.id != block.id]
        blocks.append(block)
        if not self._persist(blocks):
            return
        page = self._stack.currentWidget()
        # In Fill Mode, saving (whether a brand-new block or an edit)
        # returns to the grid with that block already selected -- a
        # first-time user can go straight from Save to Fill Open Time
        # without hunting for the card they just made.
        self._back_to_library(select_block_id=block.id)
        self._stack.removeWidget(page)
        page.deleteLater()

    def _discard_editor(self):
        page = self._stack.currentWidget()
        self._back_to_library()
        self._stack.removeWidget(page)
        page.deleteLater()

    def _fill_open_time(self):
        """Resolves the selected block against the current catalog and
        Open Time span using the SAME resolve_programming_block/complete
        lineup the detail strip already previewed, then hands it to
        previewed_lineup() for dialog.py to run through the existing
        ONE-AutoFillBlockCommand path (_try_auto_fill_block) -- this
        dialog never touches the draft itself. Every failure path here
        leaves the draft untouched and the browser open so the user can
        pick another block or retry.
        """
        if self._mode != MODE_FILL or self._selected_block_id is None:
            return
        block = next((b for b in self._blocks() if b.id == self._selected_block_id), None)
        if block is None:
            QMessageBox.information(self, "This block was deleted", "Select another Programming Block to fill this Open Time.")
            self._selected_block_id = None
            self._refresh_library()
            return
        plan = resolve_programming_block(block, self._items, self._slot_start, self._slot_duration, seed=0, show_identity_registry=self._show_identity_registry, channel_id=self._channel_id, cursor_data=self._cursor_data)
        lineup = plan.get("lineup") or []
        if not lineup:
            QMessageBox.information(
                self,
                "Nothing to schedule",
                f'"{block.name}" has no schedulable episodes for this Open Time right now.',
            )
            return
        self._result_lineup = list(lineup)
        self.accept()

    def _duplicate_block(self, block):
        copy_block = ProgrammingBlock(new_block_id(), f"{block.name} copy", list(block.show_keys), block.behavior, description=block.description)
        blocks = self._blocks() + [copy_block]
        if self._persist(blocks):
            self._refresh_library()

    def _confirm_delete_block(self, block):
        confirm = QMessageBox.question(
            self,
            "Delete this block?",
            f'Delete "{block.name}"? This only removes the block -- none of its shows or episodes are affected.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        blocks = [existing for existing in self._blocks() if existing.id != block.id]
        if self._persist(blocks):
            self._refresh_library()

    def previewed_lineup(self):
        return self._result_lineup

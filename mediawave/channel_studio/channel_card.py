"""Channel dashboard cards — Channel Studio's main "choose a channel" tiles.

Two builders live here: `build_dashboard_channel_card` (the compact tile
used for every normal channel) and `build_hero_channel_card` (the more
compact, visually special tile used for the first channel — see its
docstring for how "first" is picked today). Both are read-only aside
from the safe, confirmation-gated Remove action (see
studio_styles.confirm_remove_channel) and the Enabled checkbox, which is
preview-only for this pass (see its own docstring below for why).

Now/Next/Later comes from the same TonightSchedule data the Tonight tab
already uses; nothing here reads or writes real schedule, library, or
settings data.

Every label in a normal card is single-line and elided rather than
word-wrapped, and the schedule area always reserves the same fixed
height (rows or their empty-state equivalent) — that's what keeps every
normal card the same size regardless of how long a channel's name or
lineup titles are, without resorting to hard-clipping.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .channel_studio_widgets import FlowLayout
from .studio_styles import (
    channel_number_font_family,
    confirm_disable_companion_channel,
    confirm_remove_channel,
    schedule_row_badge_style,
    style_remove_button,
    style_setup_button,
    CHANNEL_NUMBER_COLOR,
)

_LOGO_CANDIDATE_NAMES = ("logo.png", "logo.jpg", "logo.jpeg", "bug.png", "channel.png")

CARD_WIDTH = 430
HERO_CARD_WIDTH = CARD_WIDTH * 2 + 16  # visually spans two normal cards, same gutter

_SCHEDULE_ROW_KINDS = ("now", "next", "later")
_SCHEDULE_ROW_LABELS = {"now": "NOW", "next": "NEXT", "later": "LATER"}

# Layout constants used to work out exactly how much width is left for an
# elided label next to a fixed-size neighbor. A QLabel's minimumSizeHint
# always matches its (already-elided) text, so a layout can never shrink
# it further — guessing too generously here is what causes a label to
# overlap its neighbor instead of eliding. These mirror the literal
# margins/spacing/fixed sizes used when each row is actually built below.
_CARD_MARGIN = 18
_PANEL_H_MARGIN = 20  # schedule/info panel's own 10px left + 10px right
_SCHEDULE_BADGE_WIDTH = 46
_SCHEDULE_ROW_SPACING = 8
_INFO_LABEL_WIDTH = 78
_INFO_ROW_SPACING = 8
_HERO_LEFT_COL_WIDTH = 210
_HERO_BODY_SPACING = 18

_NORMAL_CONTENT_WIDTH = CARD_WIDTH - 2 * _CARD_MARGIN
_HERO_CONTENT_WIDTH = HERO_CARD_WIDTH - 2 * _CARD_MARGIN
_HERO_RIGHT_COL_WIDTH = _HERO_CONTENT_WIDTH - _HERO_LEFT_COL_WIDTH - _HERO_BODY_SPACING

_NORMAL_SCHEDULE_TEXT_WIDTH = _NORMAL_CONTENT_WIDTH - _PANEL_H_MARGIN - _SCHEDULE_BADGE_WIDTH - _SCHEDULE_ROW_SPACING
_HERO_SCHEDULE_TEXT_WIDTH = _HERO_RIGHT_COL_WIDTH - _PANEL_H_MARGIN - _SCHEDULE_BADGE_WIDTH - _SCHEDULE_ROW_SPACING
_HERO_INFO_VALUE_WIDTH = _HERO_RIGHT_COL_WIDTH - _PANEL_H_MARGIN - _INFO_LABEL_WIDTH - _INFO_ROW_SPACING

_ENABLED_TOOLTIP = (
    "Preview only — turning channels on or off from Channel Studio isn't "
    "wired up yet."
)
_ENABLED_REAL_TOOLTIP = (
    "Updates your real settings immediately. Click Save in Advanced "
    "Configuration to make it stick."
)


def _find_channel_logo_path(root_path):
    """Best-effort, read-only fallback logo lookup. Never raises."""
    if not root_path:
        return ""
    logos_dir = os.path.join(root_path, "Logos")
    if not os.path.isdir(logos_dir):
        return ""
    try:
        entries = {name.lower(): name for name in os.listdir(logos_dir)}
    except OSError:
        return ""
    for candidate in _LOGO_CANDIDATE_NAMES:
        actual = entries.get(candidate)
        if actual:
            return os.path.join(logos_dir, actual)
    return ""


def _elide(label, text, max_width):
    """Set `label`'s text to a single-line elided version of `text` that
    fits in `max_width`, keeping the full text as a tooltip so nothing is
    silently lost. Also fixes the label's width to `max_width`: a QLabel's
    minimumSizeHint always matches its (already-elided) text, so without
    this a layout can't actually shrink it below that — if `max_width` is
    ever a slight overestimate of the real available space, the label
    would still overlap its neighbor instead of eliding further.
    """
    text = text or ""
    max_width = max(20, int(max_width))
    metrics = QFontMetrics(label.font())
    label.setText(metrics.elidedText(text, Qt.ElideRight, max_width))
    label.setToolTip(text)
    label.setFixedWidth(max_width)


def _apply_card_shadow(widget):
    """A soft drop shadow so cards read as raised, tactile tiles instead
    of flat text blocks.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(20)
    effect.setOffset(0, 3)
    effect.setColor(QColor(0, 0, 0, 150))
    widget.setGraphicsEffect(effect)


def _build_logo_widget(summary, on_set_logo, size=88):
    """The channel's logo/bug — shown once per card, never duplicated.

    Falls back to an "Add Channel Logo" button (not blank space) when no
    logo is set, which routes to the channel's Identity tab.
    """
    logo_path = summary.logo_path or _find_channel_logo_path(summary.root_path)
    if logo_path:
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            logo_lbl = QLabel()
            logo_lbl.setPixmap(
                pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            logo_lbl.setFixedSize(size, size)
            logo_lbl.setAlignment(Qt.AlignCenter)
            return logo_lbl

    placeholder = QPushButton("Add\nLogo")
    placeholder.setObjectName("channelLogoPlaceholder")
    placeholder.setToolTip("Add Channel Logo")
    placeholder.setFixedSize(size, size)
    placeholder.setCursor(Qt.PointingHandCursor)
    placeholder.setFlat(True)
    placeholder_font = placeholder.font()
    placeholder_font.setPointSize(max(8, placeholder_font.pointSize() - 2))
    placeholder.setFont(placeholder_font)
    placeholder.setStyleSheet(
        "QPushButton#channelLogoPlaceholder {"
        " background: rgba(255, 255, 255, 10);"
        " border: 1.5px dashed rgba(140, 175, 255, 140);"
        " border-radius: 8px;"
        " color: rgba(200, 215, 255, 220);"
        "}"
        "QPushButton#channelLogoPlaceholder:hover {"
        " background: rgba(255, 255, 255, 22);"
        "}"
    )
    if on_set_logo is not None:
        placeholder.clicked.connect(on_set_logo)
    return placeholder


def _build_channel_number_label(number, point_size=18, glow=False):
    label = QLabel(f"CH {int(number or 0):02d}")
    label.setFont(QFont(channel_number_font_family(), point_size, QFont.Bold))
    label.setStyleSheet(f"color: {CHANNEL_NUMBER_COLOR}; background: transparent;")
    if glow:
        effect = QGraphicsDropShadowEffect(label)
        effect.setColor(QColor(CHANNEL_NUMBER_COLOR))
        effect.setBlurRadius(24)
        effect.setOffset(0, 0)
        label.setGraphicsEffect(effect)
    return label


def _build_enabled_checkbox(enabled, on_toggle=None):
    """The card's Enabled control.

    When `on_toggle` is given, this is real: it's wired (by the caller,
    in channel_studio_pages.py, via channel_actions.py) to the same
    live widget My Catalog's own row or the Companion Channels tab's
    own checkbox uses, so flipping it here updates that real setting
    immediately, in this same dialog session. Without `on_toggle` it
    stays the original preview-only control — used for anything that
    doesn't have a safe, real setting to write to yet.
    """
    box = QCheckBox("Enabled")
    box.setChecked(bool(enabled))
    if on_toggle is not None:
        box.toggled.connect(on_toggle)
        box.setToolTip(_ENABLED_REAL_TOOLTIP)
    else:
        box.setToolTip(_ENABLED_TOOLTIP)
    return box


def _schedule_slots_or_none(schedule):
    if schedule is not None and schedule.has_data and schedule.slots:
        return list(schedule.slots)
    return None


def _build_schedule_panel(schedule, text_width, row_height=18, fixed_height=None):
    """A dark inset Now/Next/Later panel with color-coded row labels
    (green/cyan/purple) and thin dividers between rows. Always renders
    the same three rows (or the empty-state message in their place),
    which is what keeps every normal card's schedule area the same
    height regardless of the data behind it.
    """
    panel = QFrame()
    panel.setObjectName("scheduleInsetPanel")
    panel.setStyleSheet(
        "QFrame#scheduleInsetPanel {"
        " background: rgba(8, 10, 24, 170);"
        " border: 1px solid rgba(255, 255, 255, 22);"
        " border-radius: 8px;"
        "}"
    )
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(0)

    slots = _schedule_slots_or_none(schedule)
    if slots is None:
        note = QLabel("Lineup appears once this channel is playing.")
        note.setObjectName("fieldHelp")
        note.setWordWrap(True)
        layout.addWidget(note)
        if fixed_height:
            panel.setFixedHeight(fixed_height)
        return panel

    for index, kind in enumerate(_SCHEDULE_ROW_KINDS):
        row_widget = QWidget()
        row_widget.setFixedHeight(row_height)
        if index < len(_SCHEDULE_ROW_KINDS) - 1:
            row_widget.setStyleSheet("border-bottom: 1px solid rgba(255,255,255,16);")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(_SCHEDULE_ROW_SPACING)

        badge = QLabel(_SCHEDULE_ROW_LABELS[kind])
        badge.setStyleSheet(schedule_row_badge_style(kind))
        badge.setFixedWidth(_SCHEDULE_BADGE_WIDTH)
        badge.setAlignment(Qt.AlignCenter)
        row.addWidget(badge)

        slot = slots.pop(0) if slots else None
        title_lbl = QLabel()
        title_lbl.setObjectName("sectionNote" if kind == "now" else "fieldHelp")
        text = f"{slot.time_label}   {slot.title}" if (slot and slot.time_label) else (slot.title if slot else "—")
        _elide(title_lbl, text, text_width)
        row.addWidget(title_lbl, 1)

        layout.addWidget(row_widget)

    if fixed_height:
        panel.setFixedHeight(fixed_height)
    return panel


def _build_companion_status_panel(summary, text_width, fixed_height=None):
    """Replaces the Now/Next/Later schedule panel for companion cards —
    WeatherStar/RadioWaveTV/NetTV don't have a "lineup" in the folder-
    channel sense, so this shows the one piece of type-specific status
    that actually matters instead (location/music folder/playlist —
    see companion_adapter.companion_summaries for where these come
    from, including the live-status upgrade once the channel is
    actually loaded).
    """
    panel = QFrame()
    panel.setObjectName("companionStatusPanel")
    panel.setStyleSheet(
        "QFrame#companionStatusPanel {"
        " background: rgba(8, 10, 24, 170);"
        " border: 1px solid rgba(255, 255, 255, 22);"
        " border-radius: 8px;"
        "}"
    )
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(4)

    label_lbl = QLabel((summary.companion_info_label or "Status").upper())
    label_lbl.setObjectName("fieldHelp")
    label_lbl.setStyleSheet("font-weight: 700; letter-spacing: 1px;")
    layout.addWidget(label_lbl)

    value_lbl = QLabel()
    value_lbl.setObjectName("sectionNote")
    _elide(value_lbl, summary.companion_info_value or "Not configured yet", text_width)
    layout.addWidget(value_lbl)
    layout.addStretch(1)

    if fixed_height:
        panel.setFixedHeight(fixed_height)
    return panel


def build_dashboard_channel_card(
    summary,
    schedule,
    on_open,
    on_set_logo=None,
    enabled=True,
    on_toggle_enabled=None,
    on_remove=None,
):
    """Build one channel's dashboard tile for the Choose Channel grid.

    Remove is handled internally: for a companion channel with
    `on_remove` given, it's a real (but non-destructive) Disable via
    `studio_styles.confirm_disable_companion_channel`; otherwise it's
    the original safe, confirmation-only preview via
    `studio_styles.confirm_remove_channel` — callers don't need to
    wire either one up themselves beyond passing `on_remove`.
    """
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    card.setFixedWidth(CARD_WIDTH)
    card.setStyleSheet(
        "QFrame#sectionCard {"
        " background: rgba(18, 21, 44, 232);"
        " border: 1px solid rgba(90, 125, 220, 100);"
        " border-radius: 10px;"
        "}"
    )
    _apply_card_shadow(card)
    outer = QVBoxLayout(card)
    outer.setContentsMargins(18, 16, 18, 16)
    outer.setSpacing(10)

    header_row = QHBoxLayout()
    header_row.setSpacing(10)
    number_lbl = _build_channel_number_label(summary.number)
    header_row.addWidget(number_lbl)
    logo_widget = _build_logo_widget(summary, on_set_logo)

    # Measure the two fixed-size neighbors so the title column gets
    # exactly what's left — see the _elide docstring for why a guess
    # that's too generous here would overlap the logo widget.
    title_width = (
        _NORMAL_CONTENT_WIDTH
        - number_lbl.sizeHint().width()
        - logo_widget.sizeHint().width()
        - 2 * header_row.spacing()
    )
    title_width = max(60, title_width)

    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    name_lbl = QLabel()
    name_lbl.setObjectName("sectionHeader")
    _elide(name_lbl, summary.name, title_width)
    title_col.addWidget(name_lbl)
    headline_lbl = QLabel()
    headline_lbl.setObjectName("sectionNote")
    _elide(headline_lbl, summary.headline, title_width)
    title_col.addWidget(headline_lbl)
    header_row.addLayout(title_col, 1)

    header_row.addWidget(logo_widget)
    outer.addLayout(header_row)

    if summary.is_companion:
        outer.addWidget(_build_companion_status_panel(summary, _NORMAL_SCHEDULE_TEXT_WIDTH, fixed_height=76))
    else:
        outer.addWidget(
            _build_schedule_panel(schedule, _NORMAL_SCHEDULE_TEXT_WIDTH, row_height=18, fixed_height=76)
        )

    bottom_row = QHBoxLayout()
    bottom_row.addWidget(_build_enabled_checkbox(enabled, on_toggle=on_toggle_enabled))
    bottom_row.addStretch(1)
    outer.addLayout(bottom_row)

    channel_info = {"id": summary.channel_id, "name": summary.name, "default_number": summary.number}

    btn_row = FlowLayout(h_spacing=8, v_spacing=8)
    setup_btn = QPushButton("⚙  Setup")
    style_setup_button(setup_btn)
    setup_btn.clicked.connect(lambda: on_open(channel_info))
    btn_row.addWidget(setup_btn)
    if summary.is_companion and on_remove is not None:
        remove_btn = QPushButton("🚫  Disable")
        style_remove_button(remove_btn)
        remove_btn.clicked.connect(lambda: confirm_disable_companion_channel(card, summary.name, on_remove))
    else:
        remove_btn = QPushButton("🗑  Remove")
        style_remove_button(remove_btn)
        remove_btn.clicked.connect(lambda: confirm_remove_channel(card, summary.name))
    btn_row.addWidget(remove_btn)
    outer.addLayout(btn_row)

    return card


def _channel_info_rows(summary):
    """Only real, already-known values — calm fallback text otherwise.
    Never repeats the Now/Next/Later schedule shown above it.
    """
    if summary.is_companion:
        # Location/folder/playlist already has its own panel (see
        # _build_companion_status_panel) — this stays to just Type/Source
        # so the two panels don't repeat each other.
        return [("Type", "Companion channel"), ("Source", "Built in")]
    is_special = summary.channel_type != "media"
    rows = [
        ("Type", "Special channel" if is_special else "Folder channel"),
        ("Source", "Built in" if is_special else "Local folder"),
    ]
    if not is_special:
        rows.append(("Playback", f"{summary.playback_order_label} order"))
    rows.append(("Commercials", summary.commercials_label))
    if summary.content_known:
        counts = []
        if summary.show_count:
            counts.append(f"{summary.show_count} show" + ("s" if summary.show_count != 1 else ""))
        if summary.movie_count:
            counts.append(f"{summary.movie_count} movie" + ("s" if summary.movie_count != 1 else ""))
        if counts:
            rows.append(("Library", " · ".join(counts)))
    return rows


def _build_channel_info_panel(summary):
    panel = QFrame()
    panel.setObjectName("channelInfoPanel")
    panel.setStyleSheet(
        "QFrame#channelInfoPanel {"
        " background: rgba(12, 14, 32, 150);"
        " border: 1px solid rgba(255, 255, 255, 18);"
        " border-radius: 8px;"
        "}"
    )
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(3)

    heading = QLabel("Channel Info")
    heading.setObjectName("fieldHelp")
    heading.setStyleSheet("font-weight: 700; letter-spacing: 1px;")
    layout.addWidget(heading)

    for label_text, value_text in _channel_info_rows(summary):
        row = QHBoxLayout()
        row.setSpacing(_INFO_ROW_SPACING)
        label_lbl = QLabel(label_text)
        label_lbl.setObjectName("fieldHelp")
        label_lbl.setFixedWidth(_INFO_LABEL_WIDTH)
        row.addWidget(label_lbl)
        value_lbl = QLabel()
        value_lbl.setObjectName("sectionNote")
        _elide(value_lbl, value_text, _HERO_INFO_VALUE_WIDTH)
        row.addWidget(value_lbl, 1)
        layout.addLayout(row)

    return panel


def build_hero_channel_card(
    summary,
    schedule,
    on_open,
    on_set_logo=None,
    enabled=True,
    on_toggle_enabled=None,
    on_remove=None,
):
    """Build the more compact, visually special tile for the Choose
    Channel grid's hero slot.

    Callers only build this for the most-recently-customized channel
    (tracked in studio_state.py and set whenever Setup is used — see
    channel_studio_pages.py) — never a permanent "featured" pick, and
    never shown at all until the user has opened Setup on something.
    That's the whole reason for the "Finished Customizing?" badge: it's
    written for a channel the user was just working on, not a favorite.
    The same channel this card shows always still has its own tile in
    the regular grid below — this is a contextual duplicate, not a
    replacement.
    """
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    card.setFixedWidth(HERO_CARD_WIDTH)
    card.setStyleSheet(
        "QFrame#sectionCard {"
        " background: rgba(20, 24, 50, 238);"
        " border: 1.5px solid rgba(120, 170, 255, 140);"
        " border-radius: 12px;"
        "}"
    )
    _apply_card_shadow(card)
    outer = QVBoxLayout(card)
    outer.setContentsMargins(18, 14, 18, 14)
    outer.setSpacing(10)

    badge_row = QHBoxLayout()
    badge = QLabel("Finished Customizing?")
    badge.setObjectName("statusBadge")
    badge_row.addWidget(badge)
    badge_row.addStretch(1)
    outer.addLayout(badge_row)

    body_row = QHBoxLayout()
    body_row.setSpacing(_HERO_BODY_SPACING)

    left_widget = QWidget()
    left_widget.setFixedWidth(_HERO_LEFT_COL_WIDTH)
    left_col = QVBoxLayout(left_widget)
    left_col.setContentsMargins(0, 0, 0, 0)
    left_col.setSpacing(8)
    left_col.addWidget(_build_channel_number_label(summary.number, point_size=26, glow=True))
    name_lbl = QLabel()
    name_lbl.setObjectName("sectionHeader")
    _elide(name_lbl, summary.name, _HERO_LEFT_COL_WIDTH - 10)
    left_col.addWidget(name_lbl)
    left_col.addWidget(_build_logo_widget(summary, on_set_logo, size=78))
    left_col.addWidget(_build_enabled_checkbox(enabled, on_toggle=on_toggle_enabled))
    left_col.addStretch(1)
    body_row.addWidget(left_widget)

    right_col = QVBoxLayout()
    right_col.setSpacing(8)
    if summary.is_companion:
        right_col.addWidget(_build_companion_status_panel(summary, _HERO_SCHEDULE_TEXT_WIDTH))
    else:
        right_col.addWidget(_build_schedule_panel(schedule, _HERO_SCHEDULE_TEXT_WIDTH, row_height=22))
    right_col.addWidget(_build_channel_info_panel(summary))
    body_row.addLayout(right_col, 1)

    outer.addLayout(body_row)

    channel_info = {"id": summary.channel_id, "name": summary.name, "default_number": summary.number}

    btn_row = FlowLayout(h_spacing=10, v_spacing=8)
    setup_btn = QPushButton("⚙  Setup")
    style_setup_button(setup_btn)
    setup_btn.clicked.connect(lambda: on_open(channel_info))
    btn_row.addWidget(setup_btn)
    if summary.is_companion and on_remove is not None:
        remove_btn = QPushButton("🚫  Disable")
        style_remove_button(remove_btn)
        remove_btn.clicked.connect(lambda: confirm_disable_companion_channel(card, summary.name, on_remove))
    else:
        remove_btn = QPushButton("🗑  Remove")
        style_remove_button(remove_btn)
        remove_btn.clicked.connect(lambda: confirm_remove_channel(card, summary.name))
    btn_row.addWidget(remove_btn)
    outer.addLayout(btn_row)

    return card

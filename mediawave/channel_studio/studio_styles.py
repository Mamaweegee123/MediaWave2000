"""Channel-specific visual helpers for Channel Studio (Preview).

The generic pieces of this module (card shadow, button/nav/slider styles,
the themed scroll area, SinglePageStackedWidget) moved to
mediawave/studio/styles.py, part of the shared Studio toolkit -- re-exported
below so existing `from .studio_styles import ...` call sites in this
package don't need to change. Everything defined in this file itself is
genuinely Channel Studio-specific: the VHS/OSD channel-number font, the
NOW/NEXT/LATER schedule badge, and the channel/companion-channel confirm
dialogs.
"""

import os
import sys

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QMessageBox

from ..studio.styles import (  # noqa: F401 -- re-exported for this package's own call sites
    REMOVE_BUTTON_COLOR,
    SinglePageStackedWidget,
    apply_card_shadow,
    build_scroll_area,
    style_choice_button,
    style_nav_item,
    style_remove_button,
    style_setup_button,
    style_slider,
)
from .channel_studio_dialogs import show_preview_dialog

CHANNEL_NUMBER_COLOR = "#5aff6e"

NOW_COLOR = "#6dffa0"
NEXT_COLOR = "#6fd6ff"
LATER_COLOR = "#c79bff"

SETUP_BUTTON_COLOR = "#6090ff"

_CHANNEL_NUMBER_FONT_CANDIDATES = (
    "Helvetica Neue Condensed Bold",
    "HelveticaNeue-CondensedBold",
    "Arial Narrow",
    "Nimbus Sans Narrow",
    "Liberation Sans Narrow",
)

_channel_number_font_family_cache = None


def _project_root_dir():
    """A safe, project-relative base dir -- never a user-specific
    absolute path. Mirrors channelsurfer2000.py's own resource_base_dir()
    (frozen app vs. running from source) without importing that module,
    which would pull in its whole top-level startup path just to load a
    font.
    """
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(sys.executable))
    # mediawave/channel_studio/studio_styles.py -> mediawave -> project root
    this_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(this_dir))


def _find_vhs_osd_font_path():
    """Best-effort, read-only lookup for the app's own VHS/VCR/OSD font
    -- the same file used for the classic channel-switching HUD (see
    channelsurfer2000.py's ChannelOverlay/crt_font_family). Never raises.
    """
    root = _project_root_dir()
    for relative in ("Fonts/vhs-vcr-osd.ttf", "fonts/vhs-vcr-osd.ttf"):
        candidate = os.path.join(root, relative)
        if os.path.isfile(candidate):
            return candidate
    return ""


def channel_number_font_family():
    """The channel-switching HUD's own VHS/VCR/OSD font when it can be
    loaded from the project's Fonts folder; otherwise the same
    condensed-bold system-font fallback tier the rest of Channel Studio
    already used, ending in Arial.
    """
    global _channel_number_font_family_cache
    if _channel_number_font_family_cache:
        return _channel_number_font_family_cache

    font_path = _find_vhs_osd_font_path()
    if font_path:
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                _channel_number_font_family_cache = families[0]
                return _channel_number_font_family_cache

    available = set(QFontDatabase.families())
    for family in _CHANNEL_NUMBER_FONT_CANDIDATES:
        if family in available:
            _channel_number_font_family_cache = family
            return family
    _channel_number_font_family_cache = "Arial"
    return _channel_number_font_family_cache


def schedule_row_badge_style(kind):
    """Inline stylesheet for a colored NOW/NEXT/LATER pill label.
    `kind` is one of "now", "next", "later".
    """
    color = {"now": NOW_COLOR, "next": NEXT_COLOR, "later": LATER_COLOR}.get(kind, NOW_COLOR)
    return (
        f"color: {color};"
        f" background: transparent;"
        f" border: 1px solid {color};"
        " border-radius: 4px;"
        " font-size: 10px;"
        " font-weight: 700;"
        " padding: 1px 6px;"
    )


def confirm_remove_channel(parent, channel_name):
    """Shared safe "Remove" confirmation. Never deletes anything --
    only ever asks, then reports that removal isn't wired up yet.
    """
    box = QMessageBox(parent)
    box.setWindowTitle(f"Remove {channel_name}?")
    box.setText(
        "This will eventually remove the channel from Channel Studio, not delete your media."
    )
    box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
    box.setDefaultButton(QMessageBox.Cancel)
    if box.exec() == QMessageBox.Yes:
        show_preview_dialog(
            parent,
            "Remove Channel",
            "Removing channels from Channel Studio isn't wired up yet — nothing changed.",
        )


def confirm_disable_companion_channel(parent, channel_name, on_confirm):
    """"Remove" for a companion channel is real, but only ever a real
    Disable -- never a delete. Nothing about the channel's configuration
    (location, music folder, playlist URL, ...) is touched, so turning
    it back on later picks up right where it left off.
    """
    box = QMessageBox(parent)
    box.setWindowTitle(f"Disable {channel_name}?")
    box.setText("Disable this companion channel? Your settings will be kept.")
    box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
    box.setDefaultButton(QMessageBox.Cancel)
    if box.exec() == QMessageBox.Yes:
        on_confirm()

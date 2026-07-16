"""build_action_bar: a persistent footer bar for a Studio workspace.

Matches Advanced Configuration's own advFooter chrome
(channelsurfer2000.py's `QWidget#advFooter` QSS rule) -- background/
top-border tones reused as literals since this package can't import that
stylesheet function directly (see mediawave/theme_tokens.py's own
docstring for why the Studio package stays independent of the app's full
startup path). This is the same chrome Channel Studio's own footer already
used, just built from a declarative button list instead of being
hand-rolled per dialog.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from .spacing import CONTROL_SPACING
from .styles import style_setup_button

_BAR_STYLE = (
    "QWidget#studioActionBar {"
    " background: rgba(9, 11, 27, 255);"
    " border-top: 1px solid rgba(42, 54, 128, 255);"
    "}"
)

_BUTTON_LABELS = {
    "back": "←  Back",
    "cancel": "Cancel",
    "revert": "Revert",
    "save": "Save",
    "apply": "Apply",
}

# The "go do it" buttons get the filled-blue treatment (same as Channel
# Studio's own style_setup_button use elsewhere); Back/Cancel/Revert stay
# plain QPushButtons, matching Channel Studio's existing bare "← Back".
_PRIMARY_KEYS = ("save", "apply")


def build_action_bar(buttons):
    """`buttons` is an ordered list drawn from "back"/"cancel"/"revert"/
    "save"/"apply" -- different Studio tools need different combinations
    (a Setup dialog might only need Back; a future editable workspace might
    need Cancel/Revert/Save), but the chrome stays identical either way.

    "back", if present, is pinned to the far left with a stretch after it --
    matching Channel Studio's current single-button footer exactly. Every
    other requested button follows, right-aligned, in the order given.

    Returns `(bar_widget, buttons_by_key)`; `buttons_by_key["save"]` etc. is
    the real QPushButton for whichever keys were requested, so a caller
    connects only the ones it actually uses.
    """
    bar = QWidget()
    bar.setObjectName("studioActionBar")
    bar.setStyleSheet(_BAR_STYLE)
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(20, 10, 20, 16)
    layout.setSpacing(CONTROL_SPACING)

    buttons_by_key = {}

    if "back" in buttons:
        back_btn = QPushButton(_BUTTON_LABELS["back"])
        layout.addWidget(back_btn, 0, Qt.AlignLeft)
        buttons_by_key["back"] = back_btn

    layout.addStretch(1)

    for key in buttons:
        if key == "back":
            continue
        btn = QPushButton(_BUTTON_LABELS.get(key, key.title()))
        if key in _PRIMARY_KEYS:
            style_setup_button(btn)
        layout.addWidget(btn)
        buttons_by_key[key] = btn

    return bar, buttons_by_key

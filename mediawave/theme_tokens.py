"""Shared color tokens for MediaWave's fixed "deep space" dialog palette.

These values originally lived as private `_SW_*` constants directly in
channelsurfer2000.py, used to build that file's `build_themed_dialog_stylesheet()`
and `build_startup_stylesheet()` -- the app's startup screen and roughly a
dozen other dialogs across the app (Advanced Configuration among them, but
also e.g. Airing Rules), not just Studio tools. They're relocated here,
verbatim (same values), as a general, app-wide token module -- deliberately
at the top level of `mediawave`, not under `mediawave/studio/`, since core
app code (channelsurfer2000.py) depends on it and a Studio-specific package
should never be a dependency of unrelated core UI. `mediawave/studio/
sidebar.py` imports this same module for its own star field, the correct
direction: Studio consumes the app's shared palette, not the other way
around.

This module has no dependency beyond PySide6.QtGui.QColor, so importing it
never pulls in the rest of the application.

Completely independent of the active guide theme -- one consistent look,
used regardless of which theme/skin the user has selected elsewhere.
"""

from PySide6.QtGui import QColor

SW_BG = QColor(13, 16, 38)  # Deep space background
SW_HERO_TOP = QColor(9, 11, 27)  # Hero gradient top
SW_HERO_BOT = QColor(15, 18, 44)  # Hero gradient bottom
SW_CARD_BG = QColor(22, 26, 58)  # Card background
SW_CARD_BORDER = QColor(68, 108, 235)  # Electric-blue card border
SW_ACCENT = QColor(96, 144, 255)  # Blue accent
SW_CTA_BG = QColor(255, 188, 10)  # Amber "Watch TV" button
SW_CTA_TEXT = QColor(13, 16, 38)  # Dark text on CTA
SW_TEXT = QColor(210, 222, 252)  # Primary text
SW_TEXT_DIM = QColor(138, 158, 212)  # Muted / secondary
SW_HEADER = QColor(118, 162, 255)  # Section header label
SW_INPUT_BG = QColor(16, 20, 50)  # Input / path field bg
SW_INPUT_TEXT = QColor(188, 205, 248)  # Input text
SW_FOOTER_BG = QColor(9, 11, 27)  # Footer bar bg
SW_FOOTER_BORD = QColor(42, 54, 128)  # Footer top-border
SW_STAR_WARM = QColor(255, 218, 96)  # Warm pixel star
SW_STAR_COOL = QColor(148, 196, 255)  # Cool pixel star
SW_COAXIE_BODY = QColor(50, 68, 162)  # Coaxie TV body
SW_COAXIE_SCR = QColor(7, 10, 32)  # Screen dark
SW_COAXIE_GLOW = QColor(55, 96, 228)  # Screen glow edge
SW_COAXIE_EYE = QColor(96, 200, 255)  # Eye highlight
SW_COAXIE_KNOB = QColor(192, 150, 48)  # Dial/knob color

# A third, dimmer star tone used by the Advanced Config sidebar's star field
# (_AdvNavPanel.paintEvent in channelsurfer2000.py) that never got its own
# named constant there -- named here since channel_studio's own sidebar
# reuses the same three-tier star field.
SW_STAR_DIM = QColor(200, 212, 252)

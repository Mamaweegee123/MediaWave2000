"""Channel Studio (Preview) — choose a channel, then run it.

Flat by design: Channel Studio is one screen (choose a channel) that
opens one more screen (that channel, with its five tabs). There is no
settings-style sidebar of sections here — see channel_studio_cards.py
for the per-channel view.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import channel_studio_pages as pages

_LOGO_HEIGHT = 40


def _build_header_title(logo_path):
    """A small logo if the asset exists and loads, text otherwise."""
    if logo_path:
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            label = QLabel()
            label.setPixmap(
                pixmap.scaledToHeight(_LOGO_HEIGHT, Qt.SmoothTransformation)
            )
            return label
    label = QLabel("Channel Studio")
    label.setObjectName("advNavSubtitle")
    return label


def build_channel_studio_tab(dialog, nav_panel_cls=None, on_back=None, logo_path=None):
    """Build the Channel Studio (Preview) tab: just the channel picker.

    `dialog` is the owning AdvancedConfigDialog; used only to reuse its
    existing themed helpers (build_scroll_tab, build_section_card, ...).
    `nav_panel_cls` is accepted for backward compatibility with the
    caller but no longer used — Channel Studio has no side navigation.
    `on_back`, if given, is called when the header's "Back to Settings"
    button is clicked. `logo_path`, if given and it loads, replaces the
    plain "Channel Studio" header text with that image.
    """
    container = QWidget()
    container.setObjectName("channelStudioRoot")
    outer = QVBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    if on_back is not None:
        header = QHBoxLayout()
        header.setContentsMargins(16, 12, 16, 0)
        header.addWidget(_build_header_title(logo_path))
        header.addStretch(1)
        back_btn = QPushButton("←  Back to Settings")
        back_btn.setObjectName("advNavItem")
        back_btn.setFlat(True)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(on_back)
        header.addWidget(back_btn)
        outer.addLayout(header)

    content = dialog.build_scroll_tab(pages.build_channels_page(dialog))
    outer.addWidget(content, 1)
    return container

"""Sidebar navigation for Channel Studio (Preview).

Mirrors the QButtonGroup + QStackedWidget navigation philosophy already
used by the Advanced Configuration dialog's own sidebar, so Channel
Studio looks and behaves like the rest of MediaWave.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QLabel, QPushButton, QVBoxLayout, QWidget

CHANNEL_STUDIO_SECTIONS = [
    ("Channels", 0),
    ("Tonight's Schedule", 1),
    ("Library", 2),
    ("Programming", 3),
    ("Blocks", 4),
    ("Commercials", 5),
    ("Bumpers", 6),
    ("Branding", 7),
    ("Appearance", 8),
    ("Advanced", 9),
]


def build_channel_studio_sidebar(panel_cls=None, on_back=None):
    """Build the sidebar panel + its button group.

    `panel_cls` lets the caller supply the same custom-painted nav panel
    class used elsewhere in MediaWave (starfield background, fixed
    width) so Channel Studio matches pixel-for-pixel. Falls back to a
    plain QWidget if not provided. `on_back`, if given, wires a
    bottom-left "Back to Settings" button that returns to the main
    Advanced Configuration page.
    """
    panel = (panel_cls or QWidget)()
    inner = QVBoxLayout(panel)
    inner.setContentsMargins(0, 0, 0, 0)
    inner.setSpacing(2)

    header = QLabel("Channel Studio")
    header.setObjectName("advNavSubtitle")
    header.setContentsMargins(20, 22, 16, 10)
    inner.addWidget(header)

    sep = QWidget()
    sep.setObjectName("advNavSep")
    sep.setFixedHeight(1)
    inner.addWidget(sep)

    group = QButtonGroup(panel)
    group.setExclusive(True)
    for label, idx in CHANNEL_STUDIO_SECTIONS:
        btn = QPushButton(label)
        btn.setObjectName("advNavItem")
        btn.setCheckable(True)
        btn.setChecked(idx == 0)
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        inner.addWidget(btn)
        group.addButton(btn, idx)

    inner.addStretch(1)

    if on_back is not None:
        back_sep = QWidget()
        back_sep.setObjectName("advNavSep")
        back_sep.setFixedHeight(1)
        inner.addWidget(back_sep)

        back_btn = QPushButton("←  Back to Settings")
        back_btn.setObjectName("advNavItem")
        back_btn.setFlat(True)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(on_back)
        inner.addWidget(back_btn)

    return group, panel

"""Logo Studio as its own "room" (Phase 1.5 of the Channel Studio UI
framework) -- opened from the Channel Header's clickable logo instead of
living as a Setup page.

This does NOT redesign Logo Studio itself: the entire body is
setup_sections.build_logo_section, completely unchanged. All this dialog
adds is a window shell and a Back button. It's opened modally and parented
to the still-open ChannelSetupDialog (see channel_setup.py's
_open_logo_studio) rather than replacing it, so closing it drops the user
right back into the exact same Channel Setup instance -- same page, same
live settings, same scroll position -- with no state to manually restore.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPushButton, QVBoxLayout

from .setup_sections import build_logo_section


class LogoStudioDialog(QDialog):
    def __init__(self, studio_dialog, channel_info, summary, parent=None):
        super().__init__(parent)
        channel_name = channel_info.get("name", "Channel")
        self.setWindowTitle(f"Logo Studio — {channel_name}")
        self.setModal(True)
        # Wide enough that the preview (the hero element, ~60% of the
        # workspace) and the grouped control panel (~40%) both breathe at
        # their default size, with nothing clipped or scrolled -- a narrow
        # 1000px dialog was the direct cause of the cramped layout this
        # replaces (see build_logo_section's own docstring). The minimum
        # size keeps both columns above their own practical floor if the
        # user shrinks the window; below that, the control panel's own
        # scroll area (see build_logo_section) is the fallback, not
        # clipping or overlap.
        self.resize(1360, 820)
        self.setMinimumSize(1040, 680)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)

        outer.addWidget(build_logo_section(studio_dialog, channel_info, summary), 1)

        back_btn = QPushButton("←  Back to Channel Setup")
        back_btn.clicked.connect(self.accept)
        outer.addWidget(back_btn, 0, Qt.AlignLeft)

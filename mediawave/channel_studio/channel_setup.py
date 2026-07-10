"""Channel Studio's real Setup dialog -- replaces the old five-tab mock
(channel_studio_cards.ChannelEditorPreviewDialog) with five focused
sections that are wired to real settings where it's safe (see
setup_sections.py for what's real vs. preview-only per section, and
channel_actions.py for the settings bridge itself).

Same constructor shape as the dialog it replaces so the call site in
channel_studio_pages.py barely changes.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from .channel_studio_widgets import build_tab_row
from .setup_sections import (
    build_advanced_section,
    build_commercials_section,
    build_logo_section,
    build_overview_section,
    build_programming_section,
)
from .studio_styles import SinglePageStackedWidget, build_scroll_area

_SECTION_TITLES = ["Overview", "Logo", "Commercials", "Programming", "Advanced"]
_OVERVIEW_SECTION_INDEX = 0
_COMMERCIALS_SECTION_INDEX = 2


class ChannelSetupDialog(QDialog):
    """One channel's real Setup screen: a flat row of five sections,
    each answering one question about this channel. Overview,
    Commercials, and (for local channels) Logo Display are wired to
    real settings live in this same Advanced Configuration dialog
    session -- see setup_sections.py for exactly what.
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
        self._channel_info = channel_info
        self._summary = summary
        self._schedule = schedule
        self._drafts_path = drafts_path
        channel_name = channel_info.get("name", "Channel")
        self.setWindowTitle(channel_name)
        self.resize(820, 540)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)

        header = QLabel(f"{channel_name} · Channel {channel_info.get('default_number', '')}")
        header.setObjectName("sectionHeader")
        outer.addWidget(header)

        identity = QLabel(summary.headline if summary is not None else "A folder channel, ready to play.")
        identity.setObjectName("sectionNote")
        identity.setWordWrap(True)
        outer.addWidget(identity)

        tab_row, self._tab_group = build_tab_row(_SECTION_TITLES, self._show_section, initial_index=initial_tab)
        outer.addWidget(tab_row)

        self._stack = SinglePageStackedWidget()
        self._stack.addWidget(build_overview_section(studio_dialog, channel_info, summary, self._go_to_commercials))
        self._stack.addWidget(build_logo_section(studio_dialog, channel_info, summary))
        self._stack.addWidget(build_commercials_section(studio_dialog, channel_info, summary))
        self._stack.addWidget(
            build_programming_section(self, studio_dialog, channel_info, summary, schedule, drafts_path)
        )
        self._stack.addWidget(build_advanced_section(channel_info, summary))
        self._stack.setCurrentIndex(initial_tab)

        outer.addWidget(build_scroll_area(self._stack), 1)

        back_btn = QPushButton("←  Back")
        back_btn.clicked.connect(self.accept)
        outer.addWidget(back_btn, 0, Qt.AlignLeft)

    def _show_section(self, index):
        if index == _OVERVIEW_SECTION_INDEX:
            # Overview's own "Commercials: X" preview card is a static
            # snapshot from whenever it was last built -- refresh it
            # in place so a mode change made over on the Commercials
            # section (or the Enabled toggle, changed from a sibling
            # tab) doesn't look stale when the user comes back here.
            self._refresh_overview()
        self._stack.setCurrentIndex(index)

    def _refresh_overview(self):
        old_widget = self._stack.widget(_OVERVIEW_SECTION_INDEX)
        new_widget = build_overview_section(
            self._studio_dialog, self._channel_info, self._summary, self._go_to_commercials
        )
        self._stack.removeWidget(old_widget)
        self._stack.insertWidget(_OVERVIEW_SECTION_INDEX, new_widget)
        old_widget.deleteLater()

    def _go_to_commercials(self):
        button = self._tab_group.button(_COMMERCIALS_SECTION_INDEX)
        if button is not None:
            button.setChecked(True)
        self._stack.setCurrentIndex(_COMMERCIALS_SECTION_INDEX)

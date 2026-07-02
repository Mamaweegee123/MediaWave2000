"""Channel Studio (Preview) — experimental shell for a future replacement
of My Catalog.

This module builds ONLY the navigation shell: a sidebar of placeholder
sections plus a landing/channel-list/editor skeleton. No scheduling,
library, or settings logic is wired up yet — see channel_studio_pages.py
for the individual (mostly "under construction") sections.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QStackedWidget, QWidget

from . import channel_studio_pages as pages
from .channel_studio_sidebar import build_channel_studio_sidebar

_PAGE_BUILDERS = [
    pages.build_channels_page,
    pages.build_library_page,
    pages.build_programming_page,
    pages.build_blocks_page,
    pages.build_commercials_page,
    pages.build_bumpers_page,
    pages.build_branding_page,
    pages.build_appearance_page,
    pages.build_advanced_page,
]


def build_channel_studio_tab(dialog, nav_panel_cls=None, on_back=None):
    """Build the Channel Studio (Preview) tab and wire its internal sidebar.

    `dialog` is the owning AdvancedConfigDialog; used only to reuse its
    existing themed helpers (build_scroll_tab, build_section_card, ...)
    so Channel Studio inherits the same look without duplicating QSS.
    `nav_panel_cls`, if given, is the same custom-painted sidebar panel
    class used by the rest of the Advanced Configuration dialog.
    `on_back`, if given, is called when the sidebar's "Back to Settings"
    button is clicked, so the dialog can return to its main settings mode.
    """
    container = QWidget()
    container.setObjectName("channelStudioRoot")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    splitter = QSplitter(Qt.Horizontal)
    splitter.setObjectName("channelStudioSplitter")
    splitter.setChildrenCollapsible(False)

    nav_group, nav_panel = build_channel_studio_sidebar(panel_cls=nav_panel_cls, on_back=on_back)
    splitter.addWidget(nav_panel)

    stack = QStackedWidget()
    stack.setObjectName("advContentStack")
    for builder in _PAGE_BUILDERS:
        content = builder(dialog)
        stack.addWidget(dialog.build_scroll_tab(content))

    nav_group.idClicked.connect(stack.setCurrentIndex)
    splitter.addWidget(stack)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setSizes([200, 640])

    layout.addWidget(splitter)
    return container

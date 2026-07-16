"""Channel Studio's real Setup dialog -- replaces the old five-tab mock
(channel_studio_cards.ChannelEditorPreviewDialog) with focused pages that
are wired to real settings where it's safe (see setup_sections.py for
what's real vs. preview-only per page, and channel_actions.py for the
settings bridge itself).

Phase 3 of the Channel Studio UI framework matches Advanced Configuration's
own shell shape (AdvancedConfigDialog, channelsurfer2000.py): a branded left
sidebar (mediawave/studio/sidebar.py, hosting the channel identity block from
channel_setup_header.py plus the nav rail from mediawave/studio/nav_rail.py)
next to one visible workspace page at a time, and a persistent themed action
bar below -- assembled via mediawave/studio/workspace.py's build_workspace()
and mediawave/studio/action_bar.py's build_action_bar(), the shared Studio
shell every Studio tool's main dialog is built from. Earlier phases had a
separate full-width header row above a floating nav-card rail; that's gone
now -- the identity block lives at the top of the sidebar instead, same as
Advanced Configuration's own branding-block-above-nav-items layout. Logo
Studio stays its own dialog (logo_studio_dialog.py), opened by clicking the
logo in the sidebar's identity block.

Same constructor shape (minus the tab-index param, replaced by
initial_page/open_logo_studio_on_show) as the dialog it replaces so the
call site in channel_studio_pages.py barely changes.
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

from . import channel_actions
from .channel_setup_header import build_identity_block
from .channel_studio_widgets import build_page_header
from .logo_studio_dialog import LogoStudioDialog
from .setup_sections import (
    _companion_type,
    build_advanced_section,
    build_commercials_section,
    build_overview_section,
    build_programming_section,
    resolve_channel_logo_pixmap,
)
from ..studio.action_bar import build_action_bar
from ..studio.nav_rail import StudioNavRail
from ..studio.section import StudioSection
from ..studio.sidebar import StudioSidebar
from ..studio.spacing import OUTER_MARGIN
from ..studio.workspace import build_workspace
from .studio_styles import SinglePageStackedWidget, build_scroll_area

_PAGE_TITLES = ["Overview", "Programming", "Commercials", "Advanced"]
_PAGE_ICONS = {
    "Overview": "📺",
    "Programming": "📅",
    "Commercials": "💵",
    "Advanced": "⚙",
}
# Each page's one-line description -- used both as that page's nav-item
# description and as its big page-header subtitle, so the two always stay
# in sync. Each StudioSection's own (more specific) title/subtitle is
# separate -- see _SECTION_SUBTITLES below.
_PAGE_DESCRIPTIONS = {
    "Overview": "General channel settings",
    "Programming": "Schedule & automation",
    "Commercials": "Advertising & breaks",
    "Advanced": "Experimental settings",
}
_SECTION_SUBTITLES = {
    "Overview": "Name, number, and enabled status.",
    "Programming": "Tonight's lineup and draft blocks.",
    "Commercials": "Ad breaks for this channel.",
    "Advanced": "Channel ID, folder path, and hints.",
}


class ChannelSetupDialog(QDialog):
    """One channel's real Setup screen: a branded sidebar (identity block +
    nav rail) on the left, one workspace page visible at a time, and a
    persistent footer -- the same shell shape as Advanced Configuration.
    Overview, Commercials, and (via Logo Studio) Logo Display are wired to
    real settings live in this same Advanced Configuration dialog session --
    see setup_sections.py for exactly what.
    """

    def __init__(
        self,
        channel_info,
        summary=None,
        schedule=None,
        parent=None,
        studio_dialog=None,
        drafts_path=None,
        initial_page=None,
        open_logo_studio_on_show=False,
    ):
        super().__init__(parent)
        self._studio_dialog = studio_dialog
        self._channel_info = channel_info
        self._summary = summary
        self._schedule = schedule
        self._drafts_path = drafts_path
        self._channel_id = str(channel_info.get("id", "") or "")
        channel_name = channel_info.get("name", "Channel")
        self.setWindowTitle(channel_name)
        # Wide enough for the branded sidebar (studio_sidebar.SIDEBAR_WIDTH)
        # without shrinking the actual workspace area below what earlier
        # phases already sized it to.
        self.resize(1440, 660)

        identity_widget, self._identity_api = build_identity_block(
            channel_name,
            channel_info.get("default_number", ""),
            summary.headline if summary is not None else "A folder channel, ready to play.",
            logo_pixmap=resolve_channel_logo_pixmap(studio_dialog, channel_info, summary),
            on_logo_activated=self._open_logo_studio,
            status_lines=self._status_lines(),
        )

        self._sections = {}
        self._pages = {}
        self._page_stack = SinglePageStackedWidget()

        self._sections["Overview"] = self._build_section(
            "Overview", build_overview_section(studio_dialog, channel_info, summary, self._go_to_commercials)
        )
        self._sections["Programming"] = self._build_section(
            "Programming",
            build_programming_section(self, studio_dialog, channel_info, summary, schedule, drafts_path),
        )
        self._sections["Commercials"] = self._build_section(
            "Commercials", build_commercials_section(studio_dialog, channel_info, summary)
        )
        self._sections["Advanced"] = self._build_section(
            "Advanced", build_advanced_section(channel_info, summary)
        )

        for title in _PAGE_TITLES:
            page_wrap = QWidget()
            page_layout = QVBoxLayout(page_wrap)
            page_layout.setContentsMargins(*OUTER_MARGIN)
            page_layout.setSpacing(0)
            page_layout.addWidget(build_page_header(_PAGE_ICONS[title], title, _PAGE_DESCRIPTIONS[title]))
            page_layout.addWidget(self._sections[title])
            page_layout.addStretch(1)
            self._pages[title] = build_scroll_area(page_wrap)
            self._page_stack.addWidget(self._pages[title])

        self._nav_rail = StudioNavRail(
            [
                {"key": title, "icon": _PAGE_ICONS[title], "title": title, "description": _PAGE_DESCRIPTIONS[title]}
                for title in _PAGE_TITLES
            ],
            on_select=self._select_page,
        )
        self._sidebar = StudioSidebar(identity_widget, self._nav_rail)

        action_bar, action_buttons = build_action_bar(["back"])
        action_buttons["back"].clicked.connect(self.accept)
        workspace = build_workspace(self._page_stack, action_bar, sidebar=self._sidebar)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(workspace)

        # Marks whether the dialog has finished its own initial page
        # selection -- _select_page's Overview/status-line refresh only
        # makes sense for a REAL navigation back to an already-visible
        # dialog. The nav_rail.select() call right below this also fires
        # _select_page once at construction time, before the dialog's
        # first paint -- refreshing then would just rebuild content that
        # was, moments earlier, already built fresh by _build_section /
        # build_identity_block, and it's exactly what caused a duplicated/
        # orphaned Overview card and a stale, click-swallowing status label
        # (both fixed defensively too, but this avoids the redundant
        # rebuild in the first place).
        self._initialized = False
        start_page = initial_page if initial_page in _PAGE_TITLES else _PAGE_TITLES[0]
        self._nav_rail.select(start_page)
        self._initialized = True

        if open_logo_studio_on_show:
            # Deferred so the dialog is fully shown before Logo Studio pops
            # up modally on top of it -- same pattern Phase 1 used for its
            # own post-construction focus call.
            QTimer.singleShot(0, self._open_logo_studio)

    def _build_section(self, title, content):
        # Not collapsible: the left nav rail already owns which page is
        # visible, so a per-page collapse arrow here would just be a
        # second, redundant way to hide content the rail already hides by
        # switching pages -- see StudioSection's own docstring for what
        # collapsible=False removes (toggle button, reserved space,
        # animation/state-persistence).
        return StudioSection(
            title,
            subtitle=_SECTION_SUBTITLES.get(title),
            icon=_PAGE_ICONS.get(title),
            content=content,
            collapsible=False,
            accent=True,
        )

    def _status_lines(self):
        """Short status lines for the sidebar's identity block --
        commercials mode and enabled state, reusing the exact same
        helpers/derivation Overview's own card already uses
        (channel_actions.commercials_summary_label, channel_actions.
        local_channel_enabled_from_dialog) so these never disagree with
        Overview. Show/movie count isn't repeated here -- it's already part
        of the identity block's subtitle via ChannelStudioSummary.headline.
        """
        channel_id = self._channel_id
        channel_name = self._channel_info.get("name", "Channel")
        companion_type = _companion_type(self._channel_info, self._summary)
        lines = []

        commercials_supported = not companion_type or companion_type == "youtube"
        if commercials_supported:
            mode = channel_actions.commercials_summary_label(self._studio_dialog, channel_name)
            lines.append(f"Commercials: {mode}")

        if companion_type:
            enabled = True
        else:
            live = channel_actions.local_channel_enabled_from_dialog(self._studio_dialog, channel_id)
            enabled = bool(live) if live is not None else True
        lines.append("Enabled" if enabled else "Disabled")

        return lines

    def _select_page(self, title):
        # This is StudioNavRail's on_select callback -- the rail has
        # already updated its own highlight before calling this, for both
        # a real click and a programmatic select() (e.g. at startup), so
        # this only needs to swap the visible page, not re-touch the rail.
        if title not in _PAGE_TITLES:
            return
        # Skip on the dialog's own initial page selection -- the content
        # and status lines built moments earlier (in __init__) are already
        # current, so refreshing again here would be a redundant rebuild
        # before the dialog has even been shown once (see _initialized's
        # own docstring in __init__ for why that specifically is a bug).
        if self._initialized:
            if title == "Overview":
                # Overview's own "Commercials: X" preview card is a static
                # snapshot from whenever it was last built -- rebuilt in
                # place every time the user navigates back here so a mode
                # change made on a previous Commercials visit doesn't look
                # stale.
                self._refresh_overview()
            # Same reasoning for the sidebar's own status lines --
            # Commercials mode and Enabled can both be changed from other
            # pages, so refresh them on every real navigation.
            self._identity_api.set_status_lines(self._status_lines())
        self._page_stack.setCurrentWidget(self._pages[title])

    def _refresh_overview(self):
        new_widget = build_overview_section(
            self._studio_dialog, self._channel_info, self._summary, self._go_to_commercials
        )
        self._sections["Overview"].set_content(new_widget)

    def _go_to_commercials(self):
        # Through the rail's own select(), not _select_page() directly --
        # that's what keeps the rail's highlight in sync with the visible
        # page for any programmatic navigation, not just a real click.
        self._nav_rail.select("Commercials")

    def _open_logo_studio(self):
        LogoStudioDialog(self._studio_dialog, self._channel_info, self._summary, parent=self).exec()
        # Pick up any change (a new logo file, a repositioned/resized one
        # doesn't change the thumbnail, but a replaced image does) now
        # that we're back.
        self._identity_api.set_logo_pixmap(
            resolve_channel_logo_pixmap(self._studio_dialog, self._channel_info, self._summary)
        )

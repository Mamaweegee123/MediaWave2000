"""StudioNavRail: a reusable, generic vertical navigation list (Phase 1.5
introduced it as plain buttons; Phase 2 tried a "miniature card" per item;
Phase 3 settles on Advanced Configuration's own nav-item look instead --
flat rows with a 3px left accent strip and a background tint on the
selected/hovered item, no per-item card border/background/glow -- since a
sidebar's items should read as navigation, not content. Same public shape
throughout: `items` are plain icon/title/key(/description) dicts,
`on_select(key)` is the one callback, and `select(key)` works identically
whether it's a real click or a programmatic call. Knows nothing about
Channel Studio specifically, meant to sit inside a sidebar that supplies its
own background (see mediawave/studio/sidebar.py).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .styles import style_nav_item

_ACTIVE_TEXT_COLOR = "rgba(255, 255, 255, 255)"
_DIM_TEXT_COLOR = "rgba(138, 158, 212, 255)"


class _NavItem(QFrame):
    """One flat nav row -- a QFrame (not a QPushButton) so the left accent
    strip can be drawn as a real border and multiple lines (icon+title, then
    an optional description) can be laid out independently. Click/keyboard
    activation is implemented directly since it isn't a QAbstractButton.
    """

    def __init__(self, icon, title, description=None, parent=None):
        super().__init__(parent)
        self.setObjectName("studioNavItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        # QSS :hover only fires for widgets that opt into hover tracking --
        # QFrame doesn't by default (unlike QAbstractButton).
        self.setAttribute(Qt.WA_Hover, True)

        self._checked = False
        self._siblings = []
        self._index = 0
        self._on_activate = None

        layout = QVBoxLayout(self)
        # Left margin leaves room for the 3px accent strip plus a gap,
        # matching advNavItem's own "padding: 11px 16px 11px 22px" shape.
        layout.setContentsMargins(19, 11, 16, 11)
        layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        icon_lbl = QLabel(icon)
        title_row.addWidget(icon_lbl)
        self._title_lbl = QLabel(title)
        title_row.addWidget(self._title_lbl, 1)
        layout.addLayout(title_row)

        if description:
            self._desc_lbl = QLabel(description)
            self._desc_lbl.setWordWrap(True)
            self._desc_lbl.setStyleSheet(f"color: {_DIM_TEXT_COLOR}; background: transparent; font-size: 11px;")
            layout.addWidget(self._desc_lbl)
        else:
            self._desc_lbl = None

        self._apply_style()

    def set_nav_context(self, siblings, index):
        self._siblings = siblings
        self._index = index

    def set_activated_callback(self, callback):
        self._on_activate = callback

    def isChecked(self):
        return self._checked

    def set_checked(self, checked):
        checked = bool(checked)
        if checked == self._checked:
            return
        self._checked = checked
        self._apply_style()

    def _apply_style(self):
        style_nav_item(self, active=self._checked)
        color = _ACTIVE_TEXT_COLOR if self._checked else _DIM_TEXT_COLOR
        weight = 700 if self._checked else 600
        self._title_lbl.setStyleSheet(f"color: {color}; background: transparent; font-weight: {weight}; font-size: 13px;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._on_activate is not None:
            self._on_activate()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if self._on_activate is not None:
                self._on_activate()
            return
        if event.key() in (Qt.Key_Down, Qt.Key_Up) and self._siblings:
            step = 1 if event.key() == Qt.Key_Down else -1
            target = self._siblings[(self._index + step) % len(self._siblings)]
            target.setFocus(Qt.TabFocusReason)
            return
        super().keyPressEvent(event)


class StudioNavRail(QWidget):
    """A vertical, exclusive list of flat nav items. `items` is
    `[{"key": str, "icon": str, "title": str, "description": str|None}, ...]`;
    `on_select(key)` is called both on a real click and on a programmatic
    `select(key)` call, so a caller never needs two code paths for "user
    picked a page" vs. "we picked one for them" (e.g. the dialog's initial
    page, or re-syncing the highlight after returning from another dialog).
    """

    def __init__(self, items, on_select, parent=None):
        super().__init__(parent)
        self._on_select = on_select
        self._cards = {}
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        ordered_items = []
        for item in items:
            nav_item = _NavItem(item["icon"], item["title"], item.get("description"))
            nav_item.set_activated_callback(lambda key=item["key"]: self.select(key))
            layout.addWidget(nav_item)
            self._cards[item["key"]] = nav_item
            ordered_items.append(nav_item)

        for index, nav_item in enumerate(ordered_items):
            nav_item.set_nav_context(ordered_items, index)

        layout.addStretch(1)

    def select(self, key):
        """Highlight `key`'s item and invoke `on_select(key)` -- safe to
        call both from a user click and programmatically (set_checked()
        alone never re-triggers the activated callback, so there's no
        recursion risk).
        """
        item = self._cards.get(key)
        if item is None:
            return
        for item_key, c in self._cards.items():
            c.set_checked(item_key == key)
        if self._on_select is not None:
            self._on_select(key)

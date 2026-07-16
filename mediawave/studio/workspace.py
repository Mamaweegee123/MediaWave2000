"""build_workspace: the Studio Header -> Workspace -> Persistent Action Bar
shell shared by every Studio tool's main dialog.

Assembles a sidebar (optional -- some future Studio tools may not need one)
beside a content widget, with an action bar pinned below both -- exactly the
zero-margin `QVBoxLayout(QHBoxLayout(sidebar, content), action_bar)` shape
channel_setup.py already built by hand. Doesn't know anything about
channels, logos, or any other MediaWave concept; it just arranges three
widgets a caller already built.
"""

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget


def build_workspace(content, action_bar, sidebar=None):
    """Returns a QWidget shell: `sidebar` (if given) beside `content`,
    filling all available space, with `action_bar` pinned below -- all with
    zero outer margin/spacing, so a caller's own dialog layout controls the
    real page edges.
    """
    workspace = QWidget()
    outer = QVBoxLayout(workspace)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    content_row = QHBoxLayout()
    content_row.setContentsMargins(0, 0, 0, 0)
    content_row.setSpacing(0)
    if sidebar is not None:
        content_row.addWidget(sidebar)
    content_row.addWidget(content, 1)
    outer.addLayout(content_row, 1)

    outer.addWidget(action_bar)
    return workspace

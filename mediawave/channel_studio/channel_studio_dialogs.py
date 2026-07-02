"""Lightweight "Preview only" dialogs for Channel Studio (Preview).

Every mock button in Channel Studio opens one of these instead of
doing anything real, so the UI feels responsive without touching
actual channel, schedule, or library data.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class PreviewActionDialog(QDialog):
    def __init__(self, title, description, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        badge = QLabel("Preview only")
        badge.setObjectName("statusBadge")
        layout.addWidget(badge, 0, Qt.AlignLeft)

        heading = QLabel(title)
        heading.setObjectName("sectionHeader")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        body = QLabel(description)
        body.setObjectName("sectionNote")
        body.setWordWrap(True)
        layout.addWidget(body, 1)

        close_btn = QPushButton("Got it")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)


def show_preview_dialog(parent, title, description):
    PreviewActionDialog(title, description, parent=parent).exec()

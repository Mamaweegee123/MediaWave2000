"""DuplicateHereDialog: the guided workflow for adding another airing of
an existing program on the SAME date (Phase 3.1 spec section 3) --
same shape as MoveToDialog (a fixed From/To channel, a time picker, a
live preview), but framed as "Original" / "New airing" rather than
"From" / "To", since the source program is never touched.

Gathers a destination time only; validation, conflict handling, and
execution are all owned by the workspace (dialog.py), which reuses
DuplicateProgramCommand.validate() -- the exact same path Copy to
Another Day and drag-free Move To… already follow, so there is no second
mutation path for any of these interactions.
"""

import time

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
)

from .move_to_dialog import destination_epoch_for_time

_TEXT_COLOR = "rgba(210, 222, 252, 235)"
_DIM_COLOR = "rgba(138, 158, 212, 220)"
_PANEL_BG = "rgba(13, 16, 38, 255)"


def _time_label(epoch_seconds):
    return time.strftime("%I:%M %p", time.localtime(epoch_seconds)).lstrip("0")


class DuplicateHereDialog(QDialog):
    """Returns the chosen destination start epoch via
    `destination_start()` after exec() == Accepted. `block` is the
    ProgramBlock being duplicated; `lane` is its ChannelLane.
    """

    def __init__(self, block, lane, parent=None):
        super().__init__(parent)
        self._block = block
        self._duration = max(0.0, block.true_end - block.true_start)

        self.setWindowTitle("Duplicate Program")
        self.setModal(True)
        self.resize(420, 320)
        self.setStyleSheet(f"QDialog {{ background: {_PANEL_BG}; }} QLabel {{ color: {_TEXT_COLOR}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        heading = QLabel(f"Duplicate “{block.title}”")
        heading.setStyleSheet("font-size: 15px; font-weight: 700;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        channel_label = f"CH {lane.number} · {lane.name}" if lane is not None else "this channel"
        self._channel_label = channel_label

        original_lbl = QLabel(
            f"Original:\n{channel_label}\n{_time_label(block.true_start)}–{_time_label(block.true_end)}"
        )
        original_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px;")
        layout.addWidget(original_lbl)

        time_row = QHBoxLayout()
        time_row.setSpacing(10)
        time_row.addWidget(QLabel("New airing's start time:"))
        self._time_edit = QTimeEdit()
        self._time_edit.setDisplayFormat("h:mm AP")
        start_local = time.localtime(block.true_start)
        self._time_edit.setTime(QTime(start_local.tm_hour, start_local.tm_min))
        self._time_edit.timeChanged.connect(self._update_preview)
        time_row.addWidget(self._time_edit)
        time_row.addStretch(1)
        layout.addLayout(time_row)

        note = QLabel(
            "The original program stays exactly where it is — this adds one more airing "
            "on the same channel and date."
        )
        note.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 10px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._preview = QLabel("")
        self._preview.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px; font-weight: 600;")
        self._preview.setWordWrap(True)
        layout.addWidget(self._preview)
        layout.addStretch(1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self._duplicate_btn = QPushButton("Duplicate Program")
        self._duplicate_btn.clicked.connect(self.accept)
        button_row.addWidget(self._duplicate_btn)
        layout.addLayout(button_row)

        self._update_preview()

    def _update_preview(self):
        dest_start = self.destination_start()
        dest_end = dest_start + self._duration
        self._preview.setText(
            f"New airing:\n{self._channel_label}\n{_time_label(dest_start)}–{_time_label(dest_end)}"
        )

    def destination_start(self):
        qt_time = self._time_edit.time()
        return destination_epoch_for_time(self._block.true_start, qt_time.hour(), qt_time.minute())

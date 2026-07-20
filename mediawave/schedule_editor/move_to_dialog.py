"""MoveToDialog: the guided, non-drag reference implementation of moving a
program (Phase 3 spec section 3) -- built and tested before drag-and-drop
so there is always a precise, pointer-free way to move a program (keyboard
users, motor-limitation accessibility, exact time entry, or just a
preference for dialogs over dragging).

Phase 3 is same-channel-only (see commands.MoveProgramCommand's docstring
for why), so this dialog only ever lets the user change WHEN a program
airs, not which channel -- the destination channel is shown as fixed,
read-only text, with a plain note that cross-channel moves aren't
available yet.

Gathers a destination time only; validation, conflict handling, and
execution are all owned by the workspace (dialog.py), which reuses the
exact same MoveProgramCommand.validate() path this dialog and drag-and-
drop both go through -- no second mutation path for either interaction.
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

from .commands import snap_to_interval

_TEXT_COLOR = "rgba(210, 222, 252, 235)"
_DIM_COLOR = "rgba(138, 158, 212, 220)"
_PANEL_BG = "rgba(13, 16, 38, 255)"


def _time_label(epoch_seconds):
    return time.strftime("%I:%M %p", time.localtime(epoch_seconds)).lstrip("0")


def destination_epoch_for_time(reference_epoch, hour, minute):
    """The epoch for `hour:minute` on the SAME calendar day as
    `reference_epoch` (the program's current date, or the viewed date) --
    Phase 3 keeps the destination on that one date; there is no way for
    this dialog to express a different day. Snapped to the shared 5-minute
    interval (commands.snap_to_interval) so a manually-typed off-grid
    minute still lands on-grid, exactly like a drag drop would.
    """
    day = time.localtime(reference_epoch)
    candidate = time.struct_time((day.tm_year, day.tm_mon, day.tm_mday, hour, minute, 0, 0, 0, -1))
    return snap_to_interval(time.mktime(candidate))


class MoveToDialog(QDialog):
    """Returns the chosen destination start epoch via `destination_start()`
    after exec() == Accepted. `block` is the ProgramBlock being moved;
    `lane` is its ChannelLane (for the fixed From/To channel label).
    """

    def __init__(self, block, lane, parent=None):
        super().__init__(parent)
        self._block = block
        self._duration = max(0.0, block.true_end - block.true_start)

        self.setWindowTitle("Move Program")
        self.setModal(True)
        self.resize(420, 300)
        self.setStyleSheet(f"QDialog {{ background: {_PANEL_BG}; }} QLabel {{ color: {_TEXT_COLOR}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        heading = QLabel(f"Move “{block.title}”")
        heading.setStyleSheet("font-size: 15px; font-weight: 700;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        channel_label = f"CH {lane.number} · {lane.name}" if lane is not None else "this channel"

        from_lbl = QLabel(f"From:\n{channel_label}\n{_time_label(block.true_start)}–{_time_label(block.true_end)}")
        from_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px;")
        layout.addWidget(from_lbl)

        time_row = QHBoxLayout()
        time_row.setSpacing(10)
        time_row.addWidget(QLabel("New start time:"))
        self._time_edit = QTimeEdit()
        self._time_edit.setDisplayFormat("h:mm AP")
        start_local = time.localtime(block.true_start)
        self._time_edit.setTime(QTime(start_local.tm_hour, start_local.tm_min))
        self._time_edit.timeChanged.connect(self._update_preview)
        time_row.addWidget(self._time_edit)
        time_row.addStretch(1)
        layout.addLayout(time_row)

        note = QLabel("Moving between channels will be added later — this stays on the same channel and date.")
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
        self._move_btn = QPushButton("Move Program")
        self._move_btn.clicked.connect(self.accept)
        button_row.addWidget(self._move_btn)
        layout.addLayout(button_row)

        self._channel_label = channel_label
        self._update_preview()

    def _update_preview(self):
        dest_start = self.destination_start()
        dest_end = dest_start + self._duration
        self._preview.setText(f"To:\n{self._channel_label}\n{_time_label(dest_start)}–{_time_label(dest_end)}")

    def destination_start(self):
        qt_time = self._time_edit.time()
        return destination_epoch_for_time(self._block.true_start, qt_time.hour(), qt_time.minute())

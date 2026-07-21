"""CopyToAnotherDayDialog: the one-date copy workflow (Phase 3.1 spec
section 4) -- adds a QDateEdit on top of MoveToDialog/DuplicateHereDialog's
shape, since this is the one workflow that needs to ask about a
different CALENDAR DAY, not just a different time on the day already
being viewed.

This is explicitly NOT a recurring rule -- the dialog says so in plain
language, and updates that sentence live as the date changes so it never
goes stale next to whatever date is currently selected. Same-channel-only
for this phase, same reason as Move To…/Duplicate Here….
"""

import time

from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import (
    QDateEdit,
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


def destination_epoch_for_date_time(qdate, hour, minute):
    """The epoch for `hour:minute` on the given QDate -- snapped to the
    shared 5-minute interval, exactly like Move To…/Duplicate Here…'s own
    destination_epoch_for_time, just parameterized on an explicit date
    instead of "the same day as some reference epoch".
    """
    candidate = time.struct_time(
        (qdate.year(), qdate.month(), qdate.day(), hour, minute, 0, 0, 0, -1)
    )
    return snap_to_interval(time.mktime(candidate))


class CopyToAnotherDayDialog(QDialog):
    """Returns the chosen destination start epoch via
    `destination_start()` after exec() == Accepted. `block` is the
    ProgramBlock being copied; `lane` is its ChannelLane;
    `default_date_epoch`, if given, seeds the date picker (the workspace
    passes the day after the currently viewed date, a reasonable default
    for "copy this somewhere else").
    """

    def __init__(self, block, lane, default_date_epoch=None, parent=None):
        super().__init__(parent)
        self._block = block
        self._duration = max(0.0, block.true_end - block.true_start)

        self.setWindowTitle("Copy to Another Day")
        self.setModal(True)
        self.resize(440, 360)
        self.setStyleSheet(f"QDialog {{ background: {_PANEL_BG}; }} QLabel {{ color: {_TEXT_COLOR}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        heading = QLabel(f"Copy “{block.title}” to another day")
        heading.setStyleSheet("font-size: 15px; font-weight: 700;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        channel_label = f"CH {lane.number} · {lane.name}" if lane is not None else "this channel"
        self._channel_label = channel_label

        original_lbl = QLabel(
            f"Original\n{channel_label}\n"
            f"{time.strftime('%A, %B %-d', time.localtime(block.true_start))}\n"
            f"{_time_label(block.true_start)}–{_time_label(block.true_end)}"
        )
        original_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px;")
        layout.addWidget(original_lbl)

        date_row = QHBoxLayout()
        date_row.setSpacing(10)
        date_row.addWidget(QLabel("New date"))
        self._date_edit = QDateEdit()
        self._date_edit.setDisplayFormat("MMMM d, yyyy")
        self._date_edit.setCalendarPopup(True)
        today = QDate.currentDate()
        self._date_edit.setMinimumDate(today)
        seed = default_date_epoch if default_date_epoch is not None else (block.true_start + 24 * 3600)
        seed_local = time.localtime(seed)
        seed_date = QDate(seed_local.tm_year, seed_local.tm_mon, seed_local.tm_mday)
        self._date_edit.setDate(seed_date if seed_date >= today else today)
        self._date_edit.dateChanged.connect(self._update_preview)
        date_row.addWidget(self._date_edit)
        date_row.addStretch(1)
        layout.addLayout(date_row)

        time_row = QHBoxLayout()
        time_row.setSpacing(10)
        time_row.addWidget(QLabel("New start time"))
        self._time_edit = QTimeEdit()
        self._time_edit.setDisplayFormat("h:mm AP")
        start_local = time.localtime(block.true_start)
        self._time_edit.setTime(QTime(start_local.tm_hour, start_local.tm_min))
        self._time_edit.timeChanged.connect(self._update_preview)
        time_row.addWidget(self._time_edit)
        time_row.addStretch(1)
        layout.addLayout(time_row)

        note = QLabel("Moving between channels will be added later — this stays on the same channel.")
        note.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 10px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._one_date_lbl = QLabel("")
        self._one_date_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px; font-style: italic;")
        self._one_date_lbl.setWordWrap(True)
        layout.addWidget(self._one_date_lbl)

        self._preview = QLabel("")
        self._preview.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px; font-weight: 600;")
        self._preview.setWordWrap(True)
        layout.addWidget(self._preview)
        layout.addStretch(1)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn, 1)
        self._copy_btn = QPushButton("Copy Program")
        self._copy_btn.clicked.connect(self.accept)
        button_row.addWidget(self._copy_btn, 1)
        layout.addLayout(button_row)

        self._update_preview()

    def _update_preview(self):
        dest_start = self.destination_start()
        dest_end = dest_start + self._duration
        date_label = time.strftime("%A, %B %-d", time.localtime(dest_start))
        self._preview.setText(
            f"New airing\n{self._channel_label}\n{date_label}\n"
            f"{_time_label(dest_start)}–{_time_label(dest_end)}"
        )
        # Deliberately explicit, every time the date changes -- this is
        # the one sentence guaranteeing no user reads this as a recurring
        # weekly rule (Phase 3.1 spec section 4).
        self._one_date_lbl.setText(f"This adds one airing on {date_label} only.")

    def destination_start(self):
        qt_time = self._time_edit.time()
        return destination_epoch_for_date_time(self._date_edit.date(), qt_time.hour(), qt_time.minute())

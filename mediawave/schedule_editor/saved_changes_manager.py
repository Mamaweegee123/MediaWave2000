"""SavedChangesManagerDialog: lets users see and remove saved Schedule
Editor overrides for the currently viewed date without ever touching
schedule_overrides.json directly (Phase 2.1 spec section 5).

Reads the current override data through a getter (`overrides_data_get`)
rather than a one-time snapshot, because a successful removal round-trips
through the app's save pipeline and REASSIGNS the whole
`schedule_overrides_data` dict (channelsurfer2000.py's
remove_schedule_override_from_editor) -- a stale snapshot would show a
record that was just removed as if it still existed.
"""

import os
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mediawave.schedule_overrides import OVERRIDE_ACTION_ADD, override_media_status
from mediawave.studio.styles import build_scroll_area

_TEXT_COLOR = "rgba(210, 222, 252, 235)"
_DIM_COLOR = "rgba(138, 158, 212, 220)"
_PANEL_BG = "rgba(13, 16, 38, 255)"
_ROW_BG = "rgba(22, 26, 58, 200)"
_ATTENTION_BG = "rgba(64, 28, 26, 210)"
_HEADER_COLOR = "rgba(150, 190, 255, 235)"

_ACTION_BUTTON_STYLE = """
    QPushButton {
        min-width: 0px; min-height: 26px; padding: 4px 12px;
        border-radius: 6px; border: 1px solid rgba(96, 144, 255, 150);
        background: rgba(50, 70, 160, 110); color: rgba(222, 232, 255, 240);
        font-size: 11px; font-weight: 600;
    }
    QPushButton:hover { border: 1px solid rgba(120, 165, 255, 210); background: rgba(60, 84, 190, 150); color: white; }
"""
_DISMISS_BUTTON_STYLE = """
    QPushButton {
        min-width: 0px; min-height: 26px; padding: 4px 12px;
        border-radius: 6px; border: 1px solid rgba(158, 172, 210, 90);
        background: transparent; color: rgba(200, 210, 235, 220);
        font-size: 11px;
    }
    QPushButton:hover { border: 1px solid rgba(180, 195, 230, 160); background: rgba(60, 70, 100, 80); }
"""


def _time_range_label(start, end):
    start_label = time.strftime("%-I:%M", time.localtime(start))
    end_label = time.strftime("%-I:%M %p", time.localtime(end)).lstrip("0") or time.strftime("%-I:%M %p", time.localtime(end))
    return f"{start_label}–{end_label}"


def overrides_for_date(overrides_data, date_str):
    """Every override record for `date_str`, in file order -- shared by
    the manager's list-building and (indirectly, via the same function)
    anything else that needs "what's saved for the day being viewed".
    """
    records = (overrides_data or {}).get("overrides") or []
    return [record for record in records if record.get("date") == date_str]


def group_by_channel(records, channel_order):
    """`records` bucketed by channel_id, in `channel_order`'s order
    (matching the board's own channel ordering) -- channels with no
    records for the date are simply absent, never shown as an empty
    section.
    """
    by_channel = {}
    for record in records:
        by_channel.setdefault(record.get("channel_id", ""), []).append(record)
    return [(channel_id, by_channel[channel_id]) for channel_id, _label in channel_order if channel_id in by_channel]


class SavedChangesManagerDialog(QDialog):
    """`channel_order` is a list of (channel_id, label) in board order,
    e.g. [("media:/Movies", "Ch 1 · Movies"), ...] -- used both to decide
    display order and to label each section. `overrides_data_get()`
    returns the live schedule_overrides_data dict. `remove_fn(record)`
    returns (ok, error). `on_changed()`, if given, is called after any
    successful removal (the workspace hooks its own board refresh here).
    """

    def __init__(self, date_str, date_label, channel_order, overrides_data_get, remove_fn, on_changed=None, parent=None):
        super().__init__(parent)
        self._date_str = date_str
        self._channel_order = list(channel_order or [])
        self._channel_labels = dict(self._channel_order)
        self._overrides_data_get = overrides_data_get
        self._remove_fn = remove_fn
        self._on_changed = on_changed

        self.setWindowTitle("Saved Changes")
        self.setModal(True)
        self.resize(560, 620)
        self.setStyleSheet(f"QDialog {{ background: {_PANEL_BG}; }} QLabel {{ color: {_TEXT_COLOR}; }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(10)

        heading = QLabel(f"Saved schedule changes for {date_label}")
        heading.setStyleSheet("font-size: 14px; font-weight: 700;")
        outer.addWidget(heading)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(12)
        scroll = build_scroll_area(self._list_container)
        outer.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        outer.addLayout(button_row)

        self.refresh()

    def refresh(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        data = self._overrides_data_get() if self._overrides_data_get is not None else None
        records = overrides_for_date(data, self._date_str)
        if not records:
            empty = QLabel("No saved changes for this date. Your lineup matches the automatic schedule.")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px;")
            self._list_layout.addWidget(empty)
            self._list_layout.addStretch(1)
            return

        for channel_id, channel_records in group_by_channel(records, self._channel_order):
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(6)

            header = QLabel(self._channel_labels.get(channel_id, channel_id))
            header.setStyleSheet(f"color: {_HEADER_COLOR}; font-size: 12px; font-weight: 700;")
            section_layout.addWidget(header)

            for record in sorted(channel_records, key=lambda r: r.get("start", 0)):
                section_layout.addWidget(self._build_row(record))

            self._list_layout.addWidget(section)

        self._list_layout.addStretch(1)

    def _build_row(self, record):
        is_add = record.get("action") == OVERRIDE_ACTION_ADD
        status = override_media_status(record, os.path.isfile)

        row = QWidget()
        row.setStyleSheet(
            f"background: {_ATTENTION_BG if status == 'unresolved' else _ROW_BG}; border-radius: 8px;"
        )
        layout = QVBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        time_lbl = QLabel(_time_range_label(record["start"], record["end"]))
        time_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
        layout.addWidget(time_lbl)

        title_lbl = QLabel(record.get("title") or ("This program" if not is_add else "This media"))
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        if status == "unresolved":
            attention_lbl = QLabel(
                f"This saved change needs attention — “{record.get('title') or 'this media'}” "
                "could not be found in the current library."
            )
            attention_lbl.setWordWrap(True)
            attention_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
            layout.addWidget(attention_lbl)

            remove_btn = QPushButton("Remove Saved Change")
            remove_btn.setStyleSheet(_ACTION_BUTTON_STYLE)
            remove_btn.clicked.connect(lambda _checked=False, r=record: self._remove(r))
            button_row.addWidget(remove_btn)

            keep_btn = QPushButton("Keep for Later")
            keep_btn.setStyleSheet(_DISMISS_BUTTON_STYLE)
            keep_btn.clicked.connect(lambda: None)
            button_row.addWidget(keep_btn)
        else:
            status_lbl = QLabel("Added by you" if is_add else "Pulled by you")
            status_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
            layout.addWidget(status_lbl)

            action_btn = QPushButton("Remove Change" if is_add else "Restore Generated Schedule")
            action_btn.setStyleSheet(_ACTION_BUTTON_STYLE)
            action_btn.clicked.connect(lambda _checked=False, r=record: self._remove(r))
            button_row.addWidget(action_btn)

        button_row.addStretch(1)
        layout.addLayout(button_row)
        return row

    def _remove(self, record):
        if self._remove_fn is None:
            return
        ok, error = self._remove_fn(record)
        if not ok:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Couldn't remove this saved change")
            box.setText(
                (error or "Something went wrong while updating the saved schedule.")
                + "\n\nNothing was changed — you can try again."
            )
            box.exec()
            return
        self.refresh()
        if self._on_changed is not None:
            self._on_changed()

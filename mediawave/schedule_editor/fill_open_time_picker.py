"""FillOpenTimePickerDialog: a friendly, fit-ranked media picker for
filling a selected Open Time gap (Phase 3.1 spec section 6) -- a guided
UI workflow over the existing Put On Air command (spec section 7), not a
new mutation path: the workspace still builds a PutOnAirCommand from
whatever this dialog returns, through the exact same _try_put_on_air
Put On Air itself uses (including the existing longer-than-slot
Extend/Choose Something Else/Cancel conflict flow).

Shares its catalog and filtering with put_on_air_picker.py
(build_picker_catalog/filter_picker_items) -- the only new pieces are the
fit ranking (rank_items_by_fit) and the per-row fit label (fit_label),
both defined there so Put On Air's own picker could reuse them later
without a second catalog model.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from .put_on_air_picker import (
    _FILTERS,
    filter_picker_items,
    fit_label,
    format_duration_minutes,
    placement_preview_text,
    rank_items_by_fit,
)

_TEXT_COLOR = "rgba(210, 222, 252, 235)"
_DIM_COLOR = "rgba(138, 158, 212, 220)"
_PANEL_BG = "rgba(13, 16, 38, 255)"
_ROW_BG = "rgba(22, 26, 58, 200)"
_ROW_SELECTED = "rgba(50, 70, 160, 160)"
_ACCENT = "rgba(96, 144, 255, 170)"

_CHIP_STYLE = """
    QPushButton {
        min-width: 0px; min-height: 24px; padding: 3px 12px;
        border-radius: 12px; border: 1px solid rgba(68, 108, 235, 90);
        background: transparent; color: rgba(210, 222, 252, 220); font-size: 11px;
    }
    QPushButton:checked {
        background: rgba(50, 70, 160, 160); border: 1px solid rgba(96, 144, 255, 200);
        color: white;
    }
"""


class FillOpenTimePickerDialog(QDialog):
    """Choose what fills the selected Open Time gap. Returns the chosen
    catalog item via `selected_item()` after exec() == Accepted -- exactly
    the same item shape PutOnAirPickerDialog returns, so the workspace's
    existing `_try_put_on_air` needs no changes to accept it.
    """

    def __init__(self, items, channel_number, channel_name, gap_start, gap_duration, recent_paths=None, parent=None):
        super().__init__(parent)
        self._items = items
        self._recent_paths = list(recent_paths or [])
        self._channel_number = channel_number
        self._channel_name = channel_name
        self._gap_start = gap_start
        self._gap_duration = gap_duration
        self._mode = "All"
        self._selected = None

        self.setWindowTitle("Fill Open Time")
        self.setModal(True)
        self.resize(560, 640)
        self.setStyleSheet(
            f"QDialog {{ background: {_PANEL_BG}; }}"
            f"QLabel {{ color: {_TEXT_COLOR}; }}"
            f"QLineEdit {{ background: rgba(22, 26, 58, 232); color: {_TEXT_COLOR};"
            f" border: 1px solid rgba(68, 108, 235, 90); border-radius: 6px; padding: 6px 10px; }}"
            f"QListWidget {{ background: transparent; border: none; outline: none; }}"
            f"QListWidget::item {{ background: {_ROW_BG}; border-radius: 8px; margin: 3px 2px; padding: 8px 10px; color: {_TEXT_COLOR}; }}"
            f"QListWidget::item:selected {{ background: {_ROW_SELECTED}; border: 1px solid {_ACCENT}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        heading = QLabel(
            f"Find something to fill this open time on CH {channel_number} {channel_name}"
            f"  ·  {format_duration_minutes(gap_duration)} open"
        )
        heading.setStyleSheet("font-size: 13px; font-weight: 600;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        subheading = QLabel("Ranked so the best fit for this gap shows first.")
        subheading.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
        layout.addWidget(subheading)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search shows, movies, or channels…")
        self._search.textChanged.connect(self._refresh_list)
        layout.addWidget(self._search)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(6)
        self._chips = {}
        for mode in _FILTERS:
            chip = QPushButton(mode)
            chip.setCheckable(True)
            chip.setChecked(mode == self._mode)
            chip.setStyleSheet(_CHIP_STYLE)
            chip.clicked.connect(lambda _checked, m=mode: self._set_mode(m))
            chip_row.addWidget(chip)
            self._chips[mode] = chip
        chip_row.addStretch(1)
        layout.addLayout(chip_row)

        self._list = QListWidget()
        self._list.itemSelectionChanged.connect(self._on_selection)
        self._list.itemDoubleClicked.connect(lambda _item: self._confirm())
        layout.addWidget(self._list, 1)

        self._preview = QLabel("")
        self._preview.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px;")
        self._preview.setWordWrap(True)
        layout.addWidget(self._preview)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self._confirm_btn = QPushButton("Fill This Time")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm)
        button_row.addWidget(self._confirm_btn)
        layout.addLayout(button_row)

        self._refresh_list()

    def _set_mode(self, mode):
        self._mode = mode
        for name, chip in self._chips.items():
            chip.setChecked(name == mode)
        self._refresh_list()

    def _refresh_list(self):
        self._list.clear()
        visible = filter_picker_items(self._items, self._mode, self._search.text(), self._recent_paths)
        ranked = rank_items_by_fit(visible, self._gap_duration, self._recent_paths)
        for item in ranked[:400]:
            row = QListWidgetItem()
            if item["schedulable"]:
                fit_text = fit_label(item["duration"], self._gap_duration).splitlines()[0]
                duration_label = format_duration_minutes(item["duration"])
            else:
                fit_text = "Duration unknown"
                duration_label = "duration not known yet"
            parts = [f"{fit_text}  —  {item['title']}"]
            if item["episode_label"]:
                parts.append(item["episode_label"])
            parts.append(duration_label)
            if item["channel_name"]:
                parts.append(f"from {item['channel_name']}")
            row.setText("   ·   ".join(parts))
            row.setData(Qt.UserRole, item)
            if not item["schedulable"]:
                row.setFlags(row.flags() & ~Qt.ItemIsEnabled)
                row.setToolTip(
                    "MediaWave hasn't measured this file's exact runtime yet, so it can't be "
                    "scheduled into a timed slot. It will become available after the next catalog scan."
                )
            self._list.addItem(row)
        if not ranked:
            text = (
                "Nothing scheduled recently\n\nPrograms you put on air will appear here."
                if self._mode == "Recently Scheduled" and not (self._search.text() or "").strip()
                else "Nothing here matches yet."
            )
            placeholder = QListWidgetItem(text)
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsEnabled)
            self._list.addItem(placeholder)
        self._selected = None
        self._confirm_btn.setEnabled(False)
        self._preview.setText("")

    def _on_selection(self):
        rows = self._list.selectedItems()
        item = rows[0].data(Qt.UserRole) if rows else None
        self._selected = item if isinstance(item, dict) else None
        if self._selected is None:
            self._confirm_btn.setEnabled(False)
            self._preview.setText("")
            return
        self._confirm_btn.setEnabled(True)
        preview = placement_preview_text(self._selected, self._channel_number, self._channel_name, self._gap_start)
        if float(self._selected.get("duration", 0) or 0) > self._gap_duration:
            preview += "\nRuns past this open time — you'll be asked how to handle that."
        elif float(self._selected.get("duration", 0) or 0) < self._gap_duration:
            remaining = self._gap_duration - float(self._selected["duration"])
            preview += f"\nLeaves {format_duration_minutes(remaining)} of open time after it."
        self._preview.setText(preview)

    def _confirm(self):
        if self._selected is None:
            return
        self.accept()

    def selected_item(self):
        return self._selected

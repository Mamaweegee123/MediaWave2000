"""The Put On Air picker: a beginner-friendly catalog chooser for filling
an open time slot -- real catalog data (live media channels' show lists +
the app's duration cache), never a raw file dialog.

Catalog indexing is pure (build_picker_catalog / filter_picker_items, no
Qt) so tests can cover it headlessly; the dialog itself is a thin themed
list around those helpers. Items without a cached duration are still
listed but marked un-schedulable -- scheduling needs an exact duration,
and inventing one would break the board's duration-true geometry. Their
row explains this instead of silently hiding them.

"Recently Scheduled" is backed by the persisted history in
mediawave/schedule_editor/recent_media.py -- the workspace passes in
the paths of media it has recently placed into a lineup (Put On Air,
Duplicate Here…, Copy to Another Day…, Fill Open Time), newest first, so
this stays a pure display concern with no direct file access.

`rank_items_by_fit`/`fit_label`, below, back the Fill Open Time workflow
(Phase 3.1): a dedicated ranking that puts an exact-duration match first,
then closer-fitting shorter/longer media, over the same catalog this
module already builds -- no second catalog model.
"""

import os
import time

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
    QWidget,
)

from mediawave.local_media import parse_local_media

_FILTERS = ["All", "Shows", "Movies", "Recently Scheduled"]

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


def format_duration_minutes(seconds):
    minutes = max(1, round(float(seconds or 0) / 60))
    return f"{minutes} min"


def build_picker_catalog(channels_by_id, channel_names_by_id=None):
    """One entry per unique media file across every live media channel:
    {path, title, episode_label, media_type, duration, channel_name,
    schedulable}. Duration comes from the channels' shared duration cache;
    schedulable is False when no cached duration exists yet.
    """
    names = channel_names_by_id or {}
    items = []
    seen_paths = set()
    for channel_id, channel in (channels_by_id or {}).items():
        if getattr(channel, "channel_type", "media") != "media":
            continue
        duration_cache = getattr(channel, "duration_cache", {}) or {}
        for path in getattr(channel, "shows", []) or []:
            if not path or path in seen_paths:
                continue
            seen_paths.add(path)
            try:
                local = parse_local_media(path)
            except Exception:
                local = {}
            media_type = local.get("media_type", "tv") or "tv"
            title = local.get("show_name") or local.get("timeline_title") or os.path.basename(path)
            episode_label = ""
            if media_type == "tv":
                episode_bits = [bit for bit in (local.get("season_label"), local.get("episode_title")) if bit]
                if local.get("episode_number"):
                    episode_bits.insert(1 if episode_bits else 0, f"Episode {local['episode_number']}")
                episode_label = " · ".join(episode_bits)
            duration = float(duration_cache.get(path, 0) or 0)
            items.append(
                {
                    "path": path,
                    "title": title,
                    "detail_title": local.get("detail_title") or title,
                    "episode_label": episode_label,
                    "media_type": media_type,
                    "duration": duration,
                    "channel_name": names.get(channel_id, getattr(channel, "name", "")),
                    "schedulable": duration > 0,
                }
            )
    items.sort(key=lambda item: (item["title"].lower(), item["episode_label"]))
    return items


def filter_picker_items(items, mode="All", search="", recent_paths=None):
    """Pure filter used by the dialog: mode is one of _FILTERS; search
    matches title/episode/channel case-insensitively; Recently Scheduled
    keeps the recent_paths order (most recent first) -- paths no longer
    in the live catalog are simply absent from `items`, so a missing
    recent item is handled gracefully by just not appearing rather than
    erroring.
    """
    needle = (search or "").strip().lower()
    if mode == "Recently Scheduled":
        by_path = {item["path"]: item for item in items}
        chosen = [by_path[path] for path in (recent_paths or []) if path in by_path]
    elif mode == "Shows":
        chosen = [item for item in items if item["media_type"] == "tv"]
    elif mode == "Movies":
        chosen = [item for item in items if item["media_type"] == "movie"]
    else:
        chosen = list(items)
    if needle:
        chosen = [
            item
            for item in chosen
            if needle in item["title"].lower()
            or needle in item["detail_title"].lower()
            or needle in item["episode_label"].lower()
            or needle in item["channel_name"].lower()
        ]
    return chosen


# Fit tiers for Fill Open Time's ranking (Phase 3.1 spec section 6):
# 0 exact, 1 shorter-than-gap, 2 longer-than-gap, 3 unknown duration
# (never hidden, just always last -- there's no fit to rank it by).
# Seconds of slack for "exact" is a float-rounding tolerance, not a
# fuzzy-match window -- anything else is ranked purely by closeness.
_EXACT_FIT_TOLERANCE_SECONDS = 30


def fit_rank(item, gap_seconds, recent_paths=None):
    """Sort key for one catalog item against an Open Time gap of
    `gap_seconds`: (tier, distance_from_gap, recency_rank, title). Exact
    matches sort first, then closer-fitting shorter media, then
    closer-fitting longer media; within equally-close items, a recently
    scheduled one sorts ahead of an equally-close unfamiliar one.
    """
    if not item.get("schedulable"):
        return (3, 0.0, 0, item["title"].lower())
    duration = float(item.get("duration", 0) or 0)
    delta = duration - float(gap_seconds or 0)
    if abs(delta) <= _EXACT_FIT_TOLERANCE_SECONDS:
        tier = 0
    elif delta < 0:
        tier = 1
    else:
        tier = 2
    recency_rank = 0 if item["path"] in (recent_paths or []) else 1
    return (tier, abs(delta), recency_rank, item["title"].lower())


def rank_items_by_fit(items, gap_seconds, recent_paths=None):
    """`items` sorted for Fill Open Time -- see fit_rank's docstring for
    the exact ordering. Stable Python sort, so items tied on every key
    keep their incoming (alphabetical) order.
    """
    return sorted(items, key=lambda item: fit_rank(item, gap_seconds, recent_paths))


def fit_label(duration_seconds, gap_seconds):
    """The two-line fit explanation shown per row in Fill Open Time --
    never hides an overrun (Phase 3.1 spec section 6): "Perfect fit",
    "Leaves N min open", or "Runs N min long", each followed by the exact
    "X min for Y min open time" comparison.
    """
    duration_seconds = float(duration_seconds or 0)
    gap_seconds = float(gap_seconds or 0)
    comparison = f"{format_duration_minutes(duration_seconds)} for {format_duration_minutes(gap_seconds)} open time"
    delta = duration_seconds - gap_seconds
    if abs(delta) <= _EXACT_FIT_TOLERANCE_SECONDS:
        return f"Perfect fit\n{comparison}"
    minutes = max(1, round(abs(delta) / 60))
    if delta < 0:
        return f"Leaves {minutes} min open\n{comparison}"
    return f"Runs {minutes} min long\n{comparison}"


def placement_preview_text(item, channel_number, channel_name, slot_start):
    """The confirmation line: `Put “Samurai Cop” on CH 1 Movies,
    11:30 PM–1:06 AM`.
    """
    end = slot_start + float(item.get("duration", 0) or 0)
    start_label = time.strftime("%I:%M %p", time.localtime(slot_start)).lstrip("0")
    end_label = time.strftime("%I:%M %p", time.localtime(end)).lstrip("0")
    return f"Put “{item['title']}” on CH {channel_number} {channel_name}\n{start_label}–{end_label}"


class PutOnAirPickerDialog(QDialog):
    """Choose something real to put on air. Returns the chosen catalog
    item via `selected_item()` after exec() == Accepted.
    """

    def __init__(self, items, channel_number, channel_name, slot_start, slot_duration, recent_paths=None, parent=None):
        super().__init__(parent)
        self._items = items
        self._recent_paths = list(recent_paths or [])
        self._channel_number = channel_number
        self._channel_name = channel_name
        self._slot_start = slot_start
        self._slot_duration = slot_duration
        self._mode = "All"
        self._selected = None

        self.setWindowTitle("Put On Air")
        self.setModal(True)
        self.resize(560, 620)
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

        slot_label = time.strftime("%I:%M %p", time.localtime(slot_start)).lstrip("0")
        heading = QLabel(
            f"Choose what airs on CH {channel_number} {channel_name} at {slot_label}"
            f"  ·  {format_duration_minutes(slot_duration)} open"
        )
        heading.setStyleSheet("font-size: 13px; font-weight: 600;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

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
        self._confirm_btn = QPushButton("Put On Air")
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
        for item in visible[:400]:
            duration_label = format_duration_minutes(item["duration"]) if item["schedulable"] else "duration not known yet"
            parts = [item["title"]]
            if item["episode_label"]:
                parts.append(item["episode_label"])
            parts.append(duration_label)
            if item["channel_name"]:
                parts.append(f"from {item['channel_name']}")
            row = QListWidgetItem("   ·   ".join(parts))
            row.setData(Qt.UserRole, item)
            if not item["schedulable"]:
                row.setFlags(row.flags() & ~Qt.ItemIsEnabled)
                row.setToolTip(
                    "MediaWave hasn't measured this file's exact runtime yet, so it can't be "
                    "scheduled into a timed slot. It will become available after the next catalog scan."
                )
            self._list.addItem(row)
        if not visible:
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
        preview = placement_preview_text(self._selected, self._channel_number, self._channel_name, self._slot_start)
        if float(self._selected.get("duration", 0) or 0) > self._slot_duration:
            preview += "\nRuns past the open time — you'll be asked how to handle that."
        elif float(self._selected.get("duration", 0) or 0) < self._slot_duration:
            remaining = self._slot_duration - float(self._selected["duration"])
            preview += f"\nLeaves {format_duration_minutes(remaining)} of open time after it."
        self._preview.setText(preview)

    def _confirm(self):
        if self._selected is None:
            return
        self.accept()

    def selected_item(self):
        return self._selected

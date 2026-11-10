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
import random
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from mediawave.local_media import parse_local_media
from mediawave.show_identity import (
    SHOW_BEHAVIOR_RANDOM,
    SHOW_BEHAVIOR_SEQUENTIAL,
    _catalog_relative_folder_path,
    add_folder_show_rule,
    empty_registry,
    group_catalog_by_show,
    resolve_show_identity,
    show_behavior_for,
)

from .autofill_cursor import last_aired_path_for
from .autofill_planner import episode_sort_key

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


def build_picker_catalog(channels_by_id, channel_names_by_id=None, show_identity_registry=None):
    """One entry per unique media file across every live media channel:
    {path, title, episode_label, media_type, duration, channel_name,
    schedulable}. Duration comes from the channels' shared duration cache;
    schedulable is False when no cached duration exists yet.

    `show_identity_registry` (Phase 5.5.2 step 2) is an already-loaded
    mediawave.show_identity registry dict, or None -- this module never
    loads the registry file itself; the application owns that and passes
    the in-memory result in, same as it already owns channels_by_id. None
    behaves exactly like an empty registry: every show resolves as
    provisional, so an untouched library's `show_key` values are
    bit-for-bit identical to calling metadata_lookup_key directly, same as
    before this parameter existed.
    """
    names = channel_names_by_id or {}
    registry = show_identity_registry if show_identity_registry is not None else empty_registry()
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
            identity = resolve_show_identity(path, local, registry, channel_id=channel_id)
            raw_media_type = local.get("media_type", "tv") or "tv"
            # Trust the resolved identity's own media_type over the raw
            # parse when they disagree -- the only time they ever do is a
            # folder rule (Phase 5.5.5, Treat Folder as Show): a file
            # parse_local_media guessed was a "movie" (no season/episode
            # pattern) that the user has explicitly declared belongs to a
            # TV show. This never touches parse_local_media's own output
            # or the file on disk -- it's catalog/scheduling metadata
            # only, and every existing consumer (group_catalog_by_show,
            # plan_rotate_shows, filter_picker_items) already keys off
            # this exact `media_type` field, so promoting it here is all
            # that's needed for those items to start being treated as
            # episodes of one show, with zero changes to any of them.
            media_type = identity.get("media_type") or raw_media_type
            title = local.get("show_name") or local.get("timeline_title") or os.path.basename(path)
            episode_label = ""
            if media_type == "tv":
                episode_bits = [bit for bit in (local.get("season_label"), local.get("episode_title")) if bit]
                if local.get("episode_number"):
                    episode_bits.insert(1 if episode_bits else 0, f"Episode {local['episode_number']}")
                episode_label = " · ".join(episode_bits)
                if not episode_label and raw_media_type != "tv":
                    # A folder-as-show file with no season/episode pattern
                    # at all -- fall back to its own file-derived title
                    # rather than showing a blank episode label. Never a
                    # fake "S1E1"; see the module docstring/Phase 5.5.5.
                    episode_label = local.get("timeline_title") or local.get("show_name") or ""
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
                    # Auto-Fill Block's "Continue Sequentially"/"Show Marathon"
                    # strategies (autofill_planner.py) need real episode order,
                    # not just the display label -- same season/episode
                    # fields media_lineup_sort_key already uses elsewhere, so
                    # ordering here can never disagree with the rest of the
                    # app. None for movies/unmatched TV, meaning "unordered".
                    "season_number": local.get("season_number"),
                    "episode_number": local.get("episode_number"),
                    # Just the episode's own title, distinct from
                    # episode_label above (which already prefixes season/
                    # episode text for the flat list's row) -- Phase 5.2's
                    # Show behavior preview needs the bare title to build
                    # its own "S2 · E4 — Title" line without re-parsing
                    # episode_label. Empty for movies/specials with no
                    # parsed title -- EXCEPT a folder-as-show file (Phase
                    # 5.5.5), which falls back to its own file-derived
                    # title so a Continue Sequentially preview line still
                    # has something real to show, never a blank string.
                    "episode_title": local.get("episode_title") or (local.get("timeline_title") or local.get("show_name") or "" if media_type == "tv" and raw_media_type != "tv" else ""),
                    # The stable per-show identity autofill_cursor.py keys
                    # its saved "Continue Sequentially" cursor on, NOT
                    # `title`, since two different shows can share a
                    # display title but never this key, and one show's
                    # title can change without its key changing. As of
                    # Phase 5.5.2, this is the REGISTRY-RESOLVED canonical
                    # identity (mediawave.show_identity.resolve_show_
                    # identity): an untouched show's key is still exactly
                    # metadata_lookup_key's own output; a user-corrected
                    # show's key is the registry's opaque show_<uuid>
                    # instead. Every existing consumer of `show_key`
                    # (scheduling.py, autofill_planner.py, autofill_
                    # cursor.py, programming_blocks.py) keeps working
                    # unchanged either way, since it was always just an
                    # opaque grouping string to them.
                    "show_key": identity["show_key"],
                    # Always metadata_lookup_key's raw output, even when
                    # `show_key` above was resolved to a corrected
                    # identity -- callers doing alias/migration bookkeeping
                    # need this regardless of correction state.
                    "raw_show_key": identity["raw_show_key"],
                    # "override" if a registry alias or folder rule
                    # resolved this item, else "parsed" -- lets a future
                    # UI show which shows are corrected without re-deriving
                    # it from the registry itself.
                    "show_identity_source": identity["source"],
                    # The show-level corrected display name, kept
                    # DELIBERATELY separate from `title`/`episode_title`/
                    # `detail_title` above -- those describe this concrete
                    # episode/movie file and must never be overwritten by a
                    # show-level rename. Empty for an uncorrected show;
                    # group_catalog_by_show falls back to `title` in that
                    # case, so grouping is unaffected until a real
                    # correction exists.
                    "show_display_name": identity["display_name"] if identity["source"] == "override" else "",
                    # Phase 5.5.5 (Treat Folder as Show): which channel
                    # this file came from and that channel's own media
                    # root -- needed to derive a catalog-root-relative
                    # folder path (mediawave.show_identity.
                    # add_folder_show_rule) and to scope the resulting
                    # folder rule to the right channel. Nothing before
                    # this phase read either field from a catalog item;
                    # both are purely additive.
                    "channel_id": channel_id,
                    "catalog_root": getattr(channel, "_root_path", "") or getattr(channel, "root_path", "") or "",
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


class TreatFolderAsShowDialog(QDialog):
    """Phase 5.5.5: "MediaWave thought these were separate videos; now it
    knows they are one show." Same tiny, friendly correction language as
    Rename/Merge Show -- no "folder rule"/"registry"/"canonical key"/
    "path prefix" language anywhere in the UI. `compatible_count` is
    however many videos the caller already found in this folder (from
    the current catalog, not a fresh disk scan); the full catalog-
    relative path is shown only as a small secondary hint line, never as
    the dialog's main content, and never the absolute machine path.
    """

    def __init__(self, folder_display_name, compatible_count, folder_path_hint="", parent=None):
        super().__init__(parent)
        self._compatible_count = compatible_count
        self.setWindowTitle("Treat Folder as Show")
        self.setModal(True)
        self.resize(400, 280)
        self.setStyleSheet(
            f"QDialog {{ background: {_PANEL_BG}; }}"
            f"QLabel {{ color: {_TEXT_COLOR}; }}"
            f"QLineEdit {{ background: rgba(22, 26, 58, 232); color: {_TEXT_COLOR};"
            f" border: 1px solid rgba(68, 108, 235, 90); border-radius: 6px; padding: 6px 10px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        heading = QLabel("Treat Folder as Show")
        heading.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(heading)

        context_lbl = QLabel(f"Folder: {folder_display_name}")
        context_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px;")
        context_lbl.setWordWrap(True)
        layout.addWidget(context_lbl)

        field_label = QLabel("Show name")
        field_label.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
        layout.addWidget(field_label)
        self._name_edit = QLineEdit(folder_display_name)
        self._name_edit.selectAll()
        self._name_edit.textChanged.connect(self._refresh_validity)
        layout.addWidget(self._name_edit)

        video_word = "video" if compatible_count == 1 else "videos"
        self._summary_label = QLabel(f"{compatible_count} {video_word} found")
        self._summary_label.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px; font-weight: 600;")
        layout.addWidget(self._summary_label)

        scope_lbl = QLabel("This folder only")
        scope_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
        layout.addWidget(scope_lbl)

        helper = QLabel("MediaWave will group compatible videos in this folder as one show. Your files and folders will not be changed.")
        helper.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        if folder_path_hint:
            path_lbl = QLabel(folder_path_hint)
            path_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 10px;")
            path_lbl.setWordWrap(True)
            layout.addWidget(path_lbl)

        layout.addStretch(1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self._create_btn = QPushButton("Create Show")
        self._create_btn.clicked.connect(self.accept)
        button_row.addWidget(self._create_btn)
        layout.addLayout(button_row)

        self._refresh_validity()
        self._name_edit.setFocus()

    def _refresh_validity(self, *_args):
        self._create_btn.setEnabled(bool(self._name_edit.text().strip()) and self._compatible_count > 0)

    def new_show_name(self):
        return self._name_edit.text().strip()


class PutOnAirPickerDialog(QDialog):
    """Choose something real to put on air. Returns the chosen catalog
    item via `selected_item()` after exec() == Accepted.

    Phase 5.5.5: right-clicking a movie/unclassified row offers "Treat
    Folder as Show…" -- the one entry point into this correction, so it
    isn't duplicated across every picker. See _show_context_menu/
    _treat_folder_as_show_clicked/_apply_treat_folder_as_show below.
    """

    def __init__(self, items, channel_number, channel_name, slot_start, slot_duration, recent_paths=None, parent=None, initial_mode="All", show_identity_registry=None, show_identity_registry_save=None):
        super().__init__(parent)
        # Phase 5.5.5: this dialog owns the mutation+save directly
        # (unlike Rename/Merge Show, which delegate up to
        # ProgrammingBlockLibraryDialog) since it's the one and only
        # place Treat Folder as Show is reachable from, and refreshing
        # just needs to re-render this dialog's own list.
        self._show_identity_registry = show_identity_registry if isinstance(show_identity_registry, dict) else empty_registry()
        self._show_identity_registry_save = show_identity_registry_save
        self._items = items
        self._recent_paths = list(recent_paths or [])
        self._channel_number = channel_number
        self._channel_name = channel_name
        self._slot_start = slot_start
        self._slot_duration = slot_duration
        self._mode = initial_mode if initial_mode in _FILTERS else "All"
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
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
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

    def _show_context_menu(self, pos):
        """Phase 5.5.5's one entry point: right-click a movie/
        unclassified row for "Treat Folder as Show…". Absent entirely
        (no menu at all) when no save path is available or the row isn't
        a movie -- same "an action that can never work has no reason to
        be visible" rule Rename/Merge Show's row overflow menu follows.
        """
        row = self._list.itemAt(pos)
        item = row.data(Qt.UserRole) if row is not None else None
        if not isinstance(item, dict) or item.get("media_type") != "movie" or self._show_identity_registry_save is None:
            return
        menu = QMenu(self)
        action = menu.addAction("Treat Folder as Show…")
        action.triggered.connect(lambda: self._treat_folder_as_show_clicked(item))
        menu.exec(self._list.mapToGlobal(pos))

    def _treat_folder_as_show_clicked(self, item):
        """Collects the folder's currently-compatible items from THIS
        dialog's own already-built `self._items` (no filesystem rescan --
        the catalog already has everything build_picker_catalog found),
        detects ambiguity (more than one already-corrected show already
        present in the folder), and opens TreatFolderAsShowDialog to
        collect the final name before ever mutating/saving anything.
        """
        target_folder = os.path.dirname(item["path"])
        channel_id = item.get("channel_id") or ""
        catalog_root = item.get("catalog_root") or ""
        relative_path = _catalog_relative_folder_path(catalog_root, target_folder)
        if not relative_path:
            QMessageBox.warning(
                self,
                "Can't treat this folder as a show",
                "This file isn't inside a recognized catalog folder, so MediaWave can't create a show from it.",
            )
            return

        folder_items = [
            other for other in self._items
            if other.get("channel_id") == channel_id and os.path.dirname(other["path"]) == target_folder
        ] or [item]

        corrected_keys = {entry["show_key"] for entry in folder_items if entry.get("show_identity_source") == "override"}
        if len(corrected_keys) > 1:
            QMessageBox.warning(
                self,
                "Multiple shows found in this folder",
                "This folder already contains more than one corrected show. Use Merge Shows to combine them first, then try again.",
            )
            return
        target_show_key = next(iter(corrected_keys), None)
        provisional_keys = sorted({entry["raw_show_key"] for entry in folder_items if entry.get("show_identity_source") != "override"})

        folder_display_name = os.path.basename(target_folder) or target_folder
        dialog = TreatFolderAsShowDialog(folder_display_name, len(folder_items), folder_path_hint=relative_path, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        final_name = dialog.new_show_name()
        if not final_name:
            return
        ok, error = self._apply_treat_folder_as_show(channel_id, catalog_root, target_folder, final_name, target_show_key, provisional_keys)
        if not ok:
            QMessageBox.warning(self, "Couldn't create this show", error or "An unknown error occurred.")

    def _apply_treat_folder_as_show(self, channel_id, catalog_root, folder_path, display_name, target_show_key, provisional_keys):
        """Treat Folder as Show's actual mutation+save -- mirrors Rename/
        Merge Show's _apply_show_* pattern exactly: pure helper -> save
        callback -> only on success, patch this dialog's own in-memory
        `_items` and re-render. `media_type` is force-set to "tv" on the
        affected items here (not by a fresh catalog rebuild) -- the same
        override resolve_show_identity/build_picker_catalog will apply
        naturally the NEXT time the catalog is rebuilt from the (now
        updated) registry, but items already in memory need it applied
        directly so the picker's own "Shows"/"Movies" filter reflects the
        correction immediately without a rescan.
        """
        if self._show_identity_registry_save is None:
            return False, "Treat Folder as Show isn't available in this context."
        try:
            new_registry, canonical_key, _rule_id, _redirect_map = add_folder_show_rule(
                self._show_identity_registry,
                channel_id=channel_id,
                catalog_root=catalog_root,
                folder_path=folder_path,
                display_name=display_name,
                target_show_key=target_show_key,
                provisional_raw_keys=provisional_keys,
                now=time.time(),
            )
        except ValueError as error:
            return False, str(error)
        ok, error = self._show_identity_registry_save(new_registry)
        if not ok:
            return ok, error
        self._show_identity_registry = new_registry
        self._items = [
            dict(item, show_key=canonical_key, show_display_name=display_name, show_identity_source="override", media_type="tv")
            if item.get("channel_id") == channel_id and os.path.dirname(item["path"]) == folder_path
            else item
            for item in self._items
        ]
        self._refresh_list()
        return True, ""


# ── Phase 5.1: schedule a show, not an episode ──────────────────────────
#
# Programming Items are an internal grouping over this same flat catalog,
# not a new data model: group_catalog_by_show (mediawave.show_identity,
# Phase 5.5.2) groups build_picker_catalog's existing rows by the
# show_key they already carry -- the one shared grouping helper the Add-
# to-Schedule flow, Auto-Fill Block, and the Programming Block dialog all
# use, replacing what used to be independently-duplicated local copies --
# and first_available_episode resolves a chosen show down to ONE ordinary
# catalog item before anything reaches PutOnAirCommand. Nothing downstream
# of that resolution -- DraftChange, commands.py, saved overrides -- ever
# learns a show was involved.


def show_summary(show):
    """(episode_count, season_count) for one group_catalog_by_show entry.
    season_count is None when no episode carries a season_number (nothing
    to count), so the row can say "12 episodes" instead of a false "0
    seasons". Both are precomputed by group_catalog_by_show itself; this
    is just a small named accessor so callers don't reach into the dict
    directly.
    """
    return show.get("episode_count", 0), show.get("season_count")


def _initial_episode_sort_key(item):
    """Ordering for "pick the show's first episode" ONLY -- deliberately
    a separate key from autofill_planner.episode_sort_key rather than a
    change to it: episode_sort_key's plain numeric (season, episode)
    order is already relied on by Continue Sequentially/Show Marathon
    (autofill_dialog.py:148) to tile a whole show in numeric order,
    where a Season 0 special sorting before Season 1 is that feature's
    existing, established behavior -- changing it here would silently
    change what marathons/sequential fill produce.

    "Schedule this show" has a different, narrower goal: land on the
    regular series premiere, not whatever sorts first numerically. So
    this key groups before it sorts: numbered regular seasons (>= 1)
    first, Season 0/specials next, and anything with unknown season or
    episode metadata last regardless of group -- then plain numeric
    order within each group, same fallback-to-last convention
    episode_sort_key uses for missing numbers.
    """
    season = item.get("season_number")
    episode = item.get("episode_number")
    try:
        season_number = int(season)
    except (TypeError, ValueError):
        season_number = None
    try:
        episode_number = int(episode)
    except (TypeError, ValueError):
        episode_number = None

    if season_number is None or episode_number is None:
        group = 2
    elif season_number == 0:
        group = 1
    else:
        group = 0
    return (group, season_number if season_number is not None else 9999, episode_number if episode_number is not None else 9999, item.get("path", ""))


def first_available_episode(show):
    """The one episode Version 1's "schedule a show" picks: the earliest
    regular-season episode (Season 1 up) among this show's schedulable
    episodes, falling back to specials and then to anything with
    unresolved season/episode metadata only if no regular episode
    exists -- see _initial_episode_sort_key. None if the show has no
    schedulable episode at all yet (e.g. durations not measured),
    matching build_picker_catalog's own "list it, don't hide it, but
    don't let it be chosen" treatment of un-timed media.
    """
    schedulable = [ep for ep in (show.get("episodes") or []) if ep.get("schedulable")]
    if not schedulable:
        return None
    return sorted(schedulable, key=_initial_episode_sort_key)[0]


# ── Phase 5.2: Continue Sequentially / Random Episode ───────────────────
#
# resolve_show_episode is the one place a chosen show + behavior becomes
# ONE ordinary catalog item -- a plain dict, no Qt, no DraftChange. It
# reuses autofill_planner.episode_sort_key for the "what comes after the
# cursor" question (the same order Continue Sequentially/Show Marathon
# already tile a block in) and first_available_episode/
# _initial_episode_sort_key (Follow-up A) only for the "no real cursor
# yet" starting point -- so an ACTIVE cursor's wraparound behaves exactly
# like Auto-Fill's Continue Sequentially already does, and only the
# no-history starting point gets Follow-up A's "regular season first"
# treatment.

BEHAVIOR_SEQUENTIAL = "sequential"
BEHAVIOR_RANDOM = "random"


def resolve_show_episode(show, behavior, last_path=None, rng=None):
    """One schedulable episode from `show`, chosen per `behavior`
    ("sequential" or "random"). Always a COPY of the catalog item (never
    the original dict from `show["episodes"]`), so callers -- and
    re-selecting a show, or Choose Again -- can never mutate the input
    catalog. Returns None if the show has no schedulable episode.

    Sequential: continues after `last_path` (typically resolved by the
    caller via autofill_cursor.last_aired_path_for -- this function never
    looks up a cursor itself, matching plan_continue_sequentially's own
    "caller resolves storage" contract) using the same order/wraparound
    Continue Sequentially/Show Marathon already use; falls back to
    first_available_episode when there's no last_path, or it no longer
    matches a schedulable episode. The result carries `strategy` and
    `show_key` so commands.py's existing `_sequential_cursor_meta` can
    recognize it as a Continue-Sequentially placement worth advancing the
    shared cursor for once saved (see dialog.py's save-time hook).

    Random: `rng.choice` (defaults to the `random` module) over every
    schedulable episode, uniformly -- no ordering, no cursor lookup, and
    the result carries no `strategy`, so it is never mistaken for a
    sequential placement and never advances any cursor.
    """
    schedulable = [ep for ep in (show.get("episodes") or []) if ep.get("schedulable")]
    if not schedulable:
        return None

    if behavior == BEHAVIOR_RANDOM:
        chooser = rng.choice if rng is not None else random.choice
        return dict(chooser(schedulable))

    if behavior != BEHAVIOR_SEQUENTIAL:
        raise ValueError(f"Unknown show behavior: {behavior!r}")

    ordered = sorted(schedulable, key=episode_sort_key)
    next_episode = None
    if last_path:
        match = next((i for i, ep in enumerate(ordered) if ep.get("path") == last_path), None)
        if match is not None:
            next_episode = ordered[(match + 1) % len(ordered)]
    if next_episode is None:
        next_episode = first_available_episode(show)
    result = dict(next_episode)
    result["strategy"] = BEHAVIOR_SEQUENTIAL
    result["show_key"] = show.get("show_key")
    return result


def sequential_preview_note(show, last_path):
    """The honest fallback sentence to show INSTEAD of "Next: ..." when
    Continue Sequentially isn't actually continuing anything -- None
    means a real cursor was found and used, so the caller should show the
    resolved episode normally. Kept separate from resolve_show_episode
    (which only ever returns an episode, per its own contract) so the
    dialog can explain WHY it landed where it did without resolve_show_
    episode needing to know anything about UI text.
    """
    if not last_path:
        return "Starts with the first available episode."
    schedulable_paths = {ep.get("path") for ep in (show.get("episodes") or []) if ep.get("schedulable")}
    if last_path not in schedulable_paths:
        return "The previous episode is no longer available, so this starts with the first available episode."
    return None


def _episode_preview_label(episode):
    """"S2 · E4 — The Episode Title" -- the compact descriptive part
    Continue Sequentially/Random Episode previews build their sentence
    around, or None if there's nothing distinct enough to show at all
    (the caller then falls back to a generic "Next available episode" /
    "Selected episode" sentence rather than this function inventing
    something to fill the gap).

    `episode_title` is only used when it's actually distinct from the
    show's own display title (`title`) -- build_picker_catalog leaves
    `episode_title` empty for a lot of real content (movies, clip shows,
    anything parse_local_media couldn't find a per-episode title for),
    and repeating the SHOW's name after an em dash reads as if that were
    the episode's title ("Next: S1 · E2 — No Title Show"), which is more
    confusing than just omitting it. Season 0 reads as "Special" rather
    than "S0", matching the Specials concept elsewhere; a present-but-
    unknown season/episode number shows "?" rather than silently
    disappearing, since a preview should never look more confident about
    the data than build_picker_catalog actually is -- but the numbering
    segment is left out ENTIRELY when neither number exists, rather than
    showing a bare "S? · E?".
    """
    season = episode.get("season_number")
    episode_number = episode.get("episode_number")
    numbering = None
    if season is not None or episode_number is not None:
        season_label = "Special" if season == 0 else (f"S{season}" if season is not None else "S?")
        episode_label = f"E{episode_number}" if episode_number is not None else "E?"
        numbering = f"{season_label} · {episode_label}"

    episode_title = (episode.get("episode_title") or "").strip()
    show_title = (episode.get("title") or "").strip()
    distinct_title = episode_title if episode_title and episode_title.casefold() != show_title.casefold() else ""

    if numbering and distinct_title:
        return f"{numbering} — {distinct_title}"
    if numbering:
        return numbering
    if distinct_title:
        return distinct_title
    return None


class ShowPickerDialog(QDialog):
    """Add to Schedule -> Shows: one row per show, not per episode, plus
    (Phase 5.2) a compact Continue Sequentially / Random Episode choice
    once a show is selected. Confirming always schedules whatever the
    preview is currently showing -- selected_episode() returns that exact
    previewed item, never a freshly re-resolved one, so what the user saw
    is what gets placed.
    """

    def __init__(self, shows_by_key, channel_number, channel_name, slot_start, slot_duration, channel_id=None, cursor_data=None, show_identity_registry=None, parent=None):
        super().__init__(parent)
        self._shows = shows_by_key
        self._channel_number = channel_number
        self._channel_name = channel_name
        self._slot_start = slot_start
        self._slot_duration = slot_duration
        self._channel_id = channel_id
        self._cursor_data = cursor_data
        # Phase 5.5.2 step 4: threaded into last_aired_path_for's alias
        # search below, so Continue Sequentially still finds a legacy
        # cursor row saved before this show was corrected.
        self._show_identity_registry = show_identity_registry
        self._selected_show_key = None
        self._behavior = BEHAVIOR_SEQUENTIAL
        self._previewed_episode = None

        self.setWindowTitle("Choose a Show")
        self.setModal(True)
        self.resize(480, 560)
        self.setStyleSheet(
            f"QDialog {{ background: {_PANEL_BG}; }}"
            f"QLabel {{ color: {_TEXT_COLOR}; }}"
            f"QListWidget {{ background: transparent; border: none; outline: none; }}"
            f"QListWidget::item {{ background: {_ROW_BG}; border-radius: 8px; margin: 3px 2px; padding: 10px 12px; color: {_TEXT_COLOR}; }}"
            f"QListWidget::item:selected {{ background: {_ROW_SELECTED}; border: 1px solid {_ACCENT}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        slot_label = time.strftime("%I:%M %p", time.localtime(slot_start)).lstrip("0")
        heading = QLabel(f"Choose a show for CH {channel_number} {channel_name} at {slot_label}")
        heading.setStyleSheet("font-size: 13px; font-weight: 600;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        self._list = QListWidget()
        self._list.itemSelectionChanged.connect(self._on_selection)
        self._list.itemDoubleClicked.connect(lambda _item: self._confirm())
        layout.addWidget(self._list, 1)

        # Behavior choice -- hidden until a show is selected, so a
        # beginner who hasn't picked anything yet isn't shown a control
        # with nothing to act on. Two radio buttons, not a combo box or a
        # settings-style form: this is the one decision this dialog asks
        # for, and it should read as "one small choice", not "a settings
        # page" (Phase 5.2 spec).
        self._behavior_row = QWidget()
        behavior_layout = QHBoxLayout(self._behavior_row)
        behavior_layout.setContentsMargins(0, 0, 0, 0)
        behavior_layout.setSpacing(14)
        self._sequential_radio = QRadioButton("Continue Sequentially")
        self._sequential_radio.setChecked(True)
        self._random_radio = QRadioButton("Random Episode")
        self._behavior_group = QButtonGroup(self)
        self._behavior_group.addButton(self._sequential_radio)
        self._behavior_group.addButton(self._random_radio)
        self._sequential_radio.toggled.connect(self._on_behavior_changed)
        behavior_layout.addWidget(self._sequential_radio)
        behavior_layout.addWidget(self._random_radio)
        behavior_layout.addStretch(1)
        self._choose_again_btn = QPushButton("Choose Again")
        self._choose_again_btn.clicked.connect(self._choose_again)
        behavior_layout.addWidget(self._choose_again_btn)
        self._behavior_row.setVisible(False)
        layout.addWidget(self._behavior_row)

        # Phase 5.6: when the selected show has a saved Episode Behavior,
        # a small dim note under the radios makes it visible that the
        # preselection isn't arbitrary -- "this show remembers a
        # preference" -- without turning the picker into a settings
        # screen. Hidden whenever the selected show has no saved behavior
        # (Channel Default) or nothing is selected yet.
        self._saved_behavior_label = QLabel("")
        self._saved_behavior_label.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
        self._saved_behavior_label.setVisible(False)
        layout.addWidget(self._saved_behavior_label)

        self._preview = QLabel("")
        self._preview.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px;")
        self._preview.setWordWrap(True)
        layout.addWidget(self._preview)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self._confirm_btn = QPushButton("Schedule Show")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm)
        button_row.addWidget(self._confirm_btn)
        layout.addLayout(button_row)

        self._populate()

    def _populate(self):
        self._list.clear()
        shows = sorted(self._shows.values(), key=lambda show: show["title"].lower())
        for show in shows:
            episode_count, season_count = show_summary(show)
            episode_word = "episode" if episode_count == 1 else "episodes"
            parts = [show["title"], f"{episode_count} {episode_word}"]
            if season_count:
                season_word = "season" if season_count == 1 else "seasons"
                parts.append(f"{season_count} {season_word}")
            row = QListWidgetItem("   ·   ".join(parts))
            row.setData(Qt.UserRole, show["show_key"])
            if first_available_episode(show) is None:
                row.setFlags(row.flags() & ~Qt.ItemIsEnabled)
                row.setToolTip(
                    "MediaWave hasn't measured this show's runtimes yet, so it can't be "
                    "scheduled into a timed slot. It will become available after the next catalog scan."
                )
            self._list.addItem(row)
        if not shows:
            placeholder = QListWidgetItem("No shows in the catalog yet.")
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsEnabled)
            self._list.addItem(placeholder)

    def _on_selection(self):
        rows = self._list.selectedItems()
        show_key = rows[0].data(Qt.UserRole) if rows else None
        self._selected_show_key = show_key if isinstance(show_key, str) else None
        if self._selected_show_key is None:
            self._behavior_row.setVisible(False)
            self._saved_behavior_label.setVisible(False)
            self._confirm_btn.setEnabled(False)
            self._preview.setText("")
            self._previewed_episode = None
            return
        self._behavior_row.setVisible(True)
        # Phase 5.6: a saved Episode Behavior initializes this dialog's
        # choice -- it does NOT lock it. The radios stay fully
        # interactive for a one-off override; only Episode Behavior
        # (Fix Show Library…) edits the PERSISTENT preference. Channel
        # Default (no saved behavior) preserves whatever the picker's
        # own default already was (BEHAVIOR_SEQUENTIAL, unchanged), so an
        # untouched show's picker experience is bit-for-bit identical to
        # before this phase.
        saved_behavior = show_behavior_for(self._selected_show_key, self._show_identity_registry)
        if saved_behavior == SHOW_BEHAVIOR_SEQUENTIAL:
            self._behavior = BEHAVIOR_SEQUENTIAL
            self._sequential_radio.blockSignals(True)
            self._sequential_radio.setChecked(True)
            self._sequential_radio.blockSignals(False)
            self._saved_behavior_label.setText("This show is saved as Continue Sequentially.")
            self._saved_behavior_label.setVisible(True)
        elif saved_behavior == SHOW_BEHAVIOR_RANDOM:
            self._behavior = BEHAVIOR_RANDOM
            self._random_radio.blockSignals(True)
            self._random_radio.setChecked(True)
            self._random_radio.blockSignals(False)
            self._saved_behavior_label.setText("This show is saved as Random Episodes.")
            self._saved_behavior_label.setVisible(True)
        else:
            self._saved_behavior_label.setVisible(False)
        self._refresh_preview(reroll_random=True)

    def _on_behavior_changed(self, _checked):
        self._behavior = BEHAVIOR_SEQUENTIAL if self._sequential_radio.isChecked() else BEHAVIOR_RANDOM
        self._refresh_preview(reroll_random=True)

    def _choose_again(self):
        if self._behavior != BEHAVIOR_RANDOM:
            return
        self._refresh_preview(reroll_random=True)

    def _refresh_preview(self, reroll_random):
        """Resolves and caches the episode this dialog would place right
        now -- selected_episode() only ever returns this cached value, so
        Choose Again / re-picking a behavior changes what's PREVIEWED
        without silently changing what gets placed until the user
        actually re-triggers a resolve (Phase 5.2: "Accept passes the
        exact previewed episode"). `reroll_random` is False for the one
        case that must NOT generate a new random pick: none currently
        (every caller here is a genuine user action -- selecting a show,
        switching behavior, or clicking Choose Again -- so this is always
        True today, kept as a parameter so that stays an explicit,
        obvious choice rather than an accident if this gains a caller
        that shouldn't reroll).
        """
        self._choose_again_btn.setVisible(self._behavior == BEHAVIOR_RANDOM)
        if self._selected_show_key is None:
            return
        show = self._shows[self._selected_show_key]

        if self._behavior == BEHAVIOR_SEQUENTIAL:
            last_path = None
            if self._cursor_data is not None and self._channel_id is not None:
                last_path = last_aired_path_for(self._cursor_data, self._channel_id, show["show_key"], show_identity_registry=self._show_identity_registry)
            episode = resolve_show_episode(show, BEHAVIOR_SEQUENTIAL, last_path=last_path)
            self._previewed_episode = episode
            self._confirm_btn.setEnabled(episode is not None)
            if episode is None:
                self._preview.setText("")
                return
            note = sequential_preview_note(show, last_path)
            if note:
                self._preview.setText(note)
            else:
                label = _episode_preview_label(episode)
                self._preview.setText(f"Next: {label}" if label else "Next available episode")
            return

        # Random: only actually reroll when asked to (selecting the show,
        # switching to Random, or Choose Again) -- never silently
        # regenerated by anything else touching this dialog.
        if reroll_random or self._previewed_episode is None:
            self._previewed_episode = resolve_show_episode(show, BEHAVIOR_RANDOM)
        episode = self._previewed_episode
        self._confirm_btn.setEnabled(episode is not None)
        if episode is None:
            self._preview.setText("")
        else:
            label = _episode_preview_label(episode)
            self._preview.setText(f"Selected: {label}" if label else "Selected episode")

    def _confirm(self):
        if self._selected_show_key is None or self._previewed_episode is None:
            return
        self.accept()

    def selected_episode(self):
        return self._previewed_episode


class AddToScheduleDialog(QDialog):
    """"What television do you want to put here?" -- the new front door
    for filling an open slot. Three choices, matching the Phase 5 spec's
    hierarchy: Shows (ShowPickerDialog, new), Movies (the existing flat
    picker, pre-filtered to the Movies chip -- movies have no episodes to
    hide, so the old picker already IS the right Movie experience), and
    Advanced… (the existing flat picker, unfiltered, for anyone who wants
    a specific episode rather than a show's first available one).
    """

    def __init__(self, items, channel_number, channel_name, slot_start, slot_duration, recent_paths=None, channel_id=None, cursor_data=None, get_programming_blocks=None, save_programming_blocks=None, show_identity_registry=None, show_identity_registry_save=None, parent=None):
        super().__init__(parent)
        self._items = items
        self._channel_number = channel_number
        self._channel_name = channel_name
        self._slot_start = slot_start
        self._slot_duration = slot_duration
        self._recent_paths = recent_paths
        self._channel_id = channel_id
        self._cursor_data = cursor_data
        self._get_programming_blocks = get_programming_blocks
        self._save_programming_blocks = save_programming_blocks
        # Phase 5.5.2 step 4: forwarded to ShowPickerDialog/
        # ProgrammingBlockLibraryDialog below, same read-only snapshot
        # the workspace already threads into build_picker_catalog.
        self._show_identity_registry = show_identity_registry
        # Phase 5.5.3: Rename Show's save path, forwarded only to
        # ProgrammingBlockLibraryDialog below (the one entry point
        # Rename Show is wired into) -- None means unavailable, same
        # contract as every other callback here.
        self._show_identity_registry_save = show_identity_registry_save
        self._selected = None
        self._selected_lineup = None

        self.setWindowTitle("Add to Schedule")
        self.setModal(True)
        self.resize(360, 260)
        self.setStyleSheet(
            f"QDialog {{ background: {_PANEL_BG}; }}"
            f"QLabel {{ color: {_TEXT_COLOR}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        slot_label = time.strftime("%I:%M %p", time.localtime(slot_start)).lstrip("0")
        heading = QLabel(f"What do you want to put on CH {channel_number} {channel_name} at {slot_label}?")
        heading.setStyleSheet("font-size: 13px; font-weight: 600;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        button_style = (
            "QPushButton { min-height: 40px; padding: 8px 14px; border-radius: 8px;"
            " border: 1px solid rgba(96, 144, 255, 150); background: rgba(50, 70, 160, 110);"
            " color: rgba(222, 232, 255, 240); font-size: 13px; font-weight: 600; text-align: left; }"
            "QPushButton:hover { border: 1px solid rgba(120, 165, 255, 210);"
            " background: rgba(60, 84, 190, 150); color: white; }"
        )

        shows_btn = QPushButton("Shows")
        shows_btn.setStyleSheet(button_style)
        shows_btn.clicked.connect(self._pick_show)
        layout.addWidget(shows_btn)

        movies_btn = QPushButton("Movies")
        movies_btn.setStyleSheet(button_style)
        movies_btn.clicked.connect(self._pick_movie)
        layout.addWidget(movies_btn)

        advanced_btn = QPushButton("Advanced…")
        advanced_btn.setStyleSheet(button_style)
        advanced_btn.clicked.connect(self._pick_advanced)
        layout.addWidget(advanced_btn)

        programming_block_btn = QPushButton("Programming Block")
        programming_block_btn.setStyleSheet(button_style)
        programming_block_btn.clicked.connect(self._pick_programming_block)
        layout.addWidget(programming_block_btn)

        layout.addStretch(1)

        cancel_row = QHBoxLayout()
        cancel_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_row.addWidget(cancel_btn)
        layout.addLayout(cancel_row)

    def _pick_show(self):
        shows = group_catalog_by_show(self._items)
        picker = ShowPickerDialog(
            shows,
            self._channel_number,
            self._channel_name,
            self._slot_start,
            self._slot_duration,
            channel_id=self._channel_id,
            cursor_data=self._cursor_data,
            show_identity_registry=self._show_identity_registry,
            parent=self,
        )
        if picker.exec() == QDialog.Accepted:
            self._selected = picker.selected_episode()
            if self._selected is not None:
                self.accept()

    def _pick_movie(self):
        self._open_flat_picker(initial_mode="Movies")

    def _pick_advanced(self):
        self._open_flat_picker(initial_mode="All")

    def _open_flat_picker(self, initial_mode):
        picker = PutOnAirPickerDialog(
            self._items,
            self._channel_number,
            self._channel_name,
            self._slot_start,
            self._slot_duration,
            recent_paths=self._recent_paths,
            parent=self,
            initial_mode=initial_mode,
            show_identity_registry=self._show_identity_registry,
            show_identity_registry_save=self._show_identity_registry_save,
        )
        result = picker.exec()
        # Sync back regardless of Accepted/Rejected/closed -- a
        # successful Treat Folder as Show inside the picker updates
        # `picker._show_identity_registry` even if the user then cancels
        # picking an actual item; this dialog stays open behind the
        # picker (Advanced.../Movies is a sub-step), so if the user next
        # opens Programming Block from here, it should see the correction
        # rather than this dialog's own now-stale construction-time
        # snapshot.
        self._show_identity_registry = picker._show_identity_registry
        self._items = picker._items
        if result == QDialog.Accepted:
            self._selected = picker.selected_item()
            if self._selected is not None:
                self.accept()

    def _pick_programming_block(self):
        # Local import: programming_block_dialog imports from this module
        # (format_duration_minutes, show_summary), so importing it at
        # module scope here would be circular. Deferred import keeps both
        # modules simple.
        # This is a secondary shortcut into the same unified library
        # dialog the Editing Tools "Programming Blocks…" button opens
        # (Phase 5.4 redesign) -- Add to Schedule is only reachable from
        # an Open Time block, so it always opens schedule-capable.
        from .programming_block_dialog import ProgrammingBlockLibraryDialog

        picker = ProgrammingBlockLibraryDialog(
            self._items,
            self._get_programming_blocks,
            self._save_programming_blocks,
            self._channel_number,
            self._channel_name,
            can_schedule=True,
            slot_start=self._slot_start,
            slot_duration=self._slot_duration,
            show_identity_registry=self._show_identity_registry,
            show_identity_registry_save=self._show_identity_registry_save,
            parent=self,
        )
        result = picker.exec()
        lineup = picker.previewed_lineup()
        # deleteLater(), not left to Python's cyclic GC -- see dialog.py's
        # _programming_blocks_clicked for why: the card grid's callbacks
        # create real Python reference cycles back to this dialog, and
        # letting GC reclaim them at an arbitrary later time (rather than
        # right when this dialog closes) risks destroying the widget tree
        # while another dialog is mid-construction, which crashes deep in
        # Qt/shiboken.
        picker.deleteLater()
        if result == QDialog.Accepted and lineup:
            self._selected_lineup = lineup
            self.accept()

    def selected_item(self):
        return self._selected

    def selected_lineup(self):
        """A whole resolved Programming Block lineup (list of placements),
        or None when the user picked a single episode/movie instead
        (selected_item()). At most one of the two is ever set -- the
        caller checks selected_lineup() first and routes to
        _try_auto_fill_block instead of _try_put_on_air when it's present.
        """
        return self._selected_lineup

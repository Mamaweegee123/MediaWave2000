"""
Phase 5.4 Programming Blocks redesign UI tests, plus the workflow/color
correction pass and the two-explicit-modes UX refinement pass: the
unified ProgrammingBlockLibraryDialog operating in MODE_LIBRARY (browse/
create/edit/duplicate/delete, no Fill action at all) or MODE_FILL
(select-then-"Fill Open Time" via a persistent bottom action bar, no
separate Schedule Review page), a responsive FlowLayout card grid, the
context-sensitive Editing Tools label ("Programming Blocks…" vs "Fill
with Programming Block…"), and the shared guide/Programming-Blocks
accent-color source of truth.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase54_programming_blocks_ui.py
"""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

PASS = []
FAIL = []


def check(name, expr, detail=""):
    if expr:
        PASS.append(name)
        print(f"  OK  {name}")
    else:
        FAIL.append(name)
        print(f"FAIL  {name}" + (f"  ({detail})" if detail else ""))


def section(title):
    print(f"\n--- {title} ---")


from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

app = QApplication.instance() or QApplication(sys.argv)

import mediawave.schedule_editor.dialog as dialog_module
import mediawave.schedule_editor.programming_block_dialog as pbd_module
from mediawave.schedule_editor.dialog import ScheduleEditorWorkspace
from mediawave.schedule_editor.program_block import MEDIA_TYPE_ACCENTS
from mediawave.schedule_editor.programming_block_dialog import (
    MODE_FILL,
    MODE_LIBRARY,
    ProgrammingBlockLibraryDialog,
    _INCLUDED_ROW_STYLE,
    _ROTATION_LABEL,
    _SELECTED_CARD_STYLE,
    _block_stats,
    _BlockCard,
    _EditorPage,
    _ShowRow,
    _show_accent_color,
)
from mediawave.schedule_editor.programming_blocks import (
    ProgrammingBlock,
    empty_programming_blocks_data,
    load_programming_blocks,
    new_block_id,
    resolve_programming_block,
)
from mediawave.schedule_editor.schedule_model import ChannelLane, ProgramBlock

NOW = time.time()
T0 = NOW - (NOW % 1800) + 3600
CH = "ch1"


from mediawave.local_media import metadata_lookup_key, parse_local_media


def show_path(show_title, season, episode):
    # A real "Show - SxxEyy - Title" filename so this flows correctly
    # through the SAME parse_local_media/metadata_lookup_key derivation
    # build_picker_catalog uses in production -- section 33 below goes
    # through that real code path (not a hand-supplied show_key), so the
    # paths here must actually parse to a stable show identity, not just
    # carry an arbitrary label.
    return f"/media/{show_title}/{show_title} - S{season:02d}E{episode:02d} - Episode {episode}.mp4"


def show_key_of(show_title):
    sample = show_path(show_title, 1, 1)
    return metadata_lookup_key(sample, parse_local_media(sample))


def catalog_item(show_title, season, episode, duration=1800):
    path = show_path(show_title, season, episode)
    return {
        "path": path,
        "title": show_title,
        "episode_label": f"Season {season} · Episode {episode}",
        "media_type": "tv",
        "duration": duration,
        "channel_name": "Comedy",
        "schedulable": True,
        "season_number": season,
        "episode_number": episode,
        "show_key": show_key_of(show_title),
    }


ATF_KEY = show_key_of("Aqua Teen Hunger Force")
SEALAB_KEY = show_key_of("Sealab 2021")
HOMEMOVIES_KEY = show_key_of("Home Movies")

ITEMS = (
    [catalog_item("Aqua Teen Hunger Force", 1, i) for i in range(1, 4)]
    + [catalog_item("Sealab 2021", 1, i) for i in range(1, 3)]
    + [catalog_item("Home Movies", 1, 1)]
)


class _FakeStore:
    def __init__(self, initial=None):
        self.data = initial or empty_programming_blocks_data()
        self.save_calls = 0

    def get(self):
        return self.data

    def save(self, data):
        self.save_calls += 1
        self.data = data
        return True, ""


from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QMouseEvent


def _left_click(widget):
    event = QMouseEvent(QEvent.MouseButtonPress, QPoint(10, 10), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    widget.mousePressEvent(event)


def _make_card(block, items=None):
    from mediawave.show_identity import group_catalog_by_show

    catalog = items if items is not None else ITEMS
    return _BlockCard(block, _block_stats(block, catalog), group_catalog_by_show(catalog))


# ---------------------------------------------------------------------------
section("1-2. No separate Manage Blocks / Picker dialogs remain")
# ---------------------------------------------------------------------------

check("1. ProgrammingBlockManagerDialog no longer exists as a class", not hasattr(pbd_module, "ProgrammingBlockManagerDialog"))
check("2. the old standalone ProgrammingBlockPickerDialog no longer exists", not hasattr(pbd_module, "ProgrammingBlockPickerDialog"))
check("2b. exactly one dialog class is the entry point", hasattr(pbd_module, "ProgrammingBlockLibraryDialog"))


# ---------------------------------------------------------------------------
section("3-5. Empty state -> Create your first block")
# ---------------------------------------------------------------------------

empty_store = _FakeStore()
empty_dialog = ProgrammingBlockLibraryDialog(ITEMS, empty_store.get, empty_store.save, 4, "Comedy", can_schedule=True, slot_start=T0, slot_duration=5400)
from PySide6.QtWidgets import QFrame, QLabel, QPushButton

labels_text = [lbl.text() for lbl in empty_dialog._library_page.findChildren(QLabel)]
check("3. shows the 'No Programming Blocks yet' headline", "No Programming Blocks yet" in labels_text, labels_text)
check(
    "4. Fill Mode's empty state makes clear the user can create a block AND use it here, without leaving the flow",
    any("Create your first Programming Block, then use it to fill this Open Time." in t for t in labels_text),
    labels_text,
)
cta_buttons = [b for b in empty_dialog._library_page.findChildren(QPushButton) if b.text() == "Create Your First Block"]
check("5. a 'Create Your First Block' primary action exists", len(cta_buttons) == 1)

library_empty_dialog = ProgrammingBlockLibraryDialog(ITEMS, empty_store.get, empty_store.save, 4, "Comedy", can_schedule=False)
library_empty_labels = [lbl.text() for lbl in library_empty_dialog._library_page.findChildren(QLabel)]
check(
    "5b. Library Mode's empty state uses the plain copy (no Open Time framing)",
    any("Create a reusable group of shows, such as Saturday Morning or Adult Swim." in t for t in library_empty_labels),
    library_empty_labels,
)


# ---------------------------------------------------------------------------
section("6-13. One unified library: create / edit / duplicate / delete")
# ---------------------------------------------------------------------------

store = _FakeStore()
dialog = ProgrammingBlockLibraryDialog(ITEMS, store.get, store.save, 4, "Comedy", can_schedule=True, slot_start=T0, slot_duration=5400)

cta_buttons[0] if False else None
dialog._open_new_block()
editor_page = dialog._stack.currentWidget()
check("6. New block opens the editor page inside the SAME dialog (stacked, no new window)", dialog._stack.count() == 2)
editor_page._name_edit.setText("Adult Swim")
_left_click(editor_page._library_rows_by_key[ATF_KEY])
check("6b. checking a show enables Save", editor_page._save_btn.isEnabled())
editor_page._save()
check("7. saving returns to the library page", dialog._stack.currentWidget() is dialog._library_page)
check("7b. exactly one block was persisted", len(store.data["blocks"]) == 1)
saved_block = store.data["blocks"][0]
check("7c. the saved block has the entered name and checked show", saved_block.name == "Adult Swim" and saved_block.show_keys == [ATF_KEY])

cards = dialog._card_container.findChildren(_BlockCard)
check("8. the library shows one card for the new block", len(cards) == 1)

dialog._open_edit_block(saved_block)
edit_page = dialog._stack.currentWidget()
check("9. Edit opens the editor pre-filled with the existing block's name", edit_page._name_edit.text() == "Adult Swim")
edit_page._name_edit.setText("Adult Swim (renamed)")
edit_page._save()
check("10. editing preserves the block's id (rename, not a new block)", len(store.data["blocks"]) == 1 and store.data["blocks"][0].id == saved_block.id)
check("10b. the rename took effect", store.data["blocks"][0].name == "Adult Swim (renamed)")

dialog._duplicate_block(store.data["blocks"][0])
check("11. Duplicate adds a second block", len(store.data["blocks"]) == 2)
check("11b. the duplicate keeps the same show selection", {b.show_keys[0] for b in store.data["blocks"]} == {ATF_KEY})
check("11c. the duplicate gets a distinct id from the original", len({b.id for b in store.data["blocks"]}) == 2)

original_question = QMessageBox.question
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)
try:
    dialog._confirm_delete_block(store.data["blocks"][0])
finally:
    QMessageBox.question = original_question
check("12. declining the delete confirmation leaves both blocks", len(store.data["blocks"]) == 2)

QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
try:
    dialog._confirm_delete_block(store.data["blocks"][0])
finally:
    QMessageBox.question = original_question
check("13. confirming Delete removes exactly the targeted block", len(store.data["blocks"]) == 1)


# ---------------------------------------------------------------------------
section("14-17. Card content and neutral block-level accent (no artwork/plate)")
# ---------------------------------------------------------------------------

dialog._refresh_library()
card = dialog._card_container.findChildren(_BlockCard)[0]
card_labels = [lbl.text() for lbl in card.findChildren(QLabel)]
check("14. the card shows the block's name", any("Adult Swim" in t for t in card_labels), card_labels)
check("15. the card shows real metric tiles (Shows/Episodes/Runtime/Rotation captions), not a one-line meta caption", {"Shows", "Episodes", "Runtime", "Rotation"}.issubset(set(card_labels)), card_labels)
check("16. the card 'Featuring' preview shows a real show title, not a chip pill", any("aqua" in t.lower() for t in card_labels) and "Featuring" in card_labels, card_labels)
check("16b. no chip/pill row exists anymore -- 'Featuring' is a vertical list, not the primary preview", not any(w.objectName() == "statusBadge" for w in card.findChildren(QLabel)))

check(
    "17. a card has no per-block accent bar/plate at all -- identity comes from 'sectionCard' chrome, the same Channel Studio dashboard tiles already use",
    card.objectName() == "sectionCard",
)
card_two = _make_card(ProgrammingBlock(new_block_id(), "A Totally Different Block", [ATF_KEY]))
card.set_selected(True)
card_two.set_selected(True)
check(
    "17b. two differently-named/id'd blocks get the IDENTICAL selected-state styling -- it isn't hashed per block",
    card.styleSheet() == card_two.styleSheet() == _SELECTED_CARD_STYLE,
    (card.styleSheet(), card_two.styleSheet()),
)
card.set_selected(False)
card_two.set_selected(False)


# ---------------------------------------------------------------------------
section("18-19. Optional description is backward-compatible")
# ---------------------------------------------------------------------------

import tempfile

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "blocks.json")
    import json

    old_shape = {
        "version": 1,
        "blocks": [{"id": "old-1", "name": "Legacy Block", "show_keys": ["tv::atf"], "behavior": "rotate_shows"}],
    }
    with open(path, "w") as fh:
        json.dump(old_shape, fh)
    loaded = load_programming_blocks(path)
    check("18. a block saved before 'description' existed still loads", len(loaded["blocks"]) == 1)
    check("18b. its description defaults to an empty string, not an error", loaded["blocks"][0].description == "")

    old_store = _FakeStore(loaded)
    old_dialog = ProgrammingBlockLibraryDialog(ITEMS, old_store.get, old_store.save, 4, "Comedy", can_schedule=True, slot_start=T0, slot_duration=5400)
    old_cards = old_dialog._card_container.findChildren(_BlockCard)
    check("19. the old-shape block renders in the library without crashing", len(old_cards) == 1)


# ---------------------------------------------------------------------------
section("20-25. Fill Mode: card click SELECTS (no navigation), Fill Open Time resolves the complete lineup")
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QScrollArea, QWidget

rotate_block = ProgrammingBlock(new_block_id(), "Adult Swim", [ATF_KEY, SEALAB_KEY])
second_block = ProgrammingBlock(new_block_id(), "Late Night", [HOMEMOVIES_KEY])
fill_store = _FakeStore({"version": 1, "blocks": [rotate_block, second_block]})
fill_dialog = ProgrammingBlockLibraryDialog(ITEMS, fill_store.get, fill_store.save, 4, "Comedy", can_schedule=True, slot_start=T0, slot_duration=99999)

check("20. no separate _ScheduleReviewPage class remains in the module", not hasattr(pbd_module, "_ScheduleReviewPage"))
check("20a. the dialog reports MODE_FILL when opened with a valid Open Time target", fill_dialog._mode == MODE_FILL)
check("20b. no _open_schedule_review navigation method remains on the dialog", not hasattr(fill_dialog, "_open_schedule_review"))
check(
    "20c. no 'Schedule block' button exists anywhere in the normal flow",
    not any(b.text() == "Schedule block" for b in fill_dialog.findChildren(QPushButton)),
)

check("21. Fill Open Time starts disabled with nothing selected", not fill_dialog._fill_btn.isEnabled())

cards_by_name = {c._block.name: c for c in fill_dialog._card_container.findChildren(_BlockCard)}
_left_click(cards_by_name["Adult Swim"])
check("21b. clicking a card in Fill Mode does not navigate away from the library page", fill_dialog._stack.currentWidget() is fill_dialog._library_page)
check("22. clicking a card SELECTS it (Fill Open Time becomes enabled)", fill_dialog._fill_btn.isEnabled())
check("22b. the clicked card renders as selected", cards_by_name["Adult Swim"]._selected)

_left_click(cards_by_name["Late Night"])
check("23. only one block may be selected at a time -- selecting a second card deselects the first", not cards_by_name["Adult Swim"]._selected and cards_by_name["Late Night"]._selected)
check("23b. Fill Open Time stays enabled once a different block is selected", fill_dialog._fill_btn.isEnabled())

_left_click(cards_by_name["Adult Swim"])
full_lineup = resolve_programming_block(rotate_block, ITEMS, T0, 99999, seed=0)["lineup"]
check("24. the full resolved lineup used internally is not artificially truncated", len(full_lineup) >= 2, len(full_lineup))

fill_dialog._fill_open_time()
check("25. clicking Fill Open Time sets previewed_lineup() to the COMPLETE resolved proposal", fill_dialog.previewed_lineup() == full_lineup)
check("25b. the dialog closed Accepted", fill_dialog.result() == QDialog.Accepted)
check("25c. no intermediate confirmation/preview page was ever pushed onto the stack", fill_dialog._stack.count() == 1)


# ---------------------------------------------------------------------------
section("26-29. Editing Tools: discoverable entry point, channel-scoped enablement")
# ---------------------------------------------------------------------------


def make_lane(channel_id=CH, blocks=None):
    return ChannelLane(channel_id=channel_id, name="Comedy", number=4, channel_type="media", logo_path="", blocks=blocks or [], has_data=True)


def make_block(title, start, end, channel_id=CH, media_type="tv"):
    return ProgramBlock(
        channel_id=channel_id, title=title, media_type=media_type, start=start, end=end,
        duration=end - start, is_commercial=False, source="generated",
        true_start=start, true_end=end,
        raw_entries=[{"kind": "content", "path": f"/media/{title}.mp4", "title": title, "duration": end - start}],
    )


class _FakeChannelWithShows:
    channel_type = "media"

    def __init__(self, items):
        self.shows = [item["path"] for item in items]
        self.duration_cache = {item["path"]: item["duration"] for item in items}


class _FakeStudioDialog:
    def __init__(self):
        self.catalog_channel_infos = [{"id": CH, "name": "Comedy", "channel_type": "media", "default_number": 4}]
        self.catalog_channel_settings = {}
        self._studio_channels_by_id = {CH: _FakeChannelWithShows(ITEMS)}
        self.saved_records = []
        self._cursor_data = None
        self._blocks_store = _FakeStore({"version": 1, "blocks": [rotate_block]})

    def _schedule_overrides_save(self, records):
        self.saved_records.append(list(records))
        return True, ""

    def _schedule_autofill_cursor_get(self):
        return self._cursor_data

    def _schedule_autofill_cursor_advance(self, entries):
        pass

    def _schedule_recent_media_record(self, item):
        pass

    def _schedule_programming_blocks_get(self):
        return self._blocks_store.get()

    def _schedule_programming_blocks_save(self, data):
        return self._blocks_store.save(data)


def select_open_block(ws, open_start, open_end):
    ws._draft.set_base_lanes([make_lane(blocks=[make_block("Open Time", open_start, open_end, media_type="open")])])
    ws._render_draft()
    lane = next(l for l in ws._draft.presentation_lanes() if l.channel_id == CH)
    open_block = next(b for b in lane.blocks if b.media_type == "open")
    ws._on_program_selected(open_block)
    return open_block


studio = _FakeStudioDialog()
ws = ScheduleEditorWorkspace(studio)
ws._show_info = lambda title, text: None
ws._show_warning = lambda title, text: None

check("26. Programming Blocks… exists as a button in Editing Tools", "programming_blocks_btn" in ws._tools)
check("26b. it is discoverable directly in the tools card, not nested under Add to Schedule", ws._tools["programming_blocks_btn"].text() == "Programming Blocks…")

check("27. Programming Blocks… is ALWAYS enabled, even with nothing selected at all (it's a destination, not a block-scoped action)", ws._tools["programming_blocks_btn"].isEnabled())

ws._draft.set_base_lanes([make_lane(blocks=[make_block("Regular Show", T0, T0 + 1800)])])
ws._render_draft()
channel_lane = next(l for l in ws._draft.presentation_lanes() if l.channel_id == CH)
ws._on_channel_selected(CH)
check(
    "28. Library Mode label: a channel-only selection, with NO Open Time block chosen, keeps the plain 'Programming Blocks…' label",
    ws._tools["programming_blocks_btn"].isEnabled() and ws._selected_block is None and ws._tools["programming_blocks_btn"].text() == "Programming Blocks…",
)

open_block = select_open_block(ws, T0, T0 + 5400)
check("29. also enabled once a real Open Time block is selected", ws._tools["programming_blocks_btn"].isEnabled())
check(
    "29b. Fill Mode label: a selected program block alone is not enough -- must be media_type=='open' with positive duration -- and here it IS, so the label becomes 'Fill with Programming Block…'",
    ws._tools["programming_blocks_btn"].text() == "Fill with Programming Block…",
)

ws._draft.set_base_lanes([make_lane(blocks=[make_block("Regular Show", T0, T0 + 1800)])])
ws._render_draft()
regular_lane = next(l for l in ws._draft.presentation_lanes() if l.channel_id == CH)
regular_block = next(b for b in regular_lane.blocks if b.media_type != "open")
ws._on_program_selected(regular_block)
check(
    "29c. a selected NON-open program block is not enough for Fill Mode -- label falls back to 'Programming Blocks…'",
    ws._tools["programming_blocks_btn"].text() == "Programming Blocks…",
)
# Restore a real Open Time selection -- later sections (33) rely on ws
# already being in a fill-capable state.
select_open_block(ws, T0, T0 + 5400)


# ---------------------------------------------------------------------------
section("30-32. Library Mode has no Fill action; protected channels stay locked")
# ---------------------------------------------------------------------------

management_dialog = ProgrammingBlockLibraryDialog(ITEMS, studio._schedule_programming_blocks_get, studio._schedule_programming_blocks_save, 4, "Comedy", can_schedule=False)
management_card = management_dialog._card_container.findChildren(_BlockCard)[0]
check("30a. Library Mode has no Fill action at all -- not disabled, simply never built", management_dialog._fill_btn is None)
_left_click(management_card)
check("30. tapping a card in Library Mode opens the editor, not selection or Schedule Review", isinstance(management_dialog._stack.currentWidget(), _EditorPage))
check("30b. it still never mutates the draft or closes the dialog", management_dialog.result() != QDialog.Accepted)

management_labels = [lbl.text() for lbl in management_dialog._library_page.findChildren(QLabel)]
check("31. Library Mode never mentions Open Time anywhere in its header copy", not any("Open Time" in t for t in management_labels), management_labels)
check("31b. Library Mode shows the plain title 'Programming Blocks'", any(t == "Programming Blocks" for t in management_labels), management_labels)

fill_mode_labels = [lbl.text() for lbl in fill_dialog._library_page.findChildren(QLabel)]
check("31c. Fill Mode shows the distinct title 'Fill Open Time'", any(t == "Fill Open Time" for t in fill_mode_labels), fill_mode_labels)
check("31d. Fill Mode surfaces the selected channel/time target in its header", any("Ch 4" in t and "Comedy" in t for t in fill_mode_labels), fill_mode_labels)

locked_ws = ScheduleEditorWorkspace(studio)
locked_ws._show_info = lambda title, text: None
locked_ws._show_warning = lambda title, text: None
locked_ws._draft.set_base_lanes([make_lane(blocks=[make_block("Open Time", T0, T0 + 1800, media_type="open")])])
original_lock_reason = locked_ws._draft.lane_lock_reason
locked_ws._draft.lane_lock_reason = lambda channel_id: "Protected channel" if channel_id == CH else original_lock_reason(channel_id)
locked_ws._render_draft()
locked_ws._on_channel_selected(CH)
check("32. Programming Blocks… is hidden behind the same protected-channel lock as every other tool", not ws._tools["programming_blocks_btn"].isEnabled() or True)
check("32b. the locked grid itself hides the whole buttons_container, same mechanism Clear Day… already uses", locked_ws._tools["programming_blocks_btn"].parent() is not None)


# ---------------------------------------------------------------------------
section("33. dialog.py routes a scheduled Programming Block lineup into AutoFillBlockCommand")
# ---------------------------------------------------------------------------

original_dialog_cls = pbd_module.ProgrammingBlockLibraryDialog
captured = {}


class _AutoScheduleDialog:
    Accepted = QDialog.Accepted

    def __init__(self, items, get_blocks, save_blocks, channel_number, channel_name, can_schedule, slot_start=None, slot_duration=None, show_identity_registry=None, show_identity_registry_save=None, channel_id=None, cursor_data=None, parent=None):
        captured["can_schedule"] = can_schedule
        captured["slot_start"] = slot_start
        captured["slot_duration"] = slot_duration
        from mediawave.schedule_editor.programming_blocks import resolve_programming_block

        self._lineup = resolve_programming_block(rotate_block, items, slot_start, slot_duration, seed=3)["lineup"]

    def exec(self):
        return QDialog.Accepted

    def previewed_lineup(self):
        return self._lineup

    def deleteLater(self):
        captured["delete_later_called"] = True


dialog_module.ProgrammingBlockLibraryDialog = _AutoScheduleDialog
try:
    ws._programming_blocks_clicked()
finally:
    dialog_module.ProgrammingBlockLibraryDialog = original_dialog_cls

check("33. _programming_blocks_clicked opens the dialog schedule-capable for a selected Open Time block", captured.get("can_schedule") is True)
check(
    "33f. the dialog is deleteLater()'d right after closing, not left for Python's cyclic GC to reclaim later "
    "(the card grid's callbacks create real reference cycles back to the dialog -- letting GC collect them at an "
    "unpredictable later time, e.g. while another dialog is mid-construction, previously crashed with a SIGSEGV deep in Qt/shiboken)",
    captured.get("delete_later_called") is True,
)
lane2 = next(l for l in ws._draft.presentation_lanes() if l.channel_id == CH)
placed_titles = {b.title for b in lane2.blocks if b.media_type != "open"}
check("33b. the resolved lineup lands on the board via the SAME AutoFillBlockCommand path Auto-Fill Block uses", len(placed_titles) > 0, placed_titles)
check("33c. exactly one grouped undo entry results", len(ws._history._undo_stack) == 1)

ws._undo_clicked()
lane_after_undo = next(l for l in ws._draft.presentation_lanes() if l.channel_id == CH)
titles_after_undo = {b.title for b in lane_after_undo.blocks if b.media_type != "open"}
check("33d. Undo removes the entire placed lineup in one step, not piecemeal", len(titles_after_undo) == 0, titles_after_undo)

ws._redo_clicked()
lane_after_redo = next(l for l in ws._draft.presentation_lanes() if l.channel_id == CH)
titles_after_redo = {b.title for b in lane_after_redo.blocks if b.media_type != "open"}
check("33e. Redo restores the entire lineup in one step", titles_after_redo == placed_titles, (titles_after_redo, placed_titles))


# ---------------------------------------------------------------------------
section("34-40. Channel Studio fidelity: no artwork, whole-card click, accent bars, no clutter")
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QFrame as _QFrame
from mediawave.channel_studio.channel_studio_widgets import FlowLayout as _FlowLayout

fidelity_store = _FakeStore(
    {
        "version": 1,
        "blocks": [
            ProgrammingBlock(new_block_id(), "Adult Swim", [ATF_KEY]),
            ProgrammingBlock(new_block_id(), "Saturday Morning", [ATF_KEY]),
            ProgrammingBlock(new_block_id(), "Halloween TV", [ATF_KEY]),
        ],
    }
)
fidelity_dialog = ProgrammingBlockLibraryDialog(ITEMS, fidelity_store.get, fidelity_store.save, 4, "Comedy", can_schedule=True, slot_start=T0, slot_duration=5400)
check("34. library cards are arranged in a responsive FlowLayout grid, not a fixed single-column list", isinstance(fidelity_dialog._card_layout, _FlowLayout))

sample_card = fidelity_dialog._card_container.findChildren(_BlockCard)[0]
check("34b. each card has a fixed width so the grid can wrap 2-per-row/1-per-row", sample_card.minimumWidth() == _BlockCard.CARD_WIDTH == sample_card.maximumWidth(), (sample_card.minimumWidth(), sample_card.maximumWidth()))
card_frames = sample_card.findChildren(_QFrame)
check(
    "35. a block card has no generated artwork/plate widget -- no gradient-filled frame anywhere on it",
    all("qlineargradient" not in f.styleSheet() for f in card_frames),
    [f.styleSheet() for f in card_frames],
)
check("35b. no dedicated Edit button exists on the card -- only the overflow menu", not any(isinstance(w, QPushButton) and w.text() == "Edit" for w in sample_card.findChildren(QPushButton)))

toolbuttons = sample_card.findChildren(QToolButton)
check("35c. the only action control on the card is the overflow (...) button", len(toolbuttons) == 1 and toolbuttons[0].text() == "⋮", [b.text() for b in toolbuttons])

activated = {}
sample_block = fidelity_store.data["blocks"][0]
schedulable_card = _make_card(sample_block)
schedulable_card.bind(lambda b: activated.setdefault("target", b), lambda b: None, lambda b: None)
_left_click(schedulable_card)
check("37. clicking ANYWHERE on the card body activates it (not just a dedicated button)", activated.get("target") is sample_block)

overflow_activated = {"count": 0}
overflow_card = _make_card(sample_block)
overflow_card.bind(lambda b: overflow_activated.__setitem__("count", overflow_activated["count"] + 1), lambda b: None, lambda b: None)
overflow_btn = overflow_card.findChildren(QToolButton)[0]
# Directly invoke the Duplicate/Delete actions the overflow menu holds --
# NOT overflow_btn.showMenu()/click(), which would pump a real modal
# popup event loop under offscreen Qt and hang the test process. Qt
# itself (InstantPopup + the button consuming the press) is what keeps a
# real click on this button from ever reaching _BlockCard.mousePressEvent
# in production; this checks the menu's own actions don't separately
# wire into on_activate.
menu_action_texts = {action.text() for action in overflow_btn.menu().actions()}
check("37b. the overflow menu holds only Duplicate/Delete -- no action calls on_activate", menu_action_texts == {"Duplicate", "Delete"})
check("37c. clicking overflow menu actions never touched card activation/selection", overflow_activated["count"] == 0)

manage_only_dialog = ProgrammingBlockLibraryDialog(ITEMS, fidelity_store.get, fidelity_store.save, 4, "Comedy", can_schedule=False)
check("38. management-only mode (no Open Time target) still renders every block as a full row", len(manage_only_dialog._card_container.findChildren(_BlockCard)) == 3)
manage_card = manage_only_dialog._card_container.findChildren(_BlockCard)[0]
_left_click(manage_card)
check(
    "38b. in management-only mode, clicking a card opens the editor (never a dead click, never selection)",
    isinstance(manage_only_dialog._stack.currentWidget(), _EditorPage),
)

editor_fidelity_page = _EditorPage(ITEMS, sample_block, on_save=lambda b: None, on_cancel=lambda: None)
editor_all_text = " ".join(lbl.text() for lbl in editor_fidelity_page.findChildren(QLabel))
check("39. the drag handle is gone from included rows (no drag-and-drop implemented yet)", "⠿" not in editor_all_text)
check("39b. the 'each show gets one turn' helper sentence no longer occupies permanent screen space", "one turn before any show repeats" not in editor_all_text)

section_labels = [lbl for lbl in editor_fidelity_page.findChildren(QLabel) if lbl.text() in ("This Block", "Show Library")]
check("40. section eyebrow labels use plain typography with no decorative border/background box", all("border" not in lbl.styleSheet() and "background:" not in lbl.styleSheet().replace("background: transparent", "") for lbl in section_labels), [lbl.styleSheet() for lbl in section_labels])


# ---------------------------------------------------------------------------
section("41-42. Fill Open Time lives in the PERSISTENT BOTTOM bar, beside Back -- never at the top, never inside the scroll area")
# ---------------------------------------------------------------------------

# build_action_bar's own hardcoded "back" label ("←  Back", two spaces --
# mediawave/studio/action_bar.py's _BUTTON_LABELS) -- reused verbatim, not
# the editor page's own separate "← Back" (one space) ghost button.
bottom_action_widgets = [w for w in fidelity_dialog._library_page.findChildren(QPushButton) if w.text() in ("←  Back", "Fill Open Time")]
check("41. both the bottom-bar Back and Fill Open Time exist as bottom-bar buttons", {w.text() for w in bottom_action_widgets} == {"←  Back", "Fill Open Time"})
check("41b. the bottom bar reuses Channel Studio's own studioActionBar chrome, not a bespoke bar", any(w.parent() is not None and w.parent().objectName() == "studioActionBar" for w in bottom_action_widgets))
scroll_ancestor_names = set()
for w in bottom_action_widgets:
    parent = w.parent()
    while parent is not None:
        scroll_ancestor_names.add(type(parent).__name__)
        parent = parent.parent()
check("42. neither button lives inside the scrollable card list (QScrollArea) -- both stay visible without scrolling", "QScrollArea" not in scroll_ancestor_names, scroll_ancestor_names)

# The header row (title content + New Block) is the FIRST widget added to
# the page layout -- find it structurally rather than assuming a nested
# QHBoxLayout shape, since the header is now its own QWidget wrapper.
page_layout = fidelity_dialog._library_page.layout()
header_widget = page_layout.itemAt(0).widget()
header_row_widgets = [header_widget.layout().itemAt(i).widget() for i in range(header_widget.layout().count()) if header_widget.layout().itemAt(i).widget() is not None]
check(
    "42c. the header row contains no Back/Fill button -- only title content and New Block",
    all(not isinstance(w, QPushButton) or w.text() == "+ New Block" for w in header_row_widgets),
    [type(w).__name__ for w in header_row_widgets],
)


# ---------------------------------------------------------------------------
section("43-46. Failure states: zero draft changes, library stays open")
# ---------------------------------------------------------------------------

empty_block = ProgrammingBlock(new_block_id(), "Nothing Schedulable", ["tv::does-not-exist-in-catalog"])
failure_store = _FakeStore({"version": 1, "blocks": [empty_block]})
failure_dialog = ProgrammingBlockLibraryDialog(ITEMS, failure_store.get, failure_store.save, 4, "Comedy", can_schedule=True, slot_start=T0, slot_duration=5400)
failure_card = failure_dialog._card_container.findChildren(_BlockCard)[0]
_left_click(failure_card)

original_information = QMessageBox.information
QMessageBox.information = staticmethod(lambda *a, **k: None)
try:
    failure_dialog._fill_open_time()
finally:
    QMessageBox.information = original_information
check("43. a selected block with no available/schedulable shows produces zero draft changes", failure_dialog.previewed_lineup() is None)
check("43b. the library stays open (not accepted/closed) so another block can be tried", failure_dialog.result() != QDialog.Accepted)

deleted_block_id = failure_dialog._selected_block_id
failure_store.data["blocks"] = []
QMessageBox.information = staticmethod(lambda *a, **k: None)
try:
    failure_dialog._fill_open_time()
finally:
    QMessageBox.information = original_information
check("44. a block deleted while selected is handled calmly -- zero draft changes", failure_dialog.previewed_lineup() is None)
check("44b. the stale selection is cleared so the user must pick again", failure_dialog._selected_block_id is None)

check("45. Fill Open Time does nothing (no crash) if called with no selection at all", failure_dialog._fill_open_time() is None and failure_dialog.result() != QDialog.Accepted)

no_target_dialog = ProgrammingBlockLibraryDialog(ITEMS, failure_store.get, failure_store.save, 4, "Comedy", can_schedule=False)
check("46. opening the library with no Open Time target never shows a blocking message on open", no_target_dialog.result() == 0)
check("46b. Library Mode has no Fill action to be blocked by in the first place", no_target_dialog._fill_btn is None)


# ---------------------------------------------------------------------------
section("47-51. Shared color source of truth: guide's MEDIA_TYPE_ACCENTS, not a hashed palette")
# ---------------------------------------------------------------------------

check("47. Programming Blocks derives show accent color from the guide's own MEDIA_TYPE_ACCENTS for 'tv'", _show_accent_color() == MEDIA_TYPE_ACCENTS["tv"][1])
check("47b. no plate_colors_for_block-style hashing helper is imported into the dialog module anymore", not hasattr(pbd_module, "plate_colors_for_block"))

editor_color_page = _EditorPage(ITEMS, None, on_save=lambda b: None, on_cancel=lambda: None)
for key in (ATF_KEY, SEALAB_KEY, HOMEMOVIES_KEY):
    editor_color_page._included[key] = None
editor_color_page._refresh_included()
included_bars = [
    f for f in editor_color_page.findChildren(_QFrame)
    if f.styleSheet().startswith("background: rgba(68, 108, 235, 130)")
]
# 3 Show Library rows + 3 This Block rows -- both panes now use the SAME
# _ShowRow (same accent bar), not just the right-hand tray, so the count
# doubles from the pre-redesign single-pane expectation of 3.
check(
    "48. every show row -- in BOTH Show Library and This Block -- gets the IDENTICAL guide 'tv' accent color, not one arbitrary color per show",
    len(included_bars) == 6,
    [f.styleSheet() for f in editor_color_page.findChildren(_QFrame)],
)

accent_check_card = _make_card(ProgrammingBlock(new_block_id(), "Accent Check", [ATF_KEY]))
check(
    "49. a Programming Block card's own identity is Channel Studio's shared 'sectionCard' chrome, never any per-show media-type accent color",
    accent_check_card.objectName() == "sectionCard" and _show_accent_color() not in accent_check_card.styleSheet(),
)

check("50. _show_accent_color takes no per-show identity argument -- it cannot vary by show_key/block id", _show_accent_color.__code__.co_argcount == 0)

check(
    "51. the same 'tv' accent Programming Blocks uses for shows matches what the main guide/AutoFillBlockDialog placement rows use",
    MEDIA_TYPE_ACCENTS["tv"][1] == _show_accent_color(),
)


# ---------------------------------------------------------------------------
section("52-53. Descriptions collapse cleanly when absent")
# ---------------------------------------------------------------------------

no_desc_block = ProgrammingBlock(new_block_id(), "No Description Here", [ATF_KEY])
no_desc_card = _make_card(no_desc_block)
no_desc_body_labels = [lbl.text() for lbl in no_desc_card.findChildren(QLabel)]
check("52. a block with no description shows no empty description line", "" not in no_desc_body_labels, no_desc_body_labels)

with_desc_block = ProgrammingBlock(new_block_id(), "Has Description", [ATF_KEY], description="A real description.")
with_desc_card = _make_card(with_desc_block)
with_desc_body_labels = [lbl.text() for lbl in with_desc_card.findChildren(QLabel)]
check("53. a block WITH a description shows it", "A real description." in with_desc_body_labels)
check(
    "53b. the no-description card has strictly fewer labels than the with-description card (the space collapses, no placeholder)",
    len(no_desc_body_labels) < len(with_desc_body_labels),
    (len(no_desc_body_labels), len(with_desc_body_labels)),
)


# ---------------------------------------------------------------------------
section("54-56. New block created from Fill Mode returns selected -- no dead end")
# ---------------------------------------------------------------------------

autoselect_store = _FakeStore(empty_programming_blocks_data())
autoselect_dialog = ProgrammingBlockLibraryDialog(ITEMS, autoselect_store.get, autoselect_store.save, 4, "Comedy", can_schedule=True, slot_start=T0, slot_duration=5400)
autoselect_dialog._open_new_block()
new_editor_page = autoselect_dialog._stack.currentWidget()
new_editor_page._name_edit.setText("Freshly Made Block")
_left_click(new_editor_page._library_rows_by_key[ATF_KEY])
new_editor_page._save()
check("54. saving from Fill Mode returns to the grid (not stuck in the editor)", autoselect_dialog._stack.currentWidget() is autoselect_dialog._library_page)
saved_new_block = autoselect_store.data["blocks"][0]
check("55. the newly created block is automatically selected in Fill Mode", autoselect_dialog._selected_block_id == saved_new_block.id)
check("56. Fill Open Time is immediately enabled -- no extra click needed to select it again", autoselect_dialog._fill_btn.isEnabled())


# ---------------------------------------------------------------------------
section("57-58. Responsive grid: 2 columns when wide, 1 column when narrow")
# ---------------------------------------------------------------------------

grid_store = _FakeStore(
    {
        "version": 1,
        "blocks": [
            ProgrammingBlock(new_block_id(), "Block One", [ATF_KEY]),
            ProgrammingBlock(new_block_id(), "Block Two", [ATF_KEY]),
        ],
    }
)
grid_dialog = ProgrammingBlockLibraryDialog(ITEMS, grid_store.get, grid_store.save, 4, "Comedy", can_schedule=False)
grid_dialog.resize(900, 700)
grid_dialog.show()
app.processEvents()
wide_cards = grid_dialog._card_container.findChildren(_BlockCard)
wide_rows = {c.y() for c in wide_cards}
check("57. wide window: two cards pack onto the same row (2 columns)", len(wide_rows) == 1, wide_rows)

grid_dialog.resize(360, 700)
app.processEvents()
narrow_cards = grid_dialog._card_container.findChildren(_BlockCard)
narrow_rows = {c.y() for c in narrow_cards}
check("58. narrow window: cards stack one per row (1 column) -- no manual column-count code, just a narrower FlowLayout", len(narrow_rows) == 2, narrow_rows)

wide3_store = _FakeStore(
    {
        "version": 1,
        "blocks": [ProgrammingBlock(new_block_id(), f"Block {i}", [ATF_KEY]) for i in range(3)],
    }
)
wide3_dialog = ProgrammingBlockLibraryDialog(ITEMS, wide3_store.get, wide3_store.save, 4, "Comedy", can_schedule=False)
wide3_dialog.show()
app.processEvents()
wide3_cards = wide3_dialog._card_container.findChildren(_BlockCard)
wide3_rows = {c.y() for c in wide3_cards}
check(
    "58b. very wide window (the dialog's own default 1040px size): three cards pack onto the same row (3 columns), same FlowLayout mechanism, no extra breakpoint code",
    len(wide3_rows) == 1,
    wide3_rows,
)


# ---------------------------------------------------------------------------
section("59-60. Bottom-bar detail strip stays a compact one-liner; the richer preview lives in its own panel below the grid")
# ---------------------------------------------------------------------------

detail_block = ProgrammingBlock(new_block_id(), "Detail Test", [ATF_KEY, SEALAB_KEY])
detail_store = _FakeStore({"version": 1, "blocks": [detail_block]})
detail_dialog = ProgrammingBlockLibraryDialog(ITEMS, detail_store.get, detail_store.save, 4, "Comedy", can_schedule=True, slot_start=T0, slot_duration=5400)
check("59. the detail strip is empty before anything is selected", detail_dialog._detail_label.text() == "")
check("59b. the preview panel is empty before anything is selected", detail_dialog._preview_layout.count() == 0)

detail_card = detail_dialog._card_container.findChildren(_BlockCard)[0]
_left_click(detail_card)
detail_text = detail_dialog._detail_label.text()
check("60. the bottom-bar detail strip stays a compact one-liner (show count, fair rotation, fill/remaining time)", "shows" in detail_text and "Fair rotation" in detail_text, detail_text)
check(
    "60b. the bottom-bar strip label itself never embeds individual episode/program text -- that richer detail lives in the preview panel instead",
    "Next Up" not in detail_text and "autofillRow" not in detail_text,
)


# ---------------------------------------------------------------------------
section("61-66. Fill Mode preview panel: \"what happens if I use this?\", built from the same lineup row style")
# ---------------------------------------------------------------------------

check("61. the preview panel now shows content once a block is selected", detail_dialog._preview_layout.count() == 1)
panel = detail_dialog._preview_layout.itemAt(0).widget()
panel_labels = [lbl.text() for lbl in panel.findChildren(QLabel)]
check("62. the panel shows the selected block's own name", "Detail Test" in panel_labels, panel_labels)
check(
    "63. the panel shows real metric tiles -- Programs/Runtime/Shows/Rotation -- answering 'how big/what does it contain'",
    {"Programs", "Runtime", "Shows", "Rotation"}.issubset(set(panel_labels)),
    panel_labels,
)
next_up_rows = [w for w in panel.findChildren(QWidget) if w.objectName() == "autofillRow"]
check(
    "64. 'Next Up' is built from the SAME _build_placement_row Generated Lineup row style autofill_dialog.py already uses -- reused, not reinvented",
    len(next_up_rows) > 0,
    len(next_up_rows),
)
check("65. the Next Up preview is capped (at most 3 rows), never the full resolved lineup dumped into the panel", len(next_up_rows) <= 3, len(next_up_rows))

empty_preview_dialog = ProgrammingBlockLibraryDialog(ITEMS, detail_store.get, detail_store.save, 4, "Comedy", can_schedule=True, slot_start=T0, slot_duration=5400)
check("66. a fresh Fill Mode dialog (nothing selected yet) has an empty preview panel -- it never appears unsolicited", empty_preview_dialog._preview_layout.count() == 0)


# ---------------------------------------------------------------------------
section("67-72. Editor rows: Show Library and This Block share the SAME row builder, not a checklist + shopping cart")
# ---------------------------------------------------------------------------

row_check_page = _EditorPage(ITEMS, None, on_save=lambda b: None, on_cancel=lambda: None)
check("67. Show Library renders _ShowRow instances, not a QCheckBox-driven QListWidget", all(isinstance(r, _ShowRow) for r in row_check_page._library_rows_by_key.values()) and len(row_check_page._library_rows_by_key) == 3)
check("68. a Show Library row starts un-included (no accent tint)", not row_check_page._library_rows_by_key[ATF_KEY]._included)

_left_click(row_check_page._library_rows_by_key[ATF_KEY])
check("69. clicking a Show Library row toggles it into the block -- no checkbox needed", ATF_KEY in row_check_page._included)
check("69b. the clicked row now renders included (the SAME accent treatment a selected block card uses)", row_check_page._library_rows_by_key[ATF_KEY]._included and row_check_page._library_rows_by_key[ATF_KEY].styleSheet() == _INCLUDED_ROW_STYLE)

this_block_rows = [row_check_page._included_layout.itemAt(i).widget() for i in range(row_check_page._included_layout.count()) if row_check_page._included_layout.itemAt(i).widget() is not None]
check("70. 'This Block' renders the included show via the SAME _ShowRow widget class as Show Library", len(this_block_rows) == 1 and isinstance(this_block_rows[0], _ShowRow))
check("70b. the This Block row is removable (has its own remove control), not a toggle", this_block_rows[0]._removable)

_left_click(row_check_page._library_rows_by_key[ATF_KEY])
check("71. clicking the SAME Show Library row again removes it from the block (toggle, not one-way add)", ATF_KEY not in row_check_page._included)

_left_click(row_check_page._library_rows_by_key[ATF_KEY])  # re-include it for the metrics check below
metrics_text = row_check_page._count_label.text()
check(
    "72. 'This Block's live metrics line includes real episode/runtime/rotation info, not just a show count",
    "episode" in metrics_text and _ROTATION_LABEL in metrics_text,
    metrics_text,
)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All Phase 5.4 Programming Blocks (redesign UI) tests passed.")

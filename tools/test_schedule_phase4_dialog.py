"""
Phase 4 Schedule Editor tests: AutoFillBlockDialog's pure planning glue
(group_catalog_by_show/build_preview_plan) and its widget-level preview
behavior -- strategy dispatch, cursor wording, and "preview never
mutates anything" guarantees.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase4_dialog.py
"""

import copy
import os
import sys

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


from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from PySide6.QtWidgets import QLabel

from mediawave.commercials import is_commercial_entry
from mediawave.schedule_editor.autofill_cursor import advance_cursor, empty_cursor_data
from mediawave.schedule_editor.autofill_dialog import (
    AutoFillBlockDialog,
    build_preview_plan,
    build_summary_lines,
    distinct_show_count,
)
from mediawave.schedule_editor.autofill_planner import (
    STRATEGY_BEST_FIT,
    STRATEGY_MARATHON,
    STRATEGY_RANDOM,
    STRATEGY_SEQUENTIAL,
)
from mediawave.show_identity import group_catalog_by_show

CH = "media:/catalog/Comedy"


def tv_item(path, title, season, episode, duration=1320, show_key="tv::sitcom"):
    return {
        "path": path, "title": title, "episode_label": f"S{season}E{episode}", "media_type": "tv",
        "duration": duration, "channel_name": "Comedy", "schedulable": True,
        "season_number": season, "episode_number": episode, "show_key": show_key,
    }


def commercial_item(path, title, duration=30, category=None, kind="commercial"):
    """A placement dict EXPLICITLY marked as a real commercial break --
    the only way is_commercial_entry (mediawave/commercials.py) ever
    recognizes one; nothing about `title`/`path` text matters to it.
    Mirrors the real field shape the live commercial-scheduling engine
    already uses (`is_commercial`/`kind`/`category`), not an invented one.
    """
    entry = {
        "path": path, "title": title, "episode_label": "", "media_type": "commercial",
        "duration": duration, "channel_name": "Comedy", "schedulable": True,
        "season_number": None, "episode_number": None, "show_key": f"commercial::{path}",
        "is_commercial": True, "kind": kind,
    }
    if category is not None:
        entry["category"] = category
    return entry


def movie_item(path, title, duration=5400):
    return {
        "path": path, "title": title, "episode_label": "", "media_type": "movie",
        "duration": duration, "channel_name": "Comedy", "schedulable": True,
        "season_number": None, "episode_number": None, "show_key": f"movie::{path}",
    }


# ---------------------------------------------------------------------------
section("group_catalog_by_show")
# ---------------------------------------------------------------------------

items = [
    tv_item("/m/s1e1.mp4", "Sitcom", 1, 1),
    tv_item("/m/s1e2.mp4", "Sitcom", 1, 2),
    tv_item("/m/c1e1.mp4", "Cartoon", 1, 1, show_key="tv::cartoon"),
    movie_item("/m/movie.mp4", "A Movie"),
]
shows = group_catalog_by_show(items)
check("1. movies never appear as shows", all(s["title"] != "A Movie" for s in shows.values()), shows)
check("2. two distinct shows group separately", set(shows.keys()) == {"tv::sitcom", "tv::cartoon"}, shows)
check("3. a show's episodes all land under its own show_key", len(shows["tv::sitcom"]["episodes"]) == 2, shows["tv::sitcom"])


# ---------------------------------------------------------------------------
section("build_preview_plan: strategy dispatch")
# ---------------------------------------------------------------------------

sitcom = shows["tv::sitcom"]
gap_start, gap_duration = 0, 1320

plan, notes = build_preview_plan(STRATEGY_BEST_FIT, items, gap_start, 5400)
check(
    "4. Best Fit Mix produces a lineup with a whole-lineup 'prioritized' note",
    plan is not None and len(plan["lineup"]) > 0 and notes == ["Prioritized using as much of the available block as possible."],
    (plan, notes),
)

plan, notes = build_preview_plan(STRATEGY_RANDOM, items, gap_start, 5400, seed=1)
check(
    "5. Random Mix with only one schedulable item produces no 'avoided repeats' note (nothing to repeat)",
    plan is not None and len(plan["lineup"]) == 1 and notes == [],
    (plan, notes),
)
multi_movie_items = [movie_item("/m/x.mp4", "Movie X", duration=1800), movie_item("/m/y.mp4", "Movie Y", duration=1800), movie_item("/m/z.mp4", "Movie Z", duration=1800)]
plan, notes = build_preview_plan(STRATEGY_RANDOM, multi_movie_items, gap_start, 5400, seed=1)
check(
    "5b. Random Mix with more than one placement notes that immediate repeats were avoided",
    plan is not None and len(plan["lineup"]) > 1 and notes == ["Immediate title repeats were avoided."],
    (plan, notes),
)

plan, notes = build_preview_plan(STRATEGY_MARATHON, items, gap_start, 2640, show=sitcom)
check(
    "6. Show Marathon plays the chosen show's episodes in order, ignoring any cursor, with a 'built from one show' note",
    plan is not None and [e["path"] for e in plan["lineup"]] == ["/m/s1e1.mp4", "/m/s1e2.mp4"]
    and notes == ["Built from one show in episode order."],
    (plan, notes),
)

plan, notes = build_preview_plan(STRATEGY_MARATHON, items, gap_start, 2640, show=None)
check("7. a show-required strategy with no show chosen yields no plan and no notes", plan is None and notes == [], (plan, notes))


# ---------------------------------------------------------------------------
section("build_preview_plan: Continue Sequentially cursor handling")
# ---------------------------------------------------------------------------

plan, notes = build_preview_plan(
    STRATEGY_SEQUENTIAL, items, gap_start, 1320, show=sitcom, cursor_data=empty_cursor_data(), channel_id=CH,
)
check(
    "8. no cursor -> starts from the first episode, with an honest 'no prior placement' note",
    plan is not None and [e["path"] for e in plan["lineup"]] == ["/m/s1e1.mp4"]
    and len(notes) == 1 and "No prior sequential Auto-Fill placement" in notes[0],
    (plan, notes),
)
check("8b. wording never claims actual playback/airing", "aired" not in notes[0].lower())

cursor_data = advance_cursor(empty_cursor_data(), CH, "tv::sitcom", "/m/s1e1.mp4", now=1000)
plan, notes = build_preview_plan(
    STRATEGY_SEQUENTIAL, items, gap_start, 1320, show=sitcom, cursor_data=cursor_data, channel_id=CH,
)
check(
    "9. a real cursor resumes after the last-placed episode",
    plan is not None and [e["path"] for e in plan["lineup"]] == ["/m/s1e2.mp4"],
    plan,
)
check(
    "9b. the wording says 'last saved sequential Auto-Fill placement', never 'last aired episode', and names the resumed-from episode",
    "last saved sequential Auto-Fill placement" in notes[0] and "last aired" not in notes[0].lower() and "S1 · E1" in notes[0],
    notes,
)

stale_cursor = advance_cursor(empty_cursor_data(), CH, "tv::sitcom", "/m/s1e_removed.mp4", now=1000)
plan, notes = build_preview_plan(
    STRATEGY_SEQUENTIAL, items, gap_start, 1320, show=sitcom, cursor_data=stale_cursor, channel_id=CH,
)
check(
    "10. a stale cursor (episode no longer in catalog) falls back to the first episode safely",
    plan is not None and [e["path"] for e in plan["lineup"]] == ["/m/s1e1.mp4"],
    plan,
)
check("10b. the stale-cursor note is calm, not an error", "no longer available" in notes[0], notes)


# ---------------------------------------------------------------------------
section("Dialog: preview generation never mutates anything")
# ---------------------------------------------------------------------------

items_snapshot = copy.deepcopy(items)
cursor_snapshot = copy.deepcopy(cursor_data)

dialog = AutoFillBlockDialog(items, CH, 4, "Comedy", 0, 5400, cursor_data=cursor_data, parent=None)
check("11. constructing the dialog (which generates an initial preview) doesn't mutate the catalog items", items == items_snapshot, items)
check("11b. constructing the dialog doesn't mutate the cursor data", cursor_data == cursor_snapshot, cursor_data)

dialog._set_strategy(STRATEGY_SEQUENTIAL)
index = dialog._show_combo.findData("tv::sitcom")
if index >= 0:
    dialog._show_combo.setCurrentIndex(index)
dialog._regenerate()
check("12. switching strategy/show and regenerating doesn't mutate the catalog items", items == items_snapshot, items)
check("12b. regenerating doesn't mutate the cursor data", cursor_data == cursor_snapshot, cursor_data)

dialog._set_strategy(STRATEGY_RANDOM)
before_seed = dialog._random_seed
dialog._regenerate_randomly()
check("13. Regenerate changes the proposal without mutating the catalog", items == items_snapshot and dialog._random_seed != before_seed, items)


# ---------------------------------------------------------------------------
section("Dialog: preview summary and previewed_lineup()")
# ---------------------------------------------------------------------------

full_items = [tv_item("/m/only.mp4", "OnlyShow", 1, 1, duration=1800, show_key="tv::only")]
full_dialog = AutoFillBlockDialog(full_items, CH, 4, "Comedy", 0, 1800, cursor_data=None, parent=None)
full_dialog._set_strategy(STRATEGY_MARATHON)
idx = full_dialog._show_combo.findData("tv::only")
full_dialog._show_combo.setCurrentIndex(idx)
check(
    "14. a lineup that exactly fills the block reports program/show/duration counts AND 'Uses the full block'",
    full_dialog._summary.text() == "1 program · 1 show · 30 min scheduled\nUses the full block",
    full_dialog._summary.text(),
)
check("15. previewed_lineup() returns the currently-generated plan's lineup", [e["path"] for e in full_dialog.previewed_lineup()] == ["/m/only.mp4"])

short_items = [tv_item("/m/short.mp4", "ShortShow", 1, 1, duration=700, show_key="tv::short")]
short_dialog = AutoFillBlockDialog(short_items, CH, 4, "Comedy", 0, 1800, cursor_data=None, parent=None)
short_dialog._set_strategy(STRATEGY_MARATHON)
idx = short_dialog._show_combo.findData("tv::short")
short_dialog._show_combo.setCurrentIndex(idx)
short_dialog._regenerate()
check(
    "16. leftover open time is reported as a fill percentage plus remaining Open Time, not silently dropped",
    "% filled" in short_dialog._summary.text() and "Open Time" in short_dialog._summary.text(),
    short_dialog._summary.text(),
)


# ---------------------------------------------------------------------------
section("distinct_show_count / build_summary_lines (pure, no Qt)")
# ---------------------------------------------------------------------------

mixed_lineup = [
    tv_item("/m/s1e1.mp4", "Sitcom", 1, 1, duration=1800),
    tv_item("/m/s1e2.mp4", "Sitcom", 1, 2, duration=1800),
    movie_item("/m/x.mp4", "Movie X", duration=1800),
]
check("20. distinct_show_count counts unique show_key, not unique titles or row count", distinct_show_count(mixed_lineup) == 2, mixed_lineup)

full_plan = {"lineup": mixed_lineup, "filled_seconds": 5400, "gap_duration": 5400, "leftover_seconds": 0}
check(
    "21. build_summary_lines: full block reports program/show/duration counts plus 'Uses the full block'",
    build_summary_lines(full_plan) == ["3 programs · 2 shows · 1 hr 30 min scheduled", "Uses the full block"],
    build_summary_lines(full_plan),
)

partial_plan = {"lineup": mixed_lineup[:1], "filled_seconds": 1800, "gap_duration": 3600, "leftover_seconds": 1800}
check(
    "22. build_summary_lines: partial fill reports a percentage and remaining Open Time",
    build_summary_lines(partial_plan) == ["1 program · 1 show · 30 min scheduled", "50% filled · 30 min Open Time"],
    build_summary_lines(partial_plan),
)

check("23. build_summary_lines returns nothing for an empty/missing plan", build_summary_lines(None) == [] and build_summary_lines({"lineup": []}) == [])

long_plan = {"lineup": mixed_lineup, "filled_seconds": 178 * 60, "gap_duration": 180 * 60, "leftover_seconds": 2 * 60}
check(
    "24. build_summary_lines formats hours-and-minutes durations correctly ('2 hr 58 min')",
    build_summary_lines(long_plan)[0].endswith("2 hr 58 min scheduled"),
    build_summary_lines(long_plan),
)


# ---------------------------------------------------------------------------
section("Preview rows: compact card widgets, not plain-text list items")
# ---------------------------------------------------------------------------

row_items = [
    tv_item("/m/s1e1.mp4", "Sitcom", 1, 1, duration=1800),
    movie_item("/m/movie.mp4", "Big Movie Night", duration=1800),
]
row_dialog = AutoFillBlockDialog(row_items, CH, 4, "Comedy", 0, 3600, cursor_data=None, parent=None)
row_dialog._set_strategy(STRATEGY_BEST_FIT)
row_dialog._regenerate()
check("25. the preview list has one row per placement (no header/footer rows mixed in)", row_dialog._list.count() == len(row_dialog.previewed_lineup()), row_dialog._list.count())

first_item = row_dialog._list.item(0)
first_widget = row_dialog._list.itemWidget(first_item)
check("26. each placement renders as a real row widget, not a plain-text QListWidgetItem", first_widget is not None)
row_labels = first_widget.findChildren(QLabel)
row_texts = [lbl.text() for lbl in row_labels]
check("27. the row shows the placement's title text", any(row_dialog.previewed_lineup()[0]["title"] in t for t in row_texts), row_texts)
check("28. the row shows the placement's duration text", any("min" in t for t in row_texts), row_texts)

sitcom_entry = next(e for e in row_dialog.previewed_lineup() if e["media_type"] == "tv")
sitcom_index = row_dialog.previewed_lineup().index(sitcom_entry)
sitcom_widget = row_dialog._list.itemWidget(row_dialog._list.item(sitcom_index))
sitcom_labels = [lbl.text() for lbl in sitcom_widget.findChildren(QLabel)]
check("29. a TV placement's row shows its episode label", any("S1" in t for t in sitcom_labels), sitcom_labels)

from mediawave.schedule_editor.autofill_dialog import _build_placement_row, commercial_source_label


def as_placement(item, start=0):
    """Catalog items (tv_item/movie_item/commercial_item) don't carry
    start/end -- only a planner PLACEMENT does (see autofill_planner._
    placement). _build_placement_row renders placements, so direct
    unit tests on it need this tiny shape adapter rather than duplicating
    the planner's own placement-building logic.
    """
    entry = dict(item)
    entry["start"] = start
    entry["end"] = start + entry["duration"]
    return entry


lookalike_entry = as_placement(tv_item("/m/mxc.mp4", "MXC Commercial", 1, 1, duration=1320))
check(
    "31. an ordinary catalog item whose TITLE contains 'Commercial' is NOT treated as a commercial break without explicit metadata",
    commercial_source_label(lookalike_entry) == "" and not is_commercial_entry(lookalike_entry),
    lookalike_entry,
)
lookalike_widget = _build_placement_row(lookalike_entry)
lookalike_texts = [lbl.text() for lbl in lookalike_widget.findChildren(QLabel)]
check(
    "31b. that lookalike item's row shows its REAL title, not 'Commercial Break'",
    any("MXC Commercial" in t for t in lookalike_texts) and not any(t == "Commercial Break" for t in lookalike_texts),
    lookalike_texts,
)

labeled_commercial = as_placement(commercial_item("/m/ad1.mp4", "Weird File Name 42.mp4", category="80s Adult"))
commercial_widget = _build_placement_row(labeled_commercial)
commercial_texts = [lbl.text() for lbl in commercial_widget.findChildren(QLabel)]
check("32. an explicit commercial placement displays 'Commercial Break' as its heading", "Commercial Break" in commercial_texts, commercial_texts)
check(
    "32b. the commercial's own filename/title is never shown as the primary label",
    not any("Weird File Name" in t for t in commercial_texts),
    commercial_texts,
)
check("33. an existing category label is shown as a bracketed subtitle", "[80s Adult]" in commercial_texts, commercial_texts)

unlabeled_commercial = as_placement(commercial_item("/m/ad2.mp4", "Untitled Ad"))
unlabeled_widget = _build_placement_row(unlabeled_commercial)
unlabeled_texts = [lbl.text() for lbl in unlabeled_widget.findChildren(QLabel)]
check(
    "34. missing commercial category metadata produces no invented subtitle (only 'Commercial Break' plus time/duration)",
    "Commercial Break" in unlabeled_texts and not any(t.startswith("[") for t in unlabeled_texts),
    unlabeled_texts,
)
check("34b. commercial_source_label never invents a label when no category is present", commercial_source_label(unlabeled_commercial) == "")

check(
    "35. a commercial row still shows its real time range and duration",
    any("min" in t for t in unlabeled_texts) and any("–" in t for t in unlabeled_texts),
    unlabeled_texts,
)


# ---------------------------------------------------------------------------
section("Commercial-aware summary metrics")
# ---------------------------------------------------------------------------

commercial_lineup = [
    tv_item("/m/s1e1.mp4", "Sitcom", 1, 1, duration=1320),
    tv_item("/m/s1e2.mp4", "Sitcom", 1, 2, duration=1320),
    tv_item("/m/c1e1.mp4", "Cartoon", 1, 1, duration=1320, show_key="tv::cartoon"),
    commercial_item("/m/ad1.mp4", "Ad One", duration=30),
    commercial_item("/m/ad2.mp4", "Ad Two", duration=30),
]
check(
    "36. distinct_show_count over program-only entries excludes commercial placements entirely",
    distinct_show_count([e for e in commercial_lineup if not is_commercial_entry(e)]) == 2,
    commercial_lineup,
)
commercial_plan = {
    "lineup": commercial_lineup,
    "filled_seconds": sum(e["duration"] for e in commercial_lineup),
    "gap_duration": sum(e["duration"] for e in commercial_lineup),
    "leftover_seconds": 0,
}
summary = build_summary_lines(commercial_plan)
check(
    "37. the summary's program count excludes commercials, and reports a separate commercial-break count",
    summary[0].startswith("3 programs · 2 shows") and summary[1] == "Includes 2 commercial breaks",
    summary,
)
check("37b. commercial-free lineups never show an 'Includes N commercial breaks' line", not any("commercial break" in line.lower() for line in build_summary_lines(full_plan)), build_summary_lines(full_plan))

single_commercial_plan = {
    "lineup": [tv_item("/m/s1e1.mp4", "Sitcom", 1, 1, duration=1320), commercial_item("/m/ad1.mp4", "Ad One", duration=30)],
    "filled_seconds": 1350, "gap_duration": 1350, "leftover_seconds": 0,
}
check("37c. exactly one commercial break uses singular wording", build_summary_lines(single_commercial_plan)[1] == "Includes 1 commercial break", build_summary_lines(single_commercial_plan))

movie_entry_index = row_dialog.previewed_lineup().index(next(e for e in row_dialog.previewed_lineup() if e["media_type"] == "movie"))
movie_widget = row_dialog._list.itemWidget(row_dialog._list.item(movie_entry_index))
movie_labels = [lbl.text() for lbl in movie_widget.findChildren(QLabel)]
check("30. a movie placement's row has no stray episode line (no episode_label to show)", not any("S1" in t or "E1" in t for t in movie_labels), movie_labels)


# ---------------------------------------------------------------------------
section("Generated Lineup header")
# ---------------------------------------------------------------------------

header_items = [movie_item("/m/x.mp4", "Movie X", duration=1800), movie_item("/m/y.mp4", "Movie Y", duration=1800)]
header_dialog = AutoFillBlockDialog(header_items, CH, 4, "Comedy", 0, 3600, cursor_data=None, parent=None)
eyebrow_texts = [lbl.text() for lbl in header_dialog.findChildren(QLabel) if lbl.text() == "GENERATED LINEUP"]
check("38. the 'GENERATED LINEUP' header exists above the preview list", len(eyebrow_texts) == 1, eyebrow_texts)

header_dialog._set_strategy(STRATEGY_BEST_FIT)
check("39. Regenerate is hidden for a strategy that doesn't support it (Best Fit Mix)", header_dialog._regen_btn.isHidden())
header_dialog._set_strategy(STRATEGY_RANDOM)
check("40. Regenerate is shown for Random Mix, the one strategy it supports", not header_dialog._regen_btn.isHidden())
check(
    "41. Regenerate lives in the same header row layout as the eyebrow (not its own detached row)",
    header_dialog._regen_btn.parentWidget() is not None,
)

before_random_regen = header_dialog.previewed_lineup()
header_dialog._regenerate_randomly()
check(
    "42. clicking Regenerate still produces exactly one preview row per placement (no extra/fake rows from the new spacing)",
    header_dialog._list.count() == len(header_dialog.previewed_lineup()),
    (header_dialog._list.count(), header_dialog.previewed_lineup()),
)
rendered_titles = []
for i in range(header_dialog._list.count()):
    widget = header_dialog._list.itemWidget(header_dialog._list.item(i))
    # Row label creation order is fixed (see _build_placement_row): time,
    # duration, then title -- index 2 is always the title label.
    rendered_titles.append(widget.findChildren(QLabel)[2].text())
check(
    "43. the regenerated preview's row order exactly matches previewed_lineup()'s order (what AutoFillBlockCommand will receive)",
    rendered_titles == [entry["title"] for entry in header_dialog.previewed_lineup()],
    (rendered_titles, [e["title"] for e in header_dialog.previewed_lineup()]),
)


# ---------------------------------------------------------------------------
section("Dialog: empty/failure states")
# ---------------------------------------------------------------------------

no_media_dialog = AutoFillBlockDialog([], CH, 4, "Comedy", 0, 1800, cursor_data=None, parent=None)
check("17. no catalog media disables Place Lineup instead of crashing", not no_media_dialog._confirm_btn.isEnabled())

no_show_items = [movie_item("/m/movie.mp4", "A Movie")]
no_show_dialog = AutoFillBlockDialog(no_show_items, CH, 4, "Comedy", 0, 1800, cursor_data=None, parent=None)
check(
    "18. show-only strategies are disabled outright when the catalog has no shows",
    not no_show_dialog._chips[STRATEGY_SEQUENTIAL].isEnabled() and not no_show_dialog._chips[STRATEGY_MARATHON].isEnabled(),
)

no_selection_items = [tv_item("/m/e1.mp4", "HasEpisodes", 1, 1, duration=1800, show_key="tv::has")]
no_selection_dialog = AutoFillBlockDialog(no_selection_items, CH, 4, "Comedy", 0, 1800, cursor_data=None, parent=None)
no_selection_dialog._set_strategy(STRATEGY_SEQUENTIAL)
check(
    "19. switching to a show-required strategy auto-selects the only available show and previews it",
    no_selection_dialog._confirm_btn.isEnabled() and no_selection_dialog.previewed_lineup()[0]["path"] == "/m/e1.mp4",
    no_selection_dialog.previewed_lineup(),
)
empty_show_plan, _ = build_preview_plan(STRATEGY_SEQUENTIAL, [], 0, 1800, show=None)
check("19b. build_preview_plan itself still reports 'no plan' when no show is passed at all", empty_show_plan is None)


# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed checks:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("All schedule phase 4 dialog tests passed.")

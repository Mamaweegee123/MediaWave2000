"""
Phase 5.5.2 step 2 tests: build_picker_catalog's canonical show identity
annotation and the one shared group_catalog_by_show helper -- proving an
empty/None registry leaves catalog output unchanged from before this
step, and that a synthetic corrected registry produces the expected
merged grouping without disturbing per-episode fields.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase552_catalog_annotation.py
"""

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


from mediawave.local_media import metadata_lookup_key, parse_local_media
from mediawave.schedule_editor.put_on_air_picker import build_picker_catalog
from mediawave.show_identity import (
    create_registry_record,
    empty_registry,
    group_catalog_by_show,
    mint_show_key,
)


class _FakeChannel:
    def __init__(self, name, shows, duration_cache=None, channel_type="media"):
        self.name = name
        self.shows = shows
        self.duration_cache = duration_cache or {}
        self.channel_type = channel_type


# Two files that MediaWave's filename parser currently treats as two
# DIFFERENT shows (different show name in the filename itself -- a
# realistic case of one season retagged under a slightly different
# title) -- exactly the kind of fragmentation Phase 5.5 exists to let a
# user correct.
MORAL_OREL_1 = "/media/TV/Moral Orel/Season 1/Moral Orel - S01E01 - Numb.mp4"
MORAL_OREL_2 = "/media/TV/Moral Orel Redux/Season 1/Moral Orel Redux - S01E02 - Numb Pt2.mp4"
KOTH_1 = "/media/TV/King of the Hill/Season 1/King of the Hill - S01E01 - Pilot.mp4"
MOVIE_1 = "/media/Movies/Some Movie (2010)/Some Movie (2010).mkv"

CHANNELS = {
    "ch1": _FakeChannel(
        "Comedy",
        [MORAL_OREL_1, MORAL_OREL_2, KOTH_1, MOVIE_1],
        duration_cache={MORAL_OREL_1: 1320, MORAL_OREL_2: 1320, KOTH_1: 1320, MOVIE_1: 5400},
    ),
}


section("Empty/None registry: catalog output unchanged")

items_no_registry = build_picker_catalog(CHANNELS, {"ch1": "Comedy"})
items_empty_registry = build_picker_catalog(CHANNELS, {"ch1": "Comedy"}, show_identity_registry=empty_registry())

check("None registry and omitted registry produce identical output", items_no_registry == items_empty_registry)

by_path = {item["path"]: item for item in items_no_registry}
for path in (MORAL_OREL_1, MORAL_OREL_2, KOTH_1, MOVIE_1):
    parsed = parse_local_media(path)
    expected_key = metadata_lookup_key(path, parsed)
    item = by_path[path]
    check(f"untouched show_key is bit-for-bit metadata_lookup_key for {os.path.basename(path)}", item["show_key"] == expected_key)
    check(f"raw_show_key matches too for {os.path.basename(path)}", item["raw_show_key"] == expected_key)
    check(f"source is 'parsed' for {os.path.basename(path)}", item["show_identity_source"] == "parsed")
    check(f"show_display_name is empty for an uncorrected show ({os.path.basename(path)})", item["show_display_name"] == "")
    check(f"title is untouched for {os.path.basename(path)}", item["title"] == (parsed.get("show_name") or parsed.get("timeline_title") or os.path.basename(path)))


section("Synthetic corrected registry: two raw aliases merge into one canonical show")

raw_key_1 = metadata_lookup_key(MORAL_OREL_1, parse_local_media(MORAL_OREL_1))
raw_key_2 = metadata_lookup_key(MORAL_OREL_2, parse_local_media(MORAL_OREL_2))
check("the two Moral Orel files start out with different raw keys (fragmented)", raw_key_1 != raw_key_2)

canonical_key = mint_show_key()
registry = {
    "version": 1,
    "shows": {
        canonical_key: create_registry_record("Moral Orel", aliases=[raw_key_1, raw_key_2], now=1.0),
    },
    "raw_key_to_show_key": {raw_key_1: canonical_key, raw_key_2: canonical_key},
    "folder_rules": {},
}

items_corrected = build_picker_catalog(CHANNELS, {"ch1": "Comedy"}, show_identity_registry=registry)
by_path_corrected = {item["path"]: item for item in items_corrected}

item_1 = by_path_corrected[MORAL_OREL_1]
item_2 = by_path_corrected[MORAL_OREL_2]
check("both aliased files resolve to the same canonical show_key", item_1["show_key"] == item_2["show_key"] == canonical_key)
check("both aliased files keep their own distinct raw_show_key", item_1["raw_show_key"] == raw_key_1 and item_2["raw_show_key"] == raw_key_2)
check("both aliased files report source 'override'", item_1["show_identity_source"] == "override" and item_2["show_identity_source"] == "override")
check("both aliased files carry the corrected display name", item_1["show_display_name"] == "Moral Orel" and item_2["show_display_name"] == "Moral Orel")
check("episode-level title is NOT overwritten by the show display name", item_1["title"] != "Moral Orel" or item_1["episode_title"] != "")
check("episode-level detail_title still reflects the concrete file, not the corrected show name alone", "Numb" in item_1["detail_title"])

unaffected_item = by_path_corrected[KOTH_1]
check("an unrelated show is unaffected by another show's correction", unaffected_item["show_identity_source"] == "parsed")


section("group_catalog_by_show: uncorrected catalog (empty registry) matches prior grouping shape")

groups_uncorrected = group_catalog_by_show(items_no_registry)
check("two distinct TV shows group separately when untouched", raw_key_1 in groups_uncorrected and metadata_lookup_key(KOTH_1, parse_local_media(KOTH_1)) in groups_uncorrected)
check("the two differently-titled/keyed Moral Orel files remain two separate groups pre-correction", raw_key_1 in groups_uncorrected and raw_key_2 in groups_uncorrected and raw_key_1 != raw_key_2)
check("movies never appear as a show group", all(group["title"] != "Some Movie (2010)" for group in groups_uncorrected.values()))
koth_key = metadata_lookup_key(KOTH_1, parse_local_media(KOTH_1))
check("episode_count is correct pre-correction", groups_uncorrected[koth_key]["episode_count"] == 1)
check("source is 'parsed' pre-correction", groups_uncorrected[koth_key]["source"] == "parsed")


section("group_catalog_by_show: corrected catalog merges into one group")

groups_corrected = group_catalog_by_show(items_corrected)
check("exactly one group exists for the canonical show_key", canonical_key in groups_corrected)
check("the merged group's title is the corrected display name", groups_corrected[canonical_key]["title"] == "Moral Orel")
check("the merged group contains both episodes", groups_corrected[canonical_key]["episode_count"] == 2)
check("the merged group's season_count reflects both episodes' season metadata", groups_corrected[canonical_key]["season_count"] == 1)
check("the merged group collects both raw aliases", groups_corrected[canonical_key]["raw_aliases_present"] == {raw_key_1, raw_key_2})
check("the merged group is marked as 'override'", groups_corrected[canonical_key]["source"] == "override")
check("each concrete episode in the merged group keeps its own path", {ep["path"] for ep in groups_corrected[canonical_key]["episodes"]} == {MORAL_OREL_1, MORAL_OREL_2})


section("group_catalog_by_show: same display name, different canonical keys stay separate")

other_canonical_key = mint_show_key()
items_two_moral_orels = [
    dict(item_1, show_key=canonical_key, show_display_name="Moral Orel"),
    dict(item_2, show_key=other_canonical_key, show_display_name="Moral Orel"),
]
groups_same_name = group_catalog_by_show(items_two_moral_orels)
check("two distinct canonical show_keys with the identical display name remain two groups", len(groups_same_name) == 2)
check("both groups carry the same title despite being separate shows", all(group["title"] == "Moral Orel" for group in groups_same_name.values()))


section("group_catalog_by_show ignores movies and does not mutate inputs")

import copy

items_snapshot = copy.deepcopy(items_corrected)
group_catalog_by_show(items_corrected)
check("group_catalog_by_show does not mutate its input items", items_corrected == items_snapshot)
check("no movie item ever appears across any episodes list", not any(ep.get("media_type") == "movie" for group in groups_corrected.values() for ep in group["episodes"]))


section("Show Picker and Auto-Fill dialog use the shared grouping helper (no duplicated implementations remain)")

import mediawave.schedule_editor.put_on_air_picker as picker_module
import mediawave.schedule_editor.autofill_dialog as autofill_dialog_module
import mediawave.schedule_editor.programming_block_dialog as pbd_module

check("put_on_air_picker no longer defines group_shows_for_picker", not hasattr(picker_module, "group_shows_for_picker"))
check("autofill_dialog no longer defines group_shows", not hasattr(autofill_dialog_module, "group_shows"))
check("put_on_air_picker imports the shared helper", picker_module.group_catalog_by_show is group_catalog_by_show)
check("autofill_dialog imports the shared helper", autofill_dialog_module.group_catalog_by_show is group_catalog_by_show)
check("programming_block_dialog imports the shared helper", pbd_module.group_catalog_by_show is group_catalog_by_show)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

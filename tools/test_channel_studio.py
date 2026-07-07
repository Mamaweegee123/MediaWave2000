"""
Smoke tests for the Phase 1 Channel Studio read-only data adapter.
Run from the repo root:  venv/bin/python3 tools/test_channel_studio.py
No GUI required — only channel_studio_model.py / channel_studio_adapter.py
are imported, neither of which touches Qt or the filesystem.
"""
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.channel_studio import channel_studio_adapter as adapter
from mediawave.channel_studio.channel_studio_model import ChannelStudioSummary, TonightSchedule
from mediawave.channel_studio import reorder
from mediawave.channel_studio import studio_state

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


# ---------------------------------------------------------------------------
# build_channel_studio_summary — mixed media counts
# ---------------------------------------------------------------------------
section("build_channel_studio_summary: mixed media counts")

info = {
    "id": "media:/fake/root",
    "name": "Retro Cartoons",
    "channel_type": "media",
    "root_path": "/fake/root",
    "default_number": 5,
}
shows = [
    {"title": "Show A", "title_key": "show-a", "media_type": "tv"},
    {"title": "Show B", "title_key": "show-b", "media_type": "tv"},
    {"title": "Movie A", "title_key": "movie-a", "media_type": "movie"},
]
summary = adapter.build_channel_studio_summary(info, shows=shows)
check("channel id preserved", summary.channel_id == "media:/fake/root")
check("show count counts tv items", summary.show_count == 2, summary.show_count)
check("movie count counts movie items", summary.movie_count == 1, summary.movie_count)
check("content_known true when shows given", summary.content_known is True)
check("headline mentions shows and movies", "2 shows" in summary.headline and "1 movie" in summary.headline, summary.headline)

# ---------------------------------------------------------------------------
# build_channel_studio_summary — no data yet (zero-config folder channel)
# ---------------------------------------------------------------------------
section("build_channel_studio_summary: zero-config folder channel")

bare_info = {
    "id": "media:/fake/bare",
    "name": "Bare Folder",
    "channel_type": "media",
    "root_path": "/fake/bare",
    "default_number": 1,
}
bare_summary = adapter.build_channel_studio_summary(bare_info)
check("content_known false with no shows given", bare_summary.content_known is False)
check("headline falls back to folder channel copy", bare_summary.headline == "Folder channel · ready to play", bare_summary.headline)

# ---------------------------------------------------------------------------
# build_channel_studio_summary — missing logo falls back safely
# ---------------------------------------------------------------------------
section("build_channel_studio_summary: missing logo")

no_logo_summary = adapter.build_channel_studio_summary(info, shows=shows, logo_path="")
check("empty logo path is safe, not None", no_logo_summary.logo_path == "")
check("summary is still a valid dataclass instance", isinstance(no_logo_summary, ChannelStudioSummary))

# ---------------------------------------------------------------------------
# commercial status resolution
# ---------------------------------------------------------------------------
section("commercial status resolution")

commercials_config = {
    "enabled": True,
    "mode": "between_episodes",
    "channel_overrides": {
        "Retro Cartoons": {"enabled_mode": "off"},
    },
}
on_summary = adapter.build_channel_studio_summary({**info, "name": "Other Channel"}, commercials_config=commercials_config)
off_summary = adapter.build_channel_studio_summary(info, commercials_config=commercials_config)
check("global commercials enabled applies by default", on_summary.commercials_enabled is True)
check("per-channel override turns commercials off", off_summary.commercials_enabled is False)

# ---------------------------------------------------------------------------
# airing rule / seasonal rule counts
# ---------------------------------------------------------------------------
section("airing rule and seasonal rule counts")

airing_rules_config = {
    "channel_rules": [
        {"target": {"channel_id": "media:/fake/root"}},
        {"target": {"channel_id": "media:/other"}},
    ],
    "channel_takeovers": [
        {"source_channel_id": "media:/fake/root", "seasonal_preset": "halloween"},
        {"source_channel_id": "media:/fake/root", "seasonal_preset": ""},
    ],
}
hinted_summary = adapter.build_channel_studio_summary(info, airing_rules_config=airing_rules_config)
check("airing rule count matches only this channel", hinted_summary.airing_rule_count == 1, hinted_summary.airing_rule_count)
check("seasonal rule count ignores empty preset", hinted_summary.seasonal_rule_count == 1, hinted_summary.seasonal_rule_count)
check("has_hints true when rules exist", hinted_summary.has_hints is True)

# ---------------------------------------------------------------------------
# build_channel_studio_summaries — batch, order preserved
# ---------------------------------------------------------------------------
section("build_channel_studio_summaries: batch")

infos = [info, bare_info]
shows_lookup = {"media:/fake/root": shows}
summaries = adapter.build_channel_studio_summaries(infos, shows_lookup=shows_lookup)
check("batch returns one summary per info", len(summaries) == 2, len(summaries))
check("batch preserves input order", [s.channel_id for s in summaries] == [i["id"] for i in infos])
check("batch summary picks up shows_lookup by id", summaries[0].show_count == 2, summaries[0].show_count)
check("batch summary with no lookup entry is safe", summaries[1].content_known is False)


# ---------------------------------------------------------------------------
# Tonight's Schedule — no live channel object (graceful empty state)
# ---------------------------------------------------------------------------
section("build_tonight_schedule: no live channel")

no_channel_schedule = adapter.build_tonight_schedule(info, channel=None)
check("returns TonightSchedule instance", isinstance(no_channel_schedule, TonightSchedule))
check("has_data is False with no channel object", no_channel_schedule.has_data is False)
check("slots empty with no channel object", no_channel_schedule.slots == [])
check("channel name preserved even with no data", no_channel_schedule.channel_name == "Retro Cartoons")


class _EmptyScheduleChannel:
    """Mimics a real Channel with no schedule entries yet."""

    def get_programs_for_window(self, window_start, count=8):
        return []


class _FakeScheduleChannel:
    """Mimics a real Channel object's get_programs_for_window contract."""

    def get_programs_for_window(self, window_start, count=8):
        return [
            {"path": "/fake/a.mp4", "title": "Episode One", "start": window_start, "end": window_start + 1800},
            {"path": "/fake/b.mp4", "title": "Episode Two", "start": window_start + 1800, "end": window_start + 3600},
        ][:count]


# ---------------------------------------------------------------------------
# Tonight's Schedule — empty schedule from a real channel object
# ---------------------------------------------------------------------------
section("build_tonight_schedule: empty schedule handled gracefully")

empty_schedule = adapter.build_tonight_schedule(info, channel=_EmptyScheduleChannel())
check("has_data is False when channel returns no programs", empty_schedule.has_data is False)
check("slots empty when channel returns no programs", empty_schedule.slots == [])

# ---------------------------------------------------------------------------
# Tonight's Schedule — populated from the existing schedule engine
# ---------------------------------------------------------------------------
section("build_tonight_schedule: populated from schedule engine")

filled_schedule = adapter.build_tonight_schedule(info, channel=_FakeScheduleChannel(), slot_count=2)
check("has_data True when channel has programs", filled_schedule.has_data is True)
check("slot count matches programs returned", len(filled_schedule.slots) == 2, len(filled_schedule.slots))
check("slot titles carried through", filled_schedule.slots[0].title == "Episode One", filled_schedule.slots[0].title)
check("slot time_label is a non-empty string", isinstance(filled_schedule.slots[0].time_label, str) and filled_schedule.slots[0].time_label)

# ---------------------------------------------------------------------------
# build_tonight_schedules — batch
# ---------------------------------------------------------------------------
section("build_tonight_schedules: batch")

batch_schedules = adapter.build_tonight_schedules(
    [info, bare_info],
    channels_by_id={"media:/fake/root": _FakeScheduleChannel()},
)
check("batch returns one schedule per info", len(batch_schedules) == 2)
check("channel with mapping gets real data", batch_schedules[0].has_data is True)
check("channel without mapping gets graceful empty state", batch_schedules[1].has_data is False)

# ---------------------------------------------------------------------------
# No writes: adapter never mutates the settings dicts it's given
# ---------------------------------------------------------------------------
section("no writes occur during adapter/preview generation")

import copy

original_commercials = copy.deepcopy(commercials_config)
original_airing_rules = copy.deepcopy(airing_rules_config)
original_info = copy.deepcopy(info)
adapter.build_channel_studio_summary(
    original_info, shows=shows, commercials_config=original_commercials, airing_rules_config=original_airing_rules
)
check("commercials_config left untouched", original_commercials == commercials_config)
check("airing_rules_config left untouched", original_airing_rules == airing_rules_config)
check("channel info dict left untouched", original_info == info)

# ---------------------------------------------------------------------------
# reorder.apply_saved_order — merging a saved display order with reality
# ---------------------------------------------------------------------------
section("reorder.apply_saved_order")

channel_ids = ["a", "b", "c", "d"]

saved_full = ["c", "a", "b", "d"]
result_full = reorder.apply_saved_order(channel_ids, saved_full)
check("saved order applied when it covers everything", result_full == saved_full, result_full)

saved_stale = ["z", "c", "a", "y"]
result_stale = reorder.apply_saved_order(channel_ids, saved_stale)
check("stale/missing ids in saved order are dropped", "z" not in result_stale and "y" not in result_stale, result_stale)
check("known ids from saved order still lead", result_stale[:2] == ["c", "a"], result_stale)

saved_partial = ["d", "b"]
result_partial = reorder.apply_saved_order(channel_ids, saved_partial)
check(
    "channels not in saved order are appended, in original order",
    result_partial == ["d", "b", "a", "c"],
    result_partial,
)

result_empty_saved = reorder.apply_saved_order(channel_ids, [])
check("no saved order falls back to original order", result_empty_saved == channel_ids, result_empty_saved)

result_no_ids = reorder.apply_saved_order([], saved_full)
check("no known channels is a safe empty result", result_no_ids == [], result_no_ids)

result_dupe_check = reorder.apply_saved_order(channel_ids, saved_full)
check("no channel id is duplicated", len(result_dupe_check) == len(set(result_dupe_check)), result_dupe_check)
check("every known channel id is still present", set(result_dupe_check) == set(channel_ids), result_dupe_check)

# The hero card's channel is just another entry in the same id list handed
# to apply_saved_order — since every known id is always preserved, the
# grid can never lose the hero's channel just because it's featured above.
hero_id = "b"
check("hero channel id survives ordering like any other", hero_id in reorder.apply_saved_order(channel_ids, saved_stale))

# ---------------------------------------------------------------------------
# reorder.move_item — the drag-and-drop building block
# ---------------------------------------------------------------------------
section("reorder.move_item")

base_order = ["a", "b", "c", "d"]
moved_forward = reorder.move_item(base_order, 0, 2)
check("move item forward in the list", moved_forward == ["b", "c", "a", "d"], moved_forward)

moved_backward = reorder.move_item(base_order, 3, 0)
check("move item backward in the list", moved_backward == ["d", "a", "b", "c"], moved_backward)

moved_noop = reorder.move_item(base_order, 1, 1)
check("moving an item to its own spot is a no-op", moved_noop == base_order, moved_noop)

moved_negative = reorder.move_item(base_order, -1, 2)
check("negative from_index is ignored safely", moved_negative == base_order, moved_negative)

moved_out_of_range_from = reorder.move_item(base_order, 99, 0)
check("out-of-range from_index is ignored safely", moved_out_of_range_from == base_order, moved_out_of_range_from)

moved_out_of_range_to = reorder.move_item(base_order, 0, 99)
check(
    "out-of-range to_index is clamped, not ignored",
    moved_out_of_range_to == ["b", "c", "d", "a"],
    moved_out_of_range_to,
)

check("move_item on an empty list is a safe no-op", reorder.move_item([], 0, 1) == [])
check("original list object is not mutated", base_order == ["a", "b", "c", "d"])

# ---------------------------------------------------------------------------
# studio_state — last-edited channel and grid display order persistence
# ---------------------------------------------------------------------------
section("studio_state: last-edited channel and channel order")

import tempfile

with tempfile.TemporaryDirectory() as tmpdir:
    state_path = os.path.join(tmpdir, "channel_studio_state.json")

    check("no path is a safe no-op on save", studio_state.save_last_edited_channel_id(None, "x") is None)
    check("missing file has no last-edited channel", studio_state.load_last_edited_channel_id(state_path) == "")
    check("missing file has no saved channel order", studio_state.load_channel_order(state_path) == [])

    studio_state.save_last_edited_channel_id(state_path, "media:/fake/root")
    check(
        "last-edited channel id round-trips",
        studio_state.load_last_edited_channel_id(state_path) == "media:/fake/root",
    )

    studio_state.save_channel_order(state_path, ["c", "a", "b"])
    check(
        "channel order round-trips",
        studio_state.load_channel_order(state_path) == ["c", "a", "b"],
        studio_state.load_channel_order(state_path),
    )
    check(
        "saving channel order doesn't clobber last-edited channel",
        studio_state.load_last_edited_channel_id(state_path) == "media:/fake/root",
    )

    studio_state.save_channel_order(state_path, ["z", "y"])
    check(
        "saving channel order again overwrites the previous order",
        studio_state.load_channel_order(state_path) == ["z", "y"],
    )

    check(
        "saving with no path is a safe no-op",
        studio_state.save_channel_order(None, ["a"]) is None,
    )

malformed_path = os.path.join(tempfile.gettempdir(), "channel_studio_state_malformed_test.json")
with open(malformed_path, "w", encoding="utf-8") as handle:
    handle.write("not valid json{{{")
check("malformed state file falls back safely for last-edited", studio_state.load_last_edited_channel_id(malformed_path) == "")
check("malformed state file falls back safely for channel order", studio_state.load_channel_order(malformed_path) == [])
os.remove(malformed_path)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
else:
    print("All smoke tests passed.")

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
from mediawave.channel_studio import companion_adapter
from mediawave.channel_studio import channel_actions

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
# ChannelStudioSummary.is_companion / headline for companion channel types
# ---------------------------------------------------------------------------
section("ChannelStudioSummary: companion channel types")

companion_summary = ChannelStudioSummary(
    channel_id="special:radiowave",
    name="RadioWaveTV",
    number=3,
    channel_type="radiowave",
    companion_info_label="Music Folder",
    companion_info_value="/Music/RadioWave",
)
check("radiowave is recognized as a companion", companion_summary.is_companion is True)
check("companion headline reads 'Companion channel'", companion_summary.headline == "Companion channel", companion_summary.headline)

media_summary = ChannelStudioSummary(channel_id="media:/x", name="X", number=1, channel_type="media")
check("a media channel is not a companion", media_summary.is_companion is False)

missing_summary = ChannelStudioSummary(channel_id="media-name:x", name="X", number=1, channel_type="missing")
check("a 'missing' channel type is not a companion (unchanged legacy behavior)", missing_summary.is_companion is False)
check("a 'missing' channel still gets the old special-channel headline", missing_summary.headline == "Special channel · built in", missing_summary.headline)

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
# reorder.overlay_top_left — the drag-ghost cursor-hotspot math
# ---------------------------------------------------------------------------
section("reorder.overlay_top_left")

check(
    "clicking a card's own top-left keeps the overlay under the cursor exactly",
    reorder.overlay_top_left((500, 300), (0, 0)) == (500, 300),
)
check(
    "clicking mid-card offsets the overlay by that same amount",
    reorder.overlay_top_left((500, 300), (200, 120)) == (300, 180),
)
check(
    "cursor moving by (dx, dy) moves the overlay by the same (dx, dy)",
    reorder.overlay_top_left((520, 340), (200, 120)) == (320, 220),
)
check(
    "negative press offsets (clicking above/left of the overlay origin) still work",
    reorder.overlay_top_left((100, 100), (-10, -10)) == (110, 110),
)

# ---------------------------------------------------------------------------
# Reorder mode must not change card geometry constants
# ---------------------------------------------------------------------------
section("reorder mode leaves card dimensions untouched")

from mediawave.channel_studio.channel_card import CARD_WIDTH, HERO_CARD_WIDTH

check("normal card width is unchanged by the reorder-mode pass", CARD_WIDTH == 430, CARD_WIDTH)
check(
    "hero card width still derives from the normal card width",
    HERO_CARD_WIDTH == CARD_WIDTH * 2 + 16,
    HERO_CARD_WIDTH,
)

import inspect

from mediawave.channel_studio import draggable_grid

reorder_mode_source = inspect.getsource(draggable_grid._Slot.set_reorder_mode)
check(
    "reorder-mode styling uses outline, not border, so it can't change sizeHint",
    "outline" in reorder_mode_source and "border:" not in reorder_mode_source,
    reorder_mode_source,
)
check(
    "reorder-mode styling is scoped to the slot's own object name, not a bare QFrame selector",
    "QFrame#reorderSlot" in reorder_mode_source and "QFrame {" not in reorder_mode_source,
    reorder_mode_source,
)

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
# companion_adapter: reading a raw settings dict into a snapshot
# ---------------------------------------------------------------------------
section("companion_adapter.read_companion_snapshot")

raw_settings = {
    "weatherstar_enabled": True,
    "weatherstar_channel_number": 4,
    "weatherstar_location": "Springfield, IL",
    "radiowave_enabled": False,
    "radiowave_channel_number": 2,
    "radiowave_folder": "/Music/RadioWave",
    "youtube_enabled": True,
    "youtube_channel_number": 7,
    "youtube_playlist_url": "https://youtube.com/playlist?list=abc",
}
snap = companion_adapter.read_companion_snapshot(raw_settings)
check("weatherstar enabled flag read correctly", snap["weatherstar"]["enabled"] is True)
check("weatherstar number read correctly", snap["weatherstar"]["number"] == 4, snap["weatherstar"]["number"])
check("weatherstar detail is the location", snap["weatherstar"]["detail"] == "Springfield, IL")
check("radiowave enabled flag read correctly", snap["radiowave"]["enabled"] is False)
check("youtube detail is the playlist url", snap["youtube"]["detail"] == raw_settings["youtube_playlist_url"])
check(
    "malformed input falls back to an all-disabled snapshot",
    all(not entry["enabled"] for entry in companion_adapter.read_companion_snapshot(None).values()),
)
check(
    "non-numeric channel number falls back to 1",
    companion_adapter.read_companion_snapshot({"weatherstar_channel_number": "not a number"})["weatherstar"]["number"] == 1,
)

# ---------------------------------------------------------------------------
# companion_adapter: building summaries (enabled only, hides disabled)
# ---------------------------------------------------------------------------
section("companion_adapter.companion_summaries")

summaries = companion_adapter.companion_summaries(snap)
summary_types = [item["channel_type"] for item in summaries]
check("only enabled companions appear, sorted by number (weatherstar=4, youtube=7)", summary_types == ["weatherstar", "youtube"], summary_types)
check(
    "disabled radiowave is hidden entirely, not just marked",
    "radiowave" not in summary_types,
)
check(
    "summaries are sorted by real channel number ascending",
    [item["number"] for item in summaries] == sorted(item["number"] for item in summaries),
)
weatherstar_summary = next(item for item in summaries if item["channel_type"] == "weatherstar")
check("companion channel id uses the stable special: form", weatherstar_summary["channel_id"] == "special:weatherstar")
check("companion info label is type-specific", weatherstar_summary["companion_info_label"] == "Location")
check("companion info value carries the configured detail", weatherstar_summary["companion_info_value"] == "Springfield, IL")

live_status_summaries = companion_adapter.companion_summaries(snap, status_by_type={"youtube": "42 videos loaded"})
youtube_summary = next(item for item in live_status_summaries if item["channel_type"] == "youtube")
check("live status overrides the configured detail when given", youtube_summary["companion_info_value"] == "42 videos loaded")

empty_summaries = companion_adapter.companion_summaries(companion_adapter.empty_snapshot())
check("an all-disabled snapshot produces no summaries", empty_summaries == [])

unconfigured = companion_adapter.companion_summaries(
    companion_adapter.set_companion_enabled(companion_adapter.empty_snapshot(), "radiowave", True)
)
check(
    "an enabled-but-unconfigured companion still gets a calm fallback detail",
    unconfigured[0]["companion_info_value"] == "Not configured yet",
)

# ---------------------------------------------------------------------------
# companion_adapter: enabling/disabling one companion
# ---------------------------------------------------------------------------
section("companion_adapter.set_companion_enabled")

disabled_weatherstar = companion_adapter.set_companion_enabled(snap, "weatherstar", False)
check("target companion flipped off", disabled_weatherstar["weatherstar"]["enabled"] is False)
check("other companions untouched", disabled_weatherstar["youtube"]["enabled"] is True)
check("original snapshot is not mutated", snap["weatherstar"]["enabled"] is True)
check(
    "unknown companion type is a safe no-op",
    companion_adapter.set_companion_enabled(snap, "not-a-real-type", True) == dict(snap),
)

# ---------------------------------------------------------------------------
# companion_adapter: resequencing real channel numbers among companions
# ---------------------------------------------------------------------------
section("companion_adapter.resequence_companion_numbers")

three_enabled = companion_adapter.read_companion_snapshot(
    {
        "weatherstar_enabled": True,
        "weatherstar_channel_number": 1,
        "radiowave_enabled": True,
        "radiowave_channel_number": 2,
        "youtube_enabled": True,
        "youtube_channel_number": 3,
    }
)
moved = companion_adapter.resequence_companion_numbers(three_enabled, ["radiowave", "youtube", "weatherstar"])
check(
    "moving radiowave first gives it the smallest pooled number",
    moved["radiowave"]["number"] == 1,
    moved["radiowave"]["number"],
)
check("youtube takes the middle pooled number", moved["youtube"]["number"] == 2, moved["youtube"]["number"])
check("weatherstar takes the last pooled number", moved["weatherstar"]["number"] == 3, moved["weatherstar"]["number"])
check(
    "the example from the spec: radiowave 1 -> 4 when reordered past two channels 2 and 3",
    companion_adapter.resequence_companion_numbers(
        companion_adapter.read_companion_snapshot(
            {
                "radiowave_enabled": True,
                "radiowave_channel_number": 1,
                "weatherstar_enabled": True,
                "weatherstar_channel_number": 2,
                "youtube_enabled": True,
                "youtube_channel_number": 4,
            }
        ),
        ["weatherstar", "youtube", "radiowave"],
    )["radiowave"]["number"]
    == 4,
)

only_one_enabled = companion_adapter.set_companion_enabled(companion_adapter.empty_snapshot(), "radiowave", True)
check(
    "a single enabled companion is a safe no-op (nothing to redistribute)",
    companion_adapter.resequence_companion_numbers(only_one_enabled, ["radiowave"]) == only_one_enabled,
)
check(
    "disabled companions are never touched by resequencing",
    companion_adapter.resequence_companion_numbers(three_enabled, ["radiowave"])["weatherstar"]["number"] == 1,
)
local_untouched_snapshot = dict(three_enabled)
resequenced = companion_adapter.resequence_companion_numbers(local_untouched_snapshot, ["youtube", "weatherstar", "radiowave"])
check(
    "resequencing never adds keys beyond the three known companion types",
    set(resequenced.keys()) == set(companion_adapter.COMPANION_TYPES),
)

# ---------------------------------------------------------------------------
# channel_actions: a lightweight fake dialog, no QApplication required.
# Only duck-types the handful of attributes channel_actions.py touches
# (isChecked/setChecked, value/setValue, text) -- not a real widget.
# ---------------------------------------------------------------------------
section("channel_actions: companion snapshot <-> fake dialog widgets")


class _FakeCheckBox:
    def __init__(self, checked=False):
        self._checked = checked

    def isChecked(self):
        return self._checked

    def setChecked(self, value):
        self._checked = bool(value)


class _FakeSpin:
    def __init__(self, value=1):
        self._value = value

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = int(value)


class _FakeLineEdit:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text


class _FakeDialog:
    def __init__(self):
        self.weatherstar_enabled = _FakeCheckBox(True)
        self.weatherstar_channel_input = _FakeSpin(1)
        self.weatherstar_location_input = _FakeLineEdit("Springfield, IL")
        self.radiowave_enabled = _FakeCheckBox(True)
        self.radiowave_channel_input = _FakeSpin(2)
        self.radiowave_input = _FakeLineEdit("/Music/RadioWave")
        self.youtube_enabled = _FakeCheckBox(False)
        self.youtube_channel_input = _FakeSpin(3)
        self.youtube_playlist_input = _FakeLineEdit("")
        self.catalog_rows = [
            {"id": "media:/fake/a", "enabled": _FakeCheckBox(True)},
            {"id": "media:/fake/b", "enabled": _FakeCheckBox(False)},
        ]
        self.channel_commercial_overrides = {}
        self._studio_channels_by_id = {}
        self.commercials_settings = {"enabled": True, "root_folder": "/fake/commercials", "mode": "between_episodes"}
        self._parent = None

    def parent(self):
        return self._parent


fake_dialog = _FakeDialog()
fake_snapshot = channel_actions.companion_snapshot_from_dialog(fake_dialog)
check("weatherstar enabled read from the fake checkbox", fake_snapshot["weatherstar"]["enabled"] is True)
check("radiowave detail read from the fake line edit", fake_snapshot["radiowave"]["detail"] == "/Music/RadioWave")
check("youtube disabled read from the fake checkbox", fake_snapshot["youtube"]["enabled"] is False)

check("enabling a companion flips the real widget", channel_actions.set_companion_enabled_on_dialog(fake_dialog, "youtube", True) is True)
check("the widget itself is now checked", fake_dialog.youtube_enabled.isChecked() is True)
check("disabling a companion flips it back off", channel_actions.set_companion_enabled_on_dialog(fake_dialog, "youtube", False) is True)
check("unknown companion type on set_companion_enabled_on_dialog is a safe no-op", channel_actions.set_companion_enabled_on_dialog(fake_dialog, "bogus", True) is False)

resequenced = channel_actions.resequence_companions_on_dialog(fake_dialog, ["radiowave", "weatherstar"])
check("resequencing writes radiowave's new number onto the real spinbox", fake_dialog.radiowave_channel_input.value() == 1, fake_dialog.radiowave_channel_input.value())
check("resequencing writes weatherstar's new number onto the real spinbox", fake_dialog.weatherstar_channel_input.value() == 2, fake_dialog.weatherstar_channel_input.value())

# ---------------------------------------------------------------------------
# channel_actions: local folder channel enable via the My Catalog rows
# ---------------------------------------------------------------------------
section("channel_actions: local channel enable/disable")

check("local channel enabled state reads from its My Catalog row", channel_actions.local_channel_enabled_from_dialog(fake_dialog, "media:/fake/a") is True)
check("a disabled row reads as disabled", channel_actions.local_channel_enabled_from_dialog(fake_dialog, "media:/fake/b") is False)
check("an unknown channel id reads as None, not a crash", channel_actions.local_channel_enabled_from_dialog(fake_dialog, "media:/does/not/exist") is None)

check("disabling a local channel updates its real row", channel_actions.set_local_channel_enabled(fake_dialog, "media:/fake/a", False) is True)
check("the row's checkbox actually flipped", fake_dialog.catalog_rows[0]["enabled"].isChecked() is False)
check("setting an unknown channel id is a safe no-op that reports failure", channel_actions.set_local_channel_enabled(fake_dialog, "media:/nope", True) is False)

# ---------------------------------------------------------------------------
# channel_actions: per-channel commercial override mode
# ---------------------------------------------------------------------------
section("channel_actions: commercial override mode")

check("a channel with no override yet summarizes as Default", channel_actions.commercials_summary_label(fake_dialog, "Movies") == "Default")
check("mode defaults to inherit when unset", channel_actions.channel_commercial_override_mode(fake_dialog, "Movies") == "inherit")

channel_actions.set_channel_commercial_override_mode(fake_dialog, "Movies", "off")
check("setting the mode to off is reflected immediately", channel_actions.channel_commercial_override_mode(fake_dialog, "Movies") == "off")
check("an off override summarizes as Off", channel_actions.commercials_summary_label(fake_dialog, "Movies") == "Off")

channel_actions.set_channel_commercial_override_mode(fake_dialog, "Movies", "on")
check("an on override summarizes as Custom", channel_actions.commercials_summary_label(fake_dialog, "Movies") == "Custom")

fake_dialog.channel_commercial_overrides["MTV"] = {"enabled_mode": "inherit", "preferred_era": "80s"}
check("an inherit override with other fields customized still summarizes as Custom", channel_actions.commercials_summary_label(fake_dialog, "MTV") == "Custom")

check("an invalid mode is rejected rather than corrupting the override", (
    channel_actions.set_channel_commercial_override_mode(fake_dialog, "Movies", "not-a-real-mode"),
    channel_actions.channel_commercial_override_mode(fake_dialog, "Movies"),
)[1] == "on")

# ---------------------------------------------------------------------------
# channel_actions: live companion status from real channel objects
# ---------------------------------------------------------------------------
section("channel_actions: companion live status")


class _FakeRadioWaveChannel:
    empty_state = False
    shows = ["a", "b", "c"]


class _FakeEmptyRadioWaveChannel:
    empty_state = True
    empty_reason = "No readable music files were found."


class _FakeYouTubeChannel:
    entries = [{"placeholder": True}, {"id": "1"}, {"id": "2"}]


no_status_dialog = _FakeDialog()
check("no live channels yet means no status entries, not an error", channel_actions.companion_status_from_dialog(no_status_dialog) == {})

status_dialog = _FakeDialog()
status_dialog._studio_channels_by_id = {"special:radiowave": _FakeRadioWaveChannel()}
check("a loaded radiowave channel reports its track count", channel_actions.companion_status_from_dialog(status_dialog)["radiowave"] == "3 tracks loaded")

empty_status_dialog = _FakeDialog()
empty_status_dialog._studio_channels_by_id = {"special:radiowave": _FakeEmptyRadioWaveChannel()}
check("an empty-state radiowave channel reports its empty reason", channel_actions.companion_status_from_dialog(empty_status_dialog)["radiowave"] == "No readable music files were found.")

youtube_status_dialog = _FakeDialog()
youtube_status_dialog._studio_channels_by_id = {"special:youtube": _FakeYouTubeChannel()}
check("placeholder entries are excluded from the youtube video count", channel_actions.companion_status_from_dialog(youtube_status_dialog)["youtube"] == "2 videos loaded")

# ---------------------------------------------------------------------------
# channel_card.py: companion-aware card wiring (structural, no QApplication
# needed -- mirrors the existing inspect.getsource pattern used above for
# reorder-mode styling).
# ---------------------------------------------------------------------------
section("channel_card.py: companion card wiring")

from mediawave.channel_studio import channel_card

dashboard_source = inspect.getsource(channel_card.build_dashboard_channel_card)
check("dashboard card branches on is_companion for its status panel", "is_companion" in dashboard_source)
check("dashboard card threads on_toggle_enabled into the checkbox", "on_toggle=on_toggle_enabled" in dashboard_source)
check("dashboard card offers a real Disable path for companions", "confirm_disable_companion_channel" in dashboard_source)

hero_source = inspect.getsource(channel_card.build_hero_channel_card)
check("hero card also branches on is_companion", "is_companion" in hero_source)
check("hero card also threads on_toggle_enabled into the checkbox", "on_toggle=on_toggle_enabled" in hero_source)

checkbox_source = inspect.getsource(channel_card._build_enabled_checkbox)
check("the enabled checkbox only connects toggled when a real handler is given", "toggled.connect(on_toggle)" in checkbox_source)

# ---------------------------------------------------------------------------
# setup_sections: companion-type detection used to branch Setup's sections
# ---------------------------------------------------------------------------
section("setup_sections._companion_type")

from mediawave.channel_studio import setup_sections

radiowave_summary = ChannelStudioSummary(channel_id="special:radiowave", name="RadioWaveTV", number=1, channel_type="radiowave")
check(
    "a companion summary's type is read straight off the summary",
    setup_sections._companion_type({"id": "special:radiowave"}, radiowave_summary) == "radiowave",
)

media_summary = ChannelStudioSummary(channel_id="media:/x", name="Movies", number=1, channel_type="media")
check(
    "a media summary is not a companion type",
    setup_sections._companion_type({"id": "media:/x"}, media_summary) is None,
)

check(
    "with no summary at all, a special: id still resolves to its companion type",
    setup_sections._companion_type({"id": "special:youtube"}, None) == "youtube",
)
check(
    "with no summary and a non-special id, there's no companion type",
    setup_sections._companion_type({"id": "media:/y"}, None) is None,
)
check(
    "a missing id entirely is handled without raising",
    setup_sections._companion_type({}, None) is None,
)

# ---------------------------------------------------------------------------
# channel_studio_pages.py: local channels are excluded from the companion
# pipeline by companion type, not by keeping only channel_type == "media"
# -- a regression caught manually: a local channel can legitimately be
# channel_type "missing" (e.g. before self.channels is populated yet this
# session, current_catalog_channel_infos falls back to building entries
# from catalog_channel_settings alone) and must not be silently dropped.
# ---------------------------------------------------------------------------
section("channel_studio_pages.py: local-channel filter excludes by companion type")

from mediawave.channel_studio import channel_studio_pages

build_content_source = inspect.getsource(channel_studio_pages.build_channel_studio_content)
check(
    "local_infos filters out companion types, not everything that isn't 'media'",
    'not in companion_adapter.COMPANION_TYPES' in build_content_source,
    build_content_source,
)
check(
    "the old too-aggressive == \"media\" filter is gone",
    '== "media"]' not in build_content_source,
)

# ---------------------------------------------------------------------------
# "Add Channel Logo" routing -- regression caught manually: it used to
# reuse the OLD five-tab mock dialog's Identity-tab index (3), which in
# the new ChannelSetupDialog's section order (Overview, Logo,
# Commercials, Programming, Advanced) lands on Programming instead of Logo.
# ---------------------------------------------------------------------------
section("channel_studio_pages.py: Add Channel Logo opens the Logo section")

from mediawave.channel_studio import channel_setup

check(
    "_LOGO_TAB_INDEX matches ChannelSetupDialog's own Logo section position",
    channel_studio_pages._LOGO_TAB_INDEX == channel_setup._SECTION_TITLES.index("Logo"),
    (channel_studio_pages._LOGO_TAB_INDEX, channel_setup._SECTION_TITLES),
)

# ---------------------------------------------------------------------------
# channel_actions: Commercials Setup v2 -- card status, library status,
# timed-breaks label, and channel override summary.
# ---------------------------------------------------------------------------
section("channel_actions: commercials v2 status helpers")

commercials_dialog = _FakeDialog()
check("no override yet -> card status is shared commercials", channel_actions.card_commercials_status(commercials_dialog, "Movies") == "shared commercials")

channel_actions.set_channel_commercial_override_mode(commercials_dialog, "Movies", "off")
check("off override -> card status is commercials off", channel_actions.card_commercials_status(commercials_dialog, "Movies") == "commercials off")

channel_actions.set_channel_commercial_override_mode(commercials_dialog, "Movies", "on")
check("on override -> card status is custom commercials", channel_actions.card_commercials_status(commercials_dialog, "Movies") == "custom commercials")

check("library status shows a live count when the main app has one loaded", (
    lambda d: (
        setattr(d, "_parent", type("FakeApp", (), {"commercial_library": [1, 2, 3]})()),
        channel_actions.commercial_library_status(d),
    )[1]
)(_FakeDialog()) == "Shared library: 3 clips")

check("library status falls back to calm text with no folder configured", (
    lambda d: (
        setattr(d, "commercials_settings", {"enabled": True, "root_folder": "", "mode": "between_episodes"}),
        channel_actions.commercial_library_status(d),
    )[1]
)(_FakeDialog()) == "Shared library: no folder configured yet")

check("library status reports commercials off when the shared library itself is disabled", (
    lambda d: (
        setattr(d, "commercials_settings", {"enabled": False, "root_folder": "/x", "mode": "between_episodes"}),
        channel_actions.commercial_library_status(d),
    )[1]
)(_FakeDialog()) == "Shared library: commercials are off")

timed_dialog = _FakeDialog()
timed_dialog.commercials_settings = {"enabled": True, "root_folder": "/x", "mode": "timed_midroll"}
check("global mode timed_midroll -> timed breaks On for a channel with no override", channel_actions.channel_timed_breaks_label(timed_dialog, "Movies") == "On")

between_dialog = _FakeDialog()
between_dialog.commercials_settings = {"enabled": True, "root_folder": "/x", "mode": "between_episodes"}
check("global mode between_episodes -> timed breaks Off for a channel with no override", channel_actions.channel_timed_breaks_label(between_dialog, "Movies") == "Off")

override_mode_dialog = _FakeDialog()
override_mode_dialog.commercials_settings = {"enabled": True, "root_folder": "/x", "mode": "between_episodes"}
override_mode_dialog.channel_commercial_overrides = {"Movies": {"enabled_mode": "on", "mode": "timed_midroll"}}
check("a Custom override's own mode wins over the shared global mode", channel_actions.channel_timed_breaks_label(override_mode_dialog, "Movies") == "On")

check("channel_override_summary reports None with no override", channel_actions.channel_override_summary(_FakeDialog(), "Movies") == "None")

off_override_dialog = _FakeDialog()
off_override_dialog.channel_commercial_overrides = {"Movies": {"enabled_mode": "off"}}
check("channel_override_summary reports the off state plainly", channel_actions.channel_override_summary(off_override_dialog, "Movies") == "Commercials off")

custom_override_dialog = _FakeDialog()
custom_override_dialog.channel_commercial_overrides = {"Movies": {"enabled_mode": "on"}}
check("channel_override_summary reports the on/custom state plainly", channel_actions.channel_override_summary(custom_override_dialog, "Movies") == "Custom commercial settings")

inherit_with_extras_dialog = _FakeDialog()
inherit_with_extras_dialog.channel_commercial_overrides = {"Movies": {"enabled_mode": "inherit", "preferred_era": "80s"}}
check("an inherit override that still customizes a field reports Custom preferences", channel_actions.channel_override_summary(inherit_with_extras_dialog, "Movies") == "Custom preferences")

# ---------------------------------------------------------------------------
# setup_sections.py: NetTV gets the real commercial control mechanism,
# WeatherStar/RadioWaveTV stay informational-only -- confirmed via source
# inspection (the actual write path is already covered above/in
# channel_actions, this checks the section builder's own branching).
# ---------------------------------------------------------------------------
section("setup_sections.py: companion commercial support is type-specific")

commercials_section_source = inspect.getsource(setup_sections.build_commercials_section)
check(
    "only weatherstar/radiowave are treated as commercials-not-applicable",
    'companion_type in ("weatherstar", "radiowave")' in commercials_section_source,
    commercials_section_source,
)
check(
    "NetTV (youtube) gets its own copy, not the generic local-channel copy",
    "_NETTV_COMMERCIALS_MODE_COPY" in commercials_section_source and "is_nettv" in commercials_section_source,
)
check(
    "the three choice buttons are wired to the same real override functions NetTV and local channels share",
    "set_channel_commercial_override_mode" in commercials_section_source
    and "open_commercial_overrides_for_channel" in commercials_section_source,
)

overview_section_source = inspect.getsource(setup_sections.build_overview_section)
check(
    "Overview's Commercials preview also treats NetTV as supported, not just local channels",
    'companion_type == "youtube"' in overview_section_source,
    overview_section_source,
)

# ---------------------------------------------------------------------------
# channel_card.py: the new commercials_status line/row is optional and
# additive -- structural checks matching the existing inspect.getsource pattern.
# ---------------------------------------------------------------------------
section("channel_card.py: commercials_status wiring")

dashboard_source_v2 = inspect.getsource(channel_card.build_dashboard_channel_card)
check("dashboard card accepts an optional commercials_status param", "commercials_status=None" in dashboard_source_v2)
check("dashboard card only adds the extra line when a status was actually given", "if commercials_status:" in dashboard_source_v2)

info_rows_source = inspect.getsource(channel_card._channel_info_rows)
check("the Commercials row prefers the live status over the static summary label", "commercials_status or summary.commercials_label" in info_rows_source)

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

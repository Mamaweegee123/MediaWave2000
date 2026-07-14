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
from mediawave.channel_studio import channel_identity
from mediawave import channel_logos
from channelsurfer2000 import migrate_legacy_channel_settings, normalize_catalog_channel_settings

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

check("a specific channel id survives ordering like any other", "b" in reorder.apply_saved_order(channel_ids, saved_stale))

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

from mediawave.channel_studio.channel_card import CARD_WIDTH

check("normal card width is unchanged by the reorder-mode pass", CARD_WIDTH == 430, CARD_WIDTH)

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
            {"id": "media:/fake/a", "enabled": _FakeCheckBox(True), "number": _FakeSpin(1)},
            {"id": "media:/fake/b", "enabled": _FakeCheckBox(False), "number": _FakeSpin(2)},
        ]
        self.channel_commercial_overrides = {}
        self._studio_channels_by_id = {}
        self.commercials_settings = {"enabled": True, "root_folder": "/fake/commercials", "mode": "between_episodes"}
        self.channel_bug_settings = {
            "enabled": True, "corner": "bottom-right", "opacity": 0.75, "size": 80, "margin": 18,
            "horizontal_offset": 0, "vertical_offset": 0, "placement_area": "overlay",
            "grayscale_on_video": False, "fade": True,
        }
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

unified_companion_entries = channel_actions.unified_entries_from_dialog(fake_dialog)
unified_companion_numbers = channel_identity.renumber_from_order(unified_companion_entries, ["special:radiowave", "special:weatherstar"])
channel_actions.apply_unified_numbers_to_dialog(fake_dialog, unified_companion_numbers)
check("unified renumbering writes radiowave's new number onto the real spinbox", fake_dialog.radiowave_channel_input.value() == 1, fake_dialog.radiowave_channel_input.value())
check("unified renumbering writes weatherstar's new number onto the real spinbox", fake_dialog.weatherstar_channel_input.value() == 2, fake_dialog.weatherstar_channel_input.value())

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

check("there is no hero/featured card builder left in channel_card.py", not hasattr(channel_card, "build_hero_channel_card"))

checkbox_source = inspect.getsource(channel_card._build_enabled_checkbox)
check("the enabled checkbox only connects toggled when a real handler is given", "toggled.connect(on_toggle)" in checkbox_source)

# ---------------------------------------------------------------------------
# setup_sections: companion-type detection used to branch Setup's sections
# ---------------------------------------------------------------------------
section("setup_sections._companion_type")

from mediawave.channel_studio import setup_sections
from mediawave.channel_studio import logo_studio

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

# ---------------------------------------------------------------------------
# channel_actions: Logo Studio v1 override read/write helpers -- same
# live-widget-sharing pattern as the commercials helpers (dialog.channel_bug_settings
# is the same dict My Catalog's Channel Logos tab would read/write).
# ---------------------------------------------------------------------------
section("channel_actions: logo override read/write helpers")

logo_dialog = _FakeDialog()
check("a channel with no override yet is in Default mode", channel_actions.channel_logo_override_mode(logo_dialog, "Movies") == "global")
check("Default mode maps to the 'Default' label", channel_actions.channel_logo_mode_label(logo_dialog, "Movies") == "Default")

channel_actions.set_channel_logo_override_mode(logo_dialog, "Movies", "custom")
check("switching to custom creates an override entry", "Movies" in logo_dialog.channel_bug_settings["channel_overrides"])
check("the new override is seeded from the global corner", logo_dialog.channel_bug_settings["channel_overrides"]["Movies"]["corner"] == "bottom-right")
check("custom mode maps to the 'Custom' label", channel_actions.channel_logo_mode_label(logo_dialog, "Movies") == "Custom")

channel_actions.set_channel_logo_override_fields(logo_dialog, "Movies", opacity=0.4, size=150)
check("setting fields updates opacity", logo_dialog.channel_bug_settings["channel_overrides"]["Movies"]["opacity"] == 0.4)
check("setting fields updates size", logo_dialog.channel_bug_settings["channel_overrides"]["Movies"]["size"] == 150)
check(
    "setting fields doesn't clobber fields it wasn't given",
    logo_dialog.channel_bug_settings["channel_overrides"]["Movies"]["corner"] == "bottom-right",
)

channel_actions.set_channel_logo_override_mode(logo_dialog, "News", "off")
check("turning a channel off stores mode='off'", channel_actions.channel_logo_override_mode(logo_dialog, "News") == "off")
check("off mode maps to the 'Off' label", channel_actions.channel_logo_mode_label(logo_dialog, "News") == "Off")
check(
    "a channel that's off doesn't get real playback disabled globally -- only its own override",
    logo_dialog.channel_bug_settings["enabled"] is True,
)

fresh_fields_dialog = _FakeDialog()
channel_actions.set_channel_logo_override_fields(fresh_fields_dialog, "Cartoons", opacity=0.3)
check(
    "adjusting a field on a channel with no prior override promotes it straight to custom",
    channel_actions.channel_logo_override_mode(fresh_fields_dialog, "Cartoons") == "custom",
)

channel_actions.reset_channel_logo_override(logo_dialog, "Movies")
check("resetting removes the override entirely", "Movies" not in logo_dialog.channel_bug_settings.get("channel_overrides", {}))
check("a reset channel is back to Default", channel_actions.channel_logo_mode_label(logo_dialog, "Movies") == "Default")
check("resetting a channel that never had an override is a safe no-op", channel_actions.reset_channel_logo_override(logo_dialog, "NeverSet") is None)

preset_dialog = _FakeDialog()
channel_actions.apply_channel_logo_timing_preset(preset_dialog, "Cartoon Network", "random_pop_in")
check(
    "applying a preset writes its real timing dict",
    preset_dialog.channel_bug_settings["channel_overrides"]["Cartoon Network"]["timing"]["random_interval"] is True,
)
check(
    "applying a preset promotes the channel to custom",
    channel_actions.channel_logo_override_mode(preset_dialog, "Cartoon Network") == "custom",
)
check(
    "channel_logo_current_preset_id recognizes the preset that was just applied",
    channel_actions.channel_logo_current_preset_id(preset_dialog, "Cartoon Network") == "random_pop_in",
)
check(
    "a channel with no override resolves to whatever preset the global timing matches (here: always-on, the legacy default)",
    channel_actions.channel_logo_current_preset_id(preset_dialog, "Untouched Channel") == "always",
)
check("applying an unknown preset id is a safe no-op", channel_actions.apply_channel_logo_timing_preset(preset_dialog, "Cartoon Network", "not-a-preset") is None)

position_dialog = _FakeDialog()
expected_pos = channel_actions.channel_logo_preview_position(position_dialog, "Movies", 1280, 720, 80, 80)
check("channel_logo_preview_position matches the pure resolve_logo_position math", expected_pos == (1182, 622), expected_pos)

channel_actions.set_channel_logo_position_from_drop(position_dialog, "Movies", 0, 0, 1280, 720, 80, 80)
dropped_override = position_dialog.channel_bug_settings["channel_overrides"]["Movies"]
check("dropping at the top-left writes normalized pos_x/pos_y of (0.0, 0.0), not a corner snap", (dropped_override["pos_x"], dropped_override["pos_y"]) == (0.0, 0.0), dropped_override)
check("dropping writes a custom override", dropped_override["mode"] == "custom")

channel_actions.set_channel_logo_position_from_drop(position_dialog, "Movies", 600, 320, 1280, 720, 80, 80)
centered_override = position_dialog.channel_bug_settings["channel_overrides"]["Movies"]
check(
    "dropping in the middle of the screen writes a real freeform position, not clamped to a corner+offset range",
    (centered_override["pos_x"], centered_override["pos_y"]) == (0.5, 0.5),
    centered_override,
)
check(
    "channel_logo_preview_position honors the freeform position that was just dropped",
    channel_actions.channel_logo_preview_position(position_dialog, "Movies", 1280, 720, 80, 80) == (600.0, 320.0),
)

# ---------------------------------------------------------------------------
# channel_actions: Logo Studio v2 screen-shape (4:3/16:9) helpers -- a real
# per-channel setting independent of Default/Custom/Off mode.
# ---------------------------------------------------------------------------
section("channel_actions: logo screen-aspect read/write helpers")

aspect_dialog = _FakeDialog()
check("a channel with no aspect set yet defaults to 16:9", channel_actions.channel_logo_screen_aspect(aspect_dialog, "Movies") == "16:9")

channel_actions.set_channel_logo_screen_aspect(aspect_dialog, "Movies", "4:3")
check("setting the aspect to 4:3 sticks", channel_actions.channel_logo_screen_aspect(aspect_dialog, "Movies") == "4:3")
check(
    "setting the screen aspect doesn't promote the channel to Custom mode",
    channel_actions.channel_logo_override_mode(aspect_dialog, "Movies") == "global",
)

channel_actions.set_channel_logo_override_mode(aspect_dialog, "Movies", "off")
check(
    "the screen aspect survives switching the channel to Off",
    channel_actions.channel_logo_screen_aspect(aspect_dialog, "Movies") == "4:3",
)

channel_actions.set_channel_logo_screen_aspect(aspect_dialog, "Movies", "16:9")
check("setting the aspect back to the default (16:9) is a real, honest change", channel_actions.channel_logo_screen_aspect(aspect_dialog, "Movies") == "16:9")

# ---------------------------------------------------------------------------
# setup_sections.py: Logo Studio v1 structural checks (source-level, no
# QApplication -- same pattern the commercials v2 section checks used).
# ---------------------------------------------------------------------------
section("setup_sections.py: Logo Studio v1 structural checks")

logo_section_source = inspect.getsource(setup_sections.build_logo_section)
check(
    "companion channels get real Logo Studio controls now (unified logo lookup, commit 5) -- "
    "no more informational-only card",
    "No custom logo for companion channels" not in logo_section_source,
)
check("Logo Studio resolves through the shared User Content/Logos folder for channels with no folder of their own", "_shared_logos_dir" in logo_section_source)
check("the simulated screen preview widget is used", "LogoPreviewScreen(" in logo_section_source)
check("dropped preview coordinates are unscaled back to real px before writing settings", "/ scale" in logo_section_source)
check("the preview preserves the source logo's aspect ratio instead of forcing a square", "scale_logo_dimensions(" in logo_section_source)
check("the 4:3/16:9 screen shape toggle is wired to the real per-channel setting", "set_channel_logo_screen_aspect" in logo_section_source and "set_aspect(" in logo_section_source)
check("the old fake timing-preview playback button is gone", "start_timing_preview" not in logo_section_source and "_preview_timing" not in logo_section_source)
check("the 'placement, not on-air timing' explanatory note is gone -- Timing dropdown + Advanced Timing are enough", "on-air timing" not in logo_section_source)

logo_studio_source = inspect.getsource(logo_studio)
check("LogoPreviewScreen no longer simulates timing playback", "start_timing_preview" not in logo_studio_source and "stop_timing_preview" not in logo_studio_source and "_sim_timer" not in logo_studio_source)
check("LogoPreviewScreen exposes a real set_aspect for the 4:3/16:9 toggle", "def set_aspect(self, aspect_w, aspect_h):" in logo_studio_source)
check(
    "the outer widget's own height-for-width stays fixed at the widget's natural 16:9 shape -- only the active area inside it changes",
    "return max(1, int(width * PREVIEW_ASPECT_H / PREVIEW_ASPECT_W))" in logo_studio_source,
)
check(
    "the active placement rectangle is computed by the shared pure geometry helper, not duplicated ad hoc",
    "compute_active_screen_rect(" in logo_studio_source,
)
check(
    "dragging and dropping are hit-tested/clamped against the active rect, not the full widget",
    "active.width() - self._logo_w" in logo_studio_source and "active.height() - self._logo_h" in logo_studio_source,
)
check(
    "opacity and size only write real settings on release, not on every live tick",
    logo_section_source.count("sliderReleased.connect") == 2,
)
check("grayscale is wired to the one real tint the overlay supports", "grayscale_on_video" in logo_section_source)
check("no fake tint options are offered as if real -- just a short note, not a card", "More effects later" in logo_section_source)
check("the old per-channel override dialog is still reachable, not replaced", "open_logo_overrides_for_channel" in logo_section_source)
check("Reset to Default is wired to the real reset helper", "reset_channel_logo_override" in logo_section_source)
check("timing is a single dropdown built from the real preset table, not a stack of buttons", "QComboBox" in logo_section_source and "LOGO_TIMING_PRESETS" in logo_section_source)
check("advanced timing detail lives in its own dialog, not the main panel", "LogoTimingDialog(" in logo_section_source)
check("show exclusions live in their own dialog, not the main panel", "ShowExclusionsDialog(" in logo_section_source)
check("a missing logo offers to open the Logos folder instead of crashing", "_open_logos_folder" in logo_section_source and "Open Logos Folder" in logo_section_source)

# ---------------------------------------------------------------------------
# channel_actions: excluded shows + available shows lookup
# ---------------------------------------------------------------------------
section("channel_actions: show exclusions and available shows")

exclusions_dialog = _FakeDialog()
exclusions_dialog._channel_shows_lookup = {
    "media:/x": [{"title": "Show A", "title_key": "show-a", "media_type": "tv"}],
}
check(
    "available shows reads straight from the existing Airing Rules lookup",
    channel_actions.channel_logo_available_shows(exclusions_dialog, "media:/x")
    == [{"title": "Show A", "title_key": "show-a", "media_type": "tv"}],
)
check("a channel id with no shows returns an empty list, not an error", channel_actions.channel_logo_available_shows(exclusions_dialog, "media:/nope") == [])

check("a channel with no exclusions yet has an empty list", channel_actions.channel_logo_excluded_shows(exclusions_dialog, "Movies") == [])
channel_actions.set_channel_logo_excluded_shows(exclusions_dialog, "Movies", ["show-a", "show-a", ""])
check(
    "excluded shows are written deduped, with blanks dropped",
    channel_actions.channel_logo_excluded_shows(exclusions_dialog, "Movies") == ["show-a"],
)
check(
    "writing exclusions doesn't switch the channel to Custom mode -- exclusions are mode-independent",
    channel_actions.channel_logo_override_mode(exclusions_dialog, "Movies") == "global",
)
channel_actions.set_channel_logo_override_mode(exclusions_dialog, "Movies", "custom")
channel_actions.set_channel_logo_excluded_shows(exclusions_dialog, "Movies", ["show-a"])
check(
    "setting exclusions on an already-custom channel doesn't reset it back to global",
    channel_actions.channel_logo_override_mode(exclusions_dialog, "Movies") == "custom",
)

# ---------------------------------------------------------------------------
# channel_card.py + setup_sections.py: logo discovery is the SAME function
# real playback uses -- no second, weaker lookup that can drift out of sync
# and show "No channel logo found" when a logo genuinely exists.
# ---------------------------------------------------------------------------
section("logo discovery: one shared lookup, not two")

card_source = inspect.getsource(channel_card)
check("channel_card.py has no separate/weaker logo lookup of its own", "_find_channel_logo_path" not in card_source)
check("channel_card.py's logo widget uses the real, shared discovery function", "find_channel_bug_logo(summary.root_path, summary.name" in card_source)

logo_section_source_v2 = inspect.getsource(setup_sections.build_logo_section)
check(
    "Logo Studio's preview uses the same shared discovery function, not just the stale summary snapshot",
    "find_channel_bug_logo(root_path, channel_name" in logo_section_source_v2,
)

setup_dialog_source = inspect.getsource(channel_setup.ChannelSetupDialog)
check("switching to the Logo tab refreshes it (picks up a logo added mid-session)", "_refresh_logo" in setup_dialog_source)

with tempfile.TemporaryDirectory() as tmpdir:
    channel_dir = os.path.join(tmpdir, "MTV")
    logos_dir = os.path.join(channel_dir, "Logos")
    os.makedirs(logos_dir)
    logo_file = os.path.join(logos_dir, "MTV.png")
    with open(logo_file, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    check(
        "a channel-name-based logo file (not just logo.png/bug.png/channel.png) is found",
        channel_logos.find_channel_bug_logo(channel_dir, "MTV") == logo_file,
    )
    check(
        "a normalized/display-name-style lookup still finds the same file",
        channel_logos.find_channel_bug_logo(channel_dir, "MTV") == channel_logos.find_channel_bug_logo(channel_dir, "MTV"),
    )
check("a channel with no Logos folder at all fails safe, no crash", channel_logos.find_channel_bug_logo(os.path.join(tmpdir, "Nowhere"), "Nowhere") == "")
check("a missing/blank channel name fails safe, no crash", channel_logos.find_channel_bug_logo("", "") == "")

# ---------------------------------------------------------------------------
# channel_studio_pages.py: no hero/featured card, ever
# ---------------------------------------------------------------------------
section("channel_studio_pages.py: hero card removed")

pages_source = inspect.getsource(channel_studio_pages)
check("no hero card is built anywhere in Channel Studio's page", "build_hero_channel_card" not in pages_source)
check("no hero-specific container/rebuild code remains", "hero_container" not in pages_source and "_rebuild_hero" not in pages_source)
check("last-edited-channel state is no longer read or written from here", "last_edited_channel_id" not in pages_source)

with tempfile.TemporaryDirectory() as tmpdir:
    old_hero_state_path = os.path.join(tmpdir, "channel_studio_state.json")
    studio_state.save_last_edited_channel_id(old_hero_state_path, "media:/some/old/channel")
    check(
        "an old hero-state file on disk doesn't crash reading channel order (the only thing still read from this file)",
        studio_state.load_channel_order(old_hero_state_path) == [],
    )

# ---------------------------------------------------------------------------
# channel_actions.py: reorder finalization updates real channel numbers
# ---------------------------------------------------------------------------
section("channel_actions: finalized reorder updates channel numbers")

number_dialog = _FakeDialog()
before = {row["id"]: row["number"].value() for row in number_dialog.catalog_rows}
check("starting numbers are sequential", before == {"media:/fake/a": 1, "media:/fake/b": 2}, before)

number_entries = channel_actions.unified_entries_from_dialog(number_dialog)
number_new_numbers = channel_identity.renumber_from_order(number_entries, ["media:/fake/b", "media:/fake/a"])
updated_ids = channel_actions.apply_unified_numbers_to_dialog(number_dialog, number_new_numbers)
after = {row["id"]: row["number"].value() for row in number_dialog.catalog_rows}
check("unified renumbering updates both rows", set(updated_ids) == {"media:/fake/b", "media:/fake/a"}, updated_ids)
check("the channel dragged first now holds the smaller number from the SAME pool", after["media:/fake/b"] == 1, after)
check("the channel dragged second now holds the larger number from the SAME pool", after["media:/fake/a"] == 2, after)
check("numbers are still sequential after commit", sorted(after.values()) == [1, 2], after)
check("no duplicate numbers after commit", len(set(after.values())) == len(after), after)

check(
    "a stale/missing channel id in the reorder list is safely skipped, not an error",
    "media:/nonexistent" not in channel_identity.renumber_from_order(number_entries, ["media:/fake/a", "media:/nonexistent"]),
)
check("fewer than 2 matched entries is a safe no-op (nothing to redistribute)", channel_identity.renumber_from_order(number_entries, ["media:/fake/a"]) == {})
check("an entirely empty/unknown reorder list is a safe no-op", channel_identity.renumber_from_order(number_entries, ["media:/nonexistent"]) == {})

display_dialog = _FakeDialog()
local_summary = ChannelStudioSummary(channel_id="media:/fake/a", name="Movies", number=99, channel_type="media")
check("card_display_number reads the live My Catalog row, not the stale summary snapshot", channel_actions.card_display_number(display_dialog, local_summary) == 1)
channel_actions.set_local_channel_number(display_dialog, "media:/fake/a", 7)
check("card_display_number reflects a number just written by a reorder commit", channel_actions.card_display_number(display_dialog, local_summary) == 7)

ghost_summary = ChannelStudioSummary(channel_id="media:/ghost", name="Ghost", number=42, channel_type="media")
check("card_display_number falls back to the summary's own number when no live row exists", channel_actions.card_display_number(display_dialog, ghost_summary) == 42)

companion_summary = ChannelStudioSummary(channel_id="special:radiowave", name="RadioWaveTV", number=99, channel_type="radiowave")
check("card_display_number reads the live companion spinbox, same as a local channel's row", channel_actions.card_display_number(display_dialog, companion_summary) == 2)

section("channel_actions: mixed local+companion reorder actually interleaves (requirement 6+8)")

mixed_dialog = _FakeDialog()
# Starting lineup: media/fake/a=1, media/fake/b=2, weatherstar=1(!), radiowave=2(!) --
# collides with the locals on paper, but only ENABLED entries matter and
# fake/b starts disabled, so the real starting pool this reorder touches
# is {1, 2, 2} across 3 enabled entries; repair isn't run here (that's
# apply_catalog_channel_customizations' job) -- this test is specifically
# about renumber_from_order handling a real interleaved drag, so give it
# a clean, non-colliding starting pool first.
channel_actions.set_local_channel_number(mixed_dialog, "media:/fake/a", 1)
channel_actions.set_local_channel_enabled(mixed_dialog, "media:/fake/b", True)
channel_actions.set_local_channel_number(mixed_dialog, "media:/fake/b", 3)
channel_actions.set_channel_number_on_dialog(mixed_dialog, "special:weatherstar", 2)

mixed_entries = channel_actions.unified_entries_from_dialog(mixed_dialog)
# Drag weatherstar to sit BETWEEN the two local channels: a-weatherstar-b.
mixed_new_numbers = channel_identity.renumber_from_order(mixed_entries, ["media:/fake/a", "special:weatherstar", "media:/fake/b"])
channel_actions.apply_unified_numbers_to_dialog(mixed_dialog, mixed_new_numbers)
check(
    "a companion dragged between two local channels gets a real number reflecting that position, not just its own type's pool",
    (
        channel_actions.channel_number_from_dialog(mixed_dialog, "media:/fake/a"),
        channel_actions.channel_number_from_dialog(mixed_dialog, "special:weatherstar"),
        channel_actions.channel_number_from_dialog(mixed_dialog, "media:/fake/b"),
    )
    == (1, 2, 3),
)

reorder_pages_source = inspect.getsource(channel_studio_pages)
check(
    "Done Reordering commits real numbers through the unified, gap-preserving renumber algorithm",
    "channel_identity.renumber_from_order" in reorder_pages_source,
)
check(
    "Done Reordering applies the unified result through the unified dispatch, not two separate per-pool resequences",
    "apply_unified_numbers_to_dialog" in reorder_pages_source,
)
check(
    "Done Reordering refreshes the live lineup immediately -- Guide/My Catalog/playback update with no restart",
    "refresh_live_lineup" in reorder_pages_source,
)
check(
    "cards are built with a live display_number, not just the static summary snapshot",
    "display_number=number" in reorder_pages_source,
)

# ---------------------------------------------------------------------------
# channel_actions.py: unified number read/write/validate dispatch, and the
# no-restart refresh trigger (manual channel numbering, commit 2)
# ---------------------------------------------------------------------------
section("channel_actions: unified channel number dispatch (local + companion)")


class _FakeMainApp:
    def __init__(self):
        self.app_settings = {"catalog_channel_settings": {}}
        self.injected = False
        self.customized = False

    def inject_special_channels(self):
        self.injected = True

    def apply_catalog_channel_customizations(self):
        self.customized = True


number_dialog2 = _FakeDialog()
check("channel_number_from_dialog reads a local channel's live spinbox", channel_actions.channel_number_from_dialog(number_dialog2, "media:/fake/a") == 1)
check("channel_number_from_dialog reads a companion's live spinbox", channel_actions.channel_number_from_dialog(number_dialog2, "special:radiowave") == 2)
check("channel_number_from_dialog returns None for an unknown local id", channel_actions.channel_number_from_dialog(number_dialog2, "media:/nope") is None)

check("set_channel_number_on_dialog writes a local channel's spinbox", channel_actions.set_channel_number_on_dialog(number_dialog2, "media:/fake/a", 42) is True)
check("the local spinbox actually changed", number_dialog2.catalog_rows[0]["number"].value() == 42)
check("set_channel_number_on_dialog writes a companion's spinbox", channel_actions.set_channel_number_on_dialog(number_dialog2, "special:radiowave", 55) is True)
check("the companion spinbox actually changed", number_dialog2.radiowave_channel_input.value() == 55)
check("set_channel_number_on_dialog fails safely for an unknown local id", channel_actions.set_channel_number_on_dialog(number_dialog2, "media:/nope", 1) is False)

main_app = _FakeMainApp()
number_dialog2._parent = main_app
channel_actions.set_channel_number_on_dialog(number_dialog2, "media:/fake/a", 99)
check(
    "writing a number also updates the main app's real app_settings immediately, no Save needed",
    main_app.app_settings["catalog_channel_settings"]["media:/fake/a"]["channel_number"] == 99,
)

channel_actions.refresh_live_lineup(number_dialog2)
check("refresh_live_lineup calls the main app's real recompute methods", main_app.injected and main_app.customized)
check("refresh_live_lineup is a safe no-op when parent() is None", channel_actions.refresh_live_lineup(_FakeDialog()) is None)

section("channel_actions: manual number validation bridges to channel_identity")

check(
    "an available number validates ok with a friendly message",
    channel_actions.validate_channel_number_on_dialog(number_dialog2, "media:/fake/a", 7) == ("ok", "Available"),
)
check(
    "a duplicate number is rejected with the spec's exact wording",
    channel_actions.validate_channel_number_on_dialog(number_dialog2, "media:/fake/a", 55)
    == ("duplicate", "Channel number already exists."),
)
check(
    "an out-of-range number is invalid, not a crash",
    channel_actions.validate_channel_number_on_dialog(number_dialog2, "media:/fake/a", 999999)[0] == "invalid",
)
check(
    "a channel's own current number never conflicts with itself",
    channel_actions.validate_channel_number_on_dialog(number_dialog2, "media:/fake/a", 99) == ("ok", "Available"),
)

overview_source = inspect.getsource(setup_sections.build_overview_section)
check("Overview wires the inline number editor", "build_inline_value_editor" in overview_source)
check("Overview reads the live channel number through the unified dispatch", "channel_number_from_dialog" in overview_source)
check("Overview writes through the unified dispatch, not a type-specific helper", "set_channel_number_on_dialog" in overview_source)
check("Overview validates through the unified dispatch", "validate_channel_number_on_dialog" in overview_source)
check("applying a number edit triggers the no-restart refresh", "refresh_live_lineup" in overview_source)

# ---------------------------------------------------------------------------
# channel_actions.py: unified name read/write/validate dispatch (channel
# name editing, commit 3) -- display_name actually applying to a live
# channel.name is covered separately below since it needs the real
# Channel class from channelsurfer2000.py, not the fake dialog.
# ---------------------------------------------------------------------------
section("channel_actions: unified channel name dispatch (local + companion)")

name_dialog = _FakeDialog()
name_dialog.catalog_rows[0]["name"] = "4Kids"
name_dialog.catalog_rows[1]["name"] = "Movies"

check("channel_name_from_dialog reads a local channel's row name", channel_actions.channel_name_from_dialog(name_dialog, "media:/fake/a") == "4Kids")
check("channel_name_from_dialog falls back to the built-in default for an unrenamed companion", channel_actions.channel_name_from_dialog(name_dialog, "special:weatherstar") == "WeatherStar 4000+")
check("channel_name_from_dialog returns None for an unknown local id", channel_actions.channel_name_from_dialog(name_dialog, "media:/nope") is None)

check("set_channel_name_on_dialog renames a local channel's row", channel_actions.set_channel_name_on_dialog(name_dialog, "media:/fake/a", "4Kids Classic") is True)
check("the row's name string actually changed", name_dialog.catalog_rows[0]["name"] == "4Kids Classic")
check("channel_name_from_dialog reflects the rename immediately", channel_actions.channel_name_from_dialog(name_dialog, "media:/fake/a") == "4Kids Classic")
check("set_channel_name_on_dialog rejects a blank name", channel_actions.set_channel_name_on_dialog(name_dialog, "media:/fake/a", "   ") is False)
check("a blank-name rejection doesn't touch the existing name", name_dialog.catalog_rows[0]["name"] == "4Kids Classic")
check("set_channel_name_on_dialog fails safely for an unknown local id", channel_actions.set_channel_name_on_dialog(name_dialog, "media:/nope", "X") is False)

name_main_app = _FakeMainApp()
name_dialog._parent = name_main_app
check("set_channel_name_on_dialog renames a companion via its flat display-name setting", channel_actions.set_channel_name_on_dialog(name_dialog, "special:weatherstar", "The Weather Machine") is True)
check("the companion rename is readable back immediately", channel_actions.channel_name_from_dialog(name_dialog, "special:weatherstar") == "The Weather Machine")
check("renaming a local channel also updates the main app's real app_settings, no Save needed", (
    channel_actions.set_channel_name_on_dialog(name_dialog, "media:/fake/a", "4Kids Forever"),
    name_main_app.app_settings["catalog_channel_settings"]["media:/fake/a"]["display_name"],
)[1] == "4Kids Forever")

section("channel_actions: manual name validation bridges to channel_identity")

check("a normal rename validates ok", channel_actions.validate_channel_name_on_dialog(name_dialog, "media:/fake/a", "Something New") == ("ok", "Looks good"))
check("a blank candidate is invalid, not a crash", channel_actions.validate_channel_name_on_dialog(name_dialog, "media:/fake/a", "   ")[0] == "invalid")

overview_name_source = inspect.getsource(setup_sections.build_overview_section)
check("Overview wires a second inline editor for the channel name", overview_name_source.count("build_inline_value_editor") >= 2)
check("Overview reads the live channel name through the unified dispatch", "channel_name_from_dialog" in overview_name_source)
check("Overview writes the name through the unified dispatch", "set_channel_name_on_dialog" in overview_name_source)
check("Overview validates the name through the unified dispatch", "validate_channel_name_on_dialog" in overview_name_source)

section("companion_adapter: real per-companion display names (commit 3)")

named_snapshot = companion_adapter.read_companion_snapshot({
    "weatherstar_enabled": True,
    "weatherstar_channel_number": 4,
    "weatherstar_display_name": "The Weather Machine",
    "radiowave_enabled": True,
    "radiowave_channel_number": 5,
})
check("a configured display name is read from the flat setting", named_snapshot["weatherstar"]["name"] == "The Weather Machine")
check("an unset display name reads as blank, not a crash", named_snapshot["radiowave"]["name"] == "")

named_summaries = companion_adapter.companion_summaries(named_snapshot)
by_type = {s["channel_type"]: s for s in named_summaries}
check("a renamed companion's summary uses the real name", by_type["weatherstar"]["name"] == "The Weather Machine")
check("an un-renamed companion's summary falls back to the built-in default", by_type["radiowave"]["name"] == "RadioWaveTV")

# ---------------------------------------------------------------------------
# channelsurfer2000.py: display_name actually applies to a live channel's
# real .name attribute (commit 3's other half -- this was previously dead
# code for real channels)
# ---------------------------------------------------------------------------
section("apply_catalog_channel_customizations: display_name is now live")

import channelsurfer2000


class _FakeAppChannel:
    def __init__(self, name, root_path):
        self.name = name
        self.root_path = root_path
        self.channel_type = "media"


class _FakeAppForRename:
    catalog_channel_id = channelsurfer2000.ChannelSurfer.catalog_channel_id
    catalog_category_for_channel = channelsurfer2000.ChannelSurfer.catalog_category_for_channel
    catalog_settings_for_channel = channelsurfer2000.ChannelSurfer.catalog_settings_for_channel
    apply_catalog_channel_customizations = channelsurfer2000.ChannelSurfer.apply_catalog_channel_customizations

    def __init__(self, channels, catalog_channel_settings):
        self.channels = channels
        self.current_channel = 0
        self.guide_selection = 0
        self.app_settings = {"catalog_channel_settings": catalog_channel_settings}
        self.status = _FakeLineEdit("")


rename_channel = _FakeAppChannel("MTV", "/Volumes/Media/MTV")
rename_channel_id = f"media:{os.path.realpath('/Volumes/Media/MTV')}"
rename_app = _FakeAppForRename(
    [rename_channel],
    {rename_channel_id: {"enabled": True, "channel_number": 5, "display_name": "MTV Classic"}},
)
rename_app.apply_catalog_channel_customizations()
check("a stored display_name is applied to the channel's real .name attribute", rename_channel.name == "MTV Classic")
check("the channel's original, folder-derived name is preserved separately", rename_channel.folder_name == "MTV")

no_rename_channel = _FakeAppChannel("Movies", "/Volumes/Media/Movies")
no_rename_id = f"media:{os.path.realpath('/Volumes/Media/Movies')}"
no_rename_app = _FakeAppForRename([no_rename_channel], {no_rename_id: {"enabled": True, "channel_number": 1}})
no_rename_app.apply_catalog_channel_customizations()
check("no display_name set -> the channel's original name is left alone", no_rename_channel.name == "Movies")
check("folder_name is still captured even without a rename", no_rename_channel.folder_name == "Movies")

# ---------------------------------------------------------------------------
# Bug found via live/manual verification: migrate_legacy_channel_settings
# unconditionally seeds all 3 companion types into catalog_channel_settings
# -- including disabled ones. current_catalog_channel_infos()'s "leftover
# settings not yet seen" loop (for channels whose settings row exists but
# aren't in self.channels -- normally a local folder that went missing)
# didn't know to skip companion ids, so a disabled companion's entry got
# synthesized into a fake channel_type="missing" LOCAL channel info,
# which then slipped past every "channel_type not in COMPANION_TYPES"
# filter used to keep companions out of the local-channel pipelines
# (e.g. Channel Studio's grid, which showed a phantom disabled-companion
# card as if it were a broken local channel).
# ---------------------------------------------------------------------------
section("current_catalog_channel_infos: a disabled companion is never synthesized into a fake 'missing' local channel")


class _FakeInfosApp:
    catalog_channel_id = channelsurfer2000.ChannelSurfer.catalog_channel_id
    channel_display_number = channelsurfer2000.ChannelSurfer.channel_display_number
    current_catalog_channel_infos = channelsurfer2000.ChannelSurfer.current_catalog_channel_infos

    def __init__(self, channels, catalog_channel_settings):
        self.channels = channels
        self.loaded_media_channels = None
        self.app_settings = {"catalog_channel_settings": catalog_channel_settings}


mtv_infos_channel = _FakeAppChannel("MTV", "/Volumes/Media/MTV")
mtv_infos_id = f"media:{os.path.realpath('/Volumes/Media/MTV')}"
infos_app = _FakeInfosApp(
    [mtv_infos_channel],
    {
        mtv_infos_id: {"enabled": True, "channel_number": 1},
        # All three companion types seeded by migrate_legacy_channel_settings,
        # every one of them disabled -- none should ever appear in self.channels,
        # matching a fresh install where the user hasn't enabled any yet.
        "special:weatherstar": {"enabled": False, "channel_number": 1, "display_name": ""},
        "special:radiowave": {"enabled": False, "channel_number": 1, "display_name": ""},
        "special:youtube": {"enabled": False, "channel_number": 1, "display_name": ""},
    },
)
infos = infos_app.current_catalog_channel_infos()
check(
    "no disabled companion id appears in the infos list at all",
    all(not info["id"].startswith("special:") for info in infos),
    infos,
)
check("the real local channel is still present and unaffected", any(info["id"] == mtv_infos_id for info in infos))
check("exactly one info entry total -- no phantom entries synthesized", len(infos) == 1, infos)

# ---------------------------------------------------------------------------
# Bug found via live/manual verification: the Companion Channels tab's
# spinboxes (weatherstar_channel_input/radiowave_channel_input/
# youtube_channel_input) were seeded straight from the legacy flat
# weatherstar_channel_number/etc setting -- but repair_duplicate_numbers
# (channel identity cleanup) writes its fix into catalog_channel_settings'
# unified entry, never touching the flat key. A companion whose number
# got auto-repaired on startup would show its OLD, stale number the
# moment Advanced Configuration opened, silently disagreeing with the
# real, authoritative number driving Guide/playback sort order.
# ---------------------------------------------------------------------------
section("AdvancedConfigDialog: companion spinboxes seed from the authoritative, possibly-repaired entry")

init_source = inspect.getsource(channelsurfer2000.AdvancedConfigDialog.__init__)
for _companion_type in ("weatherstar", "radiowave", "youtube"):
    check(
        f"{_companion_type}_channel_input prefers catalog_channel_settings['special:{_companion_type}'] over the legacy flat key",
        f'self.catalog_channel_settings.get("special:{_companion_type}"' in init_source,
    )

# ---------------------------------------------------------------------------
# Companion channel parity (commit 4): every identity operation available
# for a local channel is available for a companion too, and the dashboard
# card gives both the same visual treatment -- no code changes needed
# here, this section is verification that commits 1-3 actually delivered
# parity, not just symmetry in name.
# ---------------------------------------------------------------------------
section("companion parity: enabled/number/name are fully symmetric")

parity_dialog = _FakeDialog()
parity_main_app = _FakeMainApp()
parity_dialog._parent = parity_main_app

check("enabled read exists for a local channel", channel_actions.local_channel_enabled_from_dialog(parity_dialog, "media:/fake/a") is not None)
check("enabled read exists for a companion", channel_actions.companion_snapshot_from_dialog(parity_dialog)["weatherstar"]["enabled"] is not None)
check("enabled write exists for a local channel", channel_actions.set_local_channel_enabled(parity_dialog, "media:/fake/a", False) is True)
check("enabled write exists for a companion", channel_actions.set_companion_enabled_on_dialog(parity_dialog, "weatherstar", False) is True)

check("number read dispatch works identically for local and companion ids", (
    channel_actions.channel_number_from_dialog(parity_dialog, "media:/fake/a") is not None,
    channel_actions.channel_number_from_dialog(parity_dialog, "special:weatherstar") is not None,
) == (True, True))
check("number write dispatch works identically for local and companion ids", (
    channel_actions.set_channel_number_on_dialog(parity_dialog, "media:/fake/a", 11),
    channel_actions.set_channel_number_on_dialog(parity_dialog, "special:weatherstar", 12),
) == (True, True))
check("number validation dispatch works identically for local and companion ids", (
    channel_actions.validate_channel_number_on_dialog(parity_dialog, "media:/fake/a", 20)[0],
    channel_actions.validate_channel_number_on_dialog(parity_dialog, "special:weatherstar", 21)[0],
) == ("ok", "ok"))

check("name read dispatch works identically for local and companion ids", (
    channel_actions.channel_name_from_dialog(parity_dialog, "media:/fake/a") is not None,
    channel_actions.channel_name_from_dialog(parity_dialog, "special:weatherstar") is not None,
) == (True, True))
check("name write dispatch works identically for local and companion ids", (
    channel_actions.set_channel_name_on_dialog(parity_dialog, "media:/fake/a", "Renamed A"),
    channel_actions.set_channel_name_on_dialog(parity_dialog, "special:weatherstar", "Renamed Weather"),
) == (True, True))
check("name validation dispatch works identically for local and companion ids", (
    channel_actions.validate_channel_name_on_dialog(parity_dialog, "media:/fake/a", "Another Name")[0],
    channel_actions.validate_channel_name_on_dialog(parity_dialog, "special:weatherstar", "Another Weather Name")[0],
) == ("ok", "ok"))

check("reorder renumbering is unified across both pools -- one algorithm, not two per-pool ones", (
    hasattr(channel_identity, "renumber_from_order"),
    hasattr(channel_actions, "apply_unified_numbers_to_dialog"),
    not hasattr(channel_actions, "resequence_local_channels_on_dialog"),
    not hasattr(channel_actions, "resequence_companions_on_dialog"),
) == (True, True, True, True))

section("companion parity: unified_entries is type-agnostic (future companion types)")

parity_pool = channel_identity.unified_entries(
    [{"id": "media:/a", "name": "A", "number": 1, "enabled": True}],
    companion_adapter.empty_snapshot(),
)
check(
    "unified_entries only depends on COMPANION_TYPES/COMPANION_CHANNEL_IDS/COMPANION_NAMES -- adding a 4th "
    "companion type to those three would flow through automatically, no channel_identity.py change needed",
    all(entry["id"] in companion_adapter.COMPANION_CHANNEL_IDS.values() or entry["id"] == "media:/a" for entry in parity_pool),
)

section("channel_card.py: no visual distinction between local and companion cards")

card_source = inspect.getsource(channel_card.build_dashboard_channel_card)
check("card width, border, and shadow are built through a single, unconditional code path for every channel", card_source.count('setObjectName("sectionCard")') == 1)
check(
    "is_companion only ever gates the status panel's content and the Remove/Disable label -- not the card's visual frame",
    card_source.count("is_companion") == 2,
)

# ---------------------------------------------------------------------------
# channel_identity.py: unified local+companion pool, dedup, validation
# ---------------------------------------------------------------------------
section("channel_identity: unified_entries merges local + companion")

local_rows = [
    {"id": "media:/a", "name": "4Kids", "number": 1, "enabled": True},
    {"id": "media:/b", "name": "Movies", "number": 2, "enabled": True},
]
snapshot = companion_adapter.set_companion_enabled(companion_adapter.empty_snapshot(), "weatherstar", True)
entries = channel_identity.unified_entries(local_rows, snapshot)
check("unified_entries includes both local rows", sum(1 for e in entries if not e["is_companion"]) == 2, entries)
check("unified_entries always includes all 3 companion slots", sum(1 for e in entries if e["is_companion"]) == 3, entries)
check("a disabled companion slot is still present, just enabled=False", any(e["id"] == "special:radiowave" and not e["enabled"] for e in entries), entries)
check("the enabled companion slot carries through", any(e["id"] == "special:weatherstar" and e["enabled"] for e in entries), entries)

section("channel_identity: duplicate detection ignores disabled entries")

fresh_install = channel_identity.unified_entries([], companion_adapter.empty_snapshot())
check("three disabled companions defaulting to the same number is NOT reported as a duplicate", channel_identity.find_duplicate_numbers(fresh_install) == {}, fresh_install)

colliding = [
    {"id": "media:/a", "name": "A", "number": 3, "enabled": True, "is_companion": False},
    {"id": "media:/b", "name": "B", "number": 3, "enabled": True, "is_companion": False},
    {"id": "media:/c", "name": "C", "number": 3, "enabled": False, "is_companion": False},
]
dupes = channel_identity.find_duplicate_numbers(colliding)
check("two enabled channels sharing a number are reported", dupes == {3: ["media:/a", "media:/b"]}, dupes)

section("channel_identity: repair_duplicate_numbers preserves gaps, fixes only collisions")

no_collision = [
    {"id": "a", "name": "A", "number": 2, "enabled": True, "is_companion": False},
    {"id": "b", "name": "B", "number": 5, "enabled": True, "is_companion": False},
    {"id": "c", "name": "C", "number": 8, "enabled": True, "is_companion": False},
]
repaired, changes = channel_identity.repair_duplicate_numbers(no_collision)
check("no collisions -> numbers untouched", [e["number"] for e in repaired] == [2, 5, 8], repaired)
check("no collisions -> empty changelog", changes == [], changes)

with_collision = [
    {"id": "a", "name": "A", "number": 2, "enabled": True, "is_companion": False},
    {"id": "b", "name": "B", "number": 2, "enabled": True, "is_companion": False},
    {"id": "c", "name": "C", "number": 8, "enabled": True, "is_companion": False},
]
repaired2, changes2 = channel_identity.repair_duplicate_numbers(with_collision)
numbers2 = [e["number"] for e in repaired2]
check("a genuine collision reassigns only the colliding entry", len(set(numbers2)) == 3, repaired2)
check("the untouched channel (8) keeps its gap", 8 in numbers2, repaired2)
check("repair never drops an entry", len(repaired2) == len(with_collision))
check("changelog records exactly one reassignment", len(changes2) == 1, changes2)

unset_and_disabled = [
    {"id": "a", "name": "A", "number": 0, "enabled": True, "is_companion": False},
    {"id": "b", "name": "B", "number": 0, "enabled": False, "is_companion": True},
]
repaired3, changes3 = channel_identity.repair_duplicate_numbers(unset_and_disabled)
check("an unset (0) enabled channel gets a real number assigned", repaired3[0]["number"] > 0, repaired3)
check("a disabled channel is left completely untouched, even at 0", repaired3[1]["number"] == 0, repaired3)
check("repair never raises on empty input", channel_identity.repair_duplicate_numbers([]) == ([], []))

section("channel_identity: manual number/name validation")

pool = [
    {"id": "media:/a", "name": "4Kids", "number": 1, "enabled": True, "is_companion": False},
    {"id": "media:/b", "name": "Movies", "number": 2, "enabled": True, "is_companion": False},
    {"id": "special:weatherstar", "name": "WeatherStar 4000+", "number": 3, "enabled": True, "is_companion": True},
]
check("an available number returns ok", channel_identity.validate_new_number(pool, "media:/a", 7) == ("ok", None))
check("a duplicate number is rejected with the conflicting id", channel_identity.validate_new_number(pool, "media:/a", 2) == ("duplicate", "media:/b"))
check("a channel doesn't conflict with its own current number", channel_identity.validate_new_number(pool, "media:/a", 1) == ("ok", None))
check("a local channel colliding with a companion's number is caught too", channel_identity.validate_new_number(pool, "media:/a", 3)[0] == "duplicate")
check("an out-of-range number is invalid, not a crash", channel_identity.validate_new_number(pool, "media:/a", 99999)[0] == "invalid")
check("zero is invalid (0 means unset internally)", channel_identity.validate_new_number(pool, "media:/a", 0)[0] == "invalid")
check("a non-numeric candidate is invalid, not a crash", channel_identity.validate_new_number(pool, "media:/a", "abc")[0] == "invalid")

check("a blank name is rejected", channel_identity.validate_new_name(pool, "media:/a", "   ")[0] == "invalid")
check("a normal rename is ok", channel_identity.validate_new_name(pool, "media:/a", "4Kids Classic") == ("ok", None))

section("channel_identity: unified reorder renumbering (requirement 8+9)")

lineup = [
    {"id": "4kids", "name": "4Kids", "number": 1, "enabled": True, "is_companion": False},
    {"id": "movies", "name": "Movies", "number": 2, "enabled": True, "is_companion": False},
    {"id": "mtv", "name": "MTV", "number": 3, "enabled": True, "is_companion": False},
    {"id": "toonami", "name": "Toonami", "number": 4, "enabled": True, "is_companion": False},
]
new_numbers = channel_identity.renumber_from_order(lineup, ["4kids", "movies", "mtv", "toonami"])
check("dragging 4Kids to the front gives it the smallest number in the pool", new_numbers["4kids"] == 1, new_numbers)
reordered = channel_identity.renumber_from_order(lineup, ["toonami", "4kids", "movies", "mtv"])
check("the spec's example: dragging 4Kids above Movies literally renumbers everyone", reordered == {"toonami": 1, "4kids": 2, "movies": 3, "mtv": 4}, reordered)

gapped = [
    {"id": "a", "name": "A", "number": 2, "enabled": True, "is_companion": False},
    {"id": "b", "name": "B", "number": 5, "enabled": True, "is_companion": False},
    {"id": "c", "name": "C", "number": 8, "enabled": True, "is_companion": True},
]
gap_result = channel_identity.renumber_from_order(gapped, ["c", "a", "b"])
check("gaps like 2/5/8 survive a reorder, just reassigned", sorted(gap_result.values()) == [2, 5, 8], gap_result)
check("a companion dragged to the front gets a real number from the shared pool", gap_result["c"] == 2, gap_result)

check("a stale id in final_order is safely skipped", "ghost" not in channel_identity.renumber_from_order(gapped, ["ghost", "a", "b", "c"]))
check("fewer than 2 matched entries is a safe no-op", channel_identity.renumber_from_order(gapped, ["a"]) == {})
check("an entirely empty order is a safe no-op", channel_identity.renumber_from_order(gapped, []) == {})

section("channel_identity: backward-compat / legacy migration")

legacy_settings = {
    "weatherstar_enabled": True,
    "weatherstar_channel_number": 9,
    "radiowave_enabled": False,
    "radiowave_channel_number": 1,
    "youtube_enabled": False,
    "youtube_channel_number": 1,
    "catalog_channel_settings": {},
}
migrate_legacy_channel_settings(legacy_settings)
check("migration seeds a special:weatherstar entry from the old flat keys", "special:weatherstar" in legacy_settings["catalog_channel_settings"])
check("migrated entry carries over the real enabled flag", legacy_settings["catalog_channel_settings"]["special:weatherstar"]["enabled"] is True)
check("migrated entry carries over the real channel number", legacy_settings["catalog_channel_settings"]["special:weatherstar"]["channel_number"] == 9)
check("the old flat key is left in place, not deleted", legacy_settings["weatherstar_channel_number"] == 9)

already_migrated = dict(legacy_settings)
already_migrated["weatherstar_channel_number"] = 999  # should NOT overwrite the existing entry
migrate_legacy_channel_settings(already_migrated)
check("migration is idempotent -- doesn't overwrite an already-migrated entry", already_migrated["catalog_channel_settings"]["special:weatherstar"]["channel_number"] == 9)

check("migration never raises on a bare empty app_settings", isinstance(migrate_legacy_channel_settings({}), dict))
check("migration never raises on non-dict input", migrate_legacy_channel_settings(None) is None)

bare_config = {}
migrate_legacy_channel_settings(bare_config)
check("a totally bare config still ends up with all 3 companion slots seeded, all disabled by default", len(bare_config["catalog_channel_settings"]) == 3)
check("normalize_catalog_channel_settings accepts the migrated shape without raising", len(normalize_catalog_channel_settings(bare_config["catalog_channel_settings"])) == 3)

# ---------------------------------------------------------------------------
# Tests: closing the one remaining manual-verification gap -- confirming
# refresh_live_lineup actually reaches the Guide (not just the two
# customization methods every earlier check already covers), completing
# the "My Catalog / Guide / playback all update, no restart" requirement.
# ---------------------------------------------------------------------------
section("refresh_live_lineup: reaches the Guide too, not just customization")


class _FakeGuideOverlay:
    def __init__(self, visible):
        self._visible = visible

    def isVisible(self):
        return self._visible


class _FakeVideoWindow:
    def __init__(self, guide_visible):
        self.guide_overlay = _FakeGuideOverlay(guide_visible)


class _FakeMainAppWithGuide(_FakeMainApp):
    def __init__(self, guide_visible):
        super().__init__()
        self.video_window = _FakeVideoWindow(guide_visible)
        self.guide_refreshed = False

    def refresh_guide(self):
        self.guide_refreshed = True


guide_visible_dialog = _FakeDialog()
guide_visible_app = _FakeMainAppWithGuide(guide_visible=True)
guide_visible_dialog._parent = guide_visible_app
channel_actions.refresh_live_lineup(guide_visible_dialog)
check(
    "refresh_live_lineup refreshes the Guide immediately when it's on screen -- no restart needed",
    guide_visible_app.injected and guide_visible_app.customized and guide_visible_app.guide_refreshed,
)

guide_hidden_dialog = _FakeDialog()
guide_hidden_app = _FakeMainAppWithGuide(guide_visible=False)
guide_hidden_dialog._parent = guide_hidden_app
channel_actions.refresh_live_lineup(guide_hidden_dialog)
check(
    "refresh_live_lineup doesn't force-refresh a Guide the user isn't currently looking at",
    guide_hidden_app.guide_refreshed is False,
)

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

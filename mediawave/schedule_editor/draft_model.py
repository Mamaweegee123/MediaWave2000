"""The Schedule Editor's isolated draft layer.

No Qt, no filesystem, no imports from channelsurfer2000 -- this module
holds plain data cloned from the read-only board model
(schedule_model.build_board_model's ChannelLane/ProgramBlock output) plus
an ordered list of DraftChange records describing unsaved edits. Nothing
here references live Channel objects, playback widgets, or media players,
so no draft operation can possibly mutate live playback, channel queues,
schedule caches, or persisted state -- the only way a draft edit reaches
the real world is Save Schedule serializing `overrides_for_save()` and
handing the records to the app's save pipeline
(save_schedule_overrides_from_editor in channelsurfer2000.py).

The draft is a CHANGE-SET over the effective lineup, not a deep copy of
it: `presentation_lanes()` recomputes what the board should show by
sequentially masking each change's interval onto the cloned base blocks --
the exact "last edit wins" semantics mediawave/schedule_overrides.py
applies to saved overrides (it reuses that module's subtract_interval), so
what you see in the draft is what saving will produce. This also makes day
navigation trivial (changes are absolute-time anchored; re-cloning a new
window's base lanes via set_base_lanes keeps every change), makes repeated
refreshes idempotent, and makes dirty-state exact: dirty == "at least one
change record exists".
"""

import time
from dataclasses import dataclass, field, replace

from mediawave.schedule_overrides import (
    OVERRIDE_ACTION_ADD,
    OVERRIDE_ACTION_REMOVE,
    OPEN_TIME_TITLE,
    subtract_interval,
)

from .schedule_model import ChannelLane, ProgramBlock

# Draft block statuses -- carried on the presentation blocks so the UI can
# label added programs and open gaps without re-deriving anything.
DRAFT_STATUS_UNCHANGED = "unchanged"
DRAFT_STATUS_ADDED = "added"
DRAFT_STATUS_OPEN = "open"

# Why a companion channel's programming can't be edited in this phase --
# shown verbatim to the user, so these are complete, friendly sentences.
COMPANION_LOCK_REASONS = {
    "weatherstar": "WeatherStar programming is generated live by the weather service, so it can't be edited here.",
    "radiowave": "RadioWaveTV plays a continuous music mix managed by its own scheduler, so individual blocks can't be edited yet.",
    "youtube": "NetTV programming follows its online playlist, so its lineup can't be edited here yet.",
}

NO_DATA_LOCK_REASON = "This channel has no scheduled breakdown to edit."


def channel_lock_reason(channel_type, has_data=True):
    """The friendly reason a channel can't be edited, or "" if it can."""
    reason = COMPANION_LOCK_REASONS.get(channel_type, "")
    if reason:
        return reason
    if not has_data:
        return NO_DATA_LOCK_REASON
    return ""


def _format_change_time_range(start_epoch, end_epoch):
    """Pure time.strftime formatting (no Qt) -- kept local rather than
    importing program_block.py's Qt-adjacent formatter, so this module
    stays importable without a QApplication.
    """
    try:
        start_label = time.strftime("%-I:%M", time.localtime(start_epoch))
        end_label = time.strftime("%-I:%M %p", time.localtime(end_epoch))
    except (OSError, OverflowError, ValueError):
        return ""
    return f"{start_label}–{end_label}"


@dataclass
class DraftChange:
    """One applied draft edit. `action` follows the saved-override
    vocabulary (mediawave/schedule_overrides.py) on purpose -- saving is a
    direct translation, not a re-interpretation.
    """

    change_id: int
    action: str  # OVERRIDE_ACTION_ADD | OVERRIDE_ACTION_REMOVE
    channel_id: str
    start: float
    end: float
    title: str = ""
    path: str = ""
    media_type: str = "tv"


class DraftSchedule:
    """The editable draft: cloned base lanes + ordered change records."""

    def __init__(self):
        self._base_lanes = []
        self._changes = []
        self._next_change_id = 1

    # ── base snapshot ────────────────────────────────────────────────

    def set_base_lanes(self, lanes):
        """Clone the read-only board lanes into the draft. Deep-copies the
        dataclass blocks (dataclasses.replace + fresh lists) so no draft
        operation can reach back into the objects the read-only board --
        or anything else -- still holds. Called at open and again on day
        navigation / refresh; existing changes are kept (they're anchored
        to absolute times, not to the cloned objects).
        """
        cloned = []
        for lane in lanes or []:
            blocks = [
                replace(block, raw_entries=list(block.raw_entries), source_titles=list(block.source_titles))
                for block in lane.blocks
            ]
            cloned.append(
                ChannelLane(
                    channel_id=lane.channel_id,
                    name=lane.name,
                    number=lane.number,
                    channel_type=lane.channel_type,
                    logo_path=lane.logo_path,
                    blocks=blocks,
                    has_data=lane.has_data,
                )
            )
        self._base_lanes = cloned

    # ── change bookkeeping ───────────────────────────────────────────

    def new_change(self, action, channel_id, start, end, title="", path="", media_type="tv"):
        """A DraftChange with a fresh id -- NOT yet applied; commands own
        when apply_change/remove_change happen so undo/redo stay exact.
        """
        change = DraftChange(
            change_id=self._next_change_id,
            action=action,
            channel_id=channel_id,
            start=float(start),
            end=float(end),
            title=title,
            path=path,
            media_type=media_type,
        )
        self._next_change_id += 1
        return change

    def apply_change(self, change):
        self._changes.append(change)

    def remove_change(self, change_id):
        self._changes = [change for change in self._changes if change.change_id != change_id]

    def find_change(self, change_id):
        return next((change for change in self._changes if change.change_id == change_id), None)

    @property
    def changes(self):
        return list(self._changes)

    def is_dirty(self):
        return bool(self._changes)

    def clear_changes(self):
        """Revert: drop every unsaved edit. The base snapshot (the
        original generated lineup clone) is untouched, so presentation
        immediately shows the pre-edit state again.
        """
        self._changes = []

    # ── channel access / editability ─────────────────────────────────

    def lanes(self):
        return list(self._base_lanes)

    def lane_for(self, channel_id):
        return next((lane for lane in self._base_lanes if lane.channel_id == channel_id), None)

    def lane_lock_reason(self, channel_id):
        lane = self.lane_for(channel_id)
        if lane is None:
            return NO_DATA_LOCK_REASON
        return channel_lock_reason(lane.channel_type, lane.has_data)

    # ── presentation ─────────────────────────────────────────────────

    def presentation_lanes(self, window_start=None, window_end=None):
        """The lanes the board should render: base blocks with each draft
        change sequentially masked in (see module docstring). Base blocks
        are never mutated -- trimmed pieces are fresh dataclass copies.

        Masking runs in window-clipped coordinates (base blocks arrive
        clipped by schedule_model's _clip_to_window; change blocks are
        clipped here when window bounds are given), so a change whose
        interval extends past the visible window still renders correctly
        inside it.
        """
        lanes = []
        for lane in self._base_lanes:
            channel_changes = [c for c in self._changes if c.channel_id == lane.channel_id]
            if not channel_changes:
                lanes.append(
                    ChannelLane(
                        channel_id=lane.channel_id,
                        name=lane.name,
                        number=lane.number,
                        channel_type=lane.channel_type,
                        logo_path=lane.logo_path,
                        blocks=list(lane.blocks),
                        has_data=lane.has_data,
                    )
                )
                continue

            blocks = list(lane.blocks)
            for change in channel_changes:
                survivors = []
                for block in blocks:
                    for piece_start, piece_end in subtract_interval(
                        block.start, block.end, change.start, change.end
                    ):
                        if piece_start == block.start and piece_end == block.end:
                            survivors.append(block)
                        else:
                            survivors.append(
                                replace(
                                    block,
                                    start=piece_start,
                                    end=piece_end,
                                    true_start=piece_start,
                                    true_end=piece_end,
                                    duration=max(0.0, piece_end - piece_start),
                                    raw_entries=list(block.raw_entries),
                                    source_titles=list(block.source_titles),
                                )
                            )
                change_block = self._block_for_change(lane.channel_id, change, window_start, window_end)
                if change_block is not None:
                    survivors.append(change_block)
                blocks = survivors

            blocks.sort(key=lambda block: (block.start, block.end))
            lanes.append(
                ChannelLane(
                    channel_id=lane.channel_id,
                    name=lane.name,
                    number=lane.number,
                    channel_type=lane.channel_type,
                    logo_path=lane.logo_path,
                    blocks=blocks,
                    has_data=lane.has_data,
                )
            )
        return lanes

    def _block_for_change(self, channel_id, change, window_start=None, window_end=None):
        visible_start = change.start if window_start is None else max(change.start, window_start)
        visible_end = change.end if window_end is None else min(change.end, window_end)
        if visible_end <= visible_start:
            return None
        return self._build_change_block(channel_id, change, visible_start, visible_end)

    def _build_change_block(self, channel_id, change, visible_start, visible_end):
        if change.action == OVERRIDE_ACTION_ADD:
            return ProgramBlock(
                channel_id=channel_id,
                title=change.title or "Untitled",
                media_type=change.media_type or "tv",
                start=visible_start,
                end=visible_end,
                duration=max(0.0, visible_end - visible_start),
                is_commercial=False,
                source="draft",
                true_start=change.start,
                true_end=change.end,
                raw_entries=[{
                    "kind": "content",
                    "path": change.path,
                    "title": change.title,
                    "duration": max(0.0, change.end - change.start),
                    "source": "draft",
                }],
            )
        return ProgramBlock(
            channel_id=channel_id,
            title=OPEN_TIME_TITLE,
            media_type="open",
            start=visible_start,
            end=visible_end,
            duration=max(0.0, visible_end - visible_start),
            is_commercial=False,
            source="draft",
            true_start=change.start,
            true_end=change.end,
            raw_entries=[{"kind": "open_time", "duration": max(0.0, change.end - change.start)}],
        )

    # ── overlap queries (for Put On Air validation) ──────────────────

    def programs_overlapping(self, channel_id, start, end):
        """Real (non-open) draft-presentation blocks intersecting
        [start, end) on the channel, sorted by start.
        """
        lane = next((l for l in self.presentation_lanes() if l.channel_id == channel_id), None)
        if lane is None:
            return []
        hits = [
            block
            for block in lane.blocks
            if block.media_type != "open" and block.true_start < end and block.true_end > start
        ]
        return sorted(hits, key=lambda block: block.true_start)

    # ── pending-changes summary (Phase 2.1) ──────────────────────────

    def describe_pending_changes(self):
        """Friendly-language rows for every currently-pending draft
        change, in edit order -- the Pending Changes panel renders these
        directly rather than keeping any list of its own (see dialog.py),
        so it can never drift out of sync with the actual change model.
        """
        return [self._describe_change(change) for change in self._changes]

    def _describe_change(self, change):
        lane = self.lane_for(change.channel_id)
        channel_label = f"Ch {lane.number} · {lane.name}" if lane is not None else "Ch ?"
        time_label = _format_change_time_range(change.start, change.end)
        if change.action == OVERRIDE_ACTION_ADD:
            headline = f"Put “{change.title or 'this media'}” on air"
        else:
            headline = f"Pulled “{change.title or 'this program'}”"
        return {
            "change_id": change.change_id,
            "action": change.action,
            "headline": headline,
            "subline": f"{channel_label} · {time_label}" if time_label else channel_label,
        }

    # ── save serialization ───────────────────────────────────────────

    def overrides_for_save(self):
        """The minimal override records for the current changes, in edit
        order (order IS precedence for saved overrides). One record per
        change -- the change-set is already minimal because undo removes
        records instead of appending compensating ones.
        """
        records = []
        for change in self._changes:
            records.append(
                {
                    "action": change.action,
                    "channel_id": change.channel_id,
                    "date": time.strftime("%Y-%m-%d", time.localtime(change.start)),
                    "start": change.start,
                    "end": change.end,
                    "title": change.title,
                    "path": change.path,
                    "media_type": change.media_type,
                }
            )
        return records

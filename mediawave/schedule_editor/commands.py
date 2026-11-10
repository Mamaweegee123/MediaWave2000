"""Schedule Editor draft commands: Pull and Put On Air, plus the small
undo/redo history that drives the toolbar buttons.

No Qt and no generic command framework -- exactly the two schedule
commands this phase needs, built so later drag-and-drop/resize commands
can follow the same shape (validate -> apply -> undo, one DraftChange per
command). Commands mutate ONLY the DraftSchedule they're handed; nothing
here can touch live playback, Channel objects, or persisted state.

Validation returns plain-language ValidationResults -- the reasons are
complete sentences shown verbatim to the user, per the "explain why in
plain language" requirement.
"""

import time
from dataclasses import dataclass, field

from mediawave.schedule_overrides import OVERRIDE_ACTION_ADD, OVERRIDE_ACTION_REMOVE

# Conflict types (spec section 11). Only the ones this phase can actually
# produce exist -- "overlaps previous program" can't happen yet because
# Put On Air always starts at a selected open slot's start, and
# "protected companion block" surfaces as a channel lock reason instead.
# Automatic conflict RESOLUTION (auto-shifting later programs, auto-fill)
# is deliberately deferred; the only supported answers to a conflict are
# cancel, extend-over (mask), or choose something else.
CONFLICT_OVERLAPS_FOLLOWING = "overlaps_following_program"
CONFLICT_OUTSIDE_EDITABLE_RANGE = "outside_editable_range"
CONFLICT_PROTECTED_BLOCK = "protected_block"
CONFLICT_INVALID_DURATION = "invalid_media_duration"
CONFLICT_MISSING_MEDIA = "missing_source_media"
# Phase 3: a move's destination overlaps one or more existing blocks. Not
# reused from CONFLICT_OVERLAPS_FOLLOWING -- a move's destination can
# overlap on either side (or be fully covered by) an existing block, not
# only "runs past the end of an open slot into what follows".
CONFLICT_OVERLAPS_DESTINATION = "overlaps_destination"
# Phase 4: one item in an Auto-Fill Block lineup overlaps an existing
# draft block. Its own type (not CONFLICT_OVERLAPS_FOLLOWING/
# CONFLICT_OVERLAPS_DESTINATION) because those describe a single-item
# placement's specific overrun/destination shape; an autofill lineup
# item can overlap anything already in the block for reasons that have
# nothing to do with either (most commonly: the draft changed between
# preview and Apply Lineup).
CONFLICT_OVERLAPS_EXISTING = "overlaps_existing_block"

# The one shared snap-to-time interval for Move To…, drag placement math,
# and command validation, so all three can never disagree about where a
# placement actually lands. Not user-configurable yet (spec: later phases
# may offer other increments; this phase ships one fixed default).
SNAP_INTERVAL_SECONDS = 5 * 60


def local_day_bounds(epoch_seconds):
    """(day_start, day_end) -- the full LOCAL calendar day containing
    `epoch_seconds`, as a half-open [midnight, next midnight) interval.
    Phase 4.5.2's Clear Day needs this to be exactly correct across a
    DST transition, so it deliberately does NOT use a fixed-86400-second
    offset (epoch_seconds - (epoch_seconds % 86400) is UTC-day-aligned,
    not local-day-aligned, and a fixed +86400 silently produces the
    wrong boundary on a 23- or 25-hour local day). Two localtime/mktime
    round-trips instead: mktime's own tm_isdst=-1 resolution handles the
    "spring forward"/"fall back" arithmetic correctly, and re-deriving
    the next midnight from a definitely-next-day instant (start + 25h
    always lands in the next calendar day, whether today is 23, 24, or
    25 hours long) rather than assuming a fixed day length.
    """
    local = time.localtime(epoch_seconds)
    day_start = time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1))
    next_local = time.localtime(day_start + 25 * 3600)
    day_end = time.mktime((next_local.tm_year, next_local.tm_mon, next_local.tm_mday, 0, 0, 0, 0, 0, -1))
    return day_start, day_end


def snap_to_interval(epoch_seconds, interval_seconds=SNAP_INTERVAL_SECONDS):
    """Round to the nearest interval boundary -- 5:02 PM -> 5:00 PM, 5:03 PM
    -> 5:05 PM, 5:28 PM -> 5:30 PM. Epoch-modulo rounding is timezone-safe
    for any offset that is itself a multiple of `interval_seconds` (true
    for the vast majority of real-world timezones), matching how
    `auto_schedule_anchor`/`_floor_to_half_hour` already treat epoch-
    modulo as safe half-hour alignment elsewhere in this codebase.
    """
    return round(epoch_seconds / interval_seconds) * interval_seconds


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""  # plain-language, user-facing
    conflicts: list = field(default_factory=list)  # [{"type", "message", ...}]


def _minutes_label(seconds):
    minutes = max(1, round(abs(seconds) / 60))
    return f"{minutes} minute" + ("" if minutes == 1 else "s")


def _draft_add_change_for_block(draft, block):
    """The pending ADD change a draft-added (unsaved) block corresponds
    to, if any -- shared by PullProgramCommand and MoveProgramCommand so
    "remove this block from the draft" always means the same thing
    regardless of which command does it: cancel out its own not-yet-saved
    add-change rather than stacking a redundant remove on top of it. A
    generated or already-saved-override block never matches (its
    placement isn't a pending add-change at all), so this correctly
    returns None for those.
    """
    if block.source != "draft" or block.media_type == "open":
        return None
    for change in draft.changes:
        if (
            change.action == OVERRIDE_ACTION_ADD
            and change.channel_id == block.channel_id
            and change.start == block.true_start
            and change.end == block.true_end
        ):
            return change
    return None


def _block_identity_matches(block, other):
    return (
        block.channel_id == other.channel_id
        and block.true_start == other.true_start
        and block.true_end == other.true_end
    )


class PullProgramCommand:
    """Remove the selected draft program from the lineup, leaving open
    time. Pulling a program that only exists as an unsaved Put On Air
    (source "draft") removes that add-change instead of stacking a remove
    on top of it -- undo/redo restore the exact same change object either
    way, so ids and history stay stable.
    """

    def __init__(self, block):
        self._block = block
        self._remove_change = None  # created once, reused across redo
        self._removed_add_change = None  # the add-change a draft-added pull removes

    @property
    def description(self):
        return f"Pull “{self._block.title}”"

    @property
    def channel_id(self):
        return self._block.channel_id

    @property
    def time_range(self):
        return (self._block.true_start, self._block.true_end)

    def command_change_id(self):
        """The DraftChange id this command currently owns in
        `draft.changes`, or None if it doesn't own one right now (the
        cancel-out branch of apply(), below, removes someone else's
        add-change instead of creating its own -- when that happens there
        is nothing left in draft.changes for this command to "own", so it
        correctly can't be looked up as a pending change to remove).
        """
        return self._remove_change.change_id if self._remove_change is not None else None

    def validate(self, draft, now=None):
        now = time.time() if now is None else now
        block = self._block
        lock_reason = draft.lane_lock_reason(block.channel_id)
        if lock_reason:
            return ValidationResult(False, lock_reason, [{"type": CONFLICT_PROTECTED_BLOCK, "message": lock_reason}])
        if block.media_type == "open":
            return ValidationResult(
                False,
                "This is already open time — there's nothing to pull here. Use Put On Air to schedule something.",
            )
        if block.is_commercial:
            reason = "Commercial breaks are placed by the commercial scheduler and can't be pulled on their own."
            return ValidationResult(False, reason, [{"type": CONFLICT_PROTECTED_BLOCK, "message": reason}])
        if block.true_end <= now:
            reason = "This program has already aired, so it can't be pulled."
            return ValidationResult(False, reason, [{"type": CONFLICT_OUTSIDE_EDITABLE_RANGE, "message": reason}])
        return ValidationResult(True)

    def apply(self, draft):
        if self._block.source == "draft" and self._block.media_type != "open":
            existing = _draft_add_change_for_block(draft, self._block)
            if existing is not None:
                self._removed_add_change = existing
                draft.remove_change(existing.change_id)
                return
        if self._remove_change is None:
            self._remove_change = draft.new_change(
                OVERRIDE_ACTION_REMOVE,
                self._block.channel_id,
                self._block.true_start,
                self._block.true_end,
                title=self._block.title,
            )
        draft.apply_change(self._remove_change)

    def undo(self, draft):
        if self._removed_add_change is not None:
            draft.apply_change(self._removed_add_change)
            self._removed_add_change = None
            return
        if self._remove_change is not None:
            draft.remove_change(self._remove_change.change_id)


class PutOnAirCommand:
    """Place a piece of media on a channel at a start time -- normally the
    start of a selected open slot. `media` is a plain dict:
    {"path", "title", "duration", "media_type"}. When the media runs past
    the open slot into real programming, validate() reports the conflict;
    constructing with extend_over_following=True records that the user
    explicitly chose Extend Into Following Time (the overlapped program is
    masked and joins in progress afterward -- nothing is silently moved
    or truncated).
    """

    def __init__(self, channel_id, start, media, slot_end=None, extend_over_following=False):
        self._channel_id = channel_id
        self._start = float(start)
        self._media = dict(media or {})
        self._slot_end = None if slot_end is None else float(slot_end)
        self._extend_over_following = bool(extend_over_following)
        self._add_change = None

    @property
    def description(self):
        return f"Put On Air “{self._media.get('title', 'Untitled')}”"

    @property
    def channel_id(self):
        return self._channel_id

    @property
    def end(self):
        return self._start + max(0.0, float(self._media.get("duration", 0) or 0))

    @property
    def time_range(self):
        return (self._start, self.end)

    def command_change_id(self):
        """The DraftChange id this command currently owns, or None before
        it has ever been applied.
        """
        return self._add_change.change_id if self._add_change is not None else None

    def validate(self, draft, now=None):
        now = time.time() if now is None else now
        lock_reason = draft.lane_lock_reason(self._channel_id)
        if lock_reason:
            return ValidationResult(False, lock_reason, [{"type": CONFLICT_PROTECTED_BLOCK, "message": lock_reason}])

        path = str(self._media.get("path", "") or "")
        if not path:
            reason = "This item doesn't have a playable media file behind it, so it can't be scheduled."
            return ValidationResult(False, reason, [{"type": CONFLICT_MISSING_MEDIA, "message": reason}])

        duration = float(self._media.get("duration", 0) or 0)
        if duration <= 0:
            reason = "This media file doesn't have a usable duration yet, so it can't be scheduled."
            return ValidationResult(False, reason, [{"type": CONFLICT_INVALID_DURATION, "message": reason}])

        end = self._start + duration
        if end <= now:
            reason = "This time slot has already aired, so nothing new can be scheduled in it."
            return ValidationResult(False, reason, [{"type": CONFLICT_OUTSIDE_EDITABLE_RANGE, "message": reason}])

        conflicts = []
        if self._slot_end is not None and end > self._slot_end:
            overlapped = draft.programs_overlapping(self._channel_id, self._slot_end, end)
            if overlapped:
                first = overlapped[0]
                overrun = end - self._slot_end
                title = self._media.get("title", "This media")
                message = (
                    f"“{title}” runs {_minutes_label(overrun)} past this open time, "
                    f"into “{first.title}”."
                )
                conflicts.append(
                    {
                        "type": CONFLICT_OVERLAPS_FOLLOWING,
                        "message": message,
                        "following_title": first.title,
                        "overrun_seconds": overrun,
                    }
                )
        if conflicts and not self._extend_over_following:
            return ValidationResult(False, conflicts[0]["message"], conflicts)
        return ValidationResult(True, conflicts=conflicts)

    def apply(self, draft):
        if self._add_change is None:
            self._add_change = draft.new_change(
                OVERRIDE_ACTION_ADD,
                self._channel_id,
                self._start,
                self.end,
                title=self._media.get("title", ""),
                path=self._media.get("path", ""),
                media_type=self._media.get("media_type", "tv") or "tv",
                # Same helper AutoFillBlockCommand uses (below): a no-op
                # unless `media` itself carries strategy="sequential" +
                # show_key -- only the Show Picker's Continue Sequentially
                # resolution (put_on_air_picker.resolve_show_episode)
                # ever stamps those on an ordinary Put On Air item, so
                # every other Put On Air/Fill Open Time/Advanced… placement
                # is unaffected. Lets one Show placement share the exact
                # same save-time cursor-advance path Auto-Fill already
                # has, instead of a second one (Phase 5.2).
                autofill_meta=_sequential_cursor_meta(self._media),
            )
        draft.apply_change(self._add_change)

    def undo(self, draft):
        if self._add_change is not None:
            draft.remove_change(self._add_change.change_id)


class MoveProgramCommand:
    """Change when (and optionally which channel) a program airs, without
    changing its length -- one user action in the draft's change history,
    even though it's internally equivalent to pulling the block from its
    source interval and putting the same media at the destination.
    `command_change_id()` hooks onto the destination add-change, so
    Pending Changes/Save Review/per-change-undo all treat a move as one
    row, never separate Pull + Put On Air rows.

    `replace_blocks`, if given, are destination-overlapping blocks the
    user has ALREADY explicitly chosen to replace (via the Move To…/drag
    conflict dialog) -- passing them here means validate() should treat
    those specific overlaps as pre-approved rather than reporting them
    again. Each is identified by (channel_id, true_start, true_end) since
    blocks have no other stable identity across a presentation rebuild.
    """

    def __init__(self, source_block, destination_channel_id, destination_start, replace_blocks=None):
        self._source_block = source_block
        self._destination_channel_id = destination_channel_id
        self._destination_start = float(destination_start)
        self._replace_blocks = list(replace_blocks or [])

        self._pull_change = None
        self._removed_source_add_change = None
        # Each entry: ("cancel", change) | ("remove", change) -- mirrors
        # the source's own cancel-or-remove choice, per replaced block.
        self._replace_changes = []
        self._add_change = None

    @property
    def description(self):
        return f"Move “{self._source_block.title}”"

    @property
    def source_channel_id(self):
        return self._source_block.channel_id

    @property
    def source_start(self):
        return self._source_block.true_start

    @property
    def destination_channel_id(self):
        return self._destination_channel_id

    @property
    def destination_start(self):
        return self._destination_start

    @property
    def duration(self):
        return max(0.0, self._source_block.true_end - self._source_block.true_start)

    @property
    def destination_end(self):
        return self._destination_start + self.duration

    def command_change_id(self):
        return self._add_change.change_id if self._add_change is not None else None

    def validate(self, draft, now=None):
        now = time.time() if now is None else now
        block = self._source_block

        source_lock = draft.lane_lock_reason(block.channel_id)
        if source_lock:
            return ValidationResult(False, source_lock, [{"type": CONFLICT_PROTECTED_BLOCK, "message": source_lock}])
        destination_lock = draft.lane_lock_reason(self._destination_channel_id)
        if destination_lock:
            return ValidationResult(False, destination_lock, [{"type": CONFLICT_PROTECTED_BLOCK, "message": destination_lock}])
        # Phase 3 scope: moving between channels needs safe cross-channel
        # media-identity handling (a channel's catalog/airing context is
        # channel-scoped) that hasn't been established yet -- same-channel
        # moves only, for now.
        if self._destination_channel_id != block.channel_id:
            return ValidationResult(False, "Moving programs between channels will be added later.")

        if block.media_type == "open":
            return ValidationResult(
                False,
                "This is open time — there's nothing to move. Use Put On Air to schedule something here.",
            )
        if block.is_commercial:
            reason = "Commercial breaks are placed by the commercial scheduler and can't be moved on their own."
            return ValidationResult(False, reason, [{"type": CONFLICT_PROTECTED_BLOCK, "message": reason}])
        if block.true_end <= now:
            reason = "This program has already aired, so it can't be moved."
            return ValidationResult(False, reason, [{"type": CONFLICT_OUTSIDE_EDITABLE_RANGE, "message": reason}])

        path = (block.raw_entries[0] or {}).get("path", "") if block.raw_entries else ""
        if not path:
            reason = "This program doesn't have a playable media file behind it, so it can't be moved."
            return ValidationResult(False, reason, [{"type": CONFLICT_MISSING_MEDIA, "message": reason}])

        duration = self.duration
        if duration <= 0:
            reason = "This program doesn't have a usable duration, so it can't be moved."
            return ValidationResult(False, reason, [{"type": CONFLICT_INVALID_DURATION, "message": reason}])

        destination_end = self.destination_end
        if destination_end <= now:
            reason = "That time has already aired, so nothing can be moved there."
            return ValidationResult(False, reason, [{"type": CONFLICT_OUTSIDE_EDITABLE_RANGE, "message": reason}])

        if self._destination_channel_id == block.channel_id and abs(self._destination_start - block.true_start) < 1.0:
            return ValidationResult(False, "This is already where it airs.")

        overlapped = draft.programs_overlapping(self._destination_channel_id, self._destination_start, destination_end)
        overlapped = [
            candidate
            for candidate in overlapped
            if not _block_identity_matches(candidate, block)
            and not any(_block_identity_matches(candidate, replaced) for replaced in self._replace_blocks)
        ]
        if overlapped:
            titles = [candidate.title for candidate in overlapped]
            if len(titles) == 1:
                overlap_start = max(self._destination_start, overlapped[0].true_start)
                overlap_end = min(destination_end, overlapped[0].true_end)
                overrun = max(0.0, overlap_end - overlap_start)
                message = f"“{block.title}” would overlap “{titles[0]}” by {_minutes_label(overrun)}."
            else:
                joined = ", ".join(f"“{title}”" for title in titles)
                message = f"“{block.title}” would overlap {joined}."
            conflicts = [
                {"type": CONFLICT_OVERLAPS_DESTINATION, "message": message, "overlapping_blocks": overlapped}
            ]
            return ValidationResult(False, message, conflicts)

        return ValidationResult(True)

    def apply(self, draft):
        if self._pull_change is None and self._removed_source_add_change is None:
            existing = _draft_add_change_for_block(draft, self._source_block)
            if existing is not None:
                self._removed_source_add_change = existing
            else:
                self._pull_change = draft.new_change(
                    OVERRIDE_ACTION_REMOVE,
                    self._source_block.channel_id,
                    self._source_block.true_start,
                    self._source_block.true_end,
                    title=self._source_block.title,
                    group_id=id(self),
                    is_move_source=True,
                )
        if self._removed_source_add_change is not None:
            draft.remove_change(self._removed_source_add_change.change_id)
        else:
            draft.apply_change(self._pull_change)

        if not self._replace_changes and self._replace_blocks:
            for replaced in self._replace_blocks:
                existing = _draft_add_change_for_block(draft, replaced)
                if existing is not None:
                    self._replace_changes.append(("cancel", existing))
                else:
                    change = draft.new_change(
                        OVERRIDE_ACTION_REMOVE,
                        replaced.channel_id,
                        replaced.true_start,
                        replaced.true_end,
                        title=replaced.title,
                        group_id=id(self),
                    )
                    self._replace_changes.append(("remove", change))
        for kind, change in self._replace_changes:
            if kind == "cancel":
                draft.remove_change(change.change_id)
            else:
                draft.apply_change(change)

        if self._add_change is None:
            path = (self._source_block.raw_entries[0] or {}).get("path", "") if self._source_block.raw_entries else ""
            self._add_change = draft.new_change(
                OVERRIDE_ACTION_ADD,
                self._destination_channel_id,
                self._destination_start,
                self.destination_end,
                title=self._source_block.title,
                path=path,
                media_type=self._source_block.media_type or "tv",
                group_id=id(self),
            )
        draft.apply_change(self._add_change)

    def undo(self, draft):
        if self._add_change is not None:
            draft.remove_change(self._add_change.change_id)
        for kind, change in reversed(self._replace_changes):
            if kind == "cancel":
                draft.apply_change(change)
            else:
                draft.remove_change(change.change_id)
        if self._removed_source_add_change is not None:
            draft.apply_change(self._removed_source_add_change)
        elif self._pull_change is not None:
            draft.remove_change(self._pull_change.change_id)


class DuplicateProgramCommand:
    """Add another airing of an existing program WITHOUT touching the
    original -- one command backs both "Duplicate Here…" (destination on
    the same date) and "Copy to Another Day…" (destination on any date);
    they're mechanically identical (an optional set of explicitly
    pre-approved destination-overlap replace-removes, plus one add-change
    for the new airing), differing only in which date the caller picks
    and the user-facing verb. `kind` ("duplicate" | "copy") controls only
    `description`/`group_kind` -- it has no effect on validate()/apply().

    Same shape as MoveProgramCommand: `command_change_id()` hooks onto the
    destination add-change, so Pending Changes/Save Review/per-change-
    undo treat the whole group as one row, and undo restores every
    replaced block exactly.

    Same-channel-only for this phase (see MoveProgramCommand's docstring
    for why cross-channel needs groundwork not yet established).
    """

    def __init__(self, source_block, destination_start, destination_channel_id=None, replace_blocks=None, kind="duplicate"):
        self._source_block = source_block
        self._destination_channel_id = destination_channel_id or source_block.channel_id
        self._destination_start = float(destination_start)
        self._replace_blocks = list(replace_blocks or [])
        self._kind = kind

        # Each entry: ("cancel", change) | ("remove", change) -- mirrors
        # MoveProgramCommand's replace bookkeeping exactly.
        self._replace_changes = []
        self._add_change = None

    @property
    def description(self):
        verb = "Duplicate" if self._kind == "duplicate" else "Copy"
        return f"{verb} “{self._source_block.title}”"

    @property
    def source_channel_id(self):
        return self._source_block.channel_id

    @property
    def source_start(self):
        return self._source_block.true_start

    @property
    def destination_channel_id(self):
        return self._destination_channel_id

    @property
    def destination_start(self):
        return self._destination_start

    @property
    def duration(self):
        return max(0.0, self._source_block.true_end - self._source_block.true_start)

    @property
    def destination_end(self):
        return self._destination_start + self.duration

    def command_change_id(self):
        return self._add_change.change_id if self._add_change is not None else None

    def validate(self, draft, now=None):
        now = time.time() if now is None else now
        block = self._source_block
        verb = "duplicated" if self._kind == "duplicate" else "copied"

        destination_lock = draft.lane_lock_reason(self._destination_channel_id)
        if destination_lock:
            return ValidationResult(False, destination_lock, [{"type": CONFLICT_PROTECTED_BLOCK, "message": destination_lock}])
        # Phase 3.1 scope: same restriction as MoveProgramCommand, for the
        # same reason -- a channel's catalog/airing context is
        # channel-scoped groundwork that hasn't been established yet.
        if self._destination_channel_id != block.channel_id:
            verb_label = "Duplicating" if self._kind == "duplicate" else "Copying"
            return ValidationResult(False, f"{verb_label} to another channel will be added later.")

        if block.media_type == "open":
            return ValidationResult(
                False,
                f"This is open time — there's nothing to {self._kind}. Use Put On Air to schedule something here.",
            )
        if block.is_commercial:
            reason = f"Commercial breaks are placed by the commercial scheduler and can't be {verb} on their own."
            return ValidationResult(False, reason, [{"type": CONFLICT_PROTECTED_BLOCK, "message": reason}])

        path = (block.raw_entries[0] or {}).get("path", "") if block.raw_entries else ""
        if not path:
            reason = f"This program doesn't have a playable media file behind it, so it can't be {verb}."
            return ValidationResult(False, reason, [{"type": CONFLICT_MISSING_MEDIA, "message": reason}])

        duration = self.duration
        if duration <= 0:
            reason = f"This program doesn't have a usable duration, so it can't be {verb}."
            return ValidationResult(False, reason, [{"type": CONFLICT_INVALID_DURATION, "message": reason}])

        destination_end = self.destination_end
        if destination_end <= now:
            reason = "That time has already aired, so nothing new can be scheduled there."
            return ValidationResult(False, reason, [{"type": CONFLICT_OUTSIDE_EDITABLE_RANGE, "message": reason}])

        overlapped = draft.programs_overlapping(self._destination_channel_id, self._destination_start, destination_end)
        overlapped = [
            candidate
            for candidate in overlapped
            if not any(_block_identity_matches(candidate, replaced) for replaced in self._replace_blocks)
        ]
        if overlapped:
            titles = [candidate.title for candidate in overlapped]
            if len(titles) == 1:
                overlap_start = max(self._destination_start, overlapped[0].true_start)
                overlap_end = min(destination_end, overlapped[0].true_end)
                overrun = max(0.0, overlap_end - overlap_start)
                message = f"“{block.title}” would overlap “{titles[0]}” by {_minutes_label(overrun)}."
            else:
                joined = ", ".join(f"“{title}”" for title in titles)
                message = f"“{block.title}” would overlap {joined}."
            conflicts = [
                {"type": CONFLICT_OVERLAPS_DESTINATION, "message": message, "overlapping_blocks": overlapped}
            ]
            return ValidationResult(False, message, conflicts)

        return ValidationResult(True)

    def apply(self, draft):
        if not self._replace_changes and self._replace_blocks:
            for replaced in self._replace_blocks:
                existing = _draft_add_change_for_block(draft, replaced)
                if existing is not None:
                    self._replace_changes.append(("cancel", existing))
                else:
                    change = draft.new_change(
                        OVERRIDE_ACTION_REMOVE,
                        replaced.channel_id,
                        replaced.true_start,
                        replaced.true_end,
                        title=replaced.title,
                        group_id=id(self),
                        group_kind=self._kind,
                    )
                    self._replace_changes.append(("remove", change))
        for kind, change in self._replace_changes:
            if kind == "cancel":
                draft.remove_change(change.change_id)
            else:
                draft.apply_change(change)

        if self._add_change is None:
            path = (self._source_block.raw_entries[0] or {}).get("path", "") if self._source_block.raw_entries else ""
            self._add_change = draft.new_change(
                OVERRIDE_ACTION_ADD,
                self._destination_channel_id,
                self._destination_start,
                self.destination_end,
                title=self._source_block.title,
                path=path,
                media_type=self._source_block.media_type or "tv",
                group_id=id(self),
                group_kind=self._kind,
            )
        draft.apply_change(self._add_change)

    def undo(self, draft):
        if self._add_change is not None:
            draft.remove_change(self._add_change.change_id)
        for kind, change in reversed(self._replace_changes):
            if kind == "cancel":
                draft.apply_change(change)
            else:
                draft.remove_change(change.change_id)


def _sequential_cursor_meta(entry):
    """The `autofill_meta` a lineup entry should carry onto its
    DraftChange, or None. Only "Continue Sequentially" placements need
    this (autofill_planner.plan_continue_sequentially tags each of its
    placements with strategy="sequential" and a show_key) -- Best Fit
    Mix/Show Marathon/Random Mix entries have no strategy tag and so
    never produce cursor-tracked metadata, since only Continue
    Sequentially has a "next episode" to remember (autofill_cursor.py).
    """
    if entry.get("strategy") != "sequential":
        return None
    show_key = entry.get("show_key")
    if not show_key:
        return None
    return {
        "strategy": "sequential",
        "show_key": show_key,
        "season_number": entry.get("season_number"),
        "episode_number": entry.get("episode_number"),
    }


class AutoFillBlockCommand:
    """Fills a selected Open Time block with an entire generated lineup
    (Phase 4, Auto-Fill Block) as ONE atomic, undoable command. `lineup`
    is a proposed lineup from autofill_planner.py -- an ordered list of
    {path, title, duration, media_type, start, end} placements with
    absolute times already assigned. This command never decides WHAT
    fills the block; it only ever turns an already-chosen lineup into
    draft changes, the same division of labor PutOnAirCommand has for
    Fill Open Time (planner/picker choose, command applies).

    Atomicity: `validate()` and `apply()` share one internal check
    (`_check`) that walks every lineup item against the CURRENT draft
    state. `apply()` re-runs it before creating any DraftChange, so a
    caller that skipped validate() (or whose draft changed between
    preview and Apply Lineup) still can't leave a partial lineup behind
    -- it raises instead of writing anything. Every add-change shares
    one `group_id` (this command's own id) and `group_kind="autofill"`,
    so Pending Changes/undo/redo treat the whole generated lineup as
    exactly one row, same mechanism MoveProgramCommand/
    DuplicateProgramCommand already use for their own multi-change groups.
    """

    def __init__(self, channel_id, block_start, block_end, lineup):
        self._channel_id = channel_id
        self._block_start = float(block_start)
        self._block_end = float(block_end)
        self._lineup = list(lineup or [])
        self._add_changes = []  # created once (first apply), reused across redo

    @property
    def description(self):
        count = len(self._lineup)
        return f"Auto-Fill Block ({count} program{'' if count == 1 else 's'})"

    @property
    def channel_id(self):
        return self._channel_id

    @property
    def time_range(self):
        return (self._block_start, self._block_end)

    def command_change_id(self):
        """The first add-change this command owns, or None before it has
        ever been applied -- same "any one change in the group identifies
        the whole group" contract MoveProgramCommand/DuplicateProgramCommand
        rely on for remove_pending_change().
        """
        return self._add_changes[0].change_id if self._add_changes else None

    def _check(self, draft, now):
        """Every reason the whole lineup can't apply, shared by validate()
        and apply()'s own defensive re-check. Returns a ValidationResult;
        never mutates the draft.
        """
        lock_reason = draft.lane_lock_reason(self._channel_id)
        if lock_reason:
            return ValidationResult(False, lock_reason, [{"type": CONFLICT_PROTECTED_BLOCK, "message": lock_reason}])

        if not self._lineup:
            return ValidationResult(False, "There's nothing to fill this block with yet.")

        if self._block_end <= now:
            reason = "This time has already aired, so it can't be auto-filled."
            return ValidationResult(False, reason, [{"type": CONFLICT_OUTSIDE_EDITABLE_RANGE, "message": reason}])

        cursor = self._block_start
        for entry in self._lineup:
            title = entry.get("title") or "This item"
            start = float(entry.get("start", 0) or 0)
            end = float(entry.get("end", 0) or 0)

            if start + 0.01 < cursor or start < self._block_start - 0.01 or end > self._block_end + 0.01:
                reason = f"“{title}” doesn't fit inside the selected block."
                return ValidationResult(False, reason, [{"type": CONFLICT_OUTSIDE_EDITABLE_RANGE, "message": reason}])
            cursor = end

            path = str(entry.get("path", "") or "")
            if not path:
                reason = f"“{title}” doesn't have a playable media file behind it, so this block can't be filled."
                return ValidationResult(False, reason, [{"type": CONFLICT_MISSING_MEDIA, "message": reason}])

            duration = float(entry.get("duration", 0) or 0)
            if duration <= 0 or abs((start + duration) - end) > 1.0:
                reason = f"“{title}” doesn't have a usable duration, so this block can't be filled."
                return ValidationResult(False, reason, [{"type": CONFLICT_INVALID_DURATION, "message": reason}])

            overlapped = draft.programs_overlapping(self._channel_id, start, end)
            if overlapped:
                titles = ", ".join(f"“{block.title}”" for block in overlapped)
                reason = f"“{title}” would overlap {titles}."
                conflict = {"type": CONFLICT_OVERLAPS_EXISTING, "message": reason, "overlapping_blocks": overlapped}
                return ValidationResult(False, reason, [conflict])

        return ValidationResult(True)

    def validate(self, draft, now=None):
        now = time.time() if now is None else now
        return self._check(draft, now)

    def apply(self, draft):
        if not self._add_changes:
            check = self._check(draft, time.time())
            if not check.ok:
                raise ValueError(f"Auto-Fill Block can no longer be applied: {check.reason}")
            group_id = id(self)
            built = [
                draft.new_change(
                    OVERRIDE_ACTION_ADD,
                    self._channel_id,
                    float(entry["start"]),
                    float(entry["end"]),
                    title=entry.get("title", ""),
                    path=entry.get("path", ""),
                    media_type=entry.get("media_type", "tv") or "tv",
                    group_id=group_id,
                    group_kind="autofill",
                    autofill_meta=_sequential_cursor_meta(entry),
                )
                for entry in self._lineup
            ]
            self._add_changes = built
        for change in self._add_changes:
            draft.apply_change(change)

    def undo(self, draft):
        for change in reversed(self._add_changes):
            draft.remove_change(change.change_id)


class ClearChannelDayCommand:
    """Replaces one channel's entire local calendar day with Open Time,
    as ONE atomic, undoable command (Phase 4.5.2) -- a single
    OVERRIDE_ACTION_REMOVE DraftChange spanning [day_start, day_end),
    the exact same mechanism PullProgramCommand already uses for one
    block, just with a whole day's wall-clock interval instead of one
    program's. Interval-anchored, not content-anchored (same as every
    saved override -- see schedule_overrides.py's module docstring), so
    it never depends on which generated blocks happened to exist when
    this command ran; no new saved-override schema or live-playback
    change is needed for it to persist and resolve correctly (Phase
    4.5.2 investigation).

    Deliberately never deletes or rewrites any other pending DraftChange
    on this channel/day -- it only ever adds this one change, which
    masks everything under its span by being the most recent change
    (last-edit-wins, same rule every command here already follows).
    That means undo is always exact: removing this one change instantly
    un-masks whatever was there before, with nothing to reconstruct.
    """

    def __init__(self, channel_id, day_start, day_end):
        self._channel_id = channel_id
        self._day_start = float(day_start)
        self._day_end = float(day_end)
        self._change = None  # created once, reused across redo

    @property
    def description(self):
        weekday = time.strftime("%A", time.localtime(self._day_start))
        return f"Clear {weekday}’s Day"

    @property
    def channel_id(self):
        return self._channel_id

    @property
    def time_range(self):
        return (self._day_start, self._day_end)

    def command_change_id(self):
        return self._change.change_id if self._change is not None else None

    def validate(self, draft, now=None):
        now = time.time() if now is None else now
        lock_reason = draft.lane_lock_reason(self._channel_id)
        if lock_reason:
            return ValidationResult(False, lock_reason, [{"type": CONFLICT_PROTECTED_BLOCK, "message": lock_reason}])
        if self._day_end <= self._day_start:
            return ValidationResult(False, "That isn't a valid day to clear.")
        if self._day_end <= now:
            reason = "This day has already fully passed, so it can't be cleared."
            return ValidationResult(False, reason, [{"type": CONFLICT_OUTSIDE_EDITABLE_RANGE, "message": reason}])
        return ValidationResult(True)

    def apply(self, draft):
        if self._change is None:
            self._change = draft.new_change(
                OVERRIDE_ACTION_REMOVE,
                self._channel_id,
                self._day_start,
                self._day_end,
                group_id=id(self),
                group_kind="clear_day",
            )
        draft.apply_change(self._change)

    def undo(self, draft):
        if self._change is not None:
            draft.remove_change(self._change.change_id)


class CommandHistory:
    """Undo/redo stacks over an ordered command list. execute() assumes
    the caller already validated; a new command after Undo clears the
    redo branch (standard editor semantics, spec section 5).
    """

    def __init__(self):
        self._undo_stack = []
        self._redo_stack = []

    def execute(self, command, draft):
        command.apply(draft)
        self._undo_stack.append(command)
        self._redo_stack = []

    def undo(self, draft):
        if not self._undo_stack:
            return None
        command = self._undo_stack.pop()
        command.undo(draft)
        self._redo_stack.append(command)
        return command

    def redo(self, draft):
        if not self._redo_stack:
            return None
        command = self._redo_stack.pop()
        command.apply(draft)
        self._undo_stack.append(command)
        return command

    @property
    def can_undo(self):
        return bool(self._undo_stack)

    @property
    def can_redo(self):
        return bool(self._redo_stack)

    @property
    def undo_description(self):
        return self._undo_stack[-1].description if self._undo_stack else ""

    @property
    def redo_description(self):
        return self._redo_stack[-1].description if self._redo_stack else ""

    def clear(self):
        self._undo_stack = []
        self._redo_stack = []

    def remove_pending_change(self, change_id, draft):
        """Undo one specific currently-pending change (a Pending Changes
        row's "Undo This Change" action) without touching any other
        change, and without the arbitrary-history-surgery risk of just
        splicing the command out of the stack.

        Safe model: find the command in the undo stack that currently
        owns `change_id` (redo-stack commands are already-undone, not
        pending, so they're not eligible); rebuild the draft's change-set
        from scratch by replaying every OTHER already-applied command, in
        their original order, against a cleared draft. Each apply() is
        deterministic and re-derives its effect from the draft state at
        that point, so replaying in original order reproduces exactly
        what would have happened had the removed command never run --
        including its knock-on effects on later commands (e.g. a later
        Pull that was cancelling out an earlier Put On Air's add-change).

        Clears the redo branch, same as any new mutating action: the
        removed command (and anything that depended on it) is no longer a
        coherent "next" step to redo.

        Returns the removed command (truthy) so callers can restore
        selection to wherever it belongs -- e.g. a MoveProgramCommand's
        source location -- or None if `change_id` wasn't found among the
        currently-pending commands.
        """
        index = next(
            (i for i, command in enumerate(self._undo_stack) if command.command_change_id() == change_id),
            None,
        )
        if index is None:
            return None
        removed = self._undo_stack[index]
        remaining = self._undo_stack[:index] + self._undo_stack[index + 1:]
        draft.clear_changes()
        for command in remaining:
            command.apply(draft)
        self._undo_stack = remaining
        self._redo_stack = []
        return removed

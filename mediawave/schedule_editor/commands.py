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

# The one shared snap-to-time interval for Move To…, drag placement math,
# and command validation, so all three can never disagree about where a
# placement actually lands. Not user-configurable yet (spec: later phases
# may offer other increments; this phase ships one fixed default).
SNAP_INTERVAL_SECONDS = 5 * 60


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

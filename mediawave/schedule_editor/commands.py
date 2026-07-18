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


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""  # plain-language, user-facing
    conflicts: list = field(default_factory=list)  # [{"type", "message", ...}]


def _minutes_label(seconds):
    minutes = max(1, round(abs(seconds) / 60))
    return f"{minutes} minute" + ("" if minutes == 1 else "s")


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

    def _find_draft_add_change(self, draft):
        for change in draft.changes:
            if (
                change.action == OVERRIDE_ACTION_ADD
                and change.channel_id == self._block.channel_id
                and change.start == self._block.true_start
                and change.end == self._block.true_end
            ):
                return change
        return None

    def apply(self, draft):
        if self._block.source == "draft" and self._block.media_type != "open":
            existing = self._find_draft_add_change(draft)
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

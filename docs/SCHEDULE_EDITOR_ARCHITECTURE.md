# Schedule Editor Architecture

Phase 2 introduced draft editing on top of the Phase 1 read-only board.
Phase 2.1 added change review and saved-override management on top of
that: a Pending Changes summary, safe per-change undo, a multi-change Save
Review, clearer board/inspector state labels, a Saved Changes manager, and
override compaction. Phase 3 added the first direct-manipulation workflow:
moving an existing program to a new time, via both a guided Move To…
dialog and dragging the program card itself. This note documents the
schedule-state layers, the draft/override design, and the policies the
editor follows. It is the reference for later phases (resizing, recurring
edits, bulk tools, cross-channel moves).

## The four schedule-state layers

MediaWave distinguishes four layers, from most automatic to most manual:

**1. Generated lineup** — the authoritative automatic schedule.
`apply_channel_schedules` (channelsurfer2000.py) builds one looping entry
list per media channel (lineup order + commercial pods) and caches it by
signature in `schedule_state.json`. Each live `Channel` object resolves
wall-clock time against that loop with modular arithmetic
(`schedule_anchor` + entry durations). The Schedule Editor never rewrites
this layer; it remains authoritative underneath every edit.

**2. Draft lineup** — `mediawave/schedule_editor/draft_model.py`. A
temporary, Qt-free change-set used only while the Schedule Editor is open:
cloned base lanes (plain dataclasses copied from the read-only board
model) plus an ordered list of `DraftChange` records. Draft mutations
never touch live playback, channel queues, generated caches, persisted
state, or runtime timers — the draft holds no references to any of them.
Closing or navigating away runs the Save / Discard / Keep Editing flow
(`ScheduleEditorWorkspace.confirm_leave`, also invoked by
`AdvancedConfigDialog.reject`), so unsaved edits are never silently
applied or dropped.

**3. Saved overrides** — `mediawave/schedule_overrides.py` and
`schedule_overrides.json`. The durable representation of intentional
edits: small per-date records, one per surviving draft change, rather than
a serialization of the whole timeline. Two actions exist in Phase 2:

    remove — nothing generated airs in [start, end); shown as Open Time
    add    — this media airs in [start, end)

Records carry `{action, channel_id, date, start, end, title, path,
media_type}` plus a file-level `version` (schema versioning). Writes are
atomic (tempfile + `os.replace`), validated before replacing existing
data, and records from long-past dates are pruned on save. Malformed
files load as empty without being rewritten or deleted.

**4. Live playback state** — what is on air right now. Draft editing
never touches it. Saved overrides reach playback only through
`Channel.get_current()`'s normal resolution, which is consulted at
tune-in and at end-of-media program advance — never mid-program.

## Override semantics

- **Time-slot anchored, per-date.** Generated entries have no stable
  per-entry IDs, but the wall-clock slot is deterministic (anchor and
  shuffle seed persist in `schedule_state.json`), so an override means
  "override what airs at this absolute time on this date". Absolute epoch
  intervals make edits inherently one-date-only; recurring edits are a
  later phase. If the generated schedule is later rebuilt (catalog or
  commercial settings changed), an override still claims the same
  wall-clock slot — intentional, documented behavior.
- **Last edit wins.** Overrides apply sequentially in file order (Save
  appends in edit order). Each record masks its interval out of
  everything below it — base programming and earlier overrides alike.
  This is the one precedence rule shared by the window splice
  (`splice_overrides_into_window`), instant resolution (`override_at`),
  and the draft presentation (`DraftSchedule.presentation_lanes`), so the
  draft preview and the saved result always agree.
- **Open Time is an explicit item, not a hole.** The TV Guide's slot
  builder assumes contiguous window items, so a removed interval becomes
  a synthetic `kind: "open_time"` item ("Open Time" in the guide, a
  dashed quiet block in the editor). Open slots are presentation-layer
  objects, never fake persisted programs.
- **Partial masking = joined in progress.** A generated program partially
  covered by an override keeps its surviving piece at real wall-clock
  times; playback's untouched modular math resumes it mid-media exactly
  where the timeline says — real-broadcast "join in progress" semantics,
  with no rewriting of the generated entries.

## Where overrides are applied

`apply_schedule_overrides_to_channels` (channelsurfer2000.py) attaches
each media channel's records to its live `Channel` object after every
`apply_channel_schedules` run (startup, catalog reload, settings apply).
`Channel.get_programs_for_window` (guide + editor board),
`get_current_entry_and_offset` (playback), and `get_now_next` (banners)
consult them; with no overrides attached, every path is byte-for-byte the
pre-Phase-2 behavior. Overrides survive restart because the file is
loaded at startup and re-applied with the schedules.

## Command architecture

`mediawave/schedule_editor/commands.py` — deliberately small and
schedule-specific, not a generic framework:

- `PullProgramCommand` / `PutOnAirCommand`: each owns validate →
  apply → undo, a human-readable description ("Pull “Viva La Bam”"),
  affected channel/time range, and produces exactly one `DraftChange`.
  Pulling an unsaved Put On Air removes that add-change instead of
  stacking a remove (so the save set stays minimal).
- `CommandHistory`: undo/redo stacks; a new command after Undo clears the
  redo branch; descriptions feed the toolbar tooltips.
- `ValidationResult` reasons are complete, user-facing sentences.

Later drag-and-drop/resize commands should follow the same shape.

## Save pipeline

Save Schedule → `DraftSchedule.overrides_for_save()` (minimal records, in
edit order) → `save_schedule_overrides_from_editor` (channelsurfer2000.py):
append to the in-memory data, validate, write atomically, reload,
re-apply to live channels, invalidate the guide-row cache. On any
failure, the in-memory state rolls back and the editor keeps its dirty
draft and full Undo history. The generated schedule cache
(`schedule_state.json`) is never rewritten by a save.

## Current-program policy

Saved changes apply to upcoming programming; the currently playing
program is never stopped or replaced. Playback re-resolves only at
program boundaries (end-of-media) and channel tunes, so a change covering
"now" takes effect when the current program ends — the editor says so
after such a save. A channel tuned into a saved open-time gap stops
playback with a friendly "open time until …" status and arms a one-shot
re-tune for when the gap ends (`schedule_open_time_retune`).

## Companion channel policy (Phase 2)

- **WeatherStar** — read-only: programming is generated live by the
  weather service.
- **RadioWaveTV** — read-only this phase: its continuous music mix has no
  per-block identities to override cleanly yet.
- **NetTV** — read-only this phase: playlist videos have durations but
  the playlist itself is remote and re-orderable, so stable overrides
  need more groundwork.

Reasons live in `draft_model.COMPANION_LOCK_REASONS` and are shown
verbatim (Editing Tools hint line, and rejection dialogs), so an
unavailable action always explains itself.

## Conflict model (Phase 2 scope)

Validation produces plain-language conflicts:
overlaps-following-program, outside-editable-range (already aired),
protected block (companions/commercial pods), invalid media duration,
missing source media. Supported resolutions are exactly: cancel, choose
something else, leave the remaining gap open, or explicitly Extend Into
Following Time (which masks the overlapped program's start — joined in
progress afterward). **Deferred intentionally:** auto-shifting later
programs, truncating media, auto-fill of gaps, replace-with-reflow, and
any automatic conflict resolution.

## Pending Changes (Phase 2.1)

The right-column "Pending Changes" card (`utility_panels.build_pending_changes_card`)
is a pure VIEW over `DraftSchedule.describe_pending_changes()` — it holds no
list of its own, so it can never drift from the real change model (spec
section 10). Each row is friendly text only ("Pulled “Viva La Bam”" / "Put
“Samurai Cop” on air" plus a channel/time subline) — no command class
names, change ids, or raw paths ever reach the UI. A clean draft shows the
calm "No unsaved changes" state, never an empty list with no explanation.

**Undoing one specific pending change** ("Undo This Change" per row) does
not splice a command out of the undo stack directly — that would risk
corrupting history ordering if a later command's effect depended on it
(e.g. a Pull that cancels out an earlier Put On Air's add-change). Instead
`CommandHistory.remove_pending_change` rebuilds the draft by clearing it
and replaying every OTHER still-applied command, in original order,
against the cleared draft. Each command's `apply()` re-derives its effect
from the draft state at that point, so replaying reproduces exactly what
would have happened had the removed command never run — including
cascading through cancel-out chains. This clears the redo branch, the same
as any new mutating action.

## Save Review (Phase 2.1)

`ScheduleEditorWorkspace._save_clicked` shows a review
(`_confirm_save_review`) only when there is more than one pending change —
a single simple edit stays a one-click save. The review lists a friendly
bullet per change ("Pull “X” from CH 4", "Put “Y” on CH 4") and states
explicitly that the changes apply to one date only, never a recurring
rule. Choices are Save Schedule / Keep Editing / Cancel; the latter two
both simply return to editing without saving.

## Board and inspector state labels (Phase 2.1)

Every block's `source` (`"generated"` | `"draft"` | `"override"`) drives a
small corner badge (`program_block._badge_spec`) and the inspector's origin
line (`utility_panels.build_selected_program_footer`) — the same
source/path logic backs both, so they can never disagree:

| source                              | board badge         | inspector label                  |
|--------------------------------------|----------------------|-----------------------------------|
| generated                            | none                 | "Auto-generated schedule"         |
| draft, real program                  | `DRAFT`              | "Your unsaved schedule edit"      |
| draft, open time                     | `DRAFT`              | "Open time from unsaved edit"     |
| override, real program (media found) | `SAVED`              | "Scheduled by you"                |
| override, open time                  | `SAVED`              | "Open time"                       |
| override, media missing (Phase 2.1)  | `NEEDS ATTENTION`    | "Saved change needs attention"    |

Badges are corner pills at the "wide" content tier only — they never cover
a title, and selection (the yellow border) stays the strongest visual cue
regardless of source.

## Saved Changes manager (Phase 2.1)

`mediawave/schedule_editor/saved_changes_manager.py`'s
`SavedChangesManagerDialog` (opened via the toolbar's "Saved Changes"
button) lists every saved override for the currently viewed date, grouped
by channel in board order. Each row shows friendly text and one action:
"Remove Change" for a saved add, "Restore Generated Schedule" for a saved
pull — both are the same underlying action
(`remove_schedule_override_from_editor` in channelsurfer2000.py: locate
the exact record, delete it, atomically rewrite, reload, re-apply to live
channels). A failed removal leaves the saved schedule untouched and shows
a recoverable error; nothing is removed from the in-memory list until the
write actually succeeds. The manager reads override data through a getter,
not a snapshot, since a successful removal reassigns the whole
`schedule_overrides_data` dict.

## Unresolved overrides (Phase 2.1)

A saved *add* override can go stale after saving — its target media may
move, get renamed, or be deleted from the catalog. `override_media_status`
(`mediawave/schedule_overrides.py`) reports `"unresolved"` when an add
override's path no longer exists on disk (checked via an injected
predicate, so it stays testable without touching a filesystem); remove-type
overrides (a saved Pull) have no media to look up and are always
`"resolved"`. This phase intentionally supports only two actions on an
unresolved override — **Remove Saved Change** and **Keep for Later** (a
no-op dismissal) — no replacement-media repair flow. Detection is a
display-layer concern only: it does not change how `get_current`/the
splice resolve at playback time, since the existing playback failure/retry
paths already handle a missing file gracefully (this is not new
Phase-2.1-introduced risk — a *generated* program can already reference
deleted media the same way).

## Override compaction (Phase 2.1)

Saves are append-only (`save_schedule_overrides_from_editor` never rewrites
older records), so repeated editing sessions on the same time range can
accumulate several fully-superseded records over time (an add later fully
pulled; the same slot replaced again on a later visit). `compact_overrides`
(`mediawave/schedule_overrides.py`) collapses the accumulated list to its
minimal equivalent before every save: grouped by channel, it walks records
in order, sequentially masking each record's interval out of every earlier
record's still-surviving pieces (reusing `subtract_interval`, the same
sequential-mask primitive the splice and draft presentation already use),
so compaction can never change what a channel resolves to at any instant —
it only ever removes records that are already entirely hidden. Adjacent
surviving pieces with the same action/payload are merged back together
purely for file readability. Compaction never merges across a genuine gap
(a real dependent ordering — e.g. add, then a partial pull creating a real
hole in the middle, then the same add's tail) — the pieces separated by a
different action's piece stay distinct.

## Moving a program (Phase 3)

`mediawave/schedule_editor/commands.py`'s `MoveProgramCommand` is the one
command behind both interactions this phase adds -- there is no second
mutation path for dragging. It is internally equivalent to a Pull at the
source plus a Put On Air at the destination (reusing the exact same
"cancel an unsaved add in place, or create a real remove" choice
`PullProgramCommand` already makes, via the shared
`_draft_add_change_for_block` helper both commands call), but behaves as
ONE user action everywhere it's visible:

- **Pending Changes / Save Review**: every `DraftChange` a move produces
  (the source pull, any replaced-destination removes, and the destination
  add) is tagged with the same `move_id` (`DraftChange.move_id`, set to
  `id(self)` on the command instance). `DraftSchedule.describe_pending_changes()`
  collapses a shared `move_id` into one "Moved …" row instead of separate
  Pull/Put On Air rows; Save Review renders the identical rows as its
  bullets, so the two can never disagree. `move_id` is a draft-only,
  in-memory tag -- it never reaches `overrides_for_save()`'s output, so
  the persisted override schema is unaffected by it.
- **Undo/Redo**: restores/reapplies the whole move (source location,
  every replaced block, and the destination) as one step, including
  through `CommandHistory.remove_pending_change`'s per-change-undo replay.
- **Saved overrides**: on Save, a plain move persists as the minimal
  remove (old placement) + add (new placement) pair; `compact_overrides`
  (Phase 2.1) then handles collapsing that against any OLDER saved
  placement for the same slot on a later save, exactly as it already does
  for repeated Put On Air/Pull edits.

**Same-channel only.** A channel's catalog, duration cache, and airing
context are channel-scoped; moving media's identity safely across that
boundary needs groundwork this phase doesn't establish. `MoveProgramCommand.validate()`
rejects a cross-channel destination with "Moving programs between
channels will be added later." -- both Move To… and drag enforce this
identically, since both call the same `validate()`.

**Move To…** (`mediawave/schedule_editor/move_to_dialog.py`) is the
guided, non-drag reference implementation, built and tested BEFORE
dragging so there is always a precise, pointer-free way to move a program
(keyboard users, motor-limitation accessibility, exact time entry, or
just a preference for dialogs). It only ever changes the time (a
`QTimeEdit`, snapped via the shared `snap_to_interval`), never the channel
or date -- the destination channel is shown as fixed, read-only text.

**Snap-to-time.** `commands.snap_to_interval` (default 5 minutes) is the
one shared primitive for Move To…, drag placement math
(`ProgrammingBoard._channel_and_time_at`), and command validation, so all
three can never disagree about where a placement actually lands. Not
user-configurable this phase.

**Conflict and replacement.** `MoveProgramCommand.validate()` reports a
`CONFLICT_OVERLAPS_DESTINATION` conflict listing every block the
destination would actually overlap (not just the first). The workspace's
`_ask_move_conflict` offers exactly Choose Another Time / Replace
Overlapping Program / Cancel -- no automatic ripple/reflow of surrounding
programs. Replacing constructs a NEW `MoveProgramCommand` with those
specific blocks passed as `replace_blocks`, which the caller has already
explicitly approved; validate() then treats exactly those overlaps as
resolved (matched by channel/start/end, since blocks have no other stable
identity across a presentation rebuild) rather than reporting them again.
Undo restores the moved program's original spot AND every replaced
program, all as part of undoing the one move command.

**Open Time.** Moving a program away leaves Open Time at the source
(the pull's own interval). Moving into Open Time consumes exactly the
program's own duration from that interval; if the interval is larger, the
remainder stays open. A destination that's part open, part an existing
generated program is a normal overlap conflict against that program --
Open Time itself is never something you can "conflict" with.

**Drag-and-drop** (`program_block.py`, `channel_row.py`, `board.py`) is a
purely mechanical, visual front end for the identical command/validation
path: `ProgramBlockWidget` tracks mouse press/move/release and only
declares a drag once the pointer has moved past
`QApplication.startDragDistance()` (so an ordinary click still just
selects, per spec section 7) and the block is draggable (not open time,
not a commercial pod, and only on a "media"-type, has-data lane -- the
same companion policy `draft_model.channel_lock_reason` already enforces,
computed once per lane in `ChannelRowStrip` and passed down). Drag/move/
finish signals bubble widget → row strip → `ProgrammingBoard`, which owns
ALL interpretation: mapping a global pointer position to `(channel_id,
snapped_start)` (`_channel_and_time_at`, scroll-offset-aware since it maps
through the actual widget hierarchy), rendering a translucent placement
preview colored for valid/conflict/invalid (never color alone -- each
state also carries a label), and a small edge-zone autoscroll timer on
both axes. The board never mutates the draft itself: a drop only emits
`move_drop(source_block, channel_id, start)`, which the workspace routes
through the exact same `_try_move`/conflict-resolution path Move To…
uses. Escape cancels an active drag with no draft mutation.

**Accessibility.** Move To… is never removed or hidden in favor of
dragging -- it is the answer for keyboard users, motor-limitation
accessibility, precise time entry, and anyone who simply prefers a
dialog. Both paths validate identically because both are, underneath,
just `MoveProgramCommand`.

**Deferred**: duration/edge resizing, recurring or weekly moves, copying,
multi-selection, bulk movement, automatic ripple of surrounding programs,
cross-channel moves, and dragging directly from the Put On Air picker.

## User-language glossary

**Pull** — Remove a program from this date's lineup. Leaves Open Time.

**Put On Air** — Place library media into open time.

**Move Program** — Change when a program airs without changing its
length. Same channel and date only, for now.

**Move To…** — The guided, dialog-based way to move a program; also the
accessible alternative to dragging.

**Replace Overlapping Program** — Move the selected program into that
time and pull the program already there. Fully undoable as one step.

**Undo This Change** — Reverse one specific pending edit, leaving every
other pending edit untouched.

**Revert Draft** — Discard every unsaved change for this editing session
and return to the last saved (or originally generated) lineup. Never
touches saved overrides.

**Save Schedule** — Persist the current draft's changes as saved overrides
for this date only.

**Restore Generated Schedule** — Remove a saved manual change and return
that time to MediaWave's automatic schedule.

**Remove Change** — Remove a saved Put On Air; the time returns to
whatever the automatic schedule would otherwise put there.

**Open Time** — Time in the lineup that MediaWave may leave empty until
you place something there.

**Saved change needs attention** — A saved override's target media could
not be found in the current library.

## Testing

`tools/test_schedule_draft.py` covers the 25 Phase 2 scenarios: draft
isolation proofs (live `Channel` state untouched by editing), command
semantics, dirty/revert behavior, override persistence (reload survival,
malformed files, atomicity), companion protection, and workspace-level
save/leave flows. `tools/test_schedule_phase21.py` covers the 25 Phase 2.1
scenarios: Pending Changes correctness, safe per-change undo, Save Review
wording, board/inspector state labels, the Saved Changes manager, unresolved
overrides, and compaction (no-op pairs, repeated replacement, and preserved
dependent ordering). `tools/test_schedule_phase3.py` covers the 40 Phase 3
scenarios: move-command mechanics (one Pending Changes row, Undo/Redo,
minimal saved overrides), snap-to-5-minutes boundaries, Open Time
interaction, overlap/replace conflicts and their Undo, protected-channel
and missing-media rejection, moving unsaved-added vs. saved-override
blocks, cross-channel policy, and widget-level drag geometry (scroll-
offset-aware channel/time mapping, frozen-column exclusion, preview
valid/conflict/invalid styling, autoscroll start/stop, click-vs-drag
threshold, and rebuild-mid-drag safety). `tools/test_schedule_editor.py`
keeps the Phase 1 board/geometry coverage updated for the Phase 2 toolbar
and Editing Tools card (now including Move To…).

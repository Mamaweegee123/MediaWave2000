# Schedule Editor Architecture

Phase 2 introduced draft editing on top of the Phase 1 read-only board.
This note documents the schedule-state layers, the draft/override design,
and the policies the editor follows. It is the reference for later phases
(drag-and-drop, resizing, recurring edits, bulk tools).

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

## Testing

`tools/test_schedule_draft.py` covers the 25 Phase 2 scenarios: draft
isolation proofs (live `Channel` state untouched by editing), command
semantics, dirty/revert behavior, override persistence (reload survival,
malformed files, atomicity), companion protection, and workspace-level
save/leave flows. `tools/test_schedule_editor.py` keeps the Phase 1
board/geometry coverage updated for the Phase 2 toolbar and Editing Tools
card.

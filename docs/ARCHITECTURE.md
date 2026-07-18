# MediaWave Architecture Notes

MediaWave is still centered around `channelsurfer2000.py` during this safe refactor pass. The main window, playback control, guide and vault rendering, scheduler generation, NetTV, commercial playback, catalog behavior, settings flow, and release behavior remain there until they can be moved in small behavior-preserving steps.

## Modules

`mediawave/airing_rules.py`

Holds the Airing Rules data model: constants, defaults, normalization, validation, diagnostics, and summary text for Airing Rules and Channel Takeovers. It is intentionally headless and does not import Qt or launch the app.

`mediawave/core_io.py`

Holds small shared filesystem helpers: safe path normalization, JSON load/save, conservative directory checks, macOS `/Volumes` detection, and standard user-content folder creation. Runtime path decisions that depend on the app bundle or main script remain in `channelsurfer2000.py`.

`mediawave/themes.py`

Holds built-in theme names, palette definitions, token-building helpers, theme lookup helpers, and the framework-only custom theme schema. Rendering and widget-specific theme application remain in `channelsurfer2000.py`.

`mediawave/local_media.py`

Holds local filename/folder parsing helpers, title normalization, metadata lookup keys, and media lineup sort keys. It is used by Vault grouping, local metadata lookup, and opt-in sequential channel playback without importing Qt.

`mediawave/local_artwork.py`

Holds local artwork and description discovery, local asset-directory selection, and short-lived local artwork signature caches. It is intentionally separate from the broader file signature cache so changed posters/backgrounds can refresh quickly.

`mediawave/scheduling.py`

Holds pure lineup helpers for random and sequential channel playback, playback-order constants, and the shared half-hour live-channel schedule anchor.

`mediawave/schedule_overrides.py`

Holds the saved schedule-override model: per-date add/remove records from the Schedule Editor, schema-versioned atomic persistence, and the pure splice/resolution helpers that layer overrides onto the generated lineup. See `docs/SCHEDULE_EDITOR_ARCHITECTURE.md` for the full layer design (generated lineup / draft / saved overrides / live playback).

`mediawave/schedule_editor/`

The Schedule Editor workspace: the programming board (Phase 1) plus the Phase 2 draft layer (`draft_model.py`), Pull/Put On Air commands with undo/redo (`commands.py`), and the Put On Air catalog picker. Draft edits are isolated until Save Schedule persists them as overrides.

`mediawave/channel_logos.py`

Holds channel logo setting defaults, timing migration/normalization, placement option constants, and per-channel effective-setting resolution. Qt overlay drawing and logo image rendering remain in `channelsurfer2000.py`.

`tools/test_airing_rules.py`

Runs the Airing Rules smoke test against the extracted model module without importing the full application.

`tools/test_themes.py`

Runs the theme framework smoke test against `mediawave/themes.py` without launching the full application.

`tools/test_local_media.py`

Runs local media parsing and episode-order smoke tests against `mediawave/local_media.py`.

`tools/test_scheduling.py`

Runs smoke tests for channel lineup ordering and catalog playback-order settings.

`tools/test_channel_logos.py`

Runs smoke tests for channel logo placement settings and per-channel override normalization.

`tools/test_local_artwork.py`

Runs local artwork discovery and signature-refresh smoke tests against `mediawave/local_artwork.py`.

## Refactor Rules

Each extraction should stay narrow, preserve public behavior, update imports, run syntax checks and smoke tests, and land as its own commit. UI, playback, scheduling, NetTV, commercial, and release behavior should not move as part of low-risk model/helper extractions.

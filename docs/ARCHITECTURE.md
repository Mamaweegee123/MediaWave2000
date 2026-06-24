# MediaWave Architecture Notes

MediaWave is still centered around `channelsurfer2000.py` during this safe refactor pass. The main window, playback control, guide and vault rendering, scheduler generation, NetTV, commercial playback, catalog behavior, settings flow, and release behavior remain there until they can be moved in small behavior-preserving steps.

## Modules

`mediawave/airing_rules.py`

Holds the Airing Rules data model: constants, defaults, normalization, JSON load/save helpers, validation, diagnostics, and summary text for Airing Rules and Channel Takeovers. It is intentionally headless and does not import Qt or launch the app.

`tools/test_airing_rules.py`

Runs the Airing Rules smoke test against the extracted model module without importing the full application.

## Refactor Rules

Each extraction should stay narrow, preserve public behavior, update imports, run syntax checks and smoke tests, and land as its own commit. UI, playback, scheduling, NetTV, commercial, and release behavior should not move as part of low-risk model/helper extractions.

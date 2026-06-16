# MediaWave2000 — Developer Guide

Internal notes for working on the source repo. (For the user-facing app guide, see [README.md](../README.md).)

## Branches

- `main` — known-good, stable. Always buildable and releasable.
- `dev` — active integration branch for in-progress feature work.
- `feature/<name>` — large systems (e.g. the scheduling/custom programming system) branch off `dev`, merge back to `dev` when stable, and only land on `main` via a release.

## Running the app locally

```
source venv/bin/activate
python channelsurfer2000.py
```

Or just run `./run.command` (macOS), which activates `venv` and launches the app for you.

The Converter app runs the same way:

```
source venv/bin/activate
python mediawave_converter.py
```

## Versioning

- `APP_VERSION` in [channelsurfer2000.py](../channelsurfer2000.py) is the main app version.
- `DISPLAY_VERSION` in [mediawave_converter.py](../mediawave_converter.py) is the Converter's version.
- Bump these before cutting a release. Release scripts read/validate against them — they do not need to be edited anywhere else.
- Add a matching entry to [docs/CHANGELOG.md](CHANGELOG.md) for every version bump.

## Building

After changing root `channelsurfer2000.py` / `mediawave_converter.py`, sync the change out to the Windows/Linux build kits and rebuild the macOS staging folder:

```
python scripts/sync_release_targets.py
```

Pass `--assets` to also resync static asset folders (`assets/`, `logos/`, `docs/`, `hooks/`, `Fonts/`, `icons/`) into the build kits.

### macOS

1. Build the `.app` bundles with PyInstaller using the specs in `dev/`:
   ```
   pyinstaller dev/MediaWave2000.spec
   pyinstaller dev/MediaWaveConverter.spec
   ```
   Output lands in `dist/`.
2. Assemble a clean staging folder + zip:
   ```
   python scripts/assemble_mac_release.py
   ```
   or the more thorough private-beta packager (validates built `.app` version against source, checks for staleness):
   ```
   python scripts/prepare_private_beta_macos.py
   ```
   Both write into `release/` (gitignored).

### Windows

Build kit lives in `release/MediaWave-Windows-Build-Kit/`. After running `sync_release_targets.py`, build the `.exe`s there with PyInstaller, then assemble the portable folder:

```
python scripts/assemble_windows_portable.py
```

### Linux

Same idea via `release/MediaWave-Linux-Build-Kit/` and `scripts/assemble_linux_portable.py`.

## Cutting a release

1. Bump `APP_VERSION` / `DISPLAY_VERSION` as needed.
2. Add a `docs/CHANGELOG.md` entry.
3. Run `scripts/sync_release_targets.py` to push source/asset changes to all build kits.
4. Build and assemble each platform (above).
5. Sanity-check the assembled `release/` output, then zip/upload as appropriate.
6. Tag the commit and merge `dev` → `main` if the release is cut from `dev`.

## Where runtime data lives

These are gitignored and live at the repo root during local development (and under `User Content/` once packaged):

| File / folder | Purpose |
|---|---|
| `app_settings.json` | User app settings |
| `library.json`, `media_cache.json`, `catalog_cache.json` | Catalog/library scan cache |
| `schedule_state.json`, `resume_state.json` | Channel schedule + resume position state |
| `on_demand_catalog.json`, `catalog_validation.json` | Vault on-demand catalog data |
| `youtube_video_cache/`, `youtube_playlist_cache.json` | NetTV cache |
| `radiowave_metadata_cache.json` | RadioWave TV metadata cache |
| `thumbnails/`, `metadata_artwork/` | Cached artwork |
| `.mediawave_converter/` | Converter app working state |

Never commit these — they're user/runtime data, not source.

## Repo housekeeping

- `archive/` (gitignored) holds old backups and one-off artifacts moved out of the repo root during cleanup — safe to delete locally if you don't need them, but nothing in there was deleted outright.
- `release/` (gitignored) is build output only; always safe to wipe and regenerate via the scripts above.

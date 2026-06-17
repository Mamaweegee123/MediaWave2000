## Core Experience

- **Live TV simulation** — plays your media library as a continuously running channel lineup, scheduled in real time
- **Auto-scheduling** — generates a full program schedule from folder contents automatically, no configuration required
- **Folder-as-channel system** — each subfolder in your catalog becomes a named channel; the folder name is the channel name
- **Recursive file scanning** — finds video files nested in subfolders (Shows, Movies, Specials, etc.) automatically
- **Multi-format support** — plays `.mp4`, `.mkv`, `.avi`, `.mov`
- **External drive / NAS support** — catalog can live on any drive or network path the system can access
- **Multiple catalogs** — switch between different catalog folders at any time

---

## TV Guide

- **Scrollable program guide** — browse your full channel lineup with show names and schedules, in the style of classic digital cable
- **Real-time schedule** — guide reflects what's actually playing and what's coming up
- **Channel selection** — click or navigate to any channel from the guide to tune in immediately
- **Episode info overlay** — press a key while watching to see current show/episode info and the channel logo

---

## The Vault (On-Demand)

- **Browse-and-play mode** — a separate section for navigating your library like a traditional streaming service
- **Full library access** — watch anything in your catalog on demand, not just what's scheduled

---

## Commercial System

- **Commercial breaks** — plays short video clips between episodes or at timed intervals during playback
- **Two timing modes** — between episodes, or mid-roll on a timer
- **Density settings** — Light (1–2 ads), Normal (2–4 ads), Heavy (4–6 ads) per break
- **Custom commercial folder** — point it at any folder of clips; real VHS-ripped ads, bumpers, station IDs all work
- **Per-channel overrides** — different commercial settings per channel in Advanced Config
- **Graceful fallback** — if no commercials are found, playback continues silently without errors

---

## Channel Logos (Channel Bug System)

- **Per-channel watermark logos** — display a custom logo overlay on any channel
- **Flexible positioning** — place logo in any corner of the screen
- **Size control** — adjustable logo size
- **Grayscale mode** — option to display logo in grayscale
- **Text fallback** — if no logo image is found, displays channel name as text instead
- **Supported formats** — PNG, JPG, JPEG, BMP, GIF

---

## Visual Themes

Three complete visual themes, each with multiple color variants:

### Set-Top Box
- 80s/90s cable box aesthetic
- CRT-era typography and layout
- Color options: Stars of Uranus, Silver Olive, Get Slimed, Blue Berry

### Promised Future
- Mid-2000s digital optimism
- Clean but dated tech aesthetic
- Color options: Stars of Uranus, Silver Olive, Silver, Olive, Tangerine Dream, Purple Passion, Charcoal, Blue Berry

### Sleek Freak
- Modern flat UI
- Minimal, clean presentation
- Color options: Stars of Uranus, Silver Olive, Baby Blue, Grape Jelly, Millenial Grey - With Light and Dark mode variants

---

## Display Options

- **Aspect ratio modes** — Auto, 4:3 (Classic TV), Widescreen (16:9)
- **Display mode** — configurable to match different monitor types
- **CRT-friendly** — 4:3 mode designed for use with actual CRT TVs

---

## Companion Channels

Built-in channels that work alongside your own library:

### WeatherStar 4000+
- Local weather display channel in the style of the classic Weather Channel
- Shows current weather data

### RadioWave TV
- Plays your music library as a dedicated music channel
- Real-time audio visualizer that reacts to the music
- Point it at any folder of audio files

### NetTV *(Beta)*
- Paste a YouTube playlist URL to generate a live channel schedule
- Pulls video metadata and builds a schedule from the playlist contents
- Currently works intermittently — experimental

---

## EAS Message System *(In Progress)*

- **Scrolling alert messages** — display custom text banners across the screen in the style of Emergency Alert System broadcasts
- User-configurable message content
- 
- Currently in development

---

## Settings and Configuration

- **Main screen** — Choose Catalog, Display Mode selector, Watch TV button; usable immediately without any advanced setup
- **Advanced Config** — full settings menu for fine-tuning channels, commercials, logos, display, and companion channels
- **My Catalog** — per-channel enable/disable and override settings
- **Settings persistence** — settings saved to platform-standard app data location
- **Portable mode** — settings can be stored in the app folder for portable/external drive setups

---

## MediaWave Converter (Companion App)

A separate standalone app included with MediaWave2000:

- **Batch video conversion** — convert multiple files or whole folders at once
- **MP4, AVI, MKV** — encodes to a clean, widely compatible format
- **Aspect ratio presets** — Classic TV (4:3), Widescreen (16:9), Ultra Wide (21:9)
- **Letterbox/pillarbox removal** — automatically crops and scales to fill the target frame
- **Quality presets** — Best Picture, Balanced, Compact
- **Hardware encoding** — uses GPU acceleration if available; falls back to software
- **Audio Leveling** - Levels out any file to an equal audio level, no more turning up a movie and then turning down the commercials!
- **Audio language selection** — choose which audio track to keep from multi-track files
- **Subtitle burn-in** — optionally burn embedded subtitle tracks into the video image *(Experimental)*
- **Smart skip** — skips files already converted at the current settings
- **Mirrored output folder structure** — converted files maintain source folder organization
- **Powered by ffmpeg** — requires ffmpeg to be installed (Homebrew on Mac, PATH or local on Windows)

---

## Platform and Distribution

- **macOS** — available now
- **Windows** — available now
- **Linux** — in progress
- **Raspberry Pi** — planned (lightweight stripped-down build)
- **Steam / Steam Deck** — long-term aspiration

---

## Things That Are WIP or Planned

- EAS scrolling message system (in progress, partially working)
- NetTV / YouTube channel stability (in progress, works intermittently)
- Custom theme and font support (planned)
- Linux build (in progress)
- Raspberry Pi build (planned)
- Steam release (long-term)
- Community theme sharing (community goal post-launch)

---

*Last updated: v0.1.0 — [6-14-26]*

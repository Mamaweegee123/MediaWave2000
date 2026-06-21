# Welcome to MediaWave2000!

> **Turn your media library into a real cable TV experience.**

<img width="288" height="180" alt="Kapture 2026-06-14 at 21 13 51" src="https://github.com/user-attachments/assets/9cc72a69-b647-43a5-8338-ebb50590794f" />

Put your videos in folders, open MediaWave2000, and watch TV!

---

## What is this?

MediaWave2000 is a desktop app that transforms your local video collection into a fully functional fake cable channel system - complete with a scrollable TV guide, "On-Demand" Vault, scheduled programming, commercial breaks, and themed on-screen displays.

If you've ever tried **FieldStation42** and wanted something simpler to easily turn your media catalog into a working cable system, this was made for you. MediaWave2000 sets itself up automatically from your folder structure. No configuring schedules, no .json files, just folders!

---

## Screenshots

<img width="1440" height="900" alt="Screenshot 2026-06-20 at 2 11 32 PM" src="https://github.com/user-attachments/assets/37fc6849-83fe-4485-a5a9-d55a97720a40" />
<img width="1440" height="900" alt="Screenshot 2026-06-20 at 2 11 48 PM" src="https://github.com/user-attachments/assets/c3f3966b-ebc0-43c9-8472-e309c4a53f03" />
<img width="1440" height="900" alt="Screenshot 2026-06-20 at 2 12 09 PM" src="https://github.com/user-attachments/assets/0eacfe00-a23a-4682-97ba-2f0cb8cddf8f" />
<img width="1440" height="900" alt="Screenshot 2026-06-20 at 2 12 28 PM" src="https://github.com/user-attachments/assets/f5c1cd64-f09b-4b48-8ff8-6a24868bf067" />
<img width="1440" height="900" alt="Screenshot 2026-06-14 at 8 51 00 PM" src="https://github.com/user-attachments/assets/97149040-1a1e-4152-bc0e-461fc858d5f1" />

---

## Features

See [FEATURES.md](FEATURES.md) for the full list, but here's the basics:

- **Scrollable TV Guide** — browse your lineup like the old digital cable you know and love!
- **The Vault** — on-demand section, like a local streaming library
- **Auto-scheduling** — point it at a folder, it builds a channel. No config required.
- **Commercial system** — plays ad breaks between episodes or on a timer
- **Three visual themes** — 80s set-top box, mid-2000s "Promised Future," and modernized "Sleek Freak" — each with multiple color variants
- **Channel logos** — custom watermark per channel, with position and size control, timing, opacity and grayscale options
- **Companion channels** — WeatherStar connectivity, RadioWave TV (music visualizer), NetTV (YouTube playlists)
- **MediaWave Converter** — companion app to batch-prep files for smooth playback
- Works on **Mac**, **Windows**, and in the future, Linux.
- More always being worked on!

---

## Getting Started

### 1. Organize your media

Each subfolder in your catalog becomes a channel. The folder name is the channel name.
Ad-break folders named Commercials, Bumpers, Promos, or Station IDs are skipped
as channels and can be configured separately in Advanced Config.

```
My Catalog/
  HBO/
    The Sopranos/
      S01E01.mp4
  Cartoon Network/
    Futurama/
      S01E01.mp4
  MTV/
    music_video_01.mp4
```

That's it! No metadata files. No renaming. As simple as I could make it :)

### 2. Download and open MediaWave2000

→ **[Download the latest release](https://github.com/Mamaweegee123/MediaWave2000/releases)**

- **Mac:** Open `MediaWave.app`
- **Windows:** Run `MediaWave2000.exe`

### 3. Choose your catalog and watch TV

Hit **Choose Catalog**, point it at your folder, press **Watch TV**.

---

## Optional Setup

**Channel logos** — drop a `logo.png` inside a `Logos/` subfolder in any channel folder:
```
HBO/
  Logos/
    logo.png
```

**Commercials** — put short video clips in any folder and point MediaWave at it in Advanced Config. Real VHS-ripped ads work great.

**Custom music** — drop audio files in `User Content/Music/` for the RadioWave TV companion channel, or keep them wherever you have them and just simply point MediaWave to the folder in "Advanced Config".

Full setup guides are in the `docs/` folder inside the app.

---

## Themes

MediaWave2000 ships with three visual themes, each with multiple color options:

| Theme | Vibe |
|-------|------|
| **Set-Top Box** | 80s/90s cable box nostalgia |
| **Promised Future** | Mid-2000s digital optimism |
| **Sleek Freak** | Clean modern flat UI |

---

## Companion Channels

Beyond your own library, MediaWave includes three built-in channels:

- **WeatherStar 4000+** — a local weather display channel in the style of the classic Weather Channel
- **RadioWave TV** — plays your music library with a reactive audio visualizer
- **NetTV** *(beta)* — paste a YouTube playlist URL and it generates a live channel schedule from the videos

---

## MediaWave Converter

A separate app included with MediaWave2000. Drop video files onto it and it batch-converts them to .mp4, .mkv, or .avi with consistent framing — removes letterboxing, normalizes resolution and audio, handles subtitle burn-in. Useful for old MKVs, weird rips, or anything that doesn't quite play how you'd like.

Requires **ffmpeg** to be installed. See `docs/Converter Guide.txt` for setup.

---

## Platform Support

| Platform | Status |
|----------|--------|
| macOS | Available |
| Windows | Available |
| Linux | In Progress |
| Raspberry Pi | Planned |

---

## Roadmap

- [ ] Linux release
- [ ] Custom theme support
- [ ] EAS-style scrolling message system (in progress)
- [ ] NetTV stability improvements (in progress)
- [ ] Raspberry Pi lightweight build
- [ ] Steam / Steam Deck release (long-term)

---

## FAQ

**Do I need to convert all my files?**
Nope! Most modern video files play fine as-is. Use the Converter when something doesn't look right, or if you want all your files to be the same format, audio level etc.

**Can I use an external drive?**
Yes, your catalog can live anywhere your system can read — USB drive, NAS, network share, wherever.

**Does this connect to the internet?**
NetTV (YouTube) and WeatherStar 4000+ do, but Your video library stays local.

**Is this free?**
Yes. Free to download, no account required, no subscription.

---

## Developing MediaWave2000

MediaWave2000 came to be after I realized how cool **FieldStation42** was but wanted something that can automatically convert your entire catalog just by the click of a button and it kind of ballooned out to what it is now (with more features coming soon!). I really want this to be something completely customizeable by you and build a community where we can share our setups, custom themes (when implemented), and bring back the golden age of television! This is still a very early beta so feel free to reach out and let me know of anything you found that needs fixing or features you'd personally like to see! 

---

## Credits

Inspired by the concept behind [FieldStation42](https://github.com/shane-mason/FieldStation42) — built for everyone who loved the idea but couldn't get it working, and everyone who misses watching cable TV.

---

## Support MediaWave

MediaWave is a passion project built in my spare time to bring back the nostalgia of scrolling through a TV Guide!

If you've enjoyed using MediaWave and would like to support future development, you can buy me a coffee on Ko-fi:

**☕ Support MediaWave:** https://ko-fi.com/Mamaweegee123

Support is completely optional, but every contribution helps fund development, testing hardware, and future features. And keeping my belly full :)

Thank you for checking out MediaWave!

---

**NO copyrighted media is included with MediaWave 2000. Users must supply their own legally obtained media files.** *Pwease >.<*


*Tune in. Sit back. There's always something on.*

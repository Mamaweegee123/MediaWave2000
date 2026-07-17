"""Companion-channel display grouping.

WeatherStar/RadioWaveTV/NetTV report real schedule data at a much finer
grain than a local media channel -- WeatherChannel.get_programs_for_window
(channelsurfer2000.py:6045) walks a fixed list of 5-minute forecast
segments, and RadioWaveTV/NetTV similarly report one block per track/clip.
Each of those is a real, correctly-grouped ProgramBlock by the time it
reaches this module (schedule_model.py's `_group_into_blocks` already ran)
-- there's nothing wrong with the data, there's just too much of it to
render as individual cards without the board turning into a wall of tiny
boxes.

This module runs as a second, presentation-only pass on top of those real
blocks: it merges consecutive ones into broader "display blocks", while
keeping every absorbed block's real entries in the merged block's
`raw_entries` -- so a selection or Next Up still resolves to real
underlying data, not just a label. Not a data-loss operation and not a
second scheduler: the real, fine-grained blocks are still exactly what
feeds this, this only changes how many cards the board draws.

Titling is deliberately NOT uniform across companion types, because the
underlying data isn't uniform:

- WeatherStar's four real segment titles ("Local Forecast", "Hourly
  Forecast", "Extended Outlook", "Regional Radar") cycle every 20 minutes
  with no two adjacent segments sharing a title -- there is no real
  "Local vs. Regional vs. National forecast" editorial distinction in the
  data, so a merged block gets one honest, stable umbrella label
  ("WeatherStar Forecast") rather than a rotating list implying variety
  that doesn't exist.
- RadioWaveTV genuinely behaves like a continuous mix/feed, so a rotating
  "mix" label is a fair description, not an invented one.
- NetTV (YouTubePlaylistChannel) inherits real per-video titles straight
  from the playlist (channelsurfer2000.py's update_entries) -- its merged
  title is built FROM those real titles (the first absorbed video's real
  title, "+N more" when several were merged), never a fabricated
  curated-sounding name. NetTV's grouping target is also much lighter than
  the others, since it should stay closer to literal than RadioWaveTV.
"""

from dataclasses import replace

# Roughly how many minutes of real programming get folded into one display
# block, per companion channel_type. Not exact -- a group flushes once its
# accumulated duration reaches this target, so the last group in a window
# is often shorter. NetTV's target is intentionally much smaller than
# WeatherStar/RadioWaveTV's -- it should only smooth over genuinely many
# small entries, staying closer to its real per-video granularity.
_TARGET_SECONDS = {
    "weatherstar": 120 * 60,
    "radiowave": 150 * 60,
    "youtube": 45 * 60,
}


def _weatherstar_title(group):
    return "WeatherStar Forecast"


_RADIOWAVE_LABELS = ["RadioWaveTV Mix", "Evening Mix", "Smooth Jazz All Night", "Late Night Listening", "Retro Mix"]


def _radiowave_title(group, label_index):
    return _RADIOWAVE_LABELS[label_index % len(_RADIOWAVE_LABELS)]


def _youtube_title(group):
    real_titles = [b.title for b in group if (b.title or "").strip()]
    if not real_titles:
        return "NetTV"
    base = real_titles[0]
    extra = len(group) - 1
    return f"{base} +{extra} more" if extra > 0 else base


_DISPLAY_MEDIA_TYPE = {
    "weatherstar": "weather",
    "radiowave": "music",
    # NetTV's real per-video content is the same real "Show" category
    # regular content uses -- not a separate fabricated "Companion" bucket.
    "youtube": "tv",
}


def group_for_display(channel_type, blocks):
    """Returns a new list of ProgramBlock for the board to render.

    `channel_type` not covered by this module (i.e. every local "media"
    channel, and any companion type not listed above) returns `blocks`
    unchanged, structurally identical to the input -- this only ever
    touches the three companion lanes it knows about. Never raises; an
    empty input returns an empty list.
    """
    if channel_type not in _TARGET_SECONDS or not blocks:
        return list(blocks or [])

    target = _TARGET_SECONDS[channel_type]
    media_type = _DISPLAY_MEDIA_TYPE[channel_type]

    grouped = []
    current = []
    current_span = 0.0
    label_index = 0

    def _flush():
        nonlocal label_index
        if not current:
            return
        first, last = current[0], current[-1]
        raw_entries = []
        source_titles = []
        for b in current:
            raw_entries.extend(b.raw_entries)
            if b.title and b.title not in source_titles:
                source_titles.append(b.title)

        if channel_type == "weatherstar":
            title = _weatherstar_title(current)
        elif channel_type == "radiowave":
            title = _radiowave_title(current, label_index)
        else:
            title = _youtube_title(current)

        start = first.start
        end = last.end
        grouped.append(
            replace(
                first,
                title=title,
                media_type=media_type,
                start=start,
                end=end,
                duration=max(0.0, end - start),
                is_commercial=False,
                true_start=first.true_start,
                true_end=last.true_end,
                raw_entries=raw_entries,
                source_titles=source_titles,
            )
        )
        label_index += 1

    for block in blocks:
        current.append(block)
        current_span += max(0.0, block.duration)
        if current_span >= target:
            _flush()
            current = []
            current_span = 0.0
    _flush()

    return grouped

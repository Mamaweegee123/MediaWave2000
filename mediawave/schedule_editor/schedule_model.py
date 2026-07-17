"""Read-only presentation model for the Schedule Editor's programming board.

No Qt, no filesystem writes, no persistence -- this module only reads
already-computed schedule data off live `Channel` objects (see
`channelsurfer2000.py`'s `Channel.get_programs_for_window`, the same query
Channel Studio's "Tonight's Schedule" preview already uses) and reshapes it
for display. It never calls `Channel.set_schedule` or writes
`schedule_state.json` -- there is no mutation path into or out of this
module.

The one genuinely new piece of logic here is `_group_into_blocks`: a movie
with internal commercial breaks is stored by the real scheduling engine
(`build_channel_schedule_entries` in channelsurfer2000.py) as several
`kind: "content"` entries sharing one `path`, interleaved with commercial
entries carrying a `parent_path` back to that same path
(`mediawave/commercials.py`'s `is_commercial_entry`/`commercial_parent_path`).
Grouping consecutive window entries by that shared path turns them back into
one logical program block for the board -- a presentation regrouping, not a
second scheduler.

A second, later pass (`companion_display.group_for_display`) further merges
those already-real blocks for companion channels (WeatherStar/RadioWaveTV/
NetTV), which otherwise report many small real segments -- see that
module's docstring for why.
"""

from dataclasses import dataclass, field

from mediawave.commercials import commercial_parent_path, is_commercial_entry
from mediawave.local_media import parse_local_media

from .companion_display import group_for_display

# How many raw schedule entries to request per window-fetch attempt, and the
# hard cap on how far we'll double that request trying to reach window_end.
# Commercial pods can make individual entries very short (tens of seconds),
# so a multi-hour window can need several hundred raw entries; the cap keeps
# a pathological channel (e.g. an all-commercial loop) from growing this
# unbounded.
_INITIAL_FETCH_COUNT = 24
_MAX_FETCH_COUNT = 600

# Board time scale: how many horizontal pixels one minute of scheduled time
# occupies. A block's on-screen width is purely duration * PX_PER_MINUTE --
# no equal-width slots -- so a 60-minute program is always exactly twice as
# wide as a 30-minute one. Kept here (Qt-free) so geometry ratios are
# testable without a QApplication; program_block.py applies its own
# minimum-legible-width floor on top of this for rendering.
#
# 7.0 puts an ordinary 30-minute show at 210px -- comfortably inside the
# "wide" content tier (program_block.py's WIDE_CONTENT_MIN_PX=170), so a
# regular half-hour block reads its full title, time, and type without
# guide scrolling. The board scrolls horizontally (see board.py) rather
# than shrinking this to fit any particular viewport width.
PX_PER_MINUTE = 7.0


def block_width_px(duration_seconds, px_per_minute=PX_PER_MINUTE):
    """Exact, unfloored width for a duration -- the ratio between two
    durations' widths always matches the ratio between the durations
    themselves, at any px_per_minute.
    """
    return max(0.0, float(duration_seconds or 0) / 60.0 * px_per_minute)


@dataclass
class ProgramBlock:
    """One logical, on-screen program card -- may represent several raw
    schedule entries (a movie's segments plus its interleaved commercial
    pods) collapsed into a single block.
    """

    channel_id: str
    title: str
    media_type: str  # "tv" | "movie" | "commercial"
    start: float  # epoch seconds, clipped to the requested window
    end: float
    duration: float
    is_commercial: bool = False
    source: str = "generated"  # the only value real schedules produce today
    true_start: float = 0.0  # unclipped, for the details strip
    true_end: float = 0.0
    raw_entries: list = field(default_factory=list)
    # Real titles of whatever this block absorbed, in order -- only
    # populated by companion_display.group_for_display(). Distinct from
    # raw_entries because some channel types (WeatherChannel) don't attach
    # an "entry" sub-dict to their window items at all, so raw_entries alone
    # can't recover the real per-segment names a merged block stands in
    # for; this field exists specifically so the details strip can stay
    # honest about what a generic label like "WeatherStar Forecast" is
    # actually made of.
    source_titles: list = field(default_factory=list)


@dataclass
class ChannelLane:
    """One channel row's worth of programming for the requested window."""

    channel_id: str
    name: str
    number: int
    channel_type: str
    logo_path: str
    blocks: list = field(default_factory=list)
    has_data: bool = True


def _resolve_media_type(entry, path):
    """Classifies a content entry as "tv" or "movie" using the same pure
    filename parser (`parse_local_media`) the rest of the app already uses
    for metadata lookup -- never the TMDB-backed, I/O-heavy path. Falls back
    to "tv" for paths that don't parse (empty paths) or aren't real files at
    all -- companion channels report synthetic pseudo-paths like
    "weatherstar://hourly-forecast" (see WeatherChannel.get_programs_for_window
    in channelsurfer2000.py), which `parse_local_media`'s filename-pattern
    matching was never meant to classify, and would otherwise mislabel as a
    "movie" simply for not matching a TV-episode filename pattern.
    """
    if not path or "://" in path:
        return "tv"
    try:
        return parse_local_media(path).get("media_type", "tv") or "tv"
    except Exception:
        return "tv"


def _fetch_window_items(channel, window_start, window_end):
    """Pulls raw (path/title/entry/start/end) items from the channel's own
    `get_programs_for_window`, doubling the requested count until the last
    item's end covers `window_end` or `_MAX_FETCH_COUNT` is hit. Never
    raises -- a broken channel just yields an empty window.
    """
    count = _INITIAL_FETCH_COUNT
    try:
        items = channel.get_programs_for_window(window_start, count=count)
    except Exception:
        return []

    while items and items[-1].get("end", 0) < window_end and count < _MAX_FETCH_COUNT:
        count = min(_MAX_FETCH_COUNT, count * 2)
        try:
            items = channel.get_programs_for_window(window_start, count=count)
        except Exception:
            break

    return items or []


def _group_key(item):
    entry = item.get("entry") or {}
    path = entry.get("path", "") or item.get("path", "")
    return commercial_parent_path(entry, path) or path


def _group_into_blocks(channel_id, items):
    """Collapses consecutive raw window items sharing the same logical
    parent (see module docstring) into one ProgramBlock each.
    """
    blocks = []
    current_key = None
    current_items = []

    def _flush():
        if not current_items:
            return
        first, last = current_items[0], current_items[-1]
        entries = [it.get("entry") or {} for it in current_items]
        all_commercial = all(is_commercial_entry(e) for e in entries)
        content_entry = next((it for it in current_items if not is_commercial_entry(it.get("entry") or {})), first)
        content_path = (content_entry.get("entry") or {}).get("path", "") or content_entry.get("path", "")
        media_type = "commercial" if all_commercial else _resolve_media_type(content_entry.get("entry"), content_path)
        start = float(first.get("start", 0) or 0)
        end = float(last.get("end", start) or start)
        blocks.append(
            ProgramBlock(
                channel_id=channel_id,
                title=first.get("title") or "Untitled",
                media_type=media_type,
                start=start,
                end=end,
                duration=max(0.0, end - start),
                is_commercial=all_commercial,
                true_start=start,
                true_end=end,
                raw_entries=list(entries),
            )
        )

    for item in items:
        key = _group_key(item)
        if current_key is None or key == current_key:
            current_items.append(item)
            current_key = key
        else:
            _flush()
            current_items = [item]
            current_key = key
    _flush()

    return blocks


def _clip_to_window(blocks, window_start, window_end):
    """Trims the visible start/end of the first and last blocks to the
    window edges (rendering only -- true_start/true_end keep the real
    values for the details strip) and drops blocks entirely outside it.
    """
    clipped = []
    for block in blocks:
        if block.end <= window_start or block.start >= window_end:
            continue
        block.start = max(block.start, window_start)
        block.end = min(block.end, window_end)
        block.duration = max(0.0, block.end - block.start)
        clipped.append(block)
    return clipped


def build_channel_lane(channel_id, name, number, channel_type, logo_path, channel, window_start, window_end):
    """Builds one channel's lane for [window_start, window_end).

    `channel` may be None (e.g. a companion the user just enabled this same
    settings session, before the app has built a live object for it -- see
    ScheduleEditorWorkspace's docstring) or, defensively, a live object that
    doesn't implement `get_programs_for_window` at all. Mirrors the exact
    `hasattr` guard `build_tonight_schedule` already uses in
    channel_studio_adapter.py, rather than inventing per-segment data for a
    channel type that doesn't expose one. Never raises.
    """
    if channel is None or not hasattr(channel, "get_programs_for_window"):
        return ChannelLane(
            channel_id=channel_id,
            name=name,
            number=number,
            channel_type=channel_type,
            logo_path=logo_path,
            blocks=[],
            has_data=False,
        )

    items = _fetch_window_items(channel, window_start, window_end)
    if not items:
        return ChannelLane(
            channel_id=channel_id,
            name=name,
            number=number,
            channel_type=channel_type,
            logo_path=logo_path,
            blocks=[],
            has_data=False,
        )

    blocks = _group_into_blocks(channel_id, items)
    blocks = _clip_to_window(blocks, window_start, window_end)
    blocks = group_for_display(channel_type, blocks)

    return ChannelLane(
        channel_id=channel_id,
        name=name,
        number=number,
        channel_type=channel_type,
        logo_path=logo_path,
        blocks=blocks,
        has_data=True,
    )


def build_board_model(channel_rows, studio_channels_by_id, window_start, window_end):
    """Builds the full board: one ChannelLane per row, in the order given.

    `channel_rows` is a list of plain dicts already sorted into the real
    lineup order (see `sort_channel_rows`) -- each needs `channel_id`,
    `name`, `number`, `channel_type`, `logo_path`. `studio_channels_by_id`
    maps channel_id -> live Channel-like object (may be missing an id, or
    map to None -- both handled by `build_channel_lane`). Never raises;
    channels that fail individually just get an empty, has_data=False lane
    rather than aborting the whole board.
    """
    lanes = []
    for row in channel_rows or []:
        channel_id = row.get("channel_id", "")
        try:
            lane = build_channel_lane(
                channel_id,
                row.get("name", "Channel"),
                int(row.get("number", 0) or 0),
                row.get("channel_type", "media"),
                row.get("logo_path", ""),
                (studio_channels_by_id or {}).get(channel_id),
                window_start,
                window_end,
            )
        except Exception:
            lane = ChannelLane(
                channel_id=channel_id,
                name=row.get("name", "Channel"),
                number=int(row.get("number", 0) or 0),
                channel_type=row.get("channel_type", "media"),
                logo_path=row.get("logo_path", ""),
                blocks=[],
                has_data=False,
            )
        lanes.append(lane)
    return lanes


def sort_channel_rows(channel_rows):
    """Real channel number ascending, name as a stable tie-break -- the
    same single lineup-order rule channel_studio_pages.py's
    `_sorted_summaries` uses (local and companion channels together, no
    separate display-order state).
    """
    return sorted(channel_rows or [], key=lambda row: (int(row.get("number", 0) or 0), row.get("name", "")))

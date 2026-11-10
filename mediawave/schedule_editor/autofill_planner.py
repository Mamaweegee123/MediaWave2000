"""Auto-Fill Block planner (Phase 4).

Pure functions only: no Qt, no draft access, no mutation. Every plan_*
function takes plain catalog items (the same shape build_picker_catalog
already produces, plus the season_number/episode_number fields it now
carries) and a gap to fill, and returns a proposed lineup -- an ordered
list of {path, title, episode_label, media_type, duration, channel_name,
start, end} placements that exactly tile [gap_start, gap_start +
gap_duration) without overlapping. Nothing here ever touches a
DraftSchedule; AutoFillBlockCommand (commands.py) is the only thing that
turns a proposed lineup into real draft changes, same as every other
Schedule Editor command.

An item that would run past the remaining open time is simply not
chosen -- Auto-Fill Block never proposes a lineup that itself needs the
Extend Into Following Time conflict flow; it fills what it can and
reports leftover_seconds so the UI can say so honestly.
"""

import random

STRATEGY_BEST_FIT = "best_fit"
STRATEGY_SEQUENTIAL = "sequential"
STRATEGY_MARATHON = "marathon"
STRATEGY_RANDOM = "random"

STRATEGY_LABELS = {
    STRATEGY_BEST_FIT: "Best Fit Mix",
    STRATEGY_SEQUENTIAL: "Continue Sequentially",
    STRATEGY_MARATHON: "Show Marathon",
    STRATEGY_RANDOM: "Random Mix",
}


def _placement(item, start, strategy=None):
    """One proposed lineup entry. `strategy`, when given, is carried
    through onto the placement itself (not just the plan_* function's
    result) so a downstream consumer -- AutoFillBlockCommand, then
    dialog.py's Save Schedule hook -- can tell which placements came
    from Continue Sequentially without threading a second parallel list
    alongside the lineup. season_number/episode_number/show_key pass
    through from the source catalog item when present (harmless None
    for anything that isn't a sequenced TV episode); autofill_cursor.py
    is the only thing that ever reads them.
    """
    duration = float(item.get("duration", 0) or 0)
    placement = {
        "path": item["path"],
        "title": item["title"],
        "episode_label": item.get("episode_label", ""),
        "media_type": item.get("media_type", "tv"),
        "duration": duration,
        "channel_name": item.get("channel_name", ""),
        "start": start,
        "end": start + duration,
        "season_number": item.get("season_number"),
        "episode_number": item.get("episode_number"),
        "show_key": item.get("show_key"),
    }
    if strategy:
        placement["strategy"] = strategy
    return placement


def _result(lineup, gap_start, gap_duration):
    filled = sum(entry["duration"] for entry in lineup)
    return {
        "lineup": lineup,
        "gap_start": gap_start,
        "gap_duration": gap_duration,
        "filled_seconds": filled,
        "leftover_seconds": max(0.0, gap_duration - filled),
    }


def _schedulable(items):
    return [item for item in items if item.get("schedulable", True) and float(item.get("duration", 0) or 0) > 0]


def episode_sort_key(item):
    """Season/episode ordering with the same "unordered items sort last"
    fallback media_lineup_sort_key (local_media.py) uses -- kept as a
    small local copy rather than an import so the planner stays free of
    any dependency beyond plain dicts; the two must simply agree on
    the None -> 9999 fallback, not share code, since this only orders
    within one already-chosen show's episodes (a much narrower job than
    local_media's whole-catalog sort key).
    """
    season = item.get("season_number")
    episode = item.get("episode_number")
    try:
        season_number = int(season)
    except (TypeError, ValueError):
        season_number = 9999
    try:
        episode_number = int(episode)
    except (TypeError, ValueError):
        episode_number = 9999
    return (season_number, episode_number, item.get("path", ""))


def plan_best_fit_mix(items, gap_start, gap_duration, recent_paths=None):
    """Greedily choose whichever remaining item best fits the remaining
    time (closest-without-going-over first, then closest-over), avoiding
    picking the exact same path twice in a row when another choice fits
    equally well. Repeats across the lineup are otherwise fine -- a real
    station block often replays a short a second time to use up the tail.
    """
    pool = _schedulable(items)
    lineup = []
    remaining = float(gap_duration)
    cursor = float(gap_start)
    last_path = None
    while remaining > 0 and pool:
        candidates = [item for item in pool if float(item["duration"]) <= remaining]
        if not candidates:
            break
        non_repeat = [item for item in candidates if item["path"] != last_path]
        ranked_from = non_repeat or candidates
        ranked = sorted(
            ranked_from,
            key=lambda item: (
                remaining - float(item["duration"]),
                item["path"] not in (recent_paths or []),
                item["title"].lower(),
            ),
        )
        chosen = ranked[0]
        lineup.append(_placement(chosen, cursor))
        cursor += float(chosen["duration"])
        remaining -= float(chosen["duration"])
        last_path = chosen["path"]
    return _result(lineup, gap_start, gap_duration)


def plan_random_mix(items, gap_start, gap_duration, seed=None):
    """A randomized lineup that still fills the block well -- shuffles the
    schedulable pool, then walks it repeatedly (looping once exhausted),
    skipping anything that doesn't fit the remaining time and never
    repeating the immediately-previous path while another option is
    available.
    """
    pool = _schedulable(items)
    if not pool:
        return _result([], gap_start, gap_duration)
    rng = random.Random(seed)
    order = list(pool)
    rng.shuffle(order)

    lineup = []
    remaining = float(gap_duration)
    cursor = float(gap_start)
    last_path = None
    index = 0
    stalled_full_passes = 0
    since_progress = 0
    while remaining > 0 and stalled_full_passes < 2:
        item = order[index % len(order)]
        index += 1
        since_progress += 1
        if since_progress > len(order):
            stalled_full_passes += 1
            since_progress = 0
        if float(item["duration"]) > remaining:
            continue
        if item["path"] == last_path and len(order) > 1:
            continue
        lineup.append(_placement(item, cursor))
        cursor += float(item["duration"])
        remaining -= float(item["duration"])
        last_path = item["path"]
        since_progress = 0
        stalled_full_passes = 0
    return _result(lineup, gap_start, gap_duration)


def _fill_sequence(ordered_episodes, start_index, gap_start, gap_duration, strategy=None):
    lineup = []
    remaining = float(gap_duration)
    cursor = float(gap_start)
    count = len(ordered_episodes)
    if count == 0:
        return _result(lineup, gap_start, gap_duration)
    i = start_index % count
    passes_without_fit = 0
    for _ in range(count * 4):  # bounded: at most a handful of full loops
        if remaining <= 0:
            break
        item = ordered_episodes[i % count]
        i += 1
        if float(item["duration"]) > remaining:
            passes_without_fit += 1
            if passes_without_fit >= count:
                break
            continue
        lineup.append(_placement(item, cursor, strategy=strategy))
        cursor += float(item["duration"])
        remaining -= float(item["duration"])
        passes_without_fit = 0
    return _result(lineup, gap_start, gap_duration)


def plan_show_marathon(show_episodes, gap_start, gap_duration):
    """`show_episodes` is one show's episodes, already ordered (callers
    use episode_sort_key). Plays them in order, looping back to the
    first episode if the block is longer than the whole series.

    Not cursor-tracked (autofill_cursor.py) -- a marathon is an explicit
    one-off replay the user asked for, not "continue where this show
    left off", so its placements carry no strategy tag and Save Schedule
    never advances a Continue Sequentially cursor because of one.
    """
    ordered = _schedulable(show_episodes)
    return _fill_sequence(ordered, 0, gap_start, gap_duration)


def plan_rotate_shows(items, show_keys, gap_start, gap_duration, seed=None, show_behaviors=None, last_aired_path_by_show=None):
    """Fills [gap_start, gap_start + gap_duration) by rotating fairly
    through the shows named in `show_keys` (a Programming Block's own
    selection) -- every eligible show gets one turn before any show
    repeats, the turn order may be shuffled (seeded, deterministic for a
    given seed/catalog). A show with no schedulable TV episodes among
    `items`, or a show_key the catalog doesn't currently have at all
    (deleted/renamed media, or simply not selected by whoever built
    `items`), is skipped entirely -- never an error, and never mutates
    `show_keys`.

    WHICH SHOW gets a turn (fair rotation, the cycle_shows shuffle below)
    is completely unaffected by anything in this docstring's next
    paragraph -- Phase 5.6 only changes WHICH EPISODE a show contributes
    once it's already been given a turn.

    `show_behaviors` (Phase 5.6): {show_key: "sequential"|"random"|None},
    typically mediawave.show_identity.show_behavior_for's own per-show
    lookups, resolved by the caller (this stays pure/storage-agnostic,
    same contract plan_continue_sequentially's `last_aired_path` already
    has). A show with no entry, or None/"random"/anything unrecognized,
    keeps TODAY'S unchanged behavior: episode_sort_key order, seeded-
    shuffled per show, reshuffled (never simply repeating the last title
    back-to-back) on wraparound -- this is Channel Default's exact
    contract ("preserve the Programming Block's current deterministic
    episode queue behavior") and is ALSO good enough to satisfy Random
    Episodes' contract ("choose a random schedulable episode"), so both
    map onto the one existing mechanism rather than needing two.

    A show explicitly marked "sequential" instead draws from its
    episodes in plain, UNSHUFFLED episode_sort_key order, starting right
    after `last_aired_path_by_show.get(show_key)` (the same shared
    per-channel/per-show sequential cursor Schedule Show and sequential
    Auto-Fill already read via autofill_cursor.last_aired_path_for) --
    falling back to the very first episode when there's no cursor row, or
    it no longer matches anything in today's catalog. On wraparound it
    restarts from the first episode again, in the same order, rather than
    reshuffling -- a rerun episode is still the NEXT one in sequence, not
    a random pick. Each such placement is tagged strategy="sequential"
    (same tag plan_continue_sequentially's placements already carry), so
    it flows through the EXISTING _sequential_cursor_meta/save-only-
    advances plumbing (commands.py, dialog.py) with no new cursor and no
    new advance-timing logic -- preview/undo/a failed save already never
    advance a "sequential"-tagged placement's cursor today, and that stays
    true here with zero additional code.

    This is the gap-filling counterpart to mediawave.scheduling.
    show_balanced_random_order: that helper permutes an entire channel's
    file pool losslessly (nothing is ever skipped), which only works
    because a live channel's lineup has no fixed end. Auto-Fill always
    fills one bounded gap instead, so here an episode that wouldn't fit
    in the remaining time is simply skipped for this fill (matching
    every other plan_* function's fits-or-skip contract) -- the show
    that owned it just doesn't get a turn that cycle rather than
    forcing an over-length placement.
    """
    show_behaviors = show_behaviors or {}
    last_aired_path_by_show = last_aired_path_by_show or {}

    wanted = [key for key in dict.fromkeys(show_keys or []) if key]
    schedulable_by_show = {}
    for item in _schedulable(items):
        show_key = item.get("show_key")
        if item.get("media_type") != "tv" or show_key not in wanted:
            continue
        schedulable_by_show.setdefault(show_key, []).append(item)
    eligible = [key for key in wanted if schedulable_by_show.get(key)]
    if not eligible:
        return _result([], gap_start, gap_duration)

    def _is_sequential(show_key):
        return show_behaviors.get(show_key) == "sequential"

    def _ordered_queue(show_key):
        return sorted(schedulable_by_show[show_key], key=episode_sort_key)

    def _fresh_queue(show_key, salt=""):
        ordered = _ordered_queue(show_key)
        seed_text = f"{seed}::{show_key}::{salt}" if seed is not None else f"{show_key}::{salt}"
        random.Random(seed_text).shuffle(ordered)
        return ordered

    def _swap_away_from(sequence, avoid_value):
        if len(sequence) < 2 or sequence[0] != avoid_value or avoid_value is None:
            return
        for i in range(1, len(sequence)):
            if sequence[i] != avoid_value:
                sequence[0], sequence[i] = sequence[i], sequence[0]
                return

    def _initial_queue_and_position(show_key):
        if not _is_sequential(show_key):
            return _fresh_queue(show_key), 0
        ordered = _ordered_queue(show_key)
        last_path = last_aired_path_by_show.get(show_key)
        position = 0
        if last_path is not None:
            for index, episode in enumerate(ordered):
                if episode.get("path") == last_path:
                    position = index + 1
                    break
        if position >= len(ordered):
            position = 0
        return ordered, position

    cycle_rng = random.Random(seed)
    per_show_queue = {}
    per_show_position = {}
    for key in eligible:
        queue, position = _initial_queue_and_position(key)
        per_show_queue[key] = queue
        per_show_position[key] = position
    per_show_last_path = {key: None for key in eligible}
    wrap_counters = {key: 0 for key in eligible}

    lineup = []
    remaining = float(gap_duration)
    cursor = float(gap_start)
    last_show_of_previous_cycle = None
    show_count = len(eligible)
    stalled_cycles = 0

    while remaining > 0 and stalled_cycles < 2:
        cycle_shows = list(eligible)
        cycle_rng.shuffle(cycle_shows)
        if show_count > 1:
            _swap_away_from(cycle_shows, last_show_of_previous_cycle)

        placed_this_cycle = 0
        for show_key in cycle_shows:
            queue = per_show_queue[show_key]
            position = per_show_position[show_key]
            if position >= len(queue):
                wrap_counters[show_key] += 1
                if _is_sequential(show_key):
                    queue = _ordered_queue(show_key)
                else:
                    queue = _fresh_queue(show_key, salt=f"wrap{wrap_counters[show_key]}")
                    _swap_away_from(queue, per_show_last_path[show_key])
                per_show_queue[show_key] = queue
                position = 0
            item = queue[position]
            per_show_position[show_key] = position + 1
            duration = float(item.get("duration", 0) or 0)
            if duration <= 0 or duration > remaining:
                continue
            strategy = "sequential" if _is_sequential(show_key) else None
            lineup.append(_placement(item, cursor, strategy=strategy))
            cursor += duration
            remaining -= duration
            per_show_last_path[show_key] = item.get("path")
            placed_this_cycle += 1
        last_show_of_previous_cycle = cycle_shows[-1] if cycle_shows else last_show_of_previous_cycle
        stalled_cycles = 0 if placed_this_cycle else stalled_cycles + 1

    return _result(lineup, gap_start, gap_duration)


def plan_continue_sequentially(show_episodes, gap_start, gap_duration, last_aired_path=None):
    """Same as Show Marathon, except it starts after whichever episode
    was last placed here (`last_aired_path` -- resolved by the caller;
    typically autofill_cursor.last_aired_path_for(), never looked up by
    the planner itself, which stays pure and storage-agnostic). Falls
    back to the first episode when there's no match, e.g. this show has
    never been auto-filled on this channel before, or the stored episode
    no longer exists in today's catalog.

    Every placement is tagged strategy="sequential" so
    AutoFillBlockCommand (commands.py) can mark its DraftChanges for the
    cursor to pick up again once Save Schedule actually commits them --
    this function itself persists nothing.
    """
    ordered = _schedulable(show_episodes)
    if not ordered:
        return _result([], gap_start, gap_duration)
    start_index = 0
    if last_aired_path:
        match = next((i for i, item in enumerate(ordered) if item["path"] == last_aired_path), None)
        if match is not None:
            start_index = (match + 1) % len(ordered)
    return _fill_sequence(ordered, start_index, gap_start, gap_duration, strategy="sequential")

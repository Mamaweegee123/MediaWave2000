"""Shared tick-time generator: both the ruler (board.py) and each row's
gridlines (channel_row.py) need to agree on exactly which timestamps get a
mark, so this lives in one place neither module owns exclusively --
importing either from the other would be circular (board.py already
imports channel_row.py).
"""

from .layout_constants import TICK_INTERVAL_SECONDS


def tick_times(window_start, window_end):
    tick = window_start - (window_start % TICK_INTERVAL_SECONDS)
    if tick < window_start:
        tick += TICK_INTERVAL_SECONDS
    while tick < window_end:
        yield tick
        tick += TICK_INTERVAL_SECONDS

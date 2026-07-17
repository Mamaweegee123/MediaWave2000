"""Shared pixel geometry for the programming board's widget layer.

Kept in one Qt-agnostic module (imported, not re-derived, by board.py,
channel_row.py, and program_block.py) so the frozen-header/frozen-column
math in board.py always agrees with what channel_row.py/program_block.py
actually draw.
"""

# One channel row's height, including its vertical margin. Taller than
# Phase 1's 68px -- chunkier rows read as a curated lineup board rather
# than a dense spreadsheet grid.
ROW_HEIGHT = 80
ROW_VERTICAL_MARGIN = 8

# The fixed identity column's width -- wide enough for a two/three-digit
# phosphor channel number, a logo, and a short name without truncating a
# typical channel name.
IDENTITY_COLUMN_WIDTH = 200

# The time-ruler header's height. Tall enough for the 12px, vertically
# centered time labels to breathe -- the header should read as a proper
# guide ruler, not a thin strip of small text.
TIME_HEADER_HEIGHT = 42

# The category-legend strip's height (between the top bar and the board).
LEGEND_HEIGHT = 34

# How often the time ruler places a tick/label, and (matching) how often
# the grid body draws a faint vertical gridline -- kept as one shared
# constant so the two can never drift out of alignment with each other.
TICK_INTERVAL_SECONDS = 30 * 60

# A program block never renders narrower than this, regardless of how short
# its real duration is (a 15-second commercial stays clickable/legible
# rather than collapsing to a sliver) -- this is a rendering floor only, it
# never affects the exact duration-proportional width math in
# schedule_model.block_width_px.
MIN_BLOCK_WIDTH_PX = 26

# Horizontal gap left between adjacent blocks so a border is always visible
# even when two programs are perfectly back-to-back in time.
BLOCK_GAP_PX = 2

# Width thresholds (px) below which a ProgramBlockWidget drops to a lower
# content-detail level. See program_block.py's _content_level.
WIDE_CONTENT_MIN_PX = 170
MEDIUM_CONTENT_MIN_PX = 100
NARROW_CONTENT_MIN_PX = 50

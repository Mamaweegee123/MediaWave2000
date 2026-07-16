"""Shared pixel geometry for the programming board's widget layer.

Kept in one Qt-agnostic module (imported, not re-derived, by board.py,
channel_row.py, and program_block.py) so the frozen-header/frozen-column
math in board.py always agrees with what channel_row.py/program_block.py
actually draw.
"""

# One channel row's height, including its vertical margin.
ROW_HEIGHT = 68
ROW_VERTICAL_MARGIN = 6

# The fixed identity column's width -- wide enough for a two/three-digit
# phosphor channel number, a logo, and a short name without truncating a
# typical channel name.
IDENTITY_COLUMN_WIDTH = 200

# The time-ruler header's height.
TIME_HEADER_HEIGHT = 32

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

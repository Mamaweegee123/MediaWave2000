"""Centralized Studio spacing constants.

The values below are exactly what Channel Studio already used inline
(StudioSection's card padding, channel_setup.py's page margins, ...) --
naming them here doesn't change a single pixel, it just gives future Studio
tools (Schedule Editor, Artwork Manager, ...) one place to match instead of
re-guessing the numbers from scratch. Not every screen has a clean existing
equivalent for every constant below (see PREVIEW_SPACING) -- those are
documented for the next tool that needs them rather than retrofitted onto
code that doesn't have an obvious home for them yet.
"""

# A workspace page's own outer margin -- see channel_setup.py's page_layout
# (`page_layout.setContentsMargins(*OUTER_MARGIN)`).
OUTER_MARGIN = (24, 20, 24, 20)

# A StudioSection card's inner content padding (left, top, right, bottom).
CARD_PADDING = (20, 18, 20, 20)

# Vertical gap between a card's header and its body content.
SECTION_SPACING = 10

# Gap between adjacent controls within a card body (e.g. StudioSection's
# body_layout, a settings row's own internal spacing).
CONTROL_SPACING = 8

# Gap between a preview surface (e.g. Logo Studio's TV screen) and the
# controls beside/below it -- not yet wired into an existing screen; the
# next Studio tool with a PreviewCard is the first real consumer.
PREVIEW_SPACING = 12

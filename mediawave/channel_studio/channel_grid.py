"""The responsive channel dashboard grid for Channel Studio's Choose
Channel page.

Built on the existing FlowLayout rather than QGridLayout: each card has
a fixed width (see channel_card.CARD_WIDTH), so the row naturally packs
two cards when there's room and drops to one per row when there isn't
— no manual column-count math, no clipping.

Cards are laid out in exactly the order `cards` arrives in -- this
module has no ordering opinion of its own. The caller (see
channel_studio_pages.py's _sorted_summaries) is the single source of
truth for that order: real channel number, ascending. There is no
drag-and-drop here, on purpose -- channel number is the only way to
move a channel's position.
"""

from .channel_studio_widgets import FlowLayout
from PySide6.QtWidgets import QWidget


def build_channel_grid(cards):
    """Lay out already-built dashboard cards in a wrapping grid."""
    grid_widget = QWidget()
    layout = FlowLayout(grid_widget, margin=0, h_spacing=16, v_spacing=16)
    for card in cards:
        layout.addWidget(card)
    return grid_widget

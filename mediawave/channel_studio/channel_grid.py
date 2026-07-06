"""The responsive channel dashboard grid for Channel Studio's Choose
Channel page.

Built on the existing FlowLayout rather than QGridLayout: each card has
a fixed width (see channel_card.CARD_WIDTH), so the row naturally packs
two cards when there's room and drops to one per row when there isn't
— no manual column-count math, no clipping.

Future drag-reorder hook point: this module is the one place that
decides card order today (the order `cards` arrives in, which mirrors
`summary.number`). A later pass can make this order mutable — e.g. by
tracking an in-memory list of channel ids here, updating it on drop,
and rebuilding the FlowLayout from that list — without touching
channel_card.py or the Choose Channel page that calls this function.
Any such reordering should stay preview-only (in-memory) until a real,
explicit persistence design is agreed on: no channel-number writes, no
settings/schedule changes, no folder changes.
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

"""One channel's row on the programming board: a fixed identity cell
(number, logo, name, accent strip) plus a horizontally-positioned strip of
ProgramBlockWidgets. Two separate widgets on purpose -- board.py keeps the
identity column pinned during horizontal scrolling and the block strip
scrolling, so they can never end up laid out inside the same scroll area.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from mediawave.channel_studio.studio_styles import CHANNEL_NUMBER_COLOR, channel_number_font_family

from .board_ticks import tick_times
from .layout_constants import IDENTITY_COLUMN_WIDTH, ROW_HEIGHT
from .program_block import ProgramBlockWidget
from .schedule_model import PX_PER_MINUTE

_GRIDLINE_COLOR = "rgba(255, 255, 255, 12)"

_ROW_BG = "rgba(16, 19, 44, 235)"
_ROW_BORDER = "rgba(255, 255, 255, 18)"
_NAME_COLOR = "rgba(210, 222, 252, 235)"
_SUBTITLE_COLOR = "rgba(138, 158, 212, 220)"

_ACCENT_BY_CHANNEL_TYPE = {
    "media": "rgba(68, 108, 235, 210)",
    "weatherstar": "rgba(96, 200, 255, 210)",
    "radiowave": "rgba(96, 200, 255, 210)",
    "youtube": "rgba(96, 200, 255, 210)",
}
_DEFAULT_ACCENT = "rgba(68, 108, 235, 210)"


class ChannelIdentityCell(QFrame):
    """The fixed-width, pinned-during-horizontal-scroll identity column for
    one channel row.
    """

    selected = Signal(str)  # channel_id

    def __init__(self, lane, parent=None):
        super().__init__(parent)
        self.channel_id = lane.channel_id
        self.setFixedSize(IDENTITY_COLUMN_WIDTH, ROW_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("scheduleIdentityCell")

        accent = _ACCENT_BY_CHANNEL_TYPE.get(lane.channel_type, _DEFAULT_ACCENT)
        self.setStyleSheet(
            "QFrame#scheduleIdentityCell {"
            f" background: {_ROW_BG};"
            f" border-bottom: 1px solid {_ROW_BORDER};"
            f" border-left: 3px solid {accent};"
            "}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)

        # A 44px number lane: wide enough that a centered one- OR
        # two-digit number gets symmetric breathing room (34px left the
        # big OSD digits visually crowding the lane's edges instead of
        # reading as centered against the name/logo block beside them).
        number_lbl = QLabel(str(lane.number or ""))
        number_lbl.setFixedWidth(44)
        number_lbl.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        # Same VHS/VCR OSD font-loading path and phosphor-green treatment
        # Channel Studio's own channel numbers use (channel_card.py's
        # _build_channel_number_label) -- reused via the two public
        # ingredients (channel_number_font_family, CHANNEL_NUMBER_COLOR)
        # rather than re-approximated, so both tools read as the same
        # product and share the same safe font-missing fallback.
        base_size = number_lbl.font().pointSize()
        number_lbl.setFont(QFont(channel_number_font_family(), base_size + 5, QFont.Bold))
        # AlignVCenter centers the font's full line box, but digits only
        # occupy [baseline - capHeight, baseline] of it -- with this OSD
        # font's tall ascent, that leaves the visible glyphs floating above
        # the row's true center. The glyph block sits (ascent - descent -
        # capHeight)/2 above center, so padding the top by twice that
        # re-centers what's actually drawn.
        fm = number_lbl.fontMetrics()
        drop = max(0, fm.ascent() - fm.descent() - fm.capHeight())
        number_lbl.setStyleSheet(
            f"color: {CHANNEL_NUMBER_COLOR}; background: transparent; padding-top: {drop}px;"
        )
        glow = QGraphicsDropShadowEffect(number_lbl)
        glow.setColor(QColor(CHANNEL_NUMBER_COLOR))
        glow.setBlurRadius(16)
        glow.setOffset(0, 0)
        number_lbl.setGraphicsEffect(glow)
        row.addWidget(number_lbl)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        text_col.addStretch(1)

        if lane.logo_path:
            pixmap = QPixmap(lane.logo_path)
            if not pixmap.isNull():
                logo_lbl = QLabel()
                logo_lbl.setPixmap(pixmap.scaledToHeight(22, Qt.SmoothTransformation))
                text_col.addWidget(logo_lbl)

        name_lbl = QLabel(lane.name)
        name_lbl.setStyleSheet(f"color: {_NAME_COLOR}; font-weight: 600; font-size: 13px; background: transparent;")
        fm = name_lbl.fontMetrics()
        # Available name width = column minus margins (10+10), the number
        # lane (44), and the layout spacing (10).
        name_lbl.setText(fm.elidedText(lane.name, Qt.ElideRight, IDENTITY_COLUMN_WIDTH - 74))
        name_lbl.setToolTip(lane.name)
        text_col.addWidget(name_lbl)

        if not lane.has_data:
            status_lbl = QLabel("No scheduled breakdown")
            status_lbl.setStyleSheet(f"color: {_SUBTITLE_COLOR}; font-size: 9px; background: transparent;")
            text_col.addWidget(status_lbl)

        text_col.addStretch(1)
        row.addLayout(text_col, 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.channel_id)
        super().mousePressEvent(event)


class ChannelRowStrip(QWidget):
    """The scrolling strip of ProgramBlockWidgets for one channel, sized to
    the full board window width and positioned by real start time.
    """

    block_widget_selected = Signal(object)  # the ProgramBlockWidget instance

    def __init__(self, lane, window_start, window_end, px_per_minute=PX_PER_MINUTE, parent=None):
        super().__init__(parent)
        self.channel_id = lane.channel_id
        total_minutes = max(0.0, (window_end - window_start) / 60.0)
        self.setFixedSize(round(total_minutes * px_per_minute), ROW_HEIGHT)
        self.setObjectName("scheduleRowStrip")
        self.setStyleSheet(
            f"QWidget#scheduleRowStrip {{ background: {_ROW_BG}; border-bottom: 1px solid {_ROW_BORDER}; }}"
        )

        # Faint vertical gridlines at each time tick, added before the
        # program blocks so they only show through in the gaps between
        # cards (each ProgramBlockWidget's outer slot is transparent
        # outside its inset card -- see program_block.py) rather than
        # cutting across card faces.
        for tick in tick_times(window_start, window_end):
            x = round((tick - window_start) / 60.0 * px_per_minute)
            gridline = QFrame(self)
            gridline.setGeometry(x, 0, 1, ROW_HEIGHT)
            gridline.setStyleSheet(f"background: {_GRIDLINE_COLOR};")
            gridline.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            gridline.show()

        self.block_widgets = []
        for block in lane.blocks:
            widget = ProgramBlockWidget(block, px_per_minute=px_per_minute, parent=self)
            x = round((block.start - window_start) / 60.0 * px_per_minute)
            y = (ROW_HEIGHT - widget.height()) // 2
            widget.move(max(0, x), y)
            widget.selected.connect(lambda _block, w=widget: self.block_widget_selected.emit(w))
            widget.show()
            self.block_widgets.append(widget)

        if not lane.has_data:
            placeholder = QLabel("Continuous programming — no scheduled breakdown available", self)
            placeholder.setStyleSheet(f"color: {_SUBTITLE_COLOR}; font-size: 11px; background: transparent;")
            placeholder.move(12, (ROW_HEIGHT - placeholder.sizeHint().height()) // 2)
            placeholder.show()

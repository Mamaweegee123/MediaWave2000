"""One channel's row on the programming board: a fixed identity cell
(number, logo, name, accent strip) plus a horizontally-positioned strip of
ProgramBlockWidgets. Two separate widgets on purpose -- board.py keeps the
identity column pinned during horizontal scrolling and the block strip
scrolling, so they can never end up laid out inside the same scroll area.
"""

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from mediawave.channel_studio.studio_styles import CHANNEL_NUMBER_COLOR, channel_number_font_family

from .board_ticks import tick_times
from .layout_constants import IDENTITY_COLUMN_WIDTH, ROW_HEIGHT
from .program_block import ProgramBlockWidget
from .schedule_model import PX_PER_MINUTE

_GRIDLINE_COLOR = "rgba(255, 255, 255, 12)"

_ROW_BG = "rgba(16, 19, 44, 235)"
_ROW_BORDER = "rgba(255, 255, 255, 18)"
_ROW_SELECTED_BG = "rgba(96, 144, 255, 30)"
_NAME_COLOR = "rgba(210, 222, 252, 235)"
_SUBTITLE_COLOR = "rgba(138, 158, 212, 220)"

_ACCENT_BY_CHANNEL_TYPE = {
    "media": "rgba(68, 108, 235, 210)",
    "weatherstar": "rgba(96, 200, 255, 210)",
    "radiowave": "rgba(96, 200, 255, 210)",
    "youtube": "rgba(96, 200, 255, 210)",
}
_DEFAULT_ACCENT = "rgba(68, 108, 235, 210)"
_SELECTED_ACCENT = "rgba(150, 190, 255, 255)"

_NUMBER_LANE_WIDTH = 44


def _ink_centered_origin(font_metrics, text, box_width, box_height):
    """The QPainter.drawText pen origin that centers `text`'s real ink --
    QFontMetrics.boundingRect(), not the advance-width box AlignHCenter/
    AlignVCenter use -- within a box_width x box_height box.

    Digital/pixel-styled fonts (like the shared VHS/VCR OSD font) routinely
    have uneven left/right glyph bearing that differs per character --
    measured for this font, "1" has a 3px left / 7px right bearing, "6" has
    0px left / 3px right, while two-digit numbers land close to symmetric.
    Centering the advance box (what AlignHCenter does) therefore centers a
    different amount of *dead space* around each string's ink, so different
    numbers visually land at different horizontal positions even though
    they're all nominally "centered". Centering the measured ink rect
    itself is exact regardless of bearing, and correct for any string.
    """
    ink = font_metrics.boundingRect(text)
    pen_x = (box_width - ink.width()) / 2.0 - ink.x()
    pen_y = (box_height - ink.height()) / 2.0 - ink.y()
    return pen_x, pen_y


class _ChannelNumberBadge(QWidget):
    """Paints a channel number using its measured ink bounding box (see
    `_ink_centered_origin`) rather than relying on Qt.AlignCenter, which
    only centers the font's advance-width box and drifts per-digit for
    this font's uneven glyph bearing. Same VHS/VCR OSD font-loading path
    and phosphor-green color Channel Studio's own channel numbers use
    (channel_card.py's _build_channel_number_label) -- reused via the two
    public ingredients (channel_number_font_family, CHANNEL_NUMBER_COLOR)
    rather than re-approximated.
    """

    def __init__(self, number, parent=None):
        super().__init__(parent)
        self._text = str(number or "")
        self.setFixedSize(_NUMBER_LANE_WIDTH, ROW_HEIGHT)
        base_size = self.font().pointSize()
        self._font = QFont(channel_number_font_family(), base_size + 5, QFont.Bold)

        glow = QGraphicsDropShadowEffect(self)
        glow.setColor(QColor(CHANNEL_NUMBER_COLOR))
        glow.setBlurRadius(16)
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(self._font)
        painter.setPen(QColor(CHANNEL_NUMBER_COLOR))
        pen_x, pen_y = _ink_centered_origin(painter.fontMetrics(), self._text, self.width(), self.height())
        painter.drawText(QPointF(pen_x, pen_y), self._text)


class ChannelIdentityCell(QFrame):
    """The fixed-width, pinned-during-horizontal-scroll identity column for
    one channel row.
    """

    selected = Signal(str)  # channel_id

    def __init__(self, lane, parent=None):
        super().__init__(parent)
        self.channel_id = lane.channel_id
        self._is_selected = False
        self.setFixedSize(IDENTITY_COLUMN_WIDTH, ROW_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("scheduleIdentityCell")

        self._accent = _ACCENT_BY_CHANNEL_TYPE.get(lane.channel_type, _DEFAULT_ACCENT)
        self._apply_style()

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)

        row.addWidget(_ChannelNumberBadge(lane.number))

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

    def _apply_style(self):
        # A subtle tint + brighter accent line -- distinct from
        # ProgramBlockWidget's strong 2px yellow border, so "this channel
        # is the current selection context" reads as a quieter cue than
        # "this exact program is selected".
        border_color = _SELECTED_ACCENT if self._is_selected else self._accent
        border_width = 4 if self._is_selected else 3
        bg = _ROW_SELECTED_BG if self._is_selected else _ROW_BG
        self.setStyleSheet(
            "QFrame#scheduleIdentityCell {"
            f" background: {bg};"
            f" border-bottom: 1px solid {_ROW_BORDER};"
            f" border-left: {border_width}px solid {border_color};"
            "}"
        )

    def set_selected(self, is_selected):
        self._is_selected = bool(is_selected)
        self._apply_style()

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

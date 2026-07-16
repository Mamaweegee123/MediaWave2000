"""One channel's row on the programming board: a fixed identity cell
(number, logo, name, accent strip) plus a horizontally-positioned strip of
ProgramBlockWidgets. Two separate widgets on purpose -- board.py keeps the
identity column pinned during horizontal scrolling and the block strip
scrolling, so they can never end up laid out inside the same scroll area.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .layout_constants import IDENTITY_COLUMN_WIDTH, ROW_HEIGHT
from .program_block import ProgramBlockWidget
from .schedule_model import PX_PER_MINUTE

# A digital-cable-box channel number gets its own restrained accent, scoped
# to this one label -- no existing SW_* token covers it (mediawave/
# theme_tokens.py's palette is all blue/amber/violet "deep space" tones),
# and it's deliberately not promoted to a shared token since nothing else in
# the app wants a phosphor-green readout.
_CHANNEL_NUMBER_GREEN = "rgba(120, 255, 168, 235)"

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
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(8)

        number_lbl = QLabel(str(lane.number or ""))
        number_lbl.setFixedWidth(30)
        number_lbl.setAlignment(Qt.AlignCenter)
        number_font = number_lbl.font()
        number_font.setFamily("Courier New")
        number_font.setBold(True)
        number_font.setPointSize(number_font.pointSize() + 3)
        number_lbl.setFont(number_font)
        number_lbl.setStyleSheet(f"color: {_CHANNEL_NUMBER_GREEN}; background: transparent;")
        row.addWidget(number_lbl)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        if lane.logo_path:
            pixmap = QPixmap(lane.logo_path)
            if not pixmap.isNull():
                logo_lbl = QLabel()
                logo_lbl.setPixmap(pixmap.scaledToHeight(18, Qt.SmoothTransformation))
                text_col.addWidget(logo_lbl)

        name_lbl = QLabel(lane.name)
        name_lbl.setStyleSheet(f"color: {_NAME_COLOR}; font-weight: 600; font-size: 12px; background: transparent;")
        fm = name_lbl.fontMetrics()
        name_lbl.setText(fm.elidedText(lane.name, Qt.ElideRight, IDENTITY_COLUMN_WIDTH - 60))
        name_lbl.setToolTip(lane.name)
        text_col.addWidget(name_lbl)

        if not lane.has_data:
            status_lbl = QLabel("No scheduled breakdown")
            status_lbl.setStyleSheet(f"color: {_SUBTITLE_COLOR}; font-size: 9px; background: transparent;")
            text_col.addWidget(status_lbl)

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

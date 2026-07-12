"""Logo Studio v1's simulated TV screen.

A small, self-contained preview widget: a dark "screen" (16:9 or 4:3,
see set_aspect) that draws the channel's real logo -- at its own aspect
ratio, never stretched -- at its configured position/size/opacity, and
lets the user drag it around freely with the mouse. See
setup_sections.build_logo_section for how this plugs into Channel Setup,
and mediawave/channel_logos.py for the position math (both the freeform
normalized-coordinate math and the legacy corner/offset math) this
widget's drag behavior is built on (this widget only deals in plain
pixel geometry -- it never reads or writes settings itself, so it stays
testable/reusable independent of the channel_bug_settings shape).

This is a static preview: it shows where and how big the logo is, not
when it would appear. Timing (see LogoTimingDialog below) is a separate
concern edited elsewhere in the Logo tab, not acted out here.
"""

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..channel_logos import channel_bug_settings_defaults, normalize_timing

PREVIEW_ASPECT_W = 16
PREVIEW_ASPECT_H = 9
_MIN_LOGO_PREVIEW_PX = 24
_NO_LOGO_TITLE = "No channel logo found"
_NO_LOGO_HINT = "Place a PNG in your Logos folder or use the existing logo settings."


class LogoPreviewScreen(QWidget):
    """Drag the logo around; drop position is reported in this widget's
    own pixel space via `logoDropped(x, y, screen_w, screen_h, logo_w,
    logo_h)` -- callers (see channel_actions.set_channel_logo_position_from_drop)
    convert that to a real normalized drag position and write it back
    through set_geometry_state(), which is also how any other change
    (a slider, an initial load, a preset) updates what's drawn here.
    """

    logoDropped = Signal(int, int, int, int, int, int)
    resized = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 124)
        self.setCursor(Qt.OpenHandCursor)
        self._logo_pixmap = None
        self._logo_x = 0
        self._logo_y = 0
        self._logo_w = 60
        self._logo_h = 60
        self._opacity = 1.0
        self._drag_offset = None  # grab offset within the logo box, or None when not dragging
        self._aspect_w = PREVIEW_ASPECT_W
        self._aspect_h = PREVIEW_ASPECT_H

    def set_logo(self, pixmap):
        """`pixmap` is a QPixmap or None (shows the "no logo" placeholder)."""
        self._logo_pixmap = pixmap if pixmap is not None and not pixmap.isNull() else None
        self.setCursor(Qt.OpenHandCursor if self._logo_pixmap is not None else Qt.ArrowCursor)
        self.update()

    def set_aspect(self, aspect_w, aspect_h):
        """Change the simulated screen's shape (e.g. 4:3 vs 16:9) -- the
        widget's own minimum/preferred height depends on this, so the
        layout is asked to re-measure it.
        """
        aspect_w = max(1, int(aspect_w))
        aspect_h = max(1, int(aspect_h))
        if (aspect_w, aspect_h) == (self._aspect_w, self._aspect_h):
            return
        self._aspect_w = aspect_w
        self._aspect_h = aspect_h
        self.updateGeometry()
        self.update()

    def set_geometry_state(self, x, y, logo_w, logo_h, opacity):
        """Position + size in this widget's own pixel space, plus opacity
        (0.0-1.0). `logo_w`/`logo_h` should already reflect the logo's
        real aspect ratio (see channel_logos.scale_logo_dimensions) --
        this widget draws exactly the box it's given, so a caller that
        wants no stretching passes a box shaped like the source image.
        Called any time the effective settings change -- including
        mid-drag, so a drag never has to fight this method.
        """
        self._logo_x = int(x)
        self._logo_y = int(y)
        self._logo_w = max(_MIN_LOGO_PREVIEW_PX, int(logo_w))
        self._logo_h = max(_MIN_LOGO_PREVIEW_PX, int(logo_h))
        self._opacity = max(0.0, min(1.0, float(opacity)))
        self.update()

    def logo_rect(self):
        return QRect(self._logo_x, self._logo_y, self._logo_w, self._logo_h)

    def sizeHint(self):
        return QSize(480, int(480 * self._aspect_h / self._aspect_w))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return max(1, int(width * self._aspect_h / self._aspect_w))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()

    # ── Paint ────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()

        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0.0, QColor(18, 20, 26))
        gradient.setColorAt(1.0, QColor(8, 9, 12))
        painter.fillRect(rect, gradient)

        painter.setPen(QPen(QColor(255, 255, 255, 10), 1))
        for y in range(0, rect.height(), 3):
            painter.drawLine(0, y, rect.width(), y)

        # A faint TV-safe-area guide (~5% inset) -- purely decorative,
        # helps the logo read as "on a screen" rather than floating on
        # a plain rectangle.
        safe = rect.adjusted(
            int(rect.width() * 0.05), int(rect.height() * 0.05),
            -int(rect.width() * 0.05), -int(rect.height() * 0.05),
        )
        safe_pen = QPen(QColor(255, 255, 255, 22), 1, Qt.DashLine)
        painter.setPen(safe_pen)
        painter.drawRect(safe)

        if self._logo_pixmap is not None:
            if self._opacity > 0.0:
                painter.setOpacity(self._opacity)
                painter.drawPixmap(self.logo_rect(), self._logo_pixmap)
                painter.setOpacity(1.0)
        else:
            title_font = painter.font()
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.setPen(QColor(200, 210, 230, 210))
            painter.drawText(rect.adjusted(16, 0, -16, -16), Qt.AlignCenter | Qt.TextWordWrap, _NO_LOGO_TITLE)

            hint_font = painter.font()
            hint_font.setBold(False)
            hint_font.setPointSize(max(7, hint_font.pointSize() - 2))
            painter.setFont(hint_font)
            painter.setPen(QColor(160, 170, 195, 190))
            hint_rect = rect.adjusted(24, 0, -24, -14)
            painter.drawText(hint_rect, Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap, _NO_LOGO_HINT)

        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.end()

    # ── Drag ─────────────────────────────────────────────────────────────

    def _event_pos(self, event):
        return event.position().toPoint() if hasattr(event, "position") else event.pos()

    def mousePressEvent(self, event):
        if self._logo_pixmap is None:
            return
        pos = self._event_pos(event)
        if self.logo_rect().contains(pos):
            # Grab offset within the logo box -- keeps the cursor's grip
            # point fixed relative to the logo instead of the logo
            # re-centering (and visibly jumping) on the cursor on the
            # first move.
            self._drag_offset = pos - self.logo_rect().topLeft()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_offset is None:
            return
        pos = self._event_pos(event)
        new_x = pos.x() - self._drag_offset.x()
        new_y = pos.y() - self._drag_offset.y()
        new_x = max(0, min(new_x, self.width() - self._logo_w))
        new_y = max(0, min(new_y, self.height() - self._logo_h))
        self._logo_x = new_x
        self._logo_y = new_y
        self.update()

    def mouseReleaseEvent(self, event):
        if self._drag_offset is None:
            return
        self._drag_offset = None
        self.setCursor(Qt.OpenHandCursor)
        self.logoDropped.emit(self._logo_x, self._logo_y, self.width(), self.height(), self._logo_w, self._logo_h)


class LogoTimingDialog(QDialog):
    """Field-level timing editor for combinations the Timing dropdown's
    presets don't cover -- everything here maps straight to the real
    `timing` sub-dict (mediawave/channel_logos.py) the overlay already
    reads; nothing invented. Kept separate from the main Logo tab so
    that stays compact (see setup_sections.build_logo_section).
    """

    def __init__(self, timing, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Timing")
        self.setModal(True)
        self.resize(360, 340)
        self.result_timing = None
        source = normalize_timing(timing)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        self._always = QCheckBox("Always visible")
        self._tune = QCheckBox("Show when tuning to this channel")
        self._program_start = QCheckBox("Show at the start of every program")
        self._periodic = QCheckBox("Repeat periodically")
        self._random = QCheckBox("Randomize the repeat interval")
        for box in (self._always, self._tune, self._program_start, self._periodic, self._random):
            outer.addWidget(box)

        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Visible for (seconds):"))
        self._duration = QSpinBox()
        self._duration.setRange(1, 120)
        duration_row.addWidget(self._duration)
        outer.addLayout(duration_row)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Repeat every (minutes):"))
        self._interval = QSpinBox()
        self._interval.setRange(1, 120)
        interval_row.addWidget(self._interval)
        outer.addLayout(interval_row)

        random_row = QHBoxLayout()
        random_row.addWidget(QLabel("Random range (minutes):"))
        self._interval_min = QSpinBox()
        self._interval_min.setRange(1, 120)
        self._interval_max = QSpinBox()
        self._interval_max.setRange(1, 120)
        random_row.addWidget(self._interval_min)
        random_row.addWidget(QLabel("to"))
        random_row.addWidget(self._interval_max)
        outer.addLayout(random_row)

        self._always.setChecked(source["always_visible"])
        self._tune.setChecked(source["on_channel_tune"])
        self._program_start.setChecked(source["on_program_start"])
        self._periodic.setChecked(source["periodic"])
        self._random.setChecked(source["random_interval"])
        self._duration.setValue(source["duration_seconds"])
        self._interval.setValue(source["periodic_interval_minutes"])
        self._interval_min.setValue(source["interval_min_minutes"])
        self._interval_max.setValue(source["interval_max_minutes"])

        for box in (self._always, self._tune, self._program_start, self._periodic, self._random):
            box.toggled.connect(self._update_enabled_state)
        self._update_enabled_state()

        outer.addStretch(1)

        reset_btn = QPushButton("Reset Timing to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        outer.addWidget(reset_btn)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_and_accept)
        buttons.addWidget(save_btn)
        outer.addLayout(buttons)

    def _update_enabled_state(self):
        always = self._always.isChecked()
        periodic = self._periodic.isChecked()
        random_on = self._random.isChecked()
        for box in (self._tune, self._program_start, self._periodic):
            box.setEnabled(not always)
        self._random.setEnabled(not always and periodic)
        self._duration.setEnabled(not always)
        self._interval.setEnabled(not always and periodic and not random_on)
        self._interval_min.setEnabled(not always and periodic and random_on)
        self._interval_max.setEnabled(not always and periodic and random_on)

    def _reset_to_defaults(self):
        defaults = channel_bug_settings_defaults()["timing"]
        self._always.setChecked(defaults["always_visible"])
        self._tune.setChecked(defaults["on_channel_tune"])
        self._program_start.setChecked(defaults["on_program_start"])
        self._periodic.setChecked(defaults["periodic"])
        self._random.setChecked(defaults["random_interval"])
        self._duration.setValue(defaults["duration_seconds"])
        self._interval.setValue(defaults["periodic_interval_minutes"])
        self._interval_min.setValue(defaults["interval_min_minutes"])
        self._interval_max.setValue(defaults["interval_max_minutes"])

    def _save_and_accept(self):
        self.result_timing = normalize_timing({
            "always_visible": self._always.isChecked(),
            "on_channel_tune": self._tune.isChecked(),
            "on_program_start": self._program_start.isChecked(),
            "periodic": self._periodic.isChecked(),
            "random_interval": self._random.isChecked(),
            "duration_seconds": self._duration.value(),
            "periodic_interval_minutes": self._interval.value(),
            "interval_min_minutes": self._interval_min.value(),
            "interval_max_minutes": self._interval_max.value(),
        })
        self.accept()


class ShowExclusionsDialog(QDialog):
    """"Disable Logo For Shows" -- for recordings that already have a
    network logo baked in, so MediaWave's own bug doesn't double up.
    Storage is a plain list of show keys on the channel's override (see
    channel_actions.set_channel_logo_excluded_shows) -- this dialog is
    just the checkbox list over that.
    """

    def __init__(self, shows, excluded_keys, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Disable Logo For Shows")
        self.setModal(True)
        self.resize(380, 420)
        self.result_excluded = None
        excluded_set = set(excluded_keys or [])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        note = QLabel("Use this when a recording already has a channel logo baked in.")
        note.setWordWrap(True)
        outer.addWidget(note)

        self._checks = []
        if not shows:
            empty = QLabel("No shows found for this channel yet.")
            empty.setWordWrap(True)
            outer.addWidget(empty)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            body = QWidget()
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(4, 4, 4, 4)
            for show in shows:
                key = str(show.get("title_key") or "")
                if not key:
                    continue
                box = QCheckBox(str(show.get("title") or key))
                box.setChecked(key in excluded_set)
                box._show_key = key
                body_layout.addWidget(box)
                self._checks.append(box)
            body_layout.addStretch(1)
            scroll.setWidget(body)
            outer.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_and_accept)
        buttons.addWidget(save_btn)
        outer.addLayout(buttons)

    def _save_and_accept(self):
        self.result_excluded = [box._show_key for box in self._checks if box.isChecked()]
        self.accept()

"""Shared low-level widgets for Channel Studio (Preview).

Everything here reuses the Advanced Configuration dialog's existing
themed object names (sectionCard, sectionHeader, statusBadge, ...) so
Channel Studio inherits the same look without any new QSS.
"""

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FlowLayout(QLayout):
    """A left-to-right, top-to-bottom layout that wraps onto new lines.

    Used for action-button rows so buttons wrap instead of clipping
    when a card or dialog is narrower than the row's natural width —
    no horizontal scrolling, no cut-off buttons at the default window
    size.
    """

    def __init__(self, parent=None, margin=0, h_spacing=8, v_spacing=8):
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._items:
            item_size = item.sizeHint()
            next_x = x + item_size.width() + self._h_spacing
            if next_x - self._h_spacing > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y += line_height + self._v_spacing
                next_x = x + item_size.width() + self._h_spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y() + bottom


def build_placeholder_note(text="This section is under construction."):
    label = QLabel(text)
    label.setObjectName("fieldHelp")
    label.setWordWrap(True)
    return label


def build_empty_state(text):
    """A friendly, non-scary "nothing here yet" block."""
    box = QFrame()
    box.setObjectName("sectionCard")
    box.setFrameShape(QFrame.NoFrame)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(20, 24, 20, 24)
    layout.setSpacing(6)

    text_lbl = QLabel(text)
    text_lbl.setObjectName("sectionNote")
    text_lbl.setWordWrap(True)
    text_lbl.setAlignment(Qt.AlignCenter)
    layout.addWidget(text_lbl)
    return box


def build_info_card(title_text, subtitle_text=None, meta_lines=None, buttons=None, badge_text=None):
    """A friendly card: title (+ optional badge), subtitle, meta lines, action buttons.

    `buttons` is a list of (label, callback) tuples. Every card built
    this way is display/mock only unless the caller's callback does
    something real.
    """
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(8)

    title_row = QHBoxLayout()
    title_row.setSpacing(8)
    title = QLabel(title_text)
    title.setObjectName("sectionHeader")
    title_row.addWidget(title)
    if badge_text:
        badge = QLabel(badge_text)
        badge.setObjectName("statusBadge")
        title_row.addWidget(badge)
    title_row.addStretch(1)
    layout.addLayout(title_row)

    if subtitle_text:
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("sectionNote")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

    if meta_lines:
        for line in meta_lines:
            meta_lbl = QLabel(line)
            meta_lbl.setObjectName("fieldHelp")
            layout.addWidget(meta_lbl)

    if buttons:
        layout.addSpacing(4)
        btn_row = FlowLayout(h_spacing=8, v_spacing=6)
        for label, callback in buttons:
            btn = QPushButton(label)
            if callback is not None:
                btn.clicked.connect(callback)
            else:
                btn.setEnabled(False)
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

    return card


def build_schedule_timeline(channel_name, slots):
    """A vertical "tonight on <channel>" timeline, arrows between slots.

    `slots` is a list of objects with `.time_label` and `.title` (see
    `ScheduleSlot` in channel_studio_model.py). Display only — nothing
    here reads or writes real schedule data.
    """
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setFrameShape(QFrame.NoFrame)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(4)

    heading = QLabel(f"Tonight on {channel_name}")
    heading.setObjectName("sectionHeader")
    layout.addWidget(heading)

    for index, slot in enumerate(slots):
        row = QHBoxLayout()
        row.setSpacing(10)
        time_lbl = QLabel(slot.time_label)
        time_lbl.setObjectName("statusBadge")
        time_lbl.setFixedWidth(84)
        time_lbl.setAlignment(Qt.AlignCenter)
        row.addWidget(time_lbl)
        title_lbl = QLabel(slot.title)
        title_lbl.setObjectName("sectionNote")
        row.addWidget(title_lbl, 1)
        layout.addLayout(row)

        if index < len(slots) - 1:
            arrow = QLabel("↓")
            arrow.setObjectName("fieldHelp")
            arrow.setAlignment(Qt.AlignCenter)
            arrow.setFixedWidth(84)
            layout.addWidget(arrow, 0, Qt.AlignLeft)

    return card


def build_card_grid(cards, columns=3, total_width=760):
    """Lay out already-built card widgets in a grid.

    Word-wrapped labels inside each card are given an explicit width
    up front. QGridLayout sizes a row from each cell's `sizeHint()`,
    but a QLabel's default sizeHint() reflects its *unconstrained*
    width, not the narrower column width it will actually render at —
    so a description that only needs to wrap once the grid squeezes it
    reports a single-line height, and the wrapped second line is
    clipped instead of growing the row. Fixing the label's width before
    layout makes heightForWidth() correct from the start.
    """
    grid_widget = QWidget()
    grid = QGridLayout(grid_widget)
    grid.setSpacing(12)
    if columns > 1:
        card_width = (total_width - (columns - 1) * 12) // columns
        for card in cards:
            for label in card.findChildren(QLabel):
                if label.wordWrap():
                    label.setFixedWidth(card_width - 32)
    for index, card in enumerate(cards):
        row, col = divmod(index, columns)
        grid.addWidget(card, row, col)
    return grid_widget


def build_mock_card_grid(items, columns=3):
    """Convenience: items are str titles or (title, subtitle) tuples."""
    cards = []
    for item in items:
        title_text, subtitle_text = item if isinstance(item, tuple) else (item, None)
        cards.append(build_info_card(title_text, subtitle_text))
    return build_card_grid(cards, columns=columns)


def build_tab_row(labels, on_select, initial_index=0):
    """A flat, single-row set of exclusive tabs — not a sidebar.

    Used to switch between a handful of top-level views (e.g. Tonight,
    Programming, Commercials, Identity, Preview) without any drill-down
    or nested navigation. `on_select(index)` is called whenever the
    selected tab changes. `initial_index` lets a caller open straight
    to a specific tab (e.g. a channel card's "Commercials" shortcut).
    """
    row = QWidget()
    layout = FlowLayout(row, margin=0, h_spacing=6, v_spacing=6)
    group = QButtonGroup(row)
    group.setExclusive(True)
    for index, label in enumerate(labels):
        btn = QPushButton(label)
        btn.setObjectName("advNavItem")
        btn.setCheckable(True)
        btn.setChecked(index == initial_index)
        btn.setCursor(Qt.PointingHandCursor)
        group.addButton(btn, index)
        layout.addWidget(btn)
    group.idClicked.connect(on_select)
    return row, group


def build_channel_studio_footer(total_count, on_reorder=None):
    """Channel Studio's own persistent footer bar: a live channel count
    and an optional Reorder Channels toggle. Deliberately has no On Air
    status here — this page is about picking a channel, not showing
    what's currently airing.

    Uses the same "advFooter" object name as the main Advanced
    Configuration dialog's Close/Save bar so it picks up the identical
    background/top-border styling — callers are expected to swap this
    in for that bar (same fixed spot, same look), not stack it below
    scrollable content.

    Returns `(footer, reorder_button)` — `reorder_button` is None if
    `on_reorder` wasn't given. Callers own the button's label (e.g.
    toggling "Reorder Channels" / "Done Reordering") since that's
    reorder-mode state this module doesn't track.
    """
    footer = QWidget()
    footer.setObjectName("advFooter")
    layout = QHBoxLayout(footer)
    layout.setContentsMargins(20, 10, 20, 16)
    layout.setSpacing(10)

    count_lbl = QLabel(f"📊  Total Channels: <b>{total_count}</b>")
    count_lbl.setTextFormat(Qt.RichText)
    count_lbl.setStyleSheet(
        "color: rgba(210, 222, 255, 235);"
        " background: rgba(68, 108, 235, 40);"
        " border: 1px solid rgba(68, 108, 235, 90);"
        " border-radius: 10px;"
        " padding: 4px 12px;"
        " font-size: 12px;"
    )
    layout.addWidget(count_lbl)
    layout.addStretch(1)

    reorder_btn = None
    if on_reorder is not None:
        reorder_btn = QPushButton("⇅  Reorder Channels")
        reorder_btn.setCursor(Qt.PointingHandCursor)
        reorder_btn.clicked.connect(on_reorder)
        layout.addWidget(reorder_btn)

    return footer, reorder_btn


def build_inline_value_editor(initial_value, on_validate, on_apply, label_formatter=None, placeholder=""):
    """A click-to-edit inline field: a plain clickable label until clicked,
    then `[ value ] [Apply]` with live validation shown underneath --
    no popup dialogs. Used by Overview's channel number and name editors
    (see setup_sections.py's build_overview_section).

    `initial_value`: the current value, as a string.
    `on_validate(candidate_str) -> ("ok"|"duplicate"|"invalid", message)`:
        called on every keystroke. Apply is enabled only when the
        candidate differs from the current value AND validates "ok".
        `message` is shown as-is after a "✓ "/"⚠ " prefix -- callers
        supply the exact wording (e.g. "Available" / "Channel number
        already exists.").
    `on_apply(candidate_str)`: called only while Apply is enabled, on
        click or Enter. The editor then collapses back to label mode
        showing the new value -- callers that need OTHER screens to
        refresh should do that from inside on_apply (see
        channel_actions.refresh_live_lineup); this widget only manages
        its own label/field swap.
    `label_formatter(value_str) -> str`: how the collapsed label renders
        the value (e.g. "CH 005" for a number). Defaults to the raw value.

    Returns `(container_widget, api)`; `api.set_value(new_value_str)` lets
    a caller update the current value from outside (e.g. another screen
    changed it) -- collapses back to label mode if the editor was open.
    """
    formatter = label_formatter or (lambda value: value)
    state = {"value": str(initial_value)}

    container = QWidget()
    outer = QVBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(2)

    row = QHBoxLayout()
    row.setSpacing(8)
    outer.addLayout(row)

    label = QLabel(formatter(state["value"]))
    label.setObjectName("sectionHeader")
    label.setCursor(Qt.PointingHandCursor)
    label.setToolTip("Click to edit")
    row.addWidget(label)

    field = QLineEdit()
    field.setPlaceholderText(placeholder)
    field.setMaximumWidth(160)
    field.setVisible(False)
    row.addWidget(field)

    apply_btn = QPushButton("Apply")
    apply_btn.setVisible(False)
    apply_btn.setEnabled(False)
    row.addWidget(apply_btn)

    row.addStretch(1)

    status_lbl = QLabel("")
    status_lbl.setObjectName("fieldHelp")
    status_lbl.setVisible(False)
    outer.addWidget(status_lbl)

    def _show_editor(_event=None):
        label.setVisible(False)
        field.setText(state["value"])
        field.setVisible(True)
        apply_btn.setVisible(True)
        apply_btn.setEnabled(False)
        status_lbl.setText("")
        status_lbl.setVisible(False)
        field.setFocus()
        field.selectAll()

    def _show_label():
        field.setVisible(False)
        apply_btn.setVisible(False)
        status_lbl.setVisible(False)
        label.setText(formatter(state["value"]))
        label.setVisible(True)

    def _on_text_changed(text):
        candidate = text.strip()
        if candidate == state["value"]:
            apply_btn.setEnabled(False)
            status_lbl.setVisible(False)
            return
        outcome, message = on_validate(candidate)
        prefix = "✓" if outcome == "ok" else "⚠"
        status_lbl.setText(f"{prefix} {message}" if message else "")
        status_lbl.setVisible(bool(message))
        apply_btn.setEnabled(outcome == "ok")

    def _on_apply(_checked=False):
        if not apply_btn.isEnabled():
            return
        candidate = field.text().strip()
        on_apply(candidate)
        state["value"] = candidate
        _show_label()

    label.mousePressEvent = _show_editor
    field.textChanged.connect(_on_text_changed)
    field.returnPressed.connect(_on_apply)
    apply_btn.clicked.connect(_on_apply)

    class _InlineValueEditorApi:
        def set_value(self, new_value):
            state["value"] = str(new_value)
            _show_label()

    return container, _InlineValueEditorApi()


def build_action_button_row(items, fallback=None):
    """Build a row of action buttons.

    `items` is a list of str labels or (label, callback) tuples. If an
    item has no callback and `fallback` is given, `fallback(label)` is
    called on click (used to pop a generic "Preview only" dialog).
    """
    row = QWidget()
    layout = FlowLayout(row, margin=0, h_spacing=10, v_spacing=8)
    buttons = []
    for item in items:
        label, callback = item if isinstance(item, tuple) else (item, None)
        btn = QPushButton(label)
        if callback is None and fallback is not None:
            callback = (lambda checked=False, l=label: fallback(l))
        if callback is not None:
            btn.clicked.connect(callback)
        else:
            btn.setEnabled(False)
            btn.setToolTip("Channel Studio preview — not yet implemented")
        layout.addWidget(btn)
        buttons.append(btn)
    return row, buttons

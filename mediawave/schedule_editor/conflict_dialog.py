"""ConflictDialog: a compact, scannable confirmation for the two
schedule-editor conflict flows -- a destination overlap (Move/Duplicate/
Copy) and a longer-than-gap fill (Put On Air/Fill Open Time).

Replaces ad-hoc QMessageBox usage for these two flows: a QMessageBox
sizes its buttons off the dialog's default width, which clipped labels
like "Replace Overlapping Program" once three buttons shared one row.
This dialog gives every button equal width and never lets a label wrap
or clip, and gives both conflict flows one consistent title/summary/
list/actions shape instead of a paragraph of prose.
"""

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

_TEXT_COLOR = "rgba(210, 222, 252, 235)"
_DIM_COLOR = "rgba(148, 166, 216, 220)"
_PANEL_BG = "rgba(13, 16, 38, 255)"
_LIST_BG = "rgba(24, 28, 60, 210)"

_BUTTON_STYLE = {
    "destructive": """
        QPushButton {
            min-height: 34px; padding: 6px 10px; border-radius: 6px;
            font-size: 12px; font-weight: 600;
            border: 1px solid rgba(230, 110, 110, 190);
            background: rgba(120, 40, 40, 160); color: white;
        }
        QPushButton:hover {
            border: 1px solid rgba(255, 140, 140, 220);
            background: rgba(150, 50, 50, 200);
        }
    """,
    "primary": """
        QPushButton {
            min-height: 34px; padding: 6px 10px; border-radius: 6px;
            font-size: 12px; font-weight: 600;
            border: 1px solid rgba(96, 144, 255, 190);
            background: rgba(56, 84, 200, 190); color: white;
        }
        QPushButton:hover {
            border: 1px solid rgba(130, 170, 255, 230);
            background: rgba(70, 100, 224, 220);
        }
    """,
    "neutral": f"""
        QPushButton {{
            min-height: 34px; padding: 6px 10px; border-radius: 6px;
            font-size: 12px; font-weight: 600;
            border: 1px solid rgba(158, 172, 210, 100);
            background: transparent; color: {_TEXT_COLOR};
        }}
        QPushButton:hover {{
            border: 1px solid rgba(180, 195, 230, 170);
            background: rgba(60, 70, 100, 90);
        }}
    """,
}


class ConflictDialog(QDialog):
    """`actions` is a list of (label, kind, key) -- kind picks the button
    style ("neutral" | "primary" | "destructive"), key is what `.result`
    is set to when that button is clicked. `.result` is None if the
    dialog is dismissed without a button click (callers treat that the
    same as a "cancel" key).
    """

    def __init__(self, title, summary, list_items=None, note=None, actions=None, parent=None):
        super().__init__(parent)
        self.result = None
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setStyleSheet(f"QDialog {{ background: {_PANEL_BG}; }} QLabel {{ color: {_TEXT_COLOR}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 15px; font-weight: 700;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        summary_lbl = QLabel(summary)
        summary_lbl.setWordWrap(True)
        summary_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 12px;")
        layout.addWidget(summary_lbl)

        if list_items:
            box = QWidget()
            box.setStyleSheet(f"background: {_LIST_BG}; border-radius: 8px;")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(12, 8, 12, 8)
            box_layout.setSpacing(3)
            for item in list_items:
                row = QLabel(f"•  {item}")
                row.setWordWrap(True)
                row.setStyleSheet(f"color: {_TEXT_COLOR}; font-size: 12px;")
                box_layout.addWidget(row)
            layout.addWidget(box)

        if note:
            note_lbl = QLabel(note)
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"color: {_DIM_COLOR}; font-size: 11px;")
            layout.addWidget(note_lbl)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        buttons = []
        for label, kind, key in (actions or []):
            btn = QPushButton(label)
            btn.setStyleSheet(_BUTTON_STYLE.get(kind, _BUTTON_STYLE["neutral"]))
            btn.clicked.connect(lambda _checked=False, k=key: self._choose(k))
            buttons.append(btn)
        # Equal width means "as wide as the widest label needs", not "an
        # even split of the row" -- stretch factors alone (the original
        # bug) can still clip a long label if it doesn't fit its equal
        # share of the total width. Sizing every button to the natural
        # width of the widest one guarantees none of them clip, ever.
        widest = max((btn.sizeHint().width() for btn in buttons), default=0)
        for btn in buttons:
            btn.setMinimumWidth(widest)
            button_row.addWidget(btn)
        layout.addLayout(button_row)

    def _choose(self, key):
        self.result = key
        self.accept()

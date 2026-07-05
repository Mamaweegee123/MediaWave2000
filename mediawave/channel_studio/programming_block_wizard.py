"""The Draft Programming Block wizard — Channel Studio's first real feature.

This is a draft-only workflow: every step asks a friendly question and the
result is saved (via `drafts.py`) only inside Channel Studio's own draft
file. Nothing here reads or writes real schedule, library, or settings
data, and nothing here affects playback.
"""

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout

from .channel_studio_dialogs import show_preview_dialog
from .drafts import ProgrammingBlockDraft, new_draft_key, upsert_draft
from .programming_blocks import get_block_type, get_playback_style, get_time_preset
from .wizard_pages import (
    build_step1_block_type,
    build_step2_time_preset,
    build_step3_content,
    build_step4_playback_style,
    build_step5_preview,
)

_STEP_TITLES = [
    "Step 1 of 5 — What kind of block are you creating?",
    "Step 2 of 5 — When does it come alive?",
    "Step 3 of 5 — What belongs in this block?",
    "Step 4 of 5 — How should it feel?",
    "Step 5 of 5 — Preview",
]


class ProgrammingBlockWizardDialog(QDialog):
    """A card-based wizard that produces a `ProgrammingBlockDraft`.

    `studio_dialog` is the owning Channel Studio dialog, used read-only to
    list already-detected shows/movies/channels in Step 3 — nothing here
    is written back to it. `drafts_path` is where the finished draft is
    saved. `existing_draft`, if given, pre-fills the wizard for editing.
    """

    def __init__(self, studio_dialog, drafts_path, existing_draft=None, parent=None):
        super().__init__(parent)
        self._studio_dialog = studio_dialog
        self._drafts_path = drafts_path
        self._existing_draft = existing_draft
        self.saved = False

        self._draft_key = existing_draft.key if existing_draft else new_draft_key()
        self._created_at = existing_draft.created_at if existing_draft else 0.0
        self._block_type = get_block_type(existing_draft.block_type) if existing_draft else None
        self._time_preset = get_time_preset(existing_draft.time_preset) if existing_draft else None
        self._media_selections = list(existing_draft.media_selections) if existing_draft else []
        self._playback_style = get_playback_style(existing_draft.playback_style) if existing_draft else None

        self.setWindowTitle(
            "New Programming Block" if existing_draft is None else f"Edit {existing_draft.title}"
        )
        self.resize(760, 580)

        outer = QVBoxLayout(self)
        outer.setSpacing(12)

        badge = QLabel("Draft only — nothing here affects playback")
        badge.setObjectName("statusBadge")
        outer.addWidget(badge, 0, Qt.AlignLeft)

        self._step_label = QLabel()
        self._step_label.setObjectName("sectionHeader")
        outer.addWidget(self._step_label)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)

        nav_row = QHBoxLayout()
        self._back_btn = QPushButton("←  Back")
        self._back_btn.clicked.connect(self._go_back)
        nav_row.addWidget(self._back_btn, 0, Qt.AlignLeft)
        nav_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        nav_row.addWidget(cancel_btn)
        outer.addLayout(nav_row)

        self._history = []
        self._go_step1()

    # ── navigation plumbing ─────────────────────────────────────────────

    def _push_step(self, index, widget):
        self._history.append(index)
        self._step_label.setText(_STEP_TITLES[index])
        self._back_btn.setVisible(len(self._history) > 1)
        self._stack.addWidget(widget)
        self._stack.setCurrentWidget(widget)

    def _go_back(self):
        if len(self._history) <= 1:
            return
        current = self._stack.currentWidget()
        self._history.pop()
        previous_index = self._history[-1]
        rebuild = {
            0: self._go_step1,
            1: self._go_step2,
            2: self._go_step3,
            3: self._go_step4,
        }.get(previous_index)
        self._history.pop()
        if rebuild is not None:
            rebuild()
        if current is not None:
            self._stack.removeWidget(current)
            current.deleteLater()

    # ── steps ────────────────────────────────────────────────────────────

    def _go_step1(self):
        widget = build_step1_block_type(self._on_block_type_chosen)
        self._push_step(0, widget)

    def _on_block_type_chosen(self, option):
        self._block_type = option
        self._go_step2()

    def _go_step2(self):
        widget = build_step2_time_preset(self._on_time_preset_chosen, self._on_custom_time)
        self._push_step(1, widget)

    def _on_custom_time(self):
        show_preview_dialog(
            self,
            "Custom Timing",
            "Picking your own days and times will live here — for now, "
            "choose one of the friendly presets to continue.",
        )

    def _on_time_preset_chosen(self, option):
        self._time_preset = option
        self._go_step3()

    def _go_step3(self):
        widget = build_step3_content(
            self._studio_dialog, self._on_content_chosen, initial_selections=self._media_selections
        )
        self._push_step(2, widget)

    def _on_content_chosen(self, selections):
        self._media_selections = selections
        self._go_step4()

    def _go_step4(self):
        widget = build_step4_playback_style(self._on_playback_style_chosen)
        self._push_step(3, widget)

    def _on_playback_style_chosen(self, option):
        self._playback_style = option
        self._go_step5()

    def _go_step5(self):
        title = self._draft_title()
        example_content = self._block_type.example_content if self._block_type else ""
        widget = build_step5_preview(
            title, self._media_selections, example_content, self._on_save
        )
        self._push_step(4, widget)

    # ── finish ───────────────────────────────────────────────────────────

    def _draft_title(self):
        if self._existing_draft is not None and self._existing_draft.title:
            return self._existing_draft.title
        if self._block_type is None:
            return "New Programming Block"
        if self._block_type.key == "scratch":
            return "New Programming Block"
        return self._block_type.title

    def _on_save(self):
        now = time.time()
        draft = ProgrammingBlockDraft(
            key=self._draft_key,
            title=self._draft_title(),
            block_type=self._block_type.key if self._block_type else "",
            time_preset=self._time_preset.key if self._time_preset else "",
            time_preset_label=self._time_preset.label if self._time_preset else "",
            media_selections=list(self._media_selections),
            playback_style=self._playback_style.key if self._playback_style else "",
            playback_style_label=self._playback_style.title if self._playback_style else "",
            created_at=self._created_at or now,
            updated_at=now,
        )
        upsert_draft(self._drafts_path, draft)
        self.saved = True
        self.accept()


def open_programming_block_wizard(studio_dialog, drafts_path, existing_draft=None, on_saved=None):
    """Open the wizard modally. Calls `on_saved()` if the user saves a draft."""
    wizard = ProgrammingBlockWizardDialog(
        studio_dialog, drafts_path, existing_draft=existing_draft, parent=studio_dialog
    )
    wizard.exec()
    if wizard.saved and on_saved is not None:
        on_saved()

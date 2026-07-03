"""Isolated draft storage for Channel Studio's Programming Block wizard.

Drafts live in their own JSON file, entirely separate from real schedule,
channel, or settings data. Saving, editing, or deleting a draft here never
reads or writes anything the scheduling engine, My Catalog, or app_settings
depend on.
"""

import time
from dataclasses import dataclass, field

from mediawave.core_io import load_json_file, save_json_file


@dataclass
class ProgrammingBlockDraft:
    """One draft created by the Programming Block wizard."""

    key: str
    title: str
    block_type: str = ""
    time_preset: str = ""
    time_preset_label: str = ""
    media_selections: list = field(default_factory=list)
    playback_style: str = ""
    playback_style_label: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self):
        return {
            "key": self.key,
            "title": self.title,
            "block_type": self.block_type,
            "time_preset": self.time_preset,
            "time_preset_label": self.time_preset_label,
            "media_selections": list(self.media_selections or []),
            "playback_style": self.playback_style,
            "playback_style_label": self.playback_style_label,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data):
        data = data if isinstance(data, dict) else {}
        return cls(
            key=str(data.get("key", "") or ""),
            title=str(data.get("title", "Untitled Block") or "Untitled Block"),
            block_type=str(data.get("block_type", "") or ""),
            time_preset=str(data.get("time_preset", "") or ""),
            time_preset_label=str(data.get("time_preset_label", "") or ""),
            media_selections=list(data.get("media_selections", []) or []),
            playback_style=str(data.get("playback_style", "") or ""),
            playback_style_label=str(data.get("playback_style_label", "") or ""),
            created_at=float(data.get("created_at", 0.0) or 0.0),
            updated_at=float(data.get("updated_at", 0.0) or 0.0),
        )


def new_draft_key():
    """A unique-enough key for a new draft — not a display value."""
    return f"draft-{int(time.time() * 1000)}"


def load_drafts(path):
    """Load all saved drafts from `path`. Never raises; missing file -> []."""
    raw = load_json_file(path, [])
    if not isinstance(raw, list):
        return []
    drafts = []
    for item in raw:
        if isinstance(item, dict):
            drafts.append(ProgrammingBlockDraft.from_dict(item))
    return drafts


def save_drafts(path, drafts):
    """Overwrite `path` with the given list of ProgrammingBlockDraft."""
    save_json_file(path, [draft.to_dict() for draft in drafts])


def upsert_draft(path, draft):
    """Save one draft, replacing any existing draft with the same key."""
    drafts = [d for d in load_drafts(path) if d.key != draft.key]
    drafts.append(draft)
    save_drafts(path, drafts)
    return drafts


def delete_draft(path, key):
    """Remove the draft with the given key, if present."""
    drafts = [d for d in load_drafts(path) if d.key != key]
    save_drafts(path, drafts)
    return drafts

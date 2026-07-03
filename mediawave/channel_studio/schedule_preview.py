"""Builds a fake "Tonight's Schedule" preview for a draft programming block.

Purely illustrative — reads nothing from and writes nothing to the real
scheduling engine. This exists only so Step 5 of the Programming Block
wizard has something fun to show before the user saves a draft.
"""

from .channel_studio_model import ScheduleSlot


def build_draft_preview_slots(items, start_time_label="8:00 PM"):
    """Build a short, made-up lineup around the first chosen/example item."""
    items = [item for item in (items or []) if item]
    primary = items[0] if items else "Featured Program"

    slots = [ScheduleSlot(time_label=start_time_label, title=primary)]
    slots.append(ScheduleSlot(time_label="", title="Commercial Break", kind="placeholder"))
    slots.append(ScheduleSlot(time_label="", title=primary))
    slots.append(ScheduleSlot(time_label="", title="Station ID", kind="placeholder"))
    slots.append(ScheduleSlot(time_label="", title=f"{primary} Ends", kind="placeholder"))
    return slots

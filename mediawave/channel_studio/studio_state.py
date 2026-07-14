"""Isolated preview-state storage for Channel Studio.

Tracks small, low-stakes UI state — which channel was last opened via
its Setup button — entirely separate from real schedule, channel, or
app settings data. This file lives next to Channel Studio's own drafts
file (see drafts.py) and is read/written the same safe, never-raising
way. Losing or resetting it never affects playback, scheduling, the
catalog, or media folders — worst case, the hero card goes back to not
showing.

An older build also stored a "channel_order" key here for the
Choose Channel grid's now-removed drag-and-drop display order. Nothing
in this module reads or writes that key anymore; a state file carrying
it from an older build is simply ignored -- load_json_file reads the
whole dict but nothing here looks at that key, so it can't crash
anything.
"""

from mediawave.core_io import load_json_file, save_json_file


def load_last_edited_channel_id(path):
    """Return the last-edited channel id, or "" if none/unreadable/no
    path given. Never raises.
    """
    if not path:
        return ""
    data = load_json_file(path, {})
    if not isinstance(data, dict):
        return ""
    return str(data.get("last_edited_channel_id", "") or "")


def save_last_edited_channel_id(path, channel_id):
    """Record `channel_id` as the most recently customized channel.
    No-op if no path was given (in-memory-only fallback).
    """
    if not path or not channel_id:
        return
    data = load_json_file(path, {})
    if not isinstance(data, dict):
        data = {}
    data["last_edited_channel_id"] = str(channel_id)
    save_json_file(path, data)

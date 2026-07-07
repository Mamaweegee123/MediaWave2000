"""Isolated preview-state storage for Channel Studio.

Tracks small, low-stakes UI state — which channel was last opened via
its Setup button, and the Choose Channel grid's display order —
entirely separate from real schedule, channel, or app settings data.
This file lives next to Channel Studio's own drafts file (see
drafts.py) and is read/written the same safe, never-raising way.
Losing or resetting it never affects playback, scheduling, the
catalog, or media folders — worst case, the hero card goes back to not
showing, and the grid falls back to channel-number order.
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


def load_channel_order(path):
    """Return the saved Choose Channel grid display order as a list of
    channel ids, or [] if none/unreadable/no path given. Never raises.
    This is display order only — see reorder.apply_saved_order for how
    it's merged with the channels that actually exist today.
    """
    if not path:
        return []
    data = load_json_file(path, {})
    if not isinstance(data, dict):
        return []
    order = data.get("channel_order", [])
    if not isinstance(order, list):
        return []
    return [str(cid) for cid in order if cid]


def save_channel_order(path, order):
    """Record the Choose Channel grid's current display order.
    No-op if no path was given (in-memory-only fallback). Never writes
    real scheduling, channel-number, or playback-order settings.
    """
    if not path:
        return
    data = load_json_file(path, {})
    if not isinstance(data, dict):
        data = {}
    data["channel_order"] = [str(cid) for cid in (order or []) if cid]
    save_json_file(path, data)

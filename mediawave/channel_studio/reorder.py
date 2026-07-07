"""Pure channel-order logic for Channel Studio's reorder mode.

No Qt, no filesystem — just list operations over channel ids. Kept
separate from studio_state.py (persistence) and draggable_grid.py
(mouse/drag mechanics) so the ordering rules themselves are easy to
unit test without a GUI.
"""


def apply_saved_order(channel_ids, saved_order):
    """Order `channel_ids` by `saved_order` where possible.

    Saved ids that still exist come first, in their saved order. Any
    channel not present in `saved_order` (new since the order was last
    saved) is appended afterward, in its original relative order —
    e.g. by channel number, since callers pass ids already sorted that
    way. Stale ids in `saved_order` that no longer exist are silently
    dropped. Never raises; never duplicates an id; every known id
    appears exactly once in the result.
    """
    known = list(dict.fromkeys(str(cid) for cid in (channel_ids or []) if cid))
    known_set = set(known)

    ordered = [str(cid) for cid in (saved_order or []) if str(cid) in known_set]
    seen = set(ordered)
    ordered.extend(cid for cid in known if cid not in seen)
    return ordered


def move_item(order, from_index, to_index):
    """Return a new list with the item at `from_index` moved to sit at
    `to_index`. Out-of-range `to_index` is clamped into range;
    out-of-range `from_index` (or an empty list) is a safe no-op that
    returns the list unchanged.
    """
    items = list(order or [])
    if not items or from_index < 0 or from_index >= len(items):
        return items
    to_index = max(0, min(to_index, len(items) - 1))
    item = items.pop(from_index)
    items.insert(to_index, item)
    return items

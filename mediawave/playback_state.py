"""Pure helpers for keeping scheduled and active playback paths in sync."""

import os


def normalized_media_path(path):
    value = str(path or "").strip()
    if not value:
        return ""
    if "://" in value:
        return value
    return os.path.normcase(os.path.realpath(os.path.abspath(value)))


def media_paths_match(left, right):
    normalized_left = normalized_media_path(left)
    normalized_right = normalized_media_path(right)
    return bool(normalized_left and normalized_right and normalized_left == normalized_right)


def tune_context_matches(context, generation, channel_index, channel_object, path):
    if not isinstance(context, dict):
        return False
    return (
        int(context.get("generation", -1)) == int(generation)
        and int(context.get("channel_index", -1)) == int(channel_index)
        and int(context.get("channel_object_id", -1)) == id(channel_object)
        and media_paths_match(context.get("path"), path)
    )


def active_playback_path(active_path, expected_path, scheduled_path):
    return str(active_path or expected_path or scheduled_path or "")


def expected_frame_path(playback_mode, expected_live_path="", on_demand_path=""):
    if playback_mode == "ondemand":
        return str(on_demand_path or "")
    if playback_mode == "live":
        return str(expected_live_path or "")
    return ""


def playback_frame_matches(playback_mode, actual_path, expected_live_path="", on_demand_path=""):
    expected_path = expected_frame_path(playback_mode, expected_live_path, on_demand_path)
    return bool(expected_path and media_paths_match(actual_path, expected_path))

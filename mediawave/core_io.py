"""Shared filesystem and JSON helpers for MediaWave."""

import json
import os
import sys


def _safe_realpath(path):
    if not path:
        return ""
    try:
        return os.path.realpath(os.path.abspath(str(path)))
    except OSError:
        return os.path.abspath(str(path))


def safe_isdir(path):
    """Best-effort directory check that avoids waking/stalling macOS volumes."""
    if not path:
        return False
    try:
        parts = path.replace("\\", "/").split("/")
        if is_macos_volumes_path(path):
            return True
        return os.path.isdir(path)
    except OSError:
        return False


def is_macos_volumes_path(path):
    if sys.platform != "darwin" or not path:
        return False
    parts = os.path.abspath(os.path.expanduser(path)).replace("\\", "/").split("/")
    return len(parts) >= 3 and parts[1] == "Volumes" and bool(parts[2])


def load_json_file(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def save_json_file(path, data):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
    except OSError:
        pass


def ensure_user_content_structure(base_dir):
    """Create standard user-content subdirectories inside base_dir if missing."""
    for sub in ("Channels", "Commercials", "Music", "Fonts", "Themes", "Converted", "Settings", "Cache"):
        try:
            os.makedirs(os.path.join(base_dir, sub), exist_ok=True)
        except OSError:
            pass

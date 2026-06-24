"""Shared filesystem and JSON helpers for MediaWave."""

import json
import os
import sys
import time


PATH_ACCESS_OK = "ok"
PATH_ACCESS_MISSING = "missing"
PATH_ACCESS_NOT_DIRECTORY = "not_directory"
PATH_ACCESS_PERMISSION_DENIED = "permission_denied"
PATH_ACCESS_UNREADABLE = "unreadable"
PATH_ACCESS_DISCONNECTED_VOLUME = "disconnected_volume"
PATH_ACCESS_EMPTY = "empty"
PATH_ACCESS_NO_MEDIA_FOUND = "no_media_found"
PATH_ACCESS_SLOW_OR_TIMEOUT = "slow_or_timeout"


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


def is_network_like_path(path):
    if not path:
        return False
    text = str(path).strip()
    normalized = text.replace("\\", "/")
    if text.startswith("\\\\"):
        return True
    if normalized.startswith("//"):
        return True
    if is_macos_volumes_path(text):
        return True
    lowered = normalized.lower()
    network_markers = (
        "/net/",
        "/network/",
        "/mnt/",
        "/media/",
        "/run/user/",
        "smb:",
        "afp:",
        "nfs:",
    )
    if any(marker in lowered for marker in network_markers):
        return True
    if sys.platform == "win32" and len(text) >= 2 and text[1] == ":":
        return True
    return False


def _path_result(status, path, message="", elapsed_ms=0.0, entries=None):
    return {
        "status": status,
        "path": path,
        "ok": status in {PATH_ACCESS_OK, PATH_ACCESS_EMPTY},
        "network_like": is_network_like_path(path),
        "message": message or describe_path_access_issue(path, status),
        "elapsed_ms": elapsed_ms,
        "entries": entries,
    }


def classify_path_access(path, slow_threshold_seconds=2.0):
    normalized = os.path.abspath(os.path.expanduser(str(path or ""))) if path else ""
    if not normalized:
        return _path_result(PATH_ACCESS_MISSING, path, "No folder was selected.")
    if is_macos_volumes_path(normalized):
        parts = normalized.replace("\\", "/").split("/")
        volume_root = "/" + "/".join(parts[1:3]) if len(parts) >= 3 else normalized
        if not os.path.exists(volume_root):
            return _path_result(PATH_ACCESS_DISCONNECTED_VOLUME, normalized)
    started = time.monotonic()
    try:
        if not os.path.exists(normalized):
            return _path_result(PATH_ACCESS_MISSING, normalized)
        if not os.path.isdir(normalized):
            return _path_result(PATH_ACCESS_NOT_DIRECTORY, normalized)
        entries = os.listdir(normalized)
    except PermissionError:
        return _path_result(PATH_ACCESS_PERMISSION_DENIED, normalized)
    except OSError:
        return _path_result(PATH_ACCESS_UNREADABLE, normalized)
    elapsed = time.monotonic() - started
    if elapsed > slow_threshold_seconds:
        return _path_result(PATH_ACCESS_SLOW_OR_TIMEOUT, normalized, elapsed_ms=elapsed * 1000.0, entries=entries)
    if not entries:
        return _path_result(PATH_ACCESS_EMPTY, normalized, elapsed_ms=elapsed * 1000.0, entries=entries)
    return _path_result(PATH_ACCESS_OK, normalized, elapsed_ms=elapsed * 1000.0, entries=entries)


def describe_path_access_issue(path, status=None):
    status = status or classify_path_access(path).get("status")
    if status == PATH_ACCESS_OK:
        return "Folder is available."
    if status == PATH_ACCESS_EMPTY:
        return "The selected folder is empty."
    if status == PATH_ACCESS_MISSING:
        return "The folder could not be found. If it is on a NAS, mapped drive, SMB share, or external drive, make sure it is mounted and try again."
    if status == PATH_ACCESS_NOT_DIRECTORY:
        return "The selected path is a file, not a folder."
    if status == PATH_ACCESS_PERMISSION_DENIED:
        return "MediaWave does not have permission to read this folder."
    if status == PATH_ACCESS_DISCONNECTED_VOLUME:
        return "This macOS /Volumes path looks disconnected. Reconnect or remount the drive/share, then choose the folder again."
    if status == PATH_ACCESS_SLOW_OR_TIMEOUT:
        return "This folder responded slowly. It may be on a NAS or network share; scans can take longer there."
    if status == PATH_ACCESS_UNREADABLE:
        return "MediaWave could not read this folder. It may be disconnected, unavailable, or blocked by permissions."
    return "MediaWave could not access this folder."


def safe_iter_media_folder(path):
    try:
        return os.scandir(path)
    except PermissionError:
        print(f"[PathAccess][warn] permission_denied: {path}", flush=True)
    except OSError:
        print(f"[PathAccess][warn] unreadable: {path}", flush=True)
    return ()


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

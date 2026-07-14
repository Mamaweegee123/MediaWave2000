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

PATH_LOCATION_LOCAL = "local"
PATH_LOCATION_EXTERNAL = "external"
PATH_LOCATION_NETWORK = "network"


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


def is_external_volume_path(path):
    return is_macos_volumes_path(path)


def is_network_like_path(path):
    if not path:
        return False
    text = str(path).strip()
    normalized = text.replace("\\", "/")
    if text.startswith("\\\\"):
        return True
    if normalized.startswith("//"):
        return True
    lowered = normalized.lower()
    network_markers = (
        "/net/",
        "/network/",
        "/run/user/",
        "smb:",
        "afp:",
        "nfs:",
    )
    if any(marker in lowered for marker in network_markers):
        return True
    return False


def path_location_kind(path):
    if is_network_like_path(path):
        return PATH_LOCATION_NETWORK
    if is_external_volume_path(path):
        return PATH_LOCATION_EXTERNAL
    return PATH_LOCATION_LOCAL


def _path_result(status, path, message="", elapsed_ms=0.0, entries=None):
    location = path_location_kind(path)
    return {
        "status": status,
        "path": path,
        "ok": status in {PATH_ACCESS_OK, PATH_ACCESS_EMPTY},
        "location": location,
        "network_like": location == PATH_LOCATION_NETWORK,
        "external_like": location == PATH_LOCATION_EXTERNAL,
        "message": message or describe_path_access_issue(path, status),
        "elapsed_ms": elapsed_ms,
        "entries": entries,
    }


def classify_path_access(path, slow_threshold_seconds=2.0):
    raw = str(path or "")
    if not raw:
        return _path_result(PATH_ACCESS_MISSING, path, "No folder was selected.")
    if is_network_like_path(raw) and (raw.startswith("\\\\") or raw.startswith("//") or "://" in raw):
        normalized = raw
    else:
        normalized = os.path.abspath(os.path.expanduser(raw))
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
        if path_location_kind(path) == PATH_LOCATION_NETWORK:
            return "MediaWave can't reach this network library folder."
        if path_location_kind(path) == PATH_LOCATION_EXTERNAL:
            return "The saved library folder is not available right now."
        return "The folder could not be found."
    if status == PATH_ACCESS_NOT_DIRECTORY:
        return "The selected path is a file, not a folder."
    if status == PATH_ACCESS_PERMISSION_DENIED:
        return "MediaWave can't read this folder."
    if status == PATH_ACCESS_DISCONNECTED_VOLUME:
        return "The saved library folder is not available right now."
    if status == PATH_ACCESS_SLOW_OR_TIMEOUT:
        return "This folder responded slowly."
    if status == PATH_ACCESS_UNREADABLE:
        return "MediaWave can't read this folder."
    return "MediaWave could not access this folder."


def no_catalog_selected_status():
    return {
        "title": "Library Status",
        "message": "Choose a folder containing your shows and movies to get started.",
        "path": "",
        "detail": "",
        "severity": "info",
    }


def format_library_path_status(path, access=None):
    access = access or classify_path_access(path)
    status = access.get("status")
    folder = access.get("path") or path or ""
    location = access.get("location") or path_location_kind(folder)
    is_network = location == PATH_LOCATION_NETWORK
    is_external = location == PATH_LOCATION_EXTERNAL

    if status in {PATH_ACCESS_OK, PATH_ACCESS_EMPTY, PATH_ACCESS_SLOW_OR_TIMEOUT}:
        detail = "Network library detected — make sure it stays connected while watching." if is_network else ""
        return {
            "title": "Library ready",
            "message": f"Using: {folder}" if folder else "Library ready",
            "path": folder,
            "detail": detail,
            "severity": "info",
        }
    if status == PATH_ACCESS_DISCONNECTED_VOLUME or (status == PATH_ACCESS_MISSING and is_external):
        return {
            "title": "Drive not found",
            "message": "Your saved library folder is not available right now. Connect the drive, then choose the folder again.",
            "path": folder,
            "detail": "",
            "severity": "warning",
        }
    if status == PATH_ACCESS_MISSING and is_network:
        return {
            "title": "Network library unavailable",
            "message": "MediaWave can't reach your saved library folder. Make sure the NAS, mapped drive, or shared folder is connected, then choose the folder again.",
            "path": folder,
            "detail": "",
            "severity": "warning",
        }
    if status in {PATH_ACCESS_PERMISSION_DENIED, PATH_ACCESS_UNREADABLE}:
        return {
            "title": "Folder unavailable",
            "message": "MediaWave can't read this folder. Check permissions or choose a different folder.",
            "path": folder,
            "detail": "",
            "severity": "warning",
        }
    if status == PATH_ACCESS_NOT_DIRECTORY:
        return {
            "title": "Choose a folder",
            "message": "The selected item is not a folder. Choose the folder that contains your shows and movies.",
            "path": folder,
            "detail": "",
            "severity": "warning",
        }
    return {
        "title": "Folder unavailable",
        "message": "MediaWave can't open this library folder. Choose a different folder and try again.",
        "path": folder,
        "detail": "",
        "severity": "warning",
    }


def format_no_playable_media_message(path, network_like=False):
    message = "No playable media found in this folder. Try choosing the folder that contains your show or movie files."
    if network_like:
        message += "\nIf this is a network library, make sure it is mounted and readable."
    return message


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
    """Create standard user-content subdirectories inside base_dir if missing.

    "Logos" is the shared, portable channel-logo folder every channel --
    local or companion -- resolves its bug logo through (see
    mediawave.channel_logos.find_channel_bug_logo's shared_logos_dir
    fallback); it needs to exist for every user, not just first-run ones,
    which is why callers should invoke this unconditionally on every
    startup, not only when guiding a brand-new install.
    """
    for sub in ("Channels", "Commercials", "Music", "Fonts", "Themes", "Converted", "Settings", "Cache", "Logos"):
        try:
            os.makedirs(os.path.join(base_dir, sub), exist_ok=True)
        except OSError:
            pass

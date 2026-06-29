"""Pure NetTV cache and metadata helpers."""

import time
import urllib.parse


NETTV_STREAM_EXPIRY_MARGIN_SECONDS = 120
NETTV_STREAM_DEFAULT_TTL_SECONDS = 30 * 60


def nettv_uploader(entry):
    if not isinstance(entry, dict):
        return ""
    return str(
        entry.get("uploader")
        or entry.get("channel")
        or entry.get("channel_name")
        or entry.get("creator")
        or ""
    ).strip()


def nettv_uploader_summary(entry):
    uploader = nettv_uploader(entry)
    return f"Uploaded by {uploader}" if uploader else ""


def merge_nettv_metadata(entry, metadata):
    merged = dict(entry or {})
    metadata = metadata if isinstance(metadata, dict) else {}
    for key in ("id", "title", "duration", "thumbnail", "url"):
        if metadata.get(key) not in (None, ""):
            if key == "url" and merged.get("url"):
                continue
            merged[key] = metadata[key]
    uploader = nettv_uploader(metadata)
    if uploader:
        merged["uploader"] = uploader
    return merged


def stream_url_expiry(stream_url, now=None):
    now = float(time.time() if now is None else now)
    try:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(str(stream_url or "")).query)
        expiry = float((query.get("expire") or [0])[0] or 0)
    except (TypeError, ValueError):
        expiry = 0.0
    return expiry if expiry > now else now + NETTV_STREAM_DEFAULT_TTL_SECONDS


def cached_stream_url(record, now=None, margin=NETTV_STREAM_EXPIRY_MARGIN_SECONDS):
    if not isinstance(record, dict):
        return ""
    stream_url = str(record.get("stream_url") or "").strip()
    if not stream_url:
        return ""
    now = float(time.time() if now is None else now)
    expires_at = float(record.get("expires_at") or 0)
    if expires_at <= now + max(0.0, float(margin or 0)):
        return ""
    return stream_url


def build_session_record(entry, stream_url, expires_at, schedule_position=-1, now=None):
    source_entry = merge_nettv_metadata({}, entry)
    entry = {
        key: source_entry[key]
        for key in ("id", "url", "path", "title", "duration", "thumbnail", "uploader")
        if source_entry.get(key) not in (None, "")
    }
    return {
        "entry": entry,
        "path": entry.get("path", ""),
        "video_id": entry.get("id", ""),
        "stream_url": str(stream_url or ""),
        "expires_at": float(expires_at or 0),
        "schedule_position": int(schedule_position),
        "updated_at": float(time.time() if now is None else now),
    }


def next_nettv_schedule_entry(entries, current_path=""):
    if not entries:
        return {}, -1
    current_path = str(current_path or "")
    current_index = -1
    for index, entry in enumerate(entries):
        youtube_entry = entry.get("youtube_entry") or {}
        if youtube_entry.get("path") == current_path or entry.get("path") == current_path:
            current_index = index
            break
    start_index = (current_index + 1) % len(entries) if current_index >= 0 else 0
    for step in range(len(entries)):
        index = (start_index + step) % len(entries)
        candidate = entries[index]
        youtube_entry = dict(candidate.get("youtube_entry") or {})
        if youtube_entry.get("placeholder"):
            continue
        youtube_entry.setdefault("path", candidate.get("path", ""))
        youtube_entry.setdefault("title", candidate.get("title", "NetTV Video"))
        youtube_entry.setdefault("duration", float(candidate.get("duration", 900.0) or 900.0))
        return youtube_entry, index
    return {}, -1

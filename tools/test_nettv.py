"""Smoke tests for NetTV playlist normalization and failure messages."""

import os
import sys
import threading
import time
from types import SimpleNamespace

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import channelsurfer2000 as app
from mediawave.nettv import (
    build_session_record,
    cached_stream_url,
    merge_nettv_metadata,
    nettv_uploader,
    nettv_uploader_summary,
    stream_url_expiry,
)


PASS = []
FAIL = []


def check(name, expression, detail=""):
    if expression:
        PASS.append(name)
        print(f"  OK  {name}")
    else:
        FAIL.append(name)
        print(f"FAIL  {name}" + (f"  ({detail})" if detail else ""))


print("\n--- playlist normalization ---")
source_entries = [
    {
        "id": f"video-{index}",
        "title": f"Video {index}",
        "url": f"https://www.youtube.com/watch?v=video-{index}",
        "duration": 60 + index,
    }
    for index in range(5000)
]
normalized = app.normalize_youtube_playlist_entries(
    {"entries": source_entries},
    "https://www.youtube.com/playlist?list=long-test",
)
check("5,000 item playlist normalization retains every exposed entry", len(normalized) == 5000, len(normalized))
check("playlist bound accommodates 5,000 entries", app.NETTV_PLAYLIST_MAX_ENTRIES >= 5000)
check("playlist indexing allows extra time", app.NETTV_PLAYLIST_INDEX_TIMEOUT_SECONDS >= 90)


print("\n--- stream and session cache ---")
now = 1_700_000_000
expiring_url = f"https://video.example/stream.mp4?expire={now + 900}"
expires_at = stream_url_expiry(expiring_url, now=now)
check("stream expiry is read from URL", expires_at == now + 900, expires_at)
check("unexpired cached stream is reusable", cached_stream_url({"stream_url": expiring_url, "expires_at": expires_at}, now=now) == expiring_url)
check("nearly expired stream is rejected", cached_stream_url({"stream_url": expiring_url, "expires_at": now + 60}, now=now) == "")
metadata = merge_nettv_metadata({"title": "Old"}, {"title": "Video", "uploader": "Real Channel"})
check("uploader metadata is preserved", nettv_uploader(metadata) == "Real Channel", metadata)
permanent_url = "https://www.youtube.com/watch?v=abc"
merged_url = merge_nettv_metadata({"url": permanent_url}, {"url": expiring_url})
check("temporary stream URL does not replace video page URL", merged_url["url"] == permanent_url, merged_url)
check("real uploader produces metadata line", nettv_uploader_summary(metadata) == "Uploaded by Real Channel")
check("missing uploader hides metadata line", nettv_uploader_summary({"title": "Video"}) == "")
session = build_session_record({"id": "abc", "path": "youtube://abc", "title": "Video", "uploader": "Real Channel"}, expiring_url, expires_at, 42, now=now)
check("session remembers schedule position", session["schedule_position"] == 42, session)
check("session remembers uploader", session["entry"]["uploader"] == "Real Channel", session)
sanitized_session = build_session_record({"id": "abc", "path": "youtube://abc", "_nettv_refresh_stream": True}, expiring_url, expires_at, 42, now=now)
check("session omits internal playback flags", "_nettv_refresh_stream" not in sanitized_session["entry"], sanitized_session)
cached_entry = {
    "id": "cached-direct",
    "path": "youtube://cached-direct",
    "url": "https://www.youtube.com/watch?v=cached-direct",
    "title": "Cached Direct",
}
cached_key = app.youtube_video_cache_key(cached_entry)
future_expiry = time.time() + 900
future_url = f"https://video.example/stream.mp4?expire={int(future_expiry)}"
fake_app = SimpleNamespace(
    youtube_cache_lock=threading.Lock(),
    youtube_playlist_cache_state={
        "streams": {
            cached_key: {
                "stream_url": future_url,
                "expires_at": future_expiry,
                "uploader": "Cached Uploader",
            }
        }
    },
    app_settings={},
)
cached_result, cached_error = app.ChannelSurfer.resolve_youtube_stream_url(fake_app, cached_entry)
check("resolver reuses cached stream without yt-dlp", cached_result == future_url and not cached_error, (cached_result, cached_error))
check("cached resolver restores uploader", cached_entry.get("uploader") == "Cached Uploader", cached_entry)
legacy_cache_app = SimpleNamespace(
    app_settings={"youtube_enabled": True, "youtube_playlist_url": "https://www.youtube.com/playlist?list=PLlegacy"},
    youtube_cache_lock=threading.Lock(),
    youtube_playlist_cache_state={
        "playlists": {
            app.youtube_playlist_cache_key("https://www.youtube.com/playlist?list=PLlegacy"): {
                "entries": [{"id": "one"}, {"id": "two"}],
                "updated_at": time.time(),
            }
        }
    },
)
check("legacy capped playlist cache refreshes once", app.ChannelSurfer.nettv_playlist_cache_needs_refresh(legacy_cache_app))


print("\n--- friendly failures ---")
failure_cases = [
    ("Sign in to confirm you're not a bot", "bot_verification", "browser verification"),
    ("ERROR: Private video", "private_or_unavailable", "private"),
    ("This video is age-restricted", "authentication_required", "signed-in"),
    ("This video is not available in your country", "region_restricted", "region"),
    ("HTTP Error 429: Too Many Requests", "rate_limited", "rate limiting"),
    ("The read operation timed out", "playlist_timeout", "too long"),
]
for raw_error, expected_category, expected_text in failure_cases:
    friendly, _ = app.nettv_friendly_error(raw_error)
    check(
        f"{expected_category} category",
        app.nettv_error_category(raw_error) == expected_category,
        app.nettv_error_category(raw_error),
    )
    check(
        f"{expected_category} friendly message",
        expected_text.lower() in friendly.lower(),
        friendly,
    )


print(f"\n{'=' * 50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All NetTV smoke tests passed.")

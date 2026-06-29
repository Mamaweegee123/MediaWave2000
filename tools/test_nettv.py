"""Smoke tests for NetTV playlist normalization and failure messages."""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import channelsurfer2000 as app


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
    for index in range(400)
]
normalized = app.normalize_youtube_playlist_entries(
    {"entries": source_entries},
    "https://www.youtube.com/playlist?list=long-test",
)
check("long playlist normalization retains every exposed entry", len(normalized) == 400, len(normalized))
check("long playlist bound exceeds the old 250 item limit", app.NETTV_PLAYLIST_MAX_ENTRIES > 250)
check("playlist indexing allows extra time", app.NETTV_PLAYLIST_INDEX_TIMEOUT_SECONDS >= 90)


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

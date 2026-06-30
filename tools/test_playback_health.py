"""Smoke tests for local playback health decisions."""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.playback_health import (
    LOCAL_PLAYBACK_HEALTHY,
    LOCAL_PLAYBACK_MAX_FALLBACK_ATTEMPTS,
    LOCAL_PLAYBACK_NO_AUDIO_OR_VIDEO,
    LOCAL_PLAYBACK_NO_VIDEO_FRAME,
    evaluate_local_playback_health,
    should_retry_local_playback,
    stream_expectations_from_probe,
    summarize_probe_for_log,
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


probe = {
    "format": {"format_name": "matroska,webm"},
    "streams": [
        {
            "codec_type": "video",
            "codec_name": "hevc",
            "width": 1440,
            "height": 1080,
            "pix_fmt": "yuv420p10le",
        },
        {"codec_type": "audio", "codec_name": "aac"},
    ],
}

expectations = stream_expectations_from_probe(probe)
check("probe detects video stream", expectations["has_video"])
check("probe detects audio stream", expectations["has_audio"])

status, reason = evaluate_local_playback_health(
    elapsed_seconds=8,
    position_ms=9000,
    last_position_ms=0,
    playback_state="PlayingState",
    media_status="BufferedMedia",
    expects_video=True,
    expects_audio=True,
    video_frame_seen=False,
    audio_seen=False,
)
check("timer progress without rendered video is unhealthy", status == LOCAL_PLAYBACK_NO_VIDEO_FRAME, (status, reason))
check("unhealthy video triggers first fallback", should_retry_local_playback(status, 0))
check(
    "fallback does not loop forever",
    not should_retry_local_playback(status, LOCAL_PLAYBACK_MAX_FALLBACK_ATTEMPTS),
)

status, reason = evaluate_local_playback_health(
    elapsed_seconds=8,
    position_ms=9000,
    last_position_ms=0,
    playback_state="PlayingState",
    media_status="BufferedMedia",
    expects_video=False,
    expects_audio=True,
    video_frame_seen=False,
    audio_seen=False,
)
check("progress alone is not healthy for audio-only expectation", status == LOCAL_PLAYBACK_NO_AUDIO_OR_VIDEO, (status, reason))

status, reason = evaluate_local_playback_health(
    elapsed_seconds=8,
    position_ms=9000,
    last_position_ms=0,
    playback_state="PlayingState",
    media_status="BufferedMedia",
    expects_video=True,
    expects_audio=True,
    video_frame_seen=True,
    audio_seen=False,
)
check("rendered video frame is healthy even before audio buffer tap", status == LOCAL_PLAYBACK_HEALTHY, (status, reason))

summary = summarize_probe_for_log("/Media/Top Gear.mkv", probe)
check("diagnostics include container", "matroska" in summary["summary"], summary)
check("diagnostics include codec", "hevc" in summary["summary"], summary)
check("diagnostics include resolution", "1440x1080" in summary["summary"], summary)
check("diagnostics include pixel format", "yuv420p10le" in summary["summary"], summary)

print(f"\nResults: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)

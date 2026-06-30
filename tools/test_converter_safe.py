"""Smoke tests for the MediaWave Safe MP4 converter contract."""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave_converter import (
    OUTPUT_FORMATS,
    QUALITY_PRESETS,
    SAFE_MEDIA_ENCODER_MODE,
    SAFE_MEDIA_OUTPUT_FORMAT,
    SAFE_MEDIA_PRESET,
    SAFE_MEDIA_VIDEO_FLAGS,
    _safe_media_argument,
)


preset = QUALITY_PRESETS[SAFE_MEDIA_PRESET]
output = OUTPUT_FORMATS[SAFE_MEDIA_OUTPUT_FORMAT]
assert preset["safe_compatibility"] is True
assert output["video_codec"] == "h264"
assert output["audio_codec"] == "aac"
assert SAFE_MEDIA_ENCODER_MODE == "Compatibility Mode"
assert ("-pix_fmt", "yuv420p") == SAFE_MEDIA_VIDEO_FLAGS[:2]
assert "cfr" in SAFE_MEDIA_VIDEO_FLAGS
assert "+faststart" in SAFE_MEDIA_VIDEO_FLAGS
assert _safe_media_argument(["converter", "--safe-media", "/tmp/video.mkv"]) == "/tmp/video.mkv"
assert _safe_media_argument(["converter"]) == ""

print("MediaWave Safe MP4 smoke tests passed.")

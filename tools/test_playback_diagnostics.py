"""Smoke tests for focused playback diagnostic helpers."""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.playback_diagnostics import (
    detailed_ffprobe_command,
    embedded_standalone_comparison,
    standalone_mpv_command,
    stream_render_summary,
)


probe = {
    "streams": [
        {
            "index": 0,
            "codec_type": "video",
            "codec_name": "hevc",
            "profile": "Main 10",
            "pix_fmt": "yuv420p10le",
            "bits_per_raw_sample": "10",
            "width": 3840,
            "height": 2160,
            "field_order": "tt",
            "color_transfer": "smpte2084",
            "color_primaries": "bt2020",
        },
        {"index": 1, "codec_type": "audio", "codec_name": "aac", "channels": 2},
    ]
}

summary = stream_render_summary(probe)
assert summary[0]["codec"] == "hevc"
assert summary[0]["bit_depth"] == "10"
assert summary[0]["hdr_likely"] is True
assert summary[0]["interlaced"] is True
assert summary[1]["codec_type"] == "audio"

assert "-show_streams" in detailed_ffprobe_command("ffprobe", "/tmp/test.mkv")
mpv_command = standalone_mpv_command("mpv", "/tmp/test.mkv", frames=30)
assert "--hwdec=no" in mpv_command
assert "--frames=30" in mpv_command
assert "--msg-level=all=v" in mpv_command

comparison = embedded_standalone_comparison(
    {"visible_frame_painted": False},
    {"available": True, "returncode": 0},
)
assert "standalone mpv decoded" in comparison

print("Playback diagnostics smoke tests passed.")

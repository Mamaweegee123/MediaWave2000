"""Tests for Commercial Cutter's read-only Smart Detect analysis."""

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.commercial_cutter_smart_detect import (
    DetectionEvent,
    build_audio_detection_command,
    build_suggestions,
    build_video_detection_command,
    confidence_label,
    detect_commercial_suggestions,
    merge_nearby_boundaries,
)


events = [
    DetectionEvent(30.0, "black"),
    DetectionEvent(30.4, "silence"),
    DetectionEvent(30.7, "scene"),
    DetectionEvent(60.0, "black"),
]
merged = merge_nearby_boundaries(events, within_seconds=1.0)
assert len(merged) == 2
assert merged[0].signals == ("black", "scene", "silence")
assert 30.0 < merged[0].time_seconds < 30.7

tiny_filtered = build_suggestions(
    [DetectionEvent(3.0, "black"), DetectionEvent(30.0, "black")],
    60.0,
    minimum_seconds=5.0,
)
assert all(item.duration >= 5.0 for item in tiny_filtered)
assert all(item.start_seconds != 0 or item.end_seconds != 3.0 for item in tiny_filtered)

max_filtered = build_suggestions(
    [DetectionEvent(10.0, "black")],
    400.0,
    maximum_seconds=300.0,
)
assert len(max_filtered) == 1
assert max_filtered[0].end_seconds == 10.0
assert all(item.duration <= 300.0 for item in max_filtered)

preset_events = [
    DetectionEvent(10.0, "scene"),
    DetectionEvent(20.0, "silence"),
    DetectionEvent(30.0, "scene"),
    DetectionEvent(40.0, "black"),
]
conservative = build_suggestions(preset_events, 50.0, "Conservative")
normal = build_suggestions(preset_events, 50.0, "Normal")
aggressive = build_suggestions(preset_events, 50.0, "Aggressive")
assert len(conservative) <= len(normal) < len(aggressive)
assert build_suggestions(preset_events, 50.0, "Lax") == conservative

assert confidence_label(0.80) == "High confidence"
assert confidence_label(0.60) == "Medium confidence"
assert confidence_label(0.30) == "Low confidence"

mock_events = [
    DetectionEvent(15.0, "black"),
    DetectionEvent(15.2, "silence"),
    DetectionEvent(15.3, "scene"),
    DetectionEvent(45.0, "black"),
    DetectionEvent(45.1, "scene"),
]
suggestions = build_suggestions(mock_events, 60.0, "Normal")
assert len(suggestions) == 3
assert suggestions[1].start_seconds > 15.0
assert "black frame" in suggestions[1].reasons
assert "scene cut" in suggestions[1].reasons
assert suggestions[1].confidence_label == "High confidence"

short_gap_events = [
    DetectionEvent(10.0, "black"),
    DetectionEvent(20.0, "black"),
    DetectionEvent(23.0, "black"),
    DetectionEvent(40.0, "black"),
]
normal_gap_suggestions = build_suggestions(short_gap_events, 50.0, "Normal", minimum_seconds=5.0)
aggressive_gap_suggestions = build_suggestions(short_gap_events, 50.0, "Aggressive", minimum_seconds=5.0)
assert any(item.start_seconds == 10.0 and item.end_seconds == 40.0 for item in normal_gap_suggestions)
assert len(normal_gap_suggestions) < len(aggressive_gap_suggestions)

video_command = build_video_detection_command("ffmpeg", Path("source.mp4"), "Normal")
audio_command = build_audio_detection_command("ffmpeg", Path("source.mp4"), "Normal")
for command in (video_command, audio_command):
    assert command[-3:] == ["-f", "null", "-"]
    assert "-f" in command and command[command.index("-f") + 1] == "null"
    assert command[-1] == "-"

with TemporaryDirectory() as temp_dir:
    folder = Path(temp_dir)
    source = folder / "source.mp4"
    source.write_bytes(b"unchanged source")
    before_names = sorted(path.name for path in folder.iterdir())
    commands: list[list[str]] = []

    def fake_runner(command, **_kwargs):
        commands.append(command)
        if command[0] == "ffprobe":
            payload = {
                "format": {"duration": "60.0"},
                "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
            }
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")
        if "-vf" in command:
            log = (
                "[blackdetect] black_start:14.8 black_end:15.2 black_duration:0.4\n"
                "[Parsed_showinfo] n:1 pts:15 pts_time:15.1\n"
                "[blackdetect] black_start:44.8 black_end:45.2 black_duration:0.4\n"
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr=log)
        log = "[silencedetect] silence_start: 14.7\n[silencedetect] silence_end: 15.3 | silence_duration: 0.6\n"
        return subprocess.CompletedProcess(command, 0, stdout="", stderr=log)

    result = detect_commercial_suggestions(
        source,
        "Normal",
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
        runner=fake_runner,
    )
    assert len(result.suggestions) == 3
    assert source.read_bytes() == b"unchanged source"
    assert sorted(path.name for path in folder.iterdir()) == before_names
    assert all(command[0] == "ffprobe" or command[-1] == "-" for command in commands)

print("Commercial Cutter Smart Detect tests passed.")

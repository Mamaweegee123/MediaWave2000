"""Focused tests for MediaWave Converter command building and progress parsing."""

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import mediawave_converter as converter
from mediawave_converter import (
    AudioStreamInfo,
    BatchWorker,
    ConversionOptions,
    ProbeInfo,
    QUALITY_PRESETS,
    SAFE_MEDIA_OUTPUT_FORMAT,
    SAFE_MEDIA_PRESET,
    audio_copy_is_safe,
    default_encoder_mode,
    ffmpeg_progress_snapshot,
    format_progress_detail,
    parse_ffmpeg_progress_line,
    shell_quote_command,
)


converter.FFMPEG_PATH = "ffmpeg"
converter.FFPROBE_PATH = "ffprobe"


def make_options(
    framing_mode: str,
    *,
    quality_label: str = SAFE_MEDIA_PRESET,
    output_format: str = SAFE_MEDIA_OUTPUT_FORMAT,
) -> ConversionOptions:
    return ConversionOptions(
        source_root=Path("/tmp/source"),
        output_root=Path("/tmp/output"),
        aspect_label="Widescreen",
        target_width=1280,
        target_height=720,
        framing_mode=framing_mode,
        crop_aggressiveness=0,
        quality_label=quality_label,
        encoder_mode="Compatibility Mode",
        output_format=output_format,
        recursive=False,
        skip_completed=False,
        audio_preference="Auto",
        audio_leveling_enabled=False,
        subtitle_preference="No Subtitles",
    )


def make_worker(framing_mode: str) -> BatchWorker:
    return BatchWorker(make_options(framing_mode))


def make_probe(audio_codec: str = "aac") -> ProbeInfo:
    return ProbeInfo(
        duration=120.0,
        width=640,
        height=480,
        has_audio=True,
        video_codec="h264",
        audio_codec=audio_codec,
        audio_streams=[
            AudioStreamInfo(
                ffmpeg_index=1,
                audio_index=0,
                codec=audio_codec,
                language="eng",
                title="",
                channels=2,
            )
        ],
        subtitle_streams=[],
    )


def assert_contains_in_order(values: list[str], expected: list[str]) -> None:
    cursor = 0
    for item in expected:
        found = False
        while cursor < len(values):
            if values[cursor] == item:
                found = True
                cursor += 1
                break
            cursor += 1
        assert found, f"Could not find {item!r} in order inside {values!r}"


keep_worker = make_worker("Keep More Picture")
keep_crop = keep_worker.apply_target_aspect((0, 0, 640, 480), 640, 480)
assert keep_crop == (0, 0, 640, 480)
keep_filter, keep_complex = keep_worker.build_video_filter(Path("/tmp/four-three.mp4"), *keep_crop)
assert keep_complex is False
assert "pad=1280:720" in keep_filter
assert "color=black" in keep_filter
assert "gblur" not in keep_filter
assert "split=2" not in keep_filter

fill_worker = make_worker("Fill Screen More")
fill_crop = fill_worker.apply_target_aspect((0, 0, 640, 480), 640, 480)
assert fill_crop == (0, 60, 640, 360)
fill_filter, fill_complex = fill_worker.build_video_filter(Path("/tmp/four-three.mp4"), *fill_crop)
assert fill_complex is False
assert fill_filter.startswith("crop=640:360:0:60,scale=1280:720")
assert "pad=" not in fill_filter
assert "gblur" not in fill_filter

blur_worker = make_worker("Blurred Fill")
blur_crop = blur_worker.apply_target_aspect((0, 0, 640, 480), 640, 480)
assert blur_crop == (0, 0, 640, 480)
blur_filter, blur_complex = blur_worker.build_video_filter(Path("/tmp/four-three.mp4"), *blur_crop)
assert blur_complex is True
assert "gblur=sigma=28" in blur_filter
assert "overlay=(W-w)/2:(H-h)/2" in blur_filter

probe = make_probe("aac")
audio = probe.audio_streams[0]
command = keep_worker.build_transcode_command(
    Path("/tmp/four-three.mp4"),
    Path("/tmp/output.mp4"),
    probe,
    keep_crop,
    "libx264",
    audio,
    None,
    "No Subtitles",
)
assert_contains_in_order(command, ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "0"])
assert_contains_in_order(command, ["-c:a", "copy"])
assert "-filter_complex" not in command
assert "-vf" in command
assert "pad=1280:720" in command[command.index("-vf") + 1]
assert QUALITY_PRESETS[SAFE_MEDIA_PRESET]["preset"] == "veryfast"
assert default_encoder_mode() == "Compatibility Mode"

ac3_probe = make_probe("ac3")
ac3_command = keep_worker.build_transcode_command(
    Path("/tmp/four-three.mkv"),
    Path("/tmp/output.mp4"),
    ac3_probe,
    keep_crop,
    "libx264",
    ac3_probe.audio_streams[0],
    None,
    "No Subtitles",
)
assert_contains_in_order(ac3_command, ["-c:a", "aac"])
assert audio_copy_is_safe("aac", "aac", audio_leveling=False) is True
assert audio_copy_is_safe("aac", "aac", audio_leveling=True) is False
assert audio_copy_is_safe("ac3", "aac", audio_leveling=False) is False

progress_data: dict[str, str] = {}
assert parse_ffmpeg_progress_line("out_time_ms=60000000", progress_data) is not None
assert parse_ffmpeg_progress_line("speed=1.8x", progress_data) is not None
assert parse_ffmpeg_progress_line("total_size=47185920", progress_data) is not None
snapshot = ffmpeg_progress_snapshot(
    progress_data,
    duration=120.0,
    elapsed_seconds=600.0,
    completed_units=3.5,
    total_units=18,
)
assert snapshot.percent == 50
assert snapshot.speed == "1.8x"
assert snapshot.output_size == "45.0 MB"
assert snapshot.remaining_seconds is not None and snapshot.remaining_seconds > 0
detail = format_progress_detail(snapshot, file_index=4, total_files=18, file_name="Episode 04.mkv")
assert "Converting 4 of 18" in detail
assert "Episode 04.mkv" in detail
assert "50%" in detail
assert "1.8x" in detail
assert "about" in detail and "remaining" in detail

end_snapshot = ffmpeg_progress_snapshot({"progress": "end"}, duration=120.0)
assert end_snapshot.stage == "Finalizing file"

with tempfile.TemporaryDirectory() as tmp:
    output_path = Path(tmp) / "not-created.mp4"
    generated = keep_worker.build_transcode_command(
        Path(tmp) / "missing source.mp4",
        output_path,
        probe,
        keep_crop,
        "libx264",
        audio,
        None,
        "No Subtitles",
    )
    quoted = shell_quote_command(generated)
    assert "missing source.mp4" in quoted
    assert not output_path.exists(), "building a debug command must not execute ffmpeg or create files"

print("Converter pipeline command/progress tests passed.")

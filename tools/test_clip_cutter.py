"""Focused tests for MediaWave Converter's Commercial Cutter helpers."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.clip_cutter import (
    ClipQueue,
    ClipSegment,
    InvalidClipRange,
    NonAdjacentClipMergeError,
    TinyClipError,
    build_accurate_cut_command,
    build_fast_cut_command,
    format_timestamp,
    next_available_output_path,
    plan_output_paths,
    sanitize_filename,
)


def assert_raises(error_type, function, *args, **kwargs) -> None:
    try:
        function(*args, **kwargs)
    except error_type:
        return
    raise AssertionError(f"Expected {error_type.__name__}")


assert format_timestamp(0) == "00:00:00"
assert format_timestamp(83.9) == "00:01:23"
assert format_timestamp(3723) == "01:02:03"
assert format_timestamp(-4) == "00:00:00"

assert sanitize_filename(' Commercials: Sept/1993? ') == "Commercials_ Sept_1993_"
assert sanitize_filename("CON") == "_CON"
assert sanitize_filename("...   ") == "Untitled Video"

queue = ClipQueue()
first = queue.add(83.25, 114.5)
second = queue.add(190, 222)
assert queue.clips == (first, second)
assert len(queue) == 2
assert queue.remove_last() == second
assert queue.clips == (first,)
queue.add(190, 222)
queue.remove_first(1)
assert queue.clips == (second,)
queue.clear()
assert queue.clips == ()
assert queue.remove_last() is None

queue.add(70, 82, origin="Smart suggestion", confidence=0.8, reasons=("black frame",))
queue.add(82, 95, origin="Smart suggestion", confidence=0.9, reasons=("audio dip",))
queue.add(130, 145)
merged_two = queue.merge_indices([0, 1])
assert merged_two.start_seconds == 70
assert merged_two.end_seconds == 95
assert merged_two.origin == "Merged"
assert merged_two.reasons == ("black frame", "audio dip")
assert [clip.start_seconds for clip in queue.clips] == [70, 130]
queue.clear()

queue.add(10, 20)
queue.add(20, 30)
queue.add(30, 40)
queue.add(90, 100)
merged_three = queue.merge_indices([0, 1, 2])
assert merged_three.start_seconds == 10
assert merged_three.end_seconds == 40
assert [clip.start_seconds for clip in queue.clips] == [10, 90]
assert len(plan_output_paths(Path("/clips"), "Commercials", len(queue))) == 2
queue.clear()

queue.add(10, 20)
queue.add(20, 30)
queue.add(30, 40)
assert_raises(NonAdjacentClipMergeError, queue.merge_indices, [0, 2])
queue.clear()

queue.add(10, 25)
queue.add(20, 30)
assert_raises(InvalidClipRange, queue.merge_indices, [0, 1])
queue.clear()

smart = queue.add(
    10,
    40,
    origin="Smart suggestion",
    confidence=0.82,
    reasons=("black frame", "audio dip"),
)
updated = queue.update_range(0, 11, 39)
assert updated.origin == "Smart suggestion"
assert updated.confidence == 0.82
assert updated.reasons == smart.reasons
assert queue.remove_at(0) == updated
assert len(queue) == 0

assert_raises(InvalidClipRange, queue.add, 10, 10)
assert_raises(InvalidClipRange, queue.add, 12, 10)
assert_raises(InvalidClipRange, queue.add, -1, 2)
assert_raises(TinyClipError, queue.add, 1, 1.5)
tiny = queue.add(1, 1.5, allow_tiny=True)
assert tiny.duration == 0.5

with TemporaryDirectory() as temp_dir:
    folder = Path(temp_dir)
    (folder / "Commercials - Clip 001.mp4").touch()
    path, number = next_available_output_path(folder, "Commercials")
    assert path.name == "Commercials - Clip 002.mp4"
    assert number == 2
    planned = plan_output_paths(folder, "Commercials", 2)
    assert [item.name for item in planned] == [
        "Commercials - Clip 002.mp4",
        "Commercials - Clip 003.mp4",
    ]

clip = ClipSegment(83.25, 114.5)
source = Path("/videos/Commercials from Sept 1993.mkv")
output = Path("/clips/Commercials from Sept 1993 - Clip 001.mp4")

accurate = build_accurate_cut_command("/tools/ffmpeg", source, output, clip)
assert accurate[:2] == ["/tools/ffmpeg", "-n"]
assert accurate[accurate.index("-ss") + 1] == "83.250"
assert accurate.index("-ss") < accurate.index("-i")
assert accurate[accurate.index("-t") + 1] == "31.250"
assert accurate[accurate.index("-c:v") + 1] == "libx264"
assert accurate[accurate.index("-pix_fmt") + 1] == "yuv420p"
assert accurate[accurate.index("-c:a") + 1] == "aac"
assert "+faststart" in accurate
assert accurate[-1] == str(output)

fast = build_fast_cut_command("/tools/ffmpeg", source, output, clip)
assert fast.index("-i") < fast.index("-ss")
assert fast[fast.index("-c") + 1] == "copy"
assert fast[fast.index("-avoid_negative_ts") + 1] == "make_zero"
assert fast[-1] == str(output)

print("Commercial Cutter helper tests passed.")

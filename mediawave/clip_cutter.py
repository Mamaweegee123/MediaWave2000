"""Pure helpers for MediaWave Converter's Commercial Cutter."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path


MIN_CLIP_SECONDS = 1.0
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class InvalidClipRange(ValueError):
    """Raised when a clip cannot be added to the queue."""


class TinyClipError(InvalidClipRange):
    """Raised when a clip is shorter than the accidental-clip threshold."""


@dataclass(frozen=True)
class ClipSegment:
    start_seconds: float
    end_seconds: float
    origin: str = "Manual"
    confidence: float | None = None
    reasons: tuple[str, ...] = ()

    @property
    def duration(self) -> float:
        return self.end_seconds - self.start_seconds


class ClipQueue:
    """Small validated queue used by the cutter UI."""

    def __init__(self) -> None:
        self._clips: list[ClipSegment] = []

    @property
    def clips(self) -> tuple[ClipSegment, ...]:
        return tuple(self._clips)

    def __len__(self) -> int:
        return len(self._clips)

    def add(
        self,
        start_seconds: float,
        end_seconds: float,
        *,
        allow_tiny: bool = False,
        origin: str = "Manual",
        confidence: float | None = None,
        reasons: tuple[str, ...] = (),
    ) -> ClipSegment:
        if not math.isfinite(start_seconds) or not math.isfinite(end_seconds):
            raise InvalidClipRange("Clip times must be finite numbers.")
        if start_seconds < 0:
            raise InvalidClipRange("Clip start cannot be negative.")
        if end_seconds <= start_seconds:
            raise InvalidClipRange("Clip end must be after clip start.")
        clip = ClipSegment(
            float(start_seconds),
            float(end_seconds),
            origin=origin,
            confidence=confidence,
            reasons=tuple(reasons),
        )
        if clip.duration < MIN_CLIP_SECONDS and not allow_tiny:
            raise TinyClipError("This clip is under 1 second long.")
        self._clips.append(clip)
        return clip

    def remove_last(self) -> ClipSegment | None:
        return self._clips.pop() if self._clips else None

    def remove_at(self, index: int) -> ClipSegment:
        return self._clips.pop(index)

    def update_range(self, index: int, start_seconds: float, end_seconds: float) -> ClipSegment:
        existing = self._clips[index]
        if start_seconds < 0 or end_seconds <= start_seconds:
            raise InvalidClipRange("Clip end must be after clip start.")
        updated = ClipSegment(
            float(start_seconds),
            float(end_seconds),
            origin=existing.origin,
            confidence=existing.confidence,
            reasons=existing.reasons,
        )
        if updated.duration < MIN_CLIP_SECONDS:
            raise TinyClipError("This clip is under 1 second long.")
        self._clips[index] = updated
        return updated

    def remove_first(self, count: int) -> None:
        if count > 0:
            del self._clips[:count]

    def clear(self) -> None:
        self._clips.clear()


def format_timestamp(seconds: float) -> str:
    """Format playback seconds as an always-readable HH:MM:SS timestamp."""
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def sanitize_filename(value: str, *, fallback: str = "Untitled Video", max_length: int = 160) -> str:
    """Return a filename component safe on macOS, Windows, and Linux."""
    cleaned = INVALID_FILENAME_CHARS.sub("_", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        cleaned = fallback
    if cleaned.upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    cleaned = cleaned[:max_length].rstrip(" .")
    return cleaned or fallback


def next_available_output_path(
    output_folder: Path,
    source_title: str,
    *,
    start_number: int = 1,
    reserved: set[Path] | None = None,
) -> tuple[Path, int]:
    """Find the next unused ``<title> - Clip NNN.mp4`` path."""
    if start_number < 1:
        raise ValueError("Clip numbering starts at 1.")
    safe_title = sanitize_filename(source_title)
    reserved_paths = reserved or set()
    number = start_number
    while True:
        candidate = output_folder / f"{safe_title} - Clip {number:03d}.mp4"
        if not candidate.exists() and candidate not in reserved_paths:
            return candidate, number
        number += 1


def plan_output_paths(output_folder: Path, source_title: str, clip_count: int) -> list[Path]:
    """Reserve non-overwriting output paths for a queued export."""
    paths: list[Path] = []
    reserved: set[Path] = set()
    next_number = 1
    for _ in range(clip_count):
        path, used_number = next_available_output_path(
            output_folder,
            source_title,
            start_number=next_number,
            reserved=reserved,
        )
        paths.append(path)
        reserved.add(path)
        next_number = used_number + 1
    return paths


def _base_cut_command(
    ffmpeg_path: str,
    source_path: Path,
    output_path: Path,
    clip: ClipSegment,
) -> list[str]:
    if clip.start_seconds < 0 or clip.end_seconds <= clip.start_seconds:
        raise InvalidClipRange("Clip end must be after clip start.")
    return [
        ffmpeg_path,
        "-n",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-sn",
        "-dn",
    ]


def build_fast_cut_command(
    ffmpeg_path: str,
    source_path: Path,
    output_path: Path,
    clip: ClipSegment,
) -> list[str]:
    """Build a fast stream-copy command, which may begin on a nearby keyframe."""
    return [
        *_base_cut_command(ffmpeg_path, source_path, output_path, clip),
        "-ss",
        f"{clip.start_seconds:.3f}",
        "-t",
        f"{clip.duration:.3f}",
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
        str(output_path),
    ]


def build_accurate_cut_command(
    ffmpeg_path: str,
    source_path: Path,
    output_path: Path,
    clip: ClipSegment,
    *,
    preset: str = "medium",
    crf: int = 20,
    audio_bitrate: str = "192k",
) -> list[str]:
    """Build a MediaWave Safe MP4 command with frame-accurate re-encoding."""
    return [
        ffmpeg_path,
        "-n",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-ss",
        f"{clip.start_seconds:.3f}",
        "-i",
        str(source_path),
        "-t",
        f"{clip.duration:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-sn",
        "-dn",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-fps_mode",
        "cfr",
        "-c:a",
        "aac",
        "-b:a",
        audio_bitrate,
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

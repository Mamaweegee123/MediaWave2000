"""Read-only FFmpeg analysis for Commercial Cutter draft suggestions."""

from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


REASON_LABELS = {
    "black": "black frame",
    "silence": "audio dip",
    "scene": "scene cut",
}


@dataclass(frozen=True)
class SmartDetectPreset:
    name: str
    boundary_threshold: float
    scene_threshold: float
    black_duration: float
    silence_noise: str
    silence_duration: float
    merge_seconds: float
    max_suggestions: int


PRESETS = {
    "Lax": SmartDetectPreset("Lax", 0.70, 0.48, 0.18, "-42dB", 0.40, 1.5, 30),
    "Normal": SmartDetectPreset("Normal", 0.50, 0.36, 0.12, "-36dB", 0.25, 1.0, 50),
    "Aggressive": SmartDetectPreset("Aggressive", 0.20, 0.25, 0.08, "-30dB", 0.15, 0.6, 80),
}


@dataclass(frozen=True)
class DetectionEvent:
    time_seconds: float
    signal: str


@dataclass(frozen=True)
class MergedBoundary:
    time_seconds: float
    signals: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class SmartSuggestion:
    start_seconds: float
    end_seconds: float
    confidence: float
    confidence_label: str
    reasons: tuple[str, ...]

    @property
    def duration(self) -> float:
        return self.end_seconds - self.start_seconds


@dataclass(frozen=True)
class SmartDetectResult:
    duration_seconds: float
    suggestions: tuple[SmartSuggestion, ...]
    event_count: int
    has_audio: bool


class SmartDetectError(RuntimeError):
    """Raised when read-only media analysis cannot complete."""


StatusCallback = Callable[[int, str], None]
CommandRunner = Callable[..., subprocess.CompletedProcess]


def confidence_label(confidence: float) -> str:
    if confidence >= 0.75:
        return "High confidence"
    if confidence >= 0.50:
        return "Medium confidence"
    return "Low confidence"


def boundary_confidence(signals: Sequence[str]) -> float:
    unique = set(signals)
    score = 0.0
    if "black" in unique:
        score += 0.75
    if "silence" in unique:
        score += 0.38
    if "scene" in unique:
        score += 0.22
    if len(unique) >= 2:
        score += 0.12
    if len(unique) == 3:
        score += 0.08
    return min(0.99, score)


def merge_nearby_boundaries(
    events: Sequence[DetectionEvent],
    *,
    within_seconds: float,
) -> list[MergedBoundary]:
    """Merge detection events close enough to describe the same boundary."""
    valid = sorted(
        (event for event in events if math.isfinite(event.time_seconds) and event.time_seconds >= 0),
        key=lambda event: event.time_seconds,
    )
    if not valid:
        return []
    clusters: list[list[DetectionEvent]] = [[valid[0]]]
    for event in valid[1:]:
        if event.time_seconds - clusters[-1][0].time_seconds <= within_seconds:
            clusters[-1].append(event)
        else:
            clusters.append([event])
    merged: list[MergedBoundary] = []
    for cluster in clusters:
        signals = tuple(sorted({event.signal for event in cluster}))
        merged.append(
            MergedBoundary(
                time_seconds=sum(event.time_seconds for event in cluster) / len(cluster),
                signals=signals,
                confidence=boundary_confidence(signals),
            )
        )
    return merged


def build_suggestions(
    events: Sequence[DetectionEvent],
    duration_seconds: float,
    preset_name: str = "Normal",
    *,
    minimum_seconds: float = 5.0,
    maximum_seconds: float = 300.0,
) -> list[SmartSuggestion]:
    """Turn mockable detection events into bounded, reviewable clip drafts."""
    if preset_name not in PRESETS:
        raise ValueError(f"Unknown Smart Detect preset: {preset_name}")
    if duration_seconds <= 0 or minimum_seconds <= 0 or maximum_seconds < minimum_seconds:
        raise ValueError("Smart Detect duration limits are invalid.")
    preset = PRESETS[preset_name]
    boundaries = merge_nearby_boundaries(events, within_seconds=preset.merge_seconds)
    accepted = [boundary for boundary in boundaries if boundary.confidence >= preset.boundary_threshold]
    accepted = [
        boundary
        for boundary in accepted
        if minimum_seconds <= boundary.time_seconds <= duration_seconds - minimum_seconds
    ]
    if not accepted:
        return []

    points: list[tuple[float, MergedBoundary | None]] = [(0.0, None)]
    points.extend((boundary.time_seconds, boundary) for boundary in accepted)
    points.append((duration_seconds, None))

    suggestions: list[SmartSuggestion] = []
    for (start, left), (end, right) in zip(points, points[1:]):
        clip_duration = end - start
        if clip_duration < minimum_seconds or clip_duration > maximum_seconds:
            continue
        evidence = [boundary for boundary in (left, right) if boundary is not None]
        if not evidence:
            continue
        score = sum(boundary.confidence for boundary in evidence) / len(evidence)
        if len(evidence) == 2:
            score += 0.05
        if 15.0 <= clip_duration <= 120.0:
            score += 0.10
        elif clip_duration > 120.0:
            score -= 0.08
        score = max(0.0, min(0.99, score))
        signal_names = sorted({signal for boundary in evidence for signal in boundary.signals})
        reasons = tuple(REASON_LABELS.get(signal, signal) for signal in signal_names)
        suggestions.append(
            SmartSuggestion(
                start_seconds=start,
                end_seconds=end,
                confidence=score,
                confidence_label=confidence_label(score),
                reasons=reasons,
            )
        )

    if len(suggestions) > preset.max_suggestions:
        suggestions = sorted(suggestions, key=lambda item: item.confidence, reverse=True)[: preset.max_suggestions]
        suggestions.sort(key=lambda item: item.start_seconds)
    return suggestions


BLACK_RE = re.compile(
    r"black_start:(?P<start>-?\d+(?:\.\d+)?)\s+black_end:(?P<end>-?\d+(?:\.\d+)?)"
)
SILENCE_START_RE = re.compile(r"silence_start:\s*(?P<time>-?\d+(?:\.\d+)?)")
SILENCE_END_RE = re.compile(r"silence_end:\s*(?P<time>-?\d+(?:\.\d+)?)")
SCENE_RE = re.compile(r"pts_time:(?P<time>-?\d+(?:\.\d+)?)")


def parse_black_events(log_text: str) -> list[DetectionEvent]:
    events: list[DetectionEvent] = []
    for match in BLACK_RE.finditer(log_text):
        start = float(match.group("start"))
        end = float(match.group("end"))
        if end >= start:
            events.append(DetectionEvent((start + end) / 2.0, "black"))
    return events


def parse_silence_events(log_text: str, *, duration_seconds: float) -> list[DetectionEvent]:
    events: list[DetectionEvent] = []
    active_start: float | None = None
    for line in log_text.splitlines():
        start_match = SILENCE_START_RE.search(line)
        if start_match:
            active_start = max(0.0, float(start_match.group("time")))
        end_match = SILENCE_END_RE.search(line)
        if end_match and active_start is not None:
            end = min(duration_seconds, float(end_match.group("time")))
            if end >= active_start:
                events.append(DetectionEvent((active_start + end) / 2.0, "silence"))
            active_start = None
    if active_start is not None and duration_seconds >= active_start:
        events.append(DetectionEvent((active_start + duration_seconds) / 2.0, "silence"))
    return events


def parse_scene_events(log_text: str) -> list[DetectionEvent]:
    return [DetectionEvent(float(match.group("time")), "scene") for match in SCENE_RE.finditer(log_text)]


def build_probe_command(ffprobe_path: str, source_path: Path) -> list[str]:
    return [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type",
        "-of",
        "json",
        str(source_path),
    ]


def build_video_detection_command(
    ffmpeg_path: str,
    source_path: Path,
    preset_name: str,
) -> list[str]:
    preset = PRESETS[preset_name]
    video_filter = (
        f"blackdetect=d={preset.black_duration}:pix_th=0.10,"
        f"select=gt(scene\\,{preset.scene_threshold}),showinfo"
    )
    return [
        ffmpeg_path,
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "info",
        "-nostdin",
        "-i",
        str(source_path),
        "-vf",
        video_filter,
        "-an",
        "-f",
        "null",
        "-",
    ]


def build_audio_detection_command(
    ffmpeg_path: str,
    source_path: Path,
    preset_name: str,
) -> list[str]:
    preset = PRESETS[preset_name]
    return [
        ffmpeg_path,
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "info",
        "-nostdin",
        "-i",
        str(source_path),
        "-af",
        f"silencedetect=noise={preset.silence_noise}:d={preset.silence_duration}",
        "-vn",
        "-f",
        "null",
        "-",
    ]


def _run_checked(runner: CommandRunner, command: list[str]) -> subprocess.CompletedProcess:
    completed = runner(command, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "Media analysis failed.").strip()
        raise SmartDetectError(detail[-2000:])
    return completed


def detect_commercial_suggestions(
    source_path: Path,
    preset_name: str,
    *,
    ffmpeg_path: str,
    ffprobe_path: str,
    minimum_seconds: float = 5.0,
    maximum_seconds: float = 300.0,
    status_callback: StatusCallback | None = None,
    runner: CommandRunner = subprocess.run,
) -> SmartDetectResult:
    """Scan media without writing files and return suggested commercial clips."""
    if preset_name not in PRESETS:
        raise ValueError(f"Unknown Smart Detect preset: {preset_name}")
    if not source_path.is_file():
        raise SmartDetectError("The source video no longer exists.")

    def update(percent: int, message: str) -> None:
        if status_callback:
            status_callback(percent, message)

    update(5, "Reading video details…")
    probe = _run_checked(runner, build_probe_command(ffprobe_path, source_path))
    try:
        probe_data = json.loads(probe.stdout or "{}")
        duration_seconds = float(probe_data.get("format", {}).get("duration", 0))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SmartDetectError("FFprobe returned video details that could not be understood.") from exc
    stream_types = {str(stream.get("codec_type", "")) for stream in probe_data.get("streams", [])}
    if duration_seconds <= 0 or "video" not in stream_types:
        raise SmartDetectError("Smart Detect needs a readable video stream with a known duration.")

    update(20, "Scanning black frames and scene changes…")
    video = _run_checked(runner, build_video_detection_command(ffmpeg_path, source_path, preset_name))
    events = parse_black_events(video.stderr or "")
    events.extend(parse_scene_events(video.stderr or ""))

    has_audio = "audio" in stream_types
    if has_audio:
        update(70, "Scanning silence and audio dips…")
        audio = _run_checked(runner, build_audio_detection_command(ffmpeg_path, source_path, preset_name))
        events.extend(parse_silence_events(audio.stderr or "", duration_seconds=duration_seconds))

    update(92, "Combining evidence into clip suggestions…")
    suggestions = build_suggestions(
        events,
        duration_seconds,
        preset_name,
        minimum_seconds=minimum_seconds,
        maximum_seconds=maximum_seconds,
    )
    update(100, f"Found {len(suggestions)} possible clips.")
    return SmartDetectResult(duration_seconds, tuple(suggestions), len(events), has_audio)

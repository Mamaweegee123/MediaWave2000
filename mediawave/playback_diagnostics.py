"""Focused diagnostics for MediaWave's Qt Multimedia playback path."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path


DIAGNOSTIC_VERSION = 1


def detailed_ffprobe_command(ffprobe_path, media_path):
    return [
        str(ffprobe_path),
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(media_path),
    ]


def standalone_mpv_command(mpv_path, media_path, frames=120):
    return [
        str(mpv_path),
        "--no-config",
        "--hwdec=no",
        "--vo=null",
        "--ao=null",
        f"--frames={max(1, int(frames))}",
        "--msg-level=all=v",
        str(media_path),
    ]


def resolve_mpv_path(extra_candidates=None):
    candidates = list(extra_candidates or [])
    candidates.extend(
        [
            shutil.which("mpv"),
            "/opt/homebrew/bin/mpv",
            "/usr/local/bin/mpv",
            "/usr/bin/mpv",
        ]
    )
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return os.path.abspath(candidate)
    return ""


def stream_render_summary(probe):
    rows = []
    for stream in (probe or {}).get("streams") or []:
        if not isinstance(stream, dict):
            continue
        if stream.get("codec_type") == "video":
            rows.append(
                {
                    "index": stream.get("index"),
                    "codec": stream.get("codec_name"),
                    "profile": stream.get("profile"),
                    "pixel_format": stream.get("pix_fmt"),
                    "bit_depth": stream.get("bits_per_raw_sample") or stream.get("bits_per_sample"),
                    "resolution": f"{stream.get('width', 0)}x{stream.get('height', 0)}",
                    "field_order": stream.get("field_order"),
                    "interlaced": stream.get("field_order") not in (None, "", "progressive", "unknown"),
                    "color_range": stream.get("color_range"),
                    "color_space": stream.get("color_space"),
                    "color_transfer": stream.get("color_transfer"),
                    "color_primaries": stream.get("color_primaries"),
                    "hdr_likely": stream.get("color_transfer") in {"smpte2084", "arib-std-b67"},
                    "frame_rate": stream.get("avg_frame_rate") or stream.get("r_frame_rate"),
                }
            )
        elif stream.get("codec_type") == "audio":
            rows.append(
                {
                    "index": stream.get("index"),
                    "codec_type": "audio",
                    "codec": stream.get("codec_name"),
                    "profile": stream.get("profile"),
                    "sample_format": stream.get("sample_fmt"),
                    "sample_rate": stream.get("sample_rate"),
                    "channels": stream.get("channels"),
                    "channel_layout": stream.get("channel_layout"),
                }
            )
    return rows


def embedded_standalone_comparison(embedded, mpv_result):
    embedded_ok = bool((embedded or {}).get("visible_frame_painted"))
    mpv_available = bool((mpv_result or {}).get("available"))
    mpv_ok = (mpv_result or {}).get("returncode") == 0 if mpv_available else None
    if not mpv_available:
        return "Standalone mpv was not found; no external comparison was run."
    if not embedded_ok and mpv_ok:
        return "Qt embedded playback did not confirm visible output, while standalone mpv decoded the sample successfully."
    if not embedded_ok and not mpv_ok:
        return "Neither Qt embedded playback nor the standalone mpv decode sample confirmed success."
    if embedded_ok and mpv_ok:
        return "Both Qt embedded playback and the standalone mpv decode sample confirmed output."
    return "Qt embedded playback confirmed output, but the standalone mpv decode sample failed."


def collect_playback_diagnostic(
    media_path,
    output_dir,
    *,
    ffprobe_path="",
    mpv_path="",
    embedded_snapshot=None,
    mediawave_options=None,
    timeout=20,
):
    media_path = os.path.abspath(os.path.expanduser(str(media_path or "")))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_stem = "".join(c if c.isalnum() or c in " ._-" else "_" for c in Path(media_path).stem)[:80]
    report_path = output_dir / f"{stamp}-{safe_stem or 'video'}-playback-diagnostic.json"
    mpv_log_path = output_dir / f"{stamp}-{safe_stem or 'video'}-mpv-verbose.log"

    probe = {}
    probe_error = ""
    if ffprobe_path:
        try:
            completed = subprocess.run(
                detailed_ffprobe_command(ffprobe_path, media_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if completed.returncode == 0:
                probe = json.loads(completed.stdout or "{}")
            else:
                probe_error = (completed.stderr or "ffprobe failed").strip()
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            probe_error = str(exc)
    else:
        probe_error = "ffprobe not found"

    resolved_mpv = mpv_path or resolve_mpv_path()
    mpv_result = {"available": bool(resolved_mpv), "path": resolved_mpv}
    if resolved_mpv:
        command = standalone_mpv_command(resolved_mpv, media_path)
        mpv_result["command"] = command
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            verbose_output = (completed.stdout or "") + (completed.stderr or "")
            mpv_result.update(
                {
                    "returncode": completed.returncode,
                    "decode_sample_passed": completed.returncode == 0,
                    "log_path": str(mpv_log_path),
                }
            )
            mpv_log_path.write_text(verbose_output, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired as exc:
            verbose_output = ((exc.stdout or "") + (exc.stderr or "")) if isinstance(exc.stdout, str) else ""
            mpv_result.update({"returncode": None, "decode_sample_passed": False, "error": "timed out"})
            mpv_log_path.write_text(verbose_output, encoding="utf-8", errors="replace")
        except OSError as exc:
            mpv_result.update({"returncode": None, "decode_sample_passed": False, "error": str(exc)})

    embedded = dict(embedded_snapshot or {})
    report = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "media_path": media_path,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "embedded_player": "Qt Multimedia FFmpeg backend (MediaWave does not embed mpv)",
        "embedded_snapshot": embedded,
        "mediawave_options": dict(mediawave_options or {}),
        "ffprobe_path": str(ffprobe_path or ""),
        "ffprobe_error": probe_error,
        "ffprobe": probe,
        "stream_render_summary": stream_render_summary(probe),
        "standalone_mpv": mpv_result,
        "comparison": embedded_standalone_comparison(embedded, mpv_result),
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True, default=str), encoding="utf-8")
    return str(report_path), report

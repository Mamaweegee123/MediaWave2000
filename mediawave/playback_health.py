"""Pure helpers for local playback health decisions."""


LOCAL_PLAYBACK_HEALTHY = "healthy"
LOCAL_PLAYBACK_WAITING = "waiting"
LOCAL_PLAYBACK_NO_VIDEO_FRAME = "no_video_frame"
LOCAL_PLAYBACK_NO_AUDIO_OR_VIDEO = "no_audio_or_video"
LOCAL_PLAYBACK_STOPPED = "stopped"
LOCAL_PLAYBACK_STALLED = "stalled"

LOCAL_PLAYBACK_GRACE_SECONDS = 5.0
LOCAL_PLAYBACK_PROGRESS_GRACE_MS = 750
LOCAL_PLAYBACK_MAX_FALLBACK_ATTEMPTS = 1


def stream_expectations_from_probe(probe):
    streams = probe.get("streams") or [] if isinstance(probe, dict) else []
    video_streams = []
    audio_streams = []
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        codec_type = stream.get("codec_type")
        if codec_type == "video":
            video_streams.append(stream)
        elif codec_type == "audio":
            audio_streams.append(stream)
    return {
        "has_video": bool(video_streams),
        "has_audio": bool(audio_streams),
        "video_streams": video_streams,
        "audio_streams": audio_streams,
    }


def summarize_probe_for_log(path, probe):
    if not isinstance(probe, dict) or not probe:
        return {
            "path": path,
            "container": "",
            "extension": _extension(path),
            "video": [],
            "audio": [],
            "summary": "probe=unavailable",
        }
    format_name = str((probe.get("format") or {}).get("format_name") or "")
    details = {
        "path": path,
        "container": format_name,
        "extension": _extension(path),
        "video": [],
        "audio": [],
    }
    for stream in probe.get("streams") or []:
        if not isinstance(stream, dict):
            continue
        codec_type = stream.get("codec_type")
        if codec_type == "video":
            width = stream.get("width") or 0
            height = stream.get("height") or 0
            details["video"].append(
                {
                    "codec": str(stream.get("codec_name") or ""),
                    "resolution": f"{width}x{height}" if width and height else "",
                    "pixel_format": str(stream.get("pix_fmt") or ""),
                }
            )
        elif codec_type == "audio":
            details["audio"].append({"codec": str(stream.get("codec_name") or "")})
    video_summary = ",".join(
        f"{item.get('codec') or 'unknown'}:{item.get('resolution') or '?'}:{item.get('pixel_format') or '?'}"
        for item in details["video"]
    )
    audio_summary = ",".join(item.get("codec") or "unknown" for item in details["audio"])
    details["summary"] = (
        f"extension={details['extension'] or 'unknown'} "
        f"container={format_name or 'unknown'} "
        f"video={video_summary or 'none'} "
        f"audio={audio_summary or 'none'}"
    )
    return details


def evaluate_local_playback_health(
    *,
    elapsed_seconds,
    position_ms,
    last_position_ms,
    playback_state,
    media_status,
    expects_video,
    expects_audio,
    video_frame_seen,
    audio_seen,
    pending_seek=False,
):
    if pending_seek:
        return LOCAL_PLAYBACK_WAITING, "seek pending"
    if media_status in {"InvalidMedia", "StalledMedia"}:
        return LOCAL_PLAYBACK_STALLED, f"media status {media_status}"
    if playback_state != "PlayingState":
        return LOCAL_PLAYBACK_STOPPED, f"player state {playback_state}"
    if float(elapsed_seconds or 0) < LOCAL_PLAYBACK_GRACE_SECONDS:
        return LOCAL_PLAYBACK_WAITING, "startup grace"

    progressing = int(position_ms or 0) > int(last_position_ms or 0) + LOCAL_PLAYBACK_PROGRESS_GRACE_MS
    if expects_video and not video_frame_seen:
        if expects_audio and audio_seen:
            return LOCAL_PLAYBACK_NO_VIDEO_FRAME, "audio active but no rendered video frame"
        if progressing:
            return LOCAL_PLAYBACK_NO_VIDEO_FRAME, "timer advancing but no rendered video frame"
        return LOCAL_PLAYBACK_WAITING, "waiting for first video frame"
    if expects_audio and not audio_seen and not video_frame_seen and progressing:
        return LOCAL_PLAYBACK_NO_AUDIO_OR_VIDEO, "timer advancing but no confirmed audio or video"
    return LOCAL_PLAYBACK_HEALTHY, "playback signals confirmed"


def should_retry_local_playback(health_status, attempts):
    if int(attempts or 0) >= LOCAL_PLAYBACK_MAX_FALLBACK_ATTEMPTS:
        return False
    return health_status in {
        LOCAL_PLAYBACK_NO_VIDEO_FRAME,
        LOCAL_PLAYBACK_NO_AUDIO_OR_VIDEO,
        LOCAL_PLAYBACK_STALLED,
        LOCAL_PLAYBACK_STOPPED,
    }


def _extension(path):
    text = str(path or "")
    if "." not in text:
        return ""
    return "." + text.rsplit(".", 1)[-1].lower()

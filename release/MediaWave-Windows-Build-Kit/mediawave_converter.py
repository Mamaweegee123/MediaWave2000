import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal, QPointF, QRectF
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QCheckBox,
    QSizePolicy,
)


APP_NAME = "MediaWaveConverter"
WINDOW_TITLE = "MediaWave Converter"
PIPELINE_VERSION = "2026.04.11"
DISPLAY_VERSION = "1.0.0"
TARGET_LUFS = -16
TARGET_TP = -1.5
TARGET_LRA = 11

_SW_BG = QColor(13, 16, 38)
_SW_HERO_TOP = QColor(9, 11, 27)
_SW_HERO_BOT = QColor(15, 18, 44)
_SW_CARD_BG = QColor(22, 26, 58)
_SW_CARD_BORDER = QColor(68, 108, 235)
_SW_ACCENT = QColor(96, 144, 255)
_SW_CTA_BG = QColor(255, 188, 10)
_SW_CTA_TEXT = QColor(13, 16, 38)
_SW_TEXT = QColor(210, 222, 252)
_SW_TEXT_DIM = QColor(138, 158, 212)
_SW_HEADER = QColor(118, 162, 255)
_SW_INPUT_BG = QColor(16, 20, 50)
_SW_INPUT_TEXT = QColor(188, 205, 248)
_SW_FOOTER_BG = QColor(9, 11, 27)
_SW_FOOTER_BORD = QColor(42, 54, 128)
_SW_STAR_WARM = QColor(255, 218, 96)
_SW_STAR_COOL = QColor(148, 196, 255)
SUPPORTED_VIDEO_EXTENSIONS = {
    ".3gp",
    ".asf",
    ".avi",
    ".dv",
    ".f4v",
    ".flv",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".mxf",
    ".ogv",
    ".qt",
    ".rm",
    ".ts",
    ".vob",
    ".webm",
    ".wmv",
}
ASPECT_CHOICES = {
    "Classic TV": {
        "ratio": 4 / 3,
        "tag": "4x3",
        "sizes": [
            ("960 x 720", (960, 720)),
            ("1280 x 960", (1280, 960)),
        ],
        "friendly": "Old-school 4:3 shape",
    },
    "Widescreen": {
        "ratio": 16 / 9,
        "tag": "16x9",
        "sizes": [
            ("1280 x 720", (1280, 720)),
            ("1920 x 1080", (1920, 1080)),
        ],
        "friendly": "Modern 16:9 shape",
    },
}
QUALITY_PRESETS = {
    "Best Picture": {
        "crf": 18,
        "preset": "fast",
        "audio_bitrate": "320k",
        "tag": "hq",
        "description": "Keeps a rich, clean picture while still moving faster than before.",
        "vt_bitrate": "9M",
        "vt_maxrate": "13M",
    },
    "Smaller Files": {
        "crf": 21,
        "preset": "veryfast",
        "audio_bitrate": "256k",
        "tag": "balanced",
        "description": "Runs quicker and saves space while still looking solid.",
        "vt_bitrate": "6M",
        "vt_maxrate": "9M",
    },
}
FRAMING_CHOICES = {
    "Keep More Picture": "Preserves more of the image when shapes do not match.",
    "Fill Screen More": "Crops more aggressively to fill the target shape.",
}
LEGACY_ASPECT_LABELS = {
    "Classic 4:3": "Classic TV",
    "Fullscreen 16:9": "Widescreen",
}
LEGACY_QUALITY_LABELS = {
    "Near-lossless": "Best Picture",
    "Balanced": "Smaller Files",
}
SLIDER_LABELS = [
    (0.0, "Gentle"),
    (0.34, "Balanced"),
    (0.67, "Assertive"),
]
ENCODER_CHOICES = {
    "Automatic": "Pick the fastest safe option for this machine.",
    "Mac Speed Boost": "Use Apple's video engine when available for faster batches.",
    "Compatibility Mode": "Use classic software encoding for the most predictable results.",
}
OUTPUT_FORMATS = {
    "MP4 (Recommended)": {
        "extension": ".mp4",
        "video_codec": "h264",
        "audio_codec": "aac",
        "subtitle_codec": "mov_text",
        "description": "Best everyday compatibility and the default MediaWave format.",
    },
    "MKV (Flexible)": {
        "extension": ".mkv",
        "video_codec": "h264",
        "audio_codec": "aac",
        "subtitle_codec": "srt",
        "description": "Flexible container that handles copied text subtitles especially well.",
    },
    "AVI (Legacy)": {
        "extension": ".avi",
        "video_codec": "mpeg4",
        "audio_codec": "mp3",
        "subtitle_codec": None,
        "description": "Legacy format for older software and devices. Copied subtitles are not supported.",
    },
}
DEFAULT_OUTPUT_FORMAT = "MP4 (Recommended)"
AUDIO_PREFERENCES = ["Auto", "Prefer English", "Prefer Japanese"]
_ENGLISH_LANG_TAGS = {"eng", "en"}
_JAPANESE_LANG_TAGS = {"jpn", "ja", "jp"}
TEXT_SUBTITLE_CODECS = {"subrip", "ass", "ssa", "webvtt", "mov_text"}
AUDIO_LEVELING_FILTER = f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}"
AUDIO_LEVELING_STATUS = (
    f"Audio leveling: on. Target: {TARGET_LUFS} LUFS / {TARGET_TP} dB true peak. Filter: loudnorm."
)
AUDIO_LEVELING_UNAVAILABLE_MESSAGE = "Audio leveling requires FFmpeg loudnorm support."


def resource_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


RESOURCE_DIR = resource_base_dir()


def app_data_dir() -> Path:
    candidates: list[Path] = []
    if sys.platform == "darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / APP_NAME)
    elif os.name == "nt":
        candidates.append(Path(os.getenv("APPDATA", str(Path.home()))) / APP_NAME)
    else:
        candidates.append(Path.home() / ".local" / "share" / APP_NAME)

    candidates.append(RESOURCE_DIR / ".mediawave_converter")
    candidates.append(Path.cwd() / ".mediawave_converter")
    candidates.append(Path("/tmp") / APP_NAME)

    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / ".write_test"
            with probe.open("w", encoding="utf-8") as handle:
                handle.write("ok")
            probe.unlink(missing_ok=True)
            return base
        except OSError:
            continue

    raise RuntimeError("Could not create a writable app data directory.")


DATA_DIR = app_data_dir()
SETTINGS_FILE = DATA_DIR / "settings.json"

_CHECKBOX_CHECK_SVG = str(DATA_DIR / "checkbox_check.svg").replace("\\", "/")
if not os.path.exists(_CHECKBOX_CHECK_SVG):
    try:
        with open(_CHECKBOX_CHECK_SVG, "w", encoding="utf-8") as _f:
            _f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><polyline points="1.5,5 4,7.5 8.5,2.5" stroke="white" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    except OSError:
        _CHECKBOX_CHECK_SVG = ""

_CONV_ARROW_DIR = os.path.join(os.environ.get("TEMP", "/tmp"), "mw2k_arrows")
_ARROW_DOWN_SVG = ""
_ARROW_UP_SVG = ""
try:
    os.makedirs(_CONV_ARROW_DIR, exist_ok=True)
    _ARROW_DOWN_SVG = os.path.join(_CONV_ARROW_DIR, "arrow_down.svg").replace("\\", "/")
    _ARROW_UP_SVG   = os.path.join(_CONV_ARROW_DIR, "arrow_up.svg").replace("\\", "/")
    with open(_ARROW_DOWN_SVG, "w", encoding="utf-8") as _f:
        _f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 6"><polyline points="1,1 5,5 9,1" stroke="#a0aadc" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    with open(_ARROW_UP_SVG, "w", encoding="utf-8") as _f:
        _f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 6"><polyline points="1,5 5,1 9,5" stroke="#a0aadc" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')
except OSError:
    _ARROW_DOWN_SVG = ""
    _ARROW_UP_SVG = ""


def mediawave_converted_dir() -> Path | None:
    """Return the shared MediaWave Converted folder if one already exists, else None.

    Checked on every call so it reflects the current filesystem state.
    Portable (frozen + User Content/ next to exe): <exe_dir>/User Content/Converted
    Installed: ~/Documents/MediaWave/Converted
    """
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            exe_dir = Path(sys.executable).resolve().parent
            portable = exe_dir / "User Content" / "Converted"
            if portable.is_dir():
                return portable
    docs_converted = Path.home() / "Documents" / "MediaWave" / "Converted"
    if docs_converted.is_dir():
        return docs_converted
    return None
MANIFEST_FILE = DATA_DIR / "processed_manifest.json"
SESSION_FILE = DATA_DIR / "batch_session.json"


def resolve_resource_path(*candidates: str) -> Path | None:
    bases = [RESOURCE_DIR, Path(__file__).resolve().parent]
    for base in bases:
        for candidate in candidates:
            path = base / candidate
            if path.exists():
                return path
    return None


def resolve_executable(name: str) -> str | None:
    binary_name = f"{name}.exe" if os.name == "nt" else name
    packaged = RESOURCE_DIR / "bin" / binary_name
    if packaged.exists():
        return str(packaged)
    discovered = shutil.which(binary_name)
    if discovered:
        return discovered
    common_locations = [
        Path("/opt/homebrew/bin") / binary_name,
        Path("/usr/local/bin") / binary_name,
        Path("/usr/bin") / binary_name,
    ]
    for location in common_locations:
        if location.exists():
            return str(location)
    return None


def ffmpeg_supports_filter(ffmpeg_path: str | None, filter_name: str) -> bool:
    if not ffmpeg_path:
        return False
    try:
        completed = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=4,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    output = f"{completed.stdout}\n{completed.stderr}".lower()
    return bool(re.search(rf"\b{re.escape(filter_name.lower())}\b", output))


def ffmpeg_supports_subtitles_filter(ffmpeg_path: str | None) -> bool:
    return ffmpeg_supports_filter(ffmpeg_path, "subtitles")


def ffmpeg_supports_loudnorm_filter(ffmpeg_path: str | None) -> bool:
    return ffmpeg_supports_filter(ffmpeg_path, "loudnorm")


def available_encoders() -> set[str]:
    if not FFMPEG_PATH:
        return set()
    try:
        completed = subprocess.run(
            [FFMPEG_PATH, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
        )
    except OSError:
        return set()
    if completed.returncode != 0:
        return set()
    encoders: set[str] = set()
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("V"):
            encoders.add(parts[1])
    return encoders


FFMPEG_PATH = resolve_executable("ffmpeg")
FFPROBE_PATH = resolve_executable("ffprobe")
FFMPEG_HAS_SUBTITLES_FILTER = ffmpeg_supports_subtitles_filter(FFMPEG_PATH)
FFMPEG_HAS_LOUDNORM_FILTER = ffmpeg_supports_loudnorm_filter(FFMPEG_PATH)
SUBTITLE_BURN_LABEL = (
    "Burn English Subtitles (experimental)"
    if FFMPEG_HAS_SUBTITLES_FILTER
    else "Burn English Subtitles (unavailable with current FFmpeg)"
)
SUBTITLE_PREFERENCES = [
    "No Subtitles",
    "Copy English Subtitles",
    SUBTITLE_BURN_LABEL,
    "Copy First Subtitle Track",
]
LEGACY_SUBTITLE_PREFERENCES = {
    "Burn English Subtitles": SUBTITLE_BURN_LABEL,
    "Burn English Subtitles (experimental)": SUBTITLE_BURN_LABEL,
    "Burn English Subtitles (unavailable with current FFmpeg)": SUBTITLE_BURN_LABEL,
}
AVAILABLE_ENCODERS = available_encoders()
LOGO_PATH = resolve_resource_path(
    "logos/MediaWave2000.png",
    "logos/MediaWave-2000-2000-2000-MediaWave-2000.png",
)
CONVERTER_LOGO_PATH = resolve_resource_path("logos/MWConverter.png")
CONVERTER_ICON_PATH = resolve_resource_path("logos/MWConverter_appicon.png")
PRIMARY_FONT_PATH = resolve_resource_path("Fonts/ArchivoNarrow-Bold.ttf")
SECONDARY_FONT_PATH = resolve_resource_path("Fonts/ArchivoNarrow-SemiBold.ttf")


def load_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def clear_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def even_floor(value: int, minimum: int = 2) -> int:
    value = int(value)
    if value % 2:
        value -= 1
    return max(minimum, value)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def percentile_value(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    percentile = clamp(percentile, 0.0, 1.0)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def format_duration(seconds: float | None) -> str:
    if not seconds or seconds <= 0:
        return "--:--"
    whole = int(round(seconds))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_time_remaining(seconds: float) -> str:
    whole = max(1, int(round(seconds)))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} hr {minutes} min" if minutes else f"{hours} hr"
    if minutes:
        return f"{minutes} min {secs} sec" if minutes < 5 and secs else f"{minutes} min"
    return f"{secs} sec"


def format_finish_clock(timestamp: float) -> str:
    return time.strftime("%I:%M %p", time.localtime(timestamp)).lstrip("0")


def human_size(byte_count: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(byte_count)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{byte_count} B"


def seconds_from_progress(raw_value: str) -> float | None:
    if not raw_value:
        return None
    if raw_value.isdigit():
        return int(raw_value) / 1_000_000.0
    if ":" in raw_value:
        hours, minutes, seconds = raw_value.split(":")
        return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)
    return None


def is_child_of(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def make_settings_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()


def slider_text(value: int) -> str:
    normalized = value / 100.0
    label = SLIDER_LABELS[-1][1]
    for threshold, name in SLIDER_LABELS:
        if normalized >= threshold:
            label = name
    return f"{label} crop ({value}%)"


def video_candidates(source_root: Path, output_root: Path, recursive: bool) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    discovered: list[Path] = []
    for candidate in sorted(source_root.glob(pattern)):
        if not candidate.is_file():
            continue
        if candidate.name.startswith("."):
            continue
        if candidate.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
            continue
        if is_child_of(candidate, output_root):
            continue
        if "__mediawave_" in candidate.stem.lower():
            continue
        discovered.append(candidate)
    return discovered


@dataclass
class RenameFileInfo:
    path: Path
    guessed_title: str
    season: int | None
    episode: int | None
    existing_episode_title: str
    guessed_year: str = ""
    proposed_name: str = ""
    status: str = "Needs a show match"


def clean_filename_words(value: str) -> str:
    value = re.sub(r"[\._]+", " ", value)
    value = re.sub(r"\[[^\]]*\]|\([^)]*(?:1080|720|2160|x26[45]|hevc|bluray|web)[^)]*\)", " ", value, flags=re.I)
    value = re.sub(r"\b(?:1080p?|720p?|2160p?|x26[45]|h\.?26[45]|hevc|aac|bluray|web[- ]?dl|webrip)\b.*$", "", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip(" -")


def parse_rename_file(path: Path) -> RenameFileInfo:
    stem = path.stem
    patterns = [
        re.compile(r"^(?P<title>.*?)[ ._-]+S(?P<season>\d{1,2})E(?P<episode>\d{1,3})(?:[ ._-]+(?P<name>.*))?$", re.I),
        re.compile(r"^(?P<title>.*?)[ ._-]+(?P<season>\d{1,2})x(?P<episode>\d{1,3})(?:[ ._-]+(?P<name>.*))?$", re.I),
    ]
    for pattern in patterns:
        match = pattern.match(stem)
        if match:
            return RenameFileInfo(
                path=path,
                guessed_title=clean_filename_words(match.group("title")),
                season=int(match.group("season")),
                episode=int(match.group("episode")),
                existing_episode_title=clean_filename_words(match.group("name") or ""),
            )
    absolute = re.match(r"^(?P<title>.*?)[ ._-]+(?:EP?|Episode)[ ._-]*(?P<episode>\d{1,4})(?:[ ._-]+(?P<name>.*))?$", stem, re.I)
    if absolute:
        return RenameFileInfo(
            path=path,
            guessed_title=clean_filename_words(absolute.group("title")),
            season=None,
            episode=int(absolute.group("episode")),
            existing_episode_title=clean_filename_words(absolute.group("name") or ""),
        )
    anime_release = re.match(
        r"^(?P<title>.*?)[ ._-]+(?P<episode>\d{1,4})(?:v\d+)?(?:[ ._-]+(?P<name>.*))?$",
        stem,
        re.I,
    )
    if anime_release:
        return RenameFileInfo(
            path=path,
            guessed_title=clean_filename_words(anime_release.group("title")),
            season=None,
            episode=int(anime_release.group("episode")),
            existing_episode_title=clean_filename_words(anime_release.group("name") or ""),
        )
    return RenameFileInfo(path, clean_filename_words(stem), None, None, "")


def parse_movie_file(path: Path) -> RenameFileInfo:
    stem = path.stem
    year_match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", stem)
    year = year_match.group(1) if year_match else ""
    title_part = stem[:year_match.start()] if year_match else stem
    title = clean_filename_words(title_part)
    if not title:
        title = clean_filename_words(stem)
    return RenameFileInfo(path, title, None, None, "", guessed_year=year, status="Needs a movie match")


def safe_filename_part(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]', "-", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value or "Untitled"


def metadata_match_confidence(query: str, title: str, query_year: str = "", result_year: str = "") -> int:
    clean_query = clean_filename_words(query).casefold()
    clean_title = clean_filename_words(title).casefold()
    if not clean_query or not clean_title:
        return 0
    if clean_query == clean_title:
        score = 97
    elif clean_query in clean_title or clean_title in clean_query:
        score = 90
    else:
        score = int(round(clamp(SequenceMatcher(None, clean_query, clean_title).ratio() * 100, 1, 87)))
    if query_year and result_year:
        score += 2 if query_year == result_year else -30
    return int(clamp(score, 1, 99))


class MetadataSearchWorker(QThread):
    results_ready = Signal(list)
    failed = Signal(str)

    def __init__(self, provider: str, query: str, media_type: str = "Shows"):
        super().__init__()
        self.provider = provider
        self.query = query
        self.media_type = media_type
        year_match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", query)
        self.query_year = year_match.group(1) if year_match else ""
        self.search_title = clean_filename_words(
            f"{query[:year_match.start()]} {query[year_match.end():]}" if year_match else query
        )

    def request_json(self, request: urllib.request.Request) -> Any:
        request.add_header("User-Agent", "MediaWaveConverter/2026.04.11")
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))

    def search_tvmaze(self) -> list[dict[str, Any]]:
        url = "https://api.tvmaze.com/search/shows?" + urllib.parse.urlencode({"q": self.search_title})
        payload = self.request_json(urllib.request.Request(url))
        results = []
        for entry in payload[:12]:
            show = entry.get("show") or {}
            premiered = str(show.get("premiered") or "")[:4]
            results.append(
                {
                    "provider": "TVmaze",
                    "id": show.get("id"),
                    "title": show.get("name") or "Untitled",
                    "year": premiered,
                    "detail": " • ".join(filter(None, [premiered, show.get("language"), show.get("type")])),
                    "confidence": metadata_match_confidence(
                        self.search_title, show.get("name") or "", self.query_year, premiered
                    ),
                    "media_type": "show",
                }
            )
        return results

    def search_cinemeta(self) -> list[dict[str, Any]]:
        query = urllib.parse.quote(self.search_title, safe="")
        url = f"https://v3-cinemeta.strem.io/catalog/movie/top/search={query}.json"
        payload = self.request_json(urllib.request.Request(url))
        results = []
        for movie in payload.get("metas", [])[:12]:
            title = movie.get("name") or "Untitled"
            year = str(movie.get("releaseInfo") or "")[:4]
            results.append(
                {
                    "provider": "Cinemeta",
                    "id": movie.get("imdb_id") or movie.get("id"),
                    "title": title,
                    "year": year,
                    "detail": " • ".join(filter(None, [year, "Movie", movie.get("imdb_id") or movie.get("id")])),
                    "confidence": metadata_match_confidence(self.search_title, title, self.query_year, year),
                    "media_type": "movie",
                }
            )
        return results

    def search_anilist(self) -> list[dict[str, Any]]:
        format_filter = ", format: MOVIE" if self.media_type == "Movies" else ""
        query = f"""
        query ($search: String) {{
          Page(page: 1, perPage: 12) {{
            media(search: $search, type: ANIME, sort: SEARCH_MATCH{format_filter}) {{
              id episodes seasonYear format
              title {{ english romaji native }}
            }}
          }}
        }}
        """
        body = json.dumps({"query": query, "variables": {"search": self.search_title}}).encode("utf-8")
        request = urllib.request.Request(
            "https://graphql.anilist.co",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        payload = self.request_json(request)
        results = []
        for media in payload.get("data", {}).get("Page", {}).get("media", []):
            titles = media.get("title") or {}
            title = titles.get("english") or titles.get("romaji") or titles.get("native") or "Untitled"
            results.append(
                {
                    "provider": "AniList",
                    "id": media.get("id"),
                    "title": title,
                    "year": str(media.get("seasonYear") or ""),
                    "detail": " • ".join(
                        filter(None, [str(media.get("seasonYear") or ""), media.get("format"), f"{media.get('episodes')} episodes" if media.get("episodes") else ""])
                    ),
                    "confidence": metadata_match_confidence(
                        self.search_title, title, self.query_year, str(media.get("seasonYear") or "")
                    ),
                    "media_type": "movie" if self.media_type == "Movies" else "show",
                }
            )
        return results

    def run(self) -> None:
        results: list[dict[str, Any]] = []
        errors: list[str] = []
        if self.media_type == "Shows" and self.provider in {"All databases", "TVmaze"}:
            try:
                results.extend(self.search_tvmaze())
            except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                errors.append(f"TVmaze: {exc}")
        if self.media_type == "Movies" and self.provider in {"All databases", "Cinemeta"}:
            try:
                results.extend(self.search_cinemeta())
            except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                errors.append(f"Cinemeta: {exc}")
        if self.provider in {"All databases", "AniList"}:
            try:
                results.extend(self.search_anilist())
            except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                errors.append(f"AniList: {exc}")
        if results:
            results.sort(key=lambda item: int(item.get("confidence", 0)), reverse=True)
            self.results_ready.emit(results)
        elif errors:
            self.failed.emit("Metadata search could not finish. " + " | ".join(errors))
        else:
            self.results_ready.emit([])


class TVmazeEpisodeWorker(QThread):
    episodes_ready = Signal(dict, str)
    failed = Signal(str)

    def __init__(self, show_id: int):
        super().__init__()
        self.show_id = show_id

    def run(self) -> None:
        try:
            request = urllib.request.Request(
                f"https://api.tvmaze.com/shows/{self.show_id}/episodes?specials=1",
                headers={"User-Agent": "MediaWaveConverter/2026.04.11"},
            )
            with urllib.request.urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
            episodes = {
                f"{int(item.get('season') or 0)}:{int(item.get('number') or 0)}": str(item.get("name") or "")
                for item in payload
                if item.get("season") is not None and item.get("number") is not None
            }
            self.episodes_ready.emit(episodes, "TVmaze")
        except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            self.failed.emit(f"TVmaze episode lookup could not finish: {exc}")


def scan_length_for(duration: float) -> float:
    if duration <= 0:
        return 10.0
    return clamp(duration * 0.055, 8.0, 18.0)


def crop_limit_for(aggressiveness: int) -> float:
    return round(0.03 + ((aggressiveness / 100.0) * 0.18), 3)


def crop_percentile_for(aggressiveness: int) -> float:
    return clamp(0.2 + ((aggressiveness / 100.0) * 0.6), 0.2, 0.8)


def load_brand_fonts() -> tuple[str | None, str | None]:
    primary_family = None
    secondary_family = None
    if PRIMARY_FONT_PATH and PRIMARY_FONT_PATH.exists():
        font_id = QFontDatabase.addApplicationFont(str(PRIMARY_FONT_PATH))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            primary_family = families[0]
    if SECONDARY_FONT_PATH and SECONDARY_FONT_PATH.exists():
        font_id = QFontDatabase.addApplicationFont(str(SECONDARY_FONT_PATH))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            secondary_family = families[0]
    return primary_family, secondary_family


def _make_startup_stars(n: int = 46) -> list[tuple[float, float, float]]:
    stars: list[tuple[float, float, float]] = []
    seed = 0xA5F3C1
    for _ in range(n):
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        x = (seed & 0xFFFF) / 0xFFFF
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        y = (seed & 0xFFFF) / 0xFFFF
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        v = (seed & 0xFFFF) / 0xFFFF
        stars.append((x, y, v))
    return stars


_STARTUP_STARS = _make_startup_stars()


def default_encoder_mode() -> str:
    if sys.platform == "darwin" and "h264_videotoolbox" in AVAILABLE_ENCODERS:
        return "Automatic"
    return "Compatibility Mode"


def resolve_video_encoder(mode: str) -> str:
    if mode == "Mac Speed Boost" and "h264_videotoolbox" in AVAILABLE_ENCODERS:
        return "h264_videotoolbox"
    if mode == "Compatibility Mode":
        return "libx264"
    if sys.platform == "darwin" and "h264_videotoolbox" in AVAILABLE_ENCODERS:
        return "h264_videotoolbox"
    return "libx264"


def encoder_summary(mode: str) -> str:
    active_encoder = resolve_video_encoder(mode)
    if active_encoder == "h264_videotoolbox":
        return "Fast Mac hardware encoding is on."
    return "Compatibility-first encoding is on."


def _common_parent(paths: list) -> Path:
    """Return the deepest common ancestor directory for a list of Paths."""
    if not paths:
        return Path.home()
    resolved = [Path(p).resolve() for p in paths]
    if len(resolved) == 1:
        p = resolved[0]
        return p.parent if p.is_file() else p
    try:
        common = Path(os.path.commonpath([str(p) for p in resolved]))
        return common if common.is_dir() else common.parent
    except ValueError:
        p = resolved[0]
        return p.parent if p.is_file() else p


class DropZone(QFrame):
    sources_dropped = Signal(list)  # list[str] of local paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(88)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel("Drop video files or folders here")
        self._label.setObjectName("dropZoneLabel")
        self._label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label)

    @staticmethod
    def _acceptable(path_str: str) -> bool:
        p = Path(path_str)
        return p.is_dir() or (p.is_file() and p.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            if any(self._acceptable(u.toLocalFile()) for u in event.mimeData().urls()):
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        event.accept()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        acceptable = [p for p in paths if self._acceptable(p)]
        if acceptable:
            self.sources_dropped.emit(acceptable)
            event.acceptProposedAction()
        else:
            event.ignore()


class StarfieldHeader(QWidget):
    _STARS = [
        (0.04, 0.18, 1.4), (0.09, 0.62, 1.0), (0.14, 0.35, 1.8),
        (0.19, 0.80, 1.2), (0.23, 0.15, 2.2), (0.28, 0.52, 1.0),
        (0.33, 0.72, 1.5), (0.37, 0.28, 1.1), (0.42, 0.88, 1.8),
        (0.47, 0.45, 1.3), (0.51, 0.12, 2.0), (0.55, 0.65, 1.0),
        (0.59, 0.38, 1.6), (0.63, 0.82, 1.2), (0.68, 0.22, 1.9),
        (0.72, 0.58, 1.1), (0.76, 0.42, 2.1), (0.80, 0.75, 1.0),
        (0.84, 0.30, 1.4), (0.88, 0.55, 1.7), (0.92, 0.18, 1.2),
        (0.96, 0.70, 1.5), (0.07, 0.90, 1.0), (0.16, 0.05, 1.3),
        (0.31, 0.95, 1.1), (0.44, 0.08, 1.8), (0.57, 0.92, 1.0),
        (0.70, 0.05, 1.6), (0.83, 0.88, 1.2), (0.95, 0.40, 1.4),
        (0.11, 0.48, 1.0), (0.26, 0.68, 1.3), (0.40, 0.22, 1.5),
        (0.53, 0.78, 1.0), (0.66, 0.12, 1.7), (0.78, 0.60, 1.1),
        (0.90, 0.85, 1.4), (0.02, 0.55, 1.2), (0.50, 0.30, 1.9),
        (0.75, 0.92, 1.0),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("starfieldHeader")
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QLinearGradient, QColor, QRadialGradient
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor("#0d1f3a"))
        grad.setColorAt(1.0, QColor("#0c1829"))
        painter.fillRect(0, 0, w, h, grad)
        for x_frac, y_frac, r in self._STARS:
            cx = int(x_frac * w)
            cy = int(y_frac * h)
            alpha = 160 if r > 1.5 else 100
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 200, alpha))
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
        painter.end()


class CoaxieWidget(QWidget):
    def __init__(self, size: int = 96, parent=None):
        super().__init__(parent)
        sz = max(50, int(size))
        self.setFixedSize(sz, int(sz * 1.38))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._blink = False
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._start_blink)
        self._blink_timer.start(3800)

    def _start_blink(self) -> None:
        self._blink = True
        self.update()
        QTimer.singleShot(115, self._end_blink)

    def _end_blink(self) -> None:
        self._blink = False
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        scale = w / 96.0

        def s(value: float) -> float:
            return value * scale

        dy = s(9)

        def y(value: float) -> float:
            return s(value) + dy

        def outline(width: float = 2.5) -> QPen:
            return QPen(QColor(14, 16, 40), max(1, s(width)))

        ant_pen = QPen(QColor(28, 20, 60), max(1, s(3)))
        ant_pen.setCapStyle(Qt.RoundCap)
        p.setPen(ant_pen)
        p.drawLine(QPointF(s(33), y(17)), QPointF(s(26), y(2)))
        p.drawLine(QPointF(s(63), y(17)), QPointF(s(75), y(1)))

        p.setPen(outline(1.5))
        p.setBrush(QColor(255, 212, 32))
        p.drawEllipse(QPointF(s(23), y(1)), s(5), s(5))
        p.setBrush(QColor(255, 180, 20))
        p.drawEllipse(QPointF(s(77), y(0)), s(4.5), s(5.5))

        body = QRectF(s(2), y(13), s(92), s(82))
        body_grad = QLinearGradient(body.topLeft(), body.bottomLeft())
        body_grad.setColorAt(0.0, QColor(72, 92, 195))
        body_grad.setColorAt(0.45, QColor(52, 68, 162))
        body_grad.setColorAt(1.0, QColor(28, 36, 110))
        p.setBrush(body_grad)
        p.setPen(outline(2.8))
        p.drawRoundedRect(body, s(7), s(7))

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 22))
        p.drawRoundedRect(
            QRectF(body.x() + s(38), body.y() + s(4), s(48), body.height() * 0.45),
            s(5),
            s(5),
        )

        screen = QRectF(s(10), y(21), s(68), s(54))
        p.setPen(outline(2))
        p.setBrush(QColor(6, 8, 28))
        p.drawRoundedRect(screen, s(4), s(4))

        cx, cy = screen.center().x(), screen.center().y()
        glow = QRadialGradient(cx - s(4), cy - s(3), s(28))
        glow.setColorAt(0.0, QColor(60, 108, 240, 45))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(screen.adjusted(s(3), s(3), -s(3), -s(3)))

        brow_pen = QPen(QColor(28, 20, 60), max(1, s(3)))
        brow_pen.setCapStyle(Qt.RoundCap)
        p.setPen(brow_pen)
        eye_y = cy - s(5)
        p.drawLine(QPointF(cx - s(19), eye_y - s(10)), QPointF(cx - s(5), eye_y - s(13)))
        p.drawLine(QPointF(cx + s(4), eye_y - s(12)), QPointF(cx + s(18), eye_y - s(10)))

        if self._blink:
            blink_pen = QPen(QColor(14, 16, 40), max(1, s(3)))
            blink_pen.setCapStyle(Qt.RoundCap)
            p.setPen(blink_pen)
            p.setBrush(Qt.NoBrush)
            p.drawLine(QPointF(cx - s(18), eye_y), QPointF(cx - s(6), eye_y))
            p.drawLine(QPointF(cx + s(5), eye_y), QPointF(cx + s(17), eye_y))
        else:
            p.setPen(outline(2))
            p.setBrush(QColor(230, 240, 255))
            p.drawEllipse(QPointF(cx - s(12), eye_y), s(7.5), s(8.5))
            p.drawEllipse(QPointF(cx + s(11), eye_y), s(6.5), s(7.5))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(40, 170, 255))
            p.drawEllipse(QPointF(cx - s(12), eye_y + s(1)), s(5), s(5.5))
            p.drawEllipse(QPointF(cx + s(11), eye_y + s(0.5)), s(4.2), s(4.8))
            p.setBrush(QColor(14, 16, 40))
            p.drawEllipse(QPointF(cx - s(11.5), eye_y + s(1)), s(2.8), s(3))
            p.drawEllipse(QPointF(cx + s(11.5), eye_y + s(0.5)), s(2.2), s(2.5))
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(QPointF(cx - s(13.5), eye_y - s(1.5)), s(1.5), s(1.5))
            p.drawEllipse(QPointF(cx + s(9.8), eye_y - s(1.2)), s(1.2), s(1.2))

        p.setPen(outline(1.2))
        p.setBrush(QColor(40, 56, 140))
        p.drawEllipse(QPointF(cx - s(1), eye_y + s(7)), s(1.8), s(1.8))

        smile_pen = QPen(QColor(96, 200, 255), max(2, s(2.6)))
        smile_pen.setCapStyle(Qt.RoundCap)
        p.setPen(smile_pen)
        p.setBrush(Qt.NoBrush)
        smile_rect = QRectF(cx - s(11), eye_y + s(7), s(22), s(14))
        p.drawArc(smile_rect, 0, -180 * 16)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(240, 100, 140, 70))
        p.drawEllipse(QPointF(cx - s(22), eye_y + s(4)), s(6), s(4))
        p.drawEllipse(QPointF(cx + s(21), eye_y + s(4)), s(6), s(4))

        grill_pen = QPen(QColor(38, 50, 130), max(1, s(1.2)))
        p.setPen(grill_pen)
        gx = screen.right() + s(5)
        for grill_index in range(4):
            gy = screen.top() + s(10) + grill_index * s(8)
            p.drawLine(QPointF(gx, gy), QPointF(gx + s(8), gy))

        knob_y = body.bottom() - s(12)
        p.setPen(outline(1.8))
        p.setBrush(QColor(212, 168, 48))
        p.drawEllipse(QPointF(s(26), knob_y), s(5.5), s(5.5))
        p.drawRoundedRect(QRectF(s(58), knob_y - s(5.5), s(11), s(11)), s(2.5), s(2.5))
        p.setPen(QPen(QColor(140, 100, 20), max(1, s(1.2))))
        p.drawLine(QPointF(s(26), knob_y - s(3.5)), QPointF(s(26), knob_y - s(1)))
        p.end()


@dataclass
class ConversionOptions:
    source_root: Path
    output_root: Path
    aspect_label: str
    target_width: int
    target_height: int
    framing_mode: str
    crop_aggressiveness: int
    quality_label: str
    encoder_mode: str
    output_format: str
    recursive: bool
    skip_completed: bool
    audio_preference: str = "Auto"
    audio_leveling_enabled: bool = False
    subtitle_preference: str = "No Subtitles"
    explicit_files: "list[Path] | None" = None

    @property
    def aspect_ratio(self) -> float:
        return ASPECT_CHOICES[self.aspect_label]["ratio"]

    @property
    def aspect_tag(self) -> str:
        return ASPECT_CHOICES[self.aspect_label]["tag"]

    @property
    def quality_profile(self) -> dict[str, Any]:
        return QUALITY_PRESETS[self.quality_label]

    @property
    def output_profile(self) -> dict[str, Any]:
        return OUTPUT_FORMATS.get(self.output_format, OUTPUT_FORMATS[DEFAULT_OUTPUT_FORMAT])

    def settings_payload(self) -> dict[str, Any]:
        return {
            "pipeline_version": PIPELINE_VERSION,
            "aspect_label": self.aspect_label,
            "target_width": self.target_width,
            "target_height": self.target_height,
            "framing_mode": self.framing_mode,
            "crop_aggressiveness": self.crop_aggressiveness,
            "quality_label": self.quality_label,
            "output_format": self.output_format,
            "recursive": self.recursive,
            "audio_preference": self.audio_preference,
            "audio_leveling_enabled": self.audio_leveling_enabled,
            "subtitle_preference": self.subtitle_preference,
            "audio_target_lufs": TARGET_LUFS,
            "audio_target_tp": TARGET_TP,
            "audio_target_lra": TARGET_LRA,
        }


@dataclass
class AudioStreamInfo:
    ffmpeg_index: int
    audio_index: int
    codec: str
    language: str
    title: str
    channels: int


@dataclass
class SubtitleStreamInfo:
    ffmpeg_index: int
    subtitle_index: int
    codec: str
    language: str
    title: str


@dataclass
class ProbeInfo:
    duration: float
    width: int
    height: int
    has_audio: bool
    video_codec: str
    audio_codec: str
    audio_streams: list  # list[AudioStreamInfo]
    subtitle_streams: list  # list[SubtitleStreamInfo]


def select_audio_stream(
    streams: list,  # list[AudioStreamInfo]
    preference: str,
) -> "AudioStreamInfo | None":
    if not streams:
        return None
    if preference == "Prefer English":
        for s in streams:
            if s.language in _ENGLISH_LANG_TAGS:
                return s
    elif preference == "Prefer Japanese":
        for s in streams:
            if s.language in _JAPANESE_LANG_TAGS:
                return s
    return streams[0]


def is_text_subtitle(codec: str) -> bool:
    return codec.lower().strip() in TEXT_SUBTITLE_CODECS


def select_subtitle_stream(
    streams: list,  # list[SubtitleStreamInfo]
    preference: str,
) -> "SubtitleStreamInfo | None":
    if not streams or preference == "No Subtitles":
        return None
    if preference == "Copy First Subtitle Track":
        return streams[0]
    if preference in {"Copy English Subtitles", SUBTITLE_BURN_LABEL}:
        for stream in streams:
            if stream.language in _ENGLISH_LANG_TAGS:
                return stream
        return None
    return None


def subtitle_mode(preference: str) -> str:
    if preference == SUBTITLE_BURN_LABEL:
        return "burn"
    if preference in {"Copy English Subtitles", "Copy First Subtitle Track"}:
        return "copy"
    return "none"


def escape_subtitle_filter_path(source_path: Path) -> str:
    value = str(source_path)
    value = value.replace("\\", "\\\\")
    value = value.replace(":", "\\:")
    value = value.replace("'", "\\'")
    value = value.replace("[", "\\[")
    value = value.replace("]", "\\]")
    value = value.replace(",", "\\,")
    return value


class BatchWorker(QThread):
    queue_initialized = Signal(list)
    row_update = Signal(str, str, str, str)
    overall_progress = Signal(int)
    file_progress = Signal(int)
    phase_changed = Signal(str)
    counters_changed = Signal(int, int, int, int)
    log_message = Signal(str)
    ffmpeg_missing = Signal(str)
    finished_summary = Signal(dict)

    def __init__(self, options: ConversionOptions):
        super().__init__()
        self.options = options
        self._cancel_requested = False
        self._pause_requested = False
        self._active_process: subprocess.Popen[str] | None = None

    def request_cancel(self) -> None:
        self._cancel_requested = True
        if self._active_process and self._active_process.poll() is None:
            try:
                self._active_process.terminate()
            except OSError:
                pass

    def force_kill_active_process(self) -> None:
        if self._active_process and self._active_process.poll() is None:
            try:
                self._active_process.kill()
            except OSError:
                pass

    def request_pause(self) -> None:
        self._pause_requested = True

    def run(self) -> None:
        if not FFMPEG_PATH or not FFPROBE_PATH:
            self.ffmpeg_missing.emit(
                "FFmpeg or FFprobe could not be found. Install FFmpeg, or bundle the binaries with this app."
            )
            return

        source_root = self.options.source_root
        output_root = self.options.output_root
        manifest = load_json(MANIFEST_FILE, {"version": 1, "entries": {}})
        entries = manifest.setdefault("entries", {})
        settings_hash = make_settings_hash(self.options.settings_payload())
        if self.options.explicit_files is not None:
            candidates = list(self.options.explicit_files)
        else:
            candidates = video_candidates(source_root, output_root, self.options.recursive)
        self.queue_initialized.emit([str(path) for path in candidates])

        total = len(candidates)
        processed = 0
        skipped = 0
        failed = 0
        self.counters_changed.emit(total, processed, skipped, failed)

        if not candidates:
            self.phase_changed.emit("I couldn't find any video files in that folder.")
            self.finished_summary.emit(
                {"total": 0, "processed": 0, "skipped": 0, "failed": 0, "canceled": False}
            )
            return

        for index, source_path in enumerate(candidates, start=1):
            if self._cancel_requested:
                break
            if self._pause_requested:
                break

            output_path = self.output_path_for(source_path)
            row_key = str(source_path)
            signature = self.source_signature(source_path)
            manifest_key = self.manifest_key(source_path, settings_hash)
            prior = entries.get(manifest_key)
            prior_output = str(prior.get("output_path", "")).strip() if prior else ""

            if (
                self.options.skip_completed
                and prior
                and prior.get("source_signature") == signature
                and prior_output
                and Path(prior_output).exists()
            ):
                skipped += 1
                self.row_update.emit(
                    row_key,
                    "Skipped",
                    "Already finished with these settings.",
                    prior_output,
                )
                self.log_message.emit(f"Skipped {source_path.name}: already converted.")
                self.overall_progress.emit(int((index / total) * 100))
                self.counters_changed.emit(total, processed, skipped, failed)
                continue

            try:
                self.phase_changed.emit(
                    f"Checking {source_path.name} — reading video details and looking for black bars ({index}/{total})"
                )
                self.row_update.emit(row_key, "Checking", "Taking a quick look at the file.", str(output_path))
                probe = self.probe_media(source_path)
                crop = self.detect_crop(source_path, probe)
                crop = self.apply_target_aspect(crop, probe.width, probe.height)
                self.row_update.emit(
                    row_key,
                    "Working",
                    f"Making the new {self.options.output_profile['extension'].upper().lstrip('.')} file.",
                    str(output_path),
                )
                chosen_audio = select_audio_stream(probe.audio_streams, self.options.audio_preference)
                if chosen_audio is not None:
                    track_desc = f"track {chosen_audio.audio_index} (lang={chosen_audio.language}, codec={chosen_audio.codec}"
                    if chosen_audio.title:
                        track_desc += f", title={chosen_audio.title!r}"
                    track_desc += ")"
                    self.log_message.emit(f"Audio for {source_path.name}: selected {track_desc}.")
                    if self.options.audio_leveling_enabled and FFMPEG_HAS_LOUDNORM_FILTER:
                        self.log_message.emit(AUDIO_LEVELING_STATUS)
                    elif self.options.audio_leveling_enabled:
                        self.log_message.emit(AUDIO_LEVELING_UNAVAILABLE_MESSAGE)
                    else:
                        self.log_message.emit("Audio leveling: off.")
                elif probe.has_audio:
                    self.log_message.emit(f"Audio for {source_path.name}: no audio streams found, encoding without audio.")
                    if self.options.audio_leveling_enabled:
                        self.log_message.emit("Audio leveling: skipped; no usable audio track was selected.")
                elif self.options.audio_leveling_enabled:
                    self.log_message.emit("Audio leveling: skipped; this file has no audio track.")
                chosen_subtitle = select_subtitle_stream(probe.subtitle_streams, self.options.subtitle_preference)
                subtitle_msg = ""
                if (
                    subtitle_mode(self.options.subtitle_preference) == "copy"
                    and chosen_subtitle is not None
                    and not self.options.output_profile["subtitle_codec"]
                ):
                    subtitle_msg = (
                        f"Subtitles for {source_path.name}: skipped; "
                        f"{self.options.output_format} does not support copied subtitles."
                    )
                    chosen_subtitle = None
                if not subtitle_msg:
                    subtitle_msg = self.describe_subtitle_selection(
                        source_path.name,
                        probe.subtitle_streams,
                        chosen_subtitle,
                        self.options.subtitle_preference,
                    )
                self.log_message.emit(subtitle_msg)
                activities = ["fitting the picture", "encoding the video"]
                if chosen_audio is not None:
                    activities.append(
                        "leveling the audio" if self.options.audio_leveling_enabled else "preparing the audio"
                    )
                if chosen_subtitle is not None:
                    action = "adding subtitles" if subtitle_mode(self.options.subtitle_preference) == "burn" else "carrying subtitles over"
                    activities.append(action)
                activity_text = ", ".join(activities[:-1]) + f", and {activities[-1]}"
                self.phase_changed.emit(
                    f"Converting {source_path.name} — {activity_text} ({index}/{total})"
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                self.transcode(source_path, output_path, probe, crop, chosen_audio, chosen_subtitle)
                self.file_progress.emit(100)
                processed += 1
                self.row_update.emit(
                    row_key,
                    "Done",
                    f"Trimmed and saved at {self.options.target_width}x{self.options.target_height}.",
                    str(output_path),
                )
                entries[manifest_key] = {
                    "completed_at": int(time.time()),
                    "output_path": str(output_path),
                    "quality": self.options.quality_label,
                    "settings_hash": settings_hash,
                    "source_path": str(source_path),
                    "source_signature": signature,
                }
                save_json(MANIFEST_FILE, manifest)
                self.log_message.emit(
                    f"Finished {source_path.name} -> {output_path.name} ({format_duration(probe.duration)})."
                )
            except RuntimeError as exc:
                if self._cancel_requested:
                    self.row_update.emit(row_key, "Stopped", "Stopped before it finished.", str(output_path))
                    self.log_message.emit(f"Canceled {source_path.name}.")
                    break
                failed += 1
                self.row_update.emit(row_key, "Problem", str(exc), str(output_path))
                self.log_message.emit(f"Failed {source_path.name}: {exc}")
            finally:
                self.overall_progress.emit(int((index / total) * 100))
                self.counters_changed.emit(total, processed, skipped, failed)
                self.file_progress.emit(0)

        canceled = self._cancel_requested
        paused = self._pause_requested and not canceled
        if canceled:
            self.phase_changed.emit("Batch stopped.")
        elif paused:
            self.phase_changed.emit("Paused. Ready to resume.")
        else:
            self.phase_changed.emit("Everything in this batch is done.")
        self.finished_summary.emit(
            {
                "total": total,
                "processed": processed,
                "skipped": skipped,
                "failed": failed,
                "canceled": canceled,
                "paused": paused,
            }
        )

    def manifest_key(self, source_path: Path, settings_hash: str) -> str:
        return f"{source_path.resolve()}::{settings_hash}"

    def source_signature(self, source_path: Path) -> str:
        stats = source_path.stat()
        return f"{stats.st_size}:{stats.st_mtime_ns}"

    def output_path_for(self, source_path: Path) -> Path:
        extension = str(self.options.output_profile["extension"])
        try:
            relative_path = source_path.relative_to(self.options.source_root)
        except ValueError:
            return self.options.output_root / f"{source_path.stem}{extension}"
        filename = f"{relative_path.stem}{extension}"
        return self.options.output_root / relative_path.parent / filename

    def probe_media(self, source_path: Path) -> ProbeInfo:
        command = [
            FFPROBE_PATH,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(source_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "FFprobe could not read this file.")
        probe_warning = completed.stderr.strip()
        if probe_warning and any(
            hint in probe_warning.lower()
            for hint in ("ended prematurely", "corrupt", "invalid data", "truncated")
        ):
            self.log_message.emit(
                f"{source_path.name}: the source appears incomplete or damaged. "
                "MediaWave will try to recover it, but conversion may need compatibility mode."
            )

        payload = json.loads(completed.stdout or "{}")
        streams = payload.get("streams", [])
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        if not video_stream:
            raise RuntimeError("This file does not contain a video stream.")

        raw_audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        raw_subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
        audio_stream_infos: list[AudioStreamInfo] = []
        for audio_idx, s in enumerate(raw_audio_streams):
            tags = s.get("tags", {}) or {}
            audio_stream_infos.append(AudioStreamInfo(
                ffmpeg_index=int(s.get("index", 0)),
                audio_index=audio_idx,
                codec=str(s.get("codec_name") or "unknown"),
                language=str(tags.get("language") or "und").lower().strip(),
                title=str(tags.get("title") or ""),
                channels=int(s.get("channels") or 0),
            ))
        subtitle_stream_infos: list[SubtitleStreamInfo] = []
        for subtitle_idx, s in enumerate(raw_subtitle_streams):
            tags = s.get("tags", {}) or {}
            subtitle_stream_infos.append(SubtitleStreamInfo(
                ffmpeg_index=int(s.get("index", 0)),
                subtitle_index=subtitle_idx,
                codec=str(s.get("codec_name") or "unknown"),
                language=str(tags.get("language") or "und").lower().strip(),
                title=str(tags.get("title") or ""),
            ))

        first_audio = audio_stream_infos[0] if audio_stream_infos else None
        duration_raw = (
            payload.get("format", {}).get("duration")
            or video_stream.get("duration")
            or (first_audio and raw_audio_streams[0].get("duration"))
            or 0
        )
        try:
            duration = float(duration_raw)
        except (TypeError, ValueError):
            duration = 0.0

        width = int(video_stream.get("width") or 0)
        height = int(video_stream.get("height") or 0)
        if width <= 0 or height <= 0:
            raise RuntimeError("The video stream is missing frame dimensions.")

        return ProbeInfo(
            duration=duration,
            width=width,
            height=height,
            has_audio=bool(audio_stream_infos),
            video_codec=str(video_stream.get("codec_name") or "unknown"),
            audio_codec=str(first_audio.codec if first_audio else "none"),
            audio_streams=audio_stream_infos,
            subtitle_streams=subtitle_stream_infos,
        )

    def detect_crop(self, source_path: Path, probe: ProbeInfo) -> tuple[int, int, int, int]:
        source_width = probe.width
        source_height = probe.height
        sample_offsets = [0.18, 0.58]
        sample_length = scan_length_for(probe.duration)
        limit = crop_limit_for(self.options.crop_aggressiveness)
        percentile = crop_percentile_for(self.options.crop_aggressiveness)
        margins = {"left": [], "top": [], "right": [], "bottom": []}

        for offset in sample_offsets:
            if self._cancel_requested:
                raise RuntimeError("Canceled.")
            start = 0.0
            if probe.duration > sample_length:
                start = clamp(probe.duration * offset, 0.0, max(probe.duration - sample_length, 0.0))
            command = [
                FFMPEG_PATH,
                "-hide_banner",
                "-ss",
                f"{start:.2f}",
                "-i",
                str(source_path),
                "-t",
                f"{sample_length:.2f}",
                "-vf",
                f"fps=1,cropdetect={limit}:2:0",
                "-an",
                "-sn",
                "-dn",
                "-f",
                "null",
                "-",
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
            crop_hits = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", completed.stderr)
            for width, height, x, y in crop_hits:
                width_i = int(width)
                height_i = int(height)
                x_i = int(x)
                y_i = int(y)
                if width_i <= 0 or height_i <= 0:
                    continue
                right_i = max(0, source_width - (x_i + width_i))
                bottom_i = max(0, source_height - (y_i + height_i))
                margins["left"].append(max(0, x_i))
                margins["top"].append(max(0, y_i))
                margins["right"].append(right_i)
                margins["bottom"].append(bottom_i)

        if not any(margins.values()):
            self.log_message.emit(f"No black bars detected for {source_path.name}; using full frame.")
            return (0, 0, even_floor(source_width), even_floor(source_height))

        left = even_floor(percentile_value(margins["left"], percentile), 0)
        top = even_floor(percentile_value(margins["top"], percentile), 0)
        right = even_floor(percentile_value(margins["right"], percentile), 0)
        bottom = even_floor(percentile_value(margins["bottom"], percentile), 0)
        crop_width = even_floor(source_width - left - right)
        crop_height = even_floor(source_height - top - bottom)

        if crop_width >= source_width - 4 and crop_height >= source_height - 4:
            return (0, 0, even_floor(source_width), even_floor(source_height))
        if crop_width < source_width * 0.4 or crop_height < source_height * 0.4:
            self.log_message.emit(
                f"Crop analysis for {source_path.name} looked unsafe; keeping the full frame instead."
            )
            return (0, 0, even_floor(source_width), even_floor(source_height))

        self.log_message.emit(
            f"Auto-crop for {source_path.name}: {crop_width}x{crop_height}+{left}+{top}."
        )
        return (left, top, crop_width, crop_height)

    def apply_target_aspect(
        self,
        crop: tuple[int, int, int, int],
        source_width: int,
        source_height: int,
    ) -> tuple[int, int, int, int]:
        x, y, width, height = crop
        target_ratio = self.options.aspect_ratio
        current_ratio = width / height
        tolerance = 0.015
        if self.options.framing_mode == "Keep More Picture":
            return (x, y, even_floor(width), even_floor(height))
        if abs(current_ratio - target_ratio) <= tolerance:
            return (x, y, even_floor(width), even_floor(height))

        if current_ratio > target_ratio:
            new_width = even_floor(int(height * target_ratio))
            delta = even_floor((width - new_width) // 2, 0)
            x += delta
            width = new_width
        else:
            new_height = even_floor(int(width / target_ratio))
            delta = even_floor((height - new_height) // 2, 0)
            y += delta
            height = new_height

        width = min(width, even_floor(source_width - x))
        height = min(height, even_floor(source_height - y))
        return (max(0, x), max(0, y), even_floor(width), even_floor(height))

    def describe_subtitle_selection(
        self,
        file_name: str,
        subtitle_streams: list[SubtitleStreamInfo],
        chosen_subtitle: "SubtitleStreamInfo | None",
        preference: str,
    ) -> str:
        if preference == "No Subtitles":
            return f"Subtitles for {file_name}: none selected."
        if not subtitle_streams:
            return f"Subtitles for {file_name}: skipped; no subtitle tracks found."
        if chosen_subtitle is None:
            if preference in {"Copy English Subtitles", SUBTITLE_BURN_LABEL}:
                return f"Subtitles for {file_name}: skipped; no English text subtitle track found."
            return f"Subtitles for {file_name}: skipped; no usable subtitle track found."
        if not is_text_subtitle(chosen_subtitle.codec):
            return f"Subtitles for {file_name}: skipped; image-based subtitles are not supported yet."
        action = "burned" if subtitle_mode(preference) == "burn" else "copied"
        track_label = "English track" if preference in {"Copy English Subtitles", SUBTITLE_BURN_LABEL} else "track"
        lang = chosen_subtitle.language or "und"
        return (
            f"Subtitles for {file_name}: {action} {track_label} "
            f"{chosen_subtitle.subtitle_index} ({lang}, {chosen_subtitle.codec})."
        )

    def transcode(
        self,
        source_path: Path,
        output_path: Path,
        probe: ProbeInfo,
        crop: tuple[int, int, int, int],
        chosen_audio: "AudioStreamInfo | None",
        chosen_subtitle: "SubtitleStreamInfo | None",
    ) -> None:
        primary_encoder = (
            "mpeg4"
            if self.options.output_profile["video_codec"] == "mpeg4"
            else resolve_video_encoder(self.options.encoder_mode)
        )
        encoder_order = [primary_encoder]
        if primary_encoder not in {"libx264", "mpeg4"}:
            encoder_order.append("libx264")

        last_error = "FFmpeg reported an error while transcoding."
        allow_burn_retry = self.options.subtitle_preference == SUBTITLE_BURN_LABEL
        for encoder_name in encoder_order:
            try:
                self.transcode_with_encoder(
                    source_path,
                    output_path,
                    probe,
                    crop,
                    encoder_name,
                    chosen_audio,
                    chosen_subtitle,
                    self.options.subtitle_preference,
                )
                if encoder_name != primary_encoder:
                    self.log_message.emit(
                        f"{source_path.name}: switched to compatibility mode after the fast encoder said no."
                    )
                return
            except RuntimeError as exc:
                last_error = str(exc)
                if allow_burn_retry and self.is_subtitle_burn_failure(last_error):
                    allow_burn_retry = False
                    if output_path.exists():
                        output_path.unlink(missing_ok=True)
                    self.file_progress.emit(0)
                    self.phase_changed.emit(
                        f"Retrying {source_path.name} without subtitles — the original subtitle track could not be used"
                    )
                    self.log_message.emit(
                        f"Subtitle burn-in failed for {source_path.name}; retrying without subtitles."
                    )
                    self.transcode_with_encoder(
                        source_path,
                        output_path,
                        probe,
                        crop,
                        encoder_name,
                        chosen_audio,
                        None,
                        "No Subtitles",
                    )
                    return
                if encoder_name == encoder_order[-1]:
                    break
                if output_path.exists():
                    output_path.unlink(missing_ok=True)
                self.file_progress.emit(0)
                self.phase_changed.emit(
                    f"Retrying {source_path.name} in compatibility mode — this file needs the slower fallback"
                )
                self.log_message.emit(
                    f"{source_path.name}: fast Mac encoding was unavailable, so trying compatibility mode."
                )
        raise RuntimeError(last_error)

    def transcode_with_encoder(
        self,
        source_path: Path,
        output_path: Path,
        probe: ProbeInfo,
        crop: tuple[int, int, int, int],
        video_encoder: str,
        chosen_audio: "AudioStreamInfo | None",
        chosen_subtitle: "SubtitleStreamInfo | None",
        subtitle_preference: str,
    ) -> None:
        x, y, width, height = crop
        use_audio_leveling = (
            self.options.audio_leveling_enabled
            and chosen_audio is not None
            and FFMPEG_HAS_LOUDNORM_FILTER
        )
        quality = self.options.quality_profile
        output_profile = self.options.output_profile
        video_filter, use_filter_complex = self.build_video_filter(
            source_path,
            x,
            y,
            width,
            height,
            chosen_subtitle if subtitle_mode(subtitle_preference) == "burn" else None,
        )

        command = [
            FFMPEG_PATH,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            "-nostats",
            "-i",
            str(source_path),
            "-map_metadata",
            "0",
            "-map_chapters",
            "0",
        ]

        if chosen_audio is not None:
            command.extend(["-map", f"0:{chosen_audio.ffmpeg_index}"])

        subtitle_copy = (
            subtitle_mode(subtitle_preference) == "copy"
            and chosen_subtitle is not None
            and is_text_subtitle(chosen_subtitle.codec)
            and bool(output_profile["subtitle_codec"])
        )
        if subtitle_copy:
            command.extend(["-map", f"0:{chosen_subtitle.ffmpeg_index}"])

        command.extend(
            [
                *(["-sn"] if not subtitle_copy else []),
                "-dn",
                "-pix_fmt",
                "yuv420p",
            ]
        )
        if output_profile["extension"] == ".mp4":
            command.extend(["-movflags", "+faststart"])
        if output_profile["video_codec"] == "h264":
            command.extend(["-profile:v", "high"])

        if use_filter_complex:
            command.extend(["-filter_complex", video_filter, "-map", "[vout]"])
        else:
            command.extend(["-map", "0:v:0"])
            command.extend(["-vf", video_filter])

        if video_encoder == "mpeg4":
            command.extend(["-c:v", "mpeg4", "-q:v", "3"])
        elif video_encoder == "h264_videotoolbox":
            command.extend(
                [
                    "-c:v",
                    "h264_videotoolbox",
                    "-allow_sw",
                    "1",
                    "-b:v",
                    quality["vt_bitrate"],
                    "-maxrate",
                    quality["vt_maxrate"],
                ]
            )
        else:
            command.extend(
                [
                    "-c:v",
                    "libx264",
                    "-preset",
                    quality["preset"],
                    "-crf",
                    str(quality["crf"]),
                ]
            )

        if chosen_audio is not None:
            if use_audio_leveling:
                command.extend(["-af", AUDIO_LEVELING_FILTER])
            if output_profile["audio_codec"] == "mp3":
                command.extend(["-c:a", "mp3", "-b:a", "192k", "-ar", "48000"])
            else:
                command.extend(
                    ["-c:a", "aac", "-b:a", quality["audio_bitrate"], "-ar", "48000"]
                )
        else:
            command.append("-an")

        if subtitle_copy:
            command.extend(["-c:s", str(output_profile["subtitle_codec"])])

        command.append(str(output_path))

        self._active_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        progress_data: dict[str, str] = {}
        ffmpeg_messages: list[str] = []

        try:
            assert self._active_process.stdout is not None
            for raw_line in self._active_process.stdout:
                if self._cancel_requested:
                    self.request_cancel()
                    raise RuntimeError("Canceled.")
                line = raw_line.strip()
                if not line or "=" not in line:
                    if line:
                        ffmpeg_messages.append(line)
                        ffmpeg_messages = ffmpeg_messages[-80:]
                    continue
                key, value = line.split("=", 1)
                progress_data[key] = value
                if key == "progress" and value == "end":
                    self.phase_changed.emit(f"Finishing {source_path.name} — saving and checking the new file")
                seconds = seconds_from_progress(
                    progress_data.get("out_time")
                    or progress_data.get("out_time_us")
                    or progress_data.get("out_time_ms")
                    or ""
                )
                if seconds is not None and probe.duration > 0:
                    pct = int(clamp((seconds / probe.duration) * 100.0, 0.0, 99.0))
                    self.file_progress.emit(pct)

            return_code = self._active_process.wait()
        finally:
            self._active_process = None

        if self._cancel_requested:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            raise RuntimeError("Canceled.")

        if return_code != 0:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            raise RuntimeError("\n".join(ffmpeg_messages).strip() or "FFmpeg reported an error while transcoding.")

    def is_subtitle_burn_failure(self, error_text: str) -> bool:
        lowered = error_text.lower()
        hints = ["subtitles", "subtitle", "libass", "filter", "unable to open", "error initializing"]
        return any(hint in lowered for hint in hints)

    def build_video_filter(
        self,
        source_path: Path,
        x: int,
        y: int,
        width: int,
        height: int,
        burned_subtitle: "SubtitleStreamInfo | None" = None,
    ) -> tuple[str, bool]:
        crop_filter = f"crop={width}:{height}:{x}:{y}"
        target_w = self.options.target_width
        target_h = self.options.target_height
        subtitle_filter = ""
        if burned_subtitle is not None and is_text_subtitle(burned_subtitle.codec):
            subtitle_filter = (
                f",subtitles=filename='{escape_subtitle_filter_path(source_path)}':si={burned_subtitle.subtitle_index}"
            )
        if self.options.framing_mode == "Keep More Picture":
            return (
                "[0:v]"
                f"{crop_filter},split=2[bg][fg];"
                f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,gblur=sigma=28,"
                f"crop={target_w}:{target_h}[bgfill];"
                f"[fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fgfit];"
                f"[bgfill][fgfit]overlay=(W-w)/2:(H-h)/2,setsar=1{subtitle_filter}[vout]",
                True,
            )
        return (
            f"{crop_filter},scale={target_w}:{target_h}:flags=lanczos,setsar=1{subtitle_filter}",
            False,
        )


class SidebarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(8, 10, 26))
        grad.setColorAt(1.0, QColor(13, 16, 38))
        painter.fillRect(0, 0, w, h, grad)
        painter.setPen(Qt.NoPen)
        for sx, sy, sv in _STARTUP_STARS[:28]:
            px = int(sx * w)
            py = int(sy * h)
            alpha_boost = 0.55
            if sv > 0.75:
                painter.setBrush(QColor(255, 218, 96, int((150 + sv * 90) * alpha_boost)))
                painter.drawEllipse(QPointF(px, py), 1.3, 1.3)
            elif sv > 0.4:
                painter.setBrush(QColor(148, 196, 255, int((110 + sv * 100) * alpha_boost)))
                painter.drawEllipse(QPointF(px, py), 0.9, 0.9)
            else:
                painter.setBrush(QColor(200, 212, 252, int((70 + sv * 110) * alpha_boost)))
                painter.drawEllipse(QPointF(px, py), 0.6, 0.6)

        glow = QLinearGradient(w - 24, 0, w, 0)
        glow.setColorAt(0.0, QColor(68, 108, 235, 0))
        glow.setColorAt(1.0, QColor(68, 108, 235, 32))
        painter.fillRect(w - 24, 0, 24, h, glow)

        painter.setPen(QPen(QColor(40, 56, 150, 180), 1))
        painter.drawLine(w - 1, 0, w - 1, h)
        painter.end()


class MediaWaveConverterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.primary_font_family, self.secondary_font_family = load_brand_fonts()
        self.worker: BatchWorker | None = None
        self.last_options: ConversionOptions | None = None
        self.source_rows: dict[str, int] = {}
        self._source_paths: list[Path] = []
        self._rename_files: list[RenameFileInfo] = []
        self._metadata_search_worker: MetadataSearchWorker | None = None
        self._episode_lookup_worker: TVmazeEpisodeWorker | None = None
        self._selected_metadata_result: dict[str, Any] | None = None
        self._nav_buttons: dict[str, QPushButton] = {}
        self._batch_started_at: float | None = None
        self._eta_seconds: float | None = None
        self._eta_total = 0
        self._eta_completed = 0
        self._eta_file_progress = 0
        self._cancel_in_progress = False
        self._close_after_cancel = False
        self._finish_timer = QTimer(self)
        self._finish_timer.setInterval(1000)
        self._finish_timer.timeout.connect(self.update_finish_timer)
        self.setup_window()
        self.build_ui()
        self.apply_styles()
        self.load_settings()
        self.refresh_ffmpeg_status()
        self.refresh_main_summary()
        self.resume_button.setEnabled(self.load_session() is not None)

    def setup_window(self) -> None:
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1180, 840)
        self.setMinimumSize(980, 720)

    def build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = SidebarWidget()
        sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        nav_header = QWidget()
        nav_header.setObjectName("advNavHeader")
        nav_header_layout = QVBoxLayout(nav_header)
        nav_header_layout.setContentsMargins(20, 22, 16, 16)
        nav_header_layout.setSpacing(6)

        logo_lbl = QLabel()
        logo_lbl.setObjectName("sidebarLogo")
        logo_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        logo_source = CONVERTER_LOGO_PATH if (CONVERTER_LOGO_PATH and CONVERTER_LOGO_PATH.exists()) else LOGO_PATH
        if logo_source and logo_source.exists():
            px = QPixmap(str(logo_source))
            logo_lbl.setPixmap(px.scaled(154, 62, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_lbl.setText("MW")
        nav_header_layout.addWidget(logo_lbl)

        app_sub = QLabel("A Great Place to Fix your Files!")
        app_sub.setObjectName("advNavTagline")
        subtitle_font = QFont(self.secondary_font_family or self.font().family(), 13)
        subtitle_font.setItalic(True)
        subtitle_font.setBold(True)
        app_sub.setFont(subtitle_font)
        app_sub.setWordWrap(True)
        app_sub.setAlignment(Qt.AlignLeft)
        nav_header_layout.addWidget(app_sub)
        sidebar_layout.addWidget(nav_header)

        nav_sep = QWidget()
        nav_sep.setObjectName("advNavSep")
        nav_sep.setFixedHeight(1)
        sidebar_layout.addWidget(nav_sep)

        self.converter_nav = self.make_nav_button("converter", "📼  Converter")
        self.queue_nav = self.make_nav_button("queue", "📋  Queue")
        self.rename_nav = self.make_nav_button("rename", "✨  Rename your Files!")
        self.advanced_nav = self.make_nav_button("advanced", "⚙  Advanced Settings")
        sidebar_layout.addWidget(self.converter_nav)
        sidebar_layout.addWidget(self.queue_nav)
        sidebar_layout.addWidget(self.rename_nav)
        sidebar_layout.addWidget(self.advanced_nav)

        sidebar_layout.addStretch()

        self.ffmpeg_status = QLabel()
        self.ffmpeg_status.setObjectName("ffmpegStatus")
        self.ffmpeg_status.setWordWrap(True)
        self.ffmpeg_status.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(self.ffmpeg_status)
        sidebar_layout.addSpacing(8)

        coaxie = CoaxieWidget(size=82)
        sidebar_layout.addWidget(coaxie, 0, Qt.AlignHCenter)
        sidebar_layout.addSpacing(6)

        ver_lbl = QLabel(f"v{DISPLAY_VERSION}\nMamaWeegee Enterprises 1997-2026")
        ver_lbl.setObjectName("advNavFooter")
        ver_lbl.setAlignment(Qt.AlignLeft)
        ver_lbl.setWordWrap(True)
        ver_lbl.setContentsMargins(20, 0, 16, 14)
        sidebar_layout.addWidget(ver_lbl)

        root.addWidget(sidebar)

        content = QWidget()
        content.setObjectName("contentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(0)
        root.addWidget(content, 1)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("advContentStack")
        content_layout.addWidget(self.page_stack, 1)

        self.converter_page = self.build_converter_page()
        self.queue_page = self.build_queue_page()
        self.rename_page = self.build_rename_page()
        self.advanced_page = self.build_advanced_page()
        self.page_stack.addWidget(self.converter_page)
        self.page_stack.addWidget(self.queue_page)
        self.page_stack.addWidget(self.rename_page)
        self.page_stack.addWidget(self.advanced_page)
        self.switch_page("converter")

    def make_nav_button(self, page_key: str, label: str) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("advNavItem")
        button.setCheckable(True)
        button.setFlat(True)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda checked=False, key=page_key: self.switch_page(key))
        self._nav_buttons[page_key] = button
        return button

    def panel_heading(self, text: str) -> QLabel:
        heading = QLabel(text)
        heading.setObjectName("sectionHeader")
        return heading

    def form_row(self, label_text: str, widget: QWidget, button: QWidget | None = None) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setObjectName("configLabel")
        label.setFixedWidth(118)
        row.addWidget(label)
        row.addWidget(widget, 1)
        if button is not None:
            row.addWidget(button)
        return row

    def make_summary_value(self, key: str, layout: QHBoxLayout) -> QLabel:
        wrap = QWidget()
        wrap.setObjectName("summaryCell")
        chip_layout = QVBoxLayout(wrap)
        chip_layout.setContentsMargins(10, 8, 10, 8)
        chip_layout.setSpacing(2)
        key_label = QLabel(key)
        key_label.setObjectName("summaryKey")
        value_label = QLabel("—")
        value_label.setObjectName("summaryValue")
        value_label.setWordWrap(True)
        wrap.setMinimumHeight(56)
        chip_layout.addWidget(key_label)
        chip_layout.addWidget(value_label)
        layout.addWidget(wrap, 1)
        return value_label

    def make_scroll_page(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("pageBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(4, 4, 4, 4)
        body_layout.setSpacing(16)
        scroll.setWidget(body)
        return scroll, body_layout

    def build_converter_page(self) -> QWidget:
        page, layout = self.make_scroll_page()

        source_panel = QFrame()
        source_panel.setObjectName("panel")
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(18, 16, 18, 16)
        source_layout.setSpacing(10)
        source_layout.addWidget(self.panel_heading("Source"))

        drop_zone = DropZone()
        drop_zone.sources_dropped.connect(self._apply_sources)
        drop_zone.setMinimumHeight(84)
        source_layout.addWidget(drop_zone)

        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Source folder")
        choose_files = QPushButton("Choose File(s)")
        choose_files.clicked.connect(self._pick_files)
        choose_folder = QPushButton("Choose Folder")
        choose_folder.clicked.connect(self.pick_source_folder)
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(choose_files)
        source_row.addWidget(choose_folder)
        source_layout.addLayout(source_row)

        self.source_summary_label = QLabel()
        self.source_summary_label.setObjectName("fieldHelp")
        self.source_summary_label.hide()
        source_layout.addWidget(self.source_summary_label)
        layout.addWidget(source_panel)

        setup_panel = QFrame()
        setup_panel.setObjectName("panel")
        setup_layout = QVBoxLayout(setup_panel)
        setup_layout.setContentsMargins(18, 16, 18, 16)
        setup_layout.setSpacing(10)
        setup_layout.addWidget(self.panel_heading("Converter"))

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Output folder")
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self.pick_output_folder)
        setup_layout.addLayout(self.form_row("Output folder", self.output_edit, output_browse))

        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(list(ASPECT_CHOICES.keys()))
        self.aspect_combo.currentTextChanged.connect(self.refresh_main_summary)
        self.aspect_combo.currentTextChanged.connect(self.sync_advanced_size_options)
        setup_layout.addLayout(self.form_row("Screen shape", self.aspect_combo))

        self.framing_mode_combo = QComboBox()
        self.framing_mode_combo.addItems(list(FRAMING_CHOICES.keys()))
        self.framing_mode_combo.currentTextChanged.connect(self.sync_framing_to_advanced)
        setup_layout.addLayout(self.form_row("Framing", self.framing_mode_combo))

        self.audio_pref_combo = QComboBox()
        self.audio_pref_combo.addItems(AUDIO_PREFERENCES)
        self.audio_pref_combo.currentTextChanged.connect(self.refresh_main_summary)
        setup_layout.addLayout(self.form_row("Audio", self.audio_pref_combo))

        self.audio_leveling_checkbox = QCheckBox("Level audio volume")
        self.audio_leveling_checkbox.setToolTip(
            "Normalizes loudness so quiet files get safer volume boost and loud files are less jarring. "
            "Uses FFmpeg loudnorm when available."
        )
        self.audio_leveling_checkbox.toggled.connect(self.refresh_main_summary)
        setup_layout.addLayout(self.form_row("Audio Leveling", self.audio_leveling_checkbox))

        self.subtitle_pref_combo = QComboBox()
        self.subtitle_pref_combo.addItems(SUBTITLE_PREFERENCES)
        self.subtitle_pref_combo.currentTextChanged.connect(self.refresh_main_summary)
        setup_layout.addLayout(self.form_row("Subtitles", self.subtitle_pref_combo))

        advanced_row = QHBoxLayout()
        advanced_row.addStretch()
        self.advanced_button = QPushButton("Advanced Settings")
        self.advanced_button.clicked.connect(self.open_advanced_settings)
        advanced_row.addWidget(self.advanced_button)
        setup_layout.addLayout(advanced_row)
        layout.addWidget(setup_panel)

        ready_panel = QFrame()
        ready_panel.setObjectName("panel")
        ready_layout = QVBoxLayout(ready_panel)
        ready_layout.setContentsMargins(18, 16, 18, 16)
        ready_layout.setSpacing(10)
        ready_layout.addWidget(self.panel_heading("Ready"))

        chips_row_one = QHBoxLayout()
        chips_row_one.setSpacing(10)
        chips_row_two = QHBoxLayout()
        chips_row_two.setSpacing(10)
        chips_row_three = QHBoxLayout()
        chips_row_three.setSpacing(10)
        self._pf_source = self.make_summary_value("Source", chips_row_one)
        self._pf_output = self.make_summary_value("Output", chips_row_one)
        self._pf_size = self.make_summary_value("Size", chips_row_two)
        self._pf_framing = self.make_summary_value("Framing", chips_row_two)
        self._pf_audio = self.make_summary_value("Audio", chips_row_three)
        self._pf_subtitles = self.make_summary_value("Subtitles", chips_row_three)
        ready_layout.addLayout(chips_row_one)
        ready_layout.addLayout(chips_row_two)
        ready_layout.addLayout(chips_row_three)

        self.batch_note = QLabel()
        self.batch_note.setObjectName("fieldHelp")
        self.batch_note.setWordWrap(True)
        ready_layout.addWidget(self.batch_note)

        self.phase_label = QLabel()
        self.phase_label.setObjectName("activityDescription")
        self.phase_label.setWordWrap(True)
        self.phase_label.setFixedHeight(38)
        self.phase_label.hide()
        self.finish_timer_label = QLabel("Finish estimate appears after conversion starts.")
        self.finish_timer_label.setObjectName("finishTimer")
        self.finish_timer_label.setFixedHeight(22)
        self.finish_timer_label.hide()

        batch_lbl = QLabel("Batch")
        batch_lbl.setObjectName("metaLabel")
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        ready_layout.addWidget(batch_lbl)
        ready_layout.addWidget(self.overall_progress)
        file_lbl = QLabel("File")
        file_lbl.setObjectName("metaLabel")
        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, 100)
        ready_layout.addWidget(file_lbl)
        ready_layout.addWidget(self.file_progress)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("saveButton")
        self.start_button.clicked.connect(self.start_batch)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_batch)
        self.pause_button.setEnabled(False)
        self.resume_button = QPushButton("Resume")
        self.resume_button.clicked.connect(self.resume_batch)
        self.resume_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_batch)
        self.cancel_button.setEnabled(False)
        action_row.addWidget(self.start_button, 2)
        action_row.addWidget(self.pause_button)
        action_row.addWidget(self.resume_button)
        action_row.addWidget(self.cancel_button)
        ready_layout.addLayout(action_row)

        activity_layout = QVBoxLayout()
        activity_layout.setSpacing(4)
        activity_layout.addWidget(self.phase_label)
        activity_layout.addWidget(self.finish_timer_label)
        activity_layout.addStretch()

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)
        bottom_row.addLayout(activity_layout, 1)
        self.open_output_button = QPushButton("Open Finished Folder")
        self.open_output_button.clicked.connect(self.open_output_folder)
        bottom_row.addWidget(self.open_output_button, 0, Qt.AlignBottom)
        ready_layout.addLayout(bottom_row)
        layout.addWidget(ready_panel, 1)
        layout.addStretch()
        return page

    def build_queue_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(16)

        status_panel = QFrame()
        status_panel.setObjectName("panel")
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(10)
        status_layout.addWidget(self.panel_heading("Status"))

        self.queue_phase_label = QLabel("No batch running right now.")
        self.queue_phase_label.setObjectName("dialogNote")
        self.queue_phase_label.setWordWrap(True)
        self.queue_finish_timer_label = QLabel("Finish estimate appears after conversion starts.")
        self.queue_finish_timer_label.setObjectName("finishTimer")
        self.queue_finish_timer_label.setFixedHeight(22)
        self.queue_finish_timer_label.setMinimumWidth(330)
        self.queue_finish_timer_label.hide()
        queue_status_row = QHBoxLayout()
        queue_status_row.setSpacing(10)
        queue_status_row.addWidget(self.queue_phase_label, 1)
        queue_status_row.addWidget(self.queue_finish_timer_label)
        status_layout.addLayout(queue_status_row)

        queue_progress_row = QHBoxLayout()
        queue_progress_row.setSpacing(14)
        overall_box = QVBoxLayout()
        overall_box.setSpacing(4)
        overall_title = QLabel("Batch progress")
        overall_title.setObjectName("metaLabel")
        self.queue_overall_progress = QProgressBar()
        self.queue_overall_progress.setRange(0, 100)
        overall_box.addWidget(overall_title)
        overall_box.addWidget(self.queue_overall_progress)
        file_box = QVBoxLayout()
        file_box.setSpacing(4)
        file_title = QLabel("File progress")
        file_title.setObjectName("metaLabel")
        self.queue_file_progress = QProgressBar()
        self.queue_file_progress.setRange(0, 100)
        file_box.addWidget(file_title)
        file_box.addWidget(self.queue_file_progress)
        queue_progress_row.addLayout(overall_box, 1)
        queue_progress_row.addLayout(file_box, 1)
        status_layout.addLayout(queue_progress_row)

        counter_row = QHBoxLayout()
        counter_row.setSpacing(8)
        self.total_counter = self.stat_chip("FOUND", "0")
        self.done_counter = self.stat_chip("DONE", "0")
        self.skip_counter = self.stat_chip("SKIPPED", "0")
        self.fail_counter = self.stat_chip("OOPS", "0")
        counter_row.addWidget(self.total_counter["card"])
        counter_row.addWidget(self.done_counter["card"])
        counter_row.addWidget(self.skip_counter["card"])
        counter_row.addWidget(self.fail_counter["card"])
        status_layout.addLayout(counter_row)
        layout.addWidget(status_panel)

        queue_panel = QFrame()
        queue_panel.setObjectName("panel")
        queue_layout = QVBoxLayout(queue_panel)
        queue_layout.setContentsMargins(18, 16, 18, 16)
        queue_layout.setSpacing(10)
        queue_layout.addWidget(self.panel_heading("Queue"))

        self.queue_table = QTableWidget(0, 3)
        self.queue_table.setHorizontalHeaderLabels(["File", "Status", "Where It Went"])
        self.queue_table.horizontalHeader().setStretchLastSection(True)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.queue_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setColumnWidth(0, 320)
        self.queue_table.setColumnWidth(1, 120)
        self.queue_table.setMinimumHeight(300)
        queue_layout.addWidget(self.queue_table, 1)
        layout.addWidget(queue_panel, 2)

        log_panel = QFrame()
        log_panel.setObjectName("panel")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(18, 16, 18, 16)
        log_layout.setSpacing(10)

        log_top = QHBoxLayout()
        log_top.setSpacing(10)
        log_top.addWidget(self.panel_heading("Log"))
        log_top.addStretch()
        clear_log_button = QPushButton("Clear Log")
        clear_log_button.clicked.connect(self.clear_log)
        log_top.addWidget(clear_log_button)
        log_layout.addLayout(log_top)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(1200)
        self.log_output.setMinimumHeight(190)
        log_layout.addWidget(self.log_output, 1)
        layout.addWidget(log_panel, 2)
        return page

    def build_rename_page(self) -> QWidget:
        page, layout = self.make_scroll_page()
        layout.setSpacing(14)

        intro_panel = QFrame()
        intro_panel.setObjectName("panel")
        intro_layout = QVBoxLayout(intro_panel)
        intro_layout.setContentsMargins(18, 16, 18, 16)
        intro_layout.setSpacing(9)
        intro_layout.addWidget(self.panel_heading("Rename your Files!"))
        intro = QLabel(
            "Turn mixed-up show and movie names into one clean library format. MediaWave previews every change first, "
            "and you can search manually whenever the filename guesses wrong."
        )
        intro.setObjectName("dialogNote")
        intro.setWordWrap(True)
        intro_layout.addWidget(intro)

        rename_drop_zone = DropZone()
        rename_drop_zone.sources_dropped.connect(self.apply_rename_sources)
        rename_drop_zone.setMinimumHeight(76)
        intro_layout.addWidget(rename_drop_zone)

        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        add_files = QPushButton("Add Video Files")
        add_files.clicked.connect(self.pick_rename_files)
        add_folder = QPushButton("Add a Folder")
        add_folder.clicked.connect(self.pick_rename_folder)
        clear_files = QPushButton("Clear")
        clear_files.clicked.connect(self.clear_rename_files)
        source_row.addWidget(add_files)
        source_row.addWidget(add_folder)
        source_row.addWidget(clear_files)
        source_row.addStretch()
        intro_layout.addLayout(source_row)
        layout.addWidget(intro_panel)

        search_panel = QFrame()
        search_panel.setObjectName("panel")
        search_layout = QVBoxLayout(search_panel)
        search_layout.setContentsMargins(18, 16, 18, 16)
        search_layout.setSpacing(9)
        self.rename_search_heading = self.panel_heading("Find the Right Show")
        search_layout.addWidget(self.rename_search_heading)
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.rename_mode_combo = QComboBox()
        self.rename_mode_combo.addItems(["Shows", "Movies"])
        self.rename_mode_combo.currentTextChanged.connect(self.change_rename_mode)
        self.rename_provider_combo = QComboBox()
        self.rename_provider_combo.addItems(["All databases", "TVmaze", "AniList"])
        self.rename_search_edit = QLineEdit()
        self.rename_search_edit.setPlaceholderText("Search for any show or anime title")
        self.rename_search_edit.returnPressed.connect(self.search_rename_metadata)
        self.rename_search_button = QPushButton("Search")
        self.rename_search_button.clicked.connect(self.search_rename_metadata)
        search_row.addWidget(self.rename_mode_combo)
        search_row.addWidget(self.rename_provider_combo)
        search_row.addWidget(self.rename_search_edit, 1)
        search_row.addWidget(self.rename_search_button)
        search_layout.addLayout(search_row)

        self.rename_results_table = QTableWidget(0, 4)
        self.rename_results_table.setHorizontalHeaderLabels(["Match", "Source", "Show", "Details"])
        self.rename_results_table.horizontalHeader().setStretchLastSection(True)
        self.rename_results_table.verticalHeader().setVisible(False)
        self.rename_results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rename_results_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.rename_results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rename_results_table.setAlternatingRowColors(True)
        self.rename_results_table.setColumnWidth(0, 75)
        self.rename_results_table.setColumnWidth(1, 85)
        self.rename_results_table.setColumnWidth(2, 270)
        self.resize_rename_results_table(0)
        self.rename_results_table.itemSelectionChanged.connect(self.select_rename_result)
        self.rename_results_table.itemDoubleClicked.connect(lambda _item: self.apply_selected_rename_match())
        search_layout.addWidget(self.rename_results_table)

        result_row = QHBoxLayout()
        result_row.setSpacing(8)
        result_hint = QLabel("Select a match above, then preview it against every loaded file.")
        result_hint.setObjectName("fieldHelp")
        self.apply_rename_match_button = QPushButton("Use This Match")
        self.apply_rename_match_button.clicked.connect(self.apply_selected_rename_match)
        self.apply_rename_match_button.setEnabled(False)
        result_row.addWidget(result_hint, 1)
        result_row.addWidget(self.apply_rename_match_button)
        search_layout.addLayout(result_row)
        self.rename_search_note = QLabel(
            "TVmaze supplies episode names. AniList is useful for finding anime titles, but usually does not provide episode names."
        )
        self.rename_search_note.setObjectName("fieldHelp")
        self.rename_search_note.setWordWrap(True)
        search_layout.addWidget(self.rename_search_note)
        self.rename_provider_credit = QLabel(
            'Metadata search powered by <a href="https://www.tvmaze.com/">TVmaze</a> and '
            '<a href="https://anilist.co/">AniList</a>. Movie search also uses '
            '<a href="https://www.stremio.com/">Cinemeta</a>.'
        )
        self.rename_provider_credit.setObjectName("fieldHelp")
        self.rename_provider_credit.setOpenExternalLinks(True)
        search_layout.addWidget(self.rename_provider_credit)
        layout.addWidget(search_panel)

        preview_panel = QFrame()
        preview_panel.setObjectName("panel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(18, 16, 18, 16)
        preview_layout.setSpacing(9)
        preview_top = QHBoxLayout()
        preview_top.addWidget(self.panel_heading("Rename Preview"))
        preview_top.addStretch()
        self.rename_status_label = QLabel("Add files to begin.")
        self.rename_status_label.setObjectName("fieldHelp")
        preview_top.addWidget(self.rename_status_label)
        preview_layout.addLayout(preview_top)

        self.rename_table = QTableWidget(0, 5)
        self.rename_table.setHorizontalHeaderLabels(["Current File", "Detected Show", "Episode", "Proposed Name", "Status"])
        self.rename_table.horizontalHeader().setStretchLastSection(True)
        self.rename_table.verticalHeader().setVisible(False)
        self.rename_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rename_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rename_table.setAlternatingRowColors(True)
        self.rename_table.setColumnWidth(0, 210)
        self.rename_table.setColumnWidth(1, 145)
        self.rename_table.setColumnWidth(2, 70)
        self.rename_table.setColumnWidth(3, 280)
        self.rename_table.setMinimumHeight(250)
        preview_layout.addWidget(self.rename_table, 1)

        action_row = QHBoxLayout()
        self.undo_rename_button = QPushButton("Undo Last Rename")
        self.undo_rename_button.clicked.connect(self.undo_last_rename)
        self.undo_rename_button.setEnabled((DATA_DIR / "rename_history.json").exists())
        self.rename_files_button = QPushButton("Rename Reviewed Files")
        self.rename_files_button.setObjectName("saveButton")
        self.rename_files_button.clicked.connect(self.rename_reviewed_files)
        self.rename_files_button.setEnabled(False)
        action_row.addWidget(self.undo_rename_button)
        action_row.addStretch()
        action_row.addWidget(self.rename_files_button)
        preview_layout.addLayout(action_row)
        layout.addWidget(preview_panel)
        return page

    def build_advanced_page(self) -> QWidget:
        page, layout = self.make_scroll_page()

        picture_panel = QFrame()
        picture_panel.setObjectName("panel")
        picture_layout = QVBoxLayout(picture_panel)
        picture_layout.setContentsMargins(18, 16, 18, 16)
        picture_layout.setSpacing(10)
        picture_layout.addWidget(self.panel_heading("Picture"))

        self.size_combo = QComboBox()
        picture_layout.addLayout(self.form_row("Final size", self.size_combo))

        self.aspect_match_combo = QComboBox()
        self.aspect_match_combo.addItems(["Keep chosen shape", "Match source shape more closely"])
        picture_layout.addLayout(self.form_row("Shape match", self.aspect_match_combo))

        self.framing_combo = QComboBox()
        self.framing_combo.addItems(list(FRAMING_CHOICES.keys()))
        self.framing_combo.currentTextChanged.connect(self.sync_framing_from_advanced)
        picture_layout.addLayout(self.form_row("Picture style", self.framing_combo))

        self.crop_slider = QSlider(Qt.Horizontal)
        self.crop_slider.setRange(0, 100)
        self.crop_slider.setSingleStep(5)
        self.crop_slider.valueChanged.connect(self.update_crop_label)
        crop_wrap = QWidget()
        crop_wrap_layout = QVBoxLayout(crop_wrap)
        crop_wrap_layout.setContentsMargins(0, 0, 0, 0)
        crop_wrap_layout.setSpacing(4)
        crop_wrap_layout.addWidget(self.crop_slider)
        self.crop_label = QLabel()
        self.crop_label.setObjectName("fieldHelp")
        crop_wrap_layout.addWidget(self.crop_label)
        picture_layout.addLayout(self.form_row("Black-bar trim", crop_wrap))
        layout.addWidget(picture_panel)

        batch_panel = QFrame()
        batch_panel.setObjectName("panel")
        batch_layout = QVBoxLayout(batch_panel)
        batch_layout.setContentsMargins(18, 16, 18, 16)
        batch_layout.setSpacing(10)
        batch_layout.addWidget(self.panel_heading("Batch"))

        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(list(OUTPUT_FORMATS.keys()))
        self.output_format_combo.currentTextChanged.connect(self.update_output_format_note)
        batch_layout.addLayout(self.form_row("File type", self.output_format_combo))
        self.output_format_note = QLabel()
        self.output_format_note.setObjectName("fieldHelp")
        self.output_format_note.setWordWrap(True)
        batch_layout.addWidget(self.output_format_note)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(list(QUALITY_PRESETS.keys()))
        self.quality_combo.currentTextChanged.connect(self.refresh_main_summary)
        batch_layout.addLayout(self.form_row("Speed mode", self.quality_combo))

        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(list(ENCODER_CHOICES.keys()))
        self.encoder_combo.currentTextChanged.connect(self.refresh_main_summary)
        batch_layout.addLayout(self.form_row("Engine", self.encoder_combo))

        self.recursive_checkbox = QCheckBox("Look through subfolders too")
        self.recursive_checkbox.toggled.connect(self.refresh_main_summary)
        batch_layout.addLayout(self.form_row("Folder scan", self.recursive_checkbox))

        self.skip_checkbox = QCheckBox("Skip files that were already finished with these settings")
        self.skip_checkbox.toggled.connect(self.refresh_main_summary)
        batch_layout.addLayout(self.form_row("Repeat runs", self.skip_checkbox))
        layout.addWidget(batch_panel)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self.apply_settings_button = QPushButton("Apply Settings")
        self.apply_settings_button.setObjectName("saveButton")
        self.apply_settings_button.clicked.connect(self.apply_advanced_settings)
        save_row.addWidget(self.apply_settings_button)
        layout.addLayout(save_row)
        layout.addStretch()

        self.size_combo.currentTextChanged.connect(self.refresh_main_summary)
        self.update_output_format_note(self.output_format_combo.currentText())
        return page

    def clear_log(self) -> None:
        self.log_output.clear()

    def update_crop_label(self, value: int) -> None:
        self.crop_label.setText(slider_text(value))
        self.refresh_main_summary()

    def update_output_format_note(self, label: str) -> None:
        profile = OUTPUT_FORMATS.get(label, OUTPUT_FORMATS[DEFAULT_OUTPUT_FORMAT])
        note = str(profile["description"])
        if profile["video_codec"] == "mpeg4":
            note += " AVI always uses compatibility encoding."
        self.output_format_note.setText(note)
        if hasattr(self, "encoder_combo"):
            self.encoder_combo.setEnabled(profile["video_codec"] != "mpeg4")
        self.refresh_main_summary()

    def apply_advanced_settings(self) -> None:
        self.save_settings()
        self.refresh_main_summary()

    def switch_page(self, page_key: str) -> None:
        page_map = {
            "converter": self.converter_page,
            "queue": self.queue_page,
            "rename": self.rename_page,
            "advanced": self.advanced_page,
        }
        target = page_map.get(page_key, self.converter_page)
        self.page_stack.setCurrentWidget(target)
        for key, button in self._nav_buttons.items():
            button.setChecked(key == page_key)

    def stat_chip(self, label: str, value: str) -> dict[str, QWidget | QLabel]:
        card = QFrame()
        card.setObjectName("statCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)
        label_widget = QLabel(label)
        label_widget.setObjectName("statLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName("statValue")
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)
        return {"card": card, "value": value_widget}

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: rgba(13,16,38,255);
            }
            QWidget#centralWidget {
                background: rgba(13,16,38,255);
            }
            QWidget#contentArea {
                background: rgba(13,16,38,255);
            }
            QStackedWidget#advContentStack {
                background: rgba(13,16,38,255);
            }
            QWidget#sidebar {
                background: transparent;
            }
            QWidget#advNavHeader {
                background: transparent;
            }
            QLabel#advNavTagline {
                color: rgba(255,218,96,235);
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QWidget#advNavSep {
                background: rgba(68,108,235,90);
            }
            QPushButton#advNavItem {
                text-align: left;
                padding: 11px 16px 11px 22px;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
                background: transparent;
                color: rgba(138,158,212,255);
                font-size: 13px;
                font-weight: 600;
                min-height: 38px;
            }
            QPushButton#advNavItem:checked {
                border-left: 3px solid rgba(96,144,255,255);
                background: rgba(68,108,235,38);
                color: white;
            }
            QPushButton#advNavItem:hover:!checked {
                background: rgba(68,108,235,18);
                color: rgba(210,222,252,255);
            }
            QLabel#advNavFooter {
                color: rgba(138,158,212,150);
                font-size: 8px;
                background: transparent;
            }
            QLabel#ffmpegStatus {
                color: rgba(255,218,96,220);
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#coaxieLabel {
                color: rgba(96,200,255,255);
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QFrame#panel {
                background: rgba(22,26,58,255);
                border: 1px solid rgba(68,108,235,110);
                border-radius: 10px;
            }
            QLabel#sectionHeader {
                color: rgba(118,162,255,255);
                font-size: 14px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#configLabel {
                color: rgba(210,222,252,255);
                font-size: 13px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#fieldHelp, QLabel#dialogNote, QLabel#metaLabel {
                color: rgba(138,158,212,255);
                font-size: 12px;
                background: transparent;
            }
            QLabel#activityDescription {
                color: rgba(188,205,248,255);
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#finishTimer {
                color: rgba(255,196,36,255);
                font-size: 12px;
                font-weight: 700;
                background: rgba(16,20,50,180);
                border: 1px solid rgba(255,188,10,80);
                border-radius: 5px;
                padding: 2px 8px;
            }
            QWidget#summaryCell {
                background: rgba(16,20,50,220);
                border: 1px solid rgba(68,108,235,110);
                border-radius: 6px;
            }
            QLabel#summaryKey {
                color: rgba(118,162,255,255);
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
                background: transparent;
            }
            QLabel#summaryValue {
                color: rgba(188,205,248,255);
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }
            QFrame#statCard {
                background: rgba(16,20,50,220);
                border: 1px solid rgba(68,108,235,110);
                border-radius: 8px;
            }
            QFrame#dropZone {
                background: rgba(16,20,50,220);
                border: 2px dashed rgba(68,108,235,180);
                border-radius: 10px;
            }
            QFrame#dropZone:hover {
                background: rgba(20,25,60,230);
                border-color: rgba(96,144,255,220);
            }
            QLabel#dropZoneLabel {
                color: rgba(138,158,212,255);
                font-size: 14px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#statLabel {
                color: rgba(138,158,212,255);
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
                background: transparent;
            }
            QLabel#statValue {
                color: rgba(210,222,252,255);
                font-size: 18px;
                font-weight: 700;
                background: transparent;
            }
            QLineEdit, QComboBox, QPlainTextEdit {
                min-height: 30px;
                padding: 4px 9px;
                border-radius: 6px;
                border: 1px solid rgba(68,108,235,160);
                background: rgba(16,20,50,255);
                color: rgba(188,205,248,255);
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
                border: 1px solid rgba(68,108,235,220);
            }
            QComboBox::drop-down {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 26px;
                border-left: 1px solid rgba(68,108,235,110);
                background: rgba(16,20,50,255);
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 8px;
                """ + (f"image: url({_ARROW_DOWN_SVG});" if _ARROW_DOWN_SVG else "") + """
            }
            QComboBox QAbstractItemView {
                border: 1px solid rgba(68,108,235,160);
                background: rgba(18,22,52,255);
                color: rgba(188,205,248,255);
                selection-background-color: rgba(96,144,255,255);
                selection-color: white;
                outline: none;
            }
            QPlainTextEdit {
                font-size: 12px;
                font-family: Menlo, Monaco, monospace;
            }
            QPushButton {
                min-height: 32px;
                padding: 5px 16px;
                border-radius: 7px;
                border: 1px solid rgba(68,108,235,160);
                color: rgba(210,222,252,255);
                background: rgba(30,38,90,220);
                font-size: 12px;
            }
            QPushButton:hover {
                border: 1px solid rgba(68,108,235,220);
                background: rgba(50,70,160,240);
                color: white;
            }
            QPushButton#saveButton {
                color: rgba(13,16,38,255);
                font-weight: 700;
                font-size: 13px;
                border: 2px solid rgba(200,148,0,200);
                background: rgba(255,188,10,255);
            }
            QPushButton#saveButton:hover {
                background: rgba(255,205,40,255);
                color: rgba(13,16,38,255);
            }
            QPushButton:disabled {
                background: rgba(30,38,90,120);
                color: rgba(138,158,212,140);
                border-color: rgba(68,108,235,90);
            }
            QProgressBar {
                min-height: 18px;
                padding: 2px;
                border-radius: 6px;
                border: 1px solid rgba(68,108,235,110);
                background: rgba(16,20,50,255);
                text-align: center;
                color: rgba(188,205,248,255);
                font-size: 11px;
            }
            QProgressBar::chunk {
                border-radius: 5px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(52,86,210,255), stop:1 rgba(255,188,10,255));
            }
            QTableWidget {
                background: rgba(16,20,50,255);
                border: 1px solid rgba(68,108,235,110);
                border-radius: 8px;
                gridline-color: rgba(68,108,235,50);
                alternate-background-color: rgba(30,38,90,150);
                color: rgba(188,205,248,255);
                font-size: 12px;
            }
            QHeaderView::section {
                background: rgba(22,26,58,255);
                color: rgba(210,222,252,255);
                border: none;
                border-bottom: 1px solid rgba(68,108,235,110);
                padding: 6px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QScrollBar:vertical {
                background: rgba(22,26,58,120);
                width: 10px;
                margin: 2px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: rgba(96,144,255,160);
                min-height: 24px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background: rgba(22,26,58,120);
                height: 8px;
                margin: 2px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(96,144,255,160);
                min-width: 24px;
                border-radius: 4px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QCheckBox {
                color: rgba(138,158,212,255);
                font-size: 13px;
                spacing: 8px;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid rgba(68,108,235,160);
                border-radius: 3px;
                background: rgba(16,20,50,255);
            }
            QCheckBox::indicator:checked {
                background: rgba(96,144,255,255);
                border: 1px solid rgba(68,108,235,160);
                """ + (f"image: url({_CHECKBOX_CHECK_SVG});" if _CHECKBOX_CHECK_SVG else "") + """
            }
            QSlider::groove:horizontal {
                height: 7px;
                border-radius: 3px;
                background: rgba(68,108,235,90);
            }
            QSlider::handle:horizontal {
                background: rgba(255,188,10,255);
                border: none;
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            """
        )

    def load_settings(self) -> None:
        settings = load_json(SETTINGS_FILE, {})
        self.source_edit.setText(settings.get("source_root", ""))
        self.output_edit.setText(settings.get("output_root", ""))
        aspect = LEGACY_ASPECT_LABELS.get(settings.get("aspect_label", ""), settings.get("aspect_label", "Classic TV"))
        if aspect in ASPECT_CHOICES:
            self.aspect_combo.setCurrentText(aspect)
        self.sync_advanced_size_options()
        stored_size = settings.get("size_label") or ASPECT_CHOICES[self.aspect_combo.currentText()]["sizes"][0][0]
        index = self.size_combo.findText(stored_size)
        if index >= 0:
            self.size_combo.setCurrentIndex(index)
        quality = LEGACY_QUALITY_LABELS.get(
            settings.get("quality_label", ""),
            settings.get("quality_label", "Best Picture"),
        )
        if quality in QUALITY_PRESETS:
            self.quality_combo.setCurrentText(quality)
        framing_mode = settings.get("framing_mode", "Keep More Picture")
        if framing_mode in FRAMING_CHOICES:
            self.framing_combo.setCurrentText(framing_mode)
            self.framing_mode_combo.setCurrentText(framing_mode)
        self.crop_slider.setValue(int(settings.get("crop_aggressiveness", 45)))
        self.recursive_checkbox.setChecked(bool(settings.get("recursive", True)))
        self.skip_checkbox.setChecked(bool(settings.get("skip_completed", True)))
        self.audio_leveling_checkbox.setChecked(
            bool(settings.get("audio_leveling_enabled", False)) and FFMPEG_HAS_LOUDNORM_FILTER
        )
        encoder_mode = settings.get("encoder_mode", default_encoder_mode())
        if encoder_mode in ENCODER_CHOICES:
            self.encoder_combo.setCurrentText(encoder_mode)
        output_format = settings.get("output_format", DEFAULT_OUTPUT_FORMAT)
        if output_format in OUTPUT_FORMATS:
            self.output_format_combo.setCurrentText(output_format)
        audio_pref = settings.get("audio_preference", "Auto")
        if audio_pref in AUDIO_PREFERENCES:
            self.audio_pref_combo.setCurrentText(audio_pref)
        subtitle_pref = LEGACY_SUBTITLE_PREFERENCES.get(
            settings.get("subtitle_preference", "No Subtitles"),
            settings.get("subtitle_preference", "No Subtitles"),
        )
        if subtitle_pref in SUBTITLE_PREFERENCES:
            self.subtitle_pref_combo.setCurrentText(subtitle_pref)
        self.refresh_main_summary()

    def save_settings(self) -> None:
        payload = {
            "source_root": self.source_edit.text().strip(),
            "output_root": self.output_edit.text().strip(),
            "aspect_label": self.aspect_combo.currentText(),
            "size_label": self.size_combo.currentText(),
            "framing_mode": self.framing_combo.currentText(),
            "quality_label": self.quality_combo.currentText(),
            "output_format": self.output_format_combo.currentText(),
            "crop_aggressiveness": self.crop_slider.value(),
            "encoder_mode": self.encoder_combo.currentText(),
            "recursive": self.recursive_checkbox.isChecked(),
            "skip_completed": self.skip_checkbox.isChecked(),
            "audio_preference": self.audio_pref_combo.currentText(),
            "audio_leveling_enabled": self.audio_leveling_checkbox.isChecked() and FFMPEG_HAS_LOUDNORM_FILTER,
            "subtitle_preference": self.subtitle_pref_combo.currentText(),
        }
        save_json(SETTINGS_FILE, payload)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker and self.worker.isRunning():
            if self._close_after_cancel:
                event.ignore()
                return
            answer = QMessageBox.question(
                self,
                "Batch In Progress",
                "A conversion batch is still running. Stop it and close the app?",
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self._close_after_cancel = True
            self.cancel_batch()
            event.ignore()
            return
        self.save_settings()
        event.accept()

    def refresh_ffmpeg_status(self) -> None:
        if hasattr(self, "audio_leveling_checkbox"):
            self.audio_leveling_checkbox.setEnabled(FFMPEG_HAS_LOUDNORM_FILTER)
            if FFMPEG_HAS_LOUDNORM_FILTER:
                self.audio_leveling_checkbox.setToolTip(
                    "Normalizes loudness so quiet files get safer volume boost and loud files are less jarring. "
                    "Uses FFmpeg loudnorm when available."
                )
            else:
                self.audio_leveling_checkbox.setChecked(False)
                self.audio_leveling_checkbox.setToolTip(AUDIO_LEVELING_UNAVAILABLE_MESSAGE)
        if FFMPEG_PATH and FFPROBE_PATH:
            if FFMPEG_HAS_LOUDNORM_FILTER:
                self.ffmpeg_status.setText("")
            else:
                self.ffmpeg_status.setText(AUDIO_LEVELING_UNAVAILABLE_MESSAGE)
        else:
            self.ffmpeg_status.setText(
                "Video tools (ffmpeg) not found. "
                "Install ffmpeg and make sure it is on your PATH, "
                "or place ffmpeg.exe in the same folder as this app."
            )

    def sync_advanced_size_options(self) -> None:
        if not hasattr(self, "size_combo"):
            return
        current_label = self.size_combo.currentText()
        current_aspect = self.aspect_combo.currentText()
        self.size_combo.blockSignals(True)
        self.size_combo.clear()
        for label, _size in ASPECT_CHOICES[current_aspect]["sizes"]:
            self.size_combo.addItem(label)
        restored = self.size_combo.findText(current_label)
        self.size_combo.setCurrentIndex(restored if restored >= 0 else 0)
        self.size_combo.blockSignals(False)

    def refresh_main_summary(self) -> None:
        required = [
            "size_combo",
            "_pf_source",
            "_pf_output",
            "_pf_size",
            "_pf_framing",
            "_pf_audio",
            "_pf_subtitles",
            "batch_note",
            "crop_slider",
            "output_format_combo",
        ]
        if not all(hasattr(self, name) for name in required):
            return
        size_label = self.size_combo.currentText() or ASPECT_CHOICES[self.aspect_combo.currentText()]["sizes"][0][0]
        framing_label = self.framing_mode_combo.currentText()
        quality_label = self.quality_combo.currentText()
        output_extension = OUTPUT_FORMATS.get(
            self.output_format_combo.currentText(), OUTPUT_FORMATS[DEFAULT_OUTPUT_FORMAT]
        )["extension"].upper().lstrip(".")
        self.batch_note.setText(
            f"{size_label} • {framing_label} • {quality_label} • {output_extension} • "
            f"{slider_text(self.crop_slider.value())}"
        )
        if self._source_paths:
            files = [p for p in self._source_paths if p.is_file()]
            dirs = [p for p in self._source_paths if p.is_dir()]
            parts = []
            if files:
                parts.append(f"{len(files)} file{'s' if len(files) != 1 else ''}")
            if dirs:
                parts.append(f"{len(dirs)} folder{'s' if len(dirs) != 1 else ''}")
            source_text = " + ".join(parts) if parts else "—"
        else:
            src = self.source_edit.text().strip()
            source_text = Path(src).name if src else "—"
        self._pf_source.setText(source_text)
        out = self.output_edit.text().strip()
        self._pf_output.setText(Path(out).name if out else "—")
        aspect = self.aspect_combo.currentText()
        self._pf_size.setText(f"{size_label}\n{aspect}")
        self._pf_framing.setText(framing_label)
        audio_summary = self.audio_pref_combo.currentText()
        if self.audio_leveling_checkbox.isChecked():
            audio_summary += "\nLeveling on"
        self._pf_audio.setText(audio_summary)
        self._pf_subtitles.setText(self.subtitle_pref_combo.currentText())

    def sync_framing_to_advanced(self, label: str) -> None:
        if not hasattr(self, "framing_combo"):
            return
        if self.framing_combo.currentText() != label:
            self.framing_combo.setCurrentText(label)
        self.refresh_main_summary()

    def sync_framing_from_advanced(self, label: str) -> None:
        if not hasattr(self, "framing_mode_combo"):
            return
        if self.framing_mode_combo.currentText() != label:
            self.framing_mode_combo.setCurrentText(label)
        self.refresh_main_summary()

    def open_advanced_settings(self) -> None:
        self.sync_advanced_size_options()
        self.switch_page("advanced")

    def pick_rename_files(self) -> None:
        ext_list = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_VIDEO_EXTENSIONS))
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose Videos to Rename",
            str(Path.home()),
            f"Video Files ({ext_list});;All Files (*)",
        )
        self.add_rename_paths([Path(path) for path in paths])

    def pick_rename_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a Video Folder", str(Path.home()))
        if not folder:
            return
        paths = [
            path for path in sorted(Path(folder).rglob("*"))
            if path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
        ]
        self.add_rename_paths(paths)

    def apply_rename_sources(self, source_paths: list[str]) -> None:
        paths: list[Path] = []
        for source in source_paths:
            path = Path(source)
            if path.is_file():
                paths.append(path)
            elif path.is_dir():
                paths.extend(
                    candidate for candidate in sorted(path.rglob("*"))
                    if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
                )
        self.add_rename_paths(paths)

    def add_rename_paths(self, paths: list[Path]) -> None:
        known = {item.path.resolve() for item in self._rename_files}
        parser = parse_movie_file if self.rename_mode_combo.currentText() == "Movies" else parse_rename_file
        for path in paths:
            if path.exists() and path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                resolved = path.resolve()
                if resolved not in known:
                    known.add(resolved)
                    self._rename_files.append(parser(path))
        self.refresh_rename_table()
        if self._rename_files and not self.rename_search_edit.text().strip():
            self.rename_search_edit.setText(self._rename_files[0].guessed_title)

    def change_rename_mode(self, mode: str) -> None:
        is_movie = mode == "Movies"
        paths = [item.path for item in self._rename_files]
        parser = parse_movie_file if is_movie else parse_rename_file
        self._rename_files = [parser(path) for path in paths]
        self._selected_metadata_result = None
        self.rename_results_table.setRowCount(0)
        self.resize_rename_results_table(0)
        self.apply_rename_match_button.setEnabled(False)
        self.rename_provider_combo.clear()
        self.rename_provider_combo.addItems(
            ["All databases", "Cinemeta", "AniList"] if is_movie
            else ["All databases", "TVmaze", "AniList"]
        )
        self.rename_results_table.setHorizontalHeaderLabels(
            ["Match", "Source", "Title" if is_movie else "Show", "Details"]
        )
        self.rename_search_heading.setText("Find the Right Movie" if is_movie else "Find the Right Show")
        self.rename_search_edit.setPlaceholderText(
            "Search for any movie title" if is_movie else "Search for any show or anime title"
        )
        if paths:
            self.rename_search_edit.setText(self._rename_files[0].guessed_title)
        self.rename_search_note.setText(
            "Movie matches use Cinemeta and AniList. A release year in the filename makes matching more accurate."
            if is_movie else
            "TVmaze supplies episode names. AniList is useful for finding anime titles, but usually does not provide episode names."
        )
        self.rename_provider_credit.setText(
            'Movie search powered by <a href="https://www.stremio.com/">Cinemeta</a> and '
            '<a href="https://anilist.co/">AniList</a>.'
            if is_movie else
            'Metadata search powered by <a href="https://www.tvmaze.com/">TVmaze</a> and '
            '<a href="https://anilist.co/">AniList</a>.'
        )
        self.refresh_rename_table()

    def clear_rename_files(self) -> None:
        self._rename_files.clear()
        self._selected_metadata_result = None
        self.rename_results_table.setRowCount(0)
        self.resize_rename_results_table(0)
        self.apply_rename_match_button.setEnabled(False)
        self.refresh_rename_table()

    def refresh_rename_table(self) -> None:
        is_movie = self.rename_mode_combo.currentText() == "Movies"
        self.rename_table.setHorizontalHeaderLabels(
            ["Current File", "Detected Title", "Year", "Proposed Name", "Status"]
            if is_movie else
            ["Current File", "Detected Show", "Episode", "Proposed Name", "Status"]
        )
        self.rename_table.setRowCount(len(self._rename_files))
        ready = 0
        blockers: dict[str, int] = {}
        for row, item in enumerate(self._rename_files):
            episode_text = ""
            if item.season is not None and item.episode is not None:
                episode_text = f"S{item.season:02d}E{item.episode:02d}"
            elif item.episode is not None:
                episode_text = f"Episode {item.episode}"
            identity_text = item.guessed_year if is_movie else episode_text
            values = [item.path.name, item.guessed_title, identity_text, item.proposed_name, item.status]
            for column, value in enumerate(values):
                self.rename_table.setItem(row, column, QTableWidgetItem(value))
            if item.proposed_name and item.status == "Ready to rename":
                ready += 1
            elif item.status not in {"Renamed"}:
                blockers[item.status] = blockers.get(item.status, 0) + 1
        self.rename_files_button.setEnabled(ready > 0)
        self.rename_files_button.setText(
            f"Rename {ready} Reviewed File{'s' if ready != 1 else ''}" if ready else "Rename Reviewed Files"
        )
        if not self._rename_files:
            self.rename_status_label.setText("Add files to begin.")
            self.rename_files_button.setText("Rename Reviewed Files")
        else:
            status_text = f"{len(self._rename_files)} files loaded • {ready} ready"
            if blockers:
                blocker_text = ", ".join(f"{count} {reason.lower()}" for reason, count in blockers.items())
                status_text += f" • Waiting on: {blocker_text}"
            self.rename_status_label.setText(status_text)

    def search_rename_metadata(self) -> None:
        query = self.rename_search_edit.text().strip()
        if not query:
            target = "movie" if self.rename_mode_combo.currentText() == "Movies" else "show or anime"
            QMessageBox.information(self, "Search for a Title", f"Type a {target} title first.")
            return
        if self._metadata_search_worker and self._metadata_search_worker.isRunning():
            return
        self.rename_search_button.setEnabled(False)
        self.rename_search_note.setText("Searching metadata databases...")
        self.rename_results_table.setRowCount(0)
        self.resize_rename_results_table(0)
        self._selected_metadata_result = None
        self.apply_rename_match_button.setEnabled(False)
        self._metadata_search_worker = MetadataSearchWorker(
            self.rename_provider_combo.currentText(), query, self.rename_mode_combo.currentText()
        )
        self._metadata_search_worker.results_ready.connect(self.show_rename_search_results)
        self._metadata_search_worker.failed.connect(self.show_rename_search_error)
        self._metadata_search_worker.finished.connect(lambda: self.rename_search_button.setEnabled(True))
        self._metadata_search_worker.start()

    def resize_rename_results_table(self, result_count: int) -> None:
        visible_rows = max(1, min(result_count, 6))
        row_height = self.rename_results_table.verticalHeader().defaultSectionSize()
        header_height = self.rename_results_table.horizontalHeader().height()
        frame_height = self.rename_results_table.frameWidth() * 2
        table_height = header_height + (row_height * visible_rows) + frame_height + 2
        self.rename_results_table.setFixedHeight(table_height)

    def show_rename_search_results(self, results: list[dict[str, Any]]) -> None:
        self.rename_results_table.setRowCount(len(results))
        self.resize_rename_results_table(len(results))
        for row, result in enumerate(results):
            values = [
                f"{int(result.get('confidence', 0))}%",
                str(result["provider"]),
                str(result["title"]),
                str(result.get("detail") or ""),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setTextAlignment(Qt.AlignCenter)
                if column == 2:
                    cell.setData(Qt.UserRole, result)
                self.rename_results_table.setItem(row, column, cell)
        self.rename_search_note.setText(
            f"Found {len(results)} possible matches, ranked by title similarity. Confidence is an estimate; check the year and source too."
            if results else "No matches found. Try a shorter title or another database."
        )
        self.apply_rename_match_button.setEnabled(False)
        if results:
            self.rename_results_table.selectRow(0)

    def show_rename_search_error(self, message: str) -> None:
        self.rename_search_note.setText(message)
        self.rename_search_button.setEnabled(True)

    def select_rename_result(self) -> None:
        row = self.rename_results_table.currentRow()
        title_cell = self.rename_results_table.item(row, 2) if row >= 0 else None
        data = title_cell.data(Qt.UserRole) if title_cell is not None else None
        self._selected_metadata_result = data if isinstance(data, dict) else None
        self.apply_rename_match_button.setEnabled(self._selected_metadata_result is not None)

    def apply_selected_rename_match(self) -> None:
        result = self._selected_metadata_result
        if not result or not self._rename_files:
            return
        if self.rename_mode_combo.currentText() == "Movies":
            self.apply_movie_preview(result)
            return
        if result["provider"] == "TVmaze":
            self.apply_rename_match_button.setEnabled(False)
            self.rename_search_note.setText("Getting TVmaze episode names...")
            self._episode_lookup_worker = TVmazeEpisodeWorker(int(result["id"]))
            self._episode_lookup_worker.episodes_ready.connect(self.apply_tvmaze_episodes)
            self._episode_lookup_worker.failed.connect(self.show_rename_search_error)
            self._episode_lookup_worker.finished.connect(lambda: self.apply_rename_match_button.setEnabled(True))
            self._episode_lookup_worker.start()
            return
        self.apply_metadata_preview(result, {}, "AniList")

    def apply_movie_preview(self, result: dict[str, Any]) -> None:
        movie_title = safe_filename_part(str(result["title"]))
        movie_year = str(result.get("year") or "")[:4]
        matched = 0
        proposed_targets: set[Path] = set()
        for item in self._rename_files:
            confidence = metadata_match_confidence(item.guessed_title, movie_title, item.guessed_year, movie_year)
            year_conflict = bool(item.guessed_year and movie_year and item.guessed_year != movie_year)
            if confidence < 78 or year_conflict:
                if not item.proposed_name:
                    item.status = "Needs a movie match"
                continue
            year_suffix = f" ({movie_year})" if movie_year else ""
            item.proposed_name = f"{movie_title}{year_suffix}{item.path.suffix.lower()}"
            target = item.path.with_name(item.proposed_name)
            if target in proposed_targets:
                item.status = "Duplicate proposed name"
            elif target.exists() and target != item.path:
                item.status = "Name already exists"
            else:
                item.status = "Ready to rename"
                proposed_targets.add(target)
            matched += 1
        self.rename_search_note.setText(
            f"Preview matched {matched} file{'s' if matched != 1 else ''} with {result['provider']}. "
            "Only close title and year matches were prepared; review every proposed name before renaming."
        )
        self.refresh_rename_table()

    def apply_tvmaze_episodes(self, episodes: dict[str, str], provider: str) -> None:
        if self._selected_metadata_result:
            self.apply_metadata_preview(self._selected_metadata_result, episodes, provider)

    def apply_metadata_preview(
        self,
        result: dict[str, Any],
        episode_names: dict[str, str],
        provider: str,
    ) -> None:
        show_title = safe_filename_part(str(result["title"]))
        for item in self._rename_files:
            if item.episode is None:
                item.proposed_name = ""
                item.status = "Needs an episode number"
                continue
            season = item.season if item.season is not None else 1
            episode_title = episode_names.get(f"{season}:{item.episode}", "")
            if not episode_title:
                episode_title = item.existing_episode_title or f"Episode {item.episode}"
            episode_title = safe_filename_part(episode_title)
            item.proposed_name = f"{show_title} S{season:02d}E{item.episode:02d} - {episode_title}{item.path.suffix.lower()}"
            target = item.path.with_name(item.proposed_name)
            item.status = "Name already exists" if target.exists() and target != item.path else "Ready to rename"
        note = f"Preview matched with {provider}. Review every proposed name before renaming."
        if provider == "AniList":
            note += " AniList does not provide individual episode names, so unnamed episodes use “Episode N.”"
        self.rename_search_note.setText(note)
        self.refresh_rename_table()

    def rename_reviewed_files(self) -> None:
        ready = [item for item in self._rename_files if item.proposed_name and item.status == "Ready to rename"]
        if not ready:
            reasons: dict[str, list[str]] = {}
            for item in self._rename_files:
                reasons.setdefault(item.status, []).append(item.path.name)
            lines = []
            if reasons.get("Needs a show match"):
                lines.append("Choose a search result and click “Use This Match.”")
            if reasons.get("Needs an episode number"):
                lines.append(
                    "MediaWave could not find an episode number in the filename. "
                    "Try a name containing S01E01, 1x01, Episode 01, or anime-style 01v2."
                )
            if reasons.get("Name already exists"):
                lines.append("A proposed filename already exists in the same folder.")
            if not lines:
                lines.append("No files currently have a reviewed proposed name.")
            self.rename_search_note.setText("Nothing renamed yet. " + " ".join(lines))
            QMessageBox.information(
                self,
                "Nothing Is Ready to Rename",
                "\n\n".join(lines),
            )
            return
        answer = QMessageBox.question(
            self,
            "Rename Reviewed Files",
            f"Rename {len(ready)} reviewed file{'s' if len(ready) != 1 else ''}? "
            "MediaWave will save an undo record.",
        )
        if answer != QMessageBox.Yes:
            return
        operations = []
        for item in ready:
            target = item.path.with_name(item.proposed_name)
            if target.exists() and target != item.path:
                item.status = "Skipped: name already exists"
                continue
            original = item.path
            original.rename(target)
            operations.append({"before": str(original), "after": str(target)})
            item.path = target
            item.status = "Renamed"
        if operations:
            save_json(DATA_DIR / "rename_history.json", {"created_at": int(time.time()), "operations": operations})
            self.undo_rename_button.setEnabled(True)
        self.refresh_rename_table()

    def undo_last_rename(self) -> None:
        history_path = DATA_DIR / "rename_history.json"
        history = load_json(history_path, {})
        operations = history.get("operations") or []
        if not operations:
            self.undo_rename_button.setEnabled(False)
            return
        answer = QMessageBox.question(self, "Undo Last Rename", f"Restore {len(operations)} file names?")
        if answer != QMessageBox.Yes:
            return
        problems = []
        for operation in reversed(operations):
            before = Path(operation["before"])
            after = Path(operation["after"])
            if after.exists() and not before.exists():
                after.rename(before)
            else:
                problems.append(after.name)
        clear_file(history_path)
        self.undo_rename_button.setEnabled(False)
        self.clear_rename_files()
        if problems:
            QMessageBox.warning(self, "Some Files Could Not Be Restored", "\n".join(problems))

    def save_session(self, options: ConversionOptions) -> None:
        save_json(
            SESSION_FILE,
            {
                "source_root": str(options.source_root),
                "output_root": str(options.output_root),
                "aspect_label": options.aspect_label,
                "target_width": options.target_width,
                "target_height": options.target_height,
                "framing_mode": options.framing_mode,
                "crop_aggressiveness": options.crop_aggressiveness,
                "quality_label": options.quality_label,
                "encoder_mode": options.encoder_mode,
                "output_format": options.output_format,
                "recursive": options.recursive,
                "skip_completed": options.skip_completed,
                "audio_preference": options.audio_preference,
                "audio_leveling_enabled": options.audio_leveling_enabled,
                "subtitle_preference": options.subtitle_preference,
                "explicit_files": [str(f) for f in (options.explicit_files or [])],
            },
        )

    def clear_session(self) -> None:
        clear_file(SESSION_FILE)
        self.resume_button.setEnabled(False)

    def load_session(self) -> ConversionOptions | None:
        payload = load_json(SESSION_FILE, {})
        if not payload:
            return None
        try:
            return ConversionOptions(
                source_root=Path(payload["source_root"]),
                output_root=Path(payload["output_root"]),
                aspect_label=payload["aspect_label"],
                target_width=int(payload["target_width"]),
                target_height=int(payload["target_height"]),
                framing_mode=payload.get("framing_mode", "Keep More Picture"),
                crop_aggressiveness=int(payload["crop_aggressiveness"]),
                quality_label=payload["quality_label"],
                encoder_mode=payload.get("encoder_mode", default_encoder_mode()),
                output_format=payload.get("output_format", DEFAULT_OUTPUT_FORMAT),
                recursive=bool(payload["recursive"]),
                skip_completed=bool(payload["skip_completed"]),
                audio_preference=payload.get("audio_preference", "Auto"),
                audio_leveling_enabled=bool(payload.get("audio_leveling_enabled", False))
                and FFMPEG_HAS_LOUDNORM_FILTER,
                subtitle_preference=LEGACY_SUBTITLE_PREFERENCES.get(
                    payload.get("subtitle_preference", "No Subtitles"),
                    payload.get("subtitle_preference", "No Subtitles"),
                ),
                explicit_files=[Path(p) for p in payload["explicit_files"]] if payload.get("explicit_files") else None,
            )
        except (KeyError, TypeError, ValueError):
            self.clear_session()
            return None

    def pick_source_folder(self) -> None:
        current = self.source_edit.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Choose Source Folder", current)
        if not folder:
            return
        self._source_paths = []
        self._refresh_source_display()
        self.source_edit.setText(folder)
        if not self.output_edit.text().strip():
            mw_out = mediawave_converted_dir()
            self.output_edit.setText(str(mw_out if mw_out is not None else Path(folder) / "MediaWave Converted"))
        self.save_settings()

    def pick_output_folder(self) -> None:
        current = self.output_edit.text().strip() or self.source_edit.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Choose Output Folder", current)
        if not folder:
            return
        self.output_edit.setText(folder)
        self.refresh_main_summary()
        self.save_settings()

    def open_output_folder(self) -> None:
        output_root = self.output_edit.text().strip()
        if not output_root:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(output_root))

    def _apply_sources(self, raw_paths: list) -> None:
        """Accept a list of path strings (files and/or folders) from drop or file picker."""
        files = [
            Path(p) for p in raw_paths
            if Path(p).is_file() and Path(p).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
        ]
        dirs = [Path(p) for p in raw_paths if Path(p).is_dir()]
        if not files and not dirs:
            return
        self._source_paths = files + dirs
        common = _common_parent(self._source_paths)
        # Refuse root-level or single-level directories as the default output location
        # (e.g. /, /Volumes, /Users).  Fall back to the first source's own parent.
        if len(common.parts) < 3:
            first = self._source_paths[0]
            common = first.parent if first.is_file() else first
        self.source_edit.setText(str(common))
        mw_out = mediawave_converted_dir()
        self.output_edit.setText(str(mw_out if mw_out is not None else common / "MediaWave Converted"))
        self._refresh_source_display()
        self.save_settings()

    def _pick_files(self) -> None:
        start_dir = self.source_edit.text().strip() or str(Path.home())
        ext_list = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_VIDEO_EXTENSIONS))
        file_filter = f"Video Files ({ext_list});;All Files (*)"
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose Video Files", start_dir, file_filter)
        if paths:
            self._apply_sources(paths)

    def _resolve_explicit_files(self) -> list:
        """Expand self._source_paths into a flat, deduplicated list of video file Paths."""
        recursive = self.recursive_checkbox.isChecked()
        pattern = "**/*" if recursive else "*"
        files: list[Path] = []
        seen: set[Path] = set()
        for path in self._source_paths:
            if path.is_file():
                key = path.resolve()
                if key not in seen and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                    seen.add(key)
                    files.append(path)
            elif path.is_dir():
                for candidate in sorted(path.glob(pattern)):
                    if not candidate.is_file():
                        continue
                    if candidate.name.startswith("."):
                        continue
                    if candidate.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
                        continue
                    if "__mediawave_" in candidate.stem.lower():
                        continue
                    key = candidate.resolve()
                    if key not in seen:
                        seen.add(key)
                        files.append(candidate)
        return files

    def _refresh_source_display(self) -> None:
        if not self._source_paths:
            self.source_summary_label.hide()
            self.refresh_main_summary()
            return
        video_files = [p for p in self._source_paths if p.is_file()]
        dirs = [p for p in self._source_paths if p.is_dir()]
        if len(self._source_paths) == 1:
            if video_files:
                text = f"1 file: {video_files[0].name}"
            else:
                text = f"Folder: {dirs[0].name}"
        else:
            parts = []
            if video_files:
                parts.append(f"{len(video_files)} file{'s' if len(video_files) != 1 else ''}")
            if dirs:
                parts.append(f"{len(dirs)} folder{'s' if len(dirs) != 1 else ''}")
            text = " + ".join(parts) + " ready to convert"
        self.source_summary_label.setText(text)
        self.source_summary_label.show()
        self.refresh_main_summary()

    def current_target_size(self) -> tuple[int, int]:
        current_aspect = self.aspect_combo.currentText()
        selected_label = self.size_combo.currentText()
        for label, size in ASPECT_CHOICES[current_aspect]["sizes"]:
            if label == selected_label:
                return size
        return ASPECT_CHOICES[current_aspect]["sizes"][0][1]

    def gather_options(self) -> ConversionOptions | None:
        output_text = self.output_edit.text().strip()

        if self._source_paths:
            explicit_files = self._resolve_explicit_files()
            if not explicit_files:
                QMessageBox.warning(
                    self,
                    "No Video Files Found",
                    "No supported video files were found in the selected sources.",
                )
                return None
            source_root = _common_parent(explicit_files)
        else:
            source_text = self.source_edit.text().strip()
            source_root = Path(source_text).expanduser()
            if not source_root.exists() or not source_root.is_dir():
                QMessageBox.warning(self, "Missing Source", "Please choose a valid source folder.")
                return None
            explicit_files = None

        if not output_text:
            mw_out = mediawave_converted_dir()
            output_text = str(mw_out if mw_out is not None else source_root / "MediaWave Converted")
            self.output_edit.setText(output_text)
        output_root = Path(output_text).expanduser()
        if source_root.resolve() == output_root.resolve():
            output_root = source_root / "MediaWave Converted"
            self.output_edit.setText(str(output_root))

        width, height = self.current_target_size()
        return ConversionOptions(
            source_root=source_root,
            output_root=output_root,
            aspect_label=self.aspect_combo.currentText(),
            target_width=width,
            target_height=height,
            framing_mode=self.framing_mode_combo.currentText(),
            crop_aggressiveness=self.crop_slider.value(),
            quality_label=self.quality_combo.currentText(),
            encoder_mode=self.encoder_combo.currentText(),
            output_format=self.output_format_combo.currentText(),
            recursive=self.recursive_checkbox.isChecked(),
            skip_completed=self.skip_checkbox.isChecked(),
            audio_preference=self.audio_pref_combo.currentText(),
            audio_leveling_enabled=self.audio_leveling_checkbox.isChecked() and FFMPEG_HAS_LOUDNORM_FILTER,
            subtitle_preference=self.subtitle_pref_combo.currentText(),
            explicit_files=explicit_files,
        )

    def start_batch(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        if not FFMPEG_PATH or not FFPROBE_PATH:
            QMessageBox.warning(
                self,
                "FFmpeg Missing",
                "FFmpeg and FFprobe are required for conversion. Install FFmpeg first.",
            )
            return

        options = self.gather_options()
        if not options:
            return

        self.last_options = options
        self.save_session(options)
        self.save_settings()
        self.reset_queue()
        self.log_output.clear()
        self.update_overall_progress(0)
        self.update_file_progress(0)
        self.update_phase_status("Looking through your folder now...")
        self.start_finish_timer()
        self.worker = BatchWorker(options)
        self.worker.queue_initialized.connect(self.initialize_queue)
        self.worker.row_update.connect(self.update_row)
        self.worker.overall_progress.connect(self.update_overall_progress)
        self.worker.file_progress.connect(self.update_file_progress)
        self.worker.phase_changed.connect(self.update_phase_status)
        self.worker.counters_changed.connect(self.update_counters)
        self.worker.log_message.connect(self.append_log)
        self.worker.ffmpeg_missing.connect(self.show_ffmpeg_warning)
        self.worker.finished_summary.connect(self.handle_finished_summary)
        self.worker.finished.connect(self.finish_close_after_worker)
        self._cancel_in_progress = False
        self._close_after_cancel = False
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.worker.start()

    def pause_batch(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.request_pause()
            self.update_phase_status("Pausing after the current file...")
            self.pause_button.setEnabled(False)

    def resume_batch(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        options = self.load_session() or self.last_options
        if not options:
            return
        self.source_edit.setText(str(options.source_root))
        self.output_edit.setText(str(options.output_root))
        self.aspect_combo.setCurrentText(options.aspect_label)
        self.framing_mode_combo.setCurrentText(options.framing_mode)
        self.sync_advanced_size_options()
        self.framing_combo.setCurrentText(options.framing_mode)
        self.quality_combo.setCurrentText(options.quality_label)
        self.encoder_combo.setCurrentText(options.encoder_mode)
        self.output_format_combo.setCurrentText(options.output_format)
        self.crop_slider.setValue(options.crop_aggressiveness)
        self.recursive_checkbox.setChecked(options.recursive)
        self.skip_checkbox.setChecked(options.skip_completed)
        if options.audio_preference in AUDIO_PREFERENCES:
            self.audio_pref_combo.setCurrentText(options.audio_preference)
        self.audio_leveling_checkbox.setChecked(options.audio_leveling_enabled and FFMPEG_HAS_LOUDNORM_FILTER)
        if options.subtitle_preference in SUBTITLE_PREFERENCES:
            self.subtitle_pref_combo.setCurrentText(options.subtitle_preference)
        self._source_paths = list(options.explicit_files) if options.explicit_files else []
        self._refresh_source_display()
        size_label = f"{options.target_width} x {options.target_height}"
        index = self.size_combo.findText(size_label)
        if index >= 0:
            self.size_combo.setCurrentIndex(index)
        self.refresh_main_summary()
        self.start_batch()

    def cancel_batch(self) -> None:
        if self._cancel_in_progress:
            return
        self._cancel_in_progress = True
        if self.worker and self.worker.isRunning():
            self.worker.request_cancel()
            self.update_phase_status("Stopping conversion...")
            QTimer.singleShot(2500, self.force_stop_worker_if_needed)
        self.cancel_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.clear_session()

    def force_stop_worker_if_needed(self) -> None:
        if self.worker and self.worker.isRunning() and self._cancel_in_progress:
            self.update_phase_status("Finishing shutdown...")
            self.worker.force_kill_active_process()

    def finish_close_after_worker(self) -> None:
        if self._close_after_cancel:
            self._close_after_cancel = False
            self.close()

    def initialize_queue(self, source_paths: list[str]) -> None:
        self.reset_queue()
        source_root = Path(self.source_edit.text().strip()).expanduser()
        for row_index, source in enumerate(source_paths):
            path = Path(source)
            try:
                display_name = str(path.relative_to(source_root))
            except ValueError:
                display_name = path.name
            self.queue_table.insertRow(row_index)
            self.queue_table.setItem(row_index, 0, QTableWidgetItem(display_name))
            self.queue_table.setItem(row_index, 1, QTableWidgetItem("Waiting"))
            self.queue_table.setItem(row_index, 2, QTableWidgetItem(""))
            self.source_rows[source] = row_index

    def reset_queue(self) -> None:
        self.queue_table.setRowCount(0)
        self.source_rows.clear()

    def update_row(self, source: str, status: str, detail: str, output_path: str) -> None:
        row = self.source_rows.get(source)
        if row is None:
            return
        self.queue_table.setItem(row, 1, QTableWidgetItem(status))
        if status in {"Problem", "Skipped", "Stopped"}:
            detail_text = detail
        else:
            detail_text = output_path or detail
        self.queue_table.setItem(row, 2, QTableWidgetItem(detail_text))
        self.queue_table.scrollToItem(self.queue_table.item(row, 0))

    def update_counters(self, total: int, done: int, skipped: int, failed: int) -> None:
        self.total_counter["value"].setText(str(total))
        self.done_counter["value"].setText(str(done))
        self.skip_counter["value"].setText(str(skipped))
        self.fail_counter["value"].setText(str(failed))
        self._eta_total = total
        self._eta_completed = done + skipped + failed

    def update_phase_status(self, message: str) -> None:
        self.phase_label.setText(message)
        self.phase_label.setToolTip(message)
        self.phase_label.show()
        self.queue_phase_label.setText(message)

    def update_overall_progress(self, value: int) -> None:
        self.overall_progress.setValue(value)
        self.queue_overall_progress.setValue(value)

    def update_file_progress(self, value: int) -> None:
        self.file_progress.setValue(value)
        self.queue_file_progress.setValue(value)
        self._eta_file_progress = value if 0 < value < 100 else 0

    def set_finish_timer_text(self, message: str) -> None:
        self.finish_timer_label.setText(message)
        self.queue_finish_timer_label.setText(message)
        self.finish_timer_label.show()
        self.queue_finish_timer_label.show()

    def start_finish_timer(self) -> None:
        self._batch_started_at = time.monotonic()
        self._eta_seconds = None
        self._eta_total = 0
        self._eta_completed = 0
        self._eta_file_progress = 0
        self.set_finish_timer_text("Estimating finish time...")
        self._finish_timer.start()

    def update_finish_timer(self) -> None:
        if self._batch_started_at is None or self._eta_total <= 0:
            self.set_finish_timer_text("Estimating finish time...")
            return

        elapsed = time.monotonic() - self._batch_started_at
        fraction = (self._eta_completed + (self._eta_file_progress / 100.0)) / self._eta_total
        fraction = clamp(fraction, 0.0, 1.0)
        if elapsed < 5 or fraction < 0.01:
            self.set_finish_timer_text("Estimating finish time...")
            return
        if fraction >= 1.0:
            self.set_finish_timer_text(f"Wrapping up • Elapsed {format_time_remaining(elapsed)}")
            return

        raw_remaining = elapsed * ((1.0 - fraction) / fraction)
        if self._eta_seconds is None:
            self._eta_seconds = raw_remaining
        else:
            self._eta_seconds = (self._eta_seconds * 0.72) + (raw_remaining * 0.28)

        finish_at = time.time() + self._eta_seconds
        self.set_finish_timer_text(
            f"About {format_time_remaining(self._eta_seconds)} left • Finishes around {format_finish_clock(finish_at)}"
        )

    def append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_output.appendPlainText(f"[{stamp}] {message}")

    def show_ffmpeg_warning(self, message: str) -> None:
        self._finish_timer.stop()
        self._batch_started_at = None
        self.set_finish_timer_text("Finish estimate unavailable until FFmpeg is ready.")
        QMessageBox.warning(self, "Video Tools Missing", message)
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(bool(self.load_session()))
        self.cancel_button.setEnabled(False)

    def handle_finished_summary(self, summary: dict[str, Any]) -> None:
        self._finish_timer.stop()
        elapsed = time.monotonic() - self._batch_started_at if self._batch_started_at is not None else 0
        self._batch_started_at = None
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self._cancel_in_progress = False
        if summary.get("paused"):
            self.set_finish_timer_text("Paused • Finish estimate will update when resumed.")
            self.resume_button.setEnabled(True)
            self.append_log("Batch paused safely.")
            self.switch_page("queue")
            return
        self.resume_button.setEnabled(False)
        if summary.get("canceled"):
            self.set_finish_timer_text(f"Stopped • Ran for {format_time_remaining(elapsed)}")
            self.append_log("Batch stopped by user.")
            self.clear_session()
            self.switch_page("queue")
            return

        processed = summary.get("processed", 0)
        skipped = summary.get("skipped", 0)
        failed = summary.get("failed", 0)
        total = summary.get("total", 0)
        self.append_log(
            f"Batch finished. {processed} converted, {skipped} skipped, {failed} failed, {total} total."
        )
        self.set_finish_timer_text(f"Finished in {format_time_remaining(elapsed)}")
        self.clear_session()
        self.switch_page("queue")
        QMessageBox.information(
            self,
            "Batch Complete",
            f"Finished files: {processed}\nSkipped: {skipped}\nProblems: {failed}\nFiles found: {total}",
        )


def main() -> int:
    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName("MediaWave")
    app = QApplication(sys.argv)
    # On macOS the bundle .icns handles Dock/app-switcher icons with proper
    # OS-applied rounding.  Only set explicitly on other platforms.
    if sys.platform != "darwin" and CONVERTER_ICON_PATH and CONVERTER_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(CONVERTER_ICON_PATH)))
    window = MediaWaveConverterWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

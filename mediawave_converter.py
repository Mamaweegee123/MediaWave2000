import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal, QPointF, QRectF
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
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
TARGET_LUFS = -16
TARGET_TP = -1.5
TARGET_LRA = 7

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
AUDIO_PREFERENCES = ["Auto", "Prefer English", "Prefer Japanese"]
_ENGLISH_LANG_TAGS = {"eng", "en"}
_JAPANESE_LANG_TAGS = {"jpn", "ja", "jp"}
TEXT_SUBTITLE_CODECS = {"subrip", "ass", "ssa", "webvtt", "mov_text"}


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


def ffmpeg_supports_subtitles_filter(ffmpeg_path: str | None) -> bool:
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
    return bool(re.search(r"\bsubtitles\b", output))


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
    recursive: bool
    skip_completed: bool
    audio_preference: str = "Auto"
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

    def settings_payload(self) -> dict[str, Any]:
        return {
            "pipeline_version": PIPELINE_VERSION,
            "aspect_label": self.aspect_label,
            "target_width": self.target_width,
            "target_height": self.target_height,
            "framing_mode": self.framing_mode,
            "crop_aggressiveness": self.crop_aggressiveness,
            "quality_label": self.quality_label,
            "recursive": self.recursive,
            "audio_preference": self.audio_preference,
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
                self.phase_changed.emit(f"Getting {source_path.name} ready ({index}/{total})")
                self.row_update.emit(row_key, "Checking", "Taking a quick look at the file.", str(output_path))
                probe = self.probe_media(source_path)
                crop = self.detect_crop(source_path, probe)
                crop = self.apply_target_aspect(crop, probe.width, probe.height)
                self.phase_changed.emit(f"Making {source_path.name} MediaWave-ready ({index}/{total})")
                self.row_update.emit(row_key, "Working", "Making the new MP4 file.", str(output_path))
                chosen_audio = select_audio_stream(probe.audio_streams, self.options.audio_preference)
                if chosen_audio is not None:
                    track_desc = f"track {chosen_audio.audio_index} (lang={chosen_audio.language}, codec={chosen_audio.codec}"
                    if chosen_audio.title:
                        track_desc += f", title={chosen_audio.title!r}"
                    track_desc += ")"
                    self.log_message.emit(f"Audio for {source_path.name}: selected {track_desc}.")
                elif probe.has_audio:
                    self.log_message.emit(f"Audio for {source_path.name}: no audio streams found, encoding without audio.")
                chosen_subtitle = select_subtitle_stream(probe.subtitle_streams, self.options.subtitle_preference)
                subtitle_msg = self.describe_subtitle_selection(
                    source_path.name,
                    probe.subtitle_streams,
                    chosen_subtitle,
                    self.options.subtitle_preference,
                )
                self.log_message.emit(subtitle_msg)
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
        try:
            relative_path = source_path.relative_to(self.options.source_root)
        except ValueError:
            return self.options.output_root / f"{source_path.stem}.mp4"
        filename = f"{relative_path.stem}.mp4"
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
        primary_encoder = resolve_video_encoder(self.options.encoder_mode)
        encoder_order = [primary_encoder]
        if primary_encoder != "libx264":
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
        audio_filters = [f"loudnorm=I={TARGET_LUFS}:LRA={TARGET_LRA}:TP={TARGET_TP}"]
        quality = self.options.quality_profile
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
        )
        if subtitle_copy:
            command.extend(["-map", f"0:{chosen_subtitle.ffmpeg_index}"])

        command.extend(
            [
                *(["-sn"] if not subtitle_copy else []),
                "-dn",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-profile:v",
                "high",
            ]
        )

        if use_filter_complex:
            command.extend(["-filter_complex", video_filter, "-map", "[vout]"])
        else:
            command.extend(["-map", "0:v:0"])
            command.extend(["-vf", video_filter])

        if video_encoder == "h264_videotoolbox":
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
            command.extend(
                [
                    "-af",
                    ",".join(audio_filters),
                    "-c:a",
                    "aac",
                    "-b:a",
                    quality["audio_bitrate"],
                    "-ar",
                    "48000",
                ]
            )
        else:
            command.append("-an")

        if subtitle_copy:
            command.extend(["-c:s", "mov_text"])

        command.append(str(output_path))

        self._active_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        progress_data: dict[str, str] = {}

        try:
            assert self._active_process.stdout is not None
            for raw_line in self._active_process.stdout:
                if self._cancel_requested:
                    self.request_cancel()
                    raise RuntimeError("Canceled.")
                line = raw_line.strip()
                if not line or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                progress_data[key] = value
                seconds = seconds_from_progress(
                    progress_data.get("out_time")
                    or progress_data.get("out_time_us")
                    or progress_data.get("out_time_ms")
                    or ""
                )
                if seconds is not None and probe.duration > 0:
                    pct = int(clamp((seconds / probe.duration) * 100.0, 0.0, 100.0))
                    self.file_progress.emit(pct)

            stderr_output = ""
            if self._active_process.stderr is not None:
                stderr_output = self._active_process.stderr.read().strip()
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
            raise RuntimeError(stderr_output or "FFmpeg reported an error while transcoding.")

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
        self._nav_buttons: dict[str, QPushButton] = {}
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
        self.advanced_nav = self.make_nav_button("advanced", "⚙  Advanced Settings")
        sidebar_layout.addWidget(self.converter_nav)
        sidebar_layout.addWidget(self.queue_nav)
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

        ver_lbl = QLabel(f"v{PIPELINE_VERSION}\n© MediaWave")
        ver_lbl.setObjectName("advNavFooter")
        ver_lbl.setAlignment(Qt.AlignLeft)
        ver_lbl.setContentsMargins(20, 0, 0, 14)
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
        self.advanced_page = self.build_advanced_page()
        self.page_stack.addWidget(self.converter_page)
        self.page_stack.addWidget(self.queue_page)
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

        self.phase_label = QLabel("Pick your source and press Start when you're ready.")
        self.phase_label.setObjectName("dialogNote")
        self.phase_label.setWordWrap(True)
        ready_layout.addWidget(self.phase_label)

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
        open_row = QHBoxLayout()
        open_row.addStretch()
        self.open_output_button = QPushButton("Open Finished Folder")
        self.open_output_button.clicked.connect(self.open_output_folder)
        open_row.addWidget(self.open_output_button)
        ready_layout.addLayout(open_row)
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
        status_layout.addWidget(self.queue_phase_label)

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
        return page

    def clear_log(self) -> None:
        self.log_output.clear()

    def update_crop_label(self, value: int) -> None:
        self.crop_label.setText(slider_text(value))
        self.refresh_main_summary()

    def apply_advanced_settings(self) -> None:
        self.save_settings()
        self.refresh_main_summary()

    def switch_page(self, page_key: str) -> None:
        page_map = {
            "converter": self.converter_page,
            "queue": self.queue_page,
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
                color: rgba(138,158,212,255);
                font-size: 10px;
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
                width: 24px;
                border-left: 1px solid rgba(68,108,235,110);
                background: rgba(30,38,90,220);
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
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
                width: 14px;
                height: 14px;
                border: 1px solid rgba(68,108,235,160);
                border-radius: 3px;
                background: rgba(16,20,50,255);
            }
            QCheckBox::indicator:checked {
                background: rgba(96,144,255,255);
                border: 1px solid rgba(68,108,235,160);
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
        encoder_mode = settings.get("encoder_mode", default_encoder_mode())
        if encoder_mode in ENCODER_CHOICES:
            self.encoder_combo.setCurrentText(encoder_mode)
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
            "crop_aggressiveness": self.crop_slider.value(),
            "encoder_mode": self.encoder_combo.currentText(),
            "recursive": self.recursive_checkbox.isChecked(),
            "skip_completed": self.skip_checkbox.isChecked(),
            "audio_preference": self.audio_pref_combo.currentText(),
            "subtitle_preference": self.subtitle_pref_combo.currentText(),
        }
        save_json(SETTINGS_FILE, payload)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker and self.worker.isRunning():
            answer = QMessageBox.question(
                self,
                "Batch In Progress",
                "A conversion batch is still running. Stop it and close the app?",
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.cancel_batch()
            QTimer.singleShot(250, self.close)
            event.ignore()
            return
        self.save_settings()
        event.accept()

    def refresh_ffmpeg_status(self) -> None:
        if FFMPEG_PATH and FFPROBE_PATH:
            self.ffmpeg_status.setText("")
        else:
            self.ffmpeg_status.setText("The video tools are missing, so conversion can't start yet.")

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
        ]
        if not all(hasattr(self, name) for name in required):
            return
        size_label = self.size_combo.currentText() or ASPECT_CHOICES[self.aspect_combo.currentText()]["sizes"][0][0]
        framing_label = self.framing_mode_combo.currentText()
        quality_label = self.quality_combo.currentText()
        self.batch_note.setText(
            f"{size_label} • {framing_label} • {quality_label} • {slider_text(self.crop_slider.value())}"
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
        self._pf_audio.setText(self.audio_pref_combo.currentText())
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
                "recursive": options.recursive,
                "skip_completed": options.skip_completed,
                "audio_preference": options.audio_preference,
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
                recursive=bool(payload["recursive"]),
                skip_completed=bool(payload["skip_completed"]),
                audio_preference=payload.get("audio_preference", "Auto"),
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
            self.output_edit.setText(str(Path(folder) / "MediaWave Converted"))
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
        self.output_edit.setText(str(common / "MediaWave Converted"))
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
            output_text = str(source_root / "MediaWave Converted")
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
            recursive=self.recursive_checkbox.isChecked(),
            skip_completed=self.skip_checkbox.isChecked(),
            audio_preference=self.audio_pref_combo.currentText(),
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
        self.crop_slider.setValue(options.crop_aggressiveness)
        self.recursive_checkbox.setChecked(options.recursive)
        self.skip_checkbox.setChecked(options.skip_completed)
        if options.audio_preference in AUDIO_PREFERENCES:
            self.audio_pref_combo.setCurrentText(options.audio_preference)
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
        if self.worker and self.worker.isRunning():
            self.worker.request_cancel()
            self.update_phase_status("Stopping after the current step...")
        self.cancel_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.clear_session()

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

    def update_phase_status(self, message: str) -> None:
        self.phase_label.setText(message)
        self.queue_phase_label.setText(message)

    def update_overall_progress(self, value: int) -> None:
        self.overall_progress.setValue(value)
        self.queue_overall_progress.setValue(value)

    def update_file_progress(self, value: int) -> None:
        self.file_progress.setValue(value)
        self.queue_file_progress.setValue(value)

    def append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_output.appendPlainText(f"[{stamp}] {message}")

    def show_ffmpeg_warning(self, message: str) -> None:
        QMessageBox.warning(self, "Video Tools Missing", message)
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(bool(self.load_session()))
        self.cancel_button.setEnabled(False)

    def handle_finished_summary(self, summary: dict[str, Any]) -> None:
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        if summary.get("paused"):
            self.resume_button.setEnabled(True)
            self.append_log("Batch paused safely.")
            self.switch_page("queue")
            return
        self.resume_button.setEnabled(False)
        if summary.get("canceled"):
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
    window = MediaWaveConverterWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

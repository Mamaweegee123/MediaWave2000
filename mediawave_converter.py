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

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
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
AVAILABLE_ENCODERS = available_encoders()
LOGO_PATH = resolve_resource_path(
    "logos/MediaWave2000.png",
    "logos/MediaWave-2000-2000-2000-MediaWave-2000.png",
)
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


class AdvancedSettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("For Real Smart Alecks")
        self.resize(540, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(14)
        layout.addLayout(form)

        self.size_combo = QComboBox()
        form.addRow("Final size", self.size_combo)

        self.framing_combo = QComboBox()
        self.framing_combo.addItems(list(FRAMING_CHOICES.keys()))
        form.addRow("Shape match", self.framing_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(list(QUALITY_PRESETS.keys()))
        form.addRow("Picture style", self.quality_combo)

        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(list(ENCODER_CHOICES.keys()))
        form.addRow("Speed mode", self.encoder_combo)

        crop_wrap = QWidget()
        crop_layout = QVBoxLayout(crop_wrap)
        crop_layout.setContentsMargins(0, 0, 0, 0)
        crop_layout.setSpacing(8)
        self.crop_slider = QSlider(Qt.Horizontal)
        self.crop_slider.setRange(0, 100)
        self.crop_label = QLabel()
        self.crop_label.setObjectName("hintText")
        self.crop_slider.valueChanged.connect(self.update_crop_label)
        crop_layout.addWidget(self.crop_slider)
        crop_layout.addWidget(self.crop_label)
        form.addRow("Black-bar trimming", crop_wrap)

        self.recursive_checkbox = QCheckBox("Look through subfolders too")
        form.addRow("Folder scan", self.recursive_checkbox)

        self.skip_checkbox = QCheckBox("Skip files that already match these settings")
        form.addRow("Repeat runs", self.skip_checkbox)

        self.encoder_hint = QLabel()
        self.encoder_hint.setObjectName("hintText")
        self.encoder_hint.setWordWrap(True)
        self.encoder_combo.currentTextChanged.connect(self.update_encoder_hint)
        layout.addWidget(self.encoder_hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_crop_label()
        self.update_encoder_hint(self.encoder_combo.currentText())

    def update_crop_label(self) -> None:
        self.crop_label.setText(
            f"{slider_text(self.crop_slider.value())}. Lower is safer. Higher trims harder."
        )

    def update_encoder_hint(self, label: str) -> None:
        self.encoder_hint.setText(ENCODER_CHOICES.get(label, ""))


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
class ProbeInfo:
    duration: float
    width: int
    height: int
    has_audio: bool
    video_codec: str
    audio_codec: str
    audio_streams: list  # list[AudioStreamInfo]


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
                output_path.parent.mkdir(parents=True, exist_ok=True)
                self.transcode(source_path, output_path, probe, crop, chosen_audio)
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

    def transcode(
        self,
        source_path: Path,
        output_path: Path,
        probe: ProbeInfo,
        crop: tuple[int, int, int, int],
        chosen_audio: "AudioStreamInfo | None",
    ) -> None:
        primary_encoder = resolve_video_encoder(self.options.encoder_mode)
        encoder_order = [primary_encoder]
        if primary_encoder != "libx264":
            encoder_order.append("libx264")

        last_error = "FFmpeg reported an error while transcoding."
        for encoder_name in encoder_order:
            try:
                self.transcode_with_encoder(source_path, output_path, probe, crop, encoder_name, chosen_audio)
                if encoder_name != primary_encoder:
                    self.log_message.emit(
                        f"{source_path.name}: switched to compatibility mode after the fast encoder said no."
                    )
                return
            except RuntimeError as exc:
                last_error = str(exc)
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
    ) -> None:
        x, y, width, height = crop
        audio_filters = [f"loudnorm=I={TARGET_LUFS}:LRA={TARGET_LRA}:TP={TARGET_TP}"]
        quality = self.options.quality_profile
        video_filter, use_filter_complex = self.build_video_filter(x, y, width, height)

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

        command.extend(
            [
                "-sn",
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

    def build_video_filter(self, x: int, y: int, width: int, height: int) -> tuple[str, bool]:
        crop_filter = f"crop={width}:{height}:{x}:{y}"
        target_w = self.options.target_width
        target_h = self.options.target_height
        if self.options.framing_mode == "Keep More Picture":
            return (
                "[0:v]"
                f"{crop_filter},split=2[bg][fg];"
                f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,gblur=sigma=28,"
                f"crop={target_w}:{target_h}[bgfill];"
                f"[fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fgfit];"
                "[bgfill][fgfit]overlay=(W-w)/2:(H-h)/2,setsar=1[vout]",
                True,
            )
        return (
            f"{crop_filter},scale={target_w}:{target_h}:flags=lanczos,setsar=1",
            False,
        )


class MediaWaveConverterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.primary_font_family, self.secondary_font_family = load_brand_fonts()
        self.worker: BatchWorker | None = None
        self.last_options: ConversionOptions | None = None
        self.source_rows: dict[str, int] = {}
        self.advanced_dialog: AdvancedSettingsDialog | None = None
        self._source_paths: list[Path] = []
        self.setup_window()
        self.build_ui()
        self.apply_styles()
        self.load_settings()
        self.refresh_ffmpeg_status()
        self.refresh_main_summary()
        self.resume_button.setEnabled(self.load_session() is not None)

    def setup_window(self) -> None:
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1180, 880)
        self.setMinimumSize(920, 760)

    def build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.setCentralWidget(scroll)

        central = QWidget()
        scroll.setWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(18)

        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(28, 28, 28, 28)
        hero_layout.setSpacing(22)

        logo_label = QLabel()
        logo_label.setObjectName("logoLabel")
        logo_label.setFixedSize(120, 120)
        if LOGO_PATH and LOGO_PATH.exists():
            pixmap = QPixmap(str(LOGO_PATH))
            logo_label.setPixmap(pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_label.setText("MW")
            logo_label.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(logo_label, 0, Qt.AlignTop)

        hero_text_layout = QVBoxLayout()
        hero_text_layout.setSpacing(10)
        title = QLabel("Make Your Videos MediaWave-Ready")
        title.setObjectName("heroTitle")
        title.setWordWrap(True)
        if self.primary_font_family:
            title.setFont(QFont(self.primary_font_family, 28))
        subtitle = QLabel("Choose your folders, pick the screen shape, and start.")
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)
        hero_text_layout.addWidget(title)
        hero_text_layout.addWidget(subtitle)

        self.ffmpeg_status = QLabel()
        self.ffmpeg_status.setObjectName("ffmpegStatus")
        self.ffmpeg_status.setWordWrap(True)
        hero_text_layout.addWidget(self.ffmpeg_status)
        hero_layout.addLayout(hero_text_layout, 1)
        root_layout.addWidget(hero_card)

        settings_card = QFrame()
        settings_card.setObjectName("card")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(24, 24, 24, 24)
        settings_layout.setSpacing(16)
        root_layout.addWidget(settings_card)

        drop_zone = DropZone()
        drop_zone.sources_dropped.connect(self._apply_sources)
        settings_layout.addWidget(drop_zone)

        source_label = QLabel("Or choose manually:")
        source_label.setObjectName("hintText")
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Folder to scan for video files.")
        files_button = QPushButton("Choose File(s)")
        files_button.clicked.connect(self._pick_files)
        source_button = QPushButton("Choose Folder")
        source_button.clicked.connect(self.pick_source_folder)
        self.source_summary_label = QLabel()
        self.source_summary_label.setObjectName("hintText")
        self.source_summary_label.hide()
        source_row = QHBoxLayout()
        source_row.setSpacing(10)
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(files_button)
        source_row.addWidget(source_button)
        settings_layout.addWidget(source_label)
        settings_layout.addLayout(source_row)
        settings_layout.addWidget(self.source_summary_label)

        output_label = QLabel("Where should the finished files go?")
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("A matching folder layout will be created here.")
        output_button = QPushButton("Choose Folder")
        output_button.clicked.connect(self.pick_output_folder)
        settings_layout.addWidget(output_label)
        settings_layout.addLayout(self.path_row(self.output_edit, output_button))

        screen_row = QHBoxLayout()
        screen_row.setSpacing(12)
        screen_prompt = QLabel("How should it fill the screen?")
        screen_prompt.setObjectName("sectionLabel")
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(list(ASPECT_CHOICES.keys()))
        self.aspect_combo.currentTextChanged.connect(self.refresh_main_summary)
        screen_row.addWidget(screen_prompt, 0)
        screen_row.addWidget(self.aspect_combo, 1)
        settings_layout.addLayout(screen_row)

        self.framing_mode_combo = QComboBox()
        self.framing_mode_combo.addItems(list(FRAMING_CHOICES.keys()))
        self.framing_mode_combo.currentTextChanged.connect(self.sync_framing_to_advanced)
        framing_row = QHBoxLayout()
        framing_row.setSpacing(12)
        framing_prompt = QLabel("How tightly should it fit?")
        framing_prompt.setObjectName("sectionLabel")
        framing_row.addWidget(framing_prompt, 0)
        framing_row.addWidget(self.framing_mode_combo, 1)
        settings_layout.addLayout(framing_row)

        audio_row = QHBoxLayout()
        audio_row.setSpacing(12)
        audio_prompt = QLabel("Audio track preference")
        audio_prompt.setObjectName("sectionLabel")
        self.audio_pref_combo = QComboBox()
        self.audio_pref_combo.addItems(AUDIO_PREFERENCES)
        audio_row.addWidget(audio_prompt, 0)
        audio_row.addWidget(self.audio_pref_combo, 1)
        settings_layout.addLayout(audio_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.start_button = QPushButton("Start Making MediaWave Files")
        self.start_button.setObjectName("primaryButton")
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
        self.advanced_button = QPushButton("For Real Smart Alecks")
        self.advanced_button.clicked.connect(self.open_advanced_settings)
        open_output_button = QPushButton("Open Finished Folder")
        open_output_button.clicked.connect(self.open_output_folder)
        action_row.addWidget(self.start_button, 1)
        action_row.addWidget(self.pause_button)
        action_row.addWidget(self.resume_button)
        action_row.addWidget(self.advanced_button)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(open_output_button)
        settings_layout.addLayout(action_row)

        progress_card = QFrame()
        progress_card.setObjectName("card")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(22, 22, 22, 22)
        progress_layout.setSpacing(12)
        root_layout.addWidget(progress_card)

        progress_title = QLabel("Progress")
        progress_title.setObjectName("cardTitle")
        progress_layout.addWidget(progress_title)

        self.phase_label = QLabel("Pick your folders and press start when you’re ready.")
        self.phase_label.setObjectName("phaseLabel")
        self.phase_label.setWordWrap(True)
        progress_layout.addWidget(self.phase_label)

        counter_row = QHBoxLayout()
        counter_row.setSpacing(12)
        self.total_counter = self.stat_chip("Found", "0")
        self.done_counter = self.stat_chip("Done", "0")
        self.skip_counter = self.stat_chip("Skipped", "0")
        self.fail_counter = self.stat_chip("Oops", "0")
        counter_row.addWidget(self.total_counter["card"])
        counter_row.addWidget(self.done_counter["card"])
        counter_row.addWidget(self.skip_counter["card"])
        counter_row.addWidget(self.fail_counter["card"])
        progress_layout.addLayout(counter_row)

        progress_layout.addWidget(QLabel("Whole batch"))
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        progress_layout.addWidget(self.overall_progress)

        progress_layout.addWidget(QLabel("File in front of the line"))
        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, 100)
        progress_layout.addWidget(self.file_progress)

        self.batch_note = QLabel()
        self.batch_note.setObjectName("hintText")
        self.batch_note.setWordWrap(True)
        progress_layout.addWidget(self.batch_note)

        queue_card = QFrame()
        queue_card.setObjectName("card")
        queue_layout = QVBoxLayout(queue_card)
        queue_layout.setContentsMargins(22, 22, 22, 22)
        queue_layout.setSpacing(12)
        root_layout.addWidget(queue_card, 1)

        queue_title = QLabel("Queue")
        queue_title.setObjectName("cardTitle")
        queue_layout.addWidget(queue_title)

        self.queue_table = QTableWidget(0, 3)
        self.queue_table.setHorizontalHeaderLabels(["File", "Status", "Where It Went"])
        self.queue_table.horizontalHeader().setStretchLastSection(True)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.queue_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.queue_table.setMinimumHeight(240)
        self.queue_table.setColumnWidth(0, 300)
        self.queue_table.setColumnWidth(1, 160)
        queue_layout.addWidget(self.queue_table, 1)

        log_card = QFrame()
        log_card.setObjectName("card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(22, 22, 22, 22)
        log_layout.setSpacing(12)
        root_layout.addWidget(log_card, 1)

        log_title = QLabel("Log")
        log_title.setObjectName("cardTitle")
        log_layout.addWidget(log_title)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(1200)
        self.log_output.setMinimumHeight(220)
        log_layout.addWidget(self.log_output, 1)

    def path_row(self, field: QLineEdit, button: QPushButton) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.addWidget(field, 1)
        layout.addWidget(button)
        return layout

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
            QMainWindow, QWidget {
                background: #7f9199;
                color: #edf4f5;
                font-size: 14px;
            }
            QFrame#heroCard {
                background: transparent;
                border: none;
            }
            QFrame#card {
                background: transparent;
                border: none;
            }
            QFrame#statCard {
                background: rgba(92, 112, 121, 0.55);
                border: none;
                border-radius: 16px;
            }
            QLabel#heroTitle {
                color: #fff8ee;
                font-size: 34px;
                font-weight: 700;
            }
            QLabel#heroSubtitle {
                color: rgba(245, 250, 251, 0.9);
                font-size: 17px;
            }
            QLabel#ffmpegStatus {
                color: #ffd899;
                font-size: 13px;
                margin-top: 6px;
            }
            QLabel#cardTitle {
                color: #fff4dd;
                font-size: 20px;
                font-weight: 700;
            }
            QLabel#phaseLabel {
                color: #f7fafb;
                font-size: 16px;
                font-weight: 600;
            }
            QLabel#hintText {
                color: rgba(236, 244, 245, 0.7);
                font-size: 13px;
            }
            QLabel#sectionLabel {
                color: #fff4dd;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#statLabel {
                color: rgba(235, 244, 245, 0.74);
                font-size: 12px;
                text-transform: uppercase;
            }
            QLabel#statValue {
                color: #ffcc8a;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#logoLabel {
                background: rgba(255, 255, 255, 0.10);
                border-radius: 18px;
                color: #ffe4b6;
                font-size: 38px;
                font-weight: 800;
            }
            QLineEdit, QComboBox, QPlainTextEdit, QTableWidget {
                background: rgba(72, 88, 96, 0.72);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 14px;
                padding: 10px 12px;
                selection-background-color: #e77d37;
                selection-color: #fffaf4;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background: #5c7079;
                color: #f0f5f6;
                border: 1px solid rgba(255, 255, 255, 0.08);
                selection-background-color: #db6e29;
            }
            QPushButton {
                background: rgba(72, 88, 96, 0.84);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                color: #f4f8f9;
                padding: 11px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(84, 102, 111, 0.92);
            }
            QPushButton#primaryButton {
                background: #e77d37;
                color: #fff9f2;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            QPushButton#primaryButton:hover {
                background: #f08c47;
            }
            QPushButton:disabled {
                background: #1c282d;
                color: rgba(240, 245, 246, 0.4);
            }
            QCheckBox {
                spacing: 10px;
                color: #f2f7f8;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.18);
                background: #0f1b20;
            }
            QCheckBox::indicator:checked {
                background: #e77d37;
            }
            QSlider::groove:horizontal {
                border: none;
                height: 8px;
                border-radius: 4px;
                background: rgba(255, 255, 255, 0.12);
            }
            QSlider::handle:horizontal {
                background: #ffcc8a;
                border: none;
                width: 20px;
                margin: -7px 0;
                border-radius: 10px;
            }
            QProgressBar {
                background: rgba(72, 88, 96, 0.72);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 2px;
                text-align: center;
                color: #f8fafb;
                min-height: 22px;
            }
            QProgressBar::chunk {
                border-radius: 9px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ef7d34, stop:1 #ffd28c);
            }
            QTableWidget {
                gridline-color: rgba(255, 255, 255, 0.05);
                alternate-background-color: rgba(255, 255, 255, 0.025);
            }
            QHeaderView::section {
                background: rgba(92, 112, 121, 0.75);
                color: #f4f8f9;
                border: none;
                padding: 10px;
                font-weight: 700;
            }
            QFrame#dropZone {
                background: rgba(55, 72, 80, 0.50);
                border: 2px dashed rgba(255, 255, 255, 0.22);
                border-radius: 14px;
            }
            QLabel#dropZoneLabel {
                color: rgba(235, 244, 245, 0.60);
                font-size: 15px;
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
        dialog = self.ensure_advanced_dialog()
        self.sync_advanced_size_options()
        stored_size = settings.get("size_label") or ASPECT_CHOICES[self.aspect_combo.currentText()]["sizes"][0][0]
        index = dialog.size_combo.findText(stored_size)
        if index >= 0:
            dialog.size_combo.setCurrentIndex(index)
        quality = LEGACY_QUALITY_LABELS.get(
            settings.get("quality_label", ""),
            settings.get("quality_label", "Best Picture"),
        )
        if quality in QUALITY_PRESETS:
            dialog.quality_combo.setCurrentText(quality)
        framing_mode = settings.get("framing_mode", "Keep More Picture")
        if framing_mode in FRAMING_CHOICES:
            dialog.framing_combo.setCurrentText(framing_mode)
            self.framing_mode_combo.setCurrentText(framing_mode)
        dialog.crop_slider.setValue(int(settings.get("crop_aggressiveness", 45)))
        dialog.recursive_checkbox.setChecked(bool(settings.get("recursive", True)))
        dialog.skip_checkbox.setChecked(bool(settings.get("skip_completed", True)))
        encoder_mode = settings.get("encoder_mode", default_encoder_mode())
        if encoder_mode in ENCODER_CHOICES:
            dialog.encoder_combo.setCurrentText(encoder_mode)
        audio_pref = settings.get("audio_preference", "Auto")
        if audio_pref in AUDIO_PREFERENCES:
            self.audio_pref_combo.setCurrentText(audio_pref)
        self.refresh_main_summary()

    def save_settings(self) -> None:
        dialog = self.ensure_advanced_dialog()
        payload = {
            "source_root": self.source_edit.text().strip(),
            "output_root": self.output_edit.text().strip(),
            "aspect_label": self.aspect_combo.currentText(),
            "size_label": dialog.size_combo.currentText(),
            "framing_mode": dialog.framing_combo.currentText(),
            "quality_label": dialog.quality_combo.currentText(),
            "crop_aggressiveness": dialog.crop_slider.value(),
            "encoder_mode": dialog.encoder_combo.currentText(),
            "recursive": dialog.recursive_checkbox.isChecked(),
            "skip_completed": dialog.skip_checkbox.isChecked(),
            "audio_preference": self.audio_pref_combo.currentText(),
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

    def ensure_advanced_dialog(self) -> AdvancedSettingsDialog:
        if self.advanced_dialog is None:
            self.advanced_dialog = AdvancedSettingsDialog(self)
            self.advanced_dialog.framing_combo.currentTextChanged.connect(self.sync_framing_from_advanced)
            self.advanced_dialog.quality_combo.currentTextChanged.connect(self.refresh_main_summary)
            self.advanced_dialog.encoder_combo.currentTextChanged.connect(self.refresh_main_summary)
            self.advanced_dialog.size_combo.currentTextChanged.connect(self.refresh_main_summary)
            self.advanced_dialog.crop_slider.valueChanged.connect(self.refresh_main_summary)
            self.advanced_dialog.recursive_checkbox.toggled.connect(self.refresh_main_summary)
            self.advanced_dialog.skip_checkbox.toggled.connect(self.refresh_main_summary)
        return self.advanced_dialog

    def advanced_snapshot(self) -> dict[str, Any]:
        dialog = self.ensure_advanced_dialog()
        return {
            "size_label": dialog.size_combo.currentText(),
            "framing_mode": dialog.framing_combo.currentText(),
            "quality_label": dialog.quality_combo.currentText(),
            "crop_aggressiveness": dialog.crop_slider.value(),
            "encoder_mode": dialog.encoder_combo.currentText(),
            "recursive": dialog.recursive_checkbox.isChecked(),
            "skip_completed": dialog.skip_checkbox.isChecked(),
        }

    def restore_advanced_snapshot(self, snapshot: dict[str, Any]) -> None:
        dialog = self.ensure_advanced_dialog()
        index = dialog.size_combo.findText(snapshot.get("size_label", ""))
        if index >= 0:
            dialog.size_combo.setCurrentIndex(index)
        if snapshot.get("framing_mode") in FRAMING_CHOICES:
            dialog.framing_combo.setCurrentText(snapshot["framing_mode"])
            self.framing_mode_combo.setCurrentText(snapshot["framing_mode"])
        if snapshot.get("quality_label") in QUALITY_PRESETS:
            dialog.quality_combo.setCurrentText(snapshot["quality_label"])
        if snapshot.get("encoder_mode") in ENCODER_CHOICES:
            dialog.encoder_combo.setCurrentText(snapshot["encoder_mode"])
        dialog.crop_slider.setValue(int(snapshot.get("crop_aggressiveness", dialog.crop_slider.value())))
        dialog.recursive_checkbox.setChecked(bool(snapshot.get("recursive", dialog.recursive_checkbox.isChecked())))
        dialog.skip_checkbox.setChecked(bool(snapshot.get("skip_completed", dialog.skip_checkbox.isChecked())))

    def sync_advanced_size_options(self) -> None:
        dialog = self.ensure_advanced_dialog()
        current_label = dialog.size_combo.currentText()
        current_aspect = self.aspect_combo.currentText()
        dialog.size_combo.blockSignals(True)
        dialog.size_combo.clear()
        for label, _size in ASPECT_CHOICES[current_aspect]["sizes"]:
            dialog.size_combo.addItem(label)
        restored = dialog.size_combo.findText(current_label)
        dialog.size_combo.setCurrentIndex(restored if restored >= 0 else 0)
        dialog.size_combo.blockSignals(False)

    def refresh_main_summary(self) -> None:
        self.sync_advanced_size_options()
        dialog = self.ensure_advanced_dialog()
        self.batch_note.setText(
            f"{dialog.size_combo.currentText()} • {dialog.framing_combo.currentText()} • {dialog.quality_combo.currentText()}"
        )

    def sync_framing_to_advanced(self, label: str) -> None:
        dialog = self.ensure_advanced_dialog()
        if dialog.framing_combo.currentText() != label:
            dialog.framing_combo.setCurrentText(label)
        self.refresh_main_summary()

    def sync_framing_from_advanced(self, label: str) -> None:
        if self.framing_mode_combo.currentText() != label:
            self.framing_mode_combo.setCurrentText(label)
        self.refresh_main_summary()

    def open_advanced_settings(self) -> None:
        dialog = self.ensure_advanced_dialog()
        self.sync_advanced_size_options()
        snapshot = self.advanced_snapshot()
        if dialog.exec() == QDialog.Accepted:
            self.save_settings()
            self.refresh_main_summary()
        else:
            self.restore_advanced_snapshot(snapshot)
            self.refresh_main_summary()

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
        dialog = self.ensure_advanced_dialog()
        recursive = dialog.recursive_checkbox.isChecked()
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

    def current_target_size(self) -> tuple[int, int]:
        dialog = self.ensure_advanced_dialog()
        current_aspect = self.aspect_combo.currentText()
        selected_label = dialog.size_combo.currentText()
        for label, size in ASPECT_CHOICES[current_aspect]["sizes"]:
            if label == selected_label:
                return size
        return ASPECT_CHOICES[current_aspect]["sizes"][0][1]

    def gather_options(self) -> ConversionOptions | None:
        dialog = self.ensure_advanced_dialog()
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
            crop_aggressiveness=dialog.crop_slider.value(),
            quality_label=dialog.quality_combo.currentText(),
            encoder_mode=dialog.encoder_combo.currentText(),
            recursive=dialog.recursive_checkbox.isChecked(),
            skip_completed=dialog.skip_checkbox.isChecked(),
            audio_preference=self.audio_pref_combo.currentText(),
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
        self.overall_progress.setValue(0)
        self.file_progress.setValue(0)
        self.phase_label.setText("Looking through your folder now...")
        self.worker = BatchWorker(options)
        self.worker.queue_initialized.connect(self.initialize_queue)
        self.worker.row_update.connect(self.update_row)
        self.worker.overall_progress.connect(self.overall_progress.setValue)
        self.worker.file_progress.connect(self.file_progress.setValue)
        self.worker.phase_changed.connect(self.phase_label.setText)
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
            self.phase_label.setText("Pausing after the current file...")
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
        dialog = self.ensure_advanced_dialog()
        self.sync_advanced_size_options()
        dialog.framing_combo.setCurrentText(options.framing_mode)
        dialog.quality_combo.setCurrentText(options.quality_label)
        dialog.encoder_combo.setCurrentText(options.encoder_mode)
        dialog.crop_slider.setValue(options.crop_aggressiveness)
        dialog.recursive_checkbox.setChecked(options.recursive)
        dialog.skip_checkbox.setChecked(options.skip_completed)
        if options.audio_preference in AUDIO_PREFERENCES:
            self.audio_pref_combo.setCurrentText(options.audio_preference)
        self._source_paths = list(options.explicit_files) if options.explicit_files else []
        self._refresh_source_display()
        size_label = f"{options.target_width} x {options.target_height}"
        index = dialog.size_combo.findText(size_label)
        if index >= 0:
            dialog.size_combo.setCurrentIndex(index)
        self.refresh_main_summary()
        self.start_batch()

    def cancel_batch(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.request_cancel()
            self.phase_label.setText("Stopping after the current step...")
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

    def append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_output.appendPlainText(f"[{stamp}] {message}")

    def show_ffmpeg_warning(self, message: str) -> None:
        QMessageBox.warning(self, "Video Tools Missing", message)
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def handle_finished_summary(self, summary: dict[str, Any]) -> None:
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        if summary.get("paused"):
            self.resume_button.setEnabled(True)
            self.append_log("Batch paused safely.")
            return
        self.resume_button.setEnabled(False)
        if summary.get("canceled"):
            self.append_log("Batch stopped by user.")
            self.clear_session()
            return

        processed = summary.get("processed", 0)
        skipped = summary.get("skipped", 0)
        failed = summary.get("failed", 0)
        total = summary.get("total", 0)
        self.append_log(
            f"Batch finished. {processed} converted, {skipped} skipped, {failed} failed, {total} total."
        )
        self.clear_session()
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

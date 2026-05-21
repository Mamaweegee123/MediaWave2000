import os
import sys
import time
import random
import subprocess
import json
import locale
import math
import hashlib
import re
import struct
import threading
import traceback
import urllib.parse
import urllib.request
import urllib.error
from difflib import SequenceMatcher
from collections import defaultdict
import shutil

try:
    import AppKit
    import Foundation
except ImportError:
    AppKit = None
    Foundation = None

from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QFileDialog, QLabel, QHBoxLayout, QComboBox, QFormLayout, QSizePolicy, QProgressBar, QDialog, QLineEdit, QCheckBox, QSpinBox, QListWidget, QAbstractItemView, QScrollArea, QTabWidget
from PySide6.QtCore import Qt, QTimer, Slot, QUrl, Signal, QRect, QPoint, QSize, QEvent
from PySide6.QtGui import QPainter, QColor, QKeySequence, QShortcut, QPixmap, QFont, QFontDatabase, QLinearGradient, QRadialGradient, QPen, QPolygon, QImage, QFontMetrics, QPainterPath
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink, QSoundEffect, QAudioBufferOutput, QAudioFormat
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

APP_NAME = "MediaWave2000"
VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mov")
AUDIO_EXTS = (".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus", ".wma")
METADATA_SCHEMA_VERSION = 2
VAULT_DEBUG_LOGGING = os.environ.get("MEDIAWAVE_VAULT_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
REMOTE_METADATA_EXPERIMENTAL = os.environ.get("MEDIAWAVE_EXPERIMENTAL_REMOTE_METADATA", "").strip().lower() in {"1", "true", "yes", "on"}

GLOBAL_START = time.time() - random.randint(0, 86400)


def resource_base_dir():
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def writable_base_dir():
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        path = os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
        os.makedirs(path, exist_ok=True)
        return path
    return os.path.dirname(os.path.abspath(__file__))


RESOURCE_DIR = resource_base_dir()
DATA_DIR = writable_base_dir()
THUMBNAIL_DIR = os.path.join(DATA_DIR, "thumbnails")
os.makedirs(THUMBNAIL_DIR, exist_ok=True)
YOUTUBE_VIDEO_CACHE_DIR = os.path.join(DATA_DIR, "youtube_video_cache")
os.makedirs(YOUTUBE_VIDEO_CACHE_DIR, exist_ok=True)
METADATA_ARTWORK_DIR = os.path.join(DATA_DIR, "metadata_artwork")
os.makedirs(METADATA_ARTWORK_DIR, exist_ok=True)

LOCAL_POSTER_NAMES = ("poster.jpg", "poster.jpeg", "poster.png", "folder.jpg", "folder.jpeg", "folder.png", "cover.jpg", "cover.jpeg", "cover.png")
LOCAL_FANART_NAMES = ("fanart.jpg", "fanart.jpeg", "fanart.png", "background.jpg", "background.jpeg", "background.png", "backdrop.jpg", "backdrop.jpeg", "backdrop.png")
LOCAL_CLEARLOGO_NAMES = ("clearlogo.png", "clearlogo.jpg", "clearlogo.jpeg", "logo.png", "logo.jpg", "logo.jpeg", "clearlogo-white.png")
LOCAL_DESCRIPTION_NAMES = ("show.txt", "description.txt", "plot.txt", "summary.txt", "desc.txt", "about.txt")


def resolve_resource_path(*relative_candidates):
    bases = [RESOURCE_DIR, os.path.dirname(os.path.abspath(__file__))]
    for base in bases:
        for relative in relative_candidates:
            candidate = os.path.join(base, relative)
            if os.path.exists(candidate):
                return candidate
    return os.path.join(RESOURCE_DIR, relative_candidates[0])


MEDIA_CACHE_FILE = os.path.join(DATA_DIR, "media_cache.json")
SCHEDULE_STATE_FILE = os.path.join(DATA_DIR, "schedule_state.json")
TMDB_CACHE_FILE = os.path.join(DATA_DIR, "tmdb_cache.json")
TMDB_OVERRIDES_FILE = os.path.join(DATA_DIR, "tmdb_overrides.json")
TMDB_REVIEW_FILE = os.path.join(DATA_DIR, "tmdb_review.json")
TMDB_CONFIG_FILE = os.path.join(DATA_DIR, "tmdb_config.json")
APP_SETTINGS_FILE = os.path.join(DATA_DIR, "app_settings.json")
RESUME_STATE_FILE = os.path.join(DATA_DIR, "resume_state.json")
ON_DEMAND_CACHE_FILE = os.path.join(DATA_DIR, "on_demand_catalog.json")
VAULT_DEBUG_LOG_FILE = os.path.join(DATA_DIR, "vault_debug.log")
COMMERCIAL_LIBRARY_CACHE_FILE = os.path.join(DATA_DIR, "commercial_library_cache.json")
SMART_BREAK_CACHE_FILE = os.path.join(DATA_DIR, "smart_break_cache.json")
SPOTIFY_LYRICS_CACHE_FILE = os.path.join(DATA_DIR, "spotify_lyrics_cache.json")
SPOTIFY_TRACK_CACHE_FILE = os.path.join(DATA_DIR, "spotify_track_cache.json")
RADIOWAVE_METADATA_CACHE_FILE = os.path.join(DATA_DIR, "radiowave_metadata_cache.json")
YOUTUBE_PLAYLIST_CACHE_FILE = os.path.join(DATA_DIR, "youtube_playlist_cache.json")
CATALOG_VALIDATION_FILE = os.path.join(DATA_DIR, "catalog_validation.json")
CHANNEL_SWITCH_SOUND = os.path.join(RESOURCE_DIR, "assets", "channel_switch.wav")
APP_LOGO_PATH = resolve_resource_path(
    "logos/MediaWave2000.png",
    "logos/MediaWave-2000-2000-2000-MediaWave-2000.png",
)
CLASSIC_APP_LOGO_PATH = resolve_resource_path("logos/mediawave80s.png")
CLOCK_FONT_PATH = resolve_resource_path("ds_digital/DS-DIGIT.TTF")
CRT_FONT_PATH = resolve_resource_path(
    "Fonts/Samsung CRT TV (extremely close to) 3x.ttf",
    "fonts/Samsung CRT TV (extremely close to) 3x.ttf",
    "Samsung CRT TV (extremely close to) 3x.ttf",
)
GUIDE_PRIMARY_FONT_PATH = resolve_resource_path(
    "Fonts/ArchivoNarrow-Bold.ttf",
    "fonts/ArchivoNarrow-Bold.ttf",
    "assets/ArchivoNarrow-Bold.ttf",
)
GUIDE_SECONDARY_FONT_PATH = resolve_resource_path(
    "Fonts/ArchivoNarrow-SemiBold.ttf",
    "fonts/ArchivoNarrow-SemiBold.ttf",
    "assets/ArchivoNarrow-SemiBold.ttf",
)
VHS_OSD_FONT_PATH = resolve_resource_path(
    "Fonts/vhs-vcr-osd.ttf",
    "fonts/vhs-vcr-osd.ttf",
    "assets/vhs-vcr-osd.ttf",
)
CUTIETOP_FONT_PATH = resolve_resource_path(
    "Fonts/CutieTopRegular-VArx.ttf",
    "fonts/CutieTopRegular-VArx.ttf",
)
VIDEOPHREAK_FONT_PATH = resolve_resource_path(
    "Fonts/VIDEOPHREAK.ttf",
    "fonts/VIDEOPHREAK.ttf",
)
SCIFI2KI_FONT_PATH = resolve_resource_path(
    "Fonts/scifi2ki.ttf",
    "fonts/scifi2ki.ttf",
)
_LOGO_CACHE = {}
_CLOCK_FONT_FAMILY = None
_CRT_FONT_FAMILY = None
_VHS_OSD_FONT_FAMILY = None
_GUIDE_FONT_FAMILY = None
_GUIDE_FONT_FAMILY_SECONDARY = None
_CUTIETOP_FONT_FAMILY = None
_VIDEOPHREAK_FONT_FAMILY = None
_SCIFI2KI_FONT_FAMILY = None
_RADIOWAVE_DEFAULT_ART = None
_UI_PIXMAP_CACHE = {}

GUIDE_UI_SCALE_DEFAULT = 1.0
GUIDE_UI_SCALE_MIN = 0.8
GUIDE_UI_SCALE_MAX = 2.0
GUIDE_UI_SCALE_STEP = 0.1
GUIDE_UI_SCALE_OSD_TIMEOUT_MS = 1800
# Keep heavyweight overlay repaints away from video-frame callbacks.
# The live Guide preview can look alive at ~5 FPS without constantly rebuilding the grid.
GUIDE_PREVIEW_REFRESH_INTERVAL_SECONDS = 0.20
RADIOWAVE_FALLBACK_DURATION_SECONDS = 180.0
METADATA_REQUEST_TIMEOUT_SECONDS = 4
RADIOWAVE_EMPTY_WARNING = (
    "Please fill the server with something quick or you may suffer the consequences! - DJ PlumCrazy"
)

CLASSIC_CABLE_TUNING = {
    "font_paths": {
        "primary": GUIDE_PRIMARY_FONT_PATH,
        "secondary": GUIDE_SECONDARY_FONT_PATH,
    },
    "font_scale": {
        "header": 11,
        "title": 10,
        "body": 9,
        "small": 8,
        "channel_number": 13,
        "channel_abbrev": 9,
        "time": 8,
        "info_title": 10,
        "info_meta": 8,
    },
    "layout": {
        "top_y": 34,
        "preview_ratio": 0.34,
        "preview_height": 0.205,
        "header_height": 24,
        "row_height": 31,
        "channel_col": 68,
        "panel_margin": 16,
        "grid_gap": 2,
    },
    "borders": {
        "cell": QColor(224, 232, 255, 118),
        "selected": QColor(244, 248, 255, 220),
        "header": QColor(188, 206, 255, 110),
        "thickness": 1,
        "selected_thickness": 2,
    },
    "crt": {
        "surface_scale": 0.97,
        "screen_mix_a": 0.045,
        "screen_mix_b": 0.022,
        "scanline_alpha": 10,
        "scanline_step": 4,
        "noise_line_alpha_base": 4,
        "noise_dot_alpha": 10,
    },
}


def clamp_guide_ui_scale(value):
    return max(GUIDE_UI_SCALE_MIN, min(GUIDE_UI_SCALE_MAX, round(float(value), 2)))


def scaled_metric(value, ui_scale, minimum=1, maximum=None):
    scaled = int(round(value * ui_scale))
    if maximum is not None:
        scaled = min(maximum, scaled)
    return max(minimum, scaled)


def scaled_pen(base_width, ui_scale, minimum=1, maximum=4):
    return max(minimum, min(maximum, int(round(base_width * ui_scale))))


def overlay_target_rect(widget):
    parent = widget.parentWidget() if widget is not None else None
    if parent is not None:
        if hasattr(parent, "display_rect"):
            rect = parent.display_rect()
            if rect is not None and not rect.isEmpty():
                return rect
        if hasattr(parent, "video_rect"):
            rect = parent.video_rect()
            if rect is not None and not rect.isEmpty():
                return rect
    return widget.rect() if widget is not None else QRect()


def color_luminance(color):
    if color is None:
        return 0.0
    def channel(value):
        value = max(0.0, min(1.0, value / 255.0))
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    return (
        (0.2126 * channel(color.red()))
        + (0.7152 * channel(color.green()))
        + (0.0722 * channel(color.blue()))
    )


def readable_text_color(background, light=None, dark=None, threshold=0.34):
    light = light or QColor(248, 250, 244)
    dark = dark or QColor(34, 28, 14)
    return dark if color_luminance(background) >= threshold else light


def build_guide_metrics(profile_name, ui_scale, skin_style):
    ui_scale = clamp_guide_ui_scale(ui_scale)
    profile = GUIDE_PROFILES.get(profile_name, GUIDE_PROFILES["Auto"])
    if skin_style == "cable":
        cable = CLASSIC_CABLE_TUNING
        layout = cable["layout"]
        font_scale = cable["font_scale"]
        borders = cable["borders"]
        return {
            "profile_scale": profile["scale"],
            "panel_margin": scaled_metric(layout["panel_margin"], ui_scale, 8),
            "top_y": scaled_metric(layout["top_y"], ui_scale, 20),
            "preview_ratio": layout["preview_ratio"],
            "preview_height": layout["preview_height"],
            "header_height": scaled_metric(layout["header_height"], ui_scale, 18),
            "row_height": scaled_metric(layout["row_height"], ui_scale, 24),
            "channel_col": scaled_metric(layout["channel_col"], ui_scale, 52),
            "grid_gap": scaled_metric(layout["grid_gap"], ui_scale, 1),
            "font_header": scaled_metric(font_scale["header"], ui_scale, 9),
            "font_title": scaled_metric(font_scale["title"], ui_scale, 9),
            "font_body": scaled_metric(font_scale["body"], ui_scale, 8),
            "font_small": scaled_metric(font_scale["small"], ui_scale, 7),
            "font_channel_number": scaled_metric(font_scale["channel_number"], ui_scale, 9),
            "font_channel_abbrev": scaled_metric(font_scale["channel_abbrev"], ui_scale, 7),
            "font_time": scaled_metric(font_scale["time"], ui_scale, 7),
            "font_info_title": scaled_metric(font_scale["info_title"], ui_scale, 9),
            "font_info_meta": scaled_metric(font_scale["info_meta"], ui_scale, 7),
            "cell_border": scaled_pen(borders["thickness"], ui_scale, 1, 3),
            "selected_border": scaled_pen(borders["selected_thickness"], ui_scale, 1, 4),
            "footer_height": scaled_metric(40, ui_scale, 32),
            "footer_y_offset": scaled_metric(72, ui_scale, 56),
        }
    if skin_style == "flat":
        return {
            "profile_scale": profile["scale"],
            "panel_margin": scaled_metric(24, ui_scale, 16),
            "top_y": scaled_metric(62, ui_scale, 38),
            "preview_ratio": profile["preview_ratio"],
            "preview_height": 0.29,
            "header_height": scaled_metric(42, ui_scale, 30),
            "row_height": scaled_metric(48, ui_scale, 36),
            "channel_col": scaled_metric(138, ui_scale, 104),
            "grid_gap": scaled_metric(14, ui_scale, 10),
            "font_header": scaled_metric(17, ui_scale, 13),
            "font_title": scaled_metric(15, ui_scale, 12),
            "font_body": scaled_metric(12, ui_scale, 10),
            "font_small": scaled_metric(10, ui_scale, 9),
            "font_channel_number": scaled_metric(14, ui_scale, 11),
            "font_channel_abbrev": scaled_metric(10, ui_scale, 9),
            "font_time": scaled_metric(10, ui_scale, 9),
            "font_info_title": scaled_metric(15, ui_scale, 12),
            "font_info_meta": scaled_metric(10, ui_scale, 9),
            "cell_border": scaled_pen(1, ui_scale, 1, 2),
            "selected_border": scaled_pen(2, ui_scale, 1, 3),
            "footer_height": scaled_metric(34, ui_scale, 26),
            "footer_y_offset": scaled_metric(54, ui_scale, 40),
        }
    return {
        "profile_scale": profile["scale"],
        "panel_margin": scaled_metric(16, ui_scale, 10),
        "top_y": scaled_metric(50, ui_scale, 28),
        "preview_ratio": profile["preview_ratio"],
        "preview_height": 0.26,
        "header_height": scaled_metric(34, ui_scale, 24),
        "row_height": scaled_metric(34, ui_scale, 26),
        "channel_col": scaled_metric(118, ui_scale, 90),
        "grid_gap": scaled_metric(10, ui_scale, 6),
        "font_header": scaled_metric(15, ui_scale, 11),
        "font_title": scaled_metric(12, ui_scale, 10),
        "font_body": scaled_metric(10, ui_scale, 9),
        "font_small": scaled_metric(9, ui_scale, 8),
        "font_channel_number": scaled_metric(12, ui_scale, 10),
        "font_channel_abbrev": scaled_metric(9, ui_scale, 8),
        "font_time": scaled_metric(9, ui_scale, 8),
        "font_info_title": scaled_metric(12, ui_scale, 10),
        "font_info_meta": scaled_metric(9, ui_scale, 8),
        "cell_border": scaled_pen(1, ui_scale, 1, 2),
        "selected_border": scaled_pen(2, ui_scale, 1, 3),
        "footer_height": scaled_metric(28, ui_scale, 22),
        "footer_y_offset": scaled_metric(42, ui_scale, 32),
    }


def load_json_file(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def save_json_file(path, data):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
    except OSError:
        pass


COMMERCIALS_SCHEMA_VERSION = 1
COMMERCIAL_DENSITY_PRESETS = {
    "none": (0, 0),
    "light": (1, 2),
    "medium": (2, 3),
    "heavy": (3, 5),
}
COMMERCIAL_SPECIAL_CATEGORY_LABELS = {
    "general": "General",
    "movie-theater": "Movie Theater",
    "network-promos": "Network Promos",
    "station-ids": "Station IDs",
}
COMMERCIAL_SIMPLE_PRESETS = {
    "premium": {
        "enabled": False,
        "mode": "between_episodes_only",
        "density": "none",
        "pre_roll_enabled": False,
        "post_roll_enabled": False,
        "allow_bumpers": False,
        "allow_promos": False,
        "prefer_promos": False,
        "allow_station_ids": False,
        "min_ads_per_break": 0,
        "max_ads_per_break": 0,
        "min_seconds_between_breaks": 1800,
        "target_break_interval_minutes": 30,
        "minimum_content_before_first_break_seconds": 1800,
        "break_jitter_seconds": 0,
        "max_ad_seconds_per_half_hour": 0,
        "skip_midroll_if_no_smart_breaks": True,
    },
    "light_tv": {
        "enabled": True,
        "mode": "between_episodes_only",
        "density": "light",
        "pre_roll_enabled": False,
        "post_roll_enabled": True,
        "allow_bumpers": False,
        "allow_promos": False,
        "prefer_promos": False,
        "allow_station_ids": False,
        "min_ads_per_break": 1,
        "max_ads_per_break": 2,
        "min_seconds_between_breaks": 600,
        "target_break_interval_minutes": 10,
        "minimum_content_before_first_break_seconds": 420,
        "break_jitter_seconds": 30,
        "max_ad_seconds_per_half_hour": 120,
        "skip_midroll_if_no_smart_breaks": True,
    },
    "classic_cable": {
        "enabled": True,
        "mode": "hybrid",
        "density": "medium",
        "pre_roll_enabled": False,
        "post_roll_enabled": True,
        "allow_bumpers": True,
        "allow_promos": True,
        "prefer_promos": False,
        "allow_station_ids": True,
        "min_ads_per_break": 2,
        "max_ads_per_break": 3,
        "min_seconds_between_breaks": 330,
        "target_break_interval_minutes": 7,
        "minimum_content_before_first_break_seconds": 90,
        "break_jitter_seconds": 45,
        "max_ad_seconds_per_half_hour": 240,
        "skip_midroll_if_no_smart_breaks": False,
    },
    "heavy_retro": {
        "enabled": True,
        "mode": "hybrid",
        "density": "heavy",
        "pre_roll_enabled": True,
        "post_roll_enabled": True,
        "allow_bumpers": True,
        "allow_promos": True,
        "prefer_promos": True,
        "allow_station_ids": True,
        "min_ads_per_break": 3,
        "max_ads_per_break": 5,
        "min_seconds_between_breaks": 240,
        "target_break_interval_minutes": 5,
        "minimum_content_before_first_break_seconds": 75,
        "break_jitter_seconds": 60,
        "max_ad_seconds_per_half_hour": 360,
        "skip_midroll_if_no_smart_breaks": False,
    },
}


def normalize_commercial_simple_preset(value):
    text = normalize_commercial_category(value).replace("-", "_")
    aliases = {
        "premium_no_ads": "premium",
        "no_ads": "premium",
        "premium_ads_off": "premium",
        "light": "light_tv",
        "classic": "classic_cable",
        "heavy": "heavy_retro",
    }
    text = aliases.get(text, text)
    if text not in COMMERCIAL_SIMPLE_PRESETS:
        return "classic_cable"
    return text


def commercial_simple_preset_label(value):
    mapping = {
        "premium": "Premium / No Ads",
        "light_tv": "Light TV",
        "classic_cable": "Set Top Box",
        "heavy_retro": "Heavy Retro",
    }
    return mapping.get(normalize_commercial_simple_preset(value), "Set Top Box")


def apply_commercial_simple_preset(settings, preset_name, smart_breaks=None, enabled=None, root_folder=None):
    merged = normalize_commercials_config(settings)
    preset_key = normalize_commercial_simple_preset(preset_name)
    merged.update(COMMERCIAL_SIMPLE_PRESETS[preset_key])
    merged["simple_preset"] = preset_key
    if smart_breaks is not None:
        merged["smart_breaks"] = bool(smart_breaks)
    if enabled is not None:
        merged["enabled"] = bool(enabled)
    if root_folder is not None:
        merged["root_folder"] = os.path.abspath(os.path.expanduser(root_folder.strip())) if root_folder else ""
    return normalize_commercials_config(merged)


def commercial_settings_defaults():
    return {
        "enabled": False,
        "root_folder": "",
        "simple_preset": "classic_cable",
        "smart_breaks": True,
        "mode": "between_episodes_only",
        "density": "light",
        "allow_fallback": True,
        "pre_roll_enabled": False,
        "post_roll_enabled": False,
        "allow_bumpers": True,
        "allow_promos": True,
        "prefer_promos": False,
        "allow_station_ids": True,
        "min_ads_per_break": 1,
        "max_ads_per_break": 3,
        "min_seconds_between_breaks": 330,
        "target_break_interval_minutes": 7,
        "minimum_content_before_first_break_seconds": 90,
        "break_jitter_seconds": 45,
        "max_ad_seconds_per_half_hour": 240,
        "skip_midroll_if_no_smart_breaks": False,
        "preferred_era": "",
        "preferred_category": "",
        "channel_overrides": {},
    }


def merge_dict_defaults(data, defaults):
    if not isinstance(defaults, dict):
        return data
    merged = {}
    source = data if isinstance(data, dict) else {}
    for key, default_value in defaults.items():
        current_value = source.get(key)
        if isinstance(default_value, dict):
            merged[key] = merge_dict_defaults(current_value, default_value)
        else:
            merged[key] = current_value if current_value is not None else default_value
    for key, value in source.items():
        if key not in merged:
            merged[key] = value
    return merged


def normalize_commercial_era(value):
    text = re.sub(r"[^0-9a-z]+", "", str(value or "").lower())
    if not text:
        return ""
    mapping = {
        "80s": "80s",
        "1980s": "80s",
        "90s": "90s",
        "1990s": "90s",
        "00s": "2000s",
        "2000s": "2000s",
        "2010s": "2010s",
        "70s": "70s",
        "1970s": "70s",
    }
    return mapping.get(text, str(value or "").strip())


def normalize_commercial_category(value):
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return text


def display_commercial_category(value):
    normalized = normalize_commercial_category(value)
    if not normalized:
        return ""
    if normalized in COMMERCIAL_SPECIAL_CATEGORY_LABELS:
        return COMMERCIAL_SPECIAL_CATEGORY_LABELS[normalized]
    return " ".join(part.capitalize() for part in normalized.split("-"))


def commercials_config_signature(config):
    return stable_hash(json.dumps(config or {}, sort_keys=True))


def normalize_commercials_config(settings):
    merged = merge_dict_defaults(settings or {}, commercial_settings_defaults())
    merged["enabled"] = bool(merged.get("enabled", False))
    merged["smart_breaks"] = bool(merged.get("smart_breaks", True))
    merged["allow_fallback"] = bool(merged.get("allow_fallback", True))
    merged["pre_roll_enabled"] = bool(merged.get("pre_roll_enabled", False))
    merged["post_roll_enabled"] = bool(merged.get("post_roll_enabled", False))
    merged["allow_bumpers"] = bool(merged.get("allow_bumpers", True))
    merged["allow_promos"] = bool(merged.get("allow_promos", True))
    merged["prefer_promos"] = bool(merged.get("prefer_promos", False))
    merged["allow_station_ids"] = bool(merged.get("allow_station_ids", True))
    merged["skip_midroll_if_no_smart_breaks"] = bool(merged.get("skip_midroll_if_no_smart_breaks", False))
    merged["root_folder"] = os.path.abspath(os.path.expanduser((merged.get("root_folder") or "").strip())) if merged.get("root_folder") else ""
    merged["simple_preset"] = normalize_commercial_simple_preset(merged.get("simple_preset", "classic_cable"))
    merged["preferred_era"] = normalize_commercial_era(merged.get("preferred_era", ""))
    merged["preferred_category"] = normalize_commercial_category(merged.get("preferred_category", ""))
    merged["mode"] = str(merged.get("mode", "between_episodes_only") or "between_episodes_only")
    if merged["mode"] not in {"between_episodes_only", "natural_breaks", "timed_breaks", "hybrid"}:
        merged["mode"] = "between_episodes_only"
    merged["density"] = str(merged.get("density", "light") or "light").lower()
    if merged["density"] not in {"none", "light", "medium", "heavy", "custom"}:
        merged["density"] = "light"
    for key in (
        "min_ads_per_break",
        "max_ads_per_break",
        "min_seconds_between_breaks",
        "target_break_interval_minutes",
        "minimum_content_before_first_break_seconds",
        "break_jitter_seconds",
        "max_ad_seconds_per_half_hour",
    ):
        try:
            merged[key] = int(merged.get(key, commercial_settings_defaults()[key]) or commercial_settings_defaults()[key])
        except (TypeError, ValueError):
            merged[key] = commercial_settings_defaults()[key]
    merged["min_ads_per_break"] = max(0, merged["min_ads_per_break"])
    merged["max_ads_per_break"] = max(merged["min_ads_per_break"], merged["max_ads_per_break"])
    normalized_overrides = {}
    for channel_name, override in (merged.get("channel_overrides") or {}).items():
        if not isinstance(channel_name, str) or not isinstance(override, dict):
            continue
        normalized_overrides[str(channel_name)] = {
            "enabled_mode": str(override.get("enabled_mode", "inherit") or "inherit"),
            "preferred_era": normalize_commercial_era(override.get("preferred_era", "")),
            "preferred_category": normalize_commercial_category(override.get("preferred_category", "")),
            "mode": str(override.get("mode", merged["mode"]) or merged["mode"]),
            "density": str(override.get("density", merged["density"]) or merged["density"]).lower(),
            "min_ads_per_break": int(override.get("min_ads_per_break", merged["min_ads_per_break"]) or merged["min_ads_per_break"]),
            "max_ads_per_break": int(override.get("max_ads_per_break", merged["max_ads_per_break"]) or merged["max_ads_per_break"]),
            "min_seconds_between_breaks": int(override.get("min_seconds_between_breaks", merged["min_seconds_between_breaks"]) or merged["min_seconds_between_breaks"]),
            "target_break_interval_minutes": int(override.get("target_break_interval_minutes", merged["target_break_interval_minutes"]) or merged["target_break_interval_minutes"]),
            "minimum_content_before_first_break_seconds": int(override.get("minimum_content_before_first_break_seconds", merged["minimum_content_before_first_break_seconds"]) or merged["minimum_content_before_first_break_seconds"]),
            "max_ad_seconds_per_half_hour": int(override.get("max_ad_seconds_per_half_hour", merged["max_ad_seconds_per_half_hour"]) or merged["max_ad_seconds_per_half_hour"]),
            "allow_fallback": bool(override.get("allow_fallback", merged["allow_fallback"])),
            "allow_bumpers": bool(override.get("allow_bumpers", merged["allow_bumpers"])),
            "allow_promos": bool(override.get("allow_promos", merged["allow_promos"])),
            "prefer_promos": bool(override.get("prefer_promos", merged["prefer_promos"])),
            "allow_station_ids": bool(override.get("allow_station_ids", merged["allow_station_ids"])),
        }
    merged["channel_overrides"] = normalized_overrides
    return merged


def infer_commercial_asset_kind(parts):
    joined = " ".join(str(part or "").lower() for part in parts)
    if re.search(r"\bbumper(s)?\b", joined):
        return "bumper"
    if re.search(r"\b(station ids?|idents?|ident|ids?)\b", joined):
        return "station_id"
    if re.search(r"\b(network promos?|promos?)\b", joined):
        return "promo"
    return "commercial"


def infer_commercial_era_from_parts(parts):
    for part in parts:
        era = normalize_commercial_era(part)
        if era:
            return era
    return ""


def infer_program_era_from_path(path, channel_name=""):
    haystack = " ".join(
        part for part in (
            channel_name,
            os.path.basename(os.path.dirname(path or "")),
            os.path.basename(path or ""),
        )
        if part
    )
    lower = haystack.lower()
    if re.search(r"\b(80s|198[0-9])\b", lower):
        return "80s"
    if re.search(r"\b(90s|199[0-9])\b", lower):
        return "90s"
    if re.search(r"\b(2000s|200[0-9]|00s)\b", lower):
        return "2000s"
    if re.search(r"\b(2010s|201[0-9])\b", lower):
        return "2010s"
    if re.search(r"\b(70s|197[0-9])\b", lower):
        return "70s"
    return ""


def infer_program_category_from_path(path, channel_name=""):
    haystack = " ".join(
        part for part in (
            channel_name,
            os.path.dirname(path or ""),
            os.path.basename(path or ""),
        )
        if part
    ).lower()
    category_rules = (
        ("kids", ("kids", "cartoon", "nick", "toon", "4kids", "family", "disney")),
        ("toys", ("toy", "toys")),
        ("food", ("food", "fast food", "restaurant")),
        ("tech", ("tech", "computer", "electronics")),
        ("games", ("game", "gaming", "video game")),
        ("music", ("music", "mtv", "vh1")),
        ("sports", ("sports", "espn", "nascar", "football", "baseball", "basketball")),
        ("movies", ("movie", "cinema", "theater")),
    )
    for label, tokens in category_rules:
        if any(token in haystack for token in tokens):
            return label
    return ""


def build_commercial_root_signature(root_folder):
    root = os.path.abspath(os.path.expanduser(root_folder or ""))
    if not root or not os.path.isdir(root):
        return ""
    files = []
    for walk_root, dirnames, filenames in os.walk(root):
        dirnames.sort(key=str.casefold)
        for file_name in sorted(filenames, key=str.casefold):
            if not file_name.lower().endswith(VIDEO_EXTS):
                continue
            full_path = os.path.join(walk_root, file_name)
            try:
                stat = os.stat(full_path)
            except OSError:
                continue
            files.append(
                {
                    "path": os.path.relpath(full_path, root),
                    "mtime": int(stat.st_mtime),
                    "size": int(stat.st_size),
                }
            )
    return stable_hash(json.dumps({"root": root, "files": files}, sort_keys=True))


def density_ad_range(profile):
    density = str((profile or {}).get("density", "light") or "light").lower()
    if density == "custom":
        minimum = max(0, int((profile or {}).get("min_ads_per_break", 1) or 0))
        maximum = max(minimum, int((profile or {}).get("max_ads_per_break", minimum) or minimum))
        return minimum, maximum
    return COMMERCIAL_DENSITY_PRESETS.get(density, COMMERCIAL_DENSITY_PRESETS["light"])


def commercial_profile_signature(profile):
    return stable_hash(json.dumps(profile or {}, sort_keys=True))


def schedule_entry_user_title(entry, fallback_title="", fallback_path=""):
    entry = entry or {}
    if entry.get("is_commercial") or entry.get("kind") in {"commercial", "promo", "bumper", "station_id"}:
        return entry.get("parent_title") or entry.get("slot_title") or fallback_title or format_program_title(entry.get("parent_path") or fallback_path)
    return entry.get("display_title") or entry.get("title") or fallback_title or format_program_title(entry.get("path") or fallback_path)


def schedule_entry_user_summary(entry, fallback_summary=""):
    entry = entry or {}
    if entry.get("is_commercial") or entry.get("kind") in {"commercial", "promo", "bumper", "station_id"}:
        return entry.get("parent_summary") or fallback_summary
    return entry.get("summary") or fallback_summary


def schedule_entry_user_path(entry, fallback_path=""):
    entry = entry or {}
    if entry.get("is_commercial") or entry.get("kind") in {"commercial", "promo", "bumper", "station_id"}:
        return entry.get("parent_path") or fallback_path or entry.get("path", "")
    return entry.get("path", "") or fallback_path


def detect_smart_break_candidates_for_path(path):
    if not FFMPEG_PATH or not path:
        return []
    command = [
        FFMPEG_PATH,
        "-hide_banner",
        "-threads",
        "1",
        "-i",
        path,
        "-vf",
        "blackdetect=d=0.20:pix_th=0.98",
        "-af",
        "silencedetect=n=-35dB:d=0.25",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=90,
        )
        stderr = result.stderr or ""
    except (subprocess.SubprocessError, OSError):
        stderr = ""

    black_points = []
    silence_points = []
    for line in stderr.splitlines():
        black_match = re.search(r"black_start:(?P<start>[0-9.]+)\s+black_end:(?P<end>[0-9.]+)", line)
        if black_match:
            start = float(black_match.group("start"))
            end = float(black_match.group("end"))
            black_points.append(max(0.0, (start + end) / 2.0))
            continue
        silence_match = re.search(r"silence_start:\s*(?P<start>[0-9.]+)", line)
        if silence_match:
            silence_points.append(float(silence_match.group("start")))
    return sorted({round(point, 2) for point in (black_points + silence_points) if point >= 15.0})


def write_vault_debug_log(channel, message, fields=None):
    if not VAULT_DEBUG_LOGGING:
        return
    fields = fields or {}
    parts = [f"{key}={fields[key]!r}" for key in sorted(fields.keys())]
    line = f"[{channel}] {message}" + (f" | {'; '.join(parts)}" if parts else "")
    print(line)
    try:
        with open(VAULT_DEBUG_LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    except OSError:
        pass


def bool_label(value):
    return "On" if bool(value) else "Off"


def metadata_cache_entry_is_current(entry, signature):
    return isinstance(entry, dict) and entry.get("signature") == signature


def extract_year_value(*values):
    for value in values:
        text = (value or "").strip()
        match = re.search(r"(19|20)\d{2}", text)
        if match:
            return match.group(0)
    return ""


def radio_art_cache_path(path):
    return os.path.join(THUMBNAIL_DIR, f"{file_cache_signature(path)}_radio_art.jpg")


def local_music_title(path):
    return format_program_title(path)


def find_music_folder_art(path):
    directory = os.path.dirname(path)
    candidates = (
        "cover.jpg", "cover.jpeg", "cover.png",
        "folder.jpg", "folder.jpeg", "folder.png",
        "front.jpg", "front.jpeg", "front.png",
        "album.jpg", "album.jpeg", "album.png",
    )
    for folder in (directory, os.path.dirname(directory)):
        for name in candidates:
            candidate = os.path.join(folder, name)
            if os.path.isfile(candidate):
                return candidate
    return ""


def extract_embedded_music_art(path):
    cached = radio_art_cache_path(path)
    if os.path.exists(cached):
        return cached
    if not FFMPEG_PATH:
        return ""
    try:
        result = subprocess.run(
            [
                FFMPEG_PATH,
                "-y",
                "-i",
                path,
                "-an",
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-vf",
                "scale=420:-1",
                cached,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        if result.returncode == 0 and os.path.exists(cached):
            return cached
    except (subprocess.SubprocessError, OSError):
        return ""
    return ""


def probe_media_json(path):
    if not FFPROBE_PATH:
        return {}
    try:
        result = subprocess.run(
            [
                FFPROBE_PATH,
                "-v",
                "error",
                "-show_entries",
                "format=duration:format_tags=title,artist,album,album_artist,date,year,genre",
                "-show_entries",
                "stream=index,codec_type:stream_tags=title,artist,album,album_artist,date,year,genre",
                "-of",
                "json",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
        return json.loads(result.stdout.decode("utf-8") or "{}")
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def validate_video_media(path):
    signature = file_cache_signature(path)
    probe = probe_media_json(path)
    if not probe:
        return False, signature, "ffprobe could not read this file"

    format_info = probe.get("format", {}) if isinstance(probe, dict) else {}
    streams = probe.get("streams", []) if isinstance(probe, dict) else []
    duration = float(format_info.get("duration", 0) or 0)
    has_video = any(stream.get("codec_type") == "video" for stream in streams if isinstance(stream, dict))
    if duration <= 0:
        return False, signature, "media duration could not be read"
    if not has_video:
        return False, signature, "no playable video stream was found"

    if not FFMPEG_PATH:
        return True, signature, ""

    sample_seconds = min(12.0, max(4.0, duration * 0.12))
    try:
        result = subprocess.run(
            [
                FFMPEG_PATH,
                "-v",
                "error",
                "-xerror",
                "-ss",
                "0",
                "-i",
                path,
                "-t",
                f"{sample_seconds:.2f}",
                "-f",
                "null",
                "-",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=max(12, int(sample_seconds) + 10),
        )
        if result.returncode != 0:
            error_text = result.stderr.decode("utf-8", errors="ignore").strip()
            return False, signature, error_text or "ffmpeg decode test failed"
    except (subprocess.SubprocessError, OSError):
        return False, signature, "ffmpeg decode test failed"

    return True, signature, ""


def ensure_unique_destination(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    index = 2
    while True:
        candidate = f"{base} ({index}){ext}"
        if not os.path.exists(candidate):
            return candidate
        index += 1


def quarantine_broken_media(path, catalog_root):
    catalog_root = os.path.abspath(catalog_root)
    sibling_root = os.path.dirname(catalog_root.rstrip(os.sep))
    broken_root = os.path.join(sibling_root, "Broken")
    try:
        relative = os.path.relpath(path, catalog_root)
    except ValueError:
        relative = os.path.basename(path)
    destination = ensure_unique_destination(os.path.join(broken_root, relative))
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.move(path, destination)
    return destination


def parse_local_music_metadata(path, duration_cache, metadata_cache):
    signature = file_cache_signature(path)
    cached = metadata_cache.get(path)
    if metadata_cache_entry_is_current(cached, signature):
        duration = float(cached.get("duration", 0) or 0)
        if duration > 0:
            duration_cache[path] = duration
        return cached

    probe = probe_media_json(path)
    format_info = probe.get("format", {}) if isinstance(probe, dict) else {}
    streams = probe.get("streams", []) if isinstance(probe, dict) else []
    format_tags = format_info.get("tags", {}) if isinstance(format_info, dict) else {}
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    stream_tags = audio_stream.get("tags", {}) if isinstance(audio_stream, dict) else {}
    duration = float(format_info.get("duration", 0) or 0)
    title = (format_tags.get("title") or stream_tags.get("title") or local_music_title(path)).strip()
    artist = (
        format_tags.get("artist")
        or stream_tags.get("artist")
        or format_tags.get("album_artist")
        or stream_tags.get("album_artist")
        or ""
    ).strip()
    album = (format_tags.get("album") or stream_tags.get("album") or "").strip()
    genre = (format_tags.get("genre") or stream_tags.get("genre") or "").strip()
    year = extract_year_value(
        format_tags.get("date"),
        stream_tags.get("date"),
        format_tags.get("year"),
        stream_tags.get("year"),
    )
    art_path = find_music_folder_art(path) or extract_embedded_music_art(path)
    if duration > 0:
        duration_cache[path] = duration
    metadata = {
        "signature": signature,
        "duration": duration,
        "title": title or local_music_title(path),
        "artist": artist,
        "album": album,
        "genre": genre,
        "year": year,
        "art_path": art_path,
    }
    metadata_cache[path] = metadata
    return metadata


def radiowave_empty_metadata(folder="", reason=""):
    folder_label = os.path.basename((folder or "").rstrip(os.sep)) if folder else ""
    summary_bits = [RADIOWAVE_EMPTY_WARNING]
    if reason:
        summary_bits.append(reason)
    if folder_label:
        summary_bits.append(f"Folder: {folder_label}")
    summary = " ".join(summary_bits)
    return {
        "duration": RADIOWAVE_FALLBACK_DURATION_SECONDS,
        "title": "The music server has been depleted.",
        "artist": "DJ PlumCrazy",
        "album": "RadioWaveTV emergency broadcast",
        "genre": "Emergency Broadcast",
        "year": "",
        "art_path": "",
        "detail_title": "The music server has been depleted.",
        "detail_summary": summary,
        "show_name": "RadioWaveTV",
        "empty_state": True,
    }


def parse_timecode_to_seconds(text):
    text = (text or "").strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        values = [int(part) for part in parts]
    except ValueError:
        return None
    if len(values) == 2:
        return values[0] * 60 + values[1]
    if len(values) == 3:
        return values[0] * 3600 + values[1] * 60 + values[2]
    return None


def spotify_source_to_url(source):
    source = (source or "").strip()
    if not source:
        return ""
    if source.startswith("spotify:"):
        parts = source.split(":")
        if len(parts) >= 3 and parts[1] in {"playlist", "album"}:
            return f"https://open.spotify.com/embed/{parts[1]}/{parts[2]}?utm_source=generator&theme=0"
    parsed = urllib.parse.urlparse(source)
    if "open.spotify.com" in (parsed.netloc or ""):
        path = parsed.path.strip("/")
        chunks = path.split("/")
        if len(chunks) >= 2 and chunks[0] in {"playlist", "album"}:
            return f"https://open.spotify.com/embed/{chunks[0]}/{chunks[1]}?utm_source=generator&theme=0"
        if path.startswith("embed/"):
            return source
    return ""


def youtube_playlist_id(source):
    source = (source or "").strip()
    if not source:
        return ""
    parsed = urllib.parse.urlparse(source)
    query = urllib.parse.parse_qs(parsed.query or "")
    list_id = (query.get("list") or [""])[0].strip()
    if list_id:
        return list_id
    if parsed.netloc and "youtube" in parsed.netloc and "/playlist" in parsed.path:
        return ""
    if source.startswith("PL") or source.startswith("UU") or source.startswith("OLAK5uy_"):
        return source
    return ""


def youtube_playlist_embed_url(source):
    list_id = youtube_playlist_id(source)
    if not list_id:
        return ""
    params = urllib.parse.urlencode(
        {
            "list": list_id,
            "autoplay": "1",
            "mute": "0",
            "controls": "0",
            "loop": "1",
            "rel": "0",
            "modestbranding": "1",
            "playsinline": "1",
        }
    )
    return f"https://www.youtube.com/embed/videoseries?{params}"


def youtube_playlist_watch_url(source):
    list_id = youtube_playlist_id(source)
    if not list_id:
        return ""
    return f"https://www.youtube.com/playlist?list={urllib.parse.quote(list_id)}"


def youtube_source_url(source):
    source = (source or "").strip()
    if not source:
        return ""
    parsed = urllib.parse.urlparse(source)
    query = urllib.parse.parse_qs(parsed.query or "")
    video_id = (query.get("v") or [""])[0].strip()
    list_id = youtube_playlist_id(source)
    if parsed.scheme in {"http", "https"} and parsed.netloc and "youtube" in parsed.netloc:
        if video_id:
            if list_id:
                params = urllib.parse.urlencode({"v": video_id, "list": list_id})
                return f"https://www.youtube.com/watch?{params}"
            return youtube_video_url(video_id)
        if list_id:
            return youtube_playlist_watch_url(list_id)
        return source
    if parsed.scheme in {"http", "https"} and parsed.netloc and "youtu.be" in parsed.netloc:
        video_id = parsed.path.strip("/")
        return youtube_video_url(video_id)
    if list_id:
        return youtube_playlist_watch_url(list_id)
    return ""


def youtube_playlist_candidate_urls(source):
    source = (source or "").strip()
    candidates = []
    list_url = youtube_playlist_watch_url(source)
    source_url = youtube_source_url(source)
    for url in (list_url, source_url):
        if url and url not in candidates:
            candidates.append(url)
    return candidates


def youtube_playlist_cache_key(source):
    list_id = youtube_playlist_id(source)
    return list_id or stable_hash((source or "").strip())


def youtube_video_url(video_id):
    video_id = (video_id or "").strip()
    if not video_id:
        return ""
    if video_id.startswith("http://") or video_id.startswith("https://"):
        return video_id
    return f"https://www.youtube.com/watch?v={urllib.parse.quote(video_id)}"


def youtube_video_user_path(playlist_key, video_id, index=0):
    video_id = (video_id or "").strip() or f"item-{int(index) + 1}"
    return f"youtube://playlist/{playlist_key}/{video_id}"


def resolve_ytdlp_command():
    candidates = []
    binary = shutil.which("yt-dlp")
    if binary:
        candidates.append([binary])
    for path in ("/opt/homebrew/bin/yt-dlp", "/usr/local/bin/yt-dlp"):
        if path and os.path.exists(path):
            candidates.append([path])
    python_bin = sys.executable or ""
    if python_bin:
        candidates.append([python_bin, "-m", "yt_dlp"])
    seen = set()
    unique = []
    for command in candidates:
        key = tuple(command)
        if key in seen:
            continue
        seen.add(key)
        unique.append(command)
    for command in unique:
        try:
            result = subprocess.run(
                command + ["--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=4,
                text=True,
            )
            if result.returncode == 0:
                return command
        except Exception:
            continue
    return []


YTDLP_COMMAND = resolve_ytdlp_command()
YOUTUBE_CACHE_VERSION = "nettv-h264-v3"
YOUTUBE_DOWNLOAD_FORMAT = (
    "bestvideo[height<=1080][ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/"
    "bestvideo[height<=720][ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/"
    "best[height<=1080][ext=mp4][vcodec^=avc1][acodec!=none]/"
    "best[height<=720][ext=mp4][vcodec^=avc1][acodec!=none]/"
    "best[ext=mp4][vcodec^=avc1][acodec!=none]/"
    "best[ext=mp4][vcodec!=none][acodec!=none]/"
    "18"
)
YOUTUBE_PROGRESSIVE_DOWNLOAD_FORMAT = (
    "best[height<=720][ext=mp4][vcodec^=avc1][acodec!=none]/"
    "best[ext=mp4][vcodec^=avc1][acodec!=none]/"
    "best[height<=720][ext=mp4][vcodec!=none][acodec!=none]/"
    "best[ext=mp4][vcodec!=none][acodec!=none]/"
    "18"
)


def select_youtube_stream_url(info):
    if not isinstance(info, dict):
        return ""
    requested = info.get("requested_downloads") or []
    for item in requested:
        url = item.get("url") if isinstance(item, dict) else ""
        if url:
            return url
    direct = info.get("url")
    if direct:
        return direct

    formats = info.get("formats") or []
    playable = []
    for fmt in formats:
        if not isinstance(fmt, dict):
            continue
        url = fmt.get("url")
        if not url:
            continue
        vcodec = fmt.get("vcodec") or ""
        acodec = fmt.get("acodec") or ""
        if vcodec == "none" or acodec == "none":
            continue
        height = int(fmt.get("height") or 0)
        ext = (fmt.get("ext") or "").lower()
        score = 0
        if ext == "mp4":
            score += 100
        if height:
            score += min(height, 1080)
        if height and height <= 720:
            score += 40
        playable.append((score, url))
    if playable:
        playable.sort(key=lambda item: item[0], reverse=True)
        return playable[0][1]
    return ""


def normalize_youtube_playlist_entries(info, playlist_source):
    playlist_key = youtube_playlist_cache_key(playlist_source)
    entries = []
    raw_entries = (info or {}).get("entries") or []
    if not raw_entries and isinstance(info, dict) and (info.get("id") or info.get("webpage_url") or info.get("original_url")):
        raw_entries = [info]
    for index, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            continue
        video_id = (entry.get("id") or entry.get("url") or "").strip()
        url = entry.get("webpage_url") or entry.get("original_url") or entry.get("url") or youtube_video_url(video_id)
        if not url:
            continue
        if not str(url).startswith(("http://", "https://")):
            url = youtube_video_url(video_id or url)
        title = (entry.get("title") or f"NetTV Video {index + 1}").strip()
        duration = float(entry.get("duration") or 0)
        if duration <= 0:
            duration = 900.0
        entries.append(
            {
                "id": video_id or stable_hash(url),
                "url": url,
                "path": youtube_video_user_path(playlist_key, video_id or stable_hash(url), index),
                "title": title,
                "duration": max(30.0, duration),
                "thumbnail": entry.get("thumbnail") or "",
            }
        )
    return entries


def youtube_video_cache_key(entry):
    entry = entry or {}
    source = entry.get("id") or entry.get("url") or entry.get("path") or entry.get("title") or "youtube-video"
    return stable_hash(f"{YOUTUBE_CACHE_VERSION}|{source}")


def cached_youtube_video_path(entry):
    cache_key = youtube_video_cache_key(entry)
    for ext in (".mp4", ".mkv", ".webm", ".mov"):
        candidate = os.path.join(YOUTUBE_VIDEO_CACHE_DIR, f"{cache_key}{ext}")
        if os.path.isfile(candidate) and os.path.getsize(candidate) > 1024:
            return candidate
    return ""


def youtube_download_template(entry):
    cache_key = youtube_video_cache_key(entry)
    return os.path.join(YOUTUBE_VIDEO_CACHE_DIR, f"{cache_key}.%(ext)s")


def pixmap_has_visible_content(pixmap, threshold=10):
    """Return True when a frame looks like real picture, not a dead black frame.

    The older check only counted fairly bright pixels. That can falsely reject
    valid NetTV frames that start with dark fades, letterboxed intros, VHS noise,
    black title cards, or low-contrast video. This version still protects against
    silent black output, but it also accepts frames with enough contrast/detail.
    """
    if pixmap.isNull():
        return False
    image = pixmap.scaled(40, 24, Qt.IgnoreAspectRatio, Qt.FastTransformation).toImage()
    if image.isNull():
        return False

    lit_pixels = 0
    total = max(1, image.width() * image.height())
    min_luma = 255.0
    max_luma = 0.0
    luma_sum = 0.0

    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            luma = (color.red() * 0.2126) + (color.green() * 0.7152) + (color.blue() * 0.0722)
            min_luma = min(min_luma, luma)
            max_luma = max(max_luma, luma)
            luma_sum += luma
            if luma >= threshold:
                lit_pixels += 1

    average_luma = luma_sum / total
    contrast = max_luma - min_luma

    # Clear visible picture.
    if lit_pixels >= max(4, total // 80):
        return True

    # Very dark, but still has visible detail/variation.
    if contrast >= 18 and max_luma >= 22 and average_luma >= 3:
        return True

    return False


def draw_nettv_standby_scene(painter, rect, title="", message="", marquee_offset=0):
    if rect is None or rect.isEmpty():
        return

    title = (title or "NetTV").strip()
    message = (message or "Preparing your playlist feed...").strip()

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, False)
    band_h = max(36, rect.height() // 12)
    top_band = QRect(rect.left(), rect.top(), rect.width(), band_h)
    bottom_band = QRect(rect.left(), rect.bottom() - band_h + 1, rect.width(), band_h)
    bars_rect = rect.adjusted(0, band_h, 0, -band_h)
    painter.fillRect(rect, QColor(0, 0, 0))

    top_colors = (
        QColor(95, 95, 95),
        QColor(190, 190, 190),
        QColor(190, 194, 30),
        QColor(16, 184, 184),
        QColor(0, 188, 48),
        QColor(190, 0, 188),
        QColor(202, 0, 20),
        QColor(34, 0, 178),
        QColor(95, 95, 95),
    )
    top_h = int(bars_rect.height() * 0.68)
    color_top = QRect(bars_rect.left(), bars_rect.top(), bars_rect.width(), top_h)
    bar_w = max(1, color_top.width() // len(top_colors))
    for index, color in enumerate(top_colors):
        x = color_top.left() + index * bar_w
        right = color_top.right() if index == len(top_colors) - 1 else x + bar_w
        painter.fillRect(QRect(x, color_top.top(), right - x + 1, color_top.height()), color)

    lower_rect = QRect(bars_rect.left(), color_top.bottom() + 1, bars_rect.width(), bars_rect.bottom() - color_top.bottom())
    lower_colors = (
        QColor(0, 220, 226),
        QColor(8, 38, 80),
        QColor(252, 255, 28),
        QColor(58, 0, 96),
        QColor(32, 32, 32),
        QColor(82, 82, 82),
        QColor(134, 134, 134),
        QColor(196, 196, 196),
        QColor(245, 245, 245),
        QColor(245, 0, 0),
        QColor(38, 0, 225),
    )
    lower_w = max(1, lower_rect.width() // len(lower_colors))
    for index, color in enumerate(lower_colors):
        x = lower_rect.left() + index * lower_w
        right = lower_rect.right() if index == len(lower_colors) - 1 else x + lower_w
        painter.fillRect(QRect(x, lower_rect.top(), right - x + 1, lower_rect.height()), color)

    painter.fillRect(bars_rect, QColor(0, 0, 0, 38))
    painter.fillRect(top_band, QColor(0, 0, 0))
    painter.fillRect(bottom_band, QColor(0, 0, 0))

    for y in range(bars_rect.top(), bars_rect.bottom(), 4):
        alpha = 30 if ((y // 4) % 2) else 14
        painter.fillRect(QRect(rect.left(), y, rect.width(), 1), QColor(255, 255, 255, alpha))

    panel_w = min(int(rect.width() * 0.74), rect.width() - 64)
    panel_h = min(int(rect.height() * 0.58), rect.height() - (band_h * 2) - 36)
    panel = QRect(
        rect.left() + (rect.width() - panel_w) // 2,
        rect.top() + band_h + (rect.height() - (band_h * 2) - panel_h) // 2,
        panel_w,
        panel_h,
    )
    painter.fillRect(panel, QColor(94, 94, 94, 236))
    painter.setPen(QPen(QColor(24, 24, 24), max(2, rect.width() // 640)))
    painter.drawRect(panel.adjusted(0, 0, -1, -1))

    headline_font = QFont(crt_font_family(), max(22, rect.height() // 16), QFont.Bold)
    headline_font.setStyleHint(QFont.TypeWriter)
    body_font = QFont(crt_font_family(), max(14, rect.height() // 28), QFont.Bold)
    small_font = QFont(crt_font_family(), max(10, rect.height() // 44), QFont.Bold)
    for font in (body_font, small_font):
        font.setStyleHint(QFont.TypeWriter)

    painter.setFont(headline_font)
    headline = "MEDIAWAVE NETTV NOTICE"
    headline_rect = QRect(panel.left() + 20, panel.top() + 24, panel.width() - 40, max(44, panel.height() // 5))
    painter.setPen(QColor(28, 28, 28))
    painter.drawText(headline_rect.translated(3, 3), Qt.AlignCenter | Qt.TextWordWrap, headline)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(headline_rect, Qt.AlignCenter | Qt.TextWordWrap, headline)

    painter.setFont(body_font)
    painter.setPen(QColor(250, 250, 250))
    painter.drawText(
        QRect(panel.left() + 28, panel.top() + int(panel.height() * 0.32), panel.width() - 56, max(44, panel.height() // 5)),
        Qt.AlignCenter | Qt.TextWordWrap,
        "PLEASE STAND BY",
    )
    painter.setFont(small_font)
    painter.setPen(QColor(245, 245, 245))
    info_lines = [
        f"CHANNEL: NETTV",
        f"PROGRAM: {title}",
        f"STATUS: {message}",
    ]
    painter.drawText(
        QRect(panel.left() + 36, panel.top() + int(panel.height() * 0.56), panel.width() - 72, int(panel.height() * 0.34)),
        Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
        "\n".join(info_lines),
    )

    painter.setPen(QColor(255, 255, 255))
    painter.setFont(small_font)
    now_text = time.strftime("%-I:%M %p") if sys.platform == "darwin" else time.strftime("%I:%M %p").lstrip("0")
    painter.drawText(top_band.adjusted(18, 0, -18, 0), Qt.AlignLeft | Qt.AlignVCenter, "NETTV SIGNAL ACQUISITION")
    painter.drawText(top_band.adjusted(18, 0, -18, 0), Qt.AlignRight | Qt.AlignVCenter, now_text)
    painter.drawText(bottom_band.adjusted(18, 0, -18, 0), Qt.AlignRight | Qt.AlignVCenter, APP_NAME.upper())
    painter.restore()


def make_nettv_standby_pixmap(size, title="", message="Preparing your playlist feed..."):
    width = max(1, size.width())
    height = max(1, size.height())
    pixmap = QPixmap(width, height)
    painter = QPainter(pixmap)
    draw_nettv_standby_scene(painter, pixmap.rect(), title, message, 0)
    painter.end()
    return pixmap


def spotify_source_label(source):
    return "RadioWaveTV"


def lyrics_cache_key(artist, title):
    return stable_hash(f"{normalize_title(artist)}::{normalize_title(title)}")


def fetch_remote_lyrics(artist, title):
    artist = (artist or "").strip()
    title = (title or "").strip()
    if not artist or not title:
        return []
    url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(artist)}/{urllib.parse.quote(title)}"
    try:
        with urllib.request.urlopen(url, timeout=2.5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return []
    lyrics = (data.get("lyrics") or "").replace("\r", "")
    lines = [line.strip() for line in lyrics.split("\n") if line.strip()]
    return lines[:40]


def fetch_track_metadata_fallback(artist, title):
    artist = (artist or "").strip()
    title = (title or "").strip()
    if not title:
        return {}
    query = urllib.parse.quote(" ".join(part for part in (artist, title) if part))
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
    try:
        with urllib.request.urlopen(url, timeout=3.0) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return {}
    results = (data or {}).get("results") or []
    if not results:
        return {}
    item = results[0]
    album = (item.get("collectionName") or "").strip()
    art_url = (item.get("artworkUrl100") or item.get("artworkUrl60") or "").strip()
    if art_url:
        art_url = art_url.replace("100x100bb", "600x600bb")
    release_date = (item.get("releaseDate") or "").strip()
    year_match = re.search(r"(19|20)\d{2}", release_date)
    year = year_match.group(0) if year_match else ""
    return {
        "artist": (item.get("artistName") or "").strip(),
        "album": album,
        "art_url": art_url,
        "year": year,
    }


def load_brand_logo(max_width=0, max_height=0, path=None):
    logo_path = path or APP_LOGO_PATH
    cache_key = (logo_path, max_width, max_height)
    if cache_key in _LOGO_CACHE:
        return _LOGO_CACHE[cache_key]
    pixmap = QPixmap(logo_path)
    if pixmap.isNull():
        return QPixmap()
    image = pixmap.toImage()
    bounds = None
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() > 0:
                if bounds is None:
                    bounds = [x, y, x, y]
                else:
                    bounds[0] = min(bounds[0], x)
                    bounds[1] = min(bounds[1], y)
                    bounds[2] = max(bounds[2], x)
                    bounds[3] = max(bounds[3], y)
    if bounds:
        pixmap = pixmap.copy(QRect(bounds[0], bounds[1], bounds[2] - bounds[0] + 1, bounds[3] - bounds[1] + 1))
    if max_width > 0 and max_height > 0:
        pixmap = pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    _LOGO_CACHE[cache_key] = pixmap
    return pixmap


def ordinal_suffix(day):
    if 10 <= (day % 100) <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def format_long_date(timestamp=None):
    ts = time.localtime(timestamp or time.time())
    day = ts.tm_mday
    return time.strftime("%B ", ts) + f"{day}{ordinal_suffix(day)}" + time.strftime(", %Y", ts)


def clock_font_family():
    global _CLOCK_FONT_FAMILY
    if _CLOCK_FONT_FAMILY:
        return _CLOCK_FONT_FAMILY
    font_id = QFontDatabase.addApplicationFont(CLOCK_FONT_PATH)
    if font_id >= 0:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            _CLOCK_FONT_FAMILY = families[0]
            return _CLOCK_FONT_FAMILY
    _CLOCK_FONT_FAMILY = "Courier New"
    return _CLOCK_FONT_FAMILY


def crt_font_family():
    global _CRT_FONT_FAMILY
    if _CRT_FONT_FAMILY:
        return _CRT_FONT_FAMILY
    font_id = QFontDatabase.addApplicationFont(CRT_FONT_PATH)
    if font_id >= 0:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            _CRT_FONT_FAMILY = families[0]
            return _CRT_FONT_FAMILY
    _CRT_FONT_FAMILY = "Courier New"
    return _CRT_FONT_FAMILY


def vhs_osd_font_family():
    global _VHS_OSD_FONT_FAMILY
    if _VHS_OSD_FONT_FAMILY:
        return _VHS_OSD_FONT_FAMILY
    loaded = load_local_font_family(VHS_OSD_FONT_PATH)
    if loaded:
        _VHS_OSD_FONT_FAMILY = loaded
        return _VHS_OSD_FONT_FAMILY
    _VHS_OSD_FONT_FAMILY = crt_font_family()
    return _VHS_OSD_FONT_FAMILY


def load_local_font_family(path):
    if os.path.exists(path):
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
    return None


def guide_font_family(weight="primary"):
    global _GUIDE_FONT_FAMILY, _GUIDE_FONT_FAMILY_SECONDARY
    if weight == "secondary" and _GUIDE_FONT_FAMILY_SECONDARY:
        return _GUIDE_FONT_FAMILY_SECONDARY
    if weight == "primary" and _GUIDE_FONT_FAMILY:
        return _GUIDE_FONT_FAMILY

    preferred_local = CLASSIC_CABLE_TUNING["font_paths"]["secondary" if weight == "secondary" else "primary"]
    loaded = load_local_font_family(preferred_local)
    if loaded:
        if weight == "secondary":
            _GUIDE_FONT_FAMILY_SECONDARY = loaded
        else:
            _GUIDE_FONT_FAMILY = loaded
        return loaded

    families = set(QFontDatabase().families())
    preferred = [
        "Arial Narrow",
        "Helvetica Neue Condensed Bold",
        "HelveticaNeue-CondensedBold",
        "Nimbus Sans Narrow",
        "Liberation Sans Narrow",
        "Arial",
        "Helvetica",
    ]
    for family in preferred:
        if family in families:
            if weight == "secondary":
                _GUIDE_FONT_FAMILY_SECONDARY = family
                return _GUIDE_FONT_FAMILY_SECONDARY
            _GUIDE_FONT_FAMILY = family
            return _GUIDE_FONT_FAMILY
    if weight == "secondary":
        _GUIDE_FONT_FAMILY_SECONDARY = "Arial"
        return _GUIDE_FONT_FAMILY_SECONDARY
    _GUIDE_FONT_FAMILY = "Arial"
    return _GUIDE_FONT_FAMILY


def cutietop_font_family():
    global _CUTIETOP_FONT_FAMILY
    if _CUTIETOP_FONT_FAMILY:
        return _CUTIETOP_FONT_FAMILY
    loaded = load_local_font_family(CUTIETOP_FONT_PATH)
    _CUTIETOP_FONT_FAMILY = loaded or guide_font_family("primary")
    return _CUTIETOP_FONT_FAMILY


def videophreak_font_family():
    global _VIDEOPHREAK_FONT_FAMILY
    if _VIDEOPHREAK_FONT_FAMILY:
        return _VIDEOPHREAK_FONT_FAMILY
    loaded = load_local_font_family(VIDEOPHREAK_FONT_PATH)
    _VIDEOPHREAK_FONT_FAMILY = loaded or guide_font_family("secondary")
    return _VIDEOPHREAK_FONT_FAMILY


def scifi2ki_font_family():
    global _SCIFI2KI_FONT_FAMILY
    if _SCIFI2KI_FONT_FAMILY:
        return _SCIFI2KI_FONT_FAMILY
    loaded = load_local_font_family(SCIFI2KI_FONT_PATH)
    _SCIFI2KI_FONT_FAMILY = loaded or guide_font_family("secondary")
    return _SCIFI2KI_FONT_FAMILY


def format_clock_range(start_ts, end_ts):
    return (
        f"{time.strftime('%I:%M', time.localtime(start_ts)).lstrip('0')} - "
        f"{time.strftime('%I:%M', time.localtime(end_ts)).lstrip('0')}"
    )


def format_resume_time(position_ms):
    total_seconds = max(0, int(position_ms / 1000))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_countdown_time(position_ms):
    total_seconds = max(0, int(round(position_ms / 1000.0)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_eta_seconds(seconds):
    seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def compact_status_detail(text, max_length=90):
    value = (text or "").strip()
    if len(value) <= max_length:
        return value
    basename = os.path.basename(value)
    if basename and len(basename) < (max_length - 8):
        head = max(12, max_length - len(basename) - 5)
        return f"{value[:head]}.../{basename}"
    keep = max(10, (max_length - 3) // 2)
    return f"{value[:keep]}...{value[-keep:]}"


def stable_hash(value):
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def build_channel_signature(channel_name, file_paths):
    payload = json.dumps(
        {
            "channel": channel_name,
            "files": sorted(file_paths),
        },
        sort_keys=True,
    )
    return stable_hash(payload)


def auto_schedule_anchor():
    # Lock the synthetic "broadcast day" to a stable boundary so schedules
    # keep their place even after the app is closed and reopened later.
    now = int(time.time())
    half_hour = 30 * 60
    return now - (now % half_hour)


def generate_auto_schedule(root_path, channel_name, file_paths):
    seeded = random.Random(stable_hash(f"{root_path}|{channel_name}"))
    ordered = list(file_paths)
    seeded.shuffle(ordered)
    return {
        "mode": "auto",
        "anchor_time": auto_schedule_anchor(),
        "lineup": ordered,
    }


def normalize_title(value):
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def clean_local_title_piece(value):
    return re.sub(r"\s+", " ", str(value or "").strip().strip("-_–—:| ")).strip()


def unique_existing_dirs(paths):
    seen = set()
    results = []
    for path in paths:
        resolved = os.path.abspath(path or "")
        if not resolved or resolved in seen or not os.path.isdir(resolved):
            continue
        seen.add(resolved)
        results.append(resolved)
    return results


def local_asset_directories(path, local):
    parent_dir = os.path.dirname(path)
    grandparent_dir = os.path.dirname(parent_dir)
    parent_name = os.path.basename(parent_dir)
    if local.get("media_type") == "tv":
        if (
            re.search(r"\bseason\s*\d{1,2}\b", parent_name, re.IGNORECASE)
            or re.search(r"\b(specials?|extras?|bonus|ova|movies?)\b", parent_name, re.IGNORECASE)
        ):
            return unique_existing_dirs([grandparent_dir, parent_dir])
        return unique_existing_dirs([parent_dir, grandparent_dir])
    return unique_existing_dirs([parent_dir])


def find_named_asset(directories, names):
    wanted = {name.casefold(): name for name in names}
    for directory in directories:
        for name in names:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
        try:
            entries = os.listdir(directory)
        except OSError:
            continue
        by_name = {entry.casefold(): entry for entry in entries}
        for wanted_name in wanted:
            entry = by_name.get(wanted_name)
            if not entry:
                continue
            candidate = os.path.join(directory, entry)
            if os.path.isfile(candidate):
                return candidate
    return ""


def load_local_description_file(path):
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def discover_local_media_assets(path, local):
    directories = local_asset_directories(path, local)
    poster_path = find_named_asset(directories, LOCAL_POSTER_NAMES)
    fanart_path = find_named_asset(directories, LOCAL_FANART_NAMES)
    clearlogo_path = find_named_asset(directories, LOCAL_CLEARLOGO_NAMES)
    description_path = find_named_asset(directories, LOCAL_DESCRIPTION_NAMES)
    return {
        "directories": directories,
        "poster_path": poster_path,
        "fanart_path": fanart_path,
        "clearlogo_path": clearlogo_path,
        "description_path": description_path,
        "description": load_local_description_file(description_path),
    }


def local_asset_signature(path, local):
    assets = discover_local_media_assets(path, local)
    parts = [file_cache_signature(path)]
    for directory in assets.get("directories", []):
        try:
            stat = os.stat(directory)
            parts.append(f"dir:{directory}:{int(stat.st_mtime)}")
        except OSError:
            continue
    for key in ("poster_path", "fanart_path", "clearlogo_path", "description_path"):
        candidate = assets.get(key, "")
        if candidate:
            parts.append(file_cache_signature(candidate))
    return stable_hash("|".join(parts))


def build_local_media_metadata(path, duration=None):
    local = parse_local_media(path)
    assets = discover_local_media_assets(path, local)
    signature = local_asset_signature(path, local)
    lookup_key = metadata_lookup_key(path, local)
    description = shorten_summary(assets.get("description", ""), 520)
    has_local_assets = any(
        assets.get(key)
        for key in ("poster_path", "fanart_path", "clearlogo_path", "description_path")
    )
    poster_path = assets.get("poster_path") or ""
    fanart_path = assets.get("fanart_path") or ""
    logo_path = assets.get("clearlogo_path") or ""
    detail_summary = description if local["media_type"] == "movie" else ""
    metadata = {
        "signature": signature,
        "path": path,
        "title": local["timeline_title"],
        "media_type": local["media_type"],
        "timeline_title": local["timeline_title"],
        "detail_title": local["detail_title"],
        "detail_summary": detail_summary,
        "description": description,
        "summary": description,
        "show_name": local["show_name"],
        "match_key": local["match_key"],
        "lookup_key": lookup_key,
        "season_number": local.get("season_number"),
        "season_label": local.get("season_label", ""),
        "episode_number": local.get("episode_number"),
        "episode_title": local.get("episode_title"),
        "episode_summary": "",
        "show_summary": description,
        "runtime_minutes": None,
        "duration": duration,
        "year": extract_year_value(local.get("show_name", ""), local.get("timeline_title", "")),
        "poster_path": poster_path,
        "fanart_path": fanart_path,
        "logo_path": logo_path,
        "artwork_path": poster_path or fanart_path,
        "show_artwork_path": poster_path or fanart_path,
        "hero_artwork_path": fanart_path or poster_path,
        "clearlogo_path": logo_path,
        "metadata_status": "local" if has_local_assets else "fallback",
        "metadata_source": "local" if has_local_assets else "fallback",
        "source": "local" if has_local_assets else "fallback",
        "needs_attention": False,
        "attention_reason": "",
        "review_candidates": [],
        "tmdb_matched": False,
        "cache_mode": "local-assets-v2",
        "enrichment_source": "local-assets" if has_local_assets else "fallback-names",
    }
    return metadata


def parse_local_media(path):
    base = format_program_title(path)
    patterns = [
        r"^(?P<show>.+?)\s*-\s*(?P<season>\d{1,2})[xX](?P<episode>\d{1,3})\s*-\s*(?P<title>.+)$",
        r"^(?P<show>.+?)\s+[Ss](?P<season>\d{1,2})[Ee](?P<episode>\d{1,3})\s*[- ]\s*(?P<title>.+)$",
        r"^(?P<show>.+?)\s*-\s*[Ss](?P<season>\d{1,2})[Ee](?P<episode>\d{1,3})\s*-\s*(?P<title>.+)$",
        r"^(?P<show>.+?)\s*-\s*(?:episode|ep)\s*(?P<episode>\d{1,3})\s*[-: ]+\s*(?P<title>.+)$",
        r"^(?P<show>.+?)\s*-\s*(?P<episode>\d{1,3})\s*-\s*(?P<title>.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, base)
        if match:
            show = clean_local_title_piece(match.group("show"))
            title = clean_local_title_piece(match.group("title"))
            season = int(match.group("season")) if match.groupdict().get("season") else 1
            episode = int(match.group("episode"))
            return {
                "media_type": "tv",
                "show_name": show,
                "timeline_title": show,
                "detail_title": f"{show} - S{season:02d}E{episode:02d} - {title}",
                "detail_summary": "",
                "season_number": season,
                "season_label": f"Season {season}",
                "episode_number": episode,
                "episode_title": title,
                "match_key": normalize_title(show),
            }

    parent = os.path.basename(os.path.dirname(path))
    grandparent = os.path.basename(os.path.dirname(os.path.dirname(path)))
    parent_title = format_program_title(parent) if parent else ""
    grandparent_title = format_program_title(grandparent) if grandparent else ""
    fallback_title = clean_local_title_piece(base)
    season_number = None
    season_source = parent_title
    season_match = re.search(r"\bseason\s*(\d{1,2})\b", parent_title, re.IGNORECASE)
    if not season_match and grandparent_title:
        season_match = re.search(r"\bseason\s*(\d{1,2})\b", grandparent_title, re.IGNORECASE)
        season_source = grandparent_title
    if season_match:
        season_number = int(season_match.group(1))

    if grandparent_title and re.search(r"\b(specials?|extras?|bonus|ova)\b", parent_title, re.IGNORECASE):
        special_match = re.match(
            r"^(?:(?:special|episode|ep)\s*)?(?P<episode>\d{1,3})\s*[-._ ]+\s*(?P<title>.+)$",
            fallback_title,
            re.IGNORECASE,
        )
        episode_number = int(special_match.group("episode")) if special_match else None
        episode_title = clean_local_title_piece((special_match.groupdict().get("title") if special_match else "") or fallback_title)
        return {
            "media_type": "tv",
            "show_name": grandparent_title,
            "timeline_title": grandparent_title,
            "detail_title": f"{grandparent_title} - Specials - {episode_title}",
            "detail_summary": "",
            "season_number": 0,
            "season_label": "Specials",
            "episode_number": episode_number,
            "episode_title": episode_title,
            "match_key": normalize_title(grandparent_title),
        }

    inferred_show = grandparent_title if season_number is not None and season_source == parent_title and grandparent_title else parent_title
    if season_number is not None and season_source == grandparent_title and parent_title:
        inferred_show = parent_title

    inferred_patterns = [
        r"^(?P<episode>\d{1,3})\s*[-._ ]+\s*(?P<title>.+)$",
        r"^(?:episode|ep)\s*(?P<episode>\d{1,3})\s*[-._ ]+\s*(?P<title>.+)$",
        r"^(?P<episode>\d{1,3})$",
    ]
    if inferred_show:
        for pattern in inferred_patterns:
            match = re.match(pattern, fallback_title, re.IGNORECASE)
            if not match:
                continue
            episode = int(match.group("episode"))
            title = clean_local_title_piece(match.groupdict().get("title") or f"Episode {episode}")
            season = season_number if season_number is not None else 1
            return {
                "media_type": "tv",
                "show_name": inferred_show,
                "timeline_title": inferred_show,
                "detail_title": f"{inferred_show} - S{season:02d}E{episode:02d} - {title}",
                "detail_summary": "",
                "season_number": season,
                "season_label": f"Season {season}",
                "episode_number": episode,
                "episode_title": title,
                "match_key": normalize_title(inferred_show),
            }

    show_name = parent_title if parent_title and parent_title.lower() not in fallback_title.lower() else fallback_title
    return {
        "media_type": "movie",
        "show_name": show_name,
        "timeline_title": fallback_title,
        "detail_title": fallback_title,
        "detail_summary": "",
        "match_key": normalize_title(show_name or fallback_title),
    }


def infer_on_demand_structure(path, channel_root):
    root = os.path.realpath(channel_root or "")
    full_path = os.path.realpath(path or "")
    if not root or not full_path:
        return {}
    try:
        relative = os.path.relpath(full_path, root)
    except ValueError:
        return {}
    if relative.startswith(".."):
        return {}
    parts = [part for part in relative.split(os.sep) if part and part != "."]
    if len(parts) < 2:
        return {}
    show_folder = format_program_title(parts[0])
    subsection_folder = format_program_title(parts[1]) if len(parts) >= 3 else ""
    return {
        "group_label": show_folder,
        "section_label": subsection_folder,
    }


def metadata_lookup_key(path, local):
    if local.get("media_type") == "tv":
        return f"tv::{local.get('match_key', normalize_title(local.get('show_name', '')))}"
    return f"movie::{stable_hash(path)}"


def strip_html_summary(value):
    text = re.sub(r"<br\s*/?>", " ", value or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def shorten_summary(value, max_length=190):
    text = (value or "").strip()
    if len(text) <= max_length:
        return text
    clipped = text[: max_length - 1].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return f"{clipped}..."


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def cache_remote_artwork(url, cache_key):
    cleaned_url = (url or "").strip()
    if not cleaned_url:
        return ""
    ext = os.path.splitext(urllib.parse.urlparse(cleaned_url).path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    destination = os.path.join(METADATA_ARTWORK_DIR, f"{stable_hash(cache_key)}{ext}")
    if os.path.isfile(destination):
        return destination
    try:
        request = urllib.request.Request(
            cleaned_url,
            headers={"User-Agent": f"{APP_NAME}/1.0"},
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            data = response.read()
        if not data:
            return ""
        with open(destination, "wb") as handle:
            handle.write(data)
        return destination
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return ""


def load_ui_pixmap(path):
    resolved = (path or "").strip()
    if not resolved or not os.path.isfile(resolved):
        return QPixmap()
    cached = _UI_PIXMAP_CACHE.get(resolved)
    if cached is not None and not cached.isNull():
        return cached
    pixmap = QPixmap(resolved)
    if pixmap.isNull():
        return QPixmap()
    _UI_PIXMAP_CACHE[resolved] = pixmap
    return pixmap


def file_cache_signature(path):
    try:
        stat = os.stat(path)
        return stable_hash(f"{path}|{int(stat.st_mtime)}|{stat.st_size}")
    except OSError:
        return stable_hash(path)


def resolve_ffprobe_path():
    candidates = [
        shutil.which("ffprobe"),
        "/opt/homebrew/bin/ffprobe",
        "/usr/local/bin/ffprobe",
        "/usr/bin/ffprobe",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


FFPROBE_PATH = resolve_ffprobe_path()


def resolve_ffmpeg_path():
    candidates = [
        shutil.which("ffmpeg"),
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


FFMPEG_PATH = resolve_ffmpeg_path()


def load_tmdb_token():
    config = load_json_file(TMDB_CONFIG_FILE, {})
    return (
        os.environ.get("TMDB_READ_ACCESS_TOKEN")
        or config.get("read_access_token")
        or ""
    ).strip()


def save_tmdb_token(token):
    config = load_json_file(TMDB_CONFIG_FILE, {})
    cleaned = (token or "").strip()
    if cleaned:
        config["read_access_token"] = cleaned
    else:
        config.pop("read_access_token", None)
    save_json_file(TMDB_CONFIG_FILE, config)


class TMDBClient:
    def __init__(self, token):
        self.token = token
        self.response_cache = {}

    @property
    def enabled(self):
        return bool(self.token)

    def request_json(self, path, params=None):
        if not self.enabled:
            return None
        params = params or {}
        cache_key = (path, tuple(sorted(params.items())))
        if cache_key in self.response_cache:
            return self.response_cache[cache_key]
        query = urllib.parse.urlencode(params)
        url = f"https://api.themoviedb.org/3{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=METADATA_REQUEST_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
                self.response_cache[cache_key] = data
                return data
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
            self.response_cache[cache_key] = None
            return None

    def search_tv(self, query):
        return self.request_json("/search/tv", {"query": query}) or {}

    def search_movie(self, query):
        return self.request_json("/search/movie", {"query": query}) or {}

    def tv_episode_details(self, series_id, season_number, episode_number):
        return self.request_json(f"/tv/{series_id}/season/{season_number}/episode/{episode_number}") or {}

    def movie_details(self, movie_id):
        return self.request_json(f"/movie/{movie_id}") or {}


class TVMazeClient:
    def __init__(self):
        self.episodes_cache = {}
        self.search_cache = {}
        self.response_cache = {}

    @property
    def enabled(self):
        return True

    def request_json(self, url):
        if url in self.response_cache:
            return self.response_cache[url]
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"{APP_NAME}/1.0",
                "accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=METADATA_REQUEST_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
                self.response_cache[url] = data
                return data
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, ValueError):
            self.response_cache[url] = None
            return None

    def search_shows(self, query):
        cleaned = (query or "").strip()
        if not cleaned:
            return []
        cache_key = normalize_title(cleaned)
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]
        url = f"https://api.tvmaze.com/search/shows?q={urllib.parse.quote(cleaned)}"
        results = self.request_json(url) or []
        self.search_cache[cache_key] = results
        return results

    def show_episodes(self, show_id):
        if show_id in self.episodes_cache:
            return self.episodes_cache[show_id]
        url = f"https://api.tvmaze.com/shows/{show_id}/episodes?specials=1"
        episodes = self.request_json(url) or []
        self.episodes_cache[show_id] = episodes
        return episodes


class AniListClient:
    def __init__(self):
        self.endpoint = "https://graphql.anilist.co"
        self.response_cache = {}
        self.search_cache = {}

    @property
    def enabled(self):
        return True

    def request_json(self, query, variables=None):
        cache_key = (query, json.dumps(variables or {}, sort_keys=True))
        if cache_key in self.response_cache:
            return self.response_cache[cache_key]
        payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "User-Agent": f"{APP_NAME}/1.0",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=METADATA_REQUEST_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
                self.response_cache[cache_key] = data
                return data
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, ValueError):
            self.response_cache[cache_key] = None
            return None

    def search_anime(self, query):
        cleaned = (query or "").strip()
        if not cleaned:
            return []
        cache_key = normalize_title(cleaned)
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]
        graphql = """
        query ($search: String) {
          Page(perPage: 8) {
            media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
              id
              episodes
              duration
              description(asHtml: false)
              format
              startDate { year }
              coverImage { extraLarge large medium }
              title { romaji english native userPreferred }
            }
          }
        }
        """
        response = self.request_json(graphql, {"search": cleaned}) or {}
        results = (((response.get("data") or {}).get("Page") or {}).get("media")) or []
        self.search_cache[cache_key] = results
        return results

    def media_details(self, media_id):
        if not media_id:
            return None
        graphql = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
            episodes
            duration
            description(asHtml: false)
            format
            startDate { year }
            coverImage { extraLarge large medium }
            title { romaji english native userPreferred }
          }
        }
        """
        response = self.request_json(graphql, {"id": int(media_id)}) or {}
        return ((response.get("data") or {}).get("Media")) or None


def anilist_display_title(item):
    title_data = (item or {}).get("title") or {}
    return (
        title_data.get("english")
        or title_data.get("userPreferred")
        or title_data.get("romaji")
        or title_data.get("native")
        or ""
    ).strip()


GUIDE_PROFILES = {
    "Auto": {"scale": 1.0, "preview_ratio": 0.33, "row_density": 1.0, "target_aspect": None},
    "CRT 4:3": {"scale": 0.92, "preview_ratio": 0.28, "row_density": 0.9, "target_aspect": 4 / 3},
    "Widescreen": {"scale": 1.0, "preview_ratio": 0.34, "row_density": 1.0, "target_aspect": 16 / 9},
    "4K Large": {"scale": 1.22, "preview_ratio": 0.36, "row_density": 1.18, "target_aspect": 16 / 9},
}

DEFAULT_SKIN_NAME = "Promised Future"
DEFAULT_THEME_NAME = "Silver Olive"

GUIDE_SKINS = {
    "Promised Future": {"style": "aero"},
    "Set Top Box": {"style": "cable"},
    "Sleek Freak": {"style": "flat"},
}

SKIN_NAME_ALIASES = {
    "Frutiger Aero": "Promised Future",
    "Classic Cable": "Set Top Box",
    "Modern": "Sleek Freak",
    "Modern Flat": "Sleek Freak",
}

THEME_NAME_ALIASES = {
    "Purple": "Purple Passion",
    "Purple Haze": "Purple Passion",
    "Orange": "Tangerine Dream",
    "Clementine": "Tangerine Dream",
    "Slate Modern": "Millennial Grey",
    "Signal Modern": "Baby Blue",
}

GUIDE_THEME_DEFINITIONS = {
    "Promised Future": {
        "Silver Olive": {
            "bg": QColor(76, 82, 72, 228),
            "panel": QColor(200, 202, 190, 218),
            "header": QColor(124, 140, 108, 240),
            "row_a": QColor(144, 158, 120, 214),
            "row_b": QColor(104, 120, 92, 214),
            "selected": QColor(246, 226, 132, 236),
            "text": QColor(250, 252, 244),
            "dark_text": QColor(36, 42, 30),
            "muted": QColor(230, 234, 218),
            "chrome_top": QColor(244, 244, 236, 240),
            "chrome_mid": QColor(198, 202, 184, 228),
            "chrome_bottom": QColor(118, 132, 102, 226),
            "glass": QColor(255, 255, 255, 56),
        },
        "Silver": {
            "bg": QColor(78, 82, 86, 228),
            "panel": QColor(216, 218, 218, 218),
            "header": QColor(142, 154, 166, 240),
            "row_a": QColor(152, 166, 178, 214),
            "row_b": QColor(116, 132, 146, 214),
            "selected": QColor(244, 226, 136, 236),
            "text": QColor(250, 252, 254),
            "dark_text": QColor(34, 40, 46),
            "muted": QColor(232, 236, 238),
            "chrome_top": QColor(252, 252, 250, 240),
            "chrome_mid": QColor(218, 222, 222, 228),
            "chrome_bottom": QColor(142, 154, 164, 226),
            "glass": QColor(255, 255, 255, 58),
        },
        "Olive": {
            "bg": QColor(66, 82, 62, 228),
            "panel": QColor(188, 204, 168, 218),
            "header": QColor(104, 136, 92, 240),
            "row_a": QColor(112, 148, 98, 214),
            "row_b": QColor(82, 118, 76, 214),
            "selected": QColor(248, 226, 132, 236),
            "text": QColor(248, 252, 242),
            "dark_text": QColor(32, 48, 28),
            "muted": QColor(228, 238, 210),
            "chrome_top": QColor(240, 246, 226, 240),
            "chrome_mid": QColor(188, 210, 166, 228),
            "chrome_bottom": QColor(112, 146, 92, 226),
            "glass": QColor(255, 255, 255, 46),
        },
        "Purple Passion": {
            "bg": QColor(70, 58, 88, 228),
            "panel": QColor(210, 198, 224, 216),
            "header": QColor(132, 108, 166, 240),
            "row_a": QColor(118, 104, 158, 214),
            "row_b": QColor(92, 82, 134, 214),
            "selected": QColor(246, 220, 150, 236),
            "text": QColor(248, 244, 255),
            "dark_text": QColor(34, 26, 56),
            "muted": QColor(226, 218, 246),
            "chrome_top": QColor(244, 238, 252, 240),
            "chrome_mid": QColor(194, 180, 220, 228),
            "chrome_bottom": QColor(132, 118, 172, 226),
            "glass": QColor(255, 255, 255, 46),
        },
        "Charcoal": {
            "bg": QColor(28, 30, 28, 232),
            "panel": QColor(142, 144, 138, 214),
            "header": QColor(70, 72, 66, 242),
            "row_a": QColor(82, 84, 78, 214),
            "row_b": QColor(62, 64, 58, 214),
            "selected": QColor(244, 210, 134, 236),
            "text": QColor(240, 240, 232),
            "dark_text": QColor(18, 20, 18),
            "muted": QColor(204, 206, 194),
            "chrome_top": QColor(224, 224, 216, 236),
            "chrome_mid": QColor(162, 162, 154, 224),
            "chrome_bottom": QColor(104, 104, 96, 222),
            "glass": QColor(255, 255, 255, 36),
        },
        "Tangerine Dream": {
            "bg": QColor(100, 70, 50, 228),
            "panel": QColor(232, 190, 158, 218),
            "header": QColor(176, 104, 70, 242),
            "row_a": QColor(186, 118, 82, 212),
            "row_b": QColor(144, 88, 66, 212),
            "selected": QColor(252, 228, 160, 238),
            "text": QColor(255, 248, 238),
            "dark_text": QColor(62, 34, 22),
            "muted": QColor(248, 222, 196),
            "chrome_top": QColor(252, 228, 198, 238),
            "chrome_mid": QColor(220, 150, 104, 226),
            "chrome_bottom": QColor(156, 92, 58, 226),
            "glass": QColor(255, 255, 255, 42),
        },
        "Digital Cable Blue": {
            "bg": QColor(10, 24, 68, 234),
            "panel": QColor(126, 166, 214, 218),
            "header": QColor(12, 58, 146, 244),
            "row_a": QColor(22, 82, 178, 220),
            "row_b": QColor(12, 46, 118, 220),
            "selected": QColor(246, 232, 132, 238),
            "text": QColor(248, 252, 255),
            "dark_text": QColor(14, 28, 58),
            "muted": QColor(206, 226, 252),
            "chrome_top": QColor(212, 232, 255, 240),
            "chrome_mid": QColor(76, 132, 204, 228),
            "chrome_bottom": QColor(10, 54, 136, 228),
            "glass": QColor(255, 255, 255, 52),
        },
    },
    "Set Top Box": {
        "Cable Blue": {
            "bg": QColor(8, 16, 58, 238),
            "panel": QColor(6, 24, 94, 232),
            "header": QColor(8, 42, 152, 244),
            "row_a": QColor(14, 44, 156, 232),
            "row_b": QColor(106, 38, 50, 228),
            "selected": QColor(242, 232, 110, 240),
            "text": QColor(248, 248, 238),
            "dark_text": QColor(14, 10, 4),
            "muted": QColor(214, 230, 255),
            "chrome_top": QColor(10, 34, 130, 236),
            "chrome_mid": QColor(8, 28, 112, 232),
            "chrome_bottom": QColor(6, 20, 84, 232),
            "glass": QColor(255, 255, 255, 18),
            "flat_panels": True,
            "starfield": False,
        },
        "Midnight Star": {
            "bg": QColor(1, 3, 16, 244),
            "panel": QColor(3, 7, 34, 238),
            "header": QColor(8, 34, 144, 246),
            "row_a": QColor(18, 66, 192, 234),
            "row_b": QColor(106, 38, 54, 230),
            "selected": QColor(246, 236, 108, 242),
            "text": QColor(244, 246, 250),
            "dark_text": QColor(22, 18, 8),
            "muted": QColor(214, 226, 252),
            "chrome_top": QColor(8, 36, 132, 238),
            "chrome_mid": QColor(5, 20, 90, 234),
            "chrome_bottom": QColor(2, 8, 40, 236),
            "glass": QColor(255, 255, 255, 12),
            "flat_panels": True,
            "starfield": True,
        },
        "Get Slimed": {
            "bg": QColor(20, 28, 10, 242),
            "panel": QColor(36, 66, 18, 236),
            "header": QColor(188, 92, 22, 244),
            "row_a": QColor(76, 132, 30, 232),
            "row_b": QColor(122, 58, 24, 228),
            "selected": QColor(226, 238, 84, 242),
            "text": QColor(248, 250, 226),
            "dark_text": QColor(24, 30, 8),
            "muted": QColor(222, 236, 178),
            "chrome_top": QColor(174, 96, 32, 238),
            "chrome_mid": QColor(84, 124, 28, 234),
            "chrome_bottom": QColor(32, 58, 16, 236),
            "glass": QColor(255, 255, 255, 14),
            "flat_panels": True,
            "starfield": False,
        },
        "Green Screen": {
            "bg": QColor(2, 10, 4, 246),
            "panel": QColor(4, 22, 10, 240),
            "header": QColor(6, 52, 20, 244),
            "row_a": QColor(8, 68, 26, 232),
            "row_b": QColor(4, 34, 14, 232),
            "selected": QColor(134, 230, 116, 242),
            "text": QColor(196, 246, 188),
            "dark_text": QColor(2, 18, 6),
            "muted": QColor(142, 210, 136),
            "chrome_top": QColor(8, 68, 26, 238),
            "chrome_mid": QColor(4, 44, 18, 234),
            "chrome_bottom": QColor(2, 18, 8, 238),
            "glass": QColor(150, 255, 140, 12),
            "flat_panels": True,
            "starfield": False,
        },
    },
    "Sleek Freak": {
        "Silver Olive": {
            "bg": QColor(8, 10, 10, 252),
            "panel": QColor(24, 27, 26, 188),
            "header": QColor(56, 64, 54, 202),
            "row_a": QColor(36, 42, 38, 150),
            "row_b": QColor(18, 21, 20, 216),
            "selected": QColor(158, 176, 118, 238),
            "text": QColor(246, 248, 244),
            "dark_text": QColor(20, 24, 20),
            "muted": QColor(196, 204, 192),
            "chrome_top": QColor(238, 244, 234, 34),
            "chrome_mid": QColor(66, 74, 64, 82),
            "chrome_bottom": QColor(7, 8, 8, 232),
            "glass": QColor(255, 255, 255, 18),
            "sleek": True,
        },
        "Grape Jelly": {
            "bg": QColor(10, 7, 16, 252),
            "panel": QColor(28, 22, 38, 190),
            "header": QColor(62, 42, 90, 202),
            "row_a": QColor(44, 32, 62, 152),
            "row_b": QColor(20, 16, 30, 218),
            "selected": QColor(176, 136, 218, 238),
            "text": QColor(252, 248, 255),
            "dark_text": QColor(26, 18, 38),
            "muted": QColor(210, 194, 228),
            "chrome_top": QColor(230, 204, 252, 32),
            "chrome_mid": QColor(72, 50, 104, 82),
            "chrome_bottom": QColor(8, 5, 14, 232),
            "glass": QColor(255, 255, 255, 18),
            "sleek": True,
        },
        "Baby Blue": {
            "bg": QColor(8, 13, 19, 252),
            "panel": QColor(24, 34, 44, 188),
            "header": QColor(50, 88, 124, 202),
            "row_a": QColor(38, 58, 78, 150),
            "row_b": QColor(18, 26, 36, 216),
            "selected": QColor(150, 202, 234, 238),
            "text": QColor(246, 252, 255),
            "dark_text": QColor(18, 30, 40),
            "muted": QColor(198, 222, 238),
            "chrome_top": QColor(222, 244, 255, 34),
            "chrome_mid": QColor(58, 104, 142, 82),
            "chrome_bottom": QColor(6, 10, 16, 232),
            "glass": QColor(255, 255, 255, 20),
            "sleek": True,
        },
        "Millennial Grey": {
            "bg": QColor(9, 11, 13, 252),
            "panel": QColor(28, 32, 38, 190),
            "header": QColor(52, 60, 72, 202),
            "row_a": QColor(40, 46, 56, 152),
            "row_b": QColor(20, 23, 28, 218),
            "selected": QColor(206, 214, 226, 238),
            "text": QColor(248, 250, 252),
            "dark_text": QColor(18, 22, 26),
            "muted": QColor(200, 208, 218),
            "chrome_top": QColor(248, 250, 254, 32),
            "chrome_mid": QColor(84, 94, 108, 78),
            "chrome_bottom": QColor(7, 9, 11, 232),
            "glass": QColor(255, 255, 255, 18),
            "sleek": True,
        },
    },
}


def with_alpha(color, alpha):
    return QColor(color.red(), color.green(), color.blue(), max(0, min(255, int(alpha))))


def color_to_css(color, alpha=None):
    if alpha is None:
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {max(0, min(255, int(alpha)))})"


def draw_sleek_app_background(painter, rect, theme):
    painter.save()
    base = theme["app_background"]
    top = QColor(min(255, base.red() + 5), min(255, base.green() + 5), min(255, base.blue() + 6), 255)
    bottom = QColor(max(0, base.red() - 8), max(0, base.green() - 8), max(0, base.blue() - 8), 255)
    bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
    bg.setColorAt(0.0, top)
    bg.setColorAt(0.62, QColor(base.red(), base.green(), base.blue(), 255))
    bg.setColorAt(1.0, bottom)
    painter.fillRect(rect, bg)

    accent = theme["selected_background"]
    glow_one = QRadialGradient(QPoint(rect.left() + int(rect.width() * 0.18), rect.top() + int(rect.height() * 0.18)), max(rect.width(), rect.height()) * 0.42)
    glow_one.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 16))
    glow_one.setColorAt(0.45, QColor(accent.red(), accent.green(), accent.blue(), 5))
    glow_one.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
    painter.fillRect(rect, glow_one)

    cool = theme["header_background"]
    glow_two = QRadialGradient(QPoint(rect.right() - int(rect.width() * 0.18), rect.bottom() - int(rect.height() * 0.10)), max(rect.width(), rect.height()) * 0.50)
    glow_two.setColorAt(0.0, QColor(cool.red(), cool.green(), cool.blue(), 12))
    glow_two.setColorAt(0.48, QColor(cool.red(), cool.green(), cool.blue(), 4))
    glow_two.setColorAt(1.0, QColor(cool.red(), cool.green(), cool.blue(), 0))
    painter.fillRect(rect, glow_two)

    vignette = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.68)
    vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
    vignette.setColorAt(0.78, QColor(0, 0, 0, 12))
    vignette.setColorAt(1.0, QColor(0, 0, 0, 64))
    painter.fillRect(rect, vignette)
    painter.restore()


def build_app_theme_tokens(theme_name, legacy, skin_name=DEFAULT_SKIN_NAME):
    theme = dict(legacy)
    sleek = bool(legacy.get("sleek"))
    set_top_box = bool(legacy.get("flat_panels")) and not sleek
    primary_text = legacy["text"]
    selected_text = legacy["dark_text"]
    panel_text = readable_text_color(legacy["panel"], light=legacy["text"], dark=legacy["dark_text"])
    dialog_bg = with_alpha(legacy["panel"], 244)
    input_bg = QColor(250, 250, 244, 245) if color_luminance(legacy["panel"]) > 120 else with_alpha(legacy["header"], 232)
    input_text = readable_text_color(input_bg, light=QColor(248, 248, 240), dark=QColor(24, 24, 18))
    if sleek:
        dialog_bg = with_alpha(legacy["bg"], 250)
        input_bg = with_alpha(legacy["row_b"], 232)
        input_text = readable_text_color(input_bg, light=QColor(252, 252, 252), dark=legacy["dark_text"])
        panel_text = readable_text_color(dialog_bg, light=QColor(250, 252, 255), dark=legacy["dark_text"])
    selected_border = with_alpha(legacy["selected"].lighter(110), 212) if sleek else with_alpha(legacy["selected"].lighter(118), 226)
    normal_border = QColor(255, 255, 255, 36) if sleek else with_alpha(legacy["muted"], 150)
    subtle_border = QColor(255, 255, 255, 18) if sleek else with_alpha(legacy["muted"], 82)
    ui_font = ".AppleSystemUIFont" if sleek else "Trebuchet MS"
    guide_header_bg = with_alpha(legacy["header"], 248 if set_top_box else (182 if sleek else legacy["header"].alpha()))
    guide_header_text = primary_text
    guide_channel_bg = with_alpha(legacy["bg"], 236) if set_top_box else with_alpha(legacy["row_b"], 176 if sleek else legacy["row_b"].alpha())
    guide_program_bg = with_alpha(legacy["row_a"], 232 if set_top_box else (150 if sleek else legacy["row_a"].alpha()))
    guide_program_alt_bg = with_alpha(legacy["row_b"], 230 if set_top_box else (134 if sleek else legacy["row_b"].alpha()))
    guide_selected_bg = with_alpha(legacy["selected"], 242 if set_top_box else (224 if sleek else legacy["selected"].alpha()))
    bottom_nav_bg = with_alpha(legacy["header"], 246 if set_top_box else (118 if sleek else legacy["header"].alpha()))
    if sleek:
        guide_header_bg = with_alpha(legacy["bg"], 0)
        guide_channel_bg = with_alpha(legacy["row_b"], 164)
        guide_program_bg = with_alpha(legacy["row_b"], 150)
        guide_program_alt_bg = with_alpha(legacy["row_a"], 118)
        bottom_nav_bg = with_alpha(legacy["bg"], 0)
    theme.update(
        {
            "theme_name": theme_name,
            "skin_name": skin_name,
            "sleek": sleek,
            "app_background": legacy["bg"],
            "panel_background": legacy["panel"],
            "panel_background_alt": legacy["row_a"],
            "header_background": legacy["header"],
            "selected_background": legacy["selected"],
            "selected_border": selected_border,
            "normal_border": normal_border,
            "subtle_border": subtle_border,
            "primary_text": primary_text,
            "secondary_text": legacy["muted"],
            "muted_text": with_alpha(legacy["muted"], 190),
            "selected_text": selected_text,
            "warning_text": QColor(255, 210, 106),
            "accent": legacy["selected"],
            "accent_secondary": legacy["row_a"],
            "highlight": legacy["selected"],
            "guide_header_bg": guide_header_bg,
            "guide_header_text": guide_header_text,
            "guide_time_row_bg": with_alpha(legacy["header"], 230 if set_top_box else (122 if sleek else legacy["header"].alpha())),
            "guide_channel_cell_bg": guide_channel_bg,
            "guide_channel_cell_text": primary_text,
            "guide_program_cell_bg": guide_program_bg,
            "guide_program_cell_alt_bg": guide_program_alt_bg,
            "guide_program_cell_text": primary_text,
            "guide_selected_bg": guide_selected_bg,
            "guide_selected_text": selected_text,
            "guide_selected_border": selected_border,
            "guide_grid_line": normal_border,
            "guide_detail_panel_bg": with_alpha(legacy["panel"], 238 if set_top_box else (172 if sleek else legacy["panel"].alpha())),
            "guide_detail_panel_border": normal_border,
            "guide_preview_border": normal_border,
            "guide_grid_background": with_alpha(legacy["row_b"], 170 if sleek else legacy["row_b"].alpha()),
            "guide_program_cell_background": guide_program_bg,
            "guide_current_program_background": guide_selected_bg,
            "bottom_nav_bg": bottom_nav_bg,
            "bottom_nav_button_bg": with_alpha(legacy["header"], 238 if set_top_box else (120 if sleek else 238)),
            "bottom_nav_button_text": primary_text,
            "menu_panel_bg": with_alpha(legacy["bg"], 240 if set_top_box else (232 if sleek else legacy["panel"].alpha())),
            "menu_panel_border": normal_border,
            "menu_button_bg": with_alpha(legacy["header"], 238 if set_top_box else (120 if sleek else 238)),
            "menu_button_selected_bg": guide_selected_bg,
            "info_overlay_bg": with_alpha(legacy["bg"] if set_top_box else legacy["panel"], 246 if set_top_box else (222 if sleek else 240)),
            "info_overlay_border": normal_border,
            "info_overlay_text": primary_text,
            "info_progress_fill": with_alpha(legacy["selected"], 236),
            "startup_bg": legacy["bg"],
            "startup_panel_bg": dialog_bg,
            "startup_card_bg": with_alpha(legacy["row_b"] if sleek else legacy["row_a"], 184 if sleek else 214),
            "startup_button_bg": with_alpha(legacy["row_b"], 210 if sleek else 238),
            "vault_bg": legacy["bg"],
            "vault_card_bg": with_alpha(legacy["row_b"], 196 if sleek else legacy["row_b"].alpha()),
            "vault_selected_bg": guide_selected_bg,
            "vault_card_background": with_alpha(legacy["row_b"], 196 if sleek else legacy["row_b"].alpha()),
            "vault_hero_background": with_alpha(legacy["panel"], 180 if sleek else legacy["panel"].alpha()),
            "dialog_background": dialog_bg,
            "dialog_panel": with_alpha(legacy["panel"], 198 if sleek else 250),
            "dialog_text": panel_text,
            "dialog_note_text": with_alpha(panel_text, 210),
            "input_background": input_bg,
            "input_text": input_text,
            "button_background": with_alpha(legacy["row_b"], 218 if sleek else 238),
            "button_selected_background": legacy["selected"],
            "overlay_scrim": QColor(0, 0, 0, 118 if sleek else 150),
            "settings_panel_background": legacy["bg"] if legacy.get("starfield") or sleek else legacy["panel"],
            "settings_panel_overlay": QColor(255, 255, 255, 10) if sleek else QColor(0, 0, 0, 78 if legacy.get("starfield") else 18),
            "settings_label_text": primary_text if legacy.get("flat_panels") or sleek else panel_text,
            "settings_value_text": primary_text,
            "settings_value_selected_text": selected_text,
            "focus_ring": selected_border if sleek else QColor(255, 255, 242, 220),
            "focus_glow": with_alpha(legacy["selected"], 70 if sleek else 74),
            "scrollbar_track": with_alpha(legacy["panel"], 118 if sleek else 150),
            "scrollbar_thumb": with_alpha(legacy["selected"], 220),
            "font_primary": ui_font,
            "font_secondary": ui_font,
            "font_ui": ui_font,
            "font_display": "Courier New",
            "scanline_alpha": 0 if sleek else (24 if legacy.get("flat_panels") else 10),
            "noise_dot_alpha": 0 if sleek else (32 if legacy.get("starfield") else 10),
            "border_radius": 8 if sleek else (2 if legacy.get("flat_panels") else 12),
            "card_radius": 8 if sleek else (2 if legacy.get("flat_panels") else 12),
            "cell_radius": 6 if sleek else 6,
            "spacing": 30 if sleek else 12,
            "glass_highlight": QColor(255, 255, 255, 14 if sleek else 74),
            "glass_shadow": QColor(0, 0, 0, 104 if sleek else 42),
            "modern_surface": with_alpha(legacy["panel"], 142 if sleek else legacy["panel"].alpha()),
            "modern_surface_alt": with_alpha(legacy["row_b"], 178 if sleek else legacy["row_b"].alpha()),
            "shape_language": "sleek" if sleek else ("set_top_box" if legacy.get("flat_panels") else "promised_future"),
        }
    )
    return theme


APP_THEMES_BY_SKIN = {
    skin_name: {
        name: build_app_theme_tokens(name, theme, skin_name)
        for name, theme in variants.items()
    }
    for skin_name, variants in GUIDE_THEME_DEFINITIONS.items()
}
APP_THEMES = APP_THEMES_BY_SKIN[DEFAULT_SKIN_NAME]


def normalize_skin_name(skin_name):
    name = str(skin_name or "").strip()
    return SKIN_NAME_ALIASES.get(name, name if name in GUIDE_SKINS else DEFAULT_SKIN_NAME)


def normalize_theme_name(theme_name):
    name = str(theme_name or "").strip()
    return THEME_NAME_ALIASES.get(name, name)


def app_theme(theme_name, skin_name=None):
    skin_name = normalize_skin_name(skin_name or DEFAULT_SKIN_NAME)
    canonical = normalize_theme_name(theme_name)
    family = APP_THEMES_BY_SKIN.get(skin_name, APP_THEMES_BY_SKIN[DEFAULT_SKIN_NAME])
    if canonical in family:
        return family[canonical]
    default_name = DEFAULT_THEME_NAME if DEFAULT_THEME_NAME in family else next(iter(family))
    return family.get(default_name) or next(iter(family.values()))


def build_themed_dialog_stylesheet(theme_name=DEFAULT_THEME_NAME, skin_name=DEFAULT_SKIN_NAME):
    theme = app_theme(theme_name, skin_name)
    dialog_bg = theme["dialog_background"]
    dialog_panel = theme["dialog_panel"]
    text = theme["dialog_text"]
    note = theme["dialog_note_text"]
    input_bg = theme["input_background"]
    input_text = theme["input_text"]
    border = theme["normal_border"]
    selected = theme["selected_background"]
    selected_text = theme["selected_text"]
    return f"""
        QDialog {{
            background: {color_to_css(dialog_bg, 255)};
        }}
        QWidget#dialogCard, QWidget#sectionCard {{
            background: {color_to_css(dialog_panel, 232)};
            border: 1px solid {color_to_css(border, 170)};
            border-radius: 14px;
        }}
        QLabel#dialogTitle {{
            color: {color_to_css(text, 255)};
            font-size: 22px;
            font-weight: 700;
        }}
        QLabel#sectionHeader, QLabel#sectionTitle {{
            color: {color_to_css(text, 255)};
            font-size: 15px;
            font-weight: 700;
        }}
        QLabel#dialogNote, QLabel#sectionNote, QLabel#presetHint, QLabel#fieldHelp, QLabel#metaLabel {{
            color: {color_to_css(note, 230)};
            font-size: 12px;
            font-weight: 500;
        }}
        QLabel#valueTitle {{
            color: {color_to_css(text, 255)};
            font-size: 24px;
            font-weight: 700;
        }}
        QLabel#reasonBox {{
            color: {color_to_css(text, 255)};
            font-size: 13px;
            background: {color_to_css(dialog_panel, 205)};
            border: 1px solid {color_to_css(border, 145)};
            border-radius: 10px;
            padding: 10px;
        }}
        QLabel#configLabel {{
            color: {color_to_css(text, 255)};
            font-size: 14px;
            font-weight: 700;
        }}
        QLineEdit, QComboBox, QSpinBox, QListWidget {{
            min-height: 32px;
            padding: 4px 10px;
            border-radius: 9px;
            border: 1px solid {color_to_css(border, 190)};
            background: {color_to_css(input_bg, 245)};
            color: {color_to_css(input_text, 255)};
        }}
        QCheckBox {{
            color: {color_to_css(text, 255)};
            font-size: 13px;
            spacing: 8px;
        }}
        QPushButton {{
            min-height: 34px;
            padding: 6px 18px;
            border-radius: 10px;
            border: 1px solid {color_to_css(border, 190)};
            color: {color_to_css(input_text, 255)};
            background: {color_to_css(theme["button_background"], 238)};
        }}
        QPushButton:hover, QPushButton:focus {{
            background: {color_to_css(selected, 238)};
            color: {color_to_css(selected_text, 255)};
        }}
        QPushButton#saveButton {{
            color: {color_to_css(selected_text, 255)};
            font-weight: 700;
            border: 1px solid {color_to_css(theme["selected_border"], 220)};
            background: {color_to_css(selected, 242)};
        }}
        QTabWidget::pane {{
            border: 1px solid {color_to_css(border, 160)};
            border-radius: 12px;
            background: {color_to_css(dialog_panel, 90)};
            top: -1px;
        }}
        QTabBar::tab {{
            min-width: 120px;
            padding: 8px 16px;
            margin-right: 6px;
            border: 1px solid {color_to_css(border, 170)};
            border-bottom: none;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            background: {color_to_css(theme["header_background"], 190)};
            color: {color_to_css(theme["primary_text"], 255)};
            font-weight: 700;
        }}
        QTabBar::tab:selected {{
            background: {color_to_css(selected, 230)};
            color: {color_to_css(selected_text, 255)};
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: {color_to_css(theme["scrollbar_track"], 130)};
            width: 12px;
            margin: 2px;
            border-radius: 6px;
        }}
        QScrollBar::handle:vertical {{
            background: {color_to_css(theme["scrollbar_thumb"], 220)};
            min-height: 32px;
            border-radius: 6px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {color_to_css(theme["scrollbar_track"], 130)};
            height: 12px;
            margin: 2px;
            border-radius: 6px;
        }}
        QScrollBar::handle:horizontal {{
            background: {color_to_css(theme["scrollbar_thumb"], 220)};
            min-width: 32px;
            border-radius: 6px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
    """


def build_startup_stylesheet(theme_name=DEFAULT_THEME_NAME, skin_name=DEFAULT_SKIN_NAME):
    theme = app_theme(theme_name, skin_name)
    text = theme["dialog_text"]
    note = theme["dialog_note_text"]
    panel = theme.get("startup_panel_bg", theme["dialog_panel"])
    card = theme.get("startup_card_bg", with_alpha(theme["panel_background_alt"], 228))
    input_bg = theme["input_background"]
    input_text = theme["input_text"]
    border = theme["normal_border"]
    selected = theme["selected_background"]
    selected_text = theme["selected_text"]
    sleek = bool(theme.get("sleek"))
    panel_radius = 8 if sleek else 14
    card_radius = 8 if sleek else 12
    control_radius = 7 if sleek else 10
    button_radius = 7 if sleek else 10
    window_bg = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 {color_to_css(QColor(min(255, theme['startup_bg'].red() + 5), min(255, theme['startup_bg'].green() + 5), min(255, theme['startup_bg'].blue() + 6)), 255)}, "
        f"stop:0.55 {color_to_css(theme['startup_bg'], 255)}, "
        f"stop:1 {color_to_css(QColor(max(0, theme['startup_bg'].red() - 8), max(0, theme['startup_bg'].green() - 8), max(0, theme['startup_bg'].blue() - 8)), 255)})"
        if sleek else color_to_css(theme["app_background"], 255)
    )
    return f"""
        QWidget#startupWindow {{
            background: {window_bg};
        }}
        QWidget#chromeCard, QWidget#loadingCard {{
            background: {color_to_css(panel, 218 if sleek else 232)};
            border: 1px solid {color_to_css(border, 150 if sleek else 170)};
            border-radius: {panel_radius}px;
        }}
        QWidget#sourceCard {{
            background: {color_to_css(card, 176 if sleek else 214)};
            border: 1px solid {color_to_css(border, 145 if sleek else 160)};
            border-radius: {card_radius}px;
        }}
        QLabel#subLabel {{
            color: {color_to_css(text, 255)};
            font-size: 16px;
            font-weight: 700;
        }}
        QLabel#sectionLabel, QLabel#fieldLabel, QLabel#loadingStage {{
            color: {color_to_css(text, 255)};
            font-size: 13px;
            font-weight: 700;
        }}
        QLabel#statusLabel, QLabel#infoPill {{
            color: {color_to_css(text, 255)};
            font-size: 13px;
            background: {color_to_css(panel, 150 if sleek else 180)};
            border: 1px solid {color_to_css(border, 135 if sleek else 150)};
            border-radius: {control_radius}px;
            padding: 10px;
            min-height: 56px;
        }}
        QLabel#loadingDetail {{
            color: {color_to_css(note, 230)};
            font-size: 12px;
        }}
        QLabel#startupLogo {{
            min-height: 86px;
        }}
        QComboBox {{
            min-height: 32px;
            padding: 4px 34px 4px 10px;
            border-radius: {control_radius}px;
            border: 1px solid {color_to_css(border, 190)};
            color: {color_to_css(input_text, 255)};
            background: {color_to_css(input_bg, 235 if sleek else 245)};
            selection-background-color: {color_to_css(selected, 235)};
            selection-color: {color_to_css(selected_text, 255)};
        }}
        QComboBox::drop-down {{
            width: 28px;
            border-left: 1px solid {color_to_css(border, 150)};
            background: {color_to_css(theme.get("startup_button_bg", theme["button_background"]), 238)};
            border-top-right-radius: {control_radius}px;
            border-bottom-right-radius: {control_radius}px;
        }}
        QComboBox QAbstractItemView {{
            border: 1px solid {color_to_css(border, 190)};
            background: {color_to_css(input_bg, 255)};
            color: {color_to_css(input_text, 255)};
            selection-background-color: {color_to_css(selected, 235)};
            selection-color: {color_to_css(selected_text, 255)};
        }}
        QPushButton {{
            min-height: 36px;
            padding: 6px 16px;
            border-radius: {button_radius}px;
            border: 1px solid {color_to_css(border, 190)};
            color: {color_to_css(input_text, 255)};
            background: {color_to_css(theme.get("startup_button_bg", theme["button_background"]), 220 if sleek else 238)};
        }}
        QPushButton:hover, QPushButton:focus, QPushButton#watchButton {{
            color: {color_to_css(selected_text, 255)};
            font-weight: 700;
            border: 1px solid {color_to_css(theme["selected_border"], 210)};
            background: {color_to_css(selected, 242)};
        }}
        QPushButton:disabled, QPushButton#watchButton:disabled {{
            color: {color_to_css(theme["muted_text"], 150)};
            border: 1px solid {color_to_css(border, 110)};
            background: {color_to_css(theme["panel_background"], 150)};
        }}
        QPushButton#advancedButton {{
            font-weight: 700;
        }}
        QProgressBar {{
            min-height: 18px;
            border: 1px solid {color_to_css(border, 170)};
            border-radius: 9px;
            background: {color_to_css(theme["panel_background"], 170)};
            text-align: center;
            color: {color_to_css(text, 255)};
        }}
        QProgressBar::chunk {{
            border-radius: 8px;
            background: {color_to_css(selected, 242)};
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: {color_to_css(theme["scrollbar_track"], 130)};
            width: 12px;
            margin: 2px;
            border-radius: 6px;
        }}
        QScrollBar::handle:vertical {{
            background: {color_to_css(theme["scrollbar_thumb"], 220)};
            min-height: 32px;
            border-radius: 6px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """


SKIN_THEME_MAP = {
    "Promised Future": ["Silver Olive", "Silver", "Olive", "Purple Passion", "Charcoal", "Tangerine Dream", "Digital Cable Blue"],
    "Set Top Box": ["Cable Blue", "Midnight Star", "Get Slimed", "Green Screen"],
    "Sleek Freak": ["Silver Olive", "Grape Jelly", "Baby Blue", "Millennial Grey"],
}


def theme_names_for_skin(skin_name):
    skin_name = normalize_skin_name(skin_name)
    names = SKIN_THEME_MAP.get(skin_name)
    if names:
        return names
    return SKIN_THEME_MAP[DEFAULT_SKIN_NAME]


def default_theme_for_skin(skin_name):
    names = theme_names_for_skin(skin_name)
    return names[0] if names else DEFAULT_THEME_NAME


def normalize_theme_for_skin(skin_name, theme_name):
    original_skin = str(skin_name or "").strip()
    original_theme = str(theme_name or "").strip()
    skin_name = normalize_skin_name(original_skin)
    theme_name = normalize_theme_name(original_theme)
    names = theme_names_for_skin(skin_name)
    if theme_name in names:
        return theme_name
    return default_theme_for_skin(skin_name)


def draw_classic_cable_starfield(painter, rect, theme_name, seed_offset=0):
    painter.save()
    painter.setClipRect(rect)
    painter.fillRect(rect, QColor(2, 4, 10))
    seed = (
        (rect.width() * 10007)
        + (rect.height() * 1009)
        + sum(ord(ch) for ch in str(theme_name))
        + int(seed_offset)
    )
    rng = random.Random(seed)
    star_count = max(180, (rect.width() * rect.height()) // 2400)
    for _ in range(star_count):
        x = rng.randint(rect.left(), max(rect.left(), rect.right() - 3))
        y = rng.randint(rect.top(), max(rect.top(), rect.bottom() - 3))
        roll = rng.random()
        if roll < 0.62:
            size = 1
        elif roll < 0.9:
            size = 2
        else:
            size = 3 if roll < 0.985 else 4
        alpha = 170 + rng.randint(0, 85)
        shade = 228 + rng.randint(0, 27)
        painter.fillRect(x, y, size, size, QColor(shade, shade, 255, alpha))
    painter.restore()


def draw_classic_cable_panel(painter, rect, theme, theme_name, inset=3, border_width=1, border_alpha=90):
    border = theme.get("guide_detail_panel_border", theme.get("normal_border", QColor(228, 236, 255)))
    header = theme.get("guide_header_bg", theme.get("header", QColor(5, 28, 136)))
    panel = theme.get("guide_detail_panel_bg", theme.get("panel", QColor(0, 0, 0)))
    painter.setPen(QPen(with_alpha(border, border_alpha), border_width))
    painter.setBrush(with_alpha(header, 255))
    painter.drawRect(rect)
    inner = rect.adjusted(inset, inset, -inset, -inset)
    if theme.get("starfield"):
        draw_classic_cable_starfield(painter, inner, theme_name, seed_offset=17)
    else:
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(with_alpha(panel, 255))
        painter.drawRect(inner)
        painter.restore()
    return inner


def draw_classic_cable_bar(painter, rect, theme, border_width=1, border_alpha=90):
    border = theme.get("guide_grid_line", theme.get("normal_border", QColor(214, 230, 255)))
    fill = theme.get("guide_header_bg", theme.get("header", QColor(5, 28, 136)))
    painter.setPen(QPen(with_alpha(border, border_alpha), border_width))
    painter.setBrush(with_alpha(fill, 255))
    painter.drawRect(rect)


def draw_classic_cable_slot_box(painter, rect, theme, active=False, border_width=1, border_alpha=84):
    border_key = "guide_selected_border" if active else "guide_grid_line"
    fill_key = "guide_selected_bg" if active else "menu_button_bg"
    border = theme.get(border_key, theme.get("normal_border", QColor(214, 230, 255)))
    fill = theme.get(fill_key, theme.get("selected" if active else "header", QColor(5, 28, 136)))
    painter.setPen(QPen(with_alpha(border, border_alpha), border_width))
    painter.setBrush(with_alpha(fill, 255))
    painter.drawRect(rect)


def draw_shared_mediawave_settings_panel(widget, painter, panel, body_font, small_font, theme):
    settings_values = getattr(widget, "settings_values", {}) or {}
    setting_rows = [
        ("Skin", str(getattr(widget, "skin_name", "")), "value"),
        ("Theme", str(getattr(widget, "theme_name", "")), "value"),
        ("Display", str(getattr(widget, "profile_name", "")), "value"),
        ("No Catalog TV", bool_label(settings_values.get("allow_empty_catalog_tv", False)), "toggle"),
        ("Dummy Vault", bool_label(settings_values.get("allow_dummy_vault_catalog", False)), "toggle"),
        ("Dev Menu", bool_label(settings_values.get("dev_menu_enabled", True)), "toggle"),
        ("Close", "Close", "action"),
    ]
    row_height = 34
    row_gap = 6
    body_top = 42
    rect_h = 66 + (len(setting_rows) * row_height) + ((len(setting_rows) - 1) * row_gap)
    rect = QRect(0, 0, 430, rect_h)
    rect.moveCenter(panel.center())
    widget.draw_xp_panel(painter, rect, theme, radius=10, inset=2)
    title_bar = QRect(rect.left() + 4, rect.top() + 4, rect.width() - 8, 28)
    widget.draw_xp_bar(painter, title_bar, theme, radius=8)
    body_rect = rect.adjusted(6, 36, -6, -6)
    if widget.skin_style() == "cable":
        painter.save()
        painter.setClipRect(body_rect)
        panel_fill = theme["settings_panel_background"]
        painter.fillRect(body_rect, QColor(panel_fill.red(), panel_fill.green(), panel_fill.blue(), 232))
        if theme.get("starfield"):
            draw_classic_cable_starfield(painter, body_rect, getattr(widget, "theme_name", "Midnight Star"), seed_offset=31337)
        painter.fillRect(body_rect, theme["settings_panel_overlay"])
        painter.restore()
        painter.save()
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(theme["normal_border"], 1))
        painter.drawRect(body_rect.adjusted(0, 0, -1, -1))
        painter.restore()

    painter.setFont(small_font)
    if widget.skin_style() == "cable":
        widget.draw_cable_text(
            painter,
            title_bar.adjusted(12, 0, -12, 0),
            f"{APP_NAME} Menu",
            theme["primary_text"],
            small_font,
            Qt.AlignVCenter | Qt.AlignLeft,
        )
    else:
        painter.setPen(theme["text"])
        painter.drawText(title_bar.adjusted(12, 0, -12, 0), Qt.AlignVCenter, f"{APP_NAME} Menu")

    left_arrow_x = rect.left() + 166
    value_x = rect.left() + 200
    value_w = rect.width() - 210 - 34
    row_tops = [body_top + idx * (row_height + row_gap) for idx in range(len(setting_rows))]
    focus_index = max(0, min(int(getattr(widget, "settings_focus_index", 0)), len(setting_rows) - 1))

    widget.skin_prev_rect = QRect(left_arrow_x, rect.top() + row_tops[0], 28, 28)
    widget.skin_next_rect = QRect(rect.right() - 38, rect.top() + row_tops[0], 28, 28)
    widget.theme_prev_rect = QRect(left_arrow_x, rect.top() + row_tops[1], 28, 28)
    widget.theme_next_rect = QRect(rect.right() - 38, rect.top() + row_tops[1], 28, 28)
    widget.profile_prev_rect = QRect(left_arrow_x, rect.top() + row_tops[2], 28, 28)
    widget.profile_next_rect = QRect(rect.right() - 38, rect.top() + row_tops[2], 28, 28)
    if hasattr(widget, "scale_prev_rect"):
        widget.scale_prev_rect = QRect()
    if hasattr(widget, "scale_next_rect"):
        widget.scale_next_rect = QRect()
    if hasattr(widget, "catalog_action_rect"):
        widget.catalog_action_rect = QRect()
    widget.close_action_rect = QRect(value_x, rect.top() + row_tops[-1], value_w, 28)

    skin_rect = QRect(value_x, rect.top() + row_tops[0], value_w, 28)
    theme_rect = QRect(value_x, rect.top() + row_tops[1], value_w, 28)
    profile_rect = QRect(value_x, rect.top() + row_tops[2], value_w, 28)
    value_rects = [QRect(value_x, rect.top() + row_top, value_w, 28) for row_top in row_tops]

    painter.setFont(body_font)
    if widget.skin_style() == "cable":
        for idx, row_top in enumerate(row_tops):
            widget.draw_cable_text(
                painter,
                QRect(rect.left() + 18, rect.top() + row_top - 8, 140, 24),
                setting_rows[idx][0].upper(),
                theme["settings_label_text"],
                body_font,
                Qt.AlignLeft | Qt.AlignVCenter,
            )
    else:
        painter.setPen(theme["settings_label_text"])
        for idx, row_top in enumerate(row_tops):
            painter.drawText(rect.left() + 18, rect.top() + row_top + 20, setting_rows[idx][0])

    for idx, rect_box in enumerate(value_rects):
        widget.draw_slot_box(painter, rect_box, theme, active=focus_index == idx)

    for rect_box, label in (
        (widget.skin_prev_rect, "<"),
        (widget.skin_next_rect, ">"),
        (widget.theme_prev_rect, "<"),
        (widget.theme_next_rect, ">"),
        (widget.profile_prev_rect, "<"),
        (widget.profile_next_rect, ">"),
    ):
        widget.draw_arrow_button(painter, rect_box, label, theme)

    painter.setFont(small_font)
    if widget.skin_style() == "cable":
        value_font = QFont(small_font.family(), small_font.pointSize(), QFont.Bold)
        for idx, (_label, value, _kind) in enumerate(setting_rows):
            widget.draw_cable_text(
                painter,
                value_rects[idx],
                value.upper(),
                theme["settings_value_selected_text"] if focus_index == idx else theme["settings_value_text"],
                value_font,
                Qt.AlignCenter,
            )
    else:
        for idx, (_label, value, _kind) in enumerate(setting_rows):
            painter.setPen(theme["settings_value_selected_text"] if focus_index == idx else theme["settings_value_text"])
            painter.drawText(value_rects[idx], Qt.AlignCenter, value)


# ---------------- CHANNEL ---------------- #

class Channel:
    def __init__(self, name, duration_cache):
        self.name = name
        self.shows = []
        self.durations = []
        self.start_time = GLOBAL_START
        self.duration_cache = duration_cache
        self.schedule_paths = []
        self.schedule_durations = []
        self.schedule_anchor = GLOBAL_START
        self.schedule_entries = []

    def get_duration(self, file):
        cached = self.duration_cache.get(file)
        if cached and cached > 0:
            return cached

        if not FFPROBE_PATH:
            return 0

        try:
            result = subprocess.run(
                [FFPROBE_PATH, "-v", "error",
                 "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1",
                 file],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            duration = float(result.stdout.decode().strip())
            self.duration_cache[file] = duration
            return duration
        except Exception:
            return 0

    def get_current_entry_and_offset(self):
        entries = self.get_schedule_entries()
        if not entries:
            return None, 0

        total = sum(float(entry.get("duration", 0) or 0) for entry in entries)
        if total <= 0:
            return None, 0

        elapsed = (time.time() - self.schedule_anchor) % total

        current = 0
        for entry in entries:
            d = float(entry.get("duration", 0) or 0)
            if current + d > elapsed:
                return entry, elapsed - current
            current += d

        return entries[0], 0

    def get_current(self):
        entry, entry_offset = self.get_current_entry_and_offset()
        if not entry:
            return None, 0
        media_offset = float(entry.get("start_offset", 0) or 0) + float(entry_offset or 0)
        return entry.get("path"), media_offset

    def get_current_index_and_offset(self):
        entries = self.get_schedule_entries()
        if not entries:
            return None, 0

        total = sum(float(entry.get("duration", 0) or 0) for entry in entries)
        if total <= 0:
            return None, 0

        elapsed = (time.time() - self.schedule_anchor) % total

        current = 0
        for i, entry in enumerate(entries):
            d = float(entry.get("duration", 0) or 0)
            if current + d > elapsed:
                return i, elapsed - current
            current += d

        return 0, 0

    def get_now_next(self):
        index, offset = self.get_current_index_and_offset()
        if index is None:
            return None

        entries = self.get_schedule_entries()
        current_entry = entries[index]
        current_path = schedule_entry_user_path(current_entry, current_entry.get("path", ""))
        current_duration = float(current_entry.get("duration", 0) or 0)
        next_index = (index + 1) % len(entries)
        next_entry = entries[next_index]
        next_path = schedule_entry_user_path(next_entry, next_entry.get("path", ""))

        now_start = time.time() - offset
        now_end = now_start + current_duration

        return {
            "current_path": current_path,
            "current_title": schedule_entry_user_title(current_entry, format_program_title(current_path), current_path),
            "current_start": now_start,
            "current_end": now_end,
            "current_entry": current_entry,
            "next_path": next_path,
            "next_title": schedule_entry_user_title(next_entry, format_program_title(next_path), next_path),
            "next_entry": next_entry,
        }

    def get_upcoming_programs(self, count=3):
        index, offset = self.get_current_index_and_offset()
        if index is None:
            return []

        entries = self.get_schedule_entries()
        items = []
        current_start = time.time() - offset
        for step in range(min(count, len(entries))):
            item_index = (index + step) % len(entries)
            entry = entries[item_index]
            start_time = current_start if step == 0 else items[-1]["end"]
            duration = float(entry.get("duration", 0) or 0)
            end_time = start_time + duration
            items.append(
                {
                    "path": schedule_entry_user_path(entry, entry.get("path", "")),
                    "title": schedule_entry_user_title(entry, format_program_title(entry.get("path", "")), entry.get("path", "")),
                    "entry": entry,
                    "start": start_time,
                    "end": end_time,
                }
            )
        return items

    def get_programs_for_window(self, window_start, count=8):
        entries = self.get_schedule_entries()
        if not entries:
            return []

        total = sum(float(entry.get("duration", 0) or 0) for entry in entries)
        if total <= 0:
            return []

        elapsed = (window_start - self.schedule_anchor) % total
        current = 0
        start_index = 0
        offset = 0
        for i, entry in enumerate(entries):
            duration = float(entry.get("duration", 0) or 0)
            if current + duration > elapsed:
                start_index = i
                offset = elapsed - current
                break
            current += duration

        items = []
        current_start = window_start - offset
        for step in range(min(count, len(entries))):
            item_index = (start_index + step) % len(entries)
            entry = entries[item_index]
            start_time = current_start if step == 0 else items[-1]["end"]
            duration = float(entry.get("duration", 0) or 0)
            end_time = start_time + duration
            items.append(
                {
                    "path": schedule_entry_user_path(entry, entry.get("path", "")),
                    "title": schedule_entry_user_title(entry, format_program_title(entry.get("path", "")), entry.get("path", "")),
                    "entry": entry,
                    "start": start_time,
                    "end": end_time,
                }
            )
        return items

    def set_schedule(self, paths, anchor_time):
        entries = []
        for item in paths:
            if isinstance(item, dict):
                path = item.get("path", "")
                duration = float(item.get("duration", 0) or self.duration_cache.get(path, 0) or 0)
                if not path or duration <= 0:
                    continue
                entry = dict(item)
                entry["duration"] = duration
                entry.setdefault("title", format_program_title(path))
                entry.setdefault("kind", "content")
                entry.setdefault("start_offset", 0.0)
                entry.setdefault("end_offset", float(entry.get("start_offset", 0) or 0) + duration)
            else:
                path = item
                duration = float(self.duration_cache.get(path, 0) or 0)
                if duration <= 0:
                    continue
                entry = {
                    "kind": "content",
                    "path": path,
                    "title": format_program_title(path),
                    "duration": duration,
                    "start_offset": 0.0,
                    "end_offset": duration,
                }
            entries.append(entry)
        self.schedule_entries = entries
        self.schedule_paths = [entry.get("path", "") for entry in entries]
        self.schedule_durations = [float(entry.get("duration", 0) or 0) for entry in entries]
        self.schedule_anchor = anchor_time

    def get_schedule_data(self):
        if self.schedule_paths and self.schedule_durations:
            return self.schedule_paths, self.schedule_durations, self.schedule_anchor
        return self.shows, self.durations, self.start_time

    def get_schedule_entries(self):
        if self.schedule_entries:
            return self.schedule_entries
        if self.shows and self.durations:
            return [
                {
                    "kind": "content",
                    "path": path,
                    "title": format_program_title(path),
                    "duration": float(duration or 0),
                    "start_offset": 0.0,
                    "end_offset": float(duration or 0),
                }
                for path, duration in zip(self.shows, self.durations)
                if float(duration or 0) > 0
            ]
        return []


class WeatherChannel:
    channel_type = "weatherstar"

    def __init__(self, location, retro=False):
        self.name = "WeatherStar 4000+"
        self.location = location.strip()
        self.retro = bool(retro)
        self.shows = []
        self.durations = []
        self.start_time = auto_schedule_anchor()
        self.schedule_paths = []
        self.schedule_durations = []
        self.schedule_anchor = self.start_time
        self.segments = [
            ("Local Forecast", 300),
            ("Hourly Forecast", 300),
            ("Extended Outlook", 300),
            ("Regional Radar", 300),
        ]

    def set_schedule(self, paths, anchor_time):
        self.schedule_anchor = anchor_time

    def weatherstar_url(self, widescreen=True):
        params = {
            "latLonQuery": self.location,
            "current-weather-checkbox": "true",
            "hourly-checkbox": "true",
            "hourly-graph-checkbox": "true",
            "extended-forecast-checkbox": "true",
            "local-forecast-checkbox": "true",
            "latest-observations-checkbox": "true",
            "regional-forecast-checkbox": "true",
            "almanac-checkbox": "true",
            "spc-outlook-checkbox": "true",
            "settings-wide-checkbox": "true" if widescreen else "false",
            "settings-scanLines-checkbox": "true" if self.retro else "false",
            "settings-kiosk-checkbox": "true",
            "settings-units-select": "us",
            "settings-speed-select": "1.00",
        }
        query = urllib.parse.urlencode(params)
        return f"https://weatherstar.netbymatt.com/?{query}"

    def get_current(self):
        info = self.get_now_next()
        if not info:
            return None, 0
        return info["current_path"], 0

    def get_current_index_and_offset(self):
        total = sum(duration for _, duration in self.segments)
        elapsed = int((time.time() - self.schedule_anchor) % total)
        current = 0
        for index, (_, duration) in enumerate(self.segments):
            if current + duration > elapsed:
                return index, elapsed - current
            current += duration
        return 0, 0

    def get_now_next(self):
        index, offset = self.get_current_index_and_offset()
        current_title, current_duration = self.segments[index]
        next_index = (index + 1) % len(self.segments)
        next_title, _ = self.segments[next_index]
        now_start = time.time() - offset
        now_end = now_start + current_duration
        return {
            "current_path": f"weatherstar://{current_title.lower().replace(' ', '-')}",
            "current_title": current_title,
            "current_start": now_start,
            "current_end": now_end,
            "next_path": f"weatherstar://{next_title.lower().replace(' ', '-')}",
            "next_title": next_title,
        }

    def get_programs_for_window(self, window_start, count=8):
        total = sum(duration for _, duration in self.segments)
        elapsed = int((window_start - self.schedule_anchor) % total)
        current = 0
        start_index = 0
        offset = 0
        for index, (_, duration) in enumerate(self.segments):
            if current + duration > elapsed:
                start_index = index
                offset = elapsed - current
                break
            current += duration

        items = []
        current_start = window_start - offset
        for step in range(count):
            item_index = (start_index + step) % len(self.segments)
            title, duration = self.segments[item_index]
            start_time = current_start if step == 0 else items[-1]["end"]
            end_time = start_time + duration
            items.append(
                {
                    "path": f"weatherstar://{title.lower().replace(' ', '-')}",
                    "title": title,
                    "start": start_time,
                    "end": end_time,
                }
            )
        return items


class YouTubePlaylistChannel(Channel):
    channel_type = "youtube"

    def __init__(self, playlist_url, entries=None, name="NetTV"):
        super().__init__((name or "NetTV").strip() or "NetTV", {})
        self.playlist_url = (playlist_url or "").strip()
        self.playlist_id = youtube_playlist_id(self.playlist_url)
        self.playlist_key = youtube_playlist_cache_key(self.playlist_url)
        self.start_time = auto_schedule_anchor()
        self.schedule_anchor = self.start_time
        self.entries = []
        self.update_entries(entries or [])

    def set_schedule(self, paths, anchor_time):
        self.schedule_anchor = anchor_time

    def youtube_url(self):
        return youtube_source_url(self.playlist_url)

    def update_entries(self, entries):
        normalized = []
        for index, entry in enumerate(entries or []):
            if not isinstance(entry, dict):
                continue
            title = (entry.get("title") or f"NetTV Video {index + 1}").strip()
            duration = float(entry.get("duration") or 0)
            if duration <= 0:
                duration = 900.0
            video_id = (entry.get("id") or stable_hash(entry.get("url", title))).strip()
            path = entry.get("path") or youtube_video_user_path(self.playlist_key, video_id, index)
            url = entry.get("url") or youtube_video_url(video_id)
            normalized.append(
                {
                    "id": video_id,
                    "url": url,
                    "path": path,
                    "title": title,
                    "duration": max(30.0, duration),
                    "thumbnail": entry.get("thumbnail") or "",
                }
            )
        if not normalized:
            normalized = [
                {
                    "id": "placeholder",
                    "url": "",
                    "path": youtube_video_user_path(self.playlist_key, "loading", 0),
                    "title": "NetTV",
                    "duration": 900.0,
                    "thumbnail": "",
                    "placeholder": True,
                }
            ]
        self.entries = normalized
        self.shows = [entry["path"] for entry in self.entries]
        self.durations = [float(entry.get("duration", 900.0) or 900.0) for entry in self.entries]
        self.schedule_entries = [
            {
                "kind": "youtube",
                "path": entry["path"],
                "title": entry.get("title", "NetTV Video"),
                "display_title": entry.get("title", "NetTV Video"),
                "duration": float(entry.get("duration", 900.0) or 900.0),
                "start_offset": 0.0,
                "end_offset": float(entry.get("duration", 900.0) or 900.0),
                "youtube_entry": dict(entry),
            }
            for entry in self.entries
        ]
        if len(self.schedule_entries) > 1:
            rng = random.Random(stable_hash(f"{self.playlist_key}|nettv-lineup"))
            rng.shuffle(self.schedule_entries)
        self.schedule_paths = [entry.get("path", "") for entry in self.schedule_entries]
        self.schedule_durations = [float(entry.get("duration", 900.0) or 900.0) for entry in self.schedule_entries]

    def get_current(self):
        entry, offset = self.get_current_entry_and_offset()
        if not entry:
            return None, 0
        youtube_entry = entry.get("youtube_entry") or {}
        return youtube_entry.get("path") or entry.get("path"), offset

    def get_current_youtube_entry_and_offset(self):
        entry, offset = self.get_current_entry_and_offset()
        if not entry:
            return None, 0
        youtube_entry = dict(entry.get("youtube_entry") or {})
        if youtube_entry.get("placeholder"):
            return None, 0
        youtube_entry.setdefault("path", entry.get("path", ""))
        youtube_entry.setdefault("title", entry.get("title", "NetTV Video"))
        youtube_entry.setdefault("duration", float(entry.get("duration", 900.0) or 900.0))
        return youtube_entry, offset


class RadioWaveChannel(Channel):
    channel_type = "radiowave"
    EMPTY_PATH = "radiowave://empty"

    def __init__(self, folder, duration_cache, metadata_cache, empty_reason=""):
        super().__init__("RadioWaveTV", duration_cache)
        self.folder = folder.strip()
        self.track_metadata = {}
        self.start_time = time.time()
        self.schedule_anchor = self.start_time
        self.empty_state = False
        self.empty_reason = (empty_reason or "").strip()
        self.discovered_audio_files = 0
        if self.empty_reason:
            self.enable_empty_state()
            return
        self.load_tracks(metadata_cache)
        if self.shows:
            self.shuffle_schedule()
        else:
            if self.discovered_audio_files > 0:
                self.empty_reason = "MediaWave2000 found audio files, but none of them could be prepared for playback."
            else:
                self.empty_reason = "No readable music files were found in the selected folder."
            self.enable_empty_state()

    def load_tracks(self, metadata_cache):
        tracks = []
        for root, dirnames, files in os.walk(self.folder):
            dirnames.sort(key=str.casefold)
            for file_name in sorted(files, key=str.casefold):
                if not file_name.lower().endswith(AUDIO_EXTS):
                    continue
                self.discovered_audio_files += 1
                full_path = os.path.join(root, file_name)
                metadata = parse_local_music_metadata(full_path, self.duration_cache, metadata_cache)
                duration = float(metadata.get("duration", 0) or self.duration_cache.get(full_path, 0) or 0)
                if duration <= 0:
                    duration = RADIOWAVE_FALLBACK_DURATION_SECONDS
                    metadata = dict(metadata)
                    metadata["duration"] = duration
                    metadata_cache[full_path] = metadata
                    self.duration_cache[full_path] = duration
                if duration <= 0:
                    continue
                self.track_metadata[full_path] = metadata
                tracks.append((full_path, duration))
        self.shows = [path for path, _ in tracks]
        self.durations = [duration for _, duration in tracks]

    def enable_empty_state(self):
        self.empty_state = True
        metadata = radiowave_empty_metadata(self.folder, self.empty_reason)
        self.track_metadata[self.EMPTY_PATH] = metadata
        self.shows = [self.EMPTY_PATH]
        self.durations = [RADIOWAVE_FALLBACK_DURATION_SECONDS]
        self.schedule_paths = list(self.shows)
        self.schedule_durations = list(self.durations)
        self.schedule_anchor = self.start_time

    def shuffle_schedule(self):
        if not self.shows:
            self.schedule_paths = []
            self.schedule_durations = []
            return
        order = list(self.shows)
        random.shuffle(order)
        total = int(sum(self.duration_cache.get(path, 0) for path in order))
        anchor = time.time() - (random.randint(0, total - 1) if total > 1 else 0)
        self.set_schedule(order, anchor)

    def metadata_for(self, path):
        return self.track_metadata.get(path, {})

    def get_now_next(self):
        if self.empty_state:
            now_start = time.time()
            now_end = now_start + RADIOWAVE_FALLBACK_DURATION_SECONDS
            metadata = self.metadata_for(self.EMPTY_PATH)
            return {
                "current_path": self.EMPTY_PATH,
                "current_title": metadata.get("title", self.name),
                "current_start": now_start,
                "current_end": now_end,
                "next_path": self.EMPTY_PATH,
                "next_title": metadata.get("title", self.name),
            }
        return super().get_now_next()

    def get_programs_for_window(self, window_start, count=8):
        if self.empty_state:
            return [
                {
                    "path": self.EMPTY_PATH,
                    "title": "Music Server Offline",
                    "start": window_start,
                    "end": window_start + (30 * 60 * max(1, count)),
                }
            ]
        return super().get_programs_for_window(window_start, count)


def format_program_title(path):
    name = os.path.splitext(os.path.basename(path))[0]
    return name.replace("_", " ").replace("`", "'")


# ---------------- STATIC ---------------- #

class StaticOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.opacity = 0
        self.frame = QPixmap()
        self.phase = 0
        self.duration_frames = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.fade)

    def trigger(self, frame=None):
        self.opacity = 255
        self.phase = 0
        self.duration_frames = 7
        self.frame = frame if frame and not frame.isNull() else QPixmap()
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.timer.start(24)

    def fade(self):
        self.phase += 1
        self.opacity = max(0, 255 - int((self.phase / max(1, self.duration_frames)) * 255))
        if self.opacity <= 0:
            self.timer.stop()
            self.hide()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(3, 3, 4))

        if not self.frame.isNull():
            self.paint_vhs_distortion(painter)

        self.paint_scanlines(painter)
        self.paint_head_switching_noise(painter)
        self.paint_edge_tearing(painter)

    def paint_vhs_distortion(self, painter):
        progress = min(1.0, self.phase / max(1, self.duration_frames))
        target_w = max(1, self.width())
        target_h = max(1, self.height())
        scaled = self.frame.scaled(
            target_w,
            target_h,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )

        painter.fillRect(self.rect(), QColor(255, 245, 220, 10 + int((1.0 - progress) * 18)))

        self.draw_chroma_layer(painter, scaled, QColor(255, 50, 120, 95), int(18 * (1.0 - progress)), int(-7 * (1.0 - progress)))
        self.draw_chroma_layer(painter, scaled, QColor(80, 255, 130, 70), int(-7 * (1.0 - progress)), 0)
        self.draw_chroma_layer(painter, scaled, QColor(70, 160, 255, 110), int(-20 * (1.0 - progress)), int(6 * (1.0 - progress)))

        line_h = 2
        for y in range(0, target_h, line_h):
            h = min(line_h, target_h - y)
            wave = int(18 * math.sin((y * 0.04) + (self.phase * 0.9)))
            jitter = random.randint(-8, 8)
            tear = 0
            if y > target_h * 0.6:
                tear = random.randint(-40, 40)
            src_y = min(max(0, y + random.randint(-5, 5)), max(0, target_h - h))
            painter.drawPixmap(wave + jitter + tear, y, scaled, 0, src_y, target_w, h)

        painter.setOpacity(0.22 + ((1.0 - progress) * 0.14))
        painter.drawPixmap(12, 0, scaled, 0, 0, target_w, target_h)
        painter.drawPixmap(-10, 4, scaled, 0, 0, target_w, target_h)
        painter.setOpacity(1.0)

        self.paint_lock_flash(painter, progress)

    def draw_chroma_layer(self, painter, pixmap, tint, x_shift, y_shift):
        painter.setOpacity(min(0.36, self.opacity / 540))
        painter.drawPixmap(x_shift, y_shift, pixmap, 0, 0, self.width(), self.height())
        painter.fillRect(self.rect(), tint)
        painter.setOpacity(1.0)

    def paint_scanlines(self, painter):
        progress = min(1.0, self.phase / max(1, self.duration_frames))
        for y in range(0, self.height(), 2):
            alpha = max(4, int((1.0 - progress) * random.randint(6, 18)))
            x = random.randint(0, 10)
            w = self.width() - random.randint(0, 24)
            shade = 70 + random.randint(0, 35)
            painter.fillRect(x, y, max(0, w), 1, QColor(shade, shade - 2, shade - 6, alpha))

        for _ in range(18):
            y = random.randint(0, max(0, self.height() - 3))
            x = random.randint(0, 20)
            w = self.width() - random.randint(0, 80)
            tone = random.choice([
                QColor(255, 255, 255, random.randint(12, 36)),
                QColor(255, 90, 160, random.randint(10, 28)),
                QColor(100, 180, 255, random.randint(10, 28)),
                QColor(120, 255, 170, random.randint(10, 24)),
            ])
            painter.fillRect(x, y, max(0, w), 1, tone)

    def paint_head_switching_noise(self, painter):
        if self.width() <= 0 or self.height() <= 0:
            return

        bar_top = int(self.height() * 0.62)
        bar_height = self.height() - bar_top
        if bar_height <= 0:
            return

        painter.fillRect(0, bar_top, self.width(), bar_height, QColor(214, 214, 214, max(14, self.opacity // 6)))

        for y in range(bar_top, self.height(), 2):
            noise_segments = random.randint(10, 24)
            for _ in range(noise_segments):
                x = random.randint(0, max(0, self.width() - 12))
                w = random.randint(8, 110)
                color = random.choice([
                    QColor(255, 255, 255, random.randint(24, 90)),
                    QColor(255, 40, 120, random.randint(22, 80)),
                    QColor(60, 255, 120, random.randint(20, 76)),
                    QColor(90, 170, 255, random.randint(22, 82)),
                    QColor(255, 220, 120, random.randint(18, 68)),
                ])
                painter.fillRect(x, y, min(w, self.width() - x), 1, color)

    def paint_edge_tearing(self, painter):
        edge_w = max(12, self.width() // 36)
        for x in range(edge_w):
            alpha = max(0, 26 - x)
            painter.fillRect(x, 0, 1, self.height(), QColor(255, 255, 255, alpha))
            painter.fillRect(self.width() - x - 1, 0, 1, self.height(), QColor(255, 255, 255, alpha))

    def paint_lock_flash(self, painter, progress):
        if progress > 0.74:
            alpha = int((progress - 0.74) / 0.26 * 80)
            painter.fillRect(self.rect(), QColor(255, 244, 220, max(0, min(80, alpha))))


class ChannelOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.display_text = ""
        self.font_family = self.load_font_family()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def load_font_family(self):
        font_id = QFontDatabase.addApplicationFont(CRT_FONT_PATH)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
        return "Courier New"

    def show_channel(self, number, name):
        self.display_text = f"CH {int(number):02d}"
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.timer.start(1900)
        self.update()

    def paintEvent(self, event):
        if not self.display_text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, False)

        target_rect = overlay_target_rect(self)

        font = QFont(self.font_family, max(14, target_rect.width() // 26), QFont.Bold)
        font.setStyleHint(QFont.TypeWriter)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(self.display_text)
        x = target_rect.right() - text_width - max(18, target_rect.width() // 24)
        y = target_rect.top() + max(32, target_rect.height() // 10)

        self.draw_osd_text(painter, x, y, self.display_text, font)

    def draw_osd_text(self, painter, x, y, text, font):
        painter.setFont(font)

        shadow = QColor(0, 22, 0, 220)
        for dx, dy in ((3, 0), (0, 3), (3, 3), (1, 1)):
            painter.setPen(shadow)
            painter.drawText(x + dx, y + dy, text)

        painter.setPen(QColor(90, 255, 110, 255))
        painter.drawText(x, y, text)
        painter.setPen(QColor(200, 255, 190, 110))
        painter.drawText(x - 1, y - 1, text)


class UIScaleOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.current_scale = GUIDE_UI_SCALE_DEFAULT
        self.visible_timer = QTimer(self)
        self.visible_timer.setSingleShot(True)
        self.visible_timer.timeout.connect(self.hide)
        self.hide()

    def show_scale(self, scale_value):
        self.current_scale = clamp_guide_ui_scale(scale_value)
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.visible_timer.start(GUIDE_UI_SCALE_OSD_TIMEOUT_MS)
        self.update()

    def paintEvent(self, event):
        if not self.isVisible():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, False)

        target_rect = overlay_target_rect(self)

        segment_count = int(round((GUIDE_UI_SCALE_MAX - GUIDE_UI_SCALE_MIN) / GUIDE_UI_SCALE_STEP)) + 1
        filled = int(round((self.current_scale - GUIDE_UI_SCALE_MIN) / GUIDE_UI_SCALE_STEP)) + 1
        filled = max(1, min(segment_count, filled))

        panel_w = min(max(420, int(target_rect.width() * 0.52)), target_rect.width() - 28)
        panel_h = max(146, int(target_rect.height() * 0.23))
        panel = QRect(
            target_rect.center().x() - panel_w // 2,
            target_rect.bottom() - panel_h - max(22, target_rect.height() // 14),
            panel_w,
            panel_h,
        )

        label_font = QFont(crt_font_family(), max(16, panel.height() // 3 - 14), QFont.Bold)
        bar_font = QFont(crt_font_family(), max(18, panel.height() // 3), QFont.Bold)
        label_metrics = QFontMetrics(label_font)
        label_text = "MENU SCALE"
        label_rect = QRect(
            panel.left(),
            panel.top() + 12,
            panel.width(),
            label_metrics.height() + 18,
        )
        self.draw_crt_osd_text(painter, label_rect, label_text, label_font, Qt.AlignHCenter | Qt.AlignTop)

        bar_left = panel.left() + 42
        bar_right = panel.right() - 42
        bar_top = label_rect.bottom() + 14
        bar_h = max(28, panel.bottom() - bar_top - 18)
        segment_gap = 5
        available_w = max(80, bar_right - bar_left)
        segment_w = max(6, (available_w - (segment_gap * (segment_count - 1))) // segment_count)

        minus_rect = QRect(panel.left() + 6, bar_top - 3, 28, bar_h + 6)
        plus_rect = QRect(panel.right() - 34, bar_top - 3, 28, bar_h + 6)
        self.draw_crt_osd_text(painter, minus_rect, "-", bar_font, Qt.AlignCenter)
        self.draw_crt_osd_text(painter, plus_rect, "+", bar_font, Qt.AlignCenter)

        for index in range(segment_count):
            seg_rect = QRect(bar_left + index * (segment_w + segment_gap), bar_top, segment_w, bar_h)
            if index < filled:
                painter.fillRect(seg_rect.adjusted(-2, -2, 2, 2), QColor(50, 255, 88, 40))
                painter.fillRect(seg_rect.adjusted(-1, -1, 1, 1), QColor(80, 255, 110, 76))
                color = QColor(38, 255, 74)
            else:
                color = QColor(8, 88, 18, 164)
            painter.fillRect(seg_rect, color)

    def draw_crt_osd_text(self, painter, rect, text, font, flags):
        painter.save()
        painter.setFont(font)
        for dx, dy, alpha in ((3, 0, 86), (-3, 0, 86), (2, 0, 128), (-2, 0, 128), (1, 0, 168), (0, 1, 132), (1, 1, 196)):
            painter.setPen(QColor(0, 16, 0, alpha))
            painter.drawText(rect.translated(dx, dy), flags, text)
        painter.setPen(QColor(144, 255, 170, 120))
        painter.drawText(rect.adjusted(-2, 0, 2, 0), flags, text)
        painter.setPen(QColor(60, 255, 90))
        painter.drawText(rect, flags, text)
        painter.restore()

    def draw_crt_osd_text_at(self, painter, x, y, text, font):
        painter.save()
        painter.setFont(font)
        for dx, dy, alpha in ((3, 0, 86), (-3, 0, 86), (2, 0, 128), (-2, 0, 128), (1, 0, 168), (0, 1, 132), (1, 1, 196)):
            painter.setPen(QColor(0, 16, 0, alpha))
            painter.drawText(x + dx, y + dy, text)
        painter.setPen(QColor(144, 255, 170, 120))
        painter.drawText(x - 1, y - 1, text)
        painter.setPen(QColor(60, 255, 90))
        painter.drawText(x, y, text)
        painter.restore()


class GuideOverlay(QWidget):
    skinStepRequested = Signal(int)
    themeStepRequested = Signal(int)
    profileStepRequested = Signal(int)
    uiScaleStepRequested = Signal(int)
    catalogRequested = Signal()
    settingsToggleRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.channels = []
        self.selected_index = 0
        self.preview_frame = QPixmap()
        self.preview_mode = "video"
        self.profile_name = "Auto"
        self.theme_name = DEFAULT_THEME_NAME
        self.skin_name = DEFAULT_SKIN_NAME
        self.ui_scale = GUIDE_UI_SCALE_DEFAULT
        self.settings_open = False
        self.settings_focus_index = 0
        self.settings_values = {}
        self.skin_prev_rect = QRect()
        self.skin_next_rect = QRect()
        self.theme_prev_rect = QRect()
        self.theme_next_rect = QRect()
        self.profile_prev_rect = QRect()
        self.profile_next_rect = QRect()
        self.catalog_action_rect = QRect()
        self.close_action_rect = QRect()
        self.nav_focus = False
        self.nav_index = 1
        self.back_rect = QRect()
        self.menu_rect = QRect()
        self.guide_rect = QRect()
        self.vault_rect = QRect()
        self.last_preview_update = 0.0
        self.timeline_start = self.floor_to_half_hour(time.time())
        self.hide()

    def show_guide(self, channels, selected_index):
        self.channels = channels
        self.selected_index = max(0, min(selected_index, len(channels) - 1)) if channels else 0
        self.nav_focus = False
        self.nav_index = 1
        self.timeline_start = self.floor_to_half_hour(time.time())
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.update()

    def update_guide(self, channels, selected_index):
        self.channels = channels
        self.selected_index = max(0, min(selected_index, len(channels) - 1)) if channels else 0
        if self.isVisible():
            self.update()

    def set_preview_frame(self, pixmap, mode="video"):
        self.preview_frame = pixmap
        self.preview_mode = mode or "video"
        now = time.time()
        if self.isVisible() and (now - self.last_preview_update) >= 0.18:
            self.last_preview_update = now
            self.update()

    def configure(self, profile_name, theme_name, skin_name, ui_scale=GUIDE_UI_SCALE_DEFAULT):
        self.profile_name = profile_name if profile_name in GUIDE_PROFILES else "Auto"
        self.skin_name = normalize_skin_name(skin_name)
        self.theme_name = normalize_theme_for_skin(self.skin_name, theme_name)
        self.ui_scale = clamp_guide_ui_scale(ui_scale)
        if self.isVisible():
            self.update()

    def guide_metrics(self):
        return build_guide_metrics(self.profile_name, self.ui_scale, self.skin_style())

    def paintEvent(self, event):
        if not self.channels:
            return

        profile = GUIDE_PROFILES[self.profile_name]
        theme = app_theme(self.theme_name, self.skin_name)
        painter = QPainter(self)
        panel = self.guide_canvas_rect()
        cable_skin = self.skin_style() == "cable"
        metrics = self.guide_metrics()
        guide_family = guide_font_family("primary") if cable_skin else theme.get("font_primary", "Trebuchet MS")
        guide_family_secondary = guide_font_family("secondary") if cable_skin else theme.get("font_secondary", "Trebuchet MS")
        body_font = QFont(guide_family_secondary, metrics["font_body"], QFont.DemiBold if cable_skin else QFont.Normal)
        small_font = QFont(guide_family, metrics["font_small"], QFont.Bold)
        if cable_skin:
            painter.fillRect(self.rect(), QColor(theme["bg"].red(), theme["bg"].green(), theme["bg"].blue(), 255))
        elif theme.get("sleek"):
            draw_sleek_app_background(painter, self.rect(), theme)
        else:
            painter.fillRect(self.rect(), QColor(theme["bg"].red(), theme["bg"].green(), theme["bg"].blue(), 170))
        if cable_skin:
            surface_size = self.cable_surface_size(panel)
            surface = QImage(surface_size, QImage.Format_ARGB32_Premultiplied)
            surface.fill(QColor(theme["bg"].red(), theme["bg"].green(), theme["bg"].blue(), 0))
            surface_painter = QPainter(surface)
            surface_painter.setRenderHint(QPainter.TextAntialiasing, False)
            surface_painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
            source_panel = QRect(0, 0, surface.width(), surface.height()).adjusted(4, 4, -4, -4)
            self.draw_guide_scene(surface_painter, source_panel, profile, theme)
            surface_painter.end()
            scaled = QPixmap.fromImage(surface).scaled(panel.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.draw_cable_composite(painter, panel, scaled)
            if self.settings_open:
                painter.fillRect(panel.adjusted(3, 3, -3, -3), QColor(8, 10, 14, 152))
                self.draw_settings_panel(painter, panel, body_font, small_font, theme)
        else:
            self.draw_guide_scene(painter, panel, profile, theme)
            if self.settings_open:
                painter.fillRect(self.rect(), QColor(8, 10, 14, 120))
                self.draw_settings_panel(painter, panel, body_font, small_font, theme)

    def cable_surface_size(self, panel):
        scale = CLASSIC_CABLE_TUNING["crt"]["surface_scale"]
        width = max(760, int(panel.width() * scale))
        height = max(520, int(panel.height() * scale))
        return QSize(width, height)

    def draw_cable_composite(self, painter, target_rect, pixmap):
        crt = CLASSIC_CABLE_TUNING["crt"]
        painter.save()
        painter.drawPixmap(target_rect, pixmap)

        painter.setCompositionMode(QPainter.CompositionMode_Screen)
        painter.setOpacity(crt["screen_mix_a"])
        painter.drawPixmap(target_rect.adjusted(1, 0, 1, 0), pixmap)
        painter.setOpacity(crt["screen_mix_b"])
        painter.drawPixmap(target_rect.adjusted(-1, 0, -1, 0), pixmap)

        painter.setOpacity(1.0)
        self.draw_scanlines(painter, target_rect.adjusted(1, 1, -1, -1))
        self.draw_noise_overlay(painter, target_rect.adjusted(1, 1, -1, -1))
        painter.restore()

    def draw_noise_overlay(self, painter, rect):
        crt = CLASSIC_CABLE_TUNING["crt"]
        painter.save()
        painter.setClipRect(rect)
        t = int(time.time() * 1000)
        for step in range(0, rect.height(), 8):
            y = rect.top() + step
            alpha = crt["noise_line_alpha_base"] + ((t + step * 17) % 4)
            painter.fillRect(rect.left(), y, rect.width(), 1, QColor(255, 255, 255, alpha))
        for i in range(0, rect.width(), 29):
            x = rect.left() + i + ((t // 33) % 5)
            y = rect.top() + ((i * 19 + t // 11) % max(1, rect.height()))
            painter.fillRect(x, y, 1, 1, QColor(255, 255, 255, crt["noise_dot_alpha"]))
        painter.restore()

    def wrap_cable_lines(self, painter, text, width, max_lines=2):
        metrics = painter.fontMetrics()
        words = [w for w in text.split() if w]
        if not words:
            return [""]
        lines = []
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if metrics.horizontalAdvance(trial) <= width:
                current = trial
            else:
                lines.append(current)
                current = word
                if len(lines) == max_lines - 1:
                    break
        remaining_words = words[len(" ".join(lines + [current]).split()):]
        if len(lines) < max_lines:
            final_line = current
            if remaining_words:
                overflow_text = " ".join([current] + remaining_words)
                final_line = metrics.elidedText(overflow_text, Qt.ElideRight, max(12, width))
            lines.append(final_line)
        return lines[:max_lines]

    def draw_guide_scene(self, painter, panel, profile, theme):
        cable_skin = self.skin_style() == "cable"
        metrics = self.guide_metrics()
        cable = CLASSIC_CABLE_TUNING
        self.draw_xp_panel(painter, panel, theme, radius=2 if cable_skin else 16, inset=3)

        scale = metrics["profile_scale"]
        guide_family = guide_font_family("primary") if cable_skin else theme.get("font_primary", "Trebuchet MS")
        guide_family_secondary = guide_font_family("secondary") if cable_skin else theme.get("font_secondary", "Trebuchet MS")
        header_font = QFont(guide_family, metrics["font_header"], QFont.Bold)
        title_font = QFont(guide_family, metrics["font_title"], QFont.Bold)
        body_font = QFont(guide_family_secondary, metrics["font_body"], QFont.DemiBold if cable_skin else QFont.Normal)
        small_font = QFont(guide_family, metrics["font_small"], QFont.Bold)
        selected = self.channels[self.selected_index]

        self.draw_top_header(painter, panel, header_font, small_font, theme, metrics)

        top_y = panel.top() + metrics["top_y"]
        preview_w = max(scaled_metric(198 if cable_skin else 220, self.ui_scale, 180), int(panel.width() * metrics["preview_ratio"]))
        preview_h = max(scaled_metric(116 if cable_skin else 138, self.ui_scale, 100), int(panel.height() * metrics["preview_height"]))
        preview_outer_gap = scaled_metric(20 if cable_skin else 20, self.ui_scale, 12)
        preview_rect = panel.adjusted(panel.width() - preview_w - preview_outer_gap, top_y, -preview_outer_gap, -(panel.height() - top_y - preview_h))
        info_right_gap = scaled_metric(18 if cable_skin else 34, self.ui_scale, 14)
        info_rect = panel.adjusted(metrics["panel_margin"], top_y, -(preview_w + info_right_gap), -(panel.height() - top_y - preview_h))

        self.draw_info_panel(painter, info_rect, selected, title_font, body_font, small_font, theme)
        self.draw_preview_panel(painter, preview_rect, selected, title_font, theme)

        header_y = top_y + preview_h + scaled_metric(6 if cable_skin else 14, self.ui_scale, 4)
        header_rect = QRect(panel.left() + metrics["panel_margin"], header_y, panel.width() - (metrics["panel_margin"] * 2), metrics["header_height"])
        footer_rect = QRect(panel.left() + metrics["panel_margin"], panel.bottom() - metrics["footer_y_offset"], panel.width() - (metrics["panel_margin"] * 2), metrics["footer_height"])

        list_top = header_y + scaled_metric(28 if cable_skin else 42, self.ui_scale, 22)
        row_h = max(metrics["row_height"], int((panel.height() // (14 if cable_skin else 13)) * profile["row_density"] * self.ui_scale))
        rows_bottom = footer_rect.top() - scaled_metric(18 if cable_skin else 8, self.ui_scale, 8)
        available_rows_height = max(row_h, rows_bottom - list_top)
        visible_rows = max(4 if cable_skin else 4, min(10 if cable_skin else 9, available_rows_height // row_h))
        start = max(0, self.selected_index - visible_rows // 2)
        end = min(len(self.channels), start + visible_rows)
        start = max(0, end - visible_rows)

        table_rect = panel.adjusted(metrics["panel_margin"], 0, -metrics["panel_margin"], -scaled_metric(34 if cable_skin else 20, self.ui_scale, 18))
        channel_col = metrics["channel_col"]
        gap = metrics["grid_gap"]
        timeline_rect = QRect(
            table_rect.left() + channel_col + gap + scaled_metric(10, self.ui_scale, 6),
            header_rect.top(),
            table_rect.width() - channel_col - gap - scaled_metric(22, self.ui_scale, 14),
            header_rect.height(),
        )
        timeline_start = self.timeline_start
        slot_seconds = 30 * 60
        slot_count = 4
        timeline_end = timeline_start + (slot_seconds * slot_count)
        self.draw_schedule_header(painter, header_rect, timeline_rect, timeline_start, slot_count, slot_seconds, small_font, theme)

        rows_clip_rect = QRect(table_rect.left(), list_top, table_rect.width(), max(row_h, rows_bottom - list_top))
        painter.save()
        painter.setClipRect(rows_clip_rect)
        for row, idx in enumerate(range(start, end)):
            item = self.channels[idx]
            y = list_top + (row * row_h)
            row_rect = table_rect
            row_rect.setTop(y)
            row_rect.setHeight(row_h - (2 if cable_skin else 4))

            is_current_row = idx == self.selected_index
            is_selected = is_current_row and not self.nav_focus and not self.settings_open
            if cable_skin:
                painter.fillRect(row_rect, with_alpha(theme["guide_detail_panel_bg"], 255))
                painter.setPen(theme["guide_selected_text"] if is_selected else theme["guide_program_cell_text"])
            elif theme.get("sleek"):
                row_fill = with_alpha(theme["selected_background"], 150) if is_selected else with_alpha(theme["panel_background_alt"] if idx % 2 == 0 else theme["vault_card_background"], 104)
                painter.setPen(Qt.NoPen)
                painter.setBrush(row_fill)
                painter.drawRoundedRect(row_rect.adjusted(2, 2, -2, -2), theme.get("cell_radius", 12), theme.get("cell_radius", 12))
                painter.setPen(theme["selected_text"] if is_selected else theme["primary_text"])
            elif is_selected:
                painter.fillRect(row_rect, theme["selected"])
                painter.setPen(theme["dark_text"])
            else:
                painter.fillRect(row_rect, theme["row_a"] if idx % 2 == 0 else theme["row_b"])
                painter.setPen(theme["text"])

            channel_rect = QRect(row_rect.left() + scaled_metric(8, self.ui_scale, 4), row_rect.top(), channel_col - scaled_metric(6, self.ui_scale, 4), row_rect.height())
            channel_box = channel_rect.adjusted(-scaled_metric(6, self.ui_scale, 3), 1 if cable_skin else scaled_metric(4, self.ui_scale, 2), -2, -2 if cable_skin else -scaled_metric(6, self.ui_scale, 3))
            self.draw_channel_cell(painter, channel_box, is_selected, theme)

            if cable_skin:
                inner_channel = channel_box.adjusted(scaled_metric(3, self.ui_scale, 2), scaled_metric(2, self.ui_scale, 1), -scaled_metric(3, self.ui_scale, 2), -scaled_metric(2, self.ui_scale, 1))
                number_h = max(scaled_metric(20, self.ui_scale, 14), int(inner_channel.height() * 0.42))
                number_rect = QRect(inner_channel.left(), inner_channel.top() + 1, inner_channel.width(), number_h)
                abbrev_rect = QRect(inner_channel.left(), number_rect.bottom() + scaled_metric(3, self.ui_scale, 2), inner_channel.width(), inner_channel.bottom() - number_rect.bottom() - scaled_metric(4, self.ui_scale, 2))
                number_font = QFont(guide_family, max(metrics["font_channel_number"], int(number_rect.height() * 0.72)), QFont.Bold)
                abbrev_font = QFont(guide_family_secondary, max(metrics["font_channel_abbrev"], int(max(12, abbrev_rect.height()) * 0.42)), QFont.Bold)
                self.draw_cable_text(
                    painter,
                    number_rect,
                    f"{item['number']:02d}",
                    theme["accent"] if not is_selected else theme["guide_selected_text"],
                    number_font,
                    Qt.AlignHCenter | Qt.AlignVCenter,
                )
                self.draw_cable_text(
                    painter,
                    abbrev_rect.adjusted(1, 0, -1, 0),
                    self.channel_abbreviation(item["name"]),
                    theme["guide_channel_cell_text"] if not is_selected else theme["guide_selected_text"],
                    abbrev_font,
                    Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                )
            else:
                painter.setFont(title_font if is_selected else body_font)
                channel_label = f"{item['number']:>2}  {item['name']}"
                if is_current_row:
                    self.draw_scrolling_text(
                        painter,
                        channel_rect.left(),
                        row_rect.top() + 27,
                        channel_label,
                        channel_rect.width() - 8,
                        title_font if is_selected else body_font,
                        theme["dark_text"] if is_selected else theme["text"],
                    )
                else:
                    painter.drawText(channel_rect.left(), row_rect.top() + 27, self.elide(painter, channel_label, channel_rect.width() - 8))

            painter.setFont(body_font)
            slots = item.get("slots", [])
            row_timeline_rect = QRect(timeline_rect.left(), row_rect.top(), timeline_rect.width(), row_rect.height())
            self.draw_time_grid_row(painter, row_timeline_rect, slot_count, theme)
            for slot_index, slot in enumerate(slots):
                start_ts = slot["start"]
                end_ts = slot["end"]
                if end_ts <= timeline_start or start_ts >= timeline_end:
                    continue
                clamped_start = max(start_ts, timeline_start)
                clamped_end = min(end_ts, timeline_end)
                rel_start = (clamped_start - timeline_start) / (timeline_end - timeline_start)
                rel_end = (clamped_end - timeline_start) / (timeline_end - timeline_start)
                slot_left = row_timeline_rect.left() + int(rel_start * row_timeline_rect.width())
                slot_right = row_timeline_rect.left() + int(rel_end * row_timeline_rect.width())
                slot_width = max(8, slot_right - slot_left)
                slot_rect = QRect(slot_left, row_rect.top(), slot_width, row_rect.height())
                slot_box = slot_rect.adjusted(1 if cable_skin else scaled_metric(2, self.ui_scale, 1), 1 if cable_skin else scaled_metric(4, self.ui_scale, 2), -1 if cable_skin else (-scaled_metric(4, self.ui_scale, 2) if slot_width > 12 else -2), -2 if cable_skin else -scaled_metric(6, self.ui_scale, 3))
                self.draw_program_cell(
                    painter,
                    slot_box,
                    is_selected,
                    theme,
                    primary=(slot_index == 0),
                    emphasis=slot_index,
                    focused=is_selected and slot_index == item.get("detail_slot_index", 0),
                )
                if cable_skin:
                    text_rect = slot_box.adjusted(scaled_metric(4, self.ui_scale, 2), scaled_metric(2, self.ui_scale, 1), -scaled_metric(10 if (is_selected and slot_index == item.get("detail_slot_index", 0)) else 3, self.ui_scale, 3), -scaled_metric(2, self.ui_scale, 1))
                    if slot_width >= 28:
                        painter.save()
                        painter.setFont(body_font)
                        painter.setClipRect(text_rect)
                        wrapped = self.wrap_cable_lines(painter, slot["title"], text_rect.width(), 2)
                        line_height = max(scaled_metric(8, self.ui_scale, 7), painter.fontMetrics().height() - 1)
                        base_y = text_rect.top() + 1
                        color = theme["guide_selected_text"] if (is_selected and slot_index == item.get("detail_slot_index", 0)) else theme["guide_program_cell_text"]
                        for line_index, line in enumerate(wrapped):
                            line_rect = QRect(text_rect.left(), base_y + line_index * line_height, text_rect.width(), line_height)
                            self.draw_cable_text(painter, line_rect, line, color, body_font, Qt.AlignLeft | Qt.AlignTop)
                        painter.restore()
                else:
                    if slot_width >= 72:
                        slot_text = f"{slot['time']}  {slot['title']}"
                        painter.drawText(slot_rect.left() + 8, row_rect.top() + 27, self.elide(painter, slot_text, slot_rect.width() - 16))
                    elif slot_width >= 34:
                        painter.drawText(slot_rect.left() + 6, row_rect.top() + 27, self.elide(painter, slot["time"], slot_rect.width() - 10))
        painter.restore()

        self.draw_footer_controls(painter, footer_rect, small_font, theme)

    def draw_top_header(self, painter, panel, header_font, small_font, theme, metrics):
        if self.skin_style() == "cable":
            brand_rect = QRect(panel.left() + scaled_metric(12, self.ui_scale, 8), panel.top() + scaled_metric(8, self.ui_scale, 6), panel.width() - scaled_metric(24, self.ui_scale, 16), scaled_metric(22, self.ui_scale, 18))
            painter.setPen(QPen(theme["guide_detail_panel_border"], metrics["cell_border"]))
            painter.setBrush(with_alpha(theme["guide_header_bg"], 244))
            painter.drawRect(brand_rect)

            label_rect = QRect(brand_rect.left() + scaled_metric(8, self.ui_scale, 6), brand_rect.top(), scaled_metric(136, self.ui_scale, 104), brand_rect.height())
            label_font = QFont(guide_font_family("primary"), max(metrics["font_header"] - 1, small_font.pointSize() + 1), QFont.Bold)
            self.draw_cable_text(painter, label_rect, "TV GUIDE", theme["guide_header_text"], label_font, Qt.AlignVCenter | Qt.AlignLeft)

            clock_rect = QRect(brand_rect.right() - scaled_metric(124, self.ui_scale, 96), brand_rect.top(), scaled_metric(114, self.ui_scale, 88), brand_rect.height())
            self.draw_cable_digital_clock(painter, clock_rect, time.strftime("%I:%M%p").lstrip("0").lower())
            return
        if theme.get("sleek"):
            top_rect = QRect(panel.left() + scaled_metric(26, self.ui_scale, 18), panel.top() + scaled_metric(20, self.ui_scale, 14), panel.width() - scaled_metric(52, self.ui_scale, 36), scaled_metric(34, self.ui_scale, 26))
            painter.setFont(QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(14, header_font.pointSize() + 1), QFont.DemiBold))
            painter.setPen(theme["primary_text"])
            painter.drawText(top_rect, Qt.AlignLeft | Qt.AlignVCenter, "TV Guide")

            clock_rect = QRect(top_rect.right() - scaled_metric(126, self.ui_scale, 96), top_rect.top() + scaled_metric(3, self.ui_scale, 2), scaled_metric(126, self.ui_scale, 96), top_rect.height() - scaled_metric(6, self.ui_scale, 4))
            painter.setPen(QPen(theme["subtle_border"], 1))
            painter.setBrush(with_alpha(theme["modern_surface_alt"], 170))
            painter.drawRoundedRect(clock_rect, theme.get("cell_radius", 8), theme.get("cell_radius", 8))
            painter.setFont(QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(11, small_font.pointSize() + 1), QFont.DemiBold))
            painter.setPen(theme["secondary_text"])
            painter.drawText(clock_rect, Qt.AlignCenter, time.strftime("%I:%M %p").lstrip("0"))
            return
        brand_rect = QRect(panel.left() + 14, panel.top() + 10, panel.width() - 28, 34)
        self.draw_xp_bar(painter, brand_rect, theme, radius=10)

        label_rect = QRect(brand_rect.left() + 12, brand_rect.top() + 4, 138, brand_rect.height() - 8)
        self.draw_logo_box(painter, label_rect, theme)
        painter.setFont(QFont(theme.get("font_ui", "Trebuchet MS"), max(11, small_font.pointSize() + 2), QFont.Bold))
        painter.setPen(theme["text"])
        painter.drawText(label_rect, Qt.AlignCenter, "TV GUIDE")

        clock_rect = QRect(brand_rect.right() - 184, brand_rect.top() + 3, 172, brand_rect.height() - 6)
        self.draw_digital_clock_box(painter, clock_rect, time.strftime("%I:%M%p").lstrip("0").lower())

    def draw_digital_clock_box(self, painter, rect, text):
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, QColor(74, 78, 80, 240))
        grad.setColorAt(1.0, QColor(44, 46, 48, 244))
        painter.setPen(QPen(QColor(22, 24, 26, 220), 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 8, 8)

        font = QFont(clock_font_family(), max(13, rect.height() - 8), QFont.Bold)
        painter.setFont(font)
        for dx, dy, alpha in ((2, 2, 120), (1, 1, 80)):
            painter.setPen(QColor(22, 0, 0, alpha))
            painter.drawText(rect.translated(dx, dy), Qt.AlignCenter, text)
        painter.setPen(QColor(255, 94, 94, 255))
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.setPen(QColor(255, 180, 180, 120))
        painter.drawText(rect.adjusted(0, -1, 0, -1), Qt.AlignCenter, text)

    def draw_cable_digital_clock(self, painter, rect, text):
        font = QFont(clock_font_family(), max(14, rect.height() - 6), QFont.Bold)
        painter.save()
        painter.setFont(font)
        for dx, dy, alpha in ((2, 2, 108), (1, 1, 84)):
            painter.setPen(QColor(26, 0, 0, alpha))
            painter.drawText(rect.translated(dx, dy), Qt.AlignRight | Qt.AlignVCenter, text)
        painter.setPen(QColor(255, 92, 92, 255))
        painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, text)
        painter.setPen(QColor(255, 182, 182, 116))
        painter.drawText(rect.adjusted(0, -1, 0, -1), Qt.AlignRight | Qt.AlignVCenter, text)
        painter.restore()

    def skin_style(self):
        return GUIDE_SKINS.get(normalize_skin_name(self.skin_name), GUIDE_SKINS[DEFAULT_SKIN_NAME]).get("style", "aero")

    def channel_abbreviation(self, name):
        parts = [part for part in re.split(r"[^A-Z0-9]+", name.upper()) if part]
        if not parts:
            return name[:5].upper()
        if len(parts) == 1:
            token = parts[0]
            return token[:6]
        joined = "".join(part[0] for part in parts[:4])
        return joined[:6]

    def draw_cable_text(self, painter, rect, text, color, font, flags):
        painter.save()
        painter.setFont(font)
        shadow = QColor(0, 0, 0, 220)
        for dx, dy in ((1, 0), (0, 1), (1, 1)):
            painter.setPen(shadow)
            painter.drawText(rect.translated(dx, dy), flags, text)
        painter.setPen(color)
        painter.drawText(rect, flags, text)
        painter.restore()

    def draw_scanlines(self, painter, rect):
        crt = CLASSIC_CABLE_TUNING["crt"]
        painter.save()
        painter.setClipRect(rect)
        painter.setPen(QPen(QColor(0, 0, 0, crt["scanline_alpha"]), 1))
        for y in range(rect.top(), rect.bottom(), crt["scanline_step"]):
            painter.drawLine(rect.left(), y, rect.right(), y)
        painter.restore()

    def draw_logo_watermark(self, painter, rect, opacity=1.0):
        logo = load_brand_logo(rect.width(), rect.height())
        if logo.isNull():
            return
        painter.save()
        painter.setOpacity(opacity)
        x = rect.left()
        y = rect.top() + (rect.height() - logo.height()) // 2
        painter.drawPixmap(x, y, logo)
        painter.restore()

    def draw_universal_buttons(self, painter, bar_rect, small_font, theme, nav_focus, nav_index):
        labels = ["BACK", "MENU", "GUIDE", "VAULT"]
        width = scaled_metric(82, self.ui_scale, 64)
        gap = scaled_metric(8, self.ui_scale, 6)
        height = scaled_metric(24, self.ui_scale, 20)
        total = (width * 4) + (gap * 3)
        start_x = bar_rect.left() + scaled_metric(10, self.ui_scale, 6)
        y = bar_rect.top() + max(2, (bar_rect.height() - height) // 2)
        rects = []
        for idx, label in enumerate(labels):
            rect = QRect(start_x + idx * (width + gap), y, width, height)
            active = nav_focus and nav_index == idx
            if self.skin_style() == "cable":
                self.draw_slot_box(painter, rect, theme, active=active)
                painter.save()
                if active:
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(QColor(250, 248, 170, 220), 2))
                    painter.drawRect(rect.adjusted(1, 1, -1, -1))
                painter.restore()
            elif theme.get("sleek"):
                painter.save()
                painter.setPen(QPen(theme["focus_ring"] if active else theme["subtle_border"], 1))
                painter.setBrush(with_alpha(theme["selected_background"], 226) if active else with_alpha(theme["modern_surface_alt"], 150))
                painter.drawRoundedRect(rect, theme.get("cell_radius", 8), theme.get("cell_radius", 8))
                if active:
                    painter.setPen(QPen(theme["focus_glow"], 4))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), theme.get("cell_radius", 8), theme.get("cell_radius", 8))
                painter.restore()
            elif active:
                self.draw_rounded_gradient_box(
                    painter,
                    rect,
                    QColor(255, 249, 210, 236),
                    QColor(233, 206, 110, 242),
                    QColor(58, 42, 14),
                    radius=6,
                )
            else:
                self.draw_slot_box(painter, rect, theme, active=False)
            if active and self.skin_style() != "cable" and not theme.get("sleek"):
                painter.save()
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(255, 255, 242, 220), 2))
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)
                painter.restore()
            painter.setFont(small_font)
            if self.skin_style() == "cable":
                self.draw_cable_text(
                    painter,
                    rect,
                    label,
                    QColor(18, 16, 8) if active else QColor(248, 248, 240),
                    small_font,
                    Qt.AlignCenter,
                )
            else:
                painter.setPen(theme["selected_text"] if active and theme.get("sleek") else (theme["primary_text"] if theme.get("sleek") else (theme["dark_text"] if active else theme["text"])))
                painter.drawText(rect, Qt.AlignCenter, label)
            rects.append(rect)
        self.back_rect, self.menu_rect, self.guide_rect, self.vault_rect = rects
        return {"left": start_x, "rects": rects}

    def draw_schedule_header(self, painter, rect, timeline_rect, timeline_start, slot_count, slot_seconds, small_font, theme):
        if self.skin_style() == "cable":
            metrics = self.guide_metrics()
            header_font = QFont(guide_font_family("primary"), max(metrics["font_time"], small_font.pointSize()), QFont.Bold)
            today_rect = QRect(rect.left() + scaled_metric(2, self.ui_scale, 1), rect.top(), scaled_metric(74, self.ui_scale, 58), rect.height())
            painter.setPen(QPen(theme["guide_grid_line"], metrics["cell_border"]))
            painter.setBrush(with_alpha(theme["guide_time_row_bg"], 236))
            painter.drawRect(today_rect)
            self.draw_cable_text(
                painter,
                today_rect,
                time.strftime("%I:%M:%S", time.localtime()).lstrip("0"),
                theme["accent"],
                header_font,
                Qt.AlignCenter,
            )

            slot_width = timeline_rect.width() / max(1, slot_count)
            for i in range(slot_count):
                slot_start = timeline_start + (i * slot_seconds)
                label = time.strftime("%I:%M %p", time.localtime(slot_start)).lstrip("0")
                slot_rect = QRect(
                    int(timeline_rect.left() + i * slot_width),
                    rect.top(),
                    int(slot_width),
                    rect.height(),
                )
                painter.setPen(QPen(theme["guide_grid_line"], metrics["cell_border"]))
                painter.setBrush(with_alpha(theme["guide_header_bg"], 228))
                painter.drawRect(slot_rect)
                self.draw_cable_text(painter, slot_rect, label, theme["guide_header_text"], header_font, Qt.AlignCenter)
            return
        if theme.get("sleek"):
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(with_alpha(theme["modern_surface_alt"], 128))
            painter.drawRoundedRect(rect.adjusted(0, 2, 0, -2), theme.get("cell_radius", 8), theme.get("cell_radius", 8))
            painter.setFont(QFont(theme.get("font_ui", ".AppleSystemUIFont"), small_font.pointSize() + 1, QFont.DemiBold))
            painter.setPen(theme["secondary_text"])
            today_rect = QRect(rect.left() + scaled_metric(10, self.ui_scale, 8), rect.top() + 4, scaled_metric(94, self.ui_scale, 72), rect.height() - 8)
            painter.drawText(today_rect, Qt.AlignLeft | Qt.AlignVCenter, "Today")
            for i in range(slot_count):
                slot_start = timeline_start + (i * slot_seconds)
                label = time.strftime("%I:%M %p", time.localtime(slot_start)).lstrip("0")
                slot_rect = QRect(
                    timeline_rect.left() + int((i / slot_count) * timeline_rect.width()),
                    rect.top() + 4,
                    int(timeline_rect.width() / slot_count),
                    rect.height() - 8,
                )
                painter.drawText(slot_rect, Qt.AlignCenter, label)
                if i > 0:
                    painter.setPen(QPen(theme["subtle_border"], 1))
                    painter.drawLine(slot_rect.left(), rect.top() + 8, slot_rect.left(), rect.bottom() - 8)
                    painter.setPen(theme["secondary_text"])
            painter.restore()
            return
        self.draw_xp_bar(painter, rect, theme, radius=8)
        painter.setFont(small_font)
        painter.setPen(theme["muted"])

        today_rect = QRect(rect.left() + 12, rect.top() + 4, 96, rect.height() - 8)
        self.draw_slot_box(painter, today_rect, theme, active=True)
        painter.drawText(today_rect, Qt.AlignCenter, "TODAY")

        for i in range(slot_count):
            slot_start = timeline_start + (i * slot_seconds)
            label = time.strftime("%I:%M%p", time.localtime(slot_start)).lstrip("0").lower()
            slot_rect = QRect(
                timeline_rect.left() + int((i / slot_count) * timeline_rect.width()),
                rect.top() + 4,
                int(timeline_rect.width() / slot_count),
                rect.height() - 8,
            )
            self.draw_slot_box(painter, slot_rect, theme, active=False)
            painter.drawText(slot_rect, Qt.AlignCenter, label)
            if i > 0:
                line_x = slot_rect.left()
                painter.setPen(QPen(QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 130), 1))
                painter.drawLine(line_x, rect.top() + 4, line_x, rect.bottom() - 4)

    def guide_canvas_rect(self):
        margin = scaled_metric(10, self.ui_scale, 8)
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        profile = GUIDE_PROFILES.get(self.profile_name, GUIDE_PROFILES["Auto"])
        target_aspect = profile.get("target_aspect")
        if not target_aspect:
            return rect

        w = rect.width()
        h = rect.height()
        if w <= 0 or h <= 0:
            return rect

        if (w / h) > target_aspect:
            target_h = h
            target_w = int(target_h * target_aspect)
        else:
            target_w = w
            target_h = int(target_w / target_aspect)

        x = rect.left() + ((w - target_w) // 2)
        y = rect.top() + ((h - target_h) // 2)
        return QRect(x, y, target_w, target_h)

    def draw_channel_cell(self, painter, rect, is_selected, theme):
        if self.skin_style() == "cable":
            metrics = self.guide_metrics()
            painter.setPen(QPen(theme["guide_grid_line"], metrics["cell_border"]))
            painter.setBrush(with_alpha(theme["guide_selected_bg"] if is_selected else theme["guide_channel_cell_bg"], 236))
            painter.drawRect(rect)
            return
        if theme.get("sleek"):
            painter.save()
            fill = with_alpha(theme["selected_background"], 224) if is_selected else with_alpha(theme["modern_surface_alt"], 170)
            painter.setPen(QPen(theme["focus_ring"] if is_selected else theme["subtle_border"], 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), theme.get("cell_radius", 8), theme.get("cell_radius", 8))
            if is_selected:
                accent = QRect(rect.left() + 4, rect.top() + 5, 3, rect.height() - 10)
                painter.setPen(Qt.NoPen)
                painter.setBrush(theme["selected_border"])
                painter.drawRoundedRect(accent, 2, 2)
            painter.restore()
            return
        top = QColor(255, 255, 255, 66 if is_selected else 42)
        bottom = theme["selected"] if is_selected else QColor(theme["panel"].red(), theme["panel"].green(), theme["panel"].blue(), 92)
        self.draw_rounded_gradient_box(
            painter,
            rect,
            top,
            bottom,
            theme["dark_text"] if is_selected else QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 120),
        )

    def draw_program_cell(self, painter, rect, is_selected, theme, primary, emphasis=0, focused=False):
        if self.skin_style() == "cable":
            metrics = self.guide_metrics()
            fill = theme["guide_selected_bg"] if focused else (theme["guide_program_cell_bg"] if primary else theme["guide_program_cell_alt_bg"])
            painter.save()
            painter.setPen(QPen(theme["guide_grid_line"], metrics["cell_border"]))
            painter.setBrush(with_alpha(fill, 240 if focused else 232))
            painter.drawRect(rect)
            if focused:
                painter.setPen(QPen(theme["guide_selected_border"], metrics["selected_border"]))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
                wedge = QPolygon(
                    [
                        QPoint(rect.right() - scaled_metric(10, self.ui_scale, 7), rect.top() + scaled_metric(3, self.ui_scale, 2)),
                        QPoint(rect.right() - 2, rect.center().y()),
                        QPoint(rect.right() - scaled_metric(10, self.ui_scale, 7), rect.bottom() - scaled_metric(3, self.ui_scale, 2)),
                    ]
                )
                painter.setPen(Qt.NoPen)
                painter.setBrush(with_alpha(theme["guide_selected_text"], 230))
                painter.drawPolygon(wedge)
            painter.restore()
            return
        if focused and theme.get("sleek"):
            painter.save()
            painter.setPen(QPen(theme["focus_ring"], 2))
            painter.setBrush(with_alpha(theme["selected_background"], 228))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), theme.get("cell_radius", 8), theme.get("cell_radius", 8))
            painter.setPen(QPen(theme["focus_glow"], 5))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(4, 4, -4, -4), theme.get("cell_radius", 8), theme.get("cell_radius", 8))
            painter.restore()
            return
        if theme.get("sleek"):
            fill = with_alpha(theme["modern_surface"], 172 if primary else 136)
            if is_selected:
                fill = with_alpha(theme["modern_surface_alt"], 190)
            painter.save()
            painter.setPen(QPen(theme["normal_border"] if is_selected else theme["subtle_border"], 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), theme.get("cell_radius", 8), theme.get("cell_radius", 8))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, 24), 1))
            painter.drawLine(rect.left() + 8, rect.top() + 2, rect.right() - 8, rect.top() + 2)
            painter.restore()
            return
        if focused:
            top = QColor(255, 248, 196, 220)
            bottom = QColor(236, 202, 102, 230)
            border = QColor(46, 38, 12)
            self.draw_rounded_gradient_box(painter, rect, top, bottom, border)
            highlight = rect.adjusted(2, 2, -2, -rect.height() + 7)
            painter.save()
            painter.setPen(QPen(QColor(255, 255, 240, 210), 2))
            painter.setBrush(QColor(255, 255, 255, 54))
            painter.drawRoundedRect(highlight, 5, 5)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 250, 180, 220), 3))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 7, 7)
            painter.restore()
            return
        if is_selected and primary:
            top = QColor(255, 251, 208, 132)
            bottom = QColor(240, 214, 126, 170)
        elif is_selected:
            top = QColor(250, 252, 255, 78)
            bottom = QColor(theme["panel"].red(), theme["panel"].green(), theme["panel"].blue(), 126)
        elif primary:
            top = QColor(
                min(255, theme["row_a"].red() + 26),
                min(255, theme["row_a"].green() + 26),
                min(255, theme["row_a"].blue() + 18),
                130,
            )
            bottom = QColor(
                max(0, theme["row_a"].red() - 12),
                max(0, theme["row_a"].green() - 12),
                max(0, theme["row_a"].blue() - 10),
                170,
            )
        else:
            top = QColor(
                min(255, theme["row_b"].red() + 20),
                min(255, theme["row_b"].green() + 20),
                min(255, theme["row_b"].blue() + 14),
                100,
            )
            bottom = QColor(
                max(0, theme["row_b"].red() - 10),
                max(0, theme["row_b"].green() - 10),
                max(0, theme["row_b"].blue() - 8),
                140,
            )
        if emphasis == 1:
            top = top.lighter(105)
        elif emphasis >= 2:
            top = top.darker(104)
            bottom = bottom.darker(102)
        border = theme["dark_text"] if is_selected else QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 110)
        self.draw_rounded_gradient_box(painter, rect, top, bottom, border)

    def draw_time_grid_row(self, painter, rect, slot_count, theme):
        painter.save()
        line_alpha = 26 if self.skin_style() == "cable" else 18
        painter.setPen(QPen(with_alpha(theme.get("guide_grid_line", theme["muted"]), line_alpha), 1))
        for i in range(1, slot_count):
            x = rect.left() + int((i / slot_count) * rect.width())
            painter.drawLine(x, rect.top() + 2, x, rect.bottom() - 2)
        painter.restore()

    def floor_to_half_hour(self, timestamp):
        timestamp = int(timestamp)
        half_hour = 30 * 60
        return timestamp - (timestamp % half_hour)

    def draw_info_panel(self, painter, rect, item, title_font, body_font, small_font, theme):
        if self.skin_style() == "cable":
            metrics = self.guide_metrics()
            self.draw_xp_panel(painter, rect, theme, radius=1, inset=1)
            pad_x = scaled_metric(16, self.ui_scale, 10)
            pad_y = scaled_metric(14, self.ui_scale, 10)
            inner = rect.adjusted(pad_x, pad_y, -pad_x, -pad_y)
            logo_h = scaled_metric(42, self.ui_scale, 28)
            top_band_y = inner.top() + scaled_metric(6, self.ui_scale, 4)
            logo_rect = QRect(inner.left(), top_band_y, int(inner.width() * 0.32), logo_h)
            date_rect = QRect(inner.right() - int(inner.width() * 0.30), top_band_y, int(inner.width() * 0.30), scaled_metric(20, self.ui_scale, 15))
            channel_rect = QRect(inner.left(), logo_rect.bottom() + scaled_metric(18, self.ui_scale, 12), inner.width(), scaled_metric(18, self.ui_scale, 14))
            title_font = QFont(guide_font_family("primary"), max(metrics["font_info_title"], title_font.pointSize()), QFont.Bold)
            title_line_height = max(scaled_metric(16, self.ui_scale, 12), QFontMetrics(title_font).height() + scaled_metric(2, self.ui_scale, 1))
            title_bottom_gutter = scaled_metric(18, self.ui_scale, 14)
            title_y = min(
                channel_rect.bottom() + scaled_metric(12, self.ui_scale, 8),
                inner.bottom() - title_bottom_gutter - title_line_height,
            )
            title_rect = QRect(
                inner.left(),
                title_y,
                inner.width(),
                title_line_height,
            )

            logo = load_brand_logo(logo_rect.width(), logo_rect.height(), CLASSIC_APP_LOGO_PATH)
            if not logo.isNull():
                painter.drawPixmap(logo_rect.left(), logo_rect.top(), logo)

            self.draw_cable_text(
                painter,
                date_rect,
                format_long_date(),
                theme["accent"],
                QFont(guide_font_family("secondary"), max(metrics["font_info_meta"], small_font.pointSize()), QFont.DemiBold),
                Qt.AlignRight | Qt.AlignTop,
            )
            painter.save()
            painter.setPen(QPen(with_alpha(theme["accent"], 210), 1))
            underline_y = date_rect.top() + scaled_metric(18, self.ui_scale, 14)
            underline_left = date_rect.right() - int(date_rect.width() * 0.66)
            painter.drawLine(underline_left, underline_y, date_rect.right(), underline_y)
            painter.restore()
            self.draw_cable_text(
                painter,
                channel_rect,
                f"CHANNEL {item['number']:02d}  {item['name'].upper()}",
                theme["info_overlay_text"],
                QFont(guide_font_family("primary"), max(metrics["font_info_meta"] + 1, small_font.pointSize()), QFont.Bold),
                Qt.AlignLeft | Qt.AlignTop,
            )
            self.draw_marquee_text_rect(
                painter,
                title_rect,
                item.get("detail_title", item["now_title"]).upper(),
                title_font,
                theme["accent"],
                speed=36.0,
            )
            return
        if theme.get("sleek"):
            self.draw_xp_panel(painter, rect, theme, radius=theme.get("border_radius", 10), inset=2)
            pad_x = scaled_metric(22, self.ui_scale, 16)
            pad_y = scaled_metric(20, self.ui_scale, 14)
            inner = rect.adjusted(pad_x, pad_y, -pad_x, -pad_y)

            eyebrow_rect = QRect(inner.left(), inner.top(), inner.width(), scaled_metric(20, self.ui_scale, 16))
            painter.setFont(QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(9, small_font.pointSize()), QFont.DemiBold))
            painter.setPen(theme["secondary_text"])
            painter.drawText(eyebrow_rect, Qt.AlignLeft | Qt.AlignVCenter, f"CH {item['number']:02d}  {item['name']}".upper())

            title_rect = QRect(inner.left(), eyebrow_rect.bottom() + scaled_metric(8, self.ui_scale, 6), inner.width(), scaled_metric(46, self.ui_scale, 34))
            painter.setFont(QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(18, title_font.pointSize() + 4), QFont.Bold))
            painter.setPen(theme["primary_text"])
            painter.drawText(title_rect, Qt.TextSingleLine, self.elide(painter, item.get("detail_title", item["now_title"]), title_rect.width()))

            status_text = item.get("detail_status", "Press ENTER to tune live.")
            status_rect = QRect(inner.left(), title_rect.bottom() + scaled_metric(10, self.ui_scale, 8), min(inner.width(), scaled_metric(360, self.ui_scale, 280)), scaled_metric(26, self.ui_scale, 22))
            self.draw_slot_box(painter, status_rect, theme, active=item.get("detail_is_live", True))
            painter.setFont(QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(9, small_font.pointSize()), QFont.DemiBold))
            painter.setPen(theme["selected_text"] if item.get("detail_is_live", True) else theme["secondary_text"])
            painter.drawText(status_rect.adjusted(12, 0, -12, 0), Qt.AlignVCenter, self.elide(painter, status_text, status_rect.width() - 24))

            desc_rect = QRect(inner.left(), status_rect.bottom() + scaled_metric(12, self.ui_scale, 8), inner.width(), inner.bottom() - status_rect.bottom() - scaled_metric(12, self.ui_scale, 8))
            painter.setFont(QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(11, body_font.pointSize()), QFont.Normal))
            painter.setPen(theme["muted_text"])
            painter.drawText(desc_rect, Qt.TextWordWrap, item.get("detail_summary", item["summary"]))
            return
        self.draw_xp_panel(painter, rect, theme, radius=10, inset=2)
        logo_rect = QRect(rect.left() + 18, rect.top() + 14, rect.width() - 36, 58)
        self.draw_logo_watermark(painter, logo_rect, opacity=0.98)

        title_rect = QRect(rect.left() + 14, logo_rect.bottom() + 6, rect.width() - 28, 30)
        meta_rect = QRect(rect.left() + 14, title_rect.bottom() + 6, rect.width() - 28, 18)
        status_rect = QRect(rect.left() + 14, meta_rect.bottom() + 8, rect.width() - 28, 24)
        desc_rect = QRect(rect.left() + 14, status_rect.bottom() + 12, rect.width() - 28, rect.bottom() - status_rect.bottom() - 18)

        painter.setFont(title_font)
        painter.setPen(theme["dark_text"])
        painter.drawText(title_rect, Qt.TextSingleLine, self.elide(painter, item.get("detail_title", item["now_title"]), title_rect.width()))

        painter.setFont(small_font)
        painter.drawText(meta_rect, Qt.TextSingleLine, f"CH {item['number']:02d} {item['name']}")

        status_text = item.get("detail_status", "Press ENTER to tune live.")
        status_box = QRect(status_rect)
        self.draw_slot_box(painter, status_box, theme, active=item.get("detail_is_live", True))
        painter.setPen(theme["dark_text"])
        painter.drawText(status_box.adjusted(10, 0, -10, 0), Qt.AlignVCenter, self.elide(painter, status_text, status_box.width() - 20))

        painter.setFont(body_font)
        painter.setPen(theme["dark_text"])
        painter.drawText(desc_rect, Qt.TextWordWrap, item.get("detail_summary", item["summary"]))

    def draw_preview_panel(self, painter, rect, item, title_font, theme):
        self.draw_xp_panel(painter, rect, theme, radius=1 if self.skin_style() == "cable" else 10, inset=3)
        inner = rect.adjusted(3, 3, -3, -3)
        painter.fillRect(
            inner,
            QColor(
                max(0, theme["bg"].red() - 18),
                max(0, theme["bg"].green() - 18),
                max(0, theme["bg"].blue() - 18),
            ),
        )
        if isinstance(item.get("detail_path"), str) and item["detail_path"].startswith("weatherstar://"):
            if not self.preview_frame.isNull():
                scaled = self.preview_frame.scaled(inner.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                src_x = max(0, (scaled.width() - inner.width()) // 2)
                src_y = max(0, (scaled.height() - inner.height()) // 2)
                painter.drawPixmap(inner, scaled, scaled.rect().adjusted(src_x, src_y, -src_x, -src_y))
                badge = QRect(inner.left() + 10, inner.bottom() - 34, 126, 24)
                self.draw_slot_box(painter, badge, theme, active=True)
                painter.setPen(theme["dark_text"])
                painter.setFont(QFont("Trebuchet MS", max(10, title_font.pointSize() - 2), QFont.Bold))
                painter.drawText(badge, Qt.AlignCenter, "WEATHERSTAR")
                return
            painter.save()
            title = "WeatherStar 4000+"
            meta = item.get("detail_summary", "")
            painter.setPen(theme["text"])
            painter.setFont(QFont("Trebuchet MS", max(18, title_font.pointSize() + 4), QFont.Bold))
            painter.drawText(inner.adjusted(18, 18, -18, -inner.height() // 2), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, title)
            painter.setFont(QFont("Trebuchet MS", max(10, title_font.pointSize() - 1), QFont.Bold))
            painter.setPen(QColor(255, 96, 96))
            painter.drawText(inner.adjusted(18, inner.height() // 2 - 8, -18, -18), Qt.AlignLeft | Qt.AlignTop, "LOCAL WEATHER")
            painter.setFont(QFont("Trebuchet MS", max(9, title_font.pointSize() - 3)))
            painter.setPen(theme["muted"])
            painter.drawText(inner.adjusted(18, inner.height() // 2 + 14, -18, -18), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, meta)
            painter.restore()
            return
        if not self.preview_frame.isNull():
            keep_mode = Qt.KeepAspectRatio if self.preview_mode in ("radiowave", "weatherstar") else Qt.KeepAspectRatioByExpanding
            scaled = self.preview_frame.scaled(inner.size(), keep_mode, Qt.SmoothTransformation)
            draw_rect = QRect(
                inner.left() + max(0, (inner.width() - scaled.width()) // 2),
                inner.top() + max(0, (inner.height() - scaled.height()) // 2),
                scaled.width(),
                scaled.height(),
            )
            painter.fillRect(inner, QColor(0, 0, 0))
            painter.drawPixmap(draw_rect, scaled)
        elif self.skin_style() == "cable":
            painter.fillRect(inner, QColor(0, 0, 0))
            self.draw_cable_text(
                painter,
                inner,
                "LIVE PREVIEW",
                QColor(252, 252, 246),
                QFont(guide_font_family(), max(11, title_font.pointSize()), QFont.Bold),
                Qt.AlignCenter,
            )

    def elide(self, painter, text, width):
        return painter.fontMetrics().elidedText(text, Qt.ElideRight, max(12, width))

    def draw_xp_panel(self, painter, rect, theme, radius=12, inset=3):
        if self.skin_style() == "cable":
            metrics = self.guide_metrics()
            draw_classic_cable_panel(
                painter,
                rect,
                theme,
                self.theme_name,
                inset=inset,
                border_width=metrics["cell_border"],
            )
            return
        if theme.get("sleek"):
            radius = min(max(radius, 4), theme.get("border_radius", 10))
            painter.save()
            shadow = rect.adjusted(0, 5, 0, 6)
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme["glass_shadow"])
            painter.drawRoundedRect(shadow, radius, radius)

            painter.setPen(QPen(theme["normal_border"], 1))
            painter.setBrush(theme["modern_surface"])
            painter.drawRoundedRect(rect, radius, radius)

            inner = rect.adjusted(inset + 1, inset + 1, -(inset + 1), -(inset + 1))
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme["modern_surface_alt"])
            painter.drawRoundedRect(inner, max(4, radius - 2), max(4, radius - 2))
            painter.setPen(QPen(theme["glass_highlight"], 1))
            painter.drawLine(inner.left() + radius, inner.top() + 1, inner.right() - radius, inner.top() + 1)
            painter.restore()
            return
        outer = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        outer.setColorAt(0.0, theme["chrome_top"])
        outer.setColorAt(0.45, theme["chrome_mid"])
        outer.setColorAt(1.0, theme["chrome_bottom"])
        painter.setPen(QPen(QColor(theme["dark_text"].red(), theme["dark_text"].green(), theme["dark_text"].blue(), 170), 1))
        painter.setBrush(outer)
        painter.drawRoundedRect(rect, radius, radius)

        inner = rect.adjusted(inset, inset, -inset, -inset)
        inner_grad = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        inner_grad.setColorAt(0.0, theme["glass"])
        inner_grad.setColorAt(0.35, theme["panel"])
        inner_grad.setColorAt(
            1.0,
            QColor(
                theme["panel"].red() - 18,
                theme["panel"].green() - 14,
                theme["panel"].blue() - 6,
                theme["panel"].alpha(),
            ),
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(inner_grad)
        painter.drawRoundedRect(inner, max(4, radius - 3), max(4, radius - 3))

    def draw_xp_bar(self, painter, rect, theme, radius=8):
        if self.skin_style() == "cable":
            metrics = self.guide_metrics()
            draw_classic_cable_bar(painter, rect, theme, border_width=metrics["cell_border"])
            return
        if theme.get("sleek"):
            radius = min(max(radius, 4), theme.get("border_radius", 10))
            painter.setPen(QPen(theme["normal_border"], 1))
            painter.setBrush(theme["guide_header_bg"] if theme["guide_header_bg"].alpha() else theme["modern_surface_alt"])
            painter.drawRoundedRect(rect, radius, radius)
            painter.setPen(QPen(theme["glass_highlight"], 1))
            painter.drawLine(rect.left() + radius, rect.top() + 1, rect.right() - radius, rect.top() + 1)
            return
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, QColor(255, 255, 255, 36))
        grad.setColorAt(0.12, QColor(min(255, theme["header"].red() + 24), min(255, theme["header"].green() + 22), min(255, theme["header"].blue() + 18), 235))
        grad.setColorAt(1.0, QColor(max(0, theme["header"].red() - 8), max(0, theme["header"].green() - 6), max(0, theme["header"].blue() - 2), 240))
        painter.setPen(QPen(QColor(theme["dark_text"].red(), theme["dark_text"].green(), theme["dark_text"].blue(), 150), 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, radius, radius)

    def draw_badge(self, painter, rect, top_color, bottom_color):
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, QColor(255, 255, 255, 40))
        grad.setColorAt(0.1, top_color)
        grad.setColorAt(1.0, bottom_color)
        painter.setPen(QPen(QColor(132, 34, 30, 210), 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 6, 6)

    def draw_logo_box(self, painter, rect, theme):
        if self.skin_style() == "cable":
            painter.setPen(QPen(theme["guide_preview_border"], 1))
            painter.setBrush(with_alpha(theme["guide_detail_panel_bg"], 230))
            painter.drawRect(rect)
            return
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(
            0.0,
            QColor(
                max(0, theme["header"].red() - 34),
                max(0, theme["header"].green() - 30),
                max(0, theme["header"].blue() - 24),
                235,
            ),
        )
        grad.setColorAt(
            1.0,
            QColor(
                max(0, theme["bg"].red() - 24),
                max(0, theme["bg"].green() - 20),
                max(0, theme["bg"].blue() - 14),
                245,
            ),
        )
        painter.setPen(QPen(QColor(255, 255, 255, 75), 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 8, 8)

    def draw_slot_box(self, painter, rect, theme, active=False):
        if self.skin_style() == "cable":
            metrics = self.guide_metrics()
            draw_classic_cable_slot_box(
                painter,
                rect,
                theme,
                active=active,
                border_width=metrics["cell_border"],
            )
            return
        if active:
            top = QColor(min(255, theme["chrome_mid"].red() + 20), min(255, theme["chrome_mid"].green() + 20), min(255, theme["chrome_mid"].blue() + 12), 170)
            bottom = QColor(max(0, theme["header"].red() - 12), max(0, theme["header"].green() - 10), max(0, theme["header"].blue() - 8), 196)
        else:
            top = QColor(min(255, theme["header"].red() + 18), min(255, theme["header"].green() + 14), min(255, theme["header"].blue() + 10), 136)
            bottom = QColor(max(0, theme["bg"].red() - 10), max(0, theme["bg"].green() - 8), max(0, theme["bg"].blue() - 6), 172)
        if theme.get("sleek"):
            fill = with_alpha(theme["selected_background"], 232) if active else theme["menu_button_bg"]
            border = theme["focus_ring"] if active else theme["subtle_border"]
            painter.setPen(QPen(border, 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, theme.get("cell_radius", 8), theme.get("cell_radius", 8))
            return
        border = QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 140)
        self.draw_rounded_gradient_box(painter, rect, top, bottom, border, radius=6)

    def draw_rounded_gradient_box(self, painter, rect, top_color, bottom_color, border_color, radius=6):
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, top_color)
        grad.setColorAt(1.0, bottom_color)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, radius, radius)

    def draw_settings_panel(self, painter, panel, body_font, small_font, theme):
        draw_shared_mediawave_settings_panel(self, painter, panel, body_font, small_font, theme)

    def draw_arrow_button(self, painter, rect, label, theme):
        self.draw_slot_box(painter, rect, theme, active=True)
        if self.skin_style() == "cable":
            arrow_font = QFont(guide_font_family("primary"), max(10, rect.height() - 12), QFont.Bold)
            self.draw_cable_text(painter, rect, label, QColor(248, 248, 240), arrow_font, Qt.AlignCenter)
        else:
            painter.setPen(theme["text"])
            painter.drawText(rect, Qt.AlignCenter, label)

    def draw_footer_controls(self, painter, rect, small_font, theme):
        if theme.get("sleek"):
            self.draw_universal_buttons(painter, rect, small_font, theme, self.nav_focus, self.nav_index)
            return
        self.draw_xp_bar(painter, rect, theme, radius=8)
        self.draw_universal_buttons(painter, rect, small_font, theme, self.nav_focus, self.nav_index)

    def draw_mediawave_logo(self, painter, rect, header_font, theme):
        logo = load_brand_logo(rect.width(), rect.height())
        if logo.isNull():
            painter.setFont(header_font)
            painter.setPen(QColor(248, 248, 242))
            painter.drawText(rect, Qt.AlignCenter, APP_NAME)
            return
        x = rect.left() + (rect.width() - logo.width()) // 2
        y = rect.top() + (rect.height() - logo.height()) // 2
        painter.drawPixmap(x, y, logo)

    def draw_scrolling_text(self, painter, x, y, text, width, font, color):
        painter.save()
        painter.setFont(font)
        painter.setPen(color)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        clip_rect = QRect(x, y - metrics.ascent(), max(12, width), metrics.height() + 4)
        painter.setClipRect(clip_rect)

        if text_width <= width:
            painter.drawText(x, y, text)
        else:
            overflow = text_width - width
            offset = int(((math.sin(time.time() * 1.4) + 1) / 2) * overflow)
            painter.drawText(x - offset, y, text)
        painter.restore()

    def draw_marquee_text_rect(self, painter, rect, text, font, color, speed=42.0):
        painter.save()
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        baseline_y = rect.top() + metrics.ascent()
        clip_rect = QRect(rect.left(), rect.top(), max(12, rect.width()), max(metrics.height() + 4, rect.height()))
        painter.setClipRect(clip_rect)

        if text_width <= rect.width():
            self.draw_cable_text(painter, rect, text, color, font, Qt.AlignLeft | Qt.AlignTop)
        else:
            overflow = text_width - rect.width()
            pause = 0.9
            travel = max(0.1, overflow / speed)
            cycle = (pause * 2.0) + (travel * 2.0)
            t = time.time() % cycle
            if t < pause:
                offset = 0.0
            elif t < pause + travel:
                offset = (t - pause) * speed
            elif t < pause + travel + pause:
                offset = overflow
            else:
                offset = overflow - ((t - pause - travel - pause) * speed)
            self.draw_cable_text(painter, QRect(int(rect.left() - offset), rect.top(), text_width + 8, rect.height()), text, color, font, Qt.AlignLeft | Qt.AlignTop)
        painter.restore()

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        if self.settings_open:
            if self.skin_prev_rect.contains(pos):
                self.skinStepRequested.emit(-1)
                event.accept()
                return
            if self.skin_next_rect.contains(pos):
                self.skinStepRequested.emit(1)
                event.accept()
                return
            if self.theme_prev_rect.contains(pos):
                self.themeStepRequested.emit(-1)
                event.accept()
                return
            if self.theme_next_rect.contains(pos):
                self.themeStepRequested.emit(1)
                event.accept()
                return
            if self.profile_prev_rect.contains(pos):
                self.profileStepRequested.emit(-1)
                event.accept()
                return
            if self.profile_next_rect.contains(pos):
                self.profileStepRequested.emit(1)
                event.accept()
                return
            if self.scale_prev_rect.contains(pos):
                self.uiScaleStepRequested.emit(-1)
                event.accept()
                return
            if self.scale_next_rect.contains(pos):
                self.uiScaleStepRequested.emit(1)
                event.accept()
                return
            if self.catalog_action_rect.contains(pos):
                self.catalogRequested.emit()
                event.accept()
                return
            if self.close_action_rect.contains(pos):
                self.settings_open = False
                self.update()
                event.accept()
                return

        super().mousePressEvent(event)


class OnDemandOverlay(QWidget):
    skinStepRequested = Signal(int)
    themeStepRequested = Signal(int)
    profileStepRequested = Signal(int)
    uiScaleStepRequested = Signal(int)
    footerNavRequested = Signal(int)
    settingsCloseRequested = Signal()
    homeCardRequested = Signal(int, int)
    upRequested = Signal()
    downRequested = Signal()
    leftRequested = Signal()
    rightRequested = Signal()
    selectRequested = Signal()
    backRequested = Signal()
    settingsToggleRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.profile_name = "Auto"
        self.theme_name = DEFAULT_THEME_NAME
        self.skin_name = DEFAULT_SKIN_NAME
        self.ui_scale = GUIDE_UI_SCALE_DEFAULT
        self.state = {}
        self.settings_open = False
        self.settings_focus_index = 0
        self.settings_values = {}
        self.home_row_offsets = {}
        self.home_row_targets = {}
        self.last_home_layout_debug_signature = None
        self.home_vertical_offset = 0.0
        self.home_vertical_target = 0.0
        self.episode_list_offset = 0.0
        self.episode_list_target = 0.0
        self.feature_previous = {}
        self.feature_current = {}
        self.feature_transition = 1.0
        self.footer_button_rects = []
        self.home_card_hit_rects = []
        self.skin_prev_rect = QRect()
        self.skin_next_rect = QRect()
        self.theme_prev_rect = QRect()
        self.theme_next_rect = QRect()
        self.profile_prev_rect = QRect()
        self.profile_next_rect = QRect()
        self.close_action_rect = QRect()
        self.stream_anim_timer = QTimer(self)
        self.stream_anim_timer.setInterval(16)
        self.stream_anim_timer.timeout.connect(self.advance_stream_animation)
        self.hide()

    def configure(self, profile_name, theme_name, skin_name, ui_scale=GUIDE_UI_SCALE_DEFAULT):
        self.profile_name = profile_name if profile_name in GUIDE_PROFILES else "Auto"
        self.skin_name = normalize_skin_name(skin_name)
        self.theme_name = normalize_theme_for_skin(self.skin_name, theme_name)
        self.ui_scale = clamp_guide_ui_scale(ui_scale)
        if self.isVisible():
            self.update()

    def skin_style(self):
        return GUIDE_SKINS.get(normalize_skin_name(self.skin_name), GUIDE_SKINS[DEFAULT_SKIN_NAME]).get("style", "aero")

    def show_browser(self, state):
        self.apply_stream_state(state or {})
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.update()

    def update_browser(self, state):
        self.apply_stream_state(state or {})
        if self.isVisible():
            self.update()

    def hideEvent(self, event):
        super().hideEvent(event)

    def apply_stream_state(self, state):
        old_view = self.state.get("view")
        old_feature = self.state.get("hero") if old_view == "home" else self.state.get("detail")
        new_view = state.get("view")
        new_feature = state.get("hero") if new_view == "home" else state.get("detail")
        self.state = state or {}
        if self.feature_signature(old_feature) != self.feature_signature(new_feature):
            self.feature_previous = old_feature or {}
            self.feature_current = new_feature or {}
            self.feature_transition = 0.0 if self.feature_previous else 1.0
            self.start_stream_animation()
        else:
            self.feature_current = new_feature or {}
            self.feature_previous = {}
            self.feature_transition = 1.0
        self.settings_focus_index = max(0, min(int(self.state.get("settings_focus_index", 0)), 6))

    def debug_vault_layout(self, message, **fields):
        write_vault_debug_log("VaultLayout", message, fields)

    def feature_signature(self, feature):
        if not feature:
            return ""
        return "||".join(
            str(feature.get(key, ""))
            for key in ("title", "subtitle", "meta", "progress_label", "badge")
        )

    def start_stream_animation(self):
        if not self.stream_anim_timer.isActive():
            self.stream_anim_timer.start()

    def ease_toward(self, current, target, factor=0.24, snap=0.6):
        if abs(target - current) <= snap:
            return target, False
        return current + ((target - current) * factor), True

    def advance_stream_animation(self):
        active = False
        self.home_vertical_offset, moved = self.ease_toward(self.home_vertical_offset, self.home_vertical_target, factor=0.2, snap=0.4)
        active = active or moved
        self.episode_list_offset, moved = self.ease_toward(self.episode_list_offset, self.episode_list_target, factor=0.22, snap=0.4)
        active = active or moved
        for key in list(set(self.home_row_offsets.keys()) | set(self.home_row_targets.keys())):
            current = self.home_row_offsets.get(key, 0.0)
            target = self.home_row_targets.get(key, 0.0)
            value, moved = self.ease_toward(current, target, factor=0.24, snap=0.4)
            self.home_row_offsets[key] = value
            active = active or moved
        if self.feature_transition < 1.0:
            self.feature_transition = min(1.0, self.feature_transition + 0.14)
            active = True
        if active:
            self.update()
        else:
            self.stream_anim_timer.stop()

    def stream_row_key(self, section, index):
        return section.get("key") or f"section-{index}"

    def stream_card_metrics(self, rect):
        gap = scaled_metric(16, self.ui_scale, 12)
        card_w = max(
            scaled_metric(214, self.ui_scale, 168),
            min(
                scaled_metric(276, self.ui_scale, 210),
                int(rect.width() * 0.24),
            ),
        )
        card_h = max(scaled_metric(164, self.ui_scale, 126), rect.height())
        return card_w, card_h, gap

    def sync_home_view_targets(self, rows_rect, sections):
        selected_section = self.state.get("selected_section", 0)
        section_item_indices = self.state.get("section_item_indices", {})
        row_gap = scaled_metric(22, self.ui_scale, 16)
        row_height = max(
            scaled_metric(198, self.ui_scale, 150),
            min(scaled_metric(228, self.ui_scale, 176), int(rows_rect.height() * 0.34)),
        )
        total_height = max(0, (len(sections) * row_height) + (max(0, len(sections) - 1) * row_gap))
        max_vertical = max(0.0, float(total_height - rows_rect.height()))
        selected_raw_y = selected_section * (row_height + row_gap)
        vertical_target = max(0.0, min(max_vertical, float(selected_raw_y)))
        if abs(vertical_target - self.home_vertical_target) > 0.5:
            self.home_vertical_target = vertical_target
            self.start_stream_animation()

        for index, section in enumerate(sections):
            key = self.stream_row_key(section, index)
            selected_item = section_item_indices.get(index, 0)
            row_padding = scaled_metric(8, self.ui_scale, 6)
            available_width = rows_rect.width() - scaled_metric(26, self.ui_scale, 18) - (row_padding * 2)
            row_cards_rect = QRect(0, 0, available_width, row_height - scaled_metric(54, self.ui_scale, 42))
            card_w, _, gap = self.stream_card_metrics(row_cards_rect)
            items = section.get("items", [])
            total_width = max(0, len(items) * (card_w + gap) - gap)
            max_offset = max(0.0, float(total_width - row_cards_rect.width()))
            target_offset = 0.0
            if items:
                focus_margin = scaled_metric(54, self.ui_scale, 38)
                selected_left = selected_item * (card_w + gap)
                selected_right = selected_left + card_w
                min_visible_offset = max(0.0, float(selected_right - row_cards_rect.width() + focus_margin))
                max_visible_offset = max(0.0, float(selected_left - focus_margin))
                current_target = self.home_row_targets.get(key, self.home_row_offsets.get(key, 0.0))
                if current_target < min_visible_offset:
                    target_offset = min_visible_offset
                elif current_target > max_visible_offset:
                    target_offset = max_visible_offset
                else:
                    target_offset = current_target
                target_offset = max(0.0, min(max_offset, target_offset))
            if abs(target_offset - self.home_row_targets.get(key, 0.0)) > 0.5:
                self.home_row_targets[key] = target_offset
                self.start_stream_animation()
            self.home_row_offsets.setdefault(key, target_offset)

    def draw_horizontal_edge_fades(self, painter, rect, theme, show_left, show_right):
        fade_w = min(scaled_metric(34, self.ui_scale, 24), max(18, rect.width() // 10))
        painter.save()
        painter.setPen(Qt.NoPen)
        if show_left:
            grad = QLinearGradient(rect.left(), 0, rect.left() + fade_w, 0)
            base = QColor(theme["panel"].red(), theme["panel"].green(), theme["panel"].blue(), 228)
            grad.setColorAt(0.0, base)
            grad.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 0))
            painter.setBrush(grad)
            painter.drawRect(QRect(rect.left(), rect.top(), fade_w, rect.height()))
        if show_right:
            grad = QLinearGradient(rect.right() - fade_w, 0, rect.right(), 0)
            base = QColor(theme["panel"].red(), theme["panel"].green(), theme["panel"].blue(), 228)
            grad.setColorAt(0.0, QColor(base.red(), base.green(), base.blue(), 0))
            grad.setColorAt(1.0, base)
            painter.setBrush(grad)
            painter.drawRect(QRect(rect.right() - fade_w + 1, rect.top(), fade_w, rect.height()))
        painter.restore()

    def draw_vertical_edge_fades(self, painter, rect, theme, show_top, show_bottom):
        fade_h = min(scaled_metric(42, self.ui_scale, 30), max(18, rect.height() // 10))
        painter.save()
        painter.setPen(Qt.NoPen)
        if show_top:
            grad = QLinearGradient(0, rect.top(), 0, rect.top() + fade_h)
            base = QColor(theme["panel"].red(), theme["panel"].green(), theme["panel"].blue(), 226)
            grad.setColorAt(0.0, base)
            grad.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 0))
            painter.setBrush(grad)
            painter.drawRect(QRect(rect.left(), rect.top(), rect.width(), fade_h))
        if show_bottom:
            grad = QLinearGradient(0, rect.bottom() - fade_h, 0, rect.bottom())
            base = QColor(theme["panel"].red(), theme["panel"].green(), theme["panel"].blue(), 226)
            grad.setColorAt(0.0, QColor(base.red(), base.green(), base.blue(), 0))
            grad.setColorAt(1.0, base)
            painter.setBrush(grad)
            painter.drawRect(QRect(rect.left(), rect.bottom() - fade_h + 1, rect.width(), fade_h))
        painter.restore()

    def paintEvent(self, event):
        if not self.state:
            return

        theme = app_theme(self.theme_name, self.skin_name)
        profile = GUIDE_PROFILES[self.profile_name]
        painter = QPainter(self)
        panel = self.canvas_rect()
        self._input_source_rect = QRect(panel)
        self._input_target_rect = QRect(panel)
        scale = profile["scale"]
        if self.skin_style() == "cable":
            header_font = QFont(guide_font_family("primary"), max(scaled_metric(13, self.ui_scale, 10), int((panel.width() // 52) * scale * self.ui_scale)), QFont.Bold)
            title_font = QFont(guide_font_family("primary"), max(scaled_metric(12, self.ui_scale, 10), int((panel.width() // 62) * scale * self.ui_scale)), QFont.Bold)
            body_font = QFont(guide_font_family("secondary"), max(scaled_metric(10, self.ui_scale, 8), int((panel.width() // 90) * scale * self.ui_scale)), QFont.DemiBold)
            small_font = QFont(guide_font_family("primary"), max(scaled_metric(9, self.ui_scale, 7), int((panel.width() // 108) * scale * self.ui_scale)), QFont.Bold)
        else:
            ui_font = theme.get("font_ui", "Trebuchet MS")
            header_font = QFont(ui_font, max(scaled_metric(15, self.ui_scale, 12), int((panel.width() // 44) * scale * self.ui_scale)), QFont.Bold)
            title_font = QFont(ui_font, max(scaled_metric(12, self.ui_scale, 10), int((panel.width() // 58) * scale * self.ui_scale)), QFont.Bold)
            body_font = QFont(ui_font, max(scaled_metric(10, self.ui_scale, 9), int((panel.width() // 84) * scale * self.ui_scale)))
            small_font = QFont(ui_font, max(scaled_metric(9, self.ui_scale, 8), int((panel.width() // 95) * scale * self.ui_scale)), QFont.Bold)

        if self.skin_style() == "cable":
            painter.fillRect(self.rect(), QColor(theme["bg"].red(), theme["bg"].green(), theme["bg"].blue(), 255))
            surface_size = self.cable_surface_size(panel)
            surface = QImage(surface_size, QImage.Format_ARGB32_Premultiplied)
            surface.fill(QColor(theme["bg"].red(), theme["bg"].green(), theme["bg"].blue(), 255))
            surface_painter = QPainter(surface)
            surface_painter.setRenderHint(QPainter.TextAntialiasing, False)
            surface_painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
            source_panel = QRect(0, 0, surface.width(), surface.height()).adjusted(4, 4, -4, -4)
            self._input_source_rect = QRect(source_panel)
            self._input_target_rect = QRect(panel)
            self.draw_vault_scene(surface_painter, source_panel, title_font, body_font, small_font, theme)
            surface_painter.end()
            scaled = QPixmap.fromImage(surface).scaled(panel.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.draw_cable_composite(painter, panel, scaled)
            if self.settings_open:
                painter.fillRect(panel.adjusted(3, 3, -3, -3), QColor(8, 10, 14, 152))
                self.draw_settings_panel(painter, panel, body_font, small_font, theme)
            return
        if theme.get("sleek"):
            draw_sleek_app_background(painter, self.rect(), theme)
        else:
            painter.fillRect(self.rect(), QColor(theme["bg"].red(), theme["bg"].green(), theme["bg"].blue(), 176))
        self.draw_vault_scene(painter, panel, title_font, body_font, small_font, theme)
        if self.settings_open:
            painter.fillRect(panel.adjusted(3, 3, -3, -3), QColor(8, 10, 14, 112))
            self.draw_settings_panel(painter, panel, body_font, small_font, theme)

    def map_interactive_rect(self, rect):
        source = getattr(self, "_input_source_rect", QRect())
        target = getattr(self, "_input_target_rect", QRect())
        if source.isNull() or target.isNull():
            return QRect(rect)
        if source == target:
            return QRect(rect)
        rel_left = (rect.left() - source.left()) / max(1, source.width())
        rel_top = (rect.top() - source.top()) / max(1, source.height())
        rel_right = (rect.right() - source.left()) / max(1, source.width())
        rel_bottom = (rect.bottom() - source.top()) / max(1, source.height())
        mapped = QRect(
            target.left() + int(round(rel_left * target.width())),
            target.top() + int(round(rel_top * target.height())),
            max(1, int(round((rel_right - rel_left) * target.width()))),
            max(1, int(round((rel_bottom - rel_top) * target.height()))),
        )
        return mapped

    def cable_surface_size(self, panel):
        scale = CLASSIC_CABLE_TUNING["crt"]["surface_scale"]
        width = max(760, int(panel.width() * scale))
        height = max(520, int(panel.height() * scale))
        return QSize(width, height)

    def draw_cable_composite(self, painter, target_rect, pixmap):
        crt = CLASSIC_CABLE_TUNING["crt"]
        painter.save()
        painter.drawPixmap(target_rect, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_Screen)
        painter.setOpacity(crt["screen_mix_a"])
        painter.drawPixmap(target_rect.adjusted(1, 0, 1, 0), pixmap)
        painter.setOpacity(crt["screen_mix_b"])
        painter.drawPixmap(target_rect.adjusted(-1, 0, -1, 0), pixmap)
        painter.setOpacity(1.0)
        self.draw_scanlines(painter, target_rect.adjusted(1, 1, -1, -1))
        self.draw_noise_overlay(painter, target_rect.adjusted(1, 1, -1, -1))
        painter.restore()

    def draw_scanlines(self, painter, rect):
        crt = CLASSIC_CABLE_TUNING["crt"]
        painter.save()
        painter.setClipRect(rect)
        painter.setPen(QPen(QColor(0, 0, 0, crt["scanline_alpha"]), 1))
        for y in range(rect.top(), rect.bottom(), crt["scanline_step"]):
            painter.drawLine(rect.left(), y, rect.right(), y)
        painter.restore()

    def draw_noise_overlay(self, painter, rect):
        crt = CLASSIC_CABLE_TUNING["crt"]
        painter.save()
        painter.setClipRect(rect)
        t = int(time.time() * 1000)
        for step in range(0, rect.height(), 8):
            y = rect.top() + step
            alpha = crt["noise_line_alpha_base"] + ((t + step * 17) % 4)
            painter.fillRect(rect.left(), y, rect.width(), 1, QColor(255, 255, 255, alpha))
        for i in range(0, rect.width(), 29):
            x = rect.left() + i + ((t // 33) % 5)
            y = rect.top() + ((i * 19 + t // 11) % max(1, rect.height()))
            painter.fillRect(x, y, 1, 1, QColor(255, 255, 255, crt["noise_dot_alpha"]))
        painter.restore()

    def draw_vault_scene(self, painter, panel, title_font, body_font, small_font, theme):
        self.draw_panel(painter, panel, theme, radius=16, inset=3)
        self.draw_header(painter, panel, title_font, small_font, theme)

        footer_rect = QRect(panel.left() + scaled_metric(18, self.ui_scale, 12), panel.bottom() - scaled_metric(42, self.ui_scale, 30), panel.width() - scaled_metric(36, self.ui_scale, 24), scaled_metric(28, self.ui_scale, 22))
        view = self.state.get("view", "menu")
        if view == "home":
            self.draw_streaming_home_view(painter, panel, footer_rect, title_font, body_font, small_font, theme)
        else:
            self.draw_streaming_detail_view(painter, panel, footer_rect, title_font, body_font, small_font, theme)
        self.draw_footer(painter, footer_rect, small_font, theme)

    def canvas_rect(self):
        margin = scaled_metric(10, self.ui_scale, 8)
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        profile = GUIDE_PROFILES.get(self.profile_name, GUIDE_PROFILES["Auto"])
        target_aspect = profile.get("target_aspect")
        if not target_aspect:
            return rect

        w = rect.width()
        h = rect.height()
        if (w / max(1, h)) > target_aspect:
            target_h = h
            target_w = int(target_h * target_aspect)
        else:
            target_w = w
            target_h = int(target_w / target_aspect)
        x = rect.left() + ((w - target_w) // 2)
        y = rect.top() + ((h - target_h) // 2)
        return QRect(x, y, target_w, target_h)

    def draw_header(self, painter, rect, header_font, small_font, theme):
        if self.skin_style() == "cable":
            bar = QRect(rect.left() + scaled_metric(12, self.ui_scale, 8), rect.top() + scaled_metric(10, self.ui_scale, 8), rect.width() - scaled_metric(24, self.ui_scale, 16), scaled_metric(28, self.ui_scale, 22))
            self.draw_bar(painter, bar, theme, radius=1)
            label_rect = QRect(bar.left() + scaled_metric(8, self.ui_scale, 6), bar.top() + 2, scaled_metric(104, self.ui_scale, 82), bar.height() - 4)
            painter.setPen(QPen(theme["guide_detail_panel_border"], 1))
            painter.setBrush(with_alpha(theme["guide_header_bg"], 255))
            painter.drawRect(label_rect)
            painter.setFont(header_font)
            painter.setPen(theme["guide_header_text"])
            painter.drawText(label_rect.adjusted(6, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft, "VAULT")
            clock_rect = QRect(bar.right() - scaled_metric(124, self.ui_scale, 98), bar.top() + 2, scaled_metric(112, self.ui_scale, 90), bar.height() - 4)
            self.draw_digital_clock_box(painter, clock_rect, time.strftime("%I:%M%p").lstrip("0").upper())
            return
        if theme.get("sleek"):
            header_rect = QRect(rect.left() + scaled_metric(28, self.ui_scale, 20), rect.top() + scaled_metric(20, self.ui_scale, 14), rect.width() - scaled_metric(56, self.ui_scale, 40), scaled_metric(36, self.ui_scale, 28))
            painter.setFont(QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(18, header_font.pointSize() + 3), QFont.Bold))
            painter.setPen(theme["primary_text"])
            painter.drawText(header_rect, Qt.AlignLeft | Qt.AlignVCenter, "Vault")

            clock_rect = QRect(header_rect.right() - scaled_metric(126, self.ui_scale, 96), header_rect.top() + scaled_metric(3, self.ui_scale, 2), scaled_metric(126, self.ui_scale, 96), header_rect.height() - scaled_metric(6, self.ui_scale, 4))
            painter.setPen(QPen(theme["subtle_border"], 1))
            painter.setBrush(with_alpha(theme["modern_surface_alt"], 170))
            painter.drawRoundedRect(clock_rect, theme.get("cell_radius", 8), theme.get("cell_radius", 8))
            painter.setFont(QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(11, small_font.pointSize() + 1), QFont.DemiBold))
            painter.setPen(theme["secondary_text"])
            painter.drawText(clock_rect, Qt.AlignCenter, time.strftime("%I:%M %p").lstrip("0"))
            return
        bar = QRect(rect.left() + scaled_metric(14, self.ui_scale, 10), rect.top() + scaled_metric(10, self.ui_scale, 8), rect.width() - scaled_metric(28, self.ui_scale, 20), scaled_metric(32, self.ui_scale, 26))
        self.draw_bar(painter, bar, theme, radius=10)
        section_rect = QRect(bar.left() + scaled_metric(12, self.ui_scale, 8), bar.top() + scaled_metric(4, self.ui_scale, 2), scaled_metric(120, self.ui_scale, 92), scaled_metric(24, self.ui_scale, 20))
        self.draw_rounded_gradient_box(
            painter,
            section_rect,
            QColor(theme["chrome_top"].red(), theme["chrome_top"].green(), theme["chrome_top"].blue(), 176),
            QColor(theme["chrome_bottom"].red(), theme["chrome_bottom"].green(), theme["chrome_bottom"].blue(), 192),
            QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 130),
            radius=8,
        )
        painter.setFont(QFont("Trebuchet MS", max(11, small_font.pointSize() + 2), QFont.Bold))
        painter.setPen(theme["text"])
        painter.drawText(section_rect, Qt.AlignCenter, "VAULT")
        clock_rect = QRect(bar.right() - scaled_metric(184, self.ui_scale, 142), bar.top() + scaled_metric(3, self.ui_scale, 2), scaled_metric(172, self.ui_scale, 134), bar.height() - scaled_metric(6, self.ui_scale, 4))
        self.draw_digital_clock_box(painter, clock_rect, time.strftime("%I:%M%p").lstrip("0").lower())

    def draw_universal_buttons(self, painter, bar_rect, small_font, theme):
        labels = ["BACK", "MENU", "GUIDE", "VAULT"]
        width = scaled_metric(94, self.ui_scale, 72)
        gap = scaled_metric(8, self.ui_scale, 6)
        height = scaled_metric(24, self.ui_scale, 20)
        total = (width * 4) + (gap * 3)
        start_x = bar_rect.left() + scaled_metric(10, self.ui_scale, 6)
        y = bar_rect.top() + max(2, (bar_rect.height() - height) // 2)
        self.footer_button_rects = []
        for idx, label in enumerate(labels):
            rect = QRect(start_x + idx * (width + gap), y, width, height)
            self.footer_button_rects.append(self.map_interactive_rect(rect))
            active = self.state.get("nav_focused") and self.state.get("nav_index", 3) == idx
            if self.skin_style() == "cable":
                self.draw_slot_box(painter, rect, theme, active=active)
                if active:
                    painter.save()
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(theme["focus_ring"], 2))
                    painter.drawRect(rect.adjusted(1, 1, -1, -1))
                    painter.restore()
                value_font = QFont(guide_font_family("primary"), max(9, small_font.pointSize()), QFont.Bold)
                self.draw_cable_text(
                    painter,
                    rect,
                    label,
                    theme["selected_text"] if active else theme["bottom_nav_button_text"],
                    value_font,
                    Qt.AlignCenter,
                )
            elif theme.get("sleek"):
                painter.save()
                painter.setPen(QPen(theme["focus_ring"] if active else theme["subtle_border"], 1))
                painter.setBrush(with_alpha(theme["selected_background"], 226) if active else with_alpha(theme["modern_surface_alt"], 150))
                painter.drawRoundedRect(rect, theme.get("cell_radius", 8), theme.get("cell_radius", 8))
                if active:
                    painter.setPen(QPen(theme["focus_glow"], 4))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), theme.get("cell_radius", 8), theme.get("cell_radius", 8))
                painter.setFont(small_font)
                painter.setPen(theme["selected_text"] if active else theme["primary_text"])
                painter.drawText(rect, Qt.AlignCenter, label)
                painter.restore()
            else:
                top = QColor(255, 249, 210, 236) if active else QColor(theme["chrome_top"].red(), theme["chrome_top"].green(), theme["chrome_top"].blue(), 180)
                bottom = QColor(233, 206, 110, 242) if active else QColor(theme["chrome_bottom"].red(), theme["chrome_bottom"].green(), theme["chrome_bottom"].blue(), 190)
                border = QColor(58, 42, 14) if active else QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 130)
                self.draw_rounded_gradient_box(painter, rect, top, bottom, border, radius=8)
                if active:
                    painter.save()
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(QColor(255, 255, 242, 220), 2))
                    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)
                    painter.restore()
                painter.setFont(small_font)
                painter.setPen(theme["dark_text"] if active else theme["text"])
                painter.drawText(rect, Qt.AlignCenter, label)
        return {"left": start_x}

    def draw_digital_clock_box(self, painter, rect, text):
        if self.skin_style() == "cable":
            font = QFont(clock_font_family(), max(13, rect.height() - 6), QFont.Bold)
            painter.setFont(font)
            for dx, dy, alpha in ((2, 1, 120), (1, 0, 80)):
                painter.setPen(QColor(40, 0, 0, alpha))
                painter.drawText(rect.translated(dx, dy), Qt.AlignCenter, text)
            painter.setPen(QColor(255, 112, 112))
            painter.drawText(rect, Qt.AlignCenter, text)
            painter.setPen(QColor(255, 186, 186, 110))
            painter.drawText(rect.adjusted(0, -1, 0, -1), Qt.AlignCenter, text)
            return
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, QColor(74, 78, 80, 240))
        grad.setColorAt(1.0, QColor(44, 46, 48, 244))
        painter.setPen(QPen(QColor(22, 24, 26, 220), 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 8, 8)

        font = QFont(clock_font_family(), max(13, rect.height() - 8), QFont.Bold)
        painter.setFont(font)
        for dx, dy, alpha in ((2, 2, 120), (1, 1, 80)):
            painter.setPen(QColor(22, 0, 0, alpha))
            painter.drawText(rect.translated(dx, dy), Qt.AlignCenter, text)
        painter.setPen(QColor(255, 94, 94, 255))
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.setPen(QColor(255, 180, 180, 120))
        painter.drawText(rect.adjusted(0, -1, 0, -1), Qt.AlignCenter, text)

    def draw_logo_watermark(self, painter, rect, opacity=1.0):
        logo = load_brand_logo(rect.width(), rect.height())
        if logo.isNull():
            return
        painter.save()
        painter.setOpacity(opacity)
        x = rect.left()
        y = rect.top() + (rect.height() - logo.height()) // 2
        painter.drawPixmap(x, y, logo)
        painter.restore()

    def draw_cable_text(self, painter, rect, text, color, font, flags):
        if not text:
            return
        painter.save()
        painter.setFont(font)
        shadow = QColor(0, 0, 0, 220)
        for dx, dy in ((1, 0), (0, 1), (1, 1)):
            painter.setPen(shadow)
            painter.drawText(rect.translated(dx, dy), flags, text)
        painter.setPen(color)
        painter.drawText(rect, flags, text)
        painter.restore()

    def draw_xp_panel(self, painter, rect, theme, radius=12, inset=3):
        self.draw_panel(painter, rect, theme, radius=radius, inset=inset)

    def draw_xp_bar(self, painter, rect, theme, radius=8):
        self.draw_bar(painter, rect, theme, radius=radius)

    def draw_slot_box(self, painter, rect, theme, active=False):
        if self.skin_style() == "cable":
            draw_classic_cable_slot_box(painter, rect, theme, active=active)
            return
        if active:
            top = QColor(min(255, theme["chrome_mid"].red() + 20), min(255, theme["chrome_mid"].green() + 20), min(255, theme["chrome_mid"].blue() + 12), 170)
            bottom = QColor(max(0, theme["header"].red() - 12), max(0, theme["header"].green() - 10), max(0, theme["header"].blue() - 8), 196)
        else:
            top = QColor(min(255, theme["header"].red() + 18), min(255, theme["header"].green() + 14), min(255, theme["header"].blue() + 10), 136)
            bottom = QColor(max(0, theme["bg"].red() - 10), max(0, theme["bg"].green() - 8), max(0, theme["bg"].blue() - 6), 172)
        if theme.get("sleek"):
            top = with_alpha(theme["selected_background"], 232) if active else QColor(255, 255, 255, 48)
            bottom = with_alpha(theme["panel_background_alt"], 184) if active else with_alpha(theme["panel_background"], 118)
            border = theme["focus_ring"] if active else theme["subtle_border"]
            self.draw_rounded_gradient_box(painter, rect, top, bottom, border, radius=theme.get("cell_radius", 12))
            return
        border = QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 140)
        self.draw_rounded_gradient_box(painter, rect, top, bottom, border, radius=6)

    def draw_arrow_button(self, painter, rect, label, theme):
        self.draw_rounded_gradient_box(
            painter,
            rect,
            QColor(theme["chrome_top"].red(), theme["chrome_top"].green(), theme["chrome_top"].blue(), 176),
            QColor(theme["chrome_bottom"].red(), theme["chrome_bottom"].green(), theme["chrome_bottom"].blue(), 196),
            QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 136),
            radius=8,
        )
        if self.skin_style() == "cable":
            self.draw_cable_text(painter, rect, label, QColor(248, 248, 240), QFont(guide_font_family("primary"), max(10, rect.height() - 12), QFont.Bold), Qt.AlignCenter)
        else:
            painter.setPen(theme["text"])
            painter.drawText(rect, Qt.AlignCenter, label)

    def draw_settings_panel(self, painter, panel, body_font, small_font, theme):
        draw_shared_mediawave_settings_panel(self, painter, panel, body_font, small_font, theme)

    def draw_streaming_home_view(self, painter, panel, footer_rect, title_font, body_font, small_font, theme):
        self.home_card_hit_rects = []
        hero_height = max(scaled_metric(166, self.ui_scale, 132), min(scaled_metric(208, self.ui_scale, 170), int(panel.height() * 0.23)))
        hero_rect = QRect(panel.left() + 18, panel.top() + 52, panel.width() - 36, hero_height)

        rows_top = hero_rect.bottom() + scaled_metric(64, self.ui_scale, 48)
        rows_bottom = footer_rect.top() - scaled_metric(22, self.ui_scale, 16)
        rows_rect = QRect(panel.left() + 18, rows_top, panel.width() - 36, max(80, rows_bottom - rows_top))
        sections = self.state.get("sections", [])
        layout_signature = (
            self.state.get("selected_section", 0),
            self.state.get("selected_item", 0),
            tuple((section.get("key", ""), len(section.get("items", []))) for section in sections),
        )
        if layout_signature != self.last_home_layout_debug_signature:
            self.last_home_layout_debug_signature = layout_signature
            self.debug_vault_layout(
                "home_view_state",
                selected_section=self.state.get("selected_section", 0),
                selected_item=self.state.get("selected_item", 0),
                section_count=len(sections),
                section_items=[len(section.get("items", [])) for section in sections],
            )
        if not sections:
            self.draw_panel(painter, rows_rect, theme, radius=12, inset=2)
            painter.setPen(theme["dark_text"])
            painter.setFont(title_font)
            painter.drawText(rows_rect, Qt.AlignCenter, "Load a catalog to build your Vault.")
            return

        row_gap = scaled_metric(22, self.ui_scale, 16)
        row_height = max(
            scaled_metric(198, self.ui_scale, 150),
            min(scaled_metric(228, self.ui_scale, 176), int(rows_rect.height() * 0.34)),
        )
        self.sync_home_view_targets(rows_rect, sections)
        section_item_indices = self.state.get("section_item_indices", {})
        painter.save()
        painter.setClipRect(rows_rect)
        base_y = rows_rect.top() - int(round(self.home_vertical_offset))
        fade_span = scaled_metric(56, self.ui_scale, 40)
        for section_index, section in enumerate(sections):
            row_rect = QRect(
                rows_rect.left(),
                base_y + section_index * (row_height + row_gap),
                rows_rect.width(),
                row_height,
            )
            if row_rect.bottom() < rows_rect.top() - row_gap or row_rect.top() > rows_rect.bottom() + row_gap:
                continue
            is_selected = (
                section_index == self.state.get("selected_section", 0)
                and not self.state.get("nav_focused", False)
                and not self.settings_open
            )
            opacity = 1.0
            if not is_selected:
                if row_rect.top() < rows_rect.top():
                    hidden_top = rows_rect.top() - row_rect.top()
                    opacity *= max(0.0, min(1.0, 1.0 - (hidden_top / max(1, fade_span))))
                if row_rect.bottom() > rows_rect.bottom():
                    hidden_bottom = row_rect.bottom() - rows_rect.bottom()
                    opacity *= max(0.0, min(1.0, 1.0 - (hidden_bottom / max(1, fade_span))))
                opacity = max(0.16, opacity)
            painter.save()
            if opacity < 0.999:
                painter.setOpacity(opacity)
            self.draw_stream_row(
                painter,
                row_rect,
                section,
                section_index,
                is_selected,
                section_item_indices.get(section_index, 0),
                title_font,
                body_font,
                small_font,
                theme,
            )
            painter.restore()
        painter.restore()
        painter.save()
        painter.setPen(Qt.NoPen)
        gap_cover = QRect(panel.left() + 18, hero_rect.bottom() + 2, panel.width() - 36, max(0, rows_rect.top() - hero_rect.bottom() - 2))
        painter.setBrush(QColor(theme["panel"].red(), theme["panel"].green(), theme["panel"].blue(), 252))
        painter.drawRect(gap_cover)
        painter.restore()
        self.draw_streaming_hero_transition(painter, hero_rect, self.state.get("hero", {}), title_font, body_font, small_font, theme)

    def draw_streaming_detail_view(self, painter, panel, footer_rect, title_font, body_font, small_font, theme):
        hero_rect = QRect(panel.left() + 18, panel.top() + 52, panel.width() - 36, max(scaled_metric(164, self.ui_scale, 136), min(scaled_metric(194, self.ui_scale, 156), int(panel.height() * 0.2))))
        self.draw_streaming_hero_transition(painter, hero_rect, self.state.get("detail", {}), title_font, body_font, small_font, theme, large=True)

        actions_rect = QRect(panel.left() + 18, hero_rect.bottom() + 12, panel.width() - 36, scaled_metric(54, self.ui_scale, 42))
        self.draw_streaming_action_row(
            painter,
            actions_rect,
            self.state.get("actions", []),
            self.state.get("action_selected", 0),
            self.state.get("detail_focus") == "actions",
            body_font,
            small_font,
            theme,
        )

        seasons_rect = QRect(panel.left() + 18, actions_rect.bottom() + 10, panel.width() - 36, scaled_metric(44, self.ui_scale, 34))
        self.draw_streaming_season_row(
            painter,
            seasons_rect,
            self.state.get("seasons", []),
            self.state.get("season_selected", 0),
            self.state.get("detail_focus") == "seasons",
            body_font,
            small_font,
            theme,
        )

        content_top = seasons_rect.bottom() + 12
        content_bottom = footer_rect.top() - scaled_metric(18, self.ui_scale, 14)
        content_rect = QRect(panel.left() + 18, content_top, panel.width() - 36, max(96, content_bottom - content_top))
        detail_w = max(scaled_metric(240, self.ui_scale, 196), int(content_rect.width() * 0.28))
        detail_rect = QRect(content_rect.left(), content_rect.top(), detail_w, content_rect.height())
        episodes_rect = QRect(detail_rect.right() + 12, content_rect.top(), content_rect.width() - detail_w - 12, content_rect.height())
        self.draw_streaming_detail_side_panel(
            painter,
            detail_rect,
            self.state.get("episode_detail", {}),
            title_font,
            body_font,
            small_font,
            theme,
        )
        self.draw_streaming_episode_list(
            painter,
            episodes_rect,
            self.state.get("episode_items", []),
            self.state.get("episode_selected", 0),
            self.state.get("detail_focus") == "episodes",
            title_font,
            body_font,
            small_font,
            theme,
        )

    def draw_streaming_hero_transition(self, painter, rect, detail, title_font, body_font, small_font, theme, large=False):
        self.draw_panel(painter, rect, theme, radius=14, inset=3)
        if self.feature_transition < 1.0 and self.feature_previous:
            painter.save()
            painter.setOpacity(max(0.0, 1.0 - self.feature_transition))
            self.draw_streaming_hero_content(painter, rect, self.feature_previous, title_font, body_font, small_font, theme, large=large)
            painter.restore()
        painter.save()
        painter.setOpacity(1.0 if self.feature_transition >= 1.0 else max(0.0, min(1.0, self.feature_transition)))
        self.draw_streaming_hero_content(painter, rect, detail, title_font, body_font, small_font, theme, large=large)
        painter.restore()

    def draw_streaming_hero_content(self, painter, rect, detail, title_font, body_font, small_font, theme, large=False):
        inner = rect.adjusted(12, 12, -12, -12)
        art_w = max(scaled_metric(176 if large else 154, self.ui_scale, 132), int(inner.width() * (0.24 if large else 0.2)))
        progress = float(detail.get("progress", 0.0) or 0.0)
        progress_label = (detail.get("progress_label") or "").strip()
        art_rect = QRect(inner.left(), inner.top(), art_w, inner.height())
        art_media_rect = art_rect
        copy_rect = QRect(art_rect.right() + 18, inner.top(), inner.width() - art_w - 18, inner.height())
        branding_w = 0
        branding_gap = scaled_metric(18, self.ui_scale, 14)
        if copy_rect.width() > scaled_metric(430, self.ui_scale, 320):
            branding_w = min(
                scaled_metric(228, self.ui_scale, 176),
                max(scaled_metric(172, self.ui_scale, 132), int(copy_rect.width() * 0.26)),
            )
        content_rect = QRect(copy_rect)
        branding_rect = QRect()
        if branding_w > 0 and (copy_rect.width() - branding_w - branding_gap) > scaled_metric(250, self.ui_scale, 190):
            branding_rect = QRect(
                copy_rect.right() - branding_w,
                copy_rect.top(),
                branding_w,
                min(copy_rect.height(), scaled_metric(116 if large else 98, self.ui_scale, 88)),
            )
            content_rect.setRight(branding_rect.left() - branding_gap)

        self.draw_streaming_art_placeholder(
            painter,
            art_media_rect,
            detail.get("title", ""),
            detail.get("badge", ""),
            theme,
            detail.get("artwork_path", ""),
            fit_mode="fit",
            show_badge=False,
        )

        badge_rect = QRect(content_rect.left(), content_rect.top(), min(content_rect.width(), scaled_metric(168, self.ui_scale, 128)), scaled_metric(26, self.ui_scale, 22))
        self.draw_badge(painter, badge_rect, QColor(255, 251, 224), QColor(236, 206, 108))
        painter.setFont(small_font)
        painter.setPen(QColor(52, 42, 12))
        painter.drawText(badge_rect, Qt.AlignCenter, detail.get("badge", "FEATURED"))

        title_top = badge_rect.bottom() + 10
        clearlogo = load_ui_pixmap(detail.get("clearlogo_path", ""))
        if not clearlogo.isNull():
            max_logo_w = content_rect.width()
            max_logo_h = scaled_metric(70 if large else 56, self.ui_scale, 50)
            scaled_logo = clearlogo.scaled(max_logo_w, max_logo_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_rect = QRect(content_rect.left(), title_top, min(content_rect.width(), scaled_logo.width()), scaled_logo.height())
            painter.drawPixmap(logo_rect, scaled_logo)
            title_top = logo_rect.bottom() + 10

        if not branding_rect.isNull():
            logo_rect = QRect(branding_rect.left(), branding_rect.top(), branding_rect.width(), scaled_metric(44, self.ui_scale, 32))
            self.draw_logo_watermark(painter, logo_rect, opacity=0.96)
            quote_rect = QRect(
                branding_rect.left(),
                logo_rect.bottom() + scaled_metric(6, self.ui_scale, 4),
                branding_rect.width(),
                branding_rect.height() - logo_rect.height() - scaled_metric(6, self.ui_scale, 4),
            )
            quote_font = QFont(
                guide_font_family("secondary") if self.skin_style() == "cable" else body_font.family(),
                max(body_font.pointSize() + 1, small_font.pointSize() + 1),
            )
            quote_font.setItalic(True)
            quote_text = "\"Step Into the Vault, Stay Awhile!\""
            if self.skin_style() == "cable":
                self.draw_cable_text(painter, quote_rect, quote_text, QColor(255, 233, 170), quote_font, Qt.AlignRight | Qt.AlignTop | Qt.TextWordWrap)
            else:
                painter.save()
                painter.setFont(quote_font)
                painter.setPen(QColor(244, 226, 168))
                painter.drawText(quote_rect, Qt.AlignRight | Qt.AlignTop | Qt.TextWordWrap, quote_text)
                painter.restore()

        painter.setPen(QColor(250, 252, 255))
        title_size = title_font.pointSize() + (5 if large else 3)
        painter.setFont(QFont(title_font.family(), title_size, QFont.Bold))
        title_rect = QRect(content_rect.left(), title_top, content_rect.width(), scaled_metric(70 if large else 54, self.ui_scale, 52))
        painter.drawText(title_rect, Qt.TextWordWrap, detail.get("title", ""))

        subtitle_rect = QRect(content_rect.left(), title_rect.bottom() + 6, content_rect.width(), scaled_metric(22, self.ui_scale, 18))
        meta_rect = QRect(content_rect.left(), subtitle_rect.bottom() + 8, content_rect.width(), scaled_metric(22, self.ui_scale, 18))
        summary_rect = QRect(content_rect.left(), meta_rect.bottom() + 10, content_rect.width(), content_rect.bottom() - meta_rect.bottom() - scaled_metric(8, self.ui_scale, 6))
        if self.skin_style() == "cable":
            cable_body_font = QFont(body_font.family(), max(body_font.pointSize() + 1, small_font.pointSize() + 1), QFont.DemiBold)
            self.draw_cable_text(painter, subtitle_rect, self.elide(painter, detail.get("subtitle", ""), subtitle_rect.width()), QColor(248, 248, 240), cable_body_font, Qt.AlignLeft | Qt.AlignVCenter)
            self.draw_cable_text(painter, meta_rect, self.elide(painter, detail.get("meta", ""), meta_rect.width()), QColor(214, 226, 252), small_font, Qt.AlignLeft | Qt.AlignVCenter)
            self.draw_cable_text(painter, summary_rect, detail.get("summary", ""), QColor(244, 244, 238), body_font, Qt.TextWordWrap)
        else:
            painter.setFont(QFont(body_font.family(), max(body_font.pointSize() + 1, small_font.pointSize() + 1), QFont.DemiBold))
            painter.setPen(theme["text"])
            painter.drawText(subtitle_rect, Qt.TextSingleLine, self.elide(painter, detail.get("subtitle", ""), subtitle_rect.width()))
            painter.setFont(small_font)
            painter.setPen(theme["muted"])
            painter.drawText(meta_rect, Qt.TextSingleLine, self.elide(painter, detail.get("meta", ""), meta_rect.width()))
            painter.setFont(body_font)
            painter.setPen(theme["dark_text"])
            painter.drawText(summary_rect, Qt.TextWordWrap, detail.get("summary", ""))

        if progress > 0:
            track_rect = QRect(art_media_rect.left(), art_media_rect.bottom() - scaled_metric(8, self.ui_scale, 6), art_media_rect.width(), scaled_metric(8, self.ui_scale, 6))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(12, 16, 24, 120))
            painter.drawRoundedRect(track_rect, 5, 5)
            fill_rect = QRect(track_rect.left(), track_rect.top(), max(8, int(track_rect.width() * max(0.0, min(1.0, progress)))), track_rect.height())
            painter.setBrush(QColor(255, 213, 97))
            painter.drawRoundedRect(fill_rect, 5, 5)
        if progress_label:
            label_w = min(art_media_rect.width() - 12, max(scaled_metric(82, self.ui_scale, 64), QFontMetrics(small_font).horizontalAdvance(progress_label) + 18))
            label_rect = QRect(art_media_rect.right() - label_w - 6, art_media_rect.bottom() - scaled_metric(30, self.ui_scale, 24), label_w, scaled_metric(18, self.ui_scale, 16))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(4, 6, 12, 196))
            painter.drawRoundedRect(label_rect, 6, 6)
            if self.skin_style() == "cable":
                self.draw_cable_text(painter, label_rect.adjusted(6, 0, -6, 0), progress_label.upper(), QColor(248, 248, 240), small_font, Qt.AlignCenter)
            else:
                painter.setFont(small_font)
                painter.setPen(QColor(248, 248, 240))
                painter.drawText(label_rect, Qt.AlignCenter, progress_label)

    def draw_stream_row(self, painter, rect, section, section_index, is_selected_section, selected_item, title_font, body_font, small_font, theme):
        self.draw_panel(painter, rect, theme, radius=12, inset=2)
        accent_rect = QRect(rect.left() + 10, rect.top() + 14, scaled_metric(6, self.ui_scale, 5), rect.height() - 28)
        painter.setPen(Qt.NoPen)
        if theme.get("sleek"):
            painter.setBrush(theme["selected_background"] if is_selected_section else with_alpha(theme["header_background"], 170))
        else:
            painter.setBrush(QColor(255, 220, 112, 235) if is_selected_section else QColor(theme["header"].red(), theme["header"].green(), theme["header"].blue(), 190))
        painter.drawRoundedRect(accent_rect, max(2, accent_rect.width() // 2), max(2, accent_rect.width() // 2))
        label_rect = QRect(accent_rect.right() + 12, rect.top() + 10, rect.width() - 34, scaled_metric(24, self.ui_scale, 19))
        sub_rect = QRect(accent_rect.right() + 12, label_rect.bottom() + 3, rect.width() - 36, scaled_metric(18, self.ui_scale, 15))
        painter.setFont(QFont(title_font.family(), max(title_font.pointSize() - 1, body_font.pointSize() + 1), QFont.Bold))
        if theme.get("sleek"):
            painter.setPen(theme["primary_text"])
        else:
            painter.setPen(QColor(255, 248, 232) if self.skin_style() == "cable" else (QColor(52, 36, 12) if is_selected_section else theme["dark_text"]))
        painter.drawText(label_rect, Qt.TextSingleLine, section.get("title", ""))
        painter.setFont(small_font)
        painter.setPen(QColor(theme["text"].red(), theme["text"].green(), theme["text"].blue(), 215) if self.skin_style() == "cable" else theme["muted"])
        painter.drawText(sub_rect, Qt.TextSingleLine, self.elide(painter, section.get("subtitle", ""), sub_rect.width()))

        cards_rect = QRect(accent_rect.right() + 12, sub_rect.bottom() + 10, rect.width() - (accent_rect.width() + 28), rect.bottom() - sub_rect.bottom() - 16)
        self.draw_stream_card_strip(
            painter,
            cards_rect,
            section.get("items", []),
            self.stream_row_key(section, section_index),
            section_index,
            selected_item,
            is_selected_section,
            body_font,
            small_font,
            theme,
        )

    def draw_stream_card_strip(self, painter, rect, items, row_key, section_index, selected_index, row_focused, body_font, small_font, theme):
        if not items:
            return
        viewport = rect.adjusted(scaled_metric(8, self.ui_scale, 6), 0, -scaled_metric(8, self.ui_scale, 6), 0)
        card_w, card_h, gap = self.stream_card_metrics(viewport)
        total_width = max(0, len(items) * (card_w + gap) - gap)
        max_offset = max(0.0, float(total_width - viewport.width()))
        offset_value = self.home_row_offsets.get(row_key, 0.0)
        show_left = offset_value > 1.0
        show_right = offset_value < max_offset - 1.0
        lane_surface = QPixmap(max(1, viewport.width()), max(1, viewport.height()))
        lane_surface.fill(Qt.transparent)
        lane_painter = QPainter(lane_surface)
        lane_painter.setRenderHint(QPainter.Antialiasing, True)
        lane_painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        lane_painter.setClipRect(QRect(0, 0, viewport.width(), viewport.height()))
        visible_indices = []
        for index, item in enumerate(items):
            card_rect = QRect((index * (card_w + gap)) - int(round(offset_value)), 0, card_w, card_h)
            if card_rect.right() <= 0 or card_rect.left() >= viewport.width():
                continue
            visible_indices.append(index)
            focused = row_focused and index == selected_index
            self.draw_stream_card(lane_painter, card_rect, item, focused, body_font, small_font, theme)
            world_rect = QRect(viewport.left() + card_rect.left(), viewport.top() + card_rect.top(), card_rect.width(), card_rect.height())
            self.home_card_hit_rects.append((self.map_interactive_rect(world_rect), section_index, index))
        lane_painter.end()
        painter.drawPixmap(viewport.topLeft(), lane_surface)
        self.draw_horizontal_edge_fades(painter, viewport, theme, show_left, show_right)
        if row_focused:
            self.debug_vault_layout(
                "row_clip_state",
                row_key=row_key,
                section_index=section_index,
                item_count=len(items),
                visible_order=visible_indices,
                selected_index=selected_index,
                selected_visible=selected_index in visible_indices,
                selected_title=(items[selected_index].get("title", "") if 0 <= selected_index < len(items) else ""),
            )

    def draw_stream_card(self, painter, rect, item, focused, body_font, small_font, theme):
        draw_rect = rect.adjusted(0, 4 if focused else 10, 0, 0)
        if focused:
            draw_rect = draw_rect.adjusted(-2, -8, 2, 2)
        if theme.get("sleek"):
            top = with_alpha(theme["selected_background"], 226) if focused else with_alpha(theme["modern_surface"], 174)
            bottom = with_alpha(theme["selected_background"].darker(108), 220) if focused else with_alpha(theme["modern_surface_alt"], 202)
            border = theme["focus_ring"] if focused else theme["subtle_border"]
            radius = theme.get("card_radius", 12)
        else:
            top = QColor(255, 249, 210, 242) if focused else QColor(theme["chrome_top"].red(), theme["chrome_top"].green(), theme["chrome_top"].blue(), 214)
            bottom = QColor(233, 206, 110, 246) if focused else QColor(theme["chrome_bottom"].red(), theme["chrome_bottom"].green(), theme["chrome_bottom"].blue(), 224)
            border = QColor(58, 42, 14) if focused else QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 120)
            radius = 16 if focused else 14
        self.draw_rounded_gradient_box(painter, draw_rect, top, bottom, border, radius=radius)
        if focused:
            painter.save()
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(theme["focus_ring"] if theme.get("sleek") else QColor(255, 255, 240, 232), 2 if theme.get("sleek") else 3))
            painter.drawRoundedRect(draw_rect.adjusted(1, 1, -1, -1), radius, radius)
            if theme.get("sleek"):
                painter.setPen(QPen(theme["focus_glow"], 5))
                painter.drawRoundedRect(draw_rect.adjusted(4, 4, -4, -4), radius, radius)
            else:
                painter.setPen(QPen(QColor(255, 244, 184, 72), 9))
                painter.drawRoundedRect(draw_rect.adjusted(4, 4, -4, -4), radius, radius)
            painter.restore()

        art_rect = QRect(draw_rect.left() + 12, draw_rect.top() + 12, draw_rect.width() - 24, max(scaled_metric(82, self.ui_scale, 64), int(draw_rect.height() * 0.48)))
        self.draw_streaming_art_placeholder(
            painter,
            art_rect,
            item.get("title", ""),
            item.get("badge", ""),
            theme,
            item.get("artwork_path", ""),
        )

        title_rect = QRect(draw_rect.left() + 14, art_rect.bottom() + 10, draw_rect.width() - 28, scaled_metric(46, self.ui_scale, 36))
        painter.setFont(QFont(body_font.family(), body_font.pointSize() + 3, QFont.Bold))
        painter.setPen(theme["selected_text"] if focused and theme.get("sleek") else (theme["dark_text"] if focused else theme["primary_text"] if theme.get("sleek") else QColor(248, 250, 244)))
        painter.drawText(title_rect, Qt.TextWordWrap, item.get("title", ""))

        subtitle_rect = QRect(draw_rect.left() + 14, title_rect.bottom() + 4, draw_rect.width() - 28, scaled_metric(18, self.ui_scale, 15))
        painter.setFont(small_font)
        painter.setPen(theme["selected_text"] if focused and theme.get("sleek") else (theme["muted_text"] if theme.get("sleek") else (theme["dark_text"] if focused else theme["text"])))
        painter.drawText(subtitle_rect, Qt.TextSingleLine, self.elide(painter, item.get("subtitle", ""), subtitle_rect.width()))

        if item.get("progress", 0.0) > 0:
            track_rect = QRect(art_rect.left(), art_rect.bottom() - scaled_metric(8, self.ui_scale, 6), art_rect.width(), scaled_metric(8, self.ui_scale, 6))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(12, 16, 24, 120))
            painter.drawRoundedRect(track_rect, 4, 4)
            fill_rect = QRect(track_rect.left(), track_rect.top(), max(8, int(track_rect.width() * item.get("progress", 0.0))), track_rect.height())
            painter.setBrush(QColor(255, 213, 97))
            painter.drawRoundedRect(fill_rect, 4, 4)
            progress_label = (item.get("progress_label") or "").strip()
            if progress_label:
                pill_w = min(art_rect.width() - 10, max(scaled_metric(70, self.ui_scale, 54), QFontMetrics(small_font).horizontalAdvance(progress_label) + 14))
                pill_rect = QRect(art_rect.right() - pill_w - 5, art_rect.bottom() - scaled_metric(28, self.ui_scale, 22), pill_w, scaled_metric(16, self.ui_scale, 14))
                painter.setBrush(QColor(4, 6, 12, 196))
                painter.drawRoundedRect(pill_rect, 5, 5)
                if self.skin_style() == "cable":
                    self.draw_cable_text(painter, pill_rect, progress_label.upper(), QColor(248, 248, 240), small_font, Qt.AlignCenter)
                else:
                    painter.setFont(small_font)
                    painter.setPen(QColor(248, 248, 240))
                    painter.drawText(pill_rect, Qt.AlignCenter, progress_label)

    def draw_streaming_art_placeholder(self, painter, rect, title, badge, theme, artwork_path="", fit_mode="cover", show_badge=True):
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(
            0.0,
            QColor(
                max(0, theme["header"].red() - 22),
                max(0, theme["header"].green() - 18),
                max(0, theme["header"].blue() - 10),
                255,
            ),
        )
        grad.setColorAt(
            0.55,
            QColor(
                min(255, theme["header"].red() + 14),
                min(255, theme["header"].green() + 12),
                min(255, theme["header"].blue() + 10),
                224,
            ),
        )
        grad.setColorAt(
            1.0,
            QColor(
                max(0, theme["bg"].red() - 18),
                max(0, theme["bg"].green() - 18),
                max(0, theme["bg"].blue() - 10),
                255,
            ),
        )
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.save()
        painter.setClipPath(path)
        pixmap = load_ui_pixmap(artwork_path)
        if not pixmap.isNull():
            aspect_mode = Qt.KeepAspectRatio if fit_mode == "fit" else Qt.KeepAspectRatioByExpanding
            scaled = pixmap.scaled(rect.size(), aspect_mode, Qt.SmoothTransformation)
            if fit_mode == "fit":
                draw_rect = QRect(
                    rect.left() + max(0, (rect.width() - scaled.width()) // 2),
                    rect.top() + max(0, (rect.height() - scaled.height()) // 2),
                    scaled.width(),
                    scaled.height(),
                )
                painter.fillRect(rect, QColor(8, 12, 18, 190))
                painter.drawPixmap(draw_rect, scaled)
            else:
                src_x = max(0, (scaled.width() - rect.width()) // 2)
                src_y = max(0, (scaled.height() - rect.height()) // 2)
                painter.drawPixmap(rect, scaled, QRect(src_x, src_y, rect.width(), rect.height()))
            overlay = QLinearGradient(rect.topLeft(), rect.bottomRight())
            overlay.setColorAt(0.0, QColor(8, 12, 32, 32))
            overlay.setColorAt(1.0, QColor(4, 6, 20, 118))
            painter.fillRect(rect, overlay)
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
            painter.setBrush(grad)
            painter.drawRoundedRect(rect, 10, 10)
            initials = "".join(ch for ch in re.findall(r"[A-Za-z0-9]", title.upper())[:2]) or "MW"
            placeholder_family = theme.get("font_primary", "Trebuchet MS") if theme.get("sleek") else guide_font_family("primary")
            painter.setFont(QFont(placeholder_family, max(scaled_metric(26, self.ui_scale, 20), rect.height() // 3), QFont.Bold))
            painter.setPen(QColor(255, 255, 255, 210))
            painter.drawText(rect, Qt.AlignCenter, initials)
        painter.restore()
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 10, 10)
        if badge and show_badge:
            badge_rect = QRect(rect.left() + 8, rect.top() + 8, min(rect.width() - 16, scaled_metric(92, self.ui_scale, 72)), scaled_metric(18, self.ui_scale, 16))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 244, 188, 220))
            painter.drawRoundedRect(badge_rect, 8, 8)
            badge_family = theme.get("font_secondary", "Trebuchet MS") if theme.get("sleek") else guide_font_family("secondary")
            painter.setFont(QFont(badge_family, max(scaled_metric(8, self.ui_scale, 7), 8), QFont.Bold))
            painter.setPen(QColor(36, 28, 8))
            painter.drawText(badge_rect, Qt.AlignCenter, badge)

    def draw_streaming_action_row(self, painter, rect, actions, selected_index, focused, body_font, small_font, theme):
        self.draw_panel(painter, rect, theme, radius=12, inset=2)
        inner = rect.adjusted(12, 10, -12, -10)
        gap = scaled_metric(12, self.ui_scale, 10)
        button_w = max(scaled_metric(170, self.ui_scale, 140), (inner.width() - gap * max(0, len(actions) - 1)) // max(1, len(actions)))
        for index, action in enumerate(actions):
            button_rect = QRect(inner.left() + index * (button_w + gap), inner.top(), button_w, inner.height())
            active = focused and index == selected_index
            if theme.get("sleek"):
                top = with_alpha(theme["selected_background"].lighter(106), 232) if active else QColor(255, 255, 255, 46)
                bottom = with_alpha(theme["panel_background_alt"], 184) if active else with_alpha(theme["panel_background"], 116)
                border = theme["focus_ring"] if active else theme["subtle_border"]
            else:
                top = QColor(255, 249, 210, 236) if active else QColor(theme["chrome_top"].red(), theme["chrome_top"].green(), theme["chrome_top"].blue(), 175)
                bottom = QColor(233, 206, 110, 242) if active else QColor(theme["chrome_bottom"].red(), theme["chrome_bottom"].green(), theme["chrome_bottom"].blue(), 195)
                border = QColor(58, 42, 14) if active else QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 120)
            self.draw_rounded_gradient_box(
                painter,
                button_rect,
                top,
                bottom,
                border,
                radius=12,
            )
            if active:
                painter.save()
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(theme["focus_ring"] if theme.get("sleek") else QColor(255, 255, 240, 220), 3))
                painter.drawRoundedRect(button_rect.adjusted(1, 1, -1, -1), 12, 12)
                painter.restore()
            painter.setFont(QFont(body_font.family(), body_font.pointSize() + 1, QFont.Bold))
            painter.setPen(theme["selected_text"] if active and theme.get("sleek") else (theme["dark_text"] if active else theme["text"]))
            painter.drawText(button_rect.adjusted(14, 0, -14, -button_rect.height() // 2 + 2), Qt.AlignLeft | Qt.AlignVCenter, action.get("label", ""))
            painter.setFont(small_font)
            painter.drawText(button_rect.adjusted(14, button_rect.height() // 2 - 4, -14, 0), Qt.AlignLeft | Qt.AlignVCenter, self.elide(painter, action.get("meta", ""), button_rect.width() - 28))

    def draw_streaming_season_row(self, painter, rect, seasons, selected_index, focused, body_font, small_font, theme):
        self.draw_panel(painter, rect, theme, radius=12, inset=2)
        inner = rect.adjusted(12, 8, -12, -8)
        x = inner.left()
        for index, season in enumerate(seasons):
            width = max(scaled_metric(118, self.ui_scale, 88), QFontMetrics(body_font).horizontalAdvance(season.get("label", "")) + scaled_metric(42, self.ui_scale, 34))
            pill_rect = QRect(x, inner.top(), width, inner.height())
            active = focused and index == selected_index
            self.draw_rounded_gradient_box(
                painter,
                pill_rect,
                QColor(255, 249, 210, 236) if active else QColor(theme["chrome_top"].red(), theme["chrome_top"].green(), theme["chrome_top"].blue(), 170),
                QColor(233, 206, 110, 242) if active else QColor(theme["chrome_bottom"].red(), theme["chrome_bottom"].green(), theme["chrome_bottom"].blue(), 190),
                QColor(58, 42, 14) if active else QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 120),
                radius=16,
            )
            painter.setFont(body_font)
            painter.setPen(theme["dark_text"] if active else theme["text"])
            painter.drawText(pill_rect.adjusted(16, 0, -16, 0), Qt.AlignLeft | Qt.AlignVCenter, season.get("label", ""))
            painter.setFont(small_font)
            painter.drawText(pill_rect.adjusted(0, 0, -14, 0), Qt.AlignRight | Qt.AlignVCenter, str(season.get("count", "")))
            x = pill_rect.right() + scaled_metric(10, self.ui_scale, 8)
            if x > inner.right():
                break

    def draw_streaming_detail_side_panel(self, painter, rect, detail, title_font, body_font, small_font, theme):
        self.draw_panel(painter, rect, theme, radius=12, inset=2)
        inner = rect.adjusted(14, 14, -14, -14)
        title_color = QColor(244, 246, 255) if self.skin_style() == "cable" else readable_text_color(theme["panel"])
        meta_color = QColor(220, 228, 242) if self.skin_style() == "cable" else readable_text_color(theme["panel"], light=QColor(220, 228, 242), dark=QColor(72, 64, 36), threshold=0.42)
        title_rect = QRect(inner.left(), inner.top(), inner.width(), scaled_metric(52, self.ui_scale, 40))
        painter.setFont(QFont(title_font.family(), title_font.pointSize() + 2, QFont.Bold))
        painter.setPen(title_color)
        painter.drawText(title_rect, Qt.TextWordWrap, detail.get("title", ""))
        meta_rect = QRect(inner.left(), title_rect.bottom() + 4, inner.width(), scaled_metric(20, self.ui_scale, 16))
        painter.setFont(small_font)
        painter.setPen(meta_color)
        painter.drawText(meta_rect, Qt.TextSingleLine, self.elide(painter, detail.get("meta", ""), meta_rect.width()))
        thumb_rect = QRect(inner.left(), meta_rect.bottom() + 10, inner.width(), max(scaled_metric(116, self.ui_scale, 90), int(inner.height() * 0.28)))
        pixmap = detail.get("thumbnail", QPixmap())
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self.draw_streaming_art_placeholder(painter, thumb_rect, detail.get("title", ""), "", theme, artwork_path="", fit_mode="cover", show_badge=False)
            scaled = pixmap.scaled(thumb_rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            src_x = max(0, (scaled.width() - thumb_rect.width()) // 2)
            src_y = max(0, (scaled.height() - thumb_rect.height()) // 2)
            painter.save()
            clip = QPainterPath()
            clip.addRoundedRect(thumb_rect, 10, 10)
            painter.setClipPath(clip)
            painter.drawPixmap(thumb_rect, scaled, QRect(src_x, src_y, thumb_rect.width(), thumb_rect.height()))
            painter.restore()
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(thumb_rect, 10, 10)
        else:
            self.draw_streaming_art_placeholder(painter, thumb_rect, detail.get("title", ""), "", theme, fit_mode="cover", show_badge=False)
        body_rect = QRect(inner.left(), thumb_rect.bottom() + 10, inner.width(), inner.bottom() - thumb_rect.bottom() - 10)
        painter.setFont(body_font)
        painter.setPen(meta_color)
        painter.drawText(body_rect, Qt.TextWordWrap, detail.get("summary", ""))

    def draw_streaming_episode_list(self, painter, rect, items, selected_index, focused, title_font, body_font, small_font, theme):
        self.draw_panel(painter, rect, theme, radius=12, inset=2)
        header_rect = rect.adjusted(14, 10, -14, -rect.height() + 30)
        header_color = QColor(244, 246, 255) if self.skin_style() == "cable" else readable_text_color(theme["panel"])
        inactive_title = QColor(248, 250, 244) if self.skin_style() == "cable" else readable_text_color(theme["chrome_bottom"], light=QColor(248, 250, 244), dark=QColor(34, 28, 14), threshold=0.48)
        inactive_meta = QColor(222, 230, 242) if self.skin_style() == "cable" else readable_text_color(theme["chrome_bottom"], light=QColor(222, 230, 242), dark=QColor(74, 64, 34), threshold=0.55)
        painter.setFont(QFont(title_font.family(), max(title_font.pointSize(), body_font.pointSize() + 2), QFont.Bold))
        painter.setPen(header_color)
        painter.drawText(header_rect, Qt.AlignLeft | Qt.AlignVCenter, "Episodes")
        painter.setFont(small_font)
        painter.setPen(inactive_meta)
        painter.drawText(header_rect, Qt.AlignRight | Qt.AlignVCenter, f"{len(items)} available")
        list_rect = rect.adjusted(12, 40, -12, -12)
        row_h = max(scaled_metric(86, self.ui_scale, 70), min(scaled_metric(102, self.ui_scale, 82), list_rect.height() // 4 if list_rect.height() > 0 else scaled_metric(86, self.ui_scale, 70)))
        total_height = max(0, len(items) * row_h)
        max_offset = max(0.0, float(total_height - list_rect.height()))
        focus_band = max(row_h, int(list_rect.height() * 0.24))
        target_offset = max(0.0, min(max_offset, float((selected_index * row_h) - focus_band)))
        if abs(target_offset - self.episode_list_target) > 0.5:
            self.episode_list_target = target_offset
            self.start_stream_animation()
        active_text = QColor(40, 28, 10)
        painter.save()
        painter.setClipRect(list_rect)
        for index, item in enumerate(items):
            row_rect = QRect(
                list_rect.left(),
                list_rect.top() + (index * row_h) - int(round(self.episode_list_offset)),
                list_rect.width(),
                row_h - 8,
            )
            if row_rect.bottom() < list_rect.top() - row_h or row_rect.top() > list_rect.bottom() + row_h:
                continue
            active = focused and index == selected_index
            self.draw_rounded_gradient_box(
                painter,
                row_rect,
                QColor(255, 249, 210, 236) if active else QColor(theme["chrome_top"].red(), theme["chrome_top"].green(), theme["chrome_top"].blue(), 150),
                QColor(233, 206, 110, 242) if active else QColor(theme["chrome_bottom"].red(), theme["chrome_bottom"].green(), theme["chrome_bottom"].blue(), 180),
                QColor(58, 42, 14) if active else QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 120),
                radius=10,
            )
            if active:
                painter.save()
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(255, 255, 240, 220), 3))
                painter.drawRoundedRect(row_rect.adjusted(1, 1, -1, -1), 10, 10)
                painter.restore()
            top_line = QRect(row_rect.left() + 14, row_rect.top() + 8, row_rect.width() - 28, scaled_metric(18, self.ui_scale, 15))
            title_line = QRect(row_rect.left() + 14, top_line.bottom() + 4, row_rect.width() - 28, scaled_metric(24, self.ui_scale, 20))
            summary_line = QRect(row_rect.left() + 14, title_line.bottom() + 4, row_rect.width() - 28, scaled_metric(18, self.ui_scale, 16))
            painter.setFont(small_font)
            painter.setPen(active_text if active else inactive_meta)
            painter.drawText(top_line, Qt.AlignLeft | Qt.AlignVCenter, self.elide(painter, item.get("meta", ""), int(top_line.width() * 0.58)))
            painter.drawText(top_line, Qt.AlignRight | Qt.AlignVCenter, self.elide(painter, item.get("runtime", ""), int(top_line.width() * 0.36)))
            painter.setFont(QFont(body_font.family(), body_font.pointSize() + 2, QFont.Bold))
            painter.setPen(active_text if active else inactive_title)
            painter.drawText(title_line, Qt.AlignLeft | Qt.AlignVCenter, self.elide(painter, item.get("label", ""), title_line.width()))
            painter.setFont(small_font)
            painter.setPen(active_text if active else inactive_meta)
            painter.drawText(summary_line, Qt.AlignLeft | Qt.AlignVCenter, self.elide(painter, item.get("summary", ""), summary_line.width()))
            progress = float(item.get("progress", 0.0) or 0.0)
            if progress > 0:
                track_rect = QRect(row_rect.left() + 14, row_rect.bottom() - scaled_metric(14, self.ui_scale, 10), row_rect.width() - 28, scaled_metric(7, self.ui_scale, 6))
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(10, 12, 18, 110))
                painter.drawRoundedRect(track_rect, 4, 4)
                fill_rect = QRect(track_rect.left(), track_rect.top(), max(8, int(track_rect.width() * progress)), track_rect.height())
                painter.setBrush(QColor(255, 213, 97))
                painter.drawRoundedRect(fill_rect, 4, 4)
        painter.restore()
        self.draw_vertical_edge_fades(
            painter,
            list_rect,
            theme,
            self.episode_list_offset > 1.0,
            self.episode_list_offset < max_offset - 1.0,
        )

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if self.settings_open:
            if self.skin_prev_rect.contains(pos):
                self.skinStepRequested.emit(-1)
                event.accept()
                return
            if self.skin_next_rect.contains(pos):
                self.skinStepRequested.emit(1)
                event.accept()
                return
            if self.theme_prev_rect.contains(pos):
                self.themeStepRequested.emit(-1)
                event.accept()
                return
            if self.theme_next_rect.contains(pos):
                self.themeStepRequested.emit(1)
                event.accept()
                return
            if self.profile_prev_rect.contains(pos):
                self.profileStepRequested.emit(-1)
                event.accept()
                return
            if self.profile_next_rect.contains(pos):
                self.profileStepRequested.emit(1)
                event.accept()
                return
            if self.close_action_rect.contains(pos):
                self.settingsCloseRequested.emit()
                event.accept()
                return
        for index, rect in enumerate(self.footer_button_rects):
            if rect.contains(pos):
                self.footerNavRequested.emit(index)
                event.accept()
                return
        if self.state.get("view") == "home":
            for rect, section_index, item_index in self.home_card_hit_rects:
                if rect.contains(pos):
                    self.homeCardRequested.emit(section_index, item_index)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        event.ignore()
        super().keyPressEvent(event)

    def draw_feature_panel(self, painter, rect, detail, title_font, body_font, small_font, theme, compact=False, show_logo=True):
        if self.skin_style() == "cable":
            self.draw_panel(painter, rect, theme, radius=1, inset=1)
            hero_rect = rect.adjusted(8, 8, -8, -8)
            hero_base = theme["app_background"] if theme.get("starfield") else theme["panel_background"]
            hero_fill = QColor(hero_base.red(), hero_base.green(), hero_base.blue(), 255)
            painter.fillRect(hero_rect, hero_fill)
            if theme.get("starfield"):
                self.draw_starfield(painter, hero_rect, theme)
            if show_logo:
                logo_rect = QRect(hero_rect.left() + 12, hero_rect.top() + 8, min(scaled_metric(220, self.ui_scale, 140), hero_rect.width() - 24), scaled_metric(44, self.ui_scale, 28))
                logo = load_brand_logo(logo_rect.width(), logo_rect.height(), CLASSIC_APP_LOGO_PATH)
                if not logo.isNull():
                    painter.drawPixmap(logo_rect.left(), logo_rect.top(), logo)
                content_top = logo_rect.bottom() + scaled_metric(10, self.ui_scale, 8)
            else:
                content_top = hero_rect.top() + scaled_metric(14, self.ui_scale, 10)

            if not compact:
                painter.setFont(title_font)
                painter.setPen(theme["accent"])
                title_rect = QRect(hero_rect.left() + 12, content_top, hero_rect.width() - 24, scaled_metric(54, self.ui_scale, 40))
                painter.drawText(title_rect, Qt.TextWordWrap, detail.get("title", f"{APP_NAME} VAULT").upper())
                painter.setFont(small_font)
                painter.setPen(theme["info_overlay_text"])
                meta_rect = QRect(hero_rect.left() + 12, title_rect.bottom() + 4, hero_rect.width() - 24, scaled_metric(18, self.ui_scale, 14))
                painter.drawText(meta_rect, Qt.AlignLeft | Qt.AlignVCenter, detail.get("meta", "").upper())
                summary_rect = QRect(rect.left() + 12, hero_rect.bottom() + 10, rect.width() - 24, rect.bottom() - hero_rect.bottom() - 18)
                if summary_rect.height() > 16:
                    painter.setFont(body_font)
                    painter.setPen(theme["info_overlay_text"])
                    painter.drawText(summary_rect, Qt.TextWordWrap, detail.get("summary", ""))
            return
        self.draw_panel(painter, rect, theme, radius=12, inset=2)
        hero_h = (rect.height() - 24) if compact else min(rect.height() - 24, 214)
        hero_rect = QRect(rect.left() + 12, rect.top() + 12, rect.width() - 24, hero_h)
        hero_grad = QLinearGradient(hero_rect.topLeft(), hero_rect.bottomRight())
        hero_grad.setColorAt(0.0, QColor(min(255, theme["header"].red() + 18), min(255, theme["header"].green() + 14), min(255, theme["header"].blue() + 12), 214))
        hero_grad.setColorAt(0.55, QColor(max(0, theme["header"].red() - 8), max(0, theme["header"].green() - 6), max(0, theme["header"].blue() - 4), 224))
        hero_grad.setColorAt(1.0, QColor(max(0, theme["bg"].red() - 10), max(0, theme["bg"].green() - 8), max(0, theme["bg"].blue() - 6), 230))
        painter.setPen(QPen(QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 120), 1))
        painter.setBrush(hero_grad)
        painter.drawRoundedRect(hero_rect, 14, 14)
        show_logo = detail.get("show_logo", show_logo)
        show_badge = detail.get("show_badge", True)
        if show_logo:
            logo_rect = QRect(hero_rect.left() + 24, hero_rect.top() + 18, hero_rect.width() - 48, 54 if compact else 64)
            self.draw_logo_watermark(painter, logo_rect, opacity=0.98 if compact else 0.94)
        else:
            logo_rect = QRect(hero_rect.left() + 24, hero_rect.top() + 6, hero_rect.width() - 48, 0)

        if compact:
            return

        content_top = logo_rect.bottom() + (10 if show_logo else 18)
        if show_badge:
            badge_rect = QRect(hero_rect.left() + 14, content_top, 110, 24)
            self.draw_badge(painter, badge_rect, QColor(255, 251, 224), QColor(236, 206, 108))
            painter.setFont(small_font)
            painter.setPen(QColor(52, 42, 12))
            painter.drawText(badge_rect, Qt.AlignCenter, "FEATURED")
            title_top = badge_rect.bottom() + 10
        else:
            badge_rect = QRect(hero_rect.left() + 14, content_top, 0, 0)
            title_top = content_top

        painter.setPen(QColor(250, 252, 255))
        painter.setFont(title_font)
        title_text = detail.get("title", f"{APP_NAME} Vault")
        title_rect = QRect(hero_rect.left() + 14, title_top, hero_rect.width() - 28, 92)
        title_bounds = painter.boundingRect(title_rect, Qt.TextWordWrap, title_text)
        title_draw_rect = QRect(
            title_rect.left(),
            title_rect.top(),
            title_rect.width(),
            min(title_rect.height(), max(34, title_bounds.height())),
        )
        painter.drawText(title_draw_rect, Qt.TextWordWrap, title_text)
        painter.setFont(small_font)
        meta_rect = QRect(hero_rect.left() + 14, title_draw_rect.bottom() + 10, hero_rect.width() - 28, 24)
        painter.drawText(meta_rect, Qt.TextSingleLine, self.elide(painter, detail.get("meta", ""), meta_rect.width()))

        copy_top = max(hero_rect.bottom() + 18, meta_rect.bottom() + 14)
        copy_rect = QRect(rect.left() + 16, copy_top, rect.width() - 32, rect.bottom() - copy_top - 18)
        if (not compact) and copy_rect.height() >= (painter.fontMetrics().height() + 10):
            painter.setFont(body_font)
            painter.setPen(theme["dark_text"])
            painter.drawText(copy_rect, Qt.TextWordWrap, detail.get("summary", ""))

    def draw_big_grid(self, painter, rect, items, selected_index, small_font, body_font, theme):
        cols = 2
        gap = 12
        item_h = 54
        item_w = (rect.width() - gap) // cols
        rows_fit = max(1, rect.height() // (item_h + gap))
        per_page = rows_fit * cols
        start = max(0, (selected_index // max(1, per_page)) * per_page)
        visible = items[start:start + per_page]
        for offset, item in enumerate(visible):
            idx = start + offset
            row = offset // cols
            col = offset % cols
            item_rect = QRect(rect.left() + col * (item_w + gap), rect.top() + row * (item_h + gap), item_w, item_h)
            selected = idx == selected_index
            self.draw_grid_button(painter, item_rect, item.get("label", ""), item.get("meta", ""), selected, selected, body_font, small_font, theme)

    def draw_grid_button(self, painter, rect, label, meta, selected, focused, body_font, small_font, theme):
        if self.skin_style() == "cable":
            fill = theme["selected"] if selected else theme["row_b"]
            border = theme["guide_selected_border"] if selected else theme["guide_grid_line"]
            painter.setPen(QPen(border, 1))
            painter.setBrush(fill)
            painter.drawRect(rect)
            if focused:
                painter.setPen(QPen(theme["focus_ring"], 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
            painter.setPen(theme["selected_text"] if selected else theme["guide_program_cell_text"])
            painter.setFont(QFont(body_font.family(), body_font.pointSize(), QFont.Bold))
            painter.drawText(rect.adjusted(8, 6, -8, -rect.height() + 24), Qt.TextWordWrap, label.upper())
            if meta:
                painter.setFont(small_font)
                painter.drawText(rect.adjusted(8, 26, -8, -6), Qt.TextWordWrap, meta.upper())
            return
        if selected:
            top = QColor(255, 249, 210, 236)
            bottom = QColor(233, 206, 110, 242)
            border = QColor(58, 42, 14)
            text_color = theme["dark_text"]
        else:
            top = QColor(min(255, theme["header"].red() + 20), min(255, theme["header"].green() + 16), min(255, theme["header"].blue() + 14), 220)
            bottom = QColor(max(0, theme["header"].red() - 10), max(0, theme["header"].green() - 8), max(0, theme["header"].blue() - 6), 230)
            border = QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 126)
            text_color = QColor(248, 250, 244)
        self.draw_rounded_gradient_box(painter, rect, top, bottom, border, radius=13)
        if focused:
            painter.save()
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 240, 220), 3))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 13, 13)
            painter.restore()
        painter.setPen(text_color)
        painter.setFont(QFont(body_font.family(), body_font.pointSize() + 1, QFont.Bold))
        painter.drawText(rect.adjusted(16, 8, -16, -rect.height() + 30), Qt.TextSingleLine, self.elide(painter, label, rect.width() - 32))
        if meta:
            painter.setFont(small_font)
            painter.drawText(rect.adjusted(16, 28, -16, -8), Qt.TextSingleLine, self.elide(painter, meta, rect.width() - 32))

    def draw_action_buttons(self, painter, rect, actions, selected_index, focused, body_font, theme):
        if not actions:
            return
        gap = 12
        button_w = (rect.width() - (gap * (len(actions) - 1))) // len(actions)
        for index, action in enumerate(actions):
            button_rect = QRect(rect.left() + index * (button_w + gap), rect.top(), button_w, rect.height())
            selected = index == selected_index
            self.draw_grid_button(
                painter,
                button_rect,
                action.get("label", ""),
                action.get("meta", ""),
                selected,
                focused and selected,
                body_font,
                QFont(body_font.family(), max(8, body_font.pointSize() - 1), QFont.Bold),
                theme,
            )

    def draw_episode_cards(self, painter, rect, items, small_font, body_font, theme):
        if not items:
            return
        gap = 12
        cols = 2
        card_w = (rect.width() - gap) // cols
        card_h = 96
        visible = items[:4]
        for offset, item in enumerate(visible):
            row = offset // cols
            col = offset % cols
            card_rect = QRect(rect.left() + col * (card_w + gap), rect.top() + row * (card_h + gap), card_w, card_h)
            self.draw_panel(painter, card_rect, theme, radius=10, inset=2)
            painter.setPen(theme["dark_text"])
            painter.setFont(small_font)
            painter.drawText(card_rect.adjusted(12, 10, -12, -card_rect.height() + 26), Qt.TextSingleLine, self.elide(painter, item.get("meta", ""), card_rect.width() - 24))
            painter.setFont(body_font)
            painter.drawText(card_rect.adjusted(12, 30, -12, -card_rect.height() + 56), Qt.TextSingleLine, self.elide(painter, item.get("label", ""), card_rect.width() - 24))
            painter.setFont(QFont(body_font.family(), max(8, body_font.pointSize() - 1)))
            painter.drawText(card_rect.adjusted(12, 52, -12, -10), Qt.TextWordWrap, item.get("summary", ""))

    def draw_list_column(self, painter, rect, label, items, selected_index, focused, body_font, small_font, theme, secondary=False):
        self.draw_panel(painter, rect, theme, radius=10, inset=2)
        painter.setPen(theme["dark_text"])
        painter.setFont(small_font)
        painter.drawText(rect.adjusted(12, 10, -12, -rect.height() + 28), Qt.TextSingleLine, label)

        list_top = rect.top() + 38
        row_h = 58 if secondary else 46
        visible_h = rect.bottom() - list_top - 12
        visible_count = max(1, visible_h // row_h)
        start = max(0, selected_index - (visible_count // 2))
        end = min(len(items), start + visible_count)
        start = max(0, end - visible_count)

        for row, index in enumerate(range(start, end)):
            item = items[index]
            item_rect = QRect(rect.left() + 10, list_top + (row * row_h), rect.width() - 20, row_h - 8)
            selected = index == selected_index
            self.draw_item_cell(painter, item_rect, theme, selected=selected, active=focused, focused=(focused and selected))
            painter.setPen(theme["dark_text"] if selected else theme["text"])
            painter.setFont(body_font if secondary else small_font)
            painter.drawText(
                item_rect.adjusted(16, 8, -12, -item_rect.height() + 28),
                Qt.TextSingleLine,
                self.elide(painter, item.get("label", ""), item_rect.width() - 32),
            )
            if item.get("meta"):
                painter.setFont(small_font)
                painter.drawText(
                    item_rect.adjusted(16, 30, -12, -8),
                    Qt.TextSingleLine,
                    self.elide(painter, item["meta"], item_rect.width() - 32),
                )

    def draw_item_cell(self, painter, rect, theme, selected=False, active=False, focused=False):
        if self.skin_style() == "cable":
            fill = theme["guide_selected_bg"] if selected else theme["guide_detail_panel_bg"]
            border = theme["guide_selected_border"] if selected else theme["guide_grid_line"]
            painter.setPen(QPen(border, 1))
            painter.setBrush(fill)
            painter.drawRect(rect)
            if focused:
                painter.setPen(QPen(theme["focus_ring"], 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
            return
        if selected:
            if theme.get("sleek"):
                top = with_alpha(theme["selected_background"].lighter(106), 232)
                bottom = with_alpha(theme["panel_background_alt"], 184)
                border = theme["focus_ring"]
            else:
                top = QColor(255, 251, 208, 236)
                bottom = QColor(236, 206, 106, 242)
                border = QColor(58, 42, 14)
        elif active:
            top = QColor(min(255, theme["header"].red() + 18), min(255, theme["header"].green() + 14), min(255, theme["header"].blue() + 12), 176)
            bottom = QColor(max(0, theme["header"].red() - 8), max(0, theme["header"].green() - 6), max(0, theme["header"].blue() - 4), 206)
            border = QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 132)
        else:
            top = QColor(min(255, theme["panel"].red() + 10), min(255, theme["panel"].green() + 12), min(255, theme["panel"].blue() + 16), 116)
            bottom = QColor(theme["panel"].red(), theme["panel"].green(), theme["panel"].blue(), 148)
            border = QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 118)
        self.draw_rounded_gradient_box(painter, rect, top, bottom, border, radius=8)
        if focused:
            painter.save()
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(theme["focus_ring"] if theme.get("sleek") else QColor(255, 255, 242, 230), 3))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)
            glow = QRect(rect.left() + 2, rect.top() + 2, rect.width() - 4, rect.height() - 4)
            painter.setPen(QPen(theme["focus_glow"] if theme.get("sleek") else QColor(255, 247, 182, 90), 6))
            painter.drawRoundedRect(glow, 8, 8)
            indicator = QRect(rect.left() + 10, rect.center().y() - 9, 12, 18)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 251, 210, 230))
            painter.drawRoundedRect(indicator, 4, 4)
            painter.restore()

    def draw_menu_button(self, painter, rect, label, selected, focused, theme, body_font):
        if selected:
            if theme.get("sleek"):
                top = with_alpha(theme["selected_background"].lighter(106), 232)
                bottom = with_alpha(theme["panel_background_alt"], 184)
                border = theme["focus_ring"]
            else:
                top = QColor(255, 249, 210, 236)
                bottom = QColor(233, 206, 110, 242)
                border = QColor(58, 42, 14)
        else:
            top = QColor(min(255, theme["header"].red() + 20), min(255, theme["header"].green() + 16), min(255, theme["header"].blue() + 14), 220)
            bottom = QColor(max(0, theme["header"].red() - 10), max(0, theme["header"].green() - 8), max(0, theme["header"].blue() - 6), 230)
            border = QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 126)
        self.draw_rounded_gradient_box(painter, rect, top, bottom, border, radius=12)
        if focused:
            painter.save()
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(theme["focus_ring"] if theme.get("sleek") else QColor(255, 255, 240, 220), 3))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 12, 12)
            painter.restore()
        painter.setFont(QFont(body_font.family(), body_font.pointSize() + 1, QFont.Bold))
        painter.setPen(theme["selected_text"] if selected and theme.get("sleek") else (theme["dark_text"] if selected else QColor(248, 250, 244)))
        painter.drawText(rect, Qt.AlignCenter, label)

    def draw_footer(self, painter, rect, small_font, theme):
        if self.skin_style() == "cable":
            self.draw_bar(painter, rect, theme, radius=1)
            self.draw_universal_buttons(painter, rect, small_font, theme)
            return
        self.draw_bar(painter, rect, theme, radius=8)
        self.draw_universal_buttons(painter, rect, small_font, theme)

    def draw_panel(self, painter, rect, theme, radius=12, inset=3):
        if self.skin_style() == "cable":
            draw_classic_cable_panel(painter, rect, theme, self.theme_name, inset=inset)
            return
        if theme.get("sleek"):
            radius = min(max(radius, 4), theme.get("border_radius", 10))
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme["glass_shadow"])
            painter.drawRoundedRect(rect.adjusted(0, 5, 0, 6), radius, radius)
            painter.setPen(QPen(theme["normal_border"], 1))
            painter.setBrush(theme["modern_surface"])
            painter.drawRoundedRect(rect, radius, radius)
            inner = rect.adjusted(inset + 1, inset + 1, -(inset + 1), -(inset + 1))
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme["modern_surface_alt"])
            painter.drawRoundedRect(inner, max(4, radius - 2), max(4, radius - 2))
            painter.setPen(QPen(theme["glass_highlight"], 1))
            painter.drawLine(inner.left() + radius, inner.top() + 1, inner.right() - radius, inner.top() + 1)
            painter.restore()
            return
        outer = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        outer.setColorAt(0.0, theme["chrome_top"])
        outer.setColorAt(0.45, theme["chrome_mid"])
        outer.setColorAt(1.0, theme["chrome_bottom"])
        painter.setPen(QPen(QColor(theme["dark_text"].red(), theme["dark_text"].green(), theme["dark_text"].blue(), 170), 1))
        painter.setBrush(outer)
        painter.drawRoundedRect(rect, radius, radius)

        inner = rect.adjusted(inset, inset, -inset, -inset)
        inner_grad = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        inner_grad.setColorAt(0.0, theme["glass"])
        inner_grad.setColorAt(0.35, theme["panel"])
        inner_grad.setColorAt(
            1.0,
            QColor(
                max(0, theme["panel"].red() - 18),
                max(0, theme["panel"].green() - 14),
                max(0, theme["panel"].blue() - 6),
                theme["panel"].alpha(),
            ),
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(inner_grad)
        painter.drawRoundedRect(inner, max(4, radius - 3), max(4, radius - 3))

    def draw_bar(self, painter, rect, theme, radius=8):
        if self.skin_style() == "cable":
            draw_classic_cable_bar(painter, rect, theme)
            return
        if theme.get("sleek"):
            radius = min(max(radius, 4), theme.get("border_radius", 10))
            painter.setPen(QPen(theme["normal_border"], 1))
            painter.setBrush(theme["guide_header_bg"] if theme["guide_header_bg"].alpha() else theme["modern_surface_alt"])
            painter.drawRoundedRect(rect, radius, radius)
            painter.setPen(QPen(theme["glass_highlight"], 1))
            painter.drawLine(rect.left() + radius, rect.top() + 1, rect.right() - radius, rect.top() + 1)
            return
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, QColor(255, 255, 255, 36))
        grad.setColorAt(0.1, QColor(min(255, theme["header"].red() + 24), min(255, theme["header"].green() + 22), min(255, theme["header"].blue() + 18), 235))
        grad.setColorAt(1.0, QColor(max(0, theme["header"].red() - 8), max(0, theme["header"].green() - 6), max(0, theme["header"].blue() - 2), 240))
        painter.setPen(QPen(QColor(theme["dark_text"].red(), theme["dark_text"].green(), theme["dark_text"].blue(), 150), 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, radius, radius)

    def draw_badge(self, painter, rect, top_color, bottom_color):
        if self.skin_style() == "cable":
            painter.setPen(QPen(top_color, 1))
            painter.setBrush(bottom_color)
            painter.drawRect(rect)
            return
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, QColor(255, 255, 255, 40))
        grad.setColorAt(0.1, top_color)
        grad.setColorAt(1.0, bottom_color)
        painter.setPen(QPen(QColor(132, 34, 30, 210), 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 6, 6)

    def draw_rounded_gradient_box(self, painter, rect, top_color, bottom_color, border_color, radius=6):
        if self.skin_style() == "cable":
            painter.setPen(QPen(border_color, 1))
            painter.setBrush(bottom_color)
            painter.drawRect(rect)
            return
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, top_color)
        grad.setColorAt(1.0, bottom_color)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, radius, radius)

    def elide(self, painter, text, width):
        return painter.fontMetrics().elidedText(text, Qt.ElideRight, max(12, width))

    def draw_starfield(self, painter, rect, theme):
        painter.save()
        painter.setClipRect(rect)
        painter.fillRect(rect, QColor(2, 4, 10))
        seed = (rect.width() * 9001) + (rect.height() * 313) + sum(ord(ch) for ch in self.theme_name)
        rng = random.Random(seed)
        for _ in range(max(180, (rect.width() * rect.height()) // 2400)):
            x = rect.left() + rng.randint(0, max(1, rect.width() - 2))
            y = rect.top() + rng.randint(0, max(1, rect.height() - 2))
            roll = rng.random()
            if roll < 0.62:
                size = 1
            elif roll < 0.9:
                size = 2
            else:
                size = 3 if roll < 0.985 else 4
            alpha = 170 + rng.randint(0, 85)
            shade = 228 + rng.randint(0, 27)
            painter.fillRect(x, y, size, size, QColor(shade, shade, 255, alpha))
        painter.restore()


class InfoOverlay(QWidget):
    uiScaleStepRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.profile_name = "Auto"
        self.theme_name = DEFAULT_THEME_NAME
        self.skin_name = DEFAULT_SKIN_NAME
        self.ui_scale = GUIDE_UI_SCALE_DEFAULT
        self.state = {}
        self.settings_open = False
        self.settings_values = {}
        self.hide()

    def configure(self, profile_name, theme_name, skin_name, ui_scale=GUIDE_UI_SCALE_DEFAULT):
        self.profile_name = profile_name if profile_name in GUIDE_PROFILES else "Auto"
        self.skin_name = normalize_skin_name(skin_name)
        self.theme_name = normalize_theme_for_skin(self.skin_name, theme_name)
        self.ui_scale = clamp_guide_ui_scale(ui_scale)
        if self.isVisible():
            self.update()

    def skin_style(self):
        return GUIDE_SKINS.get(normalize_skin_name(self.skin_name), GUIDE_SKINS[DEFAULT_SKIN_NAME]).get("style", "aero")

    def show_banner(self, state):
        self.state = state or {}
        self.settings_values = dict(self.state.get("settings_values", {}) or self.settings_values)
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.update()

    def update_banner(self, state):
        self.state = state or {}
        self.settings_values = dict(self.state.get("settings_values", {}) or self.settings_values)
        if self.isVisible():
            self.update()

    def paintEvent(self, event):
        if not self.state:
            return

        theme = app_theme(self.theme_name, self.skin_name)
        painter = QPainter(self)
        if self.skin_style() == "cable":
            target = overlay_target_rect(self)
            panel_h = min(max(scaled_metric(256, self.ui_scale, 208), target.height() // 3), target.height() - scaled_metric(44, self.ui_scale, 30))
            panel = QRect(
                target.left() + scaled_metric(16, self.ui_scale, 10),
                target.bottom() - panel_h - scaled_metric(16, self.ui_scale, 10),
                target.width() - scaled_metric(32, self.ui_scale, 20),
                panel_h,
            )
            panel_base = theme["app_background"] if theme.get("starfield") else theme["bg"]
            panel_fill = QColor(panel_base.red(), panel_base.green(), panel_base.blue(), 255)
            painter.fillRect(panel, panel_fill)
            if theme.get("starfield"):
                self.draw_starfield(painter, panel.adjusted(2, 2, -2, -2), theme)
            painter.setPen(QPen(theme["info_overlay_border"], 1))
            painter.drawRect(panel)

            small_font = QFont(guide_font_family("primary"), max(scaled_metric(9, self.ui_scale, 7), 9), QFont.Bold)
            body_font = QFont(guide_font_family("secondary"), max(scaled_metric(10, self.ui_scale, 8), 10), QFont.DemiBold)
            title_font = QFont(guide_font_family("primary"), max(scaled_metric(13, self.ui_scale, 10), 13), QFont.Bold)

            show_action = self.state.get("is_on_demand", False)
            footer_labels = ["BACK", "MENU", "GUIDE", "VAULT"] + (["START OVER"] if show_action else [])
            footer_h = scaled_metric(30, self.ui_scale, 24)
            footer_margin = scaled_metric(18, self.ui_scale, 12)
            footer = QRect(
                panel.left() + footer_margin,
                panel.bottom() - footer_h - footer_margin,
                panel.width() - (footer_margin * 2),
                footer_h,
            )

            outer_margin = scaled_metric(22, self.ui_scale, 16)
            label_rect = QRect(panel.left() + outer_margin, panel.top() + outer_margin, scaled_metric(136, self.ui_scale, 104), scaled_metric(24, self.ui_scale, 20))
            painter.setPen(QPen(theme["menu_panel_border"], 1))
            painter.setBrush(with_alpha(theme["guide_header_bg"], 255))
            painter.drawRect(label_rect)
            painter.setFont(small_font)
            painter.setPen(theme["guide_header_text"])
            painter.drawText(label_rect.adjusted(6, 0, -6, 0), Qt.AlignLeft | Qt.AlignVCenter, self.state.get("header", "PROGRAM INFO"))

            clock_rect = QRect(
                panel.right() - outer_margin - scaled_metric(108, self.ui_scale, 86),
                panel.top() + outer_margin,
                scaled_metric(108, self.ui_scale, 86),
                scaled_metric(22, self.ui_scale, 18),
            )
            self.draw_digital_clock_box(painter, clock_rect, time.strftime("%I:%M%p").lstrip("0").upper())

            content_top = label_rect.bottom() + scaled_metric(12, self.ui_scale, 10)
            left_col_x = panel.left() + scaled_metric(48, self.ui_scale, 36)
            left_col_w = max(scaled_metric(232, self.ui_scale, 176), panel.width() // 5)
            logo_rect = QRect(left_col_x, content_top, min(scaled_metric(220, self.ui_scale, 160), left_col_w - 16), scaled_metric(42, self.ui_scale, 30))
            self.draw_logo_watermark(painter, logo_rect, opacity=0.96)

            channel_rect = QRect(left_col_x, logo_rect.bottom() + scaled_metric(18, self.ui_scale, 12), left_col_w, scaled_metric(70, self.ui_scale, 52))
            painter.setFont(QFont(guide_font_family("primary"), max(scaled_metric(12, self.ui_scale, 10), 12), QFont.Bold))
            painter.setPen(theme["info_overlay_text"])
            painter.drawText(channel_rect.adjusted(0, 0, 0, -22), Qt.TextWordWrap, self.state.get("channel_line", "").upper())
            painter.setFont(small_font)
            playback_line = self.state.get("time_line", "")
            if self.state.get("is_on_demand", False):
                playback_line = "ON DEMAND PLAYBACK"
            painter.drawText(channel_rect.adjusted(0, 30, 0, 0), Qt.TextWordWrap, playback_line)

            title_left = left_col_x + left_col_w + scaled_metric(76, self.ui_scale, 58)
            title_right = panel.right() - scaled_metric(28, self.ui_scale, 20)
            title_text = self.state.get("title", "").upper()
            progress_top = footer.top() - scaled_metric(82, self.ui_scale, 64)
            title_measure_rect = QRect(
                title_left,
                content_top + scaled_metric(10, self.ui_scale, 8),
                max(180, title_right - title_left),
                max(
                    scaled_metric(76, self.ui_scale, 58),
                    progress_top - (content_top + scaled_metric(10, self.ui_scale, 8)) - scaled_metric(16, self.ui_scale, 12),
                ),
            )
            painter.setFont(title_font)
            title_bounds = painter.boundingRect(title_measure_rect, Qt.TextWordWrap, title_text)
            title_rect = QRect(
                title_measure_rect.left(),
                title_measure_rect.top(),
                title_measure_rect.width(),
                max(scaled_metric(32, self.ui_scale, 24), min(title_measure_rect.height(), title_bounds.height())),
            )
            painter.setPen(theme["accent"])
            painter.drawText(title_rect, Qt.TextWordWrap, title_text)

            progress_box = QRect(
                title_left,
                progress_top,
                panel.right() - title_left - scaled_metric(28, self.ui_scale, 20),
                scaled_metric(28, self.ui_scale, 22),
            )
            painter.setFont(small_font)
            painter.setPen(theme["info_overlay_text"])
            remain_w = min(max(scaled_metric(122, self.ui_scale, 96), progress_box.width() // 4), progress_box.width() - scaled_metric(56, self.ui_scale, 42))
            remain_rect = QRect(progress_box.left(), progress_box.top(), remain_w, progress_box.height())
            painter.drawText(remain_rect, Qt.AlignLeft | Qt.AlignVCenter, self.state.get("remaining_line", ""))
            track_left = remain_rect.right() + scaled_metric(18, self.ui_scale, 14)
            track = QRect(
                track_left,
                progress_box.center().y() - scaled_metric(5, self.ui_scale, 4),
                max(20, progress_box.right() - track_left - scaled_metric(10, self.ui_scale, 8)),
                scaled_metric(10, self.ui_scale, 8),
            )
            painter.setPen(QPen(theme["info_overlay_text"], 1))
            painter.drawRect(track)
            progress = max(0.0, min(1.0, self.state.get("progress", 0.0)))
            fill = QRect(track.left() + 1, track.top() + 1, max(6, int((track.width() - 2) * progress)), max(1, track.height() - 2))
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme["info_progress_fill"])
            painter.drawRect(fill)

            self.draw_footer_nav(painter, footer, small_font, theme, footer_labels)
            if self.settings_open:
                painter.fillRect(self.rect(), QColor(8, 10, 14, 120))
                self.draw_settings_panel(painter, panel, body_font, small_font, theme)
            return
        if theme.get("sleek"):
            target = overlay_target_rect(self)
            panel_w = min(target.width() - scaled_metric(34, self.ui_scale, 24), scaled_metric(1180, self.ui_scale, 900))
            panel_h = min(max(scaled_metric(232, self.ui_scale, 188), target.height() // 4), target.height() - scaled_metric(42, self.ui_scale, 28))
            panel = QRect(
                target.left() + (target.width() - panel_w) // 2,
                target.bottom() - panel_h - scaled_metric(22, self.ui_scale, 16),
                panel_w,
                panel_h,
            )
            radius = theme.get("border_radius", 8)
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            shadow = panel.adjusted(0, scaled_metric(6, self.ui_scale, 4), 0, scaled_metric(8, self.ui_scale, 6))
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme["glass_shadow"])
            painter.drawRoundedRect(shadow, radius, radius)
            painter.setPen(QPen(theme["info_overlay_border"], 1))
            painter.setBrush(theme["info_overlay_bg"])
            painter.drawRoundedRect(panel, radius, radius)
            painter.setPen(QPen(theme["glass_highlight"], 1))
            painter.drawLine(panel.left() + radius, panel.top() + 1, panel.right() - radius, panel.top() + 1)

            inner = panel.adjusted(scaled_metric(24, self.ui_scale, 18), scaled_metric(20, self.ui_scale, 14), -scaled_metric(24, self.ui_scale, 18), -scaled_metric(20, self.ui_scale, 14))
            small_font = QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(scaled_metric(10, self.ui_scale, 8), 10), QFont.DemiBold)
            body_font = QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(scaled_metric(12, self.ui_scale, 10), 12), QFont.Normal)
            title_font = QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(scaled_metric(18, self.ui_scale, 14), 18), QFont.DemiBold)

            header_rect = QRect(inner.left(), inner.top(), inner.width(), scaled_metric(30, self.ui_scale, 24))
            painter.setFont(small_font)
            painter.setPen(theme["secondary_text"])
            painter.drawText(header_rect, Qt.AlignLeft | Qt.AlignVCenter, self.state.get("header", "PROGRAM INFO").upper())

            clock_rect = QRect(inner.right() - scaled_metric(116, self.ui_scale, 92), inner.top(), scaled_metric(116, self.ui_scale, 92), scaled_metric(30, self.ui_scale, 24))
            painter.setPen(QPen(theme["subtle_border"], 1))
            painter.setBrush(theme["menu_button_bg"])
            painter.drawRoundedRect(clock_rect, theme.get("cell_radius", 6), theme.get("cell_radius", 6))
            painter.setPen(theme["secondary_text"])
            painter.drawText(clock_rect, Qt.AlignCenter, time.strftime("%I:%M %p").lstrip("0"))

            footer_h = scaled_metric(34, self.ui_scale, 26)
            footer = QRect(inner.left(), inner.bottom() - footer_h, min(scaled_metric(420, self.ui_scale, 320), inner.width()), footer_h)
            progress_top = footer.top() - scaled_metric(28, self.ui_scale, 22)
            left_w = min(scaled_metric(250, self.ui_scale, 190), inner.width() // 4)
            logo_rect = QRect(inner.left(), header_rect.bottom() + scaled_metric(10, self.ui_scale, 8), left_w, scaled_metric(62, self.ui_scale, 46))
            self.draw_logo_watermark(painter, logo_rect, opacity=0.86)

            channel_rect = QRect(inner.left(), logo_rect.bottom() + scaled_metric(12, self.ui_scale, 8), left_w, max(footer.top() - logo_rect.bottom() - scaled_metric(16, self.ui_scale, 10), scaled_metric(46, self.ui_scale, 36)))
            painter.setFont(QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(scaled_metric(12, self.ui_scale, 10), 12), QFont.DemiBold))
            painter.setPen(theme["primary_text"])
            painter.drawText(channel_rect.adjusted(0, 0, 0, -scaled_metric(24, self.ui_scale, 18)), Qt.TextWordWrap, self.state.get("channel_line", ""))
            painter.setFont(small_font)
            painter.setPen(theme["secondary_text"])
            painter.drawText(channel_rect.adjusted(0, scaled_metric(32, self.ui_scale, 24), 0, 0), Qt.TextWordWrap, self.state.get("time_line", ""))

            info_left = inner.left() + left_w + scaled_metric(42, self.ui_scale, 30)
            info_right = inner.right()
            info_rect = QRect(info_left, header_rect.bottom() + scaled_metric(16, self.ui_scale, 10), max(160, info_right - info_left), max(60, progress_top - header_rect.bottom() - scaled_metric(22, self.ui_scale, 16)))
            painter.setFont(title_font)
            painter.setPen(theme["primary_text"])
            title_text = self.state.get("title", "")
            title_rect = QRect(info_rect.left(), info_rect.top(), info_rect.width(), scaled_metric(56, self.ui_scale, 42))
            title_bounds = painter.boundingRect(title_rect, Qt.TextWordWrap, title_text)
            title_draw_rect = QRect(title_rect.left(), title_rect.top(), title_rect.width(), min(title_rect.height(), max(scaled_metric(26, self.ui_scale, 20), title_bounds.height())))
            painter.drawText(title_draw_rect, Qt.TextWordWrap, title_text)
            painter.setFont(body_font)
            painter.setPen(theme["muted_text"])
            summary_top = title_draw_rect.bottom() + scaled_metric(10, self.ui_scale, 8)
            summary_rect = QRect(info_rect.left(), summary_top, info_rect.width(), max(scaled_metric(24, self.ui_scale, 18), info_rect.bottom() - summary_top))
            painter.drawText(summary_rect, Qt.TextWordWrap, self.state.get("summary", ""))

            actions = self.state.get("actions", ["VIEW SHOW VAULT"])
            action_index = self.state.get("action_index", -1)
            action_gap = scaled_metric(10, self.ui_scale, 8)
            action_width = scaled_metric(190, self.ui_scale, 150)
            action_h = scaled_metric(34, self.ui_scale, 28)
            action_left = max(info_rect.left(), info_rect.right() - ((action_width * len(actions)) + (action_gap * max(0, len(actions) - 1))))
            for idx, label in enumerate(actions):
                rect = QRect(action_left + idx * (action_width + action_gap), header_rect.top(), action_width, action_h)
                focused = action_index == idx
                painter.setPen(QPen(theme["focus_ring"] if focused else theme["subtle_border"], 1))
                painter.setBrush(theme["menu_button_selected_bg"] if focused else theme["menu_button_bg"])
                painter.drawRoundedRect(rect, theme.get("cell_radius", 6), theme.get("cell_radius", 6))
                painter.setFont(small_font)
                painter.setPen(theme["selected_text"] if focused else theme["primary_text"])
                painter.drawText(rect, Qt.AlignCenter, label)

            footer_nav = self.draw_footer_nav(painter, footer, small_font, theme)
            remain_rect = QRect(max(footer_nav["right"] + scaled_metric(20, self.ui_scale, 14), info_rect.left()), progress_top - scaled_metric(18, self.ui_scale, 14), inner.right() - info_rect.left(), scaled_metric(18, self.ui_scale, 14))
            painter.setFont(small_font)
            painter.setPen(theme["secondary_text"])
            painter.drawText(remain_rect, Qt.AlignLeft | Qt.AlignVCenter, self.state.get("remaining_line", ""))
            track_left = max(footer_nav["right"] + scaled_metric(20, self.ui_scale, 14), info_rect.left())
            track = QRect(track_left, progress_top, inner.right() - track_left, scaled_metric(8, self.ui_scale, 6))
            painter.setPen(Qt.NoPen)
            painter.setBrush(with_alpha(theme["panel_background_alt"], 120))
            painter.drawRoundedRect(track, 3, 3)
            progress = max(0.0, min(1.0, self.state.get("progress", 0.0)))
            fill = QRect(track.left(), track.top(), max(8, int(track.width() * progress)), track.height())
            painter.setBrush(theme["info_progress_fill"])
            painter.drawRoundedRect(fill, 3, 3)
            painter.restore()
            if self.settings_open:
                painter.fillRect(panel.adjusted(6, 12, -6, -12), theme["overlay_scrim"])
                self.draw_settings_panel(painter, panel, body_font, small_font, theme)
            return
        panel_w = min(self.width() - scaled_metric(36, self.ui_scale, 24), scaled_metric(1120, self.ui_scale, 860))
        panel_h = scaled_metric(254, self.ui_scale, 210)
        panel = QRect((self.width() - panel_w) // 2, self.height() - panel_h - scaled_metric(28, self.ui_scale, 18), panel_w, panel_h)

        outer = QLinearGradient(panel.topLeft(), panel.bottomLeft())
        outer.setColorAt(0.0, theme["chrome_top"])
        outer.setColorAt(0.36, theme["chrome_mid"])
        outer.setColorAt(1.0, theme["chrome_bottom"])
        painter.setPen(QPen(QColor(theme["dark_text"].red(), theme["dark_text"].green(), theme["dark_text"].blue(), 190), 1))
        painter.setBrush(outer)
        painter.drawRoundedRect(panel, 16, 16)

        inner = panel.adjusted(3, 3, -3, -3)
        inner_grad = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        inner_grad.setColorAt(0.0, QColor(theme["panel"].red(), theme["panel"].green(), theme["panel"].blue(), 240))
        inner_grad.setColorAt(1.0, QColor(max(0, theme["panel"].red() - 18), max(0, theme["panel"].green() - 14), max(0, theme["panel"].blue() - 8), 232))
        painter.setPen(Qt.NoPen)
        painter.setBrush(inner_grad)
        painter.drawRoundedRect(inner, 13, 13)

        small_font = QFont("Trebuchet MS", max(scaled_metric(9, self.ui_scale, 8), panel.width() // max(95, scaled_metric(115, 1 / self.ui_scale if self.ui_scale else 1, 95))), QFont.Bold)
        body_font = QFont("Trebuchet MS", max(scaled_metric(10, self.ui_scale, 9), panel.width() // max(80, scaled_metric(95, 1 / self.ui_scale if self.ui_scale else 1, 80))))
        title_font = QFont("Trebuchet MS", max(scaled_metric(13, self.ui_scale, 11), panel.width() // max(58, scaled_metric(70, 1 / self.ui_scale if self.ui_scale else 1, 58))), QFont.Bold)
        label_rect = QRect(inner.left() + scaled_metric(14, self.ui_scale, 10), inner.top() + scaled_metric(10, self.ui_scale, 8), scaled_metric(136, self.ui_scale, 110), scaled_metric(28, self.ui_scale, 22))
        self.draw_rounded_gradient_box(
            painter,
            label_rect,
            QColor(theme["chrome_top"].red(), theme["chrome_top"].green(), theme["chrome_top"].blue(), 184),
            QColor(theme["chrome_bottom"].red(), theme["chrome_bottom"].green(), theme["chrome_bottom"].blue(), 196),
            QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 140),
            radius=8,
        )
        painter.setFont(QFont("Trebuchet MS", max(11, small_font.pointSize() + 2), QFont.Bold))
        painter.setPen(theme["text"])
        painter.drawText(label_rect, Qt.AlignCenter, self.state.get("header", "PROGRAM INFO"))

        clock_rect = QRect(inner.right() - scaled_metric(186, self.ui_scale, 146), inner.top() + scaled_metric(8, self.ui_scale, 6), scaled_metric(172, self.ui_scale, 134), scaled_metric(32, self.ui_scale, 26))
        self.draw_digital_clock_box(painter, clock_rect, time.strftime("%I:%M%p").lstrip("0").lower())

        logo_rect = QRect(inner.left() + scaled_metric(18, self.ui_scale, 12), label_rect.bottom() + scaled_metric(12, self.ui_scale, 8), min(scaled_metric(320, self.ui_scale, 220), inner.width() - scaled_metric(36, self.ui_scale, 20)), scaled_metric(58, self.ui_scale, 46))
        self.draw_logo_watermark(painter, logo_rect, opacity=0.96)

        left_column_top = logo_rect.bottom() + 12
        right_column_top = label_rect.bottom() + 18
        footer = QRect(inner.left() + scaled_metric(14, self.ui_scale, 10), inner.bottom() - scaled_metric(36, self.ui_scale, 26), inner.width() - scaled_metric(28, self.ui_scale, 20), scaled_metric(28, self.ui_scale, 22))
        progress_top = footer.top() - scaled_metric(22, self.ui_scale, 18)
        channel_rect = QRect(inner.left() + scaled_metric(18, self.ui_scale, 12), left_column_top, int(inner.width() * 0.23), scaled_metric(60, self.ui_scale, 50))
        button_rect = QRect(inner.right() - scaled_metric(230, self.ui_scale, 184), right_column_top + scaled_metric(4, self.ui_scale, 2), scaled_metric(212, self.ui_scale, 164), scaled_metric(42, self.ui_scale, 34))
        info_left = max(logo_rect.right() + scaled_metric(34, self.ui_scale, 22), inner.left() + int(inner.width() * 0.27))
        info_right = button_rect.left() - scaled_metric(26, self.ui_scale, 18)
        info_rect = QRect(info_left, right_column_top, max(scaled_metric(180, self.ui_scale, 140), info_right - info_left), max(scaled_metric(120, self.ui_scale, 96), progress_top - right_column_top - scaled_metric(16, self.ui_scale, 12)))

        painter.setFont(QFont("Trebuchet MS", max(16, panel.width() // 64), QFont.Bold))
        painter.setPen(theme["dark_text"])
        painter.drawText(channel_rect.adjusted(0, 0, 0, -24), Qt.TextWordWrap, self.state.get("channel_line", ""))
        painter.setFont(small_font)
        painter.drawText(channel_rect.adjusted(0, 34, 0, -6), Qt.TextWordWrap, self.state.get("time_line", ""))

        painter.setFont(title_font)
        title_text = self.state.get("title", "")
        title_rect = QRect(info_rect.left(), info_rect.top(), info_rect.width(), 78)
        title_bounds = painter.boundingRect(title_rect, Qt.TextWordWrap, title_text)
        title_draw_rect = QRect(
            title_rect.left(),
            title_rect.top(),
            title_rect.width(),
            min(title_rect.height(), max(30, title_bounds.height())),
        )
        painter.drawText(title_draw_rect, Qt.TextWordWrap, title_text)
        painter.setFont(body_font)
        summary_top = title_draw_rect.bottom() + 10
        summary_rect = QRect(info_rect.left(), summary_top, info_rect.width(), max(24, progress_top - summary_top - 18))
        painter.drawText(summary_rect, Qt.TextWordWrap, self.state.get("summary", ""))

        actions = self.state.get("actions", ["VIEW SHOW VAULT"])
        action_index = self.state.get("action_index", -1)
        action_gap = 12
        action_width = 212
        action_total = (action_width * len(actions)) + (action_gap * max(0, len(actions) - 1))
        action_left = max(info_rect.right() + 18, inner.right() - 18 - action_total)
        for idx, label in enumerate(actions):
            rect = QRect(action_left + idx * (action_width + action_gap), right_column_top + 10, action_width, 42)
            focused = action_index == idx
            top = QColor(255, 249, 210, 236) if focused else QColor(theme["chrome_top"].red(), theme["chrome_top"].green(), theme["chrome_top"].blue(), 188)
            bottom = QColor(233, 206, 110, 242) if focused else QColor(theme["chrome_bottom"].red(), theme["chrome_bottom"].green(), theme["chrome_bottom"].blue(), 206)
            border = QColor(58, 42, 14) if focused else QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 140)
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, top)
            grad.setColorAt(1.0, bottom)
            painter.setBrush(grad)
            painter.setPen(QPen(border, 1))
            painter.drawRoundedRect(rect, 12, 12)
            if focused:
                painter.save()
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(255, 255, 242, 220), 3))
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 12, 12)
                painter.restore()
            painter.setFont(QFont("Trebuchet MS", max(10, panel.width() // 92), QFont.Bold))
            painter.setPen(theme["dark_text"] if focused else theme["text"])
            painter.drawText(rect, Qt.AlignCenter, label)

        footer_nav = self.draw_footer_nav(painter, footer, small_font, theme)

        remain_rect = QRect(footer_nav["right"] + 18, progress_top - 20, inner.right() - footer_nav["right"] - 28, 14)
        painter.setFont(small_font)
        painter.setPen(theme["dark_text"])
        painter.drawText(remain_rect, Qt.AlignLeft | Qt.AlignVCenter, self.state.get("remaining_line", ""))

        track = QRect(footer_nav["right"] + 18, progress_top, inner.right() - footer_nav["right"] - 28, 9)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme["bg"].red(), theme["bg"].green(), theme["bg"].blue(), 94))
        painter.drawRoundedRect(track, 4, 4)
        progress = max(0.0, min(1.0, self.state.get("progress", 0.0)))
        fill = QRect(track.left(), track.top(), max(10, int(track.width() * progress)), track.height())
        fill_grad = QLinearGradient(fill.topLeft(), fill.topRight())
        fill_grad.setColorAt(0.0, QColor(255, 247, 180, 232))
        fill_grad.setColorAt(1.0, QColor(228, 190, 92, 228))
        painter.setBrush(fill_grad)
        painter.drawRoundedRect(fill, 4, 4)

        if self.settings_open:
            painter.fillRect(panel.adjusted(6, 12, -6, -12), QColor(8, 10, 14, 120))
            self.draw_settings_panel(painter, panel, body_font, small_font, theme)

    def draw_digital_clock_box(self, painter, rect, text):
        if self.skin_style() == "cable":
            font = QFont(clock_font_family(), max(13, rect.height() - 4), QFont.Bold)
            painter.setFont(font)
            for dx, dy, alpha in ((2, 1, 120), (1, 0, 80)):
                painter.setPen(QColor(40, 0, 0, alpha))
                painter.drawText(rect.translated(dx, dy), Qt.AlignCenter, text)
            painter.setPen(QColor(255, 112, 112))
            painter.drawText(rect, Qt.AlignCenter, text)
            painter.setPen(QColor(255, 186, 186, 110))
            painter.drawText(rect.adjusted(0, -1, 0, -1), Qt.AlignCenter, text)
            return
        theme = app_theme(self.theme_name, self.skin_name)
        if theme.get("sleek"):
            painter.setPen(QPen(theme["subtle_border"], 1))
            painter.setBrush(theme["menu_button_bg"])
            painter.drawRoundedRect(rect, theme.get("cell_radius", 6), theme.get("cell_radius", 6))
            painter.setFont(QFont(theme.get("font_ui", ".AppleSystemUIFont"), max(10, rect.height() - 12), QFont.DemiBold))
            painter.setPen(theme["secondary_text"])
            painter.drawText(rect, Qt.AlignCenter, text.replace("pm", " PM").replace("am", " AM"))
            return
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, QColor(74, 78, 80, 240))
        grad.setColorAt(1.0, QColor(44, 46, 48, 244))
        painter.setPen(QPen(QColor(22, 24, 26, 220), 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 8, 8)

        font = QFont(clock_font_family(), max(13, rect.height() - 8), QFont.Bold)
        painter.setFont(font)
        for dx, dy, alpha in ((2, 2, 120), (1, 1, 80)):
            painter.setPen(QColor(22, 0, 0, alpha))
            painter.drawText(rect.translated(dx, dy), Qt.AlignCenter, text)
        painter.setPen(QColor(255, 94, 94, 255))
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.setPen(QColor(255, 180, 180, 120))
        painter.drawText(rect.adjusted(0, -1, 0, -1), Qt.AlignCenter, text)

    def draw_starfield(self, painter, rect, theme):
        painter.save()
        painter.setClipRect(rect)
        painter.fillRect(rect, QColor(2, 4, 10))
        seed = (rect.width() * 8111) + (rect.height() * 379) + sum(ord(ch) for ch in self.theme_name)
        rng = random.Random(seed)
        for _ in range(max(180, (rect.width() * rect.height()) // 2400)):
            x = rect.left() + rng.randint(0, max(1, rect.width() - 2))
            y = rect.top() + rng.randint(0, max(1, rect.height() - 2))
            roll = rng.random()
            if roll < 0.62:
                size = 1
            elif roll < 0.9:
                size = 2
            else:
                size = 3 if roll < 0.985 else 4
            alpha = 170 + rng.randint(0, 85)
            shade = 228 + rng.randint(0, 27)
            painter.fillRect(x, y, size, size, QColor(shade, shade, 255, alpha))
        painter.restore()

    def draw_logo_watermark(self, painter, rect, opacity=1.0):
        logo_path = CLASSIC_APP_LOGO_PATH if self.skin_style() == "cable" else None
        logo = load_brand_logo(rect.width(), rect.height(), logo_path)
        if logo.isNull():
            return
        painter.save()
        painter.setOpacity(opacity)
        x = rect.left()
        y = rect.top() + (rect.height() - logo.height()) // 2
        painter.drawPixmap(x, y, logo)
        painter.restore()

    def draw_rounded_gradient_box(self, painter, rect, top_color, bottom_color, border_color, radius=8):
        if self.skin_style() == "cable":
            painter.setPen(QPen(border_color, 1))
            painter.setBrush(bottom_color)
            painter.drawRect(rect)
            return
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, top_color)
        grad.setColorAt(1.0, bottom_color)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, radius, radius)

    def draw_footer_nav(self, painter, bar_rect, small_font, theme, labels=None):
        if self.skin_style() == "cable":
            painter.setPen(QPen(theme["menu_panel_border"], 1))
            painter.setBrush(with_alpha(theme["bottom_nav_bg"], 255))
            painter.drawRect(bar_rect)
            return self.draw_universal_buttons(painter, bar_rect, small_font, theme, labels)
        else:
            return self.draw_universal_buttons(painter, bar_rect, small_font, theme, labels)

    def draw_universal_buttons(self, painter, bar_rect, small_font, theme, labels=None):
        labels = labels or ["BACK", "MENU", "GUIDE", "VAULT"]
        gap = scaled_metric(8, self.ui_scale, 6)
        height = max(scaled_metric(22, self.ui_scale, 18), bar_rect.height() - 8)
        start_x = bar_rect.left() + scaled_metric(8, self.ui_scale, 6)
        y = bar_rect.top() + max(1, (bar_rect.height() - height) // 2)
        x = start_x
        rects = []
        for idx, label in enumerate(labels):
            width = scaled_metric(152, self.ui_scale, 118) if label == "START OVER" else scaled_metric(82, self.ui_scale, 64)
            rect = QRect(x, y, width, height)
            rects.append(rect)
            active = self.state.get("nav_focused") and self.state.get("nav_index", 1) == idx
            if self.skin_style() == "cable":
                border = theme["guide_selected_border"] if active else theme["menu_panel_border"]
                painter.setPen(QPen(border, 1))
                painter.setBrush(theme["menu_button_selected_bg"] if active else with_alpha(theme["menu_button_bg"], 255))
                painter.drawRect(rect)
                painter.setFont(small_font)
                painter.setPen(theme["selected_text"] if active else theme["bottom_nav_button_text"])
                painter.drawText(rect, Qt.AlignCenter, label)
            elif theme.get("sleek"):
                painter.setPen(QPen(theme["focus_ring"] if active else theme["subtle_border"], 1))
                painter.setBrush(theme["menu_button_selected_bg"] if active else theme["bottom_nav_button_bg"])
                painter.drawRoundedRect(rect, theme.get("cell_radius", 6), theme.get("cell_radius", 6))
                painter.setFont(small_font)
                painter.setPen(theme["selected_text"] if active else theme["bottom_nav_button_text"])
                painter.drawText(rect, Qt.AlignCenter, label)
            else:
                grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
                if active:
                    grad.setColorAt(0.0, QColor(255, 249, 210, 236))
                    grad.setColorAt(1.0, QColor(233, 206, 110, 242))
                    border = QColor(58, 42, 14)
                else:
                    grad.setColorAt(0.0, QColor(theme["chrome_top"].red(), theme["chrome_top"].green(), theme["chrome_top"].blue(), 188))
                    grad.setColorAt(1.0, QColor(theme["chrome_bottom"].red(), theme["chrome_bottom"].green(), theme["chrome_bottom"].blue(), 206))
                    border = QColor(theme["muted"].red(), theme["muted"].green(), theme["muted"].blue(), 140)
                painter.setBrush(grad)
                painter.setPen(QPen(border, 1))
                painter.drawRoundedRect(rect, 8, 8)
                if active:
                    painter.save()
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(QColor(255, 255, 242, 220), 2))
                    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)
                    painter.restore()
                painter.setFont(small_font)
                painter.setPen(theme["dark_text"] if active else theme["text"])
                painter.drawText(rect, Qt.AlignCenter, label)
            x += width + gap
        return {"left": start_x, "right": rects[-1].right() if rects else start_x}

    def draw_cable_text(self, painter, rect, text, color, font, flags):
        if not text:
            return
        painter.save()
        painter.setFont(font)
        shadow = QColor(0, 0, 0, 220)
        for dx, dy in ((1, 0), (0, 1), (1, 1)):
            painter.setPen(shadow)
            painter.drawText(rect.translated(dx, dy), flags, text)
        painter.setPen(color)
        painter.drawText(rect, flags, text)
        painter.restore()

    def draw_xp_panel(self, painter, rect, theme, radius=12, inset=3):
        if self.skin_style() == "cable":
            draw_classic_cable_panel(painter, rect, theme, self.theme_name, border_width=1, border_alpha=118, inset=inset)
            return
        self.draw_rounded_gradient_box(
            painter,
            rect,
            theme.get("chrome_top", theme["info_overlay_bg"]),
            theme.get("chrome_bottom", theme["info_overlay_bg"]),
            theme.get("menu_panel_border", theme["info_overlay_border"]),
            radius=radius,
        )

    def draw_xp_bar(self, painter, rect, theme, radius=8):
        if self.skin_style() == "cable":
            draw_classic_cable_bar(painter, rect, theme, border_width=1, border_alpha=122)
            return
        self.draw_rounded_gradient_box(
            painter,
            rect,
            theme.get("chrome_mid", theme["info_progress_fill"]),
            theme.get("header", theme["info_progress_fill"]),
            theme.get("menu_panel_border", theme["info_overlay_border"]),
            radius=radius,
        )

    def draw_slot_box(self, painter, rect, theme, active=False):
        if self.skin_style() == "cable":
            draw_classic_cable_slot_box(painter, rect, theme, active=active)
            return
        fill = theme["menu_button_selected_bg"] if active else theme["menu_button_bg"]
        border = theme.get("focus_ring", theme["info_overlay_border"]) if active else theme["info_overlay_border"]
        if theme.get("sleek"):
            painter.setPen(QPen(border, 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, theme.get("cell_radius", 6), theme.get("cell_radius", 6))
            return
        self.draw_rounded_gradient_box(painter, rect, fill, fill, border, radius=6)

    def draw_arrow_button(self, painter, rect, label, theme):
        self.draw_slot_box(painter, rect, theme, active=False)
        if self.skin_style() == "cable":
            self.draw_cable_text(painter, rect, label, QColor(248, 248, 240), QFont(guide_font_family("primary"), max(10, rect.height() - 12), QFont.Bold), Qt.AlignCenter)
        else:
            painter.setPen(theme["text"])
            painter.drawText(rect, Qt.AlignCenter, label)

    def draw_settings_panel(self, painter, panel, body_font, small_font, theme):
        self.settings_focus_index = self.state.get("settings_focus_index", 0)
        draw_shared_mediawave_settings_panel(self, painter, panel, body_font, small_font, theme)

    def draw_scanlines(self, painter, rect):
        crt = CLASSIC_CABLE_TUNING["crt"]
        painter.save()
        painter.setClipRect(rect)
        painter.setPen(QPen(QColor(0, 0, 0, crt["scanline_alpha"]), 1))
        for y in range(rect.top(), rect.bottom(), crt["scanline_step"]):
            painter.drawLine(rect.left(), y, rect.right(), y)
        painter.restore()

    def draw_noise_overlay(self, painter, rect):
        crt = CLASSIC_CABLE_TUNING["crt"]
        painter.save()
        painter.setClipRect(rect)
        t = int(time.time() * 1000)
        for step in range(0, rect.height(), 8):
            y = rect.top() + step
            alpha = crt["noise_line_alpha_base"] + ((t + step * 17) % 4)
            painter.fillRect(rect.left(), y, rect.width(), 1, QColor(255, 255, 255, alpha))
        for i in range(0, rect.width(), 29):
            x = rect.left() + i + ((t // 33) % 5)
            y = rect.top() + ((i * 19 + t // 11) % max(1, rect.height()))
            painter.fillRect(x, y, 1, 1, QColor(255, 255, 255, crt["noise_dot_alpha"]))
        painter.restore()


class RadioWaveOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.state = {}
        self.phase = 0.0
        self.marquee_offset = 0.0
        self.preview_cache = QPixmap()
        self.last_preview_cache_at = 0.0
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(33)
        self.anim_timer.timeout.connect(self._advance)
        self.hide()

    def _advance(self):
        self.phase += 0.15
        self.marquee_offset += 1.35
        now = time.time()
        if now - self.last_preview_cache_at >= 0.45:
            self.preview_cache = QPixmap()
            self.last_preview_cache_at = now
        self.update()

    def show_state(self, state, bring_to_front=True):
        self.state = dict(state or {})
        if self.parentWidget() is not None:
            target = self.parentWidget().rect()
            if hasattr(self.parentWidget(), "display_rect"):
                display_rect = self.parentWidget().display_rect()
                if display_rect is not None and not display_rect.isEmpty():
                    target = display_rect
            elif hasattr(self.parentWidget(), "video_rect"):
                video_rect = self.parentWidget().video_rect()
                if video_rect is not None and not video_rect.isEmpty():
                    target = video_rect
            self.setGeometry(target)
        self.preview_cache = QPixmap()
        self.last_preview_cache_at = 0.0
        self.show()
        if bring_to_front:
            self.raise_()
        if not self.anim_timer.isActive():
            self.anim_timer.start()
        self.update()

    def clear_state(self):
        self.state = {}
        self.anim_timer.stop()
        self.preview_cache = QPixmap()
        self.last_preview_cache_at = 0.0
        self.hide()

    def paintEvent(self, event):
        if not self.state:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self.paint_radio_overlay(painter, self.rect())

    def render_frame(self, size):
        if not self.state:
            return QPixmap()
        target_size = QSize(max(1, size.width()), max(1, size.height()))
        pixmap = QPixmap(target_size)
        pixmap.fill(QColor(2, 4, 14))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self.paint_radio_overlay(painter, QRect(QPoint(0, 0), target_size))
        painter.end()
        return pixmap

    def preview_pixmap(self):
        if self.isVisible() and not self.preview_cache.isNull():
            return self.preview_cache
        target_rect = overlay_target_rect(self)
        target = self.size() if self.isVisible() and not self.size().isEmpty() else target_rect.size()
        if target.isEmpty():
            target = QSize(640, 480)
        self.preview_cache = self.render_frame(target)
        self.last_preview_cache_at = time.time()
        return self.preview_cache

    def paint_radio_overlay(self, painter, rect):
        palette = self.radio_palette()
        title = (self.state.get("title") or "Unknown Track").strip()
        artist = (self.state.get("artist") or "Unknown Artist").strip()
        album = (self.state.get("album") or "Unknown Album").strip()
        genre = (self.state.get("genre") or "").strip()
        year = (self.state.get("year") or "").strip()
        progress = max(0.0, min(1.0, float(self.state.get("progress", 0.0) or 0.0)))
        bands = list(self.state.get("bands") or [])
        layout = self.radio_layout(rect)

        self.draw_radio_background(painter, rect, palette)
        self.draw_xp_module(painter, layout["marquee"], palette, style="strip")
        self.draw_xp_module(painter, layout["visualizer"], palette, style="visualizer")
        self.draw_xp_module(painter, layout["bottom"], palette, style="dock")
        self.draw_marquee_bar(painter, layout["marquee"], palette)
        self.draw_visualizer_panel(painter, layout["visualizer"].adjusted(layout["inner_pad"], layout["inner_pad"], -layout["inner_pad"], -layout["inner_pad"]), progress, title, bands, palette)
        self.draw_now_playing_dock(
            painter,
            layout["bottom"].adjusted(layout["inner_pad"], layout["inner_pad"], -layout["inner_pad"], -layout["inner_pad"]),
            palette,
            artist,
            title,
            album,
            genre,
            year,
            self.state.get("art_pixmap"),
        )

    def radio_layout(self, rect):
        scale = min(rect.width() / 1280.0, rect.height() / 720.0)
        margin = max(18, int(26 * scale))
        gap = max(10, int(16 * scale))
        inner_pad = max(8, int(10 * scale))
        outer = rect.adjusted(margin, margin, -margin, -margin)

        marquee_h = max(32, int(rect.height() * 0.055))
        bottom_h = max(136, int(rect.height() * 0.24))

        marquee = QRect(outer.left(), outer.top(), outer.width(), marquee_h)
        visualizer_top = marquee.bottom() + gap
        visualizer_h = max(230, outer.height() - marquee_h - bottom_h - (gap * 2))
        visualizer = QRect(outer.left(), visualizer_top, outer.width(), visualizer_h)
        bottom = QRect(outer.left(), visualizer.bottom() + gap, outer.width(), bottom_h)

        return {
            "scale": scale,
            "margin": margin,
            "gap": gap,
            "inner_pad": inner_pad,
            "outer": outer,
            "marquee": marquee,
            "visualizer": visualizer,
            "bottom": bottom,
        }

    def radio_palette(self):
        return {
            "bg_top": QColor(18, 46, 122),
            "bg_bottom": QColor(6, 12, 34),
            "chrome_light": QColor(220, 235, 255),
            "chrome_mid": QColor(98, 152, 238),
            "chrome_dark": QColor(19, 42, 109),
            "panel_top": QColor(18, 44, 124),
            "panel_bottom": QColor(8, 18, 58),
            "panel_inner": QColor(5, 9, 26),
            "glass_top": QColor(255, 255, 255, 62),
            "glass_bottom": QColor(255, 255, 255, 10),
            "accent": QColor(152, 255, 122),
            "accent_soft": QColor(102, 214, 198),
            "accent_dark": QColor(22, 62, 48),
            "accent_text": QColor(12, 22, 16),
            "text": QColor(245, 248, 255),
            "subtext": QColor(205, 220, 242),
            "title": QColor(255, 255, 255),
            "warm": QColor(255, 226, 122),
            "violet": QColor(170, 150, 255),
            "orange": QColor(255, 174, 86),
            "cyan": QColor(104, 232, 255),
            "lime": QColor(142, 255, 112),
            "pink": QColor(255, 148, 222),
            "shadow": QColor(0, 0, 0, 190),
        }

    def draw_radio_background(self, painter, rect, palette):
        painter.save()
        bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg.setColorAt(0.0, palette["bg_top"])
        bg.setColorAt(0.56, QColor(22, 44, 104))
        bg.setColorAt(1.0, palette["bg_bottom"])
        painter.fillRect(rect, bg)

        for center, color, ratio in (
            (QPoint(rect.left() + rect.width() // 5, rect.top() + rect.height() // 4), QColor(184, 234, 255, 34), 0.24),
            (QPoint(rect.right() - rect.width() // 6, rect.top() + rect.height() // 5), QColor(164, 255, 118, 26), 0.20),
            (QPoint(rect.center().x(), rect.bottom() - rect.height() // 4), QColor(212, 124, 255, 20), 0.28),
        ):
            glow = QRadialGradient(center, int(min(rect.width(), rect.height()) * ratio))
            glow.setColorAt(0.0, color)
            glow.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillRect(rect, glow)

        painter.setPen(QPen(QColor(255, 255, 255, 8), 1))
        for y in range(rect.top(), rect.bottom(), 6):
            painter.drawLine(rect.left(), y, rect.right(), y)
        painter.restore()

    def draw_xp_module(self, painter, rect, palette, style="panel"):
        painter.save()
        radius = max(10, min(rect.width(), rect.height()) // 18)
        outer_grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        outer_grad.setColorAt(0.0, palette["chrome_light"])
        outer_grad.setColorAt(0.14, palette["chrome_mid"])
        outer_grad.setColorAt(1.0, palette["chrome_dark"])
        painter.setPen(Qt.NoPen)
        painter.setBrush(outer_grad)
        painter.drawRoundedRect(rect, radius, radius)

        inner = rect.adjusted(4, 4, -4, -4)
        inner_grad = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        if style == "strip":
            inner_grad.setColorAt(0.0, QColor(174, 228, 255))
            inner_grad.setColorAt(0.40, QColor(82, 170, 240))
            inner_grad.setColorAt(1.0, QColor(24, 62, 132))
        elif style == "dock":
            inner_grad.setColorAt(0.0, QColor(62, 98, 176))
            inner_grad.setColorAt(0.55, QColor(17, 35, 95))
            inner_grad.setColorAt(1.0, QColor(5, 15, 46))
        else:
            inner_grad.setColorAt(0.0, palette["panel_top"])
            inner_grad.setColorAt(0.56, QColor(12, 28, 80))
            inner_grad.setColorAt(1.0, palette["panel_bottom"])
        painter.setBrush(inner_grad)
        painter.drawRoundedRect(inner, max(7, radius - 3), max(7, radius - 3))

        gloss = QRect(inner.left() + 2, inner.top() + 2, inner.width() - 4, max(14, inner.height() // 5))
        gloss_grad = QLinearGradient(gloss.topLeft(), gloss.bottomLeft())
        gloss_grad.setColorAt(0.0, palette["glass_top"])
        gloss_grad.setColorAt(1.0, palette["glass_bottom"])
        painter.setBrush(gloss_grad)
        painter.drawRoundedRect(gloss, max(6, radius - 5), max(6, radius - 5))

        painter.setPen(QPen(QColor(255, 255, 255, 26), 1))
        painter.drawRoundedRect(inner.adjusted(1, 1, -1, -1), max(6, radius - 4), max(6, radius - 4))
        painter.restore()

    def draw_title_strip(self, painter, rect, palette, artist, title):
        self.draw_xp_module(painter, rect, palette, style="strip")
        inner = rect.adjusted(14, 8, -14, -8)
        left_label_w = min(max(114, int(inner.width() * 0.16)), 178)
        right_label_w = min(max(138, int(inner.width() * 0.23)), 230)
        middle_w = max(80, inner.width() - left_label_w - right_label_w - 22)
        label_font = self.fit_font_to_width("NOW PLAYING", left_label_w, max(11, rect.height() // 2 - 7), 9, weight=QFont.Bold, family=scifi2ki_font_family())
        status_font = self.fit_font_to_width("RADIOWAVETV // LIBRARY", right_label_w, max(9, rect.height() // 2 - 10), 8, weight=QFont.DemiBold, family=scifi2ki_font_family())
        center_text = f"{artist} — {title}" if artist else title
        title_font = self.fit_font_to_width(center_text, middle_w, max(14, rect.height() // 2 - 1), 10, weight=QFont.Bold, family=videophreak_font_family())

        self.draw_radio_text(painter, QRect(inner.left(), inner.top(), left_label_w, inner.height()), "NOW PLAYING", label_font, palette["accent_dark"], Qt.AlignLeft | Qt.AlignVCenter, elide=True)
        self.draw_radio_text(
            painter,
            QRect(inner.left() + left_label_w + 12, inner.top(), middle_w, inner.height()),
            center_text,
            title_font,
            palette["title"],
            Qt.AlignLeft | Qt.AlignVCenter,
            elide=True,
        )
        self.draw_radio_text(
            painter,
            QRect(inner.right() - right_label_w, inner.top(), right_label_w, inner.height()),
            "RADIOWAVETV // LIBRARY",
            status_font,
            palette["warm"],
            Qt.AlignRight | Qt.AlignVCenter,
            elide=True,
        )

    def draw_now_playing_dock(self, painter, rect, palette, artist, title, album, genre, year, art):
        inner = rect.adjusted(20, 16, -20, -16)
        art_size = min(inner.height(), max(94, rect.height() - 34))
        art_rect = QRect(inner.left(), inner.center().y() - art_size // 2, art_size, art_size)
        meta_rect = QRect(art_rect.right() + 20, inner.top(), max(20, inner.width() - art_size - 40), inner.height())

        self.draw_album_art(painter, art_rect, art, palette)

        status_h = max(16, meta_rect.height() // 6)
        title_h = max(28, meta_rect.height() // 4)
        artist_h = max(24, meta_rect.height() // 5)
        meta_h = max(24, meta_rect.height() // 5)
        time_w = min(118, max(82, meta_rect.width() // 7))
        text_w = max(40, meta_rect.width() - time_w - 12)

        status_rect = QRect(meta_rect.left(), meta_rect.top(), meta_rect.width(), status_h)
        title_rect = QRect(meta_rect.left(), status_rect.bottom() + 2, meta_rect.width(), title_h)
        artist_rect = QRect(meta_rect.left(), title_rect.bottom() + 2, meta_rect.width(), artist_h)
        meta_rect_line = QRect(meta_rect.left(), meta_rect.bottom() - meta_h, text_w, meta_h)
        time_rect = QRect(meta_rect.right() - time_w, meta_rect.bottom() - meta_h, time_w, meta_h)

        status_font = self.fit_font_to_width("RADIOWAVETV // DJ PLUMCRAZY", status_rect.width(), max(10, status_rect.height() - 4), 8, weight=QFont.DemiBold, family=scifi2ki_font_family())
        title_font = self.fit_font_to_width(title or "UNKNOWN TRACK", title_rect.width(), max(18, title_rect.height() - 2), 11, weight=QFont.Bold, family=videophreak_font_family())
        artist_font = self.fit_font_to_width(artist or "UNKNOWN ARTIST", artist_rect.width(), max(15, artist_rect.height() - 2), 10, weight=QFont.Bold, family=scifi2ki_font_family())
        meta_line = "  •  ".join(part for part in ((album or "").strip(), (year or "").strip(), (genre or "").strip()) if part) or "LOCAL LIBRARY ROTATION"
        meta_font = self.fit_font_to_width(meta_line, meta_rect_line.width(), max(13, meta_rect_line.height() - 2), 9, weight=QFont.DemiBold, family=scifi2ki_font_family())
        time_font = self.fit_font_to_width(time.strftime("%I:%M %p").lstrip("0"), time_rect.width(), max(13, time_rect.height() - 2), 10, weight=QFont.Bold, family=scifi2ki_font_family())

        self.draw_radio_text(painter, status_rect, "RADIOWAVETV // DJ PLUMCRAZY", status_font, palette["accent"], Qt.AlignLeft | Qt.AlignTop, elide=True)
        self.draw_radio_text(painter, title_rect, title or "UNKNOWN TRACK", title_font, palette["title"], Qt.AlignLeft | Qt.AlignVCenter, elide=True)
        self.draw_radio_text(painter, artist_rect, artist or "UNKNOWN ARTIST", artist_font, palette["warm"], Qt.AlignLeft | Qt.AlignVCenter, elide=True)
        self.draw_radio_text(painter, meta_rect_line, meta_line, meta_font, palette["subtext"], Qt.AlignLeft | Qt.AlignBottom, elide=True)
        self.draw_radio_text(painter, time_rect, time.strftime("%I:%M %p").lstrip("0"), time_font, palette["accent"], Qt.AlignRight | Qt.AlignBottom, elide=True)

    def draw_album_art(self, painter, art_rect, art, palette):
        frame = art_rect.adjusted(-3, -3, 3, 3)
        self.draw_xp_module(painter, frame, palette, style="dock")
        if isinstance(art, QPixmap) and not art.isNull():
            scaled = art.scaled(art_rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            source = QRect(
                max(0, (scaled.width() - art_rect.width()) // 2),
                max(0, (scaled.height() - art_rect.height()) // 2),
                art_rect.width(),
                art_rect.height(),
            )
            painter.drawPixmap(art_rect, scaled, source)
        else:
            fallback = QLinearGradient(art_rect.topLeft(), art_rect.bottomLeft())
            fallback.setColorAt(0.0, QColor(88, 130, 230))
            fallback.setColorAt(1.0, QColor(30, 52, 120))
            painter.fillRect(art_rect, fallback)
            icon_font = self.fit_font_to_width("RW", art_rect.width() - 12, max(20, art_rect.height() // 2), 16, weight=QFont.Bold)
            self.draw_radio_text(painter, art_rect, "RW", icon_font, palette["title"], Qt.AlignCenter, elide=False)

    def draw_marquee_bar(self, painter, rect, palette):
        inner = rect.adjusted(14, 6, -14, -6)
        remaining_ms = max(0, int((self.state.get("duration_ms") or 0) - (self.state.get("progress_ms") or 0)))
        remaining_text = format_countdown_time(remaining_ms)
        message = (
            f"You're watching RadioWaveTV!   "
            f"Brought to you by DJ PlumCrazy   "
            f"Local Time {time.strftime('%I:%M %p').lstrip('0')}   "
            f"Next Track In: {remaining_text}"
        )
        font = self.fit_font_to_width(message[:36], inner.width(), max(10, inner.height() - 4), 8, weight=QFont.DemiBold, family=scifi2ki_font_family())
        self.draw_radio_marquee_text(painter, inner, message, font, palette["subtext"])

    def draw_visualizer_panel(self, painter, rect, progress, seed_text, bands, palette):
        painter.save()
        painter.setClipRect(rect)
        viewport = rect.adjusted(16, 16, -16, -16)
        self.draw_xp_viewport(painter, viewport, palette)

        self.draw_retro_visualizer_backdrop(painter, viewport, palette)
        self.draw_visualizer(painter, viewport, progress, seed_text, bands, palette)
        painter.restore()

    def draw_xp_viewport(self, painter, rect, palette):
        painter.save()
        outer = rect.adjusted(-6, -6, 6, 6)
        bezel = QLinearGradient(outer.topLeft(), outer.bottomLeft())
        bezel.setColorAt(0.0, QColor(212, 232, 255))
        bezel.setColorAt(0.35, QColor(102, 142, 214))
        bezel.setColorAt(1.0, QColor(18, 32, 82))
        painter.setPen(Qt.NoPen)
        painter.setBrush(bezel)
        painter.drawRoundedRect(outer, 14, 14)
        inner = outer.adjusted(6, 6, -6, -6)
        inner_grad = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        inner_grad.setColorAt(0.0, QColor(5, 8, 18))
        inner_grad.setColorAt(1.0, QColor(0, 0, 0))
        painter.setBrush(inner_grad)
        painter.drawRoundedRect(inner, 10, 10)
        gloss = QRect(inner.left() + 2, inner.top() + 2, inner.width() - 4, max(18, inner.height() // 9))
        gloss_grad = QLinearGradient(gloss.topLeft(), gloss.bottomLeft())
        gloss_grad.setColorAt(0.0, QColor(255, 255, 255, 58))
        gloss_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(gloss_grad)
        painter.drawRoundedRect(gloss, 8, 8)
        painter.restore()

    def draw_retro_visualizer_backdrop(self, painter, rect, palette):
        painter.save()
        base = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        base.setColorAt(0.0, QColor(8, 18, 60))
        base.setColorAt(0.45, QColor(6, 12, 38))
        base.setColorAt(1.0, QColor(3, 7, 18))
        painter.fillRect(rect, base)
        painter.setPen(QPen(QColor(255, 255, 255, 10), 1))
        for y in range(rect.top() + 20, rect.bottom(), 18):
            painter.drawLine(rect.left(), y, rect.right(), y)
        painter.setPen(QPen(QColor(110, 178, 255, 10), 1))
        for x in range(rect.left() + 18, rect.right(), 18):
            painter.drawLine(x, rect.top(), x, rect.bottom())
        painter.restore()

    def draw_visualizer(self, painter, rect, progress, seed_text, bands, palette):
        painter.save()
        frame = rect.adjusted(10, 10, -10, -10)
        painter.setClipRect(frame)
        band_values = bands or [0.0] * 24
        if len(band_values) < 24:
            band_values = band_values + [0.0] * (24 - len(band_values))

        low = sum(band_values[:8]) / max(1, len(band_values[:8]))
        mid = sum(band_values[8:16]) / max(1, len(band_values[8:16]))
        high = sum(band_values[16:]) / max(1, len(band_values[16:]))
        average = sum(band_values) / max(1, len(band_values))
        bass = min(1.0, math.sqrt(max(0.0, low)) * 1.45)
        mids = min(1.0, math.sqrt(max(0.0, mid)) * 1.62)
        highs = min(1.0, math.sqrt(max(0.0, high)) * 1.78)
        energy = min(1.0, math.sqrt(max(0.0, average)) * 1.82)

        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Screen)
        wave_specs = [
            (QColor(96, 236, 255, 136), 0.55, 0.06 + bass * 0.10, 2.6),
            (QColor(255, 168, 84, 116), 0.82, 0.05 + highs * 0.09, 3.4),
        ]
        for color, speed, amp, cycles in wave_specs:
            path = QPainterPath()
            steps = 40
            baseline = frame.center().y()
            for step in range(steps + 1):
                t = step / steps
                x = frame.left() + t * frame.width()
                y = baseline + math.sin((t * math.tau * cycles) + self.phase * speed) * frame.height() * amp
                if step == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            self.stroke_glow_path(painter, path, color, 3.8 + energy * 1.8, 1.2 + energy * 0.5)
        painter.restore()

        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Screen)
        bar_area = frame.adjusted(20, 20, -20, -20)
        bar_count = min(16, len(band_values))
        bar_gap = max(4, bar_area.width() // 120)
        bar_w = max(10, (bar_area.width() - ((bar_count - 1) * bar_gap)) // bar_count)
        segment_gap = 4
        segment_h = max(8, bar_area.height() // 26)
        total_segments = max(8, (bar_area.height() + segment_gap) // (segment_h + segment_gap))
        active_colors = [
            QColor(38, 255, 82),
            QColor(52, 255, 64),
            QColor(90, 255, 56),
            QColor(160, 255, 52),
            QColor(234, 255, 70),
            QColor(255, 225, 64),
            QColor(255, 156, 54),
            QColor(255, 74, 74),
        ]
        inactive_color = QColor(32, 10, 10, 150)
        peak_color = QColor(255, 240, 120)

        for idx in range(bar_count):
            src_index = int((idx / max(1, bar_count - 1)) * (len(band_values) - 1))
            value = band_values[src_index]
            shaped_value = min(1.0, max(0.0, (value * 0.34) + (energy * 0.08)))
            lit_segments = max(1, int(round(shaped_value * total_segments)))
            peak_segment = min(total_segments - 1, lit_segments + int((math.sin(self.phase * 1.2 + idx * 0.6) + 1.0) * 0.8))
            x = bar_area.left() + idx * (bar_w + bar_gap)

            for seg in range(total_segments):
                seg_from_bottom = seg
                y = bar_area.bottom() - ((seg_from_bottom + 1) * (segment_h + segment_gap))
                seg_rect = QRect(x, y, bar_w, segment_h)
                if seg_rect.bottom() < bar_area.top():
                    continue
                if seg_from_bottom < lit_segments:
                    color_index = min(len(active_colors) - 1, int((seg_from_bottom / max(1, total_segments - 1)) * len(active_colors)))
                    base = active_colors[color_index]
                    grad = QLinearGradient(seg_rect.topLeft(), seg_rect.bottomLeft())
                    grad.setColorAt(0.0, QColor(base.red(), base.green(), base.blue(), 255))
                    grad.setColorAt(1.0, QColor(max(0, base.red() - 22), max(0, base.green() - 22), max(0, base.blue() - 22), 220))
                    painter.setBrush(grad)
                    painter.setPen(QPen(QColor(255, 255, 255, 26), 1))
                else:
                    painter.setBrush(inactive_color)
                    painter.setPen(QPen(QColor(255, 255, 255, 10), 1))
                painter.drawRoundedRect(seg_rect, 2, 2)

            peak_y = bar_area.bottom() - ((peak_segment + 1) * (segment_h + segment_gap))
            peak_rect = QRect(x, peak_y, bar_w, segment_h)
            if peak_rect.top() >= bar_area.top():
                painter.setBrush(QColor(peak_color.red(), peak_color.green(), peak_color.blue(), 210))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(peak_rect, 2, 2)
        painter.restore()

        painter.setPen(QPen(QColor(255, 255, 255, 26), 1))
        painter.drawLine(frame.left(), frame.bottom() - 4, frame.right(), frame.bottom() - 4)
        painter.setPen(QPen(QColor(palette["accent"].red(), palette["accent"].green(), palette["accent"].blue(), 130), 2))
        indicator_x = frame.left() + int(frame.width() * progress)
        painter.drawLine(indicator_x, frame.bottom() - 10, indicator_x, frame.bottom() - 1)
        painter.restore()

    def stroke_glow_path(self, painter, path, color, glow_width, core_width):
        glow_pen = QPen(QColor(color.red(), color.green(), color.blue(), min(255, color.alpha() // 2 + 42)), glow_width)
        glow_pen.setCapStyle(Qt.RoundCap)
        glow_pen.setJoinStyle(Qt.RoundJoin)
        core_pen = QPen(color, core_width)
        core_pen.setCapStyle(Qt.RoundCap)
        core_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(glow_pen)
        painter.drawPath(path)
        painter.setPen(core_pen)
        painter.drawPath(path)

    def fit_font_to_width(self, text, max_width, preferred_size, minimum_size, weight=QFont.Bold, family=None):
        family = family or guide_font_family("primary")
        safe_width = max(12, int(max_width))
        size = max(int(preferred_size), int(minimum_size))
        while size > int(minimum_size):
            font = QFont(family, size, weight)
            metrics = QFontMetrics(font)
            if metrics.horizontalAdvance(text) <= safe_width:
                return font
            size -= 1
        return QFont(family, int(minimum_size), weight)

    def fit_font_for_block(self, text, rect, preferred_size, minimum_size, weight=QFont.Bold, family=None, flags=Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap):
        family = family or guide_font_family("primary")
        size = max(int(preferred_size), int(minimum_size))
        probe_rect = QRect(0, 0, max(10, rect.width()), max(10, rect.height()))
        while size > int(minimum_size):
            font = QFont(family, size, weight)
            metrics = QFontMetrics(font)
            bound = metrics.boundingRect(probe_rect, flags, text)
            if bound.width() <= probe_rect.width() and bound.height() <= probe_rect.height():
                return font
            size -= 1
        return QFont(family, int(minimum_size), weight)

    def draw_radio_text(self, painter, rect, text, font, color, align, elide=False):
        text = (text or "").strip()
        if not text or rect.width() <= 0 or rect.height() <= 0:
            return
        painter.save()
        painter.setFont(font)
        render_text = text
        if elide and not (align & Qt.TextWordWrap):
            render_text = QFontMetrics(font).elidedText(text, Qt.ElideRight, max(10, rect.width()))
        for dx, dy in ((1, 1), (2, 2)):
            painter.setPen(QColor(0, 0, 0, 180))
            painter.drawText(rect.translated(dx, dy), align, render_text)
        painter.setPen(color)
        painter.drawText(rect, align, render_text)
        painter.restore()

    def draw_radio_marquee_text(self, painter, rect, text, font, color):
        text = (text or "").strip()
        if not text or rect.width() <= 0 or rect.height() <= 0:
            return
        painter.save()
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        painter.setClipRect(rect)
        if text_width <= rect.width():
            self.draw_radio_text(painter, rect, text, font, color, Qt.AlignLeft | Qt.AlignVCenter, elide=False)
            painter.restore()
            return
        gap = max(48, metrics.horizontalAdvance("     "))
        cycle_width = text_width + gap
        offset = self.marquee_offset % cycle_width
        first_rect = QRect(int(rect.left() - offset), rect.top(), text_width + 12, rect.height())
        second_rect = QRect(first_rect.left() + cycle_width, rect.top(), text_width + 12, rect.height())
        self.draw_radio_text(painter, first_rect, text, font, color, Qt.AlignLeft | Qt.AlignVCenter, elide=False)
        self.draw_radio_text(painter, second_rect, text, font, color, Qt.AlignLeft | Qt.AlignVCenter, elide=False)
        painter.restore()

    def draw_outlined_text(self, painter, rect, text, color, size, align=Qt.AlignHCenter | Qt.AlignVCenter | Qt.TextWordWrap):
        text = (text or "").strip()
        if not text:
            return
        font = QFont(guide_font_family("primary"), size, QFont.Bold)
        self.draw_radio_text(painter, rect, text, font, color, align)

    def draw_music_choice_text(self, painter, rect, text, color, font, align):
        if not text:
            return
        active_font = font if isinstance(font, QFont) else QFont(guide_font_family("primary"), int(font), QFont.Bold)
        self.draw_radio_text(painter, rect, text, active_font, color, align)


class NetTVStatusOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title = "NetTV"
        self.message = "Preparing channel..."
        self.marquee_offset = 0
        self.marquee_timer = QTimer(self)
        self.marquee_timer.setInterval(45)
        self.marquee_timer.timeout.connect(self.advance_marquee)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)

    def show_status(self, title="", message="Preparing NetTV channel"):
        self.title = (title or "NetTV").strip()
        self.message = (message or "Preparing NetTV channel").strip()
        if not self.marquee_timer.isActive():
            self.marquee_timer.start()
        self.show()
        self.raise_()
        self.update()

    def advance_marquee(self):
        self.marquee_offset = (self.marquee_offset + 3) % 20000
        self.update()

    def hideEvent(self, event):
        self.marquee_timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        display_rect = self.parent().display_rect() if hasattr(self.parent(), "display_rect") else self.rect()
        if display_rect is None or display_rect.isEmpty():
            display_rect = self.rect()
        draw_nettv_standby_scene(painter, display_rect, self.title, self.message, self.marquee_offset)


class VideoWindow(QWidget):
    channelUpRequested = Signal()
    channelDownRequested = Signal()
    guideRequested = Signal()
    guideUpRequested = Signal()
    guideDownRequested = Signal()
    guideLeftRequested = Signal()
    guideRightRequested = Signal()
    guideSelectRequested = Signal()
    guideCloseRequested = Signal()
    guideSettingsRequested = Signal()
    onDemandRequested = Signal()
    onDemandSettingsRequested = Signal()
    onDemandUpRequested = Signal()
    onDemandDownRequested = Signal()
    onDemandLeftRequested = Signal()
    onDemandRightRequested = Signal()
    onDemandSelectRequested = Signal()
    onDemandCloseRequested = Signal()
    playbackToggleRequested = Signal()
    infoRequested = Signal()
    infoLeftRequested = Signal()
    infoRightRequested = Signal()
    infoUpRequested = Signal()
    infoDownRequested = Signal()
    infoSelectRequested = Signal()
    infoCloseRequested = Signal()
    onDemandSeekRequested = Signal(int)
    onDemandSeekPressChanged = Signal(int, bool)
    uiScaleRequested = Signal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Player")
        self.setStyleSheet("background-color: black;")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setFocusPolicy(Qt.StrongFocus)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.video_surface = VideoSurface(self)
        self.video_surface.setFocusPolicy(Qt.NoFocus)
        self.video_surface.setStyleSheet("background-color: black;")
        layout.addWidget(self.video_surface)
        self.setLayout(layout)

        self.weather_view = QWebEngineView(self.video_surface)
        self.weather_view.hide()
        self.weather_view.loadFinished.connect(self.on_weather_view_loaded)
        self.weather_view.settings().setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        self.weather_view.page().setAudioMuted(False)
        self.weather_preview_frame = QPixmap()
        self.weather_capture_timer = QTimer(self)
        self.weather_capture_timer.setInterval(750)
        self.weather_capture_timer.timeout.connect(self.capture_weather_frame)

        self.spotify_view = QWebEngineView(self.video_surface)
        self.spotify_view.hide()
        self.spotify_view.loadFinished.connect(self.on_spotify_view_loaded)
        self.spotify_view.settings().setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        self.spotify_view.page().setAudioMuted(True)
        self.spotify_preview_frame = QPixmap()
        self.spotify_capture_timer = QTimer(self)
        self.spotify_capture_timer.setInterval(900)
        self.spotify_capture_timer.timeout.connect(self.capture_spotify_frame)
        self.spotify_poll_timer = QTimer(self)
        self.spotify_poll_timer.setInterval(1400)
        self.spotify_poll_timer.timeout.connect(self.poll_spotify_state)
        self.spotify_info = {
            "title": "",
            "artist": "",
            "album": "",
            "year": "",
            "art_url": "",
            "art_pixmap": QPixmap(),
            "progress_ms": 0,
            "duration_ms": 0,
            "lyrics_lines": [],
        }
        self.spotify_url = ""
        self.spotify_karaoke_mode = True

        self.youtube_view = QWebEngineView(self.video_surface)
        self.youtube_view.hide()
        self.youtube_view.settings().setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        self.youtube_view.page().setAudioMuted(False)
        self.youtube_url = ""

        self.nettv_status_overlay = NetTVStatusOverlay(self.video_surface)
        self.nettv_status_overlay.hide()
        self.static = StaticOverlay(self.video_surface)
        self.static.hide()
        self.channel_overlay = ChannelOverlay(self.video_surface)
        self.channel_overlay.hide()
        self.guide_overlay = GuideOverlay(self.video_surface)
        self.guide_overlay.hide()
        self.on_demand_overlay = OnDemandOverlay(self.video_surface)
        self.on_demand_overlay.hide()
        self.info_overlay = InfoOverlay(self.video_surface)
        self.info_overlay.hide()
        self.next_up_overlay = NextUpOverlay(self.video_surface)
        self.next_up_overlay.hide()
        self.transport_overlay = TransportOverlay(self.video_surface)
        self.transport_overlay.hide()
        self.ui_scale_overlay = UIScaleOverlay(self.video_surface)
        self.ui_scale_overlay.hide()
        self.spotify_overlay = RadioWaveOverlay(self.video_surface)
        self.spotify_overlay.hide()
        self.radiowave_preview_frame = QPixmap()
        self.radiowave_preview_dirty = True

        self.return_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        self.return_shortcut.setContext(Qt.WindowShortcut)
        self.return_shortcut.activated.connect(self.handle_overlay_enter_shortcut)
        self.enter_shortcut = QShortcut(QKeySequence(Qt.Key_Enter), self)
        self.enter_shortcut.setContext(Qt.WindowShortcut)
        self.enter_shortcut.activated.connect(self.handle_overlay_enter_shortcut)

        for watched in (
            self,
            self.video_surface,
            self.weather_view,
            self.spotify_view,
            self.youtube_view,
            self.nettv_status_overlay,
            self.guide_overlay,
            self.on_demand_overlay,
            self.info_overlay,
            self.next_up_overlay,
            self.transport_overlay,
            self.ui_scale_overlay,
            self.spotify_overlay,
        ):
            watched.installEventFilter(self)

    def configure_display(self, profile_name, theme_name, skin_name, ui_scale=GUIDE_UI_SCALE_DEFAULT):
        skin_name = normalize_skin_name(skin_name)
        theme_name = normalize_theme_for_skin(skin_name, theme_name)
        self.video_surface.set_display_profile(profile_name)
        self.guide_overlay.configure(profile_name, theme_name, skin_name, ui_scale)
        self.on_demand_overlay.configure(profile_name, theme_name, skin_name, ui_scale)
        self.info_overlay.configure(profile_name, theme_name, skin_name, ui_scale)
        self.next_up_overlay.configure(theme_name, skin_name, ui_scale)
        self.transport_overlay.configure(theme_name, skin_name, ui_scale)
        self.update_special_view_geometry()

    def resizeEvent(self, event):
        self.update_special_view_geometry()
        self.static.setGeometry(self.video_surface.rect())
        self.channel_overlay.setGeometry(self.video_surface.rect())
        self.guide_overlay.setGeometry(self.video_surface.rect())
        self.on_demand_overlay.setGeometry(self.video_surface.rect())
        self.info_overlay.setGeometry(self.video_surface.rect())
        self.next_up_overlay.setGeometry(self.video_surface.rect())
        self.transport_overlay.setGeometry(self.video_surface.rect())
        self.ui_scale_overlay.setGeometry(self.video_surface.rect())
        self.spotify_overlay.setGeometry(self.video_surface.rect())
        self.nettv_status_overlay.setGeometry(self.video_surface.rect())
        super().resizeEvent(event)

    def update_special_view_geometry(self):
        rect = self.video_surface.display_rect()
        if rect is None or rect.isEmpty():
            rect = self.video_surface.rect()
        self.weather_view.setGeometry(rect)
        self.spotify_view.setGeometry(rect)
        self.youtube_view.setGeometry(rect)
        self.apply_weather_view_layout()

    def show_nettv_status(self, title="", message="Preparing NetTV channel"):
        self.nettv_status_overlay.setGeometry(self.video_surface.rect())
        self.static.raise_()
        self.channel_overlay.raise_()
        self.guide_overlay.raise_()
        self.on_demand_overlay.raise_()
        self.info_overlay.raise_()
        self.next_up_overlay.raise_()
        self.transport_overlay.raise_()
        self.ui_scale_overlay.raise_()
        self.nettv_status_overlay.show_status(title, message)

    def hide_nettv_status(self):
        self.nettv_status_overlay.hide()

    def handle_overlay_enter_shortcut(self):
        if self.on_demand_overlay.isVisible():
            self.onDemandSelectRequested.emit()
            return
        if self.info_overlay.isVisible():
            self.infoSelectRequested.emit()
            return
        if self.guide_overlay.isVisible():
            self.guideSelectRequested.emit()
            return

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if self.on_demand_overlay.isVisible():
                if key == Qt.Key_Left:
                    self.onDemandLeftRequested.emit()
                    return True
                if key == Qt.Key_Right:
                    self.onDemandRightRequested.emit()
                    return True
                if key == Qt.Key_Up:
                    self.onDemandUpRequested.emit()
                    return True
                if key == Qt.Key_Down:
                    self.onDemandDownRequested.emit()
                    return True
                if key in (Qt.Key_Return, Qt.Key_Enter):
                    self.onDemandSelectRequested.emit()
                    return True
                if key == Qt.Key_Escape:
                    self.onDemandCloseRequested.emit()
                    return True
                if key == Qt.Key_M:
                    self.onDemandSettingsRequested.emit()
                    return True
            if self.info_overlay.isVisible():
                if key == Qt.Key_Left:
                    self.infoLeftRequested.emit()
                    return True
                if key == Qt.Key_Right:
                    self.infoRightRequested.emit()
                    return True
                if key == Qt.Key_Up:
                    self.infoUpRequested.emit()
                    return True
                if key == Qt.Key_Down:
                    self.infoDownRequested.emit()
                    return True
                if key in (Qt.Key_Return, Qt.Key_Enter):
                    self.infoSelectRequested.emit()
                    return True
                if key == Qt.Key_Escape:
                    self.infoCloseRequested.emit()
                    return True
            if self.guide_overlay.isVisible():
                if key == Qt.Key_Left:
                    self.guideLeftRequested.emit()
                    return True
                if key == Qt.Key_Right:
                    self.guideRightRequested.emit()
                    return True
                if key == Qt.Key_Up:
                    self.guideUpRequested.emit()
                    return True
                if key == Qt.Key_Down:
                    self.guideDownRequested.emit()
                    return True
                if key in (Qt.Key_Return, Qt.Key_Enter):
                    self.guideSelectRequested.emit()
                    return True
                if key == Qt.Key_Escape:
                    self.guideCloseRequested.emit()
                    return True
                if key == Qt.Key_M:
                    self.guideSettingsRequested.emit()
                    return True
        return super().eventFilter(obj, event)

    def hide_special_views(self):
        self.weather_capture_timer.stop()
        self.weather_view.page().setAudioMuted(True)
        self.weather_view.page().runJavaScript(
            """
(() => {
  document.querySelectorAll('audio, video').forEach((node) => {
    try { node.muted = true; node.volume = 0.0; } catch (e) {}
  });
})();
"""
        )
        self.weather_view.hide()
        self.spotify_view.page().setAudioMuted(True)
        self.spotify_view.hide()
        self.spotify_overlay.hide()
        self.youtube_view.page().setAudioMuted(True)
        self.youtube_view.hide()

    def show_radiowave_channel(self, state):
        self.hide_nettv_status()
        self.spotify_overlay.show_state(state, bring_to_front=True)
        preview = self.spotify_overlay.preview_pixmap()
        if not preview.isNull():
            self.radiowave_preview_frame = preview
            self.radiowave_preview_dirty = False
        self.static.raise_()
        self.channel_overlay.raise_()
        self.guide_overlay.raise_()
        self.on_demand_overlay.raise_()
        self.info_overlay.raise_()
        self.next_up_overlay.raise_()
        self.transport_overlay.raise_()

    def update_radiowave_channel(self, state):
        if self.spotify_overlay.isVisible():
            self.spotify_overlay.show_state(state, bring_to_front=False)
            self.radiowave_preview_dirty = False
            if self.guide_overlay.isVisible():
                self.guide_overlay.raise_()
            if self.on_demand_overlay.isVisible():
                self.on_demand_overlay.raise_()
            if self.info_overlay.isVisible():
                self.info_overlay.raise_()
            if self.next_up_overlay.isVisible():
                self.next_up_overlay.raise_()
            if self.transport_overlay.isVisible():
                self.transport_overlay.raise_()
        else:
            self.spotify_overlay.state = dict(state or {})
            self.spotify_overlay.preview_cache = QPixmap()
            self.radiowave_preview_dirty = True

    def hide_radiowave_channel(self):
        self.spotify_overlay.hide()

    def radiowave_preview_pixmap(self):
        if self.spotify_overlay.isVisible():
            pixmap = self.spotify_overlay.preview_pixmap()
            if not pixmap.isNull():
                self.radiowave_preview_frame = pixmap
                self.radiowave_preview_dirty = False
                return pixmap
        if not self.radiowave_preview_frame.isNull() and not self.radiowave_preview_dirty:
            return self.radiowave_preview_frame
        preview_size = QSize(640, 360)
        rect = self.video_surface.display_rect()
        if rect is not None and not rect.isEmpty():
            preview_size = rect.size()
        pixmap = self.spotify_overlay.render_frame(preview_size)
        if not pixmap.isNull():
            self.radiowave_preview_frame = pixmap
            self.radiowave_preview_dirty = False
        return pixmap

    def show_weather_channel(self, url):
        self.hide_nettv_status()
        self.update_special_view_geometry()
        if self.weather_view.url().toString() != url:
            self.weather_view.setUrl(QUrl(url))
        self.weather_view.page().setAudioMuted(False)
        self.weather_view.page().runJavaScript(
            """
(() => {
  document.querySelectorAll('audio, video').forEach((node) => {
    try {
      node.muted = false;
      node.volume = 1.0;
      node.play?.();
    } catch (e) {}
  });
})();
"""
        )
        self.weather_view.show()
        self.weather_view.lower()
        self.weather_capture_timer.stop()
        QTimer.singleShot(200, self.capture_weather_frame)
        QTimer.singleShot(1200, self.capture_weather_frame)
        self.static.raise_()
        self.channel_overlay.raise_()
        self.guide_overlay.raise_()
        self.on_demand_overlay.raise_()
        self.info_overlay.raise_()
        self.next_up_overlay.raise_()
        self.transport_overlay.raise_()

    def show_spotify_channel(self, url, karaoke_mode=True):
        self.hide_nettv_status()
        self.update_special_view_geometry()
        self.spotify_karaoke_mode = bool(karaoke_mode)
        if self.spotify_view.url().toString() != url:
            self.spotify_view.setUrl(QUrl(url))
        self.spotify_url = url
        self.spotify_view.setGeometry(self.video_surface.display_rect())
        self.spotify_view.page().setAudioMuted(False)
        self.spotify_view.page().runJavaScript(
            """
(() => {
  const randomChoice = (items) => items[Math.floor(Math.random() * items.length)];
  const clickIf = (matcher) => {
    const nodes = Array.from(document.querySelectorAll('button, [role="button"], a'));
    for (const node of nodes) {
      const text = ((node.innerText || node.textContent || node.ariaLabel || node.title || '') + '').trim().toLowerCase();
      if (matcher(text, node)) {
        try { node.click(); return true; } catch (e) {}
      }
    }
    return false;
  };
  const media = document.querySelector('audio, video');
  if (media) {
    try { media.muted = false; media.volume = 1.0; media.play?.(); } catch (e) {}
  }
  clickIf((text) => text.includes('shuffle') && !text.includes('off'));
  const tracks = Array.from(document.querySelectorAll('a[href*="/track/"], [data-testid="tracklist-row"] a, [role="row"] a[href*="/track/"]'))
    .filter((node) => node.offsetParent !== null);
  if (tracks.length > 0) {
    try { randomChoice(tracks).click(); } catch (e) {}
  } else {
    clickIf((text) => text === 'play' || text.includes('resume') || text.includes('play playlist') || text.includes('play album'));
  }
})();
"""
        )
        self.spotify_view.show()
        self.spotify_view.lower()
        self.spotify_capture_timer.start()
        self.spotify_poll_timer.start()
        self.spotify_overlay.show_state({
            **self.spotify_info,
            "progress": ((self.spotify_info.get("progress_ms") or 0) / max(1, (self.spotify_info.get("duration_ms") or 1))),
        })
        self.spotify_overlay.raise_()
        self.static.raise_()
        self.channel_overlay.raise_()
        self.guide_overlay.raise_()
        self.on_demand_overlay.raise_()
        self.info_overlay.raise_()
        self.next_up_overlay.raise_()
        self.transport_overlay.raise_()

    def preload_spotify_channel(self, url, karaoke_mode=True):
        if not url:
            return
        self.update_special_view_geometry()
        self.spotify_karaoke_mode = bool(karaoke_mode)
        if self.spotify_view.url().toString() != url:
            self.spotify_view.setUrl(QUrl(url))
        self.spotify_url = url
        self.spotify_view.page().setAudioMuted(True)
        self.spotify_view.hide()

    def show_youtube_channel(self, url):
        if not url:
            return
        self.update_special_view_geometry()
        if self.youtube_view.url().toString() != url:
            self.youtube_view.setUrl(QUrl(url))
        self.youtube_url = url
        self.youtube_view.page().setAudioMuted(False)
        self.youtube_view.show()
        self.youtube_view.lower()
        QTimer.singleShot(
            1400,
            lambda: self.youtube_view.page().runJavaScript(
                """
(() => {
  const media = document.querySelector('video');
  if (media) {
    try { media.muted = false; media.volume = 1.0; media.play?.(); } catch (e) {}
  }
  const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
  for (const button of buttons) {
    const label = ((button.ariaLabel || button.title || button.innerText || '') + '').toLowerCase();
    if (label.includes('play')) {
      try { button.click(); break; } catch (e) {}
    }
  }
})();
"""
            ),
        )
        self.static.raise_()
        self.channel_overlay.raise_()
        self.guide_overlay.raise_()
        self.on_demand_overlay.raise_()
        self.info_overlay.raise_()
        self.next_up_overlay.raise_()
        self.transport_overlay.raise_()

    def preload_youtube_channel(self, url):
        if not url:
            return
        self.update_special_view_geometry()
        if self.youtube_view.url().toString() != url:
            self.youtube_view.setUrl(QUrl(url))
        self.youtube_url = url
        self.youtube_view.page().setAudioMuted(True)
        self.youtube_view.hide()

    def preload_weather_channel(self, url):
        self.update_special_view_geometry()
        if self.weather_view.url().toString() != url:
            self.weather_view.setUrl(QUrl(url))
        self.weather_view.page().setAudioMuted(True)
        self.weather_capture_timer.start()

    def weather_preview_pixmap(self):
        if self.weather_view.isVisible():
            pixmap = self.weather_view.grab()
            if not pixmap.isNull():
                self.weather_preview_frame = pixmap
                return pixmap
        if not self.weather_preview_frame.isNull():
            return self.weather_preview_frame
        if not self.weather_view.url().isValid():
            return QPixmap()
        return self.weather_view.grab()

    def capture_weather_frame(self):
        if not self.weather_view.url().isValid():
            return
        pixmap = self.weather_view.grab()
        if not pixmap.isNull():
            self.weather_preview_frame = pixmap

    def on_weather_view_loaded(self, ok):
        if not ok:
            return
        script = r"""
(() => {
  const textOf = (el) => ((el?.innerText || el?.textContent || el?.ariaLabel || el?.title || el?.alt || '') + '').trim().toLowerCase();
  const clickIf = (matcher) => {
    const nodes = Array.from(document.querySelectorAll('button, [role="button"], a, img, input[type="button"]'));
    for (const node of nodes) {
      const text = textOf(node);
      if (matcher(text, node)) {
        try { node.click(); return true; } catch (e) {}
      }
    }
    return false;
  };
  document.querySelectorAll('audio, video').forEach((node) => {
    try {
      node.muted = false;
      node.volume = 1.0;
      node.play?.();
    } catch (e) {}
  });
  clickIf((text) => text.includes('unmute') || text.includes('mute off'));
  clickIf((text) => text === 'play' || text.includes('play weatherstar') || text.includes('resume'));
})();
"""
        self.weather_view.page().runJavaScript(script)
        self.apply_weather_view_layout()
        QTimer.singleShot(900, self.capture_weather_frame)

    def apply_weather_view_layout(self):
        rect = self.weather_view.geometry()
        if rect.isEmpty():
            return
        base_width = 640.0
        base_height = 480.0
        zoom = max(rect.width() / base_width, rect.height() / base_height)
        self.weather_view.setZoomFactor(max(0.75, min(2.2, zoom)))
        if not self.weather_view.url().isValid():
            return
        script = r"""
(() => {
  const body = document.body;
  const doc = document.documentElement;
  if (!body || !doc) return;
  try {
    body.style.margin = '0';
    body.style.transform = 'none';
    body.style.transformOrigin = 'top left';
    body.style.overflow = 'hidden';
    doc.style.overflow = 'hidden';
    body.style.background = 'black';
    doc.style.background = 'black';
  } catch (e) {}
})();
"""
        self.weather_view.page().runJavaScript(script)

    def on_spotify_view_loaded(self, ok):
        if not ok:
            return
        script = r"""
(() => {
  const randomChoice = (items) => items[Math.floor(Math.random() * items.length)];
  const clickIf = (matcher) => {
    const nodes = Array.from(document.querySelectorAll('button, [role="button"], a'));
    for (const node of nodes) {
      const text = ((node.innerText || node.textContent || node.ariaLabel || node.title || '') + '').trim().toLowerCase();
      if (matcher(text, node)) {
        try { node.click(); return true; } catch (e) {}
      }
    }
    return false;
  };
  const media = document.querySelector('audio, video');
  const pickText = (...selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      const text = ((node?.innerText || node?.textContent || node?.ariaLabel || node?.title || '') + '').trim();
      if (text) return text;
    }
    return '';
  };
  const pickAttr = (attr, ...selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      const value = ((node?.getAttribute?.(attr) || node?.[attr] || '') + '').trim();
      if (value) return value;
    }
    return '';
  };
  if (media) {
    try {
      media.muted = true;
      media.volume = 0.0;
      media.play?.();
    } catch (e) {}
  }
  clickIf((text) => text.includes('shuffle') && !text.includes('off'));
  const tracks = Array.from(document.querySelectorAll('a[href*="/track/"], [data-testid="tracklist-row"] a, [role="row"] a[href*="/track/"]'))
    .filter((node) => node.offsetParent !== null);
  if (tracks.length > 0) {
    try { randomChoice(tracks).click(); } catch (e) {}
  } else {
    clickIf((text) => text === 'play' || text.includes('resume') || text.includes('play playlist') || text.includes('play album'));
  }
  return {
    title: pickText('[data-testid="track-info-name"] a', '[data-testid="entityTitle"] a', '[data-testid="context-item-link"]'),
    artist: pickText('[data-testid="track-info-artists"] a', '[data-testid="entity-subtitle"] a', '[data-testid="context-item-info-artist"]'),
    album: pickText('[data-testid="context-item-info-album"]', '[data-testid="entity-subtitle"] a + span', '[aria-label*="album"]'),
    art: pickAttr('src', 'img[data-testid="cover-art-image"]', 'img[alt*="Cover art"]', 'img[draggable="false"]'),
    ogart: pickAttr('content', 'meta[property="og:image"]')
  };
})();
"""
        self.spotify_view.page().runJavaScript(script, self.on_spotify_bootstrap_state)
        QTimer.singleShot(1400, self.poll_spotify_state)
        QTimer.singleShot(1600, self.capture_spotify_frame)

    def on_spotify_bootstrap_state(self, state):
        if isinstance(state, dict):
            self.update_spotify_metadata_from_state(state)

    def poll_spotify_state(self):
        if not self.spotify_url:
            return
        script = r"""
(() => {
  const pick = (...selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      const text = ((node?.innerText || node?.textContent || '') + '').trim();
      if (text) return text;
    }
    return '';
  };
  const media = document.querySelector('audio, video');
  let title = pick('[data-testid="context-item-link"]', '[data-testid="entityTitle"] a', '[data-testid="track-info-name"] a');
  let artist = pick('[data-testid="context-item-info-artist"]', '[data-testid="track-info-artists"] a', '[data-testid="entity-subtitle"] a');
  let album = pick('[data-testid="context-item-info-album"]', '[aria-label*="album"]', '[data-testid="entity-subtitle"] span');
  let art = '';
  const artNode = document.querySelector('img[data-testid="cover-art-image"], img[alt*="Cover art"], img[draggable="false"]');
  if (artNode) {
    art = artNode.getAttribute('src') || artNode.src || '';
  }
  if (!art) {
    const og = document.querySelector('meta[property=\"og:image\"]');
    art = og?.getAttribute('content') || '';
  }
  const docTitle = (document.title || '').replace(/\s*\|\s*Spotify\s*$/i, '').trim();
  if (!title && docTitle) {
    const match = docTitle.match(/^(.*?)\s*-\s*(?:song and lyrics by|song by)\s*(.*)$/i);
    if (match) {
      title = match[1].trim();
      artist = artist || match[2].trim();
    } else {
      title = docTitle;
    }
  }
  const progressText = pick('[data-testid="playback-position"]');
  const durationText = pick('[data-testid="playback-duration"]');
  return {
    title,
    artist,
    album,
    art,
    progressText,
    durationText,
    currentTime: media ? media.currentTime : null,
    duration: media ? media.duration : null
  };
})();
"""
        self.spotify_view.page().runJavaScript(script, self.on_spotify_state_polled)

    def on_spotify_state_polled(self, state):
        if not isinstance(state, dict):
            return
        title = (state.get("title") or self.spotify_info.get("title") or "Unknown Track").strip()
        artist = (state.get("artist") or self.spotify_info.get("artist") or "").strip()
        album = (state.get("album") or self.spotify_info.get("album") or "").strip()
        art_url = (state.get("art") or self.spotify_info.get("art_url") or "").strip()
        progress_ms = int((state.get("currentTime") or 0) * 1000) if state.get("currentTime") is not None else 0
        duration_ms = int((state.get("duration") or 0) * 1000) if state.get("duration") is not None else 0
        if duration_ms <= 0:
            parsed = parse_timecode_to_seconds(state.get("durationText"))
            duration_ms = int((parsed or 0) * 1000)
        if progress_ms <= 0:
            parsed = parse_timecode_to_seconds(state.get("progressText"))
            progress_ms = int((parsed or 0) * 1000)
        if (not artist or not album or not art_url) and title:
            fallback = fetch_track_metadata_fallback(artist, title)
            artist = artist or fallback.get("artist", "")
            album = album or fallback.get("album", "")
            art_url = art_url or fallback.get("art_url", "")
        lyrics_lines = self.spotify_info.get("lyrics_lines", [])
        if title and artist and (title != self.spotify_info.get("title") or artist != self.spotify_info.get("artist")):
            lyrics_lines = self.lookup_spotify_lyrics(artist, title)
        art_pixmap = self.spotify_info.get("art_pixmap", QPixmap())
        if art_url and art_url != self.spotify_info.get("art_url"):
            art_pixmap = self.load_spotify_artwork(art_url)
        self.spotify_info = {
            "title": title,
            "artist": artist,
            "album": album,
            "year": self.extract_year_from_title(title, album),
            "art_url": art_url,
            "art_pixmap": art_pixmap,
            "progress_ms": progress_ms,
            "duration_ms": duration_ms,
            "lyrics_lines": lyrics_lines,
        }
        if self.spotify_overlay.isVisible():
            self.spotify_overlay.show_state({
                **self.spotify_info,
                "progress": (progress_ms / duration_ms) if duration_ms > 0 else 0.0,
            })

    def update_spotify_metadata_from_state(self, state):
        if not isinstance(state, dict):
            return
        art_url = (state.get("art") or state.get("ogart") or "").strip()
        album = (state.get("album") or "").strip()
        artist = (state.get("artist") or "").strip()
        title = (state.get("title") or "").strip()
        art_pixmap = self.spotify_info.get("art_pixmap", QPixmap())
        if art_url and art_url != self.spotify_info.get("art_url"):
            art_pixmap = self.load_spotify_artwork(art_url)
        self.spotify_info.update({
            "title": title or self.spotify_info.get("title", ""),
            "artist": artist or self.spotify_info.get("artist", ""),
            "album": album or self.spotify_info.get("album", ""),
            "year": self.extract_year_from_title(title or self.spotify_info.get("title", ""), album or self.spotify_info.get("album", "")),
            "art_url": art_url or self.spotify_info.get("art_url", ""),
            "art_pixmap": art_pixmap,
        })
        self.enrich_spotify_metadata()

    def extract_year_from_title(self, title, album):
        combined = f"{title} {album}"
        match = re.search(r"(19|20)\d{2}", combined)
        return match.group(0) if match else ""

    def load_spotify_artwork(self, url):
        if not url:
            return QPixmap()
        try:
            with urllib.request.urlopen(url, timeout=3.0) as response:
                data = response.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
            return QPixmap()
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        return pixmap

    def enrich_spotify_metadata(self):
        title = (self.spotify_info.get("title") or "").strip()
        artist = (self.spotify_info.get("artist") or "").strip()
        if not title:
            return
        if self.spotify_info.get("album") and self.spotify_info.get("year") and not self.spotify_info.get("art_pixmap", QPixmap()).isNull():
            return
        cache = load_json_file(SPOTIFY_TRACK_CACHE_FILE, {})
        key = lyrics_cache_key(artist or "unknown", title)
        cached = cache.get(key)
        if not isinstance(cached, dict):
            cached = fetch_track_metadata_fallback(artist, title)
            cache[key] = cached
            save_json_file(SPOTIFY_TRACK_CACHE_FILE, cache)
        if not isinstance(cached, dict):
            return
        if cached.get("album") and not self.spotify_info.get("album"):
            self.spotify_info["album"] = cached["album"]
        if cached.get("artist") and not self.spotify_info.get("artist"):
            self.spotify_info["artist"] = cached["artist"]
        if cached.get("year") and not self.spotify_info.get("year"):
            self.spotify_info["year"] = cached["year"]
        if cached.get("art_url") and not self.spotify_info.get("art_url"):
            self.spotify_info["art_url"] = cached["art_url"]
        if cached.get("art_url") and self.spotify_info.get("art_pixmap", QPixmap()).isNull():
            self.spotify_info["art_pixmap"] = self.load_spotify_artwork(cached["art_url"])

    def lookup_spotify_lyrics(self, artist, title):
        cache = load_json_file(SPOTIFY_LYRICS_CACHE_FILE, {})
        key = lyrics_cache_key(artist, title)
        cached = cache.get(key)
        if isinstance(cached, list):
            return cached
        lines = fetch_remote_lyrics(artist, title)
        cache[key] = lines
        save_json_file(SPOTIFY_LYRICS_CACHE_FILE, cache)
        return lines

    def spotify_preview_pixmap(self):
        if self.spotify_overlay.isVisible():
            pixmap = self.spotify_overlay.grab()
            if not pixmap.isNull():
                self.spotify_preview_frame = pixmap
                return pixmap
        if not self.spotify_preview_frame.isNull():
            return self.spotify_preview_frame
        if not self.spotify_view.url().isValid():
            return QPixmap()
        return self.spotify_view.grab()

    def capture_spotify_frame(self):
        if self.spotify_overlay.isVisible():
            pixmap = self.spotify_overlay.grab()
        else:
            if not self.spotify_view.url().isValid():
                return
            pixmap = self.spotify_view.grab()
        if not pixmap.isNull():
            self.spotify_preview_frame = pixmap

    def keyPressEvent(self, event):
        overlay_visible = self.guide_overlay.isVisible() or self.on_demand_overlay.isVisible() or self.info_overlay.isVisible()
        if event.key() == Qt.Key_V:
            self.onDemandRequested.emit()
            event.accept()
            return

        if event.key() == Qt.Key_I:
            self.infoRequested.emit()
            event.accept()
            return

        if event.key() == Qt.Key_Space:
            self.playbackToggleRequested.emit()
            event.accept()
            return

        if event.key() in (Qt.Key_Comma, Qt.Key_Less):
            if not event.isAutoRepeat():
                self.onDemandSeekRequested.emit(-10)
                self.onDemandSeekPressChanged.emit(-10, True)
            event.accept()
            return

        if event.key() in (Qt.Key_Period, Qt.Key_Greater):
            if not event.isAutoRepeat():
                self.onDemandSeekRequested.emit(10)
                self.onDemandSeekPressChanged.emit(10, True)
            event.accept()
            return

        if self.on_demand_overlay.isVisible():
            if event.key() == Qt.Key_Left:
                self.onDemandLeftRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Right:
                self.onDemandRightRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Up:
                self.onDemandUpRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Down:
                self.onDemandDownRequested.emit()
                event.accept()
                return
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.onDemandSelectRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Escape:
                self.onDemandCloseRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_M:
                self.onDemandSettingsRequested.emit()
                event.accept()
                return

        if self.info_overlay.isVisible():
            if event.key() == Qt.Key_Left:
                self.infoLeftRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Right:
                self.infoRightRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Up:
                self.infoUpRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Down:
                self.infoDownRequested.emit()
                event.accept()
                return
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.infoSelectRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Escape:
                self.infoCloseRequested.emit()
                event.accept()
                return

        if event.key() == Qt.Key_G:
            self.guideRequested.emit()
            event.accept()
            return

        if self.guide_overlay.isVisible():
            if event.key() == Qt.Key_Left:
                self.guideLeftRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Right:
                self.guideRightRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Up:
                self.guideUpRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Down:
                self.guideDownRequested.emit()
                event.accept()
                return
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.guideSelectRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Escape:
                self.guideCloseRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_M:
                self.guideSettingsRequested.emit()
                event.accept()
                return

        if event.key() in (Qt.Key_Equal, Qt.Key_Plus):
            self.channelUpRequested.emit()
            event.accept()
            return

        if event.key() == Qt.Key_Minus:
            self.channelDownRequested.emit()
            event.accept()
            return

        if event.key() in (Qt.Key_BracketRight, Qt.Key_BraceRight):
            if overlay_visible:
                self.uiScaleRequested.emit(1)
                event.accept()
                return

        if event.key() in (Qt.Key_BracketLeft, Qt.Key_BraceLeft):
            if overlay_visible:
                self.uiScaleRequested.emit(-1)
            event.accept()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in (Qt.Key_Comma, Qt.Key_Less):
            if not event.isAutoRepeat():
                self.onDemandSeekPressChanged.emit(-10, False)
            event.accept()
            return
        if event.key() in (Qt.Key_Period, Qt.Key_Greater):
            if not event.isAutoRepeat():
                self.onDemandSeekPressChanged.emit(10, False)
            event.accept()
            return
        super().keyReleaseEvent(event)


class NextUpOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.theme_name = DEFAULT_THEME_NAME
        self.skin_name = DEFAULT_SKIN_NAME
        self.ui_scale = GUIDE_UI_SCALE_DEFAULT
        self.state = {}
        self.hide()

    def configure(self, theme_name, skin_name, ui_scale=GUIDE_UI_SCALE_DEFAULT):
        self.skin_name = normalize_skin_name(skin_name)
        self.theme_name = normalize_theme_for_skin(self.skin_name, theme_name)
        self.ui_scale = clamp_guide_ui_scale(ui_scale)

    def skin_style(self):
        return GUIDE_SKINS.get(normalize_skin_name(self.skin_name), GUIDE_SKINS[DEFAULT_SKIN_NAME]).get("style", "aero")

    def show_next(self, state):
        self.state = state or {}
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.update()

    def update_next(self, state):
        self.state = state or {}
        if self.isVisible():
            self.update()

    def paintEvent(self, event):
        if not self.state:
            return
        painter = QPainter(self)
        theme = app_theme(self.theme_name, self.skin_name)
        target_rect = overlay_target_rect(self)

        safe_w = max(220, target_rect.width() - 28)
        panel_w = min(286, safe_w)
        panel_h = 158
        panel_x = max(target_rect.left() + 10, target_rect.right() - panel_w - 14)
        panel_y = max(target_rect.top() + 10, target_rect.bottom() - panel_h - 16)
        panel = QRect(panel_x, panel_y, panel_w, panel_h)
        if self.skin_style() == "cable":
            painter.setPen(QPen(theme["normal_border"], 1))
            painter.setBrush(QColor(theme["app_background"].red(), theme["app_background"].green(), theme["app_background"].blue(), 248))
            painter.drawRect(panel)
            inner = panel.adjusted(3, 3, -3, -3)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme["panel_background"].red(), theme["panel_background"].green(), theme["panel_background"].blue(), 255))
            painter.drawRect(inner)
        else:
            outer = QLinearGradient(panel.topLeft(), panel.bottomLeft())
            outer.setColorAt(0.0, QColor(theme["chrome_top"].red(), theme["chrome_top"].green(), theme["chrome_top"].blue(), 236))
            outer.setColorAt(1.0, QColor(theme["chrome_bottom"].red(), theme["chrome_bottom"].green(), theme["chrome_bottom"].blue(), 240))
            painter.setPen(QPen(theme["normal_border"], 1))
            painter.setBrush(outer)
            painter.drawRoundedRect(panel, 16, 16)

            inner = panel.adjusted(4, 4, -4, -4)
            inner_grad = QLinearGradient(inner.topLeft(), inner.bottomLeft())
            inner_grad.setColorAt(0.0, QColor(theme["dialog_panel"].red(), theme["dialog_panel"].green(), theme["dialog_panel"].blue(), 236))
            inner_grad.setColorAt(1.0, QColor(theme["panel_background"].red(), theme["panel_background"].green(), theme["panel_background"].blue(), 232))
            painter.setPen(Qt.NoPen)
            painter.setBrush(inner_grad)
            painter.drawRoundedRect(inner, 13, 13)

        thumb_rect = QRect(inner.left() + 12, inner.top() + 14, 98, 74)
        painter.setPen(QPen(theme["normal_border"], 1))
        painter.setBrush(QColor(theme["vault_card_background"].red(), theme["vault_card_background"].green(), theme["vault_card_background"].blue(), 220))
        if self.skin_style() == "cable":
            painter.drawRect(thumb_rect)
        else:
            painter.drawRoundedRect(thumb_rect, 10, 10)
        pixmap = self.state.get("thumbnail", QPixmap())
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            scaled = pixmap.scaled(thumb_rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            src_x = max(0, (scaled.width() - thumb_rect.width()) // 2)
            src_y = max(0, (scaled.height() - thumb_rect.height()) // 2)
            painter.drawPixmap(thumb_rect, scaled, QRect(src_x, src_y, thumb_rect.width(), thumb_rect.height()))

        title_font = QFont(guide_font_family("primary") if self.skin_style() == "cable" else "Trebuchet MS", 16, QFont.Bold)
        small_font = QFont(guide_font_family("primary") if self.skin_style() == "cable" else "Trebuchet MS", 10, QFont.Bold)
        body_font = QFont(guide_font_family("secondary") if self.skin_style() == "cable" else "Trebuchet MS", 10, QFont.DemiBold if self.skin_style() == "cable" else QFont.Normal)

        painter.setPen(theme["warning_text"] if self.skin_style() == "cable" else theme["dialog_text"])
        painter.setFont(small_font)
        text_left = thumb_rect.right() + 12
        text_width = inner.right() - text_left - 14
        painter.drawText(QRect(text_left, inner.top() + 10, text_width, 20), Qt.AlignLeft | Qt.AlignVCenter, "COMING UP NEXT!")
        painter.setFont(title_font)
        painter.setPen(theme["primary_text"] if self.skin_style() == "cable" else theme["dialog_text"])
        painter.drawText(QRect(text_left, inner.top() + 28, text_width, 64), Qt.TextWordWrap, self.state.get("title", ""))
        painter.setFont(body_font)
        painter.drawText(QRect(text_left, inner.top() + 94, text_width, 18), Qt.AlignLeft | Qt.AlignVCenter, self.state.get("meta", ""))

        countdown = int(self.state.get("countdown", 0))
        badge = QRect(inner.left() + 12, inner.bottom() - 42, 100, 24)
        painter.setPen(QPen(theme["selected_border"], 1))
        painter.setBrush(theme["selected_background"] if self.skin_style() == "cable" else QLinearGradient(badge.topLeft(), badge.bottomLeft()))
        if self.skin_style() != "cable":
            badge_grad = QLinearGradient(badge.topLeft(), badge.bottomLeft())
            badge_grad.setColorAt(0.0, QColor(theme["selected_background"].red(), theme["selected_background"].green(), theme["selected_background"].blue(), 240))
            badge_grad.setColorAt(1.0, QColor(theme["button_selected_background"].red(), theme["button_selected_background"].green(), theme["button_selected_background"].blue(), 236))
            painter.setBrush(badge_grad)
            painter.drawRoundedRect(badge, 8, 8)
        else:
            painter.drawRect(badge)
        painter.setFont(small_font)
        painter.setPen(theme["selected_text"])
        painter.drawText(badge, Qt.AlignCenter, f"Playing in {countdown}")


class TransportOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.theme_name = DEFAULT_THEME_NAME
        self.skin_name = DEFAULT_SKIN_NAME
        self.ui_scale = GUIDE_UI_SCALE_DEFAULT
        self.state = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def configure(self, theme_name, skin_name, ui_scale=GUIDE_UI_SCALE_DEFAULT):
        self.skin_name = normalize_skin_name(skin_name)
        self.theme_name = normalize_theme_for_skin(self.skin_name, theme_name)
        self.ui_scale = clamp_guide_ui_scale(ui_scale)

    def skin_style(self):
        return GUIDE_SKINS.get(normalize_skin_name(self.skin_name), GUIDE_SKINS[DEFAULT_SKIN_NAME]).get("style", "aero")

    def show_transport(self, state):
        self.state = state or {}
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.update()
        self.timer.start(1500)

    def paintEvent(self, event):
        if not self.state:
            return
        painter = QPainter(self)
        theme = app_theme(self.theme_name, self.skin_name)
        target_rect = overlay_target_rect(self)

        if self.skin_style() == "cable":
            panel_w = min(520, max(340, int(target_rect.width() * 0.42)))
            panel_h = 72
        else:
            panel_w = min(760, max(420, target_rect.width() - 160))
            panel_h = 82
        panel_x = target_rect.left() + max(18, (target_rect.width() - panel_w) // 2)
        panel_y = target_rect.bottom() - panel_h - 18
        panel = QRect(panel_x, panel_y, panel_w, panel_h)
        if self.skin_style() == "cable":
            painter.setPen(Qt.NoPen)
            painter.setBrush(Qt.NoBrush)
        else:
            grad = QLinearGradient(panel.topLeft(), panel.bottomLeft())
            grad.setColorAt(0.0, QColor(theme["panel_background"].red(), theme["panel_background"].green(), theme["panel_background"].blue(), 228))
            grad.setColorAt(1.0, QColor(theme["app_background"].red(), theme["app_background"].green(), theme["app_background"].blue(), 232))
            painter.setPen(QPen(theme["subtle_border"], 1))
            painter.setBrush(grad)
            painter.drawRoundedRect(panel, 14, 14)

        if self.skin_style() != "cable":
            icon_rect = QRect(panel.left() + 16, panel.top() + 10, panel.width() - 32, 20)
            painter.setFont(QFont(guide_font_family("primary") if self.skin_style() == "cable" else "Trebuchet MS", 11, QFont.Bold))
            painter.setPen(theme["warning_text"] if self.skin_style() == "cable" else theme["primary_text"])
            painter.drawText(icon_rect, Qt.AlignLeft | Qt.AlignVCenter, self.state.get("label", ""))

            title_rect = QRect(panel.left() + 16, panel.top() + 30, panel.width() - 32, 18)
            painter.setFont(QFont(guide_font_family("secondary") if self.skin_style() == "cable" else "Trebuchet MS", 10, QFont.DemiBold if self.skin_style() == "cable" else QFont.Normal))
            painter.setPen(theme["primary_text"] if self.skin_style() == "cable" else theme["secondary_text"])
            text = painter.fontMetrics().elidedText(self.state.get("title", ""), Qt.ElideRight, title_rect.width())
            painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, text)

        elapsed_text = self.state.get("elapsed_text", "")
        total_text = self.state.get("total_text", "")
        time_font = QFont(vhs_osd_font_family() if self.skin_style() == "cable" else "Trebuchet MS", 18 if self.skin_style() == "cable" else 10, QFont.Bold)
        painter.setFont(time_font)
        bar_y = panel.center().y() + (4 if self.skin_style() == "cable" else 17)
        if self.skin_style() == "cable":
            elapsed_rect = QRect(panel.left() + 10, bar_y - 15, 92, 28)
            total_rect = QRect(panel.right() - 102, bar_y - 15, 92, 28)
            track = QRect(elapsed_rect.right() + 12, bar_y - 7, total_rect.left() - elapsed_rect.right() - 24, 14)

            def draw_osd_time(rect, text, align):
                painter.setPen(QColor(0, 0, 0, 220))
                painter.drawText(rect.translated(1, 1), align, text)
                painter.setPen(QColor(244, 244, 238))
                painter.drawText(rect, align, text)

            draw_osd_time(elapsed_rect, elapsed_text, Qt.AlignLeft | Qt.AlignVCenter)
            draw_osd_time(total_rect, total_text, Qt.AlignRight | Qt.AlignVCenter)
        else:
            painter.setPen(theme["primary_text"])
            elapsed_rect = QRect(panel.left() + 8, bar_y - 12, 84, 18)
            total_rect = QRect(panel.right() - 92, bar_y - 12, 84, 18)
            painter.drawText(elapsed_rect, Qt.AlignLeft | Qt.AlignVCenter, elapsed_text)
            painter.drawText(total_rect, Qt.AlignRight | Qt.AlignVCenter, total_text)
            track = QRect(elapsed_rect.right() + 10, bar_y - 6, total_rect.left() - elapsed_rect.right() - 20, 8)

        if self.skin_style() == "cable":
            painter.setPen(QPen(QColor(244, 244, 238), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(track)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme["subtle_border"])
            painter.drawRoundedRect(track, 4, 4)
        progress = max(0.0, min(1.0, self.state.get("progress", 0.0)))
        fill = QRect(
            track.left() + (1 if self.skin_style() == "cable" else 0),
            track.top() + (1 if self.skin_style() == "cable" else 0),
            max(6, int((track.width() - (2 if self.skin_style() == "cable" else 0)) * progress)),
            max(1, track.height() - (2 if self.skin_style() == "cable" else 0)),
        )
        if self.skin_style() == "cable":
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(244, 244, 238))
            painter.drawRect(fill)
        else:
            fill_grad = QLinearGradient(fill.topLeft(), fill.topRight())
            fill_grad.setColorAt(0.0, QColor(theme["selected_background"].red(), theme["selected_background"].green(), theme["selected_background"].blue(), 236))
            fill_grad.setColorAt(1.0, QColor(theme["button_selected_background"].red(), theme["button_selected_background"].green(), theme["button_selected_background"].blue(), 236))
            painter.setBrush(fill_grad)
            painter.drawRoundedRect(fill, 4, 4)


class CommercialOverridesDialog(QDialog):
    def __init__(self, channel_names, overrides, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Channel Commercial Overrides")
        self.setModal(True)
        self.resize(900, 560)
        self.channel_names = list(channel_names or [])
        self.result_overrides = json.loads(json.dumps(overrides or {}))

        theme_name = parent.theme_combo.currentText() if parent is not None and hasattr(parent, "theme_combo") else DEFAULT_THEME_NAME
        skin_name = parent.skin_combo.currentText() if parent is not None and hasattr(parent, "skin_combo") else DEFAULT_SKIN_NAME
        self.setStyleSheet(build_themed_dialog_stylesheet(theme_name, skin_name))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        title = QLabel("Channel Commercial Overrides")
        title.setObjectName("dialogTitle")
        outer.addWidget(title)
        note = QLabel("Fine-tune how each channel behaves. Leave a channel on Inherit to use the global commercial settings.")
        note.setObjectName("dialogNote")
        note.setWordWrap(True)
        outer.addWidget(note)

        body = QHBoxLayout()
        body.setSpacing(14)
        outer.addLayout(body, 1)

        self.channel_list = QListWidget()
        self.channel_list.addItems(self.channel_names)
        self.channel_list.setMinimumWidth(240)
        body.addWidget(self.channel_list, 0)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_scroll = FocusScrollArea()
        right_scroll.setWidget(right)
        body.addWidget(right_scroll, 1)

        self.channel_title = QLabel("Select a channel")
        self.channel_title.setObjectName("dialogTitle")
        right_layout.addWidget(self.channel_title)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        right_layout.addLayout(form)

        self.enabled_mode_combo = QComboBox()
        self.enabled_mode_combo.addItems(["Inherit", "Commercials On", "No Commercials"])
        form.addRow("Commercials", self.enabled_mode_combo)

        self.preferred_era_combo = QComboBox()
        self.preferred_era_combo.setEditable(True)
        self.preferred_era_combo.addItems(["", "70s", "80s", "90s", "2000s", "2010s"])
        form.addRow("Preferred Era", self.preferred_era_combo)

        self.preferred_category_combo = QComboBox()
        self.preferred_category_combo.setEditable(True)
        self.preferred_category_combo.addItems(["", "Kids", "Toys", "Food", "Fast Food", "Games", "Tech", "Music", "Sports", "Movie Theater", "Network Promos", "General"])
        form.addRow("Preferred Category", self.preferred_category_combo)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["between_episodes_only", "natural_breaks", "timed_breaks", "hybrid"])
        form.addRow("Break Mode", self.mode_combo)

        self.density_combo = QComboBox()
        self.density_combo.addItems(["none", "light", "medium", "heavy", "custom"])
        form.addRow("Density", self.density_combo)

        self.min_ads_spin = QSpinBox()
        self.min_ads_spin.setRange(0, 12)
        form.addRow("Min Ads / Break", self.min_ads_spin)

        self.max_ads_spin = QSpinBox()
        self.max_ads_spin.setRange(0, 12)
        form.addRow("Max Ads / Break", self.max_ads_spin)

        self.min_seconds_between_breaks_spin = QSpinBox()
        self.min_seconds_between_breaks_spin.setRange(30, 7200)
        self.min_seconds_between_breaks_spin.setSingleStep(30)
        form.addRow("Min Seconds Between Breaks", self.min_seconds_between_breaks_spin)

        self.target_interval_spin = QSpinBox()
        self.target_interval_spin.setRange(1, 60)
        form.addRow("Target Interval (min)", self.target_interval_spin)

        self.first_break_spin = QSpinBox()
        self.first_break_spin.setRange(0, 1800)
        self.first_break_spin.setSingleStep(15)
        form.addRow("Min Before First Break (sec)", self.first_break_spin)

        self.max_ad_half_hour_spin = QSpinBox()
        self.max_ad_half_hour_spin.setRange(30, 1800)
        self.max_ad_half_hour_spin.setSingleStep(15)
        form.addRow("Max Ad Seconds / 30 Min", self.max_ad_half_hour_spin)

        self.allow_fallback = QCheckBox("Allow fallback if preferred commercials are missing")
        self.allow_bumpers = QCheckBox("Allow bumpers")
        self.allow_promos = QCheckBox("Allow promos")
        self.prefer_promos = QCheckBox("Prefer promos over regular ads")
        self.allow_station_ids = QCheckBox("Allow station IDs")
        for checkbox in (
            self.allow_fallback,
            self.allow_bumpers,
            self.allow_promos,
            self.prefer_promos,
            self.allow_station_ids,
        ):
            right_layout.addWidget(checkbox)

        right_layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("saveButton")
        save_btn.clicked.connect(self.accept)
        buttons.addWidget(save_btn)
        outer.addLayout(buttons)

        self.channel_list.currentTextChanged.connect(self.load_channel_override)
        self.channel_list.currentRowChanged.connect(self.on_channel_changed)
        if self.channel_names:
            self.channel_list.setCurrentRow(0)

    def on_channel_changed(self, row):
        if row < 0 or row >= len(self.channel_names):
            return
        self.load_channel_override(self.channel_names[row])

    def save_current_override(self):
        channel_name = self.channel_list.currentItem().text().strip() if self.channel_list.currentItem() else ""
        if not channel_name:
            return
        enabled_mode_map = {
            "Inherit": "inherit",
            "Commercials On": "on",
            "No Commercials": "off",
        }
        override = {
            "enabled_mode": enabled_mode_map.get(self.enabled_mode_combo.currentText(), "inherit"),
            "preferred_era": self.preferred_era_combo.currentText().strip(),
            "preferred_category": self.preferred_category_combo.currentText().strip(),
            "mode": self.mode_combo.currentText(),
            "density": self.density_combo.currentText(),
            "min_ads_per_break": self.min_ads_spin.value(),
            "max_ads_per_break": self.max_ads_spin.value(),
            "min_seconds_between_breaks": self.min_seconds_between_breaks_spin.value(),
            "target_break_interval_minutes": self.target_interval_spin.value(),
            "minimum_content_before_first_break_seconds": self.first_break_spin.value(),
            "max_ad_seconds_per_half_hour": self.max_ad_half_hour_spin.value(),
            "allow_fallback": self.allow_fallback.isChecked(),
            "allow_bumpers": self.allow_bumpers.isChecked(),
            "allow_promos": self.allow_promos.isChecked(),
            "prefer_promos": self.prefer_promos.isChecked(),
            "allow_station_ids": self.allow_station_ids.isChecked(),
        }
        self.result_overrides[channel_name] = override

    def load_channel_override(self, channel_name):
        if not channel_name:
            return
        self.channel_title.setText(channel_name)
        override = dict((self.result_overrides or {}).get(channel_name, {}))
        enabled_mode = str(override.get("enabled_mode", "inherit") or "inherit")
        enabled_text = {
            "inherit": "Inherit",
            "on": "Commercials On",
            "off": "No Commercials",
        }.get(enabled_mode, "Inherit")
        self.enabled_mode_combo.setCurrentText(enabled_text)
        self.preferred_era_combo.setCurrentText(str(override.get("preferred_era", "") or ""))
        self.preferred_category_combo.setCurrentText(str(override.get("preferred_category", "") or ""))
        self.mode_combo.setCurrentText(str(override.get("mode", "between_episodes_only") or "between_episodes_only"))
        self.density_combo.setCurrentText(str(override.get("density", "light") or "light"))
        self.min_ads_spin.setValue(int(override.get("min_ads_per_break", 1) or 1))
        self.max_ads_spin.setValue(int(override.get("max_ads_per_break", 3) or 3))
        self.min_seconds_between_breaks_spin.setValue(int(override.get("min_seconds_between_breaks", 330) or 330))
        self.target_interval_spin.setValue(int(override.get("target_break_interval_minutes", 7) or 7))
        self.first_break_spin.setValue(int(override.get("minimum_content_before_first_break_seconds", 90) or 90))
        self.max_ad_half_hour_spin.setValue(int(override.get("max_ad_seconds_per_half_hour", 240) or 240))
        self.allow_fallback.setChecked(bool(override.get("allow_fallback", True)))
        self.allow_bumpers.setChecked(bool(override.get("allow_bumpers", True)))
        self.allow_promos.setChecked(bool(override.get("allow_promos", True)))
        self.prefer_promos.setChecked(bool(override.get("prefer_promos", False)))
        self.allow_station_ids.setChecked(bool(override.get("allow_station_ids", True)))

    def accept(self):
        self.save_current_override()
        super().accept()


class FocusScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)

    def setWidget(self, widget):
        previous = self.widget()
        if previous:
            previous.removeEventFilter(self)
        super().setWidget(widget)
        if widget:
            self._install_focus_tracking(widget)

    def _install_focus_tracking(self, root):
        root.installEventFilter(self)
        for child in root.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.FocusIn and isinstance(watched, QWidget):
            self.ensureWidgetVisible(watched, 24, 40)
        return super().eventFilter(watched, event)


class AdvancedCommercialSettingsDialog(QDialog):
    def __init__(self, settings, channel_names=None, channel_overrides=None, allow_empty_catalog_tv=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Commercial Settings")
        self.setModal(True)
        self.resize(760, 720)
        self.channel_names = list(channel_names or [])
        self.result_overrides = json.loads(json.dumps(channel_overrides or {}))
        self.settings = normalize_commercials_config(settings or {})
        theme_name = parent.theme_combo.currentText() if parent is not None and hasattr(parent, "theme_combo") else DEFAULT_THEME_NAME
        skin_name = parent.skin_combo.currentText() if parent is not None and hasattr(parent, "skin_combo") else DEFAULT_SKIN_NAME
        self.setStyleSheet(build_themed_dialog_stylesheet(theme_name, skin_name))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        title = QLabel("Advanced Commercial Settings")
        title.setObjectName("dialogTitle")
        outer.addWidget(title)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(14)

        self.allow_empty_catalog_tv = QCheckBox("Allow Watch TV without local content loaded")
        self.allow_empty_catalog_tv.setChecked(bool(allow_empty_catalog_tv))
        test_card, test_layout = self.build_section_card(
            "Cable Test Mode",
            "Lets MediaWave open the TV interface using only enabled companion channels like WeatherStar, RadioWaveTV, and NetTV.",
        )
        test_layout.addWidget(self.allow_empty_catalog_tv)
        layout.addWidget(test_card)

        self.enabled = QCheckBox("Enable channel commercials")
        self.enabled.setChecked(bool(self.settings.get("enabled", False)))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["between_episodes_only", "natural_breaks", "timed_breaks", "hybrid"])
        self.mode_combo.setCurrentText(self.settings.get("mode", "between_episodes_only"))
        self.density_combo = QComboBox()
        self.density_combo.addItems(["none", "light", "medium", "heavy", "custom"])
        self.density_combo.setCurrentText(self.settings.get("density", "light"))
        self.era_combo = QComboBox()
        self.era_combo.setEditable(True)
        self.era_combo.addItems(["", "70s", "80s", "90s", "2000s", "2010s"])
        self.era_combo.setCurrentText(self.settings.get("preferred_era", ""))
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(["", "Kids", "Toys", "Food", "Fast Food", "Games", "Tech", "Music", "Sports", "Movie Theater", "Network Promos", "General"])
        self.category_combo.setCurrentText(display_commercial_category(self.settings.get("preferred_category", "")))
        self.allow_fallback = QCheckBox("Allow fallback through era/type/general/all commercials")
        self.allow_fallback.setChecked(bool(self.settings.get("allow_fallback", True)))

        global_card, global_layout = self.build_section_card("Global Commercial Rules")
        global_form = QFormLayout()
        global_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        global_form.setHorizontalSpacing(16)
        global_form.setVerticalSpacing(10)
        global_form.addRow("Commercials Enabled", self.enabled)
        global_form.addRow("Global Mode", self.mode_combo)
        global_form.addRow("Global Density", self.density_combo)
        global_form.addRow("Default Era", self.era_combo)
        global_form.addRow("Default Category", self.category_combo)
        global_layout.addLayout(global_form)
        global_layout.addWidget(self.allow_fallback)
        layout.addWidget(global_card)

        self.min_ads = QSpinBox()
        self.min_ads.setRange(0, 12)
        self.min_ads.setValue(int(self.settings.get("min_ads_per_break", 1) or 1))
        self.max_ads = QSpinBox()
        self.max_ads.setRange(0, 12)
        self.max_ads.setValue(int(self.settings.get("max_ads_per_break", 3) or 3))
        self.interval = QSpinBox()
        self.interval.setRange(1, 60)
        self.interval.setValue(int(self.settings.get("target_break_interval_minutes", 7) or 7))
        self.min_between = QSpinBox()
        self.min_between.setRange(30, 7200)
        self.min_between.setSingleStep(30)
        self.min_between.setValue(int(self.settings.get("min_seconds_between_breaks", 330) or 330))
        self.first_break = QSpinBox()
        self.first_break.setRange(0, 1800)
        self.first_break.setSingleStep(15)
        self.first_break.setValue(int(self.settings.get("minimum_content_before_first_break_seconds", 90) or 90))
        self.jitter = QSpinBox()
        self.jitter.setRange(0, 600)
        self.jitter.setSingleStep(15)
        self.jitter.setValue(int(self.settings.get("break_jitter_seconds", 45) or 45))
        self.max_half_hour = QSpinBox()
        self.max_half_hour.setRange(30, 1800)
        self.max_half_hour.setSingleStep(15)
        self.max_half_hour.setValue(int(self.settings.get("max_ad_seconds_per_half_hour", 240) or 240))

        timing_card, timing_layout = self.build_section_card("Break Timing")
        timing_form = QFormLayout()
        timing_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        timing_form.setHorizontalSpacing(16)
        timing_form.setVerticalSpacing(10)
        timing_form.addRow("Min Ads / Break", self.min_ads)
        timing_form.addRow("Max Ads / Break", self.max_ads)
        timing_form.addRow("Break Interval (min)", self.interval)
        timing_form.addRow("Min Seconds Between Breaks", self.min_between)
        timing_form.addRow("Min Before First Break", self.first_break)
        timing_form.addRow("Break Jitter (sec)", self.jitter)
        timing_form.addRow("Max Ad Seconds / 30 Min", self.max_half_hour)
        timing_layout.addLayout(timing_form)
        layout.addWidget(timing_card)

        self.smart_breaks = QCheckBox("Use Smart Breaks when natural cut points can be found")
        self.smart_breaks.setChecked(bool(self.settings.get("smart_breaks", True)))
        self.skip_midroll = QCheckBox("Skip mid-roll breaks if Smart Breaks cannot find a good break point")
        self.skip_midroll.setChecked(bool(self.settings.get("skip_midroll_if_no_smart_breaks", False)))
        smart_card, smart_layout = self.build_section_card("Smart Breaks")
        smart_layout.addWidget(self.smart_breaks)
        smart_layout.addWidget(self.skip_midroll)
        layout.addWidget(smart_card)

        self.pre_roll = QCheckBox("Allow commercials before a program starts")
        self.pre_roll.setChecked(bool(self.settings.get("pre_roll_enabled", False)))
        self.post_roll = QCheckBox("Allow commercials after a program ends")
        self.post_roll.setChecked(bool(self.settings.get("post_roll_enabled", False)))
        self.allow_bumpers = QCheckBox("Allow bumpers in breaks")
        self.allow_bumpers.setChecked(bool(self.settings.get("allow_bumpers", True)))
        self.allow_promos = QCheckBox("Allow promos in breaks")
        self.allow_promos.setChecked(bool(self.settings.get("allow_promos", True)))
        self.prefer_promos = QCheckBox("Prefer promos over regular commercials when available")
        self.prefer_promos.setChecked(bool(self.settings.get("prefer_promos", False)))
        self.allow_station_ids = QCheckBox("Allow station IDs")
        self.allow_station_ids.setChecked(bool(self.settings.get("allow_station_ids", True)))
        extras_card, extras_layout = self.build_section_card("Bumpers / Promos / Station IDs")
        for checkbox in (self.pre_roll, self.post_roll, self.allow_bumpers, self.allow_promos, self.prefer_promos, self.allow_station_ids):
            extras_layout.addWidget(checkbox)
        layout.addWidget(extras_card)

        channel_card, channel_layout = self.build_section_card("Per-Channel Overrides")
        channel_button = QPushButton("Edit Channel Commercial Overrides")
        channel_button.clicked.connect(self.open_channel_overrides_dialog)
        channel_layout.addWidget(channel_button)
        layout.addWidget(channel_card)
        layout.addStretch(1)

        scroll = FocusScrollArea()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("saveButton")
        save_btn.clicked.connect(self.accept)
        buttons.addWidget(save_btn)
        outer.addLayout(buttons)

    def build_section_card(self, title_text, note_text=None):
        card = QWidget()
        card.setObjectName("sectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        title = QLabel(title_text)
        title.setObjectName("sectionHeader")
        layout.addWidget(title)
        if note_text:
            note = QLabel(note_text)
            note.setObjectName("sectionNote")
            note.setWordWrap(True)
            layout.addWidget(note)
        return card, layout

    def open_channel_overrides_dialog(self):
        dialog = CommercialOverridesDialog(self.channel_names, self.result_overrides, self)
        if dialog.exec() == QDialog.Accepted:
            self.result_overrides = dialog.result_overrides

    def values(self):
        settings = dict(self.settings)
        settings.update(
            {
                "enabled": self.enabled.isChecked(),
                "smart_breaks": self.smart_breaks.isChecked(),
                "mode": self.mode_combo.currentText(),
                "density": self.density_combo.currentText(),
                "allow_fallback": self.allow_fallback.isChecked(),
                "pre_roll_enabled": self.pre_roll.isChecked(),
                "post_roll_enabled": self.post_roll.isChecked(),
                "allow_bumpers": self.allow_bumpers.isChecked(),
                "allow_promos": self.allow_promos.isChecked(),
                "prefer_promos": self.prefer_promos.isChecked(),
                "allow_station_ids": self.allow_station_ids.isChecked(),
                "skip_midroll_if_no_smart_breaks": self.skip_midroll.isChecked(),
                "preferred_era": self.era_combo.currentText().strip(),
                "preferred_category": self.category_combo.currentText().strip(),
                "min_ads_per_break": self.min_ads.value(),
                "max_ads_per_break": self.max_ads.value(),
                "min_seconds_between_breaks": self.min_between.value(),
                "target_break_interval_minutes": self.interval.value(),
                "minimum_content_before_first_break_seconds": self.first_break.value(),
                "break_jitter_seconds": self.jitter.value(),
                "max_ad_seconds_per_half_hour": self.max_half_hour.value(),
                "channel_overrides": self.result_overrides,
            }
        )
        return {
            "commercials": normalize_commercials_config(settings),
            "allow_empty_catalog_tv": self.allow_empty_catalog_tv.isChecked(),
        }


class AdvancedConfigDialog(QDialog):
    def __init__(self, settings, channel_names=None, parent=None):
        super().__init__(parent)
        self.review_requested = False
        self.channel_names = list(channel_names or [])
        self.commercials_settings = normalize_commercials_config((settings or {}).get("commercials", {}))
        self.advanced_commercials_settings = json.loads(json.dumps(self.commercials_settings))
        self.channel_commercial_overrides = json.loads(json.dumps(self.commercials_settings.get("channel_overrides", {})))
        self.setWindowTitle("Advanced Configuration")
        self.setModal(True)
        self.resize(840, 760)
        theme_name = parent.theme_combo.currentText() if parent is not None and hasattr(parent, "theme_combo") else DEFAULT_THEME_NAME
        skin_name = parent.skin_combo.currentText() if parent is not None and hasattr(parent, "skin_combo") else DEFAULT_SKIN_NAME
        self.setStyleSheet(build_themed_dialog_stylesheet(theme_name, skin_name))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        card = QWidget()
        card.setObjectName("dialogCard")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Advanced Configuration")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        note = QLabel("Manage companion channels and your commercial system. MediaWave Vault uses local names and assets, while commercial rules let each channel behave more like a real network.")
        note.setObjectName("dialogNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.weatherstar_location_input = QLineEdit()
        self.weatherstar_location_input.setPlaceholderText("City, state or ZIP code")
        self.weatherstar_location_input.setText(settings.get("weatherstar_location", ""))

        self.weatherstar_channel_input = QSpinBox()
        self.weatherstar_channel_input.setMinimum(1)
        self.weatherstar_channel_input.setMaximum(999)
        self.weatherstar_channel_input.setValue(int(settings.get("weatherstar_channel_number", 1) or 1))

        self.radiowave_input = QLineEdit()
        self.radiowave_input.setPlaceholderText("Choose a folder of MP3/FLAC/AAC files")
        self.radiowave_input.setText(settings.get("radiowave_folder", ""))
        self.radiowave_input.setReadOnly(True)
        radio_picker = QWidget()
        radio_picker_layout = QHBoxLayout(radio_picker)
        radio_picker_layout.setContentsMargins(0, 0, 0, 0)
        radio_picker_layout.setSpacing(8)
        radio_picker_layout.addWidget(self.radiowave_input, 1)
        self.radiowave_browse_btn = QPushButton("Browse")
        self.radiowave_browse_btn.clicked.connect(self.choose_radiowave_folder)
        radio_picker_layout.addWidget(self.radiowave_browse_btn)

        self.radiowave_channel_input = QSpinBox()
        self.radiowave_channel_input.setMinimum(1)
        self.radiowave_channel_input.setMaximum(999)
        self.radiowave_channel_input.setValue(int(settings.get("radiowave_channel_number", 1) or 1))

        self.youtube_playlist_input = QLineEdit()
        self.youtube_playlist_input.setPlaceholderText("Paste a YouTube playlist URL")
        self.youtube_playlist_input.setText(settings.get("youtube_playlist_url", ""))
        self.youtube_playlist_help = QLabel(
            "Make sure your playlist is public. Use a playlist URL like "
            "https://www.youtube.com/playlist?list=PL... Avoid watch-page links like "
            "youtube.com/watch?v=...&list=..., YouTube Mix/Radio playlists, Watch Later, Liked, History, "
            "private playlists, or playlists that only work while logged in."
        )
        self.youtube_playlist_help.setObjectName("fieldHelp")
        self.youtube_playlist_help.setWordWrap(True)

        self.youtube_channel_input = QSpinBox()
        self.youtube_channel_input.setMinimum(1)
        self.youtube_channel_input.setMaximum(999)
        self.youtube_channel_input.setValue(int(settings.get("youtube_channel_number", 1) or 1))

        self.weatherstar_enabled = QCheckBox("Enable WeatherStar Channel")
        self.weatherstar_enabled.setChecked(bool(settings.get("weatherstar_enabled", False)))

        self.radiowave_enabled = QCheckBox("Enable RadioWaveTV music channel")
        self.radiowave_enabled.setChecked(bool(settings.get("radiowave_enabled", False)))

        self.youtube_enabled = QCheckBox("Enable NetTV playlist channel")
        self.youtube_enabled.setChecked(bool(settings.get("youtube_enabled", False)))

        self.allow_empty_catalog_tv = QCheckBox("Allow Watch TV without local content loaded")
        self.allow_empty_catalog_tv.setChecked(bool(settings.get("allow_empty_catalog_tv", False)))
        self.allow_dummy_vault_catalog = QCheckBox("Allow dummy Vault listings without a catalog")
        self.allow_dummy_vault_catalog.setChecked(bool(settings.get("allow_dummy_vault_catalog", False)))
        self.dev_menu_enabled = QCheckBox("Enable in-app dev menu")
        self.dev_menu_enabled.setChecked(bool(settings.get("dev_menu_enabled", True)))

        self.commercials_enabled = QCheckBox("Enable channel commercials")
        self.commercials_enabled.setChecked(bool(self.commercials_settings.get("enabled", False)))

        self.commercials_root_input = QLineEdit()
        self.commercials_root_input.setReadOnly(True)
        self.commercials_root_input.setPlaceholderText("Choose a Commercials folder")
        self.commercials_root_input.setText(self.commercials_settings.get("root_folder", ""))
        commercials_picker = QWidget()
        commercials_picker_layout = QHBoxLayout(commercials_picker)
        commercials_picker_layout.setContentsMargins(0, 0, 0, 0)
        commercials_picker_layout.setSpacing(8)
        commercials_picker_layout.addWidget(self.commercials_root_input, 1)
        self.commercials_browse_btn = QPushButton("Browse")
        self.commercials_browse_btn.clicked.connect(self.choose_commercials_folder)
        commercials_picker_layout.addWidget(self.commercials_browse_btn)

        self.simple_commercials_enabled = QCheckBox("Commercials On")
        self.simple_commercials_enabled.setChecked(bool(self.commercials_settings.get("enabled", False)))
        self.simple_preset_combo = QComboBox()
        self.simple_preset_combo.addItems([
            commercial_simple_preset_label("light_tv"),
            commercial_simple_preset_label("classic_cable"),
            commercial_simple_preset_label("heavy_retro"),
            commercial_simple_preset_label("premium"),
        ])
        self.simple_preset_combo.setCurrentText(commercial_simple_preset_label(self.commercials_settings.get("simple_preset", "classic_cable")))
        self.simple_smart_breaks = QCheckBox("Smart Breaks")
        self.simple_smart_breaks.setChecked(bool(self.commercials_settings.get("smart_breaks", True)))
        self.simple_preset_hint = QLabel("")
        self.simple_preset_hint.setObjectName("presetHint")
        self.simple_preset_hint.setWordWrap(True)

        self.commercials_mode_combo = QComboBox()
        self.commercials_mode_combo.addItems(["between_episodes_only", "natural_breaks", "timed_breaks", "hybrid"])
        self.commercials_mode_combo.setCurrentText(self.commercials_settings.get("mode", "between_episodes_only"))

        self.commercials_density_combo = QComboBox()
        self.commercials_density_combo.addItems(["none", "light", "medium", "heavy", "custom"])
        self.commercials_density_combo.setCurrentText(self.commercials_settings.get("density", "light"))

        self.commercials_preferred_era_combo = QComboBox()
        self.commercials_preferred_era_combo.setEditable(True)
        self.commercials_preferred_era_combo.addItems(["", "70s", "80s", "90s", "2000s", "2010s"])
        self.commercials_preferred_era_combo.setCurrentText(self.commercials_settings.get("preferred_era", ""))

        self.commercials_preferred_category_combo = QComboBox()
        self.commercials_preferred_category_combo.setEditable(True)
        self.commercials_preferred_category_combo.addItems(["", "Kids", "Toys", "Food", "Fast Food", "Games", "Tech", "Music", "Sports", "Movie Theater", "Network Promos", "General"])
        self.commercials_preferred_category_combo.setCurrentText(display_commercial_category(self.commercials_settings.get("preferred_category", "")))

        self.commercials_min_ads_spin = QSpinBox()
        self.commercials_min_ads_spin.setRange(0, 12)
        self.commercials_min_ads_spin.setValue(int(self.commercials_settings.get("min_ads_per_break", 1) or 1))

        self.commercials_max_ads_spin = QSpinBox()
        self.commercials_max_ads_spin.setRange(0, 12)
        self.commercials_max_ads_spin.setValue(int(self.commercials_settings.get("max_ads_per_break", 3) or 3))

        self.commercials_target_interval_spin = QSpinBox()
        self.commercials_target_interval_spin.setRange(1, 60)
        self.commercials_target_interval_spin.setValue(int(self.commercials_settings.get("target_break_interval_minutes", 7) or 7))

        self.commercials_min_between_spin = QSpinBox()
        self.commercials_min_between_spin.setRange(30, 7200)
        self.commercials_min_between_spin.setSingleStep(30)
        self.commercials_min_between_spin.setValue(int(self.commercials_settings.get("min_seconds_between_breaks", 330) or 330))

        self.commercials_first_break_spin = QSpinBox()
        self.commercials_first_break_spin.setRange(0, 1800)
        self.commercials_first_break_spin.setSingleStep(15)
        self.commercials_first_break_spin.setValue(int(self.commercials_settings.get("minimum_content_before_first_break_seconds", 90) or 90))

        self.commercials_jitter_spin = QSpinBox()
        self.commercials_jitter_spin.setRange(0, 600)
        self.commercials_jitter_spin.setSingleStep(15)
        self.commercials_jitter_spin.setValue(int(self.commercials_settings.get("break_jitter_seconds", 45) or 45))

        self.commercials_max_half_hour_spin = QSpinBox()
        self.commercials_max_half_hour_spin.setRange(30, 1800)
        self.commercials_max_half_hour_spin.setSingleStep(15)
        self.commercials_max_half_hour_spin.setValue(int(self.commercials_settings.get("max_ad_seconds_per_half_hour", 240) or 240))

        self.commercials_smart_breaks = QCheckBox("Use Smart Breaks when natural cut points can be found")
        self.commercials_smart_breaks.setChecked(bool(self.commercials_settings.get("smart_breaks", True)))

        self.commercials_allow_fallback = QCheckBox("Allow fallback through era/type/general/all commercials")
        self.commercials_allow_fallback.setChecked(bool(self.commercials_settings.get("allow_fallback", True)))

        self.commercials_pre_roll = QCheckBox("Allow commercials before a program starts")
        self.commercials_pre_roll.setChecked(bool(self.commercials_settings.get("pre_roll_enabled", False)))

        self.commercials_post_roll = QCheckBox("Allow commercials after a program ends")
        self.commercials_post_roll.setChecked(bool(self.commercials_settings.get("post_roll_enabled", False)))

        self.commercials_allow_bumpers = QCheckBox("Allow bumpers in breaks")
        self.commercials_allow_bumpers.setChecked(bool(self.commercials_settings.get("allow_bumpers", True)))

        self.commercials_allow_promos = QCheckBox("Allow promos in breaks")
        self.commercials_allow_promos.setChecked(bool(self.commercials_settings.get("allow_promos", True)))

        self.commercials_prefer_promos = QCheckBox("Prefer promos over regular commercials when available")
        self.commercials_prefer_promos.setChecked(bool(self.commercials_settings.get("prefer_promos", False)))

        self.commercials_allow_station_ids = QCheckBox("Allow station IDs")
        self.commercials_allow_station_ids.setChecked(bool(self.commercials_settings.get("allow_station_ids", True)))

        self.commercials_skip_midroll = QCheckBox("Skip mid-roll breaks if Smart Breaks cannot find a good break point")
        self.commercials_skip_midroll.setChecked(bool(self.commercials_settings.get("skip_midroll_if_no_smart_breaks", False)))

        self.channel_overrides_btn = QPushButton("Edit Channel Commercial Overrides")
        self.channel_overrides_btn.clicked.connect(self.open_channel_overrides_dialog)
        self.open_advanced_commercials_btn = QPushButton("Open Advanced Commercial Settings")
        self.open_advanced_commercials_btn.clicked.connect(self.open_advanced_commercial_settings)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.tabs.addTab(self.build_commercials_tab(), "Commercials")
        self.tabs.addTab(self.build_companion_tab(), "Companions")

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Close")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("saveButton")
        save_btn.clicked.connect(self.accept)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

        self.simple_commercials_enabled.toggled.connect(self.sync_simple_to_advanced)
        self.simple_smart_breaks.toggled.connect(self.sync_simple_to_advanced)
        self.simple_preset_combo.currentTextChanged.connect(self.sync_simple_to_advanced)
        self.refresh_simple_preset_hint()

    def build_section_card(self, title_text, note_text=None):
        card = QWidget()
        card.setObjectName("sectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        title = QLabel(title_text)
        title.setObjectName("sectionHeader")
        layout.addWidget(title)
        if note_text:
            note = QLabel(note_text)
            note.setObjectName("sectionNote")
            note.setWordWrap(True)
            layout.addWidget(note)
        return card, layout

    def build_scroll_tab(self, content):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        scroll = FocusScrollArea()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return container

    def build_commercials_tab(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        card, card_layout = self.build_section_card(
            "Simple Commercial Setup",
            "A quick way to make your channels feel more like TV. These presets feed the same commercial engine as the advanced controls.",
        )
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.addRow("Commercials", self.simple_commercials_enabled)
        form.addRow("Commercial Style", self.simple_preset_combo)
        form.addRow("Smart Breaks", self.simple_smart_breaks)
        form.addRow("Commercials Folder", self._build_row_wrapper(self.commercials_root_input, self.commercials_browse_btn))
        card_layout.addLayout(form)
        card_layout.addWidget(self.simple_preset_hint)
        layout.addWidget(card)

        card2, card2_layout = self.build_section_card(
            "Power User Controls",
            "Fine-tune timing, fallback behavior, channel overrides, and cable test mode in a separate focused menu.",
        )
        card2_layout.addWidget(self.open_advanced_commercials_btn)
        layout.addWidget(card2)
        layout.addStretch(1)
        return self.build_scroll_tab(content)

    def populate_advanced_commercial_sections(self, layout):
        global_card, global_layout = self.build_section_card(
            "Global Commercial Settings",
            "These are the master commercial rules. Simple presets update these values for you, and you can still fine-tune them here.",
        )
        global_form = QFormLayout()
        global_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        global_form.setHorizontalSpacing(16)
        global_form.setVerticalSpacing(10)
        global_form.addRow("Commercials Enabled", self.commercials_enabled)
        global_form.addRow("Global Mode", self.commercials_mode_combo)
        global_form.addRow("Global Density", self.commercials_density_combo)
        global_form.addRow("Default Era Preference", self.commercials_preferred_era_combo)
        global_form.addRow("Default Category Preference", self.commercials_preferred_category_combo)
        global_layout.addLayout(global_form)
        folder_jump = QPushButton("Commercials Folder...")
        folder_jump.clicked.connect(lambda: self.tabs.setCurrentIndex(0))
        global_layout.addWidget(folder_jump)
        global_layout.addWidget(self.commercials_allow_fallback)
        layout.addWidget(global_card)

        timing_card, timing_layout = self.build_section_card(
            "Break Timing",
            "Control how often breaks appear and how large each pod can get.",
        )
        timing_form = QFormLayout()
        timing_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        timing_form.setHorizontalSpacing(16)
        timing_form.setVerticalSpacing(10)
        timing_form.addRow("Min Ads / Break", self.commercials_min_ads_spin)
        timing_form.addRow("Max Ads / Break", self.commercials_max_ads_spin)
        timing_form.addRow("Break Interval (min)", self.commercials_target_interval_spin)
        timing_form.addRow("Min Seconds Between Breaks", self.commercials_min_between_spin)
        timing_form.addRow("Min Before First Break", self.commercials_first_break_spin)
        timing_form.addRow("Break Jitter (sec)", self.commercials_jitter_spin)
        timing_form.addRow("Max Ad Seconds / 30 Min", self.commercials_max_half_hour_spin)
        timing_layout.addLayout(timing_form)
        layout.addWidget(timing_card)

        smart_card, smart_layout = self.build_section_card(
            "Smart Breaks",
            "Use fade-to-black and silence cues when possible, then fall back to timed breaks if needed.",
        )
        smart_layout.addWidget(self.commercials_smart_breaks)
        smart_layout.addWidget(self.commercials_skip_midroll)
        layout.addWidget(smart_card)

        extras_card, extras_layout = self.build_section_card(
            "Bumpers / Promos / Station IDs",
            "Shape the personality of each break without losing the ability to fine-tune channels later.",
        )
        extras_layout.addWidget(self.commercials_pre_roll)
        extras_layout.addWidget(self.commercials_post_roll)
        extras_layout.addWidget(self.commercials_allow_bumpers)
        extras_layout.addWidget(self.commercials_allow_promos)
        extras_layout.addWidget(self.commercials_prefer_promos)
        extras_layout.addWidget(self.commercials_allow_station_ids)
        layout.addWidget(extras_card)

        channel_card, channel_layout = self.build_section_card(
            "Per-Channel Overrides",
            "Each channel can still behave differently: no ads, kid-focused ads, retro density, promo-heavy blocks, and more.",
        )
        channel_layout.addWidget(self.channel_overrides_btn)
        layout.addWidget(channel_card)

    def build_companion_tab(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        companion_card, companion_layout = self.build_section_card(
            "Companion Channels",
        )
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.addRow(self._label("WeatherStar4000"), self.weatherstar_location_input)
        form.addRow(self._label("Weather Channel"), self.weatherstar_channel_input)
        form.addRow(self._label("RadioWaveTV Folder"), self._build_row_wrapper(self.radiowave_input, self.radiowave_browse_btn))
        form.addRow(self._label("Radio Channel"), self.radiowave_channel_input)
        form.addRow(self._label("NetTV Playlist"), self._build_help_stack(self.youtube_playlist_input, self.youtube_playlist_help))
        form.addRow(self._label("NetTV Channel"), self.youtube_channel_input)
        companion_layout.addLayout(form)
        companion_layout.addWidget(self.weatherstar_enabled)
        companion_layout.addWidget(self.radiowave_enabled)
        companion_layout.addWidget(self.youtube_enabled)
        companion_layout.addWidget(self.allow_empty_catalog_tv)
        companion_layout.addWidget(self.allow_dummy_vault_catalog)
        companion_layout.addWidget(self.dev_menu_enabled)
        layout.addWidget(companion_card)

        diagnostics_card, diagnostics_layout = self.build_section_card(
            "Diagnostics",
            "Useful paths and feature state for troubleshooting source vs packaged builds.",
        )
        ffmpeg_status = "found" if resolve_ffmpeg_path() else "missing"
        ffprobe_status = "found" if resolve_ffprobe_path() else "missing"
        ytdlp_status = "found" if resolve_ytdlp_command() else "missing"
        runtime_mode = "packaged app" if getattr(sys, "frozen", False) else "source checkout"
        diagnostics = QLabel(
            f"Runtime: {runtime_mode}\n"
            f"Source/resources: {RESOURCE_DIR}\n"
            f"Writable data/cache: {DATA_DIR}\n"
            f"Current catalog: {(self.parent().catalog_root if self.parent() is not None and hasattr(self.parent(), 'catalog_root') else '') or 'not selected'}\n"
            f"Theme: {self.parent().theme_combo.currentText() if self.parent() is not None and hasattr(self.parent(), 'theme_combo') else 'default'}\n"
            f"FFmpeg: {ffmpeg_status}  •  FFprobe: {ffprobe_status}  •  yt-dlp: {ytdlp_status}\n"
            f"Remote metadata matching: {'experimental enabled' if REMOTE_METADATA_EXPERIMENTAL else 'disabled'}\n"
            f"NetTV: {'enabled (experimental)' if self.youtube_enabled.isChecked() else 'disabled'}"
        )
        diagnostics.setObjectName("sectionNote")
        diagnostics.setWordWrap(True)
        diagnostics_layout.addWidget(diagnostics)
        layout.addWidget(diagnostics_card)
        layout.addStretch(1)
        return self.build_scroll_tab(content)

    def _build_row_wrapper(self, first_widget, second_widget):
        wrapper = QWidget()
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(first_widget, 1)
        row.addWidget(second_widget, 0)
        return wrapper

    def _build_help_stack(self, field_widget, help_widget):
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(field_widget)
        layout.addWidget(help_widget)
        return wrapper

    def _label(self, text):
        label = QLabel(text)
        label.setObjectName("configLabel")
        return label

    def refresh_simple_preset_hint(self):
        preset = normalize_commercial_simple_preset(self.simple_preset_combo.currentText())
        hints = {
            "premium": "Premium / No Ads keeps channels clean and uninterrupted.",
            "light_tv": "Light TV mostly keeps ads between shows with a gentler cadence.",
            "classic_cable": "Set Top Box adds moderate ads, promos, and IDs for a familiar old-TV flow.",
            "heavy_retro": "Heavy Retro leans into dense breaks, more promos, and a stronger throwback feel.",
        }
        self.simple_preset_hint.setText(hints.get(preset, hints["classic_cable"]))

    def sync_simple_to_advanced(self):
        self.refresh_simple_preset_hint()
        preset_key = normalize_commercial_simple_preset(self.simple_preset_combo.currentText())
        resolved = apply_commercial_simple_preset(
            self.values().get("commercials", self.commercials_settings),
            preset_key,
            smart_breaks=self.simple_smart_breaks.isChecked(),
            enabled=self.simple_commercials_enabled.isChecked(),
            root_folder=self.commercials_root_input.text().strip(),
        )
        self.advanced_commercials_settings = json.loads(json.dumps(resolved))
        self.commercials_enabled.setChecked(bool(resolved.get("enabled", False)))
        self.commercials_mode_combo.setCurrentText(resolved.get("mode", "between_episodes_only"))
        self.commercials_density_combo.setCurrentText(resolved.get("density", "light"))
        self.commercials_smart_breaks.setChecked(bool(resolved.get("smart_breaks", True)))
        self.commercials_pre_roll.setChecked(bool(resolved.get("pre_roll_enabled", False)))
        self.commercials_post_roll.setChecked(bool(resolved.get("post_roll_enabled", False)))
        self.commercials_allow_bumpers.setChecked(bool(resolved.get("allow_bumpers", True)))
        self.commercials_allow_promos.setChecked(bool(resolved.get("allow_promos", True)))
        self.commercials_prefer_promos.setChecked(bool(resolved.get("prefer_promos", False)))
        self.commercials_allow_station_ids.setChecked(bool(resolved.get("allow_station_ids", True)))
        self.commercials_min_ads_spin.setValue(int(resolved.get("min_ads_per_break", 1) or 1))
        self.commercials_max_ads_spin.setValue(int(resolved.get("max_ads_per_break", 3) or 3))
        self.commercials_min_between_spin.setValue(int(resolved.get("min_seconds_between_breaks", 330) or 330))
        self.commercials_target_interval_spin.setValue(int(resolved.get("target_break_interval_minutes", 7) or 7))
        self.commercials_first_break_spin.setValue(int(resolved.get("minimum_content_before_first_break_seconds", 90) or 90))
        self.commercials_jitter_spin.setValue(int(resolved.get("break_jitter_seconds", 45) or 45))
        self.commercials_max_half_hour_spin.setValue(int(resolved.get("max_ad_seconds_per_half_hour", 240) or 240))
        self.commercials_skip_midroll.setChecked(bool(resolved.get("skip_midroll_if_no_smart_breaks", False)))

    def open_channel_overrides_dialog(self):
        dialog = CommercialOverridesDialog(self.channel_names, self.channel_commercial_overrides, self)
        if dialog.exec() == QDialog.Accepted:
            self.channel_commercial_overrides = dialog.result_overrides

    def open_advanced_commercial_settings(self):
        settings = self.values().get("commercials", self.advanced_commercials_settings)
        dialog = AdvancedCommercialSettingsDialog(
            settings,
            self.channel_names,
            self.channel_commercial_overrides,
            self.allow_empty_catalog_tv.isChecked(),
            self,
        )
        if dialog.exec() == QDialog.Accepted:
            values = dialog.values()
            self.advanced_commercials_settings = normalize_commercials_config(values.get("commercials", settings))
            self.channel_commercial_overrides = self.advanced_commercials_settings.get("channel_overrides", {})
            self.allow_empty_catalog_tv.setChecked(bool(values.get("allow_empty_catalog_tv", False)))
            self.simple_commercials_enabled.setChecked(bool(self.advanced_commercials_settings.get("enabled", False)))
            self.simple_smart_breaks.setChecked(bool(self.advanced_commercials_settings.get("smart_breaks", True)))

    def values(self):
        commercials = normalize_commercials_config(self.advanced_commercials_settings)
        commercials.update(
            {
                "enabled": self.commercials_enabled.isChecked(),
                "root_folder": self.commercials_root_input.text().strip(),
                "simple_preset": normalize_commercial_simple_preset(self.simple_preset_combo.currentText()),
                "smart_breaks": self.commercials_smart_breaks.isChecked(),
                "channel_overrides": self.channel_commercial_overrides,
            }
        )
        commercials = normalize_commercials_config(commercials)
        self.advanced_commercials_settings = json.loads(json.dumps(commercials))
        return {
            "weatherstar_location": self.weatherstar_location_input.text().strip(),
            "weatherstar_channel_number": self.weatherstar_channel_input.value(),
            "weatherstar_enabled": self.weatherstar_enabled.isChecked(),
            "weatherstar_retro": False,
            "radiowave_folder": self.radiowave_input.text().strip(),
            "radiowave_channel_number": self.radiowave_channel_input.value(),
            "radiowave_enabled": self.radiowave_enabled.isChecked(),
            "youtube_playlist_url": self.youtube_playlist_input.text().strip(),
            "youtube_channel_number": self.youtube_channel_input.value(),
            "youtube_enabled": self.youtube_enabled.isChecked(),
            "allow_empty_catalog_tv": self.allow_empty_catalog_tv.isChecked(),
            "allow_dummy_vault_catalog": self.allow_dummy_vault_catalog.isChecked(),
            "dev_menu_enabled": self.dev_menu_enabled.isChecked(),
            "commercials": commercials,
        }

    def choose_radiowave_folder(self):
        start_dir = self.radiowave_input.text().strip() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, "Choose RadioWaveTV Music Folder", start_dir)
        if folder:
            self.radiowave_input.setText(os.path.abspath(os.path.expanduser(folder)))

    def choose_commercials_folder(self):
        start_dir = self.commercials_root_input.text().strip() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, "Choose Commercials Folder", start_dir)
        if folder:
            self.commercials_root_input.setText(os.path.abspath(os.path.expanduser(folder)))

class MetadataReviewDialog(QDialog):
    def __init__(self, entries, fetch_candidates_callback, overrides, parent=None):
        super().__init__(parent)
        self.entries = entries
        self.fetch_candidates_callback = fetch_candidates_callback
        self.result_overrides = json.loads(json.dumps(overrides or {"shows": {}}))
        self.modified_keys = set()
        self.setWindowTitle("Metadata Review")
        self.resize(980, 620)
        self.setModal(True)
        theme_name = parent.theme_combo.currentText() if parent is not None and hasattr(parent, "theme_combo") else DEFAULT_THEME_NAME
        skin_name = parent.skin_combo.currentText() if parent is not None and hasattr(parent, "skin_combo") else DEFAULT_SKIN_NAME
        self.setStyleSheet(build_themed_dialog_stylesheet(theme_name, skin_name))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        card = QWidget()
        card.setObjectName("dialogCard")
        outer.addWidget(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Metadata Review")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        note = QLabel("Experimental remote matching is off by default. If you enable it, review matches carefully and keep local titles whenever you are not sure.")
        note.setObjectName("dialogNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        body = QHBoxLayout()
        body.setSpacing(14)
        layout.addLayout(body, 1)

        self.title_list = QListWidget()
        self.title_list.setMinimumWidth(320)
        self.title_list.setUniformItemSizes(True)
        self.title_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        body.addWidget(self.title_list, 0)

        right = QVBoxLayout()
        right.setSpacing(10)
        body.addLayout(right, 1)

        self.value_title = QLabel("Select a title")
        self.value_title.setObjectName("valueTitle")
        self.value_title.setWordWrap(True)
        right.addWidget(self.value_title)

        self.meta_line = QLabel("")
        self.meta_line.setObjectName("metaLabel")
        self.meta_line.setWordWrap(True)
        right.addWidget(self.meta_line)

        self.reason_box = QLabel("")
        self.reason_box.setObjectName("reasonBox")
        self.reason_box.setWordWrap(True)
        right.addWidget(self.reason_box)

        current_label = QLabel("Current Match")
        current_label.setObjectName("sectionTitle")
        right.addWidget(current_label)
        self.current_match = QLabel("")
        self.current_match.setObjectName("reasonBox")
        self.current_match.setWordWrap(True)
        right.addWidget(self.current_match)

        candidate_label = QLabel("Search Matches")
        candidate_label.setObjectName("sectionTitle")
        right.addWidget(candidate_label)
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.media_type_combo = QComboBox()
        self.media_type_combo.setMinimumHeight(36)
        self.media_type_combo.addItem("Auto Type", "auto")
        self.media_type_combo.addItem("TV Show", "tv")
        self.media_type_combo.addItem("Movie", "movie")
        search_row.addWidget(self.media_type_combo, 0)
        self.provider_combo = QComboBox()
        self.provider_combo.setMinimumHeight(36)
        search_row.addWidget(self.provider_combo, 0)
        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(36)
        self.search_input.setPlaceholderText("Search title")
        search_row.addWidget(self.search_input, 1)
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.search_candidates)
        search_row.addWidget(self.search_btn, 0)
        right.addLayout(search_row)
        self.candidate_combo = QComboBox()
        self.candidate_combo.setMinimumHeight(36)
        right.addWidget(self.candidate_combo)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.apply_btn = QPushButton("Apply Match")
        self.apply_btn.clicked.connect(self.apply_selected_match)
        action_row.addWidget(self.apply_btn)
        self.keep_local_btn = QPushButton("Keep Local Title")
        self.keep_local_btn.clicked.connect(self.keep_local_title)
        action_row.addWidget(self.keep_local_btn)
        self.clear_btn = QPushButton("Clear Override")
        self.clear_btn.clicked.connect(self.clear_override)
        action_row.addWidget(self.clear_btn)
        right.addLayout(action_row)
        right.addStretch(1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_row.addWidget(close_btn)
        save_btn = QPushButton("Save Review")
        save_btn.setObjectName("saveButton")
        save_btn.clicked.connect(self.accept)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

        self.title_list.addItems(
            [
                f"{entry['local_title']}  —  {entry.get('status_label', '')}"
                for entry in self.entries
            ]
        )
        self.title_list.itemSelectionChanged.connect(self.refresh_selection_details)
        if self.entries:
            self.title_list.setCurrentRow(0)

    def current_entry(self):
        index = self.title_list.currentRow()
        if index < 0 or index >= len(self.entries):
            return None
        return self.entries[index]

    def selected_rows(self):
        rows = sorted({index.row() for index in self.title_list.selectedIndexes()})
        if rows:
            return rows
        current = self.title_list.currentRow()
        return [current] if 0 <= current < len(self.entries) else []

    def selected_entries(self):
        return [self.entries[row] for row in self.selected_rows() if 0 <= row < len(self.entries)]

    def update_row_label(self, row):
        if not (0 <= row < len(self.entries)):
            return
        item = self.title_list.item(row)
        if item is None:
            return
        entry = self.entries[row]
        item.setText(f"{entry['local_title']}  —  {entry.get('status_label', '')}")

    def refresh_selection_details(self):
        rows = self.selected_rows()
        if not rows:
            return
        self.update_entry_details(rows[0])

    def update_entry_details(self, index):
        entry = self.entries[index] if 0 <= index < len(self.entries) else None
        if not entry:
            return
        selected_entries = self.selected_entries()
        selected_count = len(selected_entries)
        if selected_count > 1:
            self.value_title.setText(f"{selected_count} titles selected")
            self.meta_line.setText("Batch review mode  •  The chosen action will apply to every selected title.")
            self.reason_box.setText(
                "You can hold Shift or Command to select multiple titles. Search once, then apply the chosen match, keep-local rule, or clear override across the whole selection."
            )
        else:
            self.value_title.setText(entry.get("local_title", ""))
            self.meta_line.setText(entry.get("meta_line", ""))
            self.reason_box.setText(entry.get("reason_text", ""))
        self.current_match.setText(entry.get("current_match_text", "Using local titles"))
        self.configure_media_type(entry)
        self.configure_sources(entry)
        self.search_input.setText(entry.get("search_query") or entry.get("local_title", ""))
        self.populate_candidates(entry)

    def configure_media_type(self, entry):
        self.media_type_combo.blockSignals(True)
        selected = entry.get("forced_media_type") or entry.get("media_type") or "auto"
        if selected not in {"auto", "tv", "movie"}:
            selected = "auto"
        index = self.media_type_combo.findData(selected)
        if index < 0:
            index = 0
        self.media_type_combo.setCurrentIndex(index)
        self.media_type_combo.blockSignals(False)

    def configure_sources(self, entry):
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        self.provider_combo.addItem("All Sources", "auto")
        self.provider_combo.addItem("TVmaze", "tvmaze")
        self.provider_combo.addItem("Anime DB", "anilist")
        self.provider_combo.addItem("Movie DB", "tmdb")
        current_source = entry.get("preferred_source")
        if current_source:
            index = self.provider_combo.findData(current_source)
            if index >= 0:
                self.provider_combo.setCurrentIndex(index)
        self.provider_combo.blockSignals(False)

    def populate_candidates(self, entry):
        self.candidate_combo.blockSignals(True)
        self.candidate_combo.clear()
        candidates = entry.get("candidates", [])
        if not candidates:
            self.candidate_combo.addItem("Search to load possible matches")
            self.candidate_combo.setEnabled(False)
        else:
            for candidate in candidates:
                self.candidate_combo.addItem(candidate.get("label", candidate.get("name", "Candidate")), candidate)
            self.candidate_combo.setEnabled(True)
        self.candidate_combo.blockSignals(False)

    def search_candidates(self):
        entry = self.current_entry()
        if not entry:
            return
        rows = self.selected_rows()
        provider = self.provider_combo.currentData()
        forced_media_type = self.media_type_combo.currentData() or "auto"
        query = self.search_input.text().strip() or entry.get("local_title", "")
        candidates = self.fetch_candidates_callback(entry, provider=provider, query=query, forced_media_type=forced_media_type)
        for row in rows:
            selected_entry = self.entries[row]
            selected_entry["preferred_source"] = provider
            selected_entry["search_query"] = query
            selected_entry["forced_media_type"] = forced_media_type
            if forced_media_type in {"tv", "movie"}:
                selected_entry["media_type"] = forced_media_type
            selected_entry["candidates"] = list(candidates)
            selected_entry["reason_text"] = (
                "Choose the correct title below. MediaWave will remember the source you pick for future scans."
                if candidates else
                "No close matches came back for that search yet. Try a shorter title or switch sources."
            )
        self.update_entry_details(self.title_list.currentRow())

    def apply_selected_match(self):
        entry = self.current_entry()
        selected = self.selected_entries()
        if not entry or not selected:
            return
        candidate = self.candidate_combo.currentData()
        forced_media_type = self.media_type_combo.currentData() or "auto"
        if isinstance(candidate, dict):
            override = {
                "media_type": forced_media_type if forced_media_type in {"tv", "movie"} else candidate.get("media_type", entry.get("media_type", "tv")),
                "source": candidate.get("source", "tvmaze"),
                "title": candidate.get("name", ""),
            }
            if candidate.get("source") == "tvmaze":
                override["tvmaze_id"] = candidate.get("id")
            elif candidate.get("source") == "anilist":
                override["anilist_id"] = candidate.get("id")
            elif candidate.get("source") == "tmdb":
                override["tmdb_id"] = candidate.get("id")
            current_match_text = f"Manual override: {candidate.get('label', candidate.get('name', 'Selected match'))}"
            status_label = "Manually Matched"
        elif forced_media_type in {"tv", "movie"}:
            override = {
                "media_type": forced_media_type,
                "source": "local",
                "title": entry.get("local_title", ""),
            }
            current_match_text = f"Manual override: treat as {'TV Show' if forced_media_type == 'tv' else 'Movie'} using local titles"
            status_label = "Manual Type"
        else:
            return
        for row in self.selected_rows():
            selected_entry = self.entries[row]
            override_key = selected_entry.get("override_key") or selected_entry["lookup_key"]
            self.result_overrides.setdefault("shows", {})[override_key] = dict(override)
            self.modified_keys.add(override_key)
            selected_entry["media_type"] = override.get("media_type", selected_entry.get("media_type", "tv"))
            selected_entry["forced_media_type"] = selected_entry["media_type"] if selected_entry["media_type"] in {"tv", "movie"} else "auto"
            selected_entry["current_match_text"] = current_match_text
            selected_entry["status_label"] = status_label
            selected_entry["reason_text"] = (
                "MediaWave will rebuild this title using your manual media-type choice."
                if override.get("source") == "local"
                else selected_entry.get("reason_text", "")
            )
            self.update_row_label(row)
        self.update_entry_details(self.title_list.currentRow())

    def keep_local_title(self):
        selected = self.selected_entries()
        if not selected:
            return
        forced_media_type = self.media_type_combo.currentData() or "auto"
        for row in self.selected_rows():
            entry = self.entries[row]
            override_key = entry.get("override_key") or entry["lookup_key"]
            self.result_overrides.setdefault("shows", {})[override_key] = {
                "media_type": forced_media_type if forced_media_type in {"tv", "movie"} else entry.get("media_type", "tv"),
                "source": "local",
                "title": entry.get("local_title", ""),
            }
            self.modified_keys.add(override_key)
            if forced_media_type in {"tv", "movie"}:
                entry["media_type"] = forced_media_type
                entry["forced_media_type"] = forced_media_type
            entry["current_match_text"] = "Manual override: keep local titles"
            entry["status_label"] = "Keep Local"
            self.update_row_label(row)
        self.update_entry_details(self.title_list.currentRow())

    def clear_override(self):
        selected = self.selected_entries()
        if not selected:
            return
        for row in self.selected_rows():
            entry = self.entries[row]
            override_key = entry.get("override_key") or entry["lookup_key"]
            self.result_overrides.setdefault("shows", {}).pop(override_key, None)
            if override_key != entry["lookup_key"]:
                self.result_overrides.setdefault("shows", {}).pop(entry["lookup_key"], None)
            self.modified_keys.add(override_key)
            entry["current_match_text"] = "Automatic matching will be used again"
            entry["status_label"] = "Automatic"
            self.update_row_label(row)
        self.update_entry_details(self.title_list.currentRow())


class VideoSurface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_frame = QPixmap()
        self.last_target_rect = None
        self.profile_name = "Auto"
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setStyleSheet("background-color: black;")

    def set_frame(self, pixmap):
        self.current_frame = pixmap
        self.update()

    def set_display_profile(self, profile_name):
        self.profile_name = profile_name if profile_name in GUIDE_PROFILES else "Auto"
        self.update()

    def video_rect(self):
        return self.last_target_rect or self.display_rect()

    def display_rect(self):
        widget_rect = self.rect()
        if widget_rect.isEmpty():
            return widget_rect
        profile = GUIDE_PROFILES.get(self.profile_name, GUIDE_PROFILES["Auto"])
        target_aspect = profile["target_aspect"]
        if not target_aspect:
            return widget_rect

        widget_w = max(1, widget_rect.width())
        widget_h = max(1, widget_rect.height())
        if (widget_w / widget_h) > target_aspect:
            target_h = widget_h
            target_w = int(target_h * target_aspect)
        else:
            target_w = widget_w
            target_h = int(target_w / target_aspect)

        target_x = (widget_w - target_w) // 2
        target_y = (widget_h - target_h) // 2
        return QRect(target_x, target_y, target_w, target_h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        if self.current_frame.isNull():
            self.last_target_rect = self.display_rect()
            return

        target_rect, source_rect = self.compute_video_mapping()
        self.last_target_rect = target_rect
        painter.drawPixmap(target_rect, self.current_frame, source_rect)

    def compute_video_mapping(self):
        widget_rect = self.rect()
        if widget_rect.isEmpty():
            return widget_rect, self.current_frame.rect()

        profile = GUIDE_PROFILES.get(self.profile_name, GUIDE_PROFILES["Auto"])
        target_aspect = profile["target_aspect"]

        if not target_aspect:
            scaled = self.current_frame.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            return scaled.rect().translated(x, y), self.current_frame.rect()

        widget_w = max(1, widget_rect.width())
        widget_h = max(1, widget_rect.height())
        if (widget_w / widget_h) > target_aspect:
            target_h = widget_h
            target_w = int(target_h * target_aspect)
        else:
            target_w = widget_w
            target_h = int(target_w / target_aspect)

        target_x = (widget_w - target_w) // 2
        target_y = (widget_h - target_h) // 2
        target_rect = QRect(target_x, target_y, target_w, target_h)

        src_rect = self.current_frame.rect()
        src_w = max(1, src_rect.width())
        src_h = max(1, src_rect.height())
        src_aspect = src_w / src_h

        if src_aspect > target_aspect:
            crop_w = int(src_h * target_aspect)
            extra_w = max(0, src_w - crop_w)
            pan = extra_w // 2
            source_rect = src_rect.adjusted(pan, 0, -(extra_w - pan), 0)
        elif src_aspect < target_aspect:
            crop_h = int(src_w / target_aspect)
            extra_h = max(0, src_h - crop_h)
            top_crop = extra_h // 2
            source_rect = src_rect.adjusted(0, top_crop, 0, -(extra_h - top_crop))
        else:
            source_rect = src_rect

        return target_rect, source_rect


# ---------------- MAIN ---------------- #

class ChannelSurfer(QWidget):
    commercialWarmScanFinished = Signal(int, str, str, list)
    youtubeStreamResolved = Signal(int, dict, str, str, float)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(760, 460)
        self.app_settings = load_json_file(
            APP_SETTINGS_FILE,
            {
                "display_mode": "Auto",
                "guide_theme": DEFAULT_THEME_NAME,
                "guide_skin": DEFAULT_SKIN_NAME,
                "guide_ui_scale": GUIDE_UI_SCALE_DEFAULT,
                "catalog_path": "",
                "weatherstar_location": "",
                "weatherstar_channel_number": 1,
                "weatherstar_enabled": False,
                "weatherstar_retro": False,
                "radiowave_folder": "",
                "radiowave_channel_number": 1,
                "radiowave_enabled": False,
                "youtube_playlist_url": "",
                "youtube_channel_number": 1,
                "youtube_enabled": False,
                "allow_empty_catalog_tv": False,
                "allow_dummy_vault_catalog": False,
                "dev_menu_enabled": True,
                "experimental_remote_metadata": False,
                "commercials": commercial_settings_defaults(),
            },
        )
        original_skin = self.app_settings.get("guide_skin", DEFAULT_SKIN_NAME)
        original_theme = self.app_settings.get("guide_theme", DEFAULT_THEME_NAME)
        migrated_skin = normalize_skin_name(original_skin)
        migrated_theme = normalize_theme_for_skin(
            original_skin,
            original_theme,
        )
        self.app_settings["guide_skin"] = migrated_skin
        self.app_settings["guide_theme"] = migrated_theme
        self.app_settings["commercials"] = normalize_commercials_config(self.app_settings.get("commercials", {}))
        if original_skin != migrated_skin or original_theme != migrated_theme:
            save_json_file(APP_SETTINGS_FILE, self.app_settings)
        self.resume_state = load_json_file(RESUME_STATE_FILE, {"entries": {}})
        self.youtube_playlist_cache_state = load_json_file(
            YOUTUBE_PLAYLIST_CACHE_FILE,
            {"playlists": {}, "streams": {}},
        )
        self.last_nettv_error = ""

        self.setObjectName("startupWindow")
        self.setStyleSheet(build_startup_stylesheet(
            self.app_settings.get("guide_theme", DEFAULT_THEME_NAME),
            self.app_settings.get("guide_skin", DEFAULT_SKIN_NAME),
        ))

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        hero = QWidget()
        hero.setObjectName("chromeCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(22, 18, 22, 18)
        hero_layout.setSpacing(12)

        self.startup_logo = QLabel()
        self.startup_logo.setObjectName("startupLogo")
        self.startup_logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        startup_logo = load_brand_logo(460, 88)
        if not startup_logo.isNull():
            self.startup_logo.setPixmap(startup_logo)
        hero_layout.addWidget(self.startup_logo)

        self.subtitle_label = QLabel("Grab the Clicker!")
        self.subtitle_label.setObjectName("subLabel")
        hero_layout.addWidget(self.subtitle_label)

        self.status = QLabel("Choose a catalog, add optional local artwork/descriptions, then press Watch TV when you’re ready to go live.")
        self.status.setObjectName("statusLabel")
        self.status.setWordWrap(True)

        self.loading_card = QWidget()
        self.loading_card.setObjectName("loadingCard")
        loading_layout = QVBoxLayout(self.loading_card)
        loading_layout.setContentsMargins(14, 12, 14, 12)
        loading_layout.setSpacing(8)
        self.loading_stage = QLabel("Loading catalog")
        self.loading_stage.setObjectName("loadingStage")
        loading_layout.addWidget(self.loading_stage)
        self.loading_detail = QLabel("")
        self.loading_detail.setObjectName("loadingDetail")
        self.loading_detail.setWordWrap(True)
        loading_layout.addWidget(self.loading_detail)
        self.loading_progress = QProgressBar()
        self.loading_progress.setTextVisible(True)
        loading_layout.addWidget(self.loading_progress)
        self.loading_card.hide()
        hero_layout.addWidget(self.status)
        hero_layout.addWidget(self.loading_card)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.catalog_btn = QPushButton("Choose Catalog")
        button_row.addWidget(self.catalog_btn)
        self.watch_btn = QPushButton("Watch TV")
        self.watch_btn.setObjectName("watchButton")
        button_row.addWidget(self.watch_btn)
        hero_layout.addLayout(button_row)
        layout.addWidget(hero)

        content_row = QHBoxLayout()
        content_row.setSpacing(14)

        sidebar = QWidget()
        sidebar.setObjectName("sourceCard")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(10)

        library_label = QLabel("Library")
        library_label.setObjectName("sectionLabel")
        sidebar_layout.addWidget(library_label)

        self.catalog_path_label = QLabel("No catalog selected yet.")
        self.catalog_path_label.setObjectName("infoPill")
        self.catalog_path_label.setWordWrap(True)
        sidebar_layout.addWidget(self.catalog_path_label)

        self.library_summary = QLabel("No channels loaded")
        self.library_summary.setObjectName("infoPill")
        sidebar_layout.addWidget(self.library_summary)
        sidebar_layout.addStretch(1)

        settings_form = QFormLayout()
        settings_form.setSpacing(12)
        settings_form.setHorizontalSpacing(16)
        settings_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        settings_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(220)
        self.profile_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.profile_combo.addItems(list(GUIDE_PROFILES.keys()))
        saved_profile = self.app_settings.get("display_mode", "Auto")
        if saved_profile in GUIDE_PROFILES:
            self.profile_combo.setCurrentText(saved_profile)
        profile_label = QLabel("Display Mode")
        profile_label.setObjectName("fieldLabel")
        settings_form.addRow(profile_label, self.profile_combo)

        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumWidth(220)
        self.theme_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.skin_combo = QComboBox()
        self.skin_combo.setMinimumWidth(220)
        self.skin_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.skin_combo.addItems(list(GUIDE_SKINS.keys()))
        saved_skin = normalize_skin_name(self.app_settings.get("guide_skin", DEFAULT_SKIN_NAME))
        self.skin_combo.setCurrentText(saved_skin)
        skin_label = QLabel("Skin")
        skin_label.setObjectName("fieldLabel")
        settings_form.addRow(skin_label, self.skin_combo)
        self.refresh_theme_combo_for_skin(initial_theme=self.app_settings.get("guide_theme", DEFAULT_THEME_NAME))
        theme_label = QLabel("Guide Theme")
        theme_label.setObjectName("fieldLabel")
        settings_form.addRow(theme_label, self.theme_combo)

        settings_card = QWidget()
        settings_card.setObjectName("chromeCard")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(18, 18, 18, 18)
        settings_layout.setSpacing(12)
        playback_label = QLabel("Playback Setup")
        playback_label.setObjectName("sectionLabel")
        settings_layout.addWidget(playback_label)
        settings_layout.addLayout(settings_form)
        self.allow_empty_catalog_tv_check = QCheckBox("Allow Watch TV without local content loaded")
        self.allow_empty_catalog_tv_check.setChecked(bool(self.app_settings.get("allow_empty_catalog_tv", False)))
        settings_layout.addWidget(self.allow_empty_catalog_tv_check)
        self.allow_dummy_vault_check = QCheckBox("Allow dummy Vault listings without a catalog")
        self.allow_dummy_vault_check.setChecked(bool(self.app_settings.get("allow_dummy_vault_catalog", False)))
        settings_layout.addWidget(self.allow_dummy_vault_check)
        self.dev_menu_enabled_check = QCheckBox("Enable in-app dev menu")
        self.dev_menu_enabled_check.setChecked(bool(self.app_settings.get("dev_menu_enabled", True)))
        settings_layout.addWidget(self.dev_menu_enabled_check)
        self.advanced_btn = QPushButton("Advanced Configuration")
        self.advanced_btn.setObjectName("advancedButton")
        settings_layout.addWidget(self.advanced_btn)
        setup_note = QLabel(f"Your theme and display mode are remembered automatically the next time you open {APP_NAME}.")
        setup_note.setObjectName("infoPill")
        setup_note.setWordWrap(True)
        settings_layout.addWidget(setup_note)
        settings_layout.addStretch(1)

        content_row.addWidget(sidebar)
        content_row.addWidget(settings_card, 1)
        layout.addLayout(content_row)
        self.setLayout(layout)

        self.catalog_btn.clicked.connect(self.browse_catalog)
        self.watch_btn.clicked.connect(self.watch_tv)
        self.advanced_btn.clicked.connect(self.open_advanced_configuration)
        self.allow_empty_catalog_tv_check.toggled.connect(lambda value: self.update_qol_setting("allow_empty_catalog_tv", value))
        self.allow_dummy_vault_check.toggled.connect(lambda value: self.update_qol_setting("allow_dummy_vault_catalog", value))
        self.dev_menu_enabled_check.toggled.connect(lambda value: self.update_qol_setting("dev_menu_enabled", value))

        self.channels = []
        self.current_channel = 0
        self.duration_cache = load_json_file(MEDIA_CACHE_FILE, {})
        self.radiowave_metadata_cache = load_json_file(RADIOWAVE_METADATA_CACHE_FILE, {})
        self.schedule_state = load_json_file(SCHEDULE_STATE_FILE, {"catalogs": {}})
        self.commercial_library_cache_state = load_json_file(COMMERCIAL_LIBRARY_CACHE_FILE, {"signature": "", "root_folder": "", "assets": []})
        self.smart_break_cache_state = load_json_file(SMART_BREAK_CACHE_FILE, {"entries": {}})
        self.tmdb_cache = load_json_file(TMDB_CACHE_FILE, {})
        self.tmdb_overrides = load_json_file(TMDB_OVERRIDES_FILE, {"shows": {}})
        self.tmdb_review = load_json_file(TMDB_REVIEW_FILE, {"shows": {}})
        self.on_demand_cache_state = load_json_file(ON_DEMAND_CACHE_FILE, {"signature": "", "catalog": []})
        self.catalog_validation_cache = load_json_file(CATALOG_VALIDATION_FILE, {"videos": {}})
        self.tmdb_client = TMDBClient(load_tmdb_token()) if REMOTE_METADATA_EXPERIMENTAL else None
        self.tvmaze_client = TVMazeClient() if REMOTE_METADATA_EXPERIMENTAL else None
        self.anilist_client = AniListClient() if REMOTE_METADATA_EXPERIMENTAL else None
        self.metadata_queue = []
        self.last_metadata_overlay_refresh_at = 0.0
        self.catalog_progress_last_pump = 0.0
        self.catalog_root = None
        self.commercial_library = []
        self.commercial_warm_queue = []
        self.commercial_warm_path_channels = {}
        self.commercial_warm_inflight = None
        self.commercial_warm_thread = None
        self.commercial_warm_generation = 0
        self.commercial_warm_dirty_channels = set()
        self.commercial_warm_completed_since_refresh = 0

        self.video_window = VideoWindow()
        self.guide_ui_scale = clamp_guide_ui_scale(self.app_settings.get("guide_ui_scale", GUIDE_UI_SCALE_DEFAULT))
        self.video_window.configure_display(
            self.profile_combo.currentText(),
            self.theme_combo.currentText(),
            self.skin_combo.currentText(),
            self.guide_ui_scale,
        )
        self.sync_overlay_qol_settings()
        self.video_window.channelUpRequested.connect(self.up)
        self.video_window.channelDownRequested.connect(self.down)
        self.video_window.guideRequested.connect(self.toggle_guide)
        self.video_window.guideUpRequested.connect(self.guide_up)
        self.video_window.guideDownRequested.connect(self.guide_down)
        self.video_window.guideLeftRequested.connect(self.guide_left)
        self.video_window.guideRightRequested.connect(self.guide_right)
        self.video_window.guideSelectRequested.connect(self.guide_select)
        self.video_window.guideCloseRequested.connect(self.hide_guide)
        self.video_window.guideSettingsRequested.connect(self.toggle_guide_settings)
        self.video_window.onDemandRequested.connect(self.toggle_on_demand)
        self.video_window.onDemandSettingsRequested.connect(self.toggle_on_demand_settings)
        self.video_window.onDemandUpRequested.connect(self.on_demand_up)
        self.video_window.onDemandDownRequested.connect(self.on_demand_down)
        self.video_window.onDemandLeftRequested.connect(self.on_demand_left)
        self.video_window.onDemandRightRequested.connect(self.on_demand_right)
        self.video_window.onDemandSelectRequested.connect(self.on_demand_select)
        self.video_window.onDemandCloseRequested.connect(self.on_demand_back)
        self.video_window.onDemandSeekRequested.connect(self.seek_on_demand)
        self.video_window.onDemandSeekPressChanged.connect(self.on_seek_press_changed)
        self.video_window.playbackToggleRequested.connect(self.toggle_play_pause)
        self.video_window.infoRequested.connect(self.toggle_info_banner)
        self.video_window.infoLeftRequested.connect(self.info_left)
        self.video_window.infoRightRequested.connect(self.info_right)
        self.video_window.infoUpRequested.connect(self.info_up)
        self.video_window.infoDownRequested.connect(self.info_down)
        self.video_window.infoSelectRequested.connect(self.info_select)
        self.video_window.infoCloseRequested.connect(self.hide_info_banner)
        self.video_window.uiScaleRequested.connect(self.adjust_ui_scale)
        self.video_window.guide_overlay.themeStepRequested.connect(self.step_theme)
        self.video_window.guide_overlay.skinStepRequested.connect(self.step_skin)
        self.video_window.guide_overlay.profileStepRequested.connect(self.step_profile)
        self.video_window.guide_overlay.uiScaleStepRequested.connect(self.adjust_ui_scale)
        self.video_window.guide_overlay.catalogRequested.connect(self.select_catalog_from_menu)
        self.video_window.on_demand_overlay.skinStepRequested.connect(self.step_skin)
        self.video_window.on_demand_overlay.themeStepRequested.connect(self.step_theme)
        self.video_window.on_demand_overlay.profileStepRequested.connect(self.step_profile)
        self.video_window.on_demand_overlay.uiScaleStepRequested.connect(self.adjust_ui_scale)
        self.video_window.on_demand_overlay.footerNavRequested.connect(lambda index: self.activate_universal_nav("vault", index))
        self.video_window.on_demand_overlay.settingsCloseRequested.connect(self.close_on_demand_settings)
        self.video_window.on_demand_overlay.homeCardRequested.connect(self.open_on_demand_home_card)
        self.video_window.on_demand_overlay.upRequested.connect(self.on_demand_up)
        self.video_window.on_demand_overlay.downRequested.connect(self.on_demand_down)
        self.video_window.on_demand_overlay.leftRequested.connect(self.on_demand_left)
        self.video_window.on_demand_overlay.rightRequested.connect(self.on_demand_right)
        self.video_window.on_demand_overlay.selectRequested.connect(self.on_demand_select)
        self.video_window.on_demand_overlay.backRequested.connect(self.on_demand_back)
        self.video_window.on_demand_overlay.settingsToggleRequested.connect(self.toggle_on_demand_settings)
        self.video_window.info_overlay.uiScaleStepRequested.connect(self.adjust_ui_scale)
        self.guide_selection = 0
        self.on_demand_catalog = []
        self.on_demand_catalog_signature = ""
        self.on_demand_catalog_dirty = True
        self.on_demand_render_sections = []
        self.on_demand_last_open_request = None
        self.on_demand_view = "home"
        self.on_demand_menu_index = 0
        self.on_demand_channel_index = 0
        self.on_demand_group_index = 0
        self.on_demand_item_index = 0
        self.on_demand_resume_index = 0
        self.on_demand_action_index = 0
        self.on_demand_section_index = 0
        self.on_demand_section_item_indices = {}
        self.on_demand_detail_focus = "actions"
        self.on_demand_season_index = 0
        self.on_demand_back_focused = False
        self.on_demand_nav_focused = False
        self.on_demand_nav_index = 3
        self.on_demand_settings_open = False
        self.on_demand_settings_focus_index = 0
        self.playback_mode = "live"
        self.current_on_demand_path = None
        self.live_info_nav_focused = False
        self.live_info_nav_index = 1
        self.live_info_settings_open = False
        self.live_info_settings_focus_index = 0
        self.live_info_action_index = -1
        self.pending_video = None
        self.pending_weather_url = None
        self.pending_weather_name = ""
        self.pending_weather_location = ""
        self.pending_radiowave_channel = None
        self.pending_youtube_url = None
        self.pending_youtube_entry = None
        self.pending_video_is_url = False
        self.current_youtube_user_path = ""
        self.youtube_stream_generation = 0
        self.youtube_cache_lock = threading.Lock()
        self.nettv_waiting_for_visible_frame = False
        self.nettv_visible_frame_seen = False
        self.nettv_waiting_started_at = 0.0
        self.nettv_black_frame_started_at = 0.0
        self.nettv_last_status_update_at = 0.0
        self.nettv_current_title = "NetTV"
        self.nettv_current_message = "Preparing your playlist feed..."
        self.nettv_playing_entry = {}
        self.nettv_playing_started_at = 0.0
        self.nettv_playing_offset = 0.0
        self.nettv_loaded_entry_path = ""
        self.nettv_loaded_stream_url = ""
        self.nettv_last_frame = QPixmap()
        self.nettv_pending_seek_ms = 0
        self.nettv_pending_play_after_seek = False
        self.nettv_prefetch_active = False
        self.nettv_prefetch_generation = 0
        self.pending_offset = 0
        self.pending_seek_ms = 0
        self.pending_play_after_seek = False
        self.last_video_frame = QPixmap()
        self.last_guide_preview_frame_update = 0.0
        self.seek_hold_direction = 0
        self.next_up_state = None
        self.radiowave_state = {
            "title": "",
            "artist": "",
            "album": "",
            "genre": "",
            "year": "",
            "art_pixmap": QPixmap(),
            "progress_ms": 0,
            "duration_ms": 0,
            "bands": [0.0] * 24,
            "next_tracks": [],
            "track_count": 0,
            "weather_context": "",
            "empty_state": False,
        }
        self.radiowave_current_path = ""
        self.radiowave_channel = None
        self.radiowave_pending_seek_ms = 0
        self.live_stall_path = ""
        self.live_stall_last_position_ms = -1
        self.live_stall_last_advance_at = 0.0
        self.live_stall_checks_started_at = 0.0
        self.live_stall_failures = {}
        self.radiowave_bands = [0.0] * 24
        self.radiowave_cached_art_path = ""
        self.radiowave_cached_art = QPixmap()
        self.radiowave_refresh_timer = QTimer(self)
        self.radiowave_refresh_timer.setSingleShot(True)
        self.radiowave_refresh_timer.timeout.connect(self.refresh_radiowave_state)
        self.radiowave_last_refresh_at = 0.0
        self.radiowave_state_dirty = False
        self.radiowave_last_guide_refresh_at = 0.0
        self.radiowave_last_info_refresh_at = 0.0
        self.audio_output = QAudioOutput(self)
        self.media_player = QMediaPlayer(self)
        self.video_sink = QVideoSink(self)
        self.nettv_audio_output = QAudioOutput(self)
        self.nettv_player = QMediaPlayer(self)
        self.nettv_video_sink = QVideoSink(self)
        self.radiowave_audio_output = QAudioOutput(self)
        self.radiowave_player = QMediaPlayer(self)
        self.radiowave_buffer_output = QAudioBufferOutput(self)
        self.switch_sound = QSoundEffect(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoSink(self.video_sink)
        self.nettv_player.setAudioOutput(self.nettv_audio_output)
        self.nettv_player.setVideoSink(self.nettv_video_sink)
        self.nettv_audio_output.setMuted(True)
        self.nettv_audio_output.setVolume(1.0)
        self.radiowave_player.setAudioOutput(self.radiowave_audio_output)
        self.radiowave_player.setAudioBufferOutput(self.radiowave_buffer_output)
        self.radiowave_audio_output.setMuted(True)
        self.radiowave_audio_output.setVolume(1.0)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.media_player.errorOccurred.connect(self.on_media_error)
        self.media_player.positionChanged.connect(self.on_live_position_changed)
        self.nettv_player.mediaStatusChanged.connect(self.on_nettv_media_status_changed)
        self.nettv_player.errorOccurred.connect(self.on_nettv_media_error)
        self.nettv_video_sink.videoFrameChanged.connect(self.on_nettv_video_frame_changed)
        self.radiowave_player.mediaStatusChanged.connect(self.on_radiowave_media_status_changed)
        self.radiowave_player.positionChanged.connect(self.on_radiowave_position_changed)
        self.radiowave_buffer_output.audioBufferReceived.connect(self.on_radiowave_audio_buffer_received)
        self.video_sink.videoFrameChanged.connect(self.on_video_frame_changed)
        self.switch_sound.setSource(QUrl.fromLocalFile(CHANNEL_SWITCH_SOUND))
        self.switch_sound.setVolume(0.18)
        self.channel_switch_timer = QTimer(self)
        self.channel_switch_timer.setSingleShot(True)
        self.channel_switch_timer.timeout.connect(self.start_pending_channel)
        self.metadata_timer = QTimer(self)
        self.metadata_timer.timeout.connect(self.process_metadata_queue)
        self.resume_timer = QTimer(self)
        self.resume_timer.setInterval(1000)
        self.resume_timer.timeout.connect(self.update_resume_progress)
        self.seek_hold_timer = QTimer(self)
        self.seek_hold_timer.setSingleShot(True)
        self.seek_hold_timer.setInterval(1000)
        self.seek_hold_timer.timeout.connect(self.begin_seek_repeat)
        self.seek_repeat_timer = QTimer(self)
        self.seek_repeat_timer.setInterval(180)
        self.seek_repeat_timer.timeout.connect(self.seek_repeat_step)
        self.info_timer = QTimer(self)
        self.info_timer.setInterval(1000)
        self.info_timer.timeout.connect(self.refresh_info_banner)
        self.live_stall_timer = QTimer(self)
        self.live_stall_timer.setInterval(2000)
        self.live_stall_timer.timeout.connect(self.check_live_playback_health)
        self.commercial_warm_timer = QTimer(self)
        self.commercial_warm_timer.setInterval(15000)
        self.commercial_warm_timer.timeout.connect(self.process_background_commercial_warmup)
        self.commercialWarmScanFinished.connect(self.on_background_commercial_warm_scan_finished)
        self.youtubeStreamResolved.connect(self.on_youtube_stream_resolved)
        self.profile_combo.currentTextChanged.connect(self.apply_display_settings)
        self.theme_combo.currentTextChanged.connect(self.apply_display_settings)
        self.skin_combo.currentTextChanged.connect(self.on_skin_changed)

        # VideoWindow already owns the live playback key handling for channel
        # surf / guide / info / on-demand navigation. Registering the same keys
        # here as application-wide shortcuts causes duplicate activations, which
        # can skip channels or immediately undo a transition.
        self.shortcuts = []

        self.refresh_controls()
        QTimer.singleShot(0, self.auto_load_catalog_if_available)
        QTimer.singleShot(300, self.refresh_nettv_playlist_cache_on_startup)

    # ---------------- LOAD ---------------- #

    @Slot()
    def browse_catalog(self):
        folder = self.choose_catalog_folder()
        if not folder:
            return False
        return self.load_catalog(folder, autoplay=False)

    @Slot()
    def watch_tv(self):
        self.ensure_nettv_playlist_cache_with_progress(force=False)
        if not self.channels:
            saved = (self.app_settings.get("catalog_path") or "").strip()
            if saved and os.path.isdir(saved):
                self.load_catalog(saved, autoplay=False)
            if not self.channels and self.app_settings.get("allow_empty_catalog_tv"):
                self.channels = []
                self.current_channel = 0
                self.inject_special_channels()
                self.refresh_controls()
                if not self.channels:
                    self.status.setText("Enable WeatherStar, RadioWaveTV, or a NetTV playlist channel to Watch TV without local content.")
                    return
            elif not self.channels and not self.browse_catalog():
                return
        self.play_channel()

    def choose_catalog_folder(self):
        if sys.platform == "darwin" and AppKit is not None and Foundation is not None:
            folder = self.choose_catalog_folder_macos()
            if folder:
                return folder
        options = QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        start_dir = self.app_settings.get("catalog_path") or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Catalog Folder",
            start_dir,
            options,
        )
        if not folder:
            return None
        return os.path.abspath(os.path.expanduser(folder))

    def choose_catalog_folder_macos(self):
        start_dir = self.app_settings.get("catalog_path") or os.path.expanduser("~")
        panel = AppKit.NSOpenPanel.openPanel()
        panel.setCanChooseFiles_(False)
        panel.setCanChooseDirectories_(True)
        panel.setAllowsMultipleSelection_(False)
        panel.setCanCreateDirectories_(False)
        panel.setTitle_("Select Catalog Folder")
        panel.setPrompt_("Choose")
        panel.setDirectoryURL_(Foundation.NSURL.fileURLWithPath_(os.path.abspath(os.path.expanduser(start_dir))))
        AppKit.NSApp.activateIgnoringOtherApps_(True)
        result = panel.runModal()
        if result != AppKit.NSModalResponseOK:
            return None
        url = panel.URL()
        if not url:
            return None
        return os.path.abspath(str(url.path()))

    def load_catalog(self, folder=None, autoplay=False):
        if folder is None:
            folder = self.choose_catalog_folder()
        if not folder:
            return False
        if not os.path.isdir(folder):
            self.status.setText(f"Saved catalog folder was not found:\n{folder}")
            return False

        self.catalog_root = folder
        self.app_settings["catalog_path"] = folder
        save_json_file(APP_SETTINGS_FILE, self.app_settings)
        self.catalog_path_label.setText(folder)

        self.stop_radiowave_background()
        self.channels = []
        self.current_channel = 0
        validation_entries = self.catalog_validation_cache.setdefault("videos", {})
        quarantined_files = []
        channel_names = [
            item for item in sorted(os.listdir(folder), key=str.casefold)
            if os.path.isdir(os.path.join(folder, item))
        ]
        self.begin_catalog_progress(folder, len(channel_names))

        for index, item in enumerate(channel_names, start=1):
            path = os.path.join(folder, item)
            ch = Channel(item, self.duration_cache)
            ch.root_path = path
            self.update_catalog_progress(index - 1, len(channel_names), f"Scanning channel {index} of {len(channel_names)}", item)

            for root, dirnames, files in os.walk(path):
                dirnames.sort(key=str.casefold)
                for f in sorted(files, key=str.casefold):
                    if f.startswith("._"):
                        full = os.path.join(root, f)
                        try:
                            moved_to = quarantine_broken_media(full, folder)
                            quarantined_files.append((full, moved_to, "macOS sidecar file"))
                        except OSError:
                            pass
                        continue
                    if f.lower().endswith(VIDEO_EXTS):
                        full = os.path.join(root, f)
                        signature = file_cache_signature(full)
                        validation = validation_entries.get(full, {})
                        if not isinstance(validation, dict) or validation.get("signature") != signature:
                            self.update_catalog_progress(index - 1, len(channel_names), "Validating media health", f"{item}: {f}")
                            ok, checked_signature, reason = validate_video_media(full)
                            validation = {
                                "signature": checked_signature,
                                "ok": bool(ok),
                                "reason": reason or "",
                            }
                            validation_entries[full] = validation
                            if not ok:
                                try:
                                    moved_to = quarantine_broken_media(full, folder)
                                    validation_entries[moved_to] = {
                                        "signature": checked_signature,
                                        "ok": False,
                                        "reason": validation["reason"],
                                        "quarantined_from": full,
                                    }
                                    quarantined_files.append((full, moved_to, validation["reason"]))
                                    validation_entries.pop(full, None)
                                except OSError as exc:
                                    validation["reason"] = validation["reason"] or str(exc)
                                    validation["move_error"] = str(exc)
                                continue
                        elif not validation.get("ok", True):
                            continue

                        self.update_catalog_progress(index - 1, len(channel_names), "Reading media durations", f"{item}: {f}")
                        dur = ch.get_duration(full)

                        if dur > 0:
                            ch.shows.append(full)
                            ch.durations.append(dur)

            if ch.shows:
                self.channels.append(ch)

        self.inject_special_channels()
        self.update_catalog_progress(len(channel_names), len(channel_names), "Saving catalog cache", os.path.basename(folder))
        save_json_file(MEDIA_CACHE_FILE, self.duration_cache)
        save_json_file(RADIOWAVE_METADATA_CACHE_FILE, self.radiowave_metadata_cache)
        save_json_file(CATALOG_VALIDATION_FILE, self.catalog_validation_cache)
        if self.commercials_ready():
            self.load_or_refresh_commercial_library(force_rescan=False, progress_callback=self.update_catalog_progress)
        self.update_catalog_progress(
            len(channel_names),
            len(channel_names),
            "Applying channel schedules",
            "Using cached smart-break data when available and falling back to timed breaks for the first pass.",
        )
        self.apply_channel_schedules(
            folder,
            allow_smart_break_scan=False,
            defer_midroll_if_no_cached_breaks=True,
        )
        if self.prepare_on_demand_catalog(clear_catalog=True):
            self.update_catalog_progress(1, 1, "Loading cached on-demand library", "MediaWave Vault is ready from cache.")
        else:
            self.update_catalog_progress(1, 1, "Deferring on-demand library build", "MediaWave Vault will finish organizing the first time you open it.")
        self.finish_catalog_progress()
        self.refresh_controls()

        if not self.channels:
            self.status.setText(f"No playable videos were found inside:\n{folder}")
            return False

        radiowave_channel = next((channel for channel in self.channels if getattr(channel, "channel_type", "media") == "radiowave"), None)
        quarantine_note = ""
        if quarantined_files:
            quarantine_note = f"\nMoved {len(quarantined_files)} broken file{'s' if len(quarantined_files) != 1 else ''} to the Broken folder beside your catalog."
        if radiowave_channel and getattr(radiowave_channel, "empty_state", False):
            self.status.setText(
                f"Loaded {len(self.channels)} channels from your catalog.\n"
                f"RadioWaveTV is in fallback mode: {radiowave_channel.empty_reason or 'No music was found.'}"
                f"{quarantine_note}"
            )
        else:
            self.status.setText(
                f"Loaded {len(self.channels)} channels from your catalog.\n"
                f"Press Watch TV to open the main interface.{quarantine_note}"
            )
        QTimer.singleShot(0, self.finish_catalog_background_setup)
        if autoplay:
            self.play_channel()
        return True

    def auto_load_catalog_if_available(self):
        saved_catalog = self.app_settings.get("catalog_path", "").strip()
        if saved_catalog and os.path.isdir(saved_catalog):
            self.catalog_root = saved_catalog
            self.catalog_path_label.setText(saved_catalog)
            self.status.setText("Saved catalog ready. Press Watch TV to load it, or Choose Catalog to switch libraries.")

    def finish_catalog_background_setup(self):
        self.preload_weather_if_configured()
        self.queue_background_commercial_warmup(self.catalog_root or self.app_settings.get("catalog_path", ""))

    def refresh_theme_combo_for_skin(self, initial_theme=None):
        skin_name = self.skin_combo.currentText() if hasattr(self, "skin_combo") else DEFAULT_SKIN_NAME
        skin_name = normalize_skin_name(skin_name)
        themes = theme_names_for_skin(skin_name)
        target_theme = normalize_theme_for_skin(skin_name, initial_theme or self.theme_combo.currentText())
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItems(themes)
        self.theme_combo.setCurrentText(target_theme)
        self.theme_combo.blockSignals(False)

    def overlay_settings_values(self):
        return {
            "allow_empty_catalog_tv": bool(self.app_settings.get("allow_empty_catalog_tv", False)),
            "allow_dummy_vault_catalog": bool(self.app_settings.get("allow_dummy_vault_catalog", False)),
            "dev_menu_enabled": bool(self.app_settings.get("dev_menu_enabled", True)),
        }

    def sync_overlay_qol_settings(self):
        values = self.overlay_settings_values()
        self.video_window.guide_overlay.settings_values = dict(values)
        self.video_window.on_demand_overlay.settings_values = dict(values)
        self.video_window.info_overlay.settings_values = dict(values)

    def update_qol_setting(self, key, value, refresh=True):
        self.app_settings[key] = bool(value)
        save_json_file(APP_SETTINGS_FILE, self.app_settings)
        if key == "allow_dummy_vault_catalog":
            self.mark_on_demand_catalog_dirty(clear_catalog=True)
        self.sync_overlay_qol_settings()
        if refresh:
            if self.video_window.guide_overlay.isVisible():
                self.refresh_guide()
            if self.video_window.on_demand_overlay.isVisible():
                self.refresh_on_demand()
            if self.video_window.info_overlay.isVisible():
                self.refresh_info_banner()

    def sync_main_qol_toggles(self):
        for attr, key in (
            ("allow_empty_catalog_tv_check", "allow_empty_catalog_tv"),
            ("allow_dummy_vault_check", "allow_dummy_vault_catalog"),
            ("dev_menu_enabled_check", "dev_menu_enabled"),
        ):
            checkbox = getattr(self, attr, None)
            if checkbox is None:
                continue
            checkbox.blockSignals(True)
            checkbox.setChecked(bool(self.app_settings.get(key, True if key == "dev_menu_enabled" else False)))
            checkbox.blockSignals(False)

    def in_app_menu_row_count(self):
        return 7

    def in_app_menu_close_index(self):
        return self.in_app_menu_row_count() - 1

    def handle_in_app_menu_toggle(self, focus_index):
        key_map = {
            3: "allow_empty_catalog_tv",
            4: "allow_dummy_vault_catalog",
            5: "dev_menu_enabled",
        }
        key = key_map.get(int(focus_index))
        if not key:
            return False
        self.update_qol_setting(key, not bool(self.app_settings.get(key, False)), refresh=False)
        self.sync_main_qol_toggles()
        return True

    def preload_weather_if_configured(self):
        weather = self.configured_weather_channel()
        widescreen = self.profile_combo.currentText() != "CRT 4:3"
        if weather:
            self.video_window.preload_weather_channel(weather.weatherstar_url(widescreen=widescreen))
        self.preload_radiowave_if_configured()

    @Slot()
    def open_advanced_configuration(self):
        dialog = AdvancedConfigDialog(
            self.app_settings,
            [channel.name for channel in self.channels if getattr(channel, "channel_type", "media") == "media"],
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        self.app_settings["weatherstar_location"] = values["weatherstar_location"]
        self.app_settings["weatherstar_channel_number"] = values["weatherstar_channel_number"]
        self.app_settings["weatherstar_enabled"] = values["weatherstar_enabled"]
        self.app_settings["weatherstar_retro"] = values["weatherstar_retro"]
        self.app_settings["radiowave_folder"] = values["radiowave_folder"]
        self.app_settings["radiowave_channel_number"] = values["radiowave_channel_number"]
        self.app_settings["radiowave_enabled"] = values["radiowave_enabled"]
        self.app_settings["youtube_playlist_url"] = values["youtube_playlist_url"]
        self.app_settings["youtube_channel_number"] = values["youtube_channel_number"]
        self.app_settings["youtube_enabled"] = values["youtube_enabled"]
        self.app_settings["allow_empty_catalog_tv"] = values["allow_empty_catalog_tv"]
        self.app_settings["allow_dummy_vault_catalog"] = values["allow_dummy_vault_catalog"]
        self.app_settings["dev_menu_enabled"] = values["dev_menu_enabled"]
        self.app_settings["commercials"] = normalize_commercials_config(values.get("commercials", {}))
        save_json_file(APP_SETTINGS_FILE, self.app_settings)
        self.sync_main_qol_toggles()
        self.sync_overlay_qol_settings()
        self.status.setText("Advanced configuration saved.")
        self.ensure_nettv_playlist_cache_with_progress(force=True)
        self.stop_background_commercial_warmup()
        self.load_or_refresh_commercial_library(force_rescan=False)
        self.prepare_on_demand_catalog(clear_catalog=False)
        if self.channels:
            self.stop_radiowave_background()
            self.inject_special_channels()
            self.preload_weather_if_configured()
            self.apply_channel_schedules(
                self.catalog_root or self.app_settings.get("catalog_path", ""),
                allow_smart_break_scan=False,
                defer_midroll_if_no_cached_breaks=True,
            )
            self.refresh_controls()
            if self.video_window.guide_overlay.isVisible():
                self.guide_selection = min(self.guide_selection, len(self.channels) - 1)
                self.refresh_guide()
            if self.video_window.on_demand_overlay.isVisible():
                self.refresh_on_demand()
        self.refresh_controls()
        self.queue_background_commercial_warmup(self.catalog_root or self.app_settings.get("catalog_path", ""))

    def begin_catalog_progress(self, folder, total_channels):
        self.catalog_btn.setEnabled(False)
        self.watch_btn.setEnabled(False)
        self.status.hide()
        self.catalog_progress_last_pump = 0.0
        self.catalog_progress_started_at = time.time()
        self.loading_stage.setText("Preparing catalog scan")
        self.loading_detail.setText(compact_status_detail(folder, 112))
        self.loading_progress.setMaximum(max(1, total_channels))
        self.loading_progress.setValue(0)
        self.loading_progress.setFormat("%v / %m channels")
        self.loading_card.show()
        QApplication.processEvents()

    def update_catalog_progress(self, current, total, message, detail=""):
        progress_total = max(1, total)
        self.loading_progress.setMaximum(progress_total)
        self.loading_progress.setValue(min(current, progress_total))
        elapsed = max(0.0, time.time() - getattr(self, "catalog_progress_started_at", time.time()))
        eta_text = ""
        if current > 0 and current < total:
            eta_seconds = max(0.0, (elapsed / max(1, current)) * max(0, total - current))
            eta_text = f"  •  About {format_eta_seconds(eta_seconds)} left"
        elif current >= total and total > 0:
            eta_text = "  •  Finishing up"
        self.loading_stage.setText(f"{message}{eta_text}")
        self.loading_detail.setText(compact_status_detail(detail, 112))
        now = time.time()
        if (now - self.catalog_progress_last_pump) >= 0.03 or current >= total:
            self.catalog_progress_last_pump = now
            QApplication.processEvents()

    def finish_catalog_progress(self):
        self.loading_progress.setValue(self.loading_progress.maximum())
        self.loading_card.hide()
        self.status.show()
        self.catalog_btn.setEnabled(True)
        self.refresh_controls()

    def nettv_playlist_cache_needs_refresh(self):
        if not self.app_settings.get("youtube_enabled"):
            return False
        playlist_url = (self.app_settings.get("youtube_playlist_url") or "").strip()
        if not youtube_source_url(playlist_url):
            return False
        key = youtube_playlist_cache_key(playlist_url)
        with self.youtube_cache_lock:
            playlist = (self.youtube_playlist_cache_state.get("playlists") or {}).get(key) or {}
            entries = playlist.get("entries") or []
            updated_at = float(playlist.get("updated_at", 0) or 0)
        return not entries or time.time() - updated_at >= 6 * 3600

    def begin_nettv_progress(self):
        self.catalog_btn.setEnabled(False)
        self.watch_btn.setEnabled(False)
        self.status.hide()
        self.catalog_progress_last_pump = 0.0
        self.catalog_progress_started_at = time.time()
        self.loading_stage.setText("Preparing NetTV playlist")
        self.loading_detail.setText("MediaWave is reading the playlist index so it can behave like a real channel.")
        self.loading_progress.setMaximum(3)
        self.loading_progress.setValue(0)
        self.loading_progress.setFormat("%v / %m steps")
        self.loading_card.show()
        QApplication.processEvents()

    def update_nettv_progress(self, current, total, message, detail=""):
        progress_total = max(1, int(total or 1))
        current = max(0, min(int(current or 0), progress_total))
        self.loading_progress.setMaximum(progress_total)
        self.loading_progress.setValue(current)
        elapsed = max(0.0, time.time() - getattr(self, "catalog_progress_started_at", time.time()))
        eta_text = ""
        if current > 0 and current < progress_total:
            eta_seconds = max(0.0, (elapsed / max(1, current)) * max(0, progress_total - current))
            eta_text = f"  •  About {format_eta_seconds(eta_seconds)} left"
        elif current >= progress_total:
            eta_text = "  •  Finishing up"
        self.loading_stage.setText(f"{message}{eta_text}")
        self.loading_detail.setText(compact_status_detail(detail, 112))
        now = time.time()
        if (now - self.catalog_progress_last_pump) >= 0.03 or current >= progress_total:
            self.catalog_progress_last_pump = now
            QApplication.processEvents()

    def finish_nettv_progress(self):
        self.loading_progress.setValue(self.loading_progress.maximum())
        self.loading_card.hide()
        self.status.show()
        self.catalog_btn.setEnabled(True)
        self.refresh_controls()

    def ensure_nettv_playlist_cache_with_progress(self, force=False):
        if not self.app_settings.get("youtube_enabled"):
            return []
        playlist_url = (self.app_settings.get("youtube_playlist_url") or "").strip()
        if not youtube_source_url(playlist_url):
            return []
        if not force and not self.nettv_playlist_cache_needs_refresh():
            return self.cached_youtube_playlist_entries(playlist_url)
        self.begin_nettv_progress()
        entries = []
        try:
            entries = self.load_youtube_playlist_entries(
                playlist_url,
                force=force,
                progress_callback=self.update_nettv_progress,
            )
        finally:
            self.finish_nettv_progress()
        if entries:
            self.status.setText(f"NetTV playlist ready.\n{len(entries)} videos are indexed for channel playback.")
        else:
            detail = self.last_nettv_error or "Check the URL, internet connection, or yt-dlp."
            self.status.setText(f"NetTV could not read the playlist yet.\n{detail}")
        return entries

    def refresh_nettv_playlist_cache_on_startup(self):
        if self.loading_card.isVisible():
            return
        if not self.nettv_playlist_cache_needs_refresh():
            return
        self.ensure_nettv_playlist_cache_with_progress(force=False)

    def begin_library_match_progress(self, total_items):
        self.catalog_btn.setEnabled(False)
        self.watch_btn.setEnabled(False)
        self.catalog_progress_last_pump = 0.0
        self.catalog_progress_started_at = time.time()
        self.loading_stage.setText("Applying library match changes")
        self.loading_detail.setText("Preparing selected titles...")
        self.loading_progress.setMaximum(max(1, total_items))
        self.loading_progress.setValue(0)
        self.loading_progress.setFormat("%v / %m items")
        self.loading_card.show()
        self.status.setText("Applying library match changes...")
        self.status.show()
        QApplication.processEvents()

    def update_library_match_progress(self, current, total, message, detail=""):
        progress_total = max(1, total)
        self.loading_progress.setMaximum(progress_total)
        self.loading_progress.setValue(min(current, progress_total))
        elapsed = max(0.0, time.time() - getattr(self, "catalog_progress_started_at", time.time()))
        eta_text = ""
        if current > 0 and current < total:
            eta_seconds = max(0.0, (elapsed / max(1, current)) * max(0, total - current))
            eta_text = f"  •  About {format_eta_seconds(eta_seconds)} left"
        elif current >= total and total > 0:
            eta_text = "  •  Finishing up"
        self.loading_stage.setText(f"{message}{eta_text}")
        self.loading_detail.setText(compact_status_detail(detail, 112))
        detail_line = compact_status_detail(detail.replace("\n", " — "), 140).strip()
        self.status.setText(f"{message}..." + (f" {detail_line}" if detail_line else ""))
        now = time.time()
        if (now - self.catalog_progress_last_pump) >= 0.03 or current >= total:
            self.catalog_progress_last_pump = now
            QApplication.processEvents()

    def finish_library_match_progress(self):
        self.loading_card.hide()
        self.catalog_btn.setEnabled(True)
        self.refresh_controls()

    @Slot()
    def select_catalog_from_menu(self):
        self.hide_guide()
        QTimer.singleShot(0, self._open_catalog_picker_from_menu)

    def _open_catalog_picker_from_menu(self):
        was_visible = self.video_window.isVisible()
        if was_visible:
            self.video_window.hide()

        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.ActiveWindowFocusReason)

        folder = self.choose_catalog_folder()

        if folder:
            self.load_catalog(folder, autoplay=True)
            return

        if was_visible and self.channels:
            self.video_window.show()
            self.video_window.showFullScreen()
            self.video_window.raise_()
            self.video_window.activateWindow()
            self.video_window.setFocus(Qt.ActiveWindowFocusReason)

    def commercial_settings(self):
        settings = normalize_commercials_config(self.app_settings.get("commercials", {}))
        self.app_settings["commercials"] = settings
        return settings

    def commercials_ready(self):
        settings = self.commercial_settings()
        return bool(settings.get("enabled")) and bool(settings.get("root_folder")) and os.path.isdir(settings.get("root_folder", ""))

    def media_duration_seconds(self, path):
        cached = float(self.duration_cache.get(path, 0) or 0)
        if cached > 0:
            return cached
        if not FFPROBE_PATH or not path:
            return 0.0
        try:
            result = subprocess.run(
                [
                    FFPROBE_PATH,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=8,
            )
            duration = float((result.stdout or "").strip() or 0)
        except (subprocess.SubprocessError, OSError, ValueError):
            duration = 0.0
        if duration > 0:
            self.duration_cache[path] = duration
        return duration

    def load_or_refresh_commercial_library(self, force_rescan=False, progress_callback=None):
        settings = self.commercial_settings()
        root_folder = settings.get("root_folder", "")
        if not settings.get("enabled") or not root_folder or not os.path.isdir(root_folder):
            self.commercial_library = []
            return []

        signature = build_commercial_root_signature(root_folder)
        cached_signature = self.commercial_library_cache_state.get("signature", "")
        cached_root = self.commercial_library_cache_state.get("root_folder", "")
        cached_assets = self.commercial_library_cache_state.get("assets", [])
        if (
            not force_rescan
            and signature
            and signature == cached_signature
            and os.path.abspath(root_folder) == os.path.abspath(cached_root or "")
            and isinstance(cached_assets, list)
        ):
            self.commercial_library = cached_assets
            if progress_callback:
                progress_callback(
                    1,
                    1,
                    "Using cached commercial library",
                    f"Loaded {len(cached_assets)} commercial assets from cache.",
                )
            return cached_assets

        assets = []
        video_files = []
        for walk_root, dirnames, filenames in os.walk(root_folder):
            dirnames.sort(key=str.casefold)
            for file_name in sorted(filenames, key=str.casefold):
                if file_name.lower().endswith(VIDEO_EXTS):
                    video_files.append(os.path.join(walk_root, file_name))
        total_files = max(1, len(video_files))
        for index, path in enumerate(video_files, start=1):
            relative = os.path.relpath(path, root_folder)
            parts = [part for part in os.path.dirname(relative).split(os.sep) if part and part != "."]
            era = infer_commercial_era_from_parts(parts)
            asset_kind = infer_commercial_asset_kind(parts)
            lowered_parts = [normalize_commercial_category(part) for part in parts]
            cleaned_parts = [part for part in lowered_parts if part and normalize_commercial_era(part) != normalize_commercial_era(era)]
            category = ""
            for candidate in cleaned_parts:
                if candidate in {"commercials", "ads", "ad", "clips"}:
                    continue
                category = candidate
                break
            if asset_kind == "promo" and not category:
                category = "network-promos"
            elif asset_kind == "station_id" and not category:
                category = "station-ids"
            elif not category:
                category = "general"
            if progress_callback:
                progress_callback(
                    index - 1,
                    total_files,
                    "Scanning commercial library",
                    os.path.basename(path),
                )
            duration = self.media_duration_seconds(path)
            if duration <= 0:
                continue
            title = format_program_title(path)
            assets.append(
                {
                    "path": path,
                    "relative_path": relative,
                    "title": title,
                    "duration": duration,
                    "era": era,
                    "category": category,
                    "subcategory": cleaned_parts[1] if len(cleaned_parts) > 1 else "",
                    "asset_kind": asset_kind,
                }
            )
            if progress_callback:
                progress_callback(
                    index,
                    total_files,
                    "Scanning commercial library",
                    os.path.basename(path),
                )
        self.commercial_library = assets
        self.commercial_library_cache_state = {
            "signature": signature,
            "root_folder": root_folder,
            "assets": assets,
        }
        save_json_file(COMMERCIAL_LIBRARY_CACHE_FILE, self.commercial_library_cache_state)
        save_json_file(MEDIA_CACHE_FILE, self.duration_cache)
        return assets

    def resolve_channel_commercial_profile(self, channel_name):
        settings = self.commercial_settings()
        profile = dict(settings)
        override = dict((settings.get("channel_overrides") or {}).get(channel_name, {}))
        enabled_mode = str(override.get("enabled_mode", "inherit") or "inherit")
        if enabled_mode == "off":
            profile["enabled"] = False
        elif enabled_mode == "on":
            profile["enabled"] = True
        for key in (
            "preferred_era",
            "preferred_category",
            "mode",
            "density",
            "min_ads_per_break",
            "max_ads_per_break",
            "min_seconds_between_breaks",
            "target_break_interval_minutes",
            "minimum_content_before_first_break_seconds",
            "max_ad_seconds_per_half_hour",
            "allow_fallback",
            "allow_bumpers",
            "allow_promos",
            "prefer_promos",
            "allow_station_ids",
        ):
            if key in override:
                profile[key] = override[key]
        profile["channel_name"] = channel_name
        return normalize_commercials_config(profile)

    def resolve_commercial_candidates(self, profile, desired_kind="commercial", era="", category=""):
        assets = list(self.commercial_library or [])
        if not assets:
            return []
        allowed_kinds = {desired_kind}
        if desired_kind == "commercial" and profile.get("allow_promos"):
            allowed_kinds.add("promo")
        if desired_kind == "commercial" and profile.get("allow_station_ids"):
            allowed_kinds.add("station_id")
        if desired_kind == "commercial" and profile.get("allow_bumpers"):
            allowed_kinds.add("bumper")
        filtered = [asset for asset in assets if asset.get("asset_kind") in allowed_kinds]
        if not filtered:
            return []

        preferred_era = normalize_commercial_era(era or profile.get("preferred_era", ""))
        preferred_category = normalize_commercial_category(category or profile.get("preferred_category", ""))

        stages = []
        if preferred_era and preferred_category:
            stages.append([asset for asset in filtered if asset.get("era") == preferred_era and asset.get("category") == preferred_category])
        if preferred_era:
            stages.append([asset for asset in filtered if asset.get("era") == preferred_era])
        if preferred_category:
            stages.append([asset for asset in filtered if asset.get("category") == preferred_category])
        stages.append([asset for asset in filtered if asset.get("category") == "general"])
        stages.append(filtered)

        if not profile.get("allow_fallback", True):
            return stages[0] if stages else filtered
        for stage in stages:
            if stage:
                return stage
        return filtered

    def build_commercial_entry(self, asset, channel_name, pod_label, parent_context=None):
        asset_kind = asset.get("asset_kind", "commercial")
        kind_title = {
            "commercial": "Commercial",
            "promo": "Network Promo",
            "bumper": "Bumper",
            "station_id": "Station ID",
        }.get(asset_kind, "Commercial")
        parent_context = parent_context or {}
        return {
            "kind": asset_kind,
            "path": asset.get("path", ""),
            "title": asset.get("title") or kind_title,
            "display_title": asset.get("title") or kind_title,
            "duration": float(asset.get("duration", 0) or 0),
            "start_offset": 0.0,
            "end_offset": float(asset.get("duration", 0) or 0),
            "is_commercial": True,
            "channel_name": channel_name,
            "summary": f"{kind_title} • {display_commercial_category(asset.get('category', 'general'))}",
            "pod_label": pod_label,
            "parent_path": parent_context.get("path", ""),
            "parent_title": parent_context.get("title", ""),
            "parent_show_name": parent_context.get("show_name", ""),
            "parent_summary": parent_context.get("summary", ""),
            "slot_title": parent_context.get("slot_title", ""),
        }

    def compose_commercial_pod(self, channel_name, profile, program_path, pod_seed, pod_label="Commercial Break", ad_seconds_budget=None, parent_context=None):
        if not profile.get("enabled") or not self.commercial_library:
            return []
        minimum, maximum = density_ad_range(profile)
        if maximum <= 0:
            return []
        rng = random.Random(stable_hash(f"{channel_name}|{program_path}|{pod_seed}|{commercial_profile_signature(profile)}"))
        if minimum == maximum:
            count = minimum
        else:
            count = rng.randint(minimum, maximum)
        if count <= 0:
            return []

        era_hint = infer_program_era_from_path(program_path, channel_name)
        category_hint = infer_program_category_from_path(program_path, channel_name)
        pod_entries = []

        def choose_one(kind_name):
            candidates = self.resolve_commercial_candidates(profile, desired_kind=kind_name, era=era_hint, category=category_hint)
            if not candidates:
                return None
            return rng.choice(candidates)

        if profile.get("allow_bumpers") and rng.random() < 0.22:
            bumper = choose_one("bumper")
            if bumper:
                pod_entries.append(self.build_commercial_entry(bumper, channel_name, pod_label, parent_context=parent_context))

        for slot in range(count):
            desired_kind = "promo" if profile.get("prefer_promos") and profile.get("allow_promos") and rng.random() < 0.5 else "commercial"
            asset = choose_one(desired_kind)
            if not asset and desired_kind != "commercial":
                asset = choose_one("commercial")
            if not asset:
                break
            entry = self.build_commercial_entry(asset, channel_name, pod_label, parent_context=parent_context)
            if ad_seconds_budget is not None:
                budget_left = float(ad_seconds_budget) - sum(float(item.get("duration", 0) or 0) for item in pod_entries)
                if budget_left <= 0:
                    break
                if float(entry.get("duration", 0) or 0) > budget_left and pod_entries:
                    break
            pod_entries.append(entry)

        if profile.get("allow_station_ids") and rng.random() < 0.16:
            station_id = choose_one("station_id")
            if station_id:
                pod_entries.append(self.build_commercial_entry(station_id, channel_name, pod_label, parent_context=parent_context))

        return [entry for entry in pod_entries if float(entry.get("duration", 0) or 0) > 0]

    def analyze_smart_break_candidates(self, path, allow_probe=True):
        signature = file_cache_signature(path)
        cached = (self.smart_break_cache_state.get("entries") or {}).get(path, {})
        if cached.get("signature") == signature and isinstance(cached.get("candidates"), list):
            return cached.get("candidates", [])
        if not allow_probe:
            return []
        candidates = detect_smart_break_candidates_for_path(path)
        self.smart_break_cache_state.setdefault("entries", {})[path] = {
            "signature": signature,
            "candidates": candidates,
        }
        save_json_file(SMART_BREAK_CACHE_FILE, self.smart_break_cache_state)
        return candidates

    def choose_breakpoints_for_program(
        self,
        channel_name,
        path,
        duration,
        profile,
        allow_smart_break_scan=True,
        defer_midroll_if_no_cached_breaks=False,
    ):
        if duration <= 0 or not profile.get("enabled"):
            return []
        mode = profile.get("mode", "between_episodes_only")
        if mode == "between_episodes_only":
            return []

        breakpoints = []
        interval = max(60, int(profile.get("target_break_interval_minutes", 7) or 7) * 60)
        minimum_first = max(0, int(profile.get("minimum_content_before_first_break_seconds", 90) or 90))
        minimum_spacing = max(60, int(profile.get("min_seconds_between_breaks", 330) or 330))
        jitter = max(0, int(profile.get("break_jitter_seconds", 45) or 45))
        rng = random.Random(stable_hash(f"{channel_name}|{path}|breakpoints|{commercial_profile_signature(profile)}"))
        target = minimum_first + interval
        candidates = (
            self.analyze_smart_break_candidates(path, allow_probe=allow_smart_break_scan)
            if profile.get("smart_breaks") and mode in {"natural_breaks", "hybrid"}
            else []
        )
        if defer_midroll_if_no_cached_breaks and not candidates and not allow_smart_break_scan:
            return []
        while target < max(0, duration - 90):
            chosen = None
            if candidates:
                nearby = [
                    point for point in candidates
                    if abs(point - target) <= max(90, interval // 2)
                    and point >= minimum_first
                    and (not breakpoints or (point - breakpoints[-1]) >= minimum_spacing)
                    and point < duration - 45
                ]
                if nearby:
                    chosen = min(nearby, key=lambda point: abs(point - target))
            if chosen is None and mode in {"timed_breaks", "hybrid"}:
                if not (profile.get("smart_breaks") and profile.get("skip_midroll_if_no_smart_breaks") and mode == "hybrid"):
                    chosen = float(max(minimum_first, min(duration - 45, target + rng.randint(-jitter, jitter))))
                    if breakpoints and (chosen - breakpoints[-1]) < minimum_spacing:
                        chosen = float(breakpoints[-1] + minimum_spacing)
            if chosen is None:
                target += interval
                continue
            if chosen >= duration - 45:
                break
            breakpoints.append(float(chosen))
            target = chosen + interval
        return breakpoints

    def build_channel_schedule_entries(
        self,
        root_path,
        channel,
        progress_callback=None,
        progress_index=0,
        progress_total=1,
        channel_position=1,
        channel_total=1,
        allow_smart_break_scan=True,
        defer_midroll_if_no_cached_breaks=False,
    ):
        base_schedule = generate_auto_schedule(root_path, channel.name, channel.shows)
        lineup = list(base_schedule.get("lineup", channel.shows))
        anchor = base_schedule.get("anchor_time", GLOBAL_START)
        profile = self.resolve_channel_commercial_profile(channel.name)
        if not profile.get("enabled") or not self.load_or_refresh_commercial_library(force_rescan=False):
            return {
                "mode": "auto",
                "anchor_time": anchor,
                "entries": list(lineup),
            }

        entries = []
        for item_index, path in enumerate(lineup):
            if progress_callback:
                stage_name = (
                    "Analyzing smart breaks"
                    if allow_smart_break_scan and profile.get("smart_breaks") and profile.get("mode") in {"natural_breaks", "hybrid"}
                    else "Planning channel commercials"
                )
                progress_callback(
                    progress_index + item_index,
                    progress_total,
                    stage_name,
                    (
                        f"{channel.name}  •  {os.path.basename(path)}"
                        f"  •  Channel {channel_position}/{channel_total}"
                        f"  •  Show {item_index + 1}/{max(1, len(lineup))}"
                    ),
                )
            duration = float(self.duration_cache.get(path, 0) or 0)
            if duration <= 0:
                if progress_callback:
                    progress_callback(
                        progress_index + item_index + 1,
                        progress_total,
                        "Planning channel commercials",
                        f"{channel.name}  •  Skipping unreadable file {os.path.basename(path)}",
                    )
                continue
            metadata = self.get_program_metadata_local(path)
            detail_title = metadata.get("detail_title") or format_program_title(path)
            parent_context = {
                "path": path,
                "title": detail_title,
                "show_name": metadata.get("show_name", detail_title),
                "summary": metadata.get("detail_summary", ""),
                "slot_title": detail_title,
            }
            content_budget = max(30.0, (float(profile.get("max_ad_seconds_per_half_hour", 240) or 240) * max(1.0, duration / 1800.0)))
            spent_ad_seconds = 0.0

            if item_index == 0 and profile.get("pre_roll_enabled"):
                pod = self.compose_commercial_pod(channel.name, profile, path, f"preroll:{item_index}", pod_label="Pre-Show", parent_context=parent_context)
                spent_ad_seconds += sum(float(entry.get("duration", 0) or 0) for entry in pod)
                entries.extend(pod)

            breakpoints = self.choose_breakpoints_for_program(
                channel.name,
                path,
                duration,
                profile,
                allow_smart_break_scan=allow_smart_break_scan,
                defer_midroll_if_no_cached_breaks=defer_midroll_if_no_cached_breaks,
            )
            cursor = 0.0
            for break_index, breakpoint in enumerate(breakpoints):
                segment_duration = max(0.1, float(breakpoint) - cursor)
                if segment_duration > 0:
                    entries.append(
                        {
                            "kind": "content",
                            "path": path,
                            "title": detail_title,
                            "display_title": detail_title,
                            "duration": segment_duration,
                            "start_offset": cursor,
                            "end_offset": float(breakpoint),
                            "summary": metadata.get("detail_summary", ""),
                        }
                    )
                budget_left = max(0.0, content_budget - spent_ad_seconds)
                pod = self.compose_commercial_pod(
                    channel.name,
                    profile,
                    path,
                    f"midroll:{item_index}:{break_index}",
                    pod_label="Commercial Break",
                    ad_seconds_budget=budget_left,
                    parent_context=parent_context,
                )
                spent_ad_seconds += sum(float(entry.get("duration", 0) or 0) for entry in pod)
                entries.extend(pod)
                cursor = float(breakpoint)

            tail_duration = max(0.1, duration - cursor)
            entries.append(
                {
                    "kind": "content",
                    "path": path,
                    "title": detail_title,
                    "display_title": detail_title,
                    "duration": tail_duration,
                    "start_offset": cursor,
                    "end_offset": duration,
                    "summary": metadata.get("detail_summary", ""),
                }
            )

            between_allowed = item_index < len(lineup) - 1 or profile.get("post_roll_enabled")
            if between_allowed:
                budget_left = max(0.0, content_budget - spent_ad_seconds)
                pod = self.compose_commercial_pod(
                    channel.name,
                    profile,
                    path,
                    f"between:{item_index}",
                    pod_label="Between Shows",
                    ad_seconds_budget=budget_left,
                    parent_context=parent_context,
                )
                entries.extend(pod)

            if progress_callback:
                progress_callback(
                    progress_index + item_index + 1,
                    progress_total,
                    "Planning channel commercials",
                    (
                        f"{channel.name}  •  Prepared {os.path.basename(path)}"
                        f"  •  Channel {channel_position}/{channel_total}"
                        f"  •  Show {item_index + 1}/{max(1, len(lineup))}"
                    ),
                )

        if not entries:
            entries = list(lineup)
        return {
            "mode": "auto-commercials",
            "anchor_time": anchor,
            "entries": entries,
        }

    def smart_break_signature_for_channel(self, channel, profile):
        if not channel or not profile.get("enabled") or not profile.get("smart_breaks") or profile.get("mode") not in {"natural_breaks", "hybrid"}:
            return ""
        entries = []
        cache_entries = (self.smart_break_cache_state.get("entries") or {})
        for path in sorted(channel.shows):
            signature = file_cache_signature(path)
            cached = cache_entries.get(path, {})
            if cached.get("signature") == signature:
                entries.append(
                    {
                        "path": path,
                        "candidate_count": len(cached.get("candidates", []) or []),
                        "signature": signature,
                    }
                )
        return stable_hash(json.dumps(entries, sort_keys=True))

    def apply_channel_schedules(
        self,
        root_path,
        allow_smart_break_scan=False,
        target_channel_names=None,
        apply_to_current_channel=True,
        defer_midroll_if_no_cached_breaks=False,
    ):
        catalog_key = stable_hash(root_path)
        catalogs = self.schedule_state.setdefault("catalogs", {})
        catalog_state = catalogs.setdefault(catalog_key, {"root_path": root_path, "channels": {}})
        channels_state = catalog_state.setdefault("channels", {})
        changed = False
        commercial_signature = commercials_config_signature(self.commercial_settings())
        commercial_root_signature = build_commercial_root_signature(self.commercial_settings().get("root_folder", ""))
        current_channel_obj = self.channels[self.current_channel] if self.channels and 0 <= self.current_channel < len(self.channels) else None
        target_names = set(target_channel_names or [])
        media_channels = [
            channel for channel in self.channels
            if getattr(channel, "channel_type", "media") == "media"
            and (not target_names or channel.name in target_names)
        ]
        rebuild_plan = []
        cached_count = 0

        for channel in media_channels:
            profile = self.resolve_channel_commercial_profile(channel.name)
            signature = stable_hash(
                json.dumps(
                    {
                        "channel": channel.name,
                        "files": sorted(channel.shows),
                        "commercials": commercial_signature,
                        "commercial_root": commercial_root_signature,
                        "smart_breaks": self.smart_break_signature_for_channel(channel, profile),
                    },
                    sort_keys=True,
                )
            )
            state = channels_state.get(channel.name)
            needs_rebuild = (
                not state
                or state.get("signature") != signature
                or not str(state.get("mode", "")).startswith("auto")
                or not state.get("entries")
            )
            if needs_rebuild:
                rebuild_plan.append((channel, signature, profile))
            else:
                cached_count += 1
                if apply_to_current_channel or channel != current_channel_obj:
                    channel.set_schedule(state.get("entries", channel.shows), state.get("anchor_time", GLOBAL_START))

        total_programs_to_rebuild = max(1, sum(max(1, len(channel.shows)) for channel, _, _ in rebuild_plan))
        if self.loading_card.isVisible():
            if rebuild_plan:
                self.update_catalog_progress(
                    0,
                    total_programs_to_rebuild,
                    "Planning channel commercials",
                    f"Using cached schedules for {cached_count} channels. Rebuilding {len(rebuild_plan)} channel schedule(s).",
                )
            elif media_channels:
                self.update_catalog_progress(
                    1,
                    1,
                    "Commercial schedules ready from cache",
                    f"Using cached commercial timing for all {len(media_channels)} media channels.",
                )

        progress_index = 0
        for channel_position, (channel, signature, profile) in enumerate(rebuild_plan, start=1):
            state = channels_state.get(channel.name)
            if (
                not state
                or state.get("signature") != signature
                or not str(state.get("mode", "")).startswith("auto")
                or not state.get("entries")
            ):
                schedule = self.build_channel_schedule_entries(
                    root_path,
                    channel,
                    progress_callback=self.update_catalog_progress if self.loading_card.isVisible() else None,
                    progress_index=progress_index,
                    progress_total=total_programs_to_rebuild,
                    channel_position=channel_position,
                    channel_total=max(1, len(rebuild_plan)),
                    allow_smart_break_scan=allow_smart_break_scan,
                    defer_midroll_if_no_cached_breaks=defer_midroll_if_no_cached_breaks,
                )
                state = {
                    "signature": signature,
                    "mode": schedule["mode"],
                    "anchor_time": schedule["anchor_time"],
                    "entries": schedule["entries"],
                }
                channels_state[channel.name] = state
                changed = True
            if apply_to_current_channel or channel != current_channel_obj:
                channel.set_schedule(state.get("entries", channel.shows), state.get("anchor_time", GLOBAL_START))
            progress_index += max(1, len(channel.shows))

        if not target_names:
            stale_names = [name for name in channels_state.keys() if name not in {channel.name for channel in self.channels}]
            for name in stale_names:
                channels_state.pop(name, None)
                changed = True

        if changed:
            save_json_file(SCHEDULE_STATE_FILE, self.schedule_state)
        if self.loading_card.isVisible() and rebuild_plan:
            self.update_catalog_progress(
                total_programs_to_rebuild,
                total_programs_to_rebuild,
                "Commercial schedule cache ready",
                f"Cached commercial timing for {len(rebuild_plan)} rebuilt channel schedule(s).",
            )

    def stop_background_commercial_warmup(self):
        self.commercial_warm_generation += 1
        self.commercial_warm_timer.stop()
        self.commercial_warm_queue = []
        self.commercial_warm_path_channels = {}
        self.commercial_warm_inflight = None
        self.commercial_warm_dirty_channels = set()
        self.commercial_warm_completed_since_refresh = 0

    def queue_background_commercial_warmup(self, root_path):
        self.stop_background_commercial_warmup()
        if not root_path or not self.channels or not self.commercials_ready():
            return
        cache_entries = self.smart_break_cache_state.get("entries", {}) or {}
        path_channels = defaultdict(set)
        queue = []
        for channel in self.channels:
            if getattr(channel, "channel_type", "media") != "media":
                continue
            profile = self.resolve_channel_commercial_profile(channel.name)
            if not profile.get("enabled") or not profile.get("smart_breaks") or profile.get("mode") not in {"natural_breaks", "hybrid"}:
                continue
            for path in channel.shows:
                signature = file_cache_signature(path)
                cached = cache_entries.get(path, {})
                path_channels[path].add(channel.name)
                if cached.get("signature") == signature and isinstance(cached.get("candidates"), list):
                    continue
                queue.append(path)
        deduped = []
        seen = set()
        for path in queue:
            if path in seen:
                continue
            seen.add(path)
            deduped.append(path)
        self.commercial_warm_queue = deduped
        self.commercial_warm_path_channels = {path: sorted(list(names)) for path, names in path_channels.items()}
        if self.commercial_warm_queue:
            self.commercial_warm_timer.start()

    def can_run_background_commercial_warmup(self):
        if self.loading_card.isVisible() or self.channel_switch_timer.isActive():
            return False
        if self.video_window.on_demand_overlay.isVisible() or self.video_window.guide_overlay.isVisible() or self.video_window.info_overlay.isVisible():
            return False
        if self.video_window.on_demand_overlay.settings_open or self.video_window.guide_overlay.settings_open or self.video_window.info_overlay.settings_open:
            return False
        if self.playback_mode != "live":
            return False
        current_channel = self.channels[self.current_channel] if self.channels and 0 <= self.current_channel < len(self.channels) else None
        if not current_channel or getattr(current_channel, "channel_type", "media") != "media":
            return False
        return self.media_player.playbackState() == QMediaPlayer.PlayingState

    def process_background_commercial_warmup(self):
        if self.commercial_warm_inflight or not self.commercial_warm_queue:
            if not self.commercial_warm_queue:
                self.commercial_warm_timer.stop()
            return
        if not self.can_run_background_commercial_warmup():
            return
        path = self.commercial_warm_queue.pop(0)
        self.commercial_warm_inflight = path
        generation = self.commercial_warm_generation
        signature = file_cache_signature(path)

        def worker():
            candidates = detect_smart_break_candidates_for_path(path)
            self.commercialWarmScanFinished.emit(generation, path, signature, candidates)

        self.commercial_warm_thread = threading.Thread(target=worker, daemon=True)
        self.commercial_warm_thread.start()

    @Slot(int, str, str, list)
    def on_background_commercial_warm_scan_finished(self, generation, path, signature, candidates):
        if generation != self.commercial_warm_generation:
            return
        self.commercial_warm_inflight = None
        self.commercial_warm_thread = None
        self.smart_break_cache_state.setdefault("entries", {})[path] = {
            "signature": signature,
            "candidates": list(candidates or []),
        }
        save_json_file(SMART_BREAK_CACHE_FILE, self.smart_break_cache_state)
        for channel_name in self.commercial_warm_path_channels.get(path, []):
            self.commercial_warm_dirty_channels.add(channel_name)
        self.commercial_warm_completed_since_refresh += 1
        if self.commercial_warm_dirty_channels and (
            self.commercial_warm_completed_since_refresh >= 3 or not self.commercial_warm_queue
        ):
            target_names = sorted(self.commercial_warm_dirty_channels)
            self.apply_channel_schedules(
                self.catalog_root or self.app_settings.get("catalog_path", ""),
                allow_smart_break_scan=False,
                target_channel_names=target_names,
                apply_to_current_channel=False,
                defer_midroll_if_no_cached_breaks=False,
            )
            self.commercial_warm_dirty_channels.clear()
            self.commercial_warm_completed_since_refresh = 0
            if self.video_window.guide_overlay.isVisible():
                self.refresh_guide()
        if not self.commercial_warm_queue:
            self.commercial_warm_timer.stop()

    def metadata_enrichment_enabled(self):
        return bool(self.app_settings.get("experimental_remote_metadata", False)) and REMOTE_METADATA_EXPERIMENTAL

    def metadata_cache_mode(self):
        return "local-assets-v2"

    def describe_metadata_attention(self, reason, local_title):
        reason_key = (reason or "").strip().lower()
        if reason_key == "ambiguous":
            return f"MediaWave found more than one close match for {local_title}, so it left the local title untouched."
        if reason_key == "no-match":
            return f"MediaWave could not find a safe metadata match for {local_title} yet."
        if reason_key == "episode-missing":
            return f"MediaWave matched the show for {local_title}, but could not safely identify the exact episode."
        if reason_key == "service-unavailable":
            return f"Metadata enrichment was temporarily unavailable while scanning {local_title}."
        return f"MediaWave kept the local naming for {local_title} to avoid applying the wrong metadata."

    def metadata_override_for(self, path, local):
        shows = self.tmdb_overrides.get("shows", {})
        lookup_key = metadata_lookup_key(path, local)
        return (
            shows.get(lookup_key)
            or shows.get(local.get("match_key", ""))
            or {}
        )

    def metadata_review_entry_for(self, path, local):
        shows = self.tmdb_review.get("shows", {})
        lookup_key = metadata_lookup_key(path, local)
        return (
            shows.get(lookup_key)
            or shows.get(local.get("match_key", ""))
            or {}
        )

    def build_metadata_candidate_label(self, candidate):
        name = candidate.get("name") or "Unknown Title"
        source = (candidate.get("source") or "").upper()
        year = (candidate.get("year") or "").strip()
        confidence = candidate.get("confidence")
        extras = []
        if source:
            extras.append(source)
        if year:
            extras.append(year)
        if confidence is not None:
            extras.append(f"{int(round(float(confidence) * 100))}%")
        return f"{name}  •  {'  •  '.join(extras)}" if extras else name

    def score_anilist_candidate(self, local_title, item):
        local_norm = normalize_title(local_title)
        title_options = [
            normalize_title((item.get("title") or {}).get(key, ""))
            for key in ("english", "userPreferred", "romaji", "native")
        ]
        title_options = [title for title in title_options if title]
        if not title_options:
            return 0.0
        ratio = max(SequenceMatcher(None, local_norm, option).ratio() for option in title_options)
        exact = 1.0 if local_norm in title_options else 0.0
        prefix_bonus = 0.05 if any(option.startswith(local_norm) or local_norm.startswith(option) for option in title_options if local_norm) else 0.0
        format_bonus = 0.04 if (item.get("format") or "").upper() in {"TV", "TV_SHORT"} else 0.0
        return min(1.0, max(ratio, (ratio * 0.85) + exact + prefix_bonus + format_bonus))

    def choose_anilist_match(self, local_title, results):
        scored = []
        for item in results or []:
            media_id = item.get("id")
            name = anilist_display_title(item)
            if not media_id or not name:
                continue
            confidence = self.score_anilist_candidate(local_title, item)
            scored.append((confidence, item))
        if not scored:
            return None, "no-match", []
        scored.sort(key=lambda entry: entry[0], reverse=True)
        best_confidence, best = scored[0]
        second_confidence = scored[1][0] if len(scored) > 1 else 0.0
        accepted = (
            best_confidence >= 0.985
            or (best_confidence >= 0.955 and (best_confidence - second_confidence) >= 0.05)
            or (best_confidence >= 0.92 and (best_confidence - second_confidence) >= 0.11)
        )
        if not accepted:
            reason = "ambiguous" if best_confidence >= 0.84 else "no-match"
            return None, reason, scored[:5]
        return best, None, scored[:5]

    def build_tvmaze_candidates(self, local_title):
        if not self.metadata_enrichment_enabled() or self.tvmaze_client is None:
            return []
        results = self.tvmaze_client.search_shows(local_title)
        candidates = []
        for confidence, result in sorted(
            [(self.score_tvmaze_candidate(local_title, result), result) for result in results or []],
            key=lambda entry: entry[0],
            reverse=True,
        )[:6]:
            show = result.get("show", {}) if isinstance(result, dict) else {}
            name = (show.get("name") or "").strip()
            show_id = show.get("id")
            if not name or not show_id:
                continue
            premiered = (show.get("premiered") or "").strip()
            year = extract_year_value(premiered)
            candidate = {
                "source": "tvmaze",
                "id": show_id,
                "name": name,
                "media_type": "tv",
                "year": year,
                "confidence": round(confidence, 3),
            }
            candidate["label"] = self.build_metadata_candidate_label(candidate)
            candidates.append(candidate)
        return candidates

    def build_anilist_candidates(self, local_title):
        if not self.metadata_enrichment_enabled() or self.anilist_client is None:
            return []
        results = self.anilist_client.search_anime(local_title)
        candidates = []
        for confidence, item in sorted(
            [(self.score_anilist_candidate(local_title, item), item) for item in results or []],
            key=lambda entry: entry[0],
            reverse=True,
        )[:6]:
            name = anilist_display_title(item)
            media_id = item.get("id")
            if not name or not media_id:
                continue
            year = str((((item.get("startDate") or {}).get("year")) or "")).strip()
            candidate = {
                "source": "anilist",
                "id": media_id,
                "name": name,
                "media_type": "tv",
                "year": year,
                "confidence": round(confidence, 3),
            }
            candidate["label"] = self.build_metadata_candidate_label(candidate)
            candidates.append(candidate)
        return candidates

    def build_tmdb_movie_candidates(self, local_title):
        if not self.metadata_enrichment_enabled() or self.tmdb_client is None or not self.tmdb_client.enabled:
            return []
        response = self.tmdb_client.search_movie(local_title)
        results = (response or {}).get("results", [])[:6]
        candidates = []
        for item in results:
            movie_id = item.get("id")
            title = (item.get("title") or "").strip()
            if not movie_id or not title:
                continue
            confidence = SequenceMatcher(None, normalize_title(local_title), normalize_title(title)).ratio()
            candidate = {
                "source": "tmdb",
                "id": movie_id,
                "name": title,
                "media_type": "movie",
                "year": extract_year_value(item.get("release_date", "")),
                "confidence": round(confidence, 3),
            }
            candidate["label"] = self.build_metadata_candidate_label(candidate)
            candidates.append(candidate)
        return candidates

    def build_metadata_review_entries(self):
        grouped = {}
        episodic_movie_counts = defaultdict(int)
        for channel in self.channels:
            if getattr(channel, "channel_type", "media") != "media":
                continue
            for path in channel.shows:
                local = parse_local_media(path)
                if local.get("media_type") != "movie":
                    continue
                match_key = local.get("match_key", "")
                if match_key and local.get("show_name"):
                    episodic_movie_counts[(channel.name, match_key)] += 1
        for channel in self.channels:
            if getattr(channel, "channel_type", "media") != "media":
                continue
            for path in channel.shows:
                local = parse_local_media(path)
                lookup_key = metadata_lookup_key(path, local)
                match_key = local.get("match_key", "")
                grouped_movie_like = (
                    local.get("media_type") == "movie"
                    and match_key
                    and episodic_movie_counts.get((channel.name, match_key), 0) > 1
                )
                review_group_key = f"group::{channel.name}::{match_key}" if grouped_movie_like else lookup_key
                override_key = match_key if grouped_movie_like else lookup_key
                entry = grouped.setdefault(
                    review_group_key,
                    {
                        "lookup_key": review_group_key,
                        "override_key": override_key,
                        "path": path,
                        "channel_label": channel.name,
                        "local_title": (
                            local.get("show_name")
                            if local.get("media_type") == "tv" or grouped_movie_like
                            else format_program_title(path)
                        ),
                        "media_type": "tv" if grouped_movie_like else local.get("media_type", "tv"),
                        "item_count": 0,
                        "preferred_source": "auto" if local.get("media_type") == "tv" or grouped_movie_like else "tmdb",
                        "search_query": (
                            local.get("show_name")
                            if local.get("media_type") == "tv" or grouped_movie_like
                            else format_program_title(path)
                        ),
                    },
                )
                entry["item_count"] += 1
        entries = []
        for entry in grouped.values():
            path = entry["path"]
            local = parse_local_media(path)
            metadata = self.tmdb_cache.get(path) or {
                "metadata_status": "local",
                "needs_attention": False,
                "attention_reason": "",
                "show_name": local.get("show_name"),
            }
            review = self.metadata_review_entry_for(path, local)
            override = self.metadata_override_for(path, local)
            effective_media_type = override.get("media_type") or entry.get("media_type", "tv")
            entry["media_type"] = effective_media_type
            entry["forced_media_type"] = override.get("media_type") if override.get("media_type") in {"tv", "movie"} else "auto"
            status_label = "Matched"
            if override.get("source") == "local":
                status_label = "Keep Local"
            elif override:
                status_label = "Manually Matched"
            elif metadata.get("needs_attention"):
                status_label = "Needs Attention"
            elif metadata.get("metadata_status") != "matched":
                status_label = "Local Only"
            current_match_text = "Using local titles"
            if override.get("source") == "local":
                current_match_text = "Manual override: keep local titles"
            elif override:
                current_match_text = f"Manual override: {override.get('title') or entry['local_title']}"
            elif metadata.get("show_name") and metadata.get("show_name") != local.get("show_name"):
                current_match_text = f"Automatic match: {metadata.get('show_name')}"
            elif metadata.get("metadata_status") == "matched":
                current_match_text = f"Automatic match: {metadata.get('show_name', entry['local_title'])}"
            reason_text = (
                metadata.get("attention_reason")
                or review.get("reason_text")
                or (
                    "MediaWave is already comfortable with this match, but you can still override it if you want something more specific."
                    if metadata.get("metadata_status") == "matched"
                    else "MediaWave is currently using your local naming for this title."
                )
            )
            candidates = []
            for candidate in review.get("candidates", []):
                candidate_copy = dict(candidate)
                candidate_copy["label"] = candidate_copy.get("label") or self.build_metadata_candidate_label(candidate_copy)
                candidates.append(candidate_copy)
            entry["meta_line"] = (
                f"{entry['channel_label']}  •  TV Show  •  {entry['item_count']} episode{'s' if entry['item_count'] != 1 else ''}"
                if effective_media_type == "tv"
                else f"{entry['channel_label']}  •  Movie"
            )
            entry["reason_text"] = reason_text
            entry["current_match_text"] = current_match_text
            entry["status_label"] = status_label
            entry["candidates"] = candidates
            entries.append(entry)
        entries.sort(key=lambda entry: (0 if entry["status_label"] in {"Needs Attention", "Local Only"} else 1, entry["local_title"].casefold()))
        return entries

    def fetch_metadata_review_candidates(self, entry, provider="auto", query=None, forced_media_type="auto"):
        if not self.metadata_enrichment_enabled():
            return []
        if not entry:
            return []
        local_title = (query or entry.get("local_title", "")).strip()
        provider = provider or "auto"
        forced_media_type = forced_media_type or "auto"
        candidates = []
        if provider == "auto":
            allow_tv = forced_media_type in ("auto", "tv")
            allow_movie = forced_media_type in ("auto", "movie")
        else:
            allow_tv = True
            allow_movie = True
        if allow_tv and provider in ("auto", "tvmaze"):
            candidates.extend(self.build_tvmaze_candidates(local_title))
        if allow_tv and provider in ("auto", "anilist"):
            existing_ids = {(item["source"], item["id"]) for item in candidates}
            for candidate in self.build_anilist_candidates(local_title):
                key = (candidate["source"], candidate["id"])
                if key not in existing_ids:
                    candidates.append(candidate)
        if allow_movie and provider in ("auto", "tmdb"):
            existing_ids = {(item["source"], item["id"]) for item in candidates}
            for candidate in self.build_tmdb_movie_candidates(local_title):
                key = (candidate["source"], candidate["id"])
                if key not in existing_ids:
                    candidates.append(candidate)
        candidates.sort(key=lambda item: float(item.get("confidence", 0.0)), reverse=True)
        reason = "manual-review"
        review_key = entry.get("override_key") or entry["lookup_key"]
        self.tmdb_review.setdefault("shows", {})[review_key] = {
            "title": local_title,
            "media_type": forced_media_type if forced_media_type in {"tv", "movie"} else entry.get("media_type", "tv"),
            "reason": reason,
            "candidates": candidates,
        }
        save_json_file(TMDB_REVIEW_FILE, self.tmdb_review)
        return candidates

    def refresh_metadata_for_lookup_keys(self, lookup_keys, progress_callback=None):
        if not lookup_keys:
            return 0
        affected_items = []
        lookup_key_set = set(lookup_keys)
        for channel in self.channels:
            if getattr(channel, "channel_type", "media") != "media":
                continue
            for path in channel.shows:
                local = parse_local_media(path)
                if metadata_lookup_key(path, local) in lookup_key_set or local.get("match_key", "") in lookup_key_set:
                    affected_items.append((path, local))
        total_items = len(affected_items)
        if not total_items:
            return 0

        updated = 0
        for index, (path, local) in enumerate(affected_items, start=1):
            override = self.metadata_override_for(path, local)
            if progress_callback:
                progress_callback(
                    index - 1,
                    total_items,
                    "Applying metadata matches",
                    f"{local.get('show_name') or format_program_title(path)}\n{os.path.basename(path)}",
                )
            self.tmdb_cache.pop(path, None)
            self.tmdb_cache[path] = self.resolve_program_metadata(
                path,
                allow_remote=self.metadata_enrichment_enabled() or bool(override),
            )
            updated += 1
            if progress_callback:
                progress_callback(
                    index,
                    total_items,
                    "Applying metadata matches",
                    f"{local.get('show_name') or format_program_title(path)}\n{os.path.basename(path)}",
                )

        if updated:
            if progress_callback:
                progress_callback(total_items, total_items, "Saving metadata cache", "Writing MediaWave metadata files...")
            save_json_file(TMDB_CACHE_FILE, self.tmdb_cache)
            save_json_file(TMDB_REVIEW_FILE, self.tmdb_review)
            save_json_file(TMDB_OVERRIDES_FILE, self.tmdb_overrides)
            if progress_callback:
                progress_callback(total_items, total_items, "Refreshing the Vault library", "Updating MediaWave Vault with your latest match decisions...")
            if self.video_window.on_demand_overlay.isVisible():
                self.build_on_demand_catalog(use_remote=False)
            else:
                self.mark_on_demand_catalog_dirty(clear_catalog=True)
            if progress_callback:
                progress_callback(total_items, total_items, "Refreshing the interface", "Updating guide, vault, and playback overlays...")
            self.refresh_controls()
            if self.video_window.guide_overlay.isVisible():
                self.refresh_guide()
            if self.video_window.on_demand_overlay.isVisible():
                self.refresh_on_demand()
            if self.video_window.info_overlay.isVisible():
                self.refresh_info_banner()
        return updated

    def open_metadata_review(self):
        if not self.metadata_enrichment_enabled():
            self.status.setText(
                "Remote metadata review is disabled. MediaWave now uses local artwork files, local descriptions, and folder/file names by default."
            )
            return
        if not self.channels:
            self.status.setText("Load a catalog first, then review local artwork and description files from your media folders.")
            return
        self.status.setText("Preparing the library match review...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            entries = self.build_metadata_review_entries()
            if not entries:
                self.status.setText("MediaWave could not find any shows or movies to review yet.")
                return
            dialog = MetadataReviewDialog(entries, self.fetch_metadata_review_candidates, self.tmdb_overrides, self)
            if dialog.exec() != QDialog.Accepted:
                self.status.setText("Library match review closed.")
                return
            self.tmdb_overrides = dialog.result_overrides
            save_json_file(TMDB_OVERRIDES_FILE, self.tmdb_overrides)
            if dialog.modified_keys:
                self.begin_library_match_progress(len(dialog.modified_keys))
            updated = self.refresh_metadata_for_lookup_keys(
                dialog.modified_keys,
                progress_callback=self.update_library_match_progress if dialog.modified_keys else None,
            )
            if dialog.modified_keys:
                self.finish_library_match_progress()
            if dialog.modified_keys:
                self.status.setText(
                    f"Saved {len(dialog.modified_keys)} metadata review decision{'s' if len(dialog.modified_keys) != 1 else ''}. "
                    f"MediaWave refreshed {updated} item{'s' if updated != 1 else ''} with your new matches."
                )
        except Exception as exc:
            self.finish_library_match_progress()
            self.status.setText(f"Could not open library match review: {exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def score_tvmaze_candidate(self, local_title, result):
        show = result.get("show", {}) if isinstance(result, dict) else {}
        candidate_name = show.get("name", "")
        local_norm = normalize_title(local_title)
        candidate_norm = normalize_title(candidate_name)
        ratio = SequenceMatcher(None, local_norm, candidate_norm).ratio()
        search_score = float(result.get("score", 0.0) or 0.0)
        exact = 1.0 if local_norm == candidate_norm and local_norm else 0.0
        prefix_bonus = 0.06 if local_norm and (candidate_norm.startswith(local_norm) or local_norm.startswith(candidate_norm)) else 0.0
        confidence = min(1.0, max(ratio, (ratio * 0.76) + (min(search_score, 1.0) * 0.24) + exact + prefix_bonus))
        return confidence

    def choose_tvmaze_match(self, local_title, results):
        scored = []
        for result in results or []:
            show = result.get("show", {}) if isinstance(result, dict) else {}
            show_id = show.get("id")
            if not show_id or not show.get("name"):
                continue
            confidence = self.score_tvmaze_candidate(local_title, result)
            scored.append((confidence, result))
        if not scored:
            return None, "no-match", []
        scored.sort(key=lambda item: item[0], reverse=True)
        best_confidence, best = scored[0]
        second_confidence = scored[1][0] if len(scored) > 1 else 0.0
        accepted = (
            best_confidence >= 0.975
            or (best_confidence >= 0.94 and (best_confidence - second_confidence) >= 0.05)
            or (best_confidence >= 0.9 and (best_confidence - second_confidence) >= 0.12)
        )
        if not accepted:
            reason = "ambiguous" if best_confidence >= 0.82 else "no-match"
            return None, reason, scored[:5]
        return best, None, scored[:5]

    def enrich_tvmaze_tv(self, local, override=None, lookup_key=None):
        review_key = lookup_key or local["match_key"]
        if override and override.get("source") == "tvmaze" and override.get("tvmaze_id"):
            show_id = override.get("tvmaze_id")
            details = self.tvmaze_client.request_json(f"https://api.tvmaze.com/shows/{show_id}") or {}
            if not details:
                return None, "service-unavailable"
            best = {"show": details}
            scored = [(1.0, best)]
            reason = None
        else:
            search_results = self.tvmaze_client.search_shows(local["show_name"])
            best, reason, scored = self.choose_tvmaze_match(local["show_name"], search_results)
        review_entry = {
            "title": local["show_name"],
            "media_type": "tv",
            "reason": reason or "matched",
            "candidates": self.build_tvmaze_candidates(local["show_name"]),
        }
        self.tmdb_review.setdefault("shows", {})[review_key] = review_entry
        if not best:
            return None, reason or "no-match"

        show = best.get("show", {})
        show_id = show.get("id")
        show_name = show.get("name") or local["show_name"]
        show_summary = strip_html_summary(show.get("summary") or "") or local["detail_summary"]
        artwork_url = (show.get("image") or {}).get("original") or (show.get("image") or {}).get("medium") or ""
        artwork_path = cache_remote_artwork(artwork_url, f"tvmaze-show-{show_id}") if artwork_url else ""
        year_value = extract_year_value(show.get("premiered", ""))
        runtime = safe_int(show.get("averageRuntime") or show.get("runtime"))
        enriched = {
            "timeline_title": show_name,
            "detail_title": show_name,
            "detail_summary": show_summary,
            "show_name": show_name,
            "show_summary": show_summary,
            "artwork_path": artwork_path,
            "show_artwork_path": artwork_path,
            "year": year_value,
            "runtime_minutes": runtime,
            "tvmaze_id": show_id,
            "metadata_status": "matched",
            "needs_attention": False,
            "attention_reason": "",
            "review_candidates": review_entry["candidates"],
        }

        season = local.get("season_number")
        episode = local.get("episode_number")
        if season is None or episode is None:
            return enriched, None

        episodes = self.tvmaze_client.show_episodes(show_id)
        match = next(
            (
                item for item in episodes
                if safe_int(item.get("season")) == season and safe_int(item.get("number")) == episode
            ),
            None,
        )
        if not match:
            return enriched, "episode-missing"

        episode_title = match.get("name") or local.get("episode_title") or local["detail_title"]
        episode_summary = strip_html_summary(match.get("summary") or "") or local["detail_summary"]
        episode_runtime = safe_int(match.get("runtime")) or runtime
        season_count = len({safe_int(item.get("season")) for item in episodes if safe_int(item.get("season")) is not None})
        enriched.update(
            {
                "detail_title": f"{show_name} - S{season:02d}E{episode:02d} - {episode_title}",
                "detail_summary": episode_summary,
                "episode_title": episode_title,
                "episode_summary": episode_summary,
                "runtime_minutes": episode_runtime,
                "season_count": season_count or None,
                "episode_count": len([item for item in episodes if safe_int(item.get("number")) is not None]),
            }
        )
        return enriched, None

    def enrich_anilist_tv(self, local, override=None, lookup_key=None):
        review_key = lookup_key or local["match_key"]
        if override and override.get("source") == "anilist" and override.get("anilist_id"):
            details = self.anilist_client.media_details(override.get("anilist_id"))
            if not details:
                return None, "service-unavailable"
            best = details
            scored = [(1.0, best)]
            reason = None
        else:
            search_results = self.anilist_client.search_anime(local["show_name"])
            best, reason, scored = self.choose_anilist_match(local["show_name"], search_results)
        review_entry = self.tmdb_review.setdefault("shows", {}).setdefault(review_key, {
            "title": local["show_name"],
            "media_type": "tv",
            "reason": reason or "matched",
            "candidates": [],
        })
        review_entry["candidates"] = review_entry.get("candidates") or []
        existing = {(candidate.get("source"), candidate.get("id")) for candidate in review_entry["candidates"]}
        for candidate in self.build_anilist_candidates(local["show_name"]):
            key = (candidate.get("source"), candidate.get("id"))
            if key not in existing:
                review_entry["candidates"].append(candidate)
        if not best:
            return None, reason or "no-match"

        title = anilist_display_title(best) or local["show_name"]
        artwork_url = ((best.get("coverImage") or {}).get("extraLarge")
                       or (best.get("coverImage") or {}).get("large")
                       or (best.get("coverImage") or {}).get("medium")
                       or "")
        artwork_path = cache_remote_artwork(artwork_url, f"anilist-show-{best.get('id')}") if artwork_url else ""
        runtime = safe_int(best.get("duration"))
        year_value = str((((best.get("startDate") or {}).get("year")) or "")).strip()
        summary = strip_html_summary(best.get("description") or "") or local["detail_summary"]
        enriched = {
            "timeline_title": title,
            "detail_title": local["detail_title"],
            "detail_summary": local["detail_summary"],
            "show_name": title,
            "show_summary": summary,
            "artwork_path": artwork_path,
            "show_artwork_path": artwork_path,
            "year": year_value,
            "runtime_minutes": runtime,
            "anilist_id": best.get("id"),
            "metadata_status": "matched",
            "needs_attention": False,
            "attention_reason": "",
            "review_candidates": review_entry["candidates"],
        }
        if local.get("season_number") is not None and local.get("episode_number") is not None:
            episode_title = local.get("episode_title") or local["detail_title"]
            enriched.update(
                {
                    "detail_title": f"{title} - S{local['season_number']:02d}E{local['episode_number']:02d} - {episode_title}",
                    "episode_title": episode_title,
                    "episode_summary": local["detail_summary"],
                    "season_count": 1 if best.get("episodes") else None,
                    "episode_count": safe_int(best.get("episodes")),
                }
            )
        return enriched, None

    def queue_metadata_refresh(self):
        if not self.metadata_enrichment_enabled():
            return
        pending = self.collect_metadata_refresh_paths()
        self.metadata_queue = pending
        if self.metadata_queue:
            self.last_metadata_overlay_refresh_at = 0.0
            self.metadata_timer.start(45)

    def collect_metadata_refresh_paths(self):
        pending = []
        cache_mode = self.metadata_cache_mode()
        for channel in self.channels:
            if getattr(channel, "channel_type", "media") != "media":
                continue
            for path in channel.shows:
                local = parse_local_media(path)
                metadata = self.tmdb_cache.get(path)
                signature = local_asset_signature(path, local)
                if (
                    not metadata
                    or metadata.get("signature") != signature
                    or metadata.get("cache_mode") != cache_mode
                ):
                    pending.append(path)
        return pending

    def compute_on_demand_catalog_signature(self):
        media_channels = []
        for channel in self.channels:
            if getattr(channel, "channel_type", "media") != "media":
                continue
            shows = []
            for path in channel.shows:
                local = parse_local_media(path)
                shows.append(
                    {
                        "path": path,
                        "signature": local_asset_signature(path, local),
                    }
                )
            media_channels.append(
                {
                    "name": channel.name,
                    "root_path": os.path.realpath(getattr(channel, "root_path", "") or ""),
                    "shows": shows,
                }
            )
        payload = {
            "schema": 3,
            "grouping_mode": "channel-show-subsections-v1",
            "catalog_root": os.path.realpath(self.catalog_root or ""),
            "metadata_mode": self.metadata_cache_mode(),
            "media_channels": media_channels,
        }
        return stable_hash(json.dumps(payload, sort_keys=True))

    def save_on_demand_catalog_cache(self):
        signature = self.compute_on_demand_catalog_signature()
        self.on_demand_catalog_signature = signature
        self.on_demand_cache_state = {
            "signature": signature,
            "catalog": self.on_demand_catalog,
        }
        save_json_file(ON_DEMAND_CACHE_FILE, self.on_demand_cache_state)

    def restore_on_demand_catalog_cache(self):
        signature = self.compute_on_demand_catalog_signature()
        cached_signature = self.on_demand_cache_state.get("signature", "")
        cached_catalog = self.on_demand_cache_state.get("catalog", [])
        self.on_demand_catalog_signature = signature
        if cached_signature == signature and isinstance(cached_catalog, list) and cached_catalog:
            self.on_demand_catalog = cached_catalog
            self.on_demand_catalog_dirty = False
            return True
        return False

    def mark_on_demand_catalog_dirty(self, clear_catalog=False):
        self.on_demand_catalog_signature = self.compute_on_demand_catalog_signature()
        self.on_demand_catalog_dirty = True
        if clear_catalog:
            self.on_demand_catalog = []

    def prepare_on_demand_catalog(self, clear_catalog=False):
        if self.restore_on_demand_catalog_cache():
            return True
        self.mark_on_demand_catalog_dirty(clear_catalog=clear_catalog)
        return False

    def run_metadata_enrichment_with_progress(self, folder_label=""):
        if not self.metadata_enrichment_enabled():
            return
        pending = self.collect_metadata_refresh_paths()
        if not pending:
            return
        total = len(pending)
        self.loading_progress.setMaximum(total)
        self.loading_progress.setFormat("%v / %m titles")
        self.catalog_progress_started_at = time.time()
        for index, path in enumerate(pending, start=1):
            title = format_program_title(path)
            self.update_catalog_progress(
                index - 1,
                total,
                f"Refreshing local metadata {index} of {total}",
                title,
            )
            metadata = self.resolve_program_metadata(path, allow_remote=self.metadata_enrichment_enabled())
            self.tmdb_cache[path] = metadata
            if index % 8 == 0 or index == total:
                save_json_file(TMDB_CACHE_FILE, self.tmdb_cache)
                save_json_file(TMDB_REVIEW_FILE, self.tmdb_review)
        self.update_catalog_progress(total, total, "Finalizing metadata library", folder_label or "MediaWave Vault")
        save_json_file(TMDB_CACHE_FILE, self.tmdb_cache)
        save_json_file(TMDB_REVIEW_FILE, self.tmdb_review)
        self.update_catalog_progress(1, 1, "Deferring enriched on-demand library", "MediaWave Vault will refresh from the new metadata the next time you open it.")
        self.mark_on_demand_catalog_dirty(clear_catalog=True)

    def process_metadata_queue(self):
        if not self.metadata_queue:
            self.metadata_timer.stop()
            save_json_file(TMDB_CACHE_FILE, self.tmdb_cache)
            save_json_file(TMDB_REVIEW_FILE, self.tmdb_review)
            if self.channels:
                if self.video_window.on_demand_overlay.isVisible():
                    self.build_on_demand_catalog(use_remote=False)
                    self.refresh_on_demand()
                else:
                    self.mark_on_demand_catalog_dirty(clear_catalog=True)
            return

        path = self.metadata_queue.pop(0)
        metadata = self.resolve_program_metadata(path, allow_remote=self.metadata_enrichment_enabled())
        self.tmdb_cache[path] = metadata
        now = time.time()
        if not self.metadata_queue:
            self.metadata_timer.stop()
            save_json_file(TMDB_CACHE_FILE, self.tmdb_cache)
            save_json_file(TMDB_REVIEW_FILE, self.tmdb_review)
        should_refresh_overlay = (now - self.last_metadata_overlay_refresh_at) >= 0.22 or not self.metadata_queue
        if should_refresh_overlay:
            if self.channels:
                if self.video_window.on_demand_overlay.isVisible():
                    self.build_on_demand_catalog(use_remote=False)
                else:
                    self.mark_on_demand_catalog_dirty(clear_catalog=True)
            self.last_metadata_overlay_refresh_at = now
            if self.video_window.guide_overlay.isVisible():
                self.refresh_guide()
            if self.video_window.on_demand_overlay.isVisible():
                self.refresh_on_demand()

    def build_dummy_on_demand_catalog(self):
        summary = "This is only a test, this is not even real dude get a clue!"

        def episode(show_name, season, number):
            path = f"dummy://{normalize_title(show_name)}/s{season:02d}e{number:02d}"
            return {
                "path": path,
                "label": "Dummy Episode",
                "meta": f"S{season:02d}E{number:02d}",
                "summary": summary,
                "detail_title": f"Dummy Episode - S{season:02d}E{number:02d}",
                "show_name": show_name,
                "season_number": season,
                "season_label": f"Season {season}",
                "section_label": f"Season {season}",
                "episode_number": number,
                "media_type": "tv",
                "runtime_minutes": 22,
                "year": "2000",
                "artwork_path": "",
                "hero_artwork_path": "",
                "clearlogo_path": "",
                "metadata_status": "dummy",
                "needs_attention": False,
                "attention_reason": "",
                "added_at": time.time(),
            }

        def show_group(show_name, season_counts):
            items = []
            for season, count in season_counts:
                for number in range(1, count + 1):
                    items.append(episode(show_name, season, number))
            return {
                "label": show_name,
                "meta": f"{len(items)} dummy episodes",
                "summary": summary,
                "artwork_path": "",
                "hero_artwork_path": "",
                "clearlogo_path": "",
                "year": "2000",
                "media_type": "tv",
                "needs_attention": False,
                "attention_reason": "",
                "added_at": time.time(),
                "items": items,
            }

        def movie_group(title, index):
            path = f"dummy://movie/{normalize_title(title) or index}"
            item = {
                "path": path,
                "label": title,
                "meta": "Movie",
                "summary": summary,
                "detail_title": title,
                "show_name": title,
                "season_number": None,
                "season_label": "",
                "section_label": "",
                "episode_number": None,
                "media_type": "movie",
                "runtime_minutes": 88 + index,
                "year": "2000",
                "artwork_path": "",
                "hero_artwork_path": "",
                "clearlogo_path": "",
                "metadata_status": "dummy",
                "needs_attention": False,
                "attention_reason": "",
                "added_at": time.time(),
            }
            return {
                "label": title,
                "meta": "Dummy feature",
                "summary": summary,
                "artwork_path": "",
                "hero_artwork_path": "",
                "clearlogo_path": "",
                "year": "2000",
                "media_type": "movie",
                "needs_attention": False,
                "attention_reason": "",
                "added_at": time.time(),
                "items": [item],
            }

        return [
            {
                "number": 1,
                "label": "Dummy Vault",
                "meta": "4 dummy collections",
                "groups": [
                    show_group("Dummy Show", [(1, 28)]),
                    show_group("Dummy Show: Live", [(season, 12) for season in range(1, 5)]),
                    movie_group("Dummy Movie", 1),
                    movie_group("Dummy Movie 2: Electic Boogaloo", 2),
                ],
            }
        ]

    def build_on_demand_catalog(self, use_remote=False, progress_callback=None):
        catalog = []
        media_channels = [channel for channel in self.channels if getattr(channel, "channel_type", "media") == "media"]
        if not media_channels and self.app_settings.get("allow_dummy_vault_catalog", False):
            self.on_demand_catalog = self.build_dummy_on_demand_catalog()
            self.on_demand_catalog_dirty = False
            return
        total_media_channels = max(1, len(media_channels))
        for media_index, channel in enumerate(media_channels, start=1):
            if progress_callback:
                progress_callback(
                    media_index - 1,
                    total_media_channels,
                    "Organizing on-demand library",
                    f"{channel.name}  •  scanning titles",
                )
            groups = {}
            for path in channel.shows:
                metadata = self.get_program_metadata_local(path)
                hierarchy = infer_on_demand_structure(path, getattr(channel, "root_path", ""))
                media_type = metadata.get("media_type", "movie")
                group_name = hierarchy.get("group_label") or metadata.get("show_name") or metadata.get("timeline_title") or format_program_title(path)
                section_label = hierarchy.get("section_label") or metadata.get("season_label") or ""
                if hierarchy.get("group_label"):
                    group_key = f"group::{normalize_title(group_name)}"
                elif media_type == "tv":
                    group_key = f"tv::{normalize_title(group_name)}"
                else:
                    group_key = f"movie::{normalize_title(group_name)}"
                try:
                    added_at = float(os.path.getmtime(path))
                except OSError:
                    added_at = 0.0
                item = {
                    "path": path,
                    "label": metadata.get("episode_title") or metadata.get("detail_title") or format_program_title(path),
                    "meta": "",
                    "summary": metadata.get("episode_summary") or metadata.get("detail_summary") or "",
                    "detail_title": metadata.get("detail_title") or format_program_title(path),
                    "show_name": metadata.get("show_name") or group_name,
                    "season_number": metadata.get("season_number"),
                    "season_label": metadata.get("season_label") or "",
                    "section_label": section_label,
                    "episode_number": metadata.get("episode_number"),
                    "media_type": media_type,
                    "runtime_minutes": metadata.get("runtime_minutes"),
                    "year": metadata.get("year", ""),
                    "artwork_path": metadata.get("artwork_path") or metadata.get("show_artwork_path") or "",
                    "hero_artwork_path": metadata.get("hero_artwork_path") or metadata.get("show_artwork_path") or metadata.get("artwork_path") or "",
                    "clearlogo_path": metadata.get("clearlogo_path") or "",
                    "metadata_status": metadata.get("metadata_status", "local"),
                    "needs_attention": bool(metadata.get("needs_attention")),
                    "attention_reason": metadata.get("attention_reason", ""),
                    "added_at": added_at,
                }
                if item["media_type"] == "tv" and item.get("season_number") is not None and item.get("episode_number") is not None:
                    item["meta"] = f"S{item['season_number']:02d}E{item['episode_number']:02d}"
                elif item["media_type"] == "tv" and item.get("season_label") == "Specials":
                    item["meta"] = "Special"
                else:
                    item["meta"] = "Movie" if item["media_type"] == "movie" else "Episode"
                group = groups.setdefault(
                    group_key,
                    {
                        "label": group_name,
                        "media_type": media_type,
                        "items": [],
                        "summary": metadata.get("show_summary") or metadata.get("detail_summary") or "",
                        "artwork_path": metadata.get("show_artwork_path") or metadata.get("artwork_path") or "",
                        "hero_artwork_path": metadata.get("hero_artwork_path") or metadata.get("show_artwork_path") or metadata.get("artwork_path") or "",
                        "clearlogo_path": metadata.get("clearlogo_path") or "",
                        "year": metadata.get("year", ""),
                        "needs_attention": False,
                        "attention_reason": "",
                        "added_at": 0.0,
                    },
                )
                if section_label:
                    group["media_type"] = "tv"
                if not group.get("summary") and item.get("summary"):
                    group["summary"] = item["summary"]
                if not group.get("artwork_path") and item.get("artwork_path"):
                    group["artwork_path"] = item["artwork_path"]
                if not group.get("hero_artwork_path") and item.get("hero_artwork_path"):
                    group["hero_artwork_path"] = item["hero_artwork_path"]
                if not group.get("clearlogo_path") and item.get("clearlogo_path"):
                    group["clearlogo_path"] = item["clearlogo_path"]
                group["added_at"] = max(float(group.get("added_at", 0.0) or 0.0), added_at)
                if item.get("needs_attention"):
                    group["needs_attention"] = True
                    if not group.get("attention_reason"):
                        group["attention_reason"] = item.get("attention_reason", "")
                group["items"].append(item)

            group_items = []
            for group in sorted(groups.values(), key=lambda entry: entry["label"].casefold()):
                items = group["items"]
                items.sort(
                    key=lambda item: (
                        0 if (item.get("section_label") or "").casefold().startswith("s") and any(ch.isdigit() for ch in item.get("section_label", "")) else (
                            1 if item.get("section_label") == "Specials" else (
                                2 if item.get("section_label") == "Movies" else (
                                    3 if item.get("season_number") is not None else 4
                                )
                            )
                        ),
                        item.get("season_number") if item.get("season_number") is not None else 10_000,
                        normalize_title(item.get("section_label", "")),
                        item.get("episode_number") if item.get("episode_number") is not None else 10_000,
                        item["label"].casefold(),
                    )
                )
                group_items.append(
                    {
                        "label": group["label"],
                        "meta": f"{len(items)} title{'s' if len(items) != 1 else ''}",
                        "summary": group.get("summary") or "",
                        "artwork_path": group.get("artwork_path") or "",
                        "hero_artwork_path": group.get("hero_artwork_path") or group.get("artwork_path") or "",
                        "clearlogo_path": group.get("clearlogo_path") or "",
                        "year": group.get("year", ""),
                        "media_type": group.get("media_type", "movie"),
                        "needs_attention": bool(group.get("needs_attention")),
                        "attention_reason": group.get("attention_reason", ""),
                        "added_at": float(group.get("added_at", 0.0) or 0.0),
                        "items": items,
                    }
                )

            catalog.append(
                {
                    "number": media_index,
                    "label": channel.name,
                    "meta": f"{len(group_items)} show{'s' if len(group_items) != 1 else ''}",
                    "groups": group_items,
                }
            )
            if progress_callback:
                progress_callback(
                    media_index,
                    total_media_channels,
                    "Organizing on-demand library",
                    f"{channel.name}  •  {len(group_items)} collection{'s' if len(group_items) != 1 else ''}",
                )
        self.on_demand_catalog = catalog
        self.on_demand_catalog_dirty = False
        self.save_on_demand_catalog_cache()

    def configured_weather_channel(self):
        if not self.app_settings.get("weatherstar_enabled"):
            return None
        location = (self.app_settings.get("weatherstar_location") or "").strip()
        if not location:
            return None
        return WeatherChannel(location, retro=False)

    def cached_youtube_playlist_entries(self, playlist_url):
        key = youtube_playlist_cache_key(playlist_url)
        with self.youtube_cache_lock:
            playlist = (self.youtube_playlist_cache_state.get("playlists") or {}).get(key) or {}
            entries = playlist.get("entries") or []
        # A playlist URL can legitimately resolve to one accessible item when YouTube,
        # privacy settings, Mix/Radio pages, or a watch-page URL hide the full list.
        # Returning the single item is much better than making NetTV look completely broken.
        return [dict(entry) for entry in entries if isinstance(entry, dict)]

    def load_youtube_playlist_entries(self, playlist_url, force=False, progress_callback=None):
        playlist_url = (playlist_url or "").strip()
        playlist_source_url = youtube_source_url(playlist_url)
        if not playlist_source_url:
            self.last_nettv_error = "No valid YouTube playlist or video URL is configured."
            return []
        requires_playlist = bool(youtube_playlist_id(playlist_url))
        key = youtube_playlist_cache_key(playlist_url)
        if progress_callback:
            progress_callback(0, 3, "Checking NetTV playlist cache", key)
        with self.youtube_cache_lock:
            playlist_cache = (self.youtube_playlist_cache_state.get("playlists") or {}).get(key) or {}
            cached_entries = playlist_cache.get("entries") or []
            updated_at = float(playlist_cache.get("updated_at", 0) or 0)
        if cached_entries and not force and time.time() - updated_at < 6 * 3600 and (not requires_playlist or len(cached_entries) > 1):
            self.last_nettv_error = ""
            if progress_callback:
                progress_callback(3, 3, "Using cached NetTV playlist", f"{len(cached_entries)} videos ready")
            return [dict(entry) for entry in cached_entries if isinstance(entry, dict)]
        if not YTDLP_COMMAND:
            self.last_nettv_error = "yt-dlp is not installed or could not be opened."
            if progress_callback:
                progress_callback(3, 3, "NetTV playlist cache unavailable", "yt-dlp is not installed or could not be opened")
            return [dict(entry) for entry in cached_entries if isinstance(entry, dict)]

        if progress_callback:
            progress_callback(1, 3, "Reading NetTV playlist", "Asking yt-dlp for the playlist index...")
        info = {}
        last_error = ""
        for candidate_url in youtube_playlist_candidate_urls(playlist_url):
            detail = "Reading playlist URL..." if "/playlist" in candidate_url else "Reading watch-page playlist context..."
            if progress_callback:
                progress_callback(1, 3, "Reading NetTV playlist", detail)
            command = YTDLP_COMMAND + [
                "--yes-playlist",
                "--flat-playlist",
                "--dump-single-json",
                "--no-warnings",
                "--socket-timeout",
                "15",
                "--playlist-end",
                "250",
                candidate_url,
            ]
            try:
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=45,
                    text=True,
                )
            except Exception as exc:
                last_error = f"yt-dlp timed out or could not run: {exc}"
                continue
            if result.returncode != 0 or not result.stdout.strip():
                message_lines = (result.stderr or "yt-dlp could not read the NetTV playlist.").strip().splitlines()
                last_error = message_lines[-1] if message_lines else "yt-dlp could not read the NetTV playlist."
                continue
            try:
                candidate_info = json.loads(result.stdout)
            except json.JSONDecodeError:
                last_error = "yt-dlp returned unreadable playlist data."
                continue
            candidate_entries = candidate_info.get("entries") or []
            # Prefer a full playlist when possible, but do not reject a single exposed
            # item. Rejecting it is what makes NetTV fall into the "no playable videos"
            # path for watch-page playlist links, YouTube Mixes, or partially private
            # playlists. The user can still watch the accessible item while the status
            # message explains that the full playlist was not exposed.
            if requires_playlist and not candidate_entries:
                last_error = "yt-dlp did not expose any videos from this playlist."
                continue
            info = candidate_info
            playlist_source_url = candidate_url
            break

        if not info:
            self.last_nettv_error = last_error or "yt-dlp could not read the full NetTV playlist."
            if progress_callback:
                progress_callback(3, 3, "NetTV playlist read failed", self.last_nettv_error)
            usable_cache = cached_entries if (not requires_playlist or len(cached_entries) > 1) else []
            return [dict(entry) for entry in usable_cache if isinstance(entry, dict)]

        if progress_callback:
            progress_callback(2, 3, "Organizing NetTV playlist", "Preparing videos as channel episodes...")
        entries = normalize_youtube_playlist_entries(info, playlist_url)
        if not entries:
            self.last_nettv_error = "yt-dlp read the source, but no playable videos were listed."
            if progress_callback:
                progress_callback(3, 3, "No NetTV videos found", "Using cached playlist if available")
            usable_cache = cached_entries
            return [dict(entry) for entry in usable_cache if isinstance(entry, dict)]
        if requires_playlist and len(entries) == 1:
            self.last_nettv_error = "Only one NetTV video was exposed from this playlist. MediaWave will play it instead of failing the channel."

        with self.youtube_cache_lock:
            playlists = self.youtube_playlist_cache_state.setdefault("playlists", {})
            playlists[key] = {
                "source": playlist_url,
                "playlist_url": playlist_source_url,
                "title": info.get("title") or "NetTV",
                "updated_at": time.time(),
                "entries": entries,
            }
            save_json_file(YOUTUBE_PLAYLIST_CACHE_FILE, self.youtube_playlist_cache_state)
        self.last_nettv_error = ""
        if progress_callback:
            progress_callback(3, 3, "NetTV playlist ready", f"{len(entries)} videos cached for the channel lineup")
        return [dict(entry) for entry in entries]

    def resolve_youtube_stream_url(self, entry):
        entry = entry or {}
        video_url = entry.get("url") or youtube_video_url(entry.get("id", ""))
        if not video_url:
            return "", "This playlist item does not have a playable video URL."
        cached_video = cached_youtube_video_path(entry)
        if cached_video:
            return cached_video, ""
        if not YTDLP_COMMAND:
            return "", "yt-dlp is not available, so MediaWave cannot resolve NetTV playlist videos yet."

        output_template = youtube_download_template(entry)
        cache_key = youtube_video_cache_key(entry)
        result = None
        last_exception = None
        format_selectors = (YOUTUBE_PROGRESSIVE_DOWNLOAD_FORMAT,) if entry.get("_nettv_force_progressive") else (YOUTUBE_DOWNLOAD_FORMAT, YOUTUBE_PROGRESSIVE_DOWNLOAD_FORMAT)
        for format_selector in format_selectors:
            command = YTDLP_COMMAND + [
                "--no-playlist",
                "--no-warnings",
                "--ignore-config",
                "--format",
                format_selector,
                "--merge-output-format",
                "mp4",
                "--retries",
                "3",
                "--fragment-retries",
                "3",
                "--newline",
                "--no-part",
                "-o",
                output_template,
                video_url,
            ]
            try:
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=600,
                    text=True,
                )
            except Exception as exc:
                last_exception = exc
                continue
            downloaded_path = cached_youtube_video_path(entry)
            if result.returncode == 0 and downloaded_path:
                break
        if result is None:
            return "", f"Could not resolve this NetTV video: {last_exception}"
        downloaded_path = cached_youtube_video_path(entry)
        if result.returncode != 0 or not downloaded_path:
            message_lines = (result.stderr or result.stdout or "yt-dlp could not download this NetTV video.").strip().splitlines()
            message = message_lines[-1] if message_lines else "yt-dlp could not download this NetTV video."
            return "", message
        with self.youtube_cache_lock:
            streams = self.youtube_playlist_cache_state.setdefault("streams", {})
            streams[cache_key] = {
                "source_url": video_url,
                "local_path": downloaded_path,
                "title": entry.get("title", "NetTV Video"),
                "duration": entry.get("duration", 900.0),
                "quality": "1080p preferred",
                "cache_version": YOUTUBE_CACHE_VERSION,
                "updated_at": time.time(),
            }
            save_json_file(YOUTUBE_PLAYLIST_CACHE_FILE, self.youtube_playlist_cache_state)
        return downloaded_path, ""

    def find_youtube_entry_by_path(self, path):
        if not isinstance(path, str) or not path.startswith("youtube://"):
            return {}
        for channel in self.channels:
            if getattr(channel, "channel_type", "media") != "youtube":
                continue
            for entry in getattr(channel, "entries", []):
                if entry.get("path") == path:
                    return dict(entry)
        with self.youtube_cache_lock:
            for playlist in (self.youtube_playlist_cache_state.get("playlists") or {}).values():
                for entry in playlist.get("entries") or []:
                    if isinstance(entry, dict) and entry.get("path") == path:
                        return dict(entry)
        return {}

    def show_youtube_tuning_slate(self, title="", message="Preparing NetTV channel"):
        title = (title or "NetTV").strip()
        message = (message or "Preparing NetTV channel").strip()
        now = time.time()
        if not self.nettv_waiting_for_visible_frame:
            self.nettv_waiting_started_at = now
        self.nettv_waiting_for_visible_frame = True
        self.nettv_visible_frame_seen = False
        self.nettv_black_frame_started_at = 0.0
        self.nettv_last_status_update_at = now
        self.nettv_current_title = title
        self.nettv_current_message = message

        display_rect = self.video_window.video_surface.display_rect()
        if display_rect is None or display_rect.isEmpty():
            surface_rect = self.video_window.video_surface.rect()
            display_rect = surface_rect if not surface_rect.isEmpty() else QRect(0, 0, max(960, self.video_window.width()), max(540, self.video_window.height()))
        pixmap = make_nettv_standby_pixmap(display_rect.size(), title, message)

        self.last_video_frame = pixmap
        self.video_window.video_surface.set_frame(pixmap)
        self.video_window.video_surface.show()
        self.video_window.show_nettv_status(title, message)

    def clear_nettv_visual_state(self):
        self.nettv_waiting_for_visible_frame = False
        self.nettv_visible_frame_seen = False
        self.nettv_waiting_started_at = 0.0
        self.nettv_black_frame_started_at = 0.0
        self.nettv_last_status_update_at = 0.0
        self.nettv_current_title = "NetTV"
        self.nettv_current_message = "Preparing your playlist feed..."
        self.nettv_playing_entry = {}
        self.nettv_playing_started_at = 0.0
        self.nettv_playing_offset = 0.0
        self.video_window.hide_nettv_status()

    def suspend_nettv_visuals(self):
        self.nettv_audio_output.setMuted(True)
        self.nettv_waiting_for_visible_frame = False
        self.nettv_black_frame_started_at = 0.0
        self.video_window.hide_nettv_status()

    def update_youtube_entry_cache(self, entry):
        if not isinstance(entry, dict) or not entry.get("path"):
            return
        changed = False
        path = entry.get("path")
        with self.youtube_cache_lock:
            for playlist in (self.youtube_playlist_cache_state.get("playlists") or {}).values():
                entries = playlist.get("entries") or []
                for index, cached in enumerate(entries):
                    if not isinstance(cached, dict) or cached.get("path") != path:
                        continue
                    merged = dict(cached)
                    for key in ("title", "duration", "thumbnail", "url", "id"):
                        if entry.get(key):
                            merged[key] = entry[key]
                    entries[index] = merged
                    changed = True
            if changed:
                save_json_file(YOUTUBE_PLAYLIST_CACHE_FILE, self.youtube_playlist_cache_state)

        channel = self.current_youtube_channel()
        if channel:
            updated_entries = []
            changed_channel = False
            for cached in getattr(channel, "entries", []):
                if cached.get("path") == path:
                    merged = dict(cached)
                    for key in ("title", "duration", "thumbnail", "url", "id"):
                        if entry.get(key):
                            merged[key] = entry[key]
                    updated_entries.append(merged)
                    changed_channel = True
                else:
                    updated_entries.append(dict(cached))
            if changed_channel:
                channel.update_entries(updated_entries)

    def configured_youtube_channel(self):
        if not self.app_settings.get("youtube_enabled"):
            return None
        playlist_url = (self.app_settings.get("youtube_playlist_url") or "").strip()
        if not youtube_source_url(playlist_url):
            return None
        entries = self.cached_youtube_playlist_entries(playlist_url)
        return YouTubePlaylistChannel(playlist_url, entries=entries)

    def configured_radiowave_channel(self):
        if not self.app_settings.get("radiowave_enabled"):
            return None
        folder = os.path.realpath(os.path.abspath(os.path.expanduser((self.app_settings.get("radiowave_folder") or "").strip()))) if (self.app_settings.get("radiowave_folder") or "").strip() else ""
        if not folder:
            channel = RadioWaveChannel(
                "",
                self.duration_cache,
                self.radiowave_metadata_cache,
                empty_reason="No music folder is configured yet.",
            )
        elif not os.path.isdir(folder):
            channel = RadioWaveChannel(
                folder,
                self.duration_cache,
                self.radiowave_metadata_cache,
                empty_reason="The configured music folder could not be opened.",
            )
        else:
            channel = RadioWaveChannel(folder, self.duration_cache, self.radiowave_metadata_cache)
        save_json_file(MEDIA_CACHE_FILE, self.duration_cache)
        save_json_file(RADIOWAVE_METADATA_CACHE_FILE, self.radiowave_metadata_cache)
        return channel

    def preload_radiowave_if_configured(self):
        radiowave_channel = next((channel for channel in self.channels if getattr(channel, "channel_type", "media") == "radiowave"), None)
        if not radiowave_channel:
            self.stop_radiowave_background()
            return
        self.configure_radiowave_background(radiowave_channel)

    def inject_special_channels(self):
        base_channels = [channel for channel in self.channels if getattr(channel, "channel_type", "media") == "media"]
        special_channels = []
        weather_channel = self.configured_weather_channel()
        if weather_channel:
            special_channels.append((int(self.app_settings.get("weatherstar_channel_number", 1) or 1), weather_channel))
        radiowave_channel = self.configured_radiowave_channel()
        if radiowave_channel:
            special_channels.append((int(self.app_settings.get("radiowave_channel_number", 1) or 1), radiowave_channel))
        youtube_channel = self.configured_youtube_channel()
        if youtube_channel:
            special_channels.append((int(self.app_settings.get("youtube_channel_number", 1) or 1), youtube_channel))
        self.channels = list(base_channels)
        for desired_number, channel in sorted(special_channels, key=lambda item: item[0]):
            insert_index = max(0, min(len(self.channels), desired_number - 1))
            self.channels.insert(insert_index, channel)

    def stop_radiowave_background(self):
        self.radiowave_refresh_timer.stop()
        self.radiowave_channel = None
        self.radiowave_current_path = ""
        self.radiowave_pending_seek_ms = 0
        self.radiowave_state_dirty = False
        self.radiowave_last_refresh_at = 0.0
        self.radiowave_last_guide_refresh_at = 0.0
        self.radiowave_last_info_refresh_at = 0.0
        self.radiowave_audio_output.setMuted(True)
        self.radiowave_player.stop()
        self.radiowave_state = {
            "title": "",
            "artist": "",
            "album": "",
            "year": "",
            "art_pixmap": QPixmap(),
            "progress_ms": 0,
            "duration_ms": 0,
            "bands": [0.0] * 24,
            "empty_state": False,
        }
        self.radiowave_bands = [0.0] * 24
        self.radiowave_cached_art_path = ""
        self.radiowave_cached_art = QPixmap()
        self.video_window.hide_radiowave_channel()

    def radiowave_visuals_needed(self):
        if self.is_radiowave_active_channel():
            return True
        if self.video_window.info_overlay.isVisible() and self.current_radiowave_channel() is not None:
            return True
        if self.video_window.guide_overlay.isVisible():
            selected_channel = self.channels[self.guide_selection] if self.channels and 0 <= self.guide_selection < len(self.channels) else None
            if getattr(selected_channel, "channel_type", "media") == "radiowave":
                return True
        return False

    def radiowave_refresh_interval_ms(self):
        if self.is_radiowave_active_channel():
            return 45
        if self.video_window.guide_overlay.isVisible():
            selected_channel = self.channels[self.guide_selection] if self.channels and 0 <= self.guide_selection < len(self.channels) else None
            if getattr(selected_channel, "channel_type", "media") == "radiowave":
                return 80
        if self.video_window.info_overlay.isVisible() and self.current_radiowave_channel() is not None:
            return 80
        return 900

    def configure_radiowave_background(self, channel):
        if not channel or not channel.shows:
            self.stop_radiowave_background()
            return
        if self.radiowave_channel is channel and self.radiowave_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            if not self.radiowave_current_path:
                current_path, offset = channel.get_current()
                if current_path:
                    self.start_radiowave_track(current_path, int(offset * 1000), muted=True)
            else:
                self.schedule_radiowave_state_refresh(40)
            return
        self.radiowave_channel = channel
        current_path, offset = channel.get_current()
        if not current_path:
            self.stop_radiowave_background()
            return
        if getattr(channel, "empty_state", False) or current_path == RadioWaveChannel.EMPTY_PATH or not os.path.isfile(current_path):
            self.radiowave_current_path = current_path
            self.radiowave_pending_seek_ms = 0
            self.radiowave_bands = [0.0] * 24
            self.radiowave_player.stop()
            self.set_radiowave_muted(True)
            self.schedule_radiowave_state_refresh(20)
            return
        self.start_radiowave_track(current_path, int(offset * 1000), muted=True)

    def is_radiowave_active_channel(self):
        return bool(self.channels) and 0 <= self.current_channel < len(self.channels) and getattr(self.channels[self.current_channel], "channel_type", "media") == "radiowave"

    def set_radiowave_muted(self, muted):
        self.radiowave_audio_output.setMuted(bool(muted))

    def load_radiowave_art(self, path):
        if path == self.radiowave_cached_art_path:
            return self.radiowave_cached_art
        metadata = self.radiowave_metadata_cache.get(path, {})
        art_path = metadata.get("art_path", "")
        if art_path and os.path.exists(art_path):
            pixmap = QPixmap(art_path)
            if not pixmap.isNull():
                self.radiowave_cached_art_path = path
                self.radiowave_cached_art = pixmap
                return pixmap
        self.radiowave_cached_art_path = path
        self.radiowave_cached_art = QPixmap()
        return self.radiowave_cached_art

    def schedule_radiowave_state_refresh(self, delay_ms=None):
        self.radiowave_state_dirty = True
        interval = self.radiowave_refresh_interval_ms() if delay_ms is None else max(0, int(delay_ms))
        now = time.time()
        elapsed_ms = (now - self.radiowave_last_refresh_at) * 1000.0
        target_delay = max(0, int(interval - elapsed_ms))
        if delay_ms is not None:
            target_delay = max(target_delay, max(0, int(delay_ms)))
        if self.radiowave_refresh_timer.isActive():
            remaining = self.radiowave_refresh_timer.remainingTime()
            if remaining >= 0 and remaining <= target_delay:
                return
            self.radiowave_refresh_timer.stop()
        self.radiowave_refresh_timer.start(target_delay)

    def refresh_radiowave_state(self):
        if not self.radiowave_current_path:
            return
        self.radiowave_refresh_timer.stop()
        self.radiowave_last_refresh_at = time.time()
        self.radiowave_state_dirty = False
        visual_context = self.radiowave_visuals_needed()
        if self.radiowave_current_path == RadioWaveChannel.EMPTY_PATH or (self.radiowave_channel and getattr(self.radiowave_channel, "empty_state", False)):
            metadata = (self.radiowave_channel.metadata_for(self.radiowave_current_path) if self.radiowave_channel else {}) or radiowave_empty_metadata()
            progress_ms = 0
            duration_ms = int((metadata.get("duration") or RADIOWAVE_FALLBACK_DURATION_SECONDS) * 1000)
            next_tracks = []
            self.radiowave_state = {
                "title": metadata.get("title") or "The music server has been depleted.",
                "artist": metadata.get("artist") or "DJ PlumCrazy",
                "album": metadata.get("album") or "RadioWaveTV emergency broadcast",
                "genre": metadata.get("genre") or "",
                "year": metadata.get("year") or "",
                "art_pixmap": QPixmap(),
                "progress_ms": progress_ms,
                "duration_ms": duration_ms,
                "progress": 0.0,
                "bands": [0.0] * 24,
                "next_tracks": next_tracks,
                "track_count": 0,
                "weather_context": (self.app_settings.get("weatherstar_location") or "").strip(),
                "empty_state": True,
            }
            self.video_window.update_radiowave_channel(self.radiowave_state)
            now = time.time()
            if self.video_window.info_overlay.isVisible() and self.current_radiowave_channel() is not None and (now - self.radiowave_last_info_refresh_at) >= 0.25:
                self.radiowave_last_info_refresh_at = now
                self.refresh_info_banner()
            selected_channel = self.channels[self.guide_selection] if self.channels and 0 <= self.guide_selection < len(self.channels) else None
            if self.video_window.guide_overlay.isVisible() and (
                self.current_radiowave_channel() is not None
                or getattr(selected_channel, "channel_type", "media") == "radiowave"
            ) and (now - self.radiowave_last_guide_refresh_at) >= 0.25:
                self.radiowave_last_guide_refresh_at = now
                self.refresh_guide()
            return
        metadata = self.radiowave_metadata_cache.get(self.radiowave_current_path) or parse_local_music_metadata(
            self.radiowave_current_path,
            self.duration_cache,
            self.radiowave_metadata_cache,
        )
        progress_ms = max(0, int(self.radiowave_player.position()))
        duration_ms = max(0, int(self.radiowave_player.duration()))
        if duration_ms <= 0:
            duration_ms = int((metadata.get("duration") or 0) * 1000)
        next_tracks = []
        if self.radiowave_channel:
            paths, _, _ = self.radiowave_channel.get_schedule_data()
            if paths:
                try:
                    current_index = paths.index(self.radiowave_current_path)
                except ValueError:
                    current_index = -1
                for offset in range(1, min(4, len(paths))):
                    next_path = paths[(current_index + offset) % len(paths)]
                    next_meta = self.radiowave_channel.metadata_for(next_path)
                    next_tracks.append(
                        {
                            "title": next_meta.get("title") or local_music_title(next_path),
                            "artist": next_meta.get("artist") or "",
                            "album": next_meta.get("album") or "",
                            "year": next_meta.get("year") or "",
                        }
                    )
        self.radiowave_state = {
            "title": metadata.get("title") or local_music_title(self.radiowave_current_path),
            "artist": metadata.get("artist") or "Unknown Artist",
            "album": metadata.get("album") or "Unknown Album",
            "genre": metadata.get("genre") or "",
            "year": metadata.get("year") or "",
            "art_pixmap": self.load_radiowave_art(self.radiowave_current_path),
            "progress_ms": progress_ms,
            "duration_ms": duration_ms,
            "progress": (progress_ms / duration_ms) if duration_ms > 0 else 0.0,
            "bands": list(self.radiowave_bands if visual_context else [0.0] * len(self.radiowave_bands)),
            "next_tracks": next_tracks,
            "track_count": len(self.radiowave_channel.shows) if self.radiowave_channel else 0,
            "weather_context": (self.app_settings.get("weatherstar_location") or "").strip(),
            "empty_state": False,
        }
        self.video_window.update_radiowave_channel(self.radiowave_state)
        now = time.time()
        if self.video_window.info_overlay.isVisible() and self.current_radiowave_channel() is not None and (now - self.radiowave_last_info_refresh_at) >= 0.25:
            self.radiowave_last_info_refresh_at = now
            self.refresh_info_banner()
        selected_channel = self.channels[self.guide_selection] if self.channels and 0 <= self.guide_selection < len(self.channels) else None
        if self.video_window.guide_overlay.isVisible() and (
            self.current_radiowave_channel() is not None
            or getattr(selected_channel, "channel_type", "media") == "radiowave"
        ) and (now - self.radiowave_last_guide_refresh_at) >= 0.25:
            self.radiowave_last_guide_refresh_at = now
            self.refresh_guide()

    def start_radiowave_track(self, path, position_ms=0, muted=True):
        if not path:
            return
        if path == RadioWaveChannel.EMPTY_PATH or not os.path.isfile(path):
            self.radiowave_current_path = path
            self.radiowave_pending_seek_ms = 0
            self.radiowave_bands = [0.0] * 24
            self.radiowave_player.stop()
            self.set_radiowave_muted(True)
            self.schedule_radiowave_state_refresh(20)
            return
        self.radiowave_current_path = path
        self.radiowave_pending_seek_ms = max(0, int(position_ms))
        self.radiowave_bands = [0.0] * 24
        self.set_radiowave_muted(muted)
        self.radiowave_player.stop()
        self.radiowave_player.setPlaybackRate(1.0)
        self.radiowave_player.setSource(QUrl.fromLocalFile(path))
        self.schedule_radiowave_state_refresh(20)

    @Slot(QMediaPlayer.MediaStatus)
    def on_radiowave_media_status_changed(self, status):
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            if self.radiowave_pending_seek_ms:
                self.radiowave_player.setPosition(self.radiowave_pending_seek_ms)
                self.radiowave_pending_seek_ms = 0
            self.radiowave_player.play()
            self.schedule_radiowave_state_refresh(30)
            return
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.radiowave_channel:
            paths, _, _ = self.radiowave_channel.get_schedule_data()
            if not paths:
                return
            try:
                current_index = paths.index(self.radiowave_current_path)
            except ValueError:
                current_index = -1
            next_path = paths[(current_index + 1) % len(paths)]
            self.start_radiowave_track(next_path, 0, muted=not self.is_radiowave_active_channel())

    @Slot(int)
    def on_radiowave_position_changed(self, _position):
        self.schedule_radiowave_state_refresh()

    @Slot(object)
    def on_radiowave_audio_buffer_received(self, buffer):
        if not self.radiowave_visuals_needed():
            return
        if not buffer or not buffer.isValid():
            return
        fmt = buffer.format()
        channel_count = max(1, fmt.channelCount())
        sample_format = fmt.sampleFormat()
        raw = bytes(buffer.constData())
        if not raw:
            return

        values = []
        if sample_format == QAudioFormat.SampleFormat.Int16:
            sample_count = len(raw) // 2
            if sample_count <= 0:
                return
            unpacked = struct.unpack("<" + "h" * sample_count, raw[: sample_count * 2])
            scale = 32768.0
            for index in range(0, sample_count, channel_count):
                frame = unpacked[index:index + channel_count]
                values.append(sum(abs(sample) for sample in frame) / (len(frame) * scale))
        elif sample_format == QAudioFormat.SampleFormat.Int32:
            sample_count = len(raw) // 4
            if sample_count <= 0:
                return
            unpacked = struct.unpack("<" + "i" * sample_count, raw[: sample_count * 4])
            scale = float(2 ** 31)
            for index in range(0, sample_count, channel_count):
                frame = unpacked[index:index + channel_count]
                values.append(sum(abs(sample) for sample in frame) / (len(frame) * scale))
        elif sample_format == QAudioFormat.SampleFormat.Float:
            sample_count = len(raw) // 4
            if sample_count <= 0:
                return
            unpacked = struct.unpack("<" + "f" * sample_count, raw[: sample_count * 4])
            for index in range(0, sample_count, channel_count):
                frame = unpacked[index:index + channel_count]
                values.append(sum(abs(sample) for sample in frame) / len(frame))
        else:
            return

        if not values:
            return
        band_count = len(self.radiowave_bands)
        bucket_size = max(1, len(values) // band_count)
        levels = []
        for index in range(band_count):
            start = index * bucket_size
            end = len(values) if index == band_count - 1 else min(len(values), start + bucket_size)
            if start >= len(values):
                levels.append(0.0)
                continue
            bucket = values[start:end]
            raw_level = sum(bucket) / max(1, len(bucket))
            boosted_level = min(1.0, math.sqrt(max(0.0, raw_level)) * 1.55)
            levels.append(boosted_level)
        self.radiowave_bands = [
            (previous * 0.68) + (current * 0.32)
            for previous, current in zip(self.radiowave_bands, levels)
        ]
        self.schedule_radiowave_state_refresh(20)

    def build_resume_items(self):
        entries = self.resume_state.get("entries", {})
        valid_paths = {path for channel in self.channels for path in channel.shows}
        items = []
        changed = False
        for path, entry in list(entries.items()):
            if path not in valid_paths:
                entries.pop(path, None)
                changed = True
                continue
            position_ms = int(entry.get("position_ms", 0))
            if position_ms <= 0:
                continue
            duration_ms = int(entry.get("duration_ms", 0) or 0)
            metadata = self.get_program_metadata(path)
            channel_name = entry.get("channel_name", "")
            items.append(
                {
                    "path": path,
                    "label": metadata.get("show_name") or format_program_title(path),
                    "meta": channel_name,
                    "position_ms": position_ms,
                    "remaining_ms": max(0, duration_ms - position_ms) if duration_ms > 0 else 0,
                    "summary": metadata.get("detail_summary") or "",
                    "detail_title": metadata.get("detail_title") or format_program_title(path),
                    "channel_name": channel_name,
                    "show_name": metadata.get("show_name") or format_program_title(path),
                    "episode_label": metadata.get("episode_title") or metadata.get("detail_title") or format_program_title(path),
                    "media_type": metadata.get("media_type", "movie"),
                    "artwork_path": metadata.get("show_artwork_path") or metadata.get("artwork_path") or "",
                    "last_played": entry.get("last_played", 0),
                }
            )
        if changed:
            save_json_file(RESUME_STATE_FILE, self.resume_state)
        items.sort(key=lambda item: item.get("last_played", 0), reverse=True)
        return items

    # ---------------- PLAY ---------------- #

    def play_channel(self, with_transition=True, show_channel_overlay=True):
        if not self.channels:
            self.status.setText("Load a catalog to start surfing channels.")
            return

        ch = self.channels[self.current_channel]
        if getattr(ch, "channel_type", "media") == "weatherstar":
            previous_frame = self.capture_current_frame()
            self.stop_player()
            self.playback_mode = "live"
            self.current_on_demand_path = None
            self.hide_info_banner()

            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                self.video_window.setGeometry(screen.geometry())
            self.video_window.show()
            self.video_window.showFullScreen()
            self.video_window.raise_()
            self.video_window.activateWindow()
            self.video_window.setFocus(Qt.ActiveWindowFocusReason)
            if self.video_window.guide_overlay.isVisible():
                self.refresh_guide()
            self.video_window.on_demand_overlay.hide()
            if with_transition:
                self.video_window.static.trigger(previous_frame)
                self.switch_sound.stop()
                self.switch_sound.play()
            if show_channel_overlay:
                self.video_window.channel_overlay.show_channel(self.current_channel + 1, ch.name)

            widescreen = self.profile_combo.currentText() != "CRT 4:3"
            self.pending_weather_url = ch.weatherstar_url(widescreen=widescreen)
            self.pending_weather_name = ch.name
            self.pending_weather_location = ch.location
            self.status.setText(
                f"Channel {self.current_channel + 1}/{len(self.channels)}: "
                f"{ch.name}\n{ch.location}"
            )
            self.channel_switch_timer.start(165 if with_transition else 10)
            return

        if getattr(ch, "channel_type", "media") == "radiowave":
            previous_frame = self.capture_current_frame()
            self.stop_player()
            self.playback_mode = "live"
            self.current_on_demand_path = None
            self.hide_info_banner()

            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                self.video_window.setGeometry(screen.geometry())
            self.video_window.show()
            self.video_window.showFullScreen()
            self.video_window.raise_()
            self.video_window.activateWindow()
            self.video_window.setFocus(Qt.ActiveWindowFocusReason)
            if self.video_window.guide_overlay.isVisible():
                self.refresh_guide()
            self.video_window.on_demand_overlay.hide()
            if with_transition:
                self.video_window.static.trigger(previous_frame)
                self.switch_sound.stop()
                self.switch_sound.play()
            if show_channel_overlay:
                self.video_window.channel_overlay.show_channel(self.current_channel + 1, ch.name)

            self.pending_radiowave_channel = ch
            self.status.setText(
                f"Channel {self.current_channel + 1}/{len(self.channels)}: "
                f"{ch.name}\nLocal music channel"
            )
            self.channel_switch_timer.start(165 if with_transition else 10)
            return

        if getattr(ch, "channel_type", "media") == "youtube":
            previous_frame = self.capture_current_frame()
            self.stop_player()
            self.playback_mode = "live"
            self.current_on_demand_path = None
            self.hide_info_banner()

            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                self.video_window.setGeometry(screen.geometry())
            self.video_window.show()
            self.video_window.showFullScreen()
            self.video_window.raise_()
            self.video_window.activateWindow()
            self.video_window.setFocus(Qt.ActiveWindowFocusReason)
            self.video_window.on_demand_overlay.hide()
            if with_transition:
                self.video_window.static.trigger(previous_frame)
                self.switch_sound.stop()
                self.switch_sound.play()
            if show_channel_overlay:
                self.video_window.channel_overlay.show_channel(self.current_channel + 1, ch.name)

            entries_now = getattr(ch, "entries", []) or []
            has_placeholder_entries = any(entry.get("placeholder") for entry in entries_now)
            if not entries_now or has_placeholder_entries:
                self.status.setText(f"{ch.name}\nLoading playlist index...")
                self.show_youtube_tuning_slate("", "Loading playlist index...")
                QApplication.processEvents()
                entries = self.load_youtube_playlist_entries(ch.playlist_url, force=has_placeholder_entries)
                ch.update_entries(entries)
            youtube_entry, offset = ch.get_current_youtube_entry_and_offset()
            if not youtube_entry:
                self.show_youtube_tuning_slate(
                    ch.name,
                    "MediaWave could not load playlist videos. Check the playlist link or update yt-dlp.",
                )
                self.status.setText(
                    f"{ch.name} is enabled, but MediaWave could not load any playlist videos.\n"
                    "Check the playlist link and make sure yt-dlp can access the source."
                )
                return

            if self.video_window.guide_overlay.isVisible():
                self.refresh_guide()

            entry_path = youtube_entry.get("path", "")
            cached_video = cached_youtube_video_path(youtube_entry)
            can_resume_live_nettv = (
                entry_path
                and entry_path == self.nettv_loaded_entry_path
                and bool(self.nettv_loaded_stream_url)
                and self.nettv_player.mediaStatus() not in (
                    QMediaPlayer.MediaStatus.NoMedia,
                    QMediaPlayer.MediaStatus.InvalidMedia,
                )
            )
            if can_resume_live_nettv:
                self.current_youtube_user_path = entry_path
                self.nettv_audio_output.setMuted(False)
                self.nettv_current_title = youtube_entry.get("title", self.nettv_current_title or "NetTV video")
                self.nettv_current_message = "Playing from a user-supplied NetTV playlist."
                if not self.nettv_last_frame.isNull():
                    self.last_video_frame = self.nettv_last_frame
                    self.video_window.video_surface.set_frame(self.nettv_last_frame)
                    self.video_window.hide_nettv_status()
                    self.nettv_waiting_for_visible_frame = False
                    self.nettv_visible_frame_seen = True
                else:
                    self.show_youtube_tuning_slate(
                        youtube_entry.get("title", "NetTV video"),
                        "Restoring NetTV picture...",
                    )
                if self.nettv_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                    self.nettv_player.play()
                self.reset_live_playback_health(entry_path)
                self.status.setText(
                    f"Channel {self.current_channel + 1}/{len(self.channels)}: "
                    f"{ch.name}\n{youtube_entry.get('title', 'NetTV video')}"
                )
                return

            if self.nettv_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                self.nettv_player.stop()
            self.nettv_loaded_entry_path = ""
            self.nettv_loaded_stream_url = ""
            self.nettv_last_frame = QPixmap()
            self.pending_youtube_entry = youtube_entry
            self.pending_youtube_entry["_nettv_selected_at"] = time.time()
            self.pending_youtube_entry["_nettv_selected_offset"] = float(offset or 0)
            self.pending_youtube_entry["_nettv_cached_at_tune"] = bool(cached_video)
            self.pending_offset = offset
            self.nettv_playing_entry = dict(youtube_entry)
            self.nettv_playing_started_at = time.time()
            self.nettv_playing_offset = float(offset or 0)
            self.nettv_current_title = youtube_entry.get("title", "NetTV video")
            self.nettv_current_message = "Resuming cached NetTV feed..." if cached_video else "Caching video for reliable playback..."
            self.nettv_waiting_for_visible_frame = True
            self.nettv_visible_frame_seen = False
            self.nettv_waiting_started_at = time.time()
            self.nettv_black_frame_started_at = 0.0
            self.show_youtube_tuning_slate(
                youtube_entry.get("title", "NetTV video"),
                "Tuning cached NetTV feed..." if cached_video else "Caching video for reliable playback...",
            )
            self.status.setText(
                f"Channel {self.current_channel + 1}/{len(self.channels)}: "
                f"{ch.name}\n{youtube_entry.get('title', 'NetTV video')}"
            )
            self.channel_switch_timer.start(165 if with_transition else 10)
            return

        video, offset = ch.get_current()

        if not video:
            self.status.setText(f"{ch.name} does not have a playable video right now.")
            return

        previous_frame = self.capture_current_frame()
        self.stop_player()
        self.playback_mode = "live"
        self.current_on_demand_path = None
        self.hide_info_banner()

        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            self.video_window.setGeometry(screen.geometry())
        self.video_window.show()
        self.video_window.showFullScreen()
        self.video_window.raise_()
        self.video_window.activateWindow()
        self.video_window.setFocus(Qt.ActiveWindowFocusReason)
        if self.video_window.guide_overlay.isVisible():
            self.refresh_guide()
        self.video_window.on_demand_overlay.hide()
        if with_transition:
            self.video_window.static.trigger(previous_frame)
            self.switch_sound.stop()
            self.switch_sound.play()
        if show_channel_overlay:
            self.video_window.channel_overlay.show_channel(self.current_channel + 1, ch.name)
        self.status.setText(
            f"Channel {self.current_channel + 1}/{len(self.channels)}: "
            f"{ch.name}\n{os.path.basename(video)}"
        )

        self.pending_video = video
        self.pending_video_is_url = False
        self.pending_offset = offset
        self.channel_switch_timer.start(165 if with_transition else 10)

    def start_pending_channel(self):
        if self.pending_weather_url:
            self.suspend_nettv_visuals()
            weather_url = self.pending_weather_url
            self.pending_weather_url = None
            self.video_window.show_weather_channel(weather_url)
            return
        if self.pending_radiowave_channel:
            self.suspend_nettv_visuals()
            self.configure_radiowave_background(self.pending_radiowave_channel)
            self.pending_radiowave_channel = None
            self.set_radiowave_muted(False)
            self.video_window.show_radiowave_channel(self.radiowave_state)
            return
        if self.pending_youtube_url:
            youtube_url = self.pending_youtube_url
            self.pending_youtube_url = None
            self.video_window.show_youtube_channel(youtube_url)
            return
        if self.pending_youtube_entry:
            entry = dict(self.pending_youtube_entry)
            offset = float(self.pending_offset or 0)
            self.pending_youtube_entry = None
            self.pending_offset = 0
            self.youtube_stream_generation += 1
            generation = self.youtube_stream_generation
            self.current_youtube_user_path = entry.get("path", "")
            self.status.setText(f"Caching NetTV video for playback...\n{entry.get('title', 'NetTV Video')}")
            self.video_window.hide_special_views()

            def worker():
                stream_url, error = self.resolve_youtube_stream_url(entry)
                self.youtubeStreamResolved.emit(generation, entry, stream_url, error, offset)

            threading.Thread(target=worker, daemon=True).start()
            return
        if not self.pending_video:
            return

        video = self.pending_video
        offset_ms = int(self.pending_offset * 1000)
        is_url = bool(self.pending_video_is_url)
        self.pending_video = None
        self.pending_video_is_url = False
        self.pending_offset = 0

        self.pending_seek_ms = offset_ms
        self.pending_play_after_seek = True
        self.reset_live_playback_health(video)
        self.media_player.setPlaybackRate(1.0)
        self.media_player.stop()
        self.suspend_nettv_visuals()
        self.media_player.setSource(QUrl(video) if is_url else QUrl.fromLocalFile(video))

    @Slot(int, dict, str, str, float)
    def on_youtube_stream_resolved(self, generation, entry, stream_url, error, offset):
        if generation != self.youtube_stream_generation or self.current_youtube_channel() is None:
            return
        title = (entry or {}).get("title", "NetTV Video")
        if not stream_url:
            self.show_youtube_tuning_slate(title, error or "This NetTV video could not be cached for playback.")
            self.status.setText(f"NetTV channel could not play:\n{title}\n{error or 'No playable video was found.'}")
            return
        self.update_youtube_entry_cache(entry)
        actual_duration = float((entry or {}).get("duration") or 0)
        selected_at = float((entry or {}).get("_nettv_selected_at") or time.time())
        effective_offset = max(0.0, float(offset or 0) + max(0.0, time.time() - selected_at))
        if actual_duration > 0 and effective_offset >= max(0.0, actual_duration - 2.0):
            self.play_channel(with_transition=False, show_channel_overlay=False)
            return
        offset_ms = int(effective_offset * 1000)
        self.nettv_pending_seek_ms = offset_ms
        self.nettv_pending_play_after_seek = True
        self.pending_video_is_url = False
        self.reset_live_playback_health((entry or {}).get("path", stream_url))
        if (entry or {}).get("_nettv_cached_at_tune"):
            self.show_youtube_tuning_slate(title, "Tuning cached NetTV feed...")
        else:
            self.show_youtube_tuning_slate(title, "Starting cached NetTV video...")
        self.nettv_playing_entry = dict(entry or {})
        self.nettv_playing_started_at = time.time()
        self.nettv_playing_offset = effective_offset
        self.nettv_current_title = title
        self.nettv_loaded_entry_path = (entry or {}).get("path", "")
        self.nettv_loaded_stream_url = stream_url
        self.nettv_audio_output.setMuted(self.current_youtube_channel() is None)
        self.nettv_player.setPlaybackRate(1.0)
        self.nettv_player.stop()
        if os.path.isfile(stream_url):
            self.nettv_player.setSource(QUrl.fromLocalFile(stream_url))
        else:
            self.nettv_player.setSource(QUrl(stream_url))
        self.status.setText(f"NetTV\n{title}")
        self.queue_nettv_prefetch(entry)

    def queue_nettv_prefetch(self, current_entry=None, count=2):
        channel = self.current_youtube_channel()
        if channel is None or self.nettv_prefetch_active:
            return
        entries = channel.get_schedule_entries()
        if not entries:
            return
        current_path = (current_entry or {}).get("path") or self.current_youtube_user_path
        start_index = -1
        for index, schedule_entry in enumerate(entries):
            youtube_entry = schedule_entry.get("youtube_entry") or {}
            if youtube_entry.get("path") == current_path or schedule_entry.get("path") == current_path:
                start_index = index
                break
        if start_index < 0:
            return
        prefetch_entries = []
        for step in range(1, min(count + 1, len(entries))):
            schedule_entry = entries[(start_index + step) % len(entries)]
            youtube_entry = dict(schedule_entry.get("youtube_entry") or {})
            if not youtube_entry or youtube_entry.get("placeholder"):
                continue
            if cached_youtube_video_path(youtube_entry):
                continue
            prefetch_entries.append(youtube_entry)
        if not prefetch_entries:
            return

        self.nettv_prefetch_active = True
        self.nettv_prefetch_generation += 1
        generation = self.nettv_prefetch_generation

        def worker():
            try:
                for entry in prefetch_entries:
                    if generation != self.nettv_prefetch_generation:
                        break
                    self.resolve_youtube_stream_url(entry)
            finally:
                self.nettv_prefetch_active = False

        threading.Thread(target=worker, daemon=True).start()

    def retry_nettv_with_compatible_format(self, reason=""):
        channel = self.current_youtube_channel()
        entry = dict(self.nettv_playing_entry or {})
        if channel is None or not entry or entry.get("_nettv_force_progressive"):
            self.show_youtube_tuning_slate("NetTV", reason or "NetTV could not open this cached video.")
            return
        cached_path = cached_youtube_video_path(entry)
        if cached_path and os.path.isfile(cached_path):
            try:
                os.remove(cached_path)
            except OSError:
                pass
        current_position = max(0.0, self.nettv_player.position() / 1000.0)
        entry["_nettv_force_progressive"] = True
        entry["_nettv_selected_at"] = time.time()
        entry["_nettv_selected_offset"] = current_position or self.nettv_playing_offset
        entry["_nettv_cached_at_tune"] = False
        self.pending_youtube_entry = entry
        self.pending_offset = float(entry["_nettv_selected_offset"])
        self.show_youtube_tuning_slate(
            entry.get("title", "NetTV Video"),
            "Rebuilding this NetTV video in a more compatible playback format...",
        )
        self.nettv_player.stop()
        self.nettv_loaded_entry_path = ""
        self.nettv_loaded_stream_url = ""
        self.channel_switch_timer.start(10)

    def reset_live_playback_health(self, path=""):
        self.live_stall_path = path or ""
        self.live_stall_last_position_ms = -1
        now = time.time()
        self.live_stall_last_advance_at = now
        self.live_stall_checks_started_at = now
        if self.playback_mode == "live" and path:
            self.live_stall_timer.start()
        else:
            self.live_stall_timer.stop()

    def on_live_position_changed(self, position):
        if self.playback_mode != "live" or not self.live_stall_path:
            return
        if position > self.live_stall_last_position_ms + 120:
            self.live_stall_last_position_ms = int(position)
            self.live_stall_last_advance_at = time.time()

    def remove_media_from_channels(self, path):
        removed_any = False
        for channel in self.channels:
            if getattr(channel, "channel_type", "media") != "media":
                continue
            kept_shows = []
            kept_durations = []
            removed_here = False
            for show_path, duration in zip(channel.shows, channel.durations):
                if show_path == path:
                    removed_any = True
                    removed_here = True
                    continue
                kept_shows.append(show_path)
                kept_durations.append(duration)
            if removed_here:
                channel.shows = kept_shows
                channel.durations = kept_durations
        if removed_any:
            self.channels = [
                channel for channel in self.channels
                if getattr(channel, "channel_type", "media") != "media" or channel.shows
            ]
            if self.channels:
                self.current_channel %= len(self.channels)
        return removed_any

    def recover_live_playback_failure(self, reason):
        if self.playback_mode != "live":
            return

        failed_path = self.live_stall_path or self.media_player.source().toLocalFile()
        self.live_stall_timer.stop()
        self.live_stall_path = ""

        if failed_path:
            failure_count = self.live_stall_failures.get(failed_path, 0) + 1
            self.live_stall_failures[failed_path] = failure_count
            if self.catalog_root and os.path.isfile(failed_path):
                signature = file_cache_signature(failed_path)
                validation_entries = self.catalog_validation_cache.setdefault("videos", {})
                validation_entries[failed_path] = {
                    "signature": signature,
                    "ok": False,
                    "reason": reason,
                }
                if failure_count >= 2:
                    try:
                        moved_to = quarantine_broken_media(failed_path, self.catalog_root)
                        validation_entries[moved_to] = {
                            "signature": signature,
                            "ok": False,
                            "reason": reason,
                            "quarantined_from": failed_path,
                        }
                        validation_entries.pop(failed_path, None)
                        self.remove_media_from_channels(failed_path)
                        save_json_file(CATALOG_VALIDATION_FILE, self.catalog_validation_cache)
                        self.status.setText(
                            f"Moved a broken media file to Broken:\n{os.path.basename(failed_path)}\n"
                            f"Reason: {reason}"
                        )
                    except OSError:
                        self.remove_media_from_channels(failed_path)
                else:
                    self.remove_media_from_channels(failed_path)

        self.media_player.stop()
        if not self.channels:
            self.status.setText("No playable channels remain after removing broken media.")
            self.refresh_controls()
            return
        self.play_channel(with_transition=False, show_channel_overlay=False)

    def check_live_playback_health(self):
        if self.playback_mode != "live" or not self.live_stall_path:
            return
        if self.current_youtube_channel() is not None:
            now = time.time()
            status = self.nettv_player.mediaStatus()
            title = self.nettv_current_title or "NetTV"
            if status in (QMediaPlayer.MediaStatus.InvalidMedia, QMediaPlayer.MediaStatus.StalledMedia):
                self.show_youtube_tuning_slate(title, "NetTV could not open this cached video. MediaWave will keep the channel on standby instead of showing a black screen.")
                self.status.setText("NetTV playback stalled or could not open this cached video.")
                return
            if self.nettv_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState and not self.nettv_pending_play_after_seek:
                self.show_youtube_tuning_slate(title, "NetTV is waiting for the player to start. The playlist is loaded, but playback has not produced picture yet.")
                self.status.setText("NetTV is waiting for the player to start.")
                return
            if self.nettv_waiting_for_visible_frame and now - self.nettv_waiting_started_at >= 6.0:
                entry = dict(self.nettv_playing_entry or {})
                waited = now - self.nettv_waiting_started_at

                # If the first cached/downloaded format never produces picture,
                # automatically rebuild it with the progressive MP4 selector
                # instead of leaving the user stuck on the standby slate.
                if waited >= 8.0 and entry and not entry.get("_nettv_force_progressive"):
                    self.retry_nettv_with_compatible_format(
                        "NetTV loaded the playlist, but the cached video did not produce visible frames. Retrying in a simpler MP4 format..."
                    )
                    return

                # Last-resort fallback: if even the progressive/local-player path
                # does not give Qt video frames, use the existing WebEngine player
                # so NetTV shows something instead of failing silently.
                if waited >= 15.0 and entry:
                    fallback_url = youtube_source_url(entry.get("url") or youtube_video_url(entry.get("id", "")))
                    if fallback_url:
                        self.nettv_player.stop()
                        self.nettv_audio_output.setMuted(True)
                        self.video_window.show_youtube_channel(fallback_url)
                        self.video_window.hide_nettv_status()
                        self.nettv_waiting_for_visible_frame = False
                        self.nettv_current_message = "Using NetTV web fallback because Qt did not expose playable video frames."
                        self.status.setText(f"NetTV web fallback active.\n{title}")
                        return

                if now - self.nettv_last_status_update_at >= 1.5:
                    self.nettv_last_status_update_at = now
                    self.video_window.show_nettv_status(
                        title,
                        "The playlist is loaded, but this video has not produced a visible frame yet.",
                    )
                self.status.setText(
                    f"NetTV is waiting for visible video.\n{title}\n"
                    "The channel is kept on standby so you never get a silent black screen."
                )
            return
        if self.current_weather_channel() is not None or self.current_radiowave_channel() is not None:
            return

        now = time.time()
        if now - self.live_stall_checks_started_at < 6.0:
            return

        status = self.media_player.mediaStatus()
        if status in (QMediaPlayer.MediaStatus.InvalidMedia, QMediaPlayer.MediaStatus.StalledMedia):
            self.recover_live_playback_failure("Playback stalled while opening this file")
            return

        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState and not self.pending_play_after_seek:
            self.recover_live_playback_failure("Playback stopped unexpectedly")
            return

        position = int(self.media_player.position())
        duration = int(self.media_player.duration())
        if position > self.live_stall_last_position_ms + 120:
            self.live_stall_last_position_ms = position
            self.live_stall_last_advance_at = now
            return

        if duration > 0 and position >= max(0, duration - 1500):
            return

        if now - self.live_stall_last_advance_at >= 7.0:
            self.recover_live_playback_failure("Playback froze and stopped advancing")

    @Slot(QMediaPlayer.MediaStatus)
    def on_media_status_changed(self, status):
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            if not self.pending_play_after_seek:
                return

            target = self.pending_seek_ms
            self.pending_seek_ms = 0
            self.pending_play_after_seek = False

            if target > 0:
                self.media_player.setPosition(target)
                QTimer.singleShot(120, self.media_player.play)
            else:
                self.media_player.play()
            if self.playback_mode == "live" and self.live_stall_path:
                self.live_stall_last_position_ms = int(target)
                self.live_stall_last_advance_at = time.time()
                self.live_stall_checks_started_at = time.time()
                self.live_stall_timer.start()
            return

        if status == QMediaPlayer.EndOfMedia:
            self.live_stall_timer.stop()
            if self.playback_mode == "ondemand":
                finished_path = self.current_on_demand_path
                next_item = self.current_next_on_demand_item()
                self.resume_timer.stop()
                self.video_window.next_up_overlay.hide()
                self.next_up_state = None
                self.current_on_demand_path = None
                if finished_path:
                    self.resume_state.setdefault("entries", {}).pop(finished_path, None)
                    save_json_file(RESUME_STATE_FILE, self.resume_state)
                if next_item:
                    self.play_on_demand(next_item["path"], 0)
                    self.status.setText(
                        f"On Demand: {next_item.get('detail_title', next_item.get('label', format_program_title(next_item['path'])))}\n"
                        "Autoplaying the next episode."
                    )
                    return
                self.playback_mode = "live"
                self.media_player.stop()
                self.show_on_demand()
                self.status.setText("Finished on-demand playback. Choose another title or resume something else.")
            else:
                self.play_channel(with_transition=False, show_channel_overlay=False)
            return

        if self.playback_mode == "live" and status in (
            QMediaPlayer.MediaStatus.InvalidMedia,
            QMediaPlayer.MediaStatus.StalledMedia,
        ):
            if self.current_youtube_channel() is not None:
                self.retry_nettv_with_compatible_format("Playback stalled or could not open this cached video.")
                self.status.setText("NetTV playback stalled or could not open this cached video.")
                return
            self.recover_live_playback_failure("The media file could not keep playing safely")

    @Slot()
    def on_media_error(self):
        error_text = self.media_player.errorString() or "Playback error"
        if self.playback_mode == "live":
            if self.current_youtube_channel() is not None:
                self.retry_nettv_with_compatible_format(error_text)
                self.status.setText(f"NetTV playback error:\n{error_text}")
                return
            self.recover_live_playback_failure(error_text)
            return
        self.status.setText(f"Playback error: {error_text}")

    @Slot(QMediaPlayer.MediaStatus)
    def on_nettv_media_status_changed(self, status):
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            if self.nettv_pending_play_after_seek:
                target = self.nettv_pending_seek_ms
                self.nettv_pending_seek_ms = 0
                self.nettv_pending_play_after_seek = False
                if target > 0:
                    self.nettv_player.setPosition(target)
                    QTimer.singleShot(120, self.nettv_player.play)
                else:
                    self.nettv_player.play()
            elif self.nettv_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self.nettv_player.play()
            if self.playback_mode == "live" and self.current_youtube_channel() is not None and self.live_stall_path:
                self.live_stall_last_position_ms = int(self.nettv_player.position())
                self.live_stall_last_advance_at = time.time()
                self.live_stall_checks_started_at = time.time()
                self.live_stall_timer.start()
            return

        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.nettv_loaded_entry_path = ""
            self.nettv_loaded_stream_url = ""
            self.nettv_last_frame = QPixmap()
            if self.current_youtube_channel() is not None:
                self.play_channel(with_transition=False, show_channel_overlay=False)
            return

        if status in (
            QMediaPlayer.MediaStatus.InvalidMedia,
            QMediaPlayer.MediaStatus.StalledMedia,
        ):
            if self.current_youtube_channel() is not None:
                self.retry_nettv_with_compatible_format("NetTV playback stalled or could not open this cached video.")

    @Slot()
    def on_nettv_media_error(self):
        if self.current_youtube_channel() is None:
            return
        error_text = self.nettv_player.errorString() or "NetTV playback error"
        self.retry_nettv_with_compatible_format(error_text)
        self.status.setText(f"NetTV playback error:\n{error_text}")

    @Slot(object)
    def on_nettv_video_frame_changed(self, frame):
        if not frame or not frame.isValid():
            return

        image = frame.toImage()
        if image.isNull():
            return

        pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            return

        visible_frame = pixmap_has_visible_content(pixmap)
        now = time.time()

        # NetTV rescue: if Qt is definitely playing and handing us frames, do
        # not let the brightness detector keep the channel on the standby slate
        # forever. Some YouTube downloads start with dark fades, black title
        # cards, or frames that macOS/Qt reports with very low luma even though
        # the video is actually moving. After playback has advanced, show the
        # frame and let the real video replace the slate naturally.
        playback_started = self.nettv_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        playback_position_ms = max(0, int(self.nettv_player.position()))
        waited_for_picture = self.nettv_waiting_started_at > 0 and (now - self.nettv_waiting_started_at) >= 1.5
        if not visible_frame and playback_started and (playback_position_ms >= 500 or waited_for_picture):
            visible_frame = True

        if visible_frame:
            self.nettv_last_frame = pixmap
            self.nettv_waiting_for_visible_frame = False
            self.nettv_visible_frame_seen = True
            self.nettv_black_frame_started_at = 0.0
            if self.current_youtube_channel() is not None:
                self.last_video_frame = pixmap
                self.video_window.video_surface.set_frame(pixmap)
                self.video_window.hide_nettv_status()
                self.update_guide_preview_frame_throttled(pixmap, mode="youtube")
            return

        if self.nettv_black_frame_started_at <= 0:
            self.nettv_black_frame_started_at = now
        black_duration = now - self.nettv_black_frame_started_at
        needs_standby = self.nettv_waiting_for_visible_frame or not self.nettv_visible_frame_seen or black_duration >= 1.25
        if self.current_youtube_channel() is not None and needs_standby:
            self.nettv_waiting_for_visible_frame = True
            if self.nettv_waiting_started_at <= 0:
                self.nettv_waiting_started_at = now
            if now - self.nettv_last_status_update_at >= 1.0 or not self.video_window.nettv_status_overlay.isVisible():
                self.nettv_last_status_update_at = now
                message = "The playlist is loaded, but this video has not produced a visible frame yet."
                self.nettv_current_message = message
                self.video_window.show_nettv_status(self.nettv_current_title or "NetTV", message)

    @Slot(object)
    def on_video_frame_changed(self, frame):
        if not frame or not frame.isValid():
            return

        image = frame.toImage()
        if image.isNull():
            return

        pixmap = QPixmap.fromImage(image)
        if not pixmap.isNull():
            if self.current_youtube_channel() is not None:
                visible_frame = pixmap_has_visible_content(pixmap)
                now = time.time()
                if visible_frame:
                    self.nettv_waiting_for_visible_frame = False
                    self.nettv_visible_frame_seen = True
                    self.nettv_black_frame_started_at = 0.0
                    self.video_window.hide_nettv_status()
                else:
                    if self.nettv_black_frame_started_at <= 0:
                        self.nettv_black_frame_started_at = now
                    black_duration = now - self.nettv_black_frame_started_at
                    needs_standby = self.nettv_waiting_for_visible_frame or not self.nettv_visible_frame_seen or black_duration >= 1.25
                    if needs_standby:
                        self.nettv_waiting_for_visible_frame = True
                        if self.nettv_waiting_started_at <= 0:
                            self.nettv_waiting_started_at = now
                        if now - self.nettv_last_status_update_at >= 1.0 or not self.video_window.nettv_status_overlay.isVisible():
                            self.nettv_last_status_update_at = now
                            message = "The playlist is loaded, but this video has not produced a visible frame yet."
                            self.nettv_current_message = message
                            self.video_window.show_nettv_status(self.nettv_current_title or "NetTV", message)
                        return
            self.last_video_frame = pixmap
            self.video_window.video_surface.set_frame(pixmap)
            if self.video_window.guide_overlay.isVisible():
                selected_channel = self.channels[self.guide_selection] if self.channels and 0 <= self.guide_selection < len(self.channels) else None
                selected_type = getattr(selected_channel, "channel_type", "media")
                if selected_type in ("weatherstar", "radiowave", "youtube") or self.current_weather_channel() is not None or self.current_radiowave_channel() is not None or self.current_youtube_channel() is not None:
                    if self.guide_preview_refresh_due():
                        self.refresh_guide()
                else:
                    self.video_window.guide_overlay.set_preview_frame(pixmap)

    @Slot()
    def up(self):
        if self.playback_mode == "ondemand":
            return
        if not self.channels:
            return
        self.current_channel = (self.current_channel + 1) % len(self.channels)
        self.play_channel()

    @Slot()
    def down(self):
        if self.playback_mode == "ondemand":
            return
        if not self.channels:
            return
        self.current_channel = (self.current_channel - 1) % len(self.channels)
        self.play_channel()

    def refresh_controls(self):
        has_channels = bool(self.channels)
        saved_catalog_ready = bool((self.app_settings.get("catalog_path") or "").strip()) and os.path.isdir((self.app_settings.get("catalog_path") or "").strip())
        weather_ready = bool(self.app_settings.get("weatherstar_enabled")) and bool((self.app_settings.get("weatherstar_location") or "").strip())
        radiowave_ready = bool(self.app_settings.get("radiowave_enabled"))
        youtube_ready = bool(self.app_settings.get("youtube_enabled")) and bool(youtube_source_url(self.app_settings.get("youtube_playlist_url", "")))
        special_only_ready = bool(self.app_settings.get("allow_empty_catalog_tv")) and bool(weather_ready or radiowave_ready or youtube_ready)
        self.watch_btn.setEnabled(has_channels or saved_catalog_ready or special_only_ready)
        self.library_summary.setText(
            f"{len(self.channels)} channel{'s' if len(self.channels) != 1 else ''} loaded"
            if has_channels else
            ("Companion-only TV ready" if special_only_ready else "No channels loaded")
        )
        if self.catalog_root:
            self.catalog_path_label.setText(self.catalog_root)

        if not has_channels:
            if self.app_settings.get("catalog_path"):
                self.status.setText("Saved catalog ready. Press Watch TV to load it, or Choose Catalog to switch libraries.")
            elif special_only_ready:
                self.status.setText("Companion-only TV is ready. Press Watch TV to test the cable system without local content.")
            else:
                self.status.setText(
                    "Choose a catalog, add optional local artwork/descriptions, then press Watch TV when you’re ready to go live."
                )

    @Slot()
    def apply_display_settings(self):
        skin_name = normalize_skin_name(self.skin_combo.currentText())
        theme_name = normalize_theme_for_skin(skin_name, self.theme_combo.currentText())
        self.video_window.configure_display(
            self.profile_combo.currentText(),
            theme_name,
            skin_name,
            self.guide_ui_scale,
        )
        self.app_settings["display_mode"] = self.profile_combo.currentText()
        self.app_settings["guide_theme"] = theme_name
        self.app_settings["guide_skin"] = skin_name
        self.app_settings["guide_ui_scale"] = self.guide_ui_scale
        self.setStyleSheet(build_startup_stylesheet(theme_name, skin_name))
        save_json_file(APP_SETTINGS_FILE, self.app_settings)
        self.preload_weather_if_configured()

    @Slot()
    def on_skin_changed(self):
        self.refresh_theme_combo_for_skin()
        self.apply_display_settings()

    @Slot(int)
    def adjust_ui_scale(self, direction):
        updated = clamp_guide_ui_scale(self.guide_ui_scale + (GUIDE_UI_SCALE_STEP * direction))
        if abs(updated - self.guide_ui_scale) < 0.001:
            self.video_window.ui_scale_overlay.show_scale(self.guide_ui_scale)
            return
        self.guide_ui_scale = updated
        self.app_settings["guide_ui_scale"] = self.guide_ui_scale
        self.setStyleSheet(build_startup_stylesheet(self.theme_combo.currentText(), self.skin_combo.currentText()))
        save_json_file(APP_SETTINGS_FILE, self.app_settings)
        self.video_window.configure_display(
            self.profile_combo.currentText(),
            self.theme_combo.currentText(),
            self.skin_combo.currentText(),
            self.guide_ui_scale,
        )
        self.video_window.ui_scale_overlay.show_scale(self.guide_ui_scale)
        if self.video_window.guide_overlay.isVisible():
            self.refresh_guide()
        if self.video_window.on_demand_overlay.isVisible():
            self.refresh_on_demand()
        if self.video_window.info_overlay.isVisible():
            self.refresh_info_banner()

    def handle_plus_shortcut(self):
        self.up()

    def handle_minus_shortcut(self):
        self.down()

    def handle_scale_up_shortcut(self):
        if self.video_window.guide_overlay.isVisible() or self.video_window.on_demand_overlay.isVisible() or self.video_window.info_overlay.isVisible():
            self.adjust_ui_scale(1)

    def handle_scale_down_shortcut(self):
        if self.video_window.guide_overlay.isVisible() or self.video_window.on_demand_overlay.isVisible() or self.video_window.info_overlay.isVisible():
            self.adjust_ui_scale(-1)

    @Slot(int)
    def step_skin(self, step):
        index = self.skin_combo.currentIndex()
        count = self.skin_combo.count()
        if count <= 0:
            return
        self.skin_combo.setCurrentIndex((index + step) % count)

    @Slot(int)
    def step_theme(self, step):
        index = self.theme_combo.currentIndex()
        count = self.theme_combo.count()
        if count <= 0:
            return
        self.theme_combo.setCurrentIndex((index + step) % count)

    @Slot(int)
    def step_profile(self, step):
        index = self.profile_combo.currentIndex()
        count = self.profile_combo.count()
        if count <= 0:
            return
        self.profile_combo.setCurrentIndex((index + step) % count)

    def get_program_metadata(self, path):
        if isinstance(path, str) and path.startswith("weatherstar://"):
            location = (self.app_settings.get("weatherstar_location") or "your area").strip() or "your area"
            title = os.path.basename(path.replace("weatherstar://", "")).replace("-", " ").title()
            return {
                "signature": stable_hash(path),
                "path": path,
                "media_type": "special",
                "timeline_title": "WeatherStar 4000+",
                "detail_title": f"WeatherStar 4000+ - {title}",
                "detail_summary": f"Local weather coverage for {location}.",
                "show_name": "WeatherStar 4000+",
                "match_key": "weatherstar-4000",
                "tmdb_matched": False,
            }
        if isinstance(path, str) and path.startswith("spotify://"):
            info = self.video_window.spotify_info if hasattr(self, "video_window") else {}
            title = (info.get("title") or "RadioWaveTV").strip()
            artist = (info.get("artist") or "").strip()
            album = (info.get("album") or "").strip()
            year = (info.get("year") or "").strip()
            source_label = "RadioWaveTV"
            summary_parts = [part for part in (artist, album, year) if part]
            if summary_parts:
                summary = " • ".join(summary_parts)
            else:
                summary = f"{source_label} music channel."
            return {
                "signature": stable_hash(path + title + artist + album + year),
                "path": path,
                "media_type": "special",
                "timeline_title": title,
                "detail_title": f"{title} - {artist}" if artist else title,
                "detail_summary": summary,
                "show_name": source_label,
                "match_key": "spotify-radio",
                "tmdb_matched": False,
            }
        if isinstance(path, str) and path.startswith("youtube://"):
            entry = self.find_youtube_entry_by_path(path)
            title = entry.get("title") or "NetTV"
            return {
                "signature": stable_hash(path + title),
                "path": path,
                "media_type": "special",
                "timeline_title": title,
                "detail_title": title,
                "detail_summary": "Playing from a user-supplied NetTV playlist.",
                "show_name": "NetTV",
                "match_key": "youtube-playlist",
                "tmdb_matched": False,
            }
        local = parse_local_media(path)
        signature = local_asset_signature(path, local)
        cached = self.tmdb_cache.get(path)
        if (
            cached
            and cached.get("signature") == signature
            and cached.get("cache_mode") == self.metadata_cache_mode()
        ):
            return cached

        metadata = self.resolve_program_metadata(path, allow_remote=False)
        self.tmdb_cache[path] = metadata
        return metadata

    def get_program_metadata_local(self, path):
        local = parse_local_media(path)
        signature = local_asset_signature(path, local)
        cached = self.tmdb_cache.get(path)
        if cached and cached.get("signature") == signature and cached.get("cache_mode") == self.metadata_cache_mode():
            return cached
        metadata = self.resolve_program_metadata(path, allow_remote=False)
        self.tmdb_cache[path] = metadata
        return metadata

    def resolve_program_metadata(self, path, allow_remote=False):
        metadata = build_local_media_metadata(path, duration=self.duration_cache.get(path))
        metadata["cache_mode"] = self.metadata_cache_mode()
        return metadata

    def resolve_tmdb_tv(self, local, override):
        if override and override.get("media_type") == "tv" and override.get("tmdb_id"):
            candidates = [{"id": override["tmdb_id"], "name": local["show_name"]}]
        else:
            response = self.tmdb_client.search_tv(local["show_name"])
            candidates = (response or {}).get("results", [])[:5]
            self.tmdb_review.setdefault("shows", {})[local["match_key"]] = {
                "title": local["show_name"],
                "media_type": "tv",
                "candidates": [
                    {"id": item.get("id"), "name": item.get("name"), "first_air_date": item.get("first_air_date")}
                    for item in candidates
                ],
            }
        if not candidates:
            return None

        best = max(
            candidates,
            key=lambda item: SequenceMatcher(None, normalize_title(local["show_name"]), normalize_title(item.get("name", ""))).ratio(),
        )
        season = local.get("season_number")
        episode = local.get("episode_number")
        if season is None or episode is None:
            return {
                "timeline_title": best.get("name", local["show_name"]),
                "detail_title": best.get("name", local["detail_title"]),
                "detail_summary": local["detail_summary"],
                "show_name": best.get("name", local["show_name"]),
                "tmdb_id": best.get("id"),
            }

        details = self.tmdb_client.tv_episode_details(best["id"], season, episode)
        if not details:
            return {
                "timeline_title": best.get("name", local["show_name"]),
                "detail_title": local["detail_title"],
                "detail_summary": local["detail_summary"],
                "show_name": best.get("name", local["show_name"]),
                "tmdb_id": best.get("id"),
            }

        episode_name = details.get("name") or local.get("episode_title") or local["detail_title"]
        overview = details.get("overview") or local["detail_summary"]
        series_name = best.get("name", local["show_name"])
        return {
            "timeline_title": series_name,
            "detail_title": f"{series_name} - S{season:02d}E{episode:02d} - {episode_name}",
            "detail_summary": overview,
            "show_name": series_name,
            "episode_title": episode_name,
            "tmdb_id": best.get("id"),
        }

    def resolve_tmdb_movie(self, local, override, lookup_key=None):
        if override and override.get("media_type") == "movie" and override.get("tmdb_id"):
            movie_id = override["tmdb_id"]
            details = self.tmdb_client.movie_details(movie_id)
            candidates = []
        else:
            response = self.tmdb_client.search_movie(local["show_name"])
            candidates = (response or {}).get("results", [])[:5]
            self.tmdb_review.setdefault("shows", {})[lookup_key or local["match_key"]] = {
                "title": local["show_name"],
                "media_type": "movie",
                "reason": "matched" if candidates else "no-match",
                "candidates": self.build_tmdb_movie_candidates(local["show_name"]),
            }
            best = max(
                candidates,
                key=lambda item: SequenceMatcher(None, normalize_title(local["show_name"]), normalize_title(item.get("title", ""))).ratio(),
                default=None,
            )
            if not best:
                return None
            details = self.tmdb_client.movie_details(best["id"])
        if not details:
            return None

        title = details.get("title") or local["show_name"]
        artwork_url = (details.get("poster_path") and f"https://image.tmdb.org/t/p/w500{details.get('poster_path')}") or ""
        artwork_path = cache_remote_artwork(artwork_url, f"tmdb-movie-{details.get('id')}") if artwork_url else ""
        return {
            "timeline_title": title,
            "detail_title": title,
            "detail_summary": details.get("overview") or local["detail_summary"],
            "show_name": title,
            "show_summary": details.get("overview") or local["detail_summary"],
            "artwork_path": artwork_path,
            "show_artwork_path": artwork_path,
            "year": extract_year_value(details.get("release_date", "")),
            "runtime_minutes": safe_int(details.get("runtime")),
            "metadata_status": "matched",
            "needs_attention": False,
            "attention_reason": "",
            "tmdb_id": details.get("id"),
        }

    def build_guide_rows(self, timeline_start=None):
        timeline_start = timeline_start or self.video_window.guide_overlay.timeline_start or self.video_window.guide_overlay.floor_to_half_hour(time.time())
        rows = []
        for index, channel in enumerate(self.channels):
            if getattr(channel, "channel_type", "media") == "weatherstar":
                info = channel.get_now_next()
                metadata = self.get_program_metadata(info["current_path"]) if info else {}
                rows.append({
                    "index": index,
                    "number": index + 1,
                    "name": channel.name,
                    "now_title": info["current_title"] if info else channel.name,
                    "now_time": time.strftime("%I:%M", time.localtime(info["current_start"])).lstrip("0") if info else "",
                    "next_title": "",
                    "next_time": "",
                    "slots": [{
                        "title": "Local Forecast",
                        "time": time.strftime("%I:%M", time.localtime(timeline_start)).lstrip("0"),
                        "start": timeline_start,
                        "end": timeline_start + (30 * 60 * 4),
                        "path": "weatherstar://local-forecast",
                    }],
                    "detail_slot_index": 0,
                    "detail_title": "WeatherStar 4000+",
                    "detail_path": "weatherstar://local-forecast",
                    "detail_is_live": True,
                    "detail_status": "ON NOW  •  ENTER tunes to the live channel feed",
                    "detail_time": "",
                    "detail_summary": f"Local weather coverage for {channel.location}. Retro mode {'on' if channel.retro else 'off'}.",
                    "summary": metadata.get("detail_summary", f"Local weather coverage for {channel.location}."),
                })
                continue
            if getattr(channel, "channel_type", "media") == "radiowave":
                info = channel.get_now_next()
                current_meta = channel.metadata_for(info["current_path"]) if info else {}
                detail_title = current_meta.get("title") or channel.name
                if getattr(channel, "empty_state", False):
                    detail_summary = current_meta.get("detail_summary") or RADIOWAVE_EMPTY_WARNING
                    slots = [{
                        "title": "Music Server Offline",
                        "time": time.strftime("%I:%M", time.localtime(timeline_start)).lstrip("0"),
                        "start": timeline_start,
                        "end": timeline_start + (30 * 60 * 4),
                        "path": RadioWaveChannel.EMPTY_PATH,
                    }]
                    detail_status = "ALERT  •  RadioWaveTV is waiting for music"
                else:
                    detail_summary_parts = [part for part in (current_meta.get("artist"), current_meta.get("album"), current_meta.get("year")) if part]
                    detail_summary = " • ".join(detail_summary_parts) if detail_summary_parts else "Local music channel."
                    slots = [{
                        "title": "RadioWaveTV Music Mix",
                        "time": time.strftime("%I:%M", time.localtime(timeline_start)).lstrip("0"),
                        "start": timeline_start,
                        "end": timeline_start + (30 * 60 * 4),
                        "path": info["current_path"] if info else "",
                    }]
                    detail_status = "ON NOW  •  RadioWaveTV music channel"
                rows.append({
                    "index": index,
                    "number": index + 1,
                    "name": channel.name,
                    "now_title": current_meta.get("title") or channel.name,
                    "now_time": time.strftime("%I:%M", time.localtime(info["current_start"])).lstrip("0") if info else "",
                    "next_title": "",
                    "next_time": "",
                    "slots": slots,
                    "detail_slot_index": 0,
                    "detail_title": detail_title,
                    "detail_path": info["current_path"] if info else "",
                    "detail_is_live": True,
                    "detail_status": detail_status,
                    "detail_time": (
                        f"{time.strftime('%I:%M', time.localtime(info['current_start'])).lstrip('0')} - "
                        f"{time.strftime('%I:%M', time.localtime(info['current_end'])).lstrip('0')}"
                    ) if info else "",
                    "detail_summary": detail_summary,
                    "summary": detail_summary,
                })
                continue
            programs = channel.get_programs_for_window(timeline_start, 10)
            info = channel.get_now_next()
            if not programs or not info:
                rows.append({
                    "index": index,
                    "number": index + 1,
                    "name": channel.name,
                    "now_title": channel.name,
                    "now_time": "",
                    "next_title": "",
                    "next_time": "",
                    "slots": [{
                        "title": "No Listings Available",
                        "time": time.strftime("%I:%M", time.localtime(timeline_start)).lstrip("0"),
                        "start": timeline_start,
                        "end": timeline_start + (30 * 60),
                        "path": "",
                    }],
                    "detail_slot_index": 0,
                    "detail_title": channel.name,
                    "detail_path": "",
                    "detail_is_live": False,
                    "detail_status": "No listings available",
                    "detail_time": "",
                    "detail_summary": f"{channel.name} is loaded, but no current schedule could be built.",
                    "summary": f"{channel.name} is loaded, but no current schedule could be built.",
                })
                continue

            slot_data = []
            for program in programs:
                metadata = self.get_program_metadata(program["path"])
                slot_data.append(
                    {
                        "title": metadata.get("timeline_title", program["title"]),
                        "time": time.strftime("%I:%M", time.localtime(program["start"])).lstrip("0"),
                        "start": program["start"],
                        "end": program["end"],
                        "path": program["path"],
                    }
                )

            detail_program = programs[0]
            detail_slot_index = 0
            for program in programs:
                if program["end"] > timeline_start:
                    detail_program = program
                    detail_slot_index = programs.index(program)
                    break
            detail_metadata = self.get_program_metadata(detail_program["path"])
            detail_is_live = detail_program["start"] <= time.time() < detail_program["end"]
            if detail_is_live:
                detail_status = "ON NOW  •  ENTER tunes to the live channel feed"
            else:
                detail_status = "UPCOMING LISTING  •  ENTER still tunes to what is airing now"

            rows.append({
                "index": index,
                "number": index + 1,
                "name": channel.name,
                "now_title": info["current_title"],
                "now_time": time.strftime("%I:%M", time.localtime(info["current_start"])).lstrip("0"),
                "next_title": info["next_title"],
                "next_time": time.strftime("%I:%M", time.localtime(info["current_end"])).lstrip("0"),
                "slots": slot_data,
                "detail_slot_index": detail_slot_index,
                "detail_title": detail_metadata.get("detail_title", detail_program["title"]),
                "detail_path": detail_program["path"],
                "detail_is_live": detail_is_live,
                "detail_status": detail_status,
                "detail_time": (
                    f"{time.strftime('%I:%M', time.localtime(detail_program['start'])).lstrip('0')} - "
                    f"{time.strftime('%I:%M', time.localtime(detail_program['end'])).lstrip('0')}"
                ),
                "detail_summary": detail_metadata.get("detail_summary") or self.build_guide_summary(channel.name, detail_program["title"]),
                "summary": self.build_guide_summary(channel.name, info["current_title"]),
            })
        return rows

    def build_guide_summary(self, channel_name, title):
        return (
            f"Currently airing on {channel_name}: {title}. "
            f"Showing local catalog metadata for now."
        )

    @Slot()
    def toggle_guide(self):
        if self.video_window.on_demand_overlay.isVisible():
            self.hide_on_demand()
            return
        if self.video_window.guide_overlay.isVisible():
            self.hide_guide()
        else:
            self.show_guide()

    def show_guide(self):
        if not self.channels:
            return
        self.hide_info_banner()
        self.hide_on_demand()
        if self.current_radiowave_channel() is not None:
            self.video_window.hide_radiowave_channel()
        self.guide_selection = self.current_channel
        self.video_window.guide_overlay.settings_open = False
        self.video_window.guide_overlay.settings_focus_index = 0
        self.video_window.guide_overlay.nav_focus = False
        self.video_window.guide_overlay.nav_index = 1
        self.refresh_guide(show=True)

    @Slot()
    def hide_guide(self, restore_special=True):
        self.video_window.guide_overlay.settings_open = False
        self.video_window.guide_overlay.nav_focus = False
        self.video_window.guide_overlay.hide()
        if restore_special and self.playback_mode == "live" and self.current_radiowave_channel() is not None and not self.video_window.info_overlay.isVisible():
            self.video_window.show_radiowave_channel(self.radiowave_state)

    def guide_preview_refresh_due(self, minimum_interval=GUIDE_PREVIEW_REFRESH_INTERVAL_SECONDS):
        now = time.time()
        if now - self.last_guide_preview_frame_update < minimum_interval:
            return False
        self.last_guide_preview_frame_update = now
        return True

    def update_guide_preview_frame_throttled(self, pixmap, mode="video", minimum_interval=GUIDE_PREVIEW_REFRESH_INTERVAL_SECONDS, force=False):
        if not self.video_window.guide_overlay.isVisible():
            return
        if force or self.guide_preview_refresh_due(minimum_interval):
            self.video_window.guide_overlay.set_preview_frame(pixmap, mode=mode)

    def refresh_guide(self, show=False):
        self.video_window.guide_overlay.settings_values = self.overlay_settings_values()
        rows = self.build_guide_rows(self.video_window.guide_overlay.timeline_start)
        if not rows:
            return
        selected_channel = self.channels[self.guide_selection] if self.channels and 0 <= self.guide_selection < len(self.channels) else None
        if getattr(selected_channel, "channel_type", "media") == "weatherstar":
            weather_preview = self.video_window.weather_preview_pixmap()
            self.video_window.guide_overlay.set_preview_frame(weather_preview if not weather_preview.isNull() else QPixmap(), mode="weatherstar")
        elif getattr(selected_channel, "channel_type", "media") == "radiowave":
            radiowave_preview = self.video_window.radiowave_preview_pixmap()
            self.video_window.guide_overlay.set_preview_frame(radiowave_preview if not radiowave_preview.isNull() else QPixmap(), mode="radiowave")
        elif getattr(selected_channel, "channel_type", "media") == "youtube":
            if self.current_youtube_channel() is not None and self.nettv_visible_frame_seen and not self.nettv_waiting_for_visible_frame and not self.last_video_frame.isNull():
                self.video_window.guide_overlay.set_preview_frame(self.last_video_frame, mode="youtube")
            else:
                title = self.nettv_current_title or getattr(selected_channel, "name", "NetTV")
                message = self.nettv_current_message or "Preparing your playlist feed..."
                self.video_window.guide_overlay.set_preview_frame(
                    make_nettv_standby_pixmap(QSize(640, 360), title, message),
                    mode="youtube",
                )
        else:
            self.video_window.guide_overlay.set_preview_frame(self.last_video_frame, mode="video")
        if show:
            self.video_window.guide_overlay.show_guide(rows, self.guide_selection)
        else:
            self.video_window.guide_overlay.update_guide(rows, self.guide_selection)

    @Slot()
    def guide_up(self):
        if not self.channels or not self.video_window.guide_overlay.isVisible():
            return
        if self.video_window.guide_overlay.settings_open:
            self.video_window.guide_overlay.settings_focus_index = (self.video_window.guide_overlay.settings_focus_index - 1) % self.in_app_menu_row_count()
            self.refresh_guide()
            return
        if self.video_window.guide_overlay.nav_focus:
            self.video_window.guide_overlay.nav_focus = False
            self.refresh_guide()
            return
        if self.guide_selection == 0:
            self.video_window.guide_overlay.nav_focus = True
        else:
            self.guide_selection = max(0, self.guide_selection - 1)
        self.refresh_guide()

    @Slot()
    def guide_down(self):
        if not self.channels or not self.video_window.guide_overlay.isVisible():
            return
        if self.video_window.guide_overlay.settings_open:
            self.video_window.guide_overlay.settings_focus_index = (self.video_window.guide_overlay.settings_focus_index + 1) % self.in_app_menu_row_count()
            self.refresh_guide()
            return
        if self.video_window.guide_overlay.nav_focus:
            self.refresh_guide()
        else:
            next_index = min(len(self.channels) - 1, self.guide_selection + 1)
            if next_index == self.guide_selection:
                self.video_window.guide_overlay.nav_focus = True
                self.video_window.guide_overlay.nav_index = 0
            else:
                self.guide_selection = next_index
        self.refresh_guide()

    @Slot()
    def guide_left(self):
        if not self.video_window.guide_overlay.isVisible():
            return
        if self.video_window.guide_overlay.settings_open:
            if self.video_window.guide_overlay.settings_focus_index == 0:
                self.step_skin(-1)
            elif self.video_window.guide_overlay.settings_focus_index == 1:
                self.step_theme(-1)
            elif self.video_window.guide_overlay.settings_focus_index == 2:
                self.step_profile(-1)
            return
        if self.video_window.guide_overlay.nav_focus:
            self.video_window.guide_overlay.nav_index = max(0, self.video_window.guide_overlay.nav_index - 1)
            self.refresh_guide()
            return
        minimum = self.video_window.guide_overlay.floor_to_half_hour(time.time())
        next_start = max(
            minimum,
            self.video_window.guide_overlay.timeline_start - (30 * 60),
        )
        if next_start == self.video_window.guide_overlay.timeline_start:
            self.video_window.guide_overlay.nav_focus = True
            self.video_window.guide_overlay.nav_index = 0
            self.refresh_guide()
            return
        self.video_window.guide_overlay.timeline_start = next_start
        self.refresh_guide()

    @Slot()
    def guide_right(self):
        if not self.video_window.guide_overlay.isVisible():
            return
        if self.video_window.guide_overlay.settings_open:
            if self.video_window.guide_overlay.settings_focus_index == 0:
                self.step_skin(1)
            elif self.video_window.guide_overlay.settings_focus_index == 1:
                self.step_theme(1)
            elif self.video_window.guide_overlay.settings_focus_index == 2:
                self.step_profile(1)
            return
        if self.video_window.guide_overlay.nav_focus:
            self.video_window.guide_overlay.nav_index = min(3, self.video_window.guide_overlay.nav_index + 1)
            self.refresh_guide()
            return
        self.video_window.guide_overlay.timeline_start += 30 * 60
        self.refresh_guide()

    @Slot()
    def guide_select(self):
        if not self.channels or not self.video_window.guide_overlay.isVisible():
            return
        if self.video_window.guide_overlay.settings_open:
            if self.video_window.guide_overlay.settings_focus_index == self.in_app_menu_close_index():
                self.video_window.guide_overlay.settings_open = False
                self.refresh_guide()
                return
            if self.handle_in_app_menu_toggle(self.video_window.guide_overlay.settings_focus_index):
                self.refresh_guide()
                return
            self.video_window.guide_overlay.settings_open = False
            self.refresh_guide()
            return
        if self.video_window.guide_overlay.nav_focus:
            self.activate_universal_nav("guide", self.video_window.guide_overlay.nav_index)
            return
        if self.current_channel == self.guide_selection:
            self.hide_guide()
            return
        self.current_channel = self.guide_selection
        self.hide_guide(restore_special=False)
        self.play_channel(with_transition=True, show_channel_overlay=True)

    @Slot()
    def toggle_guide_settings(self):
        if not self.video_window.guide_overlay.isVisible():
            return
        if not self.app_settings.get("dev_menu_enabled", True):
            self.status.setText("The in-app dev menu is disabled on the main screen.")
            return
        self.video_window.guide_overlay.settings_open = not self.video_window.guide_overlay.settings_open
        self.refresh_guide()

    @Slot()
    def toggle_on_demand_settings(self):
        if not self.video_window.on_demand_overlay.isVisible():
            return
        if not self.app_settings.get("dev_menu_enabled", True):
            self.status.setText("The in-app dev menu is disabled on the main screen.")
            return
        self.on_demand_settings_open = not self.on_demand_settings_open
        self.on_demand_nav_focused = False
        if self.on_demand_settings_open:
            self.on_demand_settings_focus_index = max(0, min(self.on_demand_settings_focus_index, self.in_app_menu_close_index()))
        self.refresh_on_demand()

    @Slot()
    def close_on_demand_settings(self):
        if not self.video_window.on_demand_overlay.isVisible():
            return
        if not self.on_demand_settings_open:
            return
        self.on_demand_settings_open = False
        self.refresh_on_demand()

    @Slot(int, int)
    def open_on_demand_home_card(self, section_index, item_index):
        def log_return(reason, **fields):
            self.log_vault_select("open_home_card_return", reason=reason, **fields)
        if not self.video_window.on_demand_overlay.isVisible():
            log_return("overlay_not_visible", section_index=section_index, item_index=item_index)
            return
        sections = self.on_demand_render_sections or self.build_on_demand_home_sections()
        self.log_vault_select(
            "open_home_card_start",
            incoming_section_index=section_index,
            incoming_item_index=item_index,
            rebuilt_section_count=len(sections),
        )
        if not sections:
            log_return("no_sections", section_index=section_index, item_index=item_index)
            return
        self.on_demand_settings_open = False
        self.on_demand_nav_focused = False
        self.on_demand_section_index = max(0, min(section_index, len(sections) - 1))
        section = sections[self.on_demand_section_index]
        self.log_vault_select(
            "open_home_card_section",
            resolved_section_index=self.on_demand_section_index,
            resolved_section_key=section.get("key", ""),
            resolved_section_title=section.get("title", ""),
            section_item_count=len(section.get("items", [])),
        )
        if not section.get("items"):
            log_return("section_has_no_items", section_index=self.on_demand_section_index, section_key=section.get("key", ""))
            self.refresh_on_demand()
            return
        clamped_item = max(0, min(item_index, len(section["items"]) - 1))
        self.on_demand_section_item_indices[self.on_demand_section_index] = clamped_item
        card = section["items"][clamped_item]
        self.log_vault_select(
            "open_home_card_resolved",
            clamped_item_index=clamped_item,
            card_title=card.get("title", ""),
            card_type=card.get("type", ""),
            card_channel_index=card.get("channel_index"),
            card_group_index=card.get("group_index"),
        )
        if card.get("type") == "resume":
            channel, group, _, item_idx, item = self.find_on_demand_item_by_path(card.get("path"))
            if channel and group and item:
                channel_index = next((idx for idx, entry in enumerate(self.on_demand_catalog) if entry is channel), 0)
                group_index = next((idx for idx, entry in enumerate(channel.get("groups", [])) if entry is group), 0)
                self.open_on_demand_group(channel_index, group_index, item_idx, focus="episodes")
            else:
                log_return("resume_lookup_failed", card_title=card.get("title", ""), path=card.get("path", ""))
                self.status.setText("That resume item could not be opened in the Vault.")
            self.refresh_on_demand()
            return

        channel_index = card.get("channel_index")
        section_key = str(section.get("key", ""))
        if channel_index is None and section_key.startswith("channel-"):
            try:
                channel_index = int(section_key.split("-", 1)[1])
            except ValueError:
                channel_index = None
        if channel_index is None or not (0 <= int(channel_index) < len(self.on_demand_catalog)):
            log_return(
                "invalid_channel_index",
                channel_index=channel_index,
                card_title=card.get("title", ""),
                catalog_len=len(self.on_demand_catalog),
            )
            self.status.setText("That Vault entry could not be opened cleanly.")
            self.refresh_on_demand()
            return
        channel_index = int(channel_index)
        channel = self.on_demand_catalog[channel_index]
        group_index = card.get("group_index")
        if group_index is None or not (0 <= int(group_index) < len(channel.get("groups", []))):
            group_index = clamped_item
        if not (0 <= int(group_index) < len(channel.get("groups", []))):
            log_return(
                "invalid_group_index",
                channel_index=channel_index,
                group_index=group_index,
                channel_group_count=len(channel.get("groups", [])),
                card_title=card.get("title", ""),
            )
            self.status.setText("That Vault group is no longer available.")
            self.refresh_on_demand()
            return
        self.log_vault_select(
            "open_home_card_opening_group",
            channel_index=channel_index,
            group_index=int(group_index),
            card_title=card.get("title", ""),
        )
        try:
            self.open_on_demand_group(channel_index, int(group_index), 0, focus="actions")
            self.log_vault_select(
                "open_home_card_group_opened",
                channel_index=channel_index,
                group_index=int(group_index),
                resulting_view=self.on_demand_view,
                detail_focus=self.on_demand_detail_focus,
            )
            self.refresh_on_demand()
        except Exception as exc:
            self.log_vault_select(
                "open_home_card_exception",
                channel_index=channel_index,
                group_index=int(group_index),
                error=repr(exc),
                traceback=traceback.format_exc(),
            )
            self.status.setText("That Vault group hit an error while opening.")
            self.refresh_on_demand()

    def ensure_on_demand_focus_state(self):
        self.on_demand_nav_index = max(0, min(int(self.on_demand_nav_index), 3))
        self.on_demand_settings_focus_index = max(0, min(int(self.on_demand_settings_focus_index), self.in_app_menu_close_index()))
        sections = self.build_on_demand_home_sections()
        if not sections:
            self.on_demand_section_index = 0
            self.on_demand_section_item_indices = {}
            self.on_demand_nav_focused = False
            self.on_demand_settings_open = False
            return sections

        self.on_demand_section_index = max(0, min(int(self.on_demand_section_index), len(sections) - 1))
        valid_section_keys = set(range(len(sections)))
        for key in list(self.on_demand_section_item_indices.keys()):
            if key not in valid_section_keys:
                self.on_demand_section_item_indices.pop(key, None)
        for idx, section in enumerate(sections):
            items = section.get("items", [])
            current = int(self.on_demand_section_item_indices.get(idx, 0))
            self.on_demand_section_item_indices[idx] = max(0, min(current, max(0, len(items) - 1))) if items else 0

        if self.on_demand_view != "home":
            channel = self.current_on_demand_channel()
            group = self.current_on_demand_group()
            if (not channel or not group) and self.repair_on_demand_open_request():
                channel = self.current_on_demand_channel()
                group = self.current_on_demand_group()
            if not channel or not group:
                self.log_vault_select(
                    "ensure_focus_reset_home",
                    channel_available=bool(channel),
                    group_available=bool(group),
                    channel_index=self.on_demand_channel_index,
                    group_index=self.on_demand_group_index,
                    last_open_request=self.on_demand_last_open_request or {},
                )
                self.on_demand_view = "home"
                self.on_demand_nav_focused = False
                self.on_demand_settings_open = False
                return sections
            actions_count = 2
            self.on_demand_action_index = max(0, min(int(self.on_demand_action_index), actions_count - 1))
            seasons = self.build_on_demand_seasons(group)
            if seasons:
                self.on_demand_season_index = max(0, min(int(self.on_demand_season_index), len(seasons) - 1))
                indices = seasons[self.on_demand_season_index]["item_indices"]
                if indices:
                    if self.on_demand_item_index not in indices:
                        self.on_demand_item_index = indices[0]
            else:
                self.on_demand_season_index = 0
                items = group.get("items", [])
                if items:
                    self.on_demand_item_index = max(0, min(int(self.on_demand_item_index), len(items) - 1))
        return sections

    def current_on_demand_channel(self):
        if not self.on_demand_catalog:
            return None
        self.on_demand_channel_index = max(0, min(self.on_demand_channel_index, len(self.on_demand_catalog) - 1))
        return self.on_demand_catalog[self.on_demand_channel_index]

    def current_on_demand_group(self):
        channel = self.current_on_demand_channel()
        if not channel or not channel.get("groups"):
            return None
        self.on_demand_group_index = max(0, min(self.on_demand_group_index, len(channel["groups"]) - 1))
        return channel["groups"][self.on_demand_group_index]

    def repair_on_demand_open_request(self, request=None):
        request = request or self.on_demand_last_open_request or {}
        if not request or not self.on_demand_catalog:
            return False

        channel_index = request.get("channel_index")
        group_index = request.get("group_index")
        if (
            isinstance(channel_index, int)
            and 0 <= channel_index < len(self.on_demand_catalog)
            and isinstance(group_index, int)
            and 0 <= group_index < len(self.on_demand_catalog[channel_index].get("groups", []))
        ):
            self.on_demand_channel_index = channel_index
            self.on_demand_group_index = group_index
            self.on_demand_item_index = max(0, int(request.get("item_index", 0) or 0))
            return True

        channel_label = normalize_title(request.get("channel_label", ""))
        group_label = normalize_title(request.get("group_label", ""))
        first_path = request.get("first_path", "")
        for resolved_channel_index, channel in enumerate(self.on_demand_catalog):
            groups = channel.get("groups", [])
            if channel_label and normalize_title(channel.get("label", "")) != channel_label:
                possible_match = any(
                    normalize_title(group.get("label", "")) == group_label
                    or (first_path and any(item.get("path") == first_path for item in group.get("items", [])))
                    for group in groups
                )
                if not possible_match:
                    continue
            for resolved_group_index, group in enumerate(groups):
                title_match = group_label and normalize_title(group.get("label", "")) == group_label
                path_match = first_path and any(item.get("path") == first_path for item in group.get("items", []))
                if not title_match and not path_match:
                    continue
                self.on_demand_channel_index = resolved_channel_index
                self.on_demand_group_index = resolved_group_index
                item_index = max(0, int(request.get("item_index", 0) or 0))
                items = group.get("items", [])
                if first_path:
                    for idx, item in enumerate(items):
                        if item.get("path") == first_path:
                            item_index = idx
                            break
                if items:
                    item_index = max(0, min(item_index, len(items) - 1))
                self.on_demand_item_index = item_index
                self.log_vault_select(
                    "repair_open_request",
                    resolved_channel_index=resolved_channel_index,
                    resolved_group_index=resolved_group_index,
                    resolved_group_title=group.get("label", ""),
                    resolved_item_index=item_index,
                )
                return True
        return False

    def current_on_demand_item(self):
        group = self.current_on_demand_group()
        if not group or not group.get("items"):
            return None
        self.on_demand_item_index = max(0, min(self.on_demand_item_index, len(group["items"]) - 1))
        return group["items"][self.on_demand_item_index]

    def group_resume_entry(self, group):
        entries = self.resume_state.get("entries", {})
        best = None
        for item in group.get("items", []):
            entry = entries.get(item.get("path"))
            if not entry or int(entry.get("position_ms", 0)) <= 0:
                continue
            if best is None or float(entry.get("last_played", 0)) > float(best.get("last_played", 0)):
                best = entry
        return best

    def describe_on_demand_group(self, channel, group):
        items = group.get("items", [])
        if not items:
            return ""
        media_type = "tv" if any(item.get("media_type") == "tv" for item in items) else "movie"
        year = (group.get("year") or "").strip()
        if media_type == "tv":
            season_numbers = sorted(
                {
                    int(item.get("season_number"))
                    for item in items
                    if item.get("season_number") is not None
                }
            )
            season_count = len(season_numbers) or 1
            episode_count = len(items)
            parts = [
                channel["label"],
                f"{season_count} season{'s' if season_count != 1 else ''}",
                f"{episode_count} episode{'s' if episode_count != 1 else ''}",
            ]
            if year:
                parts.append(year)
            return "  •  ".join(parts)
        parts = [channel["label"], f"{len(items)} title{'s' if len(items) != 1 else ''}"]
        if year:
            parts.append(year)
        return "  •  ".join(parts)

    def build_home_card_for_group(self, channel_index, group_index):
        channel = self.on_demand_catalog[channel_index]
        group = channel["groups"][group_index]
        items = group.get("items", [])
        first_item = items[0] if items else {}
        resume_entry = self.group_resume_entry(group)
        progress = 0.0
        progress_label = ""
        if resume_entry:
            duration_ms = max(1, int(resume_entry.get("duration_ms", 0) or 1))
            position_ms = max(0, int(resume_entry.get("position_ms", 0) or 0))
            progress = max(0.0, min(1.0, position_ms / duration_ms))
            progress_label = f"{format_resume_time(max(0, duration_ms - position_ms))} Left"
        media_type = "tv" if any(item.get("media_type") == "tv" for item in items) else "movie"
        summary = ""
        for item in items:
            summary = (item.get("summary") or "").strip()
            if summary:
                break
        if not summary:
            summary = (
                "Jump back into the next episode."
                if media_type == "tv"
                else "Start this feature from your local library."
            )
        return {
            "type": "group",
            "channel_index": channel_index,
            "group_index": group_index,
            "item_index": 0,
            "title": group["label"],
            "subtitle": self.describe_on_demand_group(channel, group),
            "summary": summary,
            "badge": "TV SHOW" if media_type == "tv" else "MOVIE",
            "meta": "Series" if media_type == "tv" else "Feature",
            "progress": progress,
            "progress_label": progress_label,
            "media_type": media_type,
            "episode_label": first_item.get("label", ""),
            "added_at": float(group.get("added_at", 0.0) or 0.0),
            "artwork_path": group.get("artwork_path") or first_item.get("artwork_path", ""),
            "hero_artwork_path": group.get("hero_artwork_path") or group.get("artwork_path") or first_item.get("hero_artwork_path", "") or first_item.get("artwork_path", ""),
            "clearlogo_path": group.get("clearlogo_path") or first_item.get("clearlogo_path", ""),
        }

    def build_attention_items(self):
        return []

    def build_on_demand_home_sections(self):
        sections = []
        resume_items = self.build_resume_items()
        if resume_items:
            sections.append(
                {
                    "key": "continue",
                    "title": "Continue Watching",
                    "subtitle": "Jump back into anything you left mid-stream.",
                    "items": [
                        {
                            "type": "resume",
                            "path": item["path"],
                            "title": item["show_name"],
                            "subtitle": item["detail_title"],
                            "summary": item.get("summary") or "Resume right where you left off.",
                            "badge": "CONTINUE",
                            "meta": item["meta"],
                            "progress": max(
                                0.0,
                                min(
                                    1.0,
                                    int(item.get("position_ms", 0))
                                    / max(1, int(self.resume_state.get("entries", {}).get(item["path"], {}).get("duration_ms", 1))),
                                ),
                            ),
                            "progress_label": (
                                f"{format_resume_time(int(item.get('remaining_ms', 0)))} Left"
                                if int(item.get("remaining_ms", 0)) > 0
                                else ""
                            ),
                            "artwork_path": item.get("artwork_path", ""),
                        }
                        for item in resume_items[:10]
                    ],
                }
            )

        for channel_index, channel in enumerate(self.on_demand_catalog):
            cards = [
                self.build_home_card_for_group(channel_index, group_index)
                for group_index, _group in enumerate(channel.get("groups", []))
            ]
            if not cards:
                continue
            sections.append(
                {
                    "key": f"channel-{channel_index}",
                    "title": channel["label"],
                    "subtitle": f"Channel {channel['number']}  •  {len(cards)} collection{'s' if len(cards) != 1 else ''}",
                    "items": cards,
                }
            )

        if sections:
            self.on_demand_section_index = max(0, min(self.on_demand_section_index, len(sections) - 1))
            for idx, section in enumerate(sections):
                current = self.on_demand_section_item_indices.get(idx, 0)
                self.on_demand_section_item_indices[idx] = max(0, min(current, len(section["items"]) - 1))
        else:
            self.on_demand_section_index = 0
            self.on_demand_section_item_indices = {}
        return sections

    def build_on_demand_seasons(self, group):
        items = group.get("items", []) if group else []
        seasons = []
        season_map = {}
        contains_tv = any(item.get("media_type") == "tv" for item in items)
        for idx, item in enumerate(items):
            raw_number = item.get("season_number")
            season_number = int(raw_number) if raw_number is not None else 1
            section_label = (item.get("section_label") or item.get("season_label") or "").strip()
            if not section_label:
                section_label = "Specials" if season_number == 0 else f"Season {season_number}"
            section_key = normalize_title(section_label) or f"section-{season_number}"
            if section_key not in season_map:
                season_map[section_key] = {
                    "label": section_label,
                    "season_number": season_number,
                    "item_indices": [],
                    "sort_key": (
                        0 if section_label.casefold().startswith("s") and any(ch.isdigit() for ch in section_label) else
                        1 if section_label == "Specials" else
                        2 if section_label == "Movies" else
                        3
                    ),
                }
                seasons.append(season_map[section_key])
            elif section_label and season_map[section_key]["label"].startswith("Season "):
                season_map[section_key]["label"] = section_label
            season_map[section_key]["item_indices"].append(idx)
        if not seasons and items:
            seasons = [{
                "label": "Season 1" if contains_tv else "Collection",
                "season_number": 1,
                "item_indices": list(range(len(items))),
                "sort_key": 0 if contains_tv else 3,
            }]
        seasons.sort(key=lambda item: (item.get("sort_key", 99), item["season_number"], normalize_title(item["label"])))
        return seasons

    def current_live_program(self):
        if not self.channels:
            return None
        channel = self.channels[self.current_channel]
        if getattr(channel, "channel_type", "media") == "weatherstar":
            info = channel.get_now_next()
            if not info:
                return None
            now = time.time()
            duration = max(1.0, info["current_end"] - info["current_start"])
            elapsed = max(0.0, min(duration, now - info["current_start"]))
            remaining = max(0.0, info["current_end"] - now)
            metadata = self.get_program_metadata(info["current_path"])
            return {
                "channel_number": self.current_channel + 1,
                "channel_name": channel.name,
                "path": info["current_path"],
                "title": metadata.get("detail_title", info["current_title"]),
                "show_name": metadata.get("show_name", info["current_title"]),
                "summary": f"Local weather coverage for {channel.location}. Retro mode {'on' if channel.retro else 'off'}.",
                "start": info["current_start"],
                "end": info["current_end"],
                "elapsed": elapsed,
                "remaining": remaining,
                "duration": duration,
                "progress": elapsed / duration,
            }
        if getattr(channel, "channel_type", "media") == "radiowave":
            path = self.radiowave_current_path
            if not path:
                path, _ = channel.get_current()
            metadata = channel.metadata_for(path) if path else {}
            duration = max(1.0, (self.radiowave_state.get("duration_ms") or 0) / 1000.0) if self.radiowave_state.get("duration_ms") else max(1.0, metadata.get("duration", 0))
            elapsed = max(0.0, (self.radiowave_state.get("progress_ms") or 0) / 1000.0)
            remaining = max(0.0, duration - elapsed)
            title = (metadata.get("title") or self.radiowave_state.get("title") or channel.name).strip() or channel.name
            artist = (metadata.get("artist") or self.radiowave_state.get("artist") or "").strip()
            album = (metadata.get("album") or self.radiowave_state.get("album") or "").strip()
            year = (metadata.get("year") or self.radiowave_state.get("year") or "").strip()
            if getattr(channel, "empty_state", False) or path == RadioWaveChannel.EMPTY_PATH:
                summary = metadata.get("detail_summary") or album or "RadioWaveTV is waiting for music."
            else:
                summary = " • ".join(part for part in (artist, album, year) if part) or "RadioWaveTV music channel."
            return {
                "channel_number": self.current_channel + 1,
                "channel_name": channel.name,
                "path": path or "",
                "title": title if getattr(channel, "empty_state", False) or path == RadioWaveChannel.EMPTY_PATH else (f"{title} - {artist}" if artist else title),
                "show_name": channel.name,
                "summary": summary,
                "start": time.time() - elapsed,
                "end": time.time() + remaining,
                "elapsed": elapsed,
                "remaining": remaining,
                "duration": duration,
                "progress": max(0.0, min(1.0, elapsed / duration)),
            }
        if getattr(channel, "channel_type", "media") == "youtube":
            info = channel.get_now_next()
            entry = dict(self.nettv_playing_entry or {})
            if not entry and info:
                current_entry = info.get("current_entry", {}) if isinstance(info.get("current_entry"), dict) else {}
                entry = dict(current_entry.get("youtube_entry") or {})
                entry.setdefault("path", info.get("current_path", ""))
                entry.setdefault("title", info.get("current_title", "NetTV"))
                entry.setdefault("duration", max(1.0, info.get("current_end", time.time()) - info.get("current_start", time.time())))
            if not entry and not info:
                return None
            path = entry.get("path") or (info or {}).get("current_path", "")
            title = (entry.get("title") or (info or {}).get("current_title") or channel.name).strip() or channel.name
            player_duration = max(0, int(self.nettv_player.duration()))
            player_position = max(0, int(self.nettv_player.position()))
            duration = max(1.0, (player_duration / 1000.0) if player_duration > 0 else float(entry.get("duration") or 0) or ((info or {}).get("current_end", time.time() + 1) - (info or {}).get("current_start", time.time())))
            if self.nettv_playing_entry:
                elapsed = max(0.0, min(duration, player_position / 1000.0 if player_position > 0 else self.nettv_playing_offset + max(0.0, time.time() - self.nettv_playing_started_at)))
            elif info:
                elapsed = max(0.0, min(duration, time.time() - info["current_start"]))
            else:
                elapsed = 0.0
            remaining = max(0.0, duration - elapsed)
            summary = "Playing from a user-supplied NetTV playlist."
            if self.nettv_waiting_for_visible_frame:
                summary = self.nettv_current_message or "NetTV is preparing this playlist video."
            return {
                "channel_number": self.current_channel + 1,
                "channel_name": channel.name,
                "path": path,
                "title": title,
                "show_name": channel.name,
                "summary": summary,
                "start": time.time() - elapsed,
                "end": time.time() + remaining,
                "elapsed": elapsed,
                "remaining": remaining,
                "duration": duration,
                "progress": max(0.0, min(1.0, elapsed / duration)),
            }
        info = channel.get_now_next()
        if not info:
            return None
        metadata = self.get_program_metadata(info["current_path"])
        now = time.time()
        duration = max(1.0, info["current_end"] - info["current_start"])
        elapsed = max(0.0, min(duration, now - info["current_start"]))
        remaining = max(0.0, info["current_end"] - now)
        current_entry = info.get("current_entry", {}) if isinstance(info.get("current_entry"), dict) else {}
        if current_entry.get("is_commercial") or current_entry.get("kind") in {"commercial", "promo", "bumper", "station_id"}:
            parent_path = schedule_entry_user_path(current_entry, info["current_path"])
            parent_title = schedule_entry_user_title(current_entry, info["current_title"], parent_path)
            parent_show_name = current_entry.get("parent_show_name") or metadata.get("show_name", parent_title)
            parent_summary = schedule_entry_user_summary(current_entry, metadata.get("detail_summary") or self.build_guide_summary(channel.name, parent_title))
            return {
                "channel_number": self.current_channel + 1,
                "channel_name": channel.name,
                "path": parent_path,
                "title": parent_title,
                "show_name": parent_show_name,
                "summary": parent_summary,
                "start": info["current_start"],
                "end": info["current_end"],
                "elapsed": elapsed,
                "remaining": remaining,
                "duration": duration,
                "progress": elapsed / duration,
            }
        return {
            "channel_number": self.current_channel + 1,
            "channel_name": channel.name,
            "path": info["current_path"],
            "title": metadata.get("detail_title", info["current_title"]),
            "show_name": metadata.get("show_name", info["current_title"]),
            "summary": metadata.get("detail_summary") or self.build_guide_summary(channel.name, info["current_title"]),
            "start": info["current_start"],
            "end": info["current_end"],
            "elapsed": elapsed,
            "remaining": remaining,
            "duration": duration,
            "progress": elapsed / duration,
        }

    def current_weather_channel(self):
        if not self.channels:
            return None
        channel = self.channels[self.current_channel]
        if getattr(channel, "channel_type", "media") == "weatherstar":
            return channel
        return None

    def current_radiowave_channel(self):
        if not self.channels:
            return None
        channel = self.channels[self.current_channel]
        if getattr(channel, "channel_type", "media") == "radiowave":
            return channel
        return None

    def current_youtube_channel(self):
        if not self.channels:
            return None
        channel = self.channels[self.current_channel]
        if getattr(channel, "channel_type", "media") == "youtube":
            return channel
        return None

    def current_on_demand_program(self):
        if self.playback_mode != "ondemand" or not self.current_on_demand_path:
            return None
        path = self.current_on_demand_path
        metadata = self.get_program_metadata(path)
        duration_ms = max(0, int(self.media_player.duration()))
        position_ms = max(0, int(self.media_player.position()))
        duration_s = max(1.0, duration_ms / 1000.0) if duration_ms > 0 else max(1.0, metadata.get("duration", 0))
        position_s = max(0.0, position_ms / 1000.0)
        remaining_s = max(0.0, duration_s - position_s)

        channel_name = ""
        channel_number = 0
        for index, channel in enumerate(self.channels):
            if path in channel.shows:
                channel_name = channel.name
                channel_number = index + 1
                break

        return {
            "channel_number": channel_number,
            "channel_name": channel_name or "On Demand",
            "path": path,
            "title": metadata.get("detail_title", format_program_title(path)),
            "show_name": metadata.get("show_name", format_program_title(path)),
            "summary": metadata.get("detail_summary") or f"On Demand playback from your {APP_NAME} library.",
            "start": None,
            "end": None,
            "elapsed": position_s,
            "remaining": remaining_s,
            "duration": duration_s,
            "progress": max(0.0, min(1.0, position_s / duration_s)),
        }

    def build_live_info_state(self):
        program = self.current_live_program()
        if not program:
            return {}
        actions = ["VIEW SHOW VAULT"]
        current_channel = self.channels[self.current_channel] if self.channels and 0 <= self.current_channel < len(self.channels) else None
        if getattr(current_channel, "channel_type", "media") in ("weatherstar", "radiowave", "youtube"):
            actions = []
        return {
            "header": "PROGRAM INFO",
            "channel_line": f"CH {program['channel_number']:02d}  •  {program['channel_name']}",
            "time_line": format_clock_range(program["start"], program["end"]),
            "remaining_line": f"{format_resume_time(int(program['remaining'] * 1000))} remaining",
            "title": program["title"],
            "summary": program["summary"],
            "progress": program["progress"],
            "actions": actions,
            "is_on_demand": False,
            "action_index": self.live_info_action_index,
            "nav_focused": self.live_info_nav_focused,
            "nav_index": self.live_info_nav_index,
            "settings_focus_index": self.live_info_settings_focus_index,
            "settings_values": self.overlay_settings_values(),
        }

    def build_on_demand_info_state(self):
        program = self.current_on_demand_program()
        if not program:
            return {}
        channel_line = program["channel_name"]
        if program["channel_number"]:
            channel_line = f"CH {program['channel_number']:02d}  •  {program['channel_name']}"
        return {
            "header": "PROGRAM INFO",
            "channel_line": channel_line,
            "time_line": "On Demand Playback",
            "remaining_line": f"{format_resume_time(int(program['remaining'] * 1000))} remaining",
            "title": program["title"],
            "summary": program["summary"],
            "progress": program["progress"],
            "actions": ["START FROM BEGINNING"],
            "is_on_demand": True,
            "action_index": self.live_info_action_index,
            "nav_focused": self.live_info_nav_focused,
            "nav_index": self.live_info_nav_index,
            "settings_focus_index": self.live_info_settings_focus_index,
            "settings_values": self.overlay_settings_values(),
        }

    def build_info_state(self):
        if self.playback_mode == "ondemand":
            return self.build_on_demand_info_state()
        return self.build_live_info_state()

    def current_info_actions(self):
        return self.build_info_state().get("actions", [])

    def info_nav_button_count(self):
        return 5 if self.playback_mode == "ondemand" else 4

    def activate_universal_nav(self, source, index):
        if source == "vault":
            if index == 0:
                self.on_demand_nav_focused = False
                if self.on_demand_settings_open:
                    self.on_demand_settings_open = False
                    self.refresh_on_demand()
                elif self.on_demand_view == "home":
                    self.hide_on_demand()
                else:
                    self.on_demand_view = "home"
                    self.refresh_on_demand()
                return
            index -= 1
        if source == "info":
            if index == 0:
                self.hide_info_banner()
                return
            index -= 1
        if source == "guide":
            if index == 0:
                self.hide_guide()
                return
            index -= 1
        if index == 0:
            if not self.app_settings.get("dev_menu_enabled", True):
                self.status.setText("The in-app dev menu is disabled on the main screen.")
                return
            if source == "vault":
                self.on_demand_settings_open = True
                self.on_demand_nav_focused = False
                self.refresh_on_demand()
                return
            if source == "info":
                self.live_info_settings_open = True
                self.live_info_nav_focused = False
                self.refresh_info_banner()
                return
            self.video_window.guide_overlay.settings_open = True
            self.video_window.guide_overlay.nav_focus = False
            self.refresh_guide()
            return
        if index == 1:
            self.hide_info_banner()
            self.show_guide()
            self.video_window.guide_overlay.settings_open = False
            self.video_window.guide_overlay.nav_focus = False
            self.video_window.guide_overlay.timeline_start = self.video_window.guide_overlay.floor_to_half_hour(time.time())
            self.refresh_guide()
            return
        self.hide_guide()
        self.hide_info_banner()
        self.show_on_demand()

    @Slot()
    def toggle_info_banner(self):
        if self.playback_mode == "live" and not self.channels:
            return
        if self.video_window.guide_overlay.isVisible() or self.video_window.on_demand_overlay.isVisible():
            return
        if self.video_window.info_overlay.isVisible():
            self.hide_info_banner()
            return
        self.live_info_action_index = -1
        self.live_info_nav_focused = False
        self.live_info_nav_index = 1
        self.live_info_settings_open = False
        self.live_info_settings_focus_index = 0
        state = self.build_info_state()
        if not state:
            return
        self.video_window.next_up_overlay.hide()
        self.video_window.transport_overlay.hide()
        self.video_window.info_overlay.show_banner(state)
        if self.current_youtube_channel() is not None and self.nettv_waiting_for_visible_frame:
            self.video_window.nettv_status_overlay.raise_()
        self.info_timer.start()

    @Slot()
    def hide_info_banner(self):
        self.live_info_action_index = -1
        self.live_info_nav_focused = False
        self.live_info_settings_open = False
        self.info_timer.stop()
        self.video_window.info_overlay.hide()
        self.update_next_up_overlay()

    def refresh_info_banner(self):
        if self.video_window.info_overlay.isVisible():
            self.video_window.info_overlay.settings_open = self.live_info_settings_open
            self.video_window.info_overlay.settings_values = self.overlay_settings_values()
            state = self.build_info_state()
            if state:
                self.video_window.info_overlay.update_banner(state)
                if self.current_youtube_channel() is not None and self.nettv_waiting_for_visible_frame:
                    self.video_window.nettv_status_overlay.raise_()

    @Slot()
    def info_left(self):
        if not self.video_window.info_overlay.isVisible():
            return
        if self.live_info_settings_open:
            if self.live_info_settings_focus_index == 0:
                self.step_skin(-1)
            elif self.live_info_settings_focus_index == 1:
                self.step_theme(-1)
            elif self.live_info_settings_focus_index == 2:
                self.step_profile(-1)
            return
        if self.live_info_nav_focused:
            self.live_info_nav_index = max(0, self.live_info_nav_index - 1)
        else:
            actions = self.current_info_actions()
            if self.live_info_action_index < 0:
                self.live_info_action_index = 0 if actions else -1
            elif self.live_info_action_index > 0:
                self.live_info_action_index -= 1
        self.refresh_info_banner()

    @Slot()
    def info_right(self):
        if not self.video_window.info_overlay.isVisible():
            return
        if self.live_info_settings_open:
            if self.live_info_settings_focus_index == 0:
                self.step_skin(1)
            elif self.live_info_settings_focus_index == 1:
                self.step_theme(1)
            elif self.live_info_settings_focus_index == 2:
                self.step_profile(1)
            return
        if self.live_info_nav_focused:
            self.live_info_nav_index = min(self.info_nav_button_count() - 1, self.live_info_nav_index + 1)
        else:
            actions = self.current_info_actions()
            if actions:
                if self.live_info_action_index < 0:
                    self.live_info_action_index = 0
                else:
                    self.live_info_action_index = min(len(actions) - 1, self.live_info_action_index + 1)
        self.refresh_info_banner()

    @Slot()
    def info_up(self):
        if not self.video_window.info_overlay.isVisible():
            return
        if self.live_info_settings_open:
            self.live_info_settings_focus_index = (self.live_info_settings_focus_index - 1) % self.in_app_menu_row_count()
            self.refresh_info_banner()
            return
        if self.live_info_nav_focused:
            self.live_info_nav_focused = False
            actions = self.current_info_actions()
            self.live_info_action_index = 0 if actions else -1
        elif self.live_info_action_index >= 0:
            self.live_info_action_index = -1
        self.refresh_info_banner()

    @Slot()
    def info_down(self):
        if not self.video_window.info_overlay.isVisible():
            return
        if self.live_info_settings_open:
            self.live_info_settings_focus_index = (self.live_info_settings_focus_index + 1) % self.in_app_menu_row_count()
            self.refresh_info_banner()
            return
        if self.live_info_nav_focused:
            self.refresh_info_banner()
            return
        self.live_info_nav_focused = True
        self.live_info_action_index = -1
        self.refresh_info_banner()

    @Slot()
    def info_select(self):
        if not self.video_window.info_overlay.isVisible():
            return
        if self.live_info_settings_open:
            if self.live_info_settings_focus_index == self.in_app_menu_close_index():
                self.live_info_settings_open = False
                self.refresh_info_banner()
            elif self.handle_in_app_menu_toggle(self.live_info_settings_focus_index):
                self.refresh_info_banner()
            else:
                self.live_info_settings_open = False
                self.refresh_info_banner()
            return
        if self.live_info_nav_focused:
            if self.playback_mode == "ondemand" and self.live_info_nav_index == 4:
                self.restart_on_demand_from_beginning()
                return
            self.activate_universal_nav("info", self.live_info_nav_index)
            return
        if self.live_info_action_index < 0:
            return
        if self.playback_mode == "ondemand" and self.live_info_action_index == 0:
            self.restart_on_demand_from_beginning()
            return
        self.open_current_show_in_vault()

    def open_current_show_in_vault(self):
        program = self.current_on_demand_program() if self.playback_mode == "ondemand" else self.current_live_program()
        if not program:
            return
        if not self.on_demand_catalog or self.on_demand_catalog_dirty:
            self.build_on_demand_catalog()
        match_channel = None
        match_group = None
        match_item = None
        for channel_index, channel in enumerate(self.on_demand_catalog):
            for group_index, group in enumerate(channel.get("groups", [])):
                for item_index, item in enumerate(group.get("items", [])):
                    if item.get("path") == program["path"]:
                        match_channel = channel_index
                        match_group = group_index
                        match_item = item_index
                        break
                if match_channel is not None:
                    break
            if match_channel is not None:
                break

        if match_channel is None:
            self.status.setText("That live program does not have a matching Vault entry yet.")
            return

        self.hide_info_banner()
        self.open_on_demand_group(match_channel, match_group, match_item, focus="episodes")
        self.hide_guide()
        self.refresh_on_demand(show=True)

    def build_on_demand_state(self):
        sections = self.build_on_demand_home_sections()
        base_state = {
            "nav_focused": self.on_demand_nav_focused,
            "nav_index": self.on_demand_nav_index,
            "settings_focus_index": self.on_demand_settings_focus_index,
        }

        if self.on_demand_view == "home":
            self.on_demand_render_sections = sections
            if not sections:
                return {
                    **base_state,
                    "view": "home",
                    "sections": [],
                    "hero": {
                        "title": f"{APP_NAME} Vault",
                        "subtitle": "Load a catalog to browse your library.",
                        "summary": "Your movies and shows will appear here in easy streaming rows once a catalog is loaded.",
                        "badge": "VAULT",
                        "meta": "",
                        "progress": 0.0,
                    },
                    "selected_section": 0,
                }
            selected_section = sections[self.on_demand_section_index]
            selected_item_index = max(0, min(self.on_demand_section_item_indices.get(self.on_demand_section_index, 0), len(selected_section["items"]) - 1))
            self.on_demand_section_item_indices[self.on_demand_section_index] = selected_item_index
            selected_card = selected_section["items"][selected_item_index] if selected_section["items"] else {}
            hero = {
                "title": selected_card.get("title", selected_section["title"]),
                "subtitle": selected_card.get("subtitle", selected_section["subtitle"]),
                "summary": selected_card.get("summary", selected_section["subtitle"]),
                "badge": selected_card.get("badge", selected_section["title"].upper()),
                "meta": selected_card.get("meta", ""),
                "progress": selected_card.get("progress", 0.0),
                "progress_label": selected_card.get("progress_label", ""),
                "artwork_path": selected_card.get("hero_artwork_path") or selected_card.get("artwork_path", ""),
                "clearlogo_path": selected_card.get("clearlogo_path", ""),
            }
            return {
                **base_state,
                "view": "home",
                "sections": sections,
                "selected_section": self.on_demand_section_index,
                "selected_item": selected_item_index,
                "section_item_indices": dict(self.on_demand_section_item_indices),
                "hero": hero,
            }

        self.on_demand_render_sections = []
        channel = self.current_on_demand_channel()
        group = self.current_on_demand_group()
        items = group.get("items", []) if group else []
        seasons = self.build_on_demand_seasons(group)
        if seasons:
            self.on_demand_season_index = max(0, min(self.on_demand_season_index, len(seasons) - 1))
            visible_indices = seasons[self.on_demand_season_index]["item_indices"]
        else:
            visible_indices = list(range(len(items)))
        visible_items = [items[idx] for idx in visible_indices]
        if visible_items:
            local_index = 0
            if self.on_demand_item_index in visible_indices:
                local_index = visible_indices.index(self.on_demand_item_index)
            else:
                self.on_demand_item_index = visible_indices[0]
            local_index = max(0, min(local_index, len(visible_items) - 1))
            self.on_demand_item_index = visible_indices[local_index]
            selected_episode = visible_items[local_index]
        else:
            selected_episode = None

        group_summary = ""
        group_summary = (group.get("summary") or "").strip()
        if not group_summary:
            for item in items:
                group_summary = (item.get("summary") or "").strip()
                if group_summary:
                    break
        if not group_summary:
            group_summary = (
                "Browse this series from your local MediaWave library."
                if any(item.get("media_type") == "tv" for item in items)
                else "This title is ready to play from your local MediaWave library."
            )

        selected_path = selected_episode.get("path") if selected_episode else (items[0]["path"] if items else "")
        resume_entry = self.resume_state.get("entries", {}).get(selected_path, {})
        resume_ms = int(resume_entry.get("position_ms", 0) or 0)
        episode_thumbnail = QPixmap() if str(selected_path).startswith("dummy://") else (self.get_media_thumbnail(selected_path) if selected_path else QPixmap())
        action_label = "Resume" if resume_ms > 0 else "Play"
        actions = [
            {"label": action_label, "meta": "Continue from where you left off" if resume_ms > 0 else "Start playback"},
            {"label": "Start Over", "meta": "Begin from the opening scene"},
        ]
        self.on_demand_action_index = max(0, min(self.on_demand_action_index, len(actions) - 1))
        if self.on_demand_detail_focus not in ("actions", "seasons", "episodes"):
            self.on_demand_detail_focus = "actions"

        return {
            **base_state,
            "view": "detail",
            "detail": {
                "title": group["label"] if group else "Title",
                "subtitle": self.describe_on_demand_group(channel, group) if channel and group else "",
                "summary": group_summary,
                "badge": "TV SHOW" if any(item.get("media_type") == "tv" for item in items) else "MOVIE",
                "meta": selected_episode.get("detail_title", "") if selected_episode else "",
                "progress": max(
                    0.0,
                    min(
                        1.0,
                        resume_ms / max(1, int(resume_entry.get("duration_ms", 1) or 1)),
                    ),
                ),
                "progress_label": (
                    f"{format_resume_time(max(0, int(resume_entry.get('duration_ms', 1) or 1) - resume_ms))} Left"
                    if resume_ms > 0 else ""
                ),
                "artwork_path": group.get("hero_artwork_path") or group.get("artwork_path") or (selected_episode.get("hero_artwork_path", "") if selected_episode else "") or (selected_episode.get("artwork_path", "") if selected_episode else ""),
                "clearlogo_path": group.get("clearlogo_path") or (selected_episode.get("clearlogo_path", "") if selected_episode else ""),
            },
            "actions": actions,
            "action_selected": -1 if self.on_demand_nav_focused else self.on_demand_action_index,
            "detail_focus": self.on_demand_detail_focus if not self.on_demand_nav_focused else "nav",
            "seasons": [{"label": season["label"], "count": len(season["item_indices"])} for season in seasons],
            "season_selected": self.on_demand_season_index,
            "episode_items": [
                {
                    "label": item["label"],
                    "meta": item["meta"],
                    "summary": item.get("summary") or "",
                    "runtime": (
                        f"{int(item.get('runtime_minutes'))} min"
                        if item.get("runtime_minutes")
                        else (
                            format_resume_time(int(max(0.0, float(self.duration_cache.get(item["path"], 0) or 0)) * 1000))
                            if float(self.duration_cache.get(item["path"], 0) or 0) > 0
                            else ""
                        )
                    ),
                    "progress": max(
                        0.0,
                        min(
                            1.0,
                            int(self.resume_state.get("entries", {}).get(item["path"], {}).get("position_ms", 0) or 0)
                            / max(1, int(self.resume_state.get("entries", {}).get(item["path"], {}).get("duration_ms", 0) or (float(self.duration_cache.get(item["path"], 0) or 0) * 1000) or 1)),
                        ),
                    ),
                }
                for item in visible_items
            ],
            "episode_selected": -1 if self.on_demand_nav_focused else (visible_indices.index(self.on_demand_item_index) if visible_indices else 0),
            "episode_detail": {
                "title": selected_episode.get("detail_title", group["label"] if group else "Episode") if selected_episode else (group["label"] if group else "Episode"),
                "meta": f"{channel['label']}  •  {selected_episode.get('meta', '')}" if channel and selected_episode else "",
                "summary": selected_episode.get("summary") if selected_episode else group_summary,
                "thumbnail": episode_thumbnail,
            },
        }

    def open_on_demand_group(self, channel_index, group_index, item_index=0, focus="actions"):
        try:
            safe_channel_index = int(channel_index)
            safe_group_index = int(group_index)
            safe_item_index = int(item_index)
            request = {
                "channel_index": safe_channel_index,
                "group_index": safe_group_index,
                "item_index": safe_item_index,
                "focus": focus,
            }
            if 0 <= safe_channel_index < len(self.on_demand_catalog):
                channel = self.on_demand_catalog[safe_channel_index]
                request["channel_label"] = channel.get("label", "")
                groups = channel.get("groups", [])
                if 0 <= safe_group_index < len(groups):
                    group = groups[safe_group_index]
                    request["group_label"] = group.get("label", "")
                    items = group.get("items", [])
                    if items:
                        first_index = max(0, min(safe_item_index, len(items) - 1))
                        request["first_path"] = items[first_index].get("path", "")
            self.on_demand_last_open_request = request
            self.log_vault_select("open_group_request", **request)

            if not (0 <= safe_channel_index < len(self.on_demand_catalog)):
                self.log_vault_select(
                    "open_group_invalid_channel",
                    channel_index=safe_channel_index,
                    catalog_len=len(self.on_demand_catalog),
                )
                return
            channel = self.on_demand_catalog[safe_channel_index]
            groups = channel.get("groups", [])
            if not (0 <= safe_group_index < len(groups)):
                self.log_vault_select(
                    "open_group_invalid_group",
                    channel_index=safe_channel_index,
                    group_index=safe_group_index,
                    group_count=len(groups),
                )
                return

            group = groups[safe_group_index]
            items = group.get("items", [])

            self.on_demand_channel_index = safe_channel_index
            self.on_demand_group_index = safe_group_index
            self.on_demand_item_index = max(0, min(safe_item_index, len(items) - 1)) if items else 0
            self.on_demand_action_index = 0
            self.on_demand_detail_focus = focus
            self.on_demand_season_index = 0

            seasons = self.build_on_demand_seasons(group)
            for idx, season in enumerate(seasons):
                if self.on_demand_item_index in season["item_indices"]:
                    self.on_demand_season_index = idx
                    break

            self.on_demand_view = "detail"
            self.on_demand_nav_focused = False
            self.on_demand_back_focused = False
            self.log_vault_select(
                "open_group_ready",
                channel_index=self.on_demand_channel_index,
                group_index=self.on_demand_group_index,
                item_index=self.on_demand_item_index,
                detail_focus=self.on_demand_detail_focus,
                season_index=self.on_demand_season_index,
            )
        except Exception as exc:
            self.log_vault_select(
                "open_group_exception",
                channel_index=channel_index,
                group_index=group_index,
                item_index=item_index,
                error=repr(exc),
                traceback=traceback.format_exc(),
            )
            raise

    def open_on_demand_card(self, card):
        if not card:
            return
        if card.get("type") == "resume":
            _, _, _, item_index, item = self.find_on_demand_item_by_path(card.get("path"))
            channel, group, _, _, _ = self.find_on_demand_item_by_path(card.get("path"))
            if not channel or not group or not item:
                return
            channel_index = next((idx for idx, entry in enumerate(self.on_demand_catalog) if entry is channel), 0)
            group_index = next((idx for idx, entry in enumerate(channel.get("groups", [])) if entry is group), 0)
            self.open_on_demand_group(channel_index, group_index, item_index, focus="episodes")
            return
        self.open_on_demand_group(card.get("channel_index", 0), card.get("group_index", 0), card.get("item_index", 0), focus="actions")

    @Slot()
    def toggle_on_demand(self):
        if self.video_window.on_demand_overlay.isVisible():
            self.hide_on_demand()
        else:
            self.show_on_demand()

    def show_on_demand(self):
        if not self.on_demand_catalog or self.on_demand_catalog_dirty:
            self.build_on_demand_catalog()
        if not self.on_demand_catalog:
            self.status.setText("Load a catalog to browse On Demand.")
            return
        self.hide_info_banner()
        self.hide_guide()
        if not self.video_window.isVisible():
            if self.on_demand_catalog and self.app_settings.get("allow_dummy_vault_catalog", False) and not self.channels:
                screen = self.screen() or QApplication.primaryScreen()
                if screen is not None:
                    self.video_window.setGeometry(screen.geometry())
                self.video_window.show()
                self.video_window.showFullScreen()
                self.video_window.raise_()
                self.video_window.activateWindow()
                self.video_window.setFocus(Qt.ActiveWindowFocusReason)
            else:
                self.watch_tv()
            if not self.video_window.isVisible():
                return
        self.on_demand_view = "home"
        self.on_demand_section_index = 0
        self.on_demand_action_index = 0
        self.on_demand_detail_focus = "actions"
        self.on_demand_season_index = 0
        self.on_demand_back_focused = False
        self.on_demand_nav_focused = False
        self.on_demand_nav_index = 3
        self.on_demand_settings_open = False
        self.on_demand_settings_focus_index = 0
        self.on_demand_render_sections = []
        write_vault_debug_log("VaultSelect", "show_on_demand", {
            "catalog_channels": len(self.on_demand_catalog),
            "catalog_dirty": self.on_demand_catalog_dirty,
        })
        self.ensure_on_demand_focus_state()
        self.refresh_on_demand(show=True)

    @Slot()
    def hide_on_demand(self):
        self.on_demand_settings_open = False
        self.video_window.on_demand_overlay.hide()

    def log_vault_select(self, message, **fields):
        write_vault_debug_log("VaultSelect", message, fields)

    @Slot()
    def on_demand_back(self):
        if not self.video_window.on_demand_overlay.isVisible():
            return
        if self.on_demand_settings_open:
            self.on_demand_settings_open = False
            self.refresh_on_demand()
            return
        if self.on_demand_nav_focused:
            self.on_demand_nav_focused = False
            self.refresh_on_demand()
            return
        if self.on_demand_view == "home":
            self.hide_on_demand()
            return
        self.on_demand_view = "home"
        self.on_demand_back_focused = False
        self.on_demand_nav_focused = False
        self.refresh_on_demand()

    def refresh_on_demand(self, show=False):
        requested_view = self.on_demand_view
        self.log_vault_select(
            "refresh_start",
            requested_view=requested_view,
            show=show,
            channel_index=self.on_demand_channel_index,
            group_index=self.on_demand_group_index,
            item_index=self.on_demand_item_index,
            detail_focus=self.on_demand_detail_focus,
        )
        self.ensure_on_demand_focus_state()
        state = self.build_on_demand_state()
        if requested_view == "detail" and state.get("view") == "home" and self.repair_on_demand_open_request():
            self.on_demand_view = "detail"
            self.ensure_on_demand_focus_state()
            state = self.build_on_demand_state()
        self.log_vault_select(
            "refresh_state_built",
            requested_view=requested_view,
            resulting_view=state.get("view", ""),
            current_view=self.on_demand_view,
            channel_index=self.on_demand_channel_index,
            group_index=self.on_demand_group_index,
            item_index=self.on_demand_item_index,
            detail_focus=self.on_demand_detail_focus,
        )
        self.video_window.on_demand_overlay.settings_open = self.on_demand_settings_open
        self.video_window.on_demand_overlay.settings_focus_index = self.on_demand_settings_focus_index
        self.video_window.on_demand_overlay.settings_values = self.overlay_settings_values()
        if show:
            self.video_window.on_demand_overlay.show_browser(state)
        else:
            self.video_window.on_demand_overlay.update_browser(state)
        self.video_window.activateWindow()
        self.video_window.setFocus(Qt.ActiveWindowFocusReason)

    @Slot()
    def on_demand_up(self):
        if not self.video_window.on_demand_overlay.isVisible():
            return
        if self.on_demand_settings_open:
            self.on_demand_settings_focus_index = (self.on_demand_settings_focus_index - 1) % self.in_app_menu_row_count()
            self.refresh_on_demand()
            return
        if self.on_demand_nav_focused:
            self.on_demand_nav_focused = False
            self.refresh_on_demand()
            return
        if self.on_demand_view == "home":
            if self.on_demand_section_index > 0:
                self.on_demand_section_index -= 1
        else:
            if self.on_demand_detail_focus == "episodes":
                group = self.current_on_demand_group()
                seasons = self.build_on_demand_seasons(group)
                if seasons:
                    indices = seasons[self.on_demand_season_index]["item_indices"]
                    if self.on_demand_item_index in indices:
                        local_index = indices.index(self.on_demand_item_index)
                        if local_index > 0:
                            self.on_demand_item_index = indices[local_index - 1]
                        else:
                            self.on_demand_detail_focus = "seasons"
                else:
                    self.on_demand_detail_focus = "seasons"
            else:
                order = ["actions", "seasons", "episodes"]
                current = order.index(self.on_demand_detail_focus) if self.on_demand_detail_focus in order else 0
                if current > 0:
                    self.on_demand_detail_focus = order[current - 1]
        self.refresh_on_demand()

    @Slot()
    def on_demand_down(self):
        if not self.video_window.on_demand_overlay.isVisible():
            return
        if self.on_demand_settings_open:
            self.on_demand_settings_focus_index = (self.on_demand_settings_focus_index + 1) % self.in_app_menu_row_count()
            self.refresh_on_demand()
            return
        if self.on_demand_nav_focused:
            self.refresh_on_demand()
            return
        if self.on_demand_view == "home":
            sections = self.build_on_demand_home_sections()
            if self.on_demand_section_index < len(sections) - 1:
                self.on_demand_section_index += 1
            else:
                self.on_demand_nav_focused = True
                self.on_demand_nav_index = 0
        else:
            if self.on_demand_detail_focus == "episodes":
                moved = False
                group = self.current_on_demand_group()
                seasons = self.build_on_demand_seasons(group)
                if seasons:
                    indices = seasons[self.on_demand_season_index]["item_indices"]
                    if self.on_demand_item_index in indices:
                        local_index = indices.index(self.on_demand_item_index)
                        if local_index < len(indices) - 1:
                            self.on_demand_item_index = indices[local_index + 1]
                            moved = True
                if not moved:
                    self.on_demand_nav_focused = True
                    self.on_demand_nav_index = 0
            else:
                order = ["actions", "seasons", "episodes"]
                current = order.index(self.on_demand_detail_focus) if self.on_demand_detail_focus in order else 0
                if current < len(order) - 1:
                    self.on_demand_detail_focus = order[current + 1]
                else:
                    self.on_demand_nav_focused = True
                    self.on_demand_nav_index = 0
        self.refresh_on_demand()

    @Slot()
    def on_demand_left(self):
        if not self.video_window.on_demand_overlay.isVisible():
            return
        if self.on_demand_settings_open:
            if self.on_demand_settings_focus_index == 0:
                self.step_skin(-1)
            elif self.on_demand_settings_focus_index == 1:
                self.step_theme(-1)
            elif self.on_demand_settings_focus_index == 2:
                self.step_profile(-1)
            return
        if self.on_demand_nav_focused:
            if self.on_demand_nav_index > 0:
                self.on_demand_nav_index -= 1
            self.refresh_on_demand()
            return
        moved = False
        if self.on_demand_view == "home":
            current = self.on_demand_section_item_indices.get(self.on_demand_section_index, 0)
            if current > 0:
                self.on_demand_section_item_indices[self.on_demand_section_index] = current - 1
                moved = True
        elif self.on_demand_detail_focus == "actions":
            if self.on_demand_action_index > 0:
                self.on_demand_action_index -= 1
                moved = True
        elif self.on_demand_detail_focus == "seasons":
            if self.on_demand_season_index > 0:
                self.on_demand_season_index -= 1
                group = self.current_on_demand_group()
                seasons = self.build_on_demand_seasons(group)
                if seasons:
                    self.on_demand_item_index = seasons[self.on_demand_season_index]["item_indices"][0]
                moved = True
        elif self.on_demand_detail_focus == "episodes":
            moved = True
        if not moved and self.on_demand_view != "home":
            self.on_demand_nav_focused = True
            self.on_demand_nav_index = 0
            self.refresh_on_demand()
            return
        if not moved and self.on_demand_view == "home":
            self.refresh_on_demand()
            return
        self.refresh_on_demand()

    @Slot()
    def on_demand_right(self):
        if not self.video_window.on_demand_overlay.isVisible():
            return
        if self.on_demand_settings_open:
            if self.on_demand_settings_focus_index == 0:
                self.step_skin(1)
            elif self.on_demand_settings_focus_index == 1:
                self.step_theme(1)
            elif self.on_demand_settings_focus_index == 2:
                self.step_profile(1)
            return
        if self.on_demand_nav_focused:
            if self.on_demand_nav_index < 3:
                self.on_demand_nav_index += 1
            self.refresh_on_demand()
            return
        if self.on_demand_view == "home":
            sections = self.build_on_demand_home_sections()
            if sections:
                items = sections[self.on_demand_section_index]["items"]
                current = self.on_demand_section_item_indices.get(self.on_demand_section_index, 0)
                if items and current < len(items) - 1:
                    self.on_demand_section_item_indices[self.on_demand_section_index] = current + 1
        elif self.on_demand_detail_focus == "actions":
            actions = self.build_on_demand_state().get("actions", [])
            if actions and self.on_demand_action_index < len(actions) - 1:
                self.on_demand_action_index += 1
        elif self.on_demand_detail_focus == "seasons":
            group = self.current_on_demand_group()
            seasons = self.build_on_demand_seasons(group)
            if seasons and self.on_demand_season_index < len(seasons) - 1:
                self.on_demand_season_index += 1
                self.on_demand_item_index = seasons[self.on_demand_season_index]["item_indices"][0]
        elif self.on_demand_detail_focus == "episodes":
            pass
        self.refresh_on_demand()

    @Slot()
    def on_demand_select(self):
        if not self.video_window.on_demand_overlay.isVisible():
            return
        if self.on_demand_settings_open:
            if self.on_demand_settings_focus_index == 0:
                self.step_skin(1)
                return
            if self.on_demand_settings_focus_index == 1:
                self.step_theme(1)
                return
            if self.on_demand_settings_focus_index == 2:
                self.step_profile(1)
                return
            if self.on_demand_settings_focus_index == self.in_app_menu_close_index():
                self.on_demand_settings_open = False
            elif not self.handle_in_app_menu_toggle(self.on_demand_settings_focus_index):
                self.on_demand_settings_open = False
            self.refresh_on_demand()
            return
        if self.on_demand_nav_focused:
            self.activate_universal_nav("vault", self.on_demand_nav_index)
            return
        if self.on_demand_view == "home":
            sections = self.on_demand_render_sections or self.build_on_demand_home_sections()
            current_index = self.on_demand_section_item_indices.get(self.on_demand_section_index, 0)
            rendered_sections = self.video_window.on_demand_overlay.state.get("sections", [])
            rendered_section = rendered_sections[self.on_demand_section_index] if rendered_sections and 0 <= self.on_demand_section_index < len(rendered_sections) else {}
            rendered_items = rendered_section.get("items", [])
            rendered_card = rendered_items[current_index] if rendered_items and 0 <= current_index < len(rendered_items) else {}
            self.log_vault_select(
                "select_start",
                on_demand_view=self.on_demand_view,
                settings_open=self.on_demand_settings_open,
                nav_focused=self.on_demand_nav_focused,
                section_index=self.on_demand_section_index,
                current_item_index=current_index,
                rebuilt_section_count=len(sections),
                rendered_section_count=len(rendered_sections),
                selected_section_key=rendered_section.get("key", ""),
                selected_section_title=rendered_section.get("title", ""),
                selected_card_title=rendered_card.get("title", ""),
                selected_card_type=rendered_card.get("type", ""),
                selected_card_channel_index=rendered_card.get("channel_index"),
                selected_card_group_index=rendered_card.get("group_index"),
            )
            if not sections:
                self.log_vault_select("select_return", reason="no_sections")
                return
            section = sections[self.on_demand_section_index]
            current = max(0, min(self.on_demand_section_item_indices.get(self.on_demand_section_index, 0), len(section["items"]) - 1))
            self.on_demand_section_item_indices[self.on_demand_section_index] = current
            card = section["items"][current] if section.get("items") else {}
            self.log_vault_select(
                "select_resolved",
                resolved_section_key=section.get("key", ""),
                resolved_section_title=section.get("title", ""),
                resolved_item_index=current,
                resolved_card_title=card.get("title", ""),
                resolved_card_type=card.get("type", ""),
                resolved_card_channel_index=card.get("channel_index"),
                resolved_card_group_index=card.get("group_index"),
            )
            self.open_on_demand_home_card(self.on_demand_section_index, current)
            return
        group = self.current_on_demand_group()
        items = group.get("items", []) if group else []
        if not items:
            return
        seasons = self.build_on_demand_seasons(group)
        indices = seasons[self.on_demand_season_index]["item_indices"] if seasons else list(range(len(items)))
        target_index = self.on_demand_item_index if self.on_demand_item_index in indices else indices[0]
        item = items[target_index]
        if self.on_demand_detail_focus == "actions":
            if self.on_demand_action_index == 0:
                resume_ms = int(self.resume_state.get("entries", {}).get(item["path"], {}).get("position_ms", 0))
                self.play_on_demand(item["path"], resume_ms)
                return
            self.play_on_demand(item["path"], 0)
            return
        if self.on_demand_detail_focus == "seasons":
            self.refresh_on_demand()
            return
        resume_ms = int(self.resume_state.get("entries", {}).get(item["path"], {}).get("position_ms", 0))
        self.play_on_demand(item["path"], resume_ms)

    def play_on_demand(self, path, position_ms=0):
        if not path:
            return
        if str(path).startswith("dummy://"):
            self.status.setText("Dummy Vault listings are for navigation testing only.")
            self.refresh_on_demand()
            return
        self.hide_info_banner()
        self.hide_guide()
        self.hide_on_demand()
        self.video_window.next_up_overlay.hide()
        self.next_up_state = None
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            self.video_window.setGeometry(screen.geometry())
        self.video_window.show()
        self.video_window.showFullScreen()
        self.video_window.raise_()
        self.video_window.activateWindow()
        self.video_window.setFocus(Qt.ActiveWindowFocusReason)

        self.stop_player()
        self.playback_mode = "ondemand"
        self.current_on_demand_path = path
        self.pending_seek_ms = max(0, int(position_ms))
        self.pending_play_after_seek = True
        self.media_player.setPlaybackRate(1.0)
        self.media_player.setSource(QUrl.fromLocalFile(path))
        self.resume_timer.start()

        metadata = self.get_program_metadata(path)
        self.status.setText(
            f"On Demand: {metadata.get('detail_title', format_program_title(path))}\n"
            f"Press SPACE to play or pause."
        )

    @Slot()
    def toggle_play_pause(self):
        if self.playback_mode != "ondemand":
            return
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.update_resume_progress()
            self.show_transport_overlay("Paused")
        else:
            self.media_player.play()
            self.show_transport_overlay("Playing")

    def restart_on_demand_from_beginning(self):
        if self.playback_mode != "ondemand" or not self.current_on_demand_path:
            return
        self.seek_hold_timer.stop()
        self.seek_repeat_timer.stop()
        self.media_player.setPosition(0)
        self.update_resume_progress()
        self.refresh_info_banner()
        self.show_transport_overlay("Restarted")

    @Slot(int)
    def seek_on_demand(self, seconds_delta):
        if self.playback_mode != "ondemand" or not self.current_on_demand_path or self.video_window.on_demand_overlay.isVisible():
            return
        duration_ms = int(self.media_player.duration())
        position_ms = int(self.media_player.position())
        target = position_ms + (seconds_delta * 1000)
        if duration_ms > 0:
            target = max(0, min(duration_ms, target))
        else:
            target = max(0, target)
        self.media_player.setPosition(target)
        self.update_resume_progress()
        self.refresh_info_banner()
        self.update_next_up_overlay()
        self.show_transport_overlay(f"{'Forward' if seconds_delta > 0 else 'Back'} {abs(seconds_delta)}s")

    @Slot(int, bool)
    def on_seek_press_changed(self, seconds_delta, pressed):
        if self.playback_mode != "ondemand" or self.video_window.on_demand_overlay.isVisible():
            return
        if pressed:
            self.seek_hold_direction = seconds_delta
            self.seek_hold_timer.start()
        else:
            if self.seek_hold_direction == seconds_delta:
                self.seek_hold_direction = 0
            self.seek_hold_timer.stop()
            self.seek_repeat_timer.stop()

    def begin_seek_repeat(self):
        if self.seek_hold_direction == 0:
            return
        self.seek_repeat_timer.start()

    def seek_repeat_step(self):
        if self.seek_hold_direction == 0:
            self.seek_repeat_timer.stop()
            return
        self.seek_on_demand(self.seek_hold_direction)

    def update_resume_progress(self):
        if self.playback_mode != "ondemand" or not self.current_on_demand_path:
            self.resume_timer.stop()
            self.video_window.next_up_overlay.hide()
            return
        position_ms = int(self.media_player.position())
        duration_ms = int(self.media_player.duration())
        self.store_resume_point(self.current_on_demand_path, position_ms, duration_ms)
        self.update_next_up_overlay()

    def store_resume_point(self, path, position_ms, duration_ms):
        entries = self.resume_state.setdefault("entries", {})
        if duration_ms > 0 and position_ms >= max(0, duration_ms - 1500):
            if path in entries:
                entries.pop(path, None)
                save_json_file(RESUME_STATE_FILE, self.resume_state)
            return
        if position_ms < 500:
            return

        metadata = self.get_program_metadata(path)
        channel_name = ""
        for channel in self.channels:
            if path in channel.shows:
                channel_name = channel.name
                break
        entries[path] = {
            "position_ms": int(position_ms),
            "duration_ms": int(duration_ms),
            "last_played": time.time(),
            "channel_name": channel_name,
            "show_name": metadata.get("show_name") or format_program_title(path),
        }
        save_json_file(RESUME_STATE_FILE, self.resume_state)

    def capture_current_frame(self):
        if self.current_weather_channel() is not None:
            weather_preview = self.video_window.weather_preview_pixmap()
            if not weather_preview.isNull():
                return weather_preview
        if self.current_radiowave_channel() is not None:
            radiowave_preview = self.video_window.radiowave_preview_pixmap()
            if not radiowave_preview.isNull():
                return radiowave_preview
        if not self.last_video_frame.isNull():
            return self.last_video_frame
        return QPixmap()

    def show_transport_overlay(self, label):
        if self.playback_mode != "ondemand" or not self.current_on_demand_path:
            return
        if self.video_window.info_overlay.isVisible():
            return
        metadata = self.get_program_metadata(self.current_on_demand_path)
        duration_ms = max(1, int(self.media_player.duration()))
        position_ms = max(0, int(self.media_player.position()))
        self.video_window.transport_overlay.show_transport(
            {
                "label": label,
                "title": metadata.get("detail_title", format_program_title(self.current_on_demand_path)),
                "progress": max(0.0, min(1.0, position_ms / duration_ms)),
                "elapsed_text": format_resume_time(position_ms),
                "total_text": format_resume_time(duration_ms),
            }
        )

    def stop_player(self):
        self.channel_switch_timer.stop()
        self.live_stall_timer.stop()
        self.seek_hold_timer.stop()
        self.seek_repeat_timer.stop()
        self.youtube_stream_generation += 1
        self.nettv_prefetch_generation += 1
        self.nettv_prefetch_active = False
        self.seek_hold_direction = 0
        self.pending_video = None
        self.pending_weather_url = None
        self.pending_weather_name = ""
        self.pending_weather_location = ""
        self.pending_radiowave_channel = None
        self.pending_youtube_url = None
        self.pending_youtube_entry = None
        self.pending_video_is_url = False
        self.pending_offset = 0
        self.pending_seek_ms = 0
        self.pending_play_after_seek = False
        self.nettv_pending_seek_ms = 0
        self.nettv_pending_play_after_seek = False
        self.live_stall_path = ""
        self.live_stall_last_position_ms = -1
        self.live_stall_last_advance_at = 0.0
        self.live_stall_checks_started_at = 0.0
        self.resume_timer.stop()
        self.video_window.next_up_overlay.hide()
        self.video_window.transport_overlay.hide()
        self.video_window.hide_special_views()
        self.suspend_nettv_visuals()
        self.set_radiowave_muted(True)
        if self.playback_mode == "ondemand" and self.current_on_demand_path:
            self.update_resume_progress()
        self.media_player.stop()

    def find_on_demand_item_by_path(self, path):
        for channel in self.on_demand_catalog:
            for group in channel.get("groups", []):
                items = group.get("items", [])
                for index, item in enumerate(items):
                    if item.get("path") == path:
                        return channel, group, items, index, item
        return None, None, [], -1, None

    def current_next_on_demand_item(self):
        if not self.current_on_demand_path:
            return None
        _, _, items, index, _ = self.find_on_demand_item_by_path(self.current_on_demand_path)
        if index < 0 or index + 1 >= len(items):
            return None
        return items[index + 1]

    def thumbnail_path_for_media(self, path):
        return os.path.join(THUMBNAIL_DIR, f"{file_cache_signature(path)}.jpg")

    def get_media_thumbnail(self, path):
        thumb_path = self.thumbnail_path_for_media(path)
        if os.path.exists(thumb_path):
            pixmap = QPixmap(thumb_path)
            if not pixmap.isNull():
                return pixmap
        if not FFMPEG_PATH:
            return QPixmap()
        try:
            subprocess.run(
                [
                    FFMPEG_PATH,
                    "-y",
                    "-ss",
                    "5",
                    "-i",
                    path,
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=320:-1",
                    thumb_path,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
        except (subprocess.SubprocessError, OSError):
            return QPixmap()
        pixmap = QPixmap(thumb_path)
        return pixmap if not pixmap.isNull() else QPixmap()

    def update_next_up_overlay(self):
        if self.playback_mode != "ondemand" or not self.current_on_demand_path:
            self.next_up_state = None
            self.video_window.next_up_overlay.hide()
            return
        duration_ms = int(self.media_player.duration())
        position_ms = int(self.media_player.position())
        if duration_ms <= 0:
            self.video_window.next_up_overlay.hide()
            return
        remaining_ms = max(0, duration_ms - position_ms)
        next_item = self.current_next_on_demand_item()
        if not next_item or remaining_ms > 15000 or remaining_ms <= 0:
            self.next_up_state = None
            self.video_window.next_up_overlay.hide()
            return
        countdown = max(0, math.ceil(remaining_ms / 1000))
        thumbnail = self.get_media_thumbnail(next_item["path"])
        self.next_up_state = {
            "path": next_item["path"],
            "title": next_item.get("detail_title") or next_item.get("label") or format_program_title(next_item["path"]),
            "meta": next_item.get("meta", ""),
            "countdown": countdown,
            "thumbnail": thumbnail,
        }
        if self.video_window.info_overlay.isVisible() or self.video_window.on_demand_overlay.isVisible():
            self.video_window.next_up_overlay.hide()
            return
        self.video_window.next_up_overlay.show_next(self.next_up_state)

    def closeEvent(self, event):
        self.stop_player()
        self.stop_radiowave_background()
        self.video_window.static.hide()
        save_json_file(RESUME_STATE_FILE, self.resume_state)
        self.video_window.close()
        super().closeEvent(event)


# ---------------- RUN ---------------- #

if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")
    app = QApplication(sys.argv)
    w = ChannelSurfer()
    w.show()
    sys.exit(app.exec())

"""Built-in MediaWave themes and custom theme framework helpers."""

import json
import os
import re

from PySide6.QtGui import QColor

from mediawave.core_io import save_json_file


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
    "Purple": "Grape Jelly",
    "Purple Haze": "Grape Jelly",
    "Purple Passion": "Grape Jelly",
    "Orange": "Tangerine Dream",
    "Clementine": "Tangerine Dream",
    "Slate Modern": "Millennial Grey",
    "Signal Modern": "Baby Blue",
    "Green Screen": "Silver Olive",
    "Midnight Star": "Stars of Uranus",
    "Digital Cable Blue": "Blue Berry",
    "Cable Blue": "Blue Berry",
    "Silver": "Iron Ingot",
    "Olive": "Green Been",
}

GUIDE_THEME_DEFINITIONS = {
    "Promised Future": {
        "Stars of Uranus": {
            "bg": QColor(1, 5, 20, 244),
            "panel": QColor(6, 22, 68, 238),
            "header": QColor(4, 16, 60, 248),
            "row_a": QColor(8, 28, 82, 238),
            "row_b": QColor(3, 11, 40, 236),
            "selected": QColor(252, 228, 106, 248),
            "text": QColor(248, 252, 255),
            "dark_text": QColor(4, 8, 28),
            "muted": QColor(198, 216, 252),
            "chrome_top": QColor(220, 236, 255, 240),
            "chrome_mid": QColor(36, 74, 158, 236),
            "chrome_bottom": QColor(3, 14, 56, 240),
            "glass": QColor(196, 218, 255, 62),
            "pf_outer_top": QColor(12, 32, 90, 250),
            "pf_outer_bottom": QColor(1, 6, 22, 252),
            "pf_header_top": QColor(14, 40, 108, 252),
            "pf_header_bottom": QColor(3, 14, 54, 252),
            "pf_info_top": QColor(10, 36, 100, 248),
            "pf_info_bottom": QColor(4, 16, 56, 248),
            "pf_time_top": QColor(16, 48, 124, 252),
            "pf_time_bottom": QColor(5, 20, 68, 252),
            "pf_channel_top": QColor(8, 30, 88, 250),
            "pf_channel_bottom": QColor(3, 14, 52, 250),
            "pf_program_top": QColor(10, 34, 96, 250),
            "pf_program_bottom": QColor(5, 18, 64, 250),
            "pf_program_alt_top": QColor(7, 26, 80, 250),
            "pf_program_alt_bottom": QColor(3, 12, 46, 248),
            "pf_selected_top": QColor(255, 242, 160, 252),
            "pf_selected_bottom": QColor(240, 196, 72, 252),
            "pf_grid_line": QColor(148, 190, 255, 118),
            "pf_button_top": QColor(10, 34, 100, 250),
            "pf_button_bottom": QColor(3, 14, 54, 250),
            "pf_button_selected_top": QColor(255, 238, 136, 252),
            "pf_button_selected_bottom": QColor(226, 180, 52, 252),
            "pf_led_bg_top": QColor(8, 14, 36, 250),
            "pf_led_bg_bottom": QColor(2, 4, 14, 252),
            "pf_led_text": QColor(255, 210, 60, 255),
            "stars_of_uranus": True,
        },
        "Silver Olive": {
            "bg": QColor(37, 48, 28, 238),
            "panel": QColor(224, 224, 216, 238),
            "header": QColor(54, 72, 32, 246),
            "row_a": QColor(236, 234, 222, 240),
            "row_b": QColor(214, 216, 206, 238),
            "selected": QColor(252, 225, 114, 246),
            "text": QColor(248, 250, 242),
            "dark_text": QColor(31, 39, 20),
            "muted": QColor(94, 104, 78),
            "chrome_top": QColor(250, 250, 246, 248),
            "chrome_mid": QColor(211, 214, 204, 240),
            "chrome_bottom": QColor(144, 152, 124, 238),
            "glass": QColor(255, 255, 255, 78),
            "pf_outer_top": QColor(92, 102, 70, 248),
            "pf_outer_bottom": QColor(30, 42, 20, 250),
            "pf_header_top": QColor(76, 92, 48, 250),
            "pf_header_bottom": QColor(28, 42, 18, 250),
            "pf_info_top": QColor(250, 250, 248, 250),
            "pf_info_bottom": QColor(214, 216, 208, 248),
            "pf_time_top": QColor(76, 92, 48, 250),
            "pf_time_bottom": QColor(34, 50, 22, 250),
            "pf_channel_top": QColor(244, 244, 238, 250),
            "pf_channel_bottom": QColor(216, 218, 210, 248),
            "pf_program_top": QColor(248, 247, 238, 250),
            "pf_program_bottom": QColor(224, 223, 212, 248),
            "pf_program_alt_top": QColor(240, 239, 230, 250),
            "pf_program_alt_bottom": QColor(211, 213, 204, 248),
            "pf_selected_top": QColor(255, 241, 160, 252),
            "pf_selected_bottom": QColor(238, 198, 78, 252),
            "pf_grid_line": QColor(92, 100, 72, 176),
            "pf_button_top": QColor(244, 244, 240, 248),
            "pf_button_bottom": QColor(190, 194, 184, 248),
            "pf_button_selected_top": QColor(255, 236, 138, 252),
            "pf_button_selected_bottom": QColor(222, 178, 62, 252),
            "pf_led_bg_top": QColor(58, 62, 60, 250),
            "pf_led_bg_bottom": QColor(22, 24, 24, 252),
            "pf_led_text": QColor(255, 92, 92, 255),
        },
        "Iron Ingot": {
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
        "Green Been": {
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
        "Grape Jelly": {
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
        "Blue Berry": {
            "bg": QColor(2, 18, 54, 246),
            "panel": QColor(16, 88, 166, 240),
            "header": QColor(4, 64, 148, 248),
            "row_a": QColor(24, 116, 196, 240),
            "row_b": QColor(12, 78, 158, 238),
            "selected": QColor(255, 225, 112, 248),
            "text": QColor(248, 252, 255),
            "dark_text": QColor(6, 24, 54),
            "muted": QColor(222, 238, 255),
            "chrome_top": QColor(38, 126, 210, 244),
            "chrome_mid": QColor(8, 70, 158, 246),
            "chrome_bottom": QColor(2, 28, 92, 250),
            "glass": QColor(194, 230, 255, 46),
            "pf_outer_top": QColor(8, 56, 124, 252),
            "pf_outer_bottom": QColor(1, 12, 44, 252),
            "pf_header_top": QColor(10, 80, 176, 252),
            "pf_header_bottom": QColor(2, 34, 104, 252),
            "pf_info_top": QColor(40, 138, 212, 248),
            "pf_info_bottom": QColor(4, 74, 160, 248),
            "pf_time_top": QColor(30, 120, 206, 252),
            "pf_time_bottom": QColor(2, 58, 138, 252),
            "pf_channel_top": QColor(8, 92, 178, 250),
            "pf_channel_bottom": QColor(2, 50, 126, 250),
            "pf_program_top": QColor(28, 128, 210, 250),
            "pf_program_bottom": QColor(6, 82, 168, 250),
            "pf_program_alt_top": QColor(18, 108, 194, 250),
            "pf_program_alt_bottom": QColor(4, 68, 150, 250),
            "pf_selected_top": QColor(255, 241, 156, 252),
            "pf_selected_bottom": QColor(238, 188, 58, 252),
            "pf_grid_line": QColor(148, 205, 246, 152),
            "pf_button_top": QColor(16, 78, 160, 250),
            "pf_button_bottom": QColor(2, 30, 98, 250),
            "pf_button_selected_top": QColor(255, 228, 116, 252),
            "pf_button_selected_bottom": QColor(220, 168, 46, 252),
            "pf_led_bg_top": QColor(50, 58, 66, 250),
            "pf_led_bg_bottom": QColor(18, 20, 26, 252),
            "pf_led_text": QColor(255, 94, 94, 255),
        },
    },
    "Set Top Box": {
        "Stars of Uranus": {
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
            "guide_program_upcoming_bg": QColor(108, 38, 58, 238),
            "stb_bevel_light": QColor(116, 152, 236, 190),
            "stb_bevel_dark": QColor(0, 0, 10, 235),
            "flat_panels": True,
            "starfield": True,
        },
        "Blue Berry": {
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
            "guide_program_upcoming_bg": QColor(118, 42, 58, 238),
            "stb_bevel_light": QColor(86, 156, 220, 210),
            "stb_bevel_dark": QColor(0, 6, 34, 230),
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
            "guide_program_upcoming_bg": QColor(108, 38, 58, 238),
            "stb_bevel_light": QColor(116, 152, 236, 190),
            "stb_bevel_dark": QColor(0, 0, 10, 235),
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
            "guide_program_upcoming_bg": QColor(126, 58, 24, 236),
            "stb_bevel_light": QColor(198, 218, 108, 190),
            "stb_bevel_dark": QColor(12, 22, 4, 230),
            "flat_panels": True,
            "starfield": False,
        },
        "Silver Olive": {
            "bg": QColor(48, 50, 38, 246),
            "panel": QColor(194, 194, 184, 248),
            "header": QColor(58, 62, 36, 248),
            "row_a": QColor(168, 170, 158, 240),
            "row_b": QColor(132, 136, 116, 238),
            "selected": QColor(232, 202, 70, 246),
            "text": QColor(246, 246, 236),
            "dark_text": QColor(28, 30, 20),
            "muted": QColor(226, 226, 212),
            "chrome_top": QColor(234, 234, 224, 244),
            "chrome_mid": QColor(168, 170, 154, 240),
            "chrome_bottom": QColor(68, 72, 46, 240),
            "glass": QColor(255, 255, 255, 18),
            "guide_program_upcoming_bg": QColor(116, 52, 48, 238),
            "info_overlay_bg": QColor(196, 196, 184, 248),
            "info_overlay_body_text": QColor(38, 40, 24),
            "info_button_text": QColor(246, 246, 232),
            "info_channel_card_top": QColor(226, 226, 214, 246),
            "info_channel_card_bottom": QColor(108, 112, 82, 246),
            "stb_bevel_light": QColor(252, 252, 240, 210),
            "stb_bevel_dark": QColor(32, 34, 24, 230),
            "flat_panels": True,
            "starfield": False,
        },
        "Iron Ingot": {
            "bg": QColor(30, 32, 34, 244),
            "panel": QColor(66, 70, 74, 238),
            "header": QColor(46, 50, 56, 246),
            "row_a": QColor(80, 84, 90, 234),
            "row_b": QColor(50, 54, 60, 230),
            "selected": QColor(226, 206, 96, 242),
            "text": QColor(238, 240, 244),
            "dark_text": QColor(16, 18, 20),
            "muted": QColor(194, 198, 206),
            "chrome_top": QColor(104, 112, 120, 238),
            "chrome_mid": QColor(68, 74, 82, 234),
            "chrome_bottom": QColor(32, 36, 42, 236),
            "glass": QColor(255, 255, 255, 14),
            "guide_program_upcoming_bg": QColor(98, 38, 46, 238),
            "stb_bevel_light": QColor(196, 204, 216, 190),
            "stb_bevel_dark": QColor(8, 10, 12, 235),
            "flat_panels": True,
            "starfield": False,
        },
        "Green Been": {
            "bg": QColor(22, 34, 14, 244),
            "panel": QColor(46, 68, 30, 238),
            "header": QColor(36, 58, 22, 246),
            "row_a": QColor(58, 84, 38, 234),
            "row_b": QColor(36, 58, 24, 230),
            "selected": QColor(228, 216, 88, 242),
            "text": QColor(236, 246, 222),
            "dark_text": QColor(16, 26, 8),
            "muted": QColor(192, 218, 164),
            "chrome_top": QColor(76, 116, 50, 238),
            "chrome_mid": QColor(48, 82, 30, 234),
            "chrome_bottom": QColor(24, 48, 14, 236),
            "glass": QColor(255, 255, 255, 12),
            "guide_program_upcoming_bg": QColor(108, 40, 48, 238),
            "stb_bevel_light": QColor(132, 192, 94, 190),
            "stb_bevel_dark": QColor(6, 16, 2, 230),
            "flat_panels": True,
            "starfield": False,
        },
        "Grape Jelly": {
            "bg": QColor(18, 10, 32, 244),
            "panel": QColor(42, 26, 68, 238),
            "header": QColor(58, 36, 98, 246),
            "row_a": QColor(72, 44, 112, 234),
            "row_b": QColor(44, 28, 76, 230),
            "selected": QColor(218, 188, 248, 242),
            "text": QColor(242, 238, 252),
            "dark_text": QColor(14, 8, 26),
            "muted": QColor(202, 182, 234),
            "chrome_top": QColor(90, 58, 136, 238),
            "chrome_mid": QColor(58, 36, 98, 234),
            "chrome_bottom": QColor(28, 14, 52, 236),
            "glass": QColor(255, 255, 255, 14),
            "guide_program_upcoming_bg": QColor(104, 34, 52, 238),
            "stb_bevel_light": QColor(158, 120, 218, 190),
            "stb_bevel_dark": QColor(4, 0, 12, 230),
            "flat_panels": True,
            "starfield": False,
        },
    },
    "Sleek Freak": {
        "Stars of Uranus": {
            "bg": QColor(2, 6, 20, 252),
            "panel": QColor(8, 20, 52, 188),
            "header": QColor(14, 40, 106, 202),
            "row_a": QColor(10, 30, 80, 152),
            "row_b": QColor(4, 11, 34, 218),
            "selected": QColor(246, 224, 96, 238),
            "text": QColor(246, 252, 255),
            "dark_text": QColor(4, 8, 26),
            "muted": QColor(196, 216, 250),
            "chrome_top": QColor(210, 232, 255, 34),
            "chrome_mid": QColor(18, 50, 120, 82),
            "chrome_bottom": QColor(2, 6, 18, 232),
            "glass": QColor(200, 220, 255, 18),
            "sleek": True,
            "default_mode": "dark",
            "stars_of_uranus": True,
            "modes": {
                "dark": {},
                "light": {
                    "bg": QColor(198, 118, 76, 255),
                    "panel": QColor(222, 164, 116, 218),
                    "header": QColor(40, 28, 90, 216),
                    "row_a": QColor(232, 184, 144, 172),
                    "row_b": QColor(152, 112, 148, 220),
                    "selected": QColor(248, 212, 62, 238),
                    "text": QColor(22, 14, 48),
                    "dark_text": QColor(8, 4, 22),
                    "muted": QColor(80, 50, 22),
                    "chrome_top": QColor(246, 226, 194, 52),
                    "chrome_mid": QColor(128, 84, 118, 96),
                    "chrome_bottom": QColor(76, 54, 118, 236),
                    "glass": QColor(246, 228, 198, 26),
                },
            },
        },
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
            "default_mode": "dark",
            "modes": {
                "dark": {},
                "light": {
                    "bg": QColor(224, 226, 214, 255),
                    "panel": QColor(205, 211, 192, 220),
                    "header": QColor(150, 164, 128, 214),
                    "row_a": QColor(198, 207, 178, 178),
                    "row_b": QColor(238, 239, 229, 232),
                    "selected": QColor(151, 169, 108, 238),
                    "text": QColor(36, 40, 34),
                    "dark_text": QColor(18, 22, 18),
                    "muted": QColor(92, 100, 82),
                    "chrome_top": QColor(255, 255, 252, 52),
                    "chrome_mid": QColor(166, 178, 142, 96),
                    "chrome_bottom": QColor(214, 218, 204, 236),
                    "glass": QColor(255, 255, 255, 30),
                },
            },
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
            "default_mode": "dark",
            "modes": {
                "dark": {},
                "light": {
                    "bg": QColor(226, 222, 232, 255),
                    "panel": QColor(210, 202, 222, 220),
                    "header": QColor(132, 104, 160, 214),
                    "row_a": QColor(204, 190, 218, 178),
                    "row_b": QColor(241, 236, 244, 232),
                    "selected": QColor(142, 104, 172, 238),
                    "text": QColor(36, 30, 42),
                    "dark_text": QColor(22, 16, 28),
                    "muted": QColor(96, 82, 110),
                    "chrome_top": QColor(255, 252, 255, 50),
                    "chrome_mid": QColor(154, 122, 184, 94),
                    "chrome_bottom": QColor(216, 208, 226, 236),
                    "glass": QColor(255, 255, 255, 30),
                },
            },
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
            "default_mode": "dark",
            "modes": {
                "dark": {},
                "light": {
                    "bg": QColor(222, 229, 234, 255),
                    "panel": QColor(204, 218, 228, 220),
                    "header": QColor(112, 148, 178, 214),
                    "row_a": QColor(190, 210, 224, 178),
                    "row_b": QColor(237, 243, 246, 232),
                    "selected": QColor(112, 158, 190, 238),
                    "text": QColor(28, 38, 46),
                    "dark_text": QColor(16, 24, 32),
                    "muted": QColor(72, 92, 106),
                    "chrome_top": QColor(252, 255, 255, 52),
                    "chrome_mid": QColor(130, 170, 198, 94),
                    "chrome_bottom": QColor(212, 224, 232, 236),
                    "glass": QColor(255, 255, 255, 30),
                },
            },
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
            "default_mode": "dark",
            "modes": {
                "dark": {},
                "light": {
                    "bg": QColor(226, 226, 222, 255),
                    "panel": QColor(208, 211, 212, 220),
                    "header": QColor(126, 134, 142, 214),
                    "row_a": QColor(198, 202, 204, 178),
                    "row_b": QColor(240, 240, 236, 232),
                    "selected": QColor(148, 160, 170, 238),
                    "text": QColor(34, 38, 42),
                    "dark_text": QColor(18, 22, 26),
                    "muted": QColor(82, 88, 94),
                    "chrome_top": QColor(255, 255, 255, 50),
                    "chrome_mid": QColor(160, 166, 172, 94),
                    "chrome_bottom": QColor(216, 218, 218, 236),
                    "glass": QColor(255, 255, 255, 30),
                },
            },
        },
    },
}


def with_alpha(color, alpha):
    return QColor(color.red(), color.green(), color.blue(), max(0, min(255, int(alpha))))


def blend_color(start, end, amount):
    amount = max(0.0, min(1.0, float(amount)))
    inv = 1.0 - amount
    return QColor(
        int(start.red() * inv + end.red() * amount),
        int(start.green() * inv + end.green() * amount),
        int(start.blue() * inv + end.blue() * amount),
        int(start.alpha() * inv + end.alpha() * amount),
    )


def color_to_css(color, alpha=None):
    if alpha is None:
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {max(0, min(255, int(alpha)))})"


def normalize_sleek_mode(mode):
    name = str(mode or "").strip().lower()
    if name in {"light", "lite", "day", "bright"}:
        return "light"
    return "dark"


def build_app_theme_tokens(theme_name, legacy, skin_name=DEFAULT_SKIN_NAME, mode=None):
    legacy = dict(legacy)
    if legacy.get("sleek"):
        sleek_mode = normalize_sleek_mode(mode or legacy.get("default_mode", "dark"))
        mode_overrides = (legacy.get("modes") or {}).get(sleek_mode, {})
        legacy.update(mode_overrides)
        legacy["sleek_mode"] = sleek_mode
    theme = dict(legacy)
    sleek = bool(legacy.get("sleek"))
    set_top_box = bool(legacy.get("flat_panels")) and not sleek
    promised_future = skin_name == "Promised Future" and not sleek and not set_top_box
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
    guide_program_upcoming_bg = with_alpha(
        legacy.get("guide_program_upcoming_bg", legacy["row_b"]),
        236 if set_top_box else (134 if sleek else legacy.get("guide_program_upcoming_bg", legacy["row_b"]).alpha()),
    )
    guide_selected_bg = with_alpha(legacy["selected"], 242 if set_top_box else (224 if sleek else legacy["selected"].alpha()))
    guide_channel_text = readable_text_color(guide_channel_bg, light=primary_text, dark=selected_text) if set_top_box else primary_text
    guide_program_text = readable_text_color(guide_program_bg, light=primary_text, dark=selected_text) if set_top_box else primary_text
    guide_program_upcoming_text = readable_text_color(guide_program_upcoming_bg, light=primary_text, dark=selected_text) if set_top_box else primary_text
    bottom_nav_bg = with_alpha(legacy["header"], 246 if set_top_box else (118 if sleek else legacy["header"].alpha()))
    if sleek:
        guide_header_bg = with_alpha(legacy["bg"], 0)
        guide_channel_bg = with_alpha(legacy["row_b"], 164)
        guide_program_bg = with_alpha(legacy["row_b"], 150)
        guide_program_alt_bg = with_alpha(legacy["row_a"], 118)
        bottom_nav_bg = with_alpha(legacy["bg"], 0)
    pf_outer_top = legacy.get("pf_outer_top", legacy["chrome_mid"])
    pf_outer_bottom = legacy.get("pf_outer_bottom", legacy["bg"])
    pf_header_top = legacy.get("pf_header_top", legacy["chrome_top"])
    pf_header_bottom = legacy.get("pf_header_bottom", legacy["header"])
    pf_info_top = legacy.get("pf_info_top", legacy["chrome_top"])
    pf_info_bottom = legacy.get("pf_info_bottom", legacy["panel"])
    pf_time_top = legacy.get("pf_time_top", legacy["header"].lighter(112))
    pf_time_bottom = legacy.get("pf_time_bottom", legacy["header"].darker(108))
    pf_channel_top = legacy.get("pf_channel_top", legacy["row_a"].lighter(108))
    pf_channel_bottom = legacy.get("pf_channel_bottom", legacy["row_b"].lighter(104))
    pf_program_top = legacy.get("pf_program_top", legacy["row_a"].lighter(110))
    pf_program_bottom = legacy.get("pf_program_bottom", legacy["row_a"])
    pf_program_alt_top = legacy.get("pf_program_alt_top", legacy["row_b"].lighter(108))
    pf_program_alt_bottom = legacy.get("pf_program_alt_bottom", legacy["row_b"])
    pf_selected_top = legacy.get("pf_selected_top", legacy["selected"].lighter(110))
    pf_selected_bottom = legacy.get("pf_selected_bottom", legacy["selected"].darker(104))
    pf_button_top = legacy.get("pf_button_top", legacy["chrome_top"])
    pf_button_bottom = legacy.get("pf_button_bottom", legacy["chrome_mid"])
    pf_button_selected_top = legacy.get("pf_button_selected_top", pf_selected_top)
    pf_button_selected_bottom = legacy.get("pf_button_selected_bottom", pf_selected_bottom)
    pf_led_bg_top = legacy.get("pf_led_bg_top", QColor(58, 58, 62, 250))
    pf_led_bg_bottom = legacy.get("pf_led_bg_bottom", QColor(18, 18, 22, 252))
    pf_led_text = legacy.get("pf_led_text", QColor(255, 92, 92, 255))
    pf_header_text = legacy.get("pf_header_text", readable_text_color(pf_header_bottom, light=QColor(252, 252, 246), dark=legacy["dark_text"]))
    pf_panel_text = legacy.get("pf_panel_text", readable_text_color(pf_info_bottom, light=legacy["text"], dark=legacy["dark_text"]))
    # vault_hero_text: PF vault hero uses pf_header_top/bottom for its gradient,
    # not pf_info colors.  Use pf_header_bottom (the dominant background at the
    # text area) so readable_text_color picks the right light/dark text.
    pf_vault_hero_text = legacy.get("pf_vault_hero_text", readable_text_color(pf_header_bottom, light=legacy["text"], dark=legacy["dark_text"]))
    pf_grid_text = legacy.get("pf_grid_text", readable_text_color(pf_program_bottom, light=legacy["text"], dark=legacy["dark_text"]))
    pf_selected_text = legacy.get("pf_selected_text", readable_text_color(pf_selected_bottom, light=legacy["text"], dark=legacy["dark_text"]))
    pf_grid_line = legacy.get("pf_grid_line", normal_border)
    info_header_top = legacy.get("info_overlay_header_top", pf_header_top if promised_future else legacy["chrome_top"])
    info_header_bottom = legacy.get("info_overlay_header_bottom", pf_header_bottom if promised_future else legacy["chrome_mid"])
    info_body_top = legacy.get("info_overlay_body_top", pf_info_top if promised_future else legacy["panel"])
    info_body_bottom = legacy.get("info_overlay_body_bottom", pf_info_bottom if promised_future else legacy["panel"].darker(108))
    info_body_text = legacy.get("info_overlay_body_text", pf_panel_text if promised_future else primary_text)
    info_card_top = legacy.get("info_channel_card_top", pf_channel_top if promised_future else legacy["row_a"])
    info_card_bottom = legacy.get("info_channel_card_bottom", pf_channel_bottom if promised_future else legacy["row_b"])
    info_button_top = legacy.get("info_button_top", pf_button_top if promised_future else legacy["chrome_top"])
    info_button_bottom = legacy.get("info_button_bottom", pf_button_bottom if promised_future else legacy["chrome_mid"])
    info_button_selected_top = legacy.get("info_button_selected_top", pf_button_selected_top if promised_future else pf_selected_top)
    info_button_selected_bottom = legacy.get("info_button_selected_bottom", pf_button_selected_bottom if promised_future else pf_selected_bottom)
    theme.update(
        {
            "theme_name": theme_name,
            "skin_name": skin_name,
            "sleek": sleek,
            "sleek_mode": legacy.get("sleek_mode", "dark") if sleek else None,
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
            "guide_channel_cell_text": guide_channel_text,
            "guide_program_cell_bg": guide_program_bg,
            "guide_program_cell_alt_bg": guide_program_alt_bg,
            "guide_program_upcoming_bg": guide_program_upcoming_bg,
            "guide_program_cell_text": guide_program_text,
            "guide_program_upcoming_text": guide_program_upcoming_text,
            "guide_selected_bg": guide_selected_bg,
            "guide_selected_text": selected_text,
            "guide_selected_border": selected_border,
            "guide_grid_line": normal_border,
            "stb_bevel_light": legacy.get("stb_bevel_light", QColor(255, 255, 255, 150)),
            "stb_bevel_dark": legacy.get("stb_bevel_dark", QColor(0, 0, 0, 170)),
            "stb_bevel_mid": with_alpha(legacy["chrome_mid"], 210),
            "guide_detail_panel_bg": with_alpha(legacy["panel"], 238 if set_top_box else (172 if sleek else legacy["panel"].alpha())),
            "guide_detail_panel_border": normal_border,
            "guide_preview_border": normal_border,
            "guide_grid_background": with_alpha(legacy["row_b"], 170 if sleek else legacy["row_b"].alpha()),
            "guide_program_cell_background": guide_program_bg,
            "guide_current_program_background": guide_selected_bg,
            "guide_app_background": legacy["bg"],
            "guide_header_background": with_alpha(legacy["bg"], 236 if sleek else legacy["bg"].alpha()),
            "guide_header_text": primary_text,
            "guide_hero_panel_bg": with_alpha(legacy["panel"], 214 if sleek else legacy["panel"].alpha()),
            "guide_preview_frame_bg": with_alpha(legacy["row_b"], 232 if sleek else legacy["row_b"].alpha()),
            "guide_preview_frame_border": selected_border if sleek else normal_border,
            "guide_card_bg": with_alpha(legacy["row_b"], 188 if sleek else legacy["row_b"].alpha()),
            "guide_card_border": subtle_border,
            "guide_card_selected_bg": with_alpha(legacy["selected"], 220 if sleek else legacy["selected"].alpha()),
            "guide_card_selected_border": selected_border,
            "guide_card_selected_text": selected_text,
            "guide_channel_bg": with_alpha(legacy["row_b"], 200 if sleek else legacy["row_b"].alpha()),
            "guide_channel_text": primary_text,
            "guide_time_bg": with_alpha(legacy["row_b"], 166 if sleek else legacy["row_b"].alpha()),
            "guide_time_text": with_alpha(primary_text, 220),
            "guide_chip_bg": with_alpha(legacy["selected"], 48 if sleek else 210),
            "guide_chip_text": primary_text,
            "guide_chip_selected_bg": with_alpha(legacy["selected"], 236),
            "guide_chip_selected_text": selected_text,
            "guide_progress_track": QColor(255, 255, 255, 46) if sleek else with_alpha(legacy["muted"], 118),
            "guide_progress_fill": with_alpha(legacy["selected"], 236),
            "guide_bottom_nav_bg": QColor(255, 255, 255, 24) if sleek else bottom_nav_bg,
            "guide_bottom_nav_selected_bg": with_alpha(legacy["selected"], 198 if sleek else 242),
            "guide_bottom_nav_text": primary_text,
            "guide_bottom_nav_icon": primary_text,
            "guide_primary_text": primary_text,
            "guide_secondary_text": legacy["muted"],
            "guide_muted_text": with_alpha(legacy["muted"], 180),
            "guide_divider": subtle_border,
            "guide_shadow": QColor(0, 0, 0, 110 if sleek else 42),
            "guide_glow": with_alpha(legacy["selected"], 70 if sleek else 74),
            "guide_wave_motif": with_alpha(legacy["selected"], 30 if sleek else 42),
            "promised_future": promised_future,
            "pf_outer_top": pf_outer_top,
            "pf_outer_bottom": pf_outer_bottom,
            "pf_header_top": pf_header_top,
            "pf_header_bottom": pf_header_bottom,
            "pf_header_text": pf_header_text,
            "pf_info_top": pf_info_top,
            "pf_info_bottom": pf_info_bottom,
            "pf_info_text": pf_panel_text,
            "pf_time_top": pf_time_top,
            "pf_time_bottom": pf_time_bottom,
            "pf_time_text": pf_header_text,
            "pf_channel_top": pf_channel_top,
            "pf_channel_bottom": pf_channel_bottom,
            "pf_channel_text": pf_grid_text,
            "pf_program_top": pf_program_top,
            "pf_program_bottom": pf_program_bottom,
            "pf_program_alt_top": pf_program_alt_top,
            "pf_program_alt_bottom": pf_program_alt_bottom,
            "pf_program_text": pf_grid_text,
            "pf_selected_top": pf_selected_top,
            "pf_selected_bottom": pf_selected_bottom,
            "pf_selected_text": pf_selected_text,
            "pf_grid_line": pf_grid_line,
            "pf_button_top": pf_button_top,
            "pf_button_bottom": pf_button_bottom,
            "pf_button_selected_top": pf_button_selected_top,
            "pf_button_selected_bottom": pf_button_selected_bottom,
            "pf_button_text": readable_text_color(pf_button_bottom, light=legacy["text"], dark=legacy["dark_text"]),
            "pf_button_selected_text": pf_selected_text,
            "pf_led_bg_top": pf_led_bg_top,
            "pf_led_bg_bottom": pf_led_bg_bottom,
            "pf_led_text": pf_led_text,
            "pf_bevel_highlight": QColor(255, 255, 255, 92),
            "pf_bevel_shadow": QColor(0, 0, 0, 96),
            "bottom_nav_bg": bottom_nav_bg,
            "bottom_nav_button_bg": with_alpha(legacy["header"], 238 if set_top_box else (120 if sleek else 238)),
            "bottom_nav_button_text": primary_text,
            "menu_panel_bg": with_alpha(legacy["bg"], 240 if set_top_box else (232 if sleek else legacy["panel"].alpha())),
            "menu_panel_border": normal_border,
            "menu_button_bg": with_alpha(legacy["header"], 238 if set_top_box else (120 if sleek else 238)),
            "menu_button_selected_bg": guide_selected_bg,
            "info_overlay_bg": with_alpha(legacy.get("info_overlay_bg", legacy["bg"] if set_top_box else legacy["panel"]), 246 if set_top_box else (240 if sleek else 240)),
            "info_overlay_body_top": with_alpha(info_body_top, 252 if promised_future else info_body_top.alpha()),
            "info_overlay_body_bottom": with_alpha(info_body_bottom, 252 if promised_future else info_body_bottom.alpha()),
            "info_overlay_header_top": with_alpha(info_header_top, 252 if promised_future else info_header_top.alpha()),
            "info_overlay_header_bottom": with_alpha(info_header_bottom, 252 if promised_future else info_header_bottom.alpha()),
            "info_overlay_header_text": pf_header_text if promised_future else primary_text,
            "info_overlay_border": normal_border,
            "info_overlay_highlight": QColor(255, 255, 255, 128 if promised_future else 72),
            "info_overlay_shadow": QColor(0, 0, 0, 138 if promised_future else 96),
            "info_overlay_surface": with_alpha(legacy["row_b"], 190 if sleek else 238),
            "info_overlay_edge_highlight": QColor(255, 255, 255, 64 if sleek else 92),
            "info_overlay_text": info_body_text,
            "info_channel_card_top": with_alpha(info_card_top, 250 if promised_future else info_card_top.alpha()),
            "info_channel_card_bottom": with_alpha(info_card_bottom, 250 if promised_future else info_card_bottom.alpha()),
            "info_channel_card_border": pf_grid_line if promised_future else normal_border,
            "info_channel_text": legacy.get("info_channel_text", pf_grid_text if promised_future else primary_text),
            "info_title_text": pf_panel_text if promised_future else primary_text,
            "info_description_text": with_alpha(info_body_text if sleek else (pf_panel_text if promised_future else primary_text), 238 if sleek else 214),
            "info_metadata_text": with_alpha(legacy["muted"] if sleek else info_body_text, 234 if sleek else 218),
            "info_body_text": with_alpha(info_body_text, 244 if sleek else 232),
            "info_muted_text": with_alpha(info_body_text, 192),
            "info_progress_fill": legacy.get("info_progress_fill", QColor(226, 18, 18, 244) if promised_future else with_alpha(legacy["selected"], 236)),
            "info_progress_track": legacy.get("info_progress_track", QColor(188, 190, 188, 226) if promised_future else with_alpha(legacy["muted"], 156 if sleek else 118)),
            "info_progress_knob": legacy.get("info_progress_knob", QColor(226, 226, 220, 255)),
            "info_button_top": with_alpha(info_button_top, 250 if promised_future else info_button_top.alpha()),
            "info_button_bottom": with_alpha(info_button_bottom, 250 if promised_future else info_button_bottom.alpha()),
            "info_button_selected_top": with_alpha(info_button_selected_top, 252 if promised_future else info_button_selected_top.alpha()),
            "info_button_selected_bottom": with_alpha(info_button_selected_bottom, 252 if promised_future else info_button_selected_bottom.alpha()),
            "info_button_text": legacy.get("info_button_text", readable_text_color(info_button_bottom, light=legacy["text"], dark=legacy["dark_text"])),
            "info_button_selected_text": legacy.get("info_button_selected_text", readable_text_color(info_button_selected_bottom, light=legacy["text"], dark=legacy["dark_text"])),
            "info_button_bg": QColor(255, 255, 255, 36 if sleek else 0),
            "info_button_border": subtle_border,
            "info_button_icon": primary_text,
            "info_button_focused_bg": with_alpha(legacy["selected"], 190 if sleek else 236),
            "info_button_focused_border": selected_border,
            "info_toggle_bg": QColor(255, 255, 255, 44 if sleek else 0),
            "info_toggle_icon": primary_text,
            "info_toggle_focused_bg": with_alpha(legacy["selected"], 188 if sleek else 236),
            "info_led_clock_bg_top": pf_led_bg_top if promised_future else QColor(74, 78, 80, 240),
            "info_led_clock_bg_bottom": pf_led_bg_bottom if promised_future else QColor(44, 46, 48, 244),
            "info_led_clock_text": pf_led_text if promised_future else QColor(255, 94, 94, 255),
            "startup_bg": legacy["bg"],
            "startup_panel_bg": dialog_bg,
            "startup_card_bg": with_alpha(legacy["row_b"] if sleek else legacy["row_a"], 184 if sleek else 214),
            "startup_button_bg": with_alpha(legacy["row_b"], 210 if sleek else 238),
            "vault_bg": legacy["bg"],
            "vault_surface_bg": with_alpha(legacy["panel"], 142 if sleek else (246 if set_top_box else 238)),
            "vault_panel_bg": with_alpha(legacy["panel"], 188 if sleek else (248 if set_top_box else 244)),
            "vault_header_bg": with_alpha(legacy["bg"] if sleek else (legacy["header"] if set_top_box else pf_header_bottom), 0 if sleek else (246 if set_top_box else 238)),
            "vault_hero_background": with_alpha(legacy["panel"] if sleek else (legacy["row_b"] if set_top_box else pf_info_top), 180 if sleek else (242 if set_top_box else 248)),
            "vault_card_bg": with_alpha(legacy["row_b"], 196 if sleek else (242 if set_top_box else 238)),
            "vault_selected_bg": guide_selected_bg,
            "vault_card_background": with_alpha(legacy["row_b"], 196 if sleek else (242 if set_top_box else 238)),
            "vault_card_border": selected_border if sleek else (with_alpha(legacy.get("stb_bevel_dark", normal_border), 220) if set_top_box else pf_grid_line),
            "vault_card_selected_bg": guide_selected_bg,
            "vault_card_selected_border": selected_border,
            # PF card titles are drawn on vault_card_bg (row_b), not the PF header gradient.
            # Use row_b as the reference for light-vs-dark so near-white text isn't chosen
            # for light/pale card surfaces (Charcoal, Silver, Olive themes etc.).
            "vault_primary_text": primary_text if sleek or set_top_box else readable_text_color(legacy["row_b"], light=legacy["text"], dark=legacy["dark_text"]),
            "vault_secondary_text": with_alpha(legacy["muted"] if sleek or set_top_box else readable_text_color(legacy["row_b"], light=legacy["text"], dark=legacy["dark_text"]), 220),
            "vault_muted_text": with_alpha(legacy["muted"] if sleek or set_top_box else readable_text_color(legacy["row_b"], light=legacy["text"], dark=legacy["dark_text"]), 176),
            "vault_selected_text": selected_text if sleek or set_top_box else pf_selected_text,
            "vault_header_text": pf_header_text if promised_future else (primary_text if sleek else with_alpha(primary_text, 232)),
            "vault_button_bg": with_alpha(legacy["row_b"], 206 if sleek else (242 if set_top_box else 248)),
            "vault_button_border": subtle_border if sleek else (with_alpha(legacy.get("stb_bevel_dark", normal_border), 214) if set_top_box else pf_grid_line),
            "vault_button_text": primary_text if sleek or set_top_box else pf_panel_text,
            "vault_button_focused_bg": guide_selected_bg,
            "vault_button_focused_border": selected_border if sleek else (QColor(255, 230, 96, 245) if set_top_box or promised_future else selected_border),
            "vault_button_focused_text": selected_text if sleek or set_top_box else pf_selected_text,
            "vault_chip_bg": with_alpha(legacy["row_a"], 188 if sleek else (234 if set_top_box else 230)),
            "vault_chip_text": with_alpha(primary_text if sleek or set_top_box else pf_panel_text, 224),
            "vault_chip_selected_bg": guide_selected_bg,
            "vault_chip_selected_text": selected_text if sleek or set_top_box else pf_selected_text,
            "vault_clock_top": QColor(34, 8, 8, 252) if set_top_box else (pf_time_top if promised_future else with_alpha(legacy["row_b"], 150)),
            "vault_clock_bottom": QColor(8, 0, 0, 252) if set_top_box else (pf_time_bottom if promised_future else with_alpha(legacy["row_b"], 190)),
            "vault_clock_text": QColor(255, 86, 76, 255) if set_top_box else (pf_header_text if promised_future else primary_text),
            "vault_focus_ring": selected_border if sleek else (QColor(255, 230, 96, 245) if set_top_box or promised_future else selected_border),
            "vault_focus_glow": with_alpha(legacy["selected"], 88 if set_top_box or promised_future else (70 if sleek else 74)),
            "vault_radius": 8 if sleek else (2 if set_top_box else 14),
            "vault_card_radius": 8 if sleek else (2 if set_top_box else 12),
            "vault_texture_alpha": 0 if sleek else (34 if set_top_box else 12),
            "dialog_background": dialog_bg,
            "dialog_panel": with_alpha(legacy["panel"], 198 if sleek else 250),
            "dialog_text": panel_text,
            "dialog_note_text": with_alpha(panel_text, 210),
            "input_background": input_bg,
            "input_text": input_text,
            "button_background": with_alpha(legacy["row_b"], 218 if sleek else 238),
            "button_selected_background": legacy["selected"],
            "overlay_scrim": QColor(0, 0, 0, 118 if sleek else 150),
            "stars_of_uranus": bool(legacy.get("stars_of_uranus")),
            "settings_panel_background": legacy["bg"] if legacy.get("starfield") or legacy.get("stars_of_uranus") or sleek else legacy["panel"],
            "settings_panel_overlay": QColor(255, 255, 255, 10) if sleek else QColor(0, 0, 0, 78 if legacy.get("starfield") or legacy.get("stars_of_uranus") else 18),
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
            "pf_font_family": None,
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


def app_theme(theme_name, skin_name=None, mode=None):
    skin_name = normalize_skin_name(skin_name or DEFAULT_SKIN_NAME)
    canonical = normalize_theme_name(theme_name)
    family = APP_THEMES_BY_SKIN.get(skin_name, APP_THEMES_BY_SKIN[DEFAULT_SKIN_NAME])
    if mode is not None:
        definitions = GUIDE_THEME_DEFINITIONS.get(skin_name, GUIDE_THEME_DEFINITIONS[DEFAULT_SKIN_NAME])
        legacy = definitions.get(canonical)
        if legacy is None:
            default_name = DEFAULT_THEME_NAME if DEFAULT_THEME_NAME in definitions else next(iter(definitions))
            canonical = default_name
            legacy = definitions[default_name]
        return build_app_theme_tokens(canonical, legacy, skin_name, mode=mode)
    if canonical in family:
        return family[canonical]
    default_name = DEFAULT_THEME_NAME if DEFAULT_THEME_NAME in family else next(iter(family))
    return family.get(default_name) or next(iter(family.values()))


SKIN_THEME_MAP = {
    "Promised Future": ["Stars of Uranus", "Silver Olive", "Iron Ingot", "Green Been", "Grape Jelly", "Charcoal", "Tangerine Dream", "Blue Berry"],
    "Set Top Box": ["Stars of Uranus", "Silver Olive", "Iron Ingot", "Green Been", "Grape Jelly", "Blue Berry", "Get Slimed"],
    "Sleek Freak": ["Stars of Uranus", "Silver Olive", "Grape Jelly", "Baby Blue", "Millennial Grey"],
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

CUSTOM_THEMES_VERSION = 1
CUSTOM_THEMES_FILE = os.path.join(os.getcwd(), "custom_themes.json")


def configure_custom_themes_file(path):
    """Point custom theme load/save helpers at the app's writable custom_themes.json path."""
    global CUSTOM_THEMES_FILE
    CUSTOM_THEMES_FILE = path


def normalize_theme_id(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def _builtin_theme_id(skin_name, theme_name):
    return f"{normalize_theme_id(skin_name)}:{normalize_theme_id(theme_name)}"


def custom_themes_config_defaults():
    return {
        "custom_theme_version": CUSTOM_THEMES_VERSION,
        "themes": [],
    }


def _color_to_tuple(color):
    if isinstance(color, QColor):
        return (color.red(), color.green(), color.blue(), color.alpha())
    return None


def _coerce_color(value):
    if isinstance(value, QColor):
        return value
    if isinstance(value, str):
        text = value.strip()
        if re.match(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$", text):
            red = int(text[1:3], 16)
            green = int(text[3:5], 16)
            blue = int(text[5:7], 16)
            alpha = int(text[7:9], 16) if len(text) == 9 else 255
            return QColor(red, green, blue, alpha)
    if isinstance(value, (list, tuple)) and len(value) in (3, 4):
        try:
            channels = [max(0, min(255, int(part))) for part in value]
        except (TypeError, ValueError):
            return None
        if len(channels) == 3:
            channels.append(255)
        return QColor(*channels)
    if isinstance(value, dict):
        try:
            red = int(value.get("r", value.get("red")))
            green = int(value.get("g", value.get("green")))
            blue = int(value.get("b", value.get("blue")))
            alpha = int(value.get("a", value.get("alpha", 255)))
        except (TypeError, ValueError):
            return None
        return QColor(max(0, min(255, red)), max(0, min(255, green)), max(0, min(255, blue)), max(0, min(255, alpha)))
    return None


def list_builtin_themes():
    result = []
    for skin_name, names in SKIN_THEME_MAP.items():
        for theme_name in names:
            result.append({
                "id": _builtin_theme_id(skin_name, theme_name),
                "name": theme_name,
                "skin": skin_name,
                "base_theme": theme_name,
                "custom": False,
            })
    return result


def get_builtin_theme(theme_id, skin_name=None, mode=None):
    if skin_name:
        return app_theme(theme_id, skin_name, mode=mode)
    wanted = normalize_theme_id(theme_id)
    for item in list_builtin_themes():
        if wanted in {normalize_theme_id(item["id"]), normalize_theme_id(item["name"])}:
            return app_theme(item["name"], item["skin"], mode=mode)
    return None


def normalize_custom_theme(value):
    source = value if isinstance(value, dict) else {}
    normalized = dict(source)
    raw_id = str(normalized.get("id", "") or "").strip()
    raw_name = str(normalized.get("name", "") or "").strip()
    normalized["id"] = normalize_theme_id(raw_id or raw_name)
    normalized["name"] = raw_name or raw_id or normalized["id"]
    normalized["base_theme"] = str(normalized.get("base_theme", DEFAULT_THEME_NAME) or DEFAULT_THEME_NAME).strip()
    colors = normalized.get("colors")
    normalized["colors"] = dict(colors) if isinstance(colors, dict) else {}
    fonts = normalized.get("fonts")
    normalized["fonts"] = dict(fonts) if isinstance(fonts, dict) else {}
    normalized["logo_style"] = str(normalized.get("logo_style", "") or "").strip()
    normalized["guide_style"] = str(normalized.get("guide_style", "") or "").strip()
    normalized["notes"] = str(normalized.get("notes", "") or "").strip()
    return normalized


def _base_theme_record(base_theme):
    base_name = normalize_theme_name(base_theme)
    for item in list_builtin_themes():
        if base_name == item["name"] or normalize_theme_id(base_name) == normalize_theme_id(item["id"]):
            return item
    return None


def _resolved_custom_theme_tokens(theme):
    base = _base_theme_record(theme.get("base_theme"))
    if base is None:
        base = _base_theme_record(DEFAULT_THEME_NAME)
    tokens = dict(app_theme(base["name"], base["skin"])) if base else {}
    for key, value in (theme.get("colors") or {}).items():
        color = _coerce_color(value)
        if color is not None:
            tokens[key] = color
    for key, value in (theme.get("fonts") or {}).items():
        if isinstance(value, str) and value.strip():
            tokens[key] = value.strip()
    return tokens


def validate_custom_theme(value, known_ids=None):
    warnings = []
    if not isinstance(value, dict):
        return ["custom theme is not a dict; skipped"]
    theme = normalize_custom_theme(value)
    if not theme.get("id"):
        warnings.append("custom theme is missing id/name")
    base = _base_theme_record(theme.get("base_theme"))
    if base is None:
        warnings.append(f"custom theme '{theme.get('id') or '?'}' references missing base_theme '{theme.get('base_theme')}'")
    colors = theme.get("colors") or {}
    for key, color_value in colors.items():
        if _coerce_color(color_value) is None:
            warnings.append(f"custom theme '{theme.get('id') or '?'}' has invalid color '{key}'")
    if known_ids is not None and theme.get("id") in known_ids:
        warnings.append(f"duplicate custom theme id '{theme['id']}'")
    return warnings


def normalize_custom_themes_config(data):
    source = data if isinstance(data, dict) else {}
    normalized = dict(source)
    normalized["custom_theme_version"] = CUSTOM_THEMES_VERSION
    raw_themes = source.get("themes") if isinstance(source.get("themes"), list) else []
    normalized["themes"] = [normalize_custom_theme(item) for item in raw_themes if isinstance(item, dict)]
    return normalized


def load_custom_themes_config(path=None):
    path = path or CUSTOM_THEMES_FILE
    warnings = []
    if not path or not os.path.exists(path):
        config = custom_themes_config_defaults()
        config["warnings"] = warnings
        return config
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (json.JSONDecodeError, OSError):
        config = custom_themes_config_defaults()
        config["warnings"] = ["custom themes config is malformed; defaults will be used"]
        return config
    if not isinstance(raw, dict):
        config = custom_themes_config_defaults()
        config["warnings"] = ["custom themes config is not a dict; defaults will be used"]
        return config
    config = normalize_custom_themes_config(raw)
    config["warnings"] = warnings
    return config


def save_custom_themes_config(config, path=None):
    path = path or CUSTOM_THEMES_FILE
    save_json_file(path, normalize_custom_themes_config(config))


def list_available_themes(config=None):
    config = config if isinstance(config, dict) else load_custom_themes_config()
    available = list_builtin_themes()
    seen_custom = set()
    for item in config.get("themes", []) or []:
        theme = normalize_custom_theme(item)
        warnings = validate_custom_theme(theme, known_ids=seen_custom)
        if warnings:
            continue
        seen_custom.add(theme["id"])
        base = _base_theme_record(theme.get("base_theme"))
        available.append({
            "id": theme["id"],
            "name": theme["name"],
            "skin": base["skin"] if base else DEFAULT_SKIN_NAME,
            "base_theme": theme["base_theme"],
            "custom": True,
            "theme": _resolved_custom_theme_tokens(theme),
            "source": theme,
        })
    return available


def themes_diagnostics(config=None, log=False):
    config = config if isinstance(config, dict) else load_custom_themes_config()
    warnings = list(config.get("warnings", []) or [])
    seen = set()
    duplicate_ids = []
    missing_base_refs = []
    valid_count = 0
    for item in config.get("themes", []) or []:
        theme = normalize_custom_theme(item)
        item_warnings = validate_custom_theme(theme, known_ids=seen)
        if theme.get("id") in seen:
            duplicate_ids.append(theme.get("id"))
        if _base_theme_record(theme.get("base_theme")) is None:
            missing_base_refs.append(theme.get("base_theme"))
        warnings.extend(item_warnings)
        if not item_warnings:
            valid_count += 1
        if theme.get("id"):
            seen.add(theme["id"])
    summary = {
        "custom_theme_version": config.get("custom_theme_version", CUSTOM_THEMES_VERSION),
        "builtin_theme_count": len(list_builtin_themes()),
        "custom_theme_count": valid_count,
        "invalid_custom_theme_warnings": warnings,
        "duplicate_theme_ids": duplicate_ids,
        "missing_base_theme_references": missing_base_refs,
    }
    if log:
        print(
            "[Themes] builtins={bt} custom={ct} warnings={wc}".format(
                bt=summary["builtin_theme_count"],
                ct=summary["custom_theme_count"],
                wc=len(warnings),
            ),
            flush=True,
        )
        for warning in warnings:
            print(f"[Themes][warn] {warning}", flush=True)
    return summary


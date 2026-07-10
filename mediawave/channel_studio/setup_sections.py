"""The five section builders for Channel Studio's real Setup dialog
(see channel_setup.py). Each function returns one page widget; keeping
them here (rather than inline in channel_setup.py) is what keeps that
file to just the dialog shell/section-switching.

Every "real" action funnels through channel_actions.py, which is the
only place that touches the live AdvancedConfigDialog widgets these
settings actually live on -- nothing here writes to app_settings or
disk directly.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import channel_actions
from .channel_studio_cards import build_drafts_section
from .channel_studio_widgets import build_info_card, build_schedule_timeline
from .studio_styles import style_choice_button

# Local (and NetTV, which reuses the exact same override mechanism --
# see resolve_channel_commercial_profile in channelsurfer2000.py, which
# doesn't distinguish channel type) commercial mode copy, matched to
# the three real states commercials_summary_label ever returns.
_COMMERCIALS_MODE_COPY = {
    "Default": "Use the shared commercial library.",
    "Off": "Do not play commercials on this channel.",
    "Custom": "Use this channel's own commercial settings.",
}
_NETTV_COMMERCIALS_MODE_COPY = {
    "Default": "Play short commercial breaks between videos, pulled from the shared commercial library.",
    "Off": "Skip commercial breaks between videos on this channel.",
    "Custom": "Use NetTV's own commercial settings for the breaks between videos.",
}


def _companion_type(channel_info, summary):
    if summary is not None:
        return summary.channel_type if getattr(summary, "is_companion", False) else None
    channel_id = str(channel_info.get("id", "") or "")
    return channel_id.split(":", 1)[-1] if channel_id.startswith("special:") else None


def build_overview_section(dialog, channel_info, summary, on_navigate_commercials):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 4, 2, 4)
    layout.setSpacing(10)

    channel_name = channel_info.get("name", "Channel")
    channel_id = channel_info.get("id", "")
    companion_type = _companion_type(channel_info, summary)
    channel_type_label = "Companion channel" if companion_type else "Folder channel"
    source_label = "Built in" if companion_type else "Local folder"

    meta_lines = [
        f"Channel {channel_info.get('default_number', '')}",
        f"Type: {channel_type_label}",
        f"Source: {source_label}",
    ]
    if summary is not None and not companion_type:
        meta_lines.append(f"Playback: {summary.playback_order_label} order")

    layout.addWidget(build_info_card(channel_name, None, meta_lines=meta_lines))

    enabled_card = QWidget()
    enabled_layout = QVBoxLayout(enabled_card)
    enabled_layout.setContentsMargins(0, 0, 0, 0)
    box = QCheckBox("Enabled")
    if companion_type:
        box.setChecked(True)
        box.toggled.connect(lambda checked, ct=companion_type: channel_actions.set_companion_enabled_on_dialog(dialog, ct, checked))
        box.setToolTip("Updates your real settings immediately. Click Save in Advanced Configuration to make it stick.")
    else:
        live = channel_actions.local_channel_enabled_from_dialog(dialog, channel_id)
        box.setChecked(bool(live) if live is not None else True)
        box.toggled.connect(lambda checked, cid=channel_id: channel_actions.set_local_channel_enabled(dialog, cid, checked))
        box.setToolTip("Updates your real settings immediately. Click Save in Advanced Configuration to make it stick.")
    enabled_layout.addWidget(box)
    layout.addWidget(enabled_card)

    # NetTV shares the real commercial-override mechanism with local
    # channels (see build_commercials_section's docstring for why) --
    # only WeatherStar/RadioWaveTV are genuinely "not applicable".
    commercials_supported = not companion_type or companion_type == "youtube"
    commercials_label = channel_actions.commercials_summary_label(dialog, channel_name) if commercials_supported else "Not applicable"
    layout.addWidget(
        build_info_card(
            f"Commercials: {commercials_label}",
            None if not commercials_supported else "See the Commercials section for per-channel controls.",
            buttons=None if not commercials_supported else [("Go to Commercials", lambda checked=False: on_navigate_commercials())],
        )
    )

    layout.addStretch(1)
    return page


def build_logo_section(dialog, channel_info, summary):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 4, 2, 4)
    layout.setSpacing(10)

    companion_type = _companion_type(channel_info, summary)
    if companion_type:
        layout.addWidget(
            build_info_card(
                "No custom logo for companion channels",
                "WeatherStar, RadioWaveTV, and NetTV use their own built-in on-screen look "
                "there's no channel logo image to set here.",
            )
        )
        layout.addStretch(1)
        return page

    logo_path = getattr(summary, "logo_path", "") if summary is not None else ""
    channel_name = channel_info.get("name", "Channel")
    if logo_path:
        pixmap = QPixmap(logo_path)
    else:
        pixmap = None

    if pixmap is not None and not pixmap.isNull():
        preview = QLabel()
        preview.setPixmap(pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        preview.setAlignment(Qt.AlignCenter)
        layout.addWidget(build_info_card(f"{channel_name}'s logo", None))
        layout.addWidget(preview, 0, Qt.AlignLeft)
    else:
        layout.addWidget(
            build_info_card(
                "No logo detected yet",
                "MediaWave2000 looks for a logo image in this channel's own Logos folder "
                "(logo.png, bug.png, or a file named after the channel). Add one there and "
                "it'll show up automatically the card doesn't need any changes here.",
            )
        )

    layout.addWidget(
        build_info_card(
            "Logo display",
            "Corner, size, opacity, and timing use the shared default unless you customize "
            "them for this channel specifically.",
            buttons=[
                (
                    "Customize Logo Display",
                    lambda checked=False: channel_actions.open_logo_overrides_for_channel(dialog, channel_name),
                )
            ],
        )
    )

    layout.addStretch(1)
    return page


def build_commercials_section(dialog, channel_info, summary):
    """Commercials Setup v2 -- a real control panel, not a placeholder.

    Local channels and NetTV (channel_type "youtube") share the exact
    same three-state control: NetTV's per-video filler breaks are
    resolved through resolve_channel_commercial_profile the same way a
    local channel's scheduled breaks are (channelsurfer2000.py), so the
    same channel_actions.py helpers apply safely -- only the copy
    changes, since NetTV's "commercials" are short filler between
    videos, not a scheduled program-break timeline.

    WeatherStar and RadioWaveTV never touch commercial logic anywhere
    in the app (confirmed: apply_channel_schedules only builds
    schedules for channel_type == "media", and nothing else references
    resolve_channel_commercial_profile for either type) -- so those two
    stay informational-only, honestly, rather than offering controls
    that would silently do nothing.
    """
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 4, 2, 4)
    layout.setSpacing(10)

    companion_type = _companion_type(channel_info, summary)
    if companion_type in ("weatherstar", "radiowave"):
        layout.addWidget(
            build_info_card(
                "Commercials don't apply here",
                "Commercials for this companion channel are managed by its own playback "
                "mode there's no per-channel commercial setting to control.",
            )
        )
        layout.addStretch(1)
        return page

    is_nettv = companion_type == "youtube"
    mode_copy = _NETTV_COMMERCIALS_MODE_COPY if is_nettv else _COMMERCIALS_MODE_COPY
    channel_name = channel_info.get("name", "Channel")

    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(10)
    layout.addWidget(body)
    layout.addStretch(1)

    def _render():
        # Rebuilt in place (not a fresh page) so the status and the
        # highlighted choice both update immediately after a click,
        # without reopening Setup.
        while body_layout.count():
            item = body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        mode = channel_actions.commercials_summary_label(dialog, channel_name)
        description = mode_copy.get(mode, mode_copy["Default"])
        if mode == "Default":
            status_lines = [
                channel_actions.commercial_library_status(dialog),
                f"Timed breaks: {channel_actions.channel_timed_breaks_label(dialog, channel_name)}",
                f"Channel override: {channel_actions.channel_override_summary(dialog, channel_name)}",
            ]
        else:
            status_lines = []
        if is_nettv:
            status_lines.insert(0, "Applies to: short breaks between videos, not a full schedule")

        body_layout.addWidget(
            build_info_card(f"Commercials: {mode}", description, meta_lines=status_lines)
        )

        choice_row = QWidget()
        choice_layout = QHBoxLayout(choice_row)
        choice_layout.setContentsMargins(0, 0, 0, 0)
        choice_layout.setSpacing(8)
        for choice_mode, choice_label, on_click in (
            ("Default", "Use Default", lambda: _set_mode("inherit")),
            ("Off", "Turn Off Commercials", lambda: _set_mode("off")),
            ("Custom", "Customize This Channel", lambda: _customize()),
        ):
            btn = QPushButton(choice_label)
            btn.setCursor(Qt.PointingHandCursor)
            style_choice_button(btn, active=(mode == choice_mode))
            btn.clicked.connect(lambda checked=False, action=on_click: action())
            choice_layout.addWidget(btn, 1)
        body_layout.addWidget(choice_row)

    def _set_mode(new_mode):
        channel_actions.set_channel_commercial_override_mode(dialog, channel_name, new_mode)
        _render()

    def _customize():
        channel_actions.open_commercial_overrides_for_channel(dialog, channel_name)
        _render()

    _render()
    return page


def build_programming_section(setup_dialog, dialog, channel_info, summary, schedule, drafts_path):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 4, 2, 4)
    layout.setSpacing(10)

    companion_type = _companion_type(channel_info, summary)
    if companion_type:
        layout.addWidget(
            build_info_card(
                "Automatic programming",
                "This channel's lineup is generated automatically there's no manual "
                "programming to manage here.",
            )
        )
        layout.addStretch(1)
        return page

    if summary is not None:
        counts = []
        if summary.show_count:
            counts.append(f"{summary.show_count} show" + ("s" if summary.show_count != 1 else ""))
        if summary.movie_count:
            counts.append(f"{summary.movie_count} movie" + ("s" if summary.movie_count != 1 else ""))
        count_text = " · ".join(counts) if counts else "No content detected yet"
        layout.addWidget(
            build_info_card(
                f"Playback: {summary.playback_order_label} order",
                count_text,
            )
        )

    if schedule is not None and schedule.has_data:
        layout.addWidget(build_schedule_timeline(schedule.channel_name, schedule.slots))
    else:
        layout.addWidget(
            build_info_card(
                "No lineup yet",
                "Once this channel is playing, tonight's lineup will show up here.",
            )
        )

    layout.addWidget(build_drafts_section(setup_dialog, dialog, drafts_path))
    layout.addStretch(1)
    return page


def build_advanced_section(channel_info, summary):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 4, 2, 4)
    layout.setSpacing(10)

    meta_lines = [f"Channel ID: {channel_info.get('id', '')}"]
    root_path = channel_info.get("root_path") or (getattr(summary, "root_path", "") if summary else "")
    if root_path:
        meta_lines.append(f"Folder: {root_path}")
    if summary is not None and summary.has_hints:
        hint_bits = []
        if summary.airing_rule_count:
            hint_bits.append(f"{summary.airing_rule_count} airing rule" + ("s" if summary.airing_rule_count != 1 else ""))
        if summary.seasonal_rule_count:
            hint_bits.append(f"{summary.seasonal_rule_count} seasonal rule" + ("s" if summary.seasonal_rule_count != 1 else ""))
        meta_lines.append("Channel Hints: " + " · ".join(hint_bits))

    layout.addWidget(build_info_card("Advanced details", None, meta_lines=meta_lines))
    layout.addStretch(1)
    return page

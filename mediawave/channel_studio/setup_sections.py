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
from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from . import channel_actions
from .channel_studio_cards import build_drafts_section
from .channel_studio_widgets import build_info_card, build_schedule_timeline

_COMMERCIALS_MODE_LABELS = {"inherit": "Default", "on": "Custom (on)", "off": "Off"}


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

    if companion_type:
        commercials_label = "Not applicable"
    else:
        commercials_label = channel_actions.commercials_summary_label(dialog, channel_name)
    layout.addWidget(
        build_info_card(
            f"Commercials: {commercials_label}",
            None if companion_type else "See the Commercials section for per-channel controls.",
            buttons=None if companion_type else [("Go to Commercials", lambda checked=False: on_navigate_commercials())],
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
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 4, 2, 4)
    layout.setSpacing(10)

    companion_type = _companion_type(channel_info, summary)
    if companion_type:
        layout.addWidget(
            build_info_card(
                "Commercials don't apply here",
                "Companion channels (WeatherStar, RadioWaveTV, NetTV) don't play commercial "
                "breaks.",
            )
        )
        layout.addStretch(1)
        return page

    channel_name = channel_info.get("name", "Channel")

    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(body)
    layout.addStretch(1)

    def _render():
        # Rebuilt in place (not a fresh page) so the mode label updates
        # immediately after a button click without reopening Setup.
        while body_layout.count():
            item = body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        commercials_settings = getattr(dialog, "commercials_settings", None) or {}
        shared_enabled = bool(commercials_settings.get("enabled", False))
        shared_status = "Shared library: commercials on" if shared_enabled else "Shared library: commercials off"
        mode = channel_actions.channel_commercial_override_mode(dialog, channel_name)
        mode_label = _COMMERCIALS_MODE_LABELS.get(mode, "Default")

        body_layout.addWidget(
            build_info_card(
                f"This channel: {mode_label}",
                shared_status,
                meta_lines=["Custom clips still come from the shared Commercials folder."],
                buttons=[
                    ("Use Default Commercials", lambda checked=False: _set_mode("inherit")),
                    ("Disable Commercials For This Channel", lambda checked=False: _set_mode("off")),
                    ("Customize For This Channel", lambda checked=False: _customize()),
                ],
            )
        )

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

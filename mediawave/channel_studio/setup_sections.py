"""The five section builders for Channel Studio's real Setup dialog
(see channel_setup.py). Each function returns one page widget; keeping
them here (rather than inline in channel_setup.py) is what keeps that
file to just the dialog shell/section-switching.

Every "real" action funnels through channel_actions.py, which is the
only place that touches the live AdvancedConfigDialog widgets these
settings actually live on -- nothing here writes to app_settings or
disk directly.
"""

import os

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..channel_logos import (
    CHANNEL_BUG_SCREEN_ASPECT_OPTIONS,
    LOGO_TIMING_PRESETS,
    LOGO_TIMING_PRESETS_DROPDOWN_IDS,
    find_channel_bug_logo,
    logo_opacity_to_percent,
    logo_percent_to_opacity,
    logo_percent_to_size,
    logo_size_to_percent,
    scale_logo_dimensions,
    screen_aspect_dimensions,
)

# The Timing dropdown's own public list -- see LOGO_TIMING_PRESETS_DROPDOWN_IDS's
# docstring for why the other presets stay real without being offered here.
_LOGO_TIMING_DROPDOWN_PRESETS = [p for p in LOGO_TIMING_PRESETS if p["id"] in LOGO_TIMING_PRESETS_DROPDOWN_IDS]
from . import channel_actions
from .channel_studio_cards import build_drafts_section
from .channel_studio_widgets import (
    build_action_button_row,
    build_info_card,
    build_inline_value_editor,
    build_schedule_timeline,
)
from .logo_studio import LogoPreviewScreen, LogoTimingDialog, ShowExclusionsDialog
from .studio_styles import style_choice_button, style_slider

_LOGO_PREVIEW_REFERENCE_WIDTH = 1280.0
_LOGO_MODE_DESCRIPTIONS = {
    "Default": "Using the shared logo display settings.",
    "Custom": "This channel has its own logo position, size, and timing.",
    "Off": "The logo is turned off for this channel.",
}

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

    channel_id = channel_info.get("id", "")
    companion_type = _companion_type(channel_info, summary)
    channel_type_label = "Companion channel" if companion_type else "Folder channel"
    source_label = "Built in" if companion_type else "Local folder"

    channel_name = channel_actions.channel_name_from_dialog(dialog, channel_id) or channel_info.get("name", "Channel")

    meta_lines = [
        f"Type: {channel_type_label}",
        f"Source: {source_label}",
    ]
    if summary is not None and not companion_type:
        meta_lines.append(f"Playback: {summary.playback_order_label} order")

    layout.addWidget(build_info_card(channel_name, None, meta_lines=meta_lines))

    name_row = QHBoxLayout()
    name_row.setSpacing(10)
    name_caption = QLabel("Channel name")
    name_caption.setObjectName("fieldHelp")
    name_row.addWidget(name_caption)

    def _validate_name(candidate, cid=channel_id):
        return channel_actions.validate_channel_name_on_dialog(dialog, cid, candidate)

    def _apply_name(candidate, cid=channel_id):
        channel_actions.set_channel_name_on_dialog(dialog, cid, candidate)
        channel_actions.refresh_live_lineup(dialog)

    name_editor, _name_api = build_inline_value_editor(channel_name, _validate_name, _apply_name)
    name_row.addWidget(name_editor)
    name_row.addStretch(1)
    layout.addLayout(name_row)

    number_row = QHBoxLayout()
    number_row.setSpacing(10)
    number_caption = QLabel("Channel number")
    number_caption.setObjectName("fieldHelp")
    number_row.addWidget(number_caption)

    current_number = channel_actions.channel_number_from_dialog(dialog, channel_id)
    if current_number is None:
        try:
            current_number = int(channel_info.get("default_number", 1) or 1)
        except (TypeError, ValueError):
            current_number = 1

    def _validate_number(candidate, cid=channel_id):
        return channel_actions.validate_channel_number_on_dialog(dialog, cid, candidate)

    def _apply_number(candidate, cid=channel_id):
        channel_actions.set_channel_number_on_dialog(dialog, cid, int(candidate))
        channel_actions.refresh_live_lineup(dialog)

    number_editor, _number_api = build_inline_value_editor(
        str(current_number),
        _validate_number,
        _apply_number,
        label_formatter=lambda value: f"CH {int(value):03d}",
    )
    number_row.addWidget(number_editor)
    number_row.addStretch(1)
    layout.addLayout(number_row)

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
    """Logo Studio -- a compact interactive visual editor: drag the real
    logo (aspect-preserved, never stretched) freely around a simulated
    screen, resize/opacity via live sliders, pick the screen's own 4:3/
    16:9 shape, and pick a timing mode from a dropdown. Every real change
    funnels through channel_actions.py's channel_logo_* helpers into the
    exact same channel_bug_settings["channel_overrides"] dict the old
    Channel Logos (Advanced Configuration) tab's "Customize Individual
    Channels" dialog already reads and writes -- that dialog is kept
    intact and reachable here as "Advanced Logo Settings" for anything
    this panel doesn't expose directly (placement area, per-field manual
    entry).

    The preview is a static snapshot of position/size/opacity, not a
    timing simulation -- it never tries to act out when the logo would
    appear on air; the timing controls (dropdown + Advanced Timing) are
    still real settings, just not played back visually here.

    Deliberately a single compact screen, not a long scroll: the 9
    timing modes live in one dropdown (LogoTimingDialog handles anything
    finer-grained than a preset), and "Color effects" is a one-line note
    rather than a card -- grayscale_on_video is the one real tint the
    overlay supports, nothing else is offered as if it were real.
    """
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 4, 2, 4)
    layout.setSpacing(8)

    companion_type = _companion_type(channel_info, summary)
    channel_name = channel_info.get("name", "Channel")
    channel_id = channel_info.get("id", "")
    root_path = getattr(summary, "root_path", "") if summary is not None else ""
    # A live lookup, not the summary's own logo_path snapshot -- that
    # snapshot is taken once when Advanced Configuration is opened, so
    # it can go stale (or miss a logo dropped in after the fact) while
    # real playback (which calls this same function fresh every tune)
    # keeps finding it. Falls back to the snapshot only if the live
    # lookup comes up empty (e.g. root_path unavailable this session).
    # Companions have no root_path at all -- find_channel_bug_logo's
    # shared_logos_dir fallback (the portable User Content/Logos/ folder)
    # is the only path that can ever resolve one for them, keyed by their
    # display name (e.g. "WeatherStar 4000+.png").
    shared_logos_dir = getattr(dialog, "_shared_logos_dir", "")
    logo_path = find_channel_bug_logo(root_path, channel_name, shared_logos_dir=shared_logos_dir) or (
        getattr(summary, "logo_path", "") if summary is not None else ""
    )
    pixmap = None
    if logo_path:
        candidate = QPixmap(logo_path)
        if not candidate.isNull():
            pixmap = candidate

    note = QLabel("Drag the logo on the preview, or fine-tune it here.")
    note.setObjectName("sectionNote")
    note.setWordWrap(True)
    layout.addWidget(note)

    body = QHBoxLayout()
    body.setSpacing(14)
    body_wrap = QWidget()
    body_wrap.setLayout(body)
    layout.addWidget(body_wrap, 1)

    preview = LogoPreviewScreen()
    preview.set_logo(pixmap)
    preview.set_aspect(*screen_aspect_dimensions(channel_actions.channel_logo_screen_aspect(dialog, channel_name)))
    body.addWidget(preview, 3)

    controls = QWidget()
    controls_layout = QVBoxLayout(controls)
    controls_layout.setContentsMargins(0, 0, 0, 0)
    controls_layout.setSpacing(6)
    body.addWidget(controls, 2)

    # `state` holds the opacity/size the preview is currently showing --
    # kept separate from the committed override so a slider drag can
    # repaint the preview live without writing (and re-rendering the
    # whole panel around) on every tick. Only sliderReleased commits.
    state = {"opacity": 0.75, "size": 80}

    def _sync_state_from_settings():
        eff = channel_actions.channel_logo_effective_settings(dialog, channel_name)
        state["opacity"] = float(eff.get("opacity", 0.75) or 0.75)
        state["size"] = int(eff.get("size", 80) or 80)

    def _preview_scale():
        return max(1, preview.width()) / _LOGO_PREVIEW_REFERENCE_WIDTH

    def _preview_logo_dims(scale):
        # Preserve the source image's real aspect ratio -- the exact same
        # "fit inside size x size, keep proportions" rule real playback's
        # load_channel_bug_pixmap uses, so the preview never stretches a
        # non-square logo into a forced square box, and matches what
        # would actually be drawn on air.
        if pixmap is not None:
            real_w, real_h = scale_logo_dimensions(pixmap.width(), pixmap.height(), state["size"])
        else:
            real_w = real_h = state["size"]
        return max(16, int(real_w * scale)), max(16, int(real_h * scale))

    def _repaint_preview():
        scale = _preview_scale()
        logo_w, logo_h = _preview_logo_dims(scale)
        active = preview.active_rect()
        x, y = channel_actions.channel_logo_preview_position(
            dialog, channel_name, active.width(), active.height(), logo_w, logo_h
        )
        preview.set_geometry_state(x, y, logo_w, logo_h, state["opacity"])

    def _open_logos_folder():
        # A local channel's own per-folder Logos/ wins when it exists;
        # otherwise (including every companion, which has no root_path at
        # all) fall back to the shared User Content/Logos/ folder --
        # ensure_user_content_structure creates it on every startup, so
        # it should always exist by the time this runs.
        target = os.path.join(root_path, "Logos") if root_path else ""
        if not target or not os.path.isdir(target):
            target = shared_logos_dir if shared_logos_dir and os.path.isdir(shared_logos_dir) else (root_path or "")
        if target and os.path.isdir(target):
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))

    def _on_drop(x, y, active_w, active_h, logo_w, logo_h):
        # LogoPreviewScreen reports everything in active-area-relative
        # preview-canvas pixels (see LogoPreviewScreen.active_rect);
        # unscale back to the same real-px space the normalized drag
        # position is computed in before handing off to channel_actions.
        scale = _preview_scale()
        channel_actions.set_channel_logo_position_from_drop(
            dialog, channel_name,
            x / scale, y / scale, active_w / scale, active_h / scale, logo_w / scale, logo_h / scale,
        )
        _full_render()

    def _set_aspect(aspect):
        channel_actions.set_channel_logo_screen_aspect(dialog, channel_name, aspect)
        preview.set_aspect(*screen_aspect_dimensions(aspect))
        _full_render()

    preview.resized.connect(_repaint_preview)
    preview.logoDropped.connect(_on_drop)

    def _clear_controls():
        while controls_layout.count():
            item = controls_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_mode(mode):
        channel_actions.set_channel_logo_override_mode(dialog, channel_name, mode)
        _full_render()

    def _apply_preset(preset_id):
        channel_actions.apply_channel_logo_timing_preset(dialog, channel_name, preset_id)
        _full_render()

    def _reset():
        channel_actions.reset_channel_logo_override(dialog, channel_name)
        _full_render()

    def _open_advanced():
        channel_actions.open_logo_overrides_for_channel(dialog, channel_name)
        _full_render()

    def _open_advanced_timing():
        eff = channel_actions.channel_logo_effective_settings(dialog, channel_name)
        timing_dialog = LogoTimingDialog(eff.get("timing") or {}, parent=page)
        if timing_dialog.exec() and timing_dialog.result_timing is not None:
            channel_actions.set_channel_logo_override_fields(dialog, channel_name, timing=timing_dialog.result_timing)
            _full_render()

    def _open_show_exclusions():
        shows = channel_actions.channel_logo_available_shows(dialog, channel_id)
        excluded = channel_actions.channel_logo_excluded_shows(dialog, channel_name)
        exclusions_dialog = ShowExclusionsDialog(shows, excluded, parent=page)
        if exclusions_dialog.exec() and exclusions_dialog.result_excluded is not None:
            channel_actions.set_channel_logo_excluded_shows(dialog, channel_name, exclusions_dialog.result_excluded)
            _full_render()

    def _full_render():
        _clear_controls()
        _sync_state_from_settings()

        mode = channel_actions.channel_logo_mode_label(dialog, channel_name)
        preset_id = channel_actions.channel_logo_current_preset_id(dialog, channel_name)
        preset_label = next((p["label"] for p in LOGO_TIMING_PRESETS if p["id"] == preset_id), "Custom")
        status_lines = [
            f"Opacity: {logo_opacity_to_percent(state['opacity'])}%",
            f"Size: {logo_size_to_percent(state['size'])}%",
            f"Timing: {preset_label}",
        ]
        controls_layout.addWidget(
            build_info_card(f"Logo: {mode}", _LOGO_MODE_DESCRIPTIONS.get(mode, ""), meta_lines=status_lines)
        )

        if pixmap is None:
            no_logo_hint = (
                f"Add a PNG named \"{channel_name}\" to the shared User Content/Logos folder and it'll show up "
                "automatically -- companion channels don't have a folder of their own."
                if companion_type
                else "Add a PNG to this channel's Logos folder and it'll show up automatically."
            )
            controls_layout.addWidget(
                build_info_card(
                    "No logo image found",
                    no_logo_hint,
                    buttons=[("Open Logos Folder", lambda checked=False: _open_logos_folder())],
                )
            )

        # A wrapping FlowLayout row (not a QHBoxLayout) so this row's own
        # minimum width is just its widest single button, not the sum of
        # both -- keeps the panel from forcing extra width under a
        # larger UI scale or system font.
        mode_row, mode_buttons = build_action_button_row(
            [
                ("Use Default", lambda checked=False: _set_mode("global")),
                ("Off For This Channel", lambda checked=False: _set_mode("off")),
            ]
        )
        for choice_mode, btn in zip(("Default", "Off"), mode_buttons):
            btn.setCursor(Qt.PointingHandCursor)
            style_choice_button(btn, active=(mode == choice_mode))
        controls_layout.addWidget(mode_row)

        # Screen shape -- a real per-channel setting (see
        # channel_actions.set_channel_logo_screen_aspect), independent of
        # Default/Custom/Off. Changes the simulated screen's shape
        # immediately, not just a label.
        current_aspect = channel_actions.channel_logo_screen_aspect(dialog, channel_name)
        aspect_row_wrap = QWidget()
        aspect_row_layout = QHBoxLayout(aspect_row_wrap)
        aspect_row_layout.setContentsMargins(0, 0, 0, 0)
        aspect_row_layout.setSpacing(6)
        aspect_row_layout.addWidget(QLabel("Screen shape:"))
        aspect_row, aspect_buttons = build_action_button_row(
            [(label, lambda checked=False, a=label: _set_aspect(a)) for label in CHANNEL_BUG_SCREEN_ASPECT_OPTIONS]
        )
        for label, btn in zip(CHANNEL_BUG_SCREEN_ASPECT_OPTIONS, aspect_buttons):
            btn.setCursor(Qt.PointingHandCursor)
            style_choice_button(btn, active=(label == current_aspect))
        aspect_row_layout.addWidget(aspect_row, 1)
        controls_layout.addWidget(aspect_row_wrap)

        opacity_label = QLabel(f"Opacity: {logo_opacity_to_percent(state['opacity'])}%")
        opacity_label.setObjectName("fieldHelp")
        opacity_slider = QSlider(Qt.Horizontal)
        style_slider(opacity_slider)
        opacity_slider.setRange(10, 100)
        opacity_slider.setValue(logo_opacity_to_percent(state["opacity"]))

        def _on_opacity_change(value, lbl=opacity_label):
            lbl.setText(f"Opacity: {value}%")
            state["opacity"] = logo_percent_to_opacity(value)
            _repaint_preview()

        def _on_opacity_released():
            channel_actions.set_channel_logo_override_fields(dialog, channel_name, opacity=state["opacity"])
            _full_render()

        opacity_slider.valueChanged.connect(_on_opacity_change)
        opacity_slider.sliderReleased.connect(_on_opacity_released)

        size_label = QLabel(f"Size: {logo_size_to_percent(state['size'])}%")
        size_label.setObjectName("fieldHelp")
        size_slider = QSlider(Qt.Horizontal)
        style_slider(size_slider)
        size_slider.setRange(0, 100)
        size_slider.setValue(logo_size_to_percent(state["size"]))

        def _on_size_change(value, lbl=size_label):
            lbl.setText(f"Size: {value}%")
            state["size"] = logo_percent_to_size(value)
            _repaint_preview()

        def _on_size_released():
            channel_actions.set_channel_logo_override_fields(dialog, channel_name, size=state["size"])
            _full_render()

        size_slider.valueChanged.connect(_on_size_change)
        size_slider.sliderReleased.connect(_on_size_released)

        # Opacity and size side by side, not stacked -- Logo Studio's
        # whole point is fitting the preview + controls on one screen,
        # not a tall scrolling column.
        slider_grid = QWidget()
        slider_grid_layout = QGridLayout(slider_grid)
        slider_grid_layout.setContentsMargins(0, 0, 0, 0)
        slider_grid_layout.setHorizontalSpacing(20)
        slider_grid_layout.setVerticalSpacing(2)
        slider_grid_layout.addWidget(opacity_label, 0, 0)
        slider_grid_layout.addWidget(size_label, 0, 1)
        slider_grid_layout.addWidget(opacity_slider, 1, 0)
        slider_grid_layout.addWidget(size_slider, 1, 1)
        controls_layout.addWidget(slider_grid)

        eff = channel_actions.channel_logo_effective_settings(dialog, channel_name)
        gray_check = QCheckBox("Show on-screen logo in grayscale")
        gray_check.setToolTip("Grayscale only applies to the video overlay -- the Info screen logo stays full color.")
        gray_check.setChecked(bool(eff.get("grayscale_on_video", False)))

        def _on_gray_toggled(checked):
            channel_actions.set_channel_logo_override_fields(dialog, channel_name, grayscale_on_video=checked)
            _full_render()

        gray_check.toggled.connect(_on_gray_toggled)
        controls_layout.addWidget(gray_check)

        color_note = QLabel("More effects later.")
        color_note.setObjectName("fieldHelp")
        controls_layout.addWidget(color_note)

        timing_row = QWidget()
        timing_row_layout = QHBoxLayout(timing_row)
        timing_row_layout.setContentsMargins(0, 0, 0, 0)
        timing_row_layout.setSpacing(6)
        timing_row_layout.addWidget(QLabel("Timing:"))
        timing_combo = QComboBox()
        # The longest label ("Per-Show Start + Random Returns") would
        # otherwise force the whole combo -- and the panel around it --
        # wide enough to show it without eliding. Cap the box itself to
        # a reasonable width; the full label is still visible in the
        # open dropdown and as a tooltip.
        timing_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        timing_combo.setMinimumContentsLength(14)
        timing_combo.addItem("Custom", None)
        for preset in _LOGO_TIMING_DROPDOWN_PRESETS:
            timing_combo.addItem(preset["label"], preset["id"])
            idx = timing_combo.count() - 1
            timing_combo.setItemData(idx, preset["description"], Qt.ToolTipRole)
        match_index = timing_combo.findData(preset_id) if preset_id else 0
        timing_combo.setCurrentIndex(match_index if match_index >= 0 else 0)
        timing_combo.currentIndexChanged.connect(
            lambda index, combo=timing_combo: _apply_preset(combo.itemData(index)) if combo.itemData(index) else None
        )
        timing_row_layout.addWidget(timing_combo, 1)
        controls_layout.addWidget(timing_row)

        actions_row, _ = build_action_button_row(
            [
                ("Advanced Timing…", lambda checked=False: _open_advanced_timing()),
                ("Show Exclusions…", lambda checked=False: _open_show_exclusions()),
                ("Advanced Logo Settings", lambda checked=False: _open_advanced()),
                ("Reset to Default", lambda checked=False: _reset()),
            ]
        )
        controls_layout.addWidget(actions_row)

        controls_layout.addStretch(1)
        _repaint_preview()

    _full_render()
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

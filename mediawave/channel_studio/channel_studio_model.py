"""Plain data shapes for Channel Studio (Preview) read-only summaries.

No filesystem, Qt, or settings-writing logic lives here — just the shape
of a channel's studio summary plus small, pure formatting helpers.
"""

from dataclasses import dataclass, field

# WeatherStar/RadioWaveTV/NetTV -- built-in, non-folder channels. See
# companion_adapter.py for how their summaries get built; this module
# only needs to know their type names to pick the right headline/info
# rows for a card.
COMPANION_CHANNEL_TYPES = ("weatherstar", "radiowave", "youtube")


@dataclass
class ChannelStudioSummary:
    """A read-only snapshot of one channel, built from existing app data."""

    channel_id: str
    name: str
    number: int
    channel_type: str = "media"
    root_path: str = ""
    logo_path: str = ""
    show_count: int = 0
    movie_count: int = 0
    content_known: bool = False
    playback_order_label: str = "Random"
    commercials_enabled: bool = False
    commercials_label: str = "Commercials off"
    airing_rule_count: int = 0
    seasonal_rule_count: int = 0
    # Companion-only: a short label/value pair for the one piece of
    # type-specific status worth showing (WeatherStar's location,
    # RadioWaveTV's music folder, NetTV's playlist) -- see
    # companion_adapter.companion_summaries. Unused for "media" channels.
    companion_info_label: str = ""
    companion_info_value: str = ""

    @property
    def is_companion(self):
        return self.channel_type in COMPANION_CHANNEL_TYPES

    @property
    def has_hints(self):
        return self.airing_rule_count > 0 or self.seasonal_rule_count > 0

    @property
    def headline(self):
        """A one-line, friendly summary for a channel card."""
        if self.is_companion:
            return "Companion channel"
        if self.channel_type != "media":
            return "Special channel · built in"
        if not self.content_known:
            return "Folder channel · ready to play"
        parts = []
        if self.show_count:
            parts.append(f"{self.show_count} show" + ("s" if self.show_count != 1 else ""))
        if self.movie_count:
            parts.append(f"{self.movie_count} movie" + ("s" if self.movie_count != 1 else ""))
        if not parts:
            parts.append("No content detected yet")
        parts.append("commercials on" if self.commercials_enabled else "commercials off")
        return " · ".join(parts)


@dataclass
class ScheduleSlot:
    """One entry in a Tonight's Schedule preview lineup."""

    time_label: str
    title: str
    kind: str = "content"  # "content" | "block" | "placeholder"


@dataclass
class TonightSchedule:
    """A read-only tonight's-lineup preview for a single channel."""

    channel_id: str
    channel_name: str
    slots: list = field(default_factory=list)
    has_data: bool = True

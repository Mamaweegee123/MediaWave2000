"""Read-only data shapes for Channel Studio's future programming pipeline.

These are plain dataclasses plus a small set of example presets — nothing
here reads or writes real schedule, library, or settings data, and nothing
here is wired into the scheduling engine. The goal of this module is only
to establish the shape that real programming blocks will eventually take,
so the Channel Studio preview UI has something with personality to show
instead of generic placeholder rows.
"""

from dataclasses import dataclass, field


@dataclass
class ProgrammingBlock:
    """A named identity for a recurring chunk of a broadcast day.

    Mirrors how a real network names its dayparts (e.g. "Prime Time")
    rather than exposing raw start/end times as the primary label.
    """

    key: str
    title: str
    description: str
    typical_airtime: str
    commercial_profile: str = "None"
    bumper_set: str = "None"
    branding_style: str = "Standard"


@dataclass
class ProgrammingPreset:
    """A ready-made grouping of blocks a user could apply to a channel."""

    key: str
    name: str
    description: str
    block_keys: list = field(default_factory=list)


@dataclass
class ProgrammingSuggestion:
    """A friendly, one-click "quick action" idea shown to the user.

    `icon` is an emoji shown alongside the title. Nothing about a
    suggestion is executable on its own — the UI layer decides what
    (if anything) happens when one is chosen.
    """

    title: str
    description: str
    icon: str = "✨"


DEFAULT_PROGRAMMING_BLOCKS = [
    ProgrammingBlock(
        key="morning_cartoons",
        title="Morning Cartoons",
        description="A bright, bouncy start to the day — the shows kids beg to wake up for.",
        typical_airtime="6:00 AM – 10:00 AM",
        commercial_profile="Kids Daytime",
        bumper_set="Channel IDs",
        branding_style="Bright & Bouncy",
    ),
    ProgrammingBlock(
        key="after_school",
        title="After School",
        description="The lineup that's on the second backpacks hit the floor.",
        typical_airtime="3:00 PM – 6:00 PM",
        commercial_profile="Kids Daytime",
        bumper_set="Channel IDs",
        branding_style="Bright & Bouncy",
    ),
    ProgrammingBlock(
        key="prime_time",
        title="Prime Time",
        description="The main event — the shows the whole household sits down for.",
        typical_airtime="8:00 PM – 10:00 PM",
        commercial_profile="Prime",
        bumper_set="Block Starts",
        branding_style="Standard",
    ),
    ProgrammingBlock(
        key="late_night",
        title="Late Night",
        description="Slower, moodier programming for the night owls still watching.",
        typical_airtime="12:00 AM – 6:00 AM",
        commercial_profile="Night",
        bumper_set="Adult Swim Style",
        branding_style="Moody",
    ),
    ProgrammingBlock(
        key="movie_night",
        title="Movie Night",
        description="A full feature presentation, trailers and all.",
        typical_airtime="8:00 PM – 11:00 PM",
        commercial_profile="Movies",
        bumper_set="Block Starts",
        branding_style="Feature Presentation",
    ),
    ProgrammingBlock(
        key="holiday_marathon",
        title="Holiday Marathon",
        description="A seasonal takeover — back-to-back specials for the time of year.",
        typical_airtime="All Day",
        commercial_profile="Holiday",
        bumper_set="Holiday",
        branding_style="Seasonal",
    ),
]


DEFAULT_PROGRAMMING_PRESETS = [
    ProgrammingPreset(
        key="classic_kids_network",
        name="Classic Kids Network",
        description="Cartoons all day, sitcoms after dark — the format that built Saturday mornings.",
        block_keys=["morning_cartoons", "after_school", "prime_time", "late_night"],
    ),
    ProgrammingPreset(
        key="movie_channel",
        name="Movie Channel",
        description="Feature presentations from open to close, with a marathon on holidays.",
        block_keys=["movie_night", "holiday_marathon"],
    ),
]


QUICK_ACTION_SUGGESTIONS = [
    ProgrammingSuggestion(
        title="Make Tonight More Random",
        description="Shuffle tonight's lineup for a little more surprise.",
        icon="✨",
    ),
    ProgrammingSuggestion(
        title="Add Movie Night",
        description="Drop a feature presentation into tonight's schedule.",
        icon="🎬",
    ),
    ProgrammingSuggestion(
        title="Start Night Block Earlier",
        description="Pull your late-night lineup up to an earlier start.",
        icon="🌙",
    ),
    ProgrammingSuggestion(
        title="Add More Cartoons",
        description="Give the daytime lineup a few more animated picks.",
        icon="📺",
    ),
    ProgrammingSuggestion(
        title="Add Seasonal Event",
        description="Plan a holiday or seasonal takeover ahead of time.",
        icon="🎃",
    ),
    ProgrammingSuggestion(
        title="Create Programming Block",
        description="Group content into a new recurring block, like Nick at Nite.",
        icon="🧩",
    ),
]


def get_block(key):
    """Look up a default ProgrammingBlock by key. Returns None if unknown."""
    for block in DEFAULT_PROGRAMMING_BLOCKS:
        if block.key == key:
            return block
    return None

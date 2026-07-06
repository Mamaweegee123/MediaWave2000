"""Read-only data shapes for Channel Studio's programming UI.

These are plain dataclasses plus a small set of example presets — nothing
here reads or writes real schedule, library, or settings data, and nothing
here is wired into the scheduling engine.
"""

from dataclasses import dataclass


@dataclass
class ProgrammingSuggestion:
    """A friendly, one-click "quick action" idea shown to the user.

    Nothing about a suggestion is executable on its own — the UI layer
    decides what (if anything) happens when one is chosen.
    """

    title: str
    description: str


QUICK_ACTION_SUGGESTIONS = [
    ProgrammingSuggestion(title="Shuffle Tonight", description="Shuffle tonight's lineup."),
    ProgrammingSuggestion(title="Add Movie Night", description="Add a movie to tonight's lineup."),
    ProgrammingSuggestion(title="Start Night Block Earlier", description="Move late night up an hour."),
    ProgrammingSuggestion(title="Add More Cartoons", description="Add cartoons to the daytime lineup."),
    ProgrammingSuggestion(title="Add Seasonal Event", description="Plan a holiday takeover."),
]


# ── Draft Programming Block wizard option data ──────────────────────────
#
# Everything below is display data for the wizard's card-based steps.
# None of it is wired to real scheduling — see drafts.py for what a
# finished wizard run actually saves.


@dataclass
class BlockTypeOption:
    """Step 1 card: "What kind of block are you creating?" """

    key: str
    title: str
    description: str
    typical_airtime: str
    example_content: str


WIZARD_BLOCK_TYPES = [
    BlockTypeOption(
        key="morning_cartoons",
        title="Morning Cartoons",
        description="Cartoons to start the day.",
        typical_airtime="6:00 AM – 10:00 AM",
        example_content="Saturday Morning Toons",
    ),
    BlockTypeOption(
        key="after_school",
        title="After School",
        description="Afternoon cartoons and reruns.",
        typical_airtime="3:00 PM – 6:00 PM",
        example_content="After School Special",
    ),
    BlockTypeOption(
        key="movie_night",
        title="Movie Night",
        description="A featured movie, plus trailers.",
        typical_airtime="8:00 PM – 11:00 PM",
        example_content="Ghostbusters",
    ),
    BlockTypeOption(
        key="late_night",
        title="Late Night",
        description="Reruns and late-night programming.",
        typical_airtime="12:00 AM – 6:00 AM",
        example_content="Late Night Rerun",
    ),
    BlockTypeOption(
        key="halloween_event",
        title="Halloween Event",
        description="A Halloween programming takeover.",
        typical_airtime="All Day, October",
        example_content="Halloween Special",
    ),
    BlockTypeOption(
        key="christmas_specials",
        title="Christmas Specials",
        description="Holiday specials, back-to-back.",
        typical_airtime="All Day, December",
        example_content="Christmas Special",
    ),
    BlockTypeOption(
        key="variety",
        title="Variety",
        description="A mix of shows throughout the day.",
        typical_airtime="Varies",
        example_content="Variety Hour",
    ),
    BlockTypeOption(
        key="scratch",
        title="Start From Scratch",
        description="Build your own block.",
        typical_airtime="You decide",
        example_content="New Programming Block",
    ),
]


@dataclass
class TimePresetOption:
    """Step 2 card: "When does it come alive?" """

    key: str
    label: str
    description: str = ""


WIZARD_TIME_PRESETS = [
    TimePresetOption("every_day", "Every Day", "Airs every day."),
    TimePresetOption("weekdays", "Weekdays", "Monday through Friday."),
    TimePresetOption("weekends", "Weekends", "Saturday and Sunday."),
    TimePresetOption("friday_nights", "Friday Nights", "Friday nights only."),
    TimePresetOption("saturday_morning", "Saturday Morning", "Saturday mornings only."),
    TimePresetOption("october", "October", "A Halloween takeover."),
    TimePresetOption("december", "December", "A holiday takeover."),
    TimePresetOption("custom", "Custom", "Pick your own days and times."),
]


@dataclass
class PlaybackStyleOption:
    """Step 4 card: "How should it feel?" """

    key: str
    title: str
    description: str


WIZARD_PLAYBACK_STYLES = [
    PlaybackStyleOption("random", "Random", "Plays in random order."),
    PlaybackStyleOption("sequential", "Sequential", "Plays episodes in order."),
    PlaybackStyleOption("marathon", "Marathon", "Back-to-back episodes."),
    PlaybackStyleOption("comfort_tv", "Comfort TV", "Familiar favorites on repeat."),
    PlaybackStyleOption("movie_marathon", "Movie Marathon", "A run of features, back-to-back."),
    PlaybackStyleOption("background_tv", "Background TV", "Low-key programming for the background."),
]


def get_block_type(key):
    """Look up a wizard BlockTypeOption by key. Returns None if unknown."""
    for option in WIZARD_BLOCK_TYPES:
        if option.key == key:
            return option
    return None


def get_time_preset(key):
    """Look up a wizard TimePresetOption by key. Returns None if unknown."""
    for option in WIZARD_TIME_PRESETS:
        if option.key == key:
            return option
    return None


def get_playback_style(key):
    """Look up a wizard PlaybackStyleOption by key. Returns None if unknown."""
    for option in WIZARD_PLAYBACK_STYLES:
        if option.key == key:
            return option
    return None

"""Studio card taxonomy: intent-named constructors over the shared
StudioSection base (mediawave/studio/section.py).

Per the framework spec, these "may share a common base class if
appropriate... avoid creating separate implementations when composition is
sufficient" -- each of the five below is StudioSection with the accent/
collapsible/icon defaults that match its intent, not a new widget class. A
caller that needs StudioSection's fuller control (a custom footer, a real
collapsible=True section) can still build one directly instead of going
through one of these.
"""

from .section import StudioSection


def build_preview_card(title, content, subtitle=None, icon=None):
    """PreviewCard: a card whose content simulates a real result -- a TV
    preview, a logo preview, a weather forecast preview. No accent strip
    (the preview itself is the focal point, not a settings edge); not
    collapsible (a preview's whole point is staying visible).
    """
    return StudioSection(title, subtitle=subtitle, icon=icon, content=content, collapsible=False, accent=False)


def build_property_card(title, content, subtitle=None, icon=None):
    """PropertyCard: a card of editable settings -- commercial settings,
    playback settings, signal settings. Accented, matching the visual
    weight Channel Studio's existing settings cards already use; not
    collapsible (the nav rail, not a per-card toggle, owns visibility).
    """
    return StudioSection(title, subtitle=subtitle, icon=icon, content=content, collapsible=False, accent=True)


def build_action_card(title, content, subtitle=None, icon=None):
    """ActionCard: a card that launches another workspace -- "Edit Logo",
    "Open Schedule Editor", "Manage Artwork". Same accented treatment as
    PropertyCard (it's still "doing something"); not collapsible (an entry
    point doesn't hide itself).
    """
    return StudioSection(title, subtitle=subtitle, icon=icon, content=content, collapsible=False, accent=True)


def build_status_card(title, content, subtitle=None, icon=None):
    """StatusCard: a card that summarizes configuration -- "Commercials
    enabled.", "Sequential playback.", "4:3 logo." No accent strip (it's
    reporting, not inviting action); not collapsible.
    """
    return StudioSection(title, subtitle=subtitle, icon=icon, content=content, collapsible=False, accent=False)


def build_empty_state_card(title, content, subtitle=None, icon=None):
    """EmptyStateCard: guides the user when nothing exists yet -- "No logo
    yet. Click here to add one." No accent strip; not collapsible.
    """
    return StudioSection(title, subtitle=subtitle, icon=icon, content=content, collapsible=False, accent=False)

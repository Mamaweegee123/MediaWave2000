"""Centralized Studio typography constants.

Most Channel Studio text (page titles, section notes, field help) is
already driven by the app's global QSS object-name system ("dialogTitle",
"sectionNote", "sectionHeader", "fieldHelp") rather than a literal in this
codebase -- that system is out of scope for this phase (it's app-wide, not
Studio-specific, and touching it risks far more than Studio screens).

What's captured here is the one heading style StudioSection builds inline
rather than through that system -- naming it so future card types share the
same title treatment instead of re-picking a font size per screen.
"""

# StudioSection's own card title (see mediawave/studio/section.py's
# _TITLE_STYLE) -- a step down from the app's "dialogTitle" workspace-level
# heading, a step up from "sectionHeader"/"sectionNote" body text.
SECTION_TITLE_SIZE = 16
SECTION_TITLE_WEIGHT = 700

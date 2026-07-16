# MediaWave Studio Design System

This is the canonical reference for the shared Studio UI toolkit: the
reusable building blocks every MediaWave "Studio" tool (Channel Studio,
Logo Studio, and future tools — Schedule Editor, Artwork Manager, Metadata
Editor) is assembled from. The code lives in `mediawave/studio/`.

This document describes what exists today, not an aspiration. Every module
and function named below is real and importable.

## Philosophy

MediaWave is becoming a creative suite. Every Studio tool should feel like
another room inside the same building — same layout, navigation, cards,
buttons, spacing, previews, and action bars — without the user having to
learn a different interface each time.

Channel Studio and Logo Studio are the reference implementation. This
package didn't invent a new design language; it extracted the one that
already existed inside those two tools, verbatim, so a future tool can
reuse it without importing "channel_studio" by name.

## Design Principles

- **Beginner First** — advanced controls exist, but never as the first
  thing a user sees.
- **Preview Everything** — a Studio tool should show the user what a
  setting actually looks like whenever practical (see PreviewCard below).
- **Workspaces, not dialogs** — a Studio tool is a place you go to work
  (sidebar + persistent nav + one visible page), not a modal form you fill
  in and dismiss.
- **Progressive disclosure** — one page/card owns each concern; the same
  message or control doesn't appear in three places at once.
- **Context beats menus** — clicking the thing you want to edit (e.g. a
  channel's logo) is how you get to its editor, not a separate menu item.

## Workspace structure

`mediawave/studio/workspace.py`'s `build_workspace(content, action_bar,
sidebar=None)` assembles the standard Studio shell:

```
Sidebar (optional)  |  Content (one visible page)
--------------------------------------------------
             Persistent Action Bar
```

Zero outer margin/spacing — a caller's own dialog controls the real page
edges. `mediawave/channel_studio/channel_setup.py`'s `ChannelSetupDialog` is
the first real adopter: sidebar + `SinglePageStackedWidget` + action bar,
built exactly as before, just handed to `build_workspace` instead of being
laid out by hand.

## Action Bar

`mediawave/studio/action_bar.py`'s `build_action_bar(buttons)` builds the
persistent footer bar below the workspace. `buttons` is an ordered list
drawn from `"back"` / `"cancel"` / `"revert"` / `"save"` / `"apply"` —
different tools need different combinations (a Setup dialog might need only
Back; a future editable workspace might need Cancel/Revert/Save), but the
chrome — background, top border, margins — stays identical. `"back"`, when
present, is pinned to the far left with a stretch after it. `"save"` and
`"apply"` get the filled-blue "go do it" treatment
(`mediawave/studio/styles.py`'s `style_setup_button`); everything else is a
plain button. Returns `(bar_widget, buttons_by_key)` so a caller wires up
only the buttons it actually uses.

Today only `ChannelSetupDialog`'s footer (`["back"]`) uses it.
`logo_studio_dialog.py`'s bare "← Back to Channel Setup" button is left
as-is: it has no footer-bar chrome today (just a button in the dialog's own
margins), and forcing it into `build_action_bar` would visibly change it —
a candidate for a later pass, not this one.

## Sidebar

`mediawave/studio/sidebar.py`'s `StudioSidebar` is the branded left sidebar
— a star-painted dark gradient, a right-edge glow, a 1px border — hosting
whatever identity block and nav rail a caller builds. It knows nothing about
channels, logos, or pages.

`mediawave/studio/nav_rail.py`'s `StudioNavRail` is the vertical navigation
list that goes inside it: flat rows with a 3px left accent strip, a
background tint on the selected/hovered item, keyboard up/down navigation
between items. `items` is a plain list of `{"key", "icon", "title",
"description"}` dicts; `on_select(key)` fires identically for a real click
or a programmatic `select(key)` call (so a caller never needs two code
paths for "user picked a page" vs. "we picked one for them").

Future: badges and warning indicators on individual nav items are not yet
implemented — `StudioNavRail`'s per-item constructor is the place to add
them when a Studio tool needs one.

## Cards

`mediawave/studio/section.py`'s `StudioSection` is the shared base every
card type builds on: a header (icon + title + optional subtitle + optional
collapse toggle) and a body hosting one content widget, with an optional
colored accent strip on the left edge.

`mediawave/studio/cards.py` wraps `StudioSection` in five intent-named
constructors — thin wrappers, not separate widget classes, per the
"avoid separate implementations when composition is sufficient" rule:

| Constructor | Purpose | Accent | Example |
|---|---|---|---|
| `build_preview_card` | Display a simulated result | no | TV preview, logo preview, weather preview |
| `build_property_card` | Editable settings | yes | Commercial settings, playback settings, Logo Studio's controls |
| `build_action_card` | Launch another workspace | yes | Edit Logo, Open Schedule Editor |
| `build_status_card` | Summarize configuration | no | "Commercials enabled.", "4:3 logo." |
| `build_empty_state_card` | Guide the user when nothing exists yet | no | "No logo yet. Click here to add one." |

All five are `collapsible=False` — none of today's Studio pages use the
nav-rail-owns-visibility pattern with a per-card collapse arrow too (see
`StudioSection`'s own docstring for why that combination doesn't make
sense). A caller that genuinely needs a collapsible card still builds
`StudioSection` directly.

**Adopted today:** Logo Studio's controls panel (`setup_sections.py`'s
`build_logo_section`) uses `build_property_card`. **Not yet migrated:** the
rest of `setup_sections.py`'s ~15 existing cards (Overview's identity card,
the commercials/programming cards, `channel_studio_widgets.py`'s
`build_info_card`/`build_empty_state`/`build_schedule_timeline`) — per the
framework spec, this phase is infrastructure extraction, not a full
retrofit of every existing screen. They're real candidates for a future
pass, once a second Studio tool's needs clarify whether the current five
types are the right shape.

## Spacing

`mediawave/studio/spacing.py` centralizes the margin/spacing values Channel
Studio already used inline:

- `OUTER_MARGIN` — a workspace page's own outer margin (`(24, 20, 24, 20)`)
- `CARD_PADDING` — a card's inner content padding (`(20, 18, 20, 20)`)
- `SECTION_SPACING` — gap between a card's header and body (`10`)
- `CONTROL_SPACING` — gap between adjacent controls in a card body (`8`)
- `PREVIEW_SPACING` — gap between a preview surface and its controls
  (`12`) — not yet wired into an existing screen; the next Studio tool
  with a `build_preview_card` is the first real consumer.

## Typography

`mediawave/studio/typography.py` names the one heading style
`StudioSection` builds inline (`SECTION_TITLE_SIZE = 16`,
`SECTION_TITLE_WEIGHT = 700`). Most other Studio text — page titles,
section notes, field help — is driven by the app's global QSS object-name
system (`dialogTitle`, `sectionNote`, `sectionHeader`, `fieldHelp`), not a
literal in this package. That system is app-wide, not Studio-specific, and
out of scope for this phase; touching it would affect every dialog in the
app, not just Studio tools.

## Motion

`StudioSection`'s expand/collapse animation (`mediawave/studio/section.py`)
is the one Studio-owned motion today: a 200ms `InOutCubic` height tween,
deliberately height-only with no accompanying opacity fade (a
`QGraphicsOpacityEffect` nested inside the card's own drop shadow broke
child painting in testing — not worth the risk for a "nice to have" on top
of an animation that already reads as smooth).

Keep future Studio motion in this spirit: subtle, functional (communicating
a state change, not decoration), and skip anything that risks a similar
effect-compositing interaction without a clear payoff.

## Color tokens

`mediawave/theme_tokens.py` holds the `SW_*` `QColor` constants — the fixed
"deep space" palette used well beyond Studio tools: `channelsurfer2000.py`
builds its startup screen and roughly a dozen other app dialogs
(Advanced Configuration, Airing Rules, and more) from this same palette via
`build_themed_dialog_stylesheet()`/`build_startup_stylesheet()`. It
deliberately lives at the top level of `mediawave`, not under
`mediawave/studio/` — a Studio-specific package must never be a dependency
of unrelated core app code, so the general-purpose token module lives
outside Studio and Studio imports it, not the other way around.
`mediawave/studio/sidebar.py` is the one Studio consumer, reusing it for its
own star field rather than re-hardcoding the palette.

`mediawave/studio/styles.py` holds the Studio-specific style helpers built
on top of those tokens (`apply_card_shadow`, `style_setup_button`,
`style_remove_button`, `style_choice_button`, `style_nav_item`,
`style_slider`, `build_scroll_area`, `SinglePageStackedWidget`) — these
*are* Studio-owned, since nothing outside `channel_studio` currently uses
them. Channel-specific helpers (VHS/OSD font loading, the NOW/NEXT/LATER
schedule badge, the channel/companion confirm dialogs) stay in
`mediawave/channel_studio/studio_styles.py`, which re-exports the generic
ones so existing call sites in that package didn't need to change.

"""
End-to-end proof that ChannelSetupDialog's widget lifecycle doesn't leave
stale/overlapping widgets behind -- the bug this test guards against:
StudioSection.set_content() and ChannelIdentityApi.set_status_lines() both
swap out old content via QLayout.removeWidget()/takeAt(), which detaches a
widget from layout management WITHOUT hiding it, so it stayed a fully
visible, unmanaged sibling of the new content (at whatever geometry it last
had, or Qt's raw default size if it was swapped out before ever being laid
out) until its deferred deleteLater() actually ran. Combined with
ChannelSetupDialog previously calling _refresh_overview()/set_status_lines()
redundantly on its own initial page selection (before the dialog's first
paint), this produced two real, user-visible symptoms:
  1. The Overview page showed every identity field twice, overlapping.
  2. A stale, never-laid-out "Enabled"/"Disabled" status label ballooned to
     the dialog's default size and sat on top of the entire sidebar in
     z-order, silently swallowing every click in the window -- including
     clicks on the channel logo.

Unlike tools/test_channel_studio.py (deliberately "no QApplication needed"
-- pure functions and source inspection only), this file constructs a real
ChannelSetupDialog, so it needs an offscreen-capable Qt platform. Run from
the repo root:
  QT_QPA_PLATFORM=offscreen venv/bin/python3 tools/test_channel_setup_dialog_widgets.py
(the platform is also forced below so this is safe to run headless even
without the env var set explicitly).
"""
import os
import sys
from collections import Counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from PySide6.QtCore import QEventLoop, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

app = QApplication.instance() or QApplication(sys.argv)

from mediawave.channel_studio.channel_setup import ChannelSetupDialog
from mediawave.channel_studio.channel_setup_header import _LogoControl

PASS = []
FAIL = []


def check(name, expr, detail=""):
    if expr:
        PASS.append(name)
        print(f"  OK  {name}")
    else:
        FAIL.append(name)
        print(f"FAIL  {name}" + (f"  ({detail})" if detail else ""))


def section(title):
    print(f"\n--- {title} ---")


class _FakeStudioDialog:
    """A bare stand-in for the real AdvancedConfigDialog -- channel_actions.py's
    `_widget(dialog, attr_name)` helper falls back to None/defaults for any
    attribute this doesn't define, which is all ChannelSetupDialog needs to
    build a local-channel page successfully.
    """


def _pump():
    app.processEvents(QEventLoop.AllEvents)


def _build_dialog(drafts_path):
    channel_info = {"id": "local:movies", "name": "Movies", "default_number": 1, "root_path": "/tmp"}
    dlg = ChannelSetupDialog(
        channel_info, summary=None, schedule=None, parent=None,
        studio_dialog=_FakeStudioDialog(), drafts_path=drafts_path,
    )
    dlg.show()
    _pump()
    return dlg


def _visible_label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel) if lbl.text() and lbl.isVisible()]


section("ChannelSetupDialog: Overview shows each identity field exactly once, right after construction")

dlg = _build_dialog("/tmp/test_channel_setup_dialog_widgets_1.json")
overview_page = dlg._pages["Overview"]
counts = Counter(_visible_label_texts(overview_page))
# "📺"/"Overview" legitimately appear twice -- once as the page's own big
# heading (build_page_header), once as the StudioSection card's header --
# two distinct, intentional hierarchy levels (matches the requested target
# layout exactly: a page heading above one intentional content card).
# Every other field must appear exactly once.
unexpected_dupes = {text: n for text, n in counts.items() if n > 1 and text not in ("📺", "Overview")}
check(
    "no identity field (Channel name, Movies, Channel number, CH 001, Type, Source, ...) is visibly duplicated",
    not unexpected_dupes,
    unexpected_dupes,
)
check("the page heading and the card header are each still shown exactly once at their own two levels", counts.get("📺") == 2 and counts.get("Overview") == 2)

section("ChannelSetupDialog: repeated navigation never accumulates visible duplicates")

for _ in range(4):
    dlg._nav_rail.select("Programming")
    _pump()
    dlg._nav_rail.select("Commercials")
    _pump()
    dlg._nav_rail.select("Overview")
    _pump()

overview_page = dlg._pages["Overview"]
counts = Counter(_visible_label_texts(overview_page))
unexpected_dupes = {text: n for text, n in counts.items() if n > 1 and text not in ("📺", "Overview")}
check(
    "after repeatedly navigating away from and back to Overview, no identity field is visibly duplicated",
    not unexpected_dupes,
    unexpected_dupes,
)

section("ChannelSetupDialog: the sidebar's status line never leaves a stale full-size widget behind")

status_labels = [
    lbl for lbl in dlg.findChildren(QLabel)
    if lbl.text() in ("Enabled", "Disabled") and lbl.isVisible()
]
check("exactly one visible Enabled/Disabled status label exists after repeated navigation", len(status_labels) == 1, len(status_labels))

section("ChannelSetupDialog: the channel logo is still the widget that actually receives a click at its own position")

logo_control = dlg.findChildren(_LogoControl)[0]
hit = dlg.childAt(dlg.mapFromGlobal(logo_control.mapToGlobal(logo_control.rect().center())))
check(
    "the widget actually hit-tested at the logo's screen position is the logo control itself, "
    "not some unrelated widget (e.g. an orphaned status label ballooned to the dialog's full size)",
    hit is logo_control,
    type(hit).__name__ if hit is not None else None,
)

clicked = []
logo_control._on_activated = lambda: clicked.append(True)
QTest.mouseClick(logo_control, Qt.LeftButton, pos=logo_control.rect().center())
_pump()
check("clicking the logo control still invokes its activation callback", clicked == [True])

section("ChannelSetupDialog: main workspace pages are not collapsible (no toggle arrow, always open)")

for title, section_widget in dlg._sections.items():
    check(f"'{title}' section has no toggle button at all", section_widget._toggle_btn is None, title)
    check(f"'{title}' section reports itself as always expanded", section_widget.is_expanded is True, title)

print()
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)
print("All ChannelSetupDialog widget-lifecycle smoke tests passed.")

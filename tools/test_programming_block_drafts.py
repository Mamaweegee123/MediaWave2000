"""
Smoke tests for Channel Studio's isolated Draft Programming Block storage.
Run from the repo root:  venv/bin/python3 tools/test_programming_block_drafts.py
No GUI required — only drafts.py / programming_blocks.py are imported,
neither of which touches Qt. Uses a temp file so nothing in the repo or
a real user's data directory is touched.
"""
import os
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.channel_studio import drafts
from mediawave.channel_studio.programming_blocks import (
    get_block_type,
    get_playback_style,
    get_time_preset,
)

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


# ---------------------------------------------------------------------------
# missing file -> empty list, never raises
# ---------------------------------------------------------------------------
section("load_drafts: missing file")

tmp_dir = tempfile.mkdtemp(prefix="channel_studio_drafts_test_")
drafts_path = os.path.join(tmp_dir, "channel_studio_drafts.json")

loaded = drafts.load_drafts(drafts_path)
check("returns empty list for missing file", loaded == [])

# ---------------------------------------------------------------------------
# save / load round-trip
# ---------------------------------------------------------------------------
section("upsert_draft / load_drafts: round-trip")

draft = drafts.ProgrammingBlockDraft(
    key=drafts.new_draft_key(),
    title="Movie Night",
    block_type="movie_night",
    time_preset="friday_nights",
    time_preset_label="Friday Nights",
    media_selections=["Ghostbusters"],
    playback_style="movie_marathon",
    playback_style_label="Movie Marathon",
    created_at=1.0,
    updated_at=1.0,
)
drafts.upsert_draft(drafts_path, draft)
reloaded = drafts.load_drafts(drafts_path)
check("one draft saved", len(reloaded) == 1, len(reloaded))
check("title round-trips", reloaded[0].title == "Movie Night")
check("media_selections round-trips", reloaded[0].media_selections == ["Ghostbusters"])
check("file actually exists on disk", os.path.isfile(drafts_path))

# ---------------------------------------------------------------------------
# upsert replaces same key instead of duplicating
# ---------------------------------------------------------------------------
section("upsert_draft: replace by key")

updated = drafts.ProgrammingBlockDraft(
    key=draft.key,
    title="Movie Night (Updated)",
    block_type="movie_night",
    time_preset="friday_nights",
    time_preset_label="Friday Nights",
    media_selections=["Ghostbusters", "Ghostbusters II"],
    playback_style="movie_marathon",
    playback_style_label="Movie Marathon",
    created_at=1.0,
    updated_at=2.0,
)
drafts.upsert_draft(drafts_path, updated)
reloaded = drafts.load_drafts(drafts_path)
check("still one draft after update", len(reloaded) == 1, len(reloaded))
check("title updated in place", reloaded[0].title == "Movie Night (Updated)")

# ---------------------------------------------------------------------------
# a second, distinct draft is additive
# ---------------------------------------------------------------------------
section("upsert_draft: second draft is additive")

second = drafts.ProgrammingBlockDraft(key=drafts.new_draft_key(), title="Halloween Block")
drafts.upsert_draft(drafts_path, second)
reloaded = drafts.load_drafts(drafts_path)
check("two drafts saved", len(reloaded) == 2, len(reloaded))

# ---------------------------------------------------------------------------
# delete_draft
# ---------------------------------------------------------------------------
section("delete_draft")

drafts.delete_draft(drafts_path, draft.key)
reloaded = drafts.load_drafts(drafts_path)
check("one draft remains after delete", len(reloaded) == 1, len(reloaded))
check("remaining draft is the untouched one", reloaded[0].title == "Halloween Block")

# ---------------------------------------------------------------------------
# malformed file never raises
# ---------------------------------------------------------------------------
section("load_drafts: malformed file")

with open(drafts_path, "w", encoding="utf-8") as handle:
    handle.write("not valid json {{{")
check("malformed json returns empty list", drafts.load_drafts(drafts_path) == [])

with open(drafts_path, "w", encoding="utf-8") as handle:
    handle.write('{"not": "a list"}')
check("non-list json returns empty list", drafts.load_drafts(drafts_path) == [])

# ---------------------------------------------------------------------------
# wizard option lookups (programming_blocks.py)
# ---------------------------------------------------------------------------
section("wizard option lookups")

check("get_block_type finds movie_night", get_block_type("movie_night") is not None)
check("get_block_type returns None for unknown key", get_block_type("nope") is None)
check("get_time_preset finds friday_nights", get_time_preset("friday_nights") is not None)
check("get_playback_style finds marathon", get_playback_style("marathon") is not None)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
else:
    print("All smoke tests passed.")

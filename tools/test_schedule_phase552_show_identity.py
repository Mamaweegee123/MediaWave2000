"""
Phase 5.5.2 step 1 tests: the show identity registry foundation
(mediawave/show_identity.py) -- persistence and resolution only. Nothing
in this module is wired into the picker, Programming Blocks, Auto-Fill,
or scheduling yet, so these tests exercise it in isolation.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase552_show_identity.py
"""

import os
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

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


from mediawave.local_media import metadata_lookup_key, parse_local_media
from mediawave.show_identity import (
    _catalog_relative_folder_path,
    _matching_folder_rule,
    add_folder_show_rule,
    aliases_for_show_key,
    canonical_show_key,
    create_registry_record,
    empty_registry,
    load_show_identity_registry,
    merge_shows,
    mint_show_key,
    normalize_registry,
    rename_show,
    resolve_show_identity,
    save_show_identity_registry,
)


section("Empty registry")

empty = empty_registry()
check("empty_registry has version 1", empty["version"] == 1)
check("empty_registry has no shows", empty["shows"] == {})
check("empty_registry has no aliases", empty["raw_key_to_show_key"] == {})
check("empty_registry has no folder rules", empty["folder_rules"] == {})


section("load_show_identity_registry: missing/malformed files")

with tempfile.TemporaryDirectory() as tmp:
    missing_path = os.path.join(tmp, "does_not_exist.json")
    loaded = load_show_identity_registry(missing_path)
    check("missing file loads as empty registry", loaded == empty_registry())

    garbage_path = os.path.join(tmp, "garbage.json")
    with open(garbage_path, "w", encoding="utf-8") as handle:
        handle.write("{not valid json")
    loaded = load_show_identity_registry(garbage_path)
    check("malformed JSON loads as empty registry", loaded == empty_registry())

    wrong_shape_path = os.path.join(tmp, "wrong_shape.json")
    with open(wrong_shape_path, "w", encoding="utf-8") as handle:
        handle.write('{"version": 1, "shows": "not a dict", "raw_key_to_show_key": {}, "folder_rules": {}}')
    loaded = load_show_identity_registry(wrong_shape_path)
    check("wrong-shaped 'shows' loads as empty registry", loaded == empty_registry())

    future_version_path = os.path.join(tmp, "future.json")
    with open(future_version_path, "w", encoding="utf-8") as handle:
        handle.write('{"version": 999, "shows": {}, "raw_key_to_show_key": {}, "folder_rules": {}}')
    loaded = load_show_identity_registry(future_version_path)
    check("future version loads as empty registry", loaded == empty_registry())


section("normalize_registry: version and dropped/dangling entries")

normalized, ok = normalize_registry({"not": "a registry shape... actually it is a dict"})
check("dict missing required keys -> ok is False", ok is False)
check("dict missing required keys -> empty result", normalized == empty_registry())

normalized, ok = normalize_registry("not even a dict")
check("non-dict payload -> ok is False", ok is False)

raw = {
    "version": 1,
    "shows": {
        "show_good": {
            "display_name": "Moral Orel",
            "aliases": ["tv::2", "tv::3", "tv::2"],
            "folder_rules": [],
            "created_at": 100.0,
            "updated_at": 100.0,
        },
        "": {"display_name": "dropped, empty key"},
        "show_bad_entry": "not a dict",
    },
    "raw_key_to_show_key": {
        "tv::2": "show_good",
        "tv::3": "show_good",
        "tv::dangling": "show_never_existed",
    },
    "folder_rules": {
        "rule_good": {
            "show_key": "show_good",
            "root_relative_path": "TV/Moral Orel",
            "channel_id": "adult_swim",
            "created_at": 100.0,
        },
        "rule_dangling": {
            "show_key": "show_never_existed",
            "root_relative_path": "TV/Nothing",
        },
        "rule_no_path": {
            "show_key": "show_good",
            "root_relative_path": "",
        },
    },
}
normalized, ok = normalize_registry(raw)
check("mixed-validity payload normalizes with ok=True", ok is True)
check("valid show kept", "show_good" in normalized["shows"])
check("empty-key show dropped", "" not in normalized["shows"])
check("non-dict show entry dropped", "show_bad_entry" not in normalized["shows"])
check("aliases deduped", normalized["shows"]["show_good"]["aliases"] == ["tv::2", "tv::3"])
check("valid aliases kept", normalized["raw_key_to_show_key"] == {"tv::2": "show_good", "tv::3": "show_good"})
check("dangling alias dropped", "tv::dangling" not in normalized["raw_key_to_show_key"])
check("valid folder rule kept", "rule_good" in normalized["folder_rules"])
check("folder rule with dangling show_key dropped", "rule_dangling" not in normalized["folder_rules"])
check("folder rule with empty path dropped", "rule_no_path" not in normalized["folder_rules"])
check("reserved fields present on normalized show", set(["external_ids", "behavior", "correction_source"]) <= set(normalized["shows"]["show_good"].keys()))


section("mint_show_key")

key_a = mint_show_key()
key_b = mint_show_key()
check("mint_show_key produces a string", isinstance(key_a, str))
check("mint_show_key starts with show_", key_a.startswith("show_"))
check("mint_show_key is unique across calls", key_a != key_b)
check("mint_show_key never collides with tv:: namespace", not key_a.startswith("tv::"))
check("mint_show_key never collides with movie:: namespace", not key_a.startswith("movie::"))


section("create_registry_record")

record = create_registry_record("Moral Orel", aliases=["tv::2", "tv::3", "tv::2", ""], now=42.0)
check("display_name stored", record["display_name"] == "Moral Orel")
check("aliases deduped and blanks dropped", record["aliases"] == ["tv::2", "tv::3"])
check("created_at/updated_at set from now", record["created_at"] == 42.0 and record["updated_at"] == 42.0)
check("external_ids reserved and empty", record["external_ids"] == {})
check("behavior reserved and unset", record["behavior"] is None)
check("correction_source reserved and unset", record["correction_source"] is None)

record_defaults = create_registry_record("Some Show")
check("create_registry_record works with no aliases/now", record_defaults["aliases"] == [] and record_defaults["created_at"] == 0.0)


section("resolve_show_identity: untouched library is bit-for-bit identical to today")

sample_paths = [
    "/media/TV/Moral Orel/Season 1/Moral Orel - S01E01 - Numb.mp4",
    "/media/TV/The Office (US)/Season 2/The Office - 2x05 - Halloween.mkv",
    "/media/Movies/Some Movie (2010)/Some Movie (2010).mkv",
    "/media/TV/Superjail/Season 3/07 - The Time Machine.mp4",
]
registry = empty_registry()
for path in sample_paths:
    parsed = parse_local_media(path)
    resolved = resolve_show_identity(path, parsed, registry)
    expected_key = metadata_lookup_key(path, parsed)
    check(f"untouched show_key matches metadata_lookup_key for {os.path.basename(path)}", resolved["show_key"] == expected_key)
    check(f"raw_show_key matches metadata_lookup_key for {os.path.basename(path)}", resolved["raw_show_key"] == expected_key)
    check(f"display_name matches parsed show_name for {os.path.basename(path)}", resolved["display_name"] == parsed.get("show_name", ""))
    check(f"source is 'parsed' for {os.path.basename(path)}", resolved["source"] == "parsed")
    check(f"media_type matches parsed media_type for {os.path.basename(path)}", resolved["media_type"] == parsed.get("media_type"))


section("resolve_show_identity: canonical (aliased) lookup")

path = "/media/TV/Moral Orel/Season 1/Moral Orel - S01E01 - Numb.mp4"
parsed = parse_local_media(path)
raw_key = metadata_lookup_key(path, parsed)
canonical_key = mint_show_key()
registry_with_alias = {
    "version": 1,
    "shows": {
        canonical_key: create_registry_record("Moral Orel (Corrected)", aliases=[raw_key], now=1.0),
    },
    "raw_key_to_show_key": {raw_key: canonical_key},
    "folder_rules": {},
}
resolved = resolve_show_identity(path, parsed, registry_with_alias)
check("aliased show resolves to canonical show_key", resolved["show_key"] == canonical_key)
check("aliased show resolves to corrected display_name", resolved["display_name"] == "Moral Orel (Corrected)")
check("aliased show still reports its raw_show_key", resolved["raw_show_key"] == raw_key)
check("aliased show source is 'override'", resolved["source"] == "override")

# An alias table entry pointing at a show that no longer exists must not crash.
registry_dangling = {
    "version": 1,
    "shows": {},
    "raw_key_to_show_key": {raw_key: "show_missing"},
    "folder_rules": {},
}
resolved = resolve_show_identity(path, parsed, registry_dangling)
check("dangling alias falls back to provisional identity", resolved["show_key"] == raw_key)
check("dangling alias falls back to 'parsed' source", resolved["source"] == "parsed")


section("resolve_show_identity: folder-rule placeholder")

folder_path = "/media/TV/Moral Orel/Season 1/Moral Orel - S01E02 - Numb Pt2.mp4"
sibling_path = "/media/TV/Moral Orel Extras/Season 1/Extra - S01E01 - Bonus.mp4"
parsed_folder = parse_local_media(folder_path)
parsed_sibling = parse_local_media(sibling_path)
folder_show_key = mint_show_key()
registry_with_rule = {
    "version": 1,
    "shows": {
        folder_show_key: create_registry_record("Moral Orel", aliases=[], now=1.0),
    },
    "raw_key_to_show_key": {},
    "folder_rules": {
        "rule_1": {
            "show_key": folder_show_key,
            "root_relative_path": "TV/Moral Orel",
            "channel_id": "adult_swim",
            "created_at": 1.0,
        },
    },
}
resolved = resolve_show_identity(folder_path, parsed_folder, registry_with_rule)
check("folder rule resolves matching path to its show_key", resolved["show_key"] == folder_show_key)
check("folder rule resolves matching path source to 'override'", resolved["source"] == "override")

resolved_sibling = resolve_show_identity(sibling_path, parsed_sibling, registry_with_rule)
check("folder rule does not swallow a sibling folder sharing a name prefix", resolved_sibling["show_key"] != folder_show_key)
check("sibling folder falls back to 'parsed' source", resolved_sibling["source"] == "parsed")

registry_stale_rule = {
    "version": 1,
    "shows": {},
    "raw_key_to_show_key": {},
    "folder_rules": {},
}
# normalize_registry would have dropped this dangling rule already; confirm
# resolve_show_identity is also safe if handed one directly (defense in depth).
raw_registry_with_dangling_rule = dict(registry_stale_rule)
raw_registry_with_dangling_rule["folder_rules"] = {
    "rule_1": {"show_key": "show_missing", "root_relative_path": "TV/Moral Orel"},
}
resolved = resolve_show_identity(folder_path, parsed_folder, raw_registry_with_dangling_rule)
check("folder rule pointing at a missing show does not crash and falls back", resolved["show_key"] == metadata_lookup_key(folder_path, parsed_folder))


section("resolve_show_identity: display-name fallback")

parsed_no_name = dict(parsed)
parsed_no_name["show_name"] = ""
resolved = resolve_show_identity(path, parsed_no_name, empty_registry())
check("empty parsed show_name falls back to empty display_name, not a crash", resolved["display_name"] == "")

registry_blank_display = {
    "version": 1,
    "shows": {canonical_key: create_registry_record("", aliases=[raw_key], now=1.0)},
    "raw_key_to_show_key": {raw_key: canonical_key},
    "folder_rules": {},
}
resolved = resolve_show_identity(path, parsed, registry_blank_display)
check("blank registry display_name falls back to parsed show_name", resolved["display_name"] == parsed.get("show_name", ""))


section("no input mutation")

registry_copy_check = {
    "version": 1,
    "shows": {canonical_key: create_registry_record("Moral Orel (Corrected)", aliases=[raw_key], now=1.0)},
    "raw_key_to_show_key": {raw_key: canonical_key},
    "folder_rules": {},
}
import copy
before = copy.deepcopy(registry_copy_check)
resolve_show_identity(path, parsed, registry_copy_check)
check("resolve_show_identity does not mutate the registry", registry_copy_check == before)

parsed_before = dict(parsed)
resolve_show_identity(path, parsed, empty_registry())
check("resolve_show_identity does not mutate parsed_media", parsed == parsed_before)

data_for_normalize = copy.deepcopy(raw)
normalize_registry(data_for_normalize)
check("normalize_registry does not mutate its input", data_for_normalize == raw)


section("atomic save + round trip")

with tempfile.TemporaryDirectory() as tmp:
    registry_path = os.path.join(tmp, "schedule_show_identity.json")
    to_save = {
        "version": 1,
        "shows": {canonical_key: create_registry_record("Moral Orel (Corrected)", aliases=[raw_key], now=5.0)},
        "raw_key_to_show_key": {raw_key: canonical_key},
        "folder_rules": {},
    }
    ok, error = save_show_identity_registry(registry_path, to_save)
    check("save_show_identity_registry reports ok", ok is True, error)
    check("no leftover temp files after save", not any(name.startswith(".schedule_show_identity_") for name in os.listdir(tmp)))

    reloaded = load_show_identity_registry(registry_path)
    check("round-tripped registry matches what was saved", reloaded["shows"][canonical_key]["display_name"] == "Moral Orel (Corrected)")
    check("round-tripped alias table matches what was saved", reloaded["raw_key_to_show_key"] == {raw_key: canonical_key})

    # A structurally invalid payload must not clobber the existing file.
    ok, error = save_show_identity_registry(registry_path, {"version": 1, "shows": "nope", "raw_key_to_show_key": {}, "folder_rules": {}})
    check("save refuses an invalid payload", ok is False)
    check("save error message is non-empty", bool(error))
    still_there = load_show_identity_registry(registry_path)
    check("existing file is untouched after a refused save", still_there["shows"][canonical_key]["display_name"] == "Moral Orel (Corrected)")


section("rename_show (Phase 5.5.3): provisional show")

registry_provisional = empty_registry()
new_registry_1, canonical_1 = rename_show(registry_provisional, "tv::moral orel 1", "Moral Orel", now=10.0)
check("provisional rename mints a stable canonical show_<uuid> key", canonical_1.startswith("show_"))
check("original raw key becomes an alias", new_registry_1["shows"][canonical_1]["aliases"] == ["tv::moral orel 1"])
check("raw_key_to_show_key maps the original raw key to the new canonical key", new_registry_1["raw_key_to_show_key"]["tv::moral orel 1"] == canonical_1)
check("display_name is set to the corrected name", new_registry_1["shows"][canonical_1]["display_name"] == "Moral Orel")
check("correction_source is 'renamed' for a newly-minted record", new_registry_1["shows"][canonical_1]["correction_source"] == "renamed")
check("updated_at/created_at are set from the given now", new_registry_1["shows"][canonical_1]["created_at"] == 10.0 and new_registry_1["shows"][canonical_1]["updated_at"] == 10.0)
check("rename_show does not mutate the input registry", registry_provisional == empty_registry())


section("rename_show: second rename of the same show preserves the canonical key")

new_registry_2, canonical_2 = rename_show(new_registry_1, canonical_1, "Moral Orel (Redux)", now=20.0)
check("second rename (via the canonical key) preserves the same canonical key", canonical_2 == canonical_1)
check("second rename updates display_name only", new_registry_2["shows"][canonical_1]["display_name"] == "Moral Orel (Redux)")
check("aliases are preserved across the second rename", new_registry_2["shows"][canonical_1]["aliases"] == ["tv::moral orel 1"])
check("correction_source stays 'renamed' (unchanged, not re-derived)", new_registry_2["shows"][canonical_1]["correction_source"] == "renamed")
check("created_at is preserved (not reset) across the second rename", new_registry_2["shows"][canonical_1]["created_at"] == 10.0)
check("updated_at reflects the second rename's timestamp", new_registry_2["shows"][canonical_1]["updated_at"] == 20.0)

new_registry_3, canonical_3 = rename_show(new_registry_2, "tv::moral orel 1", "Moral Orel (Via Alias)", now=30.0)
check("renaming via the ORIGINAL raw alias (not the canonical key) also preserves the canonical key -- no duplicate record minted", canonical_3 == canonical_1)
check("only one show record exists in the registry after three renames of the same show", len(new_registry_3["shows"]) == 1)


section("rename_show: preserves unrelated reserved fields")

registry_with_extras = {
    "version": 1,
    "shows": {
        canonical_1: {
            "display_name": "Old Name",
            "aliases": ["tv::a", "tv::b"],
            "folder_rules": ["rule_1"],
            "external_ids": {"tmdb": 12345},
            "behavior": "some_future_behavior",
            "correction_source": "merged",
            "created_at": 1.0,
            "updated_at": 1.0,
        },
        "show_other": create_registry_record("Untouched Show", aliases=["tv::other"], now=1.0),
    },
    "raw_key_to_show_key": {"tv::a": canonical_1, "tv::b": canonical_1, "tv::other": "show_other"},
    "folder_rules": {
        "rule_1": {"show_key": canonical_1, "root_relative_path": "TV/Old Name", "channel_id": "ch1", "created_at": 1.0},
    },
}
new_registry_4, canonical_4 = rename_show(registry_with_extras, canonical_1, "New Name", now=5.0)
check("rename preserves the canonical key for an already-corrected show", canonical_4 == canonical_1)
check("aliases are preserved untouched", new_registry_4["shows"][canonical_1]["aliases"] == ["tv::a", "tv::b"])
check("folder_rules list on the show record is preserved", new_registry_4["shows"][canonical_1]["folder_rules"] == ["rule_1"])
check("the top-level folder_rules entry itself is preserved", new_registry_4["folder_rules"]["rule_1"]["root_relative_path"] == "TV/Old Name")
check("external_ids are preserved", new_registry_4["shows"][canonical_1]["external_ids"] == {"tmdb": 12345})
check("behavior is preserved", new_registry_4["shows"][canonical_1]["behavior"] == "some_future_behavior")
check(
    "correction_source is PRESERVED as 'merged', NOT overwritten to 'renamed' -- a merged show's provenance survives a later rename",
    new_registry_4["shows"][canonical_1]["correction_source"] == "merged",
)
check("an unrelated show record is completely untouched", new_registry_4["shows"]["show_other"] == registry_with_extras["shows"]["show_other"])
check("rename_show does not mutate the input registry (including its nested dicts)", registry_with_extras["shows"][canonical_1]["display_name"] == "Old Name")


section("rename_show: edge cases")

try:
    rename_show(empty_registry(), "tv::x", "   ", now=1.0)
    check("empty/whitespace-only name raises ValueError", False)
except ValueError:
    check("empty/whitespace-only name raises ValueError", True)

try:
    rename_show(empty_registry(), "tv::x", "", now=1.0)
    check("fully empty name raises ValueError", False)
except ValueError:
    check("fully empty name raises ValueError", True)

registry_dup_a = empty_registry()
reg_a, key_a = rename_show(registry_dup_a, "tv::showa", "Duplicate Name", now=1.0)
reg_b, key_b = rename_show(reg_a, "tv::showb", "Duplicate Name", now=2.0)
check("two separate canonical shows may legitimately share the exact same display name", key_a != key_b)
check("both shows keep their own distinct display_name record (both 'Duplicate Name', by design)", reg_b["shows"][key_a]["display_name"] == reg_b["shows"][key_b]["display_name"] == "Duplicate Name")

leading_trailing_result, _key = rename_show(empty_registry(), "tv::x", "   Moral Orel   ", now=1.0)
check("leading/trailing whitespace in the new name is trimmed", leading_trailing_result["shows"][_key]["display_name"] == "Moral Orel")

malformed_registry_for_rename = {"version": 1, "shows": "not a dict", "raw_key_to_show_key": {}, "folder_rules": {}}
malformed_result, malformed_key = rename_show(malformed_registry_for_rename, "tv::x", "Fresh Name", now=1.0)
check("a malformed input registry fails open (treated as empty) rather than crashing", malformed_key.startswith("show_") and malformed_result["shows"][malformed_key]["display_name"] == "Fresh Name")


section("merge_shows (Phase 5.5.4): two/three provisional shows")

reg_m1 = empty_registry()
new_reg_1, survivor_1, redirect_1, conflicts_1 = merge_shows(reg_m1, ["tv::2", "tv::3"], "Moral Orel", now=1.0)
check("merging two provisional shows mints one canonical key", survivor_1.startswith("show_"))
check("both raw inputs redirect to the survivor", redirect_1 == {"tv::2": survivor_1, "tv::3": survivor_1})
check("both raw keys become aliases of the survivor", sorted(new_reg_1["shows"][survivor_1]["aliases"]) == ["tv::2", "tv::3"])
check("display_name uses the explicit final name", new_reg_1["shows"][survivor_1]["display_name"] == "Moral Orel")
check("merge_shows does not mutate its input registry", reg_m1 == empty_registry())

new_reg_2, survivor_2, redirect_2, _conflicts_2 = merge_shows(empty_registry(), ["tv::2", "tv::3", "tv::moral orel 1"], "Moral Orel", now=1.0)
check("merging three provisional shows also mints one canonical key", survivor_2.startswith("show_"))
check("all three raw inputs redirect to the survivor", set(redirect_2.keys()) == {"tv::2", "tv::3", "tv::moral orel 1"} and set(redirect_2.values()) == {survivor_2})
check("all three raw keys become aliases", sorted(new_reg_2["shows"][survivor_2]["aliases"]) == ["tv::2", "tv::3", "tv::moral orel 1"])
check("correction_source is 'merged' for a newly-minted survivor", new_reg_2["shows"][survivor_2]["correction_source"] == "merged")


section("merge_shows: provisional into an existing canonical show")

reg_existing, existing_key = rename_show(empty_registry(), "tv::moral orel", "Moral Orel", now=1.0)
new_reg_3, survivor_3, redirect_3, _c3 = merge_shows(reg_existing, [existing_key, "tv::moral orel redux"], "Moral Orel", now=2.0)
check("merging a provisional show into an existing canonical show keeps the EXISTING canonical key (deterministic survivor rule)", survivor_3 == existing_key)
check("the provisional show's raw key becomes a new alias of the existing canonical show", "tv::moral orel redux" in new_reg_3["shows"][survivor_3]["aliases"])
check("the pre-existing alias is preserved", "tv::moral orel" in new_reg_3["shows"][survivor_3]["aliases"])
check("created_at is preserved from the original rename, not reset", new_reg_3["shows"][survivor_3]["created_at"] == 1.0)
check("updated_at advances to the merge time", new_reg_3["shows"][survivor_3]["updated_at"] == 2.0)


section("merge_shows: two existing canonical shows -- absorbed key redirect compatibility")

reg_a, key_a = rename_show(empty_registry(), "tv::2", "Show A", now=1.0)
reg_ab, key_b = rename_show(reg_a, "tv::3", "Show B", now=2.0)
new_reg_4, survivor_4, redirect_4, _c4 = merge_shows(reg_ab, [key_a, key_b], "Combined Show", now=3.0)
check("deterministic survivor: the FIRST-SELECTED existing canonical record wins", survivor_4 == key_a)
check("the absorbed canonical key's own record is removed from 'shows'", key_b not in new_reg_4["shows"])
check("only one show record remains after merging two existing canonical shows", len(new_reg_4["shows"]) == 1)
check("the absorbed canonical key still resolves through the redirect (canonical_show_key)", canonical_show_key(key_b, new_reg_4) == survivor_4)
check("the absorbed canonical key is listed among the survivor's aliases (cursor alias-search compatibility)", key_b in aliases_for_show_key(survivor_4, new_reg_4))
check("the absorbed show's own raw alias (tv::3) also now redirects to the survivor", canonical_show_key("tv::3", new_reg_4) == survivor_4)
check("the survivor's own original raw alias (tv::2) still resolves", canonical_show_key("tv::2", new_reg_4) == survivor_4)
check("redirect_map reports the absorbed canonical key -> survivor", redirect_4[key_b] == survivor_4)
check("display_name uses the explicit final name, not either original name", new_reg_4["shows"][survivor_4]["display_name"] == "Combined Show")


section("merge_shows: folder_rules, external_ids, and behavior conflicts")

reg_extras = {
    "version": 1,
    "shows": {
        "show_x": {
            "display_name": "Show X",
            "aliases": ["tv::x"],
            "folder_rules": ["rule_x"],
            "external_ids": {"tmdb": 111},
            "behavior": "behavior_x",
            "correction_source": None,
            "created_at": 1.0,
            "updated_at": 1.0,
        },
        "show_y": {
            "display_name": "Show Y",
            "aliases": ["tv::y"],
            "folder_rules": ["rule_y"],
            "external_ids": {"tmdb": 222, "tvmaze": 999},
            "behavior": "behavior_y",
            "correction_source": None,
            "created_at": 2.0,
            "updated_at": 2.0,
        },
    },
    "raw_key_to_show_key": {"tv::x": "show_x", "tv::y": "show_y"},
    "folder_rules": {
        "rule_x": {"show_key": "show_x", "root_relative_path": "TV/Show X", "channel_id": "ch1", "created_at": 1.0},
        "rule_y": {"show_key": "show_y", "root_relative_path": "TV/Show Y", "channel_id": "ch1", "created_at": 2.0},
    },
}
new_reg_5, survivor_5, redirect_5, conflicts_5 = merge_shows(reg_extras, ["show_x", "show_y"], "Show XY", now=5.0)
check("survivor is the first-selected existing record (show_x)", survivor_5 == "show_x")
check("folder_rules ids are unioned onto the survivor's own record", sorted(new_reg_5["shows"][survivor_5]["folder_rules"]) == ["rule_x", "rule_y"])
check("the absorbed show's folder rule is repointed to the survivor at the top level", new_reg_5["folder_rules"]["rule_y"]["show_key"] == survivor_5)
check("the survivor's own folder rule is untouched", new_reg_5["folder_rules"]["rule_x"]["show_key"] == survivor_5)
check("non-conflicting external_ids are preserved (tvmaze only existed on the absorbed show)", new_reg_5["shows"][survivor_5]["external_ids"].get("tvmaze") == 999)
check("conflicting external_ids: the SURVIVOR's value wins, not silently overwritten", new_reg_5["shows"][survivor_5]["external_ids"].get("tmdb") == 111)
check("the discarded external_id conflict is reported, not silently dropped", any(c["provider"] == "tmdb" and c["discarded"] == 222 for c in conflicts_5["external_ids"]))
check("conflicting behavior: the SURVIVOR's value wins", new_reg_5["shows"][survivor_5]["behavior"] == "behavior_x")
check("the discarded behavior conflict is reported", "behavior_y" in conflicts_5["behavior"])


section("merge_shows: correction_source rule")

reg_renamed_survivor, renamed_key = rename_show(empty_registry(), "tv::x", "X", now=1.0)
new_reg_6, survivor_6, _r6, _c6 = merge_shows(reg_renamed_survivor, [renamed_key, "tv::provisional"], "X Combined", now=2.0)
check("a survivor with an existing meaningful correction_source ('renamed') keeps it -- not overwritten to 'merged'", new_reg_6["shows"][survivor_6]["correction_source"] == "renamed")

reg_no_source = {
    "version": 1,
    "shows": {"show_z": {"display_name": "Z", "aliases": ["tv::z"], "folder_rules": [], "external_ids": {}, "behavior": None, "correction_source": None, "created_at": 1.0, "updated_at": 1.0}},
    "raw_key_to_show_key": {"tv::z": "show_z"},
    "folder_rules": {},
}
new_reg_7, survivor_7, _r7, _c7 = merge_shows(reg_no_source, ["show_z", "tv::other"], "Z Combined", now=2.0)
check("a survivor with NO existing correction_source becomes 'merged'", new_reg_7["shows"][survivor_7]["correction_source"] == "merged")


section("merge_shows: unrelated registry records untouched")

reg_unrelated = {
    "version": 1,
    "shows": {
        "show_p": create_registry_record("P", aliases=["tv::p"], now=1.0),
        "show_q": create_registry_record("Q", aliases=["tv::q"], now=1.0),
        "show_untouched": create_registry_record("Untouched", aliases=["tv::untouched"], now=1.0),
    },
    "raw_key_to_show_key": {"tv::p": "show_p", "tv::q": "show_q", "tv::untouched": "show_untouched"},
    "folder_rules": {},
}
new_reg_8, _s8, _r8, _c8 = merge_shows(reg_unrelated, ["show_p", "show_q"], "PQ", now=5.0)
check("an unrelated show record is completely untouched by the merge", new_reg_8["shows"]["show_untouched"] == reg_unrelated["shows"]["show_untouched"])
check("the unrelated show's alias mapping is untouched", new_reg_8["raw_key_to_show_key"]["tv::untouched"] == "show_untouched")


section("merge_shows: edge cases")

try:
    merge_shows(empty_registry(), ["tv::only-one"], "Solo")
    check("a single show_key raises ValueError (nothing to merge)", False)
except ValueError:
    check("a single show_key raises ValueError (nothing to merge)", True)

try:
    merge_shows(empty_registry(), [], "Nothing")
    check("an empty show_keys list raises ValueError", False)
except ValueError:
    check("an empty show_keys list raises ValueError", True)

try:
    merge_shows(empty_registry(), ["tv::a", "tv::a"], "Same Twice")
    check("the same key repeated (resolves to one distinct identity) raises ValueError", False)
except ValueError:
    check("the same key repeated (resolves to one distinct identity) raises ValueError", True)

try:
    merge_shows(empty_registry(), ["tv::a", "tv::b"], "   ")
    check("a whitespace-only explicit display_name raises ValueError", False)
except ValueError:
    check("a whitespace-only explicit display_name raises ValueError", True)

new_reg_9, survivor_9, _r9, _c9 = merge_shows(empty_registry(), ["tv::a", "tv::b"], now=1.0)
check("omitting display_name entirely falls back to a sane default (first alias), not a crash", new_reg_9["shows"][survivor_9]["display_name"] == "tv::a")

before_reg = copy.deepcopy(reg_unrelated)
merge_shows(reg_unrelated, ["show_p", "show_q"], "PQ Again", now=9.0)
check("merge_shows never mutates the input registry (including nested dicts)", reg_unrelated == before_reg)


section("_catalog_relative_folder_path (Phase 5.5.5): path normalization")

check("relative POSIX path creation", _catalog_relative_folder_path("/Media/TV", "/Media/TV/Bob Ross") == "Bob Ross")
check("nested subfolder relative path", _catalog_relative_folder_path("/Media/TV", "/Media/TV/Bob Ross/Season 1") == "Bob Ross/Season 1")
check("Windows separator normalization (root)", _catalog_relative_folder_path("C:\\Media\\TV", "C:\\Media\\TV\\Bob Ross") == "Bob Ross")
check("Windows separator normalization (mixed)", _catalog_relative_folder_path("C:/Media/TV", "C:\\Media\\TV\\Bob Ross") == "Bob Ross")
check("NAS/external mount independence: only the relative layout matters, not the absolute root", _catalog_relative_folder_path("/Volumes/NAS2/TV", "/Volumes/NAS2/TV/Bob Ross") == _catalog_relative_folder_path("/mnt/external/TV", "/mnt/external/TV/Bob Ross"))
check("folder equal to catalog_root has no relative subfolder to name -- returns None", _catalog_relative_folder_path("/Media/TV", "/Media/TV") is None)
check("folder outside catalog_root returns None", _catalog_relative_folder_path("/Media/TV", "/Media/Movies/Bob Ross") is None)
check("empty catalog_root returns None", _catalog_relative_folder_path("", "/Media/TV/Bob Ross") is None)
check("empty folder_path returns None", _catalog_relative_folder_path("/Media/TV", "") is None)
check("trailing slashes are tolerated", _catalog_relative_folder_path("/Media/TV/", "/Media/TV/Bob Ross/") == "Bob Ross")


section("_matching_folder_rule (Phase 5.5.5): segment-aware matching + channel scoping")

folder_rules = {
    "rule_bob_ross": {"show_key": "show_bobross", "root_relative_path": "TV/Bob Ross", "channel_id": "ch1", "created_at": 1.0},
    "rule_bob_ross_season": {"show_key": "show_bobross_season_specific", "root_relative_path": "TV/Bob Ross/Season 1", "channel_id": "ch1", "created_at": 2.0},
}
check("path-segment-aware matching finds the rule", _matching_folder_rule("/Media/TV/Bob Ross/Mountain.mp4", folder_rules) is not None)
check("sibling prefix false positive prevented -- 'Bob Ross' does not match 'Bob Ross Weekly'", _matching_folder_rule("/Media/TV/Bob Ross Weekly/Clip.mp4", folder_rules) is None)
check("nested season folder still matches its parent rule (no season-specific rule present)", _matching_folder_rule("/Media/TV/Bob Ross/Season 2/Clip.mp4", folder_rules)["show_key"] == "show_bobross")
check("longest matching rule wins when rules overlap", _matching_folder_rule("/Media/TV/Bob Ross/Season 1/Clip.mp4", folder_rules)["show_key"] == "show_bobross_season_specific")
check("channel scoping: a rule for ch1 does not match the same relative path under ch2", _matching_folder_rule("/Media2/TV/Bob Ross/Mountain.mp4", folder_rules, channel_id="ch2") is None)
check("channel scoping: the SAME rule matches when the channel_id agrees", _matching_folder_rule("/Media/TV/Bob Ross/Mountain.mp4", folder_rules, channel_id="ch1") is not None)
check("channel scoping is skipped (permissive) when the caller passes no channel_id at all", _matching_folder_rule("/Media/TV/Bob Ross/Mountain.mp4", folder_rules) is not None)


section("resolve_show_identity (Phase 5.5.5): folder-rule matches promote media_type to 'tv'")

folder_show_key = mint_show_key()
registry_folder_promote = {
    "version": 1,
    "shows": {folder_show_key: create_registry_record("Bob Ross", now=1.0)},
    "raw_key_to_show_key": {},
    "folder_rules": {
        "rule_1": {"show_key": folder_show_key, "root_relative_path": "TV/Bob Ross", "channel_id": "ch1", "created_at": 1.0},
    },
}
movie_shaped_parse = {"media_type": "movie", "show_name": "Mountain Painting", "timeline_title": "Mountain Painting"}
resolved_promoted = resolve_show_identity("/Media/TV/Bob Ross/Mountain Painting.mp4", movie_shaped_parse, registry_folder_promote, channel_id="ch1")
check("a folder-rule match reports media_type='tv' even though the raw parse guessed 'movie'", resolved_promoted["media_type"] == "tv")
check("the folder-rule match still resolves the correct canonical show_key", resolved_promoted["show_key"] == folder_show_key)
check("the folder-rule match still resolves the corrected display_name", resolved_promoted["display_name"] == "Bob Ross")

resolved_wrong_channel = resolve_show_identity("/Media2/TV/Bob Ross/Mountain Painting.mp4", movie_shaped_parse, registry_folder_promote, channel_id="ch2")
check("a folder rule scoped to ch1 does not leak into ch2 -- media_type stays whatever the raw parse said", resolved_wrong_channel["media_type"] == "movie")
check("an unmatched-channel file falls back to provisional (parsed) identity", resolved_wrong_channel["source"] == "parsed")

resolved_alias_only = resolve_show_identity("/Media/Somewhere/Show.mp4", {"media_type": "movie"}, {
    "version": 1,
    "shows": {folder_show_key: create_registry_record("Renamed Movie", now=1.0)},
    "raw_key_to_show_key": {"movie::somehash": folder_show_key},
    "folder_rules": {},
})
check("an ALIAS match (not a folder rule) never changes media_type -- only folder rules are TV-only by design", resolved_alias_only["media_type"] == "movie" or resolved_alias_only["source"] != "override")


section("add_folder_show_rule (Phase 5.5.5): provisional folder -> new canonical show")

reg_folder_1 = empty_registry()
new_reg_f1, canonical_f1, rule_id_f1, redirect_f1 = add_folder_show_rule(
    reg_folder_1,
    channel_id="ch1",
    catalog_root="/Media/TV",
    folder_path="/Media/TV/Bob Ross",
    display_name="Bob Ross",
    provisional_raw_keys=["movie::hash1", "movie::hash2"],
    now=1.0,
)
check("a provisional folder creates one new canonical show", canonical_f1.startswith("show_"))
check("the folder rule is created with the catalog-relative path", new_reg_f1["folder_rules"][rule_id_f1]["root_relative_path"] == "Bob Ross")
check("the folder rule is scoped to the given channel", new_reg_f1["folder_rules"][rule_id_f1]["channel_id"] == "ch1")
check("the folder rule points at the new canonical show", new_reg_f1["folder_rules"][rule_id_f1]["show_key"] == canonical_f1)
check("correction_source is 'folder_rule' for a newly-minted show", new_reg_f1["shows"][canonical_f1]["correction_source"] == "folder_rule")
check("provisional raw keys become aliases of the new show", sorted(new_reg_f1["shows"][canonical_f1]["aliases"]) == ["movie::hash1", "movie::hash2"])
check("provisional raw keys resolve through the alias table", new_reg_f1["raw_key_to_show_key"]["movie::hash1"] == canonical_f1)
check("redirect_map reports each provisional key -> the new canonical show", redirect_f1 == {"movie::hash1": canonical_f1, "movie::hash2": canonical_f1})
check("the show's own folder_rules list records the new rule id", new_reg_f1["shows"][canonical_f1]["folder_rules"] == [rule_id_f1])
check("add_folder_show_rule does not mutate the input registry", reg_folder_1 == empty_registry())


section("add_folder_show_rule: attaching to an existing unambiguous canonical show")

reg_existing_show, existing_key = rename_show(empty_registry(), "movie::preexisting", "Bob Ross (Renamed)", now=1.0)
new_reg_f2, canonical_f2, rule_id_f2, redirect_f2 = add_folder_show_rule(
    reg_existing_show,
    channel_id="ch1",
    catalog_root="/Media/TV",
    folder_path="/Media/TV/Bob Ross",
    display_name="Bob Ross",
    target_show_key=existing_key,
    provisional_raw_keys=["movie::extra"],
    now=2.0,
)
check("attaching to an existing show preserves its canonical key", canonical_f2 == existing_key)
check("the pre-existing alias is preserved", "movie::preexisting" in new_reg_f2["shows"][canonical_f2]["aliases"])
check("the new provisional key also becomes an alias", "movie::extra" in new_reg_f2["shows"][canonical_f2]["aliases"])
check("the display_name is updated to the dialog's chosen name", new_reg_f2["shows"][canonical_f2]["display_name"] == "Bob Ross")
check("correction_source is PRESERVED as 'renamed', not overwritten to 'folder_rule'", new_reg_f2["shows"][canonical_f2]["correction_source"] == "renamed")
check("created_at is preserved from the original rename", new_reg_f2["shows"][canonical_f2]["created_at"] == 1.0)


section("add_folder_show_rule: unrelated registry records untouched, edge cases")

reg_unrelated_folder = {
    "version": 1,
    "shows": {"show_other": create_registry_record("Other Show", aliases=["tv::other"], now=1.0)},
    "raw_key_to_show_key": {"tv::other": "show_other"},
    "folder_rules": {},
}
new_reg_f3, _c3, _r3, _rd3 = add_folder_show_rule(
    reg_unrelated_folder, channel_id="ch1", catalog_root="/Media/TV", folder_path="/Media/TV/New Show", display_name="New Show", now=1.0
)
check("an unrelated show record is completely untouched", new_reg_f3["shows"]["show_other"] == reg_unrelated_folder["shows"]["show_other"])

try:
    add_folder_show_rule(empty_registry(), channel_id="ch1", catalog_root="/Media/TV", folder_path="/Media/TV", display_name="Root Itself", now=1.0)
    check("a folder equal to catalog_root is rejected safely", False)
except ValueError:
    check("a folder equal to catalog_root is rejected safely", True)

try:
    add_folder_show_rule(empty_registry(), channel_id="ch1", catalog_root="/Media/TV", folder_path="/Media/Movies/X", display_name="X", now=1.0)
    check("a folder outside catalog_root is rejected safely", False)
except ValueError:
    check("a folder outside catalog_root is rejected safely", True)

try:
    add_folder_show_rule(empty_registry(), channel_id="ch1", catalog_root="/Media/TV", folder_path="/Media/TV/X", display_name="   ", now=1.0)
    check("an empty display_name is rejected safely", False)
except ValueError:
    check("an empty display_name is rejected safely", True)

reg_with_rule, canonical_dup, rule_id_dup, _rd = add_folder_show_rule(
    empty_registry(), channel_id="ch1", catalog_root="/Media/TV", folder_path="/Media/TV/Bob Ross", display_name="Bob Ross", now=1.0
)
try:
    add_folder_show_rule(reg_with_rule, channel_id="ch1", catalog_root="/Media/TV", folder_path="/Media/TV/Bob Ross", display_name="Bob Ross Again", now=2.0)
    check("an overlapping rule for the exact same (channel, folder) is rejected safely", False)
except ValueError:
    check("an overlapping rule for the exact same (channel, folder) is rejected safely", True)

# A different channel is allowed to declare a rule at the same relative path.
reg_diff_channel, canonical_diff, _rid, _rd2 = add_folder_show_rule(
    reg_with_rule, channel_id="ch2", catalog_root="/Media/TV", folder_path="/Media/TV/Bob Ross", display_name="Bob Ross (Channel 2)", now=3.0
)
check("a DIFFERENT channel may declare its own rule at the same relative path", canonical_diff != canonical_dup)

before_reg_folder = copy.deepcopy(reg_with_rule)
add_folder_show_rule(reg_with_rule, channel_id="ch3", catalog_root="/Media/TV", folder_path="/Media/TV/Another Show", display_name="Another Show", now=4.0)
check("add_folder_show_rule never mutates the input registry (including nested dicts)", reg_with_rule == before_reg_folder)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

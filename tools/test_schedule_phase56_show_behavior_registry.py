"""
Phase 5.6 registry tests: persistent per-show Episode Behavior
(set_show_behavior / show_behavior_for) in mediawave.show_identity.

Run from the repo root:
  venv/bin/python3 tools/test_schedule_phase56_show_behavior_registry.py
"""

import copy
import os
import sys

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


from mediawave.show_identity import (
    empty_registry,
    create_registry_record,
    mint_show_key,
    set_show_behavior,
    show_behavior_for,
    rename_show,
    merge_shows,
    add_folder_show_rule,
)

RAW_KEY = "tv::moral orel"

section("Provisional show promotes to canonical on first behavior set")
reg = empty_registry()
new_reg, canonical_key = set_show_behavior(reg, RAW_KEY, "sequential", display_name="Moral Orel")
check("canonical key minted", canonical_key.startswith("show_"))
check("provisional not left as its own record", RAW_KEY not in new_reg["shows"])
record = new_reg["shows"][canonical_key]
check("behavior stored", record["behavior"] == "sequential")
check("raw key preserved as alias", RAW_KEY in record["aliases"])
check("display_name seeded", record["display_name"] == "Moral Orel")
check("raw_key_to_show_key redirect added", new_reg["raw_key_to_show_key"].get(RAW_KEY) == canonical_key)
check("original registry not mutated", reg == empty_registry())

section("Sequential behavior stored on already-canonical show")
base_reg = empty_registry()
base_reg["shows"]["show_abc"] = create_registry_record("Bob Ross", aliases=["tv::bob ross"])
base_reg["raw_key_to_show_key"]["tv::bob ross"] = "show_abc"
new_reg2, key2 = set_show_behavior(base_reg, "show_abc", "sequential")
check("canonical key unchanged", key2 == "show_abc")
check("behavior sequential", new_reg2["shows"]["show_abc"]["behavior"] == "sequential")
check("display_name preserved", new_reg2["shows"]["show_abc"]["display_name"] == "Bob Ross")

section("Random behavior stored")
new_reg3, key3 = set_show_behavior(base_reg, "show_abc", "random")
check("behavior random", new_reg3["shows"]["show_abc"]["behavior"] == "random")

section("Channel-default clears explicit behavior cleanly")
reg_with_behavior = new_reg3
new_reg4, key4 = set_show_behavior(reg_with_behavior, "show_abc", None)
check("behavior cleared to None", new_reg4["shows"]["show_abc"]["behavior"] is None)
check("show_behavior_for reports channel default", show_behavior_for("show_abc", new_reg4) is None)

section("Canonical key preserved across repeated behavior changes")
r = empty_registry()
r, k1 = set_show_behavior(r, "tv::superjail", "random", display_name="Superjail")
r, k2 = set_show_behavior(r, k1, "sequential")
r, k3 = set_show_behavior(r, "tv::superjail", None)
check("key stable across changes", k1 == k2 == k3)
check("raw alias still resolves after clearing", show_behavior_for("tv::superjail", r) is None)

section("Invalid behavior rejected")
threw = False
try:
    set_show_behavior(empty_registry(), "tv::x", "shuffled")
except ValueError:
    threw = True
check("ValueError for invalid behavior string", threw)

threw2 = False
try:
    set_show_behavior(empty_registry(), "", "random")
except ValueError:
    threw2 = True
check("ValueError for empty show_key", threw2)

section("Aliases preserved")
reg5 = empty_registry()
reg5["shows"]["show_x"] = create_registry_record("Show X", aliases=["tv::a", "tv::b"])
reg5["raw_key_to_show_key"]["tv::a"] = "show_x"
reg5["raw_key_to_show_key"]["tv::b"] = "show_x"
new_reg5, _ = set_show_behavior(reg5, "show_x", "sequential")
check("aliases untouched", new_reg5["shows"]["show_x"]["aliases"] == ["tv::a", "tv::b"])

section("Folder rules preserved")
reg6 = empty_registry()
reg6["shows"]["show_y"] = create_registry_record("Show Y", aliases=["tv::y"], folder_rule_ids=["rule_1"])
reg6["folder_rules"]["rule_1"] = {"show_key": "show_y", "root_relative_path": "Show Y", "channel_id": "", "created_at": 0.0}
new_reg6, _ = set_show_behavior(reg6, "show_y", "random")
check("folder_rules list preserved", new_reg6["shows"]["show_y"]["folder_rules"] == ["rule_1"])
check("folder rule entry preserved", "rule_1" in new_reg6["folder_rules"])

section("External IDs preserved")
reg7 = empty_registry()
rec7 = create_registry_record("Show Z", aliases=["tv::z"])
rec7["external_ids"] = {"tvdb": "12345"}
reg7["shows"]["show_z"] = rec7
new_reg7, _ = set_show_behavior(reg7, "show_z", "sequential")
check("external_ids preserved", new_reg7["shows"]["show_z"]["external_ids"] == {"tvdb": "12345"})

section("correction_source preserved")
reg8 = empty_registry()
rec8 = create_registry_record("Show Q", aliases=["tv::q"])
rec8["correction_source"] = "merged"
reg8["shows"]["show_q"] = rec8
new_reg8, _ = set_show_behavior(reg8, "show_q", "random")
check("correction_source untouched", new_reg8["shows"]["show_q"]["correction_source"] == "merged")

section("Display name preserved unless missing provisional record needs one")
reg9 = empty_registry()
rec9 = create_registry_record("Existing Name", aliases=["tv::n"])
reg9["shows"]["show_n"] = rec9
new_reg9, _ = set_show_behavior(reg9, "show_n", "sequential", display_name="Ignored New Name")
check("display_name not overwritten for existing record", new_reg9["shows"]["show_n"]["display_name"] == "Existing Name")

section("No input mutation (deep check)")
reg10 = empty_registry()
reg10["shows"]["show_m"] = create_registry_record("M", aliases=["tv::m"])
snapshot = copy.deepcopy(reg10)
set_show_behavior(reg10, "show_m", "random")
check("input registry identical after call", reg10 == snapshot)

section("show_behavior_for resolves raw aliases")
reg11 = empty_registry()
reg11["shows"]["show_p"] = create_registry_record("P", aliases=["tv::p"])
reg11["shows"]["show_p"]["behavior"] = "sequential"
reg11["raw_key_to_show_key"]["tv::p"] = "show_p"
check("resolves via raw alias", show_behavior_for("tv::p", reg11) == "sequential")
check("resolves via canonical key directly", show_behavior_for("show_p", reg11) == "sequential")

section("Absorbed canonical redirects resolve behavior")
reg12 = empty_registry()
reg12, ka = set_show_behavior(reg12, "tv::show-a", "sequential", display_name="Show A")
reg12, kb = set_show_behavior(reg12, "tv::show-b", "random", display_name="Show B")
merged_reg, survivor, redirect_map, conflicts = merge_shows(reg12, [ka, kb], display_name="Merged Show")
check("survivor is one of the originals", survivor in (ka, kb))
absorbed_key = kb if survivor == ka else ka
check("absorbed key redirects to survivor's behavior", show_behavior_for(absorbed_key, merged_reg) == show_behavior_for(survivor, merged_reg))

section("Malformed registry returns channel-default safely")
check("None registry", show_behavior_for("show_x", None) is None)
check("non-dict registry", show_behavior_for("show_x", "not a dict") is None)
check("empty show_key", show_behavior_for("", empty_registry()) is None)
check("unknown show_key", show_behavior_for("show_does_not_exist", empty_registry()) is None)
malformed = {"shows": "not a dict"}
check("malformed shows container", show_behavior_for("show_x", malformed) is None)
dangling = {"shows": {}, "raw_key_to_show_key": {"tv::dangling": "show_ghost"}}
check("dangling alias with no record", show_behavior_for("tv::dangling", dangling) is None)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)

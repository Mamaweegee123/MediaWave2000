"""
Smoke tests for the Phase 1 Airing Rules data model.
Run from the repo root:  venv/bin/python3 tools/test_airing_rules.py
No GUI required.
"""
import importlib.util
import json
import os
import sys
import tempfile

# ---------------------------------------------------------------------------
# Load the module without launching the Qt app
# ---------------------------------------------------------------------------
spec = importlib.util.spec_from_file_location("cs2000", os.path.join(os.path.dirname(__file__), "..", "channelsurfer2000.py"))
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except SystemExit:
    pass

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
# normalize_airing_time
# ---------------------------------------------------------------------------
section("normalize_airing_time")
check("valid time HH:MM",          mod.normalize_airing_time("22:30") == "22:30")
check("valid time H:MM pads",      mod.normalize_airing_time("9:05") == "09:05")
check("bad hour 24 rejected",      mod.normalize_airing_time("24:00") == "")
check("bad format rejected",       mod.normalize_airing_time("930") == "")
check("empty string safe",         mod.normalize_airing_time("") == "")
check("None safe",                 mod.normalize_airing_time(None) == "")

# ---------------------------------------------------------------------------
# normalize_airing_date
# ---------------------------------------------------------------------------
section("normalize_airing_date")
check("valid date",                mod.normalize_airing_date("2025-10-01") == "2025-10-01")
check("bad month 13 rejected",     mod.normalize_airing_date("2025-13-01") == "")
check("bad day 00 rejected",       mod.normalize_airing_date("2025-10-00") == "")
check("garbage rejected",          mod.normalize_airing_date("not-a-date") == "")
check("empty string safe",         mod.normalize_airing_date("") == "")

# ---------------------------------------------------------------------------
# normalize_airing_rule_type — forward compat: unknown types preserved
# ---------------------------------------------------------------------------
section("normalize_airing_rule_type and unknown type preservation")
check("known type passes",         mod.normalize_airing_rule_type("prefer_daytime") == "prefer_daytime")
check("unknown type returns empty", mod.normalize_airing_rule_type("prefer_morning_v2") == "")

rule_unknown_type = mod.normalize_airing_rule({"rule_type": "prefer_morning_v2"})
check("unknown rule_type preserved (not clobbered)", rule_unknown_type["rule_type"] == "prefer_morning_v2",
      f"got {rule_unknown_type['rule_type']!r}")
check("empty rule_type falls back to always_allowed", mod.normalize_airing_rule({})["rule_type"] == "always_allowed")

# ---------------------------------------------------------------------------
# normalize_days_of_week
# ---------------------------------------------------------------------------
section("normalize_days_of_week")
check("list input",                mod.normalize_days_of_week(["mon", "fri"]) == ["mon", "fri"])
check("string input comma",        mod.normalize_days_of_week("mon,fri") == ["mon", "fri"])
check("string input space",        mod.normalize_days_of_week("sat sun") == ["sat", "sun"])
check("order is canonical",        mod.normalize_days_of_week(["sun", "mon"]) == ["mon", "sun"])
check("garbage filtered",          mod.normalize_days_of_week(["xyz", "mon"]) == ["mon"])
check("None safe",                 mod.normalize_days_of_week(None) == [])

# ---------------------------------------------------------------------------
# normalize_airing_rule — full rule
# ---------------------------------------------------------------------------
section("normalize_airing_rule")
r = mod.normalize_airing_rule({
    "level": "show",
    "rule_type": "only_between_times",
    "rule_strength": "strict",
    "target": {"title": "Halloweentown", "extra_future_field": "preserved"},
    "start_time": "22:00",
    "end_time": "6:00",
    "only_on_dates": ["2025-10-01", "bad-date", "2025-10-31"],
})
check("level preserved",           r["level"] == "show")
check("rule_type preserved",       r["rule_type"] == "only_between_times")
check("rule_strength preserved",   r["rule_strength"] == "strict")
check("start_time normalized",     r["start_time"] == "22:00")
check("end_time normalized",       r["end_time"] == "06:00")
check("bad dates filtered from only_on_dates", r["only_on_dates"] == ["2025-10-01", "2025-10-31"],
      f"got {r['only_on_dates']}")
check("title_key auto-derived",    r["target"]["title_key"] == "halloweentown")
check("unknown target field preserved", r["target"].get("extra_future_field") == "preserved")
check("id assigned",               bool(r.get("id")))
check("id stable on re-normalize", mod.normalize_airing_rule(r)["id"] == r["id"])

# ---------------------------------------------------------------------------
# normalize_channel_takeover
# ---------------------------------------------------------------------------
section("normalize_channel_takeover")
t = mod.normalize_channel_takeover({
    "takeover_name": "FearFest",
    "source_channel_id": "media:/AMC",
    "enabled": True,
    "start_time": "20:00",
    "end_time": "6:00",
    "days_of_week": ["fri", "sat", "sun"],
    "seasonal_preset": "spooky_season",
    "rule_strength": "strong_preference",
    "future_field_v2": "keep_me",
})
check("takeover_name",             t["takeover_name"] == "FearFest")
check("source_channel_id",         t["source_channel_id"] == "media:/AMC")
check("enabled",                   t["enabled"] is True)
check("days_of_week canonical order", t["days_of_week"] == ["fri", "sat", "sun"])
check("seasonal_preset",           t["seasonal_preset"] == "spooky_season")
check("rule_strength",             t["rule_strength"] == "strong_preference")
check("unknown top-level field preserved", t.get("future_field_v2") == "keep_me")
check("id assigned",               bool(t.get("id")))

# ---------------------------------------------------------------------------
# normalize_airing_rules_config — top-level, unknown field preservation
# ---------------------------------------------------------------------------
section("normalize_airing_rules_config")
raw = {
    "airing_rules_version": 1,
    "channel_rules": [{"rule_type": "prefer_late_night", "target": {"channel_id": "media:/x"}}],
    "show_rules": [],
    "genre_rules": [],
    "channel_takeovers": [],
    "future_top_level_key": "preserved",
}
cfg = mod.normalize_airing_rules_config(raw)
check("version set",               cfg["airing_rules_version"] == mod.AIRING_RULES_VERSION)
check("channel_rules normalized",  len(cfg["channel_rules"]) == 1)
check("level overridden correctly", cfg["channel_rules"][0]["level"] == "channel")
check("unknown top-level preserved", cfg.get("future_top_level_key") == "preserved")

# malformed top-level
cfg_bad = mod.normalize_airing_rules_config("garbage string")
check("malformed config gives safe defaults", cfg_bad["channel_rules"] == [] and cfg_bad["channel_takeovers"] == [])

# null lists in config
cfg_nulls = mod.normalize_airing_rules_config({"channel_rules": None, "channel_takeovers": None})
check("null list fields safe", cfg_nulls["channel_rules"] == [] and cfg_nulls["channel_takeovers"] == [])

# non-dict items in rules list dropped
cfg_junk = mod.normalize_airing_rules_config({"channel_rules": ["not-a-dict", 42, {"rule_type": "prefer_daytime"}]})
check("non-dict rule items dropped", len(cfg_junk["channel_rules"]) == 1)

# ---------------------------------------------------------------------------
# validate_airing_rules_config
# ---------------------------------------------------------------------------
section("validate_airing_rules_config")

# valid config produces no warnings
clean = mod.normalize_airing_rules_config({
    "channel_rules": [{"rule_type": "always_allowed", "target": {"channel_id": "media:/x"}}],
    "channel_takeovers": [{
        "takeover_name": "Adult Swim",
        "source_channel_id": "media:/x",
        "start_time": "22:00",
        "end_time": "06:00",
        "enabled": True,
    }],
})
w = mod.validate_airing_rules_config(clean, known_channel_ids={"media:/x"})
check("clean config no warnings", w == [], f"warnings: {w}")

# stale channel_id warns
w2 = mod.validate_airing_rules_config(clean, known_channel_ids={"media:/other"})
check("stale channel_id warns", any("unknown channel_id" in x for x in w2), f"warnings: {w2}")

# missing logo warns
takeover_bad_logo = mod.normalize_channel_takeover({
    "takeover_name": "Test",
    "source_channel_id": "media:/x",
    "display_logo_path": "/no/such/logo.png",
})
cfg_bad_logo = {"channel_rules": [], "show_rules": [], "genre_rules": [], "channel_takeovers": [takeover_bad_logo]}
w3 = mod.validate_airing_rules_config(cfg_bad_logo)
check("missing logo warns not crashes", any("display_logo_path" in x for x in w3), f"warnings: {w3}")

# invalid date range warns
cfg_bad_date = mod.normalize_airing_rules_config({
    "channel_rules": [{"rule_type": "only_between_dates", "start_date": "2025-12-01", "end_date": "2025-01-01"}],
})
w4 = mod.validate_airing_rules_config(cfg_bad_date)
check("inverted date range warns", any("is after end_date" in x for x in w4), f"warnings: {w4}")

# custom_date_range missing dates warns
cfg_no_range = mod.normalize_airing_rules_config({
    "channel_rules": [{"rule_type": "custom_date_range"}],
})
w5 = mod.validate_airing_rules_config(cfg_no_range)
check("custom_date_range missing dates warns", any("custom_date_range" in x for x in w5), f"warnings: {w5}")

# only_on_dates rule with no dates warns
cfg_no_dates = mod.normalize_airing_rules_config({
    "show_rules": [{"rule_type": "only_on_dates"}],
})
w6 = mod.validate_airing_rules_config(cfg_no_dates)
check("only_on_dates empty warns", any("only_on_dates" in x for x in w6), f"warnings: {w6}")

# blocked_on_dates rule with no dates warns separately
cfg_no_blocked = mod.normalize_airing_rules_config({
    "show_rules": [{"rule_type": "blocked_on_dates"}],
})
w7 = mod.validate_airing_rules_config(cfg_no_blocked)
check("blocked_on_dates empty warns", any("blocked_on_dates" in x for x in w7), f"warnings: {w7}")

# conflicting strict takeovers
t1 = mod.normalize_channel_takeover({"takeover_name": "A", "source_channel_id": "media:/cn", "enabled": True, "rule_strength": "strict"})
t2 = mod.normalize_channel_takeover({"takeover_name": "B", "source_channel_id": "media:/cn", "enabled": True, "rule_strength": "strict"})
w8 = mod.validate_airing_rules_config({"channel_rules": [], "show_rules": [], "genre_rules": [], "channel_takeovers": [t1, t2]})
check("conflicting strict takeovers warn", any("conflicting strict Channel Takeovers" in x for x in w8), f"warnings: {w8}")

# non-dict config warns gracefully
w9 = mod.validate_airing_rules_config(None)
check("None config warns not crashes", len(w9) > 0)

# ---------------------------------------------------------------------------
# diagnostics return dict
# ---------------------------------------------------------------------------
section("airing_rules_diagnostics")
summary = mod.airing_rules_diagnostics(mod.airing_rules_config_defaults(), log=False)
check("returns dict",              isinstance(summary, dict))
check("has version",               "airing_rules_version" in summary)
check("has counts",                all(k in summary for k in ("channel_rule_count", "show_rule_count", "genre_rule_count", "channel_takeover_count")))
check("has warnings list",         isinstance(summary["warnings"], list))
check("diagnostics on garbage",    mod.airing_rules_diagnostics(None, log=False)["channel_rule_count"] == 0)

# ---------------------------------------------------------------------------
# File not created when no rules exist
# ---------------------------------------------------------------------------
section("file not auto-created for new users")
check("airing_rules.json does not exist in repo root",
      not os.path.exists(mod.AIRING_RULES_FILE),
      f"found at {mod.AIRING_RULES_FILE}")

# ---------------------------------------------------------------------------
# load_airing_rules_config with real temp file
# ---------------------------------------------------------------------------
section("load/save round-trip")
with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, "airing_rules.json")

    # Write a config with a future field and an unknown rule_type
    original_data = {
        "airing_rules_version": 1,
        "channel_rules": [{"rule_type": "prefer_morning_v2", "target": {"title": "Test"}, "future_rule_field": 99}],
        "show_rules": [],
        "genre_rules": [],
        "channel_takeovers": [],
        "future_top": "preserved",
    }
    with open(path, "w") as f:
        json.dump(original_data, f)

    loaded = mod.normalize_airing_rules_config(mod.load_json_file(path, mod.airing_rules_config_defaults()))
    check("round-trip: unknown rule_type preserved", loaded["channel_rules"][0]["rule_type"] == "prefer_morning_v2",
          f"got {loaded['channel_rules'][0]['rule_type']!r}")
    check("round-trip: unknown rule field preserved", loaded["channel_rules"][0].get("future_rule_field") == 99)
    check("round-trip: unknown top-level field preserved", loaded.get("future_top") == "preserved")

    # Malformed JSON loads safely
    with open(path, "w") as f:
        f.write("{not valid json")
    safe = mod.load_json_file(path, mod.airing_rules_config_defaults())
    check("malformed JSON returns defaults", safe == mod.airing_rules_config_defaults())

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

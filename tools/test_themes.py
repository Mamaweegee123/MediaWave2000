"""
Smoke tests for the theme framework module.
Run from the repo root:  venv/bin/python3 tools/test_themes.py
No GUI launch required.
"""
import os
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave import themes as mod

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


section("built-in themes")
builtins = mod.list_builtin_themes()
builtin_names = {(item["skin"], item["name"]) for item in builtins}
check("built-ins listed", len(builtins) > 0)
check("Promised Future listed", ("Promised Future", "Silver Olive") in builtin_names)
check("Set Top Box listed", ("Set Top Box", "Stars of Uranus") in builtin_names)
check("Sleek Freak listed", ("Sleek Freak", "Stars of Uranus") in builtin_names)
check("builtin lookup returns tokens", bool(mod.get_builtin_theme("Silver Olive", "Promised Future")))


section("no custom theme file")
with tempfile.TemporaryDirectory() as tmpdir:
    missing = os.path.join(tmpdir, "custom_themes.json")
    cfg = mod.load_custom_themes_config(missing)
    check("missing file safe defaults", cfg["themes"] == [] and cfg["warnings"] == [])
    check("available themes are built-ins", len(mod.list_available_themes(cfg)) == len(builtins))


section("malformed config")
with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, "custom_themes.json")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{not valid json")
    cfg = mod.load_custom_themes_config(path)
    summary = mod.themes_diagnostics(cfg)
    check("malformed config warns", bool(cfg["warnings"]))
    check("malformed config has no custom themes", summary["custom_theme_count"] == 0)


section("custom fallback and preservation")
custom = {
    "custom_theme_version": 1,
    "themes": [
        {
            "id": "my-night",
            "name": "My Night",
            "base_theme": "Silver Olive",
            "colors": {"selected": "#010203"},
            "fonts": {"font_ui": "Test UI"},
            "logo_style": "classic",
            "guide_style": "aero",
            "notes": "test only",
            "future_field": {"keep": True},
        }
    ],
    "future_top_level": "preserved",
}
cfg = mod.normalize_custom_themes_config(custom)
available = mod.list_available_themes(cfg)
custom_items = [item for item in available if item.get("custom")]
base = mod.app_theme("Silver Olive", "Promised Future")
theme = custom_items[0]["theme"] if custom_items else {}
check("custom theme included", len(custom_items) == 1)
check("missing color falls back to base", theme.get("bg") == base["bg"])
check("custom color overrides base", (theme.get("selected").red(), theme.get("selected").green(), theme.get("selected").blue()) == (1, 2, 3))
check("custom font overrides token", theme.get("font_ui") == "Test UI")
check("unknown theme field preserved", cfg["themes"][0].get("future_field") == {"keep": True})
check("unknown top-level field preserved", cfg.get("future_top_level") == "preserved")


section("warnings")
dupes = mod.normalize_custom_themes_config({
    "themes": [
        {"id": "dup", "name": "Dup", "base_theme": "Silver Olive"},
        {"id": "dup", "name": "Dup Again", "base_theme": "Silver Olive"},
        {"id": "missing-base", "name": "Missing Base", "base_theme": "Not Real"},
        {"id": "bad-color", "name": "Bad Color", "base_theme": "Silver Olive", "colors": {"bg": "nope"}},
    ]
})
summary = mod.themes_diagnostics(dupes)
check("duplicate id warns", "dup" in summary["duplicate_theme_ids"], f"summary: {summary}")
check("missing base warns", "Not Real" in summary["missing_base_theme_references"], f"summary: {summary}")
check("invalid custom warnings collected", len(summary["invalid_custom_theme_warnings"]) >= 3, f"summary: {summary}")
check("invalid themes skipped from available list", len([item for item in mod.list_available_themes(dupes) if item.get("custom")]) == 1)


print(f"\n{'='*50}")
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("All theme smoke tests passed.")

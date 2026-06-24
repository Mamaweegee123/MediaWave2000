# Custom Themes

Custom themes are framework-only for now. MediaWave still uses the existing built-in theme picker and visual behavior.

The planned config shape is versioned:

```json
{
  "custom_theme_version": 1,
  "themes": [
    {
      "id": "my-theme",
      "name": "My Theme",
      "base_theme": "Silver Olive",
      "colors": {},
      "fonts": {},
      "logo_style": "",
      "guide_style": "",
      "notes": ""
    }
  ]
}
```

Custom themes are additive. If no custom theme file exists, built-in themes continue to work. Malformed custom themes are skipped with diagnostics, missing color keys fall back to the selected base theme, and unknown future fields are preserved where reasonable.

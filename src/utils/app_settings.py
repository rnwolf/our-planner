"""Small persisted app-level preferences.

For things like base font size and zoom level - characteristics of the
user's own screen/viewing preference, not of any particular plan's data,
so they don't belong in a saved project file, and shouldn't need
re-entering every time the app launches.
"""

import json
from pathlib import Path
from typing import Any

SETTINGS_PATH = Path.home() / '.our-planner' / 'settings.json'

DEFAULTS: dict[str, Any] = {
    'base_font_size': 9,
    'zoom_level': 1.0,
}


def load_settings() -> dict[str, Any]:
    """Current settings, with defaults filled in for anything missing or
    if the file doesn't exist yet or can't be parsed."""
    settings = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, encoding='utf-8') as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            settings.update(saved)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return settings


def save_settings(changes: dict[str, Any]) -> None:
    """Merge `changes` into whatever's already saved and write it back -
    never overwrites unrelated settings a future caller might add."""
    current = load_settings()
    current.update(changes)
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(current, f, indent=2)

"""Load and save application-level settings (target window, focus behavior)."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from auto_click_zones.config import DATA_DIR, SETTINGS_FILE


@dataclass
class AppSettings:
    """Persisted settings that apply to the whole macro (not per-zone)."""

    target_window: str = ""  # substring to match against a window title, e.g. "Notepad"
    require_window_active: bool = True  # only click while the target window is focused
    auto_focus_window: bool = False  # bring target window to front before each cycle
    start_hotkey: str = "f6"  # global hotkey used to start the macro
    stop_hotkey: str = "f7"  # global hotkey used to stop the macro

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        return cls(
            target_window=data.get("target_window", ""),
            require_window_active=data.get("require_window_active", True),
            auto_focus_window=data.get("auto_focus_window", False),
            start_hotkey=data.get("start_hotkey", "f6"),
            stop_hotkey=data.get("stop_hotkey", "f7"),
        )


def load_settings(path: Optional[Path] = None) -> AppSettings:
    """Load app settings from JSON file. Returns defaults if missing or unreadable."""
    file_path = path or SETTINGS_FILE
    if not file_path.exists():
        return AppSettings()

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return AppSettings.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return AppSettings()


def save_settings(settings: AppSettings, path: Optional[Path] = None) -> None:
    """Save app settings to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_path = path or SETTINGS_FILE
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(settings.to_dict(), file, indent=2)

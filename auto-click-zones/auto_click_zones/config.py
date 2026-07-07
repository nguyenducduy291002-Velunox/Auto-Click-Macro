"""Application configuration and default settings."""

import sys
from pathlib import Path


def _get_app_dir() -> Path:
    """Return app root directory (works for script and PyInstaller exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_bundle_dir() -> Path:
    """Return bundled read-only resource directory when running as exe."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return _get_app_dir()


def ensure_runtime_data() -> None:
    """Copy bundled default data next to exe on first run."""
    if not getattr(sys, "frozen", False):
        return

    import shutil

    app_data = _get_app_dir() / "data"
    bundle_data = _get_bundle_dir() / "data"
    if not bundle_data.exists():
        return

    app_data.mkdir(parents=True, exist_ok=True)
    (app_data / "templates").mkdir(parents=True, exist_ok=True)

    zones_file = app_data / "zones.json"
    if not zones_file.exists():
        bundled_zones = bundle_data / "zones.json"
        if bundled_zones.exists():
            shutil.copy2(bundled_zones, zones_file)


# Base paths
APP_DIR = _get_app_dir()
DATA_DIR = APP_DIR / "data"
ZONES_FILE = DATA_DIR / "zones.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
TEMPLATES_DIR = DATA_DIR / "templates"

# Click behavior
DEFAULT_CLICK_DELAY = 0.5  # seconds between each zone click
DEFAULT_CYCLE_DELAY = 1.0  # seconds between full cycles
CLICKS_PER_ZONE = 1  # click each zone exactly once per cycle

# Zone detection
IMAGE_MATCH_CONFIDENCE = 0.85  # 0.0 to 1.0, higher = stricter match
SCREENSHOT_FORMAT = "PNG"

# GUI settings
WINDOW_TITLE = "Auto Click Zones"
WINDOW_WIDTH = 860
WINDOW_HEIGHT = 660

# Hotkeys
HOTKEY_START = "f6"
HOTKEY_STOP = "f7"
HOTKEY_ADD_ZONE = "f8"

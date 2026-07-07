"""Detect click zones on screen using coordinates or image matching."""

from pathlib import Path
from typing import Optional, Tuple

import pyautogui

from auto_click_zones.config import IMAGE_MATCH_CONFIDENCE
from auto_click_zones.models.zone import Zone


def get_mouse_position() -> Tuple[int, int]:
    """Return the current mouse cursor position."""
    position = pyautogui.position()
    return position.x, position.y


def detect_zone_position(zone: Zone) -> Optional[Tuple[int, int]]:
    """
    Detect where to click for a zone.

    Uses image template matching when enabled, otherwise fixed coordinates.
    Returns (x, y) or None if detection fails.
    """
    if zone.use_image_detection and zone.template_path:
        return detect_by_image(zone.template_path)

    if zone.x >= 0 and zone.y >= 0:
        return zone.x, zone.y

    return None


def detect_by_image(template_path: str) -> Optional[Tuple[int, int]]:
    """
    Find a template image on screen and return its center coordinates.

    Uses pyautogui.locateOnScreen with confidence when OpenCV is available.
    """
    path = Path(template_path)
    if not path.exists():
        return None

    try:
        location = _locate_on_screen(str(path))
    except pyautogui.ImageNotFoundException:
        return None
    except Exception:
        return None

    if location is None:
        return None

    center = pyautogui.center(location)
    return center.x, center.y


def _locate_on_screen(template_path: str):
    """Locate template on screen, using confidence if OpenCV is installed."""
    try:
        import cv2  # noqa: F401
        return pyautogui.locateOnScreen(
            template_path,
            confidence=IMAGE_MATCH_CONFIDENCE,
        )
    except ImportError:
        return pyautogui.locateOnScreen(template_path)


def capture_template_region(
    x: int,
    y: int,
    width: int,
    height: int,
    save_path: Path,
) -> bool:
    """
    Capture a screen region as a template image for later detection.

    Returns True on success.
    """
    try:
        screenshot = pyautogui.screenshot(region=(x, y, width, height))
        save_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot.save(str(save_path))
        return True
    except Exception:
        return False


def validate_zone_detectable(zone: Zone) -> Tuple[bool, str]:
    """Check if a zone can be detected. Returns (ok, message)."""
    if not zone.enabled:
        return False, "Zone is disabled"

    if zone.use_image_detection:
        if not zone.template_path:
            return False, "No template image set"
        if not Path(zone.template_path).exists():
            return False, f"Template not found: {zone.template_path}"
        position = detect_by_image(zone.template_path)
        if position is None:
            return False, "Template not visible on screen"
        return True, f"Found at {position}"

    if zone.x < 0 or zone.y < 0:
        return False, "Invalid coordinates"

    return True, f"Fixed position ({zone.x}, {zone.y})"

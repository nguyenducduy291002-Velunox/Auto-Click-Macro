"""Load, save, and manage click zones."""

import json
import uuid
from pathlib import Path
from typing import List, Optional

from auto_click_zones.config import DATA_DIR, ZONES_FILE
from auto_click_zones.models.zone import Zone


def ensure_data_dirs() -> None:
    """Create data directories if they do not exist."""
    from auto_click_zones.config import TEMPLATES_DIR

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def load_zones(path: Optional[Path] = None) -> List[Zone]:
    """Load zones from JSON file. Returns empty list if file is missing."""
    ensure_data_dirs()
    file_path = path or ZONES_FILE

    if not file_path.exists():
        return []

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    return [Zone.from_dict(item) for item in data.get("zones", [])]


def save_zones(zones: List[Zone], path: Optional[Path] = None) -> None:
    """Save zones to JSON file."""
    ensure_data_dirs()
    file_path = path or ZONES_FILE

    payload = {"zones": [zone.to_dict() for zone in zones]}
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def add_zone(
    zones: List[Zone],
    name: str,
    x: int,
    y: int,
    use_image_detection: bool = False,
    template_path: Optional[str] = None,
    delay_after: Optional[float] = None,
    after_zone_id: Optional[str] = None,
) -> Zone:
    """
    Add a new zone and return it.

    If after_zone_id is given and found, the new zone is inserted right
    after it in the list (so you can build a zone in the middle of an
    existing macro). Otherwise it's appended at the end, as before.
    """
    zone = Zone(
        id=str(uuid.uuid4())[:8],
        name=name,
        x=x,
        y=y,
        use_image_detection=use_image_detection,
        template_path=template_path,
        delay_after=delay_after,
    )
    insert_zone(zones, zone, after_zone_id)
    return zone


def insert_zone(zones: List[Zone], zone: Zone, after_zone_id: Optional[str] = None) -> None:
    """Insert `zone` right after after_zone_id, or append at the end if None/not found."""
    if after_zone_id is not None:
        for index, existing in enumerate(zones):
            if existing.id == after_zone_id:
                zones.insert(index + 1, zone)
                return
    zones.append(zone)


def move_zone(zones: List[Zone], zone_id: str, delta: int) -> bool:
    """
    Move a zone earlier (delta=-1) or later (delta=+1) in the execution
    order. Returns True if it moved, False if it was already at that end.
    """
    index = next((i for i, z in enumerate(zones) if z.id == zone_id), None)
    if index is None:
        return False
    new_index = index + delta
    if new_index < 0 or new_index >= len(zones):
        return False
    zones[index], zones[new_index] = zones[new_index], zones[index]
    return True


def set_zone_note(zones: List[Zone], zone_id: str, note: str) -> bool:
    """Set a zone's free-text note. Purely for reference - never used by the click engine."""
    zone = get_zone_by_id(zones, zone_id)
    if zone is None:
        return False
    zone.note = note
    return True


def set_zone_delay(zones: List[Zone], zone_id: str, delay_after: Optional[float]) -> bool:
    """Set the per-zone delay-after-click for a zone. Pass None to fall back to the global delay."""
    zone = get_zone_by_id(zones, zone_id)
    if zone is None:
        return False
    zone.delay_after = delay_after
    return True


def set_zone_action(
    zones: List[Zone],
    zone_id: str,
    action: str,
    scroll_amount: int = 0,
    scroll_to_extent: bool = False,
    key_sequence: str = "",
    text_to_type: str = "",
) -> bool:
    """
    Set a zone's action type.

    action: "click", "scroll", "hotkey", or "type_text". scroll_amount is
    only meaningful for "scroll" - positive scrolls up, negative scrolls down.
    If scroll_to_extent is True, scroll_amount is used as the step size per
    scroll burst, and the zone keeps scrolling in that direction until the
    screen stops changing (i.e. it reaches the top/bottom), instead of
    scrolling a fixed total amount.
    """
    zone = get_zone_by_id(zones, zone_id)
    if zone is None:
        return False
    zone.action = action
    zone.scroll_amount = scroll_amount
    zone.scroll_to_extent = scroll_to_extent
    zone.key_sequence = key_sequence
    zone.text_to_type = text_to_type
    return True


def remove_zone(zones: List[Zone], zone_id: str) -> bool:
    """Remove a zone by ID. Returns True if removed."""
    for index, zone in enumerate(zones):
        if zone.id == zone_id:
            zones.pop(index)
            return True
    return False


def get_zone_by_id(zones: List[Zone], zone_id: str) -> Optional[Zone]:
    """Find a zone by its ID."""
    for zone in zones:
        if zone.id == zone_id:
            return zone
    return None


def toggle_zone_enabled(zones: List[Zone], zone_id: str) -> bool:
    """Toggle a zone's enabled state. Returns new enabled value or False if not found."""
    zone = get_zone_by_id(zones, zone_id)
    if zone is None:
        return False
    zone.enabled = not zone.enabled
    return zone.enabled


def get_enabled_zones(zones: List[Zone]) -> List[Zone]:
    """Return only enabled zones."""
    return [zone for zone in zones if zone.enabled]

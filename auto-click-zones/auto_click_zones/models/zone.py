"""Zone data model representing a click, scroll, or keyboard target."""

from dataclasses import dataclass, field
from typing import Optional

ACTION_CLICK = "click"
ACTION_SCROLL = "scroll"
ACTION_HOTKEY = "hotkey"
ACTION_TYPE_TEXT = "type_text"


@dataclass
class Zone:
    """A zone to click, scroll, or send keyboard input.

    A zone's position can be a fixed (x, y) or detected live via an image
    template (use_image_detection) - this applies to both click and scroll
    actions, so a scrollbar captured as a template image can be located
    dynamically each cycle and scrolled at, the same way a click target can.
    Keyboard actions do not need a screen position.
    """

    name: str
    x: int = 0
    y: int = 0
    use_image_detection: bool = False
    template_path: Optional[str] = None
    enabled: bool = True
    delay_after: Optional[float] = None  # seconds to wait after acting on this zone
    action: str = ACTION_CLICK  # "click" or "scroll"
    scroll_amount: int = 0  # scroll "clicks": positive = up, negative = down
    scroll_to_extent: bool = False  # if True, keep scrolling until the page stops moving
    key_sequence: str = ""  # hotkey combo, e.g. "ctrl+c" or "ctrl+shift+v"
    text_to_type: str = ""  # literal text/numbers to type
    note: str = ""  # free-text note for your own reference; never used by the click engine
    id: str = field(default="")

    def to_dict(self) -> dict:
        """Convert zone to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "use_image_detection": self.use_image_detection,
            "template_path": self.template_path,
            "enabled": self.enabled,
            "delay_after": self.delay_after,
            "action": self.action,
            "scroll_amount": self.scroll_amount,
            "scroll_to_extent": self.scroll_to_extent,
            "key_sequence": self.key_sequence,
            "text_to_type": self.text_to_type,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Zone":
        """Create a zone from a dictionary."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Unnamed"),
            x=data.get("x", 0),
            y=data.get("y", 0),
            use_image_detection=data.get("use_image_detection", False),
            template_path=data.get("template_path"),
            enabled=data.get("enabled", True),
            delay_after=data.get("delay_after"),
            action=data.get("action", ACTION_CLICK),
            scroll_amount=data.get("scroll_amount", 0),
            scroll_to_extent=data.get("scroll_to_extent", False),
            key_sequence=data.get("key_sequence", ""),
            text_to_type=str(data.get("text_to_type", "")),
            note=data.get("note", ""),
        )

    def display_text(self) -> str:
        """Return a human-readable summary for the UI list."""
        mode = "image" if self.use_image_detection else f"({self.x}, {self.y})"
        status = "ON" if self.enabled else "OFF"
        delay = f", delay after: {self.delay_after}s" if self.delay_after is not None else ""

        if self.action == ACTION_SCROLL:
            direction = "up" if self.scroll_amount >= 0 else "down"
            if self.scroll_to_extent:
                action_text = f", action: scroll {direction} until it stops (step {abs(self.scroll_amount)})"
            else:
                action_text = f", action: scroll {direction} x{abs(self.scroll_amount)} notches"
        elif self.action == ACTION_HOTKEY:
            action_text = f", action: hotkey {self.key_sequence or '(not set)'}"
        elif self.action == ACTION_TYPE_TEXT:
            preview = self.text_to_type
            if len(preview) > 24:
                preview = f"{preview[:21]}..."
            action_text = f", action: type {preview or '(not set)'}"
        else:
            action_text = ""

        return f"{self.name} [{mode}] - {status}{action_text}{delay}"

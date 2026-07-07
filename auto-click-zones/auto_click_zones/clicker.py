"""Auto-click engine - clicks each zone once per cycle."""

import re
import threading
import time
from typing import Callable, List, Optional

import pyautogui
from PIL import ImageChops

from auto_click_zones import window_utils
from auto_click_zones.config import CLICKS_PER_ZONE, DEFAULT_CLICK_DELAY
from auto_click_zones.models.zone import ACTION_HOTKEY, ACTION_SCROLL, ACTION_TYPE_TEXT, Zone
from auto_click_zones.zone_detector import detect_zone_position
from auto_click_zones.zone_manager import get_enabled_zones

# Safety: move mouse to corner to abort (pyautogui failsafe)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

# On Windows, pyautogui.scroll(N) sends N as a raw wheel delta, not a count
# of "notches" - Windows treats one real wheel notch as 120 units
# (WHEEL_DELTA). Without this multiplier, even a huge "scroll amount" barely
# moves the page, because e.g. 999 raw units is only ~8 real notches.
WHEEL_CLICK_UNITS = 120

# Safety caps for "scroll until it stops" so a page that never settles
# (e.g. a live-updating feed) can't loop forever.
SCROLL_TO_EXTENT_MAX_STEPS = 400
SCROLL_TO_EXTENT_STABLE_STEPS_TO_STOP = 2
SCROLL_TO_EXTENT_SETTLE_DELAY = 0.15
SCROLL_TO_EXTENT_REGION_HALF_SIZE = 250  # pixels around (x, y) used to detect movement

KEY_ALIASES = {
    "control": "ctrl",
    "ctl": "ctrl",
    "escape": "esc",
    "del": "delete",
    "return": "enter",
    "windows": "win",
    "cmd": "win",
    "command": "win",
}
MODIFIER_KEYS = {"ctrl", "shift", "alt", "win"}


def _expand_hotkey_token(token: str) -> List[str]:
    """Expand one hotkey token, including forms like 'tab*2' or 'tabx2'."""
    repeat_match = re.fullmatch(r"([a-z0-9_]+)(?:\*|x)(\d+)", token)
    if repeat_match:
        key = KEY_ALIASES.get(repeat_match.group(1), repeat_match.group(1))
        count = max(1, int(repeat_match.group(2)))
        return [key] * count

    leading_count_match = re.fullmatch(r"(\d+)([a-z0-9_]+)", token)
    if leading_count_match:
        count = max(1, int(leading_count_match.group(1)))
        key = KEY_ALIASES.get(leading_count_match.group(2), leading_count_match.group(2))
        return [key] * count

    return [KEY_ALIASES.get(token, token)]


def _parse_hotkey_sequence(sequence: str) -> List[str]:
    """Convert user input like 'Ctrl C' or 'alt+tab*2' into pyautogui keys."""
    normalized = sequence.strip().lower().replace("+", " ").replace(",", " ")
    tokens = normalized.split()
    keys: List[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.isdigit() and index + 1 < len(tokens):
            next_key = KEY_ALIASES.get(tokens[index + 1], tokens[index + 1])
            keys.extend([next_key] * max(1, int(token)))
            index += 2
            continue
        keys.extend(_expand_hotkey_token(token))
        index += 1
    return keys


def _perform_hotkey(sequence: str) -> bool:
    """Press a hotkey combo. Returns False when no usable keys were provided."""
    keys = _parse_hotkey_sequence(sequence)
    if not keys:
        return False

    modifiers = []
    normal_keys = []
    for key in keys:
        if key in MODIFIER_KEYS and not normal_keys:
            modifiers.append(key)
        else:
            normal_keys.append(key)

    if not modifiers or not normal_keys:
        pyautogui.hotkey(*keys)
        return True

    for modifier in modifiers:
        pyautogui.keyDown(modifier)
    try:
        for key in normal_keys:
            pyautogui.press(key)
    finally:
        for modifier in reversed(modifiers):
            pyautogui.keyUp(modifier)
    return True


def _type_text(text: str) -> bool:
    """Type literal text/numbers into the active target."""
    if text == "":
        return False
    pyautogui.write(text, interval=0.01)
    return True


def _perform_scroll(x: int, y: int, notches: int) -> None:
    """Move to (x, y) and scroll by `notches` real mouse-wheel notches."""
    pyautogui.moveTo(x, y)
    pyautogui.scroll(notches * WHEEL_CLICK_UNITS)


def _screenshot_region(x: int, y: int):
    """Grab a screenshot of the area around (x, y), clipped to screen bounds."""
    screen_w, screen_h = pyautogui.size()
    half = SCROLL_TO_EXTENT_REGION_HALF_SIZE
    left = max(0, x - half)
    top = max(0, y - half)
    right = min(screen_w, x + half)
    bottom = min(screen_h, y + half)
    width = max(1, right - left)
    height = max(1, bottom - top)
    return pyautogui.screenshot(region=(left, top, width, height))


def _images_equal(img_a, img_b) -> bool:
    """True if two screenshots are pixel-identical (i.e. nothing moved)."""
    return ImageChops.difference(img_a.convert("RGB"), img_b.convert("RGB")).getbbox() is None


def _perform_scroll_to_extent(
    x: int,
    y: int,
    step_notches: int,
    is_running: Callable[[], bool] = lambda: True,
    on_status: Callable[[str], None] = lambda _msg: None,
) -> int:
    """
    Move to (x, y) and keep scrolling in bursts of `step_notches` (sign
    indicates direction) until the screen around that point stops changing
    between bursts - i.e. the page hit the top/bottom - or a safety cap of
    steps is reached. Returns the number of scroll bursts performed.
    """
    pyautogui.moveTo(x, y)
    previous_shot = _screenshot_region(x, y)
    stable_count = 0
    steps_done = 0

    for step in range(SCROLL_TO_EXTENT_MAX_STEPS):
        if not is_running():
            break

        pyautogui.scroll(step_notches * WHEEL_CLICK_UNITS)
        steps_done += 1
        time.sleep(SCROLL_TO_EXTENT_SETTLE_DELAY)

        current_shot = _screenshot_region(x, y)
        if _images_equal(previous_shot, current_shot):
            stable_count += 1
            if stable_count >= SCROLL_TO_EXTENT_STABLE_STEPS_TO_STOP:
                break
        else:
            stable_count = 0
        previous_shot = current_shot
    else:
        on_status(f"Scroll-to-extent hit its {SCROLL_TO_EXTENT_MAX_STEPS}-step safety limit.")

    return steps_done


class AutoClicker:
    """Runs click cycles over a list of zones in a background thread."""

    def __init__(
        self,
        on_status: Optional[Callable[[str], None]] = None,
        on_cycle_done: Optional[Callable[[int], None]] = None,
    ) -> None:
        self._zones: List[Zone] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._click_delay = DEFAULT_CLICK_DELAY
        self._cycle_delay = 1.0
        self._repeat_cycles = 1
        self._target_window = ""
        self._require_window_active = True
        self._auto_focus_window = False
        self._on_status = on_status or (lambda _: None)
        self._on_cycle_done = on_cycle_done or (lambda _: None)

    @property
    def is_running(self) -> bool:
        return self._running

    def set_zones(self, zones: List[Zone]) -> None:
        """Update the zone list used for clicking."""
        self._zones = zones

    def set_delays(self, click_delay: float, cycle_delay: float) -> None:
        """Set delay between clicks and between cycles."""
        self._click_delay = max(0.0, click_delay)
        self._cycle_delay = max(0.0, cycle_delay)

    def set_repeat_cycles(self, count: int) -> None:
        """Set how many full cycles to run (0 = infinite until stopped)."""
        self._repeat_cycles = max(0, count)

    def set_target_window(
        self,
        target_window: str,
        require_active: bool = True,
        auto_focus: bool = False,
    ) -> None:
        """
        Restrict this macro to a specific application window (OBS-style window targeting).

        target_window: substring to match against a window's title (e.g. "Notepad").
            Empty string means "no restriction - click regardless of focus".
        require_active: if True, clicking pauses whenever the target window
            is not the current foreground window, and resumes automatically
            once it is.
        auto_focus: if True, the target window is brought to the front
            before each cycle instead of waiting for the user to switch to it.
        """
        self._target_window = target_window.strip()
        self._require_window_active = require_active
        self._auto_focus_window = auto_focus

    def start(self) -> bool:
        """Start auto-clicking in a background thread."""
        if self._running:
            return False

        enabled = get_enabled_zones(self._zones)
        if not enabled:
            self._on_status("No enabled zones to click.")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop auto-clicking."""
        self._running = False

    def _run_loop(self) -> None:
        """Main click loop executed in background thread."""
        cycle_count = 0

        while self._running:
            if self._repeat_cycles > 0 and cycle_count >= self._repeat_cycles:
                break

            self._wait_for_target_window()
            if not self._running:
                break

            enabled_zones = get_enabled_zones(self._zones)
            if not enabled_zones:
                self._on_status("No enabled zones.")
                break

            cycle_count += 1
            self._on_status(f"Cycle {cycle_count}: clicking {len(enabled_zones)} zone(s)...")
            self._click_all_zones(enabled_zones)
            self._on_cycle_done(cycle_count)

            if not self._running:
                break

            if self._repeat_cycles == 0 or cycle_count < self._repeat_cycles:
                self._on_status(f"Waiting {self._cycle_delay}s before next cycle...")
                time.sleep(self._cycle_delay)

        self._running = False
        self._on_status("Stopped.")

    def _wait_for_target_window(self) -> None:
        """Block (while still running) until the target window is active, if one is set."""
        if not self._target_window:
            return

        if self._auto_focus_window:
            window_utils.focus_window(self._target_window)
            time.sleep(0.15)

        if not self._require_window_active:
            return

        notified = False
        while self._running and not window_utils.is_window_active(self._target_window):
            if not notified:
                self._on_status(f"Waiting for window '{self._target_window}' to be active...")
                notified = True
            time.sleep(0.5)

    def _click_all_zones(self, zones: List[Zone]) -> None:
        """Act on each zone: click (CLICKS_PER_ZONE times) or scroll, per its action type."""
        for zone in zones:
            if not self._running:
                break

            if zone.action == ACTION_HOTKEY:
                if _perform_hotkey(zone.key_sequence):
                    self._on_status(f"Pressed hotkey '{zone.key_sequence}' for '{zone.name}'")
                else:
                    self._on_status(f"No hotkey set for '{zone.name}'")
            elif zone.action == ACTION_TYPE_TEXT:
                if _type_text(zone.text_to_type):
                    self._on_status(f"Typed text for '{zone.name}'")
                else:
                    self._on_status(f"No text set for '{zone.name}'")
            else:
                position = detect_zone_position(zone)
                if position is None:
                    self._on_status(f"Could not detect zone: {zone.name}")
                    continue

                x, y = position

                if zone.action == ACTION_SCROLL:
                    if zone.scroll_to_extent:
                        self._on_status(f"Scrolling '{zone.name}' until it stops moving...")
                        steps = _perform_scroll_to_extent(
                            x, y, zone.scroll_amount,
                            is_running=lambda: self._running,
                            on_status=self._on_status,
                        )
                        self._on_status(f"'{zone.name}' reached the end after {steps} scroll step(s).")
                    else:
                        _perform_scroll(x, y, zone.scroll_amount)
                        direction = "up" if zone.scroll_amount >= 0 else "down"
                        self._on_status(
                            f"Scrolled {direction} x{abs(zone.scroll_amount)} at '{zone.name}' ({x}, {y})"
                        )
                else:
                    for _ in range(CLICKS_PER_ZONE):
                        if not self._running:
                            break
                        pyautogui.click(x, y)
                        self._on_status(f"Clicked '{zone.name}' at ({x}, {y})")

            delay = zone.delay_after if zone.delay_after is not None else self._click_delay
            time.sleep(delay)


def click_zone_once(zone: Zone) -> bool:
    """Perform a zone's action (click, scroll, hotkey, or type) once. Returns True on success."""
    if zone.action == ACTION_HOTKEY:
        return _perform_hotkey(zone.key_sequence)

    if zone.action == ACTION_TYPE_TEXT:
        return _type_text(zone.text_to_type)

    position = detect_zone_position(zone)
    if position is None:
        return False

    x, y = position
    if zone.action == ACTION_SCROLL:
        if zone.scroll_to_extent:
            _perform_scroll_to_extent(x, y, zone.scroll_amount)
        else:
            _perform_scroll(x, y, zone.scroll_amount)
    else:
        pyautogui.click(x, y)
    return True

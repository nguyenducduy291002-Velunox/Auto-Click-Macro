"""Hotkey listener for start/stop and quick actions."""

import threading
from typing import Callable, FrozenSet, Optional

from pynput import keyboard


class HotkeyManager:
    """Register global hotkeys using pynput."""

    def __init__(self) -> None:
        self._listener: Optional[keyboard.Listener] = None
        self._callbacks: dict[FrozenSet[str], Callable[[], None]] = {}
        self._pressed: set[str] = set()
        self._active_combos: set[FrozenSet[str]] = set()
        self._lock = threading.Lock()

    def clear(self) -> None:
        """Remove all registered hotkeys."""
        with self._lock:
            self._callbacks.clear()
            self._active_combos.clear()

    def register(self, key_name: str, callback: Callable[[], None]) -> None:
        """Register a callback for a key name like 'f6' or combo like 'ctrl+f6'."""
        combo = self._parse_combo(key_name)
        if not combo:
            return
        with self._lock:
            self._callbacks[frozenset(combo)] = callback

    def start(self) -> None:
        """Start listening for hotkeys."""
        if self._listener is not None:
            return

        def on_press(key) -> None:
            key_str = self._key_to_string(key)
            if not key_str:
                return

            callbacks_to_run = []
            with self._lock:
                self._pressed.add(key_str)
                for combo, callback in self._callbacks.items():
                    if combo.issubset(self._pressed) and combo not in self._active_combos:
                        self._active_combos.add(combo)
                        callbacks_to_run.append(callback)

            for callback in callbacks_to_run:
                callback()

        def on_release(key) -> None:
            key_str = self._key_to_string(key)
            if not key_str:
                return

            with self._lock:
                self._pressed.discard(key_str)
                self._active_combos = {
                    combo for combo in self._active_combos if combo.issubset(self._pressed)
                }

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()

    def stop(self) -> None:
        """Stop the hotkey listener."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    @staticmethod
    def _parse_combo(key_name: str) -> set[str]:
        """Convert user text into normalized key names."""
        aliases = {
            "control": "ctrl",
            "ctl": "ctrl",
            "ctrl_l": "ctrl",
            "ctrl_r": "ctrl",
            "shift_l": "shift",
            "shift_r": "shift",
            "alt_l": "alt",
            "alt_r": "alt",
            "cmd": "win",
            "command": "win",
            "windows": "win",
            "escape": "esc",
            "return": "enter",
            "del": "delete",
        }
        normalized = key_name.strip().lower().replace("+", " ").replace(",", " ")
        return {aliases.get(part, part) for part in normalized.split() if part}

    @classmethod
    def _key_to_string(cls, key) -> Optional[str]:
        """Convert a pynput key to a lowercase string."""
        try:
            if hasattr(key, "name") and key.name:
                name = key.name.lower()
                return next(iter(cls._parse_combo(name)), name)
            if hasattr(key, "char") and key.char:
                return key.char.lower()
        except Exception:
            pass
        return None

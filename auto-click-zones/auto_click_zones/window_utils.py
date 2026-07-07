"""Detect open application windows and target one for the macro to run against.

Mirrors the idea behind OBS's "Window Capture" source: list the windows
currently open on the system, let the user pick one, and later check
whether that window is the one currently in focus (or bring it to the
front) before the macro clicks anything.

Windows-only backend (pywin32 + psutil). On other platforms the functions
degrade gracefully: listing returns an empty list and active-window checks
never block clicking.
"""

import sys
from dataclasses import dataclass
from typing import List, Optional

_IS_WINDOWS = sys.platform.startswith("win")

if _IS_WINDOWS:
    try:
        import win32gui
        import win32process
        import psutil

        _BACKEND_AVAILABLE = True
    except ImportError:
        _BACKEND_AVAILABLE = False
else:
    _BACKEND_AVAILABLE = False


@dataclass
class WindowInfo:
    """Represents a top-level application window."""

    hwnd: int
    title: str
    process_name: str

    def display_text(self) -> str:
        """Human-readable label for dropdowns, e.g. 'Notepad — notepad.exe'."""
        return f"{self.title}  —  {self.process_name}"


def is_supported() -> bool:
    """Return True if window detection is available on this platform."""
    return _BACKEND_AVAILABLE


def list_windows() -> List[WindowInfo]:
    """Return visible top-level windows that have a non-empty title."""
    if not _BACKEND_AVAILABLE:
        return []

    windows: List[WindowInfo] = []

    def _enum_handler(hwnd, _result) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title.strip():
            return
        windows.append(
            WindowInfo(hwnd=hwnd, title=title, process_name=_process_name_for_hwnd(hwnd))
        )

    win32gui.EnumWindows(_enum_handler, None)
    return windows


def _process_name_for_hwnd(hwnd: int) -> str:
    """Look up the process (exe) name that owns a window handle."""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name()
    except Exception:
        return "unknown"


def get_foreground_window() -> Optional[WindowInfo]:
    """Return info about the currently focused (foreground) window."""
    if not _BACKEND_AVAILABLE:
        return None

    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None

    return WindowInfo(
        hwnd=hwnd,
        title=win32gui.GetWindowText(hwnd),
        process_name=_process_name_for_hwnd(hwnd),
    )


def find_window(title_substring: str) -> Optional[WindowInfo]:
    """Find the first visible window whose title contains the substring (case-insensitive)."""
    if not title_substring:
        return None

    needle = title_substring.lower()
    for window in list_windows():
        if needle in window.title.lower():
            return window
    return None


def is_window_active(title_substring: str) -> bool:
    """
    Check whether the window matching title_substring is the current foreground window.

    Returns True (no restriction) if title_substring is empty, or if window
    detection isn't available on this platform - we never want an
    unsupported platform to silently block clicking forever.
    """
    if not title_substring:
        return True

    if not _BACKEND_AVAILABLE:
        return True

    foreground = get_foreground_window()
    if foreground is None:
        return False
    return title_substring.lower() in foreground.title.lower()


def focus_window(title_substring: str) -> bool:
    """Bring the window matching title_substring to the foreground. Returns True on success."""
    if not _BACKEND_AVAILABLE or not title_substring:
        return False

    window = find_window(title_substring)
    if window is None:
        return False

    try:
        if win32gui.IsIconic(window.hwnd):
            win32gui.ShowWindow(window.hwnd, 9)  # SW_RESTORE
        win32gui.SetForegroundWindow(window.hwnd)
        return True
    except Exception:
        return False

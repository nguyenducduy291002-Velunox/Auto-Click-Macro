"""Screen position picker - click anywhere to capture coordinates."""

import tkinter as tk
from typing import Callable, Optional


class PositionPicker:
    """Fullscreen transparent overlay to pick a screen position."""

    def __init__(
        self,
        on_picked: Callable[[int, int], None],
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_picked = on_picked
        self._on_cancel = on_cancel
        self._root: Optional[tk.Toplevel] = None

    def open(self, parent: tk.Tk) -> None:
        """Show the picker overlay."""
        if self._root is not None:
            return

        self._root = tk.Toplevel(parent)
        self._root.attributes("-fullscreen", True)
        self._root.attributes("-alpha", 0.25)
        self._root.configure(bg="black")
        self._root.attributes("-topmost", True)
        self._root.config(cursor="crosshair")

        label = tk.Label(
            self._root,
            text="Click anywhere to set zone position  |  ESC to cancel",
            font=("Segoe UI", 16, "bold"),
            fg="white",
            bg="black",
        )
        label.pack(pady=40)

        self._root.bind("<Button-1>", self._handle_click)
        self._root.bind("<Escape>", self._handle_cancel)
        self._root.protocol("WM_DELETE_WINDOW", self._handle_cancel)

    def _handle_click(self, event: tk.Event) -> None:
        """Record click position in screen coordinates."""
        x = self._root.winfo_pointerx()
        y = self._root.winfo_pointery()
        self._close()
        self._on_picked(x, y)

    def _handle_cancel(self, _event=None) -> None:
        """Cancel picking."""
        self._close()
        if self._on_cancel:
            self._on_cancel()

    def _close(self) -> None:
        if self._root is not None:
            self._root.destroy()
            self._root = None


class RegionPicker:
    """Pick a screen region by click-and-drag for template capture."""

    def __init__(
        self,
        on_picked: Callable[[int, int, int, int], None],
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_picked = on_picked
        self._on_cancel = on_cancel
        self._root: Optional[tk.Toplevel] = None
        self._start_x = 0
        self._start_y = 0
        self._rect_id: Optional[int] = None
        self._canvas: Optional[tk.Canvas] = None

    def open(self, parent: tk.Tk) -> None:
        """Show region selection overlay."""
        if self._root is not None:
            return

        self._root = tk.Toplevel(parent)
        self._root.attributes("-fullscreen", True)
        self._root.attributes("-alpha", 0.3)
        self._root.configure(bg="grey")
        self._root.attributes("-topmost", True)
        self._root.config(cursor="crosshair")

        label = tk.Label(
            self._root,
            text="Drag to select zone region  |  ESC to cancel",
            font=("Segoe UI", 16, "bold"),
            fg="white",
            bg="grey",
        )
        label.place(relx=0.5, y=30, anchor="n")

        self._canvas = tk.Canvas(self._root, highlightthickness=0, bg="grey")
        self._canvas.pack(fill=tk.BOTH, expand=True)

        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._root.bind("<Escape>", self._handle_cancel)

    def _on_press(self, event: tk.Event) -> None:
        self._start_x = self._root.winfo_pointerx()
        self._start_y = self._root.winfo_pointery()
        if self._rect_id is not None:
            self._canvas.delete(self._rect_id)
        self._rect_id = self._canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="red", width=2,
        )

    def _on_drag(self, event: tk.Event) -> None:
        if self._rect_id is not None:
            start_canvas_x = self._canvas.winfo_pointerx() - self._root.winfo_rootx()
            start_canvas_y = self._canvas.winfo_pointery() - self._root.winfo_rooty()
            self._canvas.coords(
                self._rect_id,
                start_canvas_x - (self._root.winfo_pointerx() - self._start_x),
                start_canvas_y - (self._root.winfo_pointery() - self._start_y),
                event.x, event.y,
            )

    def _on_release(self, _event: tk.Event) -> None:
        end_x = self._root.winfo_pointerx()
        end_y = self._root.winfo_pointery()

        x = min(self._start_x, end_x)
        y = min(self._start_y, end_y)
        width = abs(end_x - self._start_x)
        height = abs(end_y - self._start_y)

        self._close()

        if width >= 5 and height >= 5:
            self._on_picked(x, y, width, height)

    def _handle_cancel(self, _event=None) -> None:
        self._close()
        if self._on_cancel:
            self._on_cancel()

    def _close(self) -> None:
        if self._root is not None:
            self._root.destroy()
            self._root = None

"""Main GUI application window."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import List, Optional

from auto_click_zones import window_utils
from auto_click_zones.clicker import AutoClicker, click_zone_once
from auto_click_zones.config import (
    DEFAULT_CLICK_DELAY,
    DEFAULT_CYCLE_DELAY,
    HOTKEY_ADD_ZONE,
    HOTKEY_START,
    HOTKEY_STOP,
    TEMPLATES_DIR,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from auto_click_zones.hotkey_manager import HotkeyManager
from auto_click_zones.models.zone import (
    ACTION_CLICK,
    ACTION_HOTKEY,
    ACTION_SCROLL,
    ACTION_TYPE_TEXT,
    Zone,
)
from auto_click_zones.position_picker import PositionPicker, RegionPicker
from auto_click_zones.settings_manager import AppSettings, load_settings, save_settings
from auto_click_zones.zone_detector import (
    capture_template_region,
    get_mouse_position,
    validate_zone_detectable,
)
from auto_click_zones.zone_manager import (
    add_zone,
    load_zones,
    move_zone,
    remove_zone,
    save_zones,
    set_zone_action,
    set_zone_delay,
    set_zone_note,
    toggle_zone_enabled,
)


class MainWindow:
    """Primary application window for managing and running auto-clicks."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(600, 480)

        self.zones: List[Zone] = load_zones()
        self._selected_zone_id: Optional[str] = None
        self._listbox_line_zone_index: List[int] = []
        self.settings: AppSettings = load_settings()
        self._start_suspended: bool = False

        self.clicker = AutoClicker(
            on_status=self._set_status,
            on_cycle_done=self._on_cycle_done,
        )
        self.clicker.set_zones(self.zones)

        self.hotkeys = HotkeyManager()
        self.position_picker = PositionPicker(
            on_picked=self._on_position_picked,
            on_cancel=self._restore_window,
        )
        self.region_picker = RegionPicker(
            on_picked=self._on_region_picked,
            on_cancel=self._restore_window,
        )

        self._build_ui()
        self._setup_hotkeys()
        self._refresh_zone_list()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        """Build all UI widgets."""
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # --- Zone list ---
        list_frame = ttk.LabelFrame(main, text="Click Zones (each clicked 1 time per cycle)", padding=8)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.zone_listbox = tk.Listbox(list_frame, font=("Consolas", 10), selectmode=tk.SINGLE)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.zone_listbox.yview)
        self.zone_listbox.configure(yscrollcommand=scrollbar.set)
        self.zone_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.zone_listbox.bind("<<ListboxSelect>>", self._on_list_select)

        # --- Add zone buttons ---
        add_frame = ttk.LabelFrame(main, text="Add Zone", padding=8)
        add_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(add_frame, text="Pick Position on Screen", command=self._pick_position).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(add_frame, text="Use Current Mouse Position", command=self._add_current_mouse).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(add_frame, text="Detect by Image Region", command=self._pick_image_region).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(add_frame, text="Add Manual (X, Y)", command=self._add_manual).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(add_frame, text="Add Hotkey", command=self._add_hotkey_step).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(add_frame, text="Add Text/Number", command=self._add_type_text_step).pack(
            side=tk.LEFT, padx=4
        )

        # --- Target application (OBS-style window targeting) ---
        target_frame = ttk.LabelFrame(main, text="Target Application (which window this macro clicks into)", padding=8)
        target_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(target_frame, text="Window:").grid(row=0, column=0, sticky="w")
        self.target_window_var = tk.StringVar(value=self.settings.target_window)
        self.target_window_combo = ttk.Combobox(
            target_frame, textvariable=self.target_window_var, width=42,
        )
        self.target_window_combo.grid(row=0, column=1, padx=8, sticky="we")

        ttk.Button(target_frame, text="Refresh List", command=self._refresh_window_list).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(target_frame, text="Use Active Window", command=self._use_active_window).grid(
            row=0, column=3, padx=4
        )

        self.require_active_var = tk.BooleanVar(value=self.settings.require_window_active)
        ttk.Checkbutton(
            target_frame,
            text="Only click while this window is active (pause otherwise)",
            variable=self.require_active_var,
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

        self.auto_focus_var = tk.BooleanVar(value=self.settings.auto_focus_window)
        ttk.Checkbutton(
            target_frame,
            text="Automatically bring this window to the front before each cycle",
            variable=self.auto_focus_var,
        ).grid(row=2, column=0, columnspan=4, sticky="w")

        target_frame.columnconfigure(1, weight=1)

        if not window_utils.is_supported():
            ttk.Label(
                target_frame,
                text="Window detection is only available on Windows. Leave 'Window' blank to click regardless of focus.",
                foreground="#a06000",
            ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))

        self._refresh_window_list()

        # --- Zone actions ---
        action_frame = ttk.Frame(main)
        action_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(action_frame, text="Remove Selected", command=self._remove_selected).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(action_frame, text="Move Up", command=lambda: self._move_selected(-1)).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(action_frame, text="Move Down", command=lambda: self._move_selected(1)).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(action_frame, text="Toggle Enable", command=self._toggle_selected).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(action_frame, text="Test Selected", command=self._test_click).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(action_frame, text="Validate Detection", command=self._validate_selected).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(action_frame, text="Save Zones", command=self._save).pack(
            side=tk.LEFT, padx=4
        )

        # --- Per-zone delay (delay after THIS zone before clicking the next one) ---
        zone_delay_frame = ttk.Frame(main)
        zone_delay_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(zone_delay_frame, text="Delay after selected zone (sec, blank = use default):").pack(
            side=tk.LEFT
        )
        self.zone_delay_var = tk.StringVar(value="")
        ttk.Entry(zone_delay_frame, textvariable=self.zone_delay_var, width=8).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(zone_delay_frame, text="Set Delay", command=self._set_selected_zone_delay).pack(
            side=tk.LEFT, padx=4
        )

        # --- Zone action (Click vs Scroll) ---
        zone_action_frame = ttk.Frame(main)
        zone_action_frame.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(zone_action_frame, text="Action for selected zone:").pack(side=tk.LEFT)
        self.zone_action_var = tk.StringVar(value="Click")
        ttk.Combobox(
            zone_action_frame,
            textvariable=self.zone_action_var,
            values=["Click", "Scroll Up", "Scroll Down", "Hotkey", "Type Text / Number"],
            width=18,
            state="readonly",
        ).pack(side=tk.LEFT, padx=8)

        ttk.Label(zone_action_frame, text="Scroll amount (wheel notches):").pack(side=tk.LEFT, padx=(12, 0))
        self.scroll_amount_var = tk.IntVar(value=5)
        ttk.Spinbox(
            zone_action_frame, from_=1, to=100, increment=1,
            textvariable=self.scroll_amount_var, width=6,
        ).pack(side=tk.LEFT, padx=8)

        self.scroll_to_extent_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            zone_action_frame,
            text="Scroll until it stops (reaches top/bottom in one go)",
            variable=self.scroll_to_extent_var,
        ).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Button(zone_action_frame, text="Set Action", command=self._set_selected_zone_action).pack(
            side=tk.LEFT, padx=4
        )

        keyboard_action_frame = ttk.Frame(main)
        keyboard_action_frame.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(keyboard_action_frame, text="Hotkey combo:").pack(side=tk.LEFT)
        self.key_sequence_var = tk.StringVar(value="")
        ttk.Entry(keyboard_action_frame, textvariable=self.key_sequence_var, width=18).pack(
            side=tk.LEFT, padx=8
        )

        ttk.Label(keyboard_action_frame, text="Text/number to type:").pack(side=tk.LEFT, padx=(12, 0))
        self.text_to_type_var = tk.StringVar(value="")
        ttk.Entry(keyboard_action_frame, textvariable=self.text_to_type_var, width=28).pack(
            side=tk.LEFT, padx=8
        )

        zone_action_tip_frame = ttk.Frame(main)
        zone_action_tip_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            zone_action_tip_frame,
            text=(
                "Tip: hotkeys accept Ctrl C, ctrl+c, ctrl+shift+v, enter, tab, esc. "
                "Text/number actions type exactly what is in the field."
            ),
            foreground="#666666",
        ).pack(side=tk.LEFT)

        # --- Note (reference only - never read by the click engine) ---
        zone_note_frame = ttk.Frame(main)
        zone_note_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(zone_note_frame, text="Note for selected zone (for your reference only):").pack(
            side=tk.LEFT
        )
        self.zone_note_var = tk.StringVar(value="")
        ttk.Entry(zone_note_frame, textvariable=self.zone_note_var, width=40).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(zone_note_frame, text="Set Note", command=self._set_selected_zone_note).pack(
            side=tk.LEFT, padx=4
        )

        # --- Settings ---
        settings_frame = ttk.LabelFrame(main, text="Settings", padding=8)
        settings_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(settings_frame, text="Default delay between zones (sec):").grid(row=0, column=0, sticky="w")
        self.click_delay_var = tk.DoubleVar(value=DEFAULT_CLICK_DELAY)
        ttk.Spinbox(
            settings_frame, from_=0.0, to=10.0, increment=0.1,
            textvariable=self.click_delay_var, width=8,
        ).grid(row=0, column=1, padx=8, sticky="w")

        ttk.Label(settings_frame, text="Delay between cycles (sec):").grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.cycle_delay_var = tk.DoubleVar(value=DEFAULT_CYCLE_DELAY)
        ttk.Spinbox(
            settings_frame, from_=0.0, to=60.0, increment=0.5,
            textvariable=self.cycle_delay_var, width=8,
        ).grid(row=0, column=3, padx=8, sticky="w")

        ttk.Label(
            settings_frame,
            text="(used only for zones that don't have their own delay set below)",
            foreground="#666666",
        ).grid(row=1, column=2, columnspan=2, sticky="w", padx=(16, 0))

        ttk.Label(settings_frame, text="Repeat cycles (0 = until stopped):").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.repeat_var = tk.IntVar(value=1)
        ttk.Spinbox(
            settings_frame, from_=0, to=9999, increment=1,
            textvariable=self.repeat_var, width=8,
        ).grid(row=2, column=1, padx=8, sticky="w", pady=(8, 0))

        ttk.Label(settings_frame, text="Start hotkey:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.start_hotkey_var = tk.StringVar(value=self.settings.start_hotkey)
        ttk.Entry(settings_frame, textvariable=self.start_hotkey_var, width=12).grid(
            row=3, column=1, padx=8, sticky="w", pady=(8, 0)
        )

        ttk.Label(settings_frame, text="Stop hotkey:").grid(row=3, column=2, sticky="w", padx=(16, 0), pady=(8, 0))
        self.stop_hotkey_var = tk.StringVar(value=self.settings.stop_hotkey)
        ttk.Entry(settings_frame, textvariable=self.stop_hotkey_var, width=12).grid(
            row=3, column=3, padx=8, sticky="w", pady=(8, 0)
        )

        ttk.Button(settings_frame, text="Apply Hotkeys", command=self._apply_hotkeys).grid(
            row=3, column=4, padx=8, sticky="w", pady=(8, 0)
        )

        ttk.Label(
            settings_frame,
            text="Examples: f6, f9, ctrl+f6, alt+s",
            foreground="#666666",
        ).grid(row=4, column=0, columnspan=5, sticky="w", pady=(4, 0))

        # --- Start / Stop ---
        control_frame = ttk.Frame(main)
        control_frame.pack(fill=tk.X, pady=(0, 8))

        self.start_btn = ttk.Button(control_frame, text="Start", command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=4)

        self.stop_btn = ttk.Button(
            control_frame, text="Stop", command=self._stop, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=4)

        self.suspend_start_btn = ttk.Button(
            control_frame, text="Suspend Start", command=self._toggle_suspend_start
        )
        self.suspend_start_btn.pack(side=tk.LEFT, padx=(16, 4))

        self.suspend_status_var = tk.StringVar(value="")
        ttk.Label(control_frame, textvariable=self.suspend_status_var, foreground="#a02020").pack(
            side=tk.LEFT, padx=8
        )

        self.hotkey_status_var = tk.StringVar(value="")
        ttk.Label(control_frame, textvariable=self.hotkey_status_var).pack(side=tk.LEFT, padx=16)
        self._refresh_hotkey_labels()
        self._update_start_button_state()

        # --- Status bar ---
        self.status_var = tk.StringVar(value="Ready. Add zones and press Start.")
        status_bar = ttk.Label(main, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status_bar.pack(fill=tk.X)

    def _setup_hotkeys(self) -> None:
        """Register global hotkeys."""
        self.hotkeys.clear()
        self.hotkeys.register(self.start_hotkey_var.get(), lambda: self.root.after(0, self._start))
        self.hotkeys.register(self.stop_hotkey_var.get(), lambda: self.root.after(0, self._stop))
        self.hotkeys.register(HOTKEY_ADD_ZONE, lambda: self.root.after(0, self._add_current_mouse))
        self.hotkeys.start()
        self._refresh_hotkey_labels()

    @staticmethod
    def _format_hotkey(value: str) -> str:
        """Return a compact label for hotkey display."""
        return value.strip().upper() if value.strip() else "(none)"

    def _refresh_hotkey_labels(self) -> None:
        """Update button and status labels to match the configured hotkeys."""
        start = self._format_hotkey(self.start_hotkey_var.get())
        stop = self._format_hotkey(self.stop_hotkey_var.get())
        self.start_btn.config(text=f"Start ({start})")
        self.stop_btn.config(text=f"Stop ({stop})")
        self.hotkey_status_var.set(
            f"Hotkeys: {start}=Start | {stop}=Stop | {HOTKEY_ADD_ZONE.upper()}=Add mouse pos"
        )

    def _apply_hotkeys(self) -> None:
        """Apply and persist user-configured Start/Stop hotkeys."""
        start = self.start_hotkey_var.get().strip()
        stop = self.stop_hotkey_var.get().strip()
        if not start or not stop:
            messagebox.showerror("Error", "Start and Stop hotkeys cannot be blank.")
            return
        if start.lower() == stop.lower():
            messagebox.showerror("Error", "Start and Stop hotkeys must be different.")
            return

        self.start_hotkey_var.set(start)
        self.stop_hotkey_var.set(stop)
        self._setup_hotkeys()
        self._save_app_settings()
        self._set_status(f"Hotkeys updated: Start={start}, Stop={stop}")

    def _refresh_zone_list(self) -> None:
        """
        Refresh the listbox from self.zones, preserving the current selection.

        Each zone gets its own line; if it has a note, an extra note-only
        line is inserted right after it (visually "between" that zone and
        the next one). Note lines aren't separate zones - clicking one just
        selects the zone above it - so we keep a per-line -> zone-index map.
        """
        self.zone_listbox.delete(0, tk.END)
        self._listbox_line_zone_index: List[int] = []

        selected_line = None
        for zone_index, zone in enumerate(self.zones):
            self.zone_listbox.insert(tk.END, zone.display_text())
            self._listbox_line_zone_index.append(zone_index)
            if zone.id == self._selected_zone_id:
                selected_line = len(self._listbox_line_zone_index) - 1

            if zone.note:
                line_index = self.zone_listbox.size()
                self.zone_listbox.insert(tk.END, f"      \u21b3 note: {zone.note}")
                self.zone_listbox.itemconfig(line_index, foreground="#666666")
                self._listbox_line_zone_index.append(zone_index)

        if selected_line is not None:
            self.zone_listbox.selection_set(selected_line)
            self.zone_listbox.see(selected_line)

    def _on_list_select(self, _event=None) -> None:
        selection = self.zone_listbox.curselection()
        if selection:
            line_index = selection[0]
            if 0 <= line_index < len(self._listbox_line_zone_index):
                zone_index = self._listbox_line_zone_index[line_index]
                if 0 <= zone_index < len(self.zones):
                    zone = self.zones[zone_index]
                    self._selected_zone_id = zone.id
                    self.zone_delay_var.set(
                        "" if zone.delay_after is None else str(zone.delay_after)
                    )
                    if zone.action == ACTION_SCROLL:
                        self.zone_action_var.set("Scroll Up" if zone.scroll_amount >= 0 else "Scroll Down")
                        self.scroll_amount_var.set(max(1, abs(zone.scroll_amount)))
                        self.scroll_to_extent_var.set(zone.scroll_to_extent)
                    elif zone.action == ACTION_HOTKEY:
                        self.zone_action_var.set("Hotkey")
                        self.scroll_to_extent_var.set(False)
                    elif zone.action == ACTION_TYPE_TEXT:
                        self.zone_action_var.set("Type Text / Number")
                        self.scroll_to_extent_var.set(False)
                    else:
                        self.zone_action_var.set("Click")
                        self.scroll_to_extent_var.set(False)
                    self.key_sequence_var.set(zone.key_sequence)
                    self.text_to_type_var.set(zone.text_to_type)
                    self.zone_note_var.set(zone.note)

    def _get_selected_zone(self) -> Optional[Zone]:
        if self._selected_zone_id is None:
            return None
        for zone in self.zones:
            if zone.id == self._selected_zone_id:
                return zone
        return None

    def _ask_zone_name(self, default: str = "Zone") -> Optional[str]:
        name = simpledialog.askstring("Zone Name", "Enter a name for this zone:", initialvalue=default)
        if name is None or not name.strip():
            return None
        return name.strip()

    def _pick_position(self) -> None:
        self.root.withdraw()
        self.root.after(300, lambda: self.position_picker.open(self.root))

    def _on_position_picked(self, x: int, y: int) -> None:
        self.root.deiconify()
        name = self._ask_zone_name(f"Zone ({x}, {y})")
        if name is None:
            return
        zone = add_zone(self.zones, name=name, x=x, y=y, after_zone_id=self._selected_zone_id)
        self.clicker.set_zones(self.zones)
        self._selected_zone_id = zone.id
        self._refresh_zone_list()
        self._set_status(f"Added zone '{name}' at ({x}, {y})")

    def _restore_window(self) -> None:
        """Bring main window back after screen picker closes."""
        self.root.deiconify()

    def _add_current_mouse(self) -> None:
        x, y = get_mouse_position()
        name = self._ask_zone_name(f"Zone ({x}, {y})")
        if name is None:
            return
        zone = add_zone(self.zones, name=name, x=x, y=y, after_zone_id=self._selected_zone_id)
        self.clicker.set_zones(self.zones)
        self._selected_zone_id = zone.id
        self._refresh_zone_list()
        self._set_status(f"Added zone '{name}' at ({x}, {y})")

    def _pick_image_region(self) -> None:
        self.root.withdraw()
        self.root.after(300, lambda: self.region_picker.open(self.root))

    def _on_region_picked(self, x: int, y: int, width: int, height: int) -> None:
        self._restore_window()
        name = self._ask_zone_name(f"Image Zone ({x}, {y})")
        if name is None:
            return

        template_path = TEMPLATES_DIR / f"{name.replace(' ', '_')}.png"
        if not capture_template_region(x, y, width, height, template_path):
            messagebox.showerror("Error", "Failed to capture template image.")
            return

        zone = add_zone(
            self.zones,
            name=name,
            x=x + width // 2,
            y=y + height // 2,
            use_image_detection=True,
            template_path=str(template_path),
            after_zone_id=self._selected_zone_id,
        )
        self.clicker.set_zones(self.zones)
        self._selected_zone_id = zone.id
        self._refresh_zone_list()
        self._set_status(f"Added image zone '{name}' with template {template_path.name}")

    def _add_manual(self) -> None:
        coords = simpledialog.askstring("Manual Coordinates", "Enter X,Y (e.g. 500,300):")
        if not coords:
            return
        try:
            parts = coords.replace(" ", "").split(",")
            x, y = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Invalid format. Use: 500,300")
            return

        name = self._ask_zone_name(f"Zone ({x}, {y})")
        if name is None:
            return
        zone = add_zone(self.zones, name=name, x=x, y=y, after_zone_id=self._selected_zone_id)
        self.clicker.set_zones(self.zones)
        self._selected_zone_id = zone.id
        self._refresh_zone_list()

    def _add_hotkey_step(self) -> None:
        sequence = simpledialog.askstring("Hotkey", "Enter hotkey combo (e.g. ctrl+c or ctrl+v):")
        if sequence is None or not sequence.strip():
            return
        name = self._ask_zone_name(f"Hotkey {sequence.strip()}")
        if name is None:
            return
        zone = add_zone(self.zones, name=name, x=0, y=0, after_zone_id=self._selected_zone_id)
        set_zone_action(self.zones, zone.id, ACTION_HOTKEY, key_sequence=sequence.strip())
        self.clicker.set_zones(self.zones)
        self._selected_zone_id = zone.id
        self._refresh_zone_list()
        self._set_status(f"Added hotkey step '{name}'")

    def _add_type_text_step(self) -> None:
        text = simpledialog.askstring("Type Text / Number", "Enter the text or number to type:")
        if text is None:
            return
        name = self._ask_zone_name(f"Type {text}")
        if name is None:
            return
        zone = add_zone(self.zones, name=name, x=0, y=0, after_zone_id=self._selected_zone_id)
        set_zone_action(self.zones, zone.id, ACTION_TYPE_TEXT, text_to_type=text)
        self.clicker.set_zones(self.zones)
        self._selected_zone_id = zone.id
        self._refresh_zone_list()
        self._set_status(f"Added typing step '{name}'")

    def _remove_selected(self) -> None:
        zone = self._get_selected_zone()
        if zone is None:
            messagebox.showinfo("Info", "Select a zone first.")
            return
        index = next((i for i, z in enumerate(self.zones) if z.id == zone.id), None)
        remove_zone(self.zones, zone.id)
        if index is not None and self.zones:
            new_index = min(index, len(self.zones) - 1)
            self._selected_zone_id = self.zones[new_index].id
        else:
            self._selected_zone_id = None
        self.clicker.set_zones(self.zones)
        self._refresh_zone_list()

    def _toggle_selected(self) -> None:
        zone = self._get_selected_zone()
        if zone is None:
            messagebox.showinfo("Info", "Select a zone first.")
            return
        toggle_zone_enabled(self.zones, zone.id)
        self.clicker.set_zones(self.zones)
        self._refresh_zone_list()

    def _move_selected(self, delta: int) -> None:
        """Move the selected zone earlier (-1) or later (+1) in the macro's execution order."""
        zone = self._get_selected_zone()
        if zone is None:
            messagebox.showinfo("Info", "Select a zone first.")
            return
        if move_zone(self.zones, zone.id, delta):
            self.clicker.set_zones(self.zones)
            self._refresh_zone_list()
            self._set_status(f"Moved '{zone.name}' {'up' if delta < 0 else 'down'}.")
        else:
            self._set_status(f"'{zone.name}' is already at that end of the list.")

    def _set_selected_zone_note(self) -> None:
        zone = self._get_selected_zone()
        if zone is None:
            messagebox.showinfo("Info", "Select a zone first.")
            return
        note = self.zone_note_var.get()
        set_zone_note(self.zones, zone.id, note)
        self._refresh_zone_list()
        self._set_status(f"Note {'set' if note else 'cleared'} for '{zone.name}'.")

    def _test_click(self) -> None:
        zone = self._get_selected_zone()
        if zone is None:
            messagebox.showinfo("Info", "Select a zone first.")
            return
        if click_zone_once(zone):
            if zone.action == ACTION_SCROLL:
                verb = "Test scrolled"
            elif zone.action == ACTION_HOTKEY:
                verb = "Test pressed hotkey"
            elif zone.action == ACTION_TYPE_TEXT:
                verb = "Test typed"
            else:
                verb = "Test clicked"
            self._set_status(f"{verb} '{zone.name}'")
        else:
            messagebox.showerror("Error", f"Could not act on zone '{zone.name}'")

    def _set_selected_zone_delay(self) -> None:
        zone = self._get_selected_zone()
        if zone is None:
            messagebox.showinfo("Info", "Select a zone first.")
            return

        text = self.zone_delay_var.get().strip()
        if text == "":
            set_zone_delay(self.zones, zone.id, None)
            self.clicker.set_zones(self.zones)
            self._refresh_zone_list()
            self._set_status(f"'{zone.name}' will use the default delay.")
            return

        try:
            delay = float(text)
            if delay < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Enter a non-negative number of seconds, or leave blank.")
            return

        set_zone_delay(self.zones, zone.id, delay)
        self.clicker.set_zones(self.zones)
        self._refresh_zone_list()
        self._set_status(f"'{zone.name}' will wait {delay}s before the next zone.")

    def _set_selected_zone_action(self) -> None:
        zone = self._get_selected_zone()
        if zone is None:
            messagebox.showinfo("Info", "Select a zone first.")
            return

        choice = self.zone_action_var.get()
        amount = self.scroll_amount_var.get()
        to_extent = self.scroll_to_extent_var.get()
        key_sequence = self.key_sequence_var.get().strip()
        text_to_type = self.text_to_type_var.get()

        if choice == "Click":
            set_zone_action(self.zones, zone.id, ACTION_CLICK, 0)
            self._set_status(f"'{zone.name}' will click.")
        elif choice == "Scroll Up":
            set_zone_action(self.zones, zone.id, ACTION_SCROLL, abs(amount), to_extent)
            suffix = "until it stops" if to_extent else f"x{abs(amount)}"
            self._set_status(f"'{zone.name}' will scroll up {suffix}.")
        elif choice == "Scroll Down":
            set_zone_action(self.zones, zone.id, ACTION_SCROLL, -abs(amount), to_extent)
            suffix = "until it stops" if to_extent else f"x{abs(amount)}"
            self._set_status(f"'{zone.name}' will scroll down {suffix}.")
        elif choice == "Hotkey":
            if not key_sequence:
                messagebox.showerror("Error", "Enter a hotkey combo such as ctrl+c or ctrl+v.")
                return
            set_zone_action(self.zones, zone.id, ACTION_HOTKEY, key_sequence=key_sequence)
            self._set_status(f"'{zone.name}' will press {key_sequence}.")
        else:  # Type Text / Number
            if text_to_type == "":
                messagebox.showerror("Error", "Enter text or a number to type.")
                return
            set_zone_action(self.zones, zone.id, ACTION_TYPE_TEXT, text_to_type=text_to_type)
            self._set_status(f"'{zone.name}' will type text.")

        self.clicker.set_zones(self.zones)
        self._refresh_zone_list()

    def _validate_selected(self) -> None:
        zone = self._get_selected_zone()
        if zone is None:
            messagebox.showinfo("Info", "Select a zone first.")
            return
        if zone.action in (ACTION_HOTKEY, ACTION_TYPE_TEXT):
            messagebox.showinfo("Validation OK", "Keyboard actions do not need screen detection.")
            return
        ok, message = validate_zone_detectable(zone)
        if ok:
            messagebox.showinfo("Validation OK", message)
        else:
            messagebox.showwarning("Validation Failed", message)

    def _refresh_window_list(self) -> None:
        """Repopulate the target-window dropdown with currently open windows."""
        windows = window_utils.list_windows()
        self._window_lookup = {w.display_text(): w.title for w in windows}
        self.target_window_combo["values"] = list(self._window_lookup.keys())

    def _use_active_window(self) -> None:
        """Fill the target-window field from whichever window currently has focus."""
        foreground = window_utils.get_foreground_window()
        if foreground is None:
            messagebox.showinfo(
                "Info",
                "Could not detect the active window (unsupported platform or none focused)."
                if not window_utils.is_supported()
                else "No active window detected.",
            )
            return
        self.target_window_var.set(foreground.title)
        self._set_status(f"Target window set to '{foreground.title}'")

    def _resolved_target_window(self) -> str:
        """Return the target window title, resolving a dropdown display label if needed."""
        value = self.target_window_var.get().strip()
        return getattr(self, "_window_lookup", {}).get(value, value)

    def _save(self) -> None:
        save_zones(self.zones)
        self._set_status("Zones saved.")

    def _start(self) -> None:
        if self._start_suspended:
            self._set_status("Start is suspended. Click 'Resume Start' to enable it again.")
            return

        self.clicker.set_zones(self.zones)
        self.clicker.set_delays(self.click_delay_var.get(), self.cycle_delay_var.get())
        self.clicker.set_repeat_cycles(self.repeat_var.get())
        self.clicker.set_target_window(
            self._resolved_target_window(),
            require_active=self.require_active_var.get(),
            auto_focus=self.auto_focus_var.get(),
        )

        if self.clicker.start():
            self.stop_btn.config(state=tk.NORMAL)
            self._update_start_button_state()
        else:
            messagebox.showwarning("Warning", "Could not start. Add at least one enabled zone.")

    def _stop(self) -> None:
        self.clicker.stop()
        self.stop_btn.config(state=tk.DISABLED)
        self._update_start_button_state()

    def _update_start_button_state(self) -> None:
        """Apply running + suspended state to the Start button (and only the Start button - Stop always works)."""
        if self.clicker.is_running or self._start_suspended:
            self.start_btn.config(state=tk.DISABLED)
        else:
            self.start_btn.config(state=tk.NORMAL)

    def _toggle_suspend_start(self) -> None:
        """Suspend or resume the Start button and Start hotkey. Stop is never affected."""
        self._start_suspended = not self._start_suspended
        if self._start_suspended:
            self.suspend_start_btn.config(text="Resume Start")
            self.suspend_status_var.set("Start is SUSPENDED (button and hotkey disabled)")
            self._set_status("Start suspended - the Start button and hotkey will not work until resumed.")
        else:
            self.suspend_start_btn.config(text="Suspend Start")
            self.suspend_status_var.set("")
            self._set_status("Start resumed.")
        self._update_start_button_state()

    def _on_cycle_done(self, count: int) -> None:
        repeat = self.repeat_var.get()
        if repeat > 0 and count >= repeat:
            self.root.after(0, self._stop)

    def _set_status(self, message: str) -> None:
        self.root.after(0, lambda: self.status_var.set(message))

    def _save_app_settings(self) -> None:
        """Persist app-level settings."""
        save_settings(
            AppSettings(
                target_window=self._resolved_target_window(),
                require_window_active=self.require_active_var.get(),
                auto_focus_window=self.auto_focus_var.get(),
                start_hotkey=self.start_hotkey_var.get().strip(),
                stop_hotkey=self.stop_hotkey_var.get().strip(),
            )
        )

    def _on_close(self) -> None:
        self.clicker.stop()
        self.hotkeys.stop()
        save_zones(self.zones)
        self._save_app_settings()
        self.root.destroy()

    def run(self) -> None:
        """Start the GUI main loop."""
        self.root.mainloop()

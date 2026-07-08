# Auto Click Zones

Detect click zones on your screen and auto-click each zone **once per cycle**.

## Features

- **Fixed position zones** — pick a point on screen or use current mouse position
- **Image detection zones** — drag a region to capture a template; the app finds it on screen before clicking
- **One click per zone per cycle** — each enabled zone is clicked exactly 1 time, then the next zone
- **Repeat cycles** — run 1 cycle (default), multiple cycles, or until you stop
- **Configurable hotkeys** — choose your own global Start and Stop hotkeys; F8 still adds the current mouse position
- **Save/load zones** — zones persist in `data/zones.json`
- **Target Application** — pick which open window this macro is for (like OBS's Window Capture). Optionally pause clicking whenever that window isn't focused, or auto-bring it to the front before each cycle. Windows-only; setting persists in `data/settings.json`
- **Per-zone delays** — set a different wait time after each individual zone (e.g. wait 1s after zone 1, then 5s after zone 2), instead of one delay applied uniformly everywhere. A zone with no delay set falls back to the global default delay
- **Scroll zones** — instead of clicking, a zone can scroll up or down by a set amount. Combine with image detection to capture a scrollbar visually, so the app finds it live each cycle and scrolls there
- **Keyboard steps** — press hotkey combos like `ctrl+c`, `ctrl+v`, `ctrl+shift+v`, `enter`, or `tab`, or type literal text/numbers as part of the same macro cycle
- **Suspend Start** — a toggle that disables the Start button *and* the Start hotkey until you resume it, so the macro can't be triggered by accident. Stop always keeps working regardless.
- **Mid-macro editing** — reorder zones with Move Up/Move Down, insert new zones anywhere (each "Add" action inserts right after whichever zone is selected, instead of always appending at the end), and attach a free-text note to any zone purely for your own reference (never read by the click engine)

## Project Structure

```
auto-click-zones/
├── main.py                      # Entry point
├── build.bat                    # Build .exe script
├── requirements.txt             # Python dependencies
├── auto_click_zones/
│   ├── config.py                # Settings and constants
│   ├── zone_manager.py          # Load/save/add/remove zones
│   ├── zone_detector.py         # Detect zones (coords or image)
│   ├── clicker.py               # Auto-click engine
│   ├── gui.py                   # Main window UI
│   ├── hotkey_manager.py        # Global hotkeys
│   ├── position_picker.py       # Screen position/region picker
│   ├── window_utils.py          # Detect/list/focus open windows (target app)
│   ├── settings_manager.py      # Load/save app-level settings (target window)
│   └── models/
│       └── zone.py              # Zone data model
└── data/
    ├── zones.json               # Saved zones
    ├── settings.json            # Target window + macro-level settings
    └── templates/               # Template images for detection
```

## Run from Python

```bash
pip install -r requirements.txt
python main.py
```

## Build .exe

```bash
build.bat
```

The executable will be at `dist/AutoClickZones.exe`.

## Usage

1. Launch the app
2. Add zones using any method (pick position, mouse position, image region, or manual X,Y)
3. Add keyboard steps if needed using **Add Hotkey** or **Add Text/Number**
4. Set delay and repeat count if needed
5. Press **Start** or your configured Start hotkey
6. Each enabled item runs once per cycle in list order
7. Press **Stop** or your configured Stop hotkey to stop (or move mouse to top-left corner for pyautogui failsafe)

## Custom Start/Stop hotkeys

In **Settings**, edit **Start hotkey** and **Stop hotkey**, then click
**Apply Hotkeys**. The app saves these choices in `data/settings.json`.

Examples: `f6`, `f9`, `ctrl+f6`, `alt+s`, `ctrl+shift+s`.

## Suspending the Start button

Click **Suspend Start** to disable the Start button and the Start hotkey until you resume it — useful if you want to prevent an accidental trigger while you're editing zones. The button relabels to **Resume Start**; click it again to restore normal behavior. **Stop** (button and hotkey) is never affected, so a running macro can always be stopped.

## Editing zones in the middle of the macro

- **Reorder**: select a zone and click **Move Up** / **Move Down** to shift it earlier or later in the execution order.
- **Insert in the middle**: select the zone you want the new one to come *after*, then use any of the Add buttons (Pick Position, Use Current Mouse Position, Detect by Image Region, Add Manual, Add Hotkey, Add Text/Number) - the new zone is inserted right after your selection instead of being appended at the end. With nothing selected, new zones are still appended at the end as before.
- **Delete**: select a zone and click **Remove Selected**, same as always.
- **Notes**: select a zone, type anything into **"Note for selected zone"**, and click **Set Note**. This is shown in the zone list for your own reference and is never read by the click engine - it has zero effect on what the macro actually does.

## Targeting a specific application

1. In the **Target Application** panel, click **Refresh List** and pick a window from the dropdown, or click **Use Active Window** to grab whatever window currently has focus, or type a partial title yourself (e.g. `Notepad` matches `Untitled - Notepad`)
2. Leave "Window" blank to click regardless of what's focused (old behavior)
3. Check **Only click while this window is active** to have the macro pause automatically whenever you tab away, and resume the moment you switch back
4. Check **Automatically bring this window to the front** to have the macro focus that window itself before each cycle instead of waiting for you

## Setting a different delay per zone

By default every zone waits the same "Default delay between zones" before the next one is clicked. To give a specific zone its own wait time instead (e.g. wait 1s after zone 1 but 5s after zone 2):

1. Select the zone in the list
2. Type the number of seconds into **"Delay after selected zone"**
3. Click **Set Delay**

Leave the field blank and click **Set Delay** to make that zone go back to using the default delay. The zone list shows each zone's custom delay (if any) next to it.

## Scrolling instead of clicking (and detecting a scrollbar)

Any zone can scroll instead of click:

1. Select the zone in the list
2. Choose **Scroll Up** or **Scroll Down** from the "Action for selected zone" dropdown, and set a scroll amount
3. Click **Set Action**

To make it scroll a specific scrollbar rather than a fixed screen point, create the zone with **Detect by Image Region** first (drag-select around the scrollbar thumb/track to capture it as a template), then set that zone's action to Scroll. Each cycle the app re-detects where the scrollbar currently is on screen and scrolls there - the same live image-matching used for click zones.

Use **Test Selected** to try a single scroll immediately without starting the full macro.

## Keyboard actions

Keyboard actions run in the same list order as click and scroll zones. They do not
need screen coordinates or image detection.

- Click **Add Hotkey** to create a step such as `ctrl+c`, `ctrl+v`, `ctrl+a`,
  `ctrl+shift+v`, `enter`, `tab`, `esc`, or `alt+tab*2`
- Click **Add Text/Number** to type literal text, such as `12345`
- To edit an existing step, select it, choose **Hotkey** or **Type Text / Number**
  under **Action for selected zone**, fill in the matching field, then click
  **Set Action**
- Hotkeys can be written with spaces, plus signs, or commas; for example
  `Ctrl C`, `ctrl+c`, and `ctrl, c` are treated the same
- To hold a modifier and press another key more than once, use repeat syntax:
  `alt+tab*2`, `alt+tab+tab`, or `alt+2 tab` all hold Alt and press Tab twice

**Note on scroll amount:** the number you set is real mouse-wheel "notches" (like turning a physical scroll wheel that many clicks) - a typical wheel notch scrolls about 3 lines, so 10-30 notches usually covers a long page. If you're updating from an older version of this app where scroll barely moved regardless of the number entered, that was a bug where the amount wasn't converted to real wheel units; it's fixed now, so re-check any large numbers you'd set as a workaround (e.g. 999) since they'll now scroll much further than before.

### Scrolling all the way to the top or bottom in one go

Rather than guessing a fixed notch count, check **"Scroll until it stops (reaches top/bottom in one go)"**. The zone will then scroll repeatedly - watching the screen after each burst - and automatically stop the moment the page stops moving (i.e. it hit the very top or bottom), all within that one zone's turn in the cycle. The "scroll amount" field becomes the step size per burst (5-10 is a good default) rather than a fixed total.

## Notes

- Image detection requires `opencv-python` (included in requirements)
- Target-application detection requires `pywin32` + `psutil` and only works on Windows; on other platforms the field is ignored and clicking is unrestricted
- Run as administrator if hotkeys do not work in some apps
- Zones are saved automatically on exit; target-window settings are saved to `data/settings.json` on exit

## Troubleshooting: "Tcl data directory ... not found" when running the .exe

This is a known PyInstaller + Tkinter bug on Windows: PyInstaller's automatic
detection of Tcl/Tk's data files sometimes fails silently, so the exe is
built without them and crashes on launch - even though `python main.py`
works fine, because that just uses your real Python install's Tcl/Tk directly.

`build.bat` (and `AutoClickZones.spec`) now explicitly detect your Python's
real Tcl/Tk data folders and force-bundle them into the exact path
(`_tcl_data` / `_tk_data`) that the exe looks for at startup, rather than
relying on PyInstaller's automatic detection. Rebuild with the updated
`build.bat` and this should be fixed.

If `build.bat` prints an error saying it can't detect `TCL_LIBRARY`, or that
the detected folder doesn't exist, your Python's own Tkinter install is
broken (common with Microsoft Store Python or minimal/embeddable installs).
Fix: install Python from [python.org](https://www.python.org/downloads/)
with the "tcl/tk and IDLE" option checked during setup, then rebuild.

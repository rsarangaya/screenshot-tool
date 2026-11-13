# PROJECT.md

## Summary
Windows snipping-tool clone. Global hotkey -> dimmed overlay -> drag a region -> the editor window opens immediately with the crop (no toast click). Editor adds a real text tool.

## Stack
- Language / framework: Python 3.13, PySide6 (Qt 6)
- Key dependencies: PySide6 (approved). Nothing else without asking; global hotkey via Win32 RegisterHotKey through ctypes.

## Commands
- Install: `python -m pip install -r requirements.txt`
- Run: `python -m snip`
- Test (all): `python -m unittest discover -s tests -q`
- Test (single): `python -m unittest discover -s tests -k test_name -q`
- Perf budget check (not in default suite): `python -m unittest discover -s tests -p "perf_*.py" -q`
- Lint / typecheck: none yet
- Build: `python -m pip install -r requirements-dev.txt` then `python -m PyInstaller --noconfirm --onefile --noconsole --name Snip --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQml --exclude-module PySide6.Qt3DCore run_snip.py` -> `dist\Snip.exe` (PyInstaller approved, build-time only)

## Architecture map
- `snip/__main__.py` -> entry: single-instance check, main window, tray (Show/New capture/Quit), hotkey, app loop; hides our windows before capture and restores after
- `snip/main_window.py` -> main window: "+ New", hotkey hint, settings (save folder, Start with Windows); close hides to tray
- `snip/settings.py` -> QSettings helpers (save folder)
- `snip/startup.py` -> HKCU Run registry value via winreg (default off)
- `snip/single_instance.py` -> QLocalServer/QLocalSocket guard; second launch raises the first window
- `snip/hotkey.py` -> global hotkey (default Ctrl+Shift+S, configurable)
- `snip/capture.py` -> grab all monitors to a QPixmap before overlay shows; DPI-aware crop
- `snip/overlay.py` -> fullscreen dim + drag-select + size readout, Esc cancels; emits the cropped pixmap
- `snip/editor.py` -> editor window (QGraphicsView/Scene): pen, highlighter, arrow, rect, text, crop, undo/redo, save, copy
- `snip/tools/` -> one module per editor tool
- `tests/` -> stdlib unittest (crop math, DPI scaling, editor undo, text edge cases, save size); `qt_support.py` holds shared offscreen setup

## Conventions
- Release of the mouse in the overlay calls the editor directly; also copy the crop to the clipboard.
- Text items are `QGraphicsTextItem`: movable, resizable, editable after placement; font, size, color, bold, background.
- Keep modules small; no global state beyond the app object.
- No new dependencies without asking.

## Performance budgets
- Hotkey to visible overlay: < 150 ms. Release to editor visible: < 300 ms.
- Idle in tray: ~0% CPU, < 100 MB RAM.
- Measure with `time.perf_counter` around the capture and show paths.

## Known gotchas
- Win+Shift+S is owned by Windows; do not try to override it.
- Mixed-DPI multi-monitor: use physical pixels for the grab and devicePixelRatio when cropping.
- Grab the screen before showing the overlay, or the dim appears in the shot.

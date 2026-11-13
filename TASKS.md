# TASKS

| id | task | agent | status | files |
|----|------|-------|--------|-------|
| 1 | Scaffold: requirements.txt, snip package, tray + hotkey | developer | done | snip/__main__.py, snip/hotkey.py |
| 2 | Capture all monitors, DPI-correct crop | developer | done | snip/capture.py |
| 3 | Overlay: dim, drag-select, Esc, auto-open editor + clipboard | developer | done | snip/overlay.py |
| 4 | Editor: view, save, copy, undo/redo, pen, highlighter, arrow, rect, crop | developer | done | snip/editor.py, snip/tools/ |
| 5 | Text tool: place, edit, move, resize, style, delete | developer | done | snip/tools/text.py |
| 6 | Tests for crop math, DPI, undo (unittest, all passing) | tester | done | tests/ |
| 7 | Review incl. performance budgets | reviewer | done (approve w/ non-blocking notes) | all |
| 9 | Context-sensitive option toolbar; pen icon cursor, highlighter I-beam | developer | done | snip/editor.py, snip/tools/{base,text,pen,highlighter,selector,crop}.py, tests/test_editor_options.py |
| 10 | Edge auto-scroll capture: stitched tall image; sticky bands, settle, tolerant matching, edge arming, width adjust, narrow-drag fix | developer/debugger | done | snip/overlay.py, snip/capture.py, snip/scroll_capture.py, tests/test_scroll_capture.py, tests/test_edge_arm.py |
| 11 | Windowed app: main window, editor + New/Save buttons, unsaved-close prompt, Start with Windows, single instance | developer | done | snip/{__main__,main_window,settings,startup,single_instance,editor,overlay}.py, tests/test_app_shell.py, tests/qt_support.py |
| 12 | Package as dist\Snip.exe with PyInstaller (run_snip.py, requirements-dev.txt) | manager | done | run_snip.py, requirements-dev.txt, PROJECT.md |

Status: todo | doing | review | done | blocked

"""Perf budget check: open_editor on a 1920x1080 crop (budget: release to editor < 300 ms).

Not part of the default suite (file name does not match test*.py). Run with:
    python -m unittest discover -s tests -p "perf_*.py" -v
"""
import statistics
import time
import unittest

from qt_support import flush, get_app, solid_pixmap

from PySide6.QtCore import QPointF  # noqa: E402

BUDGET_MS = 300.0
RUNS = 5


class OpenEditorBudgetTest(unittest.TestCase):
    def test_open_editor_1920x1080_within_budget(self):
        get_app()
        from snip import editor

        pm = solid_pixmap(1920, 1080)
        timings = []
        for _ in range(RUNS):
            t0 = time.perf_counter()
            win = editor.open_editor(pm)
            flush()
            timings.append((time.perf_counter() - t0) * 1000.0)
            win.close()
            flush()

        med = statistics.median(timings)
        print(f"\nopen_editor 1920x1080 ms: first={timings[0]:.1f} "
              f"median={med:.1f} max={max(timings):.1f} (budget {BUDGET_MS:.0f})")
        self.assertLess(med, BUDGET_MS)


if __name__ == "__main__":
    unittest.main()

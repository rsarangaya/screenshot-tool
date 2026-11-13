"""Shared Qt setup for the unittest suite: offscreen platform, one QApplication,
and small editor helpers."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtGui import QColor, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def flush(passes: int = 3):
    """Run pending events (used for zero-delay timers such as TextItem commit)."""
    for _ in range(passes):
        QCoreApplication.processEvents()


def solid_pixmap(w: int, h: int) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(QColor(200, 210, 220))
    return pm


def make_editor(w: int = 400, h: int = 300):
    """Headless EditorWindow (never shown). Imported lazily so get_app() runs first."""
    get_app()
    from snip.editor import EditorWindow
    ed = EditorWindow(solid_pixmap(w, h))
    ed.confirm_unsaved = False
    return ed

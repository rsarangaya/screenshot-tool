"""Entry point: main window + tray icon + global hotkey."""
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import editor, single_instance
from .hotkey import HOTKEY_KEY, HOTKEY_MODIFIERS, HotkeyListener
from .main_window import MainWindow
from .overlay import Overlay

HIDE_DELAY_MS = 150  # let the compositor drop hidden windows before grabbing


def _make_icon() -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setPen(QColor(30, 144, 255))
    p.drawRect(4, 4, 23, 23)
    p.drawLine(0, 12, 8, 12)
    p.drawLine(12, 0, 12, 8)
    p.end()
    return QIcon(pm)


def main() -> int:
    if single_instance.notify_existing():
        return 0
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(_make_icon())

    server = single_instance.InstanceServer(parent=app)
    combo = "+".join(m.capitalize() for m in HOTKEY_MODIFIERS) + "+" + HOTKEY_KEY
    win = MainWindow(combo)
    overlay = Overlay()
    hidden = []

    def restore():
        for w in hidden:
            try:
                w.show()
            except RuntimeError:  # editor already deleted
                pass
        hidden.clear()

    overlay.on_done = restore

    def capture(extra=None):
        """Hide our visible windows so they are not in the shot, then capture."""
        if overlay.active or hidden:
            return
        for w in (win, extra):
            if w is not None and w.isVisible():
                hidden.append(w)
                w.hide()
        if hidden:
            QTimer.singleShot(HIDE_DELAY_MS, overlay.start)
        else:
            overlay.start()

    win.new_capture.connect(lambda: capture())
    editor.new_capture_hook = capture

    tray = QSystemTrayIcon(_make_icon(), app)
    menu = QMenu()
    menu.addAction("Show", win.bring_to_front)
    menu.addAction("New capture", lambda: capture())
    menu.addAction("Quit", app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda r: win.bring_to_front() if r == QSystemTrayIcon.ActivationReason.Trigger else None
    )
    tray.setToolTip(f"Snip ({combo})")
    tray.show()

    server.activated.connect(win.bring_to_front)

    hotkey = HotkeyListener()
    app.installNativeEventFilter(hotkey)
    hotkey.triggered.connect(lambda: capture())
    if not hotkey.register():
        tray.showMessage("Snip", f"Could not register {combo} (already in use).")
    app.aboutToQuit.connect(hotkey.unregister)
    app.aboutToQuit.connect(tray.hide)

    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

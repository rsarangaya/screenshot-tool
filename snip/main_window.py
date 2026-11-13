"""Main window: + New button, hotkey hint, settings. Closing hides to tray."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from . import settings, startup


class MainWindow(QWidget):
    new_capture = Signal()

    def __init__(self, hotkey_text: str):
        super().__init__()
        self.setWindowTitle("Snip")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)

        self.btn_new = QPushButton("+ New")
        self.btn_new.setMinimumHeight(56)
        f = self.btn_new.font()
        f.setPointSize(f.pointSize() + 5)
        f.setBold(True)
        self.btn_new.setFont(f)
        self.btn_new.setDefault(True)
        self.btn_new.clicked.connect(lambda: self.new_capture.emit())
        lay.addWidget(self.btn_new)

        self.hint = QLabel(f"Or press {hotkey_text} anywhere to capture.")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.hint)

        box = QGroupBox("Settings")
        bl = QVBoxLayout(box)
        bl.addWidget(QLabel(f"Hotkey: {hotkey_text}"))
        row = QHBoxLayout()
        self.folder_label = QLabel()
        self.folder_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(QLabel("Save folder:"))
        row.addWidget(self.folder_label, 1)
        self.btn_folder = QPushButton("Change...")
        self.btn_folder.clicked.connect(self.choose_folder)
        row.addWidget(self.btn_folder)
        bl.addLayout(row)
        self.chk_startup = QCheckBox("Start with Windows")
        self.chk_startup.setChecked(startup.is_enabled())
        self.chk_startup.toggled.connect(self._startup_toggled)
        bl.addWidget(self.chk_startup)
        lay.addWidget(box)
        self.refresh_folder()

    def refresh_folder(self):
        self.folder_label.setText(settings.get_save_folder())

    def choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Default save folder",
                                             settings.get_save_folder())
        if d:
            settings.set_save_folder(d)
            self.refresh_folder()

    def _startup_toggled(self, on):
        if not startup.set_enabled(on):  # failed: revert to the real state
            self.chk_startup.blockSignals(True)
            self.chk_startup.setChecked(startup.is_enabled())
            self.chk_startup.blockSignals(False)

    def bring_to_front(self):
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        e.ignore()
        self.hide()  # stays alive in the tray

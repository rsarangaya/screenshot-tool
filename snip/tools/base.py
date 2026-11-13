"""Shared tool base class and drawing options."""
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor


class Options:
    """Current drawing options (single instance owned by the editor)."""

    def __init__(self):
        self.color = QColor(230, 40, 40)
        self.size = 4
        self.font_family = "Segoe UI"
        self.font_size = 24
        self.bold = False
        self.bg_enabled = False
        self.bg_color = QColor(255, 235, 59)


class Tool:
    """A tool receives scene-space mouse events from the canvas view.

    ctx is the editor: it exposes scene, stack (QUndoStack), base (pixmap item)
    and options.
    """

    name = ""
    cursor = Qt.CursorShape.CrossCursor
    passthrough = False  # True: view also runs default QGraphicsView handling
    shows_stroke = True  # color + width options relevant
    shows_text = False   # font/size/bold/color/background options relevant

    def __init__(self, ctx):
        self.ctx = ctx

    def passthrough_at(self, pos: QPointF) -> bool:
        return self.passthrough

    def activate(self):
        pass

    def deactivate(self):
        pass

    def press(self, pos: QPointF):
        pass

    def move(self, pos: QPointF):
        pass

    def release(self, pos: QPointF):
        pass

    def blur(self):
        """End any in-place text editing."""
        self.ctx.scene.clearFocus()

"""Select/move tool. Default view handling does selection and dragging; this
only records moves so they can be undone."""
from PySide6.QtCore import Qt
from .base import Tool
from .commands import CallbackCommand


class SelectTool(Tool):
    name = "select"
    cursor = Qt.CursorShape.ArrowCursor
    passthrough = True
    shows_stroke = False

    def __init__(self, ctx):
        super().__init__(ctx)
        self._snap = []

    def press(self, pos):
        self._snap = [(i, i.pos()) for i in self.ctx.scene.selectedItems()]

    def release(self, pos):
        moved = [(i, o, i.pos()) for i, o in self._snap if i.pos() != o]
        self._snap = []
        if not moved:
            return

        def apply(idx):
            for m in moved:
                m[0].setPos(m[idx])

        self.ctx.stack.push(CallbackCommand("Move", lambda: apply(2), lambda: apply(1)))

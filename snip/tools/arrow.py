"""Arrow tool."""
from PySide6.QtGui import QColor
from .base import Tool
from .commands import AddItemCommand
from .items import ArrowItem


class ArrowTool(Tool):
    name = "arrow"

    def __init__(self, ctx):
        super().__init__(ctx)
        self._item = None
        self._start = None

    def press(self, pos):
        self.blur()
        self.ctx.scene.clearSelection()
        o = self.ctx.options
        self._start = pos
        self._item = ArrowItem(QColor(o.color), o.size)
        self._item.set_line(pos, pos)
        self.ctx.scene.addItem(self._item)

    def move(self, pos):
        if self._item is not None:
            self._item.set_line(self._start, pos)

    def release(self, pos):
        it, self._item = self._item, None
        if it is None:
            return
        it.set_line(self._start, pos)
        d = pos - self._start
        if abs(d.x()) + abs(d.y()) < 3:
            self.ctx.scene.removeItem(it)
            return
        self.ctx.stack.push(AddItemCommand(self.ctx.scene, it, "Arrow"))

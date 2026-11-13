"""Rectangle tool (outline)."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPen, QColor
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from .base import Tool
from .commands import AddItemCommand


class RectTool(Tool):
    name = "rect"

    def __init__(self, ctx):
        super().__init__(ctx)
        self._item = None
        self._start = None

    def press(self, pos):
        self.blur()
        self.ctx.scene.clearSelection()
        o = self.ctx.options
        it = QGraphicsRectItem()
        it.setPen(QPen(QColor(o.color), o.size, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
        it.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                    | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self._item, self._start = it, pos
        self.ctx.scene.addItem(it)

    def move(self, pos):
        if self._item is not None:
            self._item.setRect(QRectF(self._start, pos).normalized())

    def release(self, pos):
        it, self._item = self._item, None
        if it is None:
            return
        r = QRectF(self._start, pos).normalized()
        if r.width() < 3 and r.height() < 3:
            self.ctx.scene.removeItem(it)
            return
        it.setRect(r)
        self.ctx.stack.push(AddItemCommand(self.ctx.scene, it, "Rectangle"))

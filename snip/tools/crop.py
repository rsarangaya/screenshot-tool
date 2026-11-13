"""Crop tool: drag a rectangle, release to crop (undoable)."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPen, QColor
from PySide6.QtWidgets import QGraphicsRectItem
from .base import Tool
from .commands import CropCommand


class CropTool(Tool):
    name = "crop"
    shows_stroke = False

    def __init__(self, ctx):
        super().__init__(ctx)
        self._item = None
        self._start = None

    def press(self, pos):
        self.blur()
        self.ctx.scene.clearSelection()
        it = QGraphicsRectItem()
        it.setPen(QPen(QColor(255, 255, 255), 0, Qt.PenStyle.DashLine))
        it.setBrush(QColor(0, 120, 215, 50))
        it.setZValue(1e6)
        self._item, self._start = it, pos
        self.ctx.scene.addItem(it)

    def _rect(self, pos):
        return QRectF(self._start, pos).normalized().intersected(self.ctx.scene.sceneRect())

    def move(self, pos):
        if self._item is not None:
            self._item.setRect(self._rect(pos))

    def release(self, pos):
        it, self._item = self._item, None
        if it is None:
            return
        self.ctx.scene.removeItem(it)
        r = self._rect(pos)
        if r.width() >= 4 and r.height() >= 4:
            self.ctx.stack.push(CropCommand(self.ctx, r))

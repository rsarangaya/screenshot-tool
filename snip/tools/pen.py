"""Pen tool (freehand)."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap
from .base import Tool
from .commands import AddItemCommand
from .items import StrokeItem

_pen_cursor = None


def pen_cursor() -> QCursor:
    """Small pen icon drawn with QPainter; hotspot at the nib (bottom-left)."""
    global _pen_cursor
    if _pen_cursor is None:
        pm = QPixmap(24, 24)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(Qt.GlobalColor.black, 1))
        p.setBrush(QColor(255, 210, 60))
        p.drawPolygon(_pts((2, 22), (4, 15), (16, 3), (21, 8), (9, 20)))
        p.setBrush(Qt.GlobalColor.black)
        p.drawPolygon(_pts((2, 22), (4, 15), (9, 20)))
        p.end()
        _pen_cursor = QCursor(pm, 2, 22)
    return _pen_cursor


def _pts(*xy):
    return [QPoint(x, y) for x, y in xy]


class PenTool(Tool):
    name = "pen"

    @property
    def cursor(self):
        return pen_cursor()

    def __init__(self, ctx):
        super().__init__(ctx)
        self._item = None

    def make_item(self):
        o = self.ctx.options
        return StrokeItem(QColor(o.color), o.size)

    def press(self, pos):
        self.blur()
        self.ctx.scene.clearSelection()
        self._item = self.make_item()
        self._item.begin(pos)
        self.ctx.scene.addItem(self._item)

    def move(self, pos):
        if self._item is not None:
            self._item.add_point(pos)

    def release(self, pos):
        it, self._item = self._item, None
        if it is None:
            return
        it.add_point(pos)
        it.finish()
        self.ctx.stack.push(AddItemCommand(self.ctx.scene, it, "Draw"))

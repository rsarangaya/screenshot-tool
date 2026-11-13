"""Highlighter: wide semi-transparent stroke."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from .items import StrokeItem
from .pen import PenTool


class HighlighterTool(PenTool):
    name = "highlighter"
    cursor = Qt.CursorShape.IBeamCursor

    def make_item(self):
        o = self.ctx.options
        c = QColor(o.color)
        c.setAlpha(100)
        return StrokeItem(c, max(14, o.size * 3), Qt.PenCapStyle.FlatCap)

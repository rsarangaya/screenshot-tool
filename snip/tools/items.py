"""Custom graphics items: freehand stroke and arrow."""
import math
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QPen, QPolygonF, QColor
from PySide6.QtWidgets import QGraphicsItem, QStyle

_FLAGS = (QGraphicsItem.GraphicsItemFlag.ItemIsMovable
          | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
_SLACK = 128.0  # bounding-rect growth chunk while drawing (avoids per-move geometry changes)


def _paint_selection(painter, option, rect):
    if option.state & QStyle.StateFlag.State_Selected:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(0, 120, 215), 0, Qt.PenStyle.DashLine))
        painter.drawRect(rect)


class StrokeItem(QGraphicsItem):
    """Freehand path, appended incrementally (quadratic smoothing)."""

    def __init__(self, color, width, cap=Qt.PenCapStyle.RoundCap):
        super().__init__()
        self.setFlags(_FLAGS)
        self._path = QPainterPath()
        self._pen = QPen(color, width, Qt.PenStyle.SolidLine, cap, Qt.PenJoinStyle.RoundJoin)
        self._pad = width / 2.0 + 1.0
        self._br = QRectF()
        self._last = None
        self._shape = None

    def begin(self, p: QPointF):
        self._path.moveTo(p)
        self._path.lineTo(p)  # dot for a click without drag
        self._last = QPointF(p)
        pad = self._pad + _SLACK
        self.prepareGeometryChange()
        self._br = QRectF(p.x() - pad, p.y() - pad, 2 * pad, 2 * pad)

    def add_point(self, p: QPointF):
        last = self._last
        dx, dy = p.x() - last.x(), p.y() - last.y()
        if dx * dx + dy * dy < 1.0:
            return
        mid = QPointF((last.x() + p.x()) * 0.5, (last.y() + p.y()) * 0.5)
        self._path.quadTo(last, mid)
        self._last = QPointF(p)
        pad = self._pad
        need = QRectF(min(last.x(), p.x()) - pad, min(last.y(), p.y()) - pad,
                      abs(dx) + 2 * pad, abs(dy) + 2 * pad)
        if not self._br.contains(need):
            self.prepareGeometryChange()
            self._br = self._br.united(need.adjusted(-_SLACK, -_SLACK, _SLACK, _SLACK))
        self.update(need)

    def finish(self):
        if self._last is not None:
            self._path.lineTo(self._last)
        self.prepareGeometryChange()
        self._br = self._path.controlPointRect().adjusted(-self._pad, -self._pad, self._pad, self._pad)
        self._shape = None
        self.update()

    def boundingRect(self):
        return self._br

    def shape(self):
        if self._shape is None:
            s = QPainterPathStroker()
            s.setWidth(max(self._pen.widthF(), 10.0))
            s.setCapStyle(Qt.PenCapStyle.RoundCap)
            self._shape = s.createStroke(self._path)
        return self._shape

    def paint(self, painter, option, widget=None):
        painter.setPen(self._pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)
        _paint_selection(painter, option, self._br)


class ArrowItem(QGraphicsItem):
    """Arrow from p1 (tail) to p2 (head), in item coordinates."""

    def __init__(self, color, width):
        super().__init__()
        self.setFlags(_FLAGS)
        self._color = QColor(color)
        self._pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                         Qt.PenJoinStyle.RoundJoin)
        self._w = width
        self._p1 = QPointF()
        self._p2 = QPointF()
        self._shaft_end = QPointF()
        self._head = QPolygonF()
        self._br = QRectF()
        self._shape = None

    def set_line(self, p1: QPointF, p2: QPointF):
        self.prepareGeometryChange()
        self._p1, self._p2 = QPointF(p1), QPointF(p2)
        dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
        length = math.hypot(dx, dy)
        hl = max(12.0, self._w * 4.0)
        if length < 1e-6:
            self._head = QPolygonF()
            self._shaft_end = QPointF(p2)
        else:
            hl = min(hl, length)
            ux, uy = dx / length, dy / length
            bx, by = p2.x() - ux * hl, p2.y() - uy * hl
            hw = hl * 0.45
            self._head = QPolygonF([p2, QPointF(bx - uy * hw, by + ux * hw),
                                    QPointF(bx + uy * hw, by - ux * hw)])
            self._shaft_end = QPointF(bx + ux * hl * 0.2, by + uy * hl * 0.2)
        pad = self._w / 2.0 + 2.0
        self._br = QRectF(p1, p2).normalized().adjusted(-pad - 8, -pad - 8, pad + 8, pad + 8)
        self._shape = None
        self.update()

    def boundingRect(self):
        return self._br

    def shape(self):
        if self._shape is None:
            path = QPainterPath(self._p1)
            path.lineTo(self._p2)
            s = QPainterPathStroker()
            s.setWidth(max(self._w, 10.0))
            self._shape = s.createStroke(path)
            self._shape.addPolygon(self._head)
        return self._shape

    def paint(self, painter, option, widget=None):
        painter.setPen(self._pen)
        painter.drawLine(self._p1, self._shaft_end)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawPolygon(self._head)
        _paint_selection(painter, option, self._br)

"""Text tool and TextItem (QGraphicsTextItem): place, edit, move, scale, style."""
import math
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPen, QBrush, QTextCursor, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem
from .base import Tool
from .commands import AddItemCommand, CallbackCommand, RemoveItemsCommand

_F = QGraphicsItem.GraphicsItemFlag


class _ScaleHandle(QGraphicsRectItem):
    """Corner handle (constant on-screen size) that uniformly scales its parent."""

    def __init__(self, parent):
        super().__init__(-5, -5, 10, 10, parent)
        self.setFlag(_F.ItemIgnoresTransformations)
        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setPen(QPen(QColor(0, 120, 215), 1))
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setZValue(10)
        self.setVisible(False)
        self._s0 = 1.0
        self._d0 = 1.0

    def _dist(self, scene_pos):
        o = self.parentItem().scenePos()
        return max(math.hypot(scene_pos.x() - o.x(), scene_pos.y() - o.y()), 1.0)

    def mousePressEvent(self, e):
        self._s0 = self.parentItem().scale()
        self._d0 = self._dist(e.scenePos())
        e.accept()

    def mouseMoveEvent(self, e):
        s = self._s0 * self._dist(e.scenePos()) / self._d0
        self.parentItem().setScale(min(max(s, 0.2), 20.0))

    def mouseReleaseEvent(self, e):
        item, old, new = self.parentItem(), self._s0, self.parentItem().scale()
        if abs(new - old) > 1e-6:
            item.stack.push(CallbackCommand("Resize text",
                                            lambda: item.setScale(new),
                                            lambda: item.setScale(old)))
        e.accept()


class TextItem(QGraphicsTextItem):
    def __init__(self, stack):
        super().__init__()
        self.stack = stack
        self._bg = None
        self._editing = False
        self._new = False
        self._orig = ""
        self.setFlags(_F.ItemIsMovable | _F.ItemIsSelectable | _F.ItemIsFocusable)
        self._handle = _ScaleHandle(self)
        self.document().contentsChanged.connect(self._place_handle)

    @property
    def editing(self):
        return self._editing

    # ---- style ----
    def style(self):
        f = self.font()
        return {"family": f.family(), "size": f.pixelSize(), "bold": f.bold(),
                "color": QColor(self.defaultTextColor()),
                "bg": QColor(self._bg) if self._bg is not None else None}

    def set_style(self, s):
        f = QFont(s["family"])
        f.setPixelSize(s["size"])
        f.setBold(s["bold"])
        self.setFont(f)
        self.setDefaultTextColor(s["color"])
        self._bg = QColor(s["bg"]) if s["bg"] is not None else None
        self._place_handle()
        self.update()

    def _place_handle(self):
        self._handle.setPos(self.boundingRect().bottomRight())

    def paint(self, painter, option, widget=None):
        if self._bg is not None:
            painter.fillRect(self.boundingRect(), self._bg)
        super().paint(painter, option, widget)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._handle.setVisible(bool(value) and self.scene() is not None)
        return super().itemChange(change, value)

    # ---- editing ----
    def start_edit(self, new=False):
        if self._editing:
            return
        self._editing = True
        self._new = new
        self._orig = self.toPlainText()
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        c = self.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(c)

    def end_edit(self):
        if not self._editing:
            return
        self._editing = False
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        c = self.textCursor()
        c.clearSelection()
        self.setTextCursor(c)
        QTimer.singleShot(0, self._commit)  # not safe to remove items inside focusOut

    def _set_text(self, t):
        self.setPlainText(t)
        self._place_handle()

    def _commit(self):
        sc = self.scene()
        if sc is None or self._editing:
            return
        text, new, self._new = self.toPlainText(), self._new, False
        if not text.strip():
            if new:
                sc.removeItem(self)
            else:
                self.setPlainText(self._orig)  # so undo restores the original text
                self.stack.push(RemoveItemsCommand(sc, [self], "Delete text"))
        elif new:
            self.stack.push(AddItemCommand(sc, self, "Add text"))
        elif text != self._orig:
            old = self._orig
            self.stack.push(CallbackCommand("Edit text", lambda: self._set_text(text),
                                            lambda: self._set_text(old)))

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.end_edit()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.clearFocus()
            e.accept()
            return
        super().keyPressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if not self._editing:
            self.start_edit()
            e.accept()
        else:
            super().mouseDoubleClickEvent(e)


class TextTool(Tool):
    name = "text"
    cursor = Qt.CursorShape.IBeamCursor
    shows_stroke = False
    shows_text = True

    def _text_at(self, pos):
        for it in self.ctx.scene.items(pos):
            if isinstance(it, TextItem):
                return it
        return None

    def passthrough_at(self, pos):
        sc = self.ctx.scene
        views = sc.views()
        dt = views[0].transform() if views else QTransform()
        for it in sc.items(pos, Qt.ItemSelectionMode.IntersectsItemShape,
                           Qt.SortOrder.DescendingOrder, dt):
            if isinstance(it, _ScaleHandle) and it.isVisible():
                return True
        it = self._text_at(pos)
        return it is not None and it.editing

    def press(self, pos):
        sc = self.ctx.scene
        f = sc.focusItem()
        if isinstance(f, TextItem) and f.editing:
            f.clearFocus()  # click away only ends editing
            return
        it = self._text_at(pos)
        if it is not None:
            sc.clearSelection()
            it.setSelected(True)
            it.start_edit()
            return
        o = self.ctx.options
        it = TextItem(self.ctx.stack)
        it.set_style({"family": o.font_family, "size": o.font_size, "bold": o.bold,
                      "color": QColor(o.color),
                      "bg": QColor(o.bg_color) if o.bg_enabled else None})
        it.setPos(pos)
        sc.clearSelection()
        sc.addItem(it)
        it.setSelected(True)
        it.start_edit(new=True)

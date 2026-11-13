"""Undo commands."""
from PySide6.QtCore import QPointF
from PySide6.QtGui import QUndoCommand


class AddItemCommand(QUndoCommand):
    """Item may already be in the scene when pushed (first redo is a no-op)."""

    def __init__(self, scene, item, text="Add"):
        super().__init__(text)
        self.scene, self.item = scene, item

    def redo(self):
        if self.item.scene() is not self.scene:
            self.scene.addItem(self.item)

    def undo(self):
        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)


class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items, text="Delete"):
        super().__init__(text)
        self.scene, self.items = scene, list(items)

    def redo(self):
        for it in self.items:
            if it.scene() is self.scene:
                self.scene.removeItem(it)

    def undo(self):
        for it in self.items:
            if it.scene() is not self.scene:
                self.scene.addItem(it)


class CallbackCommand(QUndoCommand):
    """Generic command from a redo and an undo callable."""

    def __init__(self, text, redo_fn, undo_fn):
        super().__init__(text)
        self._redo, self._undo = redo_fn, undo_fn

    def redo(self):
        self._redo()

    def undo(self):
        self._undo()


class CropCommand(QUndoCommand):
    """Replace the base pixmap with a crop and shift all items to match."""

    def __init__(self, ctx, rect):
        super().__init__("Crop")
        self.scene, self.base = ctx.scene, ctx.base
        r = rect.toRect()
        self.offset = QPointF(r.x(), r.y())
        self.old = self.base.pixmap()
        self.new = self.old.copy(r)
        self.items = [i for i in self.scene.items()
                      if i.parentItem() is None and i is not self.base]

    def _apply(self, pm, delta):
        self.base.setPixmap(pm)
        for it in self.items:
            it.setPos(it.pos() + delta)
        self.scene.setSceneRect(0, 0, pm.width(), pm.height())

    def redo(self):
        self._apply(self.new, -self.offset)

    def undo(self):
        self._apply(self.old, self.offset)

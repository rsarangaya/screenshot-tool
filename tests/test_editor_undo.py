"""Editor undo/redo for pen, rect, arrow, text (add/edit/move/delete) and crop."""
import unittest

from qt_support import flush, make_editor

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QGraphicsRectItem  # noqa: E402

from snip.editor import EditorWindow  # noqa: E402
from snip.tools.items import ArrowItem, StrokeItem  # noqa: E402
from snip.tools.text import TextItem  # noqa: E402


class EditorCase(unittest.TestCase):
    def setUp(self):
        self.ed: EditorWindow = make_editor(400, 300)
        self.stack = self.ed.stack

    def tearDown(self):
        self.ed.close()

    def _items(self, cls):
        return [i for i in self.ed.scene.items() if isinstance(i, cls)]

    def _undo_redo(self, item):
        """Assert item is in scene, undo removes it, redo restores it."""
        self.assertIsNotNone(item.scene())
        self.ed.undo()
        self.assertIsNone(item.scene())
        self.ed.redo()
        self.assertIs(item.scene(), self.ed.scene)

    def _new_text(self, pos, text):
        self.ed.set_tool("text")
        self.ed.tools["text"].press(pos)
        item = self._items(TextItem)[-1]
        item.setPlainText(text)
        item.end_edit()
        flush()
        return item


class ShapeUndoTest(EditorCase):
    def test_pen_stroke_undo_redo(self):
        self.ed.set_tool("pen")
        tool = self.ed.tools["pen"]
        tool.press(QPointF(10, 10))
        tool.move(QPointF(40, 40))
        tool.release(QPointF(60, 20))
        strokes = self._items(StrokeItem)
        self.assertEqual(len(strokes), 1)
        self.assertEqual(self.stack.count(), 1)
        self._undo_redo(strokes[0])

    def test_rect_undo_redo(self):
        self.ed.set_tool("rect")
        tool = self.ed.tools["rect"]
        tool.press(QPointF(20, 20))
        tool.move(QPointF(120, 90))
        tool.release(QPointF(120, 90))
        rects = self._items(QGraphicsRectItem)
        self.assertEqual(len(rects), 1)
        self.assertEqual(self.stack.count(), 1)
        self._undo_redo(rects[0])

    def test_rect_tiny_drag_adds_nothing(self):
        self.ed.set_tool("rect")
        tool = self.ed.tools["rect"]
        tool.press(QPointF(20, 20))
        tool.release(QPointF(21, 21))
        self.assertEqual(self.stack.count(), 0)
        self.assertEqual(self.ed.scene.items(), [self.ed.base])

    def test_arrow_undo_redo(self):
        self.ed.set_tool("arrow")
        tool = self.ed.tools["arrow"]
        tool.press(QPointF(10, 10))
        tool.move(QPointF(100, 80))
        tool.release(QPointF(100, 80))
        arrows = self._items(ArrowItem)
        self.assertEqual(len(arrows), 1)
        self.assertEqual(self.stack.count(), 1)
        self._undo_redo(arrows[0])

    def test_arrow_click_without_drag_adds_nothing(self):
        self.ed.set_tool("arrow")
        tool = self.ed.tools["arrow"]
        tool.press(QPointF(10, 10))
        tool.release(QPointF(10, 10))
        self.assertEqual(self.stack.count(), 0)
        self.assertEqual(self._items(ArrowItem), [])


class TextUndoTest(EditorCase):
    def test_text_add_undo_redo(self):
        item = self._new_text(QPointF(50, 50), "hello")
        self.assertEqual(self.stack.count(), 1)
        self._undo_redo(item)

    def test_text_edit_undo_redo(self):
        item = self._new_text(QPointF(50, 50), "hello")
        self.ed.set_tool("text")
        self.ed.tools["text"].press(item.sceneBoundingRect().center())  # re-enter edit
        self.assertTrue(item.editing)
        item.setPlainText("world")
        item.end_edit()
        flush()
        self.assertEqual(self.stack.count(), 2)
        self.assertEqual(item.toPlainText(), "world")
        self.ed.undo()
        self.assertEqual(item.toPlainText(), "hello")
        self.ed.redo()
        self.assertEqual(item.toPlainText(), "world")

    def test_text_move_undo_redo(self):
        item = self._new_text(QPointF(50, 50), "move me")
        start = QPointF(item.pos())
        self.ed.set_tool("select")
        self.ed.scene.clearSelection()
        item.setSelected(True)
        tool = self.ed.tools["select"]
        tool.press(QPointF(60, 60))
        item.setPos(start + QPointF(30, 20))
        tool.release(QPointF(90, 80))
        self.assertEqual(self.stack.count(), 2)
        self.ed.undo()
        self.assertEqual(item.pos(), start)
        self.ed.redo()
        self.assertEqual(item.pos(), start + QPointF(30, 20))

    def test_text_delete_undo_redo(self):
        item = self._new_text(QPointF(50, 50), "bye")
        self.ed.scene.clearSelection()
        item.setSelected(True)
        self.ed.delete_selected()
        self.assertIsNone(item.scene())
        self.ed.undo()
        self.assertIs(item.scene(), self.ed.scene)
        self.ed.redo()
        self.assertIsNone(item.scene())


class CropUndoTest(EditorCase):
    def test_crop_resizes_base_shifts_items_and_undoes(self):
        self.ed.set_tool("pen")
        tool = self.ed.tools["pen"]
        tool.press(QPointF(150, 150))
        tool.release(QPointF(180, 180))
        stroke = self._items(StrokeItem)[0]

        self.ed.set_tool("crop")
        crop = self.ed.tools["crop"]
        crop.press(QPointF(10, 10))
        crop.move(QPointF(70, 60))
        crop.release(QPointF(110, 60))  # 100 x 50 crop at (10, 10)

        self.assertEqual(self.ed.base.pixmap().width(), 100)
        self.assertEqual(self.ed.base.pixmap().height(), 50)
        self.assertEqual((self.ed.scene.sceneRect().width(), self.ed.scene.sceneRect().height()), (100, 50))
        self.assertEqual(stroke.pos(), QPointF(-10, -10))

        self.ed.undo()
        self.assertEqual((self.ed.base.pixmap().width(), self.ed.base.pixmap().height()), (400, 300))
        self.assertEqual(stroke.pos(), QPointF(0, 0))

        self.ed.redo()
        self.assertEqual(self.ed.base.pixmap().width(), 100)
        self.assertEqual(stroke.pos(), QPointF(-10, -10))

    def test_tiny_crop_is_ignored(self):
        self.ed.set_tool("crop")
        crop = self.ed.tools["crop"]
        crop.press(QPointF(10, 10))
        crop.release(QPointF(12, 12))
        self.assertEqual(self.stack.count(), 0)
        self.assertEqual(self.ed.base.pixmap().width(), 400)


if __name__ == "__main__":
    unittest.main()

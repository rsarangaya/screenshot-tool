"""Text tool edge cases: empty text is discarded, scale handle passthrough."""
import unittest

from qt_support import flush, make_editor

from PySide6.QtCore import QPointF  # noqa: E402

from snip.tools.text import TextItem  # noqa: E402


class TextToolTest(unittest.TestCase):
    def setUp(self):
        self.ed = make_editor(400, 300)
        self.tool = self.ed.tools["text"]
        self.ed.set_tool("text")

    def tearDown(self):
        self.ed.close()

    def _text_items(self):
        return [i for i in self.ed.scene.items() if isinstance(i, TextItem)]

    def test_empty_new_text_is_removed_without_undo_entry(self):
        self.tool.press(QPointF(50, 50))
        item = self._text_items()[0]
        item.end_edit()  # nothing typed
        flush()
        self.assertIsNone(item.scene())
        self.assertEqual(self._text_items(), [])
        self.assertEqual(self.ed.stack.count(), 0)

    def test_whitespace_only_new_text_is_removed(self):
        self.tool.press(QPointF(50, 50))
        item = self._text_items()[0]
        item.setPlainText("   \n  ")
        item.end_edit()
        flush()
        self.assertEqual(self._text_items(), [])
        self.assertEqual(self.ed.stack.count(), 0)

    def test_clearing_existing_text_deletes_it_and_undo_restores(self):
        self.tool.press(QPointF(50, 50))
        item = self._text_items()[0]
        item.setPlainText("keep")
        item.end_edit()
        flush()
        self.assertEqual(self.ed.stack.count(), 1)

        self.tool.press(item.sceneBoundingRect().center())  # re-enter edit
        item.setPlainText("")
        item.end_edit()
        flush()
        self.assertIsNone(item.scene())
        self.ed.undo()
        self.assertIs(item.scene(), self.ed.scene)
        self.assertEqual(item.toPlainText(), "keep")


class ScaleHandlePassthroughTest(unittest.TestCase):
    def setUp(self):
        self.ed = make_editor(400, 300)
        self.ed.set_tool("text")
        self.tool = self.ed.tools["text"]
        self.tool.press(QPointF(50, 50))
        self.item = [i for i in self.ed.scene.items() if isinstance(i, TextItem)][0]
        self.item.setPlainText("resize me")
        self.item.end_edit()
        flush()
        self.ed.scene.clearSelection()
        self.item.setSelected(True)

    def tearDown(self):
        self.ed.close()

    def test_passthrough_true_at_scale_handle(self):
        handle = self.item._handle
        self.assertTrue(handle.isVisible())
        self.assertTrue(self.tool.passthrough_at(handle.scenePos()))

    def test_passthrough_false_away_from_handle(self):
        far = self.item.sceneBoundingRect().topLeft() + QPointF(-100, -100)
        self.assertFalse(self.tool.passthrough_at(far))

    def test_handle_not_hit_when_item_unselected(self):
        self.ed.scene.clearSelection()
        handle = self.item._handle
        self.assertFalse(handle.isVisible())
        self.assertFalse(self.tool.passthrough_at(handle.scenePos()))


if __name__ == "__main__":
    unittest.main()

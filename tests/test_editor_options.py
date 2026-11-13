"""Option visibility per tool and tool cursors."""
import unittest

from qt_support import make_editor

from PySide6.QtCore import QPointF, Qt  # noqa: E402

from snip.tools.text import TextItem  # noqa: E402


class OptionVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.ed = make_editor(400, 300)

    def tearDown(self):
        self.ed.close()

    def _vis(self):
        return (self.ed.vis_color.isVisible(), self.ed.vis_width.isVisible(),
                all(a.isVisible() for a in self.ed.vis_text),
                any(a.isVisible() for a in self.ed.vis_text))

    def test_per_tool(self):
        for key, exp in (("pen", (True, True, False)), ("highlighter", (True, True, False)),
                         ("arrow", (True, True, False)), ("rect", (True, True, False)),
                         ("text", (True, False, True)), ("select", (False, False, False))):
            self.ed.set_tool(key)
            c, w, _all, anyt = self._vis()
            self.assertEqual((c, w, anyt), exp, key)

    def test_select_with_text_selected(self):
        self.ed.set_tool("text")
        self.ed.tools["text"].press(QPointF(20, 20))
        item = [i for i in self.ed.scene.items() if isinstance(i, TextItem)][0]
        item.setPlainText("hi")
        item.setSelected(True)
        self.ed.set_tool("select")
        self.assertTrue(self.ed.vis_text[0].isVisible())
        self.assertFalse(self.ed.vis_width.isVisible())

    def test_cursors(self):
        self.ed.set_tool("highlighter")
        self.assertEqual(self.ed.view.viewport().cursor().shape(), Qt.CursorShape.IBeamCursor)
        self.ed.set_tool("pen")
        cur = self.ed.view.viewport().cursor()
        self.assertEqual(cur.shape(), Qt.CursorShape.BitmapCursor)
        self.assertEqual((cur.hotSpot().x(), cur.hotSpot().y()), (2, 22))
        self.ed.set_tool("select")
        self.assertEqual(self.ed.view.viewport().cursor().shape(), Qt.CursorShape.ArrowCursor)


if __name__ == "__main__":
    unittest.main()

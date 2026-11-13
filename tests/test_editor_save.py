"""Saving the editor output: file dimensions match the (possibly cropped) image."""
import os
import tempfile
import unittest

from qt_support import make_editor

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402


class SaveSizeTest(unittest.TestCase):
    def setUp(self):
        self.ed = make_editor(320, 200)
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.ed.close()
        self.tmp.cleanup()

    def _saved_size(self, name):
        path = os.path.join(self.tmp.name, name)
        self.assertTrue(self.ed.save(path))
        img = QImage(path)
        self.assertFalse(img.isNull())
        return img.width(), img.height()

    def test_png_matches_image_size(self):
        self.assertEqual(self._saved_size("out.png"), (320, 200))

    def test_jpg_matches_image_size(self):
        self.assertEqual(self._saved_size("out.jpg"), (320, 200))

    def test_png_after_crop_matches_cropped_size(self):
        self.ed.set_tool("crop")
        crop = self.ed.tools["crop"]
        crop.press(QPointF(10, 10))
        crop.release(QPointF(90, 60))  # 80 x 50
        self.assertEqual(self._saved_size("cropped.png"), (80, 50))


if __name__ == "__main__":
    unittest.main()

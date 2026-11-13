"""Crop math (logical -> physical pixels) and the no-screen overlay path."""
import unittest
from unittest import mock

from qt_support import get_app

get_app()

from PySide6.QtCore import QRect  # noqa: E402
from PySide6.QtGui import QColor, QPixmap  # noqa: E402

from snip.capture import ScreenShot, logical_to_pixel_rect  # noqa: E402
from snip.overlay import Overlay  # noqa: E402


class LogicalToPixelRectTest(unittest.TestCase):
    def test_dpr_1_is_identity(self):
        self.assertEqual(logical_to_pixel_rect(10, 20, 30, 40, 1.0), (10, 20, 30, 40))

    def test_dpr_1_25(self):
        # 10..20 logical -> 12.5..25 physical: origin floors to 12, far edge ceils to 25.
        self.assertEqual(logical_to_pixel_rect(10, 10, 10, 10, 1.25), (12, 12, 13, 13))

    def test_dpr_1_5(self):
        self.assertEqual(logical_to_pixel_rect(3, 3, 5, 5, 1.5), (4, 4, 8, 8))

    def test_dpr_2_0(self):
        self.assertEqual(logical_to_pixel_rect(1, 2, 3, 4, 2.0), (2, 4, 6, 8))

    def test_fractional_origin_floors_and_far_edge_ceils(self):
        # 1.25 -> floor 1; 2.5 -> ceil 3 => width 2
        self.assertEqual(logical_to_pixel_rect(1, 0, 1, 1, 1.25), (1, 0, 2, 2))

    def test_exact_boundary_not_pushed_by_float_error(self):
        # 0.29 * 100 == 28.999999999999996 in floats; origin must stay at 29, not 28.
        self.assertEqual(logical_to_pixel_rect(0.29, 0, 1, 1, 100), (29, 0, 100, 100))

    def test_zero_size_at_integer_boundary_is_empty(self):
        self.assertEqual(logical_to_pixel_rect(5, 5, 0, 0, 1.0), (5, 5, 0, 0))

    def test_negative_size_clamped_to_zero(self):
        _, _, w, h = logical_to_pixel_rect(5, 5, -3, -3, 1.0)
        self.assertEqual((w, h), (0, 0))


class ScreenShotCropTest(unittest.TestCase):
    def test_crop_uses_physical_pixels_and_resets_dpr(self):
        pm = QPixmap(200, 100)
        pm.fill(QColor(255, 0, 0))
        pm.setDevicePixelRatio(2.0)  # 200x100 physical == 100x50 logical
        shot = ScreenShot(QRect(0, 0, 100, 50), pm, 2.0)
        out = shot.crop(QRect(10, 10, 20, 20))
        self.assertEqual((out.width(), out.height()), (40, 40))
        self.assertEqual(out.devicePixelRatio(), 1.0)


class OverlayNoScreensTest(unittest.TestCase):
    def test_start_with_no_screens_returns_cleanly(self):
        overlay = Overlay()
        with mock.patch("snip.overlay.grab_all_screens", return_value=[]):
            overlay.start()
        self.assertFalse(overlay.active)


if __name__ == "__main__":
    unittest.main()

import unittest

from tests import qt_support  # noqa: F401  (offscreen setup)
from snip.overlay import EdgeArm, edge_zone

H = 1440
Z = edge_zone(H)


class EdgeArmTest(unittest.TestCase):
    def test_press_in_top_zone_going_down_does_not_fire_top(self):
        a = EdgeArm(60, H)
        self.assertEqual(a.update(60), 0)
        self.assertEqual(a.update(100), 0)
        self.assertEqual(a.update(700), 0)
        self.assertEqual(a.update(1380), 1)

    def test_top_press_returning_to_top_after_leaving_fires_up(self):
        a = EdgeArm(60, H)
        a.update(700)
        self.assertEqual(a.update(30), -1)

    def test_mid_press_to_bottom_fires_down(self):
        a = EdgeArm(500, H)
        self.assertEqual(a.update(900), 0)
        self.assertEqual(a.update(H - 5), 1)

    def test_bottom_press_up_to_top_fires_up(self):
        a = EdgeArm(H - 40, H)
        self.assertEqual(a.update(H - 40), 0)
        self.assertEqual(a.update(600), 0)
        self.assertEqual(a.update(10), -1)

    def test_press_in_bottom_zone_not_armed_for_bottom(self):
        a = EdgeArm(H - 10, H)
        self.assertEqual(a.update(H - 5), 0)


if __name__ == "__main__":
    unittest.main()

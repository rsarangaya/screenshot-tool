"""Stitching logic for edge auto-scroll capture (synthetic images, no Win32)."""
import unittest

from qt_support import get_app

get_app()

from PySide6.QtGui import QImage  # noqa: E402

from snip.scroll_capture import (ADDED, FULL, NOMATCH, SAME, Settler, Stitcher, find_overlap,  # noqa: E402
                                 find_overlap_tolerant, moving_columns, row_hashes, static_bands)

W = 6


def page(rows):
    """Page image where row i has a unique-ish colour derived from rows[i]."""
    img = QImage(W, len(rows), QImage.Format_RGB32)
    for y, v in enumerate(rows):
        for x in range(W):
            img.setPixel(x, y, 0xFF000000 | ((v * 7919 + x) & 0xFFFFFF))
    return img


def window(rows, top, h):
    return page(rows[top:top + h])


class FindOverlapTest(unittest.TestCase):
    def test_known_offset(self):
        a = list(range(20))
        self.assertEqual(find_overlap(a, list(range(5, 25))), 15)

    def test_identical_is_full_overlap(self):
        a = list(range(10))
        self.assertEqual(find_overlap(a, a), 10)

    def test_no_overlap(self):
        self.assertEqual(find_overlap(list(range(10)), list(range(100, 110))), 0)

    def test_repeated_rows_prefers_largest(self):
        self.assertEqual(find_overlap([1] * 10, [1] * 4 + [2] * 6), 4)

    def test_empty(self):
        self.assertEqual(find_overlap([], [1, 2]), 0)


class VoteOverlapTest(unittest.TestCase):
    def test_many_changed_rows_still_match(self):
        prev = list(range(1000, 1300))
        new = prev[100:] + list(range(5000, 5100))  # moved 100 rows
        for i in range(0, 200, 5):  # 20% of overlapping rows differ
            new[i] = -i - 1
        from snip.scroll_capture import find_overlap_vote
        self.assertEqual(find_overlap_vote(prev, new, 30), 200)
        self.assertEqual(find_overlap_vote(prev, list(range(9000, 9300)), 30), 0)


class StitcherTest(unittest.TestCase):
    def setUp(self):
        self.rows = list(range(300))
        self.h = 50

    def _grab(self, top):
        return window(self.rows, top, self.h)

    def test_scroll_down_reconstructs_page(self):
        s = Stitcher(self._grab(0))
        for top in (20, 40, 60, 100, 140):
            self.assertEqual(s.add(self._grab(top)), ADDED)
        self.assertEqual(s.height, 190)
        self.assertEqual(row_hashes(s.result()), row_hashes(window(self.rows, 0, 190)))

    def test_scroll_up_reconstructs_page(self):
        s = Stitcher(self._grab(150), direction=-1)
        for top in (120, 80, 50):
            self.assertEqual(s.add(self._grab(top)), ADDED)
        self.assertEqual(row_hashes(s.result()), row_hashes(window(self.rows, 50, 150)))

    def test_no_movement(self):
        s = Stitcher(self._grab(0))
        self.assertEqual(s.add(self._grab(0)), SAME)
        self.assertEqual(s.height, self.h)

    def test_end_of_page_same_frame(self):
        s = Stitcher(self._grab(0))
        s.add(self._grab(30))
        self.assertEqual(s.add(self._grab(30)), SAME)
        self.assertEqual(s.height, 80)

    def test_jump_too_large_is_nomatch(self):
        s = Stitcher(self._grab(0))
        self.assertEqual(s.add(self._grab(200)), NOMATCH)
        self.assertEqual(s.height, self.h)

    def test_height_cap(self):
        s = Stitcher(self._grab(0), max_height=70)
        self.assertEqual(s.add(self._grab(20)), ADDED)
        self.assertEqual(s.add(self._grab(60)), FULL)
        self.assertEqual(s.height, 70)
        self.assertEqual(s.result().height(), 70)


def sticky(rows, top, h, head, foot, noise=False):
    """Frame of height h: `head` fixed rows on top, `foot` fixed rows at the bottom,
    page rows scrolling in between. Width 256 so column chunks/scrollbar logic apply."""
    w = 256
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(0xFF000000)
    for y in range(h):
        if y < head:
            v = 100000 + y
        elif y >= h - foot:
            v = 200000 + y
        else:
            v = rows[top + y - head]
        for x in range(w):
            img.setPixel(x, y, 0xFF000000 | ((v * 7919 + x) & 0xFFFFFF))
    if noise:
        for y in range(h - foot + 2, h - foot + 12):  # blinking caret in the footer
            img.setPixel(130, y, 0xFFFFFFFF)
        for y in range(h):  # scrollbar column differs
            img.setPixel(250, y, 0xFF000000 | ((top * 31 + y) & 0xFFFFFF))
    return img


class StaticBandsTest(unittest.TestCase):
    def setUp(self):
        self.rows = list(range(400))

    def test_detects_header_and_footer(self):
        a, b = sticky(self.rows, 0, 60, 8, 10), sticky(self.rows, 12, 60, 8, 10)
        self.assertEqual(static_bands(a, b), (8, 10))

    def test_identical_frames_cover_everything(self):
        a = sticky(self.rows, 0, 60, 8, 10)
        self.assertGreaterEqual(static_bands(a, a)[0], 60)

    def test_stitch_with_sticky_bands(self):
        h, head, foot = 60, 8, 10
        s = Stitcher(sticky(self.rows, 0, h, head, foot))
        for top in (12, 24, 36, 48, 60):
            self.assertEqual(s.add(sticky(self.rows, top, h, head, foot)), ADDED)
        mid = h - head - foot
        self.assertEqual(s.height, h + 5 * 12)
        want = [100000 + y for y in range(head)] + self.rows[:mid + 60] + [200000 + y for y in range(h - foot, h)]
        got = row_hashes(s.result())
        ref = row_hashes(page_rows(want))
        self.assertEqual(got, ref)

    def test_noise_tolerated(self):
        h, head, foot = 60, 8, 10
        s = Stitcher(sticky(self.rows, 0, h, head, foot, noise=True))
        for top in (12, 24, 36):
            self.assertEqual(s.add(sticky(self.rows, top, h, head, foot, noise=True)), ADDED)
        self.assertEqual(s.add(sticky(self.rows, 36, h, head, foot, noise=True)), SAME)

    def test_scroll_up_with_bands(self):
        h, head, foot = 60, 8, 10
        s = Stitcher(sticky(self.rows, 100, h, head, foot), direction=-1)
        for top in (88, 76, 64):
            self.assertEqual(s.add(sticky(self.rows, top, h, head, foot)), ADDED)
        self.assertEqual(s.height, h + 36)

    def test_tolerant_overlap(self):
        a = list(range(40))
        b = list(range(10, 50))
        b[3] = -1  # one animated row in the overlap
        self.assertEqual(find_overlap(a, b, 4), 0)
        self.assertEqual(find_overlap_tolerant(a, b, 4), 30)


def page_rows(values):
    img = QImage(256, len(values), QImage.Format_RGB32)
    for y, v in enumerate(values):
        for x in range(256):
            img.setPixel(x, y, 0xFF000000 | ((v * 7919 + x) & 0xFFFFFF))
    return img


class SettlerTest(unittest.TestCase):
    def test_settles_on_two_equal_grabs(self):
        s = Settler(max_ticks=7)
        self.assertFalse(s.feed(1))
        self.assertFalse(s.feed(2))
        self.assertTrue(s.feed(2))
        self.assertFalse(s.timed_out)

    def test_times_out_while_moving(self):
        s = Settler(max_ticks=3)
        self.assertFalse(s.feed(1))
        self.assertFalse(s.feed(2))
        self.assertTrue(s.feed(3))
        self.assertTrue(s.timed_out)

    def test_reset(self):
        s = Settler()
        s.feed(5)
        s.reset()
        self.assertFalse(s.feed(5))


def wide_window(rows, top, h, width=40):
    """Full-width frame; columns 10..19 carry the page rows, the others are
    junk that changes per call (must not influence matching)."""
    img = QImage(width, h, QImage.Format_RGB32)
    for y in range(h):
        for x in range(width):
            v = rows[top + y] * 7919 + x if 10 <= x < 20 else (top * 31 + x * 17 + y) & 0xFFFFFF
            img.setPixel(x, y, 0xFF000000 | (v & 0xFFFFFF))
    return img


class WidthChangeTest(unittest.TestCase):
    def setUp(self):
        self.rows = list(range(300))
        self.h = 50

    def _stitch(self):
        s = Stitcher(wide_window(self.rows, 0, self.h), match=(10, 10))
        for top in (20, 40, 60, 100):
            self.assertEqual(s.add(wide_window(self.rows, top, self.h)), ADDED)
        return s

    def test_match_columns_only(self):
        s = self._stitch()
        self.assertEqual(s.height, 150)
        full = s.result()
        self.assertEqual((full.width(), full.height()), (40, 150))
        for y in (0, 70, 149):
            self.assertEqual(full.pixel(12, y) & 0xFFFFFF, (self.rows[y] * 7919 + 12) & 0xFFFFFF)

    def test_crop_at_end(self):
        s = self._stitch()
        full = s.result()
        for x0, w in ((5, 12), (0, 40), (30, 10), (12, 1)):
            c = s.result(x0, w)
            self.assertEqual((c.width(), c.height()), (w, 150))
            self.assertEqual(c, full.copy(x0, 0, w, 150))

    def test_crop_with_bands(self):
        s = Stitcher(wide_window(self.rows, 0, self.h), match=(10, 10))
        self.assertEqual(s.add(wide_window(self.rows, 20, self.h)), ADDED)
        self.assertEqual(s.result(3, 20), s.result().copy(3, 0, 20, s.height))

    def test_frame_key_columns(self):
        from snip.scroll_capture import frame_key
        a, b = wide_window(self.rows, 0, self.h), wide_window(self.rows, 0, self.h)
        for x in (0, 30, 39):
            b.setPixel(x, 5, 0xFF123456)
        self.assertNotEqual(frame_key(a), frame_key(b))
        self.assertEqual(frame_key(a, 10, 10), frame_key(b, 10, 10))

    def test_span_from(self):
        from snip.scroll_capture import span_from
        self.assertEqual(span_from(100, 100, 1000), (100, 101))   # 1 px minimum
        self.assertEqual(span_from(100, 160, 1000), (100, 161))   # anchor stays left
        self.assertEqual(span_from(100, 40, 1000), (40, 101))     # cursor left of anchor
        self.assertEqual(span_from(100, -50, 1000), (0, 101))     # clamped left
        self.assertEqual(span_from(100, 5000, 1000), (100, 1000))  # clamped right
        self.assertEqual(span_from(999, 5000, 1000), (999, 1000))
        self.assertEqual(span_from(0, -9, 1000), (0, 1))

    def test_span_to_px_and_cap(self):
        from snip.scroll_capture import height_cap, span_to_px
        self.assertEqual(span_to_px(10, 20, 1.25, 100), (12, 13))
        self.assertEqual(span_to_px(0, 1, 1.0, 100), (0, 1))
        self.assertEqual(span_to_px(99, 100, 1.0, 100), (99, 1))
        self.assertEqual(height_cap(500), 30000)
        w = 3440
        self.assertLessEqual(w * 4 * height_cap(w), 400 * 1024 * 1024)
        self.assertGreater(height_cap(w), 25000)
        self.assertEqual(Stitcher(wide_window(self.rows, 0, self.h)).max_height, 30000 if 40 * 4 * 30000 < 400 * 2**20 else 1)


class MovingColumnsTest(unittest.TestCase):
    def frames(self, x0, x1, total=96, h=40):
        """Static background; columns [x0, x1) hold content that shifts by 3 rows."""
        def make(shift):
            img = QImage(total, h, QImage.Format_RGB32)
            img.fill(0xFF202020)
            for y in range(h):
                for x in range(x0, x1):
                    img.setPixel(x, y, 0xFF000000 | (((y + shift) * 7919 + x) & 0xFFFFFF))
            return img
        return make(0), make(3)

    def test_finds_scrolling_block(self):
        a, b = self.frames(48, 96)
        x, w = moving_columns(a, b)
        self.assertEqual((x, x + w), (48, 96))

    def test_limited_to_search_range(self):
        a, b = self.frames(48, 96)
        self.assertEqual(moving_columns(a, b, 0, 80), (48, 32))

    def test_nothing_moves(self):
        a, _ = self.frames(48, 96)
        self.assertIsNone(moving_columns(a, a.copy()))

    def test_too_narrow(self):
        a, b = self.frames(50, 60)
        self.assertIsNone(moving_columns(a, b))

    def test_stitcher_retunes_to_scrolling_columns(self):
        a, b = self.frames(48, 96)
        st = Stitcher(a, 1, match=(0, 96))
        st.add(b)
        self.assertEqual(st.match, (48, 48))



class SpanMinWidthTest(unittest.TestCase):
    def test_vertical_drag_gets_min_width(self):
        from snip.scroll_capture import span_from
        self.assertEqual(span_from(600, 600, 3440, 120), (600, 720))
        self.assertEqual(span_from(3430, 3430, 3440, 120), (3320, 3440))
        self.assertEqual(span_from(600, 900, 3440, 120), (600, 901))
        self.assertEqual(span_from(5, 5, 3440), (5, 6))


if __name__ == "__main__":
    unittest.main()

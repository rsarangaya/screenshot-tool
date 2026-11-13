"""Pure stitching logic for edge auto-scroll capture (no Win32, no widgets)."""
import math

from PySide6.QtGui import QImage, QPainter

CHUNKS = 16  # column chunks per row for near-equal row detection
MAX_HEIGHT = 30000  # px; bounds memory of the stitched result
MAX_BYTES = 400 * 1024 * 1024  # stored frames (full screen width) stay under this


def height_cap(width: int, max_height: int = MAX_HEIGHT, max_bytes: int = MAX_BYTES) -> int:
    """Max stitched height for frames `width` px wide (32-bit pixels)."""
    return max(1, min(max_height, max_bytes // (max(width, 1) * 4)))


def span_from(anchor: int, cursor: int, width: int, min_width: int = 1) -> tuple:
    """Selected x-range [lo, hi) from the press x and the current cursor x,
    clamped to the screen; at least `min_width` px wide (a near-vertical drag
    still gets columns to match on)."""
    lo, hi = min(anchor, cursor), max(anchor, cursor) + 1
    lo, hi = max(lo, 0), min(hi, width)
    if hi <= lo:
        lo = min(max(lo, 0), max(width - 1, 0))
        hi = lo + 1
    if hi - lo < min_width:
        hi = min(lo + min_width, width)
        lo = max(min(lo, hi - min_width), 0)
    return lo, hi


def span_to_px(lo: int, hi: int, dpr: float, img_width: int) -> tuple:
    """Logical x-range -> (x, w) in image pixels (floor/ceil, clamped, w >= 1)."""
    x0 = min(max(math.floor(lo * dpr + 1e-6), 0), max(img_width - 1, 0))
    x1 = min(max(math.ceil(hi * dpr - 1e-6), x0 + 1), img_width)
    return x0, x1 - x0

BLOCK = 16  # column block width (px) for moving-column detection


def moving_columns(prev: QImage, new: QImage, x0: int = 0, w: int = None, min_rows: float = 0.1, min_width: int = 32):
    """(x, w) of the column range inside [x0, x0 + w) whose pixels change between
    two same-size 32-bit frames (the scrolling content), or None when nothing or
    too little moves. A block counts as moving when >= `min_rows` of its rows differ."""
    if prev.size() != new.size():
        return None
    w = prev.width() - x0 if w is None else w
    a, b, h, bpl = _view(prev), _view(new), prev.height(), prev.bytesPerLine()
    need = max(1, int(h * min_rows))
    moving = []
    for bx in range(x0, x0 + w, BLOCK):
        n = min(BLOCK, x0 + w - bx) * 4
        diff = 0
        for y in range(h):
            o = y * bpl + bx * 4
            if a[o:o + n] != b[o:o + n]:
                diff += 1
        if diff >= need:
            moving.append(bx)
    if not moving:
        return None
    lo, hi = moving[0], min(moving[-1] + BLOCK, x0 + w)
    return (lo, hi - lo) if hi - lo >= min_width else None


ADDED, SAME, NOMATCH, FULL = "added", "same", "nomatch", "full"


def _view(img: QImage):
    return memoryview(img.constBits())  # no copy; caller keeps img alive


def row_hashes(img: QImage, ignore_right: int = 0, x0: int = 0, w: int = None) -> list:
    """One hash per pixel row (img must be a 32-bit format), over columns
    [x0, x0 + w) (default: all). The rightmost `ignore_right` pixels of that
    range (scrollbar column) are left out of the hash."""
    bpl, h = img.bytesPerLine(), img.height()
    data = _view(img)
    w = img.width() - x0 if w is None else w
    n = max(w - ignore_right, 1) * 4
    return [hash(data[y * bpl + x0 * 4:y * bpl + x0 * 4 + n]) for y in range(h)]


def _row_sigs(img: QImage, ignore_right: int, chunks: int = CHUNKS, x0: int = 0, w: int = None) -> list:
    """Per-row tuple of chunk hashes, so rows differing in a few pixels (caret)
    can still be recognised as nearly equal."""
    bpl, h = img.bytesPerLine(), img.height()
    data = _view(img)
    w = max((img.width() - x0 if w is None else w) - ignore_right, 1)
    chunks = chunks if w >= chunks * 4 else 1
    cw = (w // chunks) * 4
    o = x0 * 4
    return [tuple(hash(data[y * bpl + o + c * cw:y * bpl + o + (c + 1) * cw]) for c in range(chunks)) for y in range(h)]


def static_bands(prev: QImage, new: QImage, ignore_right: int = 0, x0: int = 0, w: int = None) -> tuple:
    """(top, bottom) row counts that are (nearly) identical in two frames of the
    same size: sticky header/footer. top >= height means no movement at all."""
    if prev.size() != new.size():
        return 0, 0
    a, b = _row_sigs(prev, ignore_right, CHUNKS, x0, w), _row_sigs(new, ignore_right, CHUNKS, x0, w)
    tol = 2 if len(a[0]) > 1 else 0 if a else 0

    def same(x, y):
        return sum(p != q for p, q in zip(x, y)) <= tol

    h = len(a)
    top = 0
    while top < h and same(a[top], b[top]):
        top += 1
    bottom = 0
    while bottom < h - top and same(a[h - 1 - bottom], b[h - 1 - bottom]):
        bottom += 1
    return top, bottom


def find_overlap(prev, new, min_overlap: int = 4) -> int:
    """Largest k >= min_overlap with prev[-k:] == new[:k] (row hashes), else 0.
    k == len(new) == len(prev) means the frames are identical (no movement)."""
    if not prev or not new:
        return 0
    first = new[0]
    for k in range(min(len(prev), len(new)), max(min_overlap, 1) - 1, -1):
        if prev[-k] == first and prev[-k:] == new[:k]:
            return k
    return 0


def find_overlap_tolerant(prev, new, min_overlap: int = 4, frac: float = 0.03) -> int:
    """Like find_overlap but allows a small fraction of differing rows (animated
    caret, hover highlight inside the moving area)."""
    if not prev or not new:
        return 0
    for k in range(min(len(prev), len(new)), max(min_overlap, 1) - 1, -1):
        allowed = max(1, int(k * frac))
        bad = 0
        base = len(prev) - k
        for i in range(k):
            if prev[base + i] != new[i]:
                bad += 1
                if bad > allowed:
                    break
        else:
            return k
    return 0


def find_overlap_vote(prev, new, min_overlap: int = 4, frac: float = 0.7) -> int:
    """Like find_overlap but robust to many locally changed rows (fading edges,
    hover/animated text in real apps): rows whose hash is rare vote for a shift;
    the winning shift is accepted if >= `frac` of the overlapping rows match."""
    if not prev or not new:
        return 0
    where = {}
    for i, hv in enumerate(prev):
        where.setdefault(hv, []).append(i)
    votes = {}
    for j, hv in enumerate(new):
        idx = where.get(hv)
        if idx is not None and len(idx) <= 2:
            for i in idx:
                votes[i - j] = votes.get(i - j, 0) + 1
    best, nv = None, 0
    for sh, v in votes.items():
        k = min(len(prev) - sh, len(new))
        if sh >= 0 and k >= min_overlap and v > nv:
            best, nv = sh, v
    if best is None or nv < 8:
        return 0
    k = min(len(prev) - best, len(new))
    good = sum(1 for i in range(k) if prev[best + i] == new[i])
    return k if good >= k * frac else 0


def frame_key(img: QImage, x0: int = 0, w: int = None) -> int:
    """Cheap identity of a frame's pixels (for settle detection); only columns
    [x0, x0 + w) are hashed when given."""
    if x0 or (w is not None and w < img.width()):
        img = img.copy(x0, 0, img.width() - x0 if w is None else w, img.height())
    return hash(_view(img))


class Settler:
    """Decides when a page has stopped moving after a wheel step: two consecutive
    grabs with the same key, or `max_ticks` grabs (smooth scrolling cap)."""

    def __init__(self, max_ticks: int = 7):
        self.max_ticks = max_ticks
        self.reset()

    def reset(self):
        self._last, self._ticks = None, 0

    def feed(self, key) -> bool:
        """True when settled (call reset() before the next wheel step).
        `timed_out` tells the cap case apart from a real settle."""
        self._ticks += 1
        same = key == self._last
        self._last = key
        self.timed_out = not same and self._ticks >= self.max_ticks
        return same or self.timed_out

    timed_out = False


class Stitcher:
    """Accumulates same-width frames of a fixed screen column into one tall image.
    direction +1: page scrolls down (append); -1: scrolls up (prepend).
    Sticky header/footer bands are detected once and kept a single time.
    Frames may be wider than the columns used for matching: `match=(x0, w)`
    restricts overlap detection to those columns (default: the whole frame)."""

    def __init__(self, first: QImage, direction: int = 1, max_height: int = None, match: tuple = None):
        first = self._fmt(first)
        self.direction = 1 if direction >= 0 else -1
        self._width = first.width()
        self.max_height = height_cap(self._width) if max_height is None else max_height
        self._mx, self._mw = match if match else (0, self._width)
        self._ign = 24 if self._mw >= 200 else 0
        self._first_strip = first.copy()
        self._strips = [self._first_strip]  # [0] is the whole first frame, cropped by bands in result()
        self._height = first.height()
        self._prev = first
        self._prev_h = row_hashes(first, self._ign, self._mx, self._mw)
        self._bands = None  # (top, bottom) once locked
        self._retuned = False
        self.last_ratio = 0.0  # overlap / moving height of the last stitched frame

    @staticmethod
    def _fmt(img):
        return img if img.format() == QImage.Format_RGB32 else img.convertToFormat(QImage.Format_RGB32)

    @property
    def match(self) -> tuple:
        """Columns (x, w) in px used for overlap matching."""
        return self._mx, self._mw

    @property
    def height(self) -> int:
        return self._height

    def add(self, frame: QImage) -> str:
        """Returns ADDED, SAME (page did not move), NOMATCH (no overlap) or FULL
        (height cap reached; the part that fits was still added)."""
        frame = self._fmt(frame)
        h = frame.height()
        if frame.width() != self._width or h != self._prev.height():
            return NOMATCH
        if self._bands is None and not self._retuned:
            mc = moving_columns(self._prev, frame, self._mx, self._mw)
            if mc:  # first moved frame: match on the columns that really scroll
                self._retuned = True
                if mc != (self._mx, self._mw):
                    self._mx, self._mw = mc
                    self._ign = 24 if self._mw >= 200 else 0
                    self._prev_h = row_hashes(self._prev, self._ign, self._mx, self._mw)
        new_h = row_hashes(frame, self._ign, self._mx, self._mw)
        locked = self._bands is not None
        t, b = self._bands if locked else static_bands(self._prev, frame, self._ign, self._mx, self._mw)
        if not locked and (t >= h - 1 or t + b >= h):
            return SAME
        if h - t - b < h // 3:
            t = b = 0
        mh = h - t - b
        pm, nm = self._prev_h[t:t + mh], new_h[t:t + mh]
        min_ov = max(4, mh // 10)
        find = find_overlap if self.direction > 0 else (lambda p, n, m: find_overlap(n, p, m))
        findt = find_overlap_tolerant if self.direction > 0 else (lambda p, n, m: find_overlap_tolerant(n, p, m))
        findv = find_overlap_vote if self.direction > 0 else (lambda p, n, m: find_overlap_vote(n, p, m))
        k = find(pm, nm, min_ov) or findt(pm, nm, min_ov) or findv(pm, nm, min_ov)
        if k == 0:
            return NOMATCH
        if k >= mh:
            return SAME
        self._bands = (t, b)
        self.last_ratio = k / mh
        n = mh - k
        room = self.max_height - self._height
        full = n > room
        if full:
            n = room
        if n > 0:
            if self.direction > 0:
                self._strips.append(frame.copy(0, t + k, self._width, n))
            else:
                self._strips.insert(0, frame.copy(0, t + mh - k - n, self._width, n))
            self._height += n
        self._prev, self._prev_h = frame, new_h
        return FULL if full else ADDED

    def result(self, x0: int = 0, w: int = None) -> QImage:
        """The stitched image, cropped to columns [x0, x0 + w) (default: all)."""
        w = self._width - x0 if w is None else w
        t, b = self._bands or (0, 0)
        h = self._prev.height()
        out = QImage(w, self._height, QImage.Format_RGB32)
        p = QPainter(out)
        y = t
        for s in self._strips:
            if s is self._first_strip:
                s = s.copy(0, t, self._width, h - t - b)
            p.drawImage(0, y, s, x0, 0, w, s.height())
            y += s.height()
        if t:
            p.drawImage(0, 0, self._prev, x0, 0, w, t)
        if b:
            p.drawImage(0, self._height - b, self._prev, x0, h - b, w, b)
        p.end()
        return out

"""Fullscreen dim overlay (one frameless window per screen) with drag-select."""
import os
import tempfile
import time

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from . import capture
from .capture import ScreenShot, grab_all_screens
from .scroll_capture import FULL, NOMATCH, SAME, Settler, Stitcher, frame_key, span_from, span_to_px

MIN_DRAG = 3
MIN_SCROLL_W = 120  # min selection width (logical px) once auto-scroll starts: a vertical drag still needs columns to match
_DIM = QColor(0, 0, 0, 110)
_BORDER = QPen(QColor(255, 255, 255), 1)
_LABEL_BG = QColor(0, 0, 0, 200)
_MARGIN = 60  # repaint padding to cover the size label
POLL_MS = 12  # cursor poll while the button is down (backs up lost mouse-move events)
EDGE_ZONE = 40  # min px at the top/bottom screen border that triggers auto-scroll
EDGE_FRAC = 0.08  # ...or this fraction of the screen height (a bottom-docked chat box counts as the edge)


def edge_zone(h: int) -> int:
    return max(EDGE_ZONE, round(h * EDGE_FRAC))
class EdgeArm:
    """Hysteresis for edge auto-scroll: an edge fires only after the cursor has been
    outside that edge's zone since the press, so a drag that starts inside a zone
    (e.g. an app header at the top) can extend away from it first."""

    def __init__(self, press_y: int, h: int):
        self.h = h
        self.zone = edge_zone(h)
        self.top_armed = press_y > self.zone
        self.bottom_armed = press_y < h - self.zone

    def update(self, y: int) -> int:
        """Feed the cursor y; returns 1 (bottom fires), -1 (top fires) or 0."""
        in_top = y <= self.zone
        in_bottom = y >= self.h - self.zone
        if not in_top:
            self.top_armed = True
        if not in_bottom:
            self.bottom_armed = True
        if in_bottom and self.bottom_armed:
            return 1
        if in_top and self.top_armed:
            return -1
        return 0


TICK_MS = 60  # scroll step interval; the timer only runs during a scroll capture
WHEEL_DELTA = 120  # one wheel notch per step
STALL_LIMIT = 3  # consecutive settled, unchanged frames = end of page
MAX_NOTCHES = 6  # adaptive wheel notches per step (overlap kept 30-65% of the frame)
_KEY = QColor(255, 0, 255)  # click-through colour key while scrolling
_KEY_BGR = 0xFF00FF
_SCROLL_BORDER = QPen(QColor(0, 0, 0), 3)
_DEBUG_LOG = (os.path.join(tempfile.gettempdir(), "snip_scroll.log")
              if os.environ.get("SNIP_DEBUG") == "1" else None)


def _dlog(msg):
    """Opt-in scroll diagnostics (SNIP_DEBUG=1); no-op otherwise."""
    if _DEBUG_LOG:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


class _ScreenOverlay(QWidget):
    def __init__(self, shot: ScreenShot, owner: "Overlay"):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self._shot = shot
        self._owner = owner
        self._start = None
        self._arm = None
        self._poll = None  # QTimer, only running while a drag is in progress
        self._sel = QRect()
        self._font = QFont("Segoe UI", 9)
        self.scrolling = False  # scroll-capture mode: live view, only border + hint drawn
        self.hint = ""
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setCursor(Qt.CrossCursor)
        self.setGeometry(shot.geometry)

    def paintEvent(self, ev):
        p = QPainter(self)
        r = ev.rect()
        if self.scrolling:
            p.fillRect(r, _KEY)
            if not self._sel.isNull():
                s = self._sel
                p.setPen(_SCROLL_BORDER)
                p.drawRect(s.adjusted(-2, -2, 1, 1))
                p.setPen(_BORDER)
                p.drawRect(s.adjusted(-1, -1, 0, 0))
                self._draw_label(p, s, self.hint)
            return
        # Pixmap carries its dpr, so logical coords map 1:1 to physical pixels.
        p.drawPixmap(r, self._shot.pixmap, QRect(r.topLeft() * self._shot.dpr, r.size() * self._shot.dpr))
        p.fillRect(r, _DIM)
        if not self._sel.isNull():
            s = self._sel
            p.drawPixmap(s, self._shot.pixmap, QRect(s.topLeft() * self._shot.dpr, s.size() * self._shot.dpr))
            p.setPen(_BORDER)
            p.drawRect(s.adjusted(0, 0, -1, -1))
            self._draw_label(p, s)

    def _draw_label(self, p, s, text=None):
        if text is None:
            w = round(s.width() * self._shot.dpr)
            h = round(s.height() * self._shot.dpr)
            text = f"{w} x {h}"
        p.setFont(self._font)
        tr = p.fontMetrics().boundingRect(text).adjusted(-6, -3, 6, 3)
        y = s.bottom() + 6
        if y + tr.height() > self.height():
            y = s.top() - tr.height() - 6
        tr.moveTo(max(s.left(), 0), max(y, 0))
        p.fillRect(tr, _LABEL_BG)
        p.setPen(Qt.white)
        p.drawText(tr, Qt.AlignCenter, text)

    def _dirty(self, r):
        return r.adjusted(-_MARGIN, -_MARGIN, _MARGIN, _MARGIN) if not r.isNull() else r

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._start = ev.position().toPoint()
            self._arm = EdgeArm(self._start.y(), self.height())
            if self._poll is None:
                self._poll = QTimer(self)
                self._poll.setInterval(POLL_MS)
                self._poll.timeout.connect(self._poll_cursor)
            self._poll.start()
        elif ev.button() == Qt.RightButton:
            self._owner.cancel()

    def _end_drag(self):
        self._start = None
        if self._poll is not None:
            self._poll.stop()

    def _poll_cursor(self):
        """Selection follows the real cursor even if Qt stops delivering moves
        (mouse capture lost, touch/pen input, window not yet active)."""
        if self._start is None:
            self._end_drag()
        elif capture.key_down(capture.VK_LBUTTON):
            self._drag_to(self.mapFromGlobal(QCursor.pos()))

    def mouseMoveEvent(self, ev):
        if self._start is not None:
            self._drag_to(ev.position().toPoint())

    def _drag_to(self, pos, allow_scroll=True):
        new = QRect(self._start, pos).normalized().intersected(self.rect())
        if new != self._sel:
            self.update(self._dirty(self._sel.united(new)))
            self._sel = new
        if self._arm is None:
            self._arm = EdgeArm(self._start.y(), self.height())
        fire = self._arm.update(pos.y())  # always feed, so arming tracks the whole drag
        if fire and allow_scroll and self._owner.scroll_ok and new.height() >= MIN_DRAG:
            anchor = self._start.x()
            self._end_drag()
            self._owner.begin_scroll(self, new, fire, anchor)

    def enter_scroll(self, sel):
        self.scrolling = True
        self._sel = sel
        self.hint = "scrolling..."
        hwnd = int(self.winId())
        capture.set_click_through(hwnd, _KEY_BGR)
        self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton or self._start is None:
            return
        self._drag_to(ev.position().toPoint(), allow_scroll=False)  # last position, even if moves were coalesced
        sel = self._sel
        self._end_drag()
        if sel.width() < MIN_DRAG or sel.height() < MIN_DRAG:
            self._owner.cancel()
        else:
            self._owner.finish(self._shot, sel)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self._owner.cancel()


class Overlay:
    """Controller: grab, show on all screens, crop + clipboard + editor on release."""

    def __init__(self):
        self._windows: list[_ScreenOverlay] = []
        self.scroll_ok = False
        self._timer = None
        self._stitch = None
        self._scroll = None  # (screen, full-width grab rect, direction, screen top)
        self._win = None  # overlay window showing the live selection
        self._anchor = 0  # press x (logical, window coords); the cursor x sets the other edge
        self._span = (0, 1)  # selected x-range [lo, hi), logical
        self._match = (0, 1)  # match columns (physical px) = the originally selected columns
        self._wheel_pt = None
        self._narrow = QRect()
        self._pending = False
        self._stalls = 0
        self._stopped = False
        self._notches = 1
        self._settle = Settler()
        self.on_done = None  # optional callback when the overlay closes

    @property
    def active(self) -> bool:
        return bool(self._windows)

    def start(self):
        if self._windows:
            return
        shots = grab_all_screens()  # before any window is shown
        for shot in shots:
            w = _ScreenOverlay(shot, self)
            self._windows.append(w)
            w.show()
        if not self._windows:
            if self.on_done is not None:
                self.on_done()
            return
        # Auto-scroll needs overlays hidden from screen grabs; otherwise stay off.
        self.scroll_ok = all(capture.exclude_from_capture(int(w.winId())) for w in self._windows)
        if _DEBUG_LOG:
            _dlog(f"START screens={len(self._windows)} scroll_ok={self.scroll_ok}")
        # Focus the screen under the cursor so Esc works immediately.
        pos = QCursor.pos()
        target = next((w for w in self._windows if w._shot.geometry.contains(pos)), self._windows[0])
        target.raise_()
        target.activateWindow()
        target.setFocus()

    def begin_scroll(self, win, sel: QRect, direction: int, anchor: int = None):
        screen = next((s for s in QGuiApplication.screens() if s.geometry() == win._shot.geometry), None)
        if screen is None:
            self.scroll_ok = False
            return
        # Grab the full screen width for the selected rows: the width stays adjustable
        # while scrolling; overlap matching only looks at the originally selected columns.
        lo, hi = span_from(sel.left(), sel.right(), win.width(), MIN_SCROLL_W)
        sel = QRect(lo, sel.y(), hi - lo, sel.height())
        full = QRect(0, sel.y(), win.width(), sel.height())
        first = capture.grab_region(screen, full)
        self._match = span_to_px(sel.left(), sel.right() + 1, win._shot.dpr, first.width())
        self._anchor = sel.left() if anchor is None else anchor
        self._span = (sel.left(), sel.right() + 1)
        self._win = win
        if _DEBUG_LOG:
            _dlog(f"BEGIN dir={direction} sel={sel} geom={win._shot.geometry} dpr={win._shot.dpr} first={first.width()}x{first.height()} match={self._match}")
        self.scroll_ok = False
        self._stitch = Stitcher(first, direction, match=self._match)
        self._wheel_pt = QRect(sel).center()
        self._cand = 0  # which fallback wheel x is being tried
        self._wheel_x = None  # logical x of the scrolling columns once known
        self._narrow = QRect(sel)  # logical rect of the match columns (cheap settle grabs)
        self._scroll = (screen, full, direction, win._shot.geometry.top())
        self._pending, self._stalls, self._stopped = False, 0, False
        self._notches = 1
        self._settle.reset()
        capture.release_mouse_capture()  # let the wheel reach the window below
        for w in self._windows:
            w.enter_scroll(QRect(sel) if w is win else QRect())
        if self._timer is None:
            self._timer = QTimer()
            self._timer.setInterval(TICK_MS)
            self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        if self._scroll is None:
            return
        if capture.key_down(capture.VK_ESCAPE):
            self.cancel()
            return
        if not capture.key_down(capture.VK_LBUTTON):
            self._finish_scroll()
            return
        self._update_span()
        if self._stopped:
            return
        screen, rect, direction, top = self._scroll
        if self._pending:
            # Settle on the cheap narrow grab (match columns); grab full width once settled.
            if not self._settle.feed(frame_key(capture.grab_region(screen, self._narrow))):
                if _DEBUG_LOG:
                    _dlog(f"  moving: tick={self._settle._ticks}")
                return  # page still moving (smooth scrolling): grab again next tick
            self._pending = False
            if self._settle.timed_out:
                st = SAME  # never settled (animation/video): skip frame, counts as a stall
            else:
                st = self._stitch.add(capture.grab_region(screen, rect))
            if self._stitch.match != self._match and st != NOMATCH:
                self._match = self._stitch.match  # scrolling columns found: aim the wheel there
                self._wheel_x = round((self._match[0] + self._match[1] / 2) / self._win._shot.dpr)
            if _DEBUG_LOG:
                _dlog(f"STEP st={st} timed_out={self._settle.timed_out} settle_ticks={self._settle._ticks} notches={self._notches} "
                      f"stalls={self._stalls} bands={self._stitch._bands} ratio={self._stitch.last_ratio:.2f} "
                      f"height={self._stitch.height}")
            if st == NOMATCH and self._notches > 1:
                # Jumped too far for the frames to overlap: undo and use a smaller step.
                self._wheel(screen, self._notches * direction)
                self._notches = max(1, self._notches // 2)
                self._pending = True
                self._settle.reset()
                return
            self._stalls = self._stalls + 1 if st == SAME else 0
            if st == SAME and self._wheel_x is None and self._stitch._bands is None and self._cand < 2:
                self._cand += 1  # nothing ever moved: the wheel probably missed the scroller
                self._stalls = 0
            if st == "added":
                r = self._stitch.last_ratio
                if r > 0.65 and self._notches < MAX_NOTCHES:
                    self._notches += 1
                elif r < 0.3 and self._notches > 1:
                    self._notches -= 1
            if st in (NOMATCH, FULL) or self._stalls >= STALL_LIMIT:
                self._stopped = True
                if _DEBUG_LOG:
                    _dlog(f"STOPPED reason={st} stalls={self._stalls} height={self._stitch.height}")
            self._refresh_hint()
            if self._stopped:
                return
        y = QCursor.pos().y() - top
        h = screen.geometry().height()
        if (direction > 0 and y >= h - edge_zone(h)) or (direction < 0 and y <= edge_zone(h)):
            self._wheel(screen, -self._notches * direction)
            self._settle.reset()
            self._pending = True

    def _update_span(self):
        """Cursor x sets the free edge of the selection while scrolling."""
        win = self._win
        if win is None:
            return
        cx = QCursor.pos().x() - win._shot.geometry.left()
        span = span_from(self._anchor, cx, win.width(), MIN_SCROLL_W)
        if span != self._span:
            self._span = span
            self._refresh_hint()

    def _refresh_hint(self):
        win, st = self._win, self._stitch
        if win is None or st is None:
            return
        lo, hi = self._span
        sel = QRect(lo, win._sel.y(), hi - lo, win._sel.height())
        old = win._sel
        win.hint = (f"{round((hi - lo) * win._shot.dpr)} x {st.height} px - release to finish" if self._stopped
                    else f"{round((hi - lo) * win._shot.dpr)} x {st.height} px scrolling...")
        win._sel = sel
        win.update(win._dirty(old.united(sel)))

    def _wheel(self, screen, notches):
        """Wheel over the selected content (the screen's last pixel row is the
        taskbar/hot edge and swallows it); the cursor is restored right after."""
        old = QCursor.pos()
        geo = screen.geometry()
        # Aim at the scrolling content, not the selection centre (which may sit over
        # a non-scrolling area): the scrolling columns, else the cursor's x.
        x = self._wheel_x
        if x is None:  # not known yet: try the cursor x, then the press x, then the centre
            x = (old.x() - geo.left(), self._anchor, self._wheel_pt.x())[self._cand % 3]
        x = min(max(x, 0), geo.width() - 1)
        y = self._wheel_pt.y()
        pt = geo.topLeft() + QPoint(x, y)
        if _DEBUG_LOG:
            _dlog(f"  wheel notches={notches} at={pt}")
        QCursor.setPos(pt)
        capture.send_wheel(WHEEL_DELTA * notches)
        QCursor.setPos(old)

    def _finish_scroll(self):
        self._update_span()
        lo, hi = self._span
        x, w = span_to_px(lo, hi, self._win._shot.dpr, self._stitch._width)
        img = self._stitch.result(x, w)  # stored frames are full width; crop to the final x-range
        if _DEBUG_LOG:
            _dlog(f"FINISH height={self._stitch.height}")
            img.save(_DEBUG_LOG.replace("scroll.log", "result.png"))
        self._finish_pixmap(QPixmap.fromImage(img))

    def _close_all(self):
        if self._timer is not None:
            self._timer.stop()
        self._scroll = self._stitch = self._win = None
        wins, self._windows = self._windows, []
        for w in wins:
            w.close()
        if wins and self.on_done is not None:
            self.on_done()

    def cancel(self):
        self._close_all()

    def finish(self, shot: ScreenShot, sel: QRect):
        self._finish_pixmap(shot.crop(sel))

    def _finish_pixmap(self, pm):
        QGuiApplication.clipboard().setPixmap(pm)
        self._close_all()
        QTimer.singleShot(0, lambda: self._open_editor(pm))

    def _open_editor(self, pm):
        from snip.editor import open_editor  # lazy: editor may not exist yet
        open_editor(pm)


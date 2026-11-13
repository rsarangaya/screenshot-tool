"""Screen grab (all monitors) and DPI-correct cropping."""
import math
from dataclasses import dataclass

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QImage, QPixmap


def logical_to_pixel_rect(x, y, w, h, dpr):
    """Logical (device-independent) rect relative to a screen -> physical pixel
    rect (x, y, w, h). Origin floors, far edge ceils, so the selection is never
    clipped on fractional scales."""
    px0 = math.floor(x * dpr + 1e-6)
    py0 = math.floor(y * dpr + 1e-6)
    px1 = math.ceil((x + w) * dpr - 1e-6)
    py1 = math.ceil((y + h) * dpr - 1e-6)
    return px0, py0, max(px1 - px0, 0), max(py1 - py0, 0)


@dataclass
class ScreenShot:
    geometry: QRect  # logical, virtual-desktop coordinates
    pixmap: QPixmap  # physical pixels; devicePixelRatio set to the screen's
    dpr: float

    def crop(self, rect: QRect) -> QPixmap:
        """rect is logical, relative to this screen's top-left."""
        x, y, w, h = logical_to_pixel_rect(rect.x(), rect.y(), rect.width(), rect.height(), self.dpr)
        out = self.pixmap.copy(QRect(x, y, w, h))
        out.setDevicePixelRatio(1.0)
        return out


def grab_all_screens() -> list[ScreenShot]:
    """Grab every monitor at native resolution. Call BEFORE showing the overlay.
    Each screen keeps its own dpr, so mixed-DPI setups stay sharp."""
    shots = []
    for screen in QGuiApplication.screens():
        pm = screen.grabWindow(0)
        shots.append(ScreenShot(screen.geometry(), pm, pm.devicePixelRatio() or screen.devicePixelRatio()))
    return shots


# --- Win32 helpers for edge auto-scroll (Windows only; lazy ctypes) ---------

def grab_region(screen, rect: QRect) -> QImage:
    """Live grab of a logical, screen-relative rect as a 32-bit QImage (dpr 1)."""
    img = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height()).toImage()
    img.setDevicePixelRatio(1.0)
    return img.convertToFormat(QImage.Format_RGB32)


def _user32():
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    u.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    u.SetWindowDisplayAffinity.restype = wintypes.BOOL
    u.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    u.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    u.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    u.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD]
    return u


def exclude_from_capture(hwnd: int) -> bool:
    """WDA_EXCLUDEFROMCAPTURE; False if unsupported (then auto-scroll is disabled)."""
    try:
        return bool(_user32().SetWindowDisplayAffinity(hwnd, 0x11))
    except Exception:
        return False


def set_click_through(hwnd: int, color_key_bgr: int) -> bool:
    """Layered + transparent window; pixels of color_key_bgr (0x00BBGGRR) become
    see-through, everything else is visible but ignores the mouse."""
    try:
        u = _user32()
        ex = u.GetWindowLongPtrW(hwnd, -20)
        u.SetWindowLongPtrW(hwnd, -20, ex | 0x80000 | 0x20)  # LAYERED | TRANSPARENT
        return bool(u.SetLayeredWindowAttributes(hwnd, color_key_bgr, 0, 0x1))  # LWA_COLORKEY
    except Exception:
        return False


def release_mouse_capture():
    import ctypes
    ctypes.windll.user32.ReleaseCapture()


def key_down(vk: int) -> bool:
    import ctypes
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


VK_LBUTTON, VK_ESCAPE = 0x01, 0x1B


def send_wheel(delta: int):
    """Inject a mouse-wheel event at the current cursor position."""
    import ctypes
    from ctypes import wintypes

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.c_size_t)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT)]

    inp = INPUT(0, MOUSEINPUT(0, 0, delta & 0xFFFFFFFF, 0x0800, 0, 0))  # MOUSEEVENTF_WHEEL
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

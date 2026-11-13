"""Global hotkey via Win32 RegisterHotKey; WM_HOTKEY arrives on the Qt thread."""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

# Change the hotkey here. Modifiers: any of "ctrl", "shift", "alt", "win".
HOTKEY_MODIFIERS = ("ctrl", "shift")
HOTKEY_KEY = "S"  # single letter/digit

_MODS = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "win": 0x8}
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY = 0x0312
_HOTKEY_ID = 0x5A11
_MSG_OFFSET = ctypes.sizeof(ctypes.c_void_p)  # MSG.message follows hwnd

_user32 = ctypes.windll.user32
_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]


class HotkeyListener(QAbstractNativeEventFilter, QObject):
    triggered = Signal()

    def __init__(self, parent=None):
        QAbstractNativeEventFilter.__init__(self)
        QObject.__init__(self, parent)
        self._registered = False

    def register(self) -> bool:
        mods = _MOD_NOREPEAT
        for m in HOTKEY_MODIFIERS:
            mods |= _MODS[m]
        self._registered = bool(
            _user32.RegisterHotKey(None, _HOTKEY_ID, mods, ord(HOTKEY_KEY.upper()))
        )
        return self._registered

    def unregister(self):
        if self._registered:
            _user32.UnregisterHotKey(None, _HOTKEY_ID)
            self._registered = False

    def nativeEventFilter(self, event_type, message):
        # Hot path: runs for every native message, keep it minimal.
        if event_type == b"windows_generic_MSG":
            if ctypes.c_uint.from_address(int(message) + _MSG_OFFSET).value == _WM_HOTKEY:
                self.triggered.emit()
                return True, 0
        return False, 0

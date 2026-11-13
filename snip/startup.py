"""'Start with Windows' via the HKCU Run registry value (default OFF)."""
import sys

try:
    import winreg
except ImportError:  # non-Windows
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Snip"


def command() -> str:
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        exe = exe[:-10] + "pythonw.exe"  # no console window
    return f'"{exe}" -m snip'


def is_enabled(key_path: str = RUN_KEY, name: str = VALUE_NAME) -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            winreg.QueryValueEx(k, name)
            return True
    except OSError:
        return False


def set_enabled(on: bool, key_path: str = RUN_KEY, name: str = VALUE_NAME) -> bool:
    if winreg is None:
        return False
    try:
        if on:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0,
                                    winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, command())
        else:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name)
        return True
    except FileNotFoundError:
        return not on  # nothing to delete is success
    except OSError:
        return False

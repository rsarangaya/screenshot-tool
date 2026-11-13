"""Persistent user settings (QSettings). Helpers accept a QSettings for testing."""
from pathlib import Path

from PySide6.QtCore import QSettings

_FOLDER = "save_folder"


def _s(s=None) -> QSettings:
    return s if s is not None else QSettings("Snip", "Snip")


def default_folder() -> str:
    return str(Path.home() / "Pictures")


def get_save_folder(s=None) -> str:
    return str(_s(s).value(_FOLDER, "") or default_folder())


def set_save_folder(path: str, s=None) -> None:
    _s(s).setValue(_FOLDER, path)

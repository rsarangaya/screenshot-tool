"""Headless tests: settings round trip, startup registry helper, single instance."""
import os
import tempfile
import unittest
import uuid
from unittest import mock

from tests.qt_support import get_app, make_editor

from PySide6.QtCore import QSettings

from snip import settings, startup, single_instance


class SettingsTest(unittest.TestCase):
    def test_round_trip_and_default(self):
        with tempfile.TemporaryDirectory() as d:
            s = QSettings(os.path.join(d, "t.ini"), QSettings.Format.IniFormat)
            self.assertEqual(settings.get_save_folder(s), settings.default_folder())
            settings.set_save_folder(d, s)
            self.assertEqual(settings.get_save_folder(s), d)
            del s


class StartupTest(unittest.TestCase):
    def test_enable_disable_with_private_key(self):
        if startup.winreg is None:
            self.skipTest("winreg unavailable")
        key = r"Software\SnipToolTest" + uuid.uuid4().hex
        try:
            self.assertFalse(startup.is_enabled(key))
            self.assertTrue(startup.set_enabled(True, key))
            self.assertTrue(startup.is_enabled(key))
            self.assertTrue(startup.set_enabled(False, key))
            self.assertFalse(startup.is_enabled(key))
        finally:
            try:
                startup.winreg.DeleteKey(startup.winreg.HKEY_CURRENT_USER, key)
            except OSError:
                pass

    def test_default_off_and_no_winreg(self):
        with mock.patch.object(startup, "winreg", None):
            self.assertFalse(startup.is_enabled())
            self.assertFalse(startup.set_enabled(True))

    def test_command_quotes_module(self):
        self.assertTrue(startup.command().endswith('" -m snip'))


class SingleInstanceTest(unittest.TestCase):
    def test_second_launch_notifies_first(self):
        get_app()
        name = "SnipTest" + uuid.uuid4().hex
        self.assertFalse(single_instance.notify_existing(name, 50))
        srv = single_instance.InstanceServer(name)
        self.assertTrue(srv.ok)
        hits = []
        srv.activated.connect(lambda: hits.append(1))
        self.assertTrue(single_instance.notify_existing(name, 500))
        from tests.qt_support import flush
        flush(10)
        self.assertEqual(hits, [1])


class EditorShellTest(unittest.TestCase):
    def test_new_hook_called(self):
        from snip import editor
        ed = make_editor()
        calls = []
        with mock.patch.object(editor, "new_capture_hook", calls.append):
            ed.act_new.trigger()
        self.assertEqual(calls, [ed])

    def test_close_with_edits_asks(self):
        from PySide6.QtWidgets import QMessageBox
        from snip.tools.commands import CallbackCommand
        ed = make_editor()
        ed.confirm_unsaved = True
        ed.stack.push(CallbackCommand("x", lambda: None, lambda: None))
        B = QMessageBox.StandardButton
        with mock.patch.object(QMessageBox, "question", return_value=B.Cancel) as q:
            self.assertFalse(ed.close())
            q.assert_called_once()
        with mock.patch.object(QMessageBox, "question", return_value=B.Discard):
            self.assertTrue(ed.close())

    def test_save_clears_dirty_and_never_auto_saves(self):
        ed = make_editor()
        self.assertTrue(ed.stack.isClean())
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(os.listdir(d), [])
            self.assertTrue(ed.save(os.path.join(d, "a.png")))
            self.assertEqual(os.listdir(d), ["a.png"])


if __name__ == "__main__":
    unittest.main()

"""Exercise the installed desktop entry-point's platform/fallback selection."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from litmetica3d import desktop


class DesktopEntryPointTests(unittest.TestCase):
    def test_windows_wheel_without_winui_launches_qt(self):
        launch_qt = Mock(return_value=23)
        with patch.object(desktop.sys, 'platform', 'win32'), \
                patch.object(desktop.sys, 'frozen', False, create=True), \
                patch.object(desktop.Path, 'is_file', return_value=False), \
                patch.dict('sys.modules', {'litmetica3d.gui_app': SimpleNamespace(launch_gui=launch_qt)}):
            self.assertEqual(23, desktop.launch_gui())
        launch_qt.assert_called_once_with()

    def test_built_winui_is_preferred_on_windows(self):
        with patch.object(desktop.sys, 'platform', 'win32'), \
                patch.object(desktop.sys, 'frozen', False, create=True), \
                patch.object(desktop.Path, 'is_file', return_value=True), \
                patch.object(desktop.subprocess, 'call', return_value=0) as call:
            self.assertEqual(0, desktop.launch_gui())
        self.assertTrue(call.call_args.args[0][0].endswith('Litmetica3D.WinUI.exe'))

    def test_linux_and_frozen_windows_use_qt(self):
        for platform, frozen in [('linux', False), ('win32', True)]:
            with self.subTest(platform=platform, frozen=frozen):
                launch_qt = Mock(return_value=0)
                with patch.object(desktop.sys, 'platform', platform), \
                        patch.object(desktop.sys, 'frozen', frozen, create=True), \
                        patch.dict('sys.modules', {'litmetica3d.gui_app': SimpleNamespace(launch_gui=launch_qt)}):
                    self.assertEqual(0, desktop.launch_gui())
                launch_qt.assert_called_once_with()

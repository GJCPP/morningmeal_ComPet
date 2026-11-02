"""Check overlay lifetime and native Windows task-switcher styles in isolation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OverlayWindowTests(unittest.TestCase):
    def run_probe(self, platform):
        probe = textwrap.dedent("""
            import ctypes
            import os
            import sys
            from unittest.mock import patch
            from PyQt6.QtCore import Qt
            from PyQt6.QtWidgets import QApplication

            with patch('os.path.expanduser', return_value=os.environ['COMPET_TEST_PROFILE']):
                from core.config_manager import config_mgr
                if os.environ['QT_QPA_PLATFORM'] == 'cocoa':
                    import main  # Install the production Cocoa compatibility path.
            app = QApplication([])
            from ui.pet_widget import PetWidget
            from ui.timer_widget import TimerWidget
            from ui.settings.main_window import MainSettingWindow
            settings = MainSettingWindow()

            native_windows = sys.platform == 'win32' and os.environ['QT_QPA_PLATFORM'] == 'windows'
            if native_windows:
                user32 = ctypes.WinDLL('user32', use_last_error=True)
                get_style = user32.GetWindowLongPtrW
                get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
                get_style.restype = ctypes.c_ssize_t
                get_root = user32.GetAncestor
                get_root.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                get_root.restype = ctypes.c_void_p

            for tray_mode in (False, True):
                for click_through in (False, True):
                    config_mgr.config['settings'].update(tray_mode=tray_mode, click_through=click_through)
                    pet = PetWidget(dict(config_mgr.config['pets'][0]), lambda: [], lambda: None, lambda _: None, lambda _: None)
                    timer = TimerWidget(dict(config_mgr.config['timers'][0]), lambda: [], lambda _: None, lambda: None)
                    overlays = (pet, timer)
                    for widget in overlays:
                        widget.show()
                    app.processEvents()
                    assert not pet.idle_pixmap.isNull()
                    # A visible settings window must not replace or hide overlays.
                    settings.show()
                    app.processEvents()
                    settings.close()
                    app.processEvents()
                    assert all(widget.isVisible() for widget in overlays)
                    for widget in overlays:
                        widget.update_window_flags()
                        widget.show()
                    app.processEvents()
                    for widget in overlays:
                        assert widget.isVisible()
                        assert widget.windowType() == Qt.WindowType.Tool
                        assert widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
                        if native_windows:
                            # Check the native top-level HWND, not just Qt's requested flags.
                            hwnd = get_root(int(widget.winId()), 2)  # GA_ROOT
                            assert hwnd
                            style = get_style(hwnd, -20)  # GWL_EXSTYLE
                            assert style & 0x80, hex(style)  # WS_EX_TOOLWINDOW excludes Alt+Tab.
                            assert not style & 0x40000, hex(style)  # WS_EX_APPWINDOW forces taskbar.
                    assert bool(pet.windowFlags() & Qt.WindowType.WindowTransparentForInput) == click_through
                    assert not timer.windowFlags() & Qt.WindowType.WindowTransparentForInput
                    assert settings.windowType() == Qt.WindowType.Window
                    for widget in overlays:
                        widget.close()
                        widget.deleteLater()
                    app.processEvents()
            settings.deleteLater()
            print('Overlay visibility, settings access, and switcher exclusion: passed')
        """)
        with tempfile.TemporaryDirectory(prefix='compet-overlay-test-') as profile:
            env = os.environ.copy()
            env.update(COMPET_TEST_PROFILE=profile, USERPROFILE=profile,
                       QT_QPA_PLATFORM=platform, PYTHONUTF8='1',
                       PYTHONPATH=str(ROOT / 'morningmeal_Compet_V3'))
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', probe],
                                    cwd=ROOT, env=env, capture_output=True,
                                    text=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_overlays_with_legacy_and_tray_profiles(self):
        self.run_probe(os.environ.get('COMPET_QT_TEST_PLATFORM', 'offscreen'))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native HWND styles')
    def test_windows_native_switcher_exclusion(self):
        self.run_probe('windows')

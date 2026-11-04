"""Recover real Windows overlay ordering without changing focus or settings."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'win32', 'Windows native z-order recovery')
class WindowsOverlayRecoveryTests(unittest.TestCase):
    def test_native_order_recovers_without_activation(self):
        probe = textwrap.dedent(r"""
            import ctypes, os, subprocess, sys
            from unittest.mock import patch
            from PyQt6.QtCore import Qt
            from PyQt6.QtWidgets import QApplication, QWidget
            app = QApplication([])
            with patch('os.path.expanduser', return_value=os.environ['COMPET_TEST_PROFILE']):
                from core.config_manager import config_mgr
            from ui.pet_widget import PetWidget
            from core.windows_overlay import NativeWindowOrder, OverlayRecovery, install
            pet = PetWidget(dict(config_mgr.config['pets'][0]), lambda: [], lambda: None, None, None)
            pet.show()
            settings = QWidget()
            settings.show()
            app.processEvents()
            native = NativeWindowOrder()
            native.user32.SetWindowPos.argtypes = [ctypes.c_void_p,ctypes.c_void_p,
                ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint]
            assert not native.needs_raise(int(pet.winId()), int(settings.winId()))
            # A separate process supplies an ordinary foreground-window stand-in.
            peer_code = "import sys\nfrom PyQt6.QtCore import Qt, QTimer\nfrom PyQt6.QtWidgets import QApplication, QWidget\napp=QApplication([])\nwindow=QWidget()\nwindow.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)\nif sys.argv[1]=='topmost':window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True)\nwindow.resize(160,80)\nwindow.show()\napp.processEvents()\nprint(int(window.winId()),flush=True)\nQTimer.singleShot(15000,app.quit)\napp.exec()\n"
            peers = []
            try:
                for kind in ('normal','topmost'):
                    peer = subprocess.Popen([sys.executable,'-u','-c',peer_code,kind],
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                    peers.append(peer)
                    handle = int(peer.stdout.readline().strip())
                    native.user32.SetWindowPos(int(pet.winId()),1,0,0,0,0,0x13)
                    app.processEvents()
                    if kind == 'topmost':
                        assert not native.needs_raise(int(pet.winId()),handle)
                        continue
                    original_check = native.needs_raise
                    assert original_check(int(pet.winId()),handle), 'Expected overlay below ordinary window'
                    # Use the peer as foreground without activating it or sending user input.
                    native.needs_raise = lambda target: original_check(target,handle)
                    recovery = OverlayRecovery(app,native)
                    recovery.timer.stop()
                    before = native.user32.GetForegroundWindow()
                    before_geometry = pet.geometry().getRect()
                    recovery.recover()
                    app.processEvents()
                    after = native.user32.GetForegroundWindow()
                    assert before == after, 'Recovery stole foreground focus'
                    assert pet.geometry().getRect() == before_geometry
                    assert not original_check(int(pet.winId()),handle)
                    assert native.get_style(int(pet.winId()),-20) & 0x8
                    assert native.get_style(int(pet.winId()),-20) & 0x80
                    assert not pet.idle_pixmap.isNull()
                    native.needs_raise = original_check
                installed = install(app)
                assert install(app) is installed
                installed.timer.stop()
                pet.hide()
                with patch.object(installed.native,'restore_topmost') as raised:
                    installed.recover()
                    assert not raised.called
            finally:
                for peer in peers:
                    if peer.poll() is None:
                        peer.terminate()
                    peer.wait(timeout=5)
                    peer.stdout.close()
                    peer.stderr.close()
                pet.close()
                settings.close()
        """)
        with tempfile.TemporaryDirectory(prefix='compet-zorder-test-') as profile:
            env = os.environ.copy()
            env.update(COMPET_TEST_PROFILE=profile,USERPROFILE=profile,QT_QPA_PLATFORM='windows',
                       PYTHONUTF8='1',PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'))
            result = subprocess.run([sys.executable,'-X','utf8','-c',probe],env=env,cwd=ROOT,
                capture_output=True,text=True,encoding='utf-8',timeout=35)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

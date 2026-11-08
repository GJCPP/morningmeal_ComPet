"""Settings must stay hidden until an explicit entry, independent of activation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class SettingsVisibilityTests(unittest.TestCase):
    def test_explicit_open_close_minimize_and_private_bounded_diagnostics(self):
        probe=r'''
import os,json,ast,sys
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication,QSystemTrayIcon
from PyQt6.QtCore import QEvent
from PyQt6.QtTest import QTest
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
with patch('os.path.expanduser',return_value=os.environ['COMPET_TEST_PROFILE']):
 from core.config_manager import config_mgr
from core.interaction_fixes import install
install()
from ui.settings.main_window import MainSettingWindow
from core.settings_visibility import SettingsVisibilityGuard
window=MainSettingWindow();path=Path(os.environ['COMPET_TEST_PROFILE'])/'events.json'
guard=SettingsVisibilityGuard(window,path)
window.show();app.processEvents();assert not window.isVisible()
for source in ('tray-menu','timer-menu','pet-menu'):
 guard.open(source);app.processEvents();assert window.isVisible()
 QTest.mouseClick(window.title_bar.close_btn,__import__('PyQt6.QtCore',fromlist=['Qt']).Qt.MouseButton.LeftButton)
 app.processEvents();assert not window.isVisible() and not guard.requested
 QApplication.sendEvent(window,QEvent(QEvent.Type.WindowActivate))
 window.show();app.processEvents();assert not window.isVisible()
guard.open('tray-menu');app.processEvents();window.showMinimized();app.processEvents()
assert not window.isVisible() and not guard.requested
window.showNormal();app.processEvents();assert not window.isVisible()
guard.open('pet-menu');app.processEvents();assert window.isVisible()
for i in range(105):guard.record('test')
entries=json.loads(path.read_text());assert len(entries)==100
assert all(set(e)<= {'time','event','source'} for e in entries)
# Windows stat mode bits do not describe POSIX permissions or NTFS ACLs.
if os.name != 'nt':
 assert path.stat().st_mode & 0o777 == 0o600
# Exercise the actual tray callback without launching input listeners.
module=ast.parse((Path(os.environ['COMPET_SOURCE'])/'main.py').read_text(encoding='utf-8'))
cls=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='MorningmealComPetApp')
method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='on_tray_activated')
ns={'sys':sys,'QSystemTrayIcon':QSystemTrayIcon};exec(compile(ast.Module(body=[method],type_ignores=[]),'<tray>','exec'),ns)
class Fake:
 def __init__(self):self.calls=0
 def show_settings(self):self.calls+=1
fake=Fake()
for reason in QSystemTrayIcon.ActivationReason:
 with patch.object(sys,'platform','darwin'):ns['on_tray_activated'](fake,reason)
assert fake.calls==0
guard.detach();window.close()
print('PASS: unsolicited show/activation and minimize restore blocked; explicit menus work; diagnostics contain no user input')
'''
        with tempfile.TemporaryDirectory(prefix='compet-settings-visibility-') as profile:
            env=os.environ.copy();env.update(COMPET_TEST_PROFILE=profile,COMPET_SOURCE=str(ROOT/'morningmeal_Compet_V3'),PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'),QT_QPA_PLATFORM=os.environ.get('COMPET_QT_TEST_PLATFORM','offscreen'))
            result=subprocess.run([sys.executable,'-c',probe],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
